"""Apply each surviving mutant in a scratch copy and print pytest's own summary line (passed vs error)."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(sys.argv[1]).resolve()
SURV = [
    ("greg/missions.py", "R09 a non-dict output is read as unanswered",
     '    if not isinstance(output, dict):\n        return None\n    if isinstance(output.get("schema"), str)',
     '    if not isinstance(output, dict):\n        return "not a receipt"\n    if isinstance(output.get("schema"), str)'),
    ("greg/cognition/compiler.py", "R15 the first refused step is named instead of the last", '"step": refused[-1]}', '"step": refused[0]}'),
    ("greg/cognition/compiler.py", "R18 the schema stays 0.2 though receipts carry host_stop",
     'SCHEMA = "greg-competency-compilation/0.3"', 'SCHEMA = "greg-competency-compilation/0.2"'),
]
with tempfile.TemporaryDirectory(prefix="rcu-surv-", dir=os.environ.get("TMPDIR")) as temp:
    repo = Path(temp) / "repo"
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
    env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"}
    for target, name, old, new in SURV:
        p = repo / target; orig = p.read_text(); assert orig.count(old) == 1
        p.write_text(orig.replace(old, new))
        try:
            r = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/unit/test_greg_compile_unanswered.py"],
                               cwd=repo, env=env, capture_output=True, text=True, timeout=900)
        finally:
            p.write_text(orig)
        print(name, "-> exit", r.returncode, "|", r.stdout.strip().splitlines()[-1], flush=True)
