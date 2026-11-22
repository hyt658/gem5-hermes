# SHiP and proportional-threshold ablation (2026-11-22)

48 valid runs, no prefetcher, `--no-tso --dram=ddr4_3200_1r8b`.
SHiP uses `--llc-repl=ship` (gem5 `SHiPPCRP`). The ablation uses threshold +4,
which is +5 scaled from five features to four.

## Known failure

`pr_base_ship` stops on both attempts at tick 623971901513 with this assertion:

```
src/cpu/timebuf.hh:54: TimeBuffer<T>::valid(int): idx >= -past && idx <= future
```

The cause was not found. `pr` is excluded from the SHiP averages, so SHiP results
cover six programs. `pr_O_ship` completed but has no baseline, so it is not used.

## SHiP (IPC gain %)

| Comparison | lbm | bwaves | roms | mcf | bfs | cc | SPEC | GAP (2) | All (6) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SHiP base / LRU base | -3.71 | 0.73 | -1.95 | 12.98 | 0.94 | 17.35 | 1.81 | 8.84 | 4.10 |
| Hermes-O on SHiP / SHiP base | 6.07 | 4.29 | 0.94 | 1.05 | 3.24 | 7.67 | 3.06 | 5.43 | 3.85 |
| Hermes-O on LRU / LRU base | 5.00 | 4.10 | 0.92 | 1.07 | 3.41 | 7.72 | 2.76 | 5.54 | 3.68 |

## Leave-one-out ablation, all seven programs

| Removed feature | Threshold +5 | Threshold +4 |
|---|---:|---:|
| PC+First Access | 1.43 | 1.48 |
| Offset+First Access | 2.77 | 2.81 |
| PC+Cacheline Offset | 2.78 | 2.86 |
| PC+Offset | 3.63 | 3.67 |
| Last-N Load PCs | 3.92 | 3.95 |

The ranking does not change, and each average moves by less than 0.1 points.
