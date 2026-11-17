#!/bin/bash
# LLC MPKI phase profile of the _r benchmarks (atomic CPU, no prefetching)
TOTAL=${1:-3000000000}
INTERVAL=${2:-500000000}
G=~/gem5/build/X86/gem5.opt
CFG=~/hermes_work/configs/hermes_se.py
CPU=~/spec2017/benchspec/CPU
OUT=~/hermes_work/out/profile_r
mkdir -p $OUT
# name|binary|options|stdin
BENCHES=(
  "519.lbm_r|lbm_r|3000 reference.dat 0 0 100_100_130_ldc.of|"
  "549.fotonik3d_r|fotonik3d_r||"
  "554.roms_r|roms_r||ocean_benchmark2.in.x"
  "503.bwaves_r|bwaves_r|bwaves_1|bwaves_1.in"
  "520.omnetpp_r|omnetpp_r|-c General -r 0|"
)
run_one() {
  IFS='|' read -r name bin opts inp <<< "$1"
  d=$CPU/$name/run/run_base_refrate_mytest-m64.0000
  cd $d || return
  $G -d $OUT/$name $CFG --cmd=$d/${bin}_base.mytest-m64 --options="$opts" \
     --input="$inp" --mem-size=8GB --measure=$TOTAL \
     --profile-interval=$INTERVAL > $OUT/$name.log 2>&1
  echo "done $name $?" >> $OUT/done.txt
}
export -f run_one
export G CFG CPU OUT TOTAL INTERVAL
printf '%s\n' "${BENCHES[@]}" | xargs -P 3 -I{} bash -c 'run_one "$@"' _ {}
for d in $OUT/*/; do
  printf '%-18s' $(basename $d)
  awk -v n=$INTERVAL '/^system.llc.demandMisses::total/{printf " %6.2f", $2*1000/n}' $d/stats.txt
  echo
done > $OUT/summary.txt
echo ALL_DONE >> $OUT/done.txt
