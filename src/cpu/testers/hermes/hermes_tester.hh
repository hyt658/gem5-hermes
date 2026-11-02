#ifndef __CPU_TESTERS_HERMES_HERMES_TESTER_HH__
#define __CPU_TESTERS_HERMES_HERMES_TESTER_HH__

#include <string>
#include <unordered_map>
#include <vector>

#include "base/statistics.hh"
#include "mem/packet.hh"
#include "mem/port.hh"
#include "params/HermesTester.hh"
#include "sim/clocked_object.hh"
#include "sim/eventq.hh"

namespace gem5
{

/**
 * The HermesTester replays a fixed script of regular reads, regular
 * writes and Hermes requests against a memory controller. This makes it
 * possible to test the memory controller on exact request orderings,
 * without a core or a cache hierarchy.
 */
class HermesTester : public ClockedObject
{

  public:

    typedef HermesTesterParams Params;
    HermesTester(const Params &p);

    Port &getPort(const std::string &if_name,
                  PortID idx=InvalidPortID) override;

    void startup() override;

  protected:

    class TesterPort : public RequestPort
    {
        HermesTester &tester;

        /** Set on the Hermes port, which must never get a response */
        const bool hermes;

      public:

        TesterPort(const std::string &_name, HermesTester &_tester,
                   bool _hermes)
            : RequestPort(_name), tester(_tester), hermes(_hermes)
        { }

      protected:

        bool recvTimingResp(PacketPtr pkt) override;

        void recvReqRetry() override;
    };

    TesterPort port;

    TesterPort hermesPort;

    const std::vector<Tick> opTicks;
    const std::vector<std::string> opTypes;
    const std::vector<Addr> opAddrs;

    /** Index of the next request to send */
    size_t nextOp;

    /** Request refused by the regular port, waiting for a retry */
    PacketPtr retryPkt;

    /** Number of regular reads sent so far */
    size_t readsSent;

    /** Position in the script of each outstanding regular read */
    std::unordered_map<PacketPtr, size_t> readIndex;

    const unsigned blockSize;

    /** Request ids for the regular and the Hermes traffic */
    const RequestorID requestorId;
    const RequestorID hermesRequestorId;

    /** Send every request that is due, then wait for the next one */
    void sendOps();

    EventFunctionWrapper sendEvent;

    PacketPtr makePacket(MemCmd cmd, Addr addr, RequestorID id);

    void sendHermes(Addr addr);

    void sendRegular(MemCmd cmd, Addr addr);

    void recvResponse(PacketPtr pkt);

    void recvRetry();

    struct TesterStats : public statistics::Group
    {
        TesterStats(statistics::Group *parent);
        statistics::Scalar hermesSent;
        statistics::Scalar regularSent;
        statistics::Scalar regularResponses;
        statistics::Vector readLatency;
    } stats;
};

} // namespace gem5

#endif // __CPU_TESTERS_HERMES_HERMES_TESTER_HH__
