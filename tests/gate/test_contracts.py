"""Contract invariants: 20 frozen contracts, extra-forbid, Literal guards,
timezone-aware datetimes, and deterministic canonical hashing (Hard Rules 4-5).
"""
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from kernel.contracts import CONTRACTS, KernelModel
from kernel.contracts.action import (
    ActionIntent,
    ApprovalRecord,
    AutonomyLicense,
    CapabilityGrant,
    PolicyDecision,
)
from kernel.contracts.execution import (
    CommitWitness,
    DecisionEpisode,
    ExecutionReceipt,
    OutcomeRecord,
    ReconciliationRecord,
)
from kernel.contracts.governance import (
    BusinessGenome,
    IncidentRecord,
    OrganCharter,
    RegenerativeImpactRecord,
    SwarmContract,
)
from kernel.contracts.institutional import (
    ContextPacket,
    EvidencePacket,
    InstitutionalEvent,
)
from kernel.contracts.venture import OpportunityPacket, VentureAssessment
from kernel.crypto.hashing import content_hash
from kernel.gate.fingerprint import intent_fingerprint

NOW = datetime.now(timezone.utc)
SOON = NOW + timedelta(hours=1)
FP = "f" * 64
SIG = "00" * 64


def _samples():
    ev = EvidencePacket(
        source_uri="file://research/brief",
        source_hash="ab" * 32,
        authority_class="primary",
        claims=["claim"],
        freshness_deadline=SOON,
    )
    ctx = ContextPacket(subject="subject", evidence=[ev], unknowns=["u"])
    opp = OpportunityPacket(
        source="scanner", signal_summary="sig", context=ctx, observed_at=NOW
    )
    va = VentureAssessment(packet_id=opp.id, verdict="go", reasoning_trace=["t"])
    intent = ActionIntent(
        actor_id="a",
        organ_id="o",
        legal_principal="p",
        objective="obj",
        action_type="research",
        resource="web",
        target="t",
        payload={"k": 1},
        consequence_class="C2",
        evidence_ids=[ev.id],
        expected_outcome="out",
        rollback=None,
        expiry_minutes=10,
    )
    dec = PolicyDecision(
        intent_fingerprint=FP,
        effect="PERMIT",
        governing_clauses=["c"],
        policy_version="p1",
        constitution_version="c1",
        decision_trace=["t"],
    )
    apr = ApprovalRecord(
        intent_fingerprint=FP, approver_id="founder", signature=SIG, nonce="n", expires_at=SOON
    )
    grant = CapabilityGrant(
        grant_id="g",
        intent_fingerprint=FP,
        allowed_tools=["research"],
        allowed_targets=["t"],
        budget={"cpu_seconds": 1.0, "memory_mb": 1.0, "cost_usd": 1.0},
        expires_at=SOON,
        signature=SIG,
    )
    lic = AutonomyLicense(
        capability_id="cap",
        domain="research",
        action_type="research",
        resource="web",
        target_class="public",
        consequence_class="C1",
        budget={"cost_usd": 1.0},
        duration=3600,
        stage="A1",
    )
    wit = CommitWitness(
        intent_fingerprint=FP,
        policy_decision_id=dec.id,
        approval_id=apr.id,
        grant_id=grant.grant_id,
        constitution_version="c1",
        policy_version="p1",
        exact_payload_hash="a" * 64,
        exact_target="t",
        expected_outcome="out",
        expires_at=SOON,
        witness_signature=SIG,
    )
    rcpt = ExecutionReceipt(
        witness_id=wit.id,
        adapter_id="echo",
        external_id=None,
        provider_response_hash="b" * 64,
        executed_at=NOW,
        success=True,
        signature=SIG,
    )
    rec = ReconciliationRecord(
        receipt_id=rcpt.id,
        expected_hash="a" * 64,
        actual_hash="b" * 64,
        reconciled=False,
        discrepancy="x",
    )
    out = OutcomeRecord(
        intent_fingerprint=FP,
        receipt_id=rcpt.id,
        actual_outcome="out",
        matched_expected=True,
        regenerative_effect={},
    )
    ep = DecisionEpisode(
        intent_id=intent.id,
        decision_id=dec.id,
        approval_id=apr.id,
        witness_id=wit.id,
        receipt_id=rcpt.id,
        outcome_id=out.id,
        closed=True,
        close_reason="completed",
    )
    ie = InstitutionalEvent(event_type="X", actor_id="a", organ_id="o", payload_hash="c" * 64)
    rir = RegenerativeImpactRecord(
        subject_id="s",
        accounts={"natural": 0.0, "built": 0.0, "human": 1.0, "social": 0.0, "financial": 0.0},
        debt=0.0,
        blocking=False,
    )
    inc = IncidentRecord(
        severity="S2",
        description="d",
        evidence_ids=[ev.id],
        containment="c",
        new_detection_rule=None,
    )
    charter = OrganCharter(
        organ_id="o",
        objective="obj",
        owner="founder",
        capabilities=["research"],
        budget={"cost_usd": 10.0},
        autonomy_ceiling="A2",
        lifespan_days=30,
        kill_condition="k",
    )
    genome = BusinessGenome(
        recurring_failure="f",
        affected_person="ap",
        buyer="b",
        budget_owner="bo",
        existing_workaround="w",
        urgency="u",
        offer="o",
        evidence=["e"],
        distribution="d",
        acquisition="a",
        conversion="c",
        fulfillment="f2",
        retention="r",
        revenue_model="rm",
        contribution_margin=0.5,
        working_capital=100.0,
        legal_constraints=["lc"],
        required_capabilities=["rc"],
        required_automations=["ra"],
        regenerative_effect={},
        capital_ceiling=1000.0,
        advancement_gate="ag",
        kill_condition="kc",
    )
    swarm = SwarmContract(
        objective="o",
        owner="ow",
        legal_principal="lp",
        deliverable="d",
        required_evidence=["re"],
        maximum_agents=4,
        role_types=["rt"],
        communication_schemas=["cs"],
        allowed_tools=["at"],
        allowed_data=["ad"],
        total_budget={"cost_usd": 5.0},
        consequence_ceiling="C2",
        lifespan_hours=24,
        success_condition="sc",
        failure_condition="fc",
        shutdown="sd",
    )
    return [
        ie, ev, ctx, opp, va, intent, dec, apr, grant, lic,
        wit, rcpt, rec, out, ep, rir, inc, charter, genome, swarm,
    ]


def test_registry_has_exactly_20_contracts():
    assert len(CONTRACTS) == 20
    assert len(set(CONTRACTS.values())) == 20


def test_all_contracts_frozen_and_extra_forbidden():
    for name, cls in CONTRACTS.items():
        assert issubclass(cls, KernelModel), name
        assert cls.model_config.get("frozen") is True, name
        assert cls.model_config.get("extra") == "forbid", name


def test_all_20_construct_and_have_base_fields():
    for model in _samples():
        assert model.schema_version
        assert isinstance(model.id, str) and len(model.id) == 32
        assert model.created_at.tzinfo is not None


def test_contracts_are_immutable():
    intent = _samples()[5]
    assert isinstance(intent, ActionIntent)
    with pytest.raises(ValidationError):
        intent.objective = "mutated"


def test_extra_fields_rejected():
    with pytest.raises(ValidationError):
        InstitutionalEvent(
            event_type="X", actor_id="a", organ_id="o", payload_hash="c" * 64, bogus=1
        )


def test_requires_human_approval_cannot_be_false():
    with pytest.raises(ValidationError):
        VentureAssessment(
            packet_id="p", verdict="go", reasoning_trace=[], requires_human_approval=False
        )


def test_naive_datetime_rejected_fail_closed():
    with pytest.raises(ValidationError):
        EvidencePacket(
            source_uri="file://x",
            source_hash="ab" * 32,
            authority_class="primary",
            claims=[],
            freshness_deadline=datetime.now(),  # naive -> ambiguous -> refused
        )


def test_swarm_maximum_agents_capped_at_16():
    base = dict(
        objective="o", owner="ow", legal_principal="lp", deliverable="d",
        required_evidence=[], role_types=["rt"], communication_schemas=["cs"],
        allowed_tools=[], allowed_data=[], total_budget={"cost_usd": 1.0},
        consequence_ceiling="C1", lifespan_hours=1, success_condition="s",
        failure_condition="f", shutdown="sd",
    )
    with pytest.raises(ValidationError):
        SwarmContract(maximum_agents=17, **base)
    assert SwarmContract(maximum_agents=16, **base).maximum_agents == 16


def test_regenerative_accounts_exactly_five():
    with pytest.raises(ValidationError):
        RegenerativeImpactRecord(
            subject_id="s", accounts={"natural": 0.0}, debt=0.0, blocking=False
        )


def test_content_hash_deterministic_and_key_order_independent():
    assert content_hash({"b": 1, "a": 2}) == content_hash({"a": 2, "b": 1})
    assert content_hash({"a": 2}) != content_hash({"a": 3})


def test_fingerprint_deterministic_and_ignores_ids():
    intent = _samples()[5]
    twin = intent.model_copy(update={"id": "different", "created_at": SOON})
    assert intent_fingerprint(intent, "p1") == intent_fingerprint(twin, "p1")
    mutated = intent.model_copy(update={"payload": {"k": 2}})
    assert intent_fingerprint(mutated, "p1") != intent_fingerprint(intent, "p1")
    assert intent_fingerprint(intent, "p2") != intent_fingerprint(intent, "p1")
