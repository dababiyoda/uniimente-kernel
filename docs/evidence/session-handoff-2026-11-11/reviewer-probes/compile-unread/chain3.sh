#!/bin/bash
S=/tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad
while [ ! -f $S/rcu-out/chain2.done ]; do sleep 20; done
cd $S/review-cu && TMPDIR=$S/rcu-tmp $S/venv-mind/bin/python $S/rcu-probes/verify_survivors.py $S/review-cu > $S/rcu-out/survivors-verified.txt 2>&1
echo done > $S/rcu-out/chain3.done
