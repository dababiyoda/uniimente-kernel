"""Evidence Ledger: append-only, hash-chained institutional memory.

The provenance backbone for Layer 3 receipts and Layer 10 cryptographic
institutional memory. Every record carries the hash of its predecessor;
the genesis record anchors the constitution hash, so the entire chain is
bound to the exact doctrine that authorized it.

Negative evidence is kept. Nothing is ever deleted; corrections are new
records with correction ancestry (Layer 10 adds signatures and Merkle
batching on top of this chain).
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

GENESIS_PREV = "sha256:" + "0" * 64


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_json(obj) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


@dataclass
class LedgerRecord:
    seq: int
    ts_utc: str
    record_type: str          # event | witness | receipt | outcome | seal | correction | decision
    payload: dict
    prev_hash: str
    hash: str
    corrects: str | None = None   # hash of the record this corrects (correction ancestry)


class EvidenceLedger:
    """Append-only hash chain. In-memory by default; optional JSONL persistence."""

    def __init__(self, constitution_hash: str, path: str | None = None):
        self.path = path
        self.records: list[LedgerRecord] = []
        genesis_payload = {"kind": "genesis", "constitution_hash": constitution_hash}
        gh = sha256_json({"seq": 0, "payload": genesis_payload, "prev_hash": GENESIS_PREV})
        self.records.append(LedgerRecord(0, _now(), "genesis", genesis_payload, GENESIS_PREV, gh))
        if path and os.path.exists(path):
            self._load(path)
        elif path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(self.records[0]), default=str) + "\n")

    @property
    def head(self) -> str:
        return self.records[-1].hash

    def append(self, record_type: str, payload: dict, *, corrects: str | None = None) -> LedgerRecord:
        seq = len(self.records)
        prev = self.head
        body = {"seq": seq, "record_type": record_type, "payload": payload,
                "prev_hash": prev, "corrects": corrects}
        h = sha256_json(body)
        rec = LedgerRecord(seq, _now(), record_type, payload, prev, h, corrects)
        self.records.append(rec)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(rec), default=str) + "\n")
        return rec

    def seal(self, *, sealed_by: str, reason: str) -> LedgerRecord:
        """Seal the head (shutdown propagation step 5). Returns the seal record."""
        return self.append("seal", {"sealed_by": sealed_by, "reason": reason, "head": self.head})

    def verify_chain(self) -> tuple[bool, str]:
        """Independently reconstruct and verify every link (evidence closure)."""
        for i, rec in enumerate(self.records):
            if rec.seq != i:
                return False, f"sequence break at {i}"
            if i == 0:
                if rec.prev_hash != GENESIS_PREV:
                    return False, "genesis prev_hash corrupted"
                continue
            if rec.prev_hash != self.records[i - 1].hash:
                return False, f"chain break at seq {i}"
            body = {"seq": rec.seq, "record_type": rec.record_type, "payload": rec.payload,
                    "prev_hash": rec.prev_hash, "corrects": rec.corrects}
            if sha256_json(body) != rec.hash:
                return False, f"payload hash mismatch at seq {i}"
        return True, f"chain intact: {len(self.records)} records"

    def find(self, record_hash: str) -> LedgerRecord | None:
        for r in self.records:
            if r.hash == record_hash:
                return r
        return None

    def by_type(self, record_type: str) -> list[LedgerRecord]:
        return [r for r in self.records if r.record_type == record_type]

    def _load(self, path: str) -> None:
        # Persistence is a convenience, never the source of truth: after
        # loading, the whole chain is re-verified or the ledger refuses.
        loaded = []
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    d = json.loads(line)
                    loaded.append(LedgerRecord(**d))
        if loaded:
            self.records = loaded
            ok, msg = self.verify_chain()
            if not ok:
                raise ValueError(f"ledger at {path} failed verification on load: {msg}")
