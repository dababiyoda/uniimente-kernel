"""A kill between the founder-reconciliation record and the unblock must not crash every later restart.

_record_reconciliation journals mission.action under key [mission, action, 'reconciled', request_id] with
"at": iso(now) in the payload; _unblock is a separate append. A SIGKILL between the two leaves the answered
reconciliation as the blocker, so the restarted body records again at a later now: same identity, different
content, EventError on every tick of every restart (live branch and TERMINAL branch alike).
"""
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


def _reconciliations(home, clock):
    with Body(home, clock=clock) as body:
        return [e.payload for e in body.journal.replay("decision.requested") if e.payload["kind"] == "RECONCILIATION"]


def _setup(tmp_path, monkeypatch, mid):
    home, key, body_id, _ = make_body(tmp_path)
    ws = workspace(home, mid)
    spec = mission(mid, checks=[note_check("note", ws / "note.txt", "hello")],
                   strategies=[write_strategy("write-note", "note.txt", "hello", ["note"])],
                   capabilities=["fs.read", "fs.write"])
    manifest, real = capabilities.BUILTINS["fs.write"]
    calls = []

    def dies_once(params, ctx):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("power lost mid-effect")
        return real(params, ctx)
    monkeypatch.setitem(capabilities.BUILTINS, "fs.write", (manifest, dies_once))
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    _run(home, clock, 3)
    [asked] = _reconciliations(home, clock)
    return home, key, body_id, ws, clock, asked, calls


def test_live_branch_restart_after_kill_between_record_and_unblock(tmp_path, monkeypatch):
    home, key, body_id, ws, clock, asked, calls = _setup(tmp_path, monkeypatch, "m:cr4-live")
    drop(home, signed(key, body_id, "DECISION", {"request_id": asked["request_id"],
                                                 "answer": "reconcile_not_executed"}, now=clock.now))
    _kill_once(monkeypatch, "_unblock", lambda why: why.startswith("founder answered"))
    with pytest.raises(Killed):
        _run(home, clock, 2)
    clock.advance(30)                       # a supervisor restart is always later than the kill
    _run(home, clock, 4)                    # EventError on 3cf5dab
    assert len(calls) == 2 and (ws / "note.txt").read_text() == "hello"


def test_terminal_branch_restart_after_kill_between_record_and_unblock(tmp_path, monkeypatch):
    home, key, body_id, ws, clock, asked, calls = _setup(tmp_path, monkeypatch, "m:cr4-terminal")
    drop(home, signed(key, body_id, "LIFECYCLE", {"mission_id": "m:cr4-terminal", "state": "ABANDONED",
                                                  "reason": "stop"}, now=clock.now))
    _run(home, clock, 1)
    drop(home, signed(key, body_id, "DECISION", {"request_id": asked["request_id"],
                                                 "answer": "reconcile_not_executed"}, now=clock.now))
    _kill_once(monkeypatch, "_unblock", lambda why: why.startswith("founder reconciliation recorded"))
    with pytest.raises(Killed):
        _run(home, clock, 1)
    clock.advance(30)
    _run(home, clock, 2)                    # EventError on 3cf5dab
    assert len(calls) == 1
