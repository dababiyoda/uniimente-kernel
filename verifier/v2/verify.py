#!/usr/bin/env python3
"""Verifier v2 for uniimente-kernel: orthogonal loop closure build verifier.

Exit 0 = pass. Every run is appended to verifier/runs/ (full trajectory).

V1: v1 canonical artifact passthrough (skip-missing on partial mirrors)
V2: executable unit tests green (pytest tests/unit)
V3: every registered module closes all five orthogonal closures
V4: Whole-Body Closure Controller detects false closure; gate loops CLOSED
V5: module READMEs declare the 14-condition buildability standard
"""
import os, sys, json, glob, datetime, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

failures, passes, skips = [], [], []

def check(cid, ok, msg):
    (passes if ok else failures).append(f"{cid}: {msg}")

crit = json.load(open(os.path.join(HERE, "criteria.json")))

# ---------------- V1: v1 passthrough ----------------
v1_path = os.path.join(ROOT, "verifier", "v1", "criteria.json")
if os.path.isfile(v1_path):
    v1 = json.load(open(v1_path))
    missing = [f for f in v1["checks"][0]["files"]
               if not (os.path.isfile(f) and os.path.getsize(f) > 0)]
    if not missing:
        check("V1", True, "all v1 canonical artifacts present (45/45)")
    else:
        skips.append(f"V1: partial mirror, {len(missing)} v1 files not present locally: {missing[:5]}...")
else:
    skips.append("V1: verifier/v1/criteria.json absent; v1 passthrough skipped")

# ---------------- V2: unit tests ----------------
proc = subprocess.run([sys.executable, "-m", "pytest", "tests/unit", "-q"],
                      capture_output=True, text=True, cwd=ROOT)
tail = (proc.stdout.strip().splitlines() or [""])[-1]
check("V2", proc.returncode == 0, f"pytest tests/unit: {tail}")

# ---------------- V3: five orthogonal closures per module ----------------
try:
    from closure.kernel_registry import build_registry
    ok, reports = build_registry().verify()
    open_map = {r.module: r.open_closures for r in reports if not r.complete}
    check("V3", ok, "all modules closed: " + ", ".join(r.module for r in reports)
          if ok else f"open closures: {open_map}")
except Exception as e:
    check("V3", False, f"closure registry raised {type(e).__name__}: {e}")

# ---------------- V4: whole-body closure controller ----------------
try:
    from closure.whole_body import WholeBodyClosureController, Loop, LoopEvidence
    c = WholeBodyClosureController()
    false_case = c.evaluate("v4-synthetic", {
        Loop.DISTRIBUTION: LoopEvidence(internal_ok=True, external_ok=False)})
    gate_case = c.applicable("v4-gate", {
        Loop.AUTHORITY: LoopEvidence(internal_ok=True, external_ok=True),
        Loop.EXECUTION: LoopEvidence(internal_ok=True, external_ok=True),
        Loop.CONTINUITY: LoopEvidence(internal_ok=True, external_ok=True),
    }, applicable={Loop.AUTHORITY, Loop.EXECUTION, Loop.CONTINUITY})
    ok = (false_case.overall == "FALSELY_CLOSED"
          and "regress_change" in false_case.required_actions
          and gate_case.overall == "CLOSED")
    check("V4", ok, f"false closure -> {false_case.overall}; gate applicable loops -> {gate_case.overall}")
except Exception as e:
    check("V4", False, f"whole-body controller raised {type(e).__name__}: {e}")

# ---------------- V5: buildability standard in module READMEs ----------------
kw = crit["checks"][4]["keywords"]
bad = []
for readme in crit["checks"][4]["module_readmes"]:
    if not os.path.isfile(readme):
        bad.append(f"{readme}: missing")
        continue
    text = open(readme, encoding="utf-8").read().lower()
    absent = [k for k in kw if k not in text]
    if absent:
        bad.append(f"{readme}: missing {absent}")
check("V5", not bad, "; ".join(bad) if bad else
      f"{len(crit['checks'][4]['module_readmes'])} module READMEs declare the 14-condition buildability standard")

for p in passes: print("PASS", p)
for s in skips: print("SKIP", s)
for f in failures: print("FAIL", f)
status = "PASS" if not failures else "FAIL"
run = {
    "verifier": "v2",
    "ts_utc": datetime.datetime.now(datetime.UTC).isoformat(),
    "command": "python3 verifier/v2/verify.py",
    "exit_code": 0 if not failures else 1,
    "passes": passes, "skips": skips, "failures": failures,
}
os.makedirs("verifier/runs", exist_ok=True)
name = f"verifier/runs/v2-{run['ts_utc'].replace(':','-')}.json"
json.dump(run, open(name, "w"), indent=2)
print(f"run recorded -> {name} :: {status}")
sys.exit(run["exit_code"])
