"""Append-only hash-chained JSONL spine — Hard Rule 4 (append-only, fail closed).

Each record is one canonical-JSON line in the segment file:

    {"seq", "prev_hash", "kind", "refs", "payload", "record_hash"}

``record_hash`` is sha256 over the canonical form of the other five fields, and
``prev_hash`` chains every record to its predecessor, so flipping a single byte
anywhere in the segment breaks verify_chain(). There is deliberately NO
update/delete API. Appends are flushed + fsync'd so the spine survives crashes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterator

from ..contracts.base import KernelModel
from ..contracts.institutional import InstitutionalEvent
from ..crypto.hashing import canonical_json, sha256_hex

GENESIS_HASH = "0" * 64
SEGMENT_NAME = "segment-000001.jsonl"
_RECORD_KEYS = ("seq", "prev_hash", "kind", "refs", "payload")


class SpineError(IOError):
    """Raised when the spine cannot fulfill its append-only contract."""


class Spine:
    """Append-only hash-chained JSONL log. No update/delete API — by design."""

    def __init__(self, root: str | os.PathLike):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.segment_path = self.root / SEGMENT_NAME
        self._next_seq = 0
        self._prev_hash = GENESIS_HASH
        if self.segment_path.exists():
            with open(self.segment_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        self._next_seq = int(rec["seq"]) + 1
                        self._prev_hash = str(rec["record_hash"])
                    except (ValueError, KeyError, TypeError) as exc:
                        # A corrupt tail is ambiguous; fail closed (Hard Rule 4).
                        raise SpineError(f"spine segment corrupt: {exc!r}") from exc

    @property
    def next_seq(self) -> int:
        return self._next_seq

    def append(
        self,
        model: KernelModel,
        *,
        kind: str | None = None,
        refs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append a contract to the chain and return the sealed record."""
        if not isinstance(model, KernelModel):
            raise TypeError("the spine stores KernelModel instances only")
        seq = self._next_seq
        if isinstance(model, InstitutionalEvent):
            # spine_seq is assigned by the spine on append, never by callers.
            model = model.model_copy(update={"spine_seq": seq})
        body: dict[str, Any] = {
            "seq": seq,
            "prev_hash": self._prev_hash,
            "kind": kind or type(model).__name__,
            "refs": refs or {},
            "payload": model.model_dump(mode="json"),
        }
        record_hash = sha256_hex(canonical_json(body).encode("utf-8"))
        record = {**body, "record_hash": record_hash}
        line = canonical_json(record)
        try:
            with open(self.segment_path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
                fh.flush()
                os.fsync(fh.fileno())
        except OSError as exc:
            raise SpineError(f"spine append failed: {exc!r}") from exc
        self._next_seq += 1
        self._prev_hash = record_hash
        return record

    def get(self, seq: int) -> dict[str, Any] | None:
        for rec in self.iter():
            if rec["seq"] == seq:
                return rec
        return None

    def iter(self) -> Iterator[dict[str, Any]]:
        if not self.segment_path.exists():
            return
        with open(self.segment_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def verify_chain(self) -> bool:
        """Re-read the segment and re-verify every hash and link.

        Returns False on ANY anomaly: parse errors, sequence gaps, broken
        prev_hash linkage, or record_hash mismatches (fail closed).
        """
        try:
            expected_seq = 0
            prev = GENESIS_HASH
            for rec in self.iter():
                if not isinstance(rec, dict) or set(rec.keys()) != set(_RECORD_KEYS) | {"record_hash"}:
                    return False
                if rec["seq"] != expected_seq:
                    return False
                if rec["prev_hash"] != prev:
                    return False
                body = {k: rec[k] for k in _RECORD_KEYS}
                if sha256_hex(canonical_json(body).encode("utf-8")) != rec["record_hash"]:
                    return False
                prev = rec["record_hash"]
                expected_seq += 1
            return True
        except Exception:
            return False
