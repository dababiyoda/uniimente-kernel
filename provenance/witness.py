"""Witnessed, append-only ledger checkpoints.

Mechanism provenance (see docs/mechanisms/MC-0001-append-only-witness.md):

* Donor: Sigstore's shipped verifier (`@sigstore/verify@4.1.2`,
  dist/tlog/checkpoint.js), examined with REA. It accepts a signed-note
  checkpoint when ANY one signature verifies against a trusted log key
  (`signatures.some(...)`), and verifies RFC 6962 inclusion against the
  checkpoint root. It does not verify consistency between checkpoints.
* Mutation 1 — authority separation: the ledger host's signature never
  counts toward acceptance; only witnesses distinct from the origin do.
* Mutation 2 — quorum instead of any-one: a checkpoint is accepted only with
  cosignatures from at least `threshold` distinct registered witnesses.
* Mutation 3 — failure-to-evidence: a witness never cosigns a checkpoint
  that does not provably extend the last one it cosigned. A refusal is
  retained as `SplitViewEvidence` instead of being discarded.

Recombined effect: once any honest member of a quorum has cosigned a
checkpoint, a ledger host cannot obtain an accepted checkpoint for a
rewritten history, and an auditor needs only (size, root) to check it.

Signatures use per-witness HMAC-SHA256, matching provenance/commit_witness.py.
Limitation: an HMAC verifier holds the witness key, so cosignatures are not
publicly transferable; an asymmetric scheme is a drop-in replacement for
`_mac` once the Kernel adopts one. Witness state is in memory; a persistent
witness must store `last_seen` durably or it reverts to first-use trust.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field

from provenance.consistency import ConsistencyProof, verify_consistency


def checkpoint_note(origin: str, tree_size: int, root: str) -> bytes:
    """Canonical bytes a cosignature covers (transparency-dev note layout)."""
    if "\n" in origin or not origin:
        raise ValueError("origin must be a non-empty single line")
    return f"{origin}\n{tree_size}\n{root}\n".encode()


def _mac(key: bytes, note: bytes) -> str:
    return "hmac-sha256:" + hmac.new(key, note, hashlib.sha256).hexdigest()


@dataclass
class Checkpoint:
    origin: str
    tree_size: int
    root: str
    cosignatures: dict[str, str] = field(default_factory=dict)

    @property
    def note(self) -> bytes:
        return checkpoint_note(self.origin, self.tree_size, self.root)


@dataclass(frozen=True)
class SplitViewEvidence:
    """A witness's retained reason for refusing to cosign."""
    origin: str
    witness_id: str
    seen_size: int
    seen_root: str
    offered_size: int
    offered_root: str
    reason: str
    proof: ConsistencyProof | None


class WitnessRefused(RuntimeError):
    def __init__(self, evidence: SplitViewEvidence):
        super().__init__(evidence.reason)
        self.evidence = evidence


class Witness:
    """Cosigns a checkpoint only if it extends the last one cosigned.

    The first checkpoint seen for an origin is accepted on first use and
    flagged as such in `first_use`; every later one needs a consistency
    proof from the last cosigned size.
    """

    def __init__(self, witness_id: str, key: bytes):
        if not key:
            raise ValueError("witness key required")
        self.witness_id = witness_id
        self._key = key
        self.last_seen: dict[str, tuple[int, str]] = {}
        self.first_use: set[str] = set()
        self.refusals: list[SplitViewEvidence] = []

    def _refuse(self, cp: Checkpoint, seen: tuple[int, str], reason: str,
                proof: ConsistencyProof | None) -> None:
        evidence = SplitViewEvidence(cp.origin, self.witness_id, seen[0], seen[1],
                                     cp.tree_size, cp.root, reason, proof)
        self.refusals.append(evidence)
        raise WitnessRefused(evidence)

    def cosign(self, cp: Checkpoint, proof: ConsistencyProof | None = None) -> str:
        if cp.origin == self.witness_id:
            raise ValueError("a ledger cannot witness itself")
        seen = self.last_seen.get(cp.origin)
        if seen is None:
            self.first_use.add(cp.origin)
        elif cp.tree_size < seen[0]:
            self._refuse(cp, seen, "checkpoint shrinks the log", proof)
        elif cp.tree_size == seen[0]:
            if cp.root != seen[1]:
                self._refuse(cp, seen, "two roots for one tree size (equivocation)", proof)
        else:
            valid = (proof is not None and proof.old_size == seen[0]
                     and proof.new_size == cp.tree_size
                     and verify_consistency(proof, old_root=seen[1], new_root=cp.root))
            if not valid:
                self._refuse(cp, seen, "no valid append-only proof from last cosigned checkpoint", proof)
        self.last_seen[cp.origin] = (cp.tree_size, cp.root)
        signature = _mac(self._key, cp.note)
        cp.cosignatures[self.witness_id] = signature
        return signature


class QuorumPolicy:
    """Accepts a checkpoint only with `threshold` distinct valid cosignatures.

    Unknown signers, the origin itself and invalid signatures count for
    nothing; one witness counts once however many times it appears.
    """

    def __init__(self, witness_keys: dict[str, bytes], threshold: int):
        if threshold < 1:
            raise ValueError("threshold must be at least 1")
        if threshold > len(witness_keys):
            raise ValueError("threshold exceeds registered witnesses")
        self._keys = dict(witness_keys)
        self.threshold = threshold

    def valid_witnesses(self, cp: Checkpoint) -> set[str]:
        valid = set()
        for witness_id, signature in cp.cosignatures.items():
            key = self._keys.get(witness_id)
            if key is None or witness_id == cp.origin:
                continue
            if hmac.compare_digest(_mac(key, cp.note), signature):
                valid.add(witness_id)
        return valid

    def accepts(self, cp: Checkpoint) -> tuple[bool, str]:
        valid = self.valid_witnesses(cp)
        if len(valid) >= self.threshold:
            return True, f"{len(valid)} of {self.threshold} required witnesses cosigned"
        return False, f"only {len(valid)} of {self.threshold} required witnesses cosigned"


__all__ = ["Checkpoint", "QuorumPolicy", "SplitViewEvidence", "Witness",
           "WitnessRefused", "checkpoint_note"]


def capability_genome():
    """Capability Genome for witnessed append-only checkpoints."""
    from capabilities.genome import AuthorityEnvelope, CapabilityGenome
    return CapabilityGenome(
        name="provenance.append_only_witness",
        version="1.0.0",
        description=("Consistency proofs (RFC 9162) between ledger checkpoints, witnesses "
                     "that cosign only append-only extensions, and a k-of-n quorum "
                     "acceptance policy. Detects rewritten history with O(1) auditor state."),
        interface={"inputs": {"checkpoint": "Checkpoint", "proof": "ConsistencyProof"},
                   "outputs": {"cosignature": "str", "accepted": "bool",
                               "refusal": "SplitViewEvidence"}},
        contracts=["evidence"],
        authority=AuthorityEnvelope(max_consequence_class="read_only", budget_ceiling_usd=0.0),
        acceptance_tests=["tests/unit/test_append_only_witness.py",
                          "scripts/experiment_append_only_witness.py",
                          "scripts/sigstore_inclusion_oracle.cjs"],
        failure_modes=[
            "first-use trust: a witness with no prior state cosigns whatever it sees first",
            "quorum of fresh witnesses accepts a fork they never saw the original of",
            "HMAC cosignatures are verifiable only by key holders (not publicly transferable)",
            "in-memory witness state is lost on restart unless persisted",
            "sizes are authenticated by the cosigned note, not by the consistency proof",
        ],
        recovery_path=("Detach: stop consulting QuorumPolicy; existing inclusion proofs and "
                       "hash-chain verification are unchanged. Witness refusals are retained "
                       "as SplitViewEvidence for review."),
    )
