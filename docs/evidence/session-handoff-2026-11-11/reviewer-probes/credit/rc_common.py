"""Shared helpers for the adversarial probes (copied from the branch's test file so they run on base and head)."""
import json, sys, tempfile, os
from pathlib import Path
from greg.body import Body
from greg import corrections, sop
from greg.cognition import compiler, settlement
from tests.greg_fixtures import Clock, make_body, mission, note_check, signed, workspace, write_strategy

METHOD = "cognition.swarm"
SPHERE = {"function": "sphere", "bounds": [[-5.12, 5.12]] * 3, "budget": 300, "shift": [0.5, -0.25, 1.0]}

def solve_check(check_id, problem, seed, value=1e6):
    params = {"problem_id": problem, "compile": {"geometry": {"geometry": "optimization"},
                                                 "data": {**SPHERE, "seed": seed}}}
    return {"check_id": check_id, "description": "fitness bound",
            "sensor": {"capability": "cognition.solve", "target": "cognition:bb", "params": params},
            "predicate": {"op": "lte", "field": "result.fitness", "value": value}}

def solve_mission(mid, *checks, strategies=(), capabilities=("cognition.solve",), targets=("cognition:*",),
                  ceiling="read_only"):
    return mission(mid, checks=list(checks), strategies=list(strategies), capabilities=list(capabilities),
                   targets=targets, ceiling=ceiling)

def open_body(tmp_path, *, attach=(METHOD,), read_roots=None):
    home, key, body_id, data = make_body(Path(tmp_path), read_roots=read_roots)
    clock = Clock()
    body = Body(home, clock=clock).open()
    body.boot()
    for cid in attach:
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": cid}))
    def sign(kind, payload):
        return body.apply(signed(key, body_id, kind, payload))
    return body, sign, clock, data, (home, key, body_id)

def turn(body, clock, ticks=3):
    for _ in range(ticks):
        body.tick(); clock.advance(31)

def credit(body):
    return {k: list(v) for k, v in compiler._settled_counts(body.journal).items()}

def credited(journal):
    return sorted((o["mission_id"], o["check_id"], o["correct"]) for o in settlement.measured_outcomes(journal))

def reject(sign, event_id, text, verdict="reject"):
    return sign("CRITIQUE", {"target_event_id": event_id, "verdict": verdict, "evidence_type": "founder_judgment",
                             "text": text})

def closure_of(journal, mid):
    [event] = [e for e in journal.replay("mission.achieved") if e.payload["mission_id"] == mid]
    return event

def note_mission(home, mid, text):
    return mission(mid, checks=[note_check("n", workspace(home, mid) / "n.txt", text)],
                   strategies=[write_strategy("w", "n.txt", text, ["n"])], capabilities=["fs.read", "fs.write"])

def contained(journal):
    r = getattr(corrections, "contained_receipts")(journal)
    m = getattr(corrections, "contained_missions", lambda j: "N/A")(journal)
    return {"receipts": sorted(x[:12] for x in r), "missions": m if m == "N/A" else sorted(m)}

def causes(journal):
    return [(e.payload["class"], e.payload["root"]["mission_id"], e.payload["root"]["check_id"]) for e in journal.replay("evidence.invalidated")]

def settled_records(journal):
    return [(e.payload.get("mission_id"), e.payload.get("check_id"), e.payload.get("invalidated"), (e.payload.get("reason") or "")[:60]) for e in journal.replay("cognition.settled")]

def tmp():
    base = os.environ.get("RC_TMP", "/tmp")
    return tempfile.mkdtemp(prefix="rc-", dir=base)

def out(name, value):
    print(f"{name}: {json.dumps(value, default=str)}", flush=True)
