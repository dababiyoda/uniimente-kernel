"""A check whose sensor is named by function, not by capability id. The implementation (fs.read) is detached after
the closure, before its appraisal. What does the appraiser run, and what verdict is recorded?"""
from lib import *

for what in ("attached", "detached"):
    tmp = tmpdir("p8"); child = Child(tmp)
    home, key, body_id, _ = make_body(tmp)
    note = workspace(home, MID) / "note.txt"; note.parent.mkdir(parents=True, exist_ok=True); note.write_text("original")
    check = {"check_id": "c", "description": "note contains final",
             "sensor": {"function": "filesystem.read", "params": {"path": str(note)}, "target": "fs:note.txt"},
             "predicate": {"op": "contains", "field": "text", "value": "final"}}
    try:
        drop(home, signed(key, body_id, "MISSION", mission(MID, checks=[check],
             strategies=[write_strategy("w", "note.txt", "final", ["c"])], capabilities=["fs.read", "fs.write"])))
        clock = Clock()
        close_then_stop(home, clock)
    except Exception as exc:
        show(f"{what} | setup failed", type(exc).__name__ + ": " + str(exc)[:200])
        with Body(home, clock=Clock()) as body:
            show("rejected commands", [e.payload.get("reason", e.payload)[:200] if isinstance(e.payload.get("reason"), str) else str(e.payload)[:200] for e in body.journal.replay("command.rejected")])
            m = body.engine.book.missions.get(MID)
            show("mission", (m.status, m.blocker) if m else None)
        break
    if what == "detached":
        detach(home, key, body_id)
        note.write_text("changed after the detach")
    with Body(home, clock=clock) as body:
        body.tick()
        show(f"{what} | registry fs.read, adapters run", (body.registry.state["fs.read"], child.ran))
        show(f"{what} | appraised", [(a["verdict"], a["checks"].get("world_reobserved"), a["findings"], a.get("not_run")) for a in facts(body, "mission.appraised")])
