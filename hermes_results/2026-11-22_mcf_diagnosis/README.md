# mcf memory-side diagnosis (2026-11-22)

A supplement to the main results: why Hermes helps mcf so little. The setting
is that of the 11/09 mcf runs: TSO, DDR4-2400, POPET threshold -17, 1B
instructions of fast-forward, 20M of warmup and 50M measured. The baseline is
`2026-11-09_first_runs/mcf_base`.

The binary is `popet` at `0996ae5` plus the memory controller's takeover stats
(`hermesMergedQueued`, `hermesMergedIssued`, `avgHermesHeadStart`,
`avgMergedReadLat`, `avgUnmergedReadLat`) and the load numbers (`[sn:N]`) in
the `HermesMem` debug output.

| Run | Flags on top of the mcf setting | Purpose |
|---|---|---|
| `mcf_O` | `--hermes --popet` | Hermes-O with the new stats |
| `mcf_P` | `--hermes --popet --issue-latency=18` | Hermes-P, checks the split below |
| `mcf_L100` | `--hermes --popet --issue-latency=100` | Control: the same Hermes requests, almost all too late |
| `mcf_O_trace` | Hermes-O with `--debug-flags=HermesMem,POPET` for ticks 545e9 to 546e9 | Ties each Hermes outcome to its load. The 19 MB trace is not kept |

`mcf_O` and `mcf_P` match the 11/09 runs, and `mcf_O_trace` matches `mcf_O`, on
all 19 compared stats, so the new stats and the debug output change nothing.

## Benefit and cost per LLC miss

| Run | IPC | IPC gain | LLC miss latency | Change | LLC misses taken over | Head start | Unused Hermes reads |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 0.6478 | — | 94.4 ns | — | — | — | — |
| Hermes-O | 0.6429 | -0.74% | 93.8 ns | -0.58 ns | 77.5% | 16.0 ns | 199,355 |
| Control (latency 100) | 0.6273 | -3.16% | 101.6 ns | +7.23 ns | 9.9% | 28.7 ns | 199,190 |
| Hermes-P | 0.6396 | -1.26% | 95.4 ns | +1.05 ns | 77.5% | 13.1 ns | 198,048 |

The change in LLC miss latency is modeled as `-k * x + C`, where `x` is the
share of LLC misses taken over times the head start, `k` is the realized
fraction of the head start, and `C` is the cost of the extra DRAM reads.
Hermes-O and the control have the same extra reads, so they give two
equations for `k` and `C`:

- `k` = 82%: the head start saves 10.1 ns per LLC miss
- `C` = +9.5 ns: the extra DRAM reads cost about as much
- Net: -0.6 ns, as measured
- Check with Hermes-P: predicted +1.2 ns, measured +1.0 ns

## Where the unused Hermes reads come from

Each Hermes outcome in the 1 ms trace is matched with POPET's training record
of its load (prediction and off-chip label at commit) or with the squash of
its load. All 57,364 outcomes were matched.

| Load | Taken over | Unused | Dropped, read in flight | Write queue | Total |
|---|---:|---:|---:|---:|---:|
| POPET false positive (committed, hit on chip) | 1,092 | 7,971 | 761 | 0 | 9,824 |
| True positive (committed, went off-chip) | 32,952 | 207 | 38 | 2 | 33,199 |
| Squashed | 12,549 | 1,524 | 268 | 0 | 14,341 |

82.2% of the unused reads come from POPET false positives, 15.7% from squashed
loads and 2.1% from regular reads that came after the Hermes read finished.

## Reading these results

- The head start is mostly realized. The gain is eaten by the extra DRAM reads,
  not lost in the memory controller's queue.
- Most extra reads come from POPET false positives, so the fix is a higher
  threshold. At +5, the threshold of the final setting, unused reads fall from
  199K to 66K and mcf goes from -0.7% to +1.1% (`2026-11-18_final_setting`).
- Squashed loads send many Hermes requests, but 88% of those are taken over by
  the squashed load's own regular read, so they add little traffic.

## Files

- `run.sh`: the runs and the analysis
- `decompose.py`: the split into benefit and cost
- `hermes_attrib.py`: matches the debug output with POPET's training records
- `summary.txt`: the output of the analysis and of the check against the 11/09
  runs
