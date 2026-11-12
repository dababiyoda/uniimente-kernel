#!/bin/bash
S=/tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad
while kill -0 21665 2>/dev/null; do sleep 20; done
cd $S/rcu-merge && (time timeout 3000 $S/venv-mind/bin/python -m pytest tests/unit/test_greg_compile_unanswered.py tests/unit/test_greg_functional_reconstitution.py tests/unit/test_greg_revoked_device_authority.py tests/unit/test_greg_retained_receipt_history.py -q -p no:cacheprovider 2>&1 | tail -40) > $S/rcu-out/merged-tests.txt 2>&1
cd $S/review-cu && TMPDIR=$S/rcu-tmp $S/venv-mind/bin/python $S/rcu-probes/my_mutants.py $S/review-cu > $S/rcu-out/my-mutants.txt 2>&1
cd $S/review-cu && TMPDIR=$S/rcu-tmp $S/venv-mind/bin/python scripts/ci/check_unmeasured_check_mutants.py > $S/rcu-out/gate-unmeasured-check.txt 2>&1; echo "exit $?" >> $S/rcu-out/gate-unmeasured-check.txt
cd $S/review-cu && TMPDIR=$S/rcu-tmp $S/venv-mind/bin/python scripts/ci/check_reconstitution_mutants.py > $S/rcu-out/gate-reconstitution.txt 2>&1; echo "exit $?" >> $S/rcu-out/gate-reconstitution.txt
echo done > $S/rcu-out/chain.done
