"""provenance.digests reproduces every rule the private copies used, byte for byte.

The copies were not interchangeable (ASCII escaping, NaN, ``default=str``,
spaced separators), so each migrated module is checked against the exact
expression it carried before the migration. A changed byte here would change
digests that persisted records already carry.
"""
from __future__ import annotations

import ast
import hashlib
import importlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from egregore.contracts import canonical_json
from provenance import digests

ROOT = Path(__file__).resolve().parents[2]
VALUES = [
    {"b": 1, "a": [1, 2.5, None, True], "z": {"y": "x"}},
    {"name": "Café ☕ 東京", "n": -0.0},
    [],
    "plain",
]


def _old_ascii(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":")).encode()


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


# module -> (helper name, the expression the module carried before migration)
MIGRATED = {
    "foundry.systems.agent_commerce": ("_canon", _old_ascii),
    "foundry.systems.containers": ("_canon", _old_ascii),
    "foundry.systems.discovery": ("_canon", _old_ascii),
    "foundry.systems.embassy_wire": ("_sha", lambda v: _sha(_old_ascii(v))),
    "foundry.systems.marketplace": ("_canon", _old_ascii),
    "foundry.systems.shell": ("_canon", _old_ascii),
    "foundry.systems.webserver": ("_canon", _old_ascii),
    "foundry.systems.commissioning": ("_sha", lambda v: _sha(_old_ascii(v))),
    "foundry.systems.commons": ("_sha", lambda v: _sha(_old_ascii(v))),
    "foundry.systems.federation": ("_canon", _old_ascii),
    "foundry.systems.promotion": ("_canon", _old_ascii),
    "foundry.systems.repair": ("_digest", lambda v: _sha(json.dumps(
        v, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())),
    "foundry.systems.accounting": ("_hash", lambda v: _sha(json.dumps(v, sort_keys=True).encode())),
    "foundry.completion": ("_hash", lambda v: _sha(json.dumps(v, sort_keys=True, default=str).encode())),
    "greg.institution": ("_canon", lambda v: json.dumps(
        v, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()),
}


@pytest.mark.parametrize("module", sorted(MIGRATED))
@pytest.mark.parametrize("value", VALUES, ids=range(len(VALUES)))
def test_each_migrated_helper_keeps_its_original_bytes(module, value):
    name, original = MIGRATED[module]
    helper = getattr(importlib.import_module(module), name)
    assert helper(value) == original(value)


@pytest.mark.parametrize("module", ["foundry.systems.containers", "foundry.systems.media_engine",
                                    "foundry.systems.repair", "greg.institution"])
def test_byte_digest_helpers_keep_their_bytes(module):
    name = {"foundry.systems.containers": "_digest", "foundry.systems.repair": "_sha256"}.get(module, "_sha")
    helper = getattr(importlib.import_module(module), name)
    assert helper(b"\x00abc\xff") == _sha(b"\x00abc\xff")


def test_the_rules_really_differ_so_none_may_be_swapped_for_another():
    value = {"name": "Café"}
    assert digests.compact_json_bytes(value) != digests.compact_json_bytes(value, ensure_ascii=False)
    assert digests.compact_json_bytes(value) != digests.compact_json_bytes(value, separators=None)
    assert digests.compact_json_bytes(float("nan")) == b"NaN"
    with pytest.raises(ValueError):
        digests.compact_json_bytes(math.nan, allow_nan=False)
    with pytest.raises(TypeError):
        digests.compact_json_bytes({1, 2})
    assert digests.compact_json_bytes({1}, default=str) == b'"{1}"'


def test_the_strict_rule_matches_the_canonical_contract():
    for value in VALUES:
        strict = digests.compact_json_bytes(value, ensure_ascii=False, allow_nan=False)
        assert strict == canonical_json(value).encode("utf-8")


def test_file_and_time_helpers(tmp_path):
    path = tmp_path / "blob"
    path.write_bytes(b"evidence")
    assert digests.sha256_file(path) == _sha(b"evidence")
    stamp = digests.utc_now_z()
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?Z", stamp)
    assert digests.utc_now().tzinfo is timezone.utc
    assert abs(datetime.fromisoformat(stamp.replace("Z", "+00:00")) - digests.utc_now()).total_seconds() < 5


def test_foundry_systems_grow_no_new_private_digest_rules():
    """A new system imports provenance.digests instead of defining its own look-alike rule."""
    forked = []
    for path in sorted((ROOT / "foundry" / "systems").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in {"_canon", "_sha", "_sha256", "_now"}:
                forked.append(f"{path.relative_to(ROOT)}::{node.name}")
    assert not forked, "use provenance.digests: " + ", ".join(forked)
