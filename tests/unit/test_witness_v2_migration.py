"""The v2 witness contract, and the promise that v1 stays true.

FOUNDER-RULING-2026-08-22 approved GAP-BRIDGE-D-001 and GAP-BRIDGE-G-001 as ONE
coordinated migration, and named what it must support: explicit legacy reading,
deterministic signing/canonicalisation, tamper detection, version negotiation,
migration tests, downgrade refusal, and causal-memory ingestion. Each has a
section below.

The constraint that shapes every test here is the ruling's other sentence:
*"Old signed records remain historical truth. Do not rewrite them and do not
fabricate values that were never recorded."* So the load-bearing assertions are
mostly about what the contract REFUSES to produce.
"""
from __future__ import annotations

import json

import pytest

from provenance import commit_witness as v1mod
from provenance import witness_v2 as wc
from provenance.witness_v2 import (
    UNRECORDED,
    DowngradeRefused,
    WitnessContractError,
)

KEY = b"test-witness-key"


def _v1_record() -> dict:
    """A genuine v1 witness, built by the v1 code and signed by the v1 signer.

    Constructed through `provenance.commit_witness` rather than hand-written, so
    these tests measure the real historical format instead of a restatement of
    it that could drift.

    Built through `unsigned()` rather than `asdict()`, because that is the
    shape actually stored and signed. Since the v2 migration the dataclass also
    declares the v2 fields, defaulted to None; `unsigned()` drops them, so a
    witness that sets none of them is byte-identical to a pre-migration record.
    `asdict()` would keep them as explicit nulls and quietly stop describing
    the historical format these tests exist to measure.
    """
    witness = v1mod.new_witness(
        actor="mp-001", legal_principal="Alfonso Lopez",
        action_class="publish", payload={"body": "hello"}, target="sandbox://x",
        policy_version="1.0.0", constitution_hash="sha256:" + "a" * 64,
        grant_id="grant-1", capability="publish.text",
        budget_reservation_id="res-1", expected_outcome="published",
        evidence_refs=["ev-1"])
    signer = v1mod.WitnessSigner(key=KEY)
    signer.sign(witness)
    return {**witness.unsigned(), "signature": witness.signature}


def _v2_record() -> dict:
    """A routine v2 action: admitted on evidence, carrying no prediction.

    Most actions look like this. A routine internal write is not an experiment,
    so it preregisters nothing and `predicted_success_probability` is absent —
    the honest record, rather than a manufactured 0.5.
    """
    record = wc.upgrade_shape(
        {k: v for k, v in _v1_record().items() if k != "signature"},
        evidence_confidence=0.72, consequence_class="reversible",
        exposure_ceiling_usd=25.0)
    record["signature"] = wc.sign(record, KEY)
    return record


def _v2_predicted_record() -> dict:
    """A v2 action that IS an experiment, so it carries a prediction.

    Note the two numbers disagree, deliberately: well-evidenced decision to
    act (0.72), genuinely uncertain outcome (0.55). Under the pre-0003 contract
    that pair could not be expressed at all.
    """
    record = wc.upgrade_shape(
        {k: v for k, v in _v1_record().items() if k != "signature"},
        evidence_confidence=0.72, consequence_class="reversible",
        exposure_ceiling_usd=25.0, predicted_success_probability=0.55)
    record["signature"] = wc.sign(record, KEY)
    return record


# ------------------------------------------------------- explicit legacy read
def test_a_v1_record_is_identified_by_the_absence_of_a_version():
    assert wc.detect_version(_v1_record()) == 1
    assert wc.detect_version(_v2_record()) == 2


def test_v1_signatures_still_verify_under_the_v2_reader():
    """The whole promise of the migration, in one assertion.

    If this fails, the archive has been invalidated and no amount of new
    capability compensates.
    """
    assert wc.verify(_v1_record(), KEY) is True


def test_the_v2_canonical_form_of_a_v1_record_matches_the_v1_implementation():
    """Byte equality against the original signer, not against a restatement.

    Asserting only "the signature verifies" would pass if both sides shared the
    same mistake. This compares the bytes to `commit_witness._canon`, the code
    that actually produced the historical signatures.
    """
    record = _v1_record()
    unsigned = {k: v for k, v in record.items() if k != "signature"}
    assert wc.canonical_bytes(unsigned, version=1) == v1mod._canon(unsigned)


def test_reading_a_v1_record_reports_unrecorded_and_never_a_default():
    """The ruling's hard line: absent facts stay absent.

    A `0.0` here would be indistinguishable from a genuine zero-confidence
    prediction, and would enter a calibration curve as one.
    """
    reading = wc.read(_v1_record())

    assert reading.evidence_confidence == UNRECORDED
    assert reading.consequence_class == UNRECORDED
    assert reading.exposure_ceiling_usd == UNRECORDED
    assert reading.predicted_success_probability == UNRECORDED
    assert set(reading.unrecorded) == {
        "evidence_confidence", "consequence_class", "exposure_ceiling_usd",
        "predicted_success_probability"}

    assert reading.evidence_confidence != 0.0
    assert reading.evidence_confidence is not None
    assert reading.evidence_confidence is not False


def test_the_authority_reference_was_already_there_and_is_not_reinvented():
    """`grant_id` predates v2 and v2 does not duplicate it.

    The ruling required the applicable authority reference to be preserved.
    Adding a second field for a fact v1 already carried would have manufactured
    the appearance of a fix.
    """
    assert "grant_id" in wc.V1_SIGNED_FIELDS
    assert "grant_id" not in wc.V2_ADDED_FIELDS
    assert wc.read(_v1_record()).grant_id == "grant-1"


# ------------------------------------------------ what the institution can ask
def test_a_v2_record_answers_all_five_questions_the_ruling_named():
    """What did we believe, how sure, under what authority, what exposure."""
    reading = wc.read(_v2_record())

    assert reading.expected_outcome == "published"     # what did we believe
    assert reading.evidence_confidence == 0.72         # how confident
    assert reading.grant_id == "grant-1"               # under what authority
    assert reading.exposure_ceiling_usd == 25.0        # what exposure permitted
    assert reading.consequence_class == "reversible"

    # A routine action preregisters no prediction, so the calibration field is
    # legitimately absent. Absent is the honest record; the alternative is
    # every writer inventing a forecast it never made.
    assert reading.unrecorded == ("predicted_success_probability",)
    assert reading.admission_basis_recorded is True
    assert reading.calibratable is False

    # An experiment carries both, and they disagree — which is the shape
    # CONTRADICTION-0003 existed to make expressible.
    experiment = wc.read(_v2_predicted_record())
    assert experiment.evidence_confidence == 0.72
    assert experiment.predicted_success_probability == 0.55
    assert experiment.unrecorded == ()


def test_only_v2_records_are_calibratable_and_v1_never_becomes_so():
    """The Bridge D gap, closed for new records and honestly open for old ones.

    Amended 2026-08-23 (CONTRADICTION-0003): calibration keys on the
    *prediction*, not on the admission confidence. A v2 record without a
    preregistered prediction has nothing to score, and saying so is the point —
    the earlier reading would have joined "we were justified in acting" to an
    outcome and reported the difference as forecast error.
    """
    assert wc.read(_v2_predicted_record()).calibratable is True
    assert wc.read(_v2_record()).calibratable is False
    assert wc.read(_v1_record()).calibratable is False

    # Being unscoreable is not the same as being unauditable.
    assert wc.read(_v2_record()).admission_basis_recorded is True
    assert wc.read(_v1_record()).admission_basis_recorded is False


def test_the_two_confidences_are_carried_separately_and_never_substituted():
    """CONTRADICTION-0003's core claim, asserted on the durable record.

    If a future writer collapses these back into one field, the record can no
    longer distinguish "we were right to try" from "we thought it would work",
    and the calibration loop silently starts measuring the wrong thing.
    """
    record = _v2_predicted_record()

    assert record["evidence_confidence"] != record["predicted_success_probability"]
    assert set(wc.CONFIDENCE_FIELDS) <= set(wc.V2_SIGNED_FIELDS)

    # Both are covered by the signature: neither can be edited after the fact.
    for field_name in wc.CONFIDENCE_FIELDS:
        tampered = dict(record)
        tampered[field_name] = 0.99
        assert wc.verify(tampered, KEY) is False

    # And the optional one cannot be stripped after signing either.
    stripped = {k: v for k, v in record.items()
                if k != "predicted_success_probability"}
    assert wc.verify(stripped, KEY) is False


def test_only_v2_records_can_reconstruct_the_authority_they_ran_under():
    """The Bridge G gap. `grant_id` alone was never sufficient.

    It names which permission applied without stating the ceiling that
    permission carried — an auditor could see *which* grant and not *how much*
    it allowed.
    """
    assert wc.read(_v2_record()).authority_reconstructable is True
    assert wc.read(_v1_record()).authority_reconstructable is False


# ------------------------------------------------------------ tamper detection
@pytest.mark.parametrize("field,value", [
    ("target", "sandbox://elsewhere"),
    ("grant_id", "grant-2"),
    ("evidence_confidence", 0.99),
    ("exposure_ceiling_usd", 1000000.0),
    ("consequence_class", "irreversible"),
    ("expected_outcome", "something else"),
])
def test_altering_any_signed_field_breaks_verification(field, value):
    record = _v2_record()
    assert wc.verify(record, KEY) is True
    record[field] = value
    assert wc.verify(record, KEY) is False


def test_the_new_fields_are_actually_covered_by_the_signature():
    """The migration's whole point is that these are DURABLE.

    A v2 field outside the signed set would be editable after the fact, which
    would make the exposure ceiling a comment rather than a record.
    """
    for name in wc.V2_ADDED_FIELDS:
        assert name in wc.V2_SIGNED_FIELDS


def test_a_wrong_key_does_not_verify():
    assert wc.verify(_v2_record(), b"a-different-key") is False


def test_an_unsigned_record_does_not_verify():
    record = _v2_record()
    del record["signature"]
    assert wc.verify(record, KEY) is False


# --------------------------------------------------------- downgrade refusal
def test_a_v2_record_cannot_be_presented_as_v1():
    """The laundering attack: drop the fields, keep the record.

    An inconvenient exposure ceiling would become an unrecorded one, and the
    result would look like ordinary history.
    """
    with pytest.raises(DowngradeRefused, match="cannot be presented as v1"):
        wc.refuse_downgrade(_v2_record(), target_version=1)


def test_presenting_a_record_at_its_own_version_or_higher_is_fine():
    wc.refuse_downgrade(_v2_record(), target_version=2)
    wc.refuse_downgrade(_v1_record(), target_version=1)
    wc.refuse_downgrade(_v1_record(), target_version=2)


def test_stripping_the_v2_fields_does_not_produce_a_valid_v1_record():
    """Even performing the downgrade by hand fails at verification.

    Two independent barriers: `refuse_downgrade` refuses the request, and the
    signature would not verify anyway because it was computed over the v2 field
    set. The second matters because it holds for code that never calls the
    first.
    """
    stripped = {k: v for k, v in _v2_record().items()
                if k not in wc.V2_ADDED_FIELDS}
    assert wc.detect_version(stripped) == 1
    assert wc.verify(stripped, KEY) is False


# ------------------------------------------------------- version negotiation
def test_negotiation_refuses_a_version_the_reader_does_not_accept():
    with pytest.raises(WitnessContractError, match="this reader accepts"):
        wc.negotiate(_v2_record(), accepted=frozenset({1}))


def test_negotiation_returns_the_records_own_version_never_a_lower_one():
    assert wc.negotiate(_v2_record(), accepted=frozenset({1, 2})) == 2
    assert wc.negotiate(_v1_record(), accepted=frozenset({1, 2})) == 1


def test_a_record_from_a_future_version_is_refused_not_read_optimistically():
    record = _v2_record()
    record["witness_version"] = 99
    with pytest.raises(WitnessContractError, match="not a version this kernel knows"):
        wc.detect_version(record)


def test_a_malformed_version_is_refused():
    record = _v2_record()
    record["witness_version"] = "two"
    with pytest.raises(WitnessContractError, match="not an integer"):
        wc.detect_version(record)


# ------------------------------------------------------------------ migration
def test_upgrade_shape_requires_every_new_value_from_the_caller():
    """There is no way to upgrade a historical record, and that is the design.

    Each new fact must be supplied by a caller that actually holds it. A
    default would let someone "migrate the archive" by fabricating evidence.
    """
    import inspect

    signature = inspect.signature(wc.upgrade_shape)
    for name in ("evidence_confidence", "consequence_class",
                 "exposure_ceiling_usd"):
        assert signature.parameters[name].default is inspect.Parameter.empty, (
            f"{name} has a default; that default would become fabricated evidence"
        )


def test_upgrade_shape_refuses_a_record_that_is_already_v2():
    with pytest.raises(WitnessContractError, match="expects a v1-shaped record"):
        wc.upgrade_shape(_v2_record(), evidence_confidence=0.5,
                         consequence_class="reversible",
                         exposure_ceiling_usd=1.0)


def test_upgrading_drops_the_old_signature_rather_than_carrying_it_forward():
    """A v1 signature over a v2 record would verify nothing and imply much."""
    upgraded = wc.upgrade_shape(
        {k: v for k, v in _v1_record().items() if k != "signature"},
        evidence_confidence=0.5, consequence_class="reversible",
        exposure_ceiling_usd=1.0)
    assert "signature" not in upgraded


def test_a_partial_record_is_refused_rather_than_canonicalised():
    record = _v2_record()
    del record["exposure_ceiling_usd"]
    with pytest.raises(WitnessContractError, match="missing signed fields"):
        wc.canonical_bytes({k: v for k, v in record.items()
                            if k != "signature"}, version=2)


# ------------------------------------------------------ deterministic bytes
def test_canonicalisation_is_stable_across_key_ordering():
    """Signing must not depend on dict insertion order."""
    record = _v2_record()
    unsigned = {k: v for k, v in record.items() if k != "signature"}
    shuffled = dict(reversed(list(unsigned.items())))
    assert wc.canonical_bytes(unsigned) == wc.canonical_bytes(shuffled)
    assert wc.sign(unsigned, KEY) == wc.sign(shuffled, KEY)


def test_a_v2_field_smuggled_into_a_v1_record_does_not_change_its_bytes():
    """Field selection is by version, not by whatever the dict happens to hold.

    Otherwise adding a key to a historical record would silently change its
    canonical form, and its signature would stop covering what it appears to
    say.
    """
    record = _v1_record()
    unsigned = {k: v for k, v in record.items() if k != "signature"}
    smuggled = dict(unsigned, exposure_ceiling_usd=999999.0)
    assert wc.canonical_bytes(smuggled, version=1) == \
        wc.canonical_bytes(unsigned, version=1)


def test_the_canonical_bytes_are_json_with_sorted_keys():
    record = _v2_record()
    unsigned = {k: v for k, v in record.items() if k != "signature"}
    parsed = json.loads(wc.canonical_bytes(unsigned))
    assert list(parsed) == sorted(parsed)
    # Every signed field except the optional one this record does not carry.
    assert set(parsed) == set(wc.V2_SIGNED_FIELDS) - wc.OPTIONAL_SIGNED_FIELDS

    # When it is carried, it is covered.
    predicted = _v2_predicted_record()
    parsed_predicted = json.loads(wc.canonical_bytes(
        {k: v for k, v in predicted.items() if k != "signature"}))
    assert set(parsed_predicted) == set(wc.V2_SIGNED_FIELDS)


# ------------------------------------------------- the audit check discriminates
def test_the_adoption_check_reports_open_today_and_would_flip_when_adopted(
        tmp_path, monkeypatch):
    """A gap check that can only ever say "open" measures nothing.

    `_witness_v2_is_not_emitted` reads the gate's `new_witness(...)` keywords.
    Here it is pointed at two synthetic gates — one that drops the v2 facts and
    one that passes them — so the check is shown to distinguish them rather
    than being trusted to.
    """
    from governance import gap_audit

    def _gate_with(call: str) -> str:
        root = tmp_path / f"root{abs(hash(call))}"
        (root / "policy").mkdir(parents=True)
        (root / "policy" / "consequence_gate.py").write_text(call)
        return str(root)

    v1_gate = _gate_with(
        "witness = new_witness(actor=a, legal_principal=p, action_class=c,\n"
        "                      payload=pl, target=t, grant_id=g)\n")
    v2_gate = _gate_with(
        "witness = new_witness(actor=a, legal_principal=p, action_class=c,\n"
        "                      payload=pl, target=t, grant_id=g,\n"
        "                      evidence_confidence=pr.evidence_confidence,\n"
        "                      consequence_class=pr.consequence_class,\n"
        "                      exposure_ceiling_usd=limit)\n")

    monkeypatch.setattr(gap_audit, "KERNEL_ROOT", v1_gate)
    still_open, detail = gap_audit._witness_v2_is_not_emitted()
    assert still_open is True
    assert "evidence_confidence" in detail

    monkeypatch.setattr(gap_audit, "KERNEL_ROOT", v2_gate)
    still_open, detail = gap_audit._witness_v2_is_not_emitted()
    assert still_open is False, "the check cannot recognise adoption"
    assert "emits witness contract v2" in detail


def test_the_real_gate_emits_the_facts_it_holds():
    """The finding, closed — asserted against the live file, not a restatement.

    This read `still_open is True` until 2026-08-23. CONTRADICTION-0002 Option A
    unblocked `policy/consequence_gate.py` and the Gate now passes the v2 facts
    into `new_witness`, so the probe reports the gap shut.

    The probe is kept and inverted rather than deleted: it is now the
    regression guard. Dropping the keywords again would make this fail, which
    is the only thing standing between "the contract exists" and "the contract
    is used" — the exact proxy failure the gap audit records elsewhere.
    """
    from governance import gap_audit

    still_open, detail = gap_audit._witness_v2_is_not_emitted()
    assert still_open is False
    assert detail == "the gate now emits witness contract v2"
