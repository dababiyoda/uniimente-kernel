"""Mission D (multi-worker execution): the mission budget across workers, and abandoning between dependent workers.

Acceptance D.G4: the cumulative budget across several workers in one mission was tested only at UNIT level
(LightCone.admits). D.G6: cancelling a mission between dependent worker tasks was untested. Both run here on the
canonical Body path (MissionEngine, AuthorityOffice, ConsequenceGate) with the D2 mission from
test_greg_mission_d_handoffs.py: worker-a commits, worker-b consumes worker-a's receipted commit.

In-process Body with a test clock, a per-test Ed25519 key (not Alfonso's) and a scripted worker double:
SANDBOX_VERIFIED. No model, network or real provider.
"""
from __future__ import annotations

import pytest

from greg import workers
from greg.body import Body
from tests.greg_fixtures import Clock, drop, host_worker_confinement, make_body, signed, workspace
from tests.integration.test_greg_mission_d_handoffs import Double, _repo, _spec

MID = "m:two-workers"


def _body(tmp_path, monkeypatch, double, spec_kw):
    data = tmp_path / "data"
    data.mkdir()
    repo = _repo(data)
    home, key, bid, _ = make_body(tmp_path, read_roots=[data], worker_confinement=host_worker_confinement())
    monkeypatch.setitem(workers.PROVIDERS, "scripted", double)
    drop(home, signed(key, bid, "MISSION", _spec(repo, **spec_kw)))
    return home, key, bid


def _ticks(body, clock, n, seconds=60):
    for _ in range(n):
        body.tick()
        clock.advance(seconds)


def _facts(body, kind):
    return [e.payload for e in body.journal.replay(kind)]


def _grants(body):
    return [r.payload for r in body.ledger.by_type("event") if r.payload.get("type") == "greg.authority.grant_issued"]


def _actions(body, action_id):
    return [a for a in _facts(body, "mission.action") if a["action_id"] == action_id]


# -- D.G4 ------------------------------------------------------------------------------------------------
def test_the_mission_budget_holds_across_workers_and_only_the_founder_lifts_it(tmp_path, monkeypatch):
    """A 0.7 cone and two workers signed at 0.5 each: worker-a books 0.4, so worker-b would exceed the mission
    budget. It becomes exactly one APPROVAL naming the arithmetic; nothing is granted or run for its scope until a
    signed DECISION approves it; then it runs exactly once and the mission books the sum."""
    double = Double(b_cost=0.25)
    home, key, bid = _body(tmp_path, monkeypatch, double, {"budget": 0.7, "cost_b": 0.5, "requires": True})
    clock = Clock()
    with Body(home, clock=clock) as body:
        _ticks(body, clock, 8)
        assert [c["order"] for c in double.calls] == ["a"], "worker-b never runs past the mission budget unasked"
        m = body.engine.book.missions[MID]
        assert m.spent_usd == pytest.approx(0.4)
        [ask] = [a for a in _facts(body, "decision.requested") if a["action_id"] == "worker-b"]
        assert ask["kind"] == "APPROVAL" and ask["why_now"] == "cost 0.5 with 0.4 spent exceeds budget 0.7"
        assert ask["evidence"]["budget"] == {"spent_usd": 0.4, "budget_usd": 0.7}
        assert ask["authority_requested"]["cost_usd"] == 0.5
        assert m.blocker["request_id"] == ask["request_id"]
        assert not [g for g in _grants(body) if g["scope_digest"] == ask["scope_digest"]], \
            "no grant is issued for worker-b's scope before the founder approves it"
        assert not _actions(body, "worker-b")

        drop(home, signed(key, bid, "DECISION", {"request_id": ask["request_id"], "answer": "approve",
                                                 "reason": "worth the overrun"}))
        _ticks(body, clock, 8)
        assert [c["order"] for c in double.calls] == ["a", "b"], "approved, worker-b runs exactly once"
        [done_b] = [a for a in _actions(body, "worker-b") if a["status"] == "DONE"]
        assert [g["scope_digest"] for g in _grants(body)].count(ask["scope_digest"]) == 1
        assert done_b["cost_usd"] == pytest.approx(0.25)
        m = body.engine.book.missions[MID]
        assert m.spent_usd == pytest.approx(0.4 + 0.25), "the mission books the sum of what its workers spent"
        assert len([a for a in _facts(body, "decision.requested") if a["action_id"] == "worker-b"]) == 1, \
            "one approval covers the one dispatch: no second ask"
        assert m.status == "ACHIEVED"
        assert body.ledger.verify_chain()[0]


def test_a_worker_inside_the_remaining_budget_needs_no_approval(tmp_path, monkeypatch):
    """The control for the test above: with room left in the mission budget, the same consumer is never asked."""
    double = Double(b_cost=0.25)
    home, _, _ = _body(tmp_path, monkeypatch, double, {"budget": 1.0, "cost_b": 0.5, "requires": True})
    clock = Clock()
    with Body(home, clock=clock) as body:
        _ticks(body, clock, 8)
        assert [c["order"] for c in double.calls] == ["a", "b"]
        assert not [a for a in _facts(body, "decision.requested") if a["action_id"] == "worker-b"]
        assert body.engine.book.missions[MID].status == "ACHIEVED"


# -- D.G6 ------------------------------------------------------------------------------------------------
def test_abandoning_between_dependent_workers_stops_the_consumer_and_keeps_the_producer(tmp_path, monkeypatch):
    """After worker-a is DONE (and before worker-b is dispatched) the founder abandons the mission: worker-b is
    never called, gets no grant and no work order; worker-a's evidence and receipt stay; the ledger verifies."""
    double = Double()
    home, key, bid = _body(tmp_path, monkeypatch, double, {"budget": 2.0, "requires": True})
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(8):
            body.tick()
            clock.advance(60)
            if [a for a in _actions(body, "worker-a") if a["status"] == "DONE"]:
                break
        [done_a] = [a for a in _actions(body, "worker-a") if a["status"] == "DONE"]
        assert [c["order"] for c in double.calls] == ["a"] and not _actions(body, "worker-b")
        grants_before = len(_grants(body))

        drop(home, signed(key, bid, "LIFECYCLE", {"mission_id": MID, "state": "ABANDONED", "reason": "not wanted"}))
        _ticks(body, clock, 6)
        m = body.engine.book.missions[MID]
        assert m.status == "ABANDONED"
        assert [c["order"] for c in double.calls] == ["a"], "the consumer is never called after the abandon"
        assert not _actions(body, "worker-b"), "no worker-b action of any kind is recorded"
        new_grants = _grants(body)[grants_before:]
        assert not new_grants, f"nothing is granted after the abandon: {new_grants}"
        orders = workspace(home, MID) / "work-orders"
        assert (orders / "a").is_dir() and not (orders / "b").exists(), "worker-a's work order stays; none for b"
        # worker-a's evidence and receipt are kept: the receipt is still on the ledger, unchanged
        receipt = body.ledger.find(done_a["receipt"])
        assert receipt is not None and receipt.payload["result"]["output"]["commit"]
        assert body.ledger.verify_chain()[0]
