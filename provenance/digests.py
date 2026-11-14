"""Content digests and timestamps: one implementation, explicit rules.

Many modules used to carry a private ``_canon``/``_sha``/``_now`` copy. Those
copies did not all agree: some escape non-ASCII, some refuse NaN, some stringify
unknown objects. Each difference changes the bytes that get hashed, so the
copies cannot simply be swapped for one strict rule without changing digests
that persisted records already carry.

This module therefore keeps every rule a caller relies on, but spells it out at
the call site as keyword arguments to one function instead of hiding it inside
a look-alike helper. The defaults reproduce ``json.dumps(value, sort_keys=True,
separators=(",", ":")).encode()``, the rule most copies used.

The strict rule for new contracts remains ``egregore.contracts.canonical_json``
(``ensure_ascii=False, allow_nan=False``); ``compact_json_bytes(value,
ensure_ascii=False, allow_nan=False)`` produces the same bytes. This module has
no imports outside the standard library so any organ can depend on it.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

COMPACT = (",", ":")


def compact_json_bytes(value: Any, *, ensure_ascii: bool = True, allow_nan: bool = True,
                       default: Callable[[Any], Any] | None = None,
                       separators: tuple[str, str] | None = COMPACT) -> bytes:
    """Sorted-key UTF-8 JSON. Keyword arguments mean exactly what they mean to ``json.dumps``."""
    return json.dumps(value, sort_keys=True, separators=separators, ensure_ascii=ensure_ascii,
                      allow_nan=allow_nan, default=default).encode("utf-8")


def sha256_tagged(data: bytes) -> str:
    """``sha256:<hex>`` of raw bytes."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    """``sha256:<hex>`` of a file's bytes."""
    return sha256_tagged(Path(path).read_bytes())


def sha256_json(value: Any, **rule: Any) -> str:
    """``sha256:<hex>`` of ``compact_json_bytes(value, **rule)``."""
    return sha256_tagged(compact_json_bytes(value, **rule))


def utc_now() -> datetime:
    """The current instant as an aware UTC datetime."""
    return datetime.now(timezone.utc)


def utc_now_z() -> str:
    """The current instant as ISO-8601 text ending in ``Z``."""
    return utc_now().isoformat().replace("+00:00", "Z")
