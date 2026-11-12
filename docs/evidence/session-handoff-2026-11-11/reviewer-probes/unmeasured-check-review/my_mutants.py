"""Reviewer's mutants of e917a0db's changed lines and neighbours. Each runs the two test files of the change.
usage: my_mutants.py <root worktree> <out log> [names...]   (TMPDIR must point into the scratchpad)"""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(sys.argv[1]); only = set(sys.argv[3:])
PY = sys.executable
T = "greg/missions.py"
ERR = "        errors = set(self.sensor_errors) | set(self.capability_faults)"
PUR = "        return self._pursue(m, now, failing - self.inconclusive - set(self.capability_faults), evidence)"
MUTANTS = [
    ("A errors: sensor_errors dropped (only capability faults count as unmeasured)", ERR,
     "        errors = set(self.capability_faults)"),
    ("B retry whenever anything is unmeasured, even beside a real failure",
     "        if errors and errors == failing:", "        if errors:"),
    ("C pursue: inconclusive checks pursued again", PUR,
     "        return self._pursue(m, now, failing - set(self.capability_faults), evidence)"),
    ("D pursue: every sensor error left out (a refused sensor loses its route)", PUR,
     "        return self._pursue(m, now, failing - self.inconclusive - set(self.capability_faults) - set(self.sensor_errors), evidence)"),
    ("E any capability fault makes the whole pass a retry, real failures included", ERR,
     "        errors = failing if self.capability_faults else set(self.sensor_errors)"),
    ("F pursue: only sensor-call faults left out; a Mind-reported fault is pursued beside a real failure", PUR,
     "        return self._pursue(m, now, failing - self.inconclusive - (set(self.capability_faults) & set(self.sensor_errors)), evidence)"),
    ("G alone-retry only when nothing but capability faults fail (a refused sensor beside a Mind fault is pursued, as on 8d205324)", ERR,
     "        errors = set(self.sensor_errors) | (set(self.capability_faults) if failing == set(self.capability_faults) else set())"),
    ("H SENSOR_FAILURE asked on the first unmeasured round", "            if streak >= 3:", "            if streak >= 1:"),
    ("I the retry waits an hour instead of 30 seconds", "            self._schedule(m, now, 30 * streak or 30)",
     "            self._schedule(m, now, 3600)"),
    ("K every fault the Mind reports counts as a capability fault, a host stop included",
     "                    if is_capability_fault(formed, detail, failure_class):\n                        self.capability_faults[check[\"check_id\"]] = (formed, detail, sensor.get(\"params\", {}))",
     "                    if True:\n                        self.capability_faults[check[\"check_id\"]] = (formed, detail, sensor.get(\"params\", {}))"),
    ("L SENSOR_FAILURE never asked (the retry never escalates)", "            if streak >= 3:", "            if False:"),
    ("M self-repair skipped on the unblocked path (only the blocked watch repairs)",
     "        repaired = self._self_repair(m, now)\n        if repaired is not None:\n            return repaired\n        # A check whose formed",
     "        repaired = None\n        if repaired is not None:\n            return repaired\n        # A check whose formed"),
]
TESTS = ["tests/unit/test_greg_functional_reconstitution.py", "tests/integration/test_greg_mind_constructs_capability.py"]
EXTRA = sys.argv[2].endswith(".extra.log")
if EXTRA:
    TESTS = ["tests/unit/test_greg_unmeasured_not_failed.py", "tests/unit/test_greg_self_repair.py"]

def one(mut):
    name, old, new = mut
    with tempfile.TemporaryDirectory(prefix="rv-mut-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        p = repo / T; src = p.read_text()
        if src.count(old) != 1:
            return name, "STALE", ""
        p.write_text(src.replace(old, new))
        env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"}
        r = subprocess.run([PY, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", *TESTS], cwd=repo, env=env,
                           capture_output=True, text=True, timeout=1500)
        failed = [l for l in r.stdout.splitlines() if l.startswith(("FAILED", "ERROR"))]
        tail = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-200:]
        return name, ("CAUGHT" if r.returncode == 1 and failed else "SURVIVED" if r.returncode == 0 else f"INVALID rc={r.returncode}"), \
            tail + "".join("\n      " + f[:230] for f in failed)

todo = [m for m in MUTANTS if not only or m[0].split()[0] in only]
with open(sys.argv[2], "w") as log, ThreadPoolExecutor(max_workers=3) as pool:
    for name, verdict, detail in pool.map(one, todo):
        line = f"{verdict}: {name}\n    {detail}\n"
        log.write(line); log.flush(); print(line, end="", flush=True)
