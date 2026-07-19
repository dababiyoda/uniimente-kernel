"""Happy path: C2 research intent -> REQUIRE_HUMAN -> founder approval ->
echo execution -> receipt -> reconcile -> outcome -> closed episode ->
verify_chain() passes. Plus the unbypassable-human and DENY invariants.
"""
from datetime import datetime, timedelta, timezone

import pytest

from kernel.adapters.echo import EchoAdapter
from kernel.authority.approvals import ApprovalService
from kernel.contracts.action import ActionIntent
from kernel.contracts.institutional import EvidencePacket
from kernel.crypto.hashing import sha256_hex
from kernel.gate import errors
from kernel.gate.pipeline import Gate
from kernel.spine import Spine

POLICY_VERSION = "policy-1.0"
CONSTITUTION_VERSION = "const-1.0"


def fresh_evidence(hours: float = 1.0) -> EvidencePacket:
    return EvidencePacket(
        source_uri="file://research/market-brief",
        source_hash=sha256_hex(b"market brief"),
        authority_class="simulated",
        claims=["competitor pricing is observable"],
        freshness_deadline=datetime.now(timezone.utc) + timedelta(hours=hours),
    )


def make_intent(evidence: EvidencePacket, **overrides) -> ActionIntent:
    fields = dict(
        actor_id="agent-7",
        organ_id="research-organ",
        legal_principal="Uniimente Ltd",
        objective="Research competitor pricing",
        action_type="research",
        resource="web",
        target="https://example.com/competitors",
        payload={"query": "competitor pricing", "max_pages": 3},
        consequence_class="C2",
        evidence_ids=[evidence.id],
        expected_outcome="bounded research brief on competitor pricing",
        rollback=None,
        expiry_minutes=30,
    )
    fields.update(overrides)
    return ActionIntent(**fields)


def build_world(tmp_path, **gate_kwargs):
    spine = Spine(tmp_path / "spine")
    clock = gate_kwargs.pop("clock", None)
    authority = ApprovalService(approver_id="founder", clock=clock)
    evidence = fresh_evidence()
    gate = Gate(
        POLICY_VERSION,
        CONSTITUTION_VERSION,
        authority,
        spine,
        clock=clock,
        evidence_store={evidence.id: evidence},
        **gate_kwargs,
    )
    echo = EchoAdapter(witness_public_key=authority.public_key, clock=clock)
    gate.register_adapter(echo.adapter_id, echo.public_key_hex)
    return {
        "spine": spine,
        "authority": authority,
        "gate": gate,
        "echo": echo,
        "evidence": evidence,
    }


def test_happy_path_c2_research_intent(tmp_path):
    w = build_world(tmp_path)
    gate, authority, echo, spine = w["gate"], w["authority"], w["echo"], w["spine"]

    intent = make_intent(w["evidence"])
    assert intent.consequence_class == "C2"

    # EVALUATE will produce REQUIRE_HUMAN; the founder signs an approval bound
    # to this intent's fingerprint.
    approval = authority.issue_approval(gate.fingerprint(intent))
    episode = gate.run(intent, adapter=echo, approval=approval)

    # Episode closed cleanly with every artifact linked.
    assert episode.closed is True
    assert episode.close_reason == "completed"
    assert episode.intent_id == intent.id
    assert episode.decision_id
    assert episode.approval_id == approval.id
    assert episode.witness_id
    assert episode.receipt_id
    assert episode.outcome_id

    # Exactly one execution.
    assert echo.calls == 1

    # All pipeline artifacts were appended to the spine, in order.
    kinds = [r["kind"] for r in spine.iter()]
    assert kinds == [
        "ActionIntent",
        "PolicyDecision",
        "ApprovalRecord",
        "CapabilityGrant",
        "CommitWitness",
        "EXECUTE_BEGIN",
        "ExecutionReceipt",
        "ReconciliationRecord",
        "OutcomeRecord",
        "DecisionEpisode",
    ]
    decision = spine.get(1)["payload"]
    assert decision["effect"] == "REQUIRE_HUMAN"
    assert "REQUIRE_HUMAN" in str(decision["decision_trace"])
    reconciliation = spine.get(7)["payload"]
    assert reconciliation["reconciled"] is True
    outcome = spine.get(8)["payload"]
    assert outcome["matched_expected"] is True

    # The hash chain verifies end to end.
    assert spine.verify_chain() is True


def test_require_human_is_unbypassable_without_approval(tmp_path):
    w = build_world(tmp_path)
    intent = make_intent(w["evidence"])
    with pytest.raises(errors.ApprovalRefusal):
        w["gate"].run(intent, adapter=w["echo"], approval=None)
    assert w["echo"].calls == 0
    # The refusal is recorded and the spine still verifies.
    kinds = [r["kind"] for r in w["spine"].iter()]
    assert "GATE_REFUSAL" in kinds
    episode = [r for r in w["spine"].iter() if r["kind"] == "DecisionEpisode"][-1]
    assert episode["payload"]["closed"] is True
    assert "unbypassable" in episode["payload"]["close_reason"]
    assert w["spine"].verify_chain() is True


def test_c3_denied_by_default_policy(tmp_path):
    w = build_world(tmp_path)
    intent = make_intent(w["evidence"], consequence_class="C3")
    with pytest.raises(errors.PolicyDenial):
        w["gate"].run(intent, adapter=w["echo"], approval=None)
    assert w["echo"].calls == 0
    assert w["spine"].verify_chain() is True


def test_c0_permitted_without_approval(tmp_path):
    w = build_world(tmp_path)
    intent = make_intent(w["evidence"], consequence_class="C0")
    episode = w["gate"].run(intent, adapter=w["echo"], approval=None)
    assert episode.closed is True
    assert episode.approval_id is None
    assert w["echo"].calls == 1
    assert w["spine"].verify_chain() is True


def test_empty_legal_principal_refused_at_identify(tmp_path):
    w = build_world(tmp_path)
    intent = make_intent(w["evidence"], legal_principal="   ")
    with pytest.raises(errors.IdentityRefusal):
        w["gate"].run(intent, adapter=w["echo"], approval=None)
    assert w["echo"].calls == 0
