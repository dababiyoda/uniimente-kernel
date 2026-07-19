"""UCL lexer — hand-rolled token stream (SPEC-WP02, "UCL grammar").

Enforces the lexical layer of the five real constitution/*.ucl files: line
comments (``//`` to end of line, never inside strings), double-quoted strings
(a ``}`` or ``//`` inside a string is data, not syntax), identifiers,
integer/float numbers, ``true``/``false``/``null`` literals and the
punctuation ``= { } [ ] ,``.

Constitutional clause: the kernel_invariant's ``on_violation =
"refuse_and_escalate"`` — any lexical ambiguity (unterminated string, bad
escape, stray character, malformed number) raises UCLError with line/col and
fails closed; the lexer never guesses.

No third-party parser libraries: stdlib only (SPEC-WP02 "Constraints").
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Token kinds emitted by lex(): IDENT, STRING, NUMBER, BOOL, NULL,
# EQ, LBRACE, RBRACE, LBRACKET, RBRACKET, COMMA, EOF (SPEC-WP02 module layout).
PUNCTUATION = {
    "=": "EQ",
    "{": "LBRACE",
    "}": "RBRACE",
    "[": "LBRACKET",
    "]": "RBRACKET",
    ",": "COMMA",
}

KEYWORDS = {"true": ("BOOL", True), "false": ("BOOL", False), "null": ("NULL", None)}

_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "n": "\n", "t": "\t", "r": "\r"}


class UCLError(Exception):
    """Any UCL lexical/syntax/semantic failure. Fails closed, always located."""

    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        col: int | None = None,
        filename: str | None = None,
    ):
        self.message = message
        self.line = line
        self.col = col
        self.filename = filename
        super().__init__(str(self))

    def __str__(self) -> str:
        where = ""
        if self.filename is not None:
            where += str(self.filename)
        if self.line is not None:
            where += f":{self.line}"
            if self.col is not None:
                where += f":{self.col}"
        return f"{where}: {self.message}" if where else self.message


@dataclass(frozen=True)
class Token:
    """One lexical unit with 1-based source position (for UCLError reports)."""

    kind: str
    value: Any
    line: int
    col: int


def _is_ident_start(ch: str) -> bool:
    return ch == "_" or "a" <= ch <= "z" or "A" <= ch <= "Z"


def _is_ident_part(ch: str) -> bool:
    return _is_ident_start(ch) or "0" <= ch <= "9"


def lex(source: str, *, filename: str = "<string>") -> list[Token]:
    """Tokenize ``source``. Raises UCLError (with line/col) on any ambiguity."""
    tokens: list[Token] = []
    i = 0
    line, col = 1, 1
    n = len(source)

    def error(msg: str, err_line: int, err_col: int) -> UCLError:
        return UCLError(msg, line=err_line, col=err_col, filename=filename)

    while i < n:
        ch = source[i]

        # Whitespace (newlines are not significant in the UCL grammar; they are
        # tracked only for error positions).
        if ch in " \t\r":
            i += 1
            col += 1
            continue
        if ch == "\n":
            i += 1
            line += 1
            col = 1
            continue

        # Line comment: // to end of line (outside strings only — strings are
        # consumed atomically below, so a // inside quotes never reaches here).
        if ch == "/":
            if i + 1 < n and source[i + 1] == "/":
                while i < n and source[i] != "\n":
                    i += 1
                    col += 1
                continue
            raise error(
                f"unexpected character '/': did you mean a '//' comment?", line, col
            )

        # String literal: a } or // inside quotes is data, never syntax.
        if ch == '"':
            start_line, start_col = line, col
            i += 1
            col += 1
            buf: list[str] = []
            while True:
                if i >= n or source[i] == "\n":
                    raise error(
                        "unterminated string literal", start_line, start_col
                    )
                c = source[i]
                if c == '"':
                    i += 1
                    col += 1
                    break
                if c == "\\":
                    if i + 1 >= n:
                        raise error(
                            "unterminated string literal", start_line, start_col
                        )
                    esc = source[i + 1]
                    if esc not in _ESCAPES:
                        raise error(
                            f"invalid escape sequence '\\{esc}'", line, col
                        )
                    buf.append(_ESCAPES[esc])
                    i += 2
                    col += 2
                else:
                    buf.append(c)
                    i += 1
                    col += 1
            tokens.append(Token("STRING", "".join(buf), start_line, start_col))
            continue

        # Punctuation.
        if ch in PUNCTUATION:
            tokens.append(Token(PUNCTUATION[ch], ch, line, col))
            i += 1
            col += 1
            continue

        # Number: optional '-', digits, optional fraction (float).
        if ch.isdigit() or (ch == "-" and i + 1 < n and source[i + 1].isdigit()):
            start_line, start_col = line, col
            start = i
            if ch == "-":
                i += 1
                col += 1
            while i < n and source[i].isdigit():
                i += 1
                col += 1
            is_float = False
            if i < n and source[i] == ".":
                if i + 1 >= n or not source[i + 1].isdigit():
                    raise error("malformed number: '.' must be followed by digits", line, col)
                is_float = True
                i += 1
                col += 1
                while i < n and source[i].isdigit():
                    i += 1
                    col += 1
            if i < n and _is_ident_start(source[i]):
                raise error("malformed number: identifier character after number", line, col)
            text = source[start:i]
            tokens.append(
                Token("NUMBER", float(text) if is_float else int(text), start_line, start_col)
            )
            continue

        # Identifier or keyword literal (true/false/null).
        if _is_ident_start(ch):
            start_line, start_col = line, col
            start = i
            while i < n and _is_ident_part(source[i]):
                i += 1
                col += 1
            word = source[start:i]
            if word in KEYWORDS:
                kind, value = KEYWORDS[word]
                tokens.append(Token(kind, value, start_line, start_col))
            else:
                tokens.append(Token("IDENT", word, start_line, start_col))
            continue

        raise error(f"unexpected character {ch!r}", line, col)

    tokens.append(Token("EOF", None, line, col))
    return tokens
