"""Lexer tests: token stream for every UCL construct + fail-closed errors.

Covers SPEC-WP02 "UCL grammar": comments, strings (with } and // inside),
identifiers, int/float numbers, true/false/null, = { } [ ] , and one-line
nested blocks. Error cases raise UCLError carrying line/col.
"""
import pytest

from kernel.ucl.lexer import Token, UCLError, lex


def kinds(tokens):
    return [t.kind for t in tokens]


def test_simple_assignment_token_stream():
    tokens = lex('version = "1.0.0"')
    assert kinds(tokens) == ["IDENT", "EQ", "STRING", "EOF"]
    assert tokens[0].value == "version"
    assert tokens[2].value == "1.0.0"


def test_all_scalar_value_kinds():
    tokens = lex('a = "text" b = 42 c = -7 d = 0.5 e = true f = false g = null')
    assert kinds(tokens) == [
        "IDENT", "EQ", "STRING",
        "IDENT", "EQ", "NUMBER",
        "IDENT", "EQ", "NUMBER",
        "IDENT", "EQ", "NUMBER",
        "IDENT", "EQ", "BOOL",
        "IDENT", "EQ", "BOOL",
        "IDENT", "EQ", "NULL",
        "EOF",
    ]
    values = [t.value for t in tokens if t.kind in ("STRING", "NUMBER", "BOOL", "NULL")]
    assert values == ["text", 42, -7, 0.5, True, False, None]
    assert isinstance(tokens[5].value, int)
    assert isinstance(tokens[11].value, float)


def test_block_punctuation_and_labels():
    tokens = lex('constitution "uniimente" { }')
    assert kinds(tokens) == ["IDENT", "STRING", "LBRACE", "RBRACE", "EOF"]


def test_list_tokens():
    tokens = lex('may_ratify = ["alfonso", "kernel"]')
    assert kinds(tokens) == [
        "IDENT", "EQ", "LBRACKET", "STRING", "COMMA", "STRING", "RBRACKET", "EOF",
    ]


def test_line_comments_are_skipped():
    source = (
        "// a comment with a brace } and a \"quote\" and = signs\n"
        "version = \"1.0.0\" // trailing comment\n"
        "// another one\n"
        "status = \"unratified\"\n"
    )
    tokens = lex(source)
    assert kinds(tokens) == ["IDENT", "EQ", "STRING", "IDENT", "EQ", "STRING", "EOF"]


def test_string_containing_brace_and_comment_marker_is_data():
    tokens = lex(r'note = "a } b // not a comment"')
    assert kinds(tokens) == ["IDENT", "EQ", "STRING", "EOF"]
    assert tokens[2].value == "a } b // not a comment"


def test_string_escape_sequences():
    tokens = lex(r's = "a \"quoted\" b \\ c\td"')
    assert tokens[2].value == 'a "quoted" b \\ c\td'


def test_one_line_nested_block_tokens():
    tokens = lex('state { name = "normal" external_effects = "permitted_under_grants" }')
    assert kinds(tokens) == [
        "IDENT", "LBRACE",
        "IDENT", "EQ", "STRING",
        "IDENT", "EQ", "STRING",
        "RBRACE", "EOF",
    ]


def test_positions_are_one_based_line_col():
    tokens = lex('a = 1\n\n  b = 2')
    assert (tokens[0].line, tokens[0].col) == (1, 1)
    assert (tokens[3].line, tokens[3].col) == (3, 3)
    eof = tokens[-1]
    assert eof.kind == "EOF"
    assert (eof.line, eof.col) == (3, 8)  # one past the final '2' at line 3 col 7


def test_multiline_list():
    source = 'items = [\n    "a",\n    "b",\n    "c"\n]'
    tokens = lex(source)
    assert kinds(tokens) == [
        "IDENT", "EQ", "LBRACKET",
        "STRING", "COMMA", "STRING", "COMMA", "STRING",
        "RBRACKET", "EOF",
    ]


# ------------------------------------------------------------------ errors


def test_unterminated_string_raises_with_position():
    with pytest.raises(UCLError) as excinfo:
        lex('a = "never closed\nb = 1')
    assert excinfo.value.line == 1
    assert excinfo.value.col == 5
    assert "unterminated string" in str(excinfo.value)


def test_invalid_escape_raises_with_position():
    with pytest.raises(UCLError) as excinfo:
        lex(r'a = "bad \q escape"')
    assert excinfo.value.line == 1
    assert "invalid escape" in str(excinfo.value)


def test_lone_slash_raises():
    with pytest.raises(UCLError) as excinfo:
        lex("a = / b")
    assert "unexpected character '/'" in str(excinfo.value)
    assert excinfo.value.line == 1


def test_unexpected_character_raises_with_position():
    with pytest.raises(UCLError) as excinfo:
        lex("a = 1\nb = @")
    assert excinfo.value.line == 2
    assert excinfo.value.col == 5
    assert "unexpected character" in str(excinfo.value)


def test_malformed_number_dot_without_digits():
    with pytest.raises(UCLError) as excinfo:
        lex("rank = 1.")
    assert "malformed number" in str(excinfo.value)


def test_malformed_number_trailing_identifier():
    with pytest.raises(UCLError) as excinfo:
        lex("rank = 1abc")
    assert "malformed number" in str(excinfo.value)


def test_error_message_includes_filename_and_position():
    with pytest.raises(UCLError) as excinfo:
        lex("x = $", filename="constitution/ucl-test.ucl")
    text = str(excinfo.value)
    assert "ucl-test.ucl" in text and ":1:5" in text


def test_token_is_immutable():
    token = Token("IDENT", "a", 1, 1)
    with pytest.raises(Exception):
        token.kind = "STRING"  # frozen dataclass
