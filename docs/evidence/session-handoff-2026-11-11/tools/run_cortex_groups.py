"""Run chosen groups of scripts/ci/check_cortex_mutants.py. usage (cwd = worktree): run_cortex_groups.py "mind construction" recovery"""
import sys, importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("gate", Path.cwd() / "scripts/ci/check_cortex_mutants.py")
gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)
gate.GROUPS = [g for g in gate.GROUPS if g[0] in sys.argv[1:]]
raise SystemExit(gate.main())
