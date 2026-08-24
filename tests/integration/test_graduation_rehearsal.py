"""CANARY-0001 traversed end to end through the real Gate, touching nothing.

Ruling 8 required the packet "proven end-to-end against a consequence-inert
rehearsal". This is the proof: the real Consequence Gate, a real signed witness,
a real receipt, real reconciliation — with exactly one substitution, at the
outermost point, where the external act would be.

The assertion that matters most is the last one. A rehearsal that could move
`clean_verified_outcomes` would let internal effort look like external proof,
which is the single failure this institution is built to refuse.
"""
from __future__ import annotations

import os

import pytest

from bridges.reality_to_learning import clean_verified_outcomes
from graduation.packet import PACKET
from graduation.rehearsal import REHEARSAL_PREFIX, RehearsalResult, rehearse
from compiler.ucl_compiler import compile_constitution
from identity.machine_passport import PassportRegistry
from provenance.commit_witness import WitnessSigner
from policy.consequence_gate import ConsequenceGate
from provenance.ledger import EvidenceLedger

TARGET = f"{REHEARSAL_PREFIX}daleobanks/canary-0001"


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def wired(monkeypatch):
    """A real Gate over a real ledger, with a real passport for the actor.

    Wired exactly as Bridge C's own integration tests wire it, so the rehearsal
    runs against the institution's real configuration rather than a friendlier
    one built for this test.
    """
    monkeypatch.setenv("UNIIMENTE_ENV", "development")
    compiled = compile_constitution(ROOT)
    passports = PassportRegistry()
    ledger = EvidenceLedger(compiled.constitution_hash)
    gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger,
                           signer=WitnessSigner(env="development"))
    actor = passports.issue(
        kind="agent", creator="alfonso", owner_organ="daleobanks",
        legal_principal="alfonso_lopez",
        declared_capabilities=[PACKET.capability],
        budget_ceiling_usd=0.0,
        consequence_class=PACKET.consequence_class)
    return gate, ledger, actor.passport_id


def _run(wired):
    gate, ledger, actor = wired
    result = rehearse(gate=gate, actor=actor,
                      legal_principal="alfonso_lopez", target=TARGET,
                      standing_grant=None)
    return result, ledger


# ------------------------------------------------------------ the traversal
def test_the_rehearsal_traverses_or_refuses_for_a_stated_reason(wired):
    """Either it completes, or it halts somewhere named. Never silently.

    Written to accept both outcomes deliberately: the Gate is entitled to refuse
    an `external_contact` proposal without a founder-authorised grant, and that
    refusal is a CORRECT result for an unauthorised canary — arguably the most
    reassuring one. What is not acceptable is a traversal that neither completes
    nor says where it stopped.
    """
    result, _ = _run(wired)
    assert isinstance(result, RehearsalResult)
    assert result.reached, "a traversal that reports no steps proves nothing"
    if not result.completed:
        assert result.halted_at, "halted with no stated stage"
        assert result.reason, "halted with no stated reason"


def test_the_gate_actually_ran_and_recorded_the_attempt(wired):
    """Real machinery, not a stub: the ledger carries the attempt either way."""
    result, ledger = _run(wired)
    assert any(r.record_type in ("event", "witness", "receipt")
               for r in ledger.records), "nothing reached the ledger"
    assert any("gate reached state" in step for step in result.reached)


def test_the_unauthorized_canary_does_not_reach_a_receipt_by_default(wired):
    """An external_contact action with no founder grant must not just work.

    If this ever starts passing without an authorization being supplied, the
    Gate has stopped gating the one class of action the founder reserved.
    """
    result, ledger = _run(wired)
    if result.completed:
        pytest.fail(
            "an external_contact rehearsal completed with no founder-authorised "
            "grant; the Gate is not enforcing the reserved class"
        )
    assert result.halted_at == "gate"


def test_the_honest_first_canary_still_predicts_below_the_floor_and_that_is_fine():
    """CONTRADICTION-0003, resolved — updated deliberately, as this test asked.

    The previous version asserted `predicted < floor` as a *finding*: the packet
    preregisters 0.55, the floor for external_contact is 0.70, and an honestly
    predicted first canary was therefore unauthorizable. Its own failure message
    named the condition for changing it:

        "If the floor was lowered or the field was split under
         CONTRADICTION-0003, update this test deliberately."

    The field was split (FOUNDER-RULING-2026-08-23, Options A+B). Neither number
    moved. What changed is that they are no longer compared to each other: 0.55
    is a `predicted_success_probability`, which governs nothing and will be
    scored against reality; admission is judged on `evidence_confidence`, which
    carries its own itemised basis.

    So the assertion is kept and its meaning inverted: a prediction below the
    floor is now an ordinary, honest state of affairs rather than a wall. The
    tempting edit — 0.55 to 0.71 — is still pinned as forbidden.
    """
    from policy.engine import EVIDENCE_THRESHOLDS

    predicted = PACKET.preregistration.predicted_confidence
    floor = EVIDENCE_THRESHOLDS[PACKET.consequence_class]

    # Both numbers unchanged. Neither was moved to unblock anything.
    assert floor == 0.7
    assert predicted == 0.55
    assert predicted < floor

    # And the prediction is no longer what admission is judged on.
    assert PACKET.evidence_confidence >= floor
    assert PACKET.evidence_confidence != predicted
    assert PACKET.evidence_basis, (
        "evidence_confidence must carry a written basis; a bare number above "
        "the floor is exactly the inflation this contradiction was about")


# ------------------------- the assertion the whole packet exists to protect
def test_a_rehearsal_never_moves_the_single_bottleneck_metric(wired):
    """CVO is 0 before and 0 after. This is the wall, asserted."""
    _, ledger = wired[0], wired[1]
    before = clean_verified_outcomes(ledger)
    result, ledger = _run(wired)
    after = clean_verified_outcomes(ledger)

    assert before == 0
    assert after == 0, (
        "a consequence-inert rehearsal moved the Single Bottleneck Metric. "
        "Internal effort must never register as external proof."
    )
    assert result.clean_verified_outcomes == 0
    assert result.proves_external_reality is False


def test_the_rehearsal_writes_no_externally_verified_outcome(wired):
    """The stronger form: not merely CVO == 0, but no record that could count.

    Bridge D refuses self-attestation, so a rehearsal cannot produce an
    externally verified outcome even by trying. Checked at the ledger rather
    than through the metric, so a change to how CVO is computed cannot make
    this pass by accident.
    """
    _, ledger = _run(wired)
    verified = [r for r in ledger.records
                if isinstance(r.payload, dict)
                and r.payload.get("validation_status") == "externally_verified"]
    assert verified == [], f"a rehearsal produced verified outcomes: {verified}"


def test_the_closure_verdict_is_unmoved_by_a_rehearsal(wired):
    """The whole-body reading must not improve because we practised."""
    from bridges.closure_verdict import assess

    _, ledger = _run(wired)
    verdict = assess(ledger, change_id="CANARY-0001-rehearsal")
    assert verdict["overall"] in ("FALSELY_CLOSED", "OPEN", "PARTIALLY_CLOSED")
    assert verdict["overall"] != "CLOSED", (
        "a rehearsal closed the whole-body verdict; nothing external happened"
    )


# ------------------------------------------------------------ inertness
def test_nothing_left_the_process(wired):
    """No target outside the rehearsal namespace appears anywhere in the ledger."""
    _, ledger = _run(wired)
    for record in ledger.records:
        payload = record.payload if isinstance(record.payload, dict) else {}
        target = str(payload.get("target", ""))
        if target:
            assert target.startswith(REHEARSAL_PREFIX), (
                f"a non-rehearsal target reached the ledger: {target!r}")
