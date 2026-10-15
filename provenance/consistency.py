"""Append-only (consistency) proofs over the evidence ledger's Merkle tree.

`provenance/proof.py` proves that a record is *in* a committed tree. It
cannot prove that a later tree *extends* an earlier one: a ledger host that
rewrites history and re-checkpoints produces a fresh, internally consistent
chain whose inclusion proofs all verify. An auditor holding only an old root
cannot tell.

This module adds the missing primitive from RFC 9162 §2.1.4 (Certificate
Transparency v2): a proof, O(log n) hashes long, that the tree of the first
`m` leaves is a prefix of the tree of the first `n` leaves. An auditor that
keeps 40 bytes (size + root) can check any later checkpoint without the log.

Compatibility: `MerkleTree` in proof.py promotes unpaired nodes and pairs
left-to-right, which yields the RFC 6962 tree shape (split at the largest
power of two below n). Roots are therefore identical; no existing checkpoint
changes. `tests/unit/test_consistency.py` checks this exhaustively for small
trees, and the REA experiment cross-verifies inclusion proofs with
Sigstore's shipped RFC 6962 verifier.
"""
from __future__ import annotations

from dataclasses import dataclass

from provenance.proof import _leaf_hash, _node_hash


def _largest_power_of_two_below(n: int) -> int:
    k = 1
    while k << 1 < n:
        k <<= 1
    return k


def _mth(leaves: list[bytes]) -> bytes:
    """RFC 6962 Merkle Tree Hash over already-hashed leaves."""
    if len(leaves) == 1:
        return leaves[0]
    k = _largest_power_of_two_below(len(leaves))
    return _node_hash(_mth(leaves[:k]), _mth(leaves[k:]))


def merkle_root(record_hashes: list[str]) -> str:
    if not record_hashes:
        raise ValueError("cannot commit an empty record set")
    return _mth([_leaf_hash(h) for h in record_hashes]).hex()


def _subproof(m: int, leaves: list[bytes], complete: bool) -> list[bytes]:
    n = len(leaves)
    if m == n:
        return [] if complete else [_mth(leaves)]
    k = _largest_power_of_two_below(n)
    if m <= k:
        return _subproof(m, leaves[:k], complete) + [_mth(leaves[k:])]
    return _subproof(m - k, leaves[k:], False) + [_mth(leaves[:k])]


@dataclass(frozen=True)
class ConsistencyProof:
    old_size: int
    new_size: int
    path: tuple[str, ...]


def prove_consistency(record_hashes: list[str], old_size: int) -> ConsistencyProof:
    """Prove the first `old_size` records are a prefix of `record_hashes`."""
    n = len(record_hashes)
    if not 0 < old_size <= n:
        raise ValueError(f"old_size must satisfy 0 < old_size <= {n}")
    leaves = [_leaf_hash(h) for h in record_hashes]
    path = _subproof(old_size, leaves, True)
    return ConsistencyProof(old_size=old_size, new_size=n, path=tuple(p.hex() for p in path))


def verify_consistency(proof: ConsistencyProof, *, old_root: str, new_root: str) -> bool:
    """RFC 9162 §2.1.4.2. Written from the verification algorithm, not by
    inverting the generator above, so the two check each other.

    This binds the two roots. It does not on its own authenticate the sizes:
    for some size pairs one path verifies under a neighbouring size claim.
    Sizes are authenticated by the signed/cosigned checkpoint note
    (`provenance.witness.checkpoint_note`), as in Certificate Transparency.
    """
    first, second = proof.old_size, proof.new_size
    if first <= 0 or first > second:
        return False
    try:
        path = [bytes.fromhex(p) for p in proof.path]
        first_hash, second_hash = bytes.fromhex(old_root), bytes.fromhex(new_root)
    except ValueError:
        return False
    if first == second:
        return not path and first_hash == second_hash
    if not path:
        return False
    if first & (first - 1) == 0:  # exact power of two: the old root is a node
        path = [first_hash] + path
    fn, sn = first - 1, second - 1
    while fn & 1:
        fn >>= 1
        sn >>= 1
    fr = sr = path[0]
    for c in path[1:]:
        if sn == 0:
            return False
        if fn & 1 or fn == sn:
            fr = _node_hash(c, fr)
            sr = _node_hash(c, sr)
            if not fn & 1:
                while True:
                    fn >>= 1
                    sn >>= 1
                    if fn & 1 or fn == 0:
                        break
        else:
            sr = _node_hash(sr, c)
        fn >>= 1
        sn >>= 1
    return fr == first_hash and sr == second_hash and sn == 0


__all__ = ["ConsistencyProof", "merkle_root", "prove_consistency", "verify_consistency"]
