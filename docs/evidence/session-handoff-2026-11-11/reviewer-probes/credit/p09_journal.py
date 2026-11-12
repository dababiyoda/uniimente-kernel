"""Journal-tier probes with the branch's own World fixture: order, replay, depth 2, late dependents."""
import json, sys
from tests.unit.test_greg_evidence_corrections import World, file_read, CONTAINS, NOW
from greg import corrections
from datetime import timedelta

def base():
    w = World()
    w.mission("m:a", ("a", "fs.read", {"path": "/docs/a.txt"}, CONTAINS))
    w.mission("m:r", ("a", "fs.read", {"path": "/docs/a.txt"}, CONTAINS))
    w.ra = w.read("m:a", "a", file_read("/docs/a.txt", "alpha v1")); w.achieve("m:a", w.ra)
    return w
def show(name, v): print(f"{name}: {json.dumps(v, default=str)}", flush=True)
def recs(w): return {k: len(w.journal.replay(k)) for k in ("evidence.invalidated", "evidence.correction", "evidence.requalified", "decision.requested", "decision.withdrawn")}
def cm(w): return sorted(corrections.contained_missions(w.journal)), sorted(r[:10] for r in corrections.contained_receipts(w.journal))

# 1. fail then pass, both before the first propagation
w = base()
w.read("m:r", "a", file_read("/docs/a.txt", "alpha v1"), passed=False)
w.read("m:r", "a", file_read("/docs/a.txt", "alpha v1"))
out = w.tick()
show("1 fail+pass before the first tick", {"recorded": [c["class"] for c in out], "records": recs(w), "contained": cm(w), "state": w.state("m:a")["state"]})
show("1 second tick writes", {"recorded": w.tick(), "records": recs(w)})

# 2. the passing reading comes BEFORE the failing one (requalifier before the trigger)
w = base()
w.read("m:r", "a", file_read("/docs/a.txt", "alpha v1"))
w.read("m:r", "a", file_read("/docs/a.txt", "alpha v1"), passed=False)
w.tick()
show("2 pass then fail", {"records": recs(w), "contained": cm(w), "state": w.state("m:a")["state"]})

# 3. the critique is recorded before the closure it will come to hit (a reading rejected before delivery)
w = World()
w.mission("m:a", ("a", "fs.read", {"path": "/docs/a.txt"}, CONTAINS))
ra = w.read("m:a", "a", file_read("/docs/a.txt", "alpha v1"))
[ev] = [e for e in w.journal.replay("mission.observed")]
w.record("critique.recorded", {"target_event_id": ev.event_id, "verdict": "reject", "text": "wrong"}, key=["crit-early"])
show("3a critique before any closure: tick", {"recorded": w.tick(), "contained": cm(w)})
w.achieve("m:a", ra)
out = w.tick()
show("3b closure after the critique", {"recorded": [c["class"] for c in out], "contained": cm(w), "state": w.state("m:a")["state"]})

# 4. determinism: two worlds built alike give identical records (ids and payloads but for 'at')
def build():
    w = base()
    w.read("m:r", "a", file_read("/docs/a.txt", "alpha v1"), passed=False)
    w.tick(); w.tick()
    [ach] = [e for e in w.journal.replay("mission.achieved")]
    w.record("critique.recorded", {"target_event_id": ach.event_id, "verdict": "reject", "text": "wrong"}, key=["c1"])
    w.tick()
    return w
def dump(w): return json.dumps([[e.type, e.payload] for k in ("evidence.invalidated", "evidence.correction", "evidence.requalified") for e in w.journal.replay(k)], sort_keys=True, default=str)
a, b = build(), build()
show("4 two identical histories give identical correction records", dump(a) == dump(b))
show("4 contained equal", cm(a) == cm(b))
# propagation at a different 'now' after the facts exist: any new record?
before = recs(a); a.tick(NOW + timedelta(days=3)); show("4 a later tick at another time writes nothing", recs(a) == before)

# 5. depth 2: m:c acts on m:a's reading; m:d acts on m:c's action output
w = base()
for mid, path in (("m:c", "/docs/c.txt"), ("m:d", "/docs/d.txt")):
    w.mission(mid, ("x", "fs.read", {"path": path}, CONTAINS))
act1 = w.ledger.append("receipt", {"action_id": "use1", "result": {"output": {"written": True}}}).hash
w.record("mission.action", {"mission_id": "m:c", "action_id": "use1", "receipt": act1, "input_bindings": [{"mission_id": "m:a", "receipt": w.ra, "field": "text"}]}, key=["m:c", "use1", 1])
w.achieve("m:c", w.read("m:c", "x", file_read("/docs/c.txt", "alpha c")))
act2 = w.ledger.append("receipt", {"action_id": "use2", "result": {"output": {"written": True}}}).hash
w.record("mission.action", {"mission_id": "m:d", "action_id": "use2", "receipt": act2, "input_bindings": [{"mission_id": "m:c", "receipt": act1, "field": "text"}]}, key=["m:d", "use2", 1])
w.achieve("m:d", w.read("m:d", "x", file_read("/docs/d.txt", "alpha d")))
w.read("m:r", "a", file_read("/docs/a.txt", "alpha v1"), passed=False)
w.tick()
show("5 depth 2 (a -> c -> d)", {"contained missions": cm(w)[0], "n contained receipts": len(cm(w)[1]),
     "states": {m: w.state(m)["state"] for m in ("m:a", "m:c", "m:d")}})

# 6. a dependent that arrives AFTER the correction was recorded
w = base()
w.read("m:r", "a", file_read("/docs/a.txt", "alpha v1"), passed=False)
w.tick()
w.mission("m:late", ("x", "fs.read", {"path": "/docs/l.txt"}, CONTAINS))
act = w.ledger.append("receipt", {"action_id": "use", "result": {"output": {"written": True}}}).hash
w.record("mission.action", {"mission_id": "m:late", "action_id": "use", "receipt": act, "input_bindings": [{"mission_id": "m:a", "receipt": w.ra, "field": "text"}]}, key=["m:late", "use", 1])
w.achieve("m:late", w.read("m:late", "x", file_read("/docs/l.txt", "alpha late")))
out = w.tick(); w.tick()
show("6 a mission that binds the contained reading after the correction", {"new records": [c["class"] for c in out], "contained missions": cm(w)[0],
     "state m:late": w.state("m:late")["state"], "state m:a": w.state("m:a")["state"]})

# 7. two closures of two missions that cite one receipt; a critique rejecting one closure
w = base()
w.mission("m:share", ("a", "fs.read", {"path": "/docs/a.txt"}, CONTAINS))
w.achieve("m:share", w.ra)
[ach] = [e for e in w.journal.replay("mission.achieved") if e.payload["mission_id"] == "m:share"]
w.record("critique.recorded", {"target_event_id": ach.event_id, "verdict": "reject", "text": "wrong"}, key=["c2"])
w.tick()
show("7 rejecting m:share's closure, which cites m:a's receipt", {"contained missions": cm(w)[0], "states": {m: w.state(m)["state"] for m in ("m:a", "m:share")}})
