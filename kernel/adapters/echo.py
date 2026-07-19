"""EchoAdapter — simulated bounded research adapter (no network, no side effects).

Hard Rule 1 applies exactly as for any adapter: it executes only against a
current, verified CommitWitness.

Simulation semantics: the provider's response document IS the outcome
attestation, so provider_response_hash = sha256(canonical(expected_outcome)).
A perfectly simulated execution therefore reconciles against the expected
outcome; any adapter returning a different outcome hash fails RECONCILE.
"""
from __future__ import annotations

from ..contracts.execution import CommitWitness
from ..crypto.hashing import canonical_json, sha256_hex
from .base import BoundedAdapter


class EchoAdapter(BoundedAdapter):
    """Simulated bounded research adapter."""

    def __init__(self, *, adapter_id: str = "echo-adapter", **kwargs):
        super().__init__(adapter_id=adapter_id, **kwargs)
        self.calls = 0
        self.executed_witness_ids: list[str] = []

    def _perform(self, witness: CommitWitness) -> tuple[str, str | None]:
        self.calls += 1
        self.executed_witness_ids.append(witness.id)
        # Simulated bounded research on witness.exact_target: no network.
        response_hash = sha256_hex(canonical_json(witness.expected_outcome).encode("utf-8"))
        return response_hash, f"echo-{witness.id[:12]}"
