"""Canonical JSON and ``sha256:`` content references.

The byte form is ``json.dumps(value, sort_keys=True, separators=(",", ":"))``
with the json module defaults otherwise (``ensure_ascii=True``), encoded as
UTF-8. That is exactly what the call sites replaced by this module produced,
so every digest they emit is unchanged.

``default`` is passed through untouched. Call sites that previously refused
non-JSON values (no ``default``) still refuse them; call sites that stringified
them (``default=str``) still do. Do not change a caller's ``default``: doing so
either breaks fail-closed behaviour or changes persisted digests.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Optional

SHA256_PREFIX = "sha256:"
#: ``"sha256:"`` plus 64 lowercase-or-uppercase hex characters.
SHA256_REF_LENGTH = len(SHA256_PREFIX) + 64


def canonical_json(value: Any, *, default: Optional[Callable[[Any], Any]] = None) -> str:
    """Deterministic, key-sorted, whitespace-free JSON text."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=default)


def sha256_ref(value: Any, *, default: Optional[Callable[[Any], Any]] = None) -> str:
    """``"sha256:<hex>"`` over the canonical JSON of ``value``."""
    raw = canonical_json(value, default=default).encode("utf-8")
    return SHA256_PREFIX + hashlib.sha256(raw).hexdigest()


def is_sha256_ref(value: Any) -> bool:
    """True when ``value`` has the shape of a canonical ``sha256:`` reference.

    This is the shape rule the foundry and OMNIMORPH intake checks enforced
    locally (prefix plus total length 71). It checks form, not provenance.
    """
    return isinstance(value, str) and value.startswith(SHA256_PREFIX) and len(value) == SHA256_REF_LENGTH
