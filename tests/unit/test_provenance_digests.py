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
    "greg.licensing": ("_digest", lambda v: _sha(json.dumps(
        v, sort_keys=True, separators=(",", ":"), default=str).encode())),
    "capabilities.router": ("_digest", lambda v: _sha(json.dumps(
        v, sort_keys=True, separators=(",", ":"), default=str).encode())),
    "provenance.ledger": ("sha256_json", lambda v: _sha(json.dumps(
        v, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8"))),
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


@pytest.mark.parametrize("module, name, shared", [
    ("greg.backup", "_now", digests.utc_now),
    ("provenance.ledger", "_now", digests.utc_now_z),
])
def test_timestamp_helpers_are_the_shared_one(module, name, shared):
    assert getattr(importlib.import_module(module), name) is shared


def test_default_str_rule_still_stringifies_unknown_objects():
    from provenance.ledger import sha256_json
    assert sha256_json({"at": {1}}) == _sha(b'{"at":"{1}"}')


HELPER_NAMES = {"_canon", "_canonical_json", "_digest", "_hash", "_json_digest", "_now", "_sha", "_sha256"}
HELPER_BODY = re.compile(r"hashlib|json\.dumps|datetime\.now")
# Frozen evaluation runners are pinned by their freezes and are out of scope; tests may hash as they like.
SKIP = ("tests/", "cortex/evaluation/", "docs/collaboration/lineage-archive/")

PINNED = "source hash pinned by a freeze, spec or evidence record; adopt at its next deliberate re-freeze"
SEALED = "runs or is loaded inside a sealed evolution sandbox that may import no other kernel package"
SCRIPT = "standalone script run without the repository on sys.path"
# Every private digest or timestamp helper still defined outside provenance.digests, and why it stays.
# The list may only shrink: a new copy fails, and so does an entry whose copy is gone.
KEPT = {
    "adapters/daleobanks_opportunity.py::_sha256": PINNED,
    "business/commercial_loop.py::_now": PINNED,
    "business/genome.py::_now": PINNED,
    "compiler/ucl_compiler.py::_canon": PINNED + " (and a doctrine-block rule, not JSON)",
    "events/spine.py::_now": PINNED,
    "evolution/capsule.py::_now": SEALED,
    "evolution/migration/engines.py::_now": SEALED,
    "evolution/repair/detector.py::_now": SEALED,
    "evolution/repair/disable.py::_now": SEALED,
    "foundry/systems/federation.py::_digest": "a different format: the HTTP Digest header, base64 'SHA-256='",
    "foundry/territory.py::_now": PINNED,
    "greg/cognition/evolution.py::_sha": PINNED,
    "greg/cognition/evolution_room.py::_sha": PINNED,
    "greg/cognition/genomes/admission.py::_sha": PINNED,
    "greg/cognition/genomes/search.py::_digest": PINNED,
    "greg/cognition/genomes/solvers_d.py::_digest": PINNED,
    "greg/workers.py::_sha": "protected surface: changes need founder or authorized review",
    "identity/machine_passport.py::_now": PINNED,
    "loom/ratify.py::_now": PINNED,
    "memory/affect.py::_now": SEALED,
    "policy/consequence_gate.py::_now": "integrity-protected artifact: changes need INTEGRITY_AUTHORIZE",
    "provenance/commit_witness.py::_now": PINNED,
    "provenance/commit_witness.py::_canon": PINNED,
    "scripts/build_mind_evidence_index.py::_sha": SCRIPT,
    "scripts/check_release_exclusions.py::_digest": SCRIPT,
    "scripts/data_exposure_ledger.py::_canon": SCRIPT,
    "scripts/mind_status.py::_sha": SCRIPT,
    "twins/tribunal.py::_now": SEALED,
}


def _private_helpers():
    found = set()
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(SKIP) or "/." in "/" + rel:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in tree.body:
            if (isinstance(node, ast.FunctionDef) and node.name in HELPER_NAMES
                    and HELPER_BODY.search(ast.unparse(node))):
                found.add(f"{rel}::{node.name}")
    return found


def test_no_new_private_digest_or_timestamp_rules():
    """A new module imports provenance.digests instead of defining its own look-alike rule."""
    new = sorted(_private_helpers() - set(KEPT))
    assert not new, "use provenance.digests (or record why not in KEPT): " + ", ".join(new)


def test_kept_list_only_shrinks():
    gone = sorted(set(KEPT) - _private_helpers())
    assert not gone, "these copies are gone; delete them from KEPT: " + ", ".join(gone)
