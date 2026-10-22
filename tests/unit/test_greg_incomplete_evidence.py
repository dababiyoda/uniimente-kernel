"""A mission never closes on evidence it did not retain (directive of 2026-10-22, section VI).

``authority.bounded`` keeps a receipt's long strings as their first 16 KiB plus a digest and length, and its
lists as their first 1000 items with no marker. A predicate judged on that retained part used to treat it as the
whole value: a phrase past 16 KiB was "absent", so a forbidden phrase there let the mission close. Now the
predicate is TRUE, FALSE or INSUFFICIENT, and INSUFFICIENT is an unmeasured check: re-observed, then asked,
never passed and never blamed on a strategy. In-process Body with a test clock (SANDBOX).
"""
from __future__ import annotations

import hashlib

import pytest

from greg.authority import RECEIPT_TEXT_LIMIT, bounded
from greg.missions import (FALSE, INSUFFICIENT, RECEIPT_LIST_LIMIT, TRUE, Unbound, bound_value, evaluate_predicate,
                           judge)
from tests.greg_fixtures import Clock, make_body, mission, note_check
from tests.unit.test_greg_missions import events, run, submit

FILLER = "proof settlement notice delivery party shall net due. " * 400       # about 22 KiB
assert len(FILLER) > RECEIPT_TEXT_LIMIT + 4000


def kept(text):
    return bounded({"text": text})


def p(op, value, field="text"):
    return {"op": op, "field": field, "value": value}


# -- the predicate, on retained outputs ----------------------------------------------------------------------------

@pytest.mark.parametrize("op, value, whole, verdict", [
    ("contains", "proof settlement", "short proof settlement", TRUE),        # whole values: unchanged
    ("contains", "absent clause", "short proof settlement", FALSE),
    ("not_contains", "absent clause", "short proof settlement", TRUE),
    ("equals", "short", "short", TRUE),
    ("count_gte", 3, "short", TRUE),
])
def test_a_whole_value_is_judged_as_before(op, value, whole, verdict):
    assert judge(p(op, value), kept(whole))[0] == verdict


def test_a_phrase_before_the_prefix_end_is_found():
    output = kept("renewal term is twelve months. " + FILLER)
    assert judge(p("contains", "twelve months"), output)[0] == TRUE


def test_a_phrase_after_the_prefix_end_is_insufficient_not_absent():
    output = kept(FILLER + "renewal term is twelve months.")
    verdict, detail = judge(p("contains", "twelve months"), output)
    assert verdict == INSUFFICIENT and "not in the first" in detail


def test_a_forbidden_phrase_after_the_prefix_end_never_passes():
    output = kept(FILLER + "Either party may terminate without notice.")
    assert judge(p("not_contains", "terminate without notice"), output)[0] == INSUFFICIENT
    passed, detail = evaluate_predicate(p("not_contains", "terminate without notice"), output)
    assert passed is False and detail.startswith("insufficient evidence: ")


def test_a_forbidden_phrase_inside_the_prefix_is_proved_present():
    output = kept("terminate without notice. " + FILLER)
    assert judge(p("not_contains", "terminate without notice"), output)[0] == FALSE


def test_a_match_spanning_the_prefix_boundary_is_insufficient():
    head = "x" * (RECEIPT_TEXT_LIMIT - 5)
    output = kept(head + "terminate without notice" + FILLER)          # the phrase straddles character 16384
    assert judge(p("contains", "terminate without notice"), output)[0] == INSUFFICIENT
    assert judge(p("not_contains", "terminate without notice"), output)[0] == INSUFFICIENT


def test_equality_of_a_long_string_is_decided_by_its_digest_and_length():
    text = FILLER + "end"
    assert judge(p("equals", text), kept(text))[0] == TRUE
    assert judge(p("equals", text[:-1] + "x"), kept(text))[0] == FALSE         # same length, other bytes
    assert judge(p("equals", text[:RECEIPT_TEXT_LIMIT]), kept(text))[0] == FALSE   # the prefix is not the value


def test_unicode_is_counted_in_characters_and_digested_in_utf8():
    text = "é" * (RECEIPT_TEXT_LIMIT + 10) + "fin"
    assert judge(p("equals", text), kept(text))[0] == TRUE
    assert judge(p("count_gte", RECEIPT_TEXT_LIMIT + 13), kept(text))[0] == TRUE
    assert judge(p("count_gte", RECEIPT_TEXT_LIMIT + 14), kept(text))[0] == FALSE
    assert judge(p("contains", "fin"), kept(text))[0] == INSUFFICIENT


def test_an_output_that_merely_looks_truncated_is_not_unwrapped():
    forged = {"text": {"prefix": "terminate", "truncated": True, "sha256": "0" * 64, "length": 3}}   # length <= prefix
    assert judge(p("contains", "terminate"), forged)[0] == FALSE          # a dict, not text: contains is false
    forged["text"]["note"] = "extra"
    assert judge(p("contains", "terminate"), forged)[0] == FALSE


def test_a_list_at_the_receipt_item_limit_proves_only_what_it_holds():
    rows = [f"row{i}" for i in range(RECEIPT_LIST_LIMIT + 500)]
    output = bounded({"rows": rows})
    assert len(output["rows"]) == RECEIPT_LIST_LIMIT                     # cut, with no marker
    assert judge(p("contains", "row7", "rows"), output)[0] == TRUE
    assert judge(p("contains", "row1200", "rows"), output)[0] == INSUFFICIENT
    assert judge(p("not_contains", "row1200", "rows"), output)[0] == INSUFFICIENT
    assert judge(p("not_contains", "row7", "rows"), output)[0] == FALSE
    assert judge(p("count_gte", 1000, "rows"), output)[0] == TRUE
    assert judge(p("count_gte", 1001, "rows"), output)[0] == INSUFFICIENT
    assert judge(p("equals", rows, "rows"), output)[0] == INSUFFICIENT
    assert judge({"op": "exists", "field": "rows.1200"}, output)[0] == INSUFFICIENT
    assert judge({"op": "exists", "field": "rows.12"}, output)[0] == TRUE


def test_a_capability_that_reports_its_observation_incomplete_proves_only_monotone_facts():
    output = {"text": "page one words", "complete": False, "found": None}
    assert judge(p("contains", "page one"), output)[0] == TRUE
    assert judge(p("not_contains", "clause"), output)[0] == INSUFFICIENT
    assert judge(p("equals", True, "found"), output)[0] == INSUFFICIENT
    assert judge(p("equals", False, "found"), output)[0] == INSUFFICIENT


@pytest.mark.parametrize("output", [None, {}, {"text": ""}])
def test_empty_outputs_keep_their_meaning(output):
    assert judge(p("contains", "x"), output)[0] == FALSE
    assert judge({"op": "absent", "field": "text"}, {})[0] == TRUE


def test_a_kept_prefix_is_never_bound_as_the_whole_value():
    edge = {"from": {"action_id": "read", "field": "text"}, "type": "string", "max_bytes": 10 ** 6}
    with pytest.raises(Unbound, match="prefix is not bound"):
        bound_value(edge, kept(FILLER))
    assert bound_value(edge, kept("short")) == "short"


# -- on the mission path: a long non-PDF output (fs.read of a 22 KiB text file) -----------------------------------

def _forbid(check_id, path, text):
    check = note_check(check_id, path, text)
    check["predicate"]["op"] = "not_contains"
    return check


def test_a_forbidden_phrase_past_16_kib_of_a_text_file_does_not_close_the_mission(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    contract = data / "contract.txt"
    contract.write_text(FILLER + "Either party may terminate without notice.")
    submit(home, key, body_id, "MISSION", mission("m:never", checks=[_forbid("clean", contract,
                                                                             "terminate without notice")],
                                                  strategies=[], capabilities=["fs.read"], ceiling="read_only"))
    missions, _ = run(home, Clock(), ticks=3)
    assert missions["m:never"].status != "ACHIEVED"                 # before this change: ACHIEVED on a false pass
    observed = [e for e in events(home, "mission.observed") if e["mission_id"] == "m:never"]
    assert observed and all(not e["passed"] and e["detail"].startswith("sensor inconclusive (incomplete evidence)")
                            for e in observed)


def test_a_required_phrase_past_16_kib_asks_instead_of_blaming_a_strategy(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    contract = data / "contract.txt"
    contract.write_text(FILLER + "The renewal term is twelve months.")
    submit(home, key, body_id, "MISSION", mission("m:need", checks=[note_check("term", contract, "twelve months")],
                                                  strategies=[], capabilities=["fs.read"], ceiling="read_only"))
    missions, requests = run(home, Clock(), ticks=8, step=600.0)
    assert missions["m:need"].status != "ACHIEVED"
    asks = [r for r in requests if r.get("mission_id") == "m:need"]
    assert any(r.get("kind") == "SENSOR_FAILURE" for r in asks)       # the founder learns it cannot be measured


def test_a_restarted_body_does_not_turn_an_incomplete_observation_into_a_pass(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    contract = data / "contract.txt"
    contract.write_text(FILLER + "Either party may terminate without notice.")
    submit(home, key, body_id, "MISSION", mission("m:never", checks=[_forbid("clean", contract,
                                                                             "terminate without notice")],
                                                  strategies=[], capabilities=["fs.read"], ceiling="read_only"))
    clock = Clock()
    run(home, clock, ticks=2)
    missions, _ = run(home, clock, ticks=2)                           # a new Body replays the journal
    assert missions["m:never"].status != "ACHIEVED"
    contract.write_text("A short clean contract.")                    # complete evidence now exists
    missions, _ = run(home, clock, ticks=4, step=600.0)
    assert missions["m:never"].status == "ACHIEVED"
