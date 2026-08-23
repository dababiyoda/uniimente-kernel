"""Witness contract v2: what we believed, how sure, under what authority.

Approved as ONE coordinated migration in FOUNDER-RULING-2026-08-22, closing
GAP-BRIDGE-D-001 and GAP-BRIDGE-G-001 together:

> Create the smallest coherent next-version durable action/witness contract that
> permanently preserves at least: evidence_confidence, consequence_class,
> effective budget/exposure ceiling, and the applicable authority/grant
> reference. [...] After this change the institution must be able to
> reconstruct: what did we believe, how confident were we, under exactly what
> authority did we act, what exposure was permitted, what happened, and were we
> right?

## The shape of the gap, which is smaller than it looked

Both gaps were written as though the institution never knew these facts. It
knew all of them. `policy.engine.Proposal` carries `consequence_class` and
`evidence_confidence`; the gate holds `grant["spending_limit_usd"]` at the
moment it reserves budget. The gate has every value in hand when it calls
`new_witness` — and passes none of them.

So the defect is not ignorance. It is that **the durable record discards what
the decision knew**, which is worse, because it is invisible: the action
succeeds, the ledger looks complete, and the calibration question becomes
unanswerable a moment after it was answerable.

## v1 records are historical truth

The ruling is explicit — *"Old signed records remain historical truth. Do not
rewrite them and do not fabricate values that were never recorded."* Two
mechanisms enforce that here:

1. **Version-aware canonicalisation.** A v1 witness is canonicalised over
   exactly the v1 field set, so its original signature still verifies. Nothing
   is re-signed and no record is migrated in place.
2. **`UNRECORDED` is not a value.** Reading a v1 witness through the v2 lens
   yields `UNRECORDED` for the three new facts — never `0.0`, never `False`,
   never a plausible default. `WitnessReading.unrecorded` names exactly which
   facts are missing, and `calibratable` is False for any record missing
   confidence. A calibration built on imputed confidence would be a calibration
   of the imputation.

## Downgrade is refused in both directions

A v2 record must not be readable as v1 by dropping the fields it added — that
would let a caller launder an unrecorded ceiling into an apparently-valid
historical record. And once a writer is on v2 it may not emit v1. Both are
tested; see `refuse_downgrade`.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from typing import Any, Final

#: The current contract version. v1 records carry no version field at all —
#: their absence is how they are identified, which is why `detect_version`
#: reads absence rather than looking for a `1`.
WITNESS_CONTRACT_VERSION: Final[int] = 2

#: A fact the record never captured. Deliberately a string and deliberately not
#: falsy-in-a-useful-way: `if witness.evidence_confidence:` must not quietly
#: read UNRECORDED as "no confidence", and a numeric sentinel like -1.0 would
#: average into a calibration curve without complaint.
UNRECORDED: Final[str] = "UNRECORDED"

#: Exactly the fields v1 signed, in the order it signed them. Frozen: this tuple
#: describes history and changing it would invalidate every v1 signature in the
#: ledger.
V1_SIGNED_FIELDS: Final[tuple[str, ...]] = (
    "witness_id", "issued_at", "actor", "legal_principal", "action_class",
    "payload_hash", "target", "policy_version", "constitution_hash",
    "grant_id", "capability", "budget_reservation_id", "expected_outcome",
    "evidence_refs",
)

#: What v2 adds. `grant_id` is NOT here: the ruling required the applicable
#: authority reference to be preserved, and v1 already carried it. Re-adding it
#: under a new name would have manufactured the appearance of a fix.
V2_ADDED_FIELDS: Final[tuple[str, ...]] = (
    "witness_version",
    "evidence_confidence",     # how well-evidenced the decision to act was
    "consequence_class",       # what class of consequence was authorised
    "exposure_ceiling_usd",    # the effective ceiling, not a reservation id
    # Added 2026-08-23 under CONTRADICTION-0003 Option A, before v2 emitted a
    # single durable record — the founder's "cleanest versioned contract
    # design" window, which closes the moment the first v2 witness is signed.
    "predicted_success_probability",
)

#: The two confidences, kept apart on purpose. They are the same number for
#: routine actions and *opposite* for a first canary, which is how the fusion
#: went unnoticed for so long.
#:
#: - `evidence_confidence` — "how strong is the evidence that taking this
#:   bounded action is justified?" Governs Gate admission. A high bar is right.
#: - `predicted_success_probability` — "how likely is it to achieve its
#:   preregistered outcome?" Governs nothing. This is the quantity Bridge D
#:   later joins against reality.
#:
#: For CANARY-0001 the first is high and the second is 0.55, and both are
#: honest: the argument for running it is strong precisely *because* the
#: outcome is uncertain. Fused into one field, clearing the floor required
#: writing a success prediction nobody believed — manufacturing the
#: miscalibration the calibration loop exists to detect.
CONFIDENCE_FIELDS: Final[tuple[str, ...]] = (
    "evidence_confidence", "predicted_success_probability")

V2_SIGNED_FIELDS: Final[tuple[str, ...]] = V1_SIGNED_FIELDS + V2_ADDED_FIELDS


class WitnessContractError(ValueError):
    """The record cannot be read under any accepted version."""


class DowngradeRefused(WitnessContractError):
    """A v2 record was asked to present itself as v1, or a v2 writer as v1."""


class TamperDetected(WitnessContractError):
    """The signature does not cover the bytes presented."""


def detect_version(record: dict[str, Any]) -> int:
    """Which contract version this record was written under.

    v1 predates versioning and therefore says nothing. Absence is the signal,
    and it is read as v1 rather than as an error — a reader that rejected every
    historical record would have destroyed the archive it was built to preserve.
    """
    raw = record.get("witness_version")
    if raw is None:
        return 1
    try:
        version = int(raw)
    except (TypeError, ValueError):
        raise WitnessContractError(
            f"witness_version {raw!r} is not an integer") from None
    if version < 1 or version > WITNESS_CONTRACT_VERSION:
        raise WitnessContractError(
            f"witness_version {version} is not a version this kernel knows; "
            f"current contract is v{WITNESS_CONTRACT_VERSION}. A record from the "
            "future is refused rather than read optimistically."
        )
    return version


#: Signed when present, not required to be present.
#:
#: Most actions carry no preregistered prediction — a routine internal write is
#: not an experiment — and requiring the field would force every writer to
#: invent a number for something it never predicted. That is the failure mode
#: `UNRECORDED` exists to prevent, so the field is optional in *presence* and
#: mandatory in *coverage*: when it is there the signature covers it, so adding
#: or stripping it after signing breaks verification.
OPTIONAL_SIGNED_FIELDS: Final[frozenset[str]] = frozenset(
    {"predicted_success_probability"})


def signed_fields(version: int) -> tuple[str, ...]:
    return V1_SIGNED_FIELDS if version == 1 else V2_SIGNED_FIELDS


def canonical_bytes(record: dict[str, Any], *, version: int | None = None) -> bytes:
    """Deterministic bytes for signing, over exactly this version's field set.

    Sorted keys and tight separators, matching `provenance.commit_witness._canon`
    so a v1 record canonicalises here byte-identically to how it was signed.
    That equality is what lets historical signatures keep verifying without
    re-signing anything, and `test_witness_v2_migration.py` asserts it directly
    against the v1 implementation rather than assuming it.

    Fields outside the version's set are excluded, not merely ignored: a v2
    field smuggled into a v1 record must not change its canonical form, or the
    signature would stop covering what the record appears to say.

    `OPTIONAL_SIGNED_FIELDS` may be absent without making the record partial,
    but are covered whenever present — so an absent prediction stays absent
    rather than becoming a fabricated number, and a present one cannot be
    stripped or altered without breaking the signature.
    """
    version = version if version is not None else detect_version(record)
    payload = {name: record[name] for name in signed_fields(version)
               if name in record}
    missing = [n for n in signed_fields(version)
               if n not in record and n not in OPTIONAL_SIGNED_FIELDS]
    if missing:
        raise WitnessContractError(
            f"v{version} record is missing signed fields {missing}; refusing to "
            "canonicalise a partial record"
        )
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      default=str).encode("utf-8")


def sign(record: dict[str, Any], key: bytes, *, version: int | None = None) -> str:
    version = version if version is not None else detect_version(record)
    return "hmac-sha256:" + hmac.new(
        key, canonical_bytes(record, version=version), hashlib.sha256).hexdigest()


def verify(record: dict[str, Any], key: bytes) -> bool:
    """Verify a record of either version against its own canonical form."""
    presented = record.get("signature", "")
    if not presented:
        return False
    version = detect_version(record)
    unsigned = {k: v for k, v in record.items() if k != "signature"}
    try:
        expected = sign(unsigned, key, version=version)
    except WitnessContractError:
        return False
    return hmac.compare_digest(expected, presented)


def refuse_downgrade(record: dict[str, Any], *, target_version: int) -> None:
    """Refuse to present a record under an older contract than it was written.

    The attack this blocks: take a v2 witness whose `exposure_ceiling_usd` is
    inconvenient, drop the v2 fields, and present the remainder as a valid
    historical v1 record. The bytes would canonicalise cleanly and the resulting
    record would look like ordinary history.

    Version negotiation is therefore floor-only. A reader may decline to read a
    version it does not understand; it may never re-label one.
    """
    actual = detect_version(record)
    if target_version < actual:
        raise DowngradeRefused(
            f"record was written under v{actual} and cannot be presented as "
            f"v{target_version}. Dropping the fields a later contract added "
            "would turn an authorised exposure ceiling into an unrecorded one."
        )


def negotiate(record: dict[str, Any], *, accepted: frozenset[int]) -> int:
    """Agree a version, or refuse. Never silently picks a lower one."""
    version = detect_version(record)
    if version not in accepted:
        raise WitnessContractError(
            f"record is v{version}; this reader accepts {sorted(accepted)}. "
            "Refusing rather than reinterpreting."
        )
    return version


@dataclass(frozen=True)
class WitnessReading:
    """One witness, read under either version, with its absences named.

    `unrecorded` is the field that makes this honest. A reading whose
    `evidence_confidence` is `UNRECORDED` is not a reading with low confidence —
    it is a record from before the institution captured confidence at all, and
    the two must never merge into one number.
    """

    witness_id: str
    version: int
    actor: str
    legal_principal: str
    action_class: str
    target: str
    grant_id: str
    capability: str
    expected_outcome: str
    #: v2 facts. Each is either the recorded value or `UNRECORDED`.
    evidence_confidence: float | str
    consequence_class: str
    exposure_ceiling_usd: float | str
    #: The preregistered prediction, which is what calibration measures.
    #: Separate from `evidence_confidence` by CONTRADICTION-0003 Option A.
    predicted_success_probability: float | str = UNRECORDED
    unrecorded: tuple[str, ...] = field(default_factory=tuple)

    @property
    def calibratable(self) -> bool:
        """Whether this record can contribute a (prediction, outcome) pair.

        Keys on `predicted_success_probability`, not `evidence_confidence`.
        That correction is the whole point of CONTRADICTION-0003: calibration
        compares *what we predicted would happen* against what happened.
        `evidence_confidence` answers a different question — whether acting was
        justified — and joining it to an outcome would measure the institution's
        judgement about permission, then call the result a forecast error.

        False for every v1 record, permanently and correctly. The alternative —
        imputing a prediction — would produce a calibration curve measuring the
        imputation, and would do it silently.
        """
        return self.predicted_success_probability != UNRECORDED

    @property
    def admission_basis_recorded(self) -> bool:
        """Whether the record states what the Gate actually admitted it on.

        Distinct from `calibratable` on purpose. A record can be auditable for
        *why it was allowed* while carrying no prediction to score, and a
        reviewer must be able to tell those apart.
        """
        return self.evidence_confidence != UNRECORDED

    @property
    def authority_reconstructable(self) -> bool:
        """Whether the record states the authority and exposure it ran under.

        This is the question GAP-BRIDGE-G-001 asked. `grant_id` alone was never
        enough: it names the permission without stating the ceiling that
        permission carried, so an auditor could see *which* grant and not *how
        much* it allowed.
        """
        return (self.grant_id not in ("", UNRECORDED)
                and self.exposure_ceiling_usd != UNRECORDED
                and self.consequence_class != UNRECORDED)


def read(record: dict[str, Any]) -> WitnessReading:
    """Read a witness of either version. Never fabricates a missing fact."""
    version = detect_version(record)
    absent: list[str] = []

    def v2_field(name: str):
        if version == 1 or name not in record or record[name] is None:
            absent.append(name)
            return UNRECORDED
        return record[name]

    confidence = v2_field("evidence_confidence")
    consequence = v2_field("consequence_class")
    ceiling = v2_field("exposure_ceiling_usd")
    predicted = v2_field("predicted_success_probability")

    return WitnessReading(
        witness_id=record.get("witness_id", ""),
        version=version,
        actor=record.get("actor", ""),
        legal_principal=record.get("legal_principal", ""),
        action_class=record.get("action_class", ""),
        target=record.get("target", ""),
        grant_id=record.get("grant_id", ""),
        capability=record.get("capability", ""),
        expected_outcome=record.get("expected_outcome", ""),
        evidence_confidence=confidence,
        consequence_class=consequence,
        exposure_ceiling_usd=ceiling,
        predicted_success_probability=predicted,
        unrecorded=tuple(absent),
    )


def upgrade_shape(record: dict[str, Any], *, evidence_confidence: float,
                  consequence_class: str, exposure_ceiling_usd: float,
                  predicted_success_probability: float | None = None
                  ) -> dict[str, Any]:
    """Build a v2 record from v1 fields plus values the CALLER actually holds.

    Deliberately not named `migrate`, and deliberately requires every new value
    to be supplied. There is no way to upgrade a historical record with this
    function, because there is nothing to upgrade it *from* — the facts were
    never captured. It exists for a writer that has the values in hand at
    creation time, which is exactly the gate's position.

    A caller tempted to pass zeros here to "migrate the archive" would be
    fabricating evidence, so the signature makes that a deliberate act with
    named arguments rather than a default.

    `predicted_success_probability` is the one optional argument, and its
    default is `None` rather than a number. Most actions carry no preregistered
    prediction — routine internal writes are not experiments — and the honest
    record for those is the absence, not a manufactured 0.5. Passing `None`
    stores nothing, so the field reads back as `UNRECORDED` and
    `calibratable` is False.
    """
    if detect_version(record) != 1:
        raise WitnessContractError("upgrade_shape expects a v1-shaped record")
    upgraded = dict(record)
    upgraded.pop("signature", None)
    upgraded["witness_version"] = WITNESS_CONTRACT_VERSION
    upgraded["evidence_confidence"] = float(evidence_confidence)
    upgraded["consequence_class"] = consequence_class
    upgraded["exposure_ceiling_usd"] = float(exposure_ceiling_usd)
    if predicted_success_probability is not None:
        upgraded["predicted_success_probability"] = \
            float(predicted_success_probability)
    return upgraded
