"""Adapter protocol + bounded base — Hard Rule 1.

``Adapter`` is the protocol: execute(witness) -> ExecutionReceipt. The witness
parameter is REQUIRED; calling execute() without it fails at the type level,
and passing None (or anything that is not a CommitWitness) fails at runtime
with a GateRefusal.

``BoundedAdapter`` additionally re-verifies the witness signature against the
authority public key, checks expiry, and refuses to execute the same witness
twice (one_use semantics) — defense in depth in case the gate is bypassed.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Callable, Protocol, runtime_checkable

from ..contracts.execution import CommitWitness, ExecutionReceipt
from ..crypto import keys as crypto_keys
from ..crypto.hashing import canonical_json
from ..gate import errors

_WITNESS_UNSIGNED = {"schema_version", "id", "created_at", "witness_signature"}
_RECEIPT_UNSIGNED = {"schema_version", "id", "created_at", "signature"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@runtime_checkable
class Adapter(Protocol):
    """Adapter protocol: execute(witness) -> ExecutionReceipt.

    Hard Rule 1: the CommitWitness is mandatory. No witness, no execute.
    """

    adapter_id: str

    def execute(self, witness: CommitWitness) -> ExecutionReceipt: ...


class BoundedAdapter(ABC):
    """Base adapter that can never execute without a verified witness."""

    def __init__(
        self,
        *,
        adapter_id: str,
        witness_public_key,
        receipt_private_key=None,
        clock: Callable[[], datetime] | None = None,
    ):
        self.adapter_id = adapter_id
        self._witness_pk = witness_public_key
        self._receipt_sk = receipt_private_key or crypto_keys.generate_private_key()
        self._clock = clock or _utcnow
        self._spent_witness_ids: set[str] = set()

    @property
    def public_key(self):
        return self._receipt_sk.public_key()

    @property
    def public_key_hex(self) -> str:
        return crypto_keys.public_key_to_hex(self._receipt_sk.public_key())

    @staticmethod
    def witness_signed_body(witness: CommitWitness) -> dict:
        return witness.model_dump(mode="json", exclude=_WITNESS_UNSIGNED)

    def verify_witness(self, witness: CommitWitness) -> CommitWitness:
        """Fail-closed witness verification (raises GateRefusal on doubt)."""
        stage = "EXECUTE"
        if witness is None:
            raise errors.WitnessMissing(
                "Hard Rule 1: no CommitWitness supplied; execution refused", stage=stage
            )
        if not isinstance(witness, CommitWitness):
            raise errors.WitnessRefusal(
                "object presented is not a CommitWitness", stage=stage
            )
        body = self.witness_signed_body(witness)
        if not crypto_keys.verify(
            self._witness_pk, canonical_json(body).encode("utf-8"), witness.witness_signature
        ):
            raise errors.WitnessRefusal(
                "witness signature invalid (forged witness)", stage=stage
            )
        if self._clock() >= witness.expires_at:
            raise errors.WitnessRefusal("commit witness expired", stage=stage)
        if witness.id in self._spent_witness_ids:
            raise errors.DuplicateExecution(
                "witness already spent (one_use grant reused)", stage=stage
            )
        return witness

    def execute(self, witness: CommitWitness) -> ExecutionReceipt:
        """Verify the witness, perform bounded work, return a signed receipt."""
        witness = self.verify_witness(witness)
        provider_response_hash, external_id = self._perform(witness)
        now = self._clock()
        receipt = ExecutionReceipt(
            witness_id=witness.id,
            adapter_id=self.adapter_id,
            external_id=external_id,
            provider_response_hash=provider_response_hash,
            executed_at=now,
            success=True,
            signature="",
        )
        body = receipt.model_dump(mode="json", exclude=_RECEIPT_UNSIGNED)
        signature = crypto_keys.sign(self._receipt_sk, canonical_json(body).encode("utf-8"))
        receipt = receipt.model_copy(update={"signature": signature})
        self._spent_witness_ids.add(witness.id)
        return receipt

    @abstractmethod
    def _perform(self, witness: CommitWitness) -> tuple[str, str | None]:
        """Perform the bounded work; return (provider_response_hash, external_id)."""
