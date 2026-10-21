"""A body killed between an UNCERTAIN dispatch record and its reconciliation question never retries blind.

Review finding on the merged trunk (1728728 records, then asks; a02a258 keys the held cap by attempt): if the body
died after appending the UNCERTAIN record and before the RECONCILIATION request (or before blocking on it), the
restarted body had no blocker, dispatched the next attempt of a non-retry-safe act with no founder answer, and a
priced attempt's held cap could never be released. The restarted body now settles the retained record exactly as
the dispatch would have: the standing proof when it holds, else the one question for that attempt.
"""
from __future__ import annotations

import pytest

from greg import capabilities
from greg.body import Body
from greg.missions import MissionEngine
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy


class Killed(BaseException):
    """SIGKILL, as far as the mission loop can tell: nothing after it runs."""


def _kill_once(monkeypatch, method: str, matches):
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


def _actions(home, clock, mid, aid):
    with Body(home, clock=clock) as body:
        return [(e.payload["attempt"], e.payload["status"]) for e in body.journal.replay("mission.action")
                if e.payload["mission_id"] == mid and e.payload["action_id"] == aid]


def _reconciliations(home, clock):
    with Body(home, clock=clock) as body:
        return [e.payload for e in body.journal.replay("decision.requested") if e.payload["kind"] == "RECONCILIATION"]


def test_a_kill_before_the_question_is_asked_leads_to_the_question_not_a_second_dispatch(tmp_path, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:kill-window"
    ws = workspace(home, mid)
    spec = mission(mid, checks=[note_check("note", ws / "note.txt", "hello")],
                   strategies=[write_strategy("write-note", "note.txt", "hello", ["note"])],
                   capabilities=["fs.read", "fs.write"])
    manifest, real = capabilities.BUILTINS["fs.write"]
    assert not manifest.retry_safe
    calls = []

    def dies_once(params, ctx):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("power lost mid-effect")
        return real(params, ctx)
    monkeypatch.setitem(capabilities.BUILTINS, "fs.write", (manifest, dies_once))
    _kill_once(monkeypatch, "_request", lambda **kw: kw.get("kind") == "RECONCILIATION")
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with pytest.raises(Killed):
        _run(home, clock, 3)
    assert _actions(home, clock, mid, "write-note") == [(0, "UNCERTAIN")] and _reconciliations(home, clock) == []
    _run(home, clock, 3)                                       # restart
    assert len(calls) == 1, "a non-retry-safe act was dispatched again with no founder answer"
    [asked] = _reconciliations(home, clock)
    assert asked["action_id"] == "write-note"
    drop(home, signed(key, body_id, "DECISION", {"request_id": asked["request_id"], "answer": "reconcile_not_executed"}))
    _run(home, clock, 4)
    assert len(calls) == 2 and (ws / "note.txt").read_text() == "hello"   # the one retry, after the answer


def test_a_kill_before_the_block_reuses_the_open_question_and_its_answer_settles_the_held_cap(tmp_path, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:priced-kill"
    ws = workspace(home, mid)
    manifest, _ = capabilities.BUILTINS["worker.commission"]
    calls = []

    def uncertain_worker(params, ctx):
        calls.append(1)
        return {"status": "UNCERTAIN", "changed_files": [], "patch_sha256": "", "greg_tests_passed": False,
                "worker": {"interrupted": True}}
    monkeypatch.setitem(capabilities.BUILTINS, "worker.commission", (manifest, uncertain_worker))
    _kill_once(monkeypatch, "_block", lambda blocker: blocker.get("type") == "reconciliation")
    strategy = {"action_id": "commission", "capability": "worker.commission", "target": "work:x",
                "params": {"order": "o1", "objective": "x", "acceptance": {}, "allowed_paths": ["a"],
                           "max_budget_usd": 0.05},
                "cost_usd": 0.05, "advances": ["note"], "rationale": "commission"}
    spec = mission(mid, checks=[note_check("note", ws / "note.txt", "hello")], strategies=[strategy],
                   capabilities=["fs.read", "worker.commission"], targets=("fs:*", "workspace:*", "work:*"),
                   budget=0.05)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with pytest.raises(Killed):
        _run(home, clock, 3)
    [open_question] = _reconciliations(home, clock)
    _run(home, clock, 3)                                       # restart
    assert len(calls) == 1, "blind paid retry after restart"
    assert [r["request_id"] for r in _reconciliations(home, clock)] == [open_question["request_id"]]
    with Body(home, clock=clock) as body:
        m = body.engine.book.missions[mid]
        assert m.blocker["request_id"] == open_question["request_id"] and m.spent_usd == 0.0 and m.committed_usd == 0.05
    drop(home, signed(key, body_id, "DECISION", {"request_id": open_question["request_id"],
                                                 "answer": "reconcile_not_executed"}))
    _run(home, clock, 1)
    with Body(home, clock=clock) as body:
        m = body.engine.book.missions[mid]
        assert ("commission", 0) not in m.reserved      # the answer released attempt 0's hold...
        # ...and, the worker being metered, booked its cap once as spent (#178 H.G4: "not executed" settles the
        # effect, not the money its provider may have spent). Before H.G4 the hold was released as $0 and the one
        # retry fit the signed $0.05 budget; now the budget is spent at its worst case and a retry needs the founder.
        assert m.spent_usd == 0.05 and m.committed_usd == 0.05
        asks = [e.payload for e in body.journal.replay("decision.requested")
                if e.payload["mission_id"] == mid and e.payload["kind"] == "APPROVAL"]
        assert asks and any("exceeds budget" in r for r in asks[-1]["evidence"]["policy"]), asks
    assert len(calls) == 1                              # no paid retry without the founder
