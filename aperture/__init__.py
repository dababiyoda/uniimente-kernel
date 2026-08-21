"""Reality Aperture — the external consequence boundary.

Authority is a portable, signed, independently verifiable artifact rather than
ambient state inside one engine's process. One issuer signs. Everyone verifies.
Every organ may refuse.

    from aperture import Aperture, LocalVeto          # client
    from aperture_issuer import AuthorityIssuer     # issuer only

See docs/authority/CANONICAL_AUTHORITY_ARCHITECTURE.md.
"""
from . import manifest  # noqa: F401
from .certificate import (AuthorizationCertificate, CertificateError,
                          BINDING_FIELDS, build_certificate, hash_payload,
                          hash_evidence_set)
from .verification import (VerificationRegistry, KeyRevoked, UnknownKey,
                           AlgorithmRefused, EnvironmentRefusal,
                           current_environment, TEST, DEVELOPMENT, SHADOW,
                           PRODUCTION)
from .effector import (Aperture, Presenter, LocalVeto, ExecutionReceipt,
                       VerificationRefusal, IdentityMismatch, VersionDrift,
                       Expired, Replay, VetoRefusal, ReadbackMismatch)
from .legacy import (LegacyRecord, classify_legacy_record, attest_migration,
                     refuse_as_authority, LegacyAuthorityRefused,
                     LEGACY_INTEGRITY_CHECKED, LEGACY_UNVERIFIABLE,
                     MIGRATION_ATTESTED, CANONICAL_ASYMMETRIC)

__all__ = [
    "manifest",
    "AuthorizationCertificate", "CertificateError", "BINDING_FIELDS",
    "build_certificate", "hash_payload", "hash_evidence_set",
    "VerificationRegistry", "KeyRevoked", "UnknownKey", "AlgorithmRefused",
    "EnvironmentRefusal", "current_environment",
    "TEST", "DEVELOPMENT", "SHADOW", "PRODUCTION",
    "Aperture", "Presenter", "LocalVeto", "ExecutionReceipt",
    "VerificationRefusal", "IdentityMismatch", "VersionDrift", "Expired",
    "Replay", "VetoRefusal", "ReadbackMismatch",
    "LegacyRecord", "classify_legacy_record", "attest_migration",
    "refuse_as_authority", "LegacyAuthorityRefused",
    "LEGACY_INTEGRITY_CHECKED", "LEGACY_UNVERIFIABLE", "MIGRATION_ATTESTED",
    "CANONICAL_ASYMMETRIC",
]
