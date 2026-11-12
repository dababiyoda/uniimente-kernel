"""Builder-route probes (no solver packages). Run with cwd = a worktree.
usage: beside_probe.py <scenario> [nticks_after]
"""
import os, sys, tempfile
sys.path.insert(0, os.getcwd())
from pathlib import Path
from greg import builders
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy
from tests.unit.test_greg_genesis_builder import CONTRACT, FUNCTION, GOOD

FIRST = GOOD
SECOND = ("def run(text):\n    count = 0\n    for line in text.split('\\n'):\n        body = line.lstrip(' \\t')\n"
          "        if body[:2] in ('- ', '* ', '+ ') and body[2:5] == '[ ]':\n            count += 1\n"
          "    return count\n")
TICK = 61
scenario = sys.argv[1]
nafter = int(sys.argv[2]) if len(sys.argv) > 2 else 6
tmp = Path(tempfile.mkdtemp(prefix="rv-bes-", dir=os.environ["RV_TMP"]))
home, key, body_id, data = make_body(tmp)
MID = "m:probe"
ws = workspace(home, MID)
note = ws / "note.md"

def fcheck(cid, path, expected):
    return {"check_id": cid, "description": f"{path.name} has {expected} open steps",
            "sensor": {"function": FUNCTION, "params": {"path": str(path)}, "target": f"fs:{path.name}"},
            "predicate": {"op": "equals", "field": "unchecked", "value": expected}}

NOTE = "- [ ] enroll key\n- [ ] accept closure\n"
builder_sources = [FIRST, SECOND]
pre = 4
if scenario in ("beside_nostrategy", "alone"):
    (data / "request.txt").write_text("go")
    checks = [fcheck("f", note, 2), note_check("noted", note, "enroll key"), note_check("request", data / "request.txt", "go")]
    strategies = [write_strategy("note", "note.md", NOTE, ["f", "noted"])]
elif scenario == "both_advanced":          # one strategy advances the faulted check and a check that really fails
    checks = [fcheck("f", note, 2), note_check("noted", note, "enroll key")]
    strategies = [write_strategy("note", "note.md", NOTE, ["f", "noted"])]
elif scenario == "requires_faulted":       # a strategy for a really failing check requires the faulted check
    flag = ws / "flag.txt"
    checks = [fcheck("f", note, 2), note_check("flag", flag, "on")]
    strategies = [write_strategy("note", "note.md", NOTE, ["f"]),
                  write_strategy("flag", "flag.txt", "on", ["flag"], requires=["f"])]
    pre = 6
elif scenario in ("beside_with_strategy", "unrepairable_beside", "unrepairable_alone", "unrepairable_beside_nostrategy"):
    flag = ws / "flag.txt"
    (data / "request.txt").write_text("go")
    checks = [fcheck("f", note, 2), note_check("flag", flag, "on")] + \
        ([note_check("request", data / "request.txt", "go")] if scenario == "unrepairable_beside_nostrategy" else [])
    strategies = [write_strategy("note", "note.md", NOTE, ["f"]), write_strategy("flag", "flag.txt", "on", ["flag"])]
    pre = 6
    if scenario.startswith("unrepairable"):
        builder_sources = [FIRST, FIRST, FIRST, FIRST, FIRST, FIRST]
elif scenario == "missing_file":           # only the formed function reads the file its strategy creates
    flag = ws / "flag.txt"
    checks = [fcheck("f", note, 2), note_check("flag", flag, "on")]
    strategies = [write_strategy("note", "note.md", NOTE, ["f"]), write_strategy("flag", "flag.txt", "on", ["flag"])]
    pre = 0
elif scenario == "missing_file_alone":
    checks = [fcheck("f", note, 2)]
    strategies = [write_strategy("note", "note.md", NOTE, ["f"])]
    pre = 0
else:
    raise SystemExit("unknown scenario")
spec = mission(MID, checks=checks, strategies=strategies, capabilities=["fs.read", "fs.write", f"built.{FUNCTION}.*"],
               budget=1.0, auto_attach=True, closure={"kind": "infinite", "cadence_seconds": int(os.environ.get("RV_CADENCE", "60"))})
spec["capability_specs"] = [dict(CONTRACT)]
drop(home, signed(key, body_id, "MISSION", spec))
clock, calls = Clock(), []
body = Body(home, clock=clock, builder=builders.StaticBuilder(*builder_sources, identity="static-test")).open()
real = body.registry.adapters["fs.write"]
def counted(params, ctx):
    calls.append(params["relative_path"]); return real(params, ctx)
body.registry.adapters["fs.write"] = counted
body.boot()
seen = [0]
def tick(label):
    clock.advance(TICK if label.startswith("after") and not label == "after0" else int(os.environ.get("RV_CADENCE", "60")) + 1)
    out = body.tick()
    if not out["missions"]:
        import collections
        print("NO MISSION", {k: v for k, v in out.items() if k != "missions"})
        print(collections.Counter(r.payload.get("type") for r in body.ledger.by_type("event")))
        print([r.payload for r in body.ledger.by_type("event") if "reject" in str(r.payload.get("type")) or "refus" in str(r.payload.get("type"))][:3])
        raise SystemExit(2)
    r = out["missions"][0]
    asks = [e.payload for e in body.journal.replay("decision.requested")]
    new = asks[seen[0]:]; seen[0] = len(asks)
    m = body.engine.book.missions[MID]
    print(label, "state=" + r["state"], {k: v for k, v in r.items() if k in ("checks", "action", "replaced", "still_failing", "still_unread")},
          "blocker=" + str((m.blocker or {}).get("type")), "writes=" + str(calls),
          ("NEW_ASKS=" + str([(a["kind"], str(a.get("why"))[:160]) for a in new])) if new else "")
    return r["state"]
try:
    for i in range(pre):
        tick(f"pre{i}")
    if pre:
        note.write_text(note.read_text() + "- [x] reviewed by a person\n")
        tick("hold")
        builders.ALLOWED_IMPORTS = builders.ALLOWED_IMPORTS - {"re"}
        if scenario in ("beside_nostrategy", "unrepairable_beside_nostrategy"):
            (data / "request.txt").write_text("halt")
        if scenario == "both_advanced":
            note.write_text("- [ ] step one\n- [ ] step two\n- [x] reviewed by a person\n")     # 'noted' now really fails
        if scenario in ("requires_faulted", "beside_with_strategy", "unrepairable_beside"):
            (ws / "flag.txt").write_text("off")                                                  # 'flag' now really fails
    for i in range(nafter):
        tick(f"after{i}")
    ev = lambda k: [e.payload for e in body.journal.replay(k)]
    print("actions:", [(a["action_id"], a["status"], a["attempt"]) for a in ev("mission.action")])
    print("asks:", [a["kind"] for a in ev("decision.requested")], "withdrawn:", len(ev("decision.withdrawn")))
    print("unmet:", [(u["failing_checks"], u.get("unmeasured_checks")) for u in ev("mission.unmet")])
    print("cap states:", [(s["capability_id"][-10:], s["state"]) for s in ev("capability.state")])
    print("F obs:", [(o["passed"], o.get("failure_class"), o["detail"][:70]) for o in ev("mission.observed") if o["check_id"] == "f"][-6:])
    print("person line kept:", "reviewed by a person" in note.read_text() if note.exists() else None)
finally:
    body.close()
