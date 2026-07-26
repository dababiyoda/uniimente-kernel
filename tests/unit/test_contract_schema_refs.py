"""Contract schemas must not contain dangling document-local references."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[2]


def _local_refs(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/"):
            yield ref
        for child in value.values():
            yield from _local_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from _local_refs(child)


def _resolve_pointer(document: Any, ref: str) -> Any:
    current = document
    for encoded in ref.removeprefix("#/").split("/"):
        segment = encoded.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(segment)]
        else:
            current = current[segment]
    return current


def test_every_contract_local_reference_resolves():
    schemas: list[tuple[Path, Any]] = []
    for path in sorted((ROOT / "contracts").rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(document, dict) and "$schema" in document:
            schemas.append((path, document))
    assert schemas

    broken: list[str] = []
    for path, document in schemas:
        for ref in _local_refs(document):
            try:
                _resolve_pointer(document, ref)
            except (KeyError, IndexError, TypeError, ValueError):
                broken.append(f"{path.relative_to(ROOT)} -> {ref}")

    assert not broken, "dangling local schema references:\n" + "\n".join(broken)
