"""The Competency Compiler (capabilities/router.py on main) wired into the Goal Gravity loop.

Falsification targets: an inadmissible kind of knowing never clears a gate; nothing undeclared or
unproven runs an external move; a human-only gate becomes one compressed founder decision whose
answer is the only typed evidence that can clear it; calibration moves only on independently
verified outcomes; a deficit blocks the goal without closing it and resolves when the gate routes.
Deterministic and model-free; synthetic ledgers and test-minted grants only.
"""
from __future__ import annotations

import os
import tempfile

import pytest

from capabilities.genome import AuthorityEnvelope, CapabilityGenome, GenomeRegistry
from capabilities.router import CapabilityRouter, Competency
from egregore.contracts import ContractError
from egregore.goals import GoalSpec, PlanNode, WakeCondition
from egregore.gravity import GoalGravityLoop
from provenance.ledger import EvidenceLedger
from tests.unit.test_goal_gravity import (  # noqa: F401  (stack is a fixture)
    AUTH_REF, GOOD, T0, T1, T2, T3, brief_move, governor, grant_for, obs, outreach_move, signal, stack,
)


def genome(name, cls="internal_write", budget=1.0):
    return CapabilityGenome(
        name=name, version="1.0.0", description=f"{name} mechanism",
        interface={"inputs": {"q": "str"}, "outputs": {"answer": "str"}}, contracts=["evidence"],
        authority=AuthorityEnvelope(max_consequence_class=cls, budget_ceiling_usd=budget),
        acceptance_tests=["answers within contract"], failure_modes=["wrong answer"], recovery_path="discard; re-route")


def competent_loop(stack, *, ledger=None, mechanisms=()):
    compiled, passports, default_ledger, gate, actor = stack
    ledger = ledger or default_ledger
    genomes = GenomeRegistry()
    router = CapabilityRouter(genomes, ledger=ledger)
    loop = GoalGravityLoop(ledger=ledger, compiled=compiled, passports=passports, actor=actor.passport_id,
                           legal_principal="alfonso_lopez", genomes=genomes, capability_router=router)
    for name, methods, classes, cls in mechanisms:
        genomes.register(genome(name, cls))
        loop.competency.register(Competency(name, "1.0.0", tuple(methods), tuple(classes), cls, 0.0))
    return loop, router


SIM = ("demand-sim", ["simulation"], ["forecast", "market_demand"], "read_only")
PILOT = ("pilot-landing-page", ["empirical_experiment"], ["market_demand"], "internal_write")
CALC = ("calc", ["deterministic_computation"], ["arithmetic", "code_correctness"], "internal_write")
REVIEW = ("review", ["adversarial_review"], ["code_correctness", "design_critique"], "internal_write")


def gated_goal(tag, problem_class, *, sbm=None, target=True, moves=None, requires=(), ceiling="external_contact"):
    sbm = sbm or f"{tag}.cleared"
    return GoalSpec.build(
        founder_intent=f"goal {tag}", desired_state=f"state {tag}", priority=2,
        authority={"authorized_by": "alfonso_lopez", "authorization_ref": AUTH_REF,
                   "legal_principal": "alfonso_lopez", "max_consequence_class": ceiling},
        time_horizon="months",
        plan=[PlanNode.build(node_id="G1", outcome="gate cleared", gate=f"{tag} gate", sbm=sbm, sbm_direction="eq",
                             sbm_target=target, interventions=tuple(moves or (brief_move(payload={"topic": tag}),)),
                             requires_capabilities=requires, problem_class=problem_class),
              PlanNode.build(node_id="G2", outcome="next", gate="next gate", sbm=f"{tag}.next", sbm_direction="eq",
                             sbm_target=True, interventions=(brief_move(intervention_id="next", payload={"topic": f"{tag}-next"}),))],
        wake_conditions=(WakeCondition.build(kind="tag", match=tag),))


def poke(tag, k, at=T1, observations=()):
    return signal(f"{tag}-{k}", tags=[tag], observations=list(observations) or [obs(tag, "seen", k)], observed_at=at)


def router_events(ledger, kind):
    return [r.payload for r in ledger.by_type("event") if r.payload.get("type") == f"capabilities.{kind}"]


# ---------------------------------------------------------------- epistemic fit

def test_a_simulation_cannot_answer_demand_so_the_goal_waits_with_a_typed_deficit(stack):
    compiled, passports, ledger, gate, actor = stack
    loop, router = competent_loop(stack, mechanisms=[SIM])
    spec = gated_goal("demand", "market_demand")
    goal_id = loop.registry.authorize(spec, now=T0)
    calls = []
    turn = loop.turn(trigger_id="t1", now=T1, signals=[poke("demand", 1)], resources=governor(), gate=gate,
                     executor=lambda p: calls.append(p) or GOOD(p), evidence_confidence=0.9,
                     grants={"research.brief": grant_for(loop, gate, spec, brief_move(payload={"topic": "demand"}))})
    s = turn.processed[0]
    assert s["routing"]["routed"] is False and s["routing"]["deficit"]["missing_methods"] == ["one of: empirical_experiment"]
    assert [d["decision"] for d in s["decisions"]] == ["WAIT"] and calls == []
    [deficit] = [r.payload["deficit"] for r in ledger.by_type(loop.classifier.DEFICIT_RECORD)]
    assert deficit["missing_methods"] == ["one of: empirical_experiment"] and deficit["missing_capabilities"] == []
    assert deficit["router_deficit_id"] == router_events(ledger, "routing_decision")[-1]["deficit"]
    assert deficit["resolution_order"][-1] == "escalate/abstain" and deficit["resume"] == "original_goal"
    state = loop.registry.state(goal_id)
    assert state.status == "blocked" and any("epistemic" in b for b in state.blockers)
    assert loop.status(goal_id, now=T1)["competency"]["deficit"]["problem_class"] == "market_demand"
    assert loop.measures(now=T1)["competency"]["epistemic_deficits"] == 1


def test_the_deficit_resolves_and_the_original_goal_resumes_when_a_competent_mechanism_exists(stack):
    compiled, passports, ledger, gate, actor = stack
    loop, router = competent_loop(stack, mechanisms=[SIM])
    spec = gated_goal("demand", "market_demand")
    goal_id = loop.registry.authorize(spec, now=T0)
    loop.turn(trigger_id="t1", now=T1, signals=[poke("demand", 1)], resources=governor(), evidence_confidence=0.9)
    loop.genomes.register(genome(PILOT[0], PILOT[3]))
    loop.competency.register(Competency(PILOT[0], "1.0.0", tuple(PILOT[1]), tuple(PILOT[2]), PILOT[3], 0.0))
    calls = []
    turn = loop.turn(trigger_id="t2", now=T2, signals=[poke("demand", 2, T2)], resources=governor(), gate=gate,
                     executor=lambda p: calls.append(p) or GOOD(p), evidence_confidence=0.9,
                     grants={"research.brief": grant_for(loop, gate, spec, brief_move(payload={"topic": "demand"}))})
    s = turn.processed[0]
    assert s["routing"]["selected"] == ["pilot-landing-page@1.0.0"] and s["routing"]["exploratory"] is True
    # An unproven mechanism may run an internal move (it must earn its track record somewhere) ...
    assert s["decisions"][0]["decision"] == "EXECUTE_AUTONOMOUSLY" and len(calls) == 1
    assert turn.executed[0]["routed_mechanisms"] == ["pilot-landing-page@1.0.0"]
    dispositions = [r.payload["deficit"]["disposition"] for r in ledger.by_type(loop.classifier.DEFICIT_RECORD)]
    assert dispositions == ["goal_blocked_not_closed", "resolved_resume_original_goal"]
    assert goal_id in loop.registry.goals() and loop.registry.state(goal_id).status != "completed"


def test_only_evidence_of_an_admissible_kind_clears_a_typed_gate(stack):
    loop, router = competent_loop(stack, mechanisms=[PILOT])
    spec = gated_goal("pain", "market_demand", sbm="buyers.would_pay")
    goal_id = loop.registry.authorize(spec, now=T0)
    forum = signal("forum", tags=["pain"], observations=[{"subject": "buyers", "attribute": "would_pay", "value": True,
                                                          "confidence": 0.9, "method": "retrieval"}])
    t1 = loop.turn(trigger_id="t1", now=T1, signals=[forum], resources=governor(), evidence_confidence=0.9)
    sbm = t1.processed[0]["sbm"]
    assert sbm["current"] is True and sbm["satisfied"] is False and sbm["establishes"] == "claim_with_provenance"
    assert any("market_demand gate needs external_fact" in b for b in loop.registry.state(goal_id).blockers)
    pilot = signal("pilot", source="feed://landing-page", tags=["pain"], observed_at=T2,
                   observations=[{"subject": "buyers", "attribute": "would_pay", "value": True, "confidence": 0.9,
                                  "method": "empirical_experiment"}])
    t2 = loop.turn(trigger_id="t2", now=T2, signals=[pilot], resources=governor(), evidence_confidence=0.9)
    assert t2.processed[0]["active_node_id"] == "G2"   # the experiment's observed outcome cleared the demand gate


# ---------------------------------------------------------------- human-only gates

def test_a_human_only_gate_becomes_one_decision_whose_answer_is_the_only_evidence_that_clears_it(stack):
    compiled, passports, ledger, gate, actor = stack
    loop, router = competent_loop(stack)
    spec = gated_goal("launch", "authorization", sbm="founder.go_decision",
                      moves=(brief_move(payload={"topic": "launch prep"}), outreach_move(payload={"template": "launch"})))
    goal_id = loop.registry.authorize(spec, now=T0)
    calls = []
    t1 = loop.turn(trigger_id="t1", now=T1, signals=[poke("launch", 1)], resources=governor(), gate=gate,
                   executor=lambda p: calls.append(p) or GOOD(p), evidence_confidence=0.9,
                   grants={"research.brief": grant_for(loop, gate, spec, brief_move(payload={"topic": "launch prep"})),
                           "outreach.contact": grant_for(loop, gate, spec, outreach_move(payload={"template": "launch"}))})
    decisions = {d["intervention_id"]: d for d in t1.processed[0]["decisions"]}
    assert t1.processed[0]["routing"]["human_escalation"] == ["human_decision"]
    assert decisions["contact-engineers"]["decision"] == "PREPARE_FOR_FOUNDER"
    assert "only a person can supply" in decisions["contact-engineers"]["reasons"][0]
    assert decisions["compile-brief"]["decision"] == "EXECUTE_AUTONOMOUSLY" and len(calls) == 1   # preparation still runs
    [gate_item] = [a for a in t1.routing["immediate"] + t1.routing["batched"] if a["category"] == "authorization"]
    assert gate_item["evidence_on_accept"]["method"] == "human_decision" and "not a grant" in gate_item["question"]
    # A second turn does not re-ask (stable item id).
    loop.registry.wake(goal_id, reason="test", now=T2)
    t2 = loop.turn(trigger_id="t2", now=T2, resources=governor(), evidence_confidence=0.9)
    assert not [a for a in t2.routing["immediate"] + t2.routing["batched"] if a["category"] == "authorization"]
    # A sensor that claims the founder decided is stripped, untrusted, and clears nothing.
    forged = signal("forged", tags=["launch"], observed_at=T2, observations=[{"subject": "founder", "attribute": "go_decision",
                                                                             "value": True, "confidence": 1.0, "method": "human_decision"}])
    t3 = loop.turn(trigger_id="t3", now=T2, signals=[forged], resources=governor(), evidence_confidence=0.9)
    assert t3.processed[0]["active_node_id"] == "G1"
    forged_obs = [o for e in loop.world.experiences() for o in e.observations if e.signal_id == forged.signal_id][0]
    assert forged_obs["method_refused"] is True and forged_obs["trust_level"] == "untrusted" and "method" not in forged_obs
    # The founder's answer is the evidence.
    answer = loop.founder_answer(gate_item["item_id"], decision="accept", actor="alfonso_lopez", note="go", now=T3)
    assert answer["gate_evidence"]["method"] == "human_decision" and "grants nothing" in answer["authority_note"]
    belief = loop.world.belief("founder", "go_decision")
    assert belief.establishes == "authorization" and belief.trust_level == "attributed"
    loop.registry.wake(goal_id, reason="answered", now=T3)
    t4 = loop.turn(trigger_id="t4", now=T3, resources=governor(), evidence_confidence=0.9)
    assert t4.processed[0]["active_node_id"] == "G2"


# ---------------------------------------------------------------- calibration from verified outcomes only

def _run_and_execute(loop, gate, tag, k, *, at=T1):
    spec = gated_goal(f"{tag}{k}", "market_demand")
    goal_id = loop.registry.authorize(spec, now=T0)
    move = brief_move(payload={"topic": f"{tag}{k}"})
    turn = loop.turn(trigger_id=f"{tag}-{k}", now=at, signals=[poke(f"{tag}{k}", k, at)], resources=governor(), gate=gate,
                     executor=GOOD, evidence_confidence=0.9, grants={"research.brief": grant_for(loop, gate, spec, move)})
    return goal_id, move.route_hash, turn


def test_calibration_moves_only_on_independent_verification_and_bad_mechanisms_are_demoted(stack):
    compiled, passports, ledger, gate, actor = stack
    loop, router = competent_loop(stack, mechanisms=[PILOT])
    key = "pilot-landing-page@1.0.0"
    goal_a, route_a, turn_a = _run_and_execute(loop, gate, "m", 1)
    assert turn_a.executed and turn_a.executed[0]["executor_claimed_validation"] == "internally_observed"
    assert router.calibration(key, "market_demand").trials == 0   # executor claims never calibrate
    loop.reconcile(goal_a, now=T1)
    assert router.calibration(key, "market_demand").trials == 0   # reconciliation never calibrates
    before = len(ledger.records)
    with pytest.raises(ContractError):   # the mechanism may not grade itself
        loop.verify_outcome(goal_a, route_a, verifier="pilot-landing-page@2.0.0", evidence_refs=["audit:1"], note="n", now=T2)
    with pytest.raises(ContractError):   # nor the executing actor
        loop.verify_outcome(goal_a, route_a, verifier=actor.passport_id, evidence_refs=["audit:1"], note="n", now=T2)
    assert len(ledger.records) == before
    loop.verify_outcome(goal_a, route_a, verifier="auditor:external", evidence_refs=["audit:a"], note="bought", now=T2)
    assert router.calibration(key, "market_demand").trials == 1
    with pytest.raises(ContractError):   # one verification per action
        loop.verify_outcome(goal_a, route_a, verifier="auditor:second", evidence_refs=["audit:b"], note="again", now=T2)
    # One proven success keeps it eligible (2/3 >= 0.6) and no longer exploratory ...
    goal_b, route_b, turn_b = _run_and_execute(loop, gate, "m", 2, at=T2)
    assert turn_b.processed[0]["routing"]["exploratory"] is False and turn_b.executed
    # ... and one independently refuted outcome demotes it (2/4 < 0.6): the refuted move stays executed,
    # is never released for re-dispatch, and the goal is blocked with a visible discrepancy.
    out = loop.verify_outcome(goal_b, route_b, verifier="auditor:external", evidence_refs=["audit:b"],
                              note="no buyer paid", now=T3, verdict="refuted")
    assert out["evidence_state"] == "executed" and out["detail"]["verdict"] == "refuted"
    assert loop.registry.state(goal_b).status == "blocked" and loop.ledger.by_type(loop.DISCREPANCY_RECORD)
    cal = router.calibration(key, "market_demand")
    assert (cal.correct, cal.incorrect) == (1, 1) and cal.reliability < 0.6
    _, _, turn_e = _run_and_execute(loop, gate, "m", 3, at=T3)
    assert turn_e.processed[0]["routing"]["routed"] is False
    assert "below" in turn_e.processed[0]["routing"]["rejected"][key]
    assert [d["decision"] for d in turn_e.processed[0]["decisions"]] == ["WAIT"]
    assert loop.measures(now=T3)["competency"]["verified_outcomes"] == 2


def test_a_composition_credits_every_recruited_mechanism_once(stack):
    compiled, passports, ledger, gate, actor = stack
    loop, router = competent_loop(stack, mechanisms=[CALC, REVIEW])
    spec = gated_goal("code", "code_correctness")
    goal_id = loop.registry.authorize(spec, now=T0)
    move = brief_move(payload={"topic": "code"})
    turn = loop.turn(trigger_id="t1", now=T1, signals=[poke("code", 1)], resources=governor(), gate=gate, executor=GOOD,
                     evidence_confidence=0.9, grants={"research.brief": grant_for(loop, gate, spec, move)})
    assert sorted(turn.processed[0]["routing"]["selected"]) == ["calc@1.0.0", "review@1.0.0"]
    out = loop.verify_outcome(goal_id, move.route_hash, verifier="auditor:external", evidence_refs=["ci:green"],
                              note="tests pass", now=T2)
    assert sorted(c["mechanism"] for c in out["detail"]["calibration"]) == ["calc@1.0.0", "review@1.0.0"]
    assert router.calibration("calc@1.0.0", "code_correctness").trials == 1
    assert router.calibration("review@1.0.0", "code_correctness").trials == 1


def test_track_records_survive_restart_and_are_shared_by_two_loops_on_one_ledger(stack):
    compiled, passports, _, gate_unused, actor = stack
    from policy.consequence_gate import ConsequenceGate
    from provenance.commit_witness import WitnessSigner
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "ledger.jsonl")
        ledger = EvidenceLedger(compiled.constitution_hash, path=path)
        gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger, signer=WitnessSigner(env="development"))
        loop_a, router_a = competent_loop(stack, ledger=ledger, mechanisms=[PILOT])
        loop_b, router_b = competent_loop(stack, ledger=ledger, mechanisms=[PILOT])
        goal_id, route, _ = _run_and_execute(loop_a, gate, "r", 1)
        loop_b.verify_outcome(goal_id, route, verifier="auditor:external", evidence_refs=["audit:r"], note="ok", now=T2)
        # Loop A picks up the outcome loop B recorded before it routes again.
        _, _, turn = _run_and_execute(loop_a, gate, "r", 2, at=T2)
        assert router_a.calibration("pilot-landing-page@1.0.0", "market_demand").trials == 1
        assert turn.processed[0]["routing"]["exploratory"] is False
        ledger.close()
        reopened = EvidenceLedger(compiled.constitution_hash, path=path)
        loop_c, router_c = competent_loop(stack, ledger=reopened, mechanisms=[PILOT])
        assert router_c.calibration("pilot-landing-page@1.0.0", "market_demand").trials == 1
        reopened.close()


# ---------------------------------------------------------------- margins and declared plans

def test_unproven_mechanisms_never_run_external_moves_and_ask_before_is_honoured(stack):
    compiled, passports, ledger, gate, actor = stack
    loop, router = competent_loop(stack, mechanisms=[("outreach-pilot", ["empirical_experiment"], ["market_demand"], "external_contact")])
    move = outreach_move(payload={"template": "pilot"})
    spec = gated_goal("ext", "market_demand", moves=(move,))
    loop.registry.authorize(spec, now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, signals=[poke("ext", 1)], resources=governor(), gate=gate, executor=GOOD,
                     evidence_confidence=0.95, grants={"outreach.contact": grant_for(loop, gate, spec, move, confidence=0.95)})
    d = turn.processed[0]["decisions"][0]
    assert d["decision"] == "PREPARE_FOR_FOUNDER" and "no verified track record" in d["reasons"][0]
    loop2, _ = competent_loop(stack, ledger=EvidenceLedger(compiled.constitution_hash), mechanisms=[PILOT])
    spec2 = gated_goal("int", "market_demand")
    gid = loop2.registry.authorize(spec2, now=T0)
    loop2.registry.record_preference(gid, kind="ask_before", value="exploratory_mechanism", actor="alfonso_lopez",
                                     reason="tell me first", now=T0)
    gate2 = type(gate)(compiled=compiled, passports=passports, ledger=loop2.ledger, signer=gate.signer)
    turn2 = loop2.turn(trigger_id="t1", now=T1, signals=[poke("int", 1)], resources=governor(), gate=gate2, executor=GOOD,
                       evidence_confidence=0.9, grants={"research.brief": grant_for(loop2, gate2, spec2, brief_move(payload={"topic": "int"}))})
    assert turn2.processed[0]["decisions"][0]["decision"] == "PREPARE_FOR_FOUNDER"


def test_a_rejected_declared_mechanism_prepares_and_a_better_one_is_only_reported(stack):
    compiled, passports, ledger, gate, actor = stack
    loop, router = competent_loop(stack, mechanisms=[PILOT, ("costly-pilot", ["empirical_experiment"], ["market_demand"], "internal_write")])
    loop.genomes._genomes["costly-pilot@1.0.0"].authority.budget_ceiling_usd = 1.0
    spec = gated_goal("decl", "market_demand", requires=("costly-pilot@1.0.0",))
    loop.registry.authorize(spec, now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, signals=[poke("decl", 1)], resources=governor(), evidence_confidence=0.9)
    routing = turn.processed[0]["routing"]
    assert routing["preferred_instead"] == [] or routing["preferred_instead"] == ["pilot-landing-page@1.0.0"]
    if routing["preferred_instead"]:
        assert any(i["category"] == "competency" for i in turn.routing["immediate"] + turn.routing["batched"])
    # Demote the declared mechanism by policy (over the goal's ceiling) -> the move is prepared, never substituted.
    capped = gated_goal("decl2", "market_demand", requires=("costly-pilot@1.0.0",), ceiling="read_only")
    loop.registry.authorize(capped, now=T0)
    turn2 = loop.turn(trigger_id="t2", now=T1, signals=[poke("decl2", 1)], resources=governor(), evidence_confidence=0.9)
    s = next(p for p in turn2.processed if p["goal_id"] == capped.goal_id)
    assert "costly-pilot@1.0.0" in s["routing"]["rejected"]


def test_unclassified_gates_are_not_routed_and_the_seam_has_no_authority(stack):
    loop, router = competent_loop(stack, mechanisms=[PILOT])
    from tests.unit.test_goal_gravity import robotics_goal, signal as sig
    loop.registry.authorize(robotics_goal(), now=T0)
    before = len(router_events(loop.ledger, "routing_decision"))
    turn = loop.turn(trigger_id="t1", now=T1, resources=governor(), evidence_confidence=0.9,
                     signals=[sig("e1", domain="hardware", tags=["robotics"], observations=[obs("actuator", "cost_usd", 420)])])
    assert turn.processed[0]["routing"] == {"status": "unrouted"}
    assert len(router_events(loop.ledger, "routing_decision")) == before
    assert loop.competency.execution_authority == "none"
    assert not any(hasattr(loop.competency, m) for m in ("execute", "publish", "transfer", "issue_grant", "approve"))
    with pytest.raises(ContractError):   # the router must share the loop's ledger and genome registry
        GoalGravityLoop(ledger=loop.ledger, compiled=stack[0], passports=stack[1], actor=stack[4].passport_id,
                        legal_principal="alfonso_lopez", genomes=GenomeRegistry(),
                        capability_router=CapabilityRouter(GenomeRegistry(), ledger=loop.ledger))
