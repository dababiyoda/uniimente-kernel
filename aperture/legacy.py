"""Legacy HMAC records: preserved, classified, and permanently unable to authorize.

The previous witness model signed with HMAC-SHA256 under a shared secret. Those
records are institutional memory and are not deleted. They are also not granted
attribution they cannot support.

The distinction that matters:

  An HMAC record can establish that a value is CONSISTENT with a historical
  shared-secret implementation. It cannot establish WHO produced it, because
  every party able to verify was equally able to produce it.

So a legacy record may be readable, integrity-checked, and admitted to the
historical record. It may never authorize a new external effect. That rule is
enforced here by construction: this module exposes no path that returns an
AuthorizationCertificate.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .certificate import CertificateError, canonical_json, rfc3339

# Classification vocabulary.
LEGACY_INTEGRITY_CHECKED = "LEGACY_INTEGRITY_CHECKED"
LEGACY_UNVERIFIABLE = "LEGACY_UNVERIFIABLE"
MIGRATION_ATTESTED = "MIGRATION_ATTESTED"
CANONICAL_ASYMMETRIC = "CANONICAL_ASYMMETRIC"

CLASSIFICATIONS = (LEGACY_INTEGRITY_CHECKED, LEGACY_UNVERIFIABLE,
                   MIGRATION_ATTESTED, CANONICAL_ASYMMETRIC)

# Only this one may authorize a new effect.
AUTHORIZING_CLASSIFICATIONS = frozenset({CANONICAL_ASYMMETRIC})


class LegacyAuthorityRefused(CertificateError):
    """Raised when a legacy record is offered as authority for a new effect."""


@dataclass
class LegacyRecord:
    record_id: str
    body: dict
    signature: str
    classification: str
    integrity_checked: bool = False
    attestation: Optional[dict] = None
    note: str = ""

    def authorizes_new_effect(self) -> bool:
        """Always False for every legacy classification. This is the invariant."""
        return self.classification in AUTHORIZING_CLASSIFICATIONS


def classify_legacy_record(record_id: str, body: dict, signature: str,
                           *, shared_secret: Optional[bytes] = None) -> LegacyRecord:
    """Classify a historical HMAC witness.

    With the historical secret available the record can be integrity-checked and
    becomes LEGACY_INTEGRITY_CHECKED. Without it the record is preserved as
    LEGACY_UNVERIFIABLE. Neither classification confers attribution, and neither
    can authorize anything.
    """
    if shared_secret is None:
        return LegacyRecord(
            record_id=record_id, body=body, signature=signature,
            classification=LEGACY_UNVERIFIABLE, integrity_checked=False,
            note=("historical shared secret unavailable; the record is preserved "
                  "and readable but its integrity cannot be checked"))

    expected = "hmac-sha256:" + hmac.new(
        shared_secret, canonical_json(body), hashlib.sha256).hexdigest()
    ok = hmac.compare_digest(expected, signature)
    return LegacyRecord(
        record_id=record_id, body=body, signature=signature,
        classification=LEGACY_INTEGRITY_CHECKED if ok else LEGACY_UNVERIFIABLE,
        integrity_checked=ok,
        note=("consistent with the historical shared-secret implementation. This "
              "establishes consistency, NOT signer attribution: every party able "
              "to verify this value was equally able to produce it."
              if ok else "does not match the historical secret"))


def attest_migration(record: LegacyRecord, *, reviewer_id: str,
                     statement: str) -> LegacyRecord:
    """Admit a legacy record into the current institutional record.

    The attestation says: the present institution reviewed this historical
    record and admitted it. It deliberately does NOT say that the current signer
    witnessed the original event, because the current signer did not exist then.
    A migration attestation is a statement about the reviewer, not about the past.
    """
    record.attestation = {
        "attested_by": reviewer_id,
        "attested_at": rfc3339(datetime.now(timezone.utc)),
        "statement": statement,
        "claims_original_witness": False,
        "confers_authority": False,
    }
    record.classification = MIGRATION_ATTESTED
    return record


def refuse_as_authority(record: LegacyRecord) -> None:
    """Call this wherever a legacy record might be offered as authority."""
    if not record.authorizes_new_effect():
        raise LegacyAuthorityRefused(
            f"record {record.record_id!r} is classified {record.classification} and "
            "cannot authorize a new external effect. Legacy HMAC records establish "
            "consistency with a historical shared secret, never signer attribution.",
            code="legacy_authority_refused")
