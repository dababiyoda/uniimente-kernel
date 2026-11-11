"""Run only the greg/authority.py mutants of scripts/ci/check_whole_output_mutants.py (reviewer's scratch)."""
import importlib.util, sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, str(root / "scripts/ci"))
spec = importlib.util.spec_from_file_location("gate", root / "scripts/ci/check_whole_output_mutants.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
gate.MUTANTS = [m for m in gate.MUTANTS if m[1] == "greg/authority.py"]
print("authority mutants:", len(gate.MUTANTS))
sys.exit(gate.main())
