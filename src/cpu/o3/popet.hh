/*
 * POPET: perceptron-based off-chip load predictor from Hermes
 * (Bera et al., MICRO 2022). Ported from the authors' ChampSim code
 * (src/perc_pred.cc, src/offchip_pred_perc.cc, config/ocp_hermes.ini).
 */

#ifndef __CPU_O3_POPET_HH__
#define __CPU_O3_POPET_HH__

#include <cstdint>
#include <deque>
#include <string>
#include <vector>

#include "base/statistics.hh"
#include "base/types.hh"
#include "cpu/o3/dyn_inst_ptr.hh"

namespace gem5
{

struct BaseO3CPUParams;

namespace o3
{

class Popet
{
  public:
    /** Features enabled in ocp_hermes.ini (5,8,9,11,16). */
    enum Feature
    {
        PC_Offset = 0,          // PC + cacheline index within the page
        PC_FirstAccess,         // PC + first access to that line
        Offset_FirstAccess,     // cacheline index + first access
        PC_CLOffset,            // PC + byte offset within the cacheline
        LastNLoadPCs,           // signature of the last N load PCs
        NumFeatures
    };

    Popet(statistics::Group *parent, const BaseO3CPUParams &params,
          const std::string &name);

    std::string name() const { return _name; }

    /**
     * Push a load PC into the in-order history (called at LQ insert) and
     * return the signature to snapshot in the instruction.
     */
    uint64_t recordLoadPC(Addr pc);

    /** Predict one load; fills the popet* fields of the instruction. */
    bool predict(const DynInstPtr &inst, Addr vaddr);

    /** Train with the label collected while the load executed. */
    void train(const DynInstPtr &inst);

  private:
    struct PageBufEntry
    {
        Addr page;
        uint64_t accessed;      // one bit per cacheline in the page
    };

    /** Page buffer lookup; returns true on the first access to a line. */
    bool lookupPageBuffer(Addr vpage, unsigned line);

    void updateWeights(const uint16_t *idx, int delta);

    const std::string _name;

    const int actThreshold;
    const int posTrainThreshold;
    const int negTrainThreshold;
    const int maxWeight;
    const int minWeight;
    const unsigned pageBufSets;
    const unsigned pageBufAssoc;
    const unsigned lastNLoadPCs;

    std::vector<int8_t> weights[NumFeatures];
    /** Each set is kept in LRU order, MRU at the back. */
    std::vector<std::deque<PageBufEntry>> pageBuffer;
    std::deque<Addr> loadPCHistory;

    struct PopetStats : public statistics::Group
    {
        PopetStats(statistics::Group *parent);

        statistics::Scalar predictions;
        statistics::Scalar predictedOffchip;
        statistics::Scalar trained;
        statistics::Scalar truePos;
        statistics::Scalar falsePos;
        statistics::Scalar falseNeg;
        statistics::Scalar trueNeg;
        statistics::Scalar weightUpdates;
        statistics::Scalar pageBufHits;
        statistics::Formula accuracy;
        statistics::Formula coverage;
    } stats;
};

} // namespace o3
} // namespace gem5

#endif // __CPU_O3_POPET_HH__
