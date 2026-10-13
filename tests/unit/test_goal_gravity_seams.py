"""Goal Gravity, second increment: seams, deficits, reconciliation, verification and founder controls.

Every test is deterministic and model-free. Passing them proves the mechanism on this tree;
it is not evidence of any external effect.
"""
from __future__ import annotations

import pytest

from capabilities.genome import GenomeRegistry
from egregore.attention import AttentionPolicy
from egregore.cognition_seam import GoalProposer, candidate_to_intervention, intervention_to_candidate
from egregore.contract_check import ContractViolation, validate_record
from egregore.contracts import Assessment, CandidateProposal, ContractError, IntegrityConflict, SignalEnvelope
from egregore.goals import GoalError, GoalSpec, OpportunityFactor, PlanNode, WakeCondition
from egregore.gravity import GoalGravityLoop
from egregore.resources import ResourceGovernor
from egregore.retention import DurableAsset
from egregore.runtime import StandingCognitionRuntime
from provenance.ledger import EvidenceLedger
from tests.unit.test_goal_gravity import (
    AUTH_REF, GOOD, T0, T1, T2, T3, brief_move, governor, grant_for, make_loop, obs, outreach_move, robotics_goal,
    signal, stack,  # noqa: F401  (fixture re-export)
)


# ---------------------------------------------------------------- helpers

def approving(role, *, score=0.8, veto=False, objections=()):
    def evaluate(candidate, signals, context):
        return Assessment.build(role=role, candidate_id=candidate.candidate_id, score=score, confidence=0.9,
                                objections=objections, veto=veto, evidence_refs=("review:test",))
    return evaluate


def cognition(ledger, *, proposers=None, guardian_veto=False):
    organs = {"goal-gravity": GoalProposer()}
    organs.update(proposers or {})
    return StandingCognitionRuntime(ledger=ledger, proposers=organs,
                                    evaluators={"guardian": approving("guardian", veto=guardian_veto),
                                                "treasury": approving("treasury")})


def make_cognitive_loop(stack, **kw):
    compiled, passports, ledger, gate, actor = stack
    runtime = cognition(ledger, **kw)
    return GoalGravityLoop(ledger=ledger, compiled=compiled, passports=passports, actor=actor.passport_id,
                           legal_principal="alfonso_lopez", genomes=GenomeRegistry(), cognition=runtime), runtime


def hardware_signal(event_id="e1", **kw):
    return signal(event_id, domain="hardware", tags=["robotics"], observations=[obs("actuator", "cost_usd", 420)], **kw)


def variant(spec, **changes):
    """A content-addressed spec cannot be edited in place; rebuild it with changes (new goal_id)."""
    body = {**spec.to_dict(), **changes}
    body.pop("goal_id", None)
    return GoalSpec.from_dict(body)


def simple_goal(*, sbm="g.metric", tag="g", priority=2, ceiling="internal_write", move=None, **kw):
    return GoalSpec.build(
        founder_intent=f"goal {tag}", desired_state=f"state {tag}", priority=priority,
        authority={"authorized_by": "alfonso_lopez", "authorization_ref": AUTH_REF,
                   "legal_principal": "alfonso_lopez", "max_consequence_class": ceiling},
        time_horizon="months",
        plan=[PlanNode.build(node_id="n", outcome="o", gate="g", sbm=sbm, sbm_direction="gte", sbm_target=1,
                             interventions=(move or brief_move(payload={"topic": tag}),), **kw.pop("node", {}))],
        wake_conditions=(WakeCondition.build(kind="tag", match=tag),), **kw)


# ---------------------------------------------------------------- cognition seam

def test_goal_deliberation_runs_through_the_standing_cognition_tick(stack):
    compiled, passports, ledger, gate, actor = stack
    loop, runtime = make_cognitive_loop(stack)
    spec = robotics_goal()
    goal_id = loop.registry.authorize(spec, now=T0)
    resources = governor()
    turn = loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=resources, evidence_confidence=0.9)
    summary = turn.processed[0]
    assert turn.deliberation == "standing_cognition" and summary["deliberation"]["mode"] == "standing_cognition"
    # The tick ran, was recorded by the runtime itself, and both declared moves came back as candidates.
    cycles = [r.payload["cycle"] for r in ledger.by_type(runtime.CYCLE_RECORD)]
    assert len(cycles) == 1 and cycles[0]["trigger_id"] == f"t1:goal:{goal_id[7:23]}"
    assert cycles[0]["status"] == "proposed" and cycles[0]["selected_candidate_id"] is not None
    bound = [r.payload for r in ledger.by_type(loop.CANDIDATE_RECORD)]
    assert {b["intervention_id"] for b in bound} == {"compile-brief", "contact-engineers"}
    assert sum(1 for b in bound if b["selected"]) == 1
    # Model calls were metered on the caller's governor through the per-goal carve-out (goal budget 4 calls).
    assert resources.used_model_calls > 0 and resources.used_model_calls <= 4
    usage = summary["deliberation"]["resource_usage"]
    assert usage["model_calls"] == resources.used_model_calls and usage["goal_ceiling"]["max_model_calls"] == 4
    assert all(d["selected_by_deliberation"] in (True, False) for d in summary["decisions"])
    # Deliberation never executes: no gate, no executor -> nothing executed, candidates prepared.
    assert turn.executed == () and {d["decision"] for d in summary["decisions"]} == {"PREPARE_FOR_FOUNDER"}


def test_guardian_veto_turns_an_executable_move_into_prepared_work(stack):
    compiled, passports, ledger, gate, actor = stack
    loop, runtime = make_cognitive_loop(stack, guardian_veto=True)
    spec = robotics_goal(second_node=False)
    goal_id = loop.registry.authorize(spec, now=T0)
    calls = []
    turn = loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), gate=gate,
                     executor=lambda p: calls.append(p) or GOOD(p),
                     grants={"research.brief": grant_for(loop, gate, spec, brief_move())}, evidence_confidence=0.9)
    brief = next(d for d in turn.processed[0]["decisions"] if d["intervention_id"] == "compile-brief")
    assert brief["decision"] == "PREPARE_FOR_FOUNDER" and brief["selected_by_deliberation"] is False
    assert any("did not select" in r for r in brief["reasons"]) and calls == []
    assert turn.processed[0]["deliberation"]["vetoes"] >= 1


def test_a_model_proposer_candidate_is_classified_like_any_declared_move(stack):
    compiled, passports, ledger, gate, actor = stack

    def strategist(signals, context):
        if not context.get("goal_id"):
            return []
        return [CandidateProposal.build(
            proposed_by="strategist", objective="post a public teaser about the robotics window",
            action_class="social.post", requested_capability="social.publish", target="x://robotics",
            consequence_class="external_contact", payload={"text": "teaser"},
            evidence_refs=[r for s in signals for r in s.evidence_refs], confidence=0.6, estimated_cost_usd=0.0,
            expected_outcome="teaser posted", source_signal_ids=[s.signal_id for s in signals])]

    loop, runtime = make_cognitive_loop(stack, proposers={"strategist": strategist})
    spec = robotics_goal(second_node=False)
    loop.registry.authorize(spec, now=T0)
    calls = []
    turn = loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), gate=gate,
                     executor=lambda p: calls.append(p) or GOOD(p),
                     grants={"research.brief": grant_for(loop, gate, spec, brief_move())}, evidence_confidence=0.9)
    decisions = {d["intervention_id"]: d for d in turn.processed[0]["decisions"]}
    model_move = next(k for k in decisions if k.startswith("strategist:"))
    # external_contact exceeds the goal's internal_write ceiling: prepared, never executed, even though a model proposed it
    assert decisions[model_move]["decision"] == "PREPARE_FOR_FOUNDER"
    assert [p.requested_capability for p in calls] == ["research.brief"] or calls == []
    # the candidate round-trips through the seam without authority
    candidate = strategist((hardware_signal(),), {"goal_id": "x"})[0]
    move = candidate_to_intervention(candidate)
    assert move.tactic == "proposer:strategist" and move.consequence_class == "external_contact"
    back = intervention_to_candidate("sha256:" + "0" * 64, brief_move(), [hardware_signal().signal_id])
    assert back.execution_authority == "none" and candidate_to_intervention(back).route_hash == brief_move().route_hash


def test_goal_resource_budget_bounds_deliberation_and_is_visible(stack):
    compiled, passports, ledger, gate, actor = stack
    loop, runtime = make_cognitive_loop(stack)
    starved = robotics_goal(second_node=False)
    starved = variant(starved, resource_budget={"max_model_calls": 0, "max_estimated_cost_usd": 0.0})
    goal_id = loop.registry.authorize(starved, now=T0)
    resources = governor()
    turn = loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=resources, evidence_confidence=0.9)
    summary = turn.processed[0]
    assert summary["deliberation"]["cycle_status"] == "hibernating" and summary["decisions"] == []
    assert resources.used_model_calls == 0
    assert any(d["class"] == "resource" for d in summary["deficits"])
    assert any("resource budget" in b for b in loop.registry.state(goal_id).blockers)


def test_cognition_seam_contract_guards(stack):
    compiled, passports, ledger, gate, actor = stack
    other = EvidenceLedger(compiled.constitution_hash)
    with pytest.raises(ContractError):
        GoalGravityLoop(ledger=ledger, compiled=compiled, passports=passports, actor=actor.passport_id,
                        legal_principal="alfonso_lopez", cognition=cognition(other))
    bare = StandingCognitionRuntime(ledger=ledger, proposers={"x": lambda s, c: []},
                                    evaluators={"guardian": approving("guardian"), "treasury": approving("treasury")})
    with pytest.raises(ContractError):
        GoalGravityLoop(ledger=ledger, compiled=compiled, passports=passports, actor=actor.passport_id,
                        legal_principal="alfonso_lopez", cognition=bare)
    loop = make_loop(stack)
    other_gate = type("G", (), {"ledger": other, "grants": gate.grants})()
    loop.registry.authorize(robotics_goal(), now=T0)
    with pytest.raises(ContractError):
        loop.turn(trigger_id="t1", now=T1, resources=governor(), gate=other_gate, executor=GOOD)
    with pytest.raises(ContractError):
        loop.turn(trigger_id="t2", now=T1, resources=governor(), executor=GOOD)


# ---------------------------------------------------------------- evidence is real

def test_policy_evidence_refs_are_ledger_hashes_not_labels(stack):
    compiled, passports, ledger, gate, actor = stack
    loop = make_loop(stack)
    goal_id = loop.registry.authorize(robotics_goal(), now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), evidence_confidence=0.95)
    prepared = [r.payload for r in ledger.by_type(loop.PREPARED_RECORD)]
    refs = prepared[0]["evidence_refs"]
    assert loop.registry.authorization_hash(goal_id) in refs
    assert loop.world.record_hash(hardware_signal().signal_id) in refs
    assert all(ledger.find(r) is not None for r in refs) and not any(r.startswith("goal:") for r in refs)
    # confidence is the world model's relevance-weighted belief confidence capped by the caller, never inflated
    evidence = turn.processed[0]["evidence"]
    assert evidence["basis"] == "world_model_capped_by_caller" and evidence["confidence"] <= 0.9
    # with no world evidence the caller's attestation stands alone and is labelled as such
    loop.registry.wake(goal_id, reason="test", now=T2)
    bare = loop.turn(trigger_id="t2", now=T2, resources=governor(), evidence_confidence=0.9)
    assert bare.processed[0]["evidence"]["basis"] == "world_model_capped_by_caller"  # earlier experience still relevant
    fresh = make_loop(stack, ledger=EvidenceLedger(compiled.constitution_hash))
    g2 = fresh.registry.authorize(robotics_goal(), now=T0)
    fresh.registry.wake(g2, reason="test", now=T2)
    alone = fresh.turn(trigger_id="t3", now=T2, resources=governor(), evidence_confidence=0.9)
    assert alone.processed[0]["evidence"] == {"refs": 1, "confidence": 0.9, "basis": "caller_attested_only"}


def test_low_evidence_requests_evidence_and_records_a_proof_deficit(stack):
    loop = make_loop(stack)
    goal_id = loop.registry.authorize(robotics_goal(second_node=False), now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), evidence_confidence=0.1)
    decisions = {d["intervention_id"]: d["decision"] for d in turn.processed[0]["decisions"]}
    assert decisions["compile-brief"] == "REQUEST_EVIDENCE"
    assert any(d["class"] == "proof" for d in turn.processed[0]["deficits"])
    assert loop.registry.state(goal_id).status == "blocked"


# ---------------------------------------------------------------- deficits of every class, dependencies, threats, route

def test_relationship_deficit_blocks_until_the_relationship_is_observed(stack):
    loop = make_loop(stack)
    spec = simple_goal(tag="rel", node={"requires_relationships": ("distributor",)})
    goal_id = loop.registry.authorize(spec, now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, resources=governor(), evidence_confidence=0.9,
                     signals=[signal("r1", tags=["rel"], observations=[obs("g", "metric", 0)])])
    s = turn.processed[0]
    assert s["missing_relationships"] == ["distributor"] and any(d["class"] == "relationship" for d in s["deficits"])
    assert any("relationship deficit" in b for b in loop.registry.state(goal_id).blockers)
    turn2 = loop.turn(trigger_id="t2", now=T2, resources=governor(), evidence_confidence=0.9,
                      signals=[signal("r2", tags=["rel"], observations=[obs("distributor", "relationship", True)], observed_at=T2)])
    assert turn2.processed[0]["missing_relationships"] == []


def test_unmet_goal_dependency_waits_with_a_proof_deficit(stack):
    loop = make_loop(stack)
    first = simple_goal(tag="first")
    first_id = loop.registry.authorize(first, now=T0)
    second = simple_goal(tag="second", dependencies=(first_id, "sha256:" + "9" * 64))
    second_id = loop.registry.authorize(second, now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, resources=governor(), evidence_confidence=0.9,
                     signals=[signal("s1", tags=["second"], observations=[obs("g", "metric", 0)])])
    s = next(p for p in turn.processed if p["goal_id"] == second_id)
    assert all(d["decision"] == "WAIT" for d in s["decisions"])
    assert sum(1 for d in s["deficits"] if d["class"] == "proof") == 2
    assert any("not a registered goal" in b for b in loop.registry.state(second_id).blockers)
    status = loop.status(second_id, now=T1)
    assert status["next_autonomous_work"] == [] and status["waiting_work"][0]["why"] == "WAIT"


def test_threat_factors_subtract_from_the_intersection(stack):
    loop = make_loop(stack)
    factors = (
        OpportunityFactor.build(factor_id="cheap", domain="hardware", subject="actuator", attribute="cost_usd", direction="lte", threshold=500, weight=1.5, effect="cost_down"),
        OpportunityFactor.build(factor_id="talent", domain="talent", subject="engineers", attribute="available", direction="gte", threshold=5, weight=1.5, effect="feasibility_up"),
        OpportunityFactor.build(factor_id="tariff", domain="policy", subject="tariff", attribute="rate", direction="gte", threshold=0.2, weight=2.0, effect="cost_up"),
    )
    spec = variant(robotics_goal(second_node=False, wake_threshold=5.0),
                   opportunity_factors=[f.to_dict() for f in factors], wake_conditions=[], intersection_threshold=2.5)
    goal_id = loop.registry.authorize(spec, now=T0)
    opp = [signal("a", domain="hardware", observations=[obs("actuator", "cost_usd", 400)]),
           signal("b", domain="talent", observations=[obs("engineers", "available", 9)])]
    turn = loop.turn(trigger_id="t1", now=T1, signals=opp, resources=governor(), evidence_confidence=0.9)
    assert turn.woken == (goal_id,) and turn.processed[0]["intersection"]["favorable"] is True
    loop2 = make_loop(stack, ledger=EvidenceLedger(stack[0].constitution_hash))
    goal2 = loop2.registry.authorize(spec, now=T0)
    turn2 = loop2.turn(trigger_id="t1", now=T1, resources=governor(), evidence_confidence=0.9,
                       signals=opp + [signal("c", domain="policy", observations=[obs("tariff", "rate", 0.3)])])
    assert turn2.woken == () and loop2.registry.state(goal2).status == "dormant"
    report = loop2.detector.detect(spec, now=T1, record=False)
    # threat weight x observation confidence (2.0 x 0.9) is subtracted from the score
    assert report.threat_score == pytest.approx(1.8) and report.threats[0]["factor_id"] == "tariff" and report.favorable is False


def test_route_recalculation_is_visible_when_a_later_node_is_already_satisfied(stack):
    loop = make_loop(stack)
    goal_id = loop.registry.authorize(robotics_goal(wake_threshold=0.5), now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, resources=governor(), evidence_confidence=0.9,
                     signals=[signal("p", tags=["robotics"], observations=[obs("robotics", "decision_package", True)])])
    s = turn.processed[0]
    assert s["active_node_id"] == "N1" and s["route_changed"] is True
    assert loop.status(goal_id, now=T1)["route_changed"] is True


def test_change_goal_supersedes_with_lineage_and_the_old_goal_accepts_nothing_more(stack):
    loop = make_loop(stack)
    old = robotics_goal()
    old_id = loop.registry.authorize(old, now=T0)
    loop.registry.record_preference(old_id, kind="change_goal", value="narrow to inspection drones", actor="alfonso_lopez", reason="focus", now=T1)
    assert loop.registry.state(old_id).status == "paused"
    turn = loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), evidence_confidence=0.9)
    assert turn.woken == ()   # a paused goal is never woken
    with pytest.raises(GoalError):
        loop.registry.supersede(old_id, robotics_goal(second_node=False), actor="alfonso_lopez", reason="x", now=T2)
    replacement = variant(robotics_goal(second_node=False), supersedes=old_id, desired_state="an inspection-drone plan")
    new_id = loop.registry.supersede(old_id, replacement, actor="alfonso_lopez", reason="narrowed", now=T2)
    assert loop.registry.state(old_id).status == "superseded" and loop.registry.get(new_id).supersedes == old_id
    with pytest.raises(GoalError):
        loop.registry.record_preference(old_id, kind="lower_priority", value=5, actor="alfonso_lopez", reason="x", now=T2)
    with pytest.raises(GoalError):
        loop.registry.record_refusal(old_id, route_hash=brief_move().route_hash, actor="alfonso_lopez", reason="x", now=T2)
    # restart: lineage survives
    again = make_loop(stack)
    assert again.registry.state(old_id).status == "superseded" and new_id in again.registry.goals()


# ---------------------------------------------------------------- founder controls (section 20)

def test_ask_before_forget_route_and_revoke_capability_are_enforced_before_policy(stack):
    compiled, passports, ledger, gate, actor = stack
    loop = make_loop(stack)
    spec = robotics_goal(second_node=False)
    goal_id = loop.registry.authorize(spec, now=T0)
    grants = {"research.brief": grant_for(loop, gate, spec, brief_move())}
    loop.registry.record_preference(goal_id, kind="ask_before", value="internal_write", actor="alfonso_lopez", reason="check", now=T0)
    calls = []
    turn = loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), gate=gate,
                     executor=lambda p: calls.append(p) or GOOD(p), grants=grants, evidence_confidence=0.9)
    brief = next(d for d in turn.processed[0]["decisions"] if d["intervention_id"] == "compile-brief")
    assert brief["decision"] == "PREPARE_FOR_FOUNDER" and "consulted" in brief["reasons"][0] and calls == []
    loop.registry.record_preference(goal_id, kind="forget_route", value=brief_move().route_hash, actor="alfonso_lopez", reason="drop", now=T1)
    loop.registry.record_preference(goal_id, kind="revoke_capability", value="outreach.contact", actor="alfonso_lopez", reason="no", now=T1)
    loop.registry.wake(goal_id, reason="test", now=T2)
    turn2 = loop.turn(trigger_id="t2", now=T2, resources=governor(), gate=gate, executor=GOOD, grants=grants, evidence_confidence=0.9)
    decisions = {d["intervention_id"]: d for d in turn2.processed[0]["decisions"]}
    assert decisions["compile-brief"]["decision"] == "ABSTAIN" and "refused this exact route" in decisions["compile-brief"]["reasons"][0]
    assert decisions["contact-engineers"]["decision"] == "ABSTAIN" and "revoked capability" in decisions["contact-engineers"]["reasons"][0]
    assert calls == []


def test_irreversible_moves_escalate_and_a_foreign_principal_is_prepared_only(stack):
    compiled, passports, ledger, gate, actor = stack
    loop = make_loop(stack)
    wire = brief_move(intervention_id="wire-deposit", description="wire a deposit", action_class="finance.transfer",
                      requested_capability="finance.transfer", consequence_class="irreversible", target="bank:escrow",
                      expected_outcome="deposit wired", payload={"usd": 10}, reversible=False, tactic="payment")
    spec = simple_goal(tag="esc", ceiling="irreversible", move=wire)
    loop.registry.authorize(spec, now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, resources=governor(), evidence_confidence=0.95,
                     signals=[signal("e", tags=["esc"], observations=[obs("g", "metric", 0, confidence=0.97)])])
    d = turn.processed[0]["decisions"][0]
    assert d["decision"] == "ESCALATE" and turn.escalated and turn.routing["immediate"][0]["urgency"] == "high"
    foreign = variant(simple_goal(tag="foreign"), authority={**simple_goal(tag="foreign").authority, "legal_principal": "someone_else"})
    loop.registry.authorize(foreign, now=T0)
    turn2 = loop.turn(trigger_id="t2", now=T1, resources=governor(), evidence_confidence=0.9,
                      signals=[signal("f", tags=["foreign"], observations=[obs("g", "metric", 0)])])
    d2 = next(p for p in turn2.processed if p["goal_id"] == foreign.goal_id)["decisions"][0]
    assert d2["decision"] == "PREPARE_FOR_FOUNDER" and "legal principal" in d2["reasons"][0]


# ---------------------------------------------------------------- attention (section 13)

def test_quiet_hours_batch_everything_but_emergencies_and_low_value_is_suppressed(stack):
    loop = make_loop(stack, policy=AttentionPolicy(quiet_hours_utc=(22, 7), batch_value_threshold=0.3))
    goal_id = loop.registry.authorize(robotics_goal(second_node=False), now=T0)
    night = "2026-10-13T23:30:00Z"
    turn = loop.turn(trigger_id="t1", now=night, signals=[hardware_signal()], resources=governor(), evidence_confidence=0.9)
    assert turn.routing["immediate"] == [] and len(turn.routing["batched"]) == 2
    asks = [r.payload for r in loop.ledger.by_type(loop.attention.ASK_RECORD)]
    assert all(a["quiet_hours"] is True for a in asks)
    strict = make_loop(stack, ledger=EvidenceLedger(stack[0].constitution_hash),
                       policy=AttentionPolicy(immediate_value_threshold=0.99, batch_value_threshold=0.99))
    strict.registry.authorize(robotics_goal(second_node=False), now=T0)
    quiet = strict.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), evidence_confidence=0.9)
    assert quiet.routing["immediate"] == quiet.routing["batched"] == []
    assert all("below attention value threshold" in why for _, why in quiet.routing["suppressed"])


def test_outcome_unknown_on_an_external_move_is_an_emergency_information_item(stack):
    compiled, passports, ledger, gate, actor = stack
    loop = make_loop(stack)
    spec = simple_goal(tag="ext", ceiling="external_contact", move=outreach_move())
    goal_id = loop.registry.authorize(spec, now=T0)

    def boom(p):
        raise RuntimeError("carrier timeout")

    turn = loop.turn(trigger_id="t1", now=T1, resources=governor(), gate=gate, executor=boom, evidence_confidence=0.9,
                     grants={"outreach.contact": grant_for(loop, gate, spec, outreach_move())},
                     signals=[signal("x", tags=["ext"], observations=[obs("g", "metric", 0)])])
    assert turn.processed[0]["decisions"][0]["evidence_state"] == "unknown"
    loop.registry.wake(goal_id, reason="test", now=T2)
    again = loop.turn(trigger_id="t2", now=T2, resources=governor(), gate=gate, executor=GOOD, evidence_confidence=0.9,
                      grants={"outreach.contact": grant_for(loop, gate, spec, outreach_move())})
    info = [i for i in again.routing["immediate"] if i["kind"] == "information"]
    assert info and info[0]["urgency"] == "emergency" and info[0]["category"] == "reconciliation"
    assert again.processed[0]["open_attempts"] and again.processed[0]["decisions"][0]["evidence_state"] == "unknown"


def test_defer_resurfaces_after_cadence_accept_grants_nothing_and_preference_lands_first(stack):
    loop = make_loop(stack)
    spec = robotics_goal(second_node=False)
    goal_id = loop.registry.authorize(spec, now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), evidence_confidence=0.9)
    asks = {a["route_hash"]: a for a in turn.routing["immediate"] + turn.routing["batched"]}
    brief_ask = asks[brief_move().route_hash]
    outreach_ask = asks[outreach_move().route_hash]
    deferred = loop.founder_answer(brief_ask["item_id"], decision="defer", actor="alfonso_lopez", note="next week", now=T1)
    assert deferred["resurface_after"] == "2026-10-20T13:00:00Z"
    loop.registry.wake(goal_id, reason="test", now=T2)
    soon = loop.turn(trigger_id="t2", now=T2, resources=governor(), evidence_confidence=0.9)
    assert any("deferred by founder" in why for _, why in soon.routing["suppressed"])
    loop.registry.wake(goal_id, reason="test", now="2026-10-21T13:00:00Z")
    later = loop.turn(trigger_id="t3", now="2026-10-21T13:00:00Z", resources=governor(), evidence_confidence=0.9)
    assert brief_ask["item_id"] in [a["item_id"] for a in later.routing["immediate"] + later.routing["batched"]]
    accepted = loop.founder_answer(outreach_ask["item_id"], decision="accept", actor="alfonso_lopez", note="ok", now=T2)
    assert "not a grant" in accepted["effect"] and accepted["authority_note"].startswith("answer recorded")
    # an answered item does not re-route; a refusal writes the preference BEFORE the answer record
    fresh_brief = [a for a in later.routing["immediate"] + later.routing["batched"] if a["route_hash"] == brief_move().route_hash][0]
    loop.founder_answer(fresh_brief["item_id"], decision="refuse", actor="alfonso_lopez", note="no", now=T3)
    types = [r.record_type for r in loop.ledger.records]
    assert types.index(loop.registry.PREFERENCE_RECORD, types.index(loop.attention.ANSWER_RECORD)) < len(types) - 1
    assert types[-1] == loop.attention.ANSWER_RECORD and types[-2] == loop.registry.PREFERENCE_RECORD
    assert loop.registry.is_route_refused(goal_id, brief_move().route_hash)
    assert all("manufactured_urgency" not in a for a in asks.values())


# ---------------------------------------------------------------- reconciliation, verification, closure

def test_gate_cut_between_dispatch_and_receipt_is_never_redispatched_and_reconciles_from_the_ledger(stack):
    compiled, passports, ledger, gate, actor = stack
    loop = make_loop(stack)
    spec = robotics_goal(second_node=False)
    goal_id = loop.registry.authorize(spec, now=T0)

    def cut(p):
        raise RuntimeError("process killed after dispatch")

    loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), gate=gate, executor=cut,
              grants={"research.brief": grant_for(loop, gate, spec, brief_move())}, evidence_confidence=0.9)
    assert any(r.record_type == "grant_dispatch" for r in ledger.records)
    # restart with a fresh grant: the route is open, so nothing is dispatched again
    loop2 = make_loop(stack)
    calls = []
    loop2.registry.wake(goal_id, reason="test", now=T2)
    turn = loop2.turn(trigger_id="t2", now=T2, resources=governor(), gate=gate, executor=lambda p: calls.append(p) or GOOD(p),
                      grants={"research.brief": grant_for(loop2, gate, spec, brief_move())}, evidence_confidence=0.9)
    assert calls == [] and turn.processed[0]["decisions"][0]["note"] == "already attempted; no duplicate consequential action"
    # the Gate's own records say reconciliation_required: unresolved until an accountable resolution exists
    first = loop2.reconcile(goal_id, now=T2)
    assert first["resolved"] == [] and first["unresolved"] == [brief_move().route_hash]
    with pytest.raises(ContractError):
        loop2.reconcile(goal_id, now=T2, resolutions={brief_move().route_hash: {"state": "failed", "reconciled_by": "ops", "evidence_refs": [], "note": "n"}})
    second = loop2.reconcile(goal_id, now=T3, resolutions={brief_move().route_hash: {
        "state": "failed", "reconciled_by": "ops:alfonso_lopez", "evidence_refs": ["incident:2026-10-15"], "note": "carrier confirmed nothing sent"}})
    assert second["resolved"][0]["to"] == "failed" and second["unresolved"] == []
    assert not any("reconciliation" in b for b in loop2.registry.state(goal_id).blockers)
    # a failed route is released: a later turn may dispatch it again, once
    loop2.registry.wake(goal_id, reason="test", now=T3)
    turn3 = loop2.turn(trigger_id="t3", now=T3, resources=governor(), gate=gate, executor=lambda p: calls.append(p) or GOOD(p),
                       grants={"research.brief": grant_for(loop2, gate, spec, brief_move())}, evidence_confidence=0.9)
    assert len(calls) == 1 and turn3.executed[0]["evidence_state"] == "executed"
    # the re-dispatch is a distinguishable Gate record (attempt suffix), never a replay of the claimed id
    attempts = [i.payload["detail"] for i in ledger.by_type(loop.INTERVENTION_RECORD)
                if i.payload["goal_id"] == goal_id and i.payload["evidence_state"] == "attempted"]
    assert [a["attempt"] for a in attempts] == [0, 1] and attempts[1]["proposal_id"].endswith(":r1")
    assert loop2.drift_report(goal_id)["drift"] is False
    ok, msg = ledger.verify_chain()
    assert ok, msg


def test_reconcile_closes_an_attempt_the_gate_actually_recorded(stack):
    compiled, passports, ledger, gate, actor = stack
    loop = make_loop(stack)
    spec = robotics_goal(second_node=False)
    goal_id = loop.registry.authorize(spec, now=T0)
    move = brief_move()
    fix = loop.gps.fix(spec, loop.registry.state(goal_id), now=T1, record=False)
    c = loop.classifier.classify(spec, loop.registry.state(goal_id), move, fix=fix, grant=None, evidence_refs=["x"],
                                 evidence_confidence=0.9, now=T1, record=False)
    loop._record_intervention(goal_id, move, classification_id=c.classification_id, decision=c.decision,
                              evidence_state="attempted", now=T1)
    proposal = loop.classifier.proposal_for(spec, move, evidence_refs=[loop.registry.authorization_hash(goal_id)], evidence_confidence=0.9)
    grant = gate.grants.issue_single_action(proposal=proposal, policy_version="1.0.0")
    action = gate.run(proposal, executor=GOOD, standing_grant=grant)   # the effect happened; the loop never saw the result
    assert action.state == "recorded"
    result = loop.reconcile(goal_id, now=T2)
    assert result["resolved"][0]["to"] == "executed" and result["resolved"][0]["from"] == "attempted"
    assert loop.status(goal_id, now=T2)["evidence_state"][move.route_hash] == "executed"
    assert action.receipt_hash in loop.registry.state(goal_id).evidence_refs
    latest = [r.payload for r in ledger.by_type(loop.INTERVENTION_RECORD)][-1]
    assert latest["detail"]["reconciled_from"] == "gate_ledger_events" and latest["detail"]["action_id"] == action.action_id


def test_outcome_discrepancy_blocks_the_goal_and_is_surfaced(stack):
    compiled, passports, ledger, gate, actor = stack
    loop = make_loop(stack)
    spec = robotics_goal(second_node=False)
    goal_id = loop.registry.authorize(spec, now=T0)
    wrong = lambda p: {"observed_outcome": "nothing compiled", "result_class": "negative"}
    turn = loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), gate=gate, executor=wrong,
                     grants={"research.brief": grant_for(loop, gate, spec, brief_move())}, evidence_confidence=0.9)
    assert turn.executed[0]["evidence_state"] == "executed" and turn.executed[0]["result_class"] == "negative"
    assert ledger.by_type(loop.DISCREPANCY_RECORD) and loop.registry.state(goal_id).status == "blocked"
    assert any(i["category"] == "discrepancy" for i in turn.routing["immediate"] + turn.routing["batched"])
    assert loop.retention.compounding_report()["retentions"] == 0   # nothing is retained from a negative outcome


def test_retention_binds_outcomes_to_the_goal_caps_envelopes_and_survives_restart(stack):
    compiled, passports, ledger, gate, actor = stack
    genomes = GenomeRegistry(ledger)
    loop = make_loop(stack, genomes=genomes)
    a = loop.registry.authorize(robotics_goal(second_node=False), now=T0)
    b = loop.registry.authorize(simple_goal(tag="other"), now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), gate=gate, executor=GOOD,
                     grants={"research.brief": grant_for(loop, gate, loop.registry.get(a), brief_move())}, evidence_confidence=0.9)
    outcome_id = turn.executed[0]["outcome_id"]
    cap = {"name": "brief.compiler", "version": "2.0", "description": "compiles briefs",
           "interface": {"inputs": {"topic": "str"}, "outputs": {"brief": "str"}}, "contracts": ["evidence"],
           "authority": {"max_consequence_class": "external_contact", "budget_ceiling_usd": 1.0},
           "acceptance_tests": ["t"], "failure_modes": ["f"], "recovery_path": "r"}
    with pytest.raises(ValueError):   # goal b never executed this outcome
        loop.retention.retain(goal_id=b, outcome_ref=outcome_id, what_worked=["x"], assets=[], now=T2)
    with pytest.raises(ValueError):   # the envelope exceeds the goal's internal_write ceiling: authority never inflates
        loop.retention.retain(goal_id=a, outcome_ref=outcome_id, what_worked=["x"], now=T2,
                              assets=[DurableAsset.build(kind="capability", name="brief.compiler", description="d", capability=cap)])
    cap["authority"]["max_consequence_class"] = "internal_write"
    record = loop.retention.retain(goal_id=a, outcome_ref=outcome_id, what_worked=["x"], now=T2,
                                   assets=[DurableAsset.build(kind="capability", name="brief.compiler", description="d", capability=cap)])
    assert record.capabilities_registered == ("brief.compiler@2.0",)
    restarted = make_loop(stack, genomes=GenomeRegistry(ledger))
    assert restarted.genomes.get("brief.compiler", "2.0") is not None


def test_experience_content_conflict_effects_and_stale_readings(stack):
    loop = make_loop(stack)
    goal_id = loop.registry.authorize(robotics_goal(second_node=False), now=T0)
    first = hardware_signal("e1")
    loop.turn(trigger_id="t1", now=T1, signals=[first], resources=governor(), evidence_confidence=0.9)
    event = loop.world.experiences()[0]
    assert event.content_hash == first.content_hash and event.effects["memory"] is True and goal_id in event.effects["attention"]
    forged = SignalEnvelope.build(source=first.source, source_event_id="e1", observed_at=T1,
                                  payload={"observations": [obs("actuator", "cost_usd", 10)], "domain": "hardware", "tags": ["robotics"]},
                                  evidence_refs=("source:e1",), trust_level="attributed")
    with pytest.raises(IntegrityConflict):
        loop.turn(trigger_id="t2", now=T2, signals=[forged], resources=governor(), evidence_confidence=0.9)
    assert loop.ledger.by_type(loop.world.CONFLICT_RECORD)
    older = signal("e0", domain="hardware", tags=["robotics"], observations=[obs("actuator", "cost_usd", 900)], observed_at=T0)
    loop.turn(trigger_id="t3", now=T2, signals=[older], resources=governor(), evidence_confidence=0.9)
    assert loop.world.belief("actuator", "cost_usd").value == 420
    assert any(c["disposition"] == "stale_ignored" for e in loop.world.experiences() for c in e.changes)
    with pytest.raises(ContractViolation):
        validate_record({"goal_id": "not-a-hash"}, "goal-state")


def test_measures_report_the_four_way_split_and_closures_cover_every_component(stack):
    compiled, passports, ledger, gate, actor = stack
    loop = make_loop(stack)
    spec = robotics_goal(second_node=False)
    loop.registry.authorize(spec, now=T0)
    loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), gate=gate, executor=GOOD,
              grants={"research.brief": grant_for(loop, gate, spec, brief_move())}, evidence_confidence=0.9)
    m = loop.measures(now=T1)
    assert m["persistent_identity"]["chain_intact"] and m["agency"]["executed_under_grant"] == 1
    assert m["agency"]["externally_verified"] == 0 and m["intelligence"]["status"] == "not measured here"
    assert m["experiential_surface"]["is_consciousness_score"] is False
    assert m["subjective_consciousness"] == "unresolved; not measured; not claimed"
    # nothing holds a gate, executor or grant between turns; every component reports no authority
    held = {k: v for k, v in vars(loop).items() if k in ("gate", "executor", "grants", "_gate", "_executor", "_grants")}
    assert held == {}
    components = [loop, loop.registry, loop.world, loop.router, loop.gps, loop.classifier, loop.detector, loop.retention, loop.attention]
    assert all(c.execution_authority == "none" for c in components)
    for c in components:
        assert not any(hasattr(c, m_) for m_ in ("execute", "publish", "post", "transfer", "sign", "issue_grant", "approve", "apply_change"))


def test_conserving_governor_wakes_only_high_priority_goals_and_records_the_deferral(stack):
    loop = make_loop(stack)
    high = loop.registry.authorize(simple_goal(tag="hi", priority=1), now=T0)
    low = loop.registry.authorize(simple_goal(tag="lo", priority=4), now=T0)
    resources = ResourceGovernor(max_model_calls=10, max_estimated_cost_usd=1.0, conservation_threshold=0.95)
    resources.consume_call(component="elsewhere", estimated_cost_usd=0.5)   # 50% left <= 95% threshold -> CONSERVE
    turn = loop.turn(trigger_id="t1", now=T1, resources=resources, evidence_confidence=0.9,
                     signals=[signal("h", tags=["hi"], observations=[obs("g", "metric", 0)]),
                              signal("l", tags=["lo"], observations=[obs("g", "metric", 0)])])
    assert turn.status == "conserving" and turn.woken == (high,) and turn.deferred == (low,)
    assert loop.registry.state(low).status == "dormant"
    deferrals = [r.payload for r in loop.ledger.by_type(loop.DEFICIT_CLASS_RECORD) if r.payload["goal_id"] == low]
    assert deferrals and deferrals[0]["class"] == "resource"


def test_status_carries_critical_assumptions_and_the_waiting_split(stack):
    loop = make_loop(stack)
    spec = variant(robotics_goal(), assumptions=["actuator prices keep falling", "talent stays available"])
    goal_id = loop.registry.authorize(spec, now=T0)
    loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), evidence_confidence=0.9)
    status = loop.status(goal_id, now=T1)
    assert status["critical_assumptions"] == ["actuator prices keep falling", "talent stays available"]
    assert status["next_autonomous_work"] == [] and {w["why"] for w in status["waiting_work"]} == {"founder decision"}
    for key in ("deficits", "missing_relationships", "route_changed", "deliberation", "blockers", "drift"):
        assert key in status
    cheaper = loop.work_to_first_actionable(goal_id)
    assert cheaper["first_actionable_turn"] == 1 and cheaper["work_units"] >= 3
