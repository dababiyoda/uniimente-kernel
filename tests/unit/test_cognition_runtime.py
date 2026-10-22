"""Meaningful boundary, persistence and consequence tests for the seed."""
import json
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from compiler.ucl_compiler import compile_constitution
from egregore.contracts import ContractError, IntegrityConflict, SignalEnvelope
from egregore.cognition.contracts import (
    CognitiveBudget, CognitiveRequest, ConsequenceVector, EpistemicClass,
    GateAssessment, GATE_NAMES, ProblemGeometry, ResultStatus,
)
from egregore.cognition.genomes import IntelligenceGenome, RESERVED_FAMILIES
from egregore.cognition.integration import CortexProposer, assess_for_cognition
from egregore.cognition.learning import RoutingMemory
from egregore.cognition.runtime import SeedCortex
from egregore.resources import ResourceExhausted, ResourceGovernor
from policy.engine import Proposal
from provenance.ledger import EvidenceLedger
from pathlib import Path
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import threading


def gates(**changes):
    checks = dict.fromkeys(GATE_NAMES, "pass")
    checks.update(changes)
    return GateAssessment(checks, "fixture:operator-assessment", "allow", synthetic=True)


def request(problem_id="fermi", *, epistemic=EpistemicClass.ESTIMATE, **kwargs):
    return CognitiveRequest(problem_id, "Estimate hours for bounded work", ProblemGeometry(epistemic),
        payload={"fermi": {"factors": [
            {"name": "jobs", "low": 10, "central": 15, "high": 20,
             "units": {"job": 1}, "power": 1, "assumption": "supplied workload range"},
            {"name": "duration", "low": 1, "central": 2, "high": 3,
             "units": {"hour": 1, "job": -1}, "power": 1, "assumption": "supplied duration range"}],
            "output_units": {"hour": 1}}}, **kwargs)


def test_native_route_receipts_exact_conditional_range():
    ledger = EvidenceLedger("fixture:constitution")
    cortex = SeedCortex(ledger)
    receipt = cortex.think(request(), gates=gates())
    assert receipt.selected_method == "fermi"
    assert receipt.result.status == ResultStatus.ANSWERED
    assert Decimal(receipt.result.output["low"]) == 10
    assert Decimal(receipt.result.output["central"]) == 30
    assert Decimal(receipt.result.output["high"]) == 60
    assert receipt.verification.accepted
    assert receipt.result.proof.empirical_validity == "world_unverified"
    assert receipt.to_dict()["authority_created"] is False
    assert receipt.to_dict()["legitimate_authority"] == "not_granted"
    assert ledger.verify_chain()[0]
    for name in RESERVED_FAMILIES:
        genome = cortex.registry.get(f"cognition.{name}", "0.1.0")
        assert isinstance(genome, IntelligenceGenome)
        assert not genome.cognitive_profile.enabled


@pytest.mark.parametrize("gate", GATE_NAMES)
@pytest.mark.parametrize("state", ["fail", "unknown"])
def test_any_failed_or_unknown_gate_prevents_solver_even_with_enormous_upside(gate, state):
    class ForbiddenClient:
        def complete(self, *args):
            raise AssertionError("gate must stop before inference")
    ledger = EvidenceLedger("fixture:constitution")
    req = CognitiveRequest("huge-upside", "Claim a huge advantage", ProblemGeometry(EpistemicClass.SEMANTIC),
                           payload={"projected_advantage": 10**100})
    receipt = SeedCortex(ledger, semantic_client=ForbiddenClient()).think(req, gates=gates(**{gate: state}))
    assert receipt.disposition == "abstain"
    assert receipt.selected_method is None
    assert receipt.resource_usage["used_model_calls"] == 0


def test_unknown_mixed_and_mislabelled_geometry_abstain():
    cortex = SeedCortex(EvidenceLedger("fixture:constitution"))
    unknown = CognitiveRequest("unknown", "An ambiguous problem", ProblemGeometry())
    assert cortex.think(unknown, gates=gates()).disposition == "abstain"
    mixed = replace(request("mixed"), payload={**request().payload, "formal": {}})
    assert cortex.think(mixed, gates=gates()).selected_method is None
    mislabelled = replace(request("mislabelled"), geometry=ProblemGeometry(EpistemicClass.FORMAL))
    assert cortex.think(mislabelled, gates=gates()).selected_method is None


@pytest.mark.parametrize("epistemic", [EpistemicClass.OPTIMIZATION, EpistemicClass.PREDICTION,
                                       EpistemicClass.PHYSICAL, EpistemicClass.INSTITUTIONAL])
def test_future_epistemic_classes_are_representable_and_execution_disabled(epistemic):
    cortex = SeedCortex(EvidenceLedger("fixture:c"))
    req = CognitiveRequest(epistemic.value, "Future typed problem", ProblemGeometry(epistemic))
    receipt = cortex.think(req, gates=gates())
    assert receipt.geometry["epistemic_class"] == epistemic.value
    assert receipt.disposition == "abstain"
    assert receipt.selected_method is None


def test_budget_zero_model_calls_prevents_invocation():
    class ForbiddenClient:
        def complete(self, *args):
            raise AssertionError("budget must stop before inference")
    req = CognitiveRequest("budget", "Draft", ProblemGeometry(EpistemicClass.SEMANTIC),
                           budget=CognitiveBudget(max_model_calls=0))
    receipt = SeedCortex(EvidenceLedger("fixture:c"), semantic_client=ForbiddenClient()).think(req, gates=gates())
    assert receipt.disposition == "abstain"
    assert receipt.resource_usage["used_model_calls"] == 0


def test_missing_evidence_abstains_before_model_call():
    req = CognitiveRequest("missing", "Source a claim", ProblemGeometry(EpistemicClass.SEMANTIC),
                           evidence_refs=("sha256:" + "a" * 64,))
    receipt = SeedCortex(EvidenceLedger("fixture:c")).think(req, gates=gates())
    assert receipt.disposition == "abstain"
    assert receipt.resource_usage["used_model_calls"] == 0


def test_source_correspondence_not_proved_by_formal_sat():
    pytest.importorskip("z3")
    req = CognitiveRequest("formal", "Find x with supplied constraints; world remains unverified",
        ProblemGeometry(EpistemicClass.FORMAL), payload={"formal": {
            "variables": {"x": {"min": 0, "max": 2}},
            "constraints": [{"id": "one", "lhs": {"x": 1}, "op": "==", "rhs": 1}],
            "required_constraint_ids": ["one"]}},
        consequence=ConsequenceVector("financial", harms={"financial": 1.0}))
    receipt = SeedCortex(EvidenceLedger("fixture:c")).think(req, gates=gates())
    assert receipt.result.output["solver_status"] == "SAT"
    assert receipt.result.proof.empirical_validity == "world_unverified"
    assert receipt.to_dict()["legitimate_authority"] == "not_granted"


def test_restart_reuses_receipt_without_spend_and_refuses_changed_problem_id(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    first_ledger = EvidenceLedger("fixture:c", path)
    first = SeedCortex(first_ledger).think(request(), gates=gates())
    first_ledger.close()
    second_ledger = EvidenceLedger("fixture:c", path)
    cortex = SeedCortex(second_ledger)
    second = cortex.think(request(), gates=gates())
    assert second.to_dict() == first.to_dict()
    assert len(second_ledger.by_type("cognition.receipt")) == 1
    with pytest.raises(IntegrityConflict):
        cortex.think(replace(request(), question="Changed material conditions"), gates=gates())
    second_ledger.close()


def test_receipt_reuse_rechecks_source_expiry(monkeypatch):
    import egregore.cognition.runtime as runtime
    ledger = EvidenceLedger("fixture:c")
    ref = ledger.append("evidence", {"content": "supplied workload", "expires_at": "2030-01-01T00:00:00Z"}).hash
    req = request(evidence_refs=(ref,))
    cortex = SeedCortex(ledger)
    first = cortex.think(req, gates=gates())
    assert first.disposition == "recommend"
    class Future(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2031, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(runtime, "datetime", Future)
    second = cortex.think(req, gates=gates())
    assert second.disposition == "abstain"
    assert second.receipt_id != first.receipt_id
    assert len(ledger.by_type("cognition.receipt")) == 2


def test_reference_integrity_cannot_turn_receipt_into_source_evidence():
    ledger = EvidenceLedger("fixture:c")
    ref = ledger.append("cognition.receipt", {"content": "claimed fact"}).hash
    # A malformed receipt is not a valid cache entry and never factual evidence.
    req = request("source", evidence_refs=(ref,))
    cortex = SeedCortex(ledger)
    with pytest.raises((ContractError, KeyError)):
        cortex.think(req, gates=gates())


@pytest.mark.parametrize("budget", [-1, float("nan"), float("inf"), True])
def test_nonfinite_or_negative_resources_are_rejected(budget):
    with pytest.raises(ContractError):
        CognitiveBudget(max_cost_usd=budget)


def test_causal_and_legal_routes_have_truthful_handoff():
    cortex = SeedCortex(EvidenceLedger("fixture:c"))
    for epistemic in (EpistemicClass.CAUSAL, EpistemicClass.LEGAL):
        req = CognitiveRequest(epistemic.value, "Can this intervention legally prevent failure?",
                               ProblemGeometry(epistemic))
        receipt = cortex.think(req, gates=gates())
        assert receipt.disposition in ("abstain", "test", "handoff")
        assert receipt.result.proof.empirical_validity == "world_unverified"


def test_existing_policy_refusal_dominates_supplied_domain_passes():
    compiled = compile_constitution(Path(__file__).resolve().parents[2])
    proposal = Proposal("unknown", "alfonso_lopez", "draft.prepare", "draft", {},
                        "internal://review", "internal_write", 0.0, [], 0.0,
                        "draft.prepare", "review")
    assessment = assess_for_cognition(compiled, proposal, identity_ok=False, grant=None,
                                     domain_checks=gates().checks)
    assert not assessment.eligible
    assert assessment.policy_verdict == "deny"


def test_proposer_remains_fixed_scope_with_zero_confidence():
    ledger = EvidenceLedger("fixture:c")
    cortex = SeedCortex(ledger)
    proposer = CortexProposer(cortex, lambda req: gates())
    signal = SignalEnvelope.build(source="fixture", source_event_id="one", observed_at="2026-09-30T00:00:00Z",
                                  payload={"content": "Workload request"})
    candidate = proposer((signal,), {"cognitive_request": request().to_dict()})
    assert candidate.consequence_class == "internal_write"
    assert candidate.confidence == 0.0
    assert candidate.execution_authority == "none"


def test_learning_rejects_self_report_and_unlinked_outcomes():
    ledger = EvidenceLedger("fixture:c")
    SeedCortex(ledger).think(request(), gates=gates())
    ref = ledger.by_type("cognition.receipt")[-1].hash
    outcome = ledger.append("outcome", {"result_class": "positive", "validation_status": "self_reported"}).hash
    memory = RoutingMemory(ledger)
    with pytest.raises(ContractError):
        memory.propose_update(cognitive_receipt_ref=ref, outcome_ref=outcome,
                              contributions=[{"method": "fermi", "role": "estimate", "evidence_refs": [ref]}],
                              attribution_uncertainty="cannot isolate contribution")


def test_learning_records_bounded_inert_candidate_and_preserves_authority():
    ledger = EvidenceLedger("fixture:c")
    cortex = SeedCortex(ledger)
    cortex.think(request(), gates=gates())
    cognitive = ledger.by_type("cognition.receipt")[-1]
    ledger.append("witness", {"witness_id": "fixture:witness", "action_class": "fixture.analysis",
                             "evidence_refs": [cognitive.hash], "policy_version": "fixture:policy"})
    ledger.append("receipt", {"action_id": "fixture:action", "witness_id": "fixture:witness"})
    outcome = ledger.append("outcome", {"action_ref": "fixture:action", "result_class": "positive",
                                       "validation_status": "externally_verified"})
    args = dict(cognitive_receipt_ref=cognitive.hash, outcome_ref=outcome.hash,
                contributions=[{"method": "fermi", "role": "estimate", "evidence_refs": [cognitive.hash]}],
                attribution_uncertainty="synthetic linkage only; no external reality evidence")
    memory = RoutingMemory(ledger)
    update = memory.propose_update(**args)
    assert memory.propose_update(**args).hash == update.hash
    assert update.payload["applied"] is False
    assert abs(update.payload["proposed_weight_delta"]) <= 0.05
    assert update.payload["authority_created"] is False
    assert cortex.execution_authority == "none"
    cached = memory.propose_update(**args)
    cached.payload["applied"] = True
    assert ledger.verify_chain()[0]
    revised = memory.propose_update(**{**args, "attribution_uncertainty": "revised interpretation, same outcome"})
    assert revised.record_type == "cognition.routing_attribution_revision"
    assert revised.payload["additional_observations"] == 0
    assert len(ledger.by_type("cognition.routing_update_proposed")) == 1


def test_cached_receipt_cannot_mutate_retained_ledger():
    ledger = EvidenceLedger("fixture:c")
    cortex = SeedCortex(ledger)
    cortex.think(request(), gates=gates())
    cached = cortex.think(request(), gates=gates())
    cached.geometry["x"] = "caller mutation"
    cached.resource_usage["used_model_calls"] = 999
    cached.gates["checks"]["rights"] = "fail"
    assert ledger.verify_chain()[0]
    restored = cortex.think(request(), gates=gates())
    assert "x" not in restored.geometry
    assert restored.resource_usage["used_model_calls"] == 0


def test_solver_mutation_cannot_rewrite_independent_verification_inputs():
    from egregore.cognition.organs import FermiOrgan
    class MutatingOrgan(FermiOrgan):
        def solve(self, req, evidence, **kwargs):
            req.payload["fermi"]["factors"][0]["central"] = 20
            return super().solve(req, evidence, **kwargs)
    ledger = EvidenceLedger("fixture:c")
    cortex = SeedCortex(ledger)
    cortex.organs["fermi"] = MutatingOrgan()
    receipt = cortex.think(request(), gates=gates())
    assert receipt.disposition == "abstain"
    assert not receipt.verification.accepted
    original = ledger.find(receipt.request_ref).payload["request"]
    assert original["payload"]["fermi"]["factors"][0]["central"] == 15
    assert ledger.verify_chain()[0]


def test_concurrent_replay_runs_once_across_two_cortices():
    ledger = EvidenceLedger("fixture:c")
    a, b = SeedCortex(ledger), SeedCortex(ledger)
    with ThreadPoolExecutor(max_workers=2) as executor:
        receipts = list(executor.map(lambda cortex: cortex.think(request(), gates=gates()), (a, b)))
    assert receipts[0].receipt_id == receipts[1].receipt_id
    assert len(ledger.by_type("cognition.receipt")) == 1
    assert ledger.verify_chain()[0]


def test_proposer_replay_links_returned_receipt_not_latest_other_problem():
    ledger = EvidenceLedger("fixture:c")
    cortex = SeedCortex(ledger)
    original = cortex.think(request("A"), gates=gates())
    cortex.think(request("B"), gates=gates())
    proposer = CortexProposer(cortex, lambda req: gates())
    signal = SignalEnvelope.build(source="fixture", source_event_id="one", observed_at="2026-09-30T00:00:00Z",
                                  payload={"content": "Workload request"})
    candidate = proposer((signal,), {"cognitive_request": request("A").to_dict()})
    ref = candidate.payload["cognitive_receipt_ref"]
    assert ledger.find(ref).payload["receipt"]["receipt_id"] == original.receipt_id
    assert ref in candidate.evidence_refs


def test_referenced_evidence_has_aggregate_byte_bound():
    ledger = EvidenceLedger("fixture:c")
    source = ledger.append("evidence", {"content": "x" * (128 * 1024 + 1)})
    receipt = SeedCortex(ledger).think(request(evidence_refs=(source.hash,)), gates=gates())
    assert receipt.disposition == "abstain"
    assert receipt.resource_usage["used_model_calls"] == 0


def test_evidence_expiring_during_solver_is_withheld(monkeypatch):
    import egregore.cognition.runtime as runtime
    from egregore.cognition.organs import FermiOrgan
    class Future(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2031, 1, 1, tzinfo=timezone.utc)
    class ExpiringOrgan(FermiOrgan):
        def solve(self, req, evidence, **kwargs):
            result = super().solve(req, evidence, **kwargs)
            monkeypatch.setattr(runtime, "datetime", Future)
            return result
    ledger = EvidenceLedger("fixture:c")
    source = ledger.append("evidence", {"content": "workload", "expires_at": "2030-01-01T00:00:00Z"})
    cortex = SeedCortex(ledger)
    cortex.organs["fermi"] = ExpiringOrgan()
    receipt = cortex.think(request(evidence_refs=(source.hash,)), gates=gates())
    assert receipt.disposition == "abstain"
    assert "evidence_not_current_at_completion" in receipt.result.missing_information


def test_busy_ledger_wait_is_bounded_by_declared_latency():
    ledger = EvidenceLedger("fixture:c")
    cortex = SeedCortex(ledger)
    held, release = threading.Event(), threading.Event()
    def hold():
        with ledger._lock:
            held.set()
            release.wait(timeout=1)
    thread = threading.Thread(target=hold)
    thread.start()
    assert held.wait(timeout=1)
    try:
        with pytest.raises(ResourceExhausted, match="ledger busy"):
            cortex.think(replace(request(), budget=CognitiveBudget(max_latency_ms=1)), gates=gates())
    finally:
        release.set()
        thread.join(timeout=1)
    assert not ledger.by_type("cognition.receipt")


def test_forged_cache_cannot_bypass_current_hard_gate():
    from egregore.contracts import canonical_copy, digest
    ledger = EvidenceLedger("fixture:c")
    cortex = SeedCortex(ledger)
    allowed = cortex.think(request("original"), gates=gates()).to_dict()
    req = request("forged")
    denied = gates(authorization="fail")
    input_hash = digest({"request": req.to_dict(), "gates": denied.to_dict()})
    original = ledger.append("cognition.request", {"input_digest": input_hash, "request": req.to_dict()})
    forged = canonical_copy(allowed)
    forged.update(problem_id=req.problem_id, input_digest=input_hash, gates=denied.to_dict(), request_ref=original.hash)
    forged["receipt_id"] = digest({"kind": "cognitive_receipt", "input_digest": input_hash,
                                   "result": forged["result"], "verification": forged["verification"]})
    ledger.append("cognition.receipt", {"receipt": forged})
    assert ledger.verify_chain()[0]
    with pytest.raises(IntegrityConflict, match="eligibility"):
        cortex.think(req, gates=denied)


@pytest.mark.parametrize("mutation", ["unverified", "unknown_method", "mismatched_method", "wrong_consequence", "invented_refs"])
def test_cached_recommendation_requires_verified_eligible_method_and_exact_request(mutation):
    from egregore.contracts import canonical_copy, digest
    ledger = EvidenceLedger("fixture:c")
    cortex = SeedCortex(ledger)
    saved = cortex.think(request(), gates=gates()).to_dict()
    forged = canonical_copy(saved)
    if mutation == "unverified":
        forged["verification"]["accepted"] = False
    elif mutation == "unknown_method":
        forged["selected_method"] = None
    elif mutation == "mismatched_method":
        forged["selected_method"] = "semantic"
    elif mutation == "wrong_consequence":
        forged["consequence"]["consequence_class"] = "irreversible"
    else:
        forged["evidence_refs"] = ["sha256:" + "a" * 64]
    forged["receipt_id"] = digest({"kind": "cognitive_receipt", "input_digest": saved["input_digest"],
                                   "result": forged["result"], "verification": forged["verification"]})
    ledger.append("cognition.receipt", {"receipt": forged})
    with pytest.raises(IntegrityConflict):
        cortex.think(request(), gates=gates())


def test_cached_recommendation_cannot_resolve_unresolved_geometry():
    from egregore.contracts import canonical_copy, digest
    ledger = EvidenceLedger("fixture:c")
    cortex = SeedCortex(ledger)
    saved = cortex.think(request("source"), gates=gates()).to_dict()
    req = replace(request("unresolved"), geometry=ProblemGeometry(
        EpistemicClass.ESTIMATE, unresolved=("material assumption not established",)))
    input_hash = digest({"request": req.to_dict(), "gates": gates().to_dict()})
    original = ledger.append("cognition.request", {"input_digest": input_hash, "request": req.to_dict()})
    forged = canonical_copy(saved)
    forged.update(problem_id=req.problem_id, input_digest=input_hash, request_ref=original.hash,
                  geometry=req.geometry.to_dict())
    forged["receipt_id"] = digest({"kind": "cognitive_receipt", "input_digest": input_hash,
                                   "result": forged["result"], "verification": forged["verification"]})
    ledger.append("cognition.receipt", {"receipt": forged})
    with pytest.raises(IntegrityConflict, match="eligible method"):
        cortex.think(req, gates=gates())
