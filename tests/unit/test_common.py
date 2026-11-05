"""Shared primitives in common/ keep the exact byte form their callers relied on.

Persisted digests (ledger records, ratified Loom patterns, foundry
architectures) were computed with ``json.dumps(sort_keys=True,
separators=(",", ":"))`` and json's default ``ensure_ascii=True``. These tests
pin that form so a future "cleanup" cannot silently re-hash history.
"""
import hashlib
import json
from datetime import timezone

import pytest

from common import canonical_json, is_sha256_ref, sha256_ref, utc_now, utc_now_iso


VALUE = {"b": [1, 2.5, None], "a": "café", "c": {"z": True, "y": "x"}}


def test_canonical_json_matches_the_historical_inline_form():
    legacy = json.dumps(VALUE, sort_keys=True, separators=(",", ":"))
    assert canonical_json(VALUE) == legacy
    assert canonical_json(VALUE) == '{"a":"caf\\u00e9","b":[1,2.5,null],"c":{"y":"x","z":true}}'


def test_sha256_ref_matches_the_historical_inline_digest():
    legacy = "sha256:" + hashlib.sha256(
        json.dumps(VALUE, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert sha256_ref(VALUE) == legacy
    assert is_sha256_ref(sha256_ref(VALUE))


def test_default_is_passed_through_not_invented():
    class Opaque:
        def __str__(self):
            return "opaque"
    with pytest.raises(TypeError):
        sha256_ref({"x": Opaque()})          # fail closed when the caller did
    assert canonical_json({"x": Opaque()}, default=str) == '{"x":"opaque"}'


@pytest.mark.parametrize("value", [
    None, "", "sha256:", "sha256:" + "a" * 63, "sha256:" + "a" * 65,
    "md5:" + "a" * 67, 7, b"sha256:" + b"a" * 64,
])
def test_is_sha256_ref_rejects_malformed_references(value):
    assert not is_sha256_ref(value)


def test_clock_is_utc_and_uses_z_suffix():
    assert utc_now().tzinfo is timezone.utc
    stamp = utc_now_iso()
    assert stamp.endswith("Z") and "+00:00" not in stamp
