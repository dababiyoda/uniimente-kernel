"""Spine tests: append-only hash chain, tamper detection, merkle sealing.

Hard Rule 4: the spine has no update/delete API, and flipping one byte in the
segment file must make verify_chain() return False.
"""
import pytest

from kernel.contracts.institutional import InstitutionalEvent
from kernel.crypto.hashing import sha256_hex
from kernel.spine import Spine, merkle_root, seal_day


def _event(i: int) -> InstitutionalEvent:
    return InstitutionalEvent(
        event_type="T", actor_id="a", organ_id="o", payload_hash=f"{i:064x}"
    )


def test_append_iter_get_and_spine_seq(tmp_path):
    spine = Spine(tmp_path / "spine")
    recs = [spine.append(_event(i)) for i in range(5)]
    assert [r["seq"] for r in spine.iter()] == [0, 1, 2, 3, 4]
    assert spine.get(3)["seq"] == 3
    assert spine.get(99) is None
    assert spine.verify_chain() is True
    # spine_seq is assigned by the spine on append.
    assert recs[2]["payload"]["spine_seq"] == 2


def test_spine_is_append_only_no_update_delete_api(tmp_path):
    spine = Spine(tmp_path / "s")
    for forbidden in ("update", "delete", "remove", "pop", "clear", "truncate"):
        assert not hasattr(spine, forbidden), forbidden


def test_tamper_detection_flip_one_byte(tmp_path):
    spine = Spine(tmp_path / "s")
    for i in range(4):
        spine.append(_event(i))
    assert spine.verify_chain() is True

    path = spine.segment_path
    data = bytearray(path.read_bytes())
    idx = len(data) // 2
    data[idx] = data[idx] ^ 0x01  # flip one byte in the segment file
    path.write_bytes(bytes(data))

    assert spine.verify_chain() is False


def test_tamper_detection_truncated_segment(tmp_path):
    spine = Spine(tmp_path / "s")
    for i in range(4):
        spine.append(_event(i))
    path = spine.segment_path
    data = path.read_bytes()
    # Cut the tail mid-line: the corrupted final record must fail the chain.
    # (A file cut exactly at a record boundary is a valid prefix of an
    # append-only log by design; sealing via merkle_root/seal_day covers that.)
    path.write_bytes(data[: len(data) - 5])
    assert spine.verify_chain() is False


def test_chain_resumes_after_reopen(tmp_path):
    s1 = Spine(tmp_path / "s")
    s1.append(_event(0))
    s1.append(_event(1))
    s2 = Spine(tmp_path / "s")
    assert s2.next_seq == 2
    rec = s2.append(_event(2))
    assert rec["seq"] == 2
    assert rec["prev_hash"] == s2.get(1)["record_hash"]
    assert s2.verify_chain() is True


def test_merkle_root_deterministic_and_order_sensitive():
    leaves = [sha256_hex(f"leaf{i}".encode()) for i in range(5)]
    assert merkle_root(leaves) == merkle_root(list(leaves))
    assert merkle_root(leaves) != merkle_root(leaves[::-1])
    assert merkle_root([]) == sha256_hex(b"")
    assert merkle_root([leaves[0]]) == leaves[0]


def test_seal_day_appends_seal_and_chain_still_verifies(tmp_path):
    spine = Spine(tmp_path / "s")
    for i in range(3):
        spine.append(_event(i))
    root = seal_day(spine)
    assert isinstance(root, str) and len(root) == 64
    kinds = [r["kind"] for r in spine.iter()]
    assert "DAILY_SEAL" in kinds
    assert spine.verify_chain() is True


def test_append_rejects_non_contract(tmp_path):
    spine = Spine(tmp_path / "s")
    with pytest.raises(TypeError):
        spine.append({"not": "a contract"})
