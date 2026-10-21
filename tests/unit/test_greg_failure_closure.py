"""Directive sections 11 and 14: the outcome plane hears failures, each independently appraised, each once.

Each test reproduced a defect before the change (tests/evidence/antifragility-2026-10-15). A mission whose signed
check still failed after every admissible strategy ran was blocked and never appraised. Settlement credits only
appraised closures, so the competence ledger heard successes only: the pre-registered stress settled 7 of 12
missions, all correct, while 5 had failed. Live negative evidence could never demote a method from real missions.
Re-observations of a compiled claim also hashed differently, which would have settled one failure several times.
"""
from __future__ import annotations

import json

import pytest

from greg.body import Body
from greg.cognition import compiler, settlement
from greg.routing import track_record
from greg.sop import verified_appraisals
from tests.greg_fixtures import Clock, make_body, mission, note_check, signed, workspace, write_strategy

METHODS = ("cognition.swarm", "cognition.blackbox")
LOW = {"function": "sphere", "bounds": [[-5.12, 5.12]] * 3, "budget": 300}


def blackbox(mid: str, seed: int, tau: float) -> dict:
    data = {**LOW, "shift": [0.5, -0.25, 1.0], "seed": seed}
    params = {"problem_id": f"real:{mid}", "compile": {"geometry": {"geometry": "optimization"}, "data": data}}
    return mission(mid, checks=[{
        "check_id": "good", "description": f"fitness at most {tau}",
        "sensor": {"capability": "cognition.solve", "target": "cognition:bb", "params": params},
        "predicate": {"op": "lte", "field": "result.fitness", "value": tau}}],
        strategies=[{"action_id": "compile", "capability": "cognition.solve", "target": "cognition:bb",
                     "params": params, "advances": ["good"], "rationale": "minimise"}],
        capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")


def run(tmp_path, specs, ticks=5):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    body = Body(home, clock=clock).open()
    body.boot()
    for cid in METHODS:
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": cid}))
    for spec in specs:
        body.apply(signed(key, body_id, "MISSION", spec))
    for _ in range(ticks):
        body.tick()
        clock.advance(31)
    return body, key, body_id, clock


def appraisals(body):
    return {e.payload["mission_id"]: e.payload for e in body.journal.replay("mission.appraised")}


def test_a_failed_mission_closes_unmet_and_is_appraised_as_a_verified_failure(tmp_path):
    body, *_ = run(tmp_path, [blackbox("m:fails", 1, 0.0), blackbox("m:passes", 1, 1e6)])
    try:
        [unmet] = [e.payload for e in body.journal.replay("mission.unmet")]
        assert unmet["mission_id"] == "m:fails" and unmet["failing_checks"] == ["good"]
        verdicts = appraisals(body)
        assert verdicts["m:fails"]["verdict"] == "VERIFIED_UNMET" and verdicts["m:fails"]["closure"] == "unmet"
        assert verdicts["m:fails"]["findings"] == [] and verdicts["m:passes"]["verdict"] == "VERIFIED"
    finally:
        body.close()


def test_settlement_hears_each_failure_once_and_reconciles_idempotently(tmp_path):
    body, *_ = run(tmp_path, [blackbox("m:f-one", 1, 0.0), blackbox("m:f-two", 2, 0.0), blackbox("m:okay", 3, 1e6)],
                   ticks=7)
    try:
        outcomes = settlement.measured_outcomes(body.journal)
        assert sorted((o["mission_id"], o["correct"]) for o in outcomes) == [
            ("m:f-one", False), ("m:f-two", False), ("m:okay", True)]       # re-observations revise, never add
        assert compiler._settled_counts(body.journal) == {"cognition.swarm": (3, 1)}
        settlement.reconcile(body.journal)
        before = len(body.journal.replay("cognition.settled"))
        settlement.reconcile(body.journal)
        assert len(body.journal.replay("cognition.settled")) == before
    finally:
        body.close()


def test_a_run_dependent_inner_request_never_settles_one_claim_twice(tmp_path, monkeypatch):
    """A claim's identity is its signed sensor params, not the inner request's digest. Before the thinking-budget
    fix the first step's latency limit carried planning time into that digest; any run-dependent field there must
    still settle each failure once, so this test injects one on every allotment."""
    from greg.cognition import budget
    original, calls = budget.Controller.allot, []

    def drifting(self, step, *, required):
        limit = original(self, step, required=required)
        calls.append(step)
        return None if limit is None else limit - 1e-6 * len(calls)
    monkeypatch.setattr(budget.Controller, "allot", drifting)
    body, *_ = run(tmp_path, [blackbox("m:f-one", 1, 0.0), blackbox("m:okay", 3, 1e6)], ticks=7)
    try:
        assert len(calls) > 2                                             # the claim was re-observed
        outcomes = settlement.measured_outcomes(body.journal)
        assert sorted((o["mission_id"], o["correct"]) for o in outcomes) == [("m:f-one", False), ("m:okay", True)]
    finally:
        body.close()


def test_a_verified_failure_is_never_read_as_a_success(tmp_path):
    body, *_ = run(tmp_path, [blackbox("m:fails", 1, 0.0)])
    try:
        assert "m:fails" not in verified_appraisals(body.journal)          # precedents, SOPs
        assert track_record(body.journal)["cognition.solve"]["verified"] == 0
        assert not body.journal.replay("mission.achieved")
    finally:
        body.close()


def test_a_forged_failure_closure_on_a_passing_mission_is_refuted(tmp_path):
    """Negative evidence demotes a method, so a failure claim needs proof as much as a success does."""
    body, *_ = run(tmp_path, [blackbox("m:passes", 1, 1e6)])
    try:
        forged = body.journal.record("mission.unmet", {"mission_id": "m:passes", "failing_checks": ["good"],
                                                        "actions_done": 1, "closure_rule": "forged", "at": "x"},
                                     key=["m:passes", "unmet", "forged"])
        verdict = body.appraise("m:passes", closure_event=forged.event_id)
        assert verdict["verdict"] == "REFUTED"
        assert any("satisfy the predicate the closure says fails" in f for f in verdict["findings"])
    finally:
        body.close()


def test_a_failure_the_world_no_longer_shows_is_refuted(tmp_path):
    home_note = None
    specs = []
    body, key, body_id, clock = run(tmp_path, specs, ticks=0)
    try:
        note = workspace(body.layout.home, "m:note") / "n.txt"
        home_note = note
        body.apply(signed(key, body_id, "MISSION", mission(
            "m:note", checks=[note_check("n", note, "wanted")],
            strategies=[write_strategy("w", "n.txt", "something else", ["n"])], capabilities=["fs.read", "fs.write"])))
        for _ in range(4):
            body.tick()
            clock.advance(31)
        [unmet] = body.journal.replay("mission.unmet")
        assert appraisals(body)["m:note"]["verdict"] == "VERIFIED_UNMET"
        home_note.write_text("wanted")                                      # the world now satisfies the check
        verdict = body.appraise("m:note", closure_event=unmet.event_id)
        assert verdict["verdict"] == "REFUTED" and any("world no longer matches" in f for f in verdict["findings"])
    finally:
        body.close()


def test_a_mission_waiting_on_a_precondition_is_not_closed_unmet(tmp_path):
    body, key, body_id, clock = run(tmp_path, [], ticks=0)
    try:
        note = workspace(body.layout.home, "m:wait") / "n.txt"
        never = workspace(body.layout.home, "m:wait") / "never.txt"
        body.apply(signed(key, body_id, "MISSION", mission(
            "m:wait", checks=[note_check("n", note, "x"), note_check("pre", never, "y")],
            strategies=[write_strategy("w", "n.txt", "x", ["n"], requires=["pre"])],
            capabilities=["fs.read", "fs.write"])))
        for _ in range(4):
            body.tick()
            clock.advance(31)
        assert body.journal.replay("mission.unmet") == []                   # nothing ran: no outcome to settle
    finally:
        body.close()


def test_real_failed_missions_now_demote_the_method_that_failed(tmp_path):
    """Live negative evidence from the canonical loop: before the change it could fire only in a patched test."""
    specs = [blackbox(f"m:fail-{i:02d}", i, 0.0) for i in range(11)]
    body, *_ = run(tmp_path, specs, ticks=6)
    try:
        n, k = compiler._settled_counts(body.journal)["cognition.swarm"]
        assert n >= 10 and k == 0 and compiler._settled_inhibition(n, k)
        from greg.cognition.cortex import reason
        r = reason({"problem_id": "after", "compile": {"geometry": {"geometry": "optimization"},
                                                        "data": {**LOW, "shift": [0, 0, 0], "seed": 99},
                                                        "execute": False}},
                   registry=body.registry, journal=body.journal)
        assert any(d["method"] == "cognition.swarm" and "0 of" in d["why"] for d in r["methods_demoted"])
        # demoted, never deleted: the frozen admission index rejects the other fit (SUPERSEDED), so with no
        # admissible alternative the demoted method still serves, and says so
        assert {"method": "cognition.blackbox", "why": "frozen admission status SUPERSEDED"} in r["methods_rejected"]
        assert r["method_or_composition_selected"] == "cognition.swarm"
    finally:
        body.close()
