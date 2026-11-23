#!/usr/bin/env python3
"""Tie each Hermes outcome in a gem5 debug trace to the fate of its load.

The trace must come from --debug-flags=HermesMem,POPET. The memory
controller prints every Hermes outcome with the sequence number of the load
that sent it, POPET prints the prediction and the off-chip label of every
committed load it trains on, and the LSQ prints every squashed load that had
sent a Hermes request. Outcomes near the two ends of the trace are left out,
since the fate of their load may fall outside it.
"""

import argparse
import gzip
import re
from collections import Counter

OUTCOMES = [
    ("merged", re.compile(r"merged with Hermes request \[sn:(\d+)\]")),
    ("unused", re.compile(r"finished unused \[sn:(\d+)\]")),
    ("dropInFlight", re.compile(r"Read in flight, dropping .* \[sn:(\d+)\]")),
    ("dropFull", re.compile(r"Read queue full, dropping .* \[sn:(\d+)\]")),
    ("writeQueue", re.compile(r"Hermes request \[sn:(\d+)\] needs no DRAM")),
]
TRAIN = re.compile(r"train \[sn:(\d+)\] .* pred=(\d) actual=(\d)")
SQUASH = re.compile(r"Squashed load \[sn:(\d+)\] had issued a Hermes")
TICK = re.compile(r"^\s*(\d+):")

FATES = ["falsePositive", "truePositive", "squashed", "predictedOnChip",
         "unknown"]


def parse(path):
    outcomes = {}
    trained = {}
    squashed = set()
    first_tick = last_tick = None
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", errors="replace") as f:
        for line in f:
            tick_match = TICK.match(line)
            if not tick_match:
                continue
            tick = int(tick_match.group(1))
            if first_tick is None:
                first_tick = tick
            last_tick = tick

            match = TRAIN.search(line)
            if match:
                trained[int(match.group(1))] = (int(match.group(2)),
                                                int(match.group(3)))
                continue
            match = SQUASH.search(line)
            if match:
                squashed.add(int(match.group(1)))
                continue
            for kind, pattern in OUTCOMES:
                match = pattern.search(line)
                if match:
                    outcomes[int(match.group(1))] = (kind, tick)
                    break
    return outcomes, trained, squashed, first_tick, last_tick


def fate(sn, trained, squashed):
    if sn in squashed:
        return "squashed"
    if sn in trained:
        pred, actual = trained[sn]
        if not pred:
            return "predictedOnChip"
        return "truePositive" if actual else "falsePositive"
    return "unknown"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("trace")
    parser.add_argument("--margin-us", type=float, default=20.0,
                        help="Leave out outcomes this close to either end")
    args = parser.parse_args()

    outcomes, trained, squashed, first, last = parse(args.trace)
    margin = int(args.margin_us * 1e6)
    lo, hi = first + margin, last - margin

    table = Counter()
    for sn, (kind, tick) in outcomes.items():
        if sn and lo <= tick <= hi:
            table[(fate(sn, trained, squashed), kind)] += 1

    kinds = [kind for kind, _ in OUTCOMES]
    print(f"trace {first} to {last} ticks, counting outcomes in {lo} to {hi}")
    print(f"trained loads {len(trained)}, squashed loads with Hermes "
          f"{len(squashed)}\n")

    print(f"{'load fate':<17}" + "".join(f"{k:>13}" for k in kinds)
          + f"{'total':>9}")
    for f in FATES + ["total"]:
        if f == "total":
            row = [sum(table[(g, k)] for g in FATES) for k in kinds]
        else:
            row = [table[(f, k)] for k in kinds]
        print(f"{f:<17}" + "".join(f"{v:>13}" for v in row)
              + f"{sum(row):>9}")

    unused = sum(table[(f, "unused")] for f in FATES)
    print("\nwhere the unused Hermes reads come from")
    for f in FATES:
        n = table[(f, "unused")]
        share = 100.0 * n / unused if unused else 0.0
        print(f"  {f:<17}{n:>8}  {share:5.1f}%")


if __name__ == "__main__":
    main()
