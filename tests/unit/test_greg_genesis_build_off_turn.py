"""A Genesis build must not freeze every other mission (S38-A's effect, for the builder).

A deficit's builder call (Claude Code: up to 300 s per attempt, two attempts) ran inside MissionEngine's step, under
the Body's turn lock, so while it built nothing else was stepped, the inbox was not read and the heartbeat stopped.
On #196 12119590 the first test timed out after 30 s with a held builder; released at once, it closed in 1.45 s.

Only the builder call leaves the turn (greg.background.OffTurnBuilds). The reservation, every journal write, the
screen, the verification, the registration and the attach stay on the turn. These tests hold the builder open and
check that: the other mission closes meanwhile and the heartbeat shows the building one WORKING; STOP does not wait
for the call and its reservation is still charged after a restart; a mission the founder ends while it builds never
gets its late result; a mission is never built twice at once; and two missions building at once each run under
their own signed ceiling. Founder decision on #96 (2026-11-21).
"""
import json
import threading
import time

from greg import builders
from greg.body import Body, Layout, observe
from tests.greg_fixtures import drop, make_body, mission, note_check, signed, workspace, write_strategy
from tests.unit.test_greg_genesis_builder import FUNCTION, GOOD, _mission

WAIT = 30
COST = 0.05


class HoldingBuilder(builders.StaticBuilder):
    """A paid builder whose calls are held until the test releases them; it records the ceiling each call ran under.

    Genesis copies the builder per off-turn call (``copy.copy``), so the events, lists and lock are shared by the
    copies and ``max_budget_usd`` is each copy's own."""

    def __init__(self, *sources, max_budget_usd=1.0):
        super().__init__(*sources, identity="holding-test")
        self.max_budget_usd = max_budget_usd
        self.release = threading.Event()
        self.started, self.returned = [], []
        self._lock = threading.Lock()

    def build(self, request, feedback=None):
        with self._lock:
            self.started.append({"ceiling": self.max_budget_usd, "thread": threading.current_thread().name})
        self.release.wait(WAIT * 2)
        try:
            built = super().build(request, feedback)
        finally:
            with self._lock:
                self.returned.append(self.max_budget_usd)
        return {**built, "cost_usd": COST}


def wait_for(cond, what, timeout=WAIT):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {what}")


def events(home, kind):
    with observe(home, actor="spiffe://uniimente.internal/test/genesis-off-turn") as journal:
        return [e.payload for e in journal.replay(kind)]


def achieved(home):
    return [p["mission_id"] for p in events(home, "mission.achieved")]


def heartbeat(home):
    try:
        return json.loads(Layout(home).heartbeat.read_text())
    except (OSError, ValueError):
        return {}


def working(home, mission_id):
    return any(m.get("mission_id") == mission_id and m.get("state") == "WORKING"
               for m in heartbeat(home).get("missions", []))


def quick_mission(home, mission_id="m:quick"):
    note = workspace(home, mission_id) / "c.txt"
    return mission(mission_id, checks=[note_check("c", note, "ok")],
                   strategies=[write_strategy("w", "c.txt", "ok", ["c"])], capabilities=["fs.read", "fs.write"])


def start(body):
    loop = threading.Thread(target=body.run, kwargs={"tick_seconds": 0.05}, daemon=True)
    loop.start()
    return loop


def stop(body, loop, timeout=WAIT):
    body.stop_requested = True
    loop.join(timeout)
    assert not loop.is_alive(), "the body did not stop"


def build_spend(home, deficit_id):
    """What Genesis charges this deficit's builds, from the retained journal, as Genesis._build_spend computes it."""
    settled = {(p["deficit_id"], p.get("build")) for kind in ("genesis.built", "genesis.build_failed")
               for p in events(home, kind)}
    reported = sum(p.get("cost_usd") or 0.0 for kind in ("genesis.built", "genesis.unbuilt")
                   for p in events(home, kind) if p["deficit_id"] == deficit_id)
    return reported + sum(p["reserved_usd"] for p in events(home, "genesis.build_started")
                          if p["deficit_id"] == deficit_id and (deficit_id, p["build"]) not in settled)


def test_a_long_genesis_build_does_not_freeze_the_other_missions(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    spec = _mission(data)
    spec["priority"] = 10                               # stepped first, so its build starts first
    drop(home, signed(key, body_id, "MISSION", spec))
    drop(home, signed(key, body_id, "MISSION", quick_mission(home)))
    builder = HoldingBuilder(GOOD)
    body = Body(home, builder=builder)
    loop = start(body)
    try:
        wait_for(lambda: builder.started, "the build to start")
        wait_for(lambda: "m:quick" in achieved(home), "the quick mission to close while the build holds")
        # B closed strictly while A's builder call was still held: never released, never returned
        assert not builder.release.is_set() and builder.returned == []
        wait_for(lambda: working(home, "m:runbook"), "the heartbeat to show the building mission WORKING")
        row = next(m for m in heartbeat(home)["missions"] if m["mission_id"] == "m:runbook")
        assert row["action"] == f"genesis.build:{FUNCTION}"
        assert "m:runbook" not in achieved(home)
        builder.release.set()
        wait_for(lambda: "m:runbook" in achieved(home), "the building mission to close once its build returns")
    finally:
        builder.release.set()
        stop(body, loop)
    started = events(home, "genesis.build_started")
    built = events(home, "genesis.built")
    assert [p["build"] for p in started] == [1] and [p["build"] for p in built] == [1]   # one call, taken once
    assert len(builder.started) == 1
    deficit = started[0]["deficit_id"]
    assert built[0]["deficit_id"] == deficit and built[0]["cost_usd"] == COST
    assert round(build_spend(home, deficit), 6) == COST       # the reservation settled at the reported cost
    assert [p["passed"] for p in events(home, "genesis.verified")] == [True]


def test_stop_does_not_wait_for_a_build_and_the_restart_still_charges_its_reservation(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _mission(data)))
    held = HoldingBuilder(GOOD, max_budget_usd=0.4)
    body = Body(home, builder=held)
    loop = start(body)
    wait_for(lambda: held.started, "the build to start")
    t0 = time.monotonic()
    stop(body, loop, timeout=10)                     # the held call would hold for 60 s
    assert time.monotonic() - t0 < 10
    stopped = events(home, "body.stopped")[-1]
    started = events(home, "genesis.build_started")
    assert [p["build"] for p in started] == [1] and started[0]["reserved_usd"] == 0.4
    deficit = started[0]["deficit_id"]
    assert stopped["builds_unfinished"] == [{"mission_id": "m:runbook", "deficit_id": deficit, "build": 1}]
    assert events(home, "genesis.built") == [] and events(home, "genesis.build_failed") == []
    assert build_spend(home, deficit) == 0.4         # interrupted: charged at its reserved ceiling (H.G7)

    # The restart resumes the same deficit; the interrupted call stays charged and the next call is charged too.
    fresh = HoldingBuilder(GOOD, max_budget_usd=0.4)
    fresh.release.set()
    again = Body(home, builder=fresh)
    loop = start(again)
    try:
        wait_for(lambda: "m:runbook" in achieved(home), "the mission to close after the restart")
    finally:
        stop(again, loop)
    started = events(home, "genesis.build_started")
    assert [(p["deficit_id"], p["build"]) for p in started] == [(deficit, 1), (deficit, 2)]
    assert [p["build"] for p in events(home, "genesis.built")] == [2]
    assert round(build_spend(home, deficit), 6) == round(0.4 + COST, 6)
    # The first body's call returns late, into a body that is gone: nothing more is written.
    before = len(events(home, "genesis.built"))
    held.release.set()
    wait_for(lambda: held.returned, "the abandoned call to return")
    time.sleep(0.3)
    assert len(events(home, "genesis.built")) == before


def test_a_mission_the_founder_ends_while_it_builds_never_gets_its_late_result(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _mission(data)))
    builder = HoldingBuilder(GOOD, max_budget_usd=0.4)
    body = Body(home, builder=builder)
    loop = start(body)
    try:
        wait_for(lambda: builder.started, "the build to start")
        drop(home, signed(key, body_id, "LIFECYCLE", {"mission_id": "m:runbook", "state": "ABANDONED",
                                                      "reason": "the founder ends it mid-build"}))
        wait_for(lambda: any(p["mission_id"] == "m:runbook" and p["state"] == "ABANDONED"
                             for p in events(home, "mission.lifecycle")), "the founder's cancel to be recorded")
        builder.release.set()                         # the call returns after the mission ended
        wait_for(lambda: builder.returned, "the late call to return")
        wait_for(lambda: body.engine.builds.busy("m:runbook") is None, "the call to finish")
        time.sleep(0.5)                               # several turns pass
    finally:
        builder.release.set()
        stop(body, loop)
    deficit = events(home, "genesis.build_started")[0]["deficit_id"]
    assert events(home, "genesis.built") == [] and events(home, "genesis.verified") == []
    assert events(home, "capability.registered") == []
    assert not any(p.get("state") == "ATTACHED" for p in events(home, "capability.state"))
    assert build_spend(home, deficit) == 0.4         # never taken: still charged at its reservation


def test_a_mission_is_never_built_twice_at_once(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _mission(data)))
    drop(home, signed(key, body_id, "MISSION", quick_mission(home)))
    builder = HoldingBuilder(GOOD)
    body = Body(home, builder=builder)
    loop = start(body)
    try:
        wait_for(lambda: builder.started, "the build to start")
        wait_for(lambda: "m:quick" in achieved(home), "many turns to pass")
        time.sleep(0.5)                               # ~10 more turns while the call is held
        assert len(builder.started) == 1
        assert [p["build"] for p in events(home, "genesis.build_started")] == [1]
    finally:
        builder.release.set()
        stop(body, loop)


def test_two_missions_building_at_once_each_run_under_their_own_signed_ceiling(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    low = _mission(data, budget=0.3)
    low["priority"] = 10
    high = _mission(data, budget=0.7)
    high["mission_id"] = "m:runbook-high"
    drop(home, signed(key, body_id, "MISSION", low))
    drop(home, signed(key, body_id, "MISSION", high))
    builder = HoldingBuilder(GOOD, GOOD, max_budget_usd=1.0)
    body = Body(home, builder=builder)
    loop = start(body)
    try:
        wait_for(lambda: len(builder.started) == 2, "both missions to be building at once")
        assert not builder.returned                 # both calls are in flight together
        assert sorted(c["ceiling"] for c in builder.started) == [0.3, 0.7]
        assert body.genesis.builder.max_budget_usd == 1.0    # the shared builder's own ceiling is never rewritten
        builder.release.set()
        wait_for(lambda: len(builder.returned) == 2, "both calls to return")
        wait_for(lambda: {"m:runbook", "m:runbook-high"} <= set(achieved(home)), "both missions to close")
    finally:
        builder.release.set()
        stop(body, loop)
    opened = {p["deficit_id"]: p["mission_id"] for p in events(home, "deficit.opened")}
    reserved = {opened[p["deficit_id"]]: p["reserved_usd"] for p in events(home, "genesis.build_started")}
    assert reserved == {"m:runbook": 0.3, "m:runbook-high": 0.7}
    assert sorted(builder.returned) == [0.3, 0.7]    # each call ran to its end under its own mission's ceiling
    # The first to finish is verified and attached; the other mission is then served by it. Its own call is still
    # settled at what it cost, not left charged at its 0.7 ceiling, and its candidate is never attached.
    assert len(events(home, "capability.registered")) == 1
    for deficit in opened:
        assert round(build_spend(home, deficit), 6) == COST
