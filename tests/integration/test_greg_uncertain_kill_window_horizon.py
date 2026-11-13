"""Review repro (crash-recovery #2): 3ded0a7 re-asks a reconciliation question lost to a crash before a terminal
mission compensates, but only when the mission has no blocker. A body killed between the UNCERTAIN record and its
question, then restarted after the mandate horizon, blocks on SCOPE_RENEWAL first. The founder can then only
abandon or supersede (a mission id cannot be re-registered with a new horizon), and abandonment runs compensation
at once without the interrupted dispatch ever being put to the founder."""
from __future__ import annotations

import pytest

from greg import capabilities
from greg.body import Body
from greg.missions import MissionEngine
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy


class Killed(BaseException):
    """SIGKILL, as far as the mission loop can tell: nothing after it runs."""


def _kill_once(monkeypatch, method, matches):
    real = getattr(MissionEngine, method)
    armed = {"on": True}

    def dies(self, m, *args, **kwargs):
        if armed["on"] and matches(*args, **kwargs):
            armed["on"] = False
            raise Killed(f"SIGKILL inside {method}")
        return real(self, m, *args, **kwargs)
    monkeypatch.setattr(MissionEngine, method, dies)


def _run(home, clock, ticks):
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(ticks):
            body.tick()
            clock.advance(60)


def _setup(tmp_path, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:kill-horizon"
    ws = workspace(home, mid)
    restore = {"capability": "fs.write", "params": {"relative_path": "a.txt", "content": "original"},
               "target": "workspace:a.txt"}
    spec = mission(mid, checks=[note_check("a", ws / "a.txt", "A"), note_check("note", ws / "note.txt", "hello")],
                   strategies=[write_strategy("write-a", "a.txt", "A", ["a"], compensate=restore),
                               write_strategy("write-note", "note.txt", "hello", ["note"], requires=["a"])],
                   capabilities=["fs.read", "fs.write"])
    manifest, real = capabilities.BUILTINS["fs.write"]
    assert not manifest.retry_safe

    def dies_once(params, ctx):
        if params["relative_path"] == "note.txt":
            raise RuntimeError("power lost mid-effect")       # the dispatch's outcome is unknown: UNCERTAIN
        return real(params, ctx)
    monkeypatch.setitem(capabilities.BUILTINS, "fs.write", (manifest, dies_once))
    _kill_once(monkeypatch, "_request", lambda **kw: kw.get("kind") == "RECONCILIATION")
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with pytest.raises(Killed):
        _run(home, clock, 6)
    return home, key, body_id, mid, ws, clock


def _state(home, clock, mid):
    with Body(home, clock=clock) as body:
        m = body.engine.book.missions[mid]
        recon = [e.payload for e in body.journal.replay("decision.requested") if e.payload["kind"] == "RECONCILIATION"]
        compensated = [e.payload["action_id"] for e in body.journal.replay("mission.compensated")
                       if e.payload["mission_id"] == mid]
        return m, recon, compensated


def _abandon_and_tick(home, key, body_id, mid, clock):
    drop(home, signed(key, body_id, "LIFECYCLE", {"mission_id": mid, "state": "ABANDONED", "reason": "stop"},
                      now=clock.now))
    _run(home, clock, 3)


def test_control_restart_inside_horizon_asks_before_compensating(tmp_path, monkeypatch):
    home, key, body_id, mid, ws, clock = _setup(tmp_path, monkeypatch)
    _run(home, clock, 2)                                     # restart inside the horizon
    _abandon_and_tick(home, key, body_id, mid, clock)
    m, recon, compensated = _state(home, clock, mid)
    assert [r["action_id"] for r in recon] == ["write-note"]
    assert compensated == [] and (ws / "a.txt").read_text() == "A"   # nothing undone before the answer


def test_restart_after_horizon_then_abandon_asks_before_compensating(tmp_path, monkeypatch):
    home, key, body_id, mid, ws, clock = _setup(tmp_path, monkeypatch)
    clock.advance(3 * 86400)                                 # the body comes back after the mandate horizon
    _run(home, clock, 2)
    m, recon, _ = _state(home, clock, mid)
    # The lost question is asked on restart, before the horizon's renewal, and stays the blocker past the horizon.
    assert m.blocker["type"] == "reconciliation" and [r["action_id"] for r in recon] == ["write-note"]
    _abandon_and_tick(home, key, body_id, mid, clock)
    m, recon, compensated = _state(home, clock, mid)
    # 3ded0a7: "Terminal missions ask before compensating" / "a question lost to a crash is asked before anything
    # is undone". On 3cf5dab write-a's compensation has already run and write-note was never asked about.
    assert [r["action_id"] for r in recon] == ["write-note"], \
        f"the interrupted write-note dispatch was never put to the founder (compensated={compensated})"
    assert compensated == [] and (ws / "a.txt").read_text() == "A", "an effect was undone before the answer"
