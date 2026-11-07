import argparse

import m5
from m5.objects import *

parser = argparse.ArgumentParser()
parser.add_argument("binary")
parser.add_argument(
    "--hermes",
    action="store_true",
    help="Send a Hermes request for every eligible load",
)
parser.add_argument(
    "--issue-latency",
    type=int,
    default=6,
    help="Hermes issue latency in cycles, 6 for Hermes-O and 18 for Hermes-P",
)
args = parser.parse_args()


def make_cache(size, assoc, latency, mshrs):
    # Like ChampSim, a request pays the latency of a level on its way down, so
    # an LLC miss reaches the memory controller only after all of them
    return Cache(
        size=size,
        assoc=assoc,
        tag_latency=latency,
        data_latency=latency,
        response_latency=1,
        mshrs=mshrs,
        tgts_per_mshr=20,
    )


system = System()
system.clk_domain = SrcClockDomain(
    clock="4GHz", voltage_domain=VoltageDomain()
)
system.mem_mode = "timing"
system.mem_ranges = [AddrRange("2GB")]

# Core parameters from Table 4 of the Hermes paper
system.cpu = X86O3CPU(
    fetchWidth=6,
    decodeWidth=6,
    renameWidth=6,
    dispatchWidth=6,
    issueWidth=6,
    wbWidth=6,
    commitWidth=6,
    squashWidth=6,
    numROBEntries=512,
    numIQEntries=256,
    LQEntries=128,
    SQEntries=72,
    numPhysIntRegs=768,
    numPhysFloatRegs=768,
)

# Latencies are picked to give the 5, 15 and 55 cycle round trips of Table 4
system.l1i = make_cache("32kB", 8, 4, 16)
system.l1d = make_cache("48kB", 12, 4, 16)
system.l2 = make_cache("1280kB", 20, 8, 48)
system.l3 = make_cache("3MB", 12, 36, 64)

system.l2bus = L2XBar()
system.l3bus = L2XBar()
system.membus = SystemXBar()

system.cpu.icache_port = system.l1i.cpu_side
system.cpu.dcache_port = system.l1d.cpu_side
system.l1i.mem_side = system.l2bus.cpu_side_ports
system.l1d.mem_side = system.l2bus.cpu_side_ports
system.l2.cpu_side = system.l2bus.mem_side_ports
system.l2.mem_side = system.l3bus.cpu_side_ports
system.l3.cpu_side = system.l3bus.mem_side_ports
system.l3.mem_side = system.membus.cpu_side_ports

system.cpu.createInterruptController()
system.cpu.interrupts[0].pio = system.membus.mem_side_ports
system.cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports
system.cpu.interrupts[0].int_responder = system.membus.mem_side_ports
system.system_port = system.membus.cpu_side_ports

system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR4_2400_8x8(range=system.mem_ranges[0])
system.mem_ctrl.port = system.membus.mem_side_ports

if args.hermes:
    system.cpu.enable_hermes = True
    system.cpu.hermes_issue_latency = args.issue_latency
    system.cpu.hermes_port = system.mem_ctrl.hermes_port

system.workload = SEWorkload.init_compatible(args.binary)
system.cpu.workload = Process(cmd=[args.binary], output="program.out")
system.cpu.createThreads()

root = Root(full_system=False, system=system)
m5.instantiate()

event = m5.simulate()
print(f"Exiting @ tick {m5.curTick()} because {event.getCause()}")
