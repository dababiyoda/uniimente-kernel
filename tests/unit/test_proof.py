"""Layer 10 acceptance tests: Merkle inclusion proofs over the ledger.

A checkpoint commits to every record before it. Any record's inclusion is
provable in O(log n) without trusting the ledger host; any tampering —
altered record, wrong root, foreign record — fails verification.
"""
import pytest

from provenance.ledger import EvidenceLedger
from provenance.proof import (InclusionProof, LedgerProver, MerkleTree,
                              ProofStep, verify_inclusion)

GENESIS = "sha256:" + "0" * 64


def _ledger(n_events=9):
    l = EvidenceLedger(GENESIS)
    for i in range(n_events):
        l.append("event", {"type": "test.fact", "i": i})
    return l


class TestMerkleTree:
    def test_root_commits_to_all_leaves(self):
        hashes = [f"sha256:{'%064x' % i}" for i in range(8)]
        t1, t2 = MerkleTree(hashes), MerkleTree(hashes)
        assert t1.root == t2.root                       # deterministic
        t3 = MerkleTree(hashes[:-1] + [f"sha256:{'f' * 64}"])
        assert t3.root != t1.root                       # any change moves the root

    def test_odd_leaf_count_promotes_unpaired(self):
        hashes = [f"sha256:{'%064x' % i}" for i in range(7)]
        tree = MerkleTree(hashes)
        for h in hashes:
            assert verify_inclusion(tree.prove(h))      # every leaf provable incl. odd tail

    def test_empty_tree_refused(self):
        with pytest.raises(ValueError):
            MerkleTree([])

    def test_unknown_record_has_no_proof(self):
        tree = MerkleTree([f"sha256:{'0' * 64}"])
        with pytest.raises(ValueError, match="not committed"):
            tree.prove(f"sha256:{'1' * 64}")


class TestLedgerProver:
    def test_checkpoint_anchors_prior_records_on_ledger(self):
        ledger = _ledger(9)
        prover = LedgerProver(ledger)
        before = len(ledger.records)
        cp = prover.checkpoint()
        assert len(ledger.records) == before + 1
        assert cp["covers_records"] == before
        assert cp["root"] and cp["head"] == ledger.records[before - 1].hash
        cps = ledger.by_type("checkpoint")
        assert len(cps) == 1 and cps[0].payload["type"] == "provenance.merkle_checkpoint"

    def test_every_prior_record_provable_against_checkpoint(self):
        ledger = _ledger(9)
        prover = LedgerProver(ledger)
        cp = prover.checkpoint()
        for rec in ledger.records[: cp["covers_records"]]:
            proof = prover.prove(rec.hash, tree_size=cp["covers_records"])
            assert prover.verify(proof, expected_root=cp["root"])

    def test_tampered_record_fails_verification(self):
        ledger = _ledger(9)
        prover = LedgerProver(ledger)
        cp = prover.checkpoint()
        target = ledger.records[5]
        proof = prover.prove(target.hash, tree_size=cp["covers_records"])
        forged = InclusionProof(leaf_record_hash="sha256:" + "e" * 64,
                                leaf_index=proof.leaf_index, tree_size=proof.tree_size,
                                steps=proof.steps, root=proof.root)
        assert not prover.verify(forged, expected_root=cp["root"])

    def test_wrong_root_fails(self):
        ledger = _ledger(5)
        prover = LedgerProver(ledger)
        cp = prover.checkpoint()
        proof = prover.prove(ledger.records[2].hash, tree_size=cp["covers_records"])
        assert not prover.verify(proof, expected_root="0" * 64)

    def test_checkpoint_chain_is_tamper_evident_end_to_end(self):
        ledger = _ledger(6)
        prover = LedgerProver(ledger)
        cp = prover.checkpoint()
        ok, msg = ledger.verify_chain()
        assert ok, msg
        proof = prover.prove(ledger.records[0].hash, tree_size=cp["covers_records"])
        assert verify_inclusion(proof)                  # genesis itself is provable
