"""Layer 10: Merkle inclusion proofs over the evidence ledger.

Doctrine (PROVENANCE): verification must not require trust in the whole
log. Any record's presence in any committed ledger state is provable
with O(log n) sibling hashes against a Merkle root, and the root itself
is anchored on the ledger as a checkpoint record — so a checkpoint
commits to every record before it, and tampering with any one record
invalidates its proof.

Hash scheme: SHA-256. Leaves are ledger record hashes (already SHA-256
of canonical payload); internal nodes hash left||right with domain
separation prefixes so leaves and nodes can never collide.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"


def _leaf_hash(record_hash: str) -> bytes:
    return hashlib.sha256(LEAF_PREFIX + record_hash.encode()).digest()


def _node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(NODE_PREFIX + left + right).digest()


@dataclass
class ProofStep:
    sibling: str        # hex sibling hash
    side: str           # "left" | "right" — where the sibling sits


@dataclass
class InclusionProof:
    leaf_record_hash: str
    leaf_index: int
    tree_size: int
    steps: list[ProofStep]
    root: str           # hex Merkle root this proof targets


class MerkleTree:
    """A binary Merkle tree over ordered record hashes."""

    def __init__(self, record_hashes: list[str]):
        if not record_hashes:
            raise ValueError("cannot commit an empty record set")
        self._leaves = [_leaf_hash(h) for h in record_hashes]
        self._record_hashes = list(record_hashes)
        # build levels bottom-up; odd nodes promote unpaired (no duplication)
        self._levels: list[list[bytes]] = [self._leaves]
        level = self._leaves
        while len(level) > 1:
            nxt = []
            for i in range(0, len(level), 2):
                if i + 1 < len(level):
                    nxt.append(_node_hash(level[i], level[i + 1]))
                else:
                    nxt.append(level[i])              # promote odd leaf
            self._levels.append(nxt)
            level = nxt

    @property
    def root(self) -> str:
        return self._levels[-1][0].hex()

    @property
    def size(self) -> int:
        return len(self._leaves)

    def prove(self, record_hash: str) -> InclusionProof:
        try:
            idx = self._record_hashes.index(record_hash)
        except ValueError:
            raise ValueError("record hash not committed in this tree")
        steps: list[ProofStep] = []
        for level in self._levels[:-1]:
            if idx % 2 == 0 and idx + 1 < len(level):
                steps.append(ProofStep(sibling=level[idx + 1].hex(), side="right"))
            elif idx % 2 == 1:
                steps.append(ProofStep(sibling=level[idx - 1].hex(), side="left"))
            # odd unpromoted node: no sibling at this level
            idx //= 2
        return InclusionProof(leaf_record_hash=record_hash, leaf_index=self._record_hashes.index(record_hash),
                              tree_size=self.size, steps=steps, root=self.root)


def verify_inclusion(proof: InclusionProof) -> bool:
    """Recompute the root from leaf + siblings; equality with proof.root wins."""
    node = _leaf_hash(proof.leaf_record_hash)
    for step in proof.steps:
        sib = bytes.fromhex(step.sibling)
        node = _node_hash(node, sib) if step.side == "right" else _node_hash(sib, node)
    return node.hex() == proof.root


class LedgerProver:
    """Commits a ledger state and proves inclusion against the commitment.

    checkpoint() appends a "merkle_checkpoint" record to the ledger whose
    payload carries the root over all prior record hashes. After the
    checkpoint, inclusion of any prior record is provable without
    trusting the ledger host.
    """

    def __init__(self, ledger):
        self.ledger = ledger

    def _committed_hashes(self, upto: int | None = None) -> list[str]:
        records = self.ledger.records if upto is None else self.ledger.records[:upto]
        return [r.hash for r in records]

    def checkpoint(self) -> dict:
        """Anchor the current ledger state in a new ledger record."""
        hashes = self._committed_hashes()
        tree = MerkleTree(hashes)
        payload = {"type": "provenance.merkle_checkpoint", "root": tree.root,
                   "tree_size": tree.size, "head": self.ledger.head,
                   "covers_records": len(hashes)}
        self.ledger.append("checkpoint", payload)
        return payload

    def prove(self, record_hash: str, *, tree_size: int) -> InclusionProof:
        """Prove inclusion in the tree of the first `tree_size` records."""
        tree = MerkleTree(self._committed_hashes(upto=tree_size))
        return tree.prove(record_hash)

    def verify(self, proof: InclusionProof, *, expected_root: str) -> bool:
        return proof.root == expected_root and verify_inclusion(proof)
