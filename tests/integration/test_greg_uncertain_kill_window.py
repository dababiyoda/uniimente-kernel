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


def test_a_kill_before_the_block_reuses_the_open_question_and_its_answer_books_the_metered_cap(tmp_path, monkeypatch):
    """Superseded rule (before #173 H.G4), kept as lineage: the "not executed" answer released attempt 0's held cap
    and one retry fit the signed $0.05 budget. worker.commission is metered, so the answer now replaces the hold by a
    booking of its signed cap: the retry exceeds the budget and runs only on the founder's approval."""
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
        # #173's model (merge of e410977): the held cap is a reservation the budget counts, not booked spend
        assert m.blocker["request_id"] == open_question["request_id"]
        assert (m.spent_usd, m.reserved_usd, m.committed_usd) == (0.0, 0.05, 0.05)
    drop(home, signed(key, body_id, "DECISION", {"request_id": open_question["request_id"],
                                                 "answer": "reconcile_not_executed"}))
    _run(home, clock, 1)
    with Body(home, clock=clock) as body:
        m = body.engine.book.missions[mid]
        assert ("commission", 0) not in m.reserved      # the answer settled attempt 0's hold, once
        # A metered worker's "not executed" settles its effect, not its possible spend (#173 H.G4): the cap is booked,
        # so the retry exceeds the signed $0.05 budget and is asked for, never dispatched on its own.
        assert m.spent_usd == 0.05
        [spend] = [r for r in body.engine.book.open_requests() if r["kind"] == "APPROVAL"]
        assert spend["action_id"] == "commission" and "exceeds budget" in spend["why_now"]
    assert len(calls) == 1
    drop(home, signed(key, body_id, "DECISION", {"request_id": spend["request_id"], "answer": "approve"}))
    _run(home, clock, 1)
    assert len(calls) == 2                              # the one retry, after the founder funded it
