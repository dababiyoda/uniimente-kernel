"""A re-appraisal (after a re-attach) whose three runs give no verdict, with the body killed between the third
unavailable record and the final appraised record. On restart the body finishes the record. Does it crash?"""
from lib import *
from greg.body import APPRAISAL_ATTEMPTS
from events.spine import EventError

tmp = tmpdir("p10"); child = Child(tmp)
home, key, body_id, data = make_body(tmp)
status = data / "status.txt"; status.write_text("not yet")
drop(home, signed(key, body_id, "MISSION", mission(MID, checks=[note_check("status", status, "shipped")],
     strategies=[write_strategy("nudge", "nudge.txt", "nudged", ["status"])], capabilities=["fs.read", "fs.write"])))
clock = Clock()
close_then_stop(home, clock, closure="mission.unmet", ticks=12, step=600.0)
detach(home, key, body_id)


class Killed(BaseException):
    pass


with Body(home, clock=clock) as body:
    body.tick()
    show("first", [(a["verdict"], bool(a.get("closure_event"))) for a in facts(body, "mission.appraised")])
    attach(home, key, body_id)
    child.fail_next = APPRAISAL_ATTEMPTS
    real = body.journal.record

    def record(kind, data, **kw):
        if kind == "mission.appraised" and data.get("attempts"):
            raise Killed()                       # the process dies before the final record is written
        return real(kind, data, **kw)

    body.journal.record = record
    out = []
    for _ in range(APPRAISAL_ATTEMPTS):
        clock.advance(1)
        try:
            body.tick(); out.append("ok")
        except Killed:
            out.append("killed before the final record")
    show("ticks", out)
    show("unavailable attempts, appraised", ([u["attempt"] for u in facts(body, "mission.appraisal_unavailable")],
         [a["verdict"] for a in facts(body, "mission.appraised")]))
with Body(home, clock=clock) as body:            # restart
    out = []
    for _ in range(3):
        clock.advance(1)
        try:
            body.tick(); out.append("ok")
        except EventError as exc:
            out.append("CRASH EventError " + str(exc))
    show("after restart ticks", out)
    show("appraised", [(a["verdict"], a.get("attempts"), sorted(a.get("not_run", {}))) for a in facts(body, "mission.appraised")])
    show("children", len(child.requests))
