"""Gate integration: the compiled constitution drives the WP-01 pipeline.

Golden C2 research intent runs REQUIRE_HUMAN -> founder approval -> echo
adapter -> closed episode (verify_chain True). A constitutional_amendment
intent is DENIED at EVALUATE even with a founder approval presented — the
permanent_prohibitions clause fires before APPROVE, so the approval is never
even consumed; replaying it still refuses. A replayed happy-path approval
(nonce consumed) is refused. Two independently compiled runs over the same
intent produce byte-identical decision_traces (Hard Rule 5 determinism).
"""
from datetime import datetime, timedelta, timezone

import pytest

from kernel.adapters.echo import EchoAdapter
from kernel.authority.approvals import ApprovalService
from kernel.contracts.institutional import EvidencePacket
from kernel.crypto.hashing import sha256_hex
from kernel.gate import errors
from kernel.gate.pipeline import Gate
from kernel.spine import Spine
from kernel.ucl import Constitution, compile_policy_fn
from kernel.ucl.version import constitution_version_from_dir, policy_version

from .conftest import make_intent


def fresh_evidence(hours: float = 1.0) -> EvidencePacket:
    return EvidencePacket(
        source_uri="file://research/market-brief",
        source_hash=sha256_hex(b"market brief"),
        authority_class="simulated",
        claims=["competitor pricing is observable"],
        freshness_deadline=datetime.now(timezone.utc) + timedelta(hours=hours),
    )


def build_world(tmp_path, constitution_dir, *, current_state: str = "normal", name: str = "spine"):
    """Wire the compiled constitution into the WP-01 gate, end to end."""
    model = Constitution.from_directory(constitution_dir, current_state=current_state)
    versions = {
        "policy_version": policy_version(model),
        "constitution_version": constitution_version_from_dir(constitution_dir),
    }
    policy_fn = compile_policy_fn(model, **versions)
    spine = Spine(tmp_path / name)
    authority = ApprovalService(approver_id="founder")
    evidence = fresh_evidence()
    gate = Gate(
        versions["policy_version"],
        versions["constitution_version"],
        authority,
        spine,
        policy_fn=policy_fn,
        evidence_store={evidence.id: evidence},
    )
    echo = EchoAdapter(witness_public_key=authority.public_key)
    gate.register_adapter(echo.adapter_id, echo.public_key_hex)
    return {
        "spine": spine,
        "authority": authority,
        "gate": gate,
        "echo": echo,
        "evidence": evidence,
        "versions": versions,
        "policy_fn": policy_fn,
    }


def spine_payload(spine, kind):
    return [r["payload"] for r in spine.iter() if r["kind"] == kind]


def spine_records(spine, kind):
    return [r for r in spine.iter() if r["kind"] == kind]


def test_golden_c2_research_intent_end_to_end(tmp_path, constitution_dir):
    w = build_world(tmp_path, constitution_dir)
    gate, authority, echo, spine = w["gate"], w["authority"], w["echo"], w["spine"]

    intent = make_intent(evidence_ids=[w["evidence"].id])
    approval = authority.issue_approval(gate.fingerprint(intent))
    episode = gate.run(intent, adapter=echo, approval=approval)

    # Closed episode, exactly one execution, full artifact chain.
    assert episode.closed is True and episode.close_reason == "completed"
    assert episode.approval_id == approval.id
    assert echo.calls == 1

    # The PolicyDecision on the spine is the compiled constitution's own.
    (decision,) = spine_payload(spine, "PolicyDecision")
    assert decision["effect"] == "REQUIRE_HUMAN"
    assert decision["governing_clauses"] == ["consequence_default:C2:REQUIRE_HUMAN"]
    assert decision["policy_version"] == w["versions"]["policy_version"]
    assert decision["constitution_version"] == w["versions"]["constitution_version"]
    trace = "\n".join(decision["decision_trace"])
    assert "ucl:shutdown_state" in trace
    assert "ucl:permanent_prohibitions matched=none" in trace
    assert "ucl:participant_rights flags=none" in trace
    assert "ucl:consequence_default" in trace

    (reconciliation,) = spine_payload(spine, "ReconciliationRecord")
    assert reconciliation["reconciled"] is True
    assert spine.verify_chain() is True


def test_constitutional_amendment_denied_at_evaluate_with_founder_approval(
    tmp_path, constitution_dir
):
    w = build_world(tmp_path, constitution_dir)
    gate, authority, echo, spine = w["gate"], w["authority"], w["echo"], w["spine"]

    intent = make_intent(
        action_type="constitutional_amendment",
        objective="Amend the constitution to expand agent authority",
        evidence_ids=[w["evidence"].id],
    )
    # A genuine founder approval for THIS intent is presented...
    approval = authority.issue_approval(gate.fingerprint(intent))

    # ...and the intent is still DENIED at EVALUATE, before APPROVE is reached.
    with pytest.raises(errors.PolicyDenial):
        gate.run(intent, adapter=echo, approval=approval)
    assert echo.calls == 0

    (decision,) = spine_payload(spine, "PolicyDecision")
    assert decision["effect"] == "DENY"
    assert decision["governing_clauses"] == ["permanent_prohibitions:constitutional_amendment"]
    (refusal,) = spine_records(spine, "GATE_REFUSAL")
    assert refusal["refs"]["stage"] == "EVALUATE"
    # No grant/witness/execution artifacts exist: denial happened pre-APPROVE.
    assert spine_payload(spine, "CapabilityGrant") == []
    assert spine_payload(spine, "CommitWitness") == []
    assert spine.verify_chain() is True

    # Replaying that same approval still refuses: EVALUATE denies again, and
    # the approval never even reaches nonce consumption.
    with pytest.raises(errors.PolicyDenial):
        gate.run(intent, adapter=echo, approval=approval)
    assert echo.calls == 0
    assert spine.verify_chain() is True


def test_replayed_happy_path_approval_refused(tmp_path, constitution_dir):
    w = build_world(tmp_path, constitution_dir)
    gate, authority, echo, spine = w["gate"], w["authority"], w["echo"], w["spine"]

    intent = make_intent(evidence_ids=[w["evidence"].id])
    approval = authority.issue_approval(gate.fingerprint(intent))
    episode = gate.run(intent, adapter=echo, approval=approval)
    assert episode.closed is True
    assert echo.calls == 1

    # The identical intent has the identical fingerprint; the replayed
    # approval's nonce is already consumed -> refused at APPROVE.
    with pytest.raises(errors.ApprovalRefusal, match="replay"):
        gate.run(intent, adapter=echo, approval=approval)
    assert echo.calls == 1  # no second execution
    assert spine.verify_chain() is True


def test_two_compiled_runs_produce_identical_decision_traces(tmp_path, constitution_dir):
    intent = make_intent()
    traces = []
    for name in ("spine-a", "spine-b"):
        w = build_world(tmp_path, constitution_dir, name=name)
        approval = w["authority"].issue_approval(w["gate"].fingerprint(intent))
        episode = w["gate"].run(intent, adapter=w["echo"], approval=approval)
        assert episode.closed is True
        (decision,) = spine_payload(w["spine"], "PolicyDecision")
        traces.append(decision["decision_trace"])
        assert w["spine"].verify_chain() is True
    assert traces[0] == traces[1]


def test_quarantined_state_denies_external_effect_before_approval(tmp_path, constitution_dir):
    w = build_world(tmp_path, constitution_dir, current_state="quarantined")
    intent = make_intent(evidence_ids=[w["evidence"].id])
    approval = w["authority"].issue_approval(w["gate"].fingerprint(intent))
    with pytest.raises(errors.PolicyDenial):
        w["gate"].run(intent, adapter=w["echo"], approval=approval)
    (decision,) = spine_payload(w["spine"], "PolicyDecision")
    assert decision["governing_clauses"] == ["ucl:shutdown_state:quarantined"]
    assert w["echo"].calls == 0
    assert w["spine"].verify_chain() is True
