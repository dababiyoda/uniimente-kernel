"""UCL parser: HCL-compatible constitutional doctrine -> AST.

UCL is declarative: no loops, no side-effecting functions, no I/O.
This parser is a pure function from text to Block trees. Malformed input
fails closed with a UCLSyntaxError; it never guesses.

Layer 1 of the maximum buildable science-fiction stack (Executable
Constitution): the first half of the narrow UCL compiler.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator


class UCLSyntaxError(ValueError):
    """Raised on any malformed UCL. Compilation refuses; it never repairs."""


@dataclass
class Token:
    kind: str  # IDENT | STRING | NUMBER | LBRACE | RBRACE | LBRACK | RBRACK | EQUALS | COMMA | EOF
    value: str
    line: int
    col: int


_PUNCT = {"{": "LBRACE", "}": "RBRACE", "[": "LBRACK", "]": "RBRACK", "=": "EQUALS", ",": "COMMA"}


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    i, line, col = 0, 1, 1
    n = len(text)

    def advance(k: int = 1) -> None:
        nonlocal i, line, col
        for _ in range(k):
            if i < n and text[i] == "\n":
                line += 1
                col = 1
            else:
                col += 1
            i += 1

    while i < n:
        ch = text[i]
        if ch in " \t\r\n":
            advance()
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                advance()
            continue
        if ch == "#":
            while i < n and text[i] != "\n":
                advance()
            continue
        if ch in _PUNCT:
            tokens.append(Token(_PUNCT[ch], ch, line, col))
            advance()
            continue
        if ch == '"':
            start_line, start_col = line, col
            advance()
            buf = []
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    esc = text[i + 1]
                    buf.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(esc, esc))
                    advance(2)
                    continue
                buf.append(text[i])
                advance()
            if i >= n:
                raise UCLSyntaxError(f"unterminated string at {start_line}:{start_col}")
            advance()  # closing quote
            tokens.append(Token("STRING", "".join(buf), start_line, start_col))
            continue
        if ch.isdigit() or (ch == "-" and i + 1 < n and text[i + 1].isdigit()):
            start_line, start_col = line, col
            buf = []
            while i < n and (text[i].isdigit() or text[i] in ".-"):
                buf.append(text[i])
                advance()
            tokens.append(Token("NUMBER", "".join(buf), start_line, start_col))
            continue
        if ch.isalpha() or ch == "_":
            start_line, start_col = line, col
            buf = []
            while i < n and (text[i].isalnum() or text[i] in "_./-"):
                buf.append(text[i])
                advance()
            tokens.append(Token("IDENT", "".join(buf), start_line, start_col))
            continue
        raise UCLSyntaxError(f"unexpected character {ch!r} at {line}:{col}")
    tokens.append(Token("EOF", "", line, col))
    return tokens


@dataclass
class Block:
    """One UCL block: type, optional label, assignments, nested blocks."""

    type: str
    label: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)
    blocks: list["Block"] = field(default_factory=list)

    def get(self, name: str, default: Any = None) -> Any:
        return self.fields.get(name, default)

    def children(self, type_: str) -> list["Block"]:
        return [b for b in self.blocks if b.type == type_]

    def child(self, type_: str) -> "Block | None":
        for b in self.blocks:
            if b.type == type_:
                return b
        return None


class _Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def next(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, kind: str) -> Token:
        tok = self.next()
        if tok.kind != kind:
            raise UCLSyntaxError(f"expected {kind}, got {tok.kind} ({tok.value!r}) at {tok.line}:{tok.col}")
        return tok

    def parse_file(self) -> list[Block]:
        blocks = []
        while self.peek().kind != "EOF":
            blocks.append(self.parse_block())
        return blocks

    def parse_block(self) -> Block:
        type_tok = self.expect("IDENT")
        label = None
        if self.peek().kind == "STRING":
            label = self.next().value
        self.expect("LBRACE")
        block = Block(type=type_tok.value, label=label)
        while self.peek().kind != "RBRACE":
            tok = self.peek()
            if tok.kind == "EOF":
                raise UCLSyntaxError(f"unclosed block {type_tok.value!r} opened at {type_tok.line}:{type_tok.col}")
            if tok.kind == "IDENT":
                # Lookahead: IDENT (STRING)? LBRACE -> nested block; IDENT EQUALS -> assignment
                nxt = self.tokens[self.pos + 1]
                if nxt.kind == "EQUALS":
                    name = self.next().value
                    self.expect("EQUALS")
                    block.fields[name] = self.parse_value()
                elif nxt.kind in ("LBRACE", "STRING"):
                    block.blocks.append(self.parse_block())
                else:
                    raise UCLSyntaxError(f"unexpected {nxt.kind} after identifier at {nxt.line}:{nxt.col}")
            else:
                raise UCLSyntaxError(f"unexpected {tok.kind} in block body at {tok.line}:{tok.col}")
        self.expect("RBRACE")
        return block

    def parse_value(self) -> Any:
        tok = self.next()
        if tok.kind == "STRING":
            return tok.value
        if tok.kind == "NUMBER":
            return float(tok.value) if "." in tok.value else int(tok.value)
        if tok.kind == "LBRACK":
            items = []
            while self.peek().kind != "RBRACK":
                items.append(self.parse_value())
                if self.peek().kind == "COMMA":
                    self.next()
                elif self.peek().kind != "RBRACK":
                    bad = self.peek()
                    raise UCLSyntaxError(f"expected ',' or ']' in list at {bad.line}:{bad.col}")
            self.expect("RBRACK")
            return items
        if tok.kind == "IDENT":
            if tok.value == "true":
                return True
            if tok.value == "false":
                return False
            if tok.value == "null":
                return None
            # Bare identifiers are symbolic references (e.g. escalate(alfonso) targets).
            return {"symbol": tok.value}
        raise UCLSyntaxError(f"unexpected value token {tok.kind} at {tok.line}:{tok.col}")


def parse(text: str) -> list[Block]:
    """Parse UCL source text into top-level blocks. Pure function."""
    return _Parser(tokenize(text)).parse_file()


def parse_file(path: str) -> list[Block]:
    with open(path, "r", encoding="utf-8") as fh:
        return parse(fh.read())
