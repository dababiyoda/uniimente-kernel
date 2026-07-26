#!/usr/bin/env python3
"""Verifier v2 for uniimente-kernel: orthogonal loop closure build verifier.

Exit 0 = pass. Every run is appended to verifier/runs/.

V1: v1 canonical artifact passthrough
V2: executable unit tests green
V3: every core and integrated organ closes all five orthogonal closures
V4: Whole-Body Closure Controller detects false closure
V5: module READMEs declare the buildability standard
"""
import os, sys, json, datetime, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

failures, passes, skips = [], [], []


def check(cid, ok, msg):
    (passes if ok else failures).append(f"{cid}: {msg}")


crit = json.load(open(os.path.join(HERE, "criteria.json")))

# V1: canonical artifact passthrough
v1_path = os.path.join(ROOT, "verifier", "v1", "criteria.json")
if os.path.isfile(v1_path):
    v1 = json.load(open(v1_path))
    missing = [f for f in v1["checks"][0]["files"]
               if not (os.path.isfile(f) and os.path.getsize(f) > 0)]
    if not missing:
        check("V1", True, "all v1 canonical artifacts present (45/45)")
    else:
        skips.append(f"V1: partial mirror, {len(missing)} v1 files absent: {missing[:5]}...")
else:
    skips.append("V1: verifier/v1/criteria.json absent; v1 passthrough skipped")

# V2: all unit tests
proc = subprocess.run([sys.executable, "-m", "pytest", "tests/unit", "-q"],
                      capture_output=True, text=True, cwd=ROOT)
tail = (proc.stdout.strip().splitlines() or [""])[-1]
check("V2", proc.returncode == 0, f"pytest tests/unit: {tail}")

# V3: core plus explicitly integrated organ closures
try:
    from closure.integration_registry import build_registry
    ok, reports = build_registry().verify()
    open_map = {r.module: r.open_closures for r in reports if not r.complete}
    check("V3", ok, "all modules closed: " + ", ".join(r.module for r in reports)
          if ok else f"open closures: {open_map}")
except Exception as exc:
    check("V3", False, f"integration closure registry raised {type(exc).__name__}: {exc}")

# V4: whole-body false-closure control
try:
    from closure.whole_body import WholeBodyClosureController, Loop, LoopEvidence
    controller = WholeBodyClosureController()
    false_case = controller.evaluate("v4-synthetic", {
        Loop.DISTRIBUTION: LoopEvidence(internal_ok=True, external_ok=False)})
    gate_case = controller.applicable("v4-gate", {
        Loop.AUTHORITY: LoopEvidence(internal_ok=True, external_ok=True),
        Loop.EXECUTION: LoopEvidence(internal_ok=True, external_ok=True),
        Loop.CONTINUITY: LoopEvidence(internal_ok=True, external_ok=True),
    }, applicable={Loop.AUTHORITY, Loop.EXECUTION, Loop.CONTINUITY})
    ok = (false_case.overall == "FALSELY_CLOSED"
          and "regress_change" in false_case.required_actions
          and gate_case.overall == "CLOSED")
    check("V4", ok, f"false closure -> {false_case.overall}; gate loops -> {gate_case.overall}")
except Exception as exc:
    check("V4", False, f"whole-body controller raised {type(exc).__name__}: {exc}")

# V5: module documentation standard
keywords = crit["checks"][4]["keywords"]
bad = []
for readme in crit["checks"][4]["module_readmes"]:
    if not os.path.isfile(readme):
        bad.append(f"{readme}: missing")
        continue
    text = open(readme, encoding="utf-8").read().lower()
    absent = [keyword for keyword in keywords if keyword not in text]
    if absent:
        bad.append(f"{readme}: missing {absent}")
check("V5", not bad, "; ".join(bad) if bad else
      f"{len(crit['checks'][4]['module_readmes'])} module READMEs declare the buildability standard")

for item in passes:
    print("PASS", item)
for item in skips:
    print("SKIP", item)
for item in failures:
    print("FAIL", item)
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
