#!/usr/bin/env python3
"""Verifier v2 SDK check (C9): compile sdk-python and run its unit tests.
Logs a run record under verifier/runs/. Exit 0 = pass."""
import compileall, subprocess, sys, os, json, datetime

ROOT = os.path.dirname(os.path.abspath(__file__)) + "/.."
os.chdir(ROOT)
failures, passes = [], []

ok = compileall.compile_dir("sdk-python", quiet=1)
(passes if ok else failures).append("C9-compile: sdk-python compiles" if ok else "C9-compile: compilation failed")

r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "sdk-python/tests"],
                   capture_output=True, text=True)
summary = r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "no output"
(passes if r.returncode == 0 else failures).append(f"C9-tests: {summary}")

for p in passes: print("PASS", p)
for f in failures: print("FAIL", f)
run = {
  "ts_utc": datetime.datetime.now(datetime.UTC).isoformat(),
  "command": "python3 verifier/verify_sdk.py",
  "exit_code": 0 if not failures else 1,
  "passes": passes, "failures": failures,
  "test_output_tail": (r.stderr or "")[-1500:],
}
os.makedirs("verifier/runs", exist_ok=True)
name = f"verifier/runs/{run['ts_utc'].replace(':','-')}-sdk.json"
json.dump(run, open(name, "w"), indent=2)
print(f"run recorded -> {name}")
sys.exit(run["exit_code"])
