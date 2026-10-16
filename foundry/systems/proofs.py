"""#6 Cryptographic proof primitives: hashes, Merkle inclusion, signatures (Kernel provenance/proof.py).

Proves a record was part of a committed set without revealing the rest, and
binds the committed root to a key. Negative evidence retained: an attacker can
build a self-consistent proof for their own root, so a proof only means
something against a root the verifier trusts (signed, anchored or witnessed).
External time anchoring is greg/anchor.py (RFC 3161), tested separately.
"""
from __future__ import annotations

import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _h(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def prove_and_verify(records: list[str], member: str, trusted_root: str) -> dict:
    from provenance.proof import MerkleTree, verify_inclusion
    proof = MerkleTree([_h(r) for r in records]).prove(_h(member))
    return {"self_consistent": verify_inclusion(proof), "matches_trusted_root": proof.root == trusted_root}


QUERY_OPS = {"root": lambda a, r: {"root": __import__("provenance.proof", fromlist=["MerkleTree"]).MerkleTree(
    [_h(x) for x in a["records"]]).root}}
APPLY_OPS: dict = {}


def exercise(root) -> dict:
    from provenance.proof import MerkleTree, ProofStep, verify_inclusion
    records = [f"receipt {n}: delivered brief {n}" for n in range(1, 8)]
    tree = MerkleTree([_h(r) for r in records])
    all_members_prove = all(verify_inclusion(tree.prove(_h(r))) and tree.prove(_h(r)).root == tree.root for r in records)
    proof = tree.prove(_h(records[3]))
    proof.steps[0] = ProofStep(sibling="00" * 32, side=proof.steps[0].side)
    tampered_sibling_fails = not verify_inclusion(proof)
    try:
        tree.prove(_h("never committed"))
        non_member_refused = False
    except ValueError:
        non_member_refused = True
    forged_tree = MerkleTree([_h("forged receipt")] + [_h(r) for r in records[1:]])
    forged = forged_tree.prove(_h("forged receipt"))
    forged_self_consistent = verify_inclusion(forged)
    forged_rejected_by_trusted_root = forged.root != tree.root
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))       # fixed test key: deterministic
    signature = key.sign(bytes.fromhex(tree.root))
    public = key.public_key()
    public.verify(signature, bytes.fromhex(tree.root))
    try:
        public.verify(signature, bytes.fromhex(forged_tree.root))
        substituted_root_verifies = True
    except InvalidSignature:
        substituted_root_verifies = False
    return {"root": tree.root, "all_members_prove": all_members_prove, "tampered_sibling_fails": tampered_sibling_fails,
            "non_member_refused": non_member_refused, "forged_proof_self_consistent": forged_self_consistent,
            "forged_rejected_by_trusted_root": forged_rejected_by_trusted_root,
            "signed_root_substitution_detected": not substituted_root_verifies}
