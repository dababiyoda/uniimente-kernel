"""Which tests of the reconstitution lock fail under each of its gate's mutants (no -x)."""
import os, shutil, subprocess, sys, tempfile, importlib.util
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("g", ROOT / "scripts/ci/check_reconstitution_mutants.py")
sys.path.insert(0, str(ROOT / "scripts/ci")); g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
def one(mut):
    target, name, old, new = mut
    with tempfile.TemporaryDirectory(prefix="rv-lock-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        p = repo / target; src = p.read_text(); assert src.count(old) == 1
        p.write_text(src.replace(old, new))
        env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"}
        r = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rfEx", g.TESTS], cwd=repo, env=env,
                           capture_output=True, text=True, timeout=1500)
        lines = [l.split("::")[1].split(" ")[0] for l in r.stdout.splitlines() if l.startswith(("FAILED", "ERROR", "XFAIL", "XPASS"))]
        return name, r.stdout.strip().splitlines()[-1], lines
with ThreadPoolExecutor(max_workers=2) as pool:
    for name, tail, lines in pool.map(one, g.MUTANTS):
        print("MUTANT:", name, "|", tail); [print("    ", l) for l in lines]
