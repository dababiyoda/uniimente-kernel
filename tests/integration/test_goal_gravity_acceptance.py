"""Section-33 acceptance demonstration for the Goal Gravity directive.

    Alfonso defines a persistent goal -> goal survives interruption -> GREG keeps
    observing authorized reality -> irrelevant signals are filtered -> a material
    signal changes goal state -> GREG identifies the current gate -> GREG performs
    useful work without another prompt -> GREG meets something outside its
    authority -> prepares rather than violates -> surfaces a compressed founder
    decision -> the result enters evidence -> GPS updates -> a reusable
    asset/capability is retained -> the next iteration is measurably easier.

Evidence tier of this file: INTEGRATION-TESTED on a synthetic ledger with a
test passport and development witness key. It is not founder-accepted, not
externally verified, and not proof of a real business outcome.
"""
from __future__ import annotations

import os
import tempfile

from capabilities.genome import GenomeRegistry
from compiler.ucl_compiler import compile_constitution
from egregore.contracts import SignalEnvelope
from egregore.goals import GoalSpec, InterventionSpec, OpportunityFactor, PlanNode, WakeCondition
from egregore.gravity import GoalGravityLoop
from egregore.resources import ResourceGovernor
from egregore.retention import DurableAsset
from identity.machine_passport import PassportRegistry
from policy.consequence_gate import ConsequenceGate
from provenance.commit_witness import WitnessSigner
from provenance.ledger import EvidenceLedger

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AUTH_REF = "sha256:" + "e" * 64


def _signal(event_id, observed_at, *, source, domain, tags=(), observations=()):
    payload = {"domain": domain, "tags": list(tags), "observations": list(observations)}
    return SignalEnvelope.build(source=source, source_event_id=event_id, observed_at=observed_at, payload=payload,
                                evidence_refs=(f"source:{event_id}",), trust_level="attributed")


def _goal(*, intent, state, sbm, tag, requires=(), missing=()):
    brief = InterventionSpec.build(
        intervention_id="compile-brief", description=f"compile a due-diligence brief for {tag}",
        action_class="research.compile", requested_capability="research.brief", consequence_class="internal_write",
        target="sandbox:briefs", expected_outcome="brief compiled", payload={"topic": tag}, tactic="research")
    outreach = InterventionSpec.build(
        intervention_id="contact-buyers", description="contact buyers who reported pain",
        action_class="outreach.message", requested_capability="outreach.contact", consequence_class="external_contact",
        target="mailto:buyers", expected_outcome="conversations requested", payload={"template": tag}, tactic="cold_outreach")
    return GoalSpec.build(
        founder_intent=intent, desired_state=state, priority=1,
        authority={"authorized_by": "alfonso_lopez", "authorization_ref": AUTH_REF, "legal_principal": "alfonso_lopez",
                   "max_consequence_class": "internal_write"},
        time_horizon="years",
        plan=[PlanNode.build(node_id="N1", outcome="opportunity window verified", gate="favorable convergence observed",
                             sbm=f"{tag}.opportunity_score", sbm_direction="gte", sbm_target=0.7,
                             exit_evidence=("brief compiled", "convergence score >= 0.7"),
                             interventions=(brief, outreach), requires_capabilities=requires),
              PlanNode.build(node_id="N2", outcome="founder decision package delivered", gate="founder decision",
                             sbm=f"{tag}.decision_package", sbm_direction="eq", sbm_target=True,
                             interventions=(InterventionSpec.build(
                                 intervention_id="assemble-package", description="assemble the decision package",
                                 action_class="package.assemble", requested_capability="package.assemble",
                                 consequence_class="internal_write", target="sandbox:packages",
                                 expected_outcome="package assembled", payload={"kind": tag}),))],
        relevant_entities=("actuator", "vision_model", "engineers", "buyer", tag), domains=("hardware", "software", "talent", "market"),
        wake_conditions=(WakeCondition.build(kind="tag", match=tag, weight=1.0),),
        opportunity_factors=(
            OpportunityFactor.build(factor_id="cheap-actuator", domain="hardware", subject="actuator", attribute="cost_usd", direction="lte", threshold=500, weight=1.0, effect="cost_down"),
            OpportunityFactor.build(factor_id="open-vision", domain="software", subject="vision_model", attribute="open_source_quality", direction="gte", threshold=0.8, weight=1.0, effect="feasibility_up"),
            OpportunityFactor.build(factor_id="talent", domain="talent", subject="engineers", attribute="available", direction="gte", threshold=5, weight=1.0, effect="feasibility_up"),
            OpportunityFactor.build(factor_id="buyer-pain", domain="market", subject="buyer", attribute="pain_reported", direction="eq", threshold=True, weight=1.0, effect="upside_up")),
        review_cadence_seconds=30 * 86400, intersection_threshold=2.5, missing_capabilities=missing)


def test_section_33_acceptance_chain():
    compiled = compile_constitution(ROOT)
    passports = PassportRegistry()
    signer = WitnessSigner(env="development")
    actor = passports.issue(kind="agent", creator="alfonso", owner_organ="uniimente-kernel", legal_principal="alfonso_lopez",
                            declared_capabilities=["research.brief", "outreach.contact", "package.assemble"],
                            budget_ceiling_usd=5.0, consequence_class="external_contact")
    executor_calls = []

    def executor(p):
        executor_calls.append(p.requested_capability)
        return {"observed_outcome": p.expected_outcome, "result_class": "positive", "validation_status": "internally_observed"}

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "ledger.jsonl")

        def open_body():
            ledger = EvidenceLedger(compiled.constitution_hash, path=path)
            gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger, signer=signer)
            genomes = GenomeRegistry()
            loop = GoalGravityLoop(ledger=ledger, compiled=compiled, passports=passports, actor=actor.passport_id,
                                   legal_principal="alfonso_lopez", genomes=genomes)
            return ledger, gate, loop

        # 1. Alfonso defines a persistent goal (declared lineage, not authentication).
        ledger, gate, loop = open_body()
        robotics = _goal(intent="Build a serious robotics company when the opportunity becomes unusually favorable.",
                         state="a founder-ratified robotics plan with verified convergence evidence", sbm="robotics", tag="robotics")
        goal_id = loop.registry.authorize(robotics, now="2026-10-13T12:00:00Z")
        assert loop.registry.state(goal_id).status == "dormant"
        ledger.close()

        # 2. The goal survives interruption: a fresh body reads only durable history.
        ledger, gate, loop = open_body()
        assert loop.registry.goals() == [goal_id]

        # 3-4. GREG keeps observing; irrelevant signals are filtered; it stays dormant at zero model cost.
        noise = [_signal(f"n{i}", "2026-11-01T08:00:00Z", source="feed://weather", domain="weather",
                         observations=[{"subject": "sky", "attribute": "temp_c", "value": 10 + i, "confidence": 0.9}]) for i in range(50)]
        quiet = loop.turn(trigger_id="2026-11-01", now="2026-11-01T08:00:00Z", signals=noise,
                          resources=ResourceGovernor(max_model_calls=4, max_estimated_cost_usd=0.05))
        assert quiet.status == "silent" and quiet.woken == () and quiet.resource_snapshot["used_model_calls"] == 0

        # 5. Weak signals across domains converge; the material change wakes the goal and changes its state.
        weak = [
            _signal("w1", "2026-11-20T09:00:00Z", source="feed://hardware-prices", domain="hardware",
                    observations=[{"subject": "actuator", "attribute": "cost_usd", "value": 410, "confidence": 0.9}]),
            _signal("w2", "2026-11-21T09:00:00Z", source="feed://github-releases", domain="software",
                    observations=[{"subject": "vision_model", "attribute": "open_source_quality", "value": 0.86, "confidence": 0.85}]),
            _signal("w3", "2026-11-22T09:00:00Z", source="feed://layoff-tracker", domain="talent",
                    observations=[{"subject": "engineers", "attribute": "available", "value": 14, "confidence": 0.8}]),
        ]
        woke = loop.turn(trigger_id="2026-11-22", now="2026-11-22T10:00:00Z", signals=weak,
                         resources=ResourceGovernor(max_model_calls=4, max_estimated_cost_usd=0.05), evidence_confidence=0.9)
        assert woke.woken == (goal_id,)
        assert loop.registry.state(goal_id).wake_reason.startswith("favorable intersection")
        summary = woke.processed[0]
        # 6. GREG identifies the current gate and the single bottleneck metric.
        assert summary["active_node_id"] == "N1" and summary["active_gate"] == "favorable convergence observed"
        assert summary["sbm"]["name"] == "robotics.opportunity_score" and summary["sbm"]["satisfied"] is False
        assert summary["intersection"]["favorable"] is True
        # Without a grant, both candidate moves are prepared and one compressed founder decision per move is opened.
        assert all(d["decision"] == "PREPARE_FOR_FOUNDER" for d in summary["decisions"])
        first_asks = woke.routing["immediate"] + woke.routing["batched"]
        assert {a["kind"] for a in first_asks} == {"decision"} and all(any(o["cost"] == "none" for o in a["options"]) for a in first_asks)
        ledger.close()

        # 7. GREG performs useful work without another prompt, through the Gate under a pre-existing grant,
        # 8-9. meets a move outside its authority (external contact) and prepares instead of violating.
        ledger, gate, loop = open_body()
        brief = robotics.node("N1").interventions[0]
        proposal = loop.classifier.proposal_for(robotics, brief, evidence_refs=[f"goal:{goal_id}"], evidence_confidence=0.9)
        grant = gate.grants.issue_single_action(proposal=proposal, policy_version="1.0.0")
        work = loop.turn(trigger_id="2026-11-23", now="2026-11-23T10:00:00Z", resources=ResourceGovernor(max_model_calls=4, max_estimated_cost_usd=0.05),
                         gate=gate, executor=executor, grants={"research.brief": grant}, evidence_confidence=0.9,
                         signals=[_signal("m1", "2026-11-23T09:00:00Z", source="feed://buyer-forum", domain="market", tags=["robotics"],
                                          observations=[{"subject": "buyer", "attribute": "pain_reported", "value": True, "confidence": 0.9}])])
        decisions = {d["intervention_id"]: d for d in work.processed[0]["decisions"]}
        assert decisions["compile-brief"]["decision"] == "EXECUTE_AUTONOMOUSLY" and decisions["compile-brief"]["evidence_state"] == "executed"
        assert decisions["contact-buyers"]["decision"] == "PREPARE_FOR_FOUNDER"
        assert executor_calls == ["research.brief"]
        # 10. The compressed founder decision for the outreach move stays open; the identical re-ask is suppressed,
        # so executing the brief did not cost the founder a second interruption.
        open_asks = [a for a in loop.attention.open_asks() if a["goal_id"] == goal_id]
        assert [a["route_hash"] for a in open_asks].count(robotics.node("N1").interventions[1].route_hash) == 1
        assert work.routing["immediate"] + work.routing["batched"] == []
        assert all("duplicate" in reason for _, reason in work.routing["suppressed"])
        assert loop.registry.state(goal_id).evidence_refs == [work.executed[0]["receipt_hash"]]
        # 11. The result enters evidence: witness, receipt and outcome are on the one hash chain.
        types = {r.record_type for r in ledger.records}
        assert {"witness", "receipt", "outcome", loop.INTERVENTION_RECORD, loop.PREPARED_RECORD, loop.attention.ASK_RECORD} <= types
        ok, msg = ledger.verify_chain()
        assert ok, msg
        outcome_id = work.executed[0]["outcome_id"]
        receipt = work.executed[0]["receipt_hash"]

        # 12. GPS updates when the gate's exit evidence is observed.
        moved = loop.turn(trigger_id="2026-11-24", now="2026-11-24T10:00:00Z", resources=ResourceGovernor(max_model_calls=4, max_estimated_cost_usd=0.05),
                          evidence_confidence=0.9,
                          signals=[_signal("m2", "2026-11-24T09:00:00Z", source="feed://founder-folder", domain="market", tags=["robotics"],
                                           observations=[{"subject": "robotics", "attribute": "opportunity_score", "value": 0.82, "confidence": 0.95}])])
        assert moved.processed[0]["active_node_id"] == "N2"
        status = loop.status(goal_id, now="2026-11-24T10:00:00Z")
        assert status["active_gate"] == "founder decision" and status["evidence_state"][brief.route_hash] == "executed"

        # 13. A reusable capability is retained from the verified outcome.
        retention = loop.retention.retain(
            goal_id=goal_id, outcome_ref=outcome_id, what_worked=["brief compiled from typed observations"], now="2026-11-24T11:00:00Z",
            assets=[DurableAsset.build(kind="capability", name="brief.compiler", description="reusable due-diligence brief compiler",
                                       evidence_refs=[receipt],
                                       capability={"name": "brief.compiler", "version": "1.0", "description": "compiles briefs",
                                                   "interface": {"inputs": {"topic": "str"}, "outputs": {"brief": "str"}},
                                                   "contracts": ["evidence"],
                                                   "authority": {"max_consequence_class": "internal_write", "budget_ceiling_usd": 1.0},
                                                   "acceptance_tests": ["tests/integration/test_goal_gravity_acceptance.py"],
                                                   "failure_modes": ["empty topic"], "recovery_path": "re-run with a topic"})])
        assert retention.capabilities_registered == ("brief.compiler@1.0",)

        # 14. The next iteration is measurably easier: a comparable goal that needs that capability is not blocked.
        drones = _goal(intent="Build a drone inspection company when favorable.", state="a drone inspection plan",
                       sbm="drones", tag="drones", requires=("brief.compiler@1.0",), missing=("brief.compiler@1.0",))
        drone_id = loop.registry.authorize(drones, now="2026-11-24T11:00:00Z")
        easier = loop.turn(trigger_id="2026-11-25", now="2026-11-25T10:00:00Z", resources=ResourceGovernor(max_model_calls=4, max_estimated_cost_usd=0.05),
                           evidence_confidence=0.9,
                           signals=[_signal("d1", "2026-11-25T09:00:00Z", source="feed://buyer-forum", domain="market", tags=["drones"],
                                            observations=[{"subject": "drones", "attribute": "interest", "value": 1, "confidence": 0.5}])])
        drone_summary = next(p for p in easier.processed if p["goal_id"] == drone_id)
        assert drone_summary["missing_capabilities"] == []
        assert all(d["decision"] != "WAIT" for d in drone_summary["decisions"])
        # Measurable: the robotics goal needed two turns of gate work before its first prepared move; the drone goal
        # reaches a classified, prepared move on its first awake turn with zero capability-deficit records.
        deficits = [r for r in ledger.by_type(loop.classifier.DEFICIT_RECORD) if r.payload["goal_id"] == drone_id]
        assert deficits == []
        surface = easier.experience_surface
        assert surface["is_consciousness_score"] is False and surface["trusted_modalities"] >= 5
        ok, msg = ledger.verify_chain()
        assert ok, msg
        ledger.close()
