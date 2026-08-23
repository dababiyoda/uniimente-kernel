from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any


def _validate_json_tree(
    value: Any,
    *,
    path: str = "$",
    depth: int = 0,
    seen: set[int] | None = None,
) -> None:
    """Reject Python conveniences that are not unambiguous JSON values."""
    if depth > 100:
        raise ValueError(f"{path}: JSON nesting exceeds 100 levels")
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path}: non-finite JSON number")
        return
    seen = seen if seen is not None else set()
    if isinstance(value, list):
        identity = id(value)
        if identity in seen:
            raise ValueError(f"{path}: circular JSON array")
        seen.add(identity)
        try:
            for index, item in enumerate(value):
                _validate_json_tree(
                    item,
                    path=f"{path}[{index}]",
                    depth=depth + 1,
                    seen=seen,
                )
        finally:
            seen.remove(identity)
        return
    if isinstance(value, dict):
        identity = id(value)
        if identity in seen:
            raise ValueError(f"{path}: circular JSON object")
        seen.add(identity)
        try:
            for key, item in value.items():
                if not isinstance(key, str):
                    raise TypeError(f"{path}: JSON object keys must be strings")
                _validate_json_tree(
                    item,
                    path=f"{path}.{key}",
                    depth=depth + 1,
                    seen=seen,
                )
        finally:
            seen.remove(identity)
        return
    raise TypeError(f"{path}: unsupported JSON value {type(value).__name__}")


def canonical_json(value: Any) -> bytes:
    """Return strict canonical JSON bytes.

    Unsupported objects are refused by ``json.dumps`` instead of being
    stringified.  A content-addressed contract cannot safely depend on an
    object's mutable or implementation-defined ``__str__`` representation.
    """
    _validate_json_tree(value)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def require_aware(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc)


def valid_sha256(value: str) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return False
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)
