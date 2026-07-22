"""UNIIMENTE proof-to-settlement trust rail.

The trust rail begins after the Consequence Gate has recorded an action. It
requires independent verification before issuing a portable outcome
credential, and principal-signed authority before attempting settlement.
"""

from trustrail.credentials import (
    CredentialIssuer,
    HMACSigner,
    TrustRailRefused,
    VerifierRegistry,
    sign_attestation,
)
from trustrail.models import (
    AttestationDecision,
    CredentialState,
    DisputeRecord,
    RealityStatus,
    SettlementAuthorization,
    SettlementIntent,
    SettlementReceipt,
    SettlementState,
    VerifiedOutcomeCredential,
    VerifierAttestation,
)
from trustrail.openclaw import OpenClawTrustBoundary
from trustrail.rail import ProofToSettlementRail
from trustrail.reputation import ScopedReputationLedger
from trustrail.settlement import (
    SandboxSettlementAdapter,
    SettlementAuthorityRegistry,
    SettlementRouter,
    sign_settlement_authorization,
)

__all__ = [
    "AttestationDecision",
    "CredentialIssuer",
    "CredentialState",
    "DisputeRecord",
    "HMACSigner",
    "OpenClawTrustBoundary",
    "ProofToSettlementRail",
    "RealityStatus",
    "SandboxSettlementAdapter",
    "ScopedReputationLedger",
    "SettlementAuthorityRegistry",
    "SettlementAuthorization",
    "SettlementIntent",
    "SettlementReceipt",
    "SettlementRouter",
    "SettlementState",
    "TrustRailRefused",
    "VerifiedOutcomeCredential",
    "VerifierAttestation",
    "VerifierRegistry",
    "sign_attestation",
    "sign_settlement_authorization",
]
