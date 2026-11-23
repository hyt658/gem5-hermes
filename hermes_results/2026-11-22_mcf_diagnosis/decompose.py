#!/usr/bin/env python3
"""Split the change in LLC miss latency from Hermes into benefit and cost.

usage: decompose.py BASE_DIR O_DIR CONTROL_DIR [CHECK_DIR]

Model: the change in average LLC miss latency over the baseline is
    delta = -k * x + C
where x = (takeovers per LLC miss) * (average head start), k is the fraction
of the head start that turns into lower latency, and C is the cost of the
extra DRAM reads. The control run sends the same Hermes requests with a long
issue latency, so it has the same extra reads (same C) but almost no head
start. Two runs give two equations for k and C. A third run, such as
Hermes-P, checks the model: its predicted delta scales C by its unused reads.
"""

import os
import sys


def read(path):
    values = {}
    with open(os.path.join(path, "stats.txt")) as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                try:
                    values[parts[0]] = float(parts[1])
                except ValueError:
                    pass
    return values


def summarize(path, base=None):
    s = read(path)
    run = {
        "name": os.path.basename(os.path.normpath(path)),
        "ipc": s.get("system.cpu.ipc", 0.0),
        "lat": s.get("system.l3.demandAvgMissLatency::total", 0.0) / 1000.0,
        "misses": s.get("system.l3.demandMisses::total", 0.0),
        "merged": s.get("system.mem_ctrl.hermesMerged", 0.0),
        "head": s.get("system.mem_ctrl.avgHermesHeadStart", 0.0) / 1000.0,
        "unused": s.get("system.mem_ctrl.hermesUnused", 0.0),
        "reads": s.get("system.mem_ctrl.readBursts", 0.0),
    }
    run["share"] = run["merged"] / run["misses"] if run["misses"] else 0.0
    run["x"] = run["share"] * run["head"]
    if base:
        run["delta"] = run["lat"] - base["lat"]
        run["gain"] = 100.0 * (run["ipc"] / base["ipc"] - 1.0)
        run["extra"] = run["reads"] - base["reads"]
    return run


def main():
    base = summarize(sys.argv[1])
    o = summarize(sys.argv[2], base)
    ctrl = summarize(sys.argv[3], base)
    check = summarize(sys.argv[4], base) if len(sys.argv) > 4 else None

    print(f"{'run':<14}{'IPC':>8}{'gain':>8}{'LLC ns':>8}{'delta':>8}"
          f"{'taken':>8}{'head ns':>9}{'x ns':>7}{'unused':>9}{'extra rd':>10}")
    print(f"{base['name']:<14}{base['ipc']:8.4f}{'-':>8}{base['lat']:8.1f}"
          f"{'-':>8}{'-':>8}{'-':>9}{'-':>7}{'-':>9}{'-':>10}")
    for r in [o, ctrl] + ([check] if check else []):
        print(f"{r['name']:<14}{r['ipc']:8.4f}{r['gain']:+8.2f}{r['lat']:8.1f}"
              f"{r['delta']:+8.2f}{100 * r['share']:7.1f}%{r['head']:9.1f}"
              f"{r['x']:7.2f}{r['unused']:9.0f}{r['extra']:10.0f}")

    k = (ctrl["delta"] - o["delta"]) / (o["x"] - ctrl["x"])
    cost = o["delta"] + k * o["x"]
    print(f"\nrealized share of the head start k = {100 * k:.0f}%")
    print(f"benefit -k*x = {-k * o['x']:+.1f} ns, cost of extra reads "
          f"C = {cost:+.1f} ns, net {o['delta']:+.1f} ns per LLC miss")
    if check:
        scaled = cost * check["unused"] / o["unused"] if o["unused"] else cost
        predicted = -k * check["x"] + scaled
        print(f"check with {check['name']}: predicted {predicted:+.1f} ns, "
              f"measured {check['delta']:+.1f} ns")


if __name__ == "__main__":
    main()
