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


def _qualified_and_asked(stack):
    loop, router, spec, goal_id = blocked_arithmetic_goal(stack)
    genome, competency = quantify_candidate()
    passed = loop.acquisition.qualify(goal_id, genome=genome, competency=competency, acceptance_tests=[QUANTIFY_TEST],
                                      evaluator="harness:pytest", now=T1)
    routing = loop.propose_attach(goal_id, passed, now=T1)
    [item] = [i for i in routing.immediate + routing.batched]
    return loop, spec, goal_id, passed, item


def test_attach_is_refused_without_the_founders_accepted_answer(stack):
    loop, spec, goal_id, passed, item = _qualified_and_asked(stack)
    with pytest.raises(ContractError):   # no answer at all: a direct call cannot attach
        loop.acquisition.attach(passed["qualification_hash"], actor="alfonso_lopez", now=T2)
    loop.founder_answer(item.item_id, decision="refuse", actor="alfonso_lopez", note="not now", now=T2)
    with pytest.raises(ContractError):   # a refusal is not an acceptance
        loop.acquisition.attach(passed["qualification_hash"], actor="alfonso_lopez", now=T2)
    assert loop.genomes.get("opportunity.quantify", "1.0.0") is None
    assert not loop.ledger.by_type(loop.acquisition.ATTACH_RECORD)


def test_an_attached_capability_survives_restart_and_is_shared_until_detached(stack):
    compiled, passports, ledger, gate, actor = stack
    loop, spec, goal_id, passed, item = _qualified_and_asked(stack)
    other, _ = competent_loop(stack)   # a second loop already running on the same ledger
    loop.founder_answer(item.item_id, decision="accept", actor="alfonso_lopez", note="attach it", now=T2)
    restarted, _ = competent_loop(stack)   # a new process: fresh genome registry and router
    for i, view in enumerate((restarted, other)):
        turn = view.turn(trigger_id=f"t-view-{i}", now=T2, signals=[poke("econ", 10 + i, T2)], resources=governor(),
                         evidence_confidence=0.9)
        assert turn.processed[0]["routing"]["selected"] == ["opportunity.quantify@1.0.0"]
    attaches = len(ledger.by_type(restarted.acquisition.ATTACH_RECORD))
    assert attaches == 1   # replay wrote nothing
    with pytest.raises(ContractError):
        restarted.acquisition.detach(passed["qualification_hash"], actor="alfonso_lopez", reason="", now=T3)
    detached = restarted.acquisition.detach(passed["qualification_hash"], actor="alfonso_lopez",
                                            reason="canary showed no value", now=T3)
    assert detached["lifecycle"] == "HISTORICAL"
    with pytest.raises(ContractError):
        restarted.acquisition.detach(passed["qualification_hash"], actor="alfonso_lopez", reason="again", now=T3)
    again, _ = competent_loop(stack)   # replay after a detach never brings it back
    for i, view in enumerate((again, loop)):
        turn = view.turn(trigger_id=f"t-after-{i}", now=T3, signals=[poke("econ", 20 + i, T3)], resources=governor(),
                         evidence_confidence=0.9)
        assert turn.processed[0]["routing"].get("selected", []) == []
        assert [d["decision"] for d in turn.processed[0]["decisions"]] == ["WAIT"]
    assert len(ledger.by_type(again.acquisition.ATTACH_RECORD)) == 1   # the attachment stays as history


def test_detach_never_removes_a_genome_registered_by_someone_else(stack):
    loop, spec, goal_id, passed, item = _qualified_and_asked(stack)
    genome, _ = quantify_candidate()
    loop.genomes.register(genome)   # an operator registered the genome independently
    loop.founder_answer(item.item_id, decision="accept", actor="alfonso_lopez", note="attach it", now=T2)
    attached = loop.ledger.by_type(loop.acquisition.ATTACH_RECORD)[-1].payload
    assert attached["genome_registered"] is False and attached["competency_registered"] is True
    loop.acquisition.detach(passed["qualification_hash"], actor="alfonso_lopez", reason="retire", now=T3)
    assert loop.genomes.get("opportunity.quantify", "1.0.0") is not None


def test_an_acceptance_whose_attach_was_lost_to_a_crash_completes_on_the_next_turn(stack):
    loop, spec, goal_id, passed, item = _qualified_and_asked(stack)
    # The answer lands, then the process dies before the attach record: simulated by answering at the
    # attention layer only, which is the first of the two writes founder_answer makes.
    loop.attention.answer(item.item_id, decision="accept", actor="alfonso_lopez", note="attach it", now=T2)
    assert not loop.ledger.by_type(loop.acquisition.ATTACH_RECORD)
    restarted, _ = competent_loop(stack)
    turn = restarted.turn(trigger_id="t-recover", now=T2, signals=[poke("econ", 30, T2)], resources=governor(),
                          evidence_confidence=0.9)
    [attach] = [r.payload for r in restarted.ledger.by_type(restarted.acquisition.ATTACH_RECORD)]
    assert attach["attached_by"] == "alfonso_lopez" and attach["answer_hash"]
    assert turn.processed[0]["routing"]["selected"] == ["opportunity.quantify@1.0.0"]
    assert not [a for a in restarted.attention.open_asks() if a.get("category") == "capability_attach"]   # never re-asked
