"""Two more ways a judge verdict claimed more than its evidence (directive of 2026-10-22, section VI; review of
#196's judge, findings J8 and J9).

- J8: an output that declares itself incomplete (``"complete": false``, e.g. a PDF with a page that has no text
  layer) limits every verdict to what more data could not undo. A field the receipt kept as a prefix, and a field the
  observation has not reached, used to be judged before that was asked: ``count_gte`` and ``equals`` decided over a
  long incomplete text, and a missing field read as ``absent``.
- J9: a predicate or bind path that steps into the receipt's own record of a cut string (``text.prefix``) read the
  16 KiB prefix as a whole string, so ``not_contains`` passed on a phrase the receipt never kept.
"""
from __future__ import annotations

import pytest

from greg.authority import RECEIPT_TEXT_LIMIT, keep_output
from greg.missions import FALSE, INSUFFICIENT, TRUE, Unbound, bound_value, judge, judge_receipt

FILLER = "proof settlement notice delivery party shall net due. " * 400       # about 22 KiB, no test phrase
PHRASE = "terminate without notice"
assert PHRASE not in FILLER and len(FILLER) > RECEIPT_TEXT_LIMIT


def p(op, value=None, field="text"):
    return {"op": op, "field": field, **({"value": value} if value is not None else {})}


def kept(output):
    return keep_output(output, None)[0]          # the receipt's kept output, no store


# -- J8 --------------------------------------------------------------------------------------------------------------

LONG_INCOMPLETE = {"text": FILLER + PHRASE, "complete": False, "pages_without_text": [2]}


@pytest.mark.parametrize("predicate, verdict", [
    (p("count_gte", len(FILLER) + 1000), INSUFFICIENT),         # before: FALSE, although more pages may add text
    (p("count_gte", 100), TRUE),                                # monotone: more data cannot shorten the text
    (p("equals", FILLER + PHRASE), INSUFFICIENT),               # before: TRUE by digest of an incomplete text
    (p("equals", "something else"), INSUFFICIENT),              # before: FALSE
    (p("gte", 3), INSUFFICIENT),                                # before: FALSE
    (p("contains", "proof settlement"), TRUE),                  # found in the kept prefix: monotone
    (p("not_contains", "proof settlement"), FALSE),
    (p("contains", PHRASE), INSUFFICIENT),                      # past the prefix: unknown, as before
])
def test_a_long_text_from_an_incomplete_observation_keeps_only_monotone_verdicts(predicate, verdict):
    assert judge(predicate, kept(LONG_INCOMPLETE))[0] == verdict


@pytest.mark.parametrize("predicate", [
    {"op": "absent", "field": "termination_clause"},            # before: TRUE
    {"op": "exists", "field": "termination_clause"},            # before: FALSE
    p("equals", "none", "termination_clause"),                  # before: FALSE
    p("not_contains", "x", "termination_clause"),               # before: FALSE
])
def test_a_field_an_incomplete_observation_has_not_reached_is_not_absent(predicate):
    output = {"text": "page one", "complete": False}
    verdict, detail = judge(predicate, output)
    assert verdict == INSUFFICIENT and "incomplete" in detail
    assert judge(predicate, output, whole=True)[0] == INSUFFICIENT


def test_a_complete_output_and_a_vouched_field_are_judged_as_before():
    assert judge({"op": "absent", "field": "x"}, {"text": "page one"})[0] == TRUE
    assert judge(p("count_gte", len(FILLER) + 1000), kept({"text": FILLER + PHRASE}))[0] == FALSE
    assert judge(p("equals", FILLER + PHRASE), kept({"text": FILLER + PHRASE}))[0] == TRUE
    vouched = {"text": FILLER, "complete": False, "decided": ["found", "text"], "found": False}
    assert judge(p("equals", False, "found"), vouched)[0] == TRUE
    assert judge(p("equals", FILLER, "text"), kept(vouched))[0] == TRUE
    assert judge(p("equals", False, "complete"), {"complete": False})[0] == TRUE


# -- J9 --------------------------------------------------------------------------------------------------------------

def test_a_path_into_the_receipts_prefix_record_decides_nothing():
    receipt = kept({"text": FILLER + PHRASE})
    assert receipt["text"]["truncated"] is True                 # the receipt holds a prefix record for text
    for field in ("text.prefix", "text.length", "text.sha256", "text.truncated"):
        verdict, detail = judge(p("not_contains", PHRASE, field), receipt)
        assert verdict == INSUFFICIENT and "kept only as a prefix" in detail, field    # before: TRUE for prefix
    assert judge(p("not_contains", PHRASE, "text"), receipt)[0] == INSUFFICIENT


def test_a_record_the_sensor_itself_returned_is_read_as_data():
    """pipeline.inspect returns another receipt's record of a cut string: its digest and length are exact facts,
    and the inspecting receipt cut nothing (it records no output_artifact). Only the prefix stays refused, as a
    prefix is never a whole string (review of #209, APR-1: J9 had made a check on value.sha256 undecidable)."""
    import hashlib
    record = kept({"text": FILLER + PHRASE})["text"]
    output = {"value": record}
    digest = hashlib.sha256((FILLER + PHRASE).encode()).hexdigest()
    result = {"output": output}                                  # the inspecting receipt recorded no cut
    assert judge_receipt(p("equals", digest, "value.sha256"), result, None)[0] == TRUE
    assert judge_receipt(p("equals", len(FILLER + PHRASE), "value.length"), result, None)[0] == TRUE
    assert judge_receipt(p("not_contains", PHRASE, "value.prefix"), result, None)[0] == INSUFFICIENT
    assert judge(p("equals", digest, "value.sha256"), output, whole=True)[0] == TRUE      # the fresh re-reading
    # a receipt that recorded a cut still refuses every part of its own record
    assert judge_receipt(p("equals", digest, "value.sha256"), {**result, "output_artifact": {"address": None}},
                         None)[0] == INSUFFICIENT


def test_over_the_whole_output_the_prefix_record_does_not_exist(tmp_path):
    output = {"text": FILLER + PHRASE}
    receipt, record = keep_output(output, tmp_path)
    result = {"output": receipt, "output_artifact": record}
    assert judge_receipt(p("not_contains", PHRASE, "text.prefix"), result, None)[0] == INSUFFICIENT
    # the whole output has no text.prefix: the field is absent, as it is in the value uncut
    assert judge_receipt(p("not_contains", PHRASE, "text.prefix"), result, tmp_path)[0] == \
        judge(p("not_contains", PHRASE, "text.prefix"), output, whole=True)[0] == FALSE


def test_a_bind_edge_into_the_prefix_record_is_unbound():
    edge = {"from": {"action_id": "a", "field": "text.prefix"}, "type": "string", "to": "body"}
    with pytest.raises(Unbound, match="kept only as a prefix"):
        bound_value(edge, kept({"text": FILLER + PHRASE}))
