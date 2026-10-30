"""One text interpretation contract for extraction, PDF reading, judgment, and appraisal.

These cases are the disagreements measured on #201 ``9977ae26`` before the contract: extraction
(``documents.find_phrase`` / ``fold``) and the PDF reader's form, against mission judgment
(``contains``) and the re-derivation appraisal uses (``evaluate_predicate``).
"""
from __future__ import annotations

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
