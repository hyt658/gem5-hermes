#!/bin/bash
G=~/gem5/build/X86/gem5.opt
CFG=~/gem5/configs/hermes/se_hermes.py
OUT=~/popet_runs
cd $OUT
$G -d $OUT/scan_all_O $CFG --hermes $OUT/bin/scan_test > $OUT/scan_all_O.log 2>&1 &
$G -d $OUT/scan_popet_P $CFG --hermes --popet --issue-latency=18 $OUT/bin/scan_test > $OUT/scan_popet_P.log 2>&1 &
wait
echo SCAN2_DONE > $OUT/scan2_done.txt
