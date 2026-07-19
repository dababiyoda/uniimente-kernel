"""UCL abstract syntax tree — Block(kind, label|None, attrs, children).

Mirrors the block structure of the five real constitution/*.ucl files:
top-level named blocks (``constitution "uniimente" { ... }``,
``participant_rights "uniimente" { ... }`` ...) containing attributes
(``key = value``) and nested blocks, which may be anonymous
(``purpose { ... }``, ``state { ... }``) or labelled
(``step "proposal" { ... }``, ``right "safety" { ... }``).

Values are scalars (string, number, bool, null) or lists of scalars — nothing
else exists in the UCL grammar, so nothing else is representable here (fail
closed by construction).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

# Scalar value types permitted by the UCL grammar (SPEC-WP02 "UCL grammar").
Scalar = str | int | float | bool | None


@dataclass(frozen=True)
class Block:
    """One UCL block: ``kind [label] { attributes and/or nested blocks }``."""

    kind: str
    label: str | None
    attrs: dict[str, Any]
    children: tuple["Block", ...] = field(default_factory=tuple)
    # Source positions are diagnostic only: they never affect AST equality.
    line: int = field(default=0, compare=False)
    col: int = field(default=0, compare=False)

    def attr(self, name: str, default: Any = None) -> Any:
        """Attribute value or ``default`` (no implicit invention of content)."""
        return self.attrs.get(name, default)

    def children_of(self, kind: str, label: str | None = None) -> list["Block"]:
        """Direct children of ``kind`` (and ``label`` if given), in order."""
        return [
            child
            for child in self.children
            if child.kind == kind and (label is None or child.label == label)
        ]

    def child(self, kind: str, label: str | None = None) -> "Block | None":
        """First direct child of ``kind`` (and ``label`` if given), or None."""
        found = self.children_of(kind, label)
        return found[0] if found else None

    def walk(self) -> Iterator["Block"]:
        """Yield this block and all descendants, depth first."""
        yield self
        for child in self.children:
            yield from child.walk()
