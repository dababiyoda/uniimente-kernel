"""Append-only proofs and witnessed checkpoints: honest paths and attacks."""
from __future__ import annotations

import hashlib
import random

import pytest

from provenance.consistency import (
    ConsistencyProof, merkle_root, prove_consistency, verify_consistency)
from provenance.ledger import EvidenceLedger
from provenance.proof import LedgerProver, MerkleTree
from provenance.witness import Checkpoint, QuorumPolicy, Witness, WitnessRefused

HASHES = ["sha256:" + hashlib.sha256(str(i).encode()).hexdigest() for i in range(160)]


def _cp(origin, hashes, n):
    return Checkpoint(origin=origin, tree_size=n, root=merkle_root(hashes[:n]))


# --- compatibility with the existing tree --------------------------------

def test_roots_match_existing_merkle_tree():
    for n in range(1, 160):
        assert merkle_root(HASHES[:n]) == MerkleTree(HASHES[:n]).root


# --- consistency proofs ----------------------------------------------------

def test_every_honest_proof_verifies():
    for n in range(1, 65):
        for m in range(1, n + 1):
            proof = prove_consistency(HASHES[:n], m)
            assert verify_consistency(proof, old_root=merkle_root(HASHES[:m]),
                                      new_root=merkle_root(HASHES[:n])), (m, n)


def test_proofs_are_logarithmic():
    proof = prove_consistency(HASHES[:160], 37)
    assert len(proof.path) <= 2 * (160).bit_length()


def test_every_rewrite_of_a_committed_record_is_detected():
    for n in range(2, 33):
        for m in range(1, n):
            old_root = merkle_root(HASHES[:m])
            for k in range(m):
                forged = list(HASHES[:n])
                forged[k] = "sha256:" + "f" * 64
                proof = prove_consistency(forged, m)
                assert not verify_consistency(proof, old_root=old_root,
                                              new_root=merkle_root(forged)), (m, n, k)


def test_every_single_hash_corruption_fails():
    for n in range(2, 33):
        for m in range(1, n):
            proof = prove_consistency(HASHES[:n], m)
            for i in range(len(proof.path)):
                path = list(proof.path)
                path[i] = hashlib.sha256(path[i].encode()).hexdigest()
                bad = ConsistencyProof(m, n, tuple(path))
                assert not verify_consistency(bad, old_root=merkle_root(HASHES[:m]),
                                              new_root=merkle_root(HASHES[:n])), (m, n, i)


@pytest.mark.parametrize("mutate", [
    lambda p: ConsistencyProof(p.old_size, p.new_size, p.path[:-1]),
    lambda p: ConsistencyProof(p.old_size, p.new_size, p.path + (p.path[0],)),
    lambda p: ConsistencyProof(p.old_size + 1, p.new_size, p.path),
    lambda p: ConsistencyProof(p.new_size, p.old_size, p.path),
    lambda p: ConsistencyProof(0, p.new_size, p.path),
    lambda p: ConsistencyProof(p.old_size, p.new_size, ("zz",) + p.path[1:]),
])
def test_malformed_proofs_fail(mutate):
    proof = prove_consistency(HASHES[:21], 6)
    assert not verify_consistency(mutate(proof), old_root=merkle_root(HASHES[:6]),
                                  new_root=merkle_root(HASHES[:21]))


def test_sizes_are_bound_by_the_signed_note_not_the_proof():
    """RFC 9162 verification binds the two roots; for some size pairs the
    same path also verifies under a neighbouring claimed size. The size is
    authenticated by the cosigned checkpoint note, so a cosignature over
    (size, root) never transfers to another size."""
    proof = prove_consistency(HASHES[:21], 6)
    relabelled = ConsistencyProof(6, 22, proof.path)
    assert verify_consistency(relabelled, old_root=merkle_root(HASHES[:6]),
                              new_root=merkle_root(HASHES[:21]))
    policy = QuorumPolicy({"wmi": b"k"}, threshold=1)
    cp = _cp("kernel", HASHES, 21)
    Witness("wmi", b"k").cosign(cp)
    assert not policy.accepts(Checkpoint("kernel", 22, cp.root, dict(cp.cosignatures)))[0]


def test_equal_sizes_need_equal_roots_and_empty_path():
    root = merkle_root(HASHES[:9])
    assert verify_consistency(ConsistencyProof(9, 9, ()), old_root=root, new_root=root)
    assert not verify_consistency(ConsistencyProof(9, 9, ()), old_root=root,
                                  new_root=merkle_root(HASHES[1:10]))


# --- the gap this closes ---------------------------------------------------

def _ledger(payloads):
    ledger = EvidenceLedger("sha256:" + "0" * 64)
    for p in payloads:
        ledger.append("event", p)
    return ledger


def test_existing_inclusion_proofs_cannot_detect_a_rewritten_history():
    """Counterfactual baseline: the pre-existing mechanism accepts a fork."""
    honest = _ledger([{"i": i} for i in range(8)])
    old = LedgerProver(honest).checkpoint()
    forged = _ledger([{"i": i} if i != 3 else {"i": "rewritten"} for i in range(12)])
    new = LedgerProver(forged).checkpoint()

    assert forged.verify_chain()[0]
    prover = LedgerProver(forged)
    assert all(prover.verify(prover.prove(r.hash, tree_size=new["covers_records"]),
                             expected_root=new["root"])
               for r in forged.records[:new["covers_records"]])

    hashes = [r.hash for r in forged.records[:new["covers_records"]]]
    proof = prove_consistency(hashes, old["covers_records"])
    assert not verify_consistency(proof, old_root=old["root"], new_root=new["root"])


def test_honest_ledger_growth_is_provably_append_only():
    ledger = _ledger([{"i": i} for i in range(8)])
    old = LedgerProver(ledger).checkpoint()
    for i in range(8, 20):
        ledger.append("event", {"i": i})
    new = LedgerProver(ledger).checkpoint()
    hashes = [r.hash for r in ledger.records[:new["covers_records"]]]
    proof = prove_consistency(hashes, old["covers_records"])
    assert verify_consistency(proof, old_root=old["root"], new_root=new["root"])


# --- witnesses and quorum --------------------------------------------------

KEYS = {"wmi": b"k-wmi", "daleobanks": b"k-dale", "auditor": b"k-aud"}


def _witnesses():
    return {wid: Witness(wid, key) for wid, key in KEYS.items()}


def test_witness_cosigns_honest_extension_and_quorum_accepts():
    ws = _witnesses()
    policy = QuorumPolicy(KEYS, threshold=2)
    first = _cp("kernel", HASHES, 10)
    for w in ws.values():
        w.cosign(first)
    second = _cp("kernel", HASHES, 25)
    proof = prove_consistency(HASHES[:25], 10)
    ws["wmi"].cosign(second, proof)
    ws["auditor"].cosign(second, proof)
    assert policy.accepts(second)[0]
    assert all("kernel" in w.first_use for w in ws.values())


def test_witness_refuses_rewritten_history_and_retains_evidence():
    w = Witness("auditor", KEYS["auditor"])
    w.cosign(_cp("kernel", HASHES, 10))
    forged = list(HASHES[:25])
    forged[4] = "sha256:" + "a" * 64
    cp = Checkpoint("kernel", 25, merkle_root(forged))
    with pytest.raises(WitnessRefused) as exc:
        w.cosign(cp, prove_consistency(forged, 10))
    assert "append-only" in exc.value.evidence.reason
    assert w.refusals[0].offered_root == cp.root
    assert "auditor" not in cp.cosignatures
    assert w.last_seen["kernel"][0] == 10  # refusal does not advance state


@pytest.mark.parametrize("cp,reason", [
    (lambda: Checkpoint("kernel", 10, merkle_root(HASHES[1:11])), "equivocation"),
    (lambda: _cp("kernel", HASHES, 7), "shrinks"),
    (lambda: _cp("kernel", HASHES, 12), "append-only"),  # no proof supplied
])
def test_witness_refuses_equivocation_shrink_and_unproven_growth(cp, reason):
    w = Witness("auditor", KEYS["auditor"])
    w.cosign(_cp("kernel", HASHES, 10))
    with pytest.raises(WitnessRefused, match=reason):
        w.cosign(cp())


def test_proof_from_wrong_base_is_refused():
    w = Witness("auditor", KEYS["auditor"])
    w.cosign(_cp("kernel", HASHES, 10))
    with pytest.raises(WitnessRefused):
        w.cosign(_cp("kernel", HASHES, 20), prove_consistency(HASHES[:20], 9))


def test_ledger_cannot_witness_itself():
    with pytest.raises(ValueError):
        Witness("kernel", b"k").cosign(_cp("kernel", HASHES, 3))


def test_host_signature_and_unknown_signers_count_for_nothing():
    policy = QuorumPolicy(KEYS, threshold=1)
    cp = _cp("wmi", HASHES, 5)
    Witness("wmi-host", KEYS["wmi"]).cosign(cp)  # unknown id, valid-looking key
    cp.cosignatures["wmi"] = cp.cosignatures["wmi-host"]  # origin claiming to witness itself
    assert not policy.accepts(cp)[0]


def test_one_witness_counts_once_and_forgeries_fail():
    policy = QuorumPolicy(KEYS, threshold=2)
    cp = _cp("kernel", HASHES, 5)
    Witness("wmi", KEYS["wmi"]).cosign(cp)
    cp.cosignatures["daleobanks"] = cp.cosignatures["wmi"]  # copied signature
    cp.cosignatures["auditor"] = "hmac-sha256:" + "0" * 64
    assert policy.valid_witnesses(cp) == {"wmi"}
    assert not policy.accepts(cp)[0]


def test_cosignature_does_not_transfer_to_another_root():
    policy = QuorumPolicy(KEYS, threshold=1)
    cp = _cp("kernel", HASHES, 5)
    Witness("wmi", KEYS["wmi"]).cosign(cp)
    moved = Checkpoint("kernel", 5, merkle_root(HASHES[2:7]), dict(cp.cosignatures))
    assert not policy.accepts(moved)[0]


def test_threshold_must_be_satisfiable():
    with pytest.raises(ValueError):
        QuorumPolicy(KEYS, threshold=4)
    with pytest.raises(ValueError):
        QuorumPolicy(KEYS, threshold=0)


def test_randomized_split_view_campaign():
    """Held-out: random sizes and rewrite positions the tests above never use."""
    rng = random.Random(20261014)
    pool = ["sha256:" + hashlib.sha256(f"held-out-{i}".encode()).hexdigest() for i in range(2000)]
    for _ in range(300):
        n = rng.randint(2, 2000)
        m = rng.randint(1, n - 1)
        w = Witness("auditor", b"k")
        w.cosign(Checkpoint("kernel", m, merkle_root(pool[:m])))
        if rng.random() < 0.5:
            w.cosign(Checkpoint("kernel", n, merkle_root(pool[:n])), prove_consistency(pool[:n], m))
        else:
            forged = list(pool[:n])
            forged[rng.randrange(m)] = "sha256:" + hashlib.sha256(str(rng.random()).encode()).hexdigest()
            with pytest.raises(WitnessRefused):
                w.cosign(Checkpoint("kernel", n, merkle_root(forged)), prove_consistency(forged, m))


def test_capability_genome_is_complete_and_read_only():
    from capabilities.genome import GenomeRegistry
    from provenance.witness import capability_genome
    genome = capability_genome()
    assert genome.validate() == []
    assert genome.authority.max_consequence_class == "read_only"
    registry = GenomeRegistry()
    registry.register(genome)


# --- durable witness state ---------------------------------------------------

def test_restarted_witness_keeps_its_view_and_refuses_a_rewrite(tmp_path):
    state = str(tmp_path / "auditor.json")
    Witness("auditor", b"k", state_path=state).cosign(_cp("kernel", HASHES, 10))
    restarted = Witness("auditor", b"k", state_path=state)
    assert restarted.last_seen["kernel"] == (10, merkle_root(HASHES[:10]))
    forged = list(HASHES[:20])
    forged[2] = "sha256:" + "b" * 64
    with pytest.raises(WitnessRefused):
        restarted.cosign(Checkpoint("kernel", 20, merkle_root(forged)), prove_consistency(forged, 10))
    again = Witness("auditor", b"k", state_path=state)
    assert again.refusals and again.refusals[0].offered_root == merkle_root(forged)
    assert again.last_seen["kernel"][0] == 10


def test_witness_without_state_path_forgets_on_restart():
    """Documented failure mode, kept visible: no state_path, no memory."""
    Witness("auditor", b"k").cosign(_cp("kernel", HASHES, 10))
    fresh = Witness("auditor", b"k")
    assert fresh.last_seen == {}


@pytest.mark.parametrize("content", ["{not json", '{"version": 1, "witness_id": "someone-else", "last_seen": {}}'])
def test_corrupt_or_foreign_state_fails_closed(tmp_path, content):
    state = tmp_path / "w.json"
    state.write_text(content)
    with pytest.raises(ValueError):
        Witness("auditor", b"k", state_path=str(state))
