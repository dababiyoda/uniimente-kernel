#!/usr/bin/env python3
"""Verifier v4 check C11: parity between uniimente_kernel.contracts and the
wire schema files. Logs a run record. Exit 0 = pass."""
import json, os, sys, datetime

ROOT = os.path.dirname(os.path.abspath(__file__)) + "/.."
sys.path.insert(0, os.path.join(ROOT, "sdk-python"))
from uniimente_kernel import contracts  # noqa: E402

failures, passes = [], []

def check(name, cond):
    (passes if cond else failures).append(f"C11: {name}")

def load(name):
    with open(os.path.join(ROOT, "contracts", name)) as f:
        return json.load(f)

sig = load("venture-signal.schema.json")["properties"]
asm = load("signal-assessment.schema.json")["properties"]
inst = load("venture-assessment.schema.json")["properties"]

check("signal_type enum parity", set(sig["signal_type"]["enum"]) == set(contracts.ALLOWED_SIGNAL_TYPES))
check("urgency enum parity", set(sig["urgency"]["enum"]) == set(contracts.ALLOWED_URGENCY))
check("status enum parity", set(sig["status"]["enum"]) == set(contracts.ALLOWED_STATUSES))
check("signal schema_version const", sig["schema_version"]["const"] == contracts.SCHEMA_VERSION)
check("go_no_go enum parity", set(asm["go_no_go"]["enum"]) == set(contracts.ALLOWED_GO_NO_GO))
check("risk_level enum parity", set(asm["risk_level"]["enum"]) == set(contracts.ALLOWED_RISK_LEVELS))
check("assessment requires_human_approval const", asm["requires_human_approval"]["const"] is True)
check("assessment schema_version const", asm["schema_version"]["const"] == contracts.SCHEMA_VERSION)
check("institutional verdict enum parity", set(inst["verdict"]["enum"]) == set(contracts.ALLOWED_GO_NO_GO))

try:
    contracts.validate_packet_wire({"id": "p", "signal_type": "operator_thought", "core_thesis": "t"})
    check("minimal conforming packet validates", True)
except Exception as exc:
    check(f"minimal conforming packet validates ({exc})", False)
try:
    contracts.validate_assessment_wire({"go_no_go": "go", "opportunity_packet_id": "p",
                                        "requires_human_approval": False})
    check("self-executing assessment rejected", False)
except ValueError:
    check("self-executing assessment rejected", True)

for p in passes: print("PASS", p)
for f in failures: print("FAIL", f)
run = {"ts_utc": datetime.datetime.now(datetime.UTC).isoformat(),
       "command": "python3 verifier/verify_contracts.py",
       "exit_code": 0 if not failures else 1, "passes": passes, "failures": failures}
os.makedirs(os.path.join(ROOT, "verifier/runs"), exist_ok=True)
name = os.path.join(ROOT, "verifier/runs", run["ts_utc"].replace(":", "-") + "-contracts.json")
json.dump(run, open(name, "w"), indent=2)
print(f"run recorded -> {name}")
sys.exit(run["exit_code"])
