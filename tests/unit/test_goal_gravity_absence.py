"""Founder return report: the absence digest is ledger-derived, honest and requests nothing.

Deterministic and model-free. Passing proves the fold works on this tree; it is not evidence that any move
touched reality.
"""
from __future__ import annotations

import pytest

from egregore.absence import AbsenceReporter
from egregore.contracts import ContractError
from egregore.goals import InterventionSpec
from provenance.ledger import EvidenceLedger
from tests.unit.test_goal_gravity import (  # noqa: F401  (stack is a fixture)
    GOOD, T0, T1, T2, T3, brief_move, governor, grant_for, make_loop, obs, outreach_move, robotics_goal, signal, stack,
)
from tests.unit.test_goal_gravity_seams import hardware_signal, simple_goal

EARLY_SINCE, EARLY_UNTIL = "2026-10-01T00:00:00Z", "2026-10-02T00:00:00Z"
LATE_SINCE, LATE_UNTIL = "2027-01-01T00:00:00Z", "2027-01-02T00:00:00Z"


def package_move(**kw):
    base = dict(intervention_id="assemble-package", description="assemble the founder decision package",
                action_class="package.assemble", requested_capability="package.assemble", consequence_class="internal_write",
                target="sandbox:packages", expected_outcome="package assembled", payload={"kind": "decision"}, tactic="package")
    base.update(kw)
    return InterventionSpec.build(**base)


def with_moves(spec, *moves):
    """The same goal with the first node's moves replaced; the content-addressed id is recomputed."""
    body = {k: v for k, v in spec.to_dict().items() if k != "goal_id"}
    body["plan"] = [{**spec.plan[0].to_dict(), "interventions": [m.to_dict() for m in moves]}] + [n.to_dict() for n in spec.plan[1:]]
    return type(spec).from_dict(body)


def executed_brief(stack, loop, *, cost=0.04, executor=GOOD, now=T1):
    """One goal, one executed brief (receipt), one prepared outreach (ask)."""
    compiled, passports, ledger, gate, actor = stack
    spec = with_moves(robotics_goal(second_node=False), brief_move(estimated_cost_usd=cost), outreach_move(estimated_cost_usd=0.5))
    goal_id = loop.registry.authorize(spec, now=T0)
    turn = loop.turn(trigger_id="t1", now=now, signals=[hardware_signal()], resources=governor(), gate=gate, executor=executor,
                     grants={"research.brief": grant_for(loop, gate, spec, brief_move(estimated_cost_usd=cost))},
                     evidence_confidence=0.9)
    return spec, goal_id, turn


# ---------------------------------------------------------------- empty and disjoint windows

def test_report_over_an_empty_window_is_zero_and_requests_nothing(stack):
    loop = make_loop(stack)
    loop.registry.authorize(robotics_goal(), now=T0)
    out = loop.return_report(since=EARLY_SINCE, until=EARLY_UNTIL)
    report = out["report"]
    assert report["kind"] == "information" and report["requests_nothing"] is True and "options" not in report
    assert report["executed"] == [] and report["prepared"] == [] and report["refused_by_gate"] == []
    assert report["turns"]["count"] == 0 and report["decisions_waiting_as_of_until"] == []
    assert report["founder_activity"]["away"] is True
    assert report["headline"][0].startswith("Nothing happened in this window")
    assert out["execution_authority"] == "none" and report["execution_authority"] == "none"
    with pytest.raises(ContractError):
        loop.return_report(since=EARLY_UNTIL, until=EARLY_SINCE)


def test_window_bounds_exclude_everything_outside_them(stack):
    loop = make_loop(stack)
    executed_brief(stack, loop)
    inside = loop.return_report(since=T0, until=T1, record=False)["report"]
    outside = loop.return_report(since=LATE_SINCE, until=LATE_UNTIL, record=False)["report"]
    assert len(inside["executed"]) == 1 and inside["turns"]["count"] == 1
    assert outside["executed"] == [] and outside["prepared"] == [] and outside["turns"]["count"] == 0
    assert outside["founder_activity"]["goals_authorized"] == 0 and inside["founder_activity"]["goals_authorized"] == 1


# ---------------------------------------------------------------- the founder's scene, honestly

def test_report_separates_executed_prepared_refused_and_unknown(stack):
    compiled, passports, ledger, gate, actor = stack
    loop = make_loop(stack)
    spec, goal_id, turn = executed_brief(stack, loop)
    # A second goal whose external move is dispatched and whose outcome is unknown (executor raised).
    ext = simple_goal(tag="ext", ceiling="external_contact", move=outreach_move(payload={"template": "ext"}))
    ext_id = loop.registry.authorize(ext, now=T0)

    def boom(_p):
        raise RuntimeError("carrier timeout")

    unknown = loop.turn(trigger_id="t2", now=T2, resources=governor(), gate=gate, executor=boom, evidence_confidence=0.9,
                        grants={"outreach.contact": grant_for(loop, gate, ext, outreach_move(payload={"template": "ext"}))},
                        signals=[signal("x", tags=["ext"], observations=[obs("g", "metric", 0)], observed_at=T2)])
    assert unknown.processed[0]["decisions"][0]["evidence_state"] == "unknown"
    # A third goal whose grant is bound to a different objective: the Gate refuses at admission.
    pkg = simple_goal(tag="pkg", move=package_move())
    pkg_id = loop.registry.authorize(pkg, now=T0)
    wrong = grant_for(loop, gate, pkg, package_move(intervention_id="assemble-other", description="assemble a different package",
                                                    target="sandbox:other", payload={"kind": "other"}))
    refused = loop.turn(trigger_id="t3", now=T3, resources=governor(), gate=gate, executor=GOOD, evidence_confidence=0.9,
                        grants={"package.assemble": wrong},
                        signals=[signal("y", tags=["pkg"], observations=[obs("g", "metric", 0)], observed_at=T3)])
    pkg_summary = next(p for p in refused.processed if p["goal_id"] == pkg_id)
    assert pkg_summary["decisions"][0]["evidence_state"] == "failed"

    out = loop.return_report(since=T1, until=T3)
    report = out["report"]
    # Authorizations happened at T0, before the window: the founder was away for the whole window.
    assert report["founder_activity"]["away"] is True and report["founder_activity"]["goals_authorized"] == 0
    # Executed: exactly the brief, with a receipt that exists on the one ledger; never the prepared outreach.
    assert [e["intervention_id"] for e in report["executed"]] == ["compile-brief"]
    receipt = report["executed"][0]["receipt_hash"]
    assert receipt and ledger.find(receipt) is not None and ledger.find(receipt).record_type == "receipt"
    assert report["executed"][0]["reconciled"] is True and report["executed"][0]["verification"] is None
    assert "contact-engineers" in {p["intervention_id"] for p in report["prepared"]}
    assert all(p["intervention_id"] != "compile-brief" for p in report["prepared"])
    # Refused by the Gate (not by the classifier) with the Gate's own reasons.
    assert [r["intervention_id"] for r in report["refused_by_gate"]] == ["assemble-package"]
    assert report["refused_by_gate"][0]["gate_state"] == "refused" and any("grant" in x for x in report["refused_by_gate"][0]["reasons"])
    # The unknown attempt is open as of the end of the window and is never counted as executed.
    assert [o["goal_id"] for o in report["open_attempts_as_of_until"]] == [ext_id]
    assert report["open_attempts_as_of_until"][0]["evidence_state"] == "unknown"
    assert report["attempted_in_window"] == 3   # three dispatch attempts were recorded, one became executed, one unknown, one failed
    # Decisions waiting: the outreach ask opened at T1 (a decision), the unknown attempt informs, nothing is requested.
    waiting = report["decisions_waiting_as_of_until"]
    assert waiting and all(w["kind"] == "decision" for w in waiting) and all(w["waiting_seconds"] > 0 for w in waiting)
    assert any(w["goal_id"] == goal_id for w in waiting)
    # Money is estimates with reconciliation flags, never settlement.
    assert report["money"]["estimated_cost_usd_executed"] == 0.04
    assert report["money"]["estimated_cost_usd_prepared_not_spent"] == 0.5
    assert report["money"]["executed_moves_reconciled"] == 1 and report["money"]["executed_moves_unreconciled"] == 0
    assert "not money moved" in report["money"]["note"]
    # Retention: the positive, reconciled outcome retained its receipt as an evidence asset automatically.
    assert report["retained"]["retentions"] >= 1 and report["retained"]["assets_by_kind"].get("evidence", 0) >= 1
    # Per goal.
    per = {g["goal_id"]: g for g in report["goals"]["per_goal"]}
    assert per[goal_id]["executed"] == 1 and per[goal_id]["prepared"] >= 1 and per[ext_id]["open_attempts"] == 1
    assert per[pkg_id]["refused_by_gate"] == 1 and report["goals"]["active_in_window"] == 3
    # Headline sentences carry the scene without inflating it.
    text = " ".join(report["headline"])
    assert "1 move(s) executed through the Consequence Gate with receipts" in text
    assert "not a bank statement" in text and "requests nothing" in text
    assert "1 dispatched move(s) have an unknown outcome" in text
    assert "You answered nothing in this window" in text
    assert report["evidence_tier"]["externally_verified_moves"] == 0
    assert report["evidence_tier"]["prepared_counted_as_executed"] is False
    assert out["recorded"] is True and ledger.find(out["record_hash"]).record_type == AbsenceReporter.REPORT_RECORD
    # The ext goal woke by cadence at T3 and informed (emergency) about its unknown external move: an information item,
    # never a decision. Reporting itself is information: no ask was opened or closed by it.
    assert any(i["urgency"] == "emergency" and i["category"] == "reconciliation" for i in report["information_items_in_window"])
    assert len([a for a in loop.attention.open_asks() if a["kind"] in ("decision", "confirmation")]) == len(waiting)


def test_executor_claims_are_not_verification_but_an_independent_verifier_is(stack):
    compiled, passports, ledger, gate, actor = stack
    loop = make_loop(stack)
    claims = lambda p: {**GOOD(p), "validation_status": "externally_verified"}  # noqa: E731
    spec, goal_id, turn = executed_brief(stack, loop, executor=claims)
    before = loop.return_report(since=T0, until=T1, record=False)["report"]
    assert before["executed"][0]["executor_claimed_validation"] == "externally_verified"
    assert before["executed"][0]["verification"] is None and before["verifications"] == []
    assert before["evidence_tier"]["externally_verified_moves"] == 0
    assert before["evidence_tier"]["executor_claims_counted_as_verification"] is False
    receipt = before["executed"][0]["receipt_hash"]
    loop.verify_outcome(goal_id, brief_move(estimated_cost_usd=0.04).route_hash, verifier="auditor:independent",
                        evidence_refs=[receipt], note="brief exists and matches", now=T2)
    after = loop.return_report(since=T0, until=T2, record=False)["report"]
    assert len(after["executed"]) == 1   # the verification-derived record never double counts the execution
    assert after["executed"][0]["verification"]["verdict"] == "confirmed"
    assert after["executed"][0]["verification"]["verifier"] == "auditor:independent"
    assert len(after["verifications"]) == 1 and after["evidence_tier"]["externally_verified_moves"] == 1
    assert after["learned"]["independent_verifications"] == 1
    # The earlier window still reports the move as unverified: verification is dated, not retroactive.
    assert loop.return_report(since=T0, until=T1, record=False)["report"]["evidence_tier"]["externally_verified_moves"] == 0


def test_decisions_waiting_are_as_of_until_and_founder_activity_is_dated(stack):
    loop = make_loop(stack)
    spec, goal_id, turn = executed_brief(stack, loop)
    ask = next(a for a in loop.attention.open_asks() if a["route_hash"] == outreach_move(estimated_cost_usd=0.5).route_hash)
    loop.founder_answer(ask["item_id"], decision="refuse", actor="alfonso_lopez", note="not this route", now=T2)
    at_t1 = loop.return_report(since=T0, until=T1, record=False)["report"]
    at_t2 = loop.return_report(since=T0, until=T2, record=False)["report"]
    assert ask["item_id"] in {w["item_id"] for w in at_t1["decisions_waiting_as_of_until"]}
    assert at_t1["founder_activity"]["answers"] == 0
    assert ask["item_id"] not in {w["item_id"] for w in at_t2["decisions_waiting_as_of_until"]}
    assert at_t2["founder_activity"]["answers"] == 1 and at_t2["founder_activity"]["answer_decisions"] == {"refuse": 1}
    assert at_t2["founder_activity"]["preferences_or_refusals"] >= 1 and at_t2["founder_activity"]["away"] is False
    assert "alfonso_lopez" in at_t2["founder_activity"]["actors"]
    assert "You acted 1 answer(s)" in " ".join(at_t2["headline"])


def test_deferred_asks_are_listed_separately_not_as_waiting(stack):
    loop = make_loop(stack)
    spec, goal_id, turn = executed_brief(stack, loop)
    ask = next(a for a in loop.attention.open_asks() if a["goal_id"] == goal_id)
    loop.founder_answer(ask["item_id"], decision="defer", actor="alfonso_lopez", note="next week", now=T2)
    report = loop.return_report(since=T0, until=T2, record=False)["report"]
    assert ask["item_id"] not in {w["item_id"] for w in report["decisions_waiting_as_of_until"]}
    deferred = [d for d in report["deferred_as_of_until"] if d["item_id"] == ask["item_id"]]
    assert deferred and deferred[0]["resurface_after"] == "2026-10-21T13:00:00Z"


# ---------------------------------------------------------------- determinism and idempotence

def test_two_loops_over_one_ledger_and_a_restart_produce_the_same_report_recorded_once(stack):
    compiled, passports, _ledger, gate, actor = stack
    loop_a = make_loop(stack)
    executed_brief(stack, loop_a)
    first = loop_a.return_report(since=T0, until=T1)
    loop_b = make_loop(stack)
    second = loop_b.return_report(since=T0, until=T1)
    assert first["report"] == second["report"] and first["report_id"] == second["report_id"]
    assert first["recorded"] is True and second["recorded"] is False and second["record_hash"] == first["record_hash"]
    assert len(loop_a.ledger.by_type(AbsenceReporter.REPORT_RECORD)) == 1
    # A different window is a different report and is recorded on its own.
    other = loop_b.return_report(since=T0, until=T2)
    assert other["report_id"] != first["report_id"] and other["recorded"] is True
    assert len(loop_a.ledger.by_type(AbsenceReporter.REPORT_RECORD)) == 2
    ok, msg = loop_a.ledger.verify_chain()
    assert ok, msg


def test_report_is_a_fold_of_records_not_of_in_memory_state(stack):
    """A fresh loop over the same records (no shared Python objects) reports identically; the report record itself
    is retained as evidence of what was shown."""
    compiled, passports, _ledger, gate, actor = stack
    ledger = EvidenceLedger(compiled.constitution_hash)
    loop = make_loop(stack, ledger=ledger)
    executed_brief((compiled, passports, ledger, type(gate)(compiled=compiled, passports=passports, ledger=ledger,
                                                              signer=gate.signer), actor), loop)
    shown = loop.return_report(since=T0, until=T1)
    fresh = make_loop(stack, ledger=ledger)
    again = fresh.return_report(since=T0, until=T1)
    assert again["report"] == shown["report"] and again["recorded"] is False
    stored = ledger.find(shown["record_hash"]).payload
    assert stored["report"] == shown["report"] and stored["disposition"].startswith("information_only")


def test_learning_counts_belief_updates_and_contradictions_in_window(stack):
    loop = make_loop(stack)
    loop.registry.authorize(robotics_goal(second_node=False), now=T0)
    loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal("e1")], resources=governor(), evidence_confidence=0.9)
    # A second source disagrees: the contradiction is retained, never collapsed, and the report counts it.
    other = signal("e2", domain="hardware", source="feed://other-prices", observed_at=T2,
                   observations=[obs("actuator", "cost_usd", 900, 0.6)])
    loop.turn(trigger_id="t2", now=T2, signals=[other], resources=governor(), evidence_confidence=0.9)
    report = loop.return_report(since=T0, until=T2, record=False)["report"]
    assert report["learned"]["experiences_integrated"] >= 2
    assert report["learned"]["contradictions_retained"] == 1
    assert report["turns"]["count"] == 2 and report["turns"]["signals_integrated"] == 2
    assert loop.return_report(since=T0, until=T1, record=False)["report"]["learned"]["contradictions_retained"] == 0


# ---------------------------------------------------------------- defect found while building the report (fixed in this increment)

def test_an_open_attempt_is_never_hidden_by_a_later_grantless_wake_and_never_redispatched(stack):
    """Reproduced on 6ce6b3f: a grantless wake re-classified the route to PREPARE, wrote a fresh ``planned`` record,
    hid the ``unknown`` attempt from ``_latest_by_route``, dropped the reconciliation blocker, and a later grant
    dispatched the route a second time under an attempt-suffixed proposal id. A route with an open attempt is now
    never re-classified until reconciliation closes it."""
    compiled, passports, ledger, gate, actor = stack
    loop = make_loop(stack)
    move = outreach_move(payload={"template": "ext"})
    ext = simple_goal(tag="ext", ceiling="external_contact", move=move)
    ext_id = loop.registry.authorize(ext, now=T0)

    def boom(_p):
        raise RuntimeError("carrier timeout")

    loop.turn(trigger_id="t1", now=T1, resources=governor(), gate=gate, executor=boom, evidence_confidence=0.9,
              grants={"outreach.contact": grant_for(loop, gate, ext, move)},
              signals=[signal("x1", tags=["ext"], observations=[obs("g", "metric", 0)])])
    assert loop._latest_by_route(ext_id)[move.route_hash]["evidence_state"] == "unknown"
    records_before = len(ledger.by_type(loop.INTERVENTION_RECORD))
    # The goal wakes again with no grant: the classifier would prepare, the loop must not write a fresh record.
    again = loop.turn(trigger_id="t2", now=T2, resources=governor(), evidence_confidence=0.9,
                      signals=[signal("x2", tags=["ext"], observations=[obs("g", "metric", 0)], observed_at=T2)])
    decision = next(d for d in again.processed[0]["decisions"] if d["intervention_id"] == move.intervention_id)
    assert decision["evidence_state"] == "unknown" and "reconciliation required" in decision["disposition"]
    assert loop._latest_by_route(ext_id)[move.route_hash]["evidence_state"] == "unknown"
    assert len(ledger.by_type(loop.INTERVENTION_RECORD)) == records_before
    assert not [a for a in loop.attention.open_asks() if a.get("route_hash") == move.route_hash], "no ask for an unknown move"
    assert any("reconciliation required" in b for b in loop.registry.state(ext_id).blockers)
    # A grant arrives later: still no second dispatch while the first outcome is unknown.
    calls = []

    def tracked(p):
        calls.append(p.requested_capability)
        return GOOD(p)

    loop.registry.wake(ext_id, reason="test", now=T3)
    third = loop.turn(trigger_id="t3", now=T3, resources=governor(), gate=gate, executor=tracked, evidence_confidence=0.9,
                      grants={"outreach.contact": grant_for(loop, gate, ext, move)})
    assert calls == [] and third.processed[0]["decisions"][0]["evidence_state"] == "unknown"
    assert len(ledger.by_type("grant_dispatch")) == 1
    # Only an accountable reconciliation releases the route, and the report shows the attempt open until then.
    report = loop.return_report(since=T0, until=T3, record=False)["report"]
    assert [o["goal_id"] for o in report["open_attempts_as_of_until"]] == [ext_id]
    loop.reconcile(ext_id, now=T3, resolutions={move.route_hash: {"state": "failed", "reconciled_by": "alfonso_lopez",
                                                                 "evidence_refs": ["carrier:ticket-77"], "note": "nothing sent"}})
    assert loop._latest_by_route(ext_id)[move.route_hash]["evidence_state"] == "failed"
    assert loop.return_report(since=T0, until=T3, record=False)["report"]["open_attempts_as_of_until"] == []


def test_an_executed_route_is_not_re_proposed_or_hidden_by_a_later_grantless_wake(stack):
    """The same defect on the done side: a grantless wake used to overwrite ``executed`` with ``planned``, so status
    lost the receipt, a new ask for already-done work could open, and verify_outcome refused the move."""
    loop = make_loop(stack)
    spec, goal_id, turn = executed_brief(stack, loop)
    route = brief_move(estimated_cost_usd=0.04).route_hash
    asks_before = {a["item_id"] for a in loop.attention.open_asks()}
    loop.registry.wake(goal_id, reason="test", now=T2)
    again = loop.turn(trigger_id="t2", now=T2, resources=governor(), evidence_confidence=0.9)
    decision = next(d for d in again.processed[0]["decisions"] if d["intervention_id"] == "compile-brief")
    assert decision["evidence_state"] == "executed" and "not re-proposed" in decision["disposition"]
    assert loop.status(goal_id, now=T2)["evidence_state"][route] == "executed"
    assert {a["item_id"] for a in loop.attention.open_asks()} == asks_before
    receipt = loop._latest_by_route(goal_id)[route]["detail"]["receipt_hash"]
    loop.verify_outcome(goal_id, route, verifier="auditor:independent", evidence_refs=[receipt], note="ok", now=T3)
    assert loop._latest_by_route(goal_id)[route]["evidence_state"] == "externally_verified"
