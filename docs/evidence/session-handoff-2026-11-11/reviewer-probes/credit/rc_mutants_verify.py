"""Re-run named mutants and print pytest's return code and summary line, to tell a true survivor from an invalid one."""
import os, shutil, subprocess, sys, tempfile, importlib.util
from pathlib import Path
ROOT, names = Path(sys.argv[1]), sys.argv[2:]
src = (Path(__file__).with_name("rc_mutants.py")).read_text().replace("raise SystemExit(run(MUTANTS, TESTS, \"rc-mutants-\", root=ROOT))", "")
sys.argv = [sys.argv[0], str(ROOT)]
ns = {"__file__": str(Path(__file__).with_name("rc_mutants.py"))}
exec(compile(src, "rc_mutants.py", "exec"), ns)
with tempfile.TemporaryDirectory(prefix="rc-mv-") as temp:
    repo = Path(temp) / "repo"
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
    env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"}
    for target, name, old, new in ns["MUTANTS"]:
        if not any(name.startswith(n + " ") for n in names):
            continue
        path = repo / target; original = path.read_text()
        assert original.count(old) == 1, name
        path.write_text(original.replace(old, new))
        try:
            r = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", ns["TESTS"]], cwd=repo, env=env, capture_output=True, text=True, timeout=1500)
        finally:
            path.write_text(original)
        print(name.split(" ")[0], "returncode", r.returncode, "|", r.stdout.strip().splitlines()[-1], flush=True)
