import os, sys, tempfile
sys.path.insert(0, os.getcwd())
from pathlib import Path
import pytest
from greg import builders
import tests.unit.test_greg_functional_reconstitution as T
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy
tmp = Path(tempfile.mkdtemp(prefix="rv-gate-", dir=os.environ["RV_TMP"]))
home, key, body_id, data = make_body(tmp)
note = workspace(home, "m:replay") / "note.md"
(data / "request.txt").write_text("go")
spec = mission("m:replay", checks=[T._function_check("note-open-items", note, 2), note_check("noted", note, "enroll key"),
                                   note_check("request", data / "request.txt", "go")],
               strategies=[write_strategy("note", "note.md", "- [ ] enroll key\n- [ ] accept closure\n", ["note-open-items", "noted"])],
               capabilities=["fs.read", "fs.write", f"built.{T.FUNCTION}.*"], budget=1.0, auto_attach=True,
               closure={"kind": "infinite", "cadence_seconds": 60})
spec["capability_specs"] = [dict(T.CONTRACT)]
drop(home, signed(key, body_id, "MISSION", spec))
clock, calls = Clock(), []
body = T._open(home, clock, builders.StaticBuilder(T.FIRST, T.SECOND, identity="static-test"), calls)
print("before:", T._ticks(body, clock, 4), calls)
note.write_text(note.read_text() + "- [x] reviewed by a person\n")
print("hold:", T._ticks(body, clock, 1))
builders.ALLOWED_IMPORTS = builders.ALLOWED_IMPORTS - {"re"}
(data / "request.txt").write_text("halt")
print("after:", T._ticks(body, clock, 3), calls)
rec = T._write_records(body, "note")
print("gate:", {k: (len(v) if isinstance(v, list) else v) for k, v in rec.items()}, "distinct receipts:", len(set(rec["receipts"])))
print("actions:", [(a["action_id"], a["status"], a["attempt"]) for a in T._events(body, "mission.action")])
print("asks:", [a["kind"] for a in T._events(body, "decision.requested")])
print("person line kept:", "reviewed by a person" in note.read_text())
body.close()
