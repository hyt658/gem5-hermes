#!/bin/bash
# mcf memory-side diagnosis: the takeover stats and the load numbers in the
# Hermes debug output, on the setting of the 11/09 mcf runs (TSO, DDR4-2400,
# POPET threshold -17), whose baseline is reused.
#   bash run.sh [out dir]
G=~/gem5/build/X86/gem5.opt
CFG=~/gem5/configs/hermes/se_hermes.py
HERE=$(cd "$(dirname "$0")" && pwd)
O=${1:-~/mcf_diag}
MCF=~/spec2017/benchspec/CPU/605.mcf_s
RUN=$MCF/run/run_base_refspeed_mytest-m64.0000
MCFBIN=$MCF/build/build_base_mytest-m64.0000/mcf_s
OPT="--mem-size=8GB --fast-forward=1000000000 --warmup=20000000 \
--max-insts=50000000 --options=inp.in"
BASE=$HERE/../2026-11-09_first_runs
mkdir -p $O

# run NAME ARGS...: one mcf run in the background, started where inp.in is
run() {
    local name=$1
    shift
    (cd $RUN && $G -d $O/$name "$@" > $O/$name.log 2>&1
     echo "$name: exit $?" > $O/$name.rc) &
}

# Hermes-O and Hermes-P for the new stats, the control run whose Hermes
# requests almost all come too late, and Hermes-O with the debug output of a
# 1 ms window
run mcf_O $CFG $OPT --hermes --popet $MCFBIN
run mcf_P $CFG $OPT --hermes --popet --issue-latency=18 $MCFBIN
run mcf_L100 $CFG $OPT --hermes --popet --issue-latency=100 $MCFBIN
run mcf_O_trace --debug-flags=HermesMem,POPET --debug-start=545000000000 \
    --debug-end=546000000000 --debug-file=hermes_trace.gz \
    $CFG $OPT --hermes --popet $MCFBIN
wait

cat $O/*.rc
python3 $HERE/decompose.py $BASE/mcf_base $O/mcf_O $O/mcf_L100 $O/mcf_P
python3 $HERE/hermes_attrib.py $O/mcf_O_trace/hermes_trace.gz
