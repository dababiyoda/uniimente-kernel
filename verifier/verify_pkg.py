#!/usr/bin/env python3
"""Verifier v3 packaging check (C10): pip-install sdk-python to a temp target
and import uniimente_kernel from it. Logs a run record. Exit 0 = pass."""
import subprocess, sys, os, json, tempfile, datetime

ROOT = os.path.dirname(os.path.abspath(__file__)) + "/.."
failures, passes = [], []

with tempfile.TemporaryDirectory() as target:
    r = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--target", target,
                        os.path.join(ROOT, "sdk-python")], capture_output=True, text=True)
    (passes if r.returncode == 0 else failures).append(
        "C10-install: pip install succeeded" if r.returncode == 0 else f"C10-install: {r.stderr[-400:]}")
    if r.returncode == 0:
        r2 = subprocess.run([sys.executable, "-c",
            "import sys; sys.path.insert(0, %r); import uniimente_kernel as k; print(len(k.__all__))" % target],
            capture_output=True, text=True)
        ok = r2.returncode == 0 and r2.stdout.strip().isdigit() and int(r2.stdout.strip()) >= 12
        (passes if ok else failures).append(
            f"C10-import: {r2.stdout.strip()} symbols exported" if ok else f"C10-import: {r2.stderr[-400:]}")

for p in passes: print("PASS", p)
for f in failures: print("FAIL", f)
run = {"ts_utc": datetime.datetime.now(datetime.UTC).isoformat(),
       "command": "python3 verifier/verify_pkg.py",
       "exit_code": 0 if not failures else 1,
       "passes": passes, "failures": failures}
os.makedirs(os.path.join(ROOT, "verifier/runs"), exist_ok=True)
name = os.path.join(ROOT, "verifier/runs", run["ts_utc"].replace(":", "-") + "-pkg.json")
json.dump(run, open(name, "w"), indent=2)
print(f"run recorded -> {name}")
sys.exit(run["exit_code"])
