# Hermes results, 11/17 to 11/20

Each run is 1B instructions of fast-forward, 20M of warmup and 50M measured.
Regenerate the tables below with `python hermes_results/summarize.py`.

| Folder | Contents |
|---|---|
| `2026-11-17_extensions` | Store Hermes, MC cancel, DDR4-3200/6400, SPP |
| `2026-11-18_final_setting` | Threshold sweep, no TSO limit, 1R8B DRAM, MC throttle, final setting |
| `2026-11-20_github_verify` | Final setting rerun from the `popet` branch at ef607c3 |

The final setting is:

```
--no-tso --dram=ddr4_3200_1r8b --hermes --popet --popet-threshold=5
```

The 11/18 runs used the flag name `ddr4_3200_paper` for the same DRAM.

## Differences from the paper

- The paper reports Hermes-O at +11.5% over no prefetching and +5.4% over
  Pythia. Our +2.8% is over no prefetching, on 4 SPEC programs.
- The paper warms up for 100M and measures 500M instructions.
- The paper's LLC uses SHiP and its core uses a perceptron branch predictor.
  We use gem5's defaults.
- Threshold +5 was picked on the same 4 programs it is reported on.
- `--no-tso` removes gem5's one-store-at-a-time limit to get closer to
  ChampSim. It is not a model of a real x86 core.

## Tables

All values are IPC relative to the listed baseline (1.000 = no change).

### Final setting (no TSO limit, DDR4-3200 1R8B, threshold +5)

| Config | lbm | bwaves | roms | mcf | Geomean |
|---|---:|---:|---:|---:|---:|
| Hermes-O | 1.050 | 1.041 | 1.009 | 1.011 | 1.028 |
| Hermes-P | 1.034 | 1.031 | 1.008 | 1.006 | 1.020 |
| Hermes-O + stores | 1.052 | 1.054 | 1.016 | 1.011 | 1.033 |
| Hermes-O, threshold -17 | 1.050 | 1.039 | 1.010 | 0.990 | 1.022 |

### POPET activation threshold (TSO, DDR4-2400)

| Config | lbm | bwaves | roms | mcf | Geomean |
|---|---:|---:|---:|---:|---:|
| -17 | 0.998 | 0.987 | 1.004 | 0.993 | 0.996 |
| -5 | 0.998 | 0.987 | 1.005 | 1.007 | 0.999 |
| 0 | 0.998 | 0.987 | 1.005 | 1.010 | 1.000 |
| +5 | 0.998 | 0.988 | 1.005 | 1.011 | 1.000 |
| +10 | 0.998 | 0.988 | 1.005 | 1.011 | 1.000 |
| +15 | 0.998 | 0.988 | 1.005 | 1.011 | 1.000 |

### No TSO limit (DDR4-2400, threshold -17)

| Config | lbm | bwaves | roms | mcf | Geomean |
|---|---:|---:|---:|---:|---:|
| Hermes-O | 1.065 | 1.053 | 1.005 | 0.994 | 1.029 |
| Hermes-P | 1.047 | 1.040 | 1.004 | 0.988 | 1.019 |
| Hermes-O + stores | 1.074 | 1.083 | 1.011 | 0.994 | 1.040 |

### DDR4-3200 1R8B (TSO, threshold -17)

| Config | lbm | bwaves | roms | mcf | Geomean |
|---|---:|---:|---:|---:|---:|
| Hermes-O | 1.003 | 0.991 | 1.006 | 0.989 | 0.997 |

### Memory controller throttle (TSO, DDR4-2400)

| Config | lbm | bwaves | roms | mcf | Geomean |
|---|---:|---:|---:|---:|---:|
| max read queue 4 | 0.998 | 0.987 | 1.005 | 0.999 | 0.997 |
| max read queue 8 | 0.998 | 0.987 | 1.005 | 0.995 | 0.996 |
| max read queue 16 | 0.998 | 0.987 | 1.004 | 0.993 | 0.996 |
| threshold +5, queue 8 | 0.998 | 0.988 | 1.005 | 1.012 | 1.001 |

### Extensions (TSO, threshold -17)

| Config | lbm | bwaves | roms | mcf | Geomean |
|---|---:|---:|---:|---:|---:|
| Hermes-O + stores | 1.208 | 1.177 | 1.078 | 0.993 | 1.111 |
| Hermes-O + cancel | 0.998 | 0.987 | 1.005 | 0.994 | 0.996 |
| Hermes-O + stores + cancel | 1.208 | 1.176 | 1.078 | 0.993 | 1.111 |
| DDR4-3200 | 0.997 | 0.989 | 1.003 | 0.998 | 0.997 |
| DDR4-6400 | 0.996 | 0.987 | 1.002 | 1.014 | 1.000 |
| SPP prefetcher | 0.994 | 1.001 | 1.001 | 0.999 | 0.999 |

### GitHub build check

16 of 16 runs have the same IPC and simTicks as the 11/18 runs.
