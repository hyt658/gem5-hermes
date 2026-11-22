import argparse
import sys

import m5
from m5.objects import *

PREFETCHERS = {
    "stride": StridePrefetcher,
    "bop": BOPPrefetcher,
    "spp": SignaturePathPrefetcher,
}


class DDR4_3200_8x8(DDR4_2400_8x8):
    tCK = "0.625ns"
    tBURST = "2.5ns"
    tRCD = "12.5ns"
    tCL = "12.5ns"
    tRP = "12.5ns"
    tRRD = "2.5ns"
    tRTW = "1.25ns"
    tCS = "1.25ns"


class DDR4_6400_8x8(DDR4_3200_8x8):
    tCK = "0.3125ns"
    tBURST = "1.25ns"
    tCCD_L = "2.5ns"
    tRRD = "1.25ns"
    tRRD_L = "2.45ns"
    tXAW = "10.5ns"
    tRTW = "0.625ns"
    tCS = "0.625ns"


class DDR4_3200_8x8_1R8B(DDR4_3200_8x8):
    ranks_per_channel = 1
    banks_per_rank = 8
    bank_groups_per_rank = 2


DRAMS = {
    "ddr4_2400": DDR4_2400_8x8,
    "ddr4_3200": DDR4_3200_8x8,
    "ddr4_3200_1r8b": DDR4_3200_8x8_1R8B,
    "ddr4_6400": DDR4_6400_8x8,
}

# the atomic CPU only runs for a few hundred instructions in each switch
ATOMIC_TICKS = 100 * 1000

# exit causes of m5.simulate()
MAX_INSTS = "a thread reached the max instruction count"
LIMIT_REACHED = "simulate() limit reached"
WARMUP_DONE = "warmup done"
MEASUREMENT_DONE = "measurement done"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("binary")
    parser.add_argument(
        "--options",
        default="",
        help="Command line arguments of the program, as one string",
    )
    parser.add_argument(
        "--input",
        default="",
        help="File given to the program as its standard input",
    )
    parser.add_argument(
        "--mem-size",
        default="2GB",
        help="Size of the simulated memory, large SPEC inputs need 8GB",
    )
    parser.add_argument(
        "--hermes",
        action="store_true",
        help="Send Hermes requests, for every eligible load unless --popet "
        "is also given",
    )
    parser.add_argument(
        "--popet",
        action="store_true",
        help="Run the POPET predictor; with --hermes only loads predicted "
        "to go off-chip send a Hermes request, without it POPET only "
        "predicts and trains",
    )
    parser.add_argument(
        "--drop-squashed",
        action="store_true",
        help="Drop the queued Hermes request of a load that is squashed "
        "before the request is sent",
    )
    parser.add_argument(
        "--popet-threshold",
        type=int,
        help="POPET activation threshold, a load (or store) whose sum is at "
        "least this goes off-chip; the default is the authors' -17",
    )
    parser.add_argument(
        "--popet-feature-mask",
        type=int,
        default=31,
        help="Bit mask of the POPET features in use (31 = all five)",
    )
    parser.add_argument(
        "--hermes-max-rdq",
        type=int,
        default=0,
        metavar="N",
        help="The memory controller drops Hermes requests while N or more "
        "reads are queued (0 = never)",
    )
    parser.add_argument(
        "--no-tso",
        action="store_true",
        help="Let several stores write to the cache at once instead of one at "
        "a time, closer to the ChampSim core of the paper",
    )
    parser.add_argument(
        "--cancel-squashed",
        action="store_true",
        help="A squashed load whose Hermes request was already sent tells "
        "the memory controller to drop it",
    )
    parser.add_argument(
        "--hermes-stores",
        action="store_true",
        help="Stores also send a Hermes request when they are written to the "
        "cache, predicted by a second POPET when --popet is given",
    )
    parser.add_argument(
        "--issue-latency",
        type=int,
        default=6,
        help="Hermes issue latency in cycles, 6 for Hermes-O and 18 for "
        "Hermes-P",
    )
    parser.add_argument(
        "--dram",
        choices=DRAMS.keys(),
        default="ddr4_2400",
        help="DRAM of the single memory channel",
    )
    parser.add_argument(
        "--prefetcher",
        choices=PREFETCHERS.keys(),
        help="Add this prefetcher to the L2 cache",
    )
    parser.add_argument(
        "--fast-forward",
        type=int,
        default=0,
        metavar="INSTS",
        help="Run this many instructions on the atomic CPU, then switch to "
        "O3",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=0,
        metavar="INSTS",
        help="Reset the stats after this many instructions on O3",
    )
    parser.add_argument(
        "--max-insts",
        type=int,
        default=0,
        metavar="INSTS",
        help="Stop after measuring this many instructions on O3, instead of "
        "at the end of the program",
    )
    parser.add_argument(
        "--repeat-switch",
        type=int,
        default=0,
        metavar="TICKS",
        help="For testing: every TICKS ticks on O3, switch to the atomic CPU "
        "and back, which drains the system while Hermes requests are in "
        "flight",
    )
    args = parser.parse_args()

    if args.repeat_switch and not args.fast_forward:
        parser.error("--repeat-switch needs --fast-forward")
    # an instruction count stop would be split across the two CPUs
    if args.repeat_switch and (args.warmup or args.max_insts):
        parser.error(
            "--repeat-switch can't be used with --warmup or --max-insts"
        )

    return args


# Like ChampSim, a request pays the latency of a level on its way down, so an LLC
# miss reaches the memory controller only after all of them
def make_cache(size, assoc, latency, mshrs):
    return Cache(
        size=size,
        assoc=assoc,
        tag_latency=latency,
        data_latency=latency,
        response_latency=1,
        mshrs=mshrs,
        tgts_per_mshr=20,
    )


def build_system(args):
    system = System()
    system.clk_domain = SrcClockDomain(
        clock="4GHz", voltage_domain=VoltageDomain()
    )
    # the atomic CPU needs atomic mode, and switching to O3 changes it to timing
    system.mem_mode = "atomic" if args.fast_forward else "timing"
    system.mem_ranges = [AddrRange(args.mem_size)]

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
        cpu_id=0,
        switched_out=args.fast_forward > 0,
    )

    # The CPU that runs first owns the cache ports and the interrupt controller,
    # and each switch hands them to the other CPU
    first_cpu = system.cpu
    if args.fast_forward:
        # a CPU left at cpu_id -1 gets the next free id, but a switch needs
        # both CPUs to have the same id
        system.atomic_cpu = X86AtomicSimpleCPU(
            cpu_id=0, max_insts_any_thread=args.fast_forward
        )
        first_cpu = system.atomic_cpu

    # Latencies are picked to give the 5, 15 and 55 cycle round trips of Table 4
    system.l1i = make_cache("32kB", 8, 4, 16)
    system.l1d = make_cache("48kB", 12, 4, 16)
    system.l2 = make_cache("1280kB", 20, 8, 48)
    system.l3 = make_cache("3MB", 12, 36, 64)
    if args.prefetcher:
        system.l2.prefetcher = PREFETCHERS[args.prefetcher]()

    system.l2bus = L2XBar()
    system.l3bus = L2XBar()
    system.membus = SystemXBar()

    first_cpu.icache_port = system.l1i.cpu_side
    first_cpu.dcache_port = system.l1d.cpu_side
    # SE mode never walks page tables, but a switch moves the walker ports
    # too and fails if they are not connected
    first_cpu.mmu.connectWalkerPorts(
        system.l2bus.cpu_side_ports, system.l2bus.cpu_side_ports
    )
    system.l1i.mem_side = system.l2bus.cpu_side_ports
    system.l1d.mem_side = system.l2bus.cpu_side_ports
    system.l2.cpu_side = system.l2bus.mem_side_ports
    system.l2.mem_side = system.l3bus.cpu_side_ports
    system.l3.cpu_side = system.l3bus.mem_side_ports
    system.l3.mem_side = system.membus.cpu_side_ports

    first_cpu.createInterruptController()
    first_cpu.interrupts[0].pio = system.membus.mem_side_ports
    first_cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports
    first_cpu.interrupts[0].int_responder = system.membus.mem_side_ports
    system.system_port = system.membus.cpu_side_ports

    system.mem_ctrl = MemCtrl()
    system.mem_ctrl.dram = DRAMS[args.dram](range=system.mem_ranges[0])
    system.mem_ctrl.port = system.membus.mem_side_ports
    if args.hermes_max_rdq:
        system.mem_ctrl.hermes_max_read_queue = args.hermes_max_rdq

    if args.hermes:
        system.cpu.enable_hermes = True
        system.cpu.hermes_issue_latency = args.issue_latency
        system.cpu.hermes_drop_squashed = args.drop_squashed
        system.cpu.hermes_stores = args.hermes_stores
        system.cpu.hermes_cancel_squashed = args.cancel_squashed
        system.cpu.hermes_port = system.mem_ctrl.hermes_port

    if args.popet:
        system.cpu.popetEnable = True
    if args.popet_threshold is not None:
        system.cpu.popetActThreshold = args.popet_threshold
    system.cpu.popetFeatureMask = args.popet_feature_mask
    if args.no_tso:
        system.cpu.needsTSO = False

    system.workload = SEWorkload.init_compatible(args.binary)
    process = Process(
        cmd=[args.binary] + args.options.split(), output="program.out"
    )
    if args.input:
        process.input = args.input
    system.cpu.workload = process
    system.cpu.createThreads()
    if args.fast_forward:
        # both CPUs run the same thread, so they share its process and ISA state
        system.atomic_cpu.workload = system.cpu.workload
        system.atomic_cpu.isa = system.cpu.isa
        system.atomic_cpu.createThreads()

    return system


def finish(event):
    print(f"Exiting @ tick {m5.curTick()} because {event.getCause()}")

    # pass on the exit code of the program, so a test that checks its own
    # results fails the run
    sys.exit(event.getCode())


def run_until(cause, ticks=None):
    # any other exit, such as the end of the program, ends the whole run
    event = m5.simulate(ticks) if ticks else m5.simulate()
    if event.getCause() != cause:
        finish(event)


def run(args, system):
    if args.fast_forward:
        run_until(MAX_INSTS)
        m5.switchCpus(system, [(system.atomic_cpu, system.cpu)])

    while args.repeat_switch:
        run_until(LIMIT_REACHED, args.repeat_switch)
        m5.switchCpus(system, [(system.cpu, system.atomic_cpu)])
        run_until(LIMIT_REACHED, ATOMIC_TICKS)
        m5.switchCpus(system, [(system.atomic_cpu, system.cpu)])

    if args.warmup:
        system.cpu.scheduleInstStop(0, args.warmup, WARMUP_DONE)
        run_until(WARMUP_DONE)
        m5.stats.reset()

    if args.max_insts:
        system.cpu.scheduleInstStop(0, args.max_insts, MEASUREMENT_DONE)

    finish(m5.simulate())


args = parse_args()
system = build_system(args)
root = Root(full_system=False, system=system)
m5.instantiate()
run(args, system)
