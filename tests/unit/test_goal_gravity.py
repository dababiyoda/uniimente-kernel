"""Goal Gravity: the section-25 falsification scenarios.

Every test here is deterministic and model-free. Passing them proves the
mechanism works on this tree; it is not evidence of external effect.
"""
from __future__ import annotations

import os
import tempfile

import pytest

from capabilities.genome import GenomeRegistry
from compiler.ucl_compiler import compile_constitution
from egregore.attention import AttentionItem, AttentionPolicy
from egregore.contracts import IntegrityConflict, SignalEnvelope
from egregore.goals import (
    GoalError, GoalRegistry, GoalSpec, InterventionSpec, OpportunityFactor, PlanNode, WakeCondition,
)
from egregore.gravity import GoalGravityLoop
from egregore.resources import ResourceGovernor
from egregore.retention import DurableAsset
from identity.machine_passport import PassportRegistry
from policy.consequence_gate import ConsequenceGate
from provenance.commit_witness import WitnessSigner
from provenance.ledger import EvidenceLedger

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
T0 = "2026-10-13T12:00:00Z"
T1 = "2026-10-13T13:00:00Z"
T2 = "2026-10-14T13:00:00Z"
T3 = "2026-10-15T13:00:00Z"
AUTH_REF = "sha256:" + "f" * 64


# ---------------------------------------------------------------- fixtures

@pytest.fixture
def stack():
    compiled = compile_constitution(ROOT)
    passports = PassportRegistry()
    ledger = EvidenceLedger(compiled.constitution_hash)
    gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger, signer=WitnessSigner(env="development"))
    actor = passports.issue(kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
                            legal_principal="alfonso_lopez",
                            declared_capabilities=["research.brief", "outreach.contact", "package.assemble"],
                            budget_ceiling_usd=5.0, consequence_class="external_contact")
    return compiled, passports, ledger, gate, actor


def make_loop(stack, *, ledger=None, genomes=None, policy=None):
    compiled, passports, default_ledger, gate, actor = stack
    return GoalGravityLoop(ledger=ledger or default_ledger, compiled=compiled, passports=passports,
                           actor=actor.passport_id, legal_principal="alfonso_lopez",
                           genomes=genomes if genomes is not None else GenomeRegistry(), attention_policy=policy)


def brief_move(**kw):
    base = dict(intervention_id="compile-brief", description="compile a due-diligence brief",
                action_class="research.compile", requested_capability="research.brief",
                consequence_class="internal_write", target="sandbox:briefs",
                expected_outcome="brief compiled", payload={"topic": "robotics window"}, tactic="research")
    base.update(kw)
    return InterventionSpec.build(**base)


def outreach_move(**kw):
    base = dict(intervention_id="contact-engineers", description="contact available engineers",
                action_class="outreach.message", requested_capability="outreach.contact",
                consequence_class="external_contact", target="mailto:engineers",
                expected_outcome="introductions requested", payload={"template": "intro"}, tactic="cold_outreach")
    base.update(kw)
    return InterventionSpec.build(**base)


def robotics_goal(*, requires=(), ceiling="internal_write", second_node=True, wake_threshold=1.0):
    nodes = [PlanNode.build(
        node_id="N1", outcome="opportunity window verified", gate="favorable convergence observed",
        sbm="robotics.opportunity_score", sbm_direction="gte", sbm_target=0.7,
        exit_evidence=("brief compiled", "convergence score >= 0.7"),
        interventions=(brief_move(), outreach_move()), requires_capabilities=requires)]
    if second_node:
        nodes.append(PlanNode.build(
            node_id="N2", outcome="founder decision package delivered", gate="founder decision",
            sbm="robotics.decision_package", sbm_direction="eq", sbm_target=True,
            interventions=(InterventionSpec.build(
                intervention_id="assemble-package", description="assemble the founder decision package",
                action_class="package.assemble", requested_capability="package.assemble",
                consequence_class="internal_write", target="sandbox:packages",
                expected_outcome="package assembled", payload={"kind": "decision"}, tactic="package"),)))
    return GoalSpec.build(
        founder_intent="Build a serious robotics company when the opportunity becomes unusually favorable.",
        desired_state="a founder-ratified robotics company plan with verified convergence evidence",
        priority=2,
        authority={"authorized_by": "alfonso_lopez", "authorization_ref": AUTH_REF,
                   "legal_principal": "alfonso_lopez", "max_consequence_class": ceiling},
        time_horizon="years", plan=nodes,
        relevant_entities=("actuator", "vision_model", "engineers", "grant", "buyer", "robotics"),
        domains=("hardware", "software", "talent", "funding", "market"),
        wake_conditions=(WakeCondition.build(kind="tag", match="robotics", weight=0.5),
                         WakeCondition.build(kind="domain", match="hardware", weight=0.5),
                         WakeCondition.build(kind="metric", match="actuator.cost_usd", direction="lte", threshold=500, weight=1.0),
                         WakeCondition.build(kind="subject", match="vision_model", weight=0.5)),
        opportunity_factors=(
            OpportunityFactor.build(factor_id="cheap-actuator", domain="hardware", subject="actuator", attribute="cost_usd", direction="lte", threshold=500, weight=1.0, effect="cost_down"),
            OpportunityFactor.build(factor_id="open-vision", domain="software", subject="vision_model", attribute="open_source_quality", direction="gte", threshold=0.8, weight=1.0, effect="feasibility_up"),
            OpportunityFactor.build(factor_id="talent", domain="talent", subject="engineers", attribute="available", direction="gte", threshold=5, weight=1.0, effect="feasibility_up"),
            OpportunityFactor.build(factor_id="grant", domain="funding", subject="grant", attribute="program_open", direction="eq", threshold=True, weight=0.5, effect="cost_down"),
            OpportunityFactor.build(factor_id="buyer-pain", domain="market", subject="buyer", attribute="pain_reported", direction="eq", threshold=True, weight=1.0, effect="upside_up")),
        review_cadence_seconds=7 * 86400, wake_threshold=wake_threshold, intersection_threshold=2.5)


def signal(event_id, *, domain=None, tags=(), observations=(), source="feed://hardware-prices", observed_at=T1):
    payload = {"observations": list(observations)}
    if domain:
        payload["domain"] = domain
    if tags:
        payload["tags"] = list(tags)
    return SignalEnvelope.build(source=source, source_event_id=event_id, observed_at=observed_at, payload=payload,
                                evidence_refs=(f"source:{event_id}",), trust_level="attributed")


def obs(subject, attribute, value, confidence=0.9):
    return {"subject": subject, "attribute": attribute, "value": value, "confidence": confidence}


def governor(calls=10):
    return ResourceGovernor(max_model_calls=calls, max_estimated_cost_usd=1.0)


GOOD = lambda p: {"observed_outcome": p.expected_outcome, "result_class": "positive", "validation_status": "internally_observed"}


def grant_for(loop, gate, spec, move, *, confidence=0.9):
    proposal = loop.classifier.proposal_for(spec, move, evidence_refs=[f"goal:{spec.goal_id}"], evidence_confidence=confidence)
    return gate.grants.issue_single_action(proposal=proposal, policy_version="1.0.0")


# ---------------------------------------------------------------- scenarios

def test_persistent_goal_survival_across_restart(stack):
    compiled, *_ = stack
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "ledger.jsonl")
        ledger = EvidenceLedger(compiled.constitution_hash, path=path)
        loop = make_loop(stack, ledger=ledger)
        spec = robotics_goal()
        goal_id = loop.registry.authorize(spec, now=T0)
        loop.turn(trigger_id="t1", now=T1, signals=[signal("e1", domain="hardware", tags=["robotics"],
                                                           observations=[obs("actuator", "cost_usd", 420)])],
                  resources=governor())
        before = loop.registry.state(goal_id).to_dict()
        ledger.close()
        # Restart: a fresh process rebuilds everything from durable history alone.
        reopened = EvidenceLedger(compiled.constitution_hash, path=path)
        loop2 = make_loop(stack, ledger=reopened)
        assert loop2.registry.goals() == [goal_id]
        assert loop2.registry.get(goal_id).to_dict() == spec.to_dict()
        assert loop2.registry.state(goal_id).to_dict() == before
        assert loop2.world.belief("actuator", "cost_usd").value == 420
        ok, msg = reopened.verify_chain()
        assert ok, msg
        reopened.close()


def test_dormant_goal_wakes_from_materially_relevant_event(stack):
    loop = make_loop(stack)
    goal_id = loop.registry.authorize(robotics_goal(), now=T0)
    assert loop.registry.state(goal_id).status == "dormant"
    turn = loop.turn(trigger_id="t1", now=T1, resources=governor(),
                     signals=[signal("e1", domain="hardware", tags=["robotics"], observations=[obs("actuator", "cost_usd", 420)])])
    assert goal_id in turn.woken
    assert loop.registry.state(goal_id).wake_reason.startswith("relevant evidence")
    # After the turn the goal sleeps again; dormancy is the resting state.
    assert loop.registry.state(goal_id).status in ("dormant", "blocked")


def test_irrelevant_event_rejected_goal_remains_dormant(stack):
    loop = make_loop(stack)
    goal_id = loop.registry.authorize(robotics_goal(), now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, resources=governor(),
                     signals=[signal("e1", domain="weather", tags=["rain"], observations=[obs("sky", "cloud_cover", 0.9)])])
    assert turn.woken == ()
    assert turn.status == "silent"
    assert loop.registry.state(goal_id).status == "dormant"
    assert loop.registry.state(goal_id).wake_reason is None
    # The experience is still integrated (it may matter to a future goal); it just does not wake this one.
    assert loop.world.belief("sky", "cloud_cover").value == 0.9


def test_cross_signal_convergence_crosses_justified_threshold(stack):
    loop = make_loop(stack)
    spec = robotics_goal()
    loop.registry.authorize(spec, now=T0)
    weak = [
        signal("e1", domain="hardware", observations=[obs("actuator", "cost_usd", 420)], source="feed://hardware"),
        signal("e2", domain="software", observations=[obs("vision_model", "open_source_quality", 0.85)], source="feed://github"),
        signal("e3", domain="talent", observations=[obs("engineers", "available", 12)], source="feed://layoffs"),
    ]
    # One weak signal alone does not cross.
    loop.turn(trigger_id="t1", now=T1, signals=weak[:1], resources=governor())
    assert loop.detector.detect(spec, now=T1, record=False).favorable is False
    # Three individually weak signals across three domains do.
    turn = loop.turn(trigger_id="t2", now=T1, signals=weak[1:], resources=governor())
    report = loop.detector.detect(spec, now=T1, record=False)
    assert report.favorable and report.cross_domain and report.score >= spec.intersection_threshold
    assert set(report.domains) == {"hardware", "software", "talent"}
    recorded = [r for r in loop.ledger.by_type(loop.detector.INTERSECTION_RECORD)]
    assert len(recorded) == 1 and recorded[0].payload["disposition"] == "observed_not_acted"
    assert turn.processed[0]["intersection"]["favorable"] is True


def test_authority_boundary_prepares_but_never_executes(stack):
    compiled, passports, ledger, gate, actor = stack
    loop = make_loop(stack)
    spec = robotics_goal(ceiling="internal_write")
    goal_id = loop.registry.authorize(spec, now=T0)
    calls = []
    executor = lambda p: calls.append(p) or GOOD(p)
    # A grant exists for the brief; none exists for outreach, and outreach exceeds the goal's ceiling anyway.
    grants = {"research.brief": grant_for(loop, gate, spec, brief_move())}
    turn = loop.turn(trigger_id="t1", now=T1, resources=governor(), gate=gate, executor=executor, grants=grants,
                     evidence_confidence=0.9,
                     signals=[signal("e1", domain="hardware", tags=["robotics"], observations=[obs("actuator", "cost_usd", 420)])])
    decisions = {d["intervention_id"]: d for d in turn.processed[0]["decisions"]}
    assert decisions["compile-brief"]["decision"] == "EXECUTE_AUTONOMOUSLY"
    assert decisions["contact-engineers"]["decision"] == "PREPARE_FOR_FOUNDER"
    assert [p.requested_capability for p in calls] == ["research.brief"]
    prepared = [r.payload for r in ledger.by_type(loop.PREPARED_RECORD)]
    assert prepared and prepared[0]["intervention"]["intervention_id"] == "contact-engineers"
    assert prepared[0]["disposition"] == "prepared_not_executed"
    # The founder sees one compressed decision with a no-cost option; nothing external was contacted.
    asks = [r.payload for r in ledger.by_type(loop.attention.ASK_RECORD)]
    assert len(asks) == 1 and asks[0]["item"]["route_hash"] == outreach_move().route_hash
    assert any(o["cost"] == "none" for o in asks[0]["item"]["options"])
    assert "no external channel contacted" in asks[0]["disposition"]


def test_capability_deficit_path_keeps_original_goal_intact(stack):
    compiled, passports, ledger, gate, actor = stack
    genomes = GenomeRegistry(ledger)
    loop = make_loop(stack, genomes=genomes)
    spec = robotics_goal(requires=("brief.compiler@1.0",))
    goal_id = loop.registry.authorize(spec, now=T0)
    grants = {"research.brief": grant_for(loop, gate, spec, brief_move())}
    calls = []
    turn = loop.turn(trigger_id="t1", now=T1, resources=governor(), gate=gate, grants=grants, evidence_confidence=0.9,
                     executor=lambda p: calls.append(p) or GOOD(p),
                     signals=[signal("e1", domain="hardware", tags=["robotics"], observations=[obs("actuator", "cost_usd", 420)])])
    assert all(d["decision"] == "WAIT" for d in turn.processed[0]["decisions"])
    assert calls == []
    deficits = [r.payload for r in ledger.by_type(loop.classifier.DEFICIT_RECORD)]
    assert deficits and deficits[0]["missing_capabilities"] == ["brief.compiler@1.0"]
    assert deficits[0]["founder_intent"] == spec.founder_intent and deficits[0]["disposition"] == "goal_blocked_not_closed"
    state = loop.registry.state(goal_id)
    assert state.status == "blocked" and state.missing_capabilities == ["brief.compiler@1.0"]
    assert loop.registry.get(goal_id).to_dict() == spec.to_dict()  # the original goal is untouched


def test_goal_drift_becomes_visible(stack):
    compiled, passports, ledger, gate, actor = stack
    loop = make_loop(stack)
    spec = robotics_goal()
    goal_id = loop.registry.authorize(spec, now=T0)
    # Something committed an action in this goal's name on a route the authorized plan never declared.
    ledger.append("event", {"type": "action.committed", "action_id": "x", "proposal_id": f"egregore:goal:{goal_id[:23]}:" + "d" * 23})
    report = loop.drift_report(goal_id)
    assert report["drift"] and report["drifted_routes"] == ["d" * 23]
    turn = loop.turn(trigger_id="t1", now=T1, resources=governor(),
                     signals=[signal("e1", domain="hardware", tags=["robotics"], observations=[obs("actuator", "cost_usd", 420)])])
    assert turn.processed[0]["drift"] == ["d" * 23]
    assert ledger.by_type(loop.DRIFT_RECORD)[0].payload["disposition"] == "discrepancy_visible_not_hidden"


def test_founder_refusal_is_recorded_and_route_not_reproposed_unchanged(stack):
    compiled, passports, ledger, gate, actor = stack
    loop = make_loop(stack)
    spec = robotics_goal()
    goal_id = loop.registry.authorize(spec, now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, resources=governor(), evidence_confidence=0.9,
                     signals=[signal("e1", domain="hardware", tags=["robotics"], observations=[obs("actuator", "cost_usd", 420)])])
    ask = next(i for i in turn.routing["immediate"] + turn.routing["batched"] if i["route_hash"] == outreach_move().route_hash)
    loop.founder_answer(ask["item_id"], decision="refuse", actor="alfonso_lopez", note="not now", now=T1)
    assert loop.registry.is_route_refused(goal_id, outreach_move().route_hash)
    turn2 = loop.turn(trigger_id="t2", now=T2, resources=governor(), evidence_confidence=0.9,
                      signals=[signal("e2", domain="hardware", tags=["robotics"], observations=[obs("actuator", "cost_usd", 400)])])
    decisions = {d["intervention_id"]: d for d in turn2.processed[0]["decisions"]}
    assert decisions["contact-engineers"]["decision"] == "ABSTAIN"
    assert "refused" in decisions["contact-engineers"]["reasons"][0]
    assert all(i["route_hash"] != outreach_move().route_hash for i in turn2.routing["immediate"] + turn2.routing["batched"])
    # A materially changed route is a new proposal and is classified afresh.
    changed = outreach_move(payload={"template": "warm-intro-via-mutual-contact"})
    assert changed.route_hash != outreach_move().route_hash
    fix = loop.gps.fix(spec, loop.registry.state(goal_id), now=T2, record=False)
    verdict = loop.classifier.classify(spec, loop.registry.state(goal_id), changed, fix=fix, grant=None,
                                       evidence_refs=["x"], evidence_confidence=0.9, now=T2, record=False)
    assert verdict.decision == "PREPARE_FOR_FOUNDER"
    # "never use this tactic" removes the whole tactic family.
    loop.registry.record_preference(goal_id, kind="never_use_tactic", value="cold_outreach", actor="alfonso_lopez", reason="policy", now=T2)
    verdict = loop.classifier.classify(spec, loop.registry.state(goal_id), changed, fix=fix, grant=None,
                                       evidence_refs=["x"], evidence_confidence=0.9, now=T2, record=False)
    assert verdict.decision == "ABSTAIN"


def test_restart_continuity_without_duplicate_consequential_action(stack):
    compiled, passports, ledger, gate, actor = stack
    loop = make_loop(stack)
    spec = robotics_goal()
    goal_id = loop.registry.authorize(spec, now=T0)
    calls = []
    executor = lambda p: calls.append(p) or GOOD(p)
    grants = {"research.brief": grant_for(loop, gate, spec, brief_move())}
    sig = signal("e1", domain="hardware", tags=["robotics"], observations=[obs("actuator", "cost_usd", 420)])
    first = loop.turn(trigger_id="t1", now=T1, signals=[sig], resources=governor(), gate=gate, executor=executor,
                      grants=grants, evidence_confidence=0.9)
    assert len(calls) == 1 and first.executed and first.executed[0]["evidence_state"] == "executed"
    # Same trigger replayed: the recorded turn is returned; nothing runs again.
    again = loop.turn(trigger_id="t1", now=T1, signals=[sig], resources=governor(), gate=gate, executor=executor,
                      grants=grants, evidence_confidence=0.9)
    assert again.to_dict() == first.to_dict() and len(calls) == 1
    # A different request under the same trigger is a conflict, retained and refused.
    with pytest.raises(IntegrityConflict):
        loop.turn(trigger_id="t1", now=T2, signals=[sig], resources=governor(), gate=gate, executor=executor,
                  grants=grants, evidence_confidence=0.9)
    # Process restart: a new loop over the same history must not re-run the executed move.
    loop2 = make_loop(stack)
    grants2 = {"research.brief": grant_for(loop2, gate, spec, brief_move())}
    loop2.registry.wake(goal_id, reason="test", now=T2)
    turn3 = loop2.turn(trigger_id="t3", now=T2, resources=governor(), gate=gate, executor=executor, grants=grants2,
                       evidence_confidence=0.9)
    decision = next(d for d in turn3.processed[0]["decisions"] if d["intervention_id"] == "compile-brief")
    assert decision["note"] == "already attempted; no duplicate consequential action"
    assert len(calls) == 1
    # Interruption after durable 'attempted' and before any result: never retried blindly.
    loop3 = make_loop(stack)
    spec_b = robotics_goal(second_node=False)
    goal_b = loop3.registry.authorize(spec_b, now=T0)
    pending = brief_move()
    fix = loop3.gps.fix(spec_b, loop3.registry.state(goal_b), now=T2, record=False)
    classification = loop3.classifier.classify(spec_b, loop3.registry.state(goal_b), pending, fix=fix, grant=None,
                                               evidence_refs=["x"], evidence_confidence=0.9, now=T2, record=False)
    loop3._record_intervention(goal_b, pending, classification_id=classification.classification_id,
                               decision=classification.decision, evidence_state="attempted", now=T2)
    loop4 = make_loop(stack)
    loop4.registry.wake(goal_b, reason="test", now=T3)
    grants4 = {"research.brief": grant_for(loop4, gate, spec_b, pending)}
    turn4 = loop4.turn(trigger_id="t4", now=T3, resources=governor(), gate=gate, executor=executor, grants=grants4,
                       evidence_confidence=0.9)
    d = next(d for d in turn4.processed[0]["decisions"] if d["intervention_id"] == "compile-brief")
    assert d["evidence_state"] == "attempted" and len(calls) == 1


def test_evidence_integrity_distinguishes_every_state(stack):
    compiled, passports, ledger, gate, actor = stack
    loop = make_loop(stack)
    spec = robotics_goal(second_node=False)
    goal_id = loop.registry.authorize(spec, now=T0)
    sig = signal("e1", domain="hardware", tags=["robotics"], observations=[obs("actuator", "cost_usd", 420)])
    # planned: policy allows but no grant -> prepared, state planned
    turn = loop.turn(trigger_id="t0", now=T1, signals=[sig], resources=governor(), evidence_confidence=0.9)
    states = {i.payload["intervention"]["intervention_id"]: i.payload["evidence_state"]
              for i in ledger.by_type(loop.INTERVENTION_RECORD)}
    assert states["compile-brief"] == "planned"
    # failed: a grant bound to a different effect passes policy review but fails closed at commit time
    g = grant_for(loop, gate, spec, brief_move(payload={"topic": "a different brief"}))
    loop.registry.wake(goal_id, reason="test", now=T2)
    loop.turn(trigger_id="t1", now=T2, resources=governor(), gate=gate, executor=GOOD, grants={"research.brief": g}, evidence_confidence=0.9)
    seq = [i.payload["evidence_state"] for i in ledger.by_type(loop.INTERVENTION_RECORD) if i.payload["intervention"]["intervention_id"] == "compile-brief"]
    assert seq[-2:] == ["attempted", "failed"]
    last_brief = [i.payload for i in ledger.by_type(loop.INTERVENTION_RECORD) if i.payload["intervention"]["intervention_id"] == "compile-brief"][-1]
    assert any("mismatch" in r for r in last_brief["detail"]["reasons"])
    # a revoked grant never even reaches the Gate: the classifier prepares instead
    revoked = grant_for(loop, gate, spec, brief_move())
    gate.grants.revoke(revoked["grant_id"], reason="test", revoker="alfonso")
    fix = loop.gps.fix(spec, loop.registry.state(goal_id), now=T2, record=False)
    verdict = loop.classifier.classify(spec, loop.registry.state(goal_id), brief_move(), fix=fix, grant=revoked,
                                       evidence_refs=["x"], evidence_confidence=0.9, now=T2, record=False)
    assert verdict.decision == "PREPARE_FOR_FOUNDER" and any("revoked" in r for r in verdict.reasons)
    # unknown: an exploding executor leaves the outcome unknown; nothing is retried
    loop_b = make_loop(stack)
    spec_b = robotics_goal(second_node=False, wake_threshold=0.5)
    goal_b = loop_b.registry.authorize(spec_b, now=T0)
    def boom(p):
        raise RuntimeError("adapter exploded")
    loop_b.registry.wake(goal_b, reason="test", now=T2)
    loop_b.turn(trigger_id="t2", now=T2, resources=governor(), gate=gate, executor=boom,
                grants={"research.brief": grant_for(loop_b, gate, spec_b, brief_move())}, evidence_confidence=0.9)
    seq_b = [i.payload["evidence_state"] for i in ledger.by_type(loop.INTERVENTION_RECORD)
             if i.payload["goal_id"] == goal_b and i.payload["intervention"]["intervention_id"] == "compile-brief"]
    assert seq_b[-2:] == ["attempted", "unknown"]
    assert any("reconciliation" in b for b in loop_b.registry.state(goal_b).blockers)
    # executed: the executor's own "externally_verified" claim is retained as a claim, never as the state
    loop_c = make_loop(stack)
    spec_c = robotics_goal(second_node=False, wake_threshold=0.25)
    goal_c = loop_c.registry.authorize(spec_c, now=T0)
    loop_c.registry.wake(goal_c, reason="test", now=T2)
    self_certified = lambda p: {"observed_outcome": p.expected_outcome, "result_class": "positive", "validation_status": "externally_verified"}
    turn_c = loop_c.turn(trigger_id="t3", now=T2, resources=governor(), gate=gate, executor=self_certified,
                         grants={"research.brief": grant_for(loop_c, gate, spec_c, brief_move())}, evidence_confidence=0.9)
    assert turn_c.executed[0]["evidence_state"] == "executed"
    assert turn_c.executed[0]["executor_claimed_validation"] == "externally_verified"
    route_c = brief_move().route_hash
    # externally_verified is earned from an independent party citing evidence; the executing actor cannot self-verify
    with pytest.raises(Exception):
        loop_c.verify_outcome(goal_c, route_c, verifier=actor.passport_id, evidence_refs=["audit:1"], note="self", now=T3)
    with pytest.raises(Exception):
        loop_c.verify_outcome(goal_c, route_c, verifier="auditor:external", evidence_refs=[], note="no evidence", now=T3)
    verified = loop_c.verify_outcome(goal_c, route_c, verifier="auditor:external", evidence_refs=["audit:brief-2026-10-15"],
                                     note="brief inspected against the source observations", now=T3)
    assert verified["evidence_state"] == "externally_verified" and verified["detail"]["verifier"] == "auditor:external"
    assert loop_c.status(goal_c, now=T3)["evidence_state"][route_c] == "externally_verified"
    assert "audit:brief-2026-10-15" in loop_c.registry.state(goal_c).evidence_refs
    # a planned/failed route cannot be verified
    with pytest.raises(Exception):
        loop.verify_outcome(goal_id, route_c, verifier="auditor:external", evidence_refs=["audit:x"], note="n", now=T3)
    ok, msg = ledger.verify_chain()
    assert ok, msg


def test_compounding_makes_next_comparable_mission_cheaper(stack):
    compiled, passports, ledger, gate, actor = stack
    genomes = GenomeRegistry(ledger)
    loop = make_loop(stack, genomes=genomes)
    first = robotics_goal(second_node=False)
    later = GoalSpec.build(
        founder_intent="Build a drone inspection company when favorable.", desired_state="a drone inspection plan",
        priority=3, authority={"authorized_by": "alfonso_lopez", "authorization_ref": AUTH_REF,
                               "legal_principal": "alfonso_lopez", "max_consequence_class": "internal_write"},
        time_horizon="years",
        plan=[PlanNode.build(node_id="D1", outcome="window verified", gate="convergence", sbm="drones.opportunity_score",
                             sbm_direction="gte", sbm_target=0.7, interventions=(brief_move(payload={"topic": "drones"}),),
                             requires_capabilities=("brief.compiler@1.0",))],
        wake_conditions=(WakeCondition.build(kind="tag", match="drones"),), missing_capabilities=("brief.compiler@1.0",))
    a = loop.registry.authorize(first, now=T0)
    b = loop.registry.authorize(later, now=T0)
    # Before: the later goal is blocked by the missing capability.
    pre = loop.turn(trigger_id="t0", now=T1, resources=governor(), evidence_confidence=0.9,
                    signals=[signal("d0", tags=["drones"], observations=[obs("drones", "demand", 1)])])
    assert pre.processed[0]["decisions"][0]["decision"] == "WAIT"
    assert loop.registry.state(b).status == "blocked"
    # The first goal executes its move; the loop retains the receipt as evidence automatically.
    turn = loop.turn(trigger_id="t1", now=T1, resources=governor(), gate=gate, executor=GOOD, evidence_confidence=0.9,
                     grants={"research.brief": grant_for(loop, gate, first, brief_move())},
                     signals=[signal("e1", domain="hardware", tags=["robotics"], observations=[obs("actuator", "cost_usd", 420)])])
    outcome_id = turn.executed[0]["outcome_id"]
    # Richer retention: the brief compiler is now a reusable, bounded capability.
    record = loop.retention.retain(
        goal_id=a, outcome_ref=outcome_id, what_worked=["structured brief template"], now=T2,
        assets=[DurableAsset.build(kind="capability", name="brief.compiler", description="reusable brief compiler",
                                   evidence_refs=[turn.executed[0]["receipt_hash"]],
                                   capability={"name": "brief.compiler", "version": "1.0", "description": "compiles briefs",
                                               "interface": {"inputs": {"topic": "str"}, "outputs": {"brief": "str"}},
                                               "contracts": ["evidence"],
                                               "authority": {"max_consequence_class": "internal_write", "budget_ceiling_usd": 1.0},
                                               "acceptance_tests": ["tests/unit/test_goal_gravity.py"],
                                               "failure_modes": ["empty topic"], "recovery_path": "re-run with topic"})])
    assert record.capabilities_registered == ("brief.compiler@1.0",) and b in record.goals_made_cheaper
    assert loop.registry.state(b).missing_capabilities == []
    # After: the later goal proceeds past the gate that previously blocked it, with less work.
    post = loop.turn(trigger_id="t2", now=T2, resources=governor(), evidence_confidence=0.9,
                     signals=[signal("d1", tags=["drones"], observations=[obs("drones", "demand", 2)])])
    assert post.processed[0]["goal_id"] == b
    assert post.processed[0]["decisions"][0]["decision"] != "WAIT"
    assert loop.retention.compounding_report()["goals_made_cheaper"] == [b]
    # A retention claim without a ledgered outcome is refused.
    with pytest.raises(ValueError):
        loop.retention.retain(goal_id=a, outcome_ref="not-an-outcome", what_worked=["x"], assets=[], now=T2)


def test_attention_conservation_under_large_event_volume(stack):
    compiled, passports, ledger, gate, actor = stack
    loop = make_loop(stack, policy=AttentionPolicy(immediate_value_threshold=0.8, batch_value_threshold=0.3, max_immediate_per_turn=2))
    specs = []
    for i in range(6):
        s = GoalSpec.build(
            founder_intent=f"goal {i}", desired_state=f"state {i}", priority=1 if i < 3 else 4,
            authority={"authorized_by": "alfonso_lopez", "authorization_ref": AUTH_REF,
                       "legal_principal": "alfonso_lopez", "max_consequence_class": "internal_write"},
            time_horizon="months",
            plan=[PlanNode.build(node_id="n", outcome="o", gate="g", sbm=f"g{i}.metric", sbm_direction="gte", sbm_target=1,
                                 interventions=(outreach_move(intervention_id=f"reach-{i}", payload={"i": i}),))],
            wake_conditions=(WakeCondition.build(kind="tag", match=f"goal{i}"),))
        loop.registry.authorize(s, now=T0)
        specs.append(s)
    noise = [signal(f"noise-{k}", domain="weather", observations=[obs("sky", "temp", k)], observed_at=T1) for k in range(300)]
    relevant = [signal(f"rel-{i}", tags=[f"goal{i}"], observations=[obs(f"g{i}", "metric", 0)]) for i in range(6)]
    turn = loop.turn(trigger_id="t1", now=T1, signals=noise + relevant, resources=governor(), evidence_confidence=0.9)
    assert len(turn.signal_ids) == 306 and len(turn.woken) == 6
    assert len(turn.routing["immediate"]) <= 2
    assert len(turn.routing["immediate"]) + len(turn.routing["batched"]) + len(turn.routing["suppressed"]) == 6
    # Replaying the same asks next turn produces no new interruptions: duplicates are suppressed.
    turn2 = loop.turn(trigger_id="t2", now=T2, signals=[signal(f"rel2-{i}", tags=[f"goal{i}"], observations=[obs(f"g{i}", "metric", 0)]) for i in range(6)],
                      resources=governor(), evidence_confidence=0.9)
    assert turn2.routing["immediate"] == [] and turn2.routing["batched"] == []
    assert all("duplicate" in reason for _, reason in turn2.routing["suppressed"])
    # An ask without a no-cost option is suppressed as a manipulation guard.
    item = AttentionItem.build(goal_id=specs[0].goal_id, kind="decision", urgency="high", marginal_value=0.95, title="t",
                               question="q", options=[{"label": "pay", "cost": "100 USD"}], recommendation="r",
                               evidence_refs=(), effort_estimate="1 min", category="financial", created_at=T2)
    routing = loop.attention.route([item], now=T2)
    assert routing.immediate == () and "manipulation guard" in routing.suppressed[0][1]


def test_sensor_contradiction_is_preserved_not_collapsed(stack):
    loop = make_loop(stack)
    spec = robotics_goal(second_node=False)
    goal_id = loop.registry.authorize(spec, now=T0)
    a = signal("a1", source="feed://vendor-a", domain="hardware", tags=["robotics"], observations=[obs("robotics", "opportunity_score", 0.9, 0.6)])
    b = signal("b1", source="feed://vendor-b", domain="hardware", tags=["robotics"], observations=[obs("robotics", "opportunity_score", 0.2, 0.8)])
    turn = loop.turn(trigger_id="t1", now=T1, signals=[a, b], resources=governor(), evidence_confidence=0.9)
    belief = loop.world.belief("robotics", "opportunity_score")
    assert belief.contradicted is True
    values = {belief.value} | {alt["value"] for alt in belief.alternatives}
    assert values == {0.9, 0.2}
    contradictions = loop.world.contradictions()
    assert len(contradictions) == 1 and contradictions[0]["disposition"] == "both_retained_not_collapsed"
    # A contradicted bottleneck metric blocks the gate instead of silently passing it.
    fix = loop.gps.fix(spec, loop.registry.state(goal_id), now=T1, record=False)
    assert fix.active_node_id == "N1" and any("contradicted" in b for b in fix.blockers)
    assert loop.world.experience_surface()["contradictions_retained"] == 1
    # Agreeing independent sources corroborate instead.
    c = signal("c1", source="feed://vendor-c", domain="hardware", observations=[obs("actuator", "cost_usd", 420, 0.5)])
    d = signal("d1", source="feed://vendor-d", domain="hardware", observations=[obs("actuator", "cost_usd", 420, 0.7)])
    loop.turn(trigger_id="t2", now=T2, signals=[c, d], resources=governor())
    corroborated = loop.world.belief("actuator", "cost_usd")
    assert corroborated.contradicted is False and corroborated.confidence == 0.7


def test_experience_changes_world_model_and_later_decision(stack):
    loop = make_loop(stack)
    spec = robotics_goal()
    goal_id = loop.registry.authorize(spec, now=T0)
    first = loop.turn(trigger_id="t1", now=T1, resources=governor(), evidence_confidence=0.9,
                      signals=[signal("e1", domain="hardware", tags=["robotics"], observations=[obs("actuator", "cost_usd", 420)])])
    assert first.processed[0]["active_node_id"] == "N1"
    assert {d["intervention_id"] for d in first.processed[0]["decisions"]} == {"compile-brief", "contact-engineers"}
    # An external observation satisfies N1's bottleneck metric; the next decision is a different move.
    second = loop.turn(trigger_id="t2", now=T2, resources=governor(), evidence_confidence=0.9,
                       signals=[signal("e2", domain="hardware", tags=["robotics"], source="feed://diligence",
                                       observations=[obs("robotics", "opportunity_score", 0.8)])])
    assert second.processed[0]["active_node_id"] == "N2"
    assert [d["intervention_id"] for d in second.processed[0]["decisions"]] == ["assemble-package"]
    assert loop.registry.state(goal_id).sbm["name"] == "robotics.decision_package"
    # Completion follows from observed evidence, never from a claim.
    third = loop.turn(trigger_id="t3", now=T3, resources=governor(),
                      signals=[signal("e3", domain="hardware", tags=["robotics"], source="feed://founder-folder",
                                      observations=[obs("robotics", "decision_package", True)])])
    assert third.processed[0]["complete"] is True and loop.registry.state(goal_id).status == "completed"


# ---------------------------------------------------------------- boundaries

def test_goal_authority_is_declared_lineage_not_authentication(stack):
    loop = make_loop(stack)
    with pytest.raises(GoalError):
        GoalSpec.build(founder_intent="x", desired_state="y", priority=1, time_horizon="z", plan=robotics_goal().plan,
                       authority={"authorized_by": "x", "authorization_ref": "r", "legal_principal": "UNIIMENTE",
                                  "max_consequence_class": "read_only"})
    goal_id = loop.registry.authorize(robotics_goal(), now=T0)
    record = loop.ledger.by_type(loop.registry.AUTHORIZED_RECORD)[0].payload
    assert "not founder authentication" in record["authority_note"]
    assert loop.registry.get(goal_id).to_dict()["execution_authority"] == "none"


def test_loop_exposes_no_direct_effect_or_self_authorizing_methods(stack):
    loop = make_loop(stack)
    for obj in (loop, loop.registry, loop.world, loop.gps, loop.classifier, loop.detector, loop.attention, loop.retention):
        assert obj.execution_authority == "none"
        for name in ("execute", "publish", "post", "trade", "transfer", "sign", "issue_grant", "approve", "apply_change", "grant"):
            assert not hasattr(obj, name), f"{type(obj).__name__} exposes {name}"


def test_hibernating_resources_process_no_goal(stack):
    loop = make_loop(stack)
    loop.registry.authorize(robotics_goal(), now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, resources=ResourceGovernor(max_model_calls=0, max_estimated_cost_usd=0.0),
                     signals=[signal("e1", domain="hardware", tags=["robotics"], observations=[obs("actuator", "cost_usd", 420)])])
    assert turn.status == "hibernating" and turn.woken == () and turn.processed == ()


def test_founder_control_surface(stack):
    loop = make_loop(stack)
    goal_id = loop.registry.authorize(robotics_goal(), now=T0)
    loop.registry.record_preference(goal_id, kind="do_not_monitor", value="hardware", actor="alfonso_lopez", reason="privacy", now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, resources=governor(),
                     signals=[signal("e1", domain="hardware", tags=["robotics"], observations=[obs("actuator", "cost_usd", 420)])])
    assert turn.woken == ()
    loop.registry.record_preference(goal_id, kind="lower_priority", value=4, actor="alfonso_lopez", reason="later", now=T0)
    assert loop.registry.effective_priority(goal_id) == 4
    with pytest.raises(GoalError):
        loop.registry.record_preference(goal_id, kind="lower_priority", value=1, actor="alfonso_lopez", reason="raise", now=T0)
    loop.registry.record_preference(goal_id, kind="stop_pushing", value=True, actor="alfonso_lopez", reason="pause", now=T0)
    assert loop.registry.state(goal_id).status == "paused"
    with pytest.raises(GoalError):
        loop.registry.wake(goal_id, reason="x", now=T1)
    loop.registry.record_preference(goal_id, kind="stop_pushing", value=False, actor="alfonso_lopez", reason="resume", now=T0)
    assert loop.registry.state(goal_id).status == "dormant"
    loop.registry.revoke(goal_id, actor="alfonso_lopez", reason="done", now=T1)
    with pytest.raises(GoalError):
        loop.registry.transition(goal_id, reason="x", now=T1, status="awake")


def test_review_cadence_wakes_long_dormant_goal(stack):
    loop = make_loop(stack)
    goal_id = loop.registry.authorize(robotics_goal(), now=T0)
    assert loop.registry.due_for_review(T1) == []
    assert loop.registry.due_for_review("2026-10-21T12:00:00Z") == [goal_id]
    turn = loop.turn(trigger_id="t1", now="2026-10-21T12:00:00Z", resources=governor())
    assert turn.woken == (goal_id,) and loop.registry.state(goal_id).wake_reason == "review cadence elapsed"


def test_status_compresses_section_27_fields(stack):
    loop = make_loop(stack)
    goal_id = loop.registry.authorize(robotics_goal(), now=T0)
    loop.turn(trigger_id="t1", now=T1, resources=governor(), evidence_confidence=0.9,
              signals=[signal("e1", domain="hardware", tags=["robotics"], observations=[obs("actuator", "cost_usd", 420)])])
    status = loop.status(goal_id, now=T1)
    for key in ("desired_state", "current_position", "critical_assumptions", "active_node", "active_gate",
                "single_bottleneck_metric", "relevant_environmental_signals", "available_capabilities",
                "missing_capabilities", "next_autonomous_work", "prepared_work", "founder_required_decisions",
                "evidence_state", "review_trigger"):   # the fourteen section-27 fields
        assert key in status
    assert set(status["prepared_work"]) == {"compile-brief", "contact-engineers"}
    assert len(status["founder_required_decisions"]) == 2 and status["active_node"] == "N1"
    assert status["execution_authority"] == "none"
