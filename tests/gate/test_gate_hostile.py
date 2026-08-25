"""Hostile test suite — the 12 attacks from SPEC.md. Every attack must be
refused (GateRefusal), no execution may happen unless explicitly expected,
and the spine must keep verifying after each refusal.

Attack coverage:
 1. payload mutated after approval -> refused at revalidation
 2. target substituted after approval -> refused
 3. approval replay (same nonce) -> refused
 4. stale evidence (freshness_deadline passed) -> refused
 5. expired grant -> refused
 6. revoked grant -> refused
 7. split-budget evasion (two grants under limit vs one over) -> refused
 8. cross-organ capability use -> refused
 9. duplicate execution (one_use grant reused) -> refused
10. forged receipt (bad signature) -> refused
11. direct adapter call without witness -> refused (type/protocol level)
12. restart during uncertain effect: spine loss mid-pipeline -> refusal is
    recorded; recovery replays and does not double-execute
"""
from datetime import datetime, timedelta, timezone

import pytest

from kernel.adapters.echo import EchoAdapter
from kernel.authority.approvals import ApprovalService
from kernel.crypto.keys import generate_private_key
from kernel.gate import errors
from kernel.gate.pipeline import Gate
from kernel.spine import Spine

from test_gate_happy_path import (
    CONSTITUTION_VERSION,
    POLICY_VERSION,
    build_world,
    fresh_evidence,
    make_intent,
)


class MutableClock:
    """Test clock the attack scenarios can advance at will."""

    def __init__(self):
        self._now = datetime.now(timezone.utc)

    def __call__(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += timedelta(seconds=seconds)


def _approved(w, intent):
    return w["authority"].issue_approval(w["gate"].fingerprint(intent))


# ---------------------------------------------------------------- 1 & 2


def test_01_payload_mutated_after_approval_refused_at_revalidation(tmp_path):
    def tamper(gate, ctx):
        mutated = dict(ctx.intent.payload)
        mutated["query"] = "exfiltrate the credential store"
        ctx.intent = ctx.intent.model_copy(update={"payload": mutated})

    w = build_world(tmp_path, interceptors={"WITNESS": [tamper]})
    intent = make_intent(w["evidence"])
    approval = _approved(w, intent)
    with pytest.raises(errors.ReauthorizationRefusal):
        w["gate"].run(intent, adapter=w["echo"], approval=approval)
    assert w["echo"].calls == 0
    assert "GATE_REFUSAL" in [r["kind"] for r in w["spine"].iter()]
    assert w["spine"].verify_chain() is True


def test_02_target_substituted_after_approval_refused(tmp_path):
    def tamper(gate, ctx):
        ctx.intent = ctx.intent.model_copy(
            update={"target": "https://evil.example/exfil"}
        )

    w = build_world(tmp_path, interceptors={"WITNESS": [tamper]})
    intent = make_intent(w["evidence"])
    approval = _approved(w, intent)
    with pytest.raises(errors.ReauthorizationRefusal):
        w["gate"].run(intent, adapter=w["echo"], approval=approval)
    assert w["echo"].calls == 0
    assert w["spine"].verify_chain() is True


# ---------------------------------------------------------------- 3 & 4


def test_03_approval_replay_same_nonce_refused(tmp_path):
    w = build_world(tmp_path)
    intent = make_intent(w["evidence"])
    approval = _approved(w, intent)
    episode = w["gate"].run(intent, adapter=w["echo"], approval=approval)
    assert episode.closed and episode.close_reason == "completed"
    assert w["echo"].calls == 1
    # Replay the exact same approval (same nonce): refused at APPROVE.
    with pytest.raises(errors.ApprovalRefusal, match="replay"):
        w["gate"].run(intent, adapter=w["echo"], approval=approval)
    assert w["echo"].calls == 1
    assert w["spine"].verify_chain() is True


def test_04_stale_evidence_refused(tmp_path):
    stale = fresh_evidence(hours=-1.0)  # freshness_deadline already passed
    w = build_world(tmp_path)
    gate = Gate(
        POLICY_VERSION,
        CONSTITUTION_VERSION,
        w["authority"],
        w["spine"],
        evidence_store={stale.id: stale},
    )
    gate.register_adapter(w["echo"].adapter_id, w["echo"].public_key_hex)
    intent = make_intent(stale)
    approval = w["authority"].issue_approval(gate.fingerprint(intent))
    with pytest.raises(errors.StaleEvidence):
        gate.run(intent, adapter=w["echo"], approval=approval)
    assert w["echo"].calls == 0
    assert w["spine"].verify_chain() is True


# ---------------------------------------------------------------- 5 & 6


def test_05_expired_grant_refused(tmp_path):
    clock = MutableClock()

    def expire_grant(gate, ctx):
        clock.advance(120.0)  # push commit time past the 60s grant TTL

    w = build_world(
        tmp_path, clock=clock, grant_ttl_seconds=60, interceptors={"ISSUE": [expire_grant]}
    )
    intent = make_intent(w["evidence"])
    approval = _approved(w, intent)
    with pytest.raises(errors.GrantExpired):
        w["gate"].run(intent, adapter=w["echo"], approval=approval)
    assert w["echo"].calls == 0
    assert w["spine"].verify_chain() is True


def test_06_revoked_grant_refused(tmp_path):
    def revoke(gate, ctx):
        gate.grant_store.revoke(ctx.grant.grant_id)

    w = build_world(tmp_path, interceptors={"ISSUE": [revoke]})
    intent = make_intent(w["evidence"])
    approval = _approved(w, intent)
    with pytest.raises(errors.GrantRevoked):
        w["gate"].run(intent, adapter=w["echo"], approval=approval)
    assert w["echo"].calls == 0
    assert w["spine"].verify_chain() is True


# ---------------------------------------------------------------- 7 & 8


def test_07_split_budget_evasion_refused(tmp_path):
    caps = {
        "per_intent": {"cpu_seconds": 600.0, "memory_mb": 8192.0, "cost_usd": 25.0},
        "window": {"cpu_seconds": 3600.0, "memory_mb": 32768.0, "cost_usd": 30.0},
    }
    w = build_world(tmp_path, budget_caps=caps)
    gate, echo, ev = w["gate"], w["echo"], w["evidence"]

    # One intent over the per-intent limit: refused outright at RESERVE.
    big = make_intent(
        ev, consequence_class="C1", objective="one oversized action",
        payload={"budget": {"cost_usd": 31.0}},
    )
    with pytest.raises(errors.BudgetRefusal):
        gate.run(big, adapter=echo)

    # Two intents, each under the limit, that together evade it: the second
    # is refused by the cumulative window cap.
    slice_a = make_intent(
        ev, consequence_class="C1", objective="evasion slice A",
        payload={"budget": {"cost_usd": 20.0}},
    )
    slice_b = make_intent(
        ev, consequence_class="C1", objective="evasion slice B",
        payload={"budget": {"cost_usd": 20.0}},
    )
    episode = gate.run(slice_a, adapter=echo)  # first slice passes
    assert episode.closed and episode.close_reason == "completed"
    with pytest.raises(errors.BudgetRefusal, match="split-budget evasion"):
        gate.run(slice_b, adapter=echo)
    assert echo.calls == 1  # only the first slice ever executed
    assert w["spine"].verify_chain() is True


def test_08_cross_organ_capability_use_refused(tmp_path):
    w = build_world(tmp_path)
    ev = w["evidence"]
    intent_a = make_intent(ev, organ_id="organ-a")
    intent_b = make_intent(ev, organ_id="organ-b")  # identical except organ

    # The fingerprint binds the organ: a different organ is a different intent.
    assert w["gate"].fingerprint(intent_a) != w["gate"].fingerprint(intent_b)

    # Approval issued for organ A's intent cannot be used by organ B.
    approval_for_a = w["authority"].issue_approval(w["gate"].fingerprint(intent_a))
    with pytest.raises(errors.ApprovalRefusal, match="fingerprint mismatch"):
        w["gate"].run(intent_b, adapter=w["echo"], approval=approval_for_a)
    assert w["echo"].calls == 0
    assert w["spine"].verify_chain() is True


# ---------------------------------------------------------------- 9 & 10


def test_09_duplicate_execution_one_use_grant_reused_refused(tmp_path):
    captured = {}

    def capture(gate, ctx):
        captured["witness"] = ctx.witness

    w = build_world(tmp_path, interceptors={"WITNESS": [capture]})
    gate, echo = w["gate"], w["echo"]
    intent = make_intent(w["evidence"])
    gate.run(intent, adapter=echo, approval=_approved(w, intent))
    assert echo.calls == 1
    witness = captured["witness"]

    # (a) Reusing the same one_use witness/grant at the adapter: refused.
    with pytest.raises(errors.DuplicateExecution):
        echo.execute(witness)

    # (b) Replaying the whole pipeline with a FRESH approval: the durable
    # EXECUTE_BEGIN marker on the spine refuses the double execution.
    approval2 = _approved(w, intent)
    with pytest.raises(errors.DuplicateExecution):
        gate.run(intent, adapter=echo, approval=approval2)
    assert echo.calls == 1
    assert w["spine"].verify_chain() is True


def test_10_forged_receipt_refused(tmp_path):
    w = build_world(tmp_path)
    # Attacker impersonates the registered echo adapter id but signs receipts
    # with their own key. The gate trusts only its registry key.
    evil = EchoAdapter(
        adapter_id="echo-adapter",
        receipt_private_key=generate_private_key(),
        witness_public_key=w["authority"].public_key,
    )
    intent = make_intent(w["evidence"])
    approval = _approved(w, intent)
    with pytest.raises(errors.ReceiptForgery):
        w["gate"].run(intent, adapter=evil, approval=approval)
    assert "GATE_REFUSAL" in [r["kind"] for r in w["spine"].iter()]
    assert w["spine"].verify_chain() is True


# ---------------------------------------------------------------- 11


def test_11_direct_adapter_call_without_witness_refused(tmp_path):
    captured = {}

    def capture(gate, ctx):
        captured["witness"] = ctx.witness

    w = build_world(tmp_path, interceptors={"WITNESS": [capture]})
    echo = w["echo"]

    # (a) Protocol level: witness is a required argument.
    with pytest.raises(TypeError):
        echo.execute()

    # (b) No witness, no execute. No exceptions.
    with pytest.raises(errors.WitnessMissing):
        echo.execute(None)

    # (c) A non-witness object is refused.
    with pytest.raises(errors.WitnessRefusal):
        echo.execute({"intent_fingerprint": "f" * 64})

    # (d) A forged/tampered witness (signature no longer valid) is refused.
    intent = make_intent(w["evidence"])
    w["gate"].run(intent, adapter=echo, approval=_approved(w, intent))
    real_witness = captured["witness"]
    tampered = real_witness.model_copy(update={"exact_target": "https://evil.example"})
    with pytest.raises(errors.WitnessRefusal):
        echo.execute(tampered)
    forged_sig = real_witness.model_copy(update={"witness_signature": "00" * 64})
    with pytest.raises(errors.WitnessRefusal):
        echo.execute(forged_sig)

    assert echo.calls == 1  # only the legitimate gate-driven execution ran


# ---------------------------------------------------------------- 12


class FlakySpine:
    """Simulates spine loss mid-pipeline: appends fail once next_seq reaches
    ``fail_at_seq``; everything else delegates to the real spine."""

    def __init__(self, real: Spine, fail_at_seq: int):
        self._real = real
        self.fail_at_seq = fail_at_seq

    def append(self, model, *, kind=None, refs=None):
        if self._real.next_seq >= self.fail_at_seq:
            raise IOError("simulated spine loss (disk gone)")
        return self._real.append(model, kind=kind, refs=refs)

    def __getattr__(self, name):
        return getattr(self._real, name)


def test_12_restart_during_uncertain_effect_no_double_execution(tmp_path):
    real_spine = Spine(tmp_path / "spine")
    authority = ApprovalService(approver_id="founder")
    evidence = fresh_evidence()
    echo = EchoAdapter(witness_public_key=authority.public_key)
    intent = make_intent(evidence)

    # --- Attempt 1: the spine dies right after execution, before the receipt
    # is sealed (the "uncertain effect" window: did the external effect land?).
    # Spine seqs: 0 intent, 1 decision, 2 approval, 3 grant, 4 witness,
    #             5 EXECUTE_BEGIN, 6 receipt  <- fails here
    flaky = FlakySpine(real_spine, fail_at_seq=6)
    gate1 = Gate(
        POLICY_VERSION, CONSTITUTION_VERSION, authority, flaky,
        evidence_store={evidence.id: evidence},
    )
    gate1.register_adapter(echo.adapter_id, echo.public_key_hex)
    approval1 = authority.issue_approval(gate1.fingerprint(intent))
    with pytest.raises(errors.GateRefusal) as crash:
        gate1.run(intent, adapter=echo, approval=approval1)
    assert crash.value.stage == "SPINE"

    # The effect happened exactly once; the receipt was never sealed.
    assert echo.calls == 1
    assert real_spine.next_seq == 6
    kinds = [r["kind"] for r in real_spine.iter()]
    assert "EXECUTE_BEGIN" in kinds
    assert "ExecutionReceipt" not in kinds
    assert real_spine.verify_chain() is True

    # --- Recovery: spine restored; replay must refuse and must NOT
    # double-execute, and the refusal must be recorded on the spine.
    gate2 = Gate(
        POLICY_VERSION, CONSTITUTION_VERSION, authority, real_spine,
        evidence_store={evidence.id: evidence},
    )
    gate2.register_adapter(echo.adapter_id, echo.public_key_hex)
    approval2 = authority.issue_approval(gate2.fingerprint(intent))  # fresh nonce
    with pytest.raises(errors.DuplicateExecution):
        gate2.run(intent, adapter=echo, approval=approval2)

    # No double execution, ever.
    assert echo.calls == 1

    # The refusal is recorded and the chain still verifies.
    records = list(real_spine.iter())
    refusals = [r for r in records if r["kind"] == "GATE_REFUSAL"]
    assert refusals, "recovery refusal must be recorded on the restored spine"
    assert refusals[-1]["refs"]["stage"] == "REAUTHORIZE"
    assert real_spine.verify_chain() is True
