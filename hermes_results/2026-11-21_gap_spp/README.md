# GAP, SPP and long-run validation (11/21)

All runs use the final setting from `../SUMMARY.md` unless the config name says otherwise.
Each run is 1B instructions of fast-forward, 20M of warmup and 50M measured.
The two `mcf_*_long` runs measure 200M. The 16 SPEC runs without SPP are in `../2026-11-20_github_verify`.

GAP is commit 941462c, on a Kronecker graph with 2^20 vertices, built for baseline x86-64
because gem5 does not implement `pcmpeqq`, which the optimized `mt19937` uses:

```
make SERIAL=1 CXX_FLAGS="-std=c++11 -O3 -march=x86-64 -mtune=generic -static" bfs pr cc
```

Config lists are in `configs_b6.txt`, `configs_b7.txt` and `configs_long.txt`. GAP commands are in `benches_gap.txt`.

## IPC gain

| Config | lbm | bwaves | roms | mcf | bfs | pr | cc | SPEC | GAP | All |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Hermes-O / base | 5.00 | 4.10 | 0.92 | 1.07 | 3.41 | 4.56 | 7.72 | 2.76 | 5.21 | 3.80 |
| Hermes-P / base | 3.41 | 3.11 | 0.77 | 0.64 | 2.54 | 3.92 | 5.34 | 1.97 | 3.93 | 2.81 |
| Hermes-O / SPP, threshold +5 | 0.48 | 0.41 | 0.12 | -0.01 | 1.44 | 0.48 | 5.62 | 0.25 | 2.49 | 1.21 |
| Hermes-O / SPP, threshold -17 | 0.59 | 0.31 | 0.07 | -0.61 | 2.59 | -1.00 | 8.75 | 0.09 | 3.37 | 1.48 |

mcf with 200M measured instructions: Hermes-O +1.06%.

## Reading these results

- GAP was not used to choose threshold +5, so it is a held-out check.
- On top of SPP, POPET coverage drops sharply (lbm 97% to 9%, bwaves 99% to 9%, pr 27% to about 0%).
- Threshold -17 raises coverage only modestly, adds unused requests, and makes mcf and pr negative.
- The paper reports +11.5% over no prefetching and +5.4% over Pythia. We use SPP, so the prefetcher numbers are not directly comparable.
