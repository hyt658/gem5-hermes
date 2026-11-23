# Second prefetcher and DRAM bandwidth (2026-11-23)

47 valid runs. All use `--no-tso --mem-size=8GB --fast-forward=1000000000
--warmup=20000000 --max-insts=50000000`. Hermes runs add `--hermes --popet
--popet-threshold=5`, and Hermes-P adds `--issue-latency=18`. `configs.txt` lists
the flags of each configuration. The binary is `0996ae5` plus the two DRAM
variants in `configs/hermes/se_hermes.py`. BOP runs also use `bop_phase_fix.diff`.

## BOP fix

Stock gem5 BOP checks `bestScore <= badScore` after every round, so it turns itself
off after one round of each learning phase and issues about 7,000 prefetches per
run. `bop_phase_fix.diff` makes the on/off decision once per learning phase, as in
the BOP paper. **The fix is not applied to `src/` in this branch.** Apply the diff
and rebuild to reproduce the BOP runs. Only the corrected runs are stored here.

BOP issues no prefetches on bwaves and roms, so their BOP results equal the
no-prefetcher results. It is a weak prefetcher on these programs (+1.14% on
average, SPP is +8.65%).

## BOP (IPC gain %)

| Comparison | lbm | bwaves | roms | mcf | bfs | pr | cc | SPEC | GAP | All |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BOP / base | 11.19 | 0.00 | 0.00 | -2.98 | 1.54 | -1.47 | 0.31 | 1.92 | 0.12 | 1.14 |
| Hermes-O on BOP / BOP | 5.53 | 4.10 | 0.92 | 0.63 | 3.39 | 3.54 | 7.65 | 2.77 | 4.84 | 3.66 |
| Hermes-P on BOP / BOP | 4.52 | 3.11 | 0.77 | 0.29 | 2.28 | 1.90 | 5.90 | 2.16 | 3.34 | 2.66 |
| Hermes-O, no prefetcher | 5.00 | 4.10 | 0.92 | 1.07 | 3.41 | 4.56 | 7.72 | 2.76 | 5.21 | 3.80 |
| Hermes-O on SPP / SPP | 0.48 | 0.41 | 0.12 | -0.01 | 1.44 | 0.48 | 5.62 | 0.25 | 2.49 | 1.21 |

## DRAM bandwidth: Hermes-O over its own baseline (IPC gain %)

| DRAM | lbm | bwaves | roms | mcf | bfs | cc | SPEC | GAP (2) | All (6) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| DDR4-1600 | 4.21 | 2.73 | 0.93 | -0.91 | 3.08 | 7.34 | 1.72 | 5.19 | 2.86 |
| DDR4-3200 | 5.00 | 4.10 | 0.92 | 1.07 | 3.41 | 7.72 | 2.76 | 5.54 | 3.68 |
| DDR4-6400 | 3.62 | 4.29 | 0.82 | 1.79 | 3.51 | 7.89 | 2.62 | 5.67 | 3.63 |

DDR4-1600 and DDR4-6400 keep 1 rank, 8 banks, and the same tRCD, tCL, and tRP.

## Known failure

`pr_base_bw6400` and `pr_O_bw6400` stop on both attempts with this assertion, the
same one as `pr_base_ship`:

```
src/cpu/timebuf.hh:54: TimeBuffer<T>::valid(int): idx >= -past && idx <= future
```

The cause was not found. `pr` is excluded from the bandwidth averages.
`cc_O_bw6400` first failed because the disk was full and passed on rerun.

## DRAM reads (% over the baseline)

Counted with `system.mem_ctrl.readBursts`, which includes Hermes reads that end up
unused. `dram.numReads::total` leaves them out.

| Config | lbm | bwaves | roms | mcf | bfs | pr | cc | All |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Hermes-O | 0.08 | 0.00 | 0.01 | 5.64 | 1.20 | 0.92 | 4.71 | 1.77 |
| Hermes-P | 0.08 | 0.00 | 0.01 | 5.62 | 1.13 | 0.83 | 4.69 | 1.74 |
| SPP | 0.00 | 0.01 | 11.32 | 28.83 | 13.93 | 68.70 | 24.89 | 19.32 |
| BOP | 0.01 | 0.00 | 0.00 | 20.10 | 6.03 | 27.92 | 14.66 | 9.34 |
| O on SPP | 0.07 | 0.03 | 0.06 | 1.33 | 1.35 | 0.02 | 9.05 | 1.66 |
| O on BOP | 1.09 | 0.00 | 0.01 | 4.37 | 2.50 | 1.71 | 6.10 | 2.23 |

The `O on SPP` and `O on BOP` rows are relative to the SPP and BOP baselines. The
other rows are relative to the no-prefetcher baseline.
