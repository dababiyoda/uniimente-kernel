#!/usr/bin/env python3
"""Verifier v5 check C12: parity between uniimente_kernel.events and
contracts/event.schema.json, plus a behavioral spine check (emit ->
hash-chain -> causal walk; hostile envelopes rejected).
Logs a run record. Exit 0 = pass."""
import json, os, sys, tempfile, datetime

ROOT = os.path.dirname(os.path.abspath(__file__)) + "/.."
sys.path.insert(0, os.path.join(ROOT, "sdk-python"))
from uniimente_kernel import events  # noqa: E402
from uniimente_kernel.ledger import DecisionLedger  # noqa: E402

failures, passes = [], []

def check(name, cond):
    (passes if cond else failures).append(f"C12: {name}")

with open(os.path.join(ROOT, "contracts", "event.schema.json")) as f:
    schema = json.load(f)
props = schema["properties"]

# --- Static parity: module constants vs the wire schema -----------------
check("field set parity", set(props) == set(events.EVENT_FIELDS))
check("required set parity", set(schema["required"]) == set(events.REQUIRED_FIELDS))
check("sensitivity enum parity", set(props["sensitivity"]["enum"]) == set(events.SENSITIVITIES))
check("specversion const parity", props["specversion"]["const"] == events.SPECVERSION)
# Pattern-level parity: drift in either copy is caught here, not in production.
check("type pattern parity", props["type"]["pattern"] == events._TYPE_RE.pattern)
check("source spiffe pattern parity", props["source"]["pattern"] == events._SPIFFE_RE.pattern)
check("actor spiffe pattern parity", props["actor"]["pattern"] == events._SPIFFE_RE.pattern)
check("hash pattern parity", schema["$defs"]["hash"]["pattern"] == events._HASH_RE.pattern)
check("confidence bounds parity",
      props["confidence"]["minimum"] == 0 and props["confidence"]["maximum"] == 1)

# --- Behavioral: the spine emits chained, causally walkable events ------
ORG = "spiffe://uniimente.internal/organ/daleobanks"
AGENT = "spiffe://uniimente.internal/organ/daleobanks/agent/publisher"
with tempfile.TemporaryDirectory() as tmp:
    spine = events.EventSpine(
        DecisionLedger(path=os.path.join(tmp, "events.jsonl")),
        source=ORG, actor=AGENT, legal_principal="alfonso-lopez", policy_version="1.0.0")
    a = spine.emit("signal.detected", data={"signal_type": "operator_thought"})
    b = spine.chain("approval.requested", a)
    c = spine.chain("action.committed", b)
    ok, bad = spine.ledger.verify_chain()
    check("emitted events hash-chain verifies", ok and bad is None)
    walk = [e["id"] for e in spine.causal_chain(c.id)]
    check("causal walk reaches origin", walk == [a.id, b.id, c.id])
    check("replay filters by type", len(spine.replay("approval.requested")) == 1)

# --- Hostile: malformed/attack-shaped envelopes are rejected ------------
valid = {
    "specversion": "1.0",
    "id": "123e4567-e89b-42d3-a456-426614174000",
    "type": "signal.detected",
    "source": ORG,
    "actor": AGENT,
    "legal_principal": "alfonso-lopez",
    "time": "2026-07-19T00:00:00+00:00",
    "sensitivity": "internal",
    "causal_parent": None,
}
for name, mutate in (
    ("unknown field rejected", lambda d: d.update(execute_now=True)),
    ("non-spiffe actor rejected", lambda d: d.update(actor="daleobanks")),
    ("non-sha256 evidence ref rejected", lambda d: d.update(evidence_refs=["md5:abc"])),
    ("self-authored authority rejected", lambda d: d.update(legal_principal="")),
):
    d = dict(valid)
    mutate(d)
    try:
        events.validate_event_dict(d)
        check(name, False)
    except events.EventValidationError:
        check(name, True)

for p in passes: print("PASS", p)
for f in failures: print("FAIL", f)
run = {"ts_utc": datetime.datetime.now(datetime.UTC).isoformat(),
       "command": "python3 verifier/verify_events.py",
       "exit_code": 0 if not failures else 1, "passes": passes, "failures": failures}
os.makedirs(os.path.join(ROOT, "verifier/runs"), exist_ok=True)
name = os.path.join(ROOT, "verifier/runs", run["ts_utc"].replace(":", "-") + "-events.json")
json.dump(run, open(name, "w"), indent=2)
print(f"run recorded -> {name}")
sys.exit(run["exit_code"])
