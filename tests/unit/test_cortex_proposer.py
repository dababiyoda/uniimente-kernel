"""The Seed Cortex attaches to the standing cognition runtime as a proposer that
ledgers every receipt and creates no authority."""
from __future__ import annotations

import pytest

from cortex.routing import Cortex
from egregore.contracts import Assessment, ContractError, SignalEnvelope
from egregore.cortex_proposer import RECEIPT_RECORD, REQUEST_KEY, CortexProposer
from egregore.resources import ResourceGovernor
from egregore.runtime import CycleStatus, StandingCognitionRuntime
from provenance.ledger import EvidenceLedger

FORMAL = {"problem_id": "cp-formal-1", "question": "Is the pair schedulable?", "payload": {
    "formal_model": {"requirement": "x + y <= 4",
                     "variables": [{"name": "x", "sort": "int", "lo": 0, "hi": 4},
                                   {"name": "y", "sort": "int", "lo": 0, "hi": 4}],
                     "obligations": [{"id": "R1", "text": "x + y at most 4"}],
                     "constraints": [{"id": "C1", "covers": ["R1"], "expr": ["<=", ["+", "x", "y"], 4]}]},
    "declared": {"consequence_class": "internal_write", "reversibility": "reversible"}}}
LEGAL = {"problem_id": "cp-legal-1", "question": "May we rely on this clause?", "payload": {
    "sources": [{"id": "s1", "text": "Clause 4 says notice is required."}],
    "declared": {"epistemic_class": "legal", "consequence_class": "internal_write", "reversibility": "reversible"}}}
EMPTY = {"problem_id": "cp-empty-1", "question": "What should we do?", "payload": {
    "declared": {"consequence_class": "internal_write", "reversibility": "reversible"}}}


def signal(event_id="event-1"):
    return SignalEnvelope.build(source="discord://community/main", source_event_id=event_id,
                                observed_at="2026-10-13T00:00:00Z", payload={"text": "a question arrived"},
                                evidence_refs=(f"source:{event_id}",))


def approving(role):
    def evaluate(candidate, signals, context):
        return Assessment.build(role=role, candidate_id=candidate.candidate_id, score=0.8, confidence=0.9,
                                objections=(), veto=False, evidence_refs=("review:test",))
    return evaluate


def harness(proposer_kwargs=None):
    ledger = EvidenceLedger("sha256:" + "a" * 64)
    cortex = Cortex(clock=lambda: "2026-10-13T00:00:00Z")
    proposer = CortexProposer(cortex, ledger, **(proposer_kwargs or {}))
    runtime = StandingCognitionRuntime(ledger=ledger, proposers={proposer.name: proposer},
                                       evaluators={"guardian": approving("guardian"), "treasury": approving("treasury")})
    return ledger, proposer, runtime


def tick(runtime, problem, trigger="tick-1"):
    s = signal()
    runtime.ingest(s)
    return runtime.tick(trigger_id=trigger, signal_ids=(s.signal_id,),
                        resources=ResourceGovernor(max_model_calls=20, max_estimated_cost_usd=1.0),
                        context={REQUEST_KEY: {"problem": problem}})


def test_recommendation_becomes_a_review_candidate_with_a_ledgered_receipt():
    ledger, proposer, runtime = harness()
    cycle = tick(runtime, FORMAL)
    assert cycle.status == CycleStatus.PROPOSED
    assert len(cycle.candidates) == 1
    c = cycle.candidates[0]
    assert c.proposed_by == "seed_cortex" and c.action_class == "draft.prepare"
    assert c.consequence_class == "internal_write" and c.execution_authority == "none"
    assert c.payload["authority_created"] is False and c.payload["disposition"]["kind"] == "recommend"
    assert c.payload["epistemic_class"] == "constraint_feasibility"
    assert c.payload["selected_routes"] == ["cortex.formal.z3@0.2.0"]
    receipts = ledger.by_type(RECEIPT_RECORD)
    assert len(receipts) == 1 and receipts[0].hash == c.payload["cortex_receipt_ref"]
    assert receipts[0].payload["execution_authority"] == "none"
    assert receipts[0].payload["receipt"]["authority_created"] is False
    assert f"ledger:{receipts[0].hash}" in c.evidence_refs
    assert proposer.receipts() == receipts


def test_abstention_is_ledgered_but_proposes_nothing():
    ledger, _, runtime = harness()
    cycle = tick(runtime, EMPTY)
    assert cycle.candidates == () and cycle.status == CycleStatus.SILENT
    receipts = ledger.by_type(RECEIPT_RECORD)
    assert len(receipts) == 1
    assert receipts[0].payload["receipt"]["disposition"]["kind"] == "abstain"


def test_human_authority_question_is_handed_off_not_decided():
    ledger, _, runtime = harness()
    cycle = tick(runtime, LEGAL)
    assert len(cycle.candidates) == 1
    c = cycle.candidates[0]
    assert c.action_class == "human.adjudicate" and c.requested_capability == "human.adjudicate"
    assert c.payload["disposition"]["kind"] == "handoff" and c.payload["epistemic_class"] == "legal"
    assert c.consequence_class == "internal_write" and c.execution_authority == "none"


def test_model_budget_is_clamped_to_the_proposer_ceiling():
    seen = {}

    class Spy:
        def run(self, problem, records=None):
            seen["problem"] = problem
            return Cortex(clock=lambda: "2026-10-13T00:00:00Z").run(problem, records=records)

    ledger = EvidenceLedger("sha256:" + "a" * 64)
    proposer = CortexProposer(Spy(), ledger, max_model_calls=1)
    request = {"problem_id": "cp-budget", "question": "q", "payload": {"resources": {"max_model_calls": 5},
               "declared": {"consequence_class": "internal_write", "reversibility": "reversible"}}}
    proposer((signal(),), {REQUEST_KEY: {"problem": request}})
    assert seen["problem"]["payload"]["resources"]["max_model_calls"] == 1
    with pytest.raises(ContractError):
        proposer((signal(),), {REQUEST_KEY: {"problem": {**request, "payload": {"resources": {"max_model_calls": -1}}}}})


def test_no_request_means_no_opinion_and_bad_request_is_a_recorded_failure():
    ledger, proposer, runtime = harness()
    assert proposer((signal(),), {}) is None
    assert proposer((), {REQUEST_KEY: {"problem": FORMAL}}) is None
    assert ledger.by_type(RECEIPT_RECORD) == []
    s = signal()
    runtime.ingest(s)
    cycle = runtime.tick(trigger_id="tick-bad", signal_ids=(s.signal_id,),
                         resources=ResourceGovernor(max_model_calls=20, max_estimated_cost_usd=1.0),
                         context={REQUEST_KEY: {"problem": "not a mapping"}})
    assert cycle.status == CycleStatus.REFUSED
    assert cycle.failures and cycle.failures[0]["component"] == "proposer:seed_cortex"


def test_malformed_problem_still_yields_a_receipt_and_no_candidate():
    ledger, _, runtime = harness()
    cycle = tick(runtime, {"problem_id": "cp-mal", "question": "q", "payload": {"formal_model": {"bogus": True}}})
    assert cycle.candidates == ()
    receipts = ledger.by_type(RECEIPT_RECORD)
    assert len(receipts) == 1
    assert receipts[0].payload["receipt"]["output"]["state"] in ("MALFORMED_INPUT", "FORMALIZATION_INCOMPLETE")


def test_binding_imports_nothing_that_can_act():
    import egregore.cortex_proposer as binding
    imports = [line.strip() for line in open(binding.__file__, encoding="utf-8")
               if line.startswith(("import ", "from "))]
    assert imports, "the guard must see the import lines"
    for line in imports:
        for forbidden in ("policy", "adapters", "gate_adapter", "commit_witness", "subprocess", "socket",
                          "urllib", "requests", "events", "foundry"):
            assert f" {forbidden}" not in f" {line}" and f".{forbidden}" not in line, line


def test_constructor_refuses_a_cortex_without_run_or_a_ledger_without_a_chain():
    class NoRun: ...
    with pytest.raises(ContractError):
        CortexProposer(NoRun(), EvidenceLedger("sha256:" + "a" * 64))
    with pytest.raises(ContractError):
        CortexProposer(Cortex(), object())
    with pytest.raises(ContractError):
        CortexProposer(Cortex(), EvidenceLedger("sha256:" + "a" * 64), max_model_calls=-1)
