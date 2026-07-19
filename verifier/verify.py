#!/usr/bin/env python3
"""Verifier v1 for uniimente-kernel canonical artifacts. Exit 0 = pass."""
import os, sys, json, glob, datetime

ROOT = os.path.dirname(os.path.abspath(__file__)) + "/.."
sys.path.insert(0, ROOT)
os.chdir(ROOT)

failures, passes = [], []

def check(cid, ok, msg):
    (passes if ok else failures).append(f"{cid}: {msg}")

crit = json.load(open("verifier/v1/criteria.json"))

# C1: existence
missing = [f for f in crit["checks"][0]["files"] if not (os.path.isfile(f) and os.path.getsize(f) > 0)]
check("C1", not missing, f"missing/empty: {missing}" if missing else f"all {len(crit['checks'][0]['files'])} canonical files present")

# C2: JSON schemas
bad = []
for f in glob.glob("contracts/*.schema.json"):
    try:
        d = json.load(open(f))
        for k in ("$schema", "title", "type", "required"):
            if k not in d: bad.append(f"{f}: missing {k}")
        if d.get("type") != "object": bad.append(f"{f}: type != object")
        if "2020-12" not in d.get("$schema",""): bad.append(f"{f}: not draft 2020-12")
    except Exception as e:
        bad.append(f"{f}: {e}")
schemas = glob.glob("contracts/*.schema.json")
check("C2", not bad and len(schemas) == 9, "; ".join(bad) if bad else f"{len(schemas)} valid 2020-12 schemas")

# C3: YAML parse
try:
    import yaml
    bad = []
    for f in glob.glob("**/*.yaml", recursive=True):
        if f.startswith("verifier/"): continue
        try:
            d = yaml.safe_load(open(f))
            if not isinstance(d, dict) or not d: bad.append(f"{f}: empty or not a mapping")
        except Exception as e:
            bad.append(f"{f}: {e}")
    check("C3", not bad, "; ".join(bad) if bad else "all YAML parse as non-empty mappings")
except ImportError:
    check("C3", False, "pyyaml unavailable")

# C4: UCL structural sanity
bad = []
for f in glob.glob("constitution/*.ucl"):
    t = open(f).read()
    if t.count("{") != t.count("}"): bad.append(f"{f}: unbalanced braces")
    if "{" not in t: bad.append(f"{f}: no blocks")
check("C4", not bad, "; ".join(bad) if bad else "all .ucl structurally sane")

# C5: doctrine presence
blob = " ".join(open(f).read().lower() for f in glob.glob("constitution/*.ucl") + glob.glob("authority/*.yaml"))
needles = crit["checks"][4]["needles"]
missing = [n for n in needles if n not in blob]
check("C5", not missing, f"missing doctrine terms: {missing}" if missing else "kernel invariant + sovereignty + non-delegables present")

# C6: test dirs
bad = [d for d in crit["checks"][5]["dirs"] if not glob.glob(os.path.join(d, "*.yaml"))]
check("C6", not bad, f"dirs without spec files: {bad}" if bad else "6 doctrine test dirs each hold >=1 spec")

# C7: docs
missing = [f for f in crit["checks"][6]["files"] if not (os.path.isfile(f) and os.path.getsize(f) > 0)]
check("C7", not missing, f"missing: {missing}" if missing else "README/LICENSE/docs present")

# C8: module readmes
bad = [d for d in crit["checks"][7]["dirs"] if not os.path.isfile(os.path.join(d, "README.md"))]
check("C8", not bad, f"missing module READMEs: {bad}" if bad else "8 module placeholder READMEs present")

for p in passes: print("PASS", p)
for f_ in failures: print("FAIL", f_)
status = "PASS" if not failures else "FAIL"
run = {
  "ts_utc": datetime.datetime.now(datetime.UTC).isoformat(),
  "command": "python3 verifier/verify.py",
  "exit_code": 0 if not failures else 1,
  "passes": passes, "failures": failures,
}
os.makedirs("verifier/runs", exist_ok=True)
name = f"verifier/runs/{run['ts_utc'].replace(':','-')}.json"
json.dump(run, open(name, "w"), indent=2)
print(f"run recorded -> {name} :: {status}")
sys.exit(run["exit_code"])
