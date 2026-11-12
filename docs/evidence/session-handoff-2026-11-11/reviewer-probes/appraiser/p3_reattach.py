"""Re-attach semantics, restart and idempotence. Run on head (and base for comparison)."""
import sys
from lib import *
from events.spine import EventError

HEAD = tree() == "ra-head"


def ap(body, mid=MID):
    return [(a["verdict"], "closure" if a.get("closure_event") else "achieved", sorted(a.get("not_run", {})))
            for a in facts(body, "mission.appraised", mid)]


def safe_tick(body, clock, n=1, step=60):
    out = []
    for _ in range(n):
        try:
            body.tick()
            out.append("ok")
        except Exception as exc:
            out.append("CRASH " + type(exc).__name__ + ": " + str(exc)[:100])
        clock.advance(step)
    return out


def s_states():
    for st in ("QUARANTINED", "VERIFIED", "DISCOVERED"):
        tmp = tmpdir("p3s"); child = Child(tmp)
        home, key, body_id, note = note_mission(tmp)
        clock = Clock(); close_then_stop(home, clock)
        with Body(home, clock=clock) as body:
            body.journal.record("capability.state", {"capability_id": "fs.read", "state": st, "why": "probe",
                                                     "by": "self-repair (probe)"}, key=["fs.read", "probe", st])
            body._apply_capability_states()
            safe_tick(body, clock)
            show(f"state {st} | registry, adapters run, appraised", (body.registry.state["fs.read"], child.ran, ap(body)))
            # QUARANTINED -> founder ATTACH is refused by the body ("only verified capabilities may be attached")
            attach(home, key, body_id)
            res = safe_tick(body, clock, 2)
            show(f"state {st} | after founder ATTACH: ticks, registry, children, appraised",
                 (res, body.registry.state["fs.read"], len(child.requests), child.ran, ap(body)))


def s_attach_detach_same_turn():
    tmp = tmpdir("p3a"); child = Child(tmp)
    home, key, body_id, note = note_mission(tmp)
    clock = Clock(); close_then_stop(home, clock); detach(home, key, body_id)
    with Body(home, clock=clock) as body:
        safe_tick(body, clock)
        drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "fs.read"}), "1-attach.json")
        drop(home, signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "fs.read"}), "2-detach.json")
        safe_tick(body, clock, 3)
        show("attach+detach same turn | children, ran, appraised", (len(child.requests), child.ran, ap(body)))
        attach(home, key, body_id)
        safe_tick(body, clock, 3)
        show("then attach | children, ran, appraised", (len(child.requests), child.ran, ap(body)))
        # redundant ATTACH commands while ATTACHED and already re-appraised
        for _ in range(3):
            attach(home, key, body_id)
            safe_tick(body, clock)
        show("3 redundant ATTACH | children, ran, appraised", (len(child.requests), child.ran, ap(body)))


def s_attach_stop_detach():
    """attach is accepted, the body stops before close-out, the founder detaches again, the body restarts."""
    tmp = tmpdir("p3b"); child = Child(tmp)
    home, key, body_id, note = note_mission(tmp)
    clock = Clock(); close_then_stop(home, clock); detach(home, key, body_id)
    with Body(home, clock=clock) as body:
        safe_tick(body, clock)
        attach(home, key, body_id)
        body.layout.stop_file.touch()           # the body stops in the turn that accepted the attach
        r = body.tick(); clock.advance(1)
        show("attach then stop | tick result stopped, registry, children", (r.get("stopped"), body.registry.state["fs.read"], len(child.requests)))
    (Path(home) / "STOP").unlink()
    detach(home, key, body_id)
    with Body(home, clock=clock) as body:
        safe_tick(body, clock, 3)
        show("restart with detach | registry, children, ran, appraised", (body.registry.state["fs.read"], len(child.requests), child.ran, ap(body)))
    attach(home, key, body_id)
    with Body(home, clock=clock) as body:
        safe_tick(body, clock, 3)
        show("restart with attach | registry, children, ran, appraised", (body.registry.state["fs.read"], len(child.requests), child.ran, ap(body)))
    for i in range(3):
        with Body(home, clock=clock) as body:
            safe_tick(body, clock, 2)
    with Body(home, clock=clock) as body:
        show("3 more restarts | children, ran, appraised, unavailable", (len(child.requests), child.ran, ap(body), len(facts(body, "mission.appraisal_unavailable"))))


def s_kill_runs_after_reattach():
    tmp = tmpdir("p3c"); child = Child(tmp)
    home, key, body_id, note = note_mission(tmp)
    clock = Clock(); close_then_stop(home, clock); detach(home, key, body_id)
    with Body(home, clock=clock) as body:
        safe_tick(body, clock)
        attach(home, key, body_id)
        child.fail_next = 2
        res = safe_tick(body, clock, 2)
        show("2 killed runs after re-attach | ticks, children, appraised, unavailable attempts",
             (res, len(child.requests), ap(body), [u["attempt"] for u in facts(body, "mission.appraisal_unavailable")]))
        detach(home, key, body_id)       # detached again between retries
        res = safe_tick(body, clock, 3)
        show("detached again between retries | ticks, children, ran, appraised", (res, len(child.requests), child.ran, ap(body)))
        attach(home, key, body_id)
        res = safe_tick(body, clock, 3)
        show("attached again | ticks, children, ran, appraised, attempts", (res, len(child.requests), child.ran, ap(body),
             [u["attempt"] for u in facts(body, "mission.appraisal_unavailable")]))
        child.fail_next = 0


def s_two_missions():
    """Two missions' closures wait on the same detached sensor."""
    tmp = tmpdir("p3d"); child = Child(tmp)
    home, key, body_id, _ = make_body(tmp)
    notes = {}
    for mid in ("m:one", "m:two"):
        note = workspace(home, mid) / "note.txt"; note.parent.mkdir(parents=True, exist_ok=True); note.write_text("original")
        notes[mid] = note
        drop(home, signed(key, body_id, "MISSION", mission(mid, checks=[note_check("c", note, "final")],
             strategies=[write_strategy("w", "note.txt", "final", ["c"])], capabilities=["fs.read", "fs.write"])))
    clock = Clock()
    with Body(home, clock=clock) as body:
        engine_tick = body.engine.tick
        def tick_then_stop(now, **kw):
            out = engine_tick(now, **kw)
            if facts(body, "mission.achieved", "m:one") and facts(body, "mission.achieved", "m:two"):
                body.layout.stop_file.touch()
            return out
        body.engine.tick = tick_then_stop
        for _ in range(10):
            r = body.tick(); clock.advance(1)
            if r.get("stopped"): break
        show("two missions | stopped before close-out, appraised", (r.get("stopped"), len(body.journal.replay("mission.appraised"))))
    (Path(home) / "STOP").unlink()
    detach(home, key, body_id)
    with Body(home, clock=clock) as body:
        safe_tick(body, clock, 2)
        show("two missions detached | children, ran, verdicts", (len(child.requests), child.ran,
             [(e.payload["mission_id"], e.payload["verdict"]) for e in body.journal.replay("mission.appraised")]))
        attach(home, key, body_id)
        safe_tick(body, clock, 3)
        show("two missions re-attached | children, ran, verdicts", (len(child.requests), child.ran,
             [(e.payload["mission_id"], e.payload["verdict"]) for e in body.journal.replay("mission.appraised")]))


for fn in (s_states, s_attach_detach_same_turn, s_attach_stop_detach, s_kill_runs_after_reattach, s_two_missions):
    if len(sys.argv) > 1 and fn.__name__ not in sys.argv[1:]:
        continue
    try:
        fn()
    except Exception as exc:
        import traceback
        show(fn.__name__ + " RAISED", "".join(traceback.format_exception_only(type(exc), exc)).strip()[:300])
        traceback.print_exc(limit=4)
