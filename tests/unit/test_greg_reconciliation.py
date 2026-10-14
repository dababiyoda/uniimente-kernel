"""Founder reconciliation of an UNCERTAIN dispatch, on a real body.

An executor exception between the Gate's dispatch and its receipt makes the action UNCERTAIN;
the founder then states whether it executed. The reconciliation record is a new fact about
that same attempt: it names the capability the dispatch used, books the signed spend cap when
the founder says it executed, counts once in routing, and is never a receipted execution that
routing can blame or a consumer can bind from. The founder key is a per-test key, not Alfonso's.
"""
import json

from types import SimpleNamespace

import pytest

from foundry.systems import reputation
from greg import resilience, routing
from greg.body import Body
from greg.missions import Unbound
from greg.tribunal import morning_report
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy


def explode_once(body, capability="fs.write"):
    """The first dispatch dies mid-effect (power loss), so the Gate records no receipt."""
    real, calls = body.registry.adapters[capability], []

    def adapter(params, ctx):
        calls.append(params)
        if len(calls) == 1:
            raise RuntimeError("power lost mid-effect")
        return real(params, ctx)
    body.registry.adapters[capability] = adapter
    return calls


def tick(body, clock, n):
    for _ in range(n):
        body.tick()
        clock.advance(1)


def reconcile(body, key, body_id, clock, answer, *, after=6):
    [request] = [r for r in body.engine.book.open_requests() if r["kind"] == "RECONCILIATION"]
    drop(body.layout.home, signed(key, body_id, "DECISION", {"request_id": request["request_id"], "answer": answer,
                                                             "reason": "inspected the retained evidence"}))
    tick(body, clock, after)
    return request


def actions(body, mission_id=None):
    return [e.payload for e in body.journal.replay("mission.action")
            if mission_id is None or e.payload["mission_id"] == mission_id]


@pytest.mark.parametrize("answer", ["reconcile_executed", "reconcile_not_executed"])
def test_reconciling_a_function_named_strategy_names_the_dispatched_capability(tmp_path, answer):
    home, key, body_id, _ = make_body(tmp_path)
    note = workspace(home, "m:reconcile-fn") / "c.txt"
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:reconcile-fn", checks=[note_check("c", note, "ok")],
        strategies=[{"action_id": "w", "function": "filesystem.write", "target": "workspace:c.txt",
                     "params": {"relative_path": "c.txt", "content": "ok"}, "advances": ["c"],
                     "rationale": "write through whichever capability serves the function"}],
        capabilities=["fs.read", "fs.write"])))
    clock = Clock()
    with Body(home, clock=clock) as body:
        explode_once(body)
        tick(body, clock, 3)
        assert [a["status"] for a in actions(body)] == ["UNCERTAIN"]
        reconcile(body, key, body_id, clock, answer)
        # every reader of mission.action renders the reconciled ledger
        report = resilience.summary(body.journal)
        morning = morning_report(body.journal, body.engine)
        assert set(report["after_failure"]) == {"fs.write"}
        assert {r["capability"] for r in morning["routing_knowledge"]} >= {"fs.write"}
        reconciled = [a for a in actions(body) if a.get("route") == "founder_reconciliation"]
        assert len(reconciled) == 1
        assert reconciled[0]["capability"] == "fs.write" and reconciled[0]["attempt"] == 0
        assert reconciled[0]["receipt"] is None and reconciled[0]["dispatch_route"] == "api"
        # a founder reconciliation is not a receipted execution for routing to blame
        assert not [o for o in body.journal.replay("routing.outcome") if not o.payload.get("receipt")]


@pytest.mark.parametrize("answer, sequence, counts", [
    ("reconcile_not_executed", [("w", 0, "UNCERTAIN"), ("w", 0, "RECONCILED_NOT_EXECUTED"), ("w", 1, "DONE")],
     {"done": 1, "failed": 1, "founder_reconciled": 0, "ineffective": 0}),
    ("reconcile_executed", [("w", 0, "UNCERTAIN"), ("w", 0, "DONE"), ("w2", 0, "DONE")],
     {"done": 1, "failed": 0, "founder_reconciled": 1, "ineffective": 0}),
])
def test_routing_counts_one_outcome_per_attempt_and_a_reconciliation_is_no_receipted_success(
        tmp_path, answer, sequence, counts):
    home, key, body_id, _ = make_body(tmp_path)
    note = workspace(home, "m:reconcile-routing") / "c.txt"
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:reconcile-routing", checks=[note_check("c", note, "ok")],
        strategies=[write_strategy("w", "c.txt", "ok", ["c"]),
                    write_strategy("w2", "c.txt", "ok, by the alternative", ["c"])],
        capabilities=["fs.read", "fs.write"])))
    clock = Clock()
    with Body(home, clock=clock) as body:
        explode_once(body)
        tick(body, clock, 3)
        reconcile(body, key, body_id, clock, answer)
        assert [(a["action_id"], a["attempt"], a["status"]) for a in actions(body)] == sequence
        assert body.engine.book.missions["m:reconcile-routing"].status == "ACHIEVED"
        record = routing.track_record(body.journal)["fs.write"]
    assert {k: record.get(k, 0) for k in counts} == counts
    assert routing.reliability(record) == routing.reliability({**record, "founder_reconciled": 0})


def test_a_paid_action_reconciled_as_executed_books_its_signed_cap_against_the_budget(tmp_path):
    """The founder says the paid dispatch ran, but no provider measured it: the signed cap is spent."""
    home, key, body_id, _ = make_body(tmp_path)
    note = workspace(home, "m:reconcile-paid") / "c.txt"
    spec = mission("m:reconcile-paid", checks=[note_check("c", note, "ok")],
                   strategies=[write_strategy("a", "c.txt", "ok", ["c"], cost_usd=0.6),
                               write_strategy("b", "c.txt", "ok, paid again", ["c"], cost_usd=0.6)],
                   capabilities=["fs.read", "fs.write"], budget=1.0)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        explode_once(body)
        tick(body, clock, 3)
        reconcile(body, key, body_id, clock, "reconcile_executed")
        # a second 0.6 would pass the signed 1.0 budget: it is not run, it is asked for
        assert not [a for a in actions(body) if a["action_id"] == "b"]
        [ask] = body.engine.book.open_requests()
        assert ask["kind"] == "APPROVAL" and ask["action_id"] == "b"
        m = body.engine.book.missions["m:reconcile-paid"]
        assert m.spent_usd == pytest.approx(0.6) and m.status == "ACTIVE" and not note.exists()
        [reconciled] = [a for a in actions(body) if a.get("route") == "founder_reconciliation"]
        assert reconciled["cost_usd"] == reconciled["cost_cap_usd"] == 0.6
        assert reconciled["spend_basis"] == "signed_cap: founder reconciled executed; provider spend unknown"
        from greg.mission_control import cost_rows
        [row] = cost_rows(actions(body), [{"mission_id": "m:reconcile-paid", "cone": spec["light_cone"]}], [])
        assert row["booked_usd"] == row["unknown_at_cap_usd"] == 0.6 and row["measured_usd"] == 0.0


class Journal:
    """A retained journal as readers see it: append-only payloads, some written before 2026-10-14."""

    def __init__(self):
        self.events = []

    def add(self, kind, payload, at="2026-10-13T08:00:00+00:00"):
        self.events.append(SimpleNamespace(type="greg." + kind, payload=payload, occurred_at=at,
                                           event_id=f"ev-{len(self.events)}"))
        return self

    def replay(self, prefix=""):
        return [e for e in self.events if e.type.startswith("greg." + prefix)]


def test_readers_tolerate_legacy_and_unnamed_reconciliation_records():
    uncertain = {"mission_id": "m1", "action_id": "w", "attempt": 0, "status": "UNCERTAIN", "capability": "fs.write",
                 "route": "api", "receipt": None, "cost_usd": 0.0, "at": "2026-10-13T08:00:00+00:00"}
    legacy = {"mission_id": "m1", "action_id": "w", "attempt": 0, "status": "DONE", "cost_usd": 0.0,
              "reasons": ["founder reconciliation: reconcile_executed"]}   # no capability, route, receipt or at
    unnamed = {"mission_id": "m2", "action_id": "f", "attempt": 0, "status": "RECONCILED_NOT_EXECUTED",
               "capability": None, "route": "founder_reconciliation", "receipt": None, "cost_usd": 0.0,
               "reasons": ["founder reconciliation: reconcile_not_executed"], "at": "2026-10-13T09:00:00+00:00"}
    j = Journal().add("mission.action", uncertain).add("mission.action", legacy).add("mission.action", unnamed)
    j.add("mission.action", {**uncertain, "mission_id": "m2", "action_id": "g", "status": "UNAVAILABLE"})
    j.add("routing.outcome", {"mission_id": "m2", "action_id": "f", "capability": None, "verdict": "ineffective",
                              "receipt": None, "reason": "retained before the reconciliation named its capability"})
    j.add("mission.appraised", {"mission_id": "m1", "verdict": "VERIFIED", "checks": {}})
    record = routing.track_record(j)
    # the legacy reconciliation replaces its attempt's UNCERTAIN and inherits the capability it reconciles
    assert record["fs.write"] == {"done": 0, "failed": 1, "ineffective": 0, "refuted": 0, "verified": 0,
                                  "founder_reconciled": 1}
    assert [r["capability"] for r in routing.routing_knowledge(j)] == ["?", "fs.write"]
    summary = resilience.summary(j)
    assert set(summary["after_failure"]) == {"?", "fs.write"}
    assert [c["capability"] for c in summary["common_cause_candidates"]] == ["fs.write"]
    events = [{"type": e.type, "event_id": e.event_id, "payload": e.payload, "at": e.occurred_at} for e in j.events]
    assert [r["subject"] for r in reputation.from_greg(events)] == ["?"]
