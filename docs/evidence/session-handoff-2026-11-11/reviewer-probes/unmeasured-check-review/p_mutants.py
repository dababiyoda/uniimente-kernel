"""The two entries 2d883484 added to scripts/ci/check_whole_output_mutants.py, run alone through the shared harness."""
import sys
from pathlib import Path
root = Path(sys.argv[1]); sys.path.insert(0, str(root / "scripts" / "ci"))
from mutation_harness import run
A = '            if set(s.get("requires", [])) & unproven:'
M = [("greg/missions.py", "the hold on an unproven precondition is dropped", A, "            if False:"),
     ("greg/missions.py", "a founder approval overrides the hold on an unproven precondition", A,
      '            if set(s.get("requires", [])) & unproven and not m.approved_scopes:')]
raise SystemExit(run(M, "tests/unit/test_greg_precondition_unheld.py", "rv-p-mutants-", root=root))
