"""A success check on bounded evidence decides only what that evidence proves.

``authority.bounded`` keeps a 16 KiB prefix (with the whole string's sha256 and length) of long text and the first
RECEIPT_LIST_LIMIT items of a list. A predicate that judged the part as if it were the whole could pass a
``not_contains`` whose forbidden text sits past the cut, so a mission would close on evidence that refutes it.
"""
import hashlib

from greg.authority import RECEIPT_LIST_LIMIT, RECEIPT_TEXT_LIMIT, bounded
from greg.body import Body
from greg.missions import evaluate_predicate
from tests.greg_fixtures import Clock, drop, make_body, mission, signed, workspace, write_strategy

HEAD = "status: done\n"
LONG = HEAD + "x" * RECEIPT_TEXT_LIMIT + "\nFORBIDDEN tail\n"          # the forbidden words sit past the cut
TEXT = bounded({"text": LONG})


def check(op, value=None, output=TEXT, field="text"):
    return evaluate_predicate({"op": op, "field": field, "value": value}, output)


def test_the_receipt_keeps_a_prefix_and_the_whole_texts_digest_and_length():
    kept = TEXT["text"]
    assert kept["truncated"] and len(kept["prefix"]) == RECEIPT_TEXT_LIMIT and "FORBIDDEN" not in kept["prefix"]
    assert kept["length"] == len(LONG) and kept["sha256"] == hashlib.sha256(LONG.encode()).hexdigest()


def test_not_contains_never_passes_on_a_prefix():
    passed, detail = check("not_contains", "FORBIDDEN")
    assert not passed and "truncated" in detail          # the prefix cannot show the tail is clean
    assert check("not_contains", "status: done")[0] is False   # found in the prefix: false on the whole, decided


def test_contains_passes_on_a_prefix_hit_and_otherwise_cannot_decide():
    assert check("contains", "status: done")[0] is True
    passed, detail = check("contains", "FORBIDDEN tail")
    assert not passed and "truncated" in detail


def test_equals_on_truncated_text_is_decided_exactly_by_digest_and_length():
    assert check("equals", LONG)[0] is True
    assert check("equals", LONG[:-1] + "!")[0] is False
    assert check("equals", TEXT["text"]["prefix"])[0] is False          # the prefix is not the value


def test_count_gte_on_truncated_text_counts_the_whole_length():
    assert check("count_gte", len(LONG))[0] is True
    assert check("count_gte", len(LONG) + 1)[0] is False


def test_a_list_at_the_receipt_limit_is_judged_as_possibly_longer():
    output = bounded({"items": [f"row {i}" for i in range(RECEIPT_LIST_LIMIT + 5)]})
    assert len(output["items"]) == RECEIPT_LIST_LIMIT
    passed, detail = check("not_contains", f"row {RECEIPT_LIST_LIMIT + 2}", output, "items")
    assert not passed and "truncated" in detail
    assert check("contains", "row 3", output, "items")[0] is True
    assert check("count_gte", RECEIPT_LIST_LIMIT, output, "items")[0] is True
    assert check("count_gte", RECEIPT_LIST_LIMIT + 1, output, "items")[0] is False
    assert check("equals", output["items"], output, "items")[0] is False


def test_short_evidence_is_judged_exactly_as_before():
    output = bounded({"text": "all clear", "items": ["a", "b"]})
    assert check("not_contains", "FORBIDDEN", output)[0] is True
    assert check("equals", "all clear", output)[0] is True
    assert check("contains", "clear", output)[0] is True
    assert check("count_gte", 2, output, "items")[0] is True
    assert check("not_contains", "c", output, "items")[0] is True
    assert check("exists", None, output)[0] is True and check("absent", None, output, "nothing")[0] is True


def test_a_mission_does_not_close_on_a_clean_prefix_of_a_file_that_says_otherwise(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    report = workspace(home, "m:clean") / "report.txt"
    clean = {"check_id": "clean", "description": "the report names no forbidden item",
             "sensor": {"capability": "fs.read", "params": {"path": str(report)}, "target": "fs:report.txt"},
             "predicate": {"op": "not_contains", "field": "text", "value": "FORBIDDEN"}}
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:clean", checks=[clean], strategies=[write_strategy("write", "report.txt", LONG, ["clean"])],
        capabilities=["fs.read", "fs.write"])))
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(6):
            body.tick()
            clock.advance(1.0)
        state = body.engine.book.missions["m:clean"]
        observed = [e.payload for e in body.journal.replay("mission.observed")]
    assert report.read_text() == LONG
    assert state.status != "ACHIEVED"
    assert any("truncated" in str(o.get("detail", "")) for o in observed)
