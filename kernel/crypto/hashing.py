"""Canonical hashing — Hard Rule 5 (determinism).

All hashes are computed over canonical JSON: sorted keys, no whitespace,
UTF-8 encoded. Same inputs therefore produce byte-identical digests, which is
what makes fingerprints, witnesses and the spine hash chain reproducible.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel


def canonical_json(obj: Any) -> str:
    """Canonical JSON: sorted keys, no whitespace (Hard Rule 5)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_hash(model: Any) -> str:
    """sha256 of the canonical JSON form of a pydantic model or plain mapping."""
    if isinstance(model, BaseModel):
        obj = model.model_dump(mode="json")
    else:
        obj = model
    return sha256_hex(canonical_json(obj).encode("utf-8"))
