"""Directive section 15: a blocked goal acquires a bounded capability and resumes, without a builder.

The candidate here is a real bounded utility already in this repository (the opportunity package's
baseline arithmetic) with a real acceptance test; qualification runs that test in a subprocess.
"""
from __future__ import annotations

import pytest

from capabilities.genome import AuthorityEnvelope, CapabilityGenome
from capabilities.router import Competency
from egregore.contracts import ContractError
from tests.unit.test_goal_gravity import T0, T1, T2, T3, GOOD, brief_move, governor, grant_for, stack  # noqa: F401
from tests.unit.test_goal_gravity_competency import competent_loop, gated_goal, poke

QUANTIFY_TEST = ("tests/unit/test_goal_gravity_opportunity.py::"
                 "test_a_favorable_intersection_is_quantified_against_baselines_and_nothing_executes")


def quantify_candidate(cls="internal_write"):
    genome = CapabilityGenome(
        name="opportunity.quantify", version="1.0.0", description="baseline arithmetic for opportunity factors",
        interface={"inputs": {"baseline": "number", "observed": "number"}, "outputs": {"relative_improvement": "number"}},
        contracts=["evidence"], authority=AuthorityEnvelope(max_consequence_class=cls, budget_ceiling_usd=0.0),
        acceptance_tests=[QUANTIFY_TEST], failure_modes=["division by a zero baseline"], recovery_path="report unquantified")
    return genome, Competency("opportunity.quantify", "1.0.0", ("deterministic_computation",), ("arithmetic",), "internal_write", 0.0)


def blocked_arithmetic_goal(stack):
    loop, router = competent_loop(stack)
    spec = gated_goal("econ", "arithmetic", ceiling="internal_write")
    goal_id = loop.registry.authorize(spec, now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, signals=[poke("econ", 1)], resources=governor(), evidence_confidence=0.9)
    assert [d["decision"] for d in turn.processed[0]["decisions"]] == ["WAIT"]
    return loop, router, spec, goal_id


def test_the_plan_walks_the_ladder_from_recorded_facts_only(stack):
    loop, router, spec, goal_id = blocked_arithmetic_goal(stack)
    plan = loop.acquisition.plan(goal_id, now=T1)
    assert plan["methods_needed"] == ["deterministic_computation"]
    rungs = {r["rung"]: r["finding"] for r in plan["rungs"]}
    assert list(rungs)[0] == "existing capability" and list(rungs)[-1] == "escalate/abstain"
    assert rungs["open source"]["leads"] == []   # nothing in the catalog supplies deterministic computation
    assert "GREG qualifies, it does not build" in rungs["small bounded utility"]["status"]
    assert plan["disposition"].startswith("prepared_not_executed")
    assert loop.acquisition.plan(goal_id, now=T2)["plan_id"] == plan["plan_id"]
    assert len(loop.ledger.by_type(loop.acquisition.PLAN_RECORD)) == 1


def test_open_source_leads_are_named_as_unverified_leads(stack):
    loop, router = competent_loop(stack)
    goal_id = loop.registry.authorize(gated_goal("facts", "fact_lookup", ceiling="internal_write"), now=T0)
    loop.turn(trigger_id="t1", now=T1, signals=[poke("facts", 1)], resources=governor(), evidence_confidence=0.9)
    plan = loop.acquisition.plan(goal_id, now=T1)
    rungs = {r["rung"]: r["finding"] for r in plan["rungs"]}
    infra = {l["repo"] for l in rungs["commodity infrastructure"]["leads"]}
    oss = {l["repo"] for l in rungs["open source"]["leads"]}
    assert {"searxng/searxng", "qdrant/qdrant"} <= infra and "huggingface/sentence-transformers" in oss
    assert all(l["status"] == "lead: unverified, not installed" for l in rungs["open source"]["leads"])
    assert rungs["open source"]["observed_on"] == "2026-09-30"


def test_qualification_is_independent_bounded_and_never_attaches_by_itself(stack):
    compiled, passports, ledger, gate, actor = stack
    loop, router, spec, goal_id = blocked_arithmetic_goal(stack)
    genome, competency = quantify_candidate()
    with pytest.raises(ContractError):
        loop.acquisition.qualify(goal_id, genome=genome, competency=competency, acceptance_tests=[QUANTIFY_TEST],
                                 evaluator="opportunity.quantify@2.0.0", now=T1)
    with pytest.raises(ContractError):
        loop.acquisition.qualify(goal_id, genome=genome, competency=competency, acceptance_tests=[QUANTIFY_TEST],
                                 evaluator=actor.passport_id, now=T1)
    with pytest.raises(ContractError):
        loop.acquisition.qualify(goal_id, genome=genome, competency=competency, acceptance_tests=["../etc/passwd"],
                                 evaluator="harness:pytest", now=T1)
    with pytest.raises(ContractError):
        loop.acquisition.qualify(goal_id, genome=quantify_candidate("external_contact")[0], competency=competency,
                                 acceptance_tests=[QUANTIFY_TEST], evaluator="harness:pytest", now=T1)
    failed = loop.acquisition.qualify(goal_id, genome=genome, competency=competency, evaluator="harness:pytest", now=T1,
                                      acceptance_tests=["tests/unit/test_goal_gravity_opportunity.py::does_not_exist"])
    assert failed["passed"] is False and failed["lifecycle"] == "QUARANTINED"
    with pytest.raises(ContractError):
        loop.propose_attach(goal_id, failed, now=T1)
    with pytest.raises(ContractError):
        loop.acquisition.attach(failed["qualification_hash"], actor="alfonso_lopez", now=T1)
    passed = loop.acquisition.qualify(goal_id, genome=genome, competency=competency, acceptance_tests=[QUANTIFY_TEST],
                                      evaluator="harness:pytest", now=T1)
    assert passed["passed"] is True and passed["lifecycle"] == "TESTED" and "not an isolation boundary" in passed["isolation"]
    assert loop.genomes.get("opportunity.quantify", "1.0.0") is None   # qualification registers nothing


def test_attach_on_a_founder_decision_resumes_the_original_goal(stack):
    compiled, passports, ledger, gate, actor = stack
    loop, router, spec, goal_id = blocked_arithmetic_goal(stack)
    genome, competency = quantify_candidate()
    passed = loop.acquisition.qualify(goal_id, genome=genome, competency=competency, acceptance_tests=[QUANTIFY_TEST],
                                      evaluator="harness:pytest", now=T1)
    routing = loop.propose_attach(goal_id, passed, now=T1)
    [item] = [i for i in routing.immediate + routing.batched]
    assert item.category == "capability_attach" and "not a grant" in item.question
    assert loop.genomes.get("opportunity.quantify", "1.0.0") is None   # nothing attaches before the answer
    answer = loop.founder_answer(item.item_id, decision="accept", actor="alfonso_lopez", note="attach it", now=T2)
    assert answer["attached"]["lifecycle"] == "CANARY" and answer["attached"]["competency_registered"] is True
    assert loop.genomes.get("opportunity.quantify", "1.0.0") is not None
    with pytest.raises(ContractError):
        loop.acquisition.attach(passed["qualification_hash"], actor="alfonso_lopez", now=T2)
    move = brief_move(payload={"topic": "econ"})
    resumed = loop.turn(trigger_id="t2", now=T2, signals=[poke("econ", 2, T2)], resources=governor(), gate=gate,
                        executor=GOOD, evidence_confidence=0.9, grants={"research.brief": grant_for(loop, gate, spec, move)})
    s = resumed.processed[0]
    assert s["routing"]["selected"] == ["opportunity.quantify@1.0.0"] and s["routing"]["exploratory"] is True
    assert s["decisions"][0]["decision"] == "EXECUTE_AUTONOMOUSLY" and resumed.executed
    dispositions = [r.payload["deficit"]["disposition"] for r in ledger.by_type(loop.classifier.DEFICIT_RECORD)]
    assert dispositions[-1] == "resolved_resume_original_goal"
    assert goal_id in loop.registry.goals() and loop.registry.state(goal_id).status != "completed"
