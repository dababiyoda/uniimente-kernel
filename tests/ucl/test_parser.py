"""Parser tests: AST for every UCL construct + fail-closed syntax errors.

Covers SPEC-WP02 "UCL grammar": labelled and anonymous blocks, nested
blocks, one-line blocks, lists, null, bool, numbers, comments. Error cases
(missing '}', bad value, duplicates, nested lists) raise UCLError with
line/col — the parser never recovers or guesses.
"""
import pytest

from kernel.ucl import UCLError, parse, parse_file
from kernel.ucl.ast import Block
from kernel.ucl.parser import Document


def test_labelled_top_level_block_with_attributes():
    doc = parse('constitution "uniimente" {\n    version = "1.0.0"\n    status = "unratified"\n}')
    assert isinstance(doc, Document)
    assert len(doc) == 1
    block = doc.blocks[0]
    assert block.kind == "constitution"
    assert block.label == "uniimente"
    assert block.attrs == {"version": "1.0.0", "status": "unratified"}
    assert block.children == ()


def test_anonymous_nested_block():
    doc = parse(
        'constitution "uniimente" {\n'
        "    doctrine {\n"
        "        humans_authorize = true\n"
        "        kernel_decides = false\n"
        "    }\n"
        "}"
    )
    constitution = doc.blocks[0]
    doctrine = constitution.child("doctrine")
    assert doctrine is not None
    assert doctrine.label is None
    assert doctrine.attrs == {"humans_authorize": True, "kernel_decides": False}


def test_labelled_nested_blocks_preserve_order():
    doc = parse(
        'participant_rights "uniimente" {\n'
        '    right "safety" { rule = "no harm" enforcement = "hard_refusal" }\n'
        '    right "exit" { rule = "opt out" enforcement = "automatic" }\n'
        "}"
    )
    rights = doc.blocks[0].children_of("right")
    assert [r.label for r in rights] == ["safety", "exit"]
    assert rights[0].attrs["enforcement"] == "hard_refusal"
    assert rights[1].attrs["rule"] == "opt out"


def test_one_line_block_with_multiple_attributes():
    doc = parse('safety_states "ladder" {\n    state { name = "normal" external_effects = "permitted_under_grants" }\n}')
    state = doc.blocks[0].child("state")
    assert state.attrs == {"name": "normal", "external_effects": "permitted_under_grants"}


def test_all_value_kinds():
    doc = parse(
        "block {\n"
        '    s = "text"\n'
        "    i = 42\n"
        "    neg = -7\n"
        "    f = 0.5\n"
        "    t = true\n"
        "    ff = false\n"
        "    n = null\n"
        "}"
    )
    attrs = doc.blocks[0].attrs
    assert attrs == {"s": "text", "i": 42, "neg": -7, "f": 0.5, "t": True, "ff": False, "n": None}
    assert isinstance(attrs["i"], int) and not isinstance(attrs["i"], bool)
    assert isinstance(attrs["f"], float)
    assert attrs["t"] is True and attrs["ff"] is False and attrs["n"] is None


def test_lists_of_scalars_and_trailing_comma():
    doc = parse(
        "block {\n"
        '    a = ["x", "y"]\n'
        "    b = [1, 2, 3,]\n"
        "    c = []\n"
        '    d = [true, null, "s", 1.5]\n'
        "}"
    )
    attrs = doc.blocks[0].attrs
    assert attrs["a"] == ["x", "y"]
    assert attrs["b"] == [1, 2, 3]
    assert attrs["c"] == []
    assert attrs["d"] == [True, None, "s", 1.5]


def test_multiline_list_from_real_constitution_shape():
    doc = parse(
        "permanent_prohibitions {\n"
        "    non_delegable = [\n"
        '        "constitutional_amendment",\n'
        '        "shutdown_override"\n'
        "    ]\n"
        "}"
    )
    assert doc.blocks[0].attrs["non_delegable"] == [
        "constitutional_amendment",
        "shutdown_override",
    ]


def test_comments_do_not_affect_the_ast():
    with_comments = parse(
        "// header comment\n"
        'block "x" { // trailing\n'
        "    a = 1 // another\n"
        "}"
    )
    without = parse('block "x" {\n    a = 1\n}')
    assert with_comments == without


def test_deeply_nested_blocks_and_walk():
    doc = parse("a { b { c { d = 1 } } }")
    kinds = [block.kind for block in doc.blocks[0].walk()]
    assert kinds == ["a", "b", "c"]
    assert doc.blocks[0].child("b").child("c").attrs == {"d": 1}


def test_document_find_helpers():
    doc = parse('kill_condition "cathedral" { when = "w" then = "t" }\npolicy "p" { rule = "r" }')
    assert doc.find("kill_condition").label == "cathedral"
    assert doc.find("kill_condition", label="cathedral").attrs["then"] == "t"
    assert doc.find("kill_condition", label="other") is None
    assert [b.kind for b in doc.find_all("policy")] == ["policy"]


def test_parse_file_roundtrip(tmp_path):
    path = tmp_path / "sample.ucl"
    path.write_text('policy "x" { rule = "r" }', encoding="utf-8")
    doc = parse_file(path)
    assert doc.filename == str(path)
    assert doc.blocks[0].kind == "policy"


def test_parse_file_missing_raises_uclerror(tmp_path):
    with pytest.raises(UCLError):
        parse_file(tmp_path / "does-not-exist.ucl")


# ------------------------------------------------------------------ errors


def test_missing_closing_brace_raises_with_position():
    with pytest.raises(UCLError) as excinfo:
        parse('block "x" {\n    a = 1\n')
    assert "missing '}'" in str(excinfo.value)
    assert excinfo.value.line == 3  # EOF token position


def test_bad_value_raises_with_position():
    with pytest.raises(UCLError) as excinfo:
        parse("block {\n    a = }\n}")
    assert "expected a value" in str(excinfo.value)
    assert excinfo.value.line == 2


def test_identifier_without_equals_or_brace_raises():
    with pytest.raises(UCLError) as excinfo:
        parse("block {\n    stray_identifier 1\n}")
    assert "expected '=', '{' or a string label" in str(excinfo.value)


def test_missing_brace_after_label_raises():
    with pytest.raises(UCLError) as excinfo:
        parse('right "safety" rule = "x"')
    assert "expected '{'" in str(excinfo.value)


def test_duplicate_attribute_fails_closed():
    with pytest.raises(UCLError) as excinfo:
        parse("block {\n    a = 1\n    a = 2\n}")
    assert "duplicate attribute" in str(excinfo.value)
    assert excinfo.value.line == 3


def test_nested_list_is_rejected():
    with pytest.raises(UCLError) as excinfo:
        parse('block { a = [["x"]] }')
    assert "lists may contain only scalar values" in str(excinfo.value)


def test_list_without_comma_is_rejected():
    with pytest.raises(UCLError) as excinfo:
        parse('block { a = ["x" "y"] }')
    assert "expected ',' or ']'" in str(excinfo.value)


def test_block_as_list_item_is_rejected():
    with pytest.raises(UCLError) as excinfo:
        parse("block { a = [state { }] }")
    assert "lists may contain only scalar values" in str(excinfo.value)


def test_top_level_garbage_is_rejected():
    with pytest.raises(UCLError):
        parse('"just a string"')


def test_block_positions_recorded():
    doc = parse('\n\nright "safety" {\n    rule = "x"\n}')
    block = doc.blocks[0]
    assert isinstance(block, Block)
    assert (block.line, block.col) == (3, 1)
