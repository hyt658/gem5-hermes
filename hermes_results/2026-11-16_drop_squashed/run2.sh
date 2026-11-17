#!/bin/bash
# Round 2: --drop-squashed checks and mcf experiments. Results: ~/popet_runs2/<name>/
G=~/gem5/build/X86/gem5.opt
CFG=~/gem5/configs/hermes/se_hermes.py
BIN=~/popet_runs/bin
MCF=~/spec2017/benchspec/CPU/605.mcf_s
OUT=~/popet_runs2
MCFOPT="--mem-size=8GB --fast-forward=1000000000 --warmup=20000000 --max-insts=50000000 --options=inp.in"
MCFRUN=$MCF/run/run_base_refspeed_mytest-m64.0000
MCFBIN=$MCF/build/build_base_mytest-m64.0000/mcf_s
mkdir -p $OUT
RUNS=(
  "squash_O|$OUT|$BIN/squash_test|--hermes"
  "squash_O_drop|$OUT|$BIN/squash_test|--hermes --drop-squashed"
  "store_O_drop|$OUT|$BIN/store_test|--hermes --drop-squashed"
  "chase_popet_O_regress|$OUT|$BIN/pointer_chase|--hermes --popet"
  "mcf_popet_O_drop|$MCFRUN|$MCFBIN|$MCFOPT --hermes --popet --drop-squashed"
  "mcf_popet_O_lat0|$MCFRUN|$MCFBIN|$MCFOPT --hermes --popet --issue-latency=0"
  "mcf_popet_P_drop|$MCFRUN|$MCFBIN|$MCFOPT --hermes --popet --issue-latency=18 --drop-squashed"
)
run_one() {
  IFS='|' read -r name cwd bin flags <<< "$1"
  cd "$cwd" || exit 1
  start=$(date +%s)
  $G -d $OUT/$name $CFG $flags $bin > $OUT/$name.log 2>&1
  echo "$name exit=$? $(( $(date +%s) - start ))s" >> $OUT/done.txt
}
export -f run_one
export G CFG OUT
rm -f $OUT/done.txt
printf '%s\n' "${RUNS[@]}" | xargs -P 7 -I{} bash -c 'run_one "$@"' _ {}
echo ALL_DONE >> $OUT/done.txt
