#!/bin/bash
# Final runs: every benchmark x every config. Results: $OUT/<bench>_<config>/
#   bash final_matrix.sh <bench list> [out dir] [parallel jobs]
# Bench list, one per line: name|run dir|binary|options|stdin file
G=~/gem5/build/X86/gem5.opt
CFG=~/gem5/configs/hermes/se_hermes.py
LIST=$1
OUT=${2:-~/final_runs}
JOBS=${3:-7}
COMMON="--mem-size=8GB --fast-forward=1000000000 --warmup=20000000 --max-insts=50000000"
CONFIGS=(
  "base|"
  "O_all|--hermes"
  "O_popet|--hermes --popet"
  "P_popet|--hermes --popet --issue-latency=18"
)
mkdir -p $OUT

run_one() {
  IFS='|' read -r bench cwd bin opts inp cname cflags <<< "$1"
  name=${bench}_$cname
  [ -f $OUT/$name/stats.txt ] && [ -s $OUT/$name/stats.txt ] && return
  cd "$cwd" || return
  start=$(date +%s)
  $G -d $OUT/$name $CFG $COMMON $cflags --options="$opts" --input="$inp" \
     $bin > $OUT/$name.log 2>&1
  echo "$name exit=$? $(( $(date +%s) - start ))s" >> $OUT/done.txt
}
export -f run_one
export G CFG OUT COMMON

# configs in the outer loop, so every benchmark gets its baseline first
for c in "${CONFIGS[@]}"; do
  grep -v '^#' $LIST | grep . | while read -r b; do echo "$b|$c"; done
done | xargs -P $JOBS -I{} bash -c 'run_one "$@"' _ {}
echo ALL_DONE >> $OUT/done.txt
