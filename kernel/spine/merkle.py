"""Merkle sealing — supports Hard Rule 4.

seal_day() folds record hashes into a single merkle root and appends it back
to the spine as a DAILY_SEAL event; any later tampering breaks both the seal
and verify_chain().
"""
from __future__ import annotations

from ..contracts.institutional import InstitutionalEvent
from ..crypto.hashing import sha256_hex
from .log import Spine


def merkle_root(leaves: list[str]) -> str:
    """Deterministic binary merkle root over hex-hash leaves."""
    if not leaves:
        return sha256_hex(b"")
    level = list(leaves)
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])  # duplicate odd leaf
        level = [
            sha256_hex(bytes.fromhex(a) + bytes.fromhex(b))
            for a, b in zip(level[0::2], level[1::2])
        ]
    return level[0]


def seal_day(spine: Spine, day: str | None = None, *, actor_id: str = "spine", organ_id: str = "spine") -> str:
    """Seal record hashes into a merkle root and append a DAILY_SEAL event."""
    records = list(spine.iter())
    if day is not None:
        records = [r for r in records if str(r["payload"].get("created_at", "")).startswith(day)]
    root = merkle_root([r["record_hash"] for r in records])
    event = InstitutionalEvent(
        event_type="DAILY_SEAL",
        actor_id=actor_id,
        organ_id=organ_id,
        payload_hash=root,
    )
    spine.append(event, kind="DAILY_SEAL", refs={"day": day or "all", "leaf_count": len(records)})
    return root
