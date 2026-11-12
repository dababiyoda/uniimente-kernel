"""Claim 3: after a failure closure, a state round trip makes later ticks raise EventError (crash loop).
Variants: detach/attach sensor, detach/attach strategy capability, mission pause/resume, body pause/resume,
reject the ask, abandon. Reports per variant whether any tick raised."""
import sys, traceback
from lib import *
from events.spine import EventError

MID2 = "m:stuck"


def build(tmp):
    home, key, body_id, _ = make_body(tmp)
    note = workspace(home, MID2) / "n.txt"
    clock = Clock()
    body = Body(home, clock=clock).open()
    body.boot()
    body.apply(signed(key, body_id, "MISSION", mission(
        MID2, checks=[note_check("n", note, "wanted")],
        strategies=[write_strategy("w", "n.txt", "something else", ["n"])], capabilities=["fs.read", "fs.write"])))
    return body, key, body_id, clock, note


def turns(body, clock, n, seconds=31):
    out = []
    for _ in range(n):
        try:
            body.tick()
            out.append("ok")
        except EventError as exc:
            out.append("CRASH EventError " + str(exc))
        except Exception as exc:
            out.append("CRASH " + type(exc).__name__ + " " + str(exc)[:120])
        clock.advance(seconds)
    return out


def state(body):
    m = body.engine.book.missions[MID2]
    return (m.status, (m.blocker or {}).get("type"), m.paused, m.actions_done)


def variant(name, steps):
    tmp = tmpdir("p5")
    body, key, body_id, clock, note = build(tmp)
    try:
        first = turns(body, clock, 4)
        show(f"{name} | setup ticks", first)
        show(f"{name} | unmet, appraised, state", (len(body.journal.replay("mission.unmet")),
             [e.payload["verdict"] for e in body.journal.replay("mission.appraised")], state(body)))
        for label, fn in steps:
            try:
                fn(body, key, body_id, clock, note)
            except Exception as exc:
                show(f"{name} | step {label} raised", type(exc).__name__ + ": " + str(exc)[:160])
                continue
            res = turns(body, clock, 3, 3600)
            show(f"{name} | after {label}", (res, state(body), len(body.journal.replay("mission.unmet")),
                 [e.payload["verdict"] for e in body.journal.replay("mission.appraised")]))
    finally:
        body.close()


def cmd(kind, payload):
    return lambda body, key, body_id, clock, note: body.apply(signed(key, body_id, kind, payload))


def answer(ans):
    def fn(body, key, body_id, clock, note):
        m = body.engine.book.missions[MID2]
        rid = (m.blocker or {}).get("request_id")
        body.apply(signed(key, body_id, "DECISION", {"request_id": rid, "answer": ans}))
    return fn


if __name__ == "__main__": variant("V1 detach/attach sensor fs.read", [("detach fs.read", cmd("CAPABILITY_DETACH", {"capability_id": "fs.read"})),
                                             ("attach fs.read", cmd("CAPABILITY_ATTACH", {"capability_id": "fs.read"}))])
if __name__ == "__main__": variant("V2 detach/attach strategy fs.write", [("detach fs.write", cmd("CAPABILITY_DETACH", {"capability_id": "fs.write"})),
                                                ("attach fs.write", cmd("CAPABILITY_ATTACH", {"capability_id": "fs.write"}))])
if __name__ == "__main__": variant("V3 mission pause/resume", [("PAUSED", cmd("LIFECYCLE", {"mission_id": MID2, "state": "PAUSED"})),
                                     ("ACTIVE", cmd("LIFECYCLE", {"mission_id": MID2, "state": "ACTIVE"}))])
if __name__ == "__main__": variant("V4 body pause/resume", [("BODY_PAUSE", cmd("BODY_PAUSE", {})), ("BODY_RESUME", cmd("BODY_RESUME", {}))])
if __name__ == "__main__": variant("V5 reject the ask", [("reject", answer("reject"))])
if __name__ == "__main__": variant("V6 approve the ask", [("approve", answer("approve"))])
if __name__ == "__main__": variant("V7 abandon then detach/attach", [("ABANDONED", cmd("LIFECYCLE", {"mission_id": MID2, "state": "ABANDONED"})),
                                           ("detach fs.read", cmd("CAPABILITY_DETACH", {"capability_id": "fs.read"})),
                                           ("attach fs.read", cmd("CAPABILITY_ATTACH", {"capability_id": "fs.read"}))])


def restart_variant():
    name = "V8 restart after unmet"
    tmp = tmpdir("p5")
    body, key, body_id, clock, note = build(tmp)
    home = body.layout.home
    try:
        show(f"{name} | setup", turns(body, clock, 4))
    finally:
        body.close()
    with Body(home, clock=clock) as body:
        show(f"{name} | after restart", (turns(body, clock, 3, 3600), state(body), len(body.journal.replay("mission.unmet"))))


if __name__ == "__main__": restart_variant()
