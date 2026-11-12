#!/bin/bash
S=/tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad
while [ ! -f $S/rcu-out/chain.done ]; do sleep 20; done
cd $S/rcu-merge && (time timeout 2400 $S/venv-mind/bin/python -m pytest tests/integration/test_greg_mind_constructs_capability.py tests/unit/test_greg_cognition_seed_path.py tests/unit/test_greg_handoff_evidence.py tests/unit/test_greg_background_dispatch.py tests/unit/test_greg_unmeasured_not_failed.py -q -p no:cacheprovider 2>&1 | tail -30) > $S/rcu-out/merged-tests-2.txt 2>&1
cd $S/rcu-merge-credit && (time timeout 2400 $S/venv-mind/bin/python -m pytest tests/unit/test_greg_compile_unanswered.py tests/unit/test_greg_evidence_corrections.py -q -p no:cacheprovider 2>&1 | tail -30) > $S/rcu-out/merged-credit-tests.txt 2>&1
cd $S/review-cu && (time timeout 2400 $S/venv-mind/bin/python -m pytest tests/unit/test_greg_mind_convergence.py tests/unit/test_mind_evidence_sources.py -q -p no:cacheprovider 2>&1 | tail -15) > $S/rcu-out/binding-tests-head.txt 2>&1
echo done > $S/rcu-out/chain2.done
