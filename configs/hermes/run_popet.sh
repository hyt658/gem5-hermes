#!/bin/bash
# First POPET / Hermes runs for the status report.  Results: ~/popet_runs/<name>/
G=~/gem5/build/X86/gem5.opt
CFG=~/gem5/configs/hermes/se_hermes.py
BIN=~/popet_runs/bin
MCF=~/spec2017/benchspec/CPU/605.mcf_s
OUT=~/popet_runs
MCFOPT="--mem-size=8GB --fast-forward=1000000000 --warmup=20000000 --max-insts=50000000 --options=inp.in"

# name|cwd|binary|flags
RUNS=(
  "chase_base|$OUT|$BIN/pointer_chase|"
  "chase_popet|$OUT|$BIN/pointer_chase|--popet"
  "chase_all_O|$OUT|$BIN/pointer_chase|--hermes"
  "chase_popet_O|$OUT|$BIN/pointer_chase|--hermes --popet"
  "chase_popet_P|$OUT|$BIN/pointer_chase|--hermes --popet --issue-latency=18"
  "scan_base|$OUT|$BIN/scan_test|"
  "scan_popet|$OUT|$BIN/scan_test|--popet"
  "scan_popet_O|$OUT|$BIN/scan_test|--hermes --popet"
  "mcf_base|$MCF/run/run_base_refspeed_mytest-m64.0000|$MCF/build/build_base_mytest-m64.0000/mcf_s|$MCFOPT"
  "mcf_all_O|$MCF/run/run_base_refspeed_mytest-m64.0000|$MCF/build/build_base_mytest-m64.0000/mcf_s|$MCFOPT --hermes"
  "mcf_popet_O|$MCF/run/run_base_refspeed_mytest-m64.0000|$MCF/build/build_base_mytest-m64.0000/mcf_s|$MCFOPT --hermes --popet"
  "mcf_popet_P|$MCF/run/run_base_refspeed_mytest-m64.0000|$MCF/build/build_base_mytest-m64.0000/mcf_s|$MCFOPT --hermes --popet --issue-latency=18"
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
