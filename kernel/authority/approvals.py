"""Founder-signed approval service — Hard Rules 2 and 3.

``issue_approval`` creates an Ed25519-signed ApprovalRecord over
fingerprint+approver+nonce. ``verify_approval`` fails closed on: fingerprint
mismatch (Hard Rule 2), bad signature, expiry, unknown approver, or nonce
replay — each nonce is consumed on first successful verification, so a
replayed approval is always refused.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable

from ..contracts.action import ApprovalRecord
from ..crypto import keys as crypto_keys
from ..crypto.hashing import canonical_json
from ..gate.errors import ApprovalRefusal


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ApprovalService:
    """Founder approval authority holding the founder Ed25519 keypair."""

    def __init__(
        self,
        private_key=None,
        *,
        approver_id: str = "founder",
        clock: Callable[[], datetime] | None = None,
    ):
        self._sk = private_key or crypto_keys.generate_private_key()
        self.approver_id = approver_id
        self._clock = clock or _utcnow
        self._used_nonces: set[str] = set()

    @property
    def public_key(self):
        return self._sk.public_key()

    @property
    def public_key_hex(self) -> str:
        return crypto_keys.public_key_to_hex(self._sk.public_key())

    @staticmethod
    def approval_body(intent_fingerprint: str, approver_id: str, nonce: str) -> dict:
        # The signed body is exactly fingerprint+approver+nonce (SPEC).
        return {
            "approver_id": approver_id,
            "intent_fingerprint": intent_fingerprint,
            "nonce": nonce,
        }

    def sign_body(self, body: dict) -> str:
        """Sign an arbitrary canonical-JSON body with the founder key."""
        return crypto_keys.sign(self._sk, canonical_json(body).encode("utf-8"))

    def verify_body(self, body: dict, signature_hex: str) -> bool:
        return crypto_keys.verify(
            self.public_key, canonical_json(body).encode("utf-8"), signature_hex
        )

    def issue_approval(
        self,
        intent_fingerprint: str,
        *,
        ttl_seconds: int = 600,
        approver_id: str | None = None,
    ) -> ApprovalRecord:
        """Founder signs an ApprovalRecord bound to ``intent_fingerprint``."""
        now = self._clock()
        nonce = uuid.uuid4().hex
        apr = approver_id or self.approver_id
        signature = self.sign_body(self.approval_body(intent_fingerprint, apr, nonce))
        return ApprovalRecord(
            intent_fingerprint=intent_fingerprint,
            approver_id=apr,
            signature=signature,
            nonce=nonce,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )

    def verify_approval(
        self,
        approval: ApprovalRecord,
        intent_fingerprint: str,
        *,
        now: datetime | None = None,
    ) -> None:
        """Fail-closed verification; consumes the nonce on success."""
        stage = "APPROVE"
        now = now or self._clock()
        if not isinstance(approval, ApprovalRecord):
            raise ApprovalRefusal("object presented is not an ApprovalRecord", stage=stage)
        if approval.intent_fingerprint != intent_fingerprint:
            raise ApprovalRefusal(
                "approval fingerprint mismatch: this approval does not bind to this intent",
                stage=stage,
            )
        body = self.approval_body(
            approval.intent_fingerprint, approval.approver_id, approval.nonce
        )
        if not self.verify_body(body, approval.signature):
            raise ApprovalRefusal("approval signature invalid (forged approval)", stage=stage)
        if approval.approver_id != self.approver_id:
            raise ApprovalRefusal(f"approver {approval.approver_id!r} not recognized", stage=stage)
        if now >= approval.expires_at:
            raise ApprovalRefusal("approval expired", stage=stage)
        if approval.nonce in self._used_nonces:
            raise ApprovalRefusal("approval nonce already consumed (replay refused)", stage=stage)
        self._used_nonces.add(approval.nonce)
