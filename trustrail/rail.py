"""Small application facade for the proof-to-settlement lifecycle."""
from __future__ import annotations

from trustrail.credentials import CredentialIssuer
from trustrail.models import SettlementAuthorization, VerifierAttestation
from trustrail.settlement import SettlementRouter


class ProofToSettlementRail:
    def __init__(self, issuer: CredentialIssuer, settlements: SettlementRouter):
        self.issuer = issuer
        self.settlements = settlements

    def issue_outcome_credential(self, action_id: str,
                                 attestation: VerifierAttestation):
        return self.issuer.issue(action_id, attestation)

    def create_settlement_intent(self, authorization: SettlementAuthorization,
                                 *, requested_by: str, amount: str):
        return self.settlements.create_intent(
            authorization, requested_by=requested_by, amount=amount
        )

    def commit_settlement(self, intent_id: str):
        """Privileged operation; intentionally absent from the OpenClaw tool surface."""
        return self.settlements.commit(intent_id)

    def credential_status(self, credential_id: str) -> dict:
        credential = self.issuer.verify_integrity(credential_id)
        return credential.as_verifiable_credential(self.issuer.state(credential_id))

    def metrics(self) -> dict[str, int]:
        return self.settlements.metrics()
