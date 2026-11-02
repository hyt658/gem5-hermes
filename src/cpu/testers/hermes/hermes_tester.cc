#include "cpu/testers/hermes/hermes_tester.hh"

#include <algorithm>
#include <cstring>
#include <memory>

#include "base/logging.hh"
#include "base/trace.hh"
#include "debug/HermesTester.hh"
#include "mem/request.hh"
#include "sim/system.hh"

namespace gem5
{

bool
HermesTester::TesterPort::recvTimingResp(PacketPtr pkt)
{
    panic_if(hermes, "%s got a response to a Hermes request: %s\n", name(),
             pkt->print());

    tester.recvResponse(pkt);
    return true;
}

void
HermesTester::TesterPort::recvReqRetry()
{
    panic_if(hermes, "%s got a retry, Hermes requests are never refused\n",
             name());

    tester.recvRetry();
}

HermesTester::HermesTester(const Params &p)
    : ClockedObject(p),
      port("port", *this, false),
      hermesPort("hermes_port", *this, true),
      opTicks(p.op_ticks),
      opTypes(p.op_types),
      opAddrs(p.op_addrs),
      nextOp(0),
      retryPkt(nullptr),
      readsSent(0),
      blockSize(p.system->cacheLineSize()),
      requestorId(p.system->getRequestorId(this)),
      hermesRequestorId(p.system->getRequestorId(this, "hermes")),
      sendEvent([this]{ sendOps(); }, name()),
      stats(this)
{
    fatal_if(opTicks.size() != opTypes.size() ||
             opTicks.size() != opAddrs.size(),
             "%s: op_ticks, op_types and op_addrs differ in length\n", name());

    for (size_t i = 1; i < opTicks.size(); i++) {
        fatal_if(opTicks[i] < opTicks[i - 1],
                 "%s: op_ticks must be sorted\n", name());
    }

    // a statistics vector can't be empty
    size_t num_reads = std::count(opTypes.begin(), opTypes.end(), "read");
    stats.readLatency.init(std::max<size_t>(num_reads, 1));
}

Port &
HermesTester::getPort(const std::string &if_name, PortID idx)
{
    if (if_name == "port")
        return port;
    else if (if_name == "hermes_port")
        return hermesPort;
    else
        return ClockedObject::getPort(if_name, idx);
}

void
HermesTester::startup()
{
    if (!opTicks.empty())
        schedule(sendEvent, opTicks.front());
}

void
HermesTester::sendOps()
{
    while (!retryPkt && nextOp < opTicks.size() &&
           opTicks[nextOp] <= curTick()) {
        const std::string &type = opTypes[nextOp];
        const Addr addr = opAddrs[nextOp];
        nextOp++;

        if (type == "hermes")
            sendHermes(addr);
        else if (type == "read")
            sendRegular(MemCmd::ReadReq, addr);
        else if (type == "write")
            sendRegular(MemCmd::WriteReq, addr);
        else
            fatal("%s: unknown request type %s\n", name(), type);
    }

    // a blocked script resumes from recvRetry instead
    if (!retryPkt && nextOp < opTicks.size())
        schedule(sendEvent, opTicks[nextOp]);
}

PacketPtr
HermesTester::makePacket(MemCmd cmd, Addr addr, RequestorID id)
{
    Request::Flags flags;
    RequestPtr req = std::make_shared<Request>(addr, blockSize, flags, id);
    return new Packet(req, cmd);
}

void
HermesTester::sendHermes(Addr addr)
{
    DPRINTF(HermesTester, "Sending Hermes request to %#x\n", addr);

    PacketPtr pkt = makePacket(MemCmd::HermesReadReq, addr,
                               hermesRequestorId);

    panic_if(!hermesPort.sendTimingReq(pkt),
             "%s: Hermes request was refused\n", name());

    stats.hermesSent++;
}

void
HermesTester::sendRegular(MemCmd cmd, Addr addr)
{
    DPRINTF(HermesTester, "Sending %s to %#x\n", cmd.toString(), addr);

    PacketPtr pkt = makePacket(cmd, addr, requestorId);
    pkt->allocate();

    if (pkt->isWrite())
        std::memset(pkt->getPtr<uint8_t>(), 0xa5, blockSize);
    else
        readIndex[pkt] = readsSent++;

    stats.regularSent++;

    if (!port.sendTimingReq(pkt))
        retryPkt = pkt;
}

void
HermesTester::recvResponse(PacketPtr pkt)
{
    DPRINTF(HermesTester, "Got %s for %#x\n", pkt->cmdString(),
            pkt->getAddr());

    stats.regularResponses++;

    if (pkt->isRead()) {
        stats.readLatency[readIndex.at(pkt)] = curTick() - pkt->req->time();
        readIndex.erase(pkt);
    }

    delete pkt;
}

void
HermesTester::recvRetry()
{
    assert(retryPkt);

    if (port.sendTimingReq(retryPkt)) {
        retryPkt = nullptr;
        sendOps();
    }
}

HermesTester::TesterStats::TesterStats(statistics::Group *parent)
    : statistics::Group(parent),
      ADD_STAT(hermesSent, statistics::units::Count::get(),
               "Number of Hermes requests sent"),
      ADD_STAT(regularSent, statistics::units::Count::get(),
               "Number of regular requests sent"),
      ADD_STAT(regularResponses, statistics::units::Count::get(),
               "Number of responses to regular requests"),
      ADD_STAT(readLatency, statistics::units::Tick::get(),
               "Latency of each regular read, in script order")
{
}

} // namespace gem5
