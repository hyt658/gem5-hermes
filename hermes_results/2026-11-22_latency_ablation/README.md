# Issue latency and feature ablation (2026-11-22)

56 runs on 7 programs (lbm, bwaves, roms, mcf, bfs, pr, cc), no prefetcher.
Setting: `--no-tso --dram=ddr4_3200_1r8b --hermes --popet --popet-threshold=5`.
Issue latency uses `--issue-latency=N`. Ablation uses `--popet-feature-mask=N`
(masks 30, 29, 27, 23, 15 remove features 0 to 4). The 6-cycle and 18-cycle
points and the full-feature baseline come from `2026-11-21_gap_spp`.

With the default mask (31), lbm and cc reproduce the earlier simTicks exactly.

## IPC gain over no Hermes (%)

| Config | lbm | bwaves | roms | mcf | bfs | pr | cc | SPEC | GAP | All |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Latency 0 | 5.58 | 4.57 | 1.02 | 1.30 | 3.84 | 4.72 | 8.95 | 3.10 | 5.81 | 4.25 |
| Latency 6 (Hermes-O) | 5.00 | 4.10 | 0.92 | 1.07 | 3.41 | 4.56 | 7.72 | 2.76 | 5.21 | 3.80 |
| Latency 12 | 4.22 | 3.63 | 0.88 | 0.83 | 3.00 | 4.48 | 6.54 | 2.38 | 4.66 | 3.35 |
| Latency 18 (Hermes-P) | 3.41 | 3.11 | 0.77 | 0.64 | 2.54 | 3.92 | 5.34 | 1.97 | 3.93 | 2.81 |
| Latency 24 | 2.71 | 2.49 | 0.69 | 0.31 | 2.04 | 3.38 | 4.17 | 1.54 | 3.19 | 2.25 |
| No PC+Offset | 4.97 | 4.07 | 0.92 | 1.02 | 2.58 | 5.43 | 6.55 | 2.73 | 4.84 | 3.63 |
| No PC+First Access | 4.45 | 2.26 | 0.76 | -0.74 | 0.65 | 1.11 | 1.56 | 1.66 | 1.11 | 1.43 |
| No Offset+First Access | 4.90 | 4.12 | 0.98 | 0.40 | 0.99 | 5.02 | 3.06 | 2.58 | 3.01 | 2.77 |
| No PC+Cacheline Offset | 4.35 | 2.29 | 0.83 | 0.96 | 3.26 | 1.25 | 6.63 | 2.10 | 3.69 | 2.78 |
| No Last-N Load PCs | 4.96 | 4.16 | 0.98 | 1.04 | 3.39 | 5.81 | 7.24 | 2.77 | 5.47 | 3.92 |

## Reading these results

- Each extra cycle of issue latency costs about 0.08 points. Even 0 cycles reaches only +4.25%, so latency alone does not explain the gap to the paper's +11.5%.
- PC+First Access matters most. Last-N Load PCs and PC+Offset add little on these programs.
- The threshold stays at +5 during ablation. With four weights the sum reaches it less easily, so part of each loss may come from the threshold.
