"""Cross-version probe: stage 1 runs on one checkout (PYTHONPATH), stage 2 on another, same body home.
usage: xver.py stage1 <tmp> <window>   window: record | ask | none
       xver.py stage2 <tmp>"""
import json, sys, pickle
from pathlib import Path
from datetime import datetime, timezone

from greg.body import Body
from greg.missions import MissionEngine
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy
import greg, inspect

MID = "m:xver"
BROKEN = {"capability": "fs.write", "params": {"relative_path": "other.txt", "content": "original"},
          "target": "workspace:note.txt"}


class Killed(BaseException):
    pass


def tick(body, clock, n):
    for _ in range(n):
        body.tick()
        clock.advance(1)


def facts(body, kind):
    return [e.payload for e in body.journal.replay(kind) if e.payload.get("mission_id") == MID]


stage, tmp = sys.argv[1], Path(sys.argv[2])
print(stage, "code:", Path(inspect.getfile(greg)).parent.parent.name)
if stage == "stage1":
    window = sys.argv[3]
    tmp.mkdir(parents=True)
    home, key, body_id, _ = make_body(tmp)
    note = workspace(home, MID) / "note.txt"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("original")
    drop(home, signed(key, body_id, "MISSION", mission(
        MID, checks=[note_check("c", note, "final")],
        strategies=[write_strategy("w", "note.txt", "draft", ["c"], compensate=BROKEN)],
        capabilities=["fs.read", "fs.write"])))
    clock = Clock()
    try:
        with Body(home, clock=clock) as body:
            tick(body, clock, 3)
            drop(home, signed(key, body_id, "LIFECYCLE", {"mission_id": MID, "state": "ABANDONED", "reason": "no"}))
            if window == "record":
                record = body.journal.record

                def dies(name, data, **kw):
                    if name == "mission.compensated":
                        raise Killed()
                    return record(name, data, **kw)
                body.journal.record = dies
            elif window == "ask":
                def dies(self, *a, **k):
                    raise Killed()
                MissionEngine._compensation_ask = dies
            tick(body, clock, 3)
    except Killed:
        print("stage1 killed in window", window)
    (tmp / "state.json").write_text(json.dumps({"home": str(home), "now": clock.now.isoformat()}))
    with Body(home) as body:
        print("stage1 end: compensated", [(c["status"], c["reasons"]) for c in facts(body, "mission.compensated")],
              "| open asks", sorted(r["kind"] for r in body.engine.book.open_requests()),
              "| receipts", [r.payload["result"]["result_class"] for r in body.ledger.by_type("receipt")][-1:])
else:
    st = json.loads((tmp / "state.json").read_text())
    home = Path(st["home"])
    clock = Clock(datetime.fromisoformat(st["now"]))
    for round_ in range(2):
        with Body(home, clock=clock) as body:
            tick(body, clock, 5)
            print(f"stage2 round {round_}: compensated", [(c["status"], c["reasons"]) for c in facts(body, "mission.compensated")],
                  "| open asks", sorted(r["kind"] for r in body.engine.book.open_requests()),
                  "| COMPENSATION asks recorded", len([e for e in body.journal.replay("decision.requested")
                                                      if e.payload["kind"] == "COMPENSATION"]),
                  "| dispatch claims", len(body.ledger.by_type("grant_dispatch")),
                  "| receipts", len(body.ledger.by_type("receipt")))
