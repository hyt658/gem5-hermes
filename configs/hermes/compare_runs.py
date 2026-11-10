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
HERMES_ISSUED = CPU + "lsq0.issuedHermes"
READ_BURSTS = CTRL + "readBursts"
HERMES_REQS = CTRL + "hermesReqs"
HERMES_MERGED = CTRL + "hermesMerged"
HERMES_UNUSED = CTRL + "hermesUnused"
HERMES_DROP_FULL = CTRL + "hermesDropFull"
HERMES_DROP_IN_FLIGHT = CTRL + "hermesDropInFlight"
HERMES_WRQ = CTRL + "hermesServicedByWrQ"
POPET = CPU + "popet."
POPET_STATS = [
    POPET + name
    for name in ("predictions", "predictedOffchip", "truePos", "falsePos",
                 "falseNeg", "trueNeg", "accuracy", "coverage")
]

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
] + POPET_STATS


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("off_dir", help="Output directory of the baseline run")
    parser.add_argument("on_dir", help="Output directory of the Hermes run")
    parser.add_argument(
        "--require",
        action="append",
        default=[],
        metavar="STAT",
        help="A stat that must be positive in the Hermes run, to show that a "
        "test reached the case it targets. Can be given more than once",
    )
    parser.add_argument(
        "--skip-perf",
        action="store_true",
        help="Skip the latency and IPC checks, for tests that target "
        "correctness",
    )
    return parser.parse_args()


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


def print_table(off, on, names):
    print(f"{'stat':<40}{'off':>16}{'on':>16}{'change':>10}")
    for name in names:
        off_value = stat(off, name)
        on_value = stat(on, name)
        change = ""
        if off_value:
            change = f"{(on_value / off_value - 1) * 100:+.1f}%"
        print(f"{name:<40}{off_value:>16g}{on_value:>16g}{change:>10}")


def make_checks(args, off, on):
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
        (
            "same instruction count",
            stat(off, SIM_INSTS) == stat(on, SIM_INSTS),
        ),
        ("baseline sends no Hermes requests", stat(off, HERMES_REQS) == 0),
        ("loads issue Hermes requests", stat(on, HERMES_ISSUED) > 0),
        ("regular reads merge with Hermes", stat(on, HERMES_MERGED) > 0),
    ]

    if not args.skip_perf:
        checks += [
            (
                "load latency drops",
                stat(on, LOAD_LATENCY) < stat(off, LOAD_LATENCY),
            ),
            ("IPC rises", stat(on, IPC) > stat(off, IPC)),
        ]

    checks += [(f"{name} > 0", stat(on, name) > 0) for name in args.require]
    return checks


def print_checks(checks):
    all_passed = True
    for description, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'} {description}")
        all_passed = all_passed and passed
    return all_passed


args = parse_args()
off = read_stats(args.off_dir)
on = read_stats(args.on_dir)

print_table(off, on, SHOWN + [n for n in args.require if n not in SHOWN])
print()
all_passed = print_checks(make_checks(args, off, on))
sys.exit(0 if all_passed else 1)
