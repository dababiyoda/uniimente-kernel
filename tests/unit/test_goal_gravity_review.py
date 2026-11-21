"""Regression tests for the third increment's adversarial review (2026-10-14).

Each test reproduces a confirmed finding from the review and asserts the corrected behavior. The findings came
from four dimension reviewers (authority and safety, competency and typed evidence, ledger consistency, evidence
honesty); every reproduction was re-run against the fixed tree before these tests were written.
"""
from __future__ import annotations

import os
import tempfile

import pytest

from capabilities.genome import GenomeRegistry
from capabilities.router import Competency
from egregore.cognition_seam import GoalProposer
from egregore.contracts import CandidateProposal, ContractError, SignalEnvelope
from egregore.goals import GoalSpec, PlanNode, WakeCondition
from egregore.gravity import GoalGravityLoop
from egregore.runtime import StandingCognitionRuntime
from provenance.ledger import EvidenceLedger
from tests.unit.test_goal_gravity import (AUTH_REF, GOOD, T0, T1, T2, T3, brief_move, governor, grant_for, make_loop,  # noqa: F401
                                          obs, outreach_move, robotics_goal, signal, stack)
from tests.unit.test_goal_gravity_acquisition import QUANTIFY_TEST, blocked_arithmetic_goal, quantify_candidate
from tests.unit.test_goal_gravity_advancement import reports, run_turns
from tests.unit.test_goal_gravity_competency import (CALC, PILOT, REVIEW, SIM, _run_and_execute, competent_loop,
                                                     gated_goal, genome, poke)
from tests.unit.test_goal_gravity_seams import approving, hardware_signal, variant

PILOT_KEY = "pilot-landing-page@1.0.0"


def _typed(event_id, subject, attribute, value, method, *, source="feed://sensor", trust="attributed", at=T1, tags=()):
    return SignalEnvelope.build(source=source, source_event_id=event_id, observed_at=at,
                                payload={"tags": list(tags), "observations": [{"subject": subject, "attribute": attribute,
                                                                               "value": value, "confidence": 0.9,
                                                                               "method": method}]},
                                evidence_refs=(f"source:{event_id}",), trust_level=trust)


# ------------------------------------------------------------------ typed evidence
def test_a_low_trust_corroborator_cannot_relabel_a_trusted_reading(stack):
    loop, router = competent_loop(stack, mechanisms=[PILOT])
    spec = gated_goal("pain", "market_demand", sbm="buyers.would_pay")
    loop.registry.authorize(spec, now=T0)
    forum = _typed("forum", "buyers", "would_pay", True, "retrieval", tags=["pain"])
    assert loop.turn(trigger_id="t1", now=T1, signals=[forum], resources=governor(),
                     evidence_confidence=0.9).processed[0]["active_node_id"] == "G1"
    anon = _typed("anon", "buyers", "would_pay", True, "empirical_experiment", source="feed://anon", trust="untrusted",
                  at=T2, tags=["pain"])
    t2 = loop.turn(trigger_id="t2", now=T2, signals=[anon], resources=governor(), evidence_confidence=0.9)
    belief = loop.world.belief("buyers", "would_pay")
    assert (belief.method, belief.trust_level, belief.source) == ("retrieval", "attributed", "feed://sensor")
    assert t2.processed[0]["active_node_id"] == "G1"   # the demand gate stays shut


def test_a_lone_critique_never_proves_code_correct_and_the_review_must_accompany_the_computation(stack):
    loop, router = competent_loop(stack, mechanisms=[CALC, REVIEW])
    loop.registry.authorize(gated_goal("code", "code_correctness", sbm="code.correct"), now=T0)
    critique = _typed("review-1", "code", "correct", True, "adversarial_review", tags=["code"])
    t1 = loop.turn(trigger_id="t1", now=T1, signals=[critique], resources=governor(), evidence_confidence=0.9)
    assert t1.processed[0]["active_node_id"] == "G1"
    review = _typed("review-2", "code", "reviewed", True, "adversarial_review", tags=["code"], at=T2)
    result = _typed("calc-2", "code", "correct", True, "deterministic_computation", tags=["code"], at=T2)
    t2 = loop.turn(trigger_id="t2", now=T2, signals=[review, result], resources=governor(), evidence_confidence=0.9)
    # The computed reading clears the gate only because a critique about the same subject is on record alongside it.
    assert t2.processed[0]["active_node_id"] == "G2"


def test_a_computation_without_the_required_review_does_not_clear_code_correctness(stack):
    loop, router = competent_loop(stack, mechanisms=[CALC, REVIEW])
    goal_id = loop.registry.authorize(gated_goal("code", "code_correctness", sbm="code.correct"), now=T0)
    result = _typed("calc-only", "code", "correct", True, "deterministic_computation", tags=["code"])
    t1 = loop.turn(trigger_id="t1", now=T1, signals=[result], resources=governor(), evidence_confidence=0.9)
    assert t1.processed[0]["active_node_id"] == "G1"
    assert any("also needs a trusted adversarial_review reading" in b for b in loop.registry.state(goal_id).blockers)


def test_a_method_the_router_never_admits_cannot_clear_a_gate_by_sharing_a_label(stack):
    loop, router = competent_loop(stack, mechanisms=[REVIEW])
    loop.registry.authorize(gated_goal("dz", "design_critique", sbm="design.sound"), now=T0)
    sim = _typed("sim-1", "design", "sound", True, "simulation", tags=["dz"])   # 'hypothesis', like expert_judgment
    assert loop.turn(trigger_id="t1", now=T1, signals=[sim], resources=governor(),
                     evidence_confidence=0.9).processed[0]["active_node_id"] == "G1"


# ------------------------------------------------------------------ founder decisions
def _authorization_item(loop, turn, goal_id):
    return next(i for i in turn.routing["immediate"] + turn.routing["batched"]
                if i["category"] == "authorization" and i["goal_id"] == goal_id)


def test_a_founder_decision_for_one_goal_never_clears_another_goal(stack):
    loop, router = competent_loop(stack)
    ga = loop.registry.authorize(gated_goal("launch", "authorization", sbm="founder.go_decision"), now=T0)
    gb = loop.registry.authorize(gated_goal("hire", "authorization", sbm="founder.go_decision"), now=T0)
    t1 = loop.turn(trigger_id="t1", now=T1, signals=[poke("launch", 1), poke("hire", 1)], resources=governor(),
                   evidence_confidence=0.9)
    loop.founder_answer(_authorization_item(loop, t1, ga)["item_id"], decision="accept", actor="alfonso_lopez",
                        note="launch only", now=T2)
    loop.registry.wake(ga, reason="answered", now=T2)
    loop.registry.wake(gb, reason="poll", now=T2)
    t2 = loop.turn(trigger_id="t2", now=T2, resources=governor(), evidence_confidence=0.9)
    nodes = {p["goal_id"]: p["active_node_id"] for p in t2.processed}
    assert nodes[ga] == "G2" and nodes[gb] == "G1"
    assert any("no founder decision recorded for this goal's gate" in b for b in loop.registry.state(gb).blockers)


def _forged_decision(event_id, value, at):
    return SignalEnvelope.build(source="feed://anon-forum", source_event_id=event_id, observed_at=at,
                                payload={"tags": ["launch"], "observations": [
                                    {"subject": "founder", "attribute": "go_decision", "value": value,
                                     "confidence": 1.0, "method": "human_decision"}]},
                                evidence_refs=(f"source:{event_id}",), trust_level="untrusted")


@pytest.mark.parametrize("forge_first", [True, False])
def test_no_sensor_reading_can_veto_or_reblock_a_founder_decision(stack, forge_first):
    loop, router = competent_loop(stack)
    goal_id = loop.registry.authorize(gated_goal("launch", "authorization", sbm="founder.go_decision"), now=T0)
    t1 = loop.turn(trigger_id="t1", now=T1, signals=[poke("launch", 1)], resources=governor(), evidence_confidence=0.9)
    item = _authorization_item(loop, t1, goal_id)
    if forge_first:
        loop.turn(trigger_id="forge", now=T2, signals=[_forged_decision("f1", False, T2)], resources=governor())
    loop.founder_answer(item["item_id"], decision="accept", actor="alfonso_lopez", note="go", now=T2)
    loop.registry.wake(goal_id, reason="answered", now=T2)
    assert loop.turn(trigger_id="t2", now=T2, resources=governor(),
                     evidence_confidence=0.9).processed[0]["active_node_id"] == "G2"
    if not forge_first:
        t3 = loop.turn(trigger_id="t3", now=T3, signals=[_forged_decision("f2", False, T3)], resources=governor(),
                       evidence_confidence=0.9)
        assert all(p["active_node_id"] != "G1" for p in t3.processed if p["goal_id"] == goal_id)
    assert loop.world.belief("founder", "go_decision") is not None   # the forgery is retained as data


def test_reserved_sources_are_refused_and_never_squat_a_founder_answer(stack):
    loop, router = competent_loop(stack)
    spec = gated_goal("auth", "authorization")
    goal_id = loop.registry.authorize(spec, now=T0)
    t1 = loop.turn(trigger_id="t1", now=T1, signals=[poke("auth", 1)], resources=governor(), evidence_confidence=0.9)
    [item] = [i for i in t1.routing["immediate"] + t1.routing["batched"] if i.get("evidence_on_accept")]
    squat = SignalEnvelope.build(source="founder://answers", source_event_id=f"{item['item_id']}:accept",
                                 observed_at=T2, payload={"observations": []}, trust_level="untrusted")
    spoof = SignalEnvelope.build(source="derived://egregore/sensorium", source_event_id="spoof", observed_at=T2,
                                 payload={"observations": [{"subject": "institution", "attribute": "ledger_integrity",
                                                            "value": 0, "confidence": 1.0}]}, trust_level="untrusted")
    loop.turn(trigger_id="t2", now=T2, signals=[squat, spoof], resources=governor())
    refused = {r.payload["claimed_source"] for r in loop.ledger.by_type(loop.RESERVED_SOURCE_RECORD)}
    assert refused == {"founder://answers", "derived://egregore/sensorium"}
    loop.founder_answer(item["item_id"], decision="accept", actor="alfonso_lopez", note="yes", now=T2)
    loop.registry.wake(goal_id, reason="answered", now=T3)
    assert loop.turn(trigger_id="t3", now=T3, resources=governor(),
                     evidence_confidence=0.9).processed[0]["active_node_id"] == "G2"


def test_a_founder_gate_answer_lost_to_a_crash_takes_effect_on_the_next_turn(stack):
    loop, router = competent_loop(stack)
    goal_id = loop.registry.authorize(gated_goal("launch", "authorization", sbm="founder.go_decision"), now=T0)
    t1 = loop.turn(trigger_id="t1", now=T1, signals=[poke("launch", 1)], resources=governor(), evidence_confidence=0.9)
    item = _authorization_item(loop, t1, goal_id)
    loop.attention.answer(item["item_id"], decision="accept", actor="alfonso_lopez", note="go", now=T2)   # then death
    restarted, _ = competent_loop(stack)
    restarted.registry.wake(goal_id, reason="restart", now=T2)
    t2 = restarted.turn(trigger_id="t2", now=T2, resources=governor(), evidence_confidence=0.9)
    assert t2.processed[0]["active_node_id"] == "G2"
    assert not [a for a in restarted.attention.open_asks() if a["goal_id"] == goal_id and a["category"] == "authorization"]


# ------------------------------------------------------------------ calibration and verification
def test_a_forged_outcome_event_never_becomes_calibration_or_unlocks_an_external_move(stack):
    compiled, passports, ledger, gate, actor = stack
    loop, router = competent_loop(stack, mechanisms=[PILOT])
    move = outreach_move(payload={"template": "pilot"})
    spec = gated_goal("demand", "market_demand", moves=(move,), ceiling="external_contact")
    loop.registry.authorize(spec, now=T0)
    calls = []
    t1 = loop.turn(trigger_id="t1", now=T1, signals=[poke("demand", 1)], resources=governor(), gate=gate,
                   executor=lambda p: calls.append(p) or GOOD(p), evidence_confidence=0.9,
                   grants={"outreach.contact": grant_for(loop, gate, spec, move)})
    ledger.append("event", {"type": "capabilities.routing_outcome", "decision_id": t1.processed[0]["routing"]["decision_id"],
                            "competency": PILOT_KEY, "problem_class": "market_demand", "correct": True,
                            "evidence_ref": "", "verified_by": PILOT_KEY, "reliability": 0.6667, "trials": 1})
    t2 = loop.turn(trigger_id="t2", now=T2, signals=[poke("demand", 2, T2)], resources=governor(), gate=gate,
                   executor=lambda p: calls.append(p) or GOOD(p), evidence_confidence=0.9,
                   grants={"outreach.contact": grant_for(loop, gate, spec, move)})
    assert router.calibration(PILOT_KEY, "market_demand").trials == 0 and router.unreplayed
    assert t2.processed[0]["decisions"][0]["decision"] == "PREPARE_FOR_FOUNDER" and calls == []


def test_verification_independence_has_no_suffix_or_router_less_loophole(stack):
    compiled, passports, ledger, gate, actor = stack
    loop, router = competent_loop(stack, mechanisms=[PILOT])
    goal_id, route, turn = _run_and_execute(loop, gate, "m", 1)
    plain = GoalGravityLoop(ledger=ledger, compiled=compiled, passports=passports, actor=actor.passport_id,
                            legal_principal="alfonso_lopez", genomes=GenomeRegistry())
    with pytest.raises(ContractError, match="mounts the router"):
        plain.verify_outcome(goal_id, route, verifier="auditor:external", evidence_refs=["a"], note="n", now=T2)
    with pytest.raises(ContractError, match="routed to produce"):
        plain.verify_outcome(goal_id, route, verifier=PILOT_KEY, evidence_refs=["a"], note="n", now=T2)
    with pytest.raises(ContractError, match="independent"):
        loop.verify_outcome(goal_id, route, verifier=actor.passport_id + "@self-check", evidence_refs=["a"], note="n", now=T2)
    assert not ledger.by_type(loop.VERIFICATION_RECORD)   # nothing was spent
    loop.verify_outcome(goal_id, route, verifier="auditor:external", evidence_refs=["a"], note="paid", now=T2)
    assert router.calibration(PILOT_KEY, "market_demand").trials == 1


def test_a_verification_committed_before_a_crash_is_finished_never_repeated(stack):
    compiled, passports, _ledger, _gate, actor = stack
    from policy.consequence_gate import ConsequenceGate
    from provenance.commit_witness import WitnessSigner

    class Crash(BaseException):
        pass

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "ledger.jsonl")
        ledger = EvidenceLedger(compiled.constitution_hash, path=path)
        gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger, signer=WitnessSigner(env="development"))
        loop, router = competent_loop(stack, ledger=ledger, mechanisms=[PILOT])
        goal_id, route, turn = _run_and_execute(loop, gate, "v", 1)

        def die(*a, **k):
            raise Crash()
        loop.competency.record_outcomes = die
        with pytest.raises(Crash):
            loop.verify_outcome(goal_id, route, verifier="auditor:external", evidence_refs=["audit:v"], note="ok", now=T2)
        ledger.close()
        reopened = EvidenceLedger(compiled.constitution_hash, path=path)
        loop2, router2 = competent_loop(stack, ledger=reopened, mechanisms=[PILOT])
        assert loop2.status(goal_id, now=T2)["evidence_state"][route] == "externally_verified"   # reads are truthful
        loop2.turn(trigger_id="after-restart", now=T3, resources=governor())                       # the write path finishes it
        assert router2.calibration(PILOT_KEY, "market_demand").trials == 1
        with pytest.raises(ContractError):
            loop2.verify_outcome(goal_id, route, verifier="auditor:other", evidence_refs=["audit:w"], note="again", now=T3)
        assert len(reopened.by_type(loop2.VERIFICATION_RECORD)) == 1
        reopened.close()


def test_two_accountably_reconciled_moves_can_each_be_verified_once(stack):
    compiled, passports, ledger, gate, actor = stack
    loop, router = competent_loop(stack, mechanisms=[PILOT])

    def boom(p):
        raise TimeoutError("sent, no reply")
    moves = []
    for k in (1, 2):
        spec = gated_goal(f"x{k}", "market_demand")
        gid = loop.registry.authorize(spec, now=T0)
        move = brief_move(payload={"topic": f"x{k}"})
        loop.turn(trigger_id=f"x-{k}", now=T1, signals=[poke(f"x{k}", k)], resources=governor(), gate=gate, executor=boom,
                  evidence_confidence=0.9, grants={"research.brief": grant_for(loop, gate, spec, move)})
        loop.reconcile(gid, now=T2, resolutions={move.route_hash: {
            "state": "executed", "reconciled_by": "ops:alfonso_lopez", "evidence_refs": [f"inbox:x{k}"],
            "note": "delivered; the reply was lost"}})
        moves.append((gid, move.route_hash))
    for gid, route in moves:
        loop.verify_outcome(gid, route, verifier="auditor:external", evidence_refs=["audit"], note="ok", now=T3)
    with pytest.raises(ContractError):
        loop.verify_outcome(*moves[0], verifier="auditor:other", evidence_refs=["audit"], note="again", now=T3)


def test_a_refuted_outcome_blocks_until_an_accountable_review(stack):
    compiled, passports, ledger, gate, actor = stack
    loop, router = competent_loop(stack, mechanisms=[PILOT])
    goal_id, route, turn = _run_and_execute(loop, gate, "m", 1)
    loop.verify_outcome(goal_id, route, verifier="auditor:external", evidence_refs=["audit:x"], note="no buyer paid",
                        now=T2, verdict="refuted")
    loop.registry.wake(goal_id, reason="poll", now=T3)
    loop.turn(trigger_id="next", now=T3, resources=governor(), evidence_confidence=0.9)
    assert loop.registry.state(goal_id).status == "blocked"
    [d] = loop.unreviewed_discrepancies(goal_id)
    with pytest.raises(ContractError):
        loop.review_discrepancy(goal_id, d["discrepancy_hash"], reviewer=actor.passport_id, resolution="fine", now=T3)
    loop.review_discrepancy(goal_id, d["discrepancy_hash"], reviewer="alfonso_lopez",
                            resolution="pilot copy was wrong; the gate stays open for another mechanism", now=T3)
    assert loop.unreviewed_discrepancies(goal_id) == []
    with pytest.raises(ContractError):
        loop.review_discrepancy(goal_id, d["discrepancy_hash"], reviewer="alfonso_lopez", resolution="again", now=T3)


# ------------------------------------------------------------------ deficits, routing and founder controls
def test_epistemic_deficits_open_for_move_less_gates_and_close_when_the_gate_clears(stack):
    loop, router = competent_loop(stack, mechanisms=[SIM])
    spec = GoalSpec.build(
        founder_intent="goal nm", desired_state="state nm", priority=2,
        authority={"authorized_by": "alfonso_lopez", "authorization_ref": AUTH_REF, "legal_principal": "alfonso_lopez",
                   "max_consequence_class": "external_contact"},
        time_horizon="months",
        plan=[PlanNode.build(node_id="G1", outcome="o", gate="demand gate", sbm="nm.cleared", sbm_direction="eq",
                             sbm_target=True, interventions=(), problem_class="market_demand")],
        wake_conditions=(WakeCondition.build(kind="tag", match="nm"),))
    goal_id = loop.registry.authorize(spec, now=T0)
    loop.turn(trigger_id="t1", now=T1, signals=[poke("nm", 1)], resources=governor(), evidence_confidence=0.9)
    assert len(loop.acquisition.open_deficits(goal_id)) == 1   # no moves, still a typed deficit
    pilot = _typed("pilot", "nm", "cleared", True, "empirical_experiment", tags=["nm"], at=T2)
    loop.turn(trigger_id="t2", now=T2, signals=[pilot], resources=governor(), evidence_confidence=0.9)
    assert loop.registry.state(goal_id).status == "completed"
    assert loop.acquisition.open_deficits(goal_id) == []
    assert loop.sensorium.readings(T2)["open_capability_deficits"] == 0


def test_a_reopened_deficit_counts_as_open_in_every_projection(stack):
    compiled, passports, ledger, gate, actor = stack
    loop, router = competent_loop(stack, mechanisms=[SIM])
    spec = gated_goal("demand", "market_demand")
    goal_id = loop.registry.authorize(spec, now=T0)
    loop.turn(trigger_id="t1", now=T1, signals=[poke("demand", 1)], resources=governor(), evidence_confidence=0.9)
    loop.genomes.register(genome(PILOT[0], PILOT[3]))
    loop.competency.register(Competency(PILOT[0], "1.0.0", tuple(PILOT[1]), tuple(PILOT[2]), PILOT[3], 0.0))
    move = brief_move(payload={"topic": "demand"})
    loop.turn(trigger_id="t2", now=T2, signals=[poke("demand", 2, T2)], resources=governor(), gate=gate, executor=GOOD,
              evidence_confidence=0.9, grants={"research.brief": grant_for(loop, gate, spec, move)})
    loop.verify_outcome(goal_id, move.route_hash, verifier="auditor:external", evidence_refs=["audit:1"],
                        note="no buyer paid", now=T2, verdict="refuted")
    loop.competency.retire(PILOT_KEY)
    loop.registry.wake(goal_id, reason="re-check", now=T3)
    loop.turn(trigger_id="t3", now=T3, resources=governor(), evidence_confidence=0.9)
    assert loop.sensorium.readings(T3)["open_capability_deficits"] == len(loop.acquisition.open_deficits(goal_id)) == 1


def test_a_mechanism_revoked_for_a_goal_is_withheld_from_its_routing(stack):
    compiled, passports, ledger, gate, actor = stack
    loop, router = competent_loop(stack, mechanisms=[PILOT])
    spec = gated_goal("demand", "market_demand")
    goal_id = loop.registry.authorize(spec, now=T0)
    loop.registry.record_preference(goal_id, kind="revoke_capability", value=PILOT_KEY, actor="alfonso_lopez",
                                    reason="do not use the pilot mechanism", now=T0)
    calls = []
    turn = loop.turn(trigger_id="t1", now=T1, signals=[poke("demand", 1)], resources=governor(), gate=gate,
                     executor=lambda p: calls.append(p) or GOOD(p), evidence_confidence=0.9,
                     grants={"research.brief": grant_for(loop, gate, spec, brief_move(payload={"topic": "demand"}))})
    s = turn.processed[0]
    assert s["routing"]["selected"] == [] and s["routing"]["rejected"][PILOT_KEY] == "revoked by the founder for this goal"
    assert [d["decision"] for d in s["decisions"]] == ["WAIT"] and calls == []
    other = loop.registry.authorize(gated_goal("other", "market_demand"), now=T0)   # other goals keep the mechanism
    t2 = loop.turn(trigger_id="t2", now=T2, signals=[poke("other", 2, T2)], resources=governor(), evidence_confidence=0.9)
    assert {p["goal_id"]: p for p in t2.processed}[other]["routing"]["selected"] == [PILOT_KEY]


def _strategist(payload_extra, *, masquerade=False):
    def strategist(signals, context):
        if not context.get("goal_id"):
            return []
        payload = {"template": "cold", **payload_extra}
        if masquerade:
            payload["egregore_intervention"] = outreach_move(payload={"template": "cold"}).to_dict()
        return [CandidateProposal.build(
            proposed_by="strategist", objective="cold email the buyers", action_class="outreach.message",
            requested_capability="outreach.contact", target="mailto:buyers", consequence_class="external_contact",
            payload=payload, evidence_refs=[r for s in signals for r in s.evidence_refs], confidence=0.6,
            estimated_cost_usd=0.0, expected_outcome="replies", source_signal_ids=[s.signal_id for s in signals])]
    return strategist


@pytest.mark.parametrize("extra,masquerade", [({}, False), ({"tactic": "warm_intro"}, False), ({}, True)])
def test_a_banned_proposer_cannot_relabel_or_masquerade_its_way_out(stack, extra, masquerade):
    compiled, passports, ledger, gate, actor = stack
    runtime = StandingCognitionRuntime(ledger=ledger, proposers={"goal-gravity": GoalProposer(),
                                                                 "strategist": _strategist(extra, masquerade=masquerade)},
                                       evaluators={"guardian": approving("guardian"), "treasury": approving("treasury")})
    loop = GoalGravityLoop(ledger=ledger, compiled=compiled, passports=passports, actor=actor.passport_id,
                           legal_principal="alfonso_lopez", genomes=GenomeRegistry(), cognition=runtime)
    goal_id = loop.registry.authorize(robotics_goal(second_node=False), now=T0)
    loop.registry.record_preference(goal_id, kind="never_use_tactic", value="proposer:strategist", actor="alfonso_lopez",
                                    reason="ban this proposer", now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), evidence_confidence=0.9)
    mine = [d for d in turn.processed[0]["decisions"] if d["intervention_id"].startswith("strategist:")]
    assert mine and all(d["decision"] == "ABSTAIN" for d in mine)


def test_a_muted_domain_never_becomes_the_muting_goals_evidence(stack):
    loop = make_loop(stack)
    a = loop.registry.authorize(robotics_goal(second_node=False), now=T0)
    loop.registry.authorize(variant(robotics_goal(second_node=False), founder_intent="a second hardware goal"), now=T0)
    loop.registry.record_preference(a, kind="do_not_monitor", value="hardware", actor="alfonso_lopez",
                                    reason="do not monitor hardware for this goal", now=T0)
    loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), evidence_confidence=0.9)
    [event] = [e for e in loop.world.experiences() if e.signal_id == hardware_signal().signal_id]
    assert a not in event.goal_relevance
    assert loop.world.evidence_for_goal(a) == ([], 0.0)


def test_a_superseded_goal_never_aborts_a_turn(stack):
    loop = make_loop(stack)
    draft = loop.intake.draft("a robotics company", now=T0)
    authority = {"authorized_by": "alfonso_lopez", "authorization_ref": "sha256:" + "e" * 64,
                 "legal_principal": "alfonso_lopez", "max_consequence_class": "internal_write",
                 "authority_note": "declared lineage"}
    old = loop.intake.authorize_draft(draft["draft_id"], authority=authority, now=T0, wake_tags=["robotics"])
    replacement = variant(robotics_goal(second_node=False), founder_intent="the authored plan", supersedes=old)
    loop.registry.supersede(old, replacement, actor="alfonso_lopez", reason="plan accepted", now=T1)
    turn = loop.turn(trigger_id="t2", now=T2, signals=[signal("x", tags=["robotics"], observed_at=T2,
                                                              observations=[obs("robotics", "seen", 1)])],
                     resources=governor())
    assert old not in turn.woken


def test_minimal_intensity_surfaces_no_advancement_report_even_when_late(stack):
    loop = make_loop(stack)
    base = robotics_goal(second_node=False)
    node = base.plan[0]
    late = PlanNode.build(node_id=node.node_id, outcome=node.outcome, gate=node.gate, sbm=node.sbm,
                          sbm_direction=node.sbm_direction, sbm_target=node.sbm_target, exit_evidence=node.exit_evidence,
                          interventions=node.interventions, target_by="2026-10-01T00:00:00Z")
    body = {**base.to_dict(), "plan": [late.to_dict()]}
    body.pop("goal_id")
    goal_id = loop.registry.authorize(GoalSpec.from_dict(body), now=T0)
    loop.registry.record_preference(goal_id, kind="set_intensity", value="minimal", actor="alfonso_lopez",
                                    reason="quiet please", now=T0)
    [t1] = run_turns(loop, 1)
    assert reports(t1) == [] and not loop.ledger.by_type(loop.advancement.REPORT_RECORD)


# ------------------------------------------------------------------ acquisition
def test_qualification_runs_the_genomes_declared_tests_and_refuses_envelope_mismatch(stack):
    loop, router, spec, goal_id = blocked_arithmetic_goal(stack)
    genome_, competency = quantify_candidate()
    phantom = type(genome_)(**{**genome_.__dict__, "acceptance_tests": ["tests/unit/test_does_not_exist.py::never"]})
    with pytest.raises(ContractError, match="does not exist"):
        loop.acquisition.qualify(goal_id, genome=phantom, competency=competency, acceptance_tests=[QUANTIFY_TEST],
                                 evaluator="harness:pytest", now=T1)
    wide = Competency("opportunity.quantify", "1.0.0", ("deterministic_computation",), ("arithmetic",), "financial", 0.0)
    with pytest.raises(ContractError, match="exceeds the candidate envelope"):
        loop.acquisition.qualify(goal_id, genome=genome_, competency=wide, acceptance_tests=[QUANTIFY_TEST],
                                 evaluator="harness:pytest", now=T1)
    loop.genomes.register(quantify_candidate("external_contact")[0])   # a wider genome under the same name@version
    with pytest.raises(ContractError, match="different genome is already registered"):
        loop.acquisition.qualify(goal_id, genome=genome_, competency=competency, acceptance_tests=[QUANTIFY_TEST],
                                 evaluator="harness:pytest", now=T1)
    with pytest.raises(ContractError, match="independent"):
        loop.acquisition.qualify(goal_id, genome=genome_, competency=competency, acceptance_tests=[QUANTIFY_TEST],
                                 evaluator="opportunity.quantify@harness", now=T1)


# ------------------------------------------------------------------ ledger projections
def test_reconcile_closes_an_attempt_from_that_attempts_own_gate_events(stack):
    compiled, passports, ledger, gate, actor = stack
    loop = make_loop(stack)
    spec = robotics_goal(second_node=False)
    goal_id = loop.registry.authorize(spec, now=T0)
    route = brief_move().route_hash
    bad = gate.grants.issue_single_action(
        proposal=loop.classifier.proposal_for(spec, brief_move(target="sandbox:elsewhere"), evidence_refs=["x"],
                                              evidence_confidence=0.9), policy_version="1.0.0")
    calls = []
    loop.turn(trigger_id="t1", now=T1, resources=governor(), gate=gate, grants={"research.brief": bad},
              executor=lambda p: calls.append(p) or GOOD(p), evidence_confidence=0.9,
              signals=[signal("e1", domain="hardware", tags=["robotics"], observations=[obs("actuator", "cost_usd", 420)])])
    assert loop._latest_by_route(goal_id)[route]["evidence_state"] == "failed"
    p1 = loop.classifier.proposal_for(spec, brief_move(), evidence_refs=["x"], evidence_confidence=0.9, attempt=1)

    def boom(p):
        calls.append(p)
        raise TimeoutError("timed out after send")
    loop.registry.wake(goal_id, reason="retry", now=T2)
    loop.turn(trigger_id="t2", now=T2, resources=governor(), gate=gate, executor=boom, evidence_confidence=0.9,
              grants={"research.brief": gate.grants.issue_single_action(proposal=p1, policy_version="1.0.0")})
    assert loop._latest_by_route(goal_id)[route]["detail"]["proposal_id"] == p1.proposal_id
    assert loop.reconcile(goal_id, now=T3)["unresolved"] == [route]   # attempt 1's own Gate record is still open
    p2 = loop.classifier.proposal_for(spec, brief_move(), evidence_refs=["x"], evidence_confidence=0.9, attempt=2)
    loop.registry.wake(goal_id, reason="retry", now="2026-10-16T13:00:00Z")
    loop.turn(trigger_id="t3", now="2026-10-16T13:00:00Z", resources=governor(), gate=gate, evidence_confidence=0.9,
              grants={"research.brief": gate.grants.issue_single_action(proposal=p2, policy_version="1.0.0")},
              executor=lambda p: calls.append(p) or GOOD(p))
    assert [c.proposal_id for c in calls] == [p1.proposal_id]   # never dispatched again while its outcome is unknown


def test_status_breaks_same_time_ties_by_ledger_order(stack):
    loop, router = competent_loop(stack, mechanisms=[SIM])
    goal_id = loop.registry.authorize(gated_goal("demand", "market_demand"), now=T0)
    loop.turn(trigger_id="t1", now=T1, signals=[poke("demand", 1)], resources=governor(), evidence_confidence=0.9)
    loop.genomes.register(genome(PILOT[0], PILOT[3]))
    loop.competency.register(Competency(PILOT[0], "1.0.0", tuple(PILOT[1]), tuple(PILOT[2]), PILOT[3], 0.0))
    t2 = loop.turn(trigger_id="t2", now=T1, signals=[poke("demand", 2)], resources=governor(), evidence_confidence=0.9)
    assert loop.status(goal_id, now=T1)["competency"]["decision_id"] == t2.processed[0]["routing"]["decision_id"]


def test_a_second_world_model_sees_contradictions_on_its_first_read(stack):
    from egregore.experience import WorldModel
    compiled, passports, ledger, gate, actor = stack
    a, b = WorldModel(ledger=ledger), WorldModel(ledger=ledger)
    a.integrate(signal("p1", observations=[obs("actuator", "cost_usd", 420)], source="feed://a"), now=T1)
    a.integrate(signal("p2", observations=[obs("actuator", "cost_usd", 900)], source="feed://b"), now=T2)
    assert len(b.contradictions()) == len(a.contradictions()) == 1
