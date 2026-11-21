"""Print the speedup tables of the 11/17-11/20 runs as Markdown."""
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
BENCHES = ["lbm", "bwaves", "roms", "mcf"]
EXT = "2026-11-17_extensions"
FINAL = "2026-11-18_final_setting"
VERIFY = "2026-11-20_github_verify"


def stat(path, name):
    # a run can dump more than once, and the last dump is the measured region
    value = None
    with open(os.path.join(HERE, path, "stats.txt"), errors="ignore") as f:
        for line in f:
            if line.startswith(name + " "):
                value = float(line.split()[1])
    if value is None:
        raise KeyError(f"{path}: {name}")
    return value


def ipc(path):
    return stat(path, "system.cpu.ipc")


def matrix(bench, config):
    if bench == "mcf":
        name = {"base": "mcf_base", "O_popet": "mcf_popet_O"}[config]
        return f"2026-11-09_first_runs/{name}"
    return f"2026-11-17_spec_matrix/{bench}_{config}"


def table(title, rows):
    print(f"\n### {title}\n")
    print("| Config | " + " | ".join(BENCHES) + " | Geomean |")
    print("|---|" + "---:|" * (len(BENCHES) + 1))
    for label, run, base in rows:
        speedups = [ipc(run(b)) / ipc(base(b)) for b in BENCHES]
        geo = math.exp(sum(map(math.log, speedups)) / len(speedups))
        cells = " | ".join(f"{s:.3f}" for s in speedups)
        print(f"| {label} | {cells} | {geo:.3f} |")


def runs(folder, config):
    return lambda b: f"{folder}/{b}_{config}"


def old(config):
    return lambda b: matrix(b, config)


base = old("base")
final_base = runs(FINAL, "base_final")
print("All values are IPC relative to the listed baseline (1.000 = no change).")
table("Final setting (no TSO limit, DDR4-3200 1R8B, threshold +5)", [
    ("Hermes-O", runs(FINAL, "O_popet_final"), final_base),
    ("Hermes-P", runs(FINAL, "P_popet_final"), final_base),
    ("Hermes-O + stores", runs(FINAL, "O_popet_st_final"), final_base),
    ("Hermes-O, threshold -17", runs(FINAL, "O_popet_final_tdef"), final_base),
])
table("POPET activation threshold (TSO, DDR4-2400)", [
    ("-17", old("O_popet"), base),
    *[(t, runs(FINAL, f"O_popet_{c}"), base) for t, c in
      [("-5", "tm5"), ("0", "t0"), ("+5", "t5"), ("+10", "t10"), ("+15", "t15")]],
])
nt = runs(FINAL, "base_notso")
table("No TSO limit (DDR4-2400, threshold -17)", [
    ("Hermes-O", runs(FINAL, "O_popet_notso"), nt),
    ("Hermes-P", runs(FINAL, "P_popet_notso"), nt),
    ("Hermes-O + stores", runs(FINAL, "O_popet_st_notso"), nt),
])
table("DDR4-3200 1R8B (TSO, threshold -17)", [
    ("Hermes-O", runs(FINAL, "O_popet_paper"), runs(FINAL, "base_paper")),
])
table("Memory controller throttle (TSO, DDR4-2400)", [
    ("max read queue 4", runs(FINAL, "O_popet_q4"), base),
    ("max read queue 8", runs(FINAL, "O_popet_q8"), base),
    ("max read queue 16", runs(FINAL, "O_popet_q16"), base),
    ("threshold +5, queue 8", runs(FINAL, "O_popet_t5_q8"), base),
])
table("Extensions (TSO, threshold -17)", [
    ("Hermes-O + stores", runs(EXT, "O_popet_st"), base),
    ("Hermes-O + cancel", runs(EXT, "O_popet_cancel"), base),
    ("Hermes-O + stores + cancel", runs(EXT, "O_popet_st_cancel"), base),
    ("DDR4-3200", runs(EXT, "O_popet_3200"), runs(EXT, "base_3200")),
    ("DDR4-6400", runs(EXT, "O_popet_6400"), runs(EXT, "base_6400")),
    ("SPP prefetcher", runs(EXT, "O_popet_spp"), runs(EXT, "base_spp")),
])

same = total = 0
for run in sorted(os.listdir(os.path.join(HERE, VERIFY))):
    if not os.path.isdir(os.path.join(HERE, VERIFY, run)):
        continue
    total += 1
    a, b = f"{VERIFY}/{run}", f"{FINAL}/{run}"
    same += all(stat(a, s) == stat(b, s) for s in ("system.cpu.ipc", "simTicks"))
print(f"\n### GitHub build check\n\n{same} of {total} runs have the same IPC "
      "and simTicks as the 11/18 runs.")
