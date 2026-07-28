"""Reality Aperture — the external consequence boundary.

Authority is a portable, signed, independently verifiable artifact rather than
ambient state inside one engine's process. One issuer signs. Everyone verifies.
Every organ may refuse.

    from aperture import AuthorityIssuer, Aperture, LocalVeto

See docs/authority/CANONICAL_AUTHORITY_ARCHITECTURE.md.
"""
from .certificate import (AuthorizationCertificate, CertificateError,
                          BINDING_FIELDS, build_certificate, hash_payload,
                          hash_evidence_set)
from .keys import (SigningProvider, Ed25519SigningProvider,
                   VerificationRegistry, SigningUnavailable, KeyRevoked,
                   UnknownKey, AlgorithmRefused)
from .issuer import (AuthorityIssuer, Principal, Proposal, ApprovalRecord,
                     BudgetOffice, PolicyRefusal, ApprovalRequired,
                     ScopeRefusal, UnknownEntity, BudgetRefusal,
                     CONSEQUENCE_ORDER)
from .effector import (Aperture, Presenter, LocalVeto, ExecutionReceipt,
                       VerificationRefusal, IdentityMismatch, VersionDrift,
                       Expired, Replay, VetoRefusal, ReadbackMismatch)
from .legacy import (LegacyRecord, classify_legacy_record, attest_migration,
                     refuse_as_authority, LegacyAuthorityRefused,
                     LEGACY_INTEGRITY_CHECKED, LEGACY_UNVERIFIABLE,
                     MIGRATION_ATTESTED, CANONICAL_ASYMMETRIC)

__all__ = [
    "AuthorizationCertificate", "CertificateError", "BINDING_FIELDS",
    "build_certificate", "hash_payload", "hash_evidence_set",
    "SigningProvider", "Ed25519SigningProvider", "VerificationRegistry",
    "SigningUnavailable", "KeyRevoked", "UnknownKey", "AlgorithmRefused",
    "AuthorityIssuer", "Principal", "Proposal", "ApprovalRecord",
    "BudgetOffice", "PolicyRefusal", "ApprovalRequired", "ScopeRefusal",
    "UnknownEntity", "BudgetRefusal", "CONSEQUENCE_ORDER",
    "Aperture", "Presenter", "LocalVeto", "ExecutionReceipt",
    "VerificationRefusal", "IdentityMismatch", "VersionDrift", "Expired",
    "Replay", "VetoRefusal", "ReadbackMismatch",
    "LegacyRecord", "classify_legacy_record", "attest_migration",
    "refuse_as_authority", "LegacyAuthorityRefused",
    "LEGACY_INTEGRITY_CHECKED", "LEGACY_UNVERIFIABLE", "MIGRATION_ATTESTED",
    "CANONICAL_ASYMMETRIC",
]
