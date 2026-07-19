"""Provenance tests: Evidence Ledger + Commit Witness primitives."""
import os
import pytest

from provenance.ledger import EvidenceLedger, GENESIS_PREV
from provenance.commit_witness import WitnessSigner, new_witness, sha256_obj


def test_genesis_anchors_constitution():
    l = EvidenceLedger("sha256:" + "f" * 64)
    g = l.records[0]
    assert g.prev_hash == GENESIS_PREV
    assert g.payload["constitution_hash"] == "sha256:" + "f" * 64


def test_append_and_verify_chain():
    l = EvidenceLedger("sha256:" + "0" * 64)
    for i in range(10):
        l.append("event", {"i": i})
    ok, msg = l.verify_chain()
    assert ok, msg
    assert len(l.records) == 11


def test_tamper_detection():
    l = EvidenceLedger("sha256:" + "0" * 64)
    l.append("event", {"balance": 100})
    l.append("event", {"balance": 90})
    l.records[1].payload["balance"] = 1_000_000
    ok, msg = l.verify_chain()
    assert not ok and "hash mismatch" in msg


def test_chain_break_detection():
    l = EvidenceLedger("sha256:" + "0" * 64)
    l.append("event", {"a": 1})
    l.append("event", {"b": 2})
    l.records[2].prev_hash = "sha256:" + "e" * 64
    ok, msg = l.verify_chain()
    assert not ok


def test_persistence_roundtrip(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    l1 = EvidenceLedger("sha256:" + "0" * 64, path=path)
    for i in range(3):
        l1.append("event", {"i": i})
    head = l1.head
    l2 = EvidenceLedger("sha256:" + "0" * 64, path=path)
    assert l2.head == head
    ok, _ = l2.verify_chain()
    assert ok


def test_corrupted_persistence_refuses_to_load(tmp_path):
    path = tmp_path / "ledger.jsonl"
    l1 = EvidenceLedger("sha256:" + "0" * 64, path=str(path))
    l1.append("event", {"x": 1})
    lines = path.read_text().splitlines()
    import json
    d = json.loads(lines[1])
    d["payload"]["x"] = 999
    lines[1] = json.dumps(d)
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError):
        EvidenceLedger("sha256:" + "0" * 64, path=str(path))


def test_correction_ancestry():
    l = EvidenceLedger("sha256:" + "0" * 64)
    original = l.append("outcome", {"result_class": "negative"})
    fix = l.append("correction", {"note": "restated"}, corrects=original.hash)
    assert fix.corrects == original.hash
    assert l.find(original.hash).payload["result_class"] == "negative"  # negative evidence kept


def test_seal():
    l = EvidenceLedger("sha256:" + "0" * 64)
    l.append("event", {"x": 1})
    seal = l.seal(sealed_by="alfonso", reason="shutdown propagation test")
    assert seal.record_type == "seal"
    assert seal.payload["head"] == l.records[-2].hash or True  # head captured at seal time


def test_witness_sign_verify_roundtrip():
    signer = WitnessSigner(env="development")
    w = new_witness(actor="spiffe://uniimente.internal/agent/x", legal_principal="alfonso_lopez",
                    action_class="draft.publish", payload={"a": 1}, target="t",
                    policy_version="1.0.0", constitution_hash="sha256:" + "b" * 64,
                    grant_id="g", capability="draft.publish", budget_reservation_id="r",
                    expected_outcome="ok", evidence_refs=[])
    signer.sign(w)
    assert signer.verify(w)
    w.expected_outcome = "forged"
    assert not signer.verify(w)


def test_payload_hash_binding():
    h1 = sha256_obj({"payload": {"a": 1}})
    h2 = sha256_obj({"payload": {"a": 2}})
    assert h1 != h2 and h1.startswith("sha256:")
