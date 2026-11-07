import argparse
import filecmp
import os
import sys

CPU = "system.cpu."
CTRL = "system.mem_ctrl."

SIM_INSTS = "simInsts"
CYCLES = CPU + "numCycles"
IPC = CPU + "ipc"
LOAD_LATENCY = CPU + "lsq0.loadToUse::mean"
HERMES_ISSUED = CPU + "lsq0.hermesIssued"
READ_BURSTS = CTRL + "readBursts"
HERMES_REQS = CTRL + "hermesReqs"
HERMES_MERGED = CTRL + "hermesMerged"
HERMES_UNUSED = CTRL + "hermesUnused"
HERMES_DROP_FULL = CTRL + "hermesDropFull"
HERMES_DROP_IN_FLIGHT = CTRL + "hermesDropInFlight"
HERMES_WRQ = CTRL + "hermesServicedByWrQ"

SHOWN = [
    SIM_INSTS,
    CYCLES,
    IPC,
    LOAD_LATENCY,
    READ_BURSTS,
    HERMES_ISSUED,
    HERMES_REQS,
    HERMES_MERGED,
    HERMES_UNUSED,
    HERMES_DROP_FULL,
    HERMES_DROP_IN_FLIGHT,
    HERMES_WRQ,
]


def read_stats(run_dir):
    stats = {}
    with open(os.path.join(run_dir, "stats.txt")) as f:
        for line in f:
            fields = line.split()
            if len(fields) >= 2:
                stats[fields[0]] = fields[1]
    return stats


def stat(stats, name):
    return float(stats.get(name, 0))


parser = argparse.ArgumentParser()
parser.add_argument("off_dir", help="Output directory of the baseline run")
parser.add_argument("on_dir", help="Output directory of the Hermes run")
args = parser.parse_args()

off = read_stats(args.off_dir)
on = read_stats(args.on_dir)

print(f"{'stat':<40}{'off':>16}{'on':>16}{'change':>10}")
for name in SHOWN:
    off_value = stat(off, name)
    on_value = stat(on, name)
    change = ""
    if off_value:
        change = f"{(on_value / off_value - 1) * 100:+.1f}%"
    print(f"{name:<40}{off_value:>16g}{on_value:>16g}{change:>10}")

checks = [
    # a crashed run leaves stats.txt empty, and the checks below would then
    # compare zeros and pass
    ("baseline run finished", stat(off, SIM_INSTS) > 0),
    ("Hermes run finished", stat(on, SIM_INSTS) > 0),
    (
        "same program output",
        filecmp.cmp(
            os.path.join(args.off_dir, "program.out"),
            os.path.join(args.on_dir, "program.out"),
            shallow=False,
        ),
    ),
    ("same instruction count", stat(off, SIM_INSTS) == stat(on, SIM_INSTS)),
    ("baseline sends no Hermes requests", stat(off, HERMES_REQS) == 0),
    ("loads issue Hermes requests", stat(on, HERMES_ISSUED) > 0),
    ("regular reads merge with Hermes", stat(on, HERMES_MERGED) > 0),
    ("load latency drops", stat(on, LOAD_LATENCY) < stat(off, LOAD_LATENCY)),
    ("IPC rises", stat(on, IPC) > stat(off, IPC)),
]

print()
failed = False
for description, passed in checks:
    print(f"{'PASS' if passed else 'FAIL'} {description}")
    failed = failed or not passed

sys.exit(1 if failed else 0)
