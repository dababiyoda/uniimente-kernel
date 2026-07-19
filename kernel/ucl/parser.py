"""UCL recursive-descent parser — token stream -> Document(list[Block]).

Grammar (SPEC-WP02 "UCL grammar", derived from the five real .ucl files)::

    document  := block* EOF
    block     := IDENT [STRING] '{' body '}'
    body      := statement*
    statement := attribute | block
    attribute := IDENT '=' value
    value     := STRING | NUMBER | BOOL | NULL | '[' [value (',' value)* [',']] ']'

Attributes end at the end of their single value, so one-line nested blocks
such as ``state { name = "normal" external_effects = "permitted_under_grants" }``
parse unambiguously without any newline sensitivity.

Constitutional clause: kernel_invariant ``on_violation = "refuse_and_escalate"``
— every syntax error (missing '}', bad value, duplicate attribute, nested
list, non-scalar list item) raises UCLError with line/col. The parser never
recovers or guesses: ambiguity fails closed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from .ast import Block
from .lexer import Token, UCLError, lex

_VALUE_KINDS = ("STRING", "NUMBER", "BOOL", "NULL")
_SCALAR_KINDS = _VALUE_KINDS  # lists may contain scalars only


class Document:
    """One parsed .ucl file: an ordered list of top-level Blocks."""

    def __init__(self, blocks: list[Block], *, filename: str = "<string>"):
        self.blocks: list[Block] = list(blocks)
        self.filename = filename

    def find_all(self, kind: str, label: str | None = None) -> list[Block]:
        """Top-level blocks of ``kind`` (and ``label`` if given), in order."""
        return [
            block
            for block in self.blocks
            if block.kind == kind and (label is None or block.label == label)
        ]

    def find(self, kind: str, label: str | None = None) -> Block | None:
        """First top-level block of ``kind`` (and ``label`` if given), or None."""
        found = self.find_all(kind, label)
        return found[0] if found else None

    def __iter__(self) -> Iterator[Block]:
        return iter(self.blocks)

    def __len__(self) -> int:
        return len(self.blocks)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Document) and self.blocks == other.blocks

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Document({self.blocks!r}, filename={self.filename!r})"


class Parser:
    """Recursive-descent parser over the lexer's token stream."""

    def __init__(self, tokens: list[Token], *, filename: str = "<string>"):
        self._tokens = tokens
        self._pos = 0
        self._filename = filename

    # ------------------------------------------------------------- utilities

    def _peek(self, ahead: int = 0) -> Token:
        return self._tokens[min(self._pos + ahead, len(self._tokens) - 1)]

    def _next(self) -> Token:
        token = self._tokens[self._pos]
        if self._pos < len(self._tokens) - 1:
            self._pos += 1
        return token

    def _error(self, message: str, token: Token) -> UCLError:
        return UCLError(message, line=token.line, col=token.col, filename=self._filename)

    def _expect(self, kind: str, what: str) -> Token:
        token = self._peek()
        if token.kind != kind:
            raise self._error(
                f"expected {what}, found {token.kind} {token.value!r}", token
            )
        return self._next()

    # ---------------------------------------------------------------- grammar

    def parse_document(self) -> Document:
        blocks: list[Block] = []
        while self._peek().kind != "EOF":
            blocks.append(self._parse_block())
        return Document(blocks, filename=self._filename)

    def _parse_block(self) -> Block:
        keyword = self._expect("IDENT", "a block keyword")
        label: str | None = None
        if self._peek().kind == "STRING":
            label = self._next().value
        self._expect("LBRACE", "'{' to open the block")
        attrs, children = self._parse_body()
        return Block(
            kind=keyword.value,
            label=label,
            attrs=attrs,
            children=tuple(children),
            line=keyword.line,
            col=keyword.col,
        )

    def _parse_body(self) -> tuple[dict[str, Any], list[Block]]:
        attrs: dict[str, Any] = {}
        children: list[Block] = []
        while self._peek().kind != "RBRACE":
            token = self._peek()
            if token.kind == "EOF":
                raise self._error("missing '}': end of file inside block", token)
            if token.kind != "IDENT":
                raise self._error(
                    f"expected an attribute or nested block, found {token.kind} {token.value!r}",
                    token,
                )
            lookahead = self._peek(1)
            if lookahead.kind == "EQ":
                name = self._next().value
                self._next()  # consume '='
                value = self._parse_value()
                if name in attrs:
                    raise self._error(
                        f"duplicate attribute {name!r} in the same block", token
                    )
                attrs[name] = value
            elif lookahead.kind in ("LBRACE", "STRING"):
                children.append(self._parse_block())
            else:
                raise self._error(
                    f"expected '=', '{{' or a string label after identifier {token.value!r}",
                    lookahead,
                )
        self._next()  # consume '}'
        return attrs, children

    def _parse_value(self) -> Any:
        token = self._peek()
        if token.kind in _VALUE_KINDS:
            return self._next().value
        if token.kind == "LBRACKET":
            return self._parse_list()
        raise self._error(
            f"expected a value (string, number, bool, null or list), found {token.kind} {token.value!r}",
            token,
        )

    def _parse_list(self) -> list[Any]:
        self._expect("LBRACKET", "'[' to open the list")
        items: list[Any] = []
        while True:
            token = self._peek()
            if token.kind == "RBRACKET":
                self._next()
                return items
            if token.kind not in _SCALAR_KINDS:
                raise self._error(
                    f"lists may contain only scalar values, found {token.kind} {token.value!r}",
                    token,
                )
            items.append(self._next().value)
            separator = self._peek()
            if separator.kind == "COMMA":
                self._next()
                continue
            if separator.kind == "RBRACKET":
                self._next()
                return items
            raise self._error(
                f"expected ',' or ']' in list, found {separator.kind} {separator.value!r}",
                separator,
            )


def parse(source: str, *, filename: str = "<string>") -> Document:
    """Parse UCL source text into a Document. Raises UCLError on any error."""
    tokens = lex(source, filename=filename)
    return Parser(tokens, filename=filename).parse_document()


def parse_file(path: str | Path) -> Document:
    """Parse one .ucl file. Raises UCLError on read or syntax failure."""
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise UCLError(f"cannot read UCL file: {exc}", filename=str(p)) from exc
    return parse(text, filename=str(p))
