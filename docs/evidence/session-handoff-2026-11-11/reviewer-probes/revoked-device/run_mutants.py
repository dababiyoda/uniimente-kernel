"""Apply each reviewer mutant in a scratch copy and print the pytest summary line (so a survivor is shown to be
'50 passed', not an import error). A control mutant from the builder's own gate comes first and must be caught."""
import importlib.util, os, shutil, subprocess, sys, tempfile
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.argv = [sys.argv[0], str(root)] + sys.argv[2:]
spec = importlib.util.spec_from_file_location("rm", Path(__file__).with_name("reviewer_mutants.py"))
rm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rm)
only = sys.argv[2:]
CONTROL = ("C0 control (builder's own mutant): the fold ignores a device revocation", "greg/missions.py",
           '        if kind == "device.revoked":\n            self._revoked(data, event_id)\n            return\n', '')
mutants = [CONTROL] + [m for m in rm.MUTANTS if not only or m[0].split()[0] in only]
with tempfile.TemporaryDirectory(prefix="rdr-mut-") as temp:
    repo = Path(temp) / "repo"
    shutil.copytree(root, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
    env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"}
    for name, target, old, new in mutants:
        path = repo / target
        original = path.read_text()
        assert original.count(old) == 1, name
        path.write_text(original.replace(old, new))
        try:
            r = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", rm.TESTS],
                               cwd=repo, env=env, capture_output=True, text=True, timeout=1500)
        finally:
            path.write_text(original)
        last = [l for l in r.stdout.strip().splitlines() if l.strip()][-1]
        failed = [l.split("::")[1].split(" ")[0] for l in r.stdout.splitlines() if l.startswith("FAILED ")]
        print(("CAUGHT  " if r.returncode == 1 and failed else "SURVIVED" if r.returncode == 0 else "INVALID "),
              name, "|", last, "|", failed[:3], flush=True)
