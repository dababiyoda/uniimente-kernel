"""One text interpretation contract for extraction, PDF reading, judgment, and appraisal.

These cases are the disagreements measured on #201 ``9977ae26`` before the contract: extraction
(``documents.find_phrase`` / ``fold``) and the PDF reader's form, against mission judgment
(``contains``) and the re-derivation appraisal uses (``evaluate_predicate``).
"""
from __future__ import annotations

import shutil

import pytest

from greg import documents, genesis as genesis_mod
from greg.missions import FALSE, INSUFFICIENT, TRUE, evaluate_predicate, judge


def _read(text: str, phrase: str) -> dict:
    """What document.text keeps: the reader's form as ``text``, and the phrase result beside it."""
    folded = documents.fold(text)
    out = documents.find_phrase(folded, {"phrase": phrase}, text + "\f", {"pdfimages": ""})
    out["text"] = folded
    return out


def test_extraction_and_judgment_agree_a_phrase_inside_a_word_is_absent():
    text = "The nonrenewal term is twelve months."
    phrase = "renewal term"
    out = _read(text, phrase)
    assert out["found"] is False
    assert judge({"op": "contains", "field": "text", "value": phrase}, out)[0] == FALSE
    assert evaluate_predicate({"op": "contains", "field": "text", "value": phrase}, out)[0] is False


def test_extraction_and_judgment_agree_on_a_curly_apostrophe():
    text = "The Tenant\u2019s deposit is held in trust."
    phrase = "Tenant\u2019s deposit"
    out = _read(text, phrase)
    assert out["found"] is True
    assert judge({"op": "contains", "field": "text", "value": phrase}, out)[0] == TRUE


def test_extraction_and_judgment_agree_on_a_line_end_hyphen():
    text = "The employee accepts a noncompete covenant for twelve months."
    phrase = "non-compete covenant"
    out = _read(text, phrase)
    assert out["found"] is True
    assert judge({"op": "contains", "field": "text", "value": phrase}, out)[0] == TRUE


def test_the_qualification_oracle_compares_in_the_reader_form(monkeypatch):
    seen = []
    real = documents.fold

    def spy(text):
        seen.append(text)
        return real(text)

    monkeypatch.setattr(documents, "fold", spy)
    documents.oracle_document_text(1)
    assert seen, "PDF qualification compared a form the reader does not use"


def test_pdf_reading_uses_the_same_form_as_extraction():
    assert genesis_mod.PARSERS["words"]("Tenant\u2019s  deposit") == documents.fold("Tenant\u2019s  deposit")


def test_a_cut_receipt_uses_the_contract_on_the_kept_prefix():
    import hashlib
    out = _read("The nonrenewal term is twelve months.", "renewal term")
    whole = out["text"]
    out["text"] = {"prefix": whole, "truncated": True,
                   "sha256": hashlib.sha256(whole.encode()).hexdigest(), "length": len(whole) + 5}
    # The substring is in the prefix; the contract's whole-word match is not, so the cut decides nothing.
    assert judge({"op": "contains", "field": "text", "value": "renewal term"}, out)[0] == INSUFFICIENT


def test_a_reading_with_no_contract_still_matches_a_raw_substring():
    # A sensor that does not record the contract (fs.read of JSON) keeps substring matching.
    assert judge({"op": "contains", "field": "text", "value": "{"}, {"text": "{\"a\": 1}"})[0] == TRUE


def test_a_receipt_under_a_different_contract_is_not_judged_or_appraised():
    from greg.appraisal import receipt_contract_holds

    out = _read("The renewal term is twelve months.", "renewal term")
    out["interpretation"]["sha256"] = "0" * 64
    verdict, detail = judge({"op": "contains", "field": "text", "value": "renewal term"}, out)
    assert verdict == INSUFFICIENT and "interpretation contract" in detail
    assert receipt_contract_holds("states", out)


def test_a_found_bit_the_contract_does_not_support_is_not_proof():
    out = _read("a b", "a")
    assert out["found"] is True
    out["found"] = False
    verdict, detail = judge({"op": "equals", "field": "found", "value": False}, out)
    assert verdict == INSUFFICIENT and "interpretation contract" in detail


def test_the_four_stages_record_and_apply_one_contract():
    import inspect

    import greg.text_interpretation as contract
    from greg import appraisal

    out = _read("a b", "a")
    assert out["interpretation"] == contract.record()
    assert contract.agrees(out["interpretation"])
    assert "receipt_contract_holds" in inspect.getsource(appraisal.appraise)
    assert inspect.getsource(appraisal.appraise).count("receipt_contract_holds") >= 2


# Review of #244: twelve readings, each judged on a receipt that records the contract and on the receipt
# #196's reader writes (text_form, no interpretation record). A false TRUE closes a mission.
CURLY = "Tenant\u2019s deposit"
DRAWN = "The  Tenant\u2019s  deposit is held."
FOLDED_LEASE = "The Tenant's deposit is held in trust."
JOINED = "The employee accepts a noncompete covenant for twelve months."
NONRENEWAL = "The nonrenewal term is twelve months."


def _receipt(text, *, interpretation: bool, **extra) -> dict:
    from greg import text_interpretation
    out = {"text": text, "text_form": documents.FOLDING, "complete": True}
    if interpretation:
        out["interpretation"] = text_interpretation.record()
    out.update(extra)
    return out


def _matrix():
    """(name, predicate, text or None, extra, want). text None: the case builds its own output."""
    return [
        ("C1", {"op": "not_contains", "field": "text", "value": CURLY}, FOLDED_LEASE, {}, FALSE),
        ("C2", {"op": "not_contains", "field": "text", "value": CURLY},
         "The Tenant\u02bcs deposit is held in trust.", {}, FALSE),
        ("C3", {"op": "not_contains", "field": "text", "value": "non-compete covenant"}, JOINED, {}, FALSE),
        ("C4", {"op": "contains", "field": "text", "value": "renewal term"}, NONRENEWAL, {}, FALSE),
        ("C5", {"op": "contains", "field": "text", "value": " renewal term "}, NONRENEWAL, {}, FALSE),
        ("C6", {"op": "not_contains", "field": "text", "value": "Tenant"}, FOLDED_LEASE, {}, FALSE),
        ("C7", {"op": "not_contains", "field": "text", "value": "deposit"}, "The deposits are held.", {}, FALSE),
        ("C8", {"op": "contains", "field": "text", "value": "   "}, NONRENEWAL, {}, FALSE),
        ("C9", {"op": "equals", "field": "text", "value": DRAWN}, documents.fold(DRAWN), {}, TRUE),
        ("C10", {"op": "not_contains", "field": "clauses", "value": CURLY}, "x",
         {"clauses": ["Tenant's deposit"]}, FALSE),
        ("C11", {"op": "contains", "field": "text", "value": "\ufb01nal notice"},
         "The final notice was served.", {}, TRUE),
    ]


def test_modifier_apostrophe_and_the_fold_are_stable():
    folded = documents.fold("Tenant\u02bcs  ﬁnal–notice")
    assert folded == documents.fold(folded)
    assert "Tenant's" in folded and "final-notice" in folded
    assert "\u02bc" not in folded and "\ufb01" not in folded


@pytest.mark.parametrize("interpretation", [True, False])
@pytest.mark.parametrize("name, predicate, text, extra, want", _matrix())
def test_review_matrix_does_not_close_on_a_false_reading(interpretation, name, predicate, text, extra, want):
    verdict, _detail = judge(predicate, _receipt(text, interpretation=interpretation, **extra))
    assert verdict == want, name


@pytest.mark.parametrize("interpretation", [True, False])
def test_a_reading_nested_beside_its_form_is_the_reading_that_is_judged(interpretation):
    """C12. The text and its form sit at result.output, not on the object the judge is handed."""
    inner = _receipt(FOLDED_LEASE, interpretation=interpretation)
    verdict, _detail = judge({"op": "not_contains", "field": "result.output.text", "value": CURLY},
                             {"result": {"output": inner}})
    assert verdict == FALSE


@pytest.mark.parametrize("interpretation", [True, False])
def test_a_prefix_cut_mid_word_does_not_prove_the_shorter_word(interpretation):
    """Kept-prefix probe. 'renewal' cut out of 'renewals' is not a whole word in the whole text, and the
    prefix must not read contains as true."""
    import hashlib
    whole = "The renewals are annual."
    prefix = whole[:whole.index("renewal") + len("renewal")]
    assert prefix.endswith("renewal") and not whole[len(prefix):].startswith(" ")
    cut = {"prefix": prefix, "truncated": True, "sha256": hashlib.sha256(whole.encode()).hexdigest(),
           "length": len(whole)}
    kept = _receipt(whole, interpretation=interpretation)
    kept["text"] = cut
    assert judge({"op": "contains", "field": "text", "value": "renewal"}, _receipt(whole, interpretation=interpretation))[0] \
        == FALSE
    assert judge({"op": "contains", "field": "text", "value": "renewal"}, kept)[0] == INSUFFICIENT


def test_a_whole_word_inside_a_kept_prefix_is_still_present():
    import hashlib
    whole = "The renewal term is twelve months. " + "tail"
    prefix = whole[:whole.index("months") + len("months. ")]
    cut = {"prefix": prefix, "truncated": True, "sha256": hashlib.sha256(whole.encode()).hexdigest(),
           "length": len(whole)}
    out = _receipt(whole, interpretation=True)
    out["text"] = cut
    assert judge({"op": "contains", "field": "text", "value": "renewal term"}, out)[0] == TRUE


def test_an_undeclared_form_does_not_decide_an_absence_the_code_points_miss():
    out = {"text": FOLDED_LEASE, "text_form": "raw code points"}
    verdict, detail = judge({"op": "not_contains", "field": "text", "value": CURLY}, out)
    assert verdict == INSUFFICIENT and "interpretation contract" in detail


def test_a_blank_phrase_decides_neither_claim():
    out = _receipt(NONRENEWAL, interpretation=True)
    assert judge({"op": "contains", "field": "text", "value": "   "}, out)[0] == FALSE
    assert judge({"op": "not_contains", "field": "text", "value": "   "}, out)[0] == FALSE


def test_not_contains_tenant_on_a_lease_that_states_it_does_not_close(tmp_path):
    """End to end, real pdftotext. A lease that states "Tenant's" must not achieve on not_contains "Tenant".
    On #244 that check closed ACHIEVED; the base and #196 left it false."""
    if shutil.which("pdftotext") is None or genesis_mod.installed_binary("pdftotext") is None:
        pytest.skip("pdftotext not installed on this body")
    from tests.greg_fixtures import Clock, make_body, mission
    from tests.unit.test_greg_missions import run, submit
    home, key, body_id, data = make_body(tmp_path)
    lease = data / "lease.pdf"
    lease.write_bytes(documents.write_pdf([["The Tenant's deposit is held in trust."]]))
    check = {"check_id": "absent", "description": "lease.pdf does not name the tenant",
             "sensor": {"function": "document.text", "params": {"path": str(lease)}, "target": "fs:lease.pdf"},
             "predicate": {"op": "not_contains", "field": "text", "value": "Tenant"}}
    submit(home, key, body_id, "MISSION", mission("m:lease", checks=[check], strategies=[],
                                                  capabilities=["fs.read", "acquired.document.text.*"],
                                                  ceiling="read_only", auto_attach=True))
    missions, _requests = run(home, Clock(), ticks=4)
    assert missions["m:lease"].status != "ACHIEVED"
    from tests.unit.test_greg_missions import events
    observed = [e for e in events(home, "mission.observed") if e["mission_id"] == "m:lease"]
    assert observed and observed[-1]["passed"] is False
    assert "Tenant" in observed[-1]["detail"] and not observed[-1]["detail"].startswith("sensor ")


# Review of #250 (owner of #209/#228/#229). A whole-word hit is proof only when the kept text closes both of its
# boundaries. The receipt keeps a long text's first RECEIPT_TEXT_LIMIT characters; a hit that only closing
# punctuation separates from the cut may continue past it ("$1,000" in "$1,000,000", "Tenant" in "Tenant's").
def _long_reading(tail: str, phrase: str) -> dict:
    """A reading whose text the receipt cuts two characters after ``phrase`` (inside ``tail``)."""
    from greg.authority import RECEIPT_TEXT_LIMIT
    pad = RECEIPT_TEXT_LIMIT - 2 - len(phrase) - tail.index(phrase)
    text = documents.fold(("proof " * pad)[:pad - pad % 6 - 1] + "x" * (pad % 6) + " " + tail)
    assert text.index(phrase, RECEIPT_TEXT_LIMIT - 200) + len(phrase) + 2 == RECEIPT_TEXT_LIMIT
    out = documents.find_phrase(text, {}, text, {"pdfimages": ""})
    out["text"] = text
    return out


@pytest.mark.parametrize("interpretation", [True, False])
@pytest.mark.parametrize("tail, phrase", [("The fee is $1,000,000 per year.", "$1,000"),
                                          ("The Tenant’s deposit is held.", "Tenant"),
                                          ("See renewal.example now.", "renewal")])
def test_a_hit_the_cut_leaves_open_after_closing_punctuation_is_not_presence(tmp_path, interpretation, tail, phrase):
    from greg.authority import keep_output
    from greg.missions import judge_receipt
    out = _long_reading(tail, phrase)
    if not interpretation:
        out.pop("interpretation")
    predicate = {"op": "contains", "field": "text", "value": phrase}
    assert judge(predicate, out, whole=True)[0] == FALSE           # not a whole word in the whole text
    kept, record = keep_output(out, tmp_path)
    assert isinstance(kept["text"], dict) and record["address"]
    assert judge(predicate, kept)[0] == INSUFFICIENT               # the prefix alone cannot tell
    verdict, detail = judge_receipt(predicate, {"output": kept, "output_artifact": record}, tmp_path)
    assert verdict == FALSE, detail                                # decided over the whole output it kept


@pytest.mark.parametrize("kept_as", ["text", "prefix record"])
def test_a_text_kept_as_its_end_does_not_prove_the_word_it_begins_with(kept_as):
    import hashlib
    tail = "renewal term is twelve months."
    whole = "The nonrenewal term is twelve months."
    assert judge({"op": "contains", "field": "text", "value": "renewal term"}, _receipt(whole, interpretation=True))[0] \
        == FALSE
    value = tail if kept_as == "text" else {"prefix": tail, "truncated": True, "length": len(tail) + 9,
                                            "sha256": hashlib.sha256(b"x").hexdigest()}
    out = _receipt(tail, interpretation=True, complete=False, cut_at={"text": "start"}, decided=[])
    out["text"] = value
    assert judge({"op": "contains", "field": "text", "value": "renewal term"}, out)[0] == INSUFFICIENT
    # a word the kept text opens itself is still present
    assert judge({"op": "contains", "field": "text", "value": "twelve"}, out)[0] == TRUE


@pytest.mark.parametrize("record", ["contract", "text_form only", "foreign contract", "foreign inside a contract"])
def test_an_inspected_reading_is_judged_under_its_producers_contract(tmp_path, record):
    """pipeline.inspect hands the producer's declaration on beside the value, as it hands on ``complete``. Before,
    it dropped it, and not_contains on a curly-apostrophe phrase read the folded lease as absent (TRUE)."""
    from greg import text_interpretation
    from greg.body import Body
    from tests.greg_fixtures import signed
    from tests.unit.test_greg_handoff_evidence import _body_with, _inspect, _produce, _ref
    reading = _read("The Tenant’s deposit is held in trust.", "deposit")
    if record == "text_form only":
        reading.pop("interpretation")
    if record == "foreign contract":
        reading["interpretation"] = {**text_interpretation.record(), "id": "greg.text-interpretation/0"}
    produced = {"reading": reading, "note": "a producer that nests its reading"}
    if record == "foreign inside a contract":     # the declaration nearest the text decides, as the judge reads it
        reading["interpretation"] = {**text_interpretation.record(), "id": "greg.text-interpretation/0"}
        produced.update(interpretation=text_interpretation.record(), text_form=documents.FOLDING)
    home, key, body_id, spec = _body_with(tmp_path)
    with Body(home) as body:
        body.apply(signed(key, body_id, "MISSION", spec), channel="inbox")
        state = body.engine.book.missions["m:hand"]
        _produce(body, state, "read", produced)
        inspected = _inspect(body, state, _ref("read", "reading.text", "string"))
    predicate = {"op": "not_contains", "field": "value", "value": CURLY}
    assert judge({"op": "not_contains", "field": "reading.text", "value": CURLY}, produced)[0] == \
        judge(predicate, inspected)[0] == (INSUFFICIENT if record.startswith("foreign") else FALSE)
