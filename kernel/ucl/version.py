"""Content-addressed versions (SPEC-WP02 "Versioning").

``constitution_version = "ucl-" + sha256(canonical concatenation of the five
file contents)[:16]`` — the canonical concatenation is, for each .ucl file in
sorted filename order, ``"<name>\\n<content>\\n"``.

``policy_version = "policy-" + sha256(canonical model dump)[:16]`` — the model
dump is ``Constitution.to_canonical()`` serialized with the WP-01 canonical
JSON (sorted keys, no whitespace; Hard Rule 5 determinism).

Same files produce the same versions, forever: no timestamps, no randomness.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ..crypto.hashing import canonical_json, sha256_hex
from .lexer import UCLError
from .model import Constitution

CONSTITUTION_VERSION_PREFIX = "ucl-"
POLICY_VERSION_PREFIX = "policy-"
_VERSION_HEX_CHARS = 16


def canonical_file_set(files: Iterable[tuple[str, str]]) -> bytes:
    """Canonical concatenation of ``(filename, content)`` pairs, sorted by name."""
    parts = [f"{name}\n{content}\n" for name, content in sorted(files, key=lambda p: p[0])]
    return "".join(parts).encode("utf-8")


def constitution_version(files: Iterable[tuple[str, str]]) -> str:
    """``ucl-<sha256[:16]>`` over the canonical concatenation of the .ucl set."""
    files = list(files)
    if not files:
        raise UCLError("cannot version an empty constitution file set")
    return CONSTITUTION_VERSION_PREFIX + sha256_hex(canonical_file_set(files))[:_VERSION_HEX_CHARS]


def constitution_version_from_dir(path: str | Path) -> str:
    """``constitution_version`` over every *.ucl file in ``path``."""
    root = Path(path)
    if not root.is_dir():
        raise UCLError(f"constitution directory not found: {root}")
    files = [(p.name, p.read_text(encoding="utf-8")) for p in sorted(root.glob("*.ucl"), key=lambda p: p.name)]
    if not files:
        raise UCLError(f"no .ucl files found in {root}")
    return constitution_version(files)


def policy_version(model: Constitution) -> str:
    """``policy-<sha256[:16]>`` over the canonical semantic model dump."""
    if not isinstance(model, Constitution):
        raise UCLError("policy_version requires a Constitution model")
    dump = canonical_json(model.to_canonical()).encode("utf-8")
    return POLICY_VERSION_PREFIX + sha256_hex(dump)[:_VERSION_HEX_CHARS]
