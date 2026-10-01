"""Resolve evidence references used by the cortex traceability documents.

Forms: ``path`` (file or directory exists), ``path::Class::test`` (each name is
defined in that file), ``path#/json/pointer`` (pointer resolves), and
``path.md#slug`` (a Markdown heading with that GitHub-style slug exists).
"""
from __future__ import annotations

import json
import re
from pathlib import Path


def slug(heading: str) -> str:
    return re.sub(r"\s+", "-", re.sub(r"[^\w\s-]", "", heading.strip().lower()))


def resolve(root: Path, ref: str) -> None:
    """Raise AssertionError naming the reference when it does not resolve."""
    if "::" in ref:
        path, *names = ref.split("::")
        text = (root / path).read_text(encoding="utf-8")
        for name in names:
            assert re.search(rf"^\s*(class|def) {re.escape(name)}\b", text, re.M), f"{ref}: {name} not defined"
        return
    path, _, fragment = ref.partition("#")
    target = root / path
    assert target.exists(), f"{ref}: missing file"
    if not fragment:
        return
    if fragment.startswith("/"):
        node = json.loads(target.read_text(encoding="utf-8"))
        for part in fragment.strip("/").split("/"):
            node = node[int(part)] if isinstance(node, list) else node[part]
        return
    slugs = {slug(h) for h in re.findall(r"^#{1,6}\s+(.+)$", target.read_text(encoding="utf-8"), re.M)}
    assert fragment in slugs, f"{ref}: heading not found"
