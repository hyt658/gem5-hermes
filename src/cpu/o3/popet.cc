/*
 * POPET: perceptron-based off-chip load predictor from Hermes
 * (Bera et al., MICRO 2022). Ported from the authors' ChampSim code.
 */

#include "cpu/o3/popet.hh"

#include <algorithm>

#include "base/trace.hh"
#include "cpu/o3/dyn_inst.hh"
#include "debug/POPET.hh"
#include "params/BaseO3CPU.hh"

namespace gem5
{

namespace o3
{

namespace
{

constexpr unsigned LogBlockSize = 6;    // 64B lines
constexpr unsigned LogPageSize = 12;    // 4KB pages

static_assert(sizeof(DynInst::popetIdx) ==
              Popet::NumFeatures * sizeof(uint16_t),
              "DynInst::popetIdx must hold one index per POPET feature");

/** Weight table sizes from ocp_hermes.ini, same order as Popet::Feature. */
constexpr unsigned WeightTableSize[Popet::NumFeatures] =
    {1024, 1024, 128, 1024, 1024};

/** util.cc folded_xor(value, 2): xor the two 32-bit halves. */
uint32_t
foldedXor(uint64_t value)
{
    return (uint32_t)value ^ (uint32_t)(value >> 32);
}

/** util.cc HashZoo::jenkins, i.e. hash type 2 used by ocp_hermes.ini. */
uint32_t
jenkins(uint32_t key)
{
    key += (key << 12);
    key ^= (key >> 22);
    key += (key << 4);
    key ^= (key >> 9);
    key += (key << 10);
    key ^= (key >> 2);
    key += (key << 7);
    key ^= (key >> 12);
    return key;
}

/** HashZoo::fnv1a64: 32-bit FNV-1a over the 8 bytes of key. */
uint32_t
fnv1a(uint64_t key)
{
    uint32_t hash = 0x811C9DC5;
    for (int i = 0; i < 8; i++) {
        hash = ((uint8_t)(key >> (8 * i)) ^ hash) * 0x01000193;
    }
    return hash;
}

} // anonymous namespace

Popet::Popet(statistics::Group *parent, const BaseO3CPUParams &params,
             const std::string &name)
    : _name(name),
      actThreshold(params.popetActThreshold),
      posTrainThreshold(params.popetPosTrainThreshold),
      negTrainThreshold(params.popetNegTrainThreshold),
      maxWeight(params.popetMaxWeight),
      minWeight(params.popetMinWeight),
      pageBufSets(params.popetPageBufSets),
      pageBufAssoc(params.popetPageBufAssoc),
      lastNLoadPCs(params.popetLastNLoadPCs),
      pageBuffer(params.popetPageBufSets),
      stats(parent)
{
    for (int f = 0; f < NumFeatures; f++) {
        weights[f].assign(WeightTableSize[f], 0);
    }
}

uint64_t
Popet::recordLoadPC(Addr pc)
{
    if (loadPCHistory.size() >= lastNLoadPCs) {
        loadPCHistory.pop_front();
    }
    loadPCHistory.push_back(pc);

    uint64_t sig = 0;
    for (Addr p : loadPCHistory) {
        sig <<= 1;
        sig ^= p;
    }
    return sig;
}

bool
Popet::lookupPageBuffer(Addr vpage, unsigned line)
{
    auto &set = pageBuffer[fnv1a(vpage) % pageBufSets];
    auto it = std::find_if(set.begin(), set.end(),
            [vpage](const PageBufEntry &e) { return e.page == vpage; });

    if (it != set.end()) {
        PageBufEntry entry = *it;
        bool first = !(entry.accessed & (1ULL << line));
        entry.accessed |= 1ULL << line;
        set.erase(it);
        set.push_back(entry);
        stats.pageBufHits++;
        return first;
    }

    if (set.size() >= pageBufAssoc) {
        set.pop_front();
    }
    set.push_back({vpage, 1ULL << line});
    return true;
}

bool
Popet::predict(const DynInstPtr &inst, Addr vaddr)
{
    // Naming follows the ChampSim code: "voffset" is the cacheline index
    // within the page, "v_cl_offset" is the byte offset within the line.
    const Addr vpage = vaddr >> LogPageSize;
    const uint32_t line = (vaddr >> LogBlockSize) &
        ((1u << (LogPageSize - LogBlockSize)) - 1);
    const uint32_t cl_offset = vaddr & ((1u << LogBlockSize) - 1);
    const uint32_t fpc = foldedXor(inst->pcState().instAddr());
    const bool first = lookupPageBuffer(vpage, line);

    uint32_t key[NumFeatures];
    key[PC_Offset] = (fpc << 6) + line;
    key[PC_FirstAccess] = (fpc & 0x7fffffffu) | ((uint32_t)first << 31);
    key[Offset_FirstAccess] = (line & 0x3f) | ((uint32_t)first << 6);
    key[PC_CLOffset] = (fpc << 6) + cl_offset;
    key[LastNLoadPCs] = foldedXor(inst->popetLoadPCSig);

    int sum = 0;
    for (int f = 0; f < NumFeatures; f++) {
        inst->popetIdx[f] = jenkins(key[f]) % WeightTableSize[f];
        sum += weights[f][inst->popetIdx[f]];
    }

    const bool pred = sum >= actThreshold;
    inst->popetPredicted = true;
    inst->popetPredOffchip = pred;
    inst->popetSum = sum;

    stats.predictions++;
    if (pred) {
        stats.predictedOffchip++;
    }

    DPRINTF(POPET, "predict [sn:%llu] pc=%#x vaddr=%#x first=%d sum=%d "
            "pred=%d\n", inst->seqNum, inst->pcState().instAddr(), vaddr,
            first, sum, pred);
    return pred;
}

void
Popet::updateWeights(const uint16_t *idx, int delta)
{
    for (int f = 0; f < NumFeatures; f++) {
        int w = weights[f][idx[f]] + delta;
        if (w <= maxWeight && w >= minWeight) {
            weights[f][idx[f]] = w;
        }
    }
    stats.weightUpdates++;
}

void
Popet::train(const DynInstPtr &inst)
{
    const bool pred = inst->popetPredOffchip;
    const bool actual = inst->wentOffchip;

    stats.trained++;
    if (pred && actual) stats.truePos++;
    else if (pred && !actual) stats.falsePos++;
    else if (!pred && actual) stats.falseNeg++;
    else stats.trueNeg++;

    // perc_pred.cc: always train on a misprediction; on a correct one,
    // only while the sum is still inside [negTrain, posTrain].
    const bool unsaturated = inst->popetSum >= negTrainThreshold &&
                             inst->popetSum <= posTrainThreshold;
    if (pred != actual || unsaturated) {
        updateWeights(inst->popetIdx, actual ? 1 : -1);
    }

    DPRINTF(POPET, "train [sn:%llu] pc=%#x sum=%d pred=%d actual=%d\n",
            inst->seqNum, inst->pcState().instAddr(), inst->popetSum,
            pred, actual);
}

Popet::PopetStats::PopetStats(statistics::Group *parent)
    : statistics::Group(parent, "popet"),
      ADD_STAT(predictions, statistics::units::Count::get(),
               "Number of loads POPET made a prediction for"),
      ADD_STAT(predictedOffchip, statistics::units::Count::get(),
               "Number of loads predicted to go off-chip"),
      ADD_STAT(trained, statistics::units::Count::get(),
               "Number of committed loads used for training"),
      ADD_STAT(truePos, statistics::units::Count::get(),
               "Committed loads predicted off-chip that went off-chip"),
      ADD_STAT(falsePos, statistics::units::Count::get(),
               "Committed loads predicted off-chip that stayed on-chip"),
      ADD_STAT(falseNeg, statistics::units::Count::get(),
               "Committed loads predicted on-chip that went off-chip"),
      ADD_STAT(trueNeg, statistics::units::Count::get(),
               "Committed loads predicted on-chip that stayed on-chip"),
      ADD_STAT(weightUpdates, statistics::units::Count::get(),
               "Number of training events that changed the weights"),
      ADD_STAT(pageBufHits, statistics::units::Count::get(),
               "Number of page buffer hits"),
      ADD_STAT(accuracy, statistics::units::Ratio::get(),
               "TP / (TP + FP)", truePos / (truePos + falsePos)),
      ADD_STAT(coverage, statistics::units::Ratio::get(),
               "TP / (TP + FN)", truePos / (truePos + falseNeg))
{
}

} // namespace o3
} // namespace gem5
