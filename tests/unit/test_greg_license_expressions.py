"""License expression semantics: what a declaration permits in GREG's use (directive of 2026-10-22, section VII).

The review of #201 at a1d2abf (GitHub comment 6476294065, findings SPDX-1 to SPDX-7) showed declarations whose
restrictive term was dropped, masked by an unknown neighbour, or never read, and one harmless phrase read as a
restriction. Each case below failed on a1d2abf. The rules they pin:

- AND applies every term (its obligations are conjunctive); OR is usable when one whole alternative is, and terms
  are never mixed across alternatives; WITH binds an exception to its license and never loosens anything else;
  parentheses and SPDX precedence (WITH, then AND, then OR) hold in both SPDX and DEP-5 syntax.
- A known restrictive term is never masked by an unknown neighbour, and an unknown never becomes a clearance.
- Open-source, source-available, restricted-use and unclassified terms are distinguished.

This is a small assessor, not a legal engine: it reads what a package declares and says what it cannot read.
"""
from __future__ import annotations

import itertools
from email.message import Message

import pytest

from greg import licensing as L

P, W, S, N, X, U = L.PERMISSIVE, L.WEAK_COPYLEFT, L.STRONG_COPYLEFT, L.NETWORK_COPYLEFT, L.NOT_OPEN, L.UNKNOWN
USE = L.GREG_USE
MITC = "License :: OSI Approved :: MIT License"
APACHE = "License :: OSI Approved :: Apache Software License"


class FakeDist:
    """Installed-distribution metadata only, as importlib.metadata exposes it."""

    def __init__(self, name, expression=None, classifiers=(), text=None):
        self.metadata = Message()
        self.metadata["Name"] = name
        if expression:
            self.metadata["License-Expression"] = expression
        for c in classifiers:
            self.metadata["Classifier"] = c
        if text:
            self.metadata["License"] = text


def assess(expression=None, classifiers=(), text=None):
    return L.assess(FakeDist("p", expression, classifiers, text))


def deb(field):
    """One DEP-5 Files paragraph carrying ``field`` as its License."""
    return L.dep5(f"Format: x\n\nFiles: *\nCopyright: a\nLicense: {field}\n")


def held(parsed):
    return [t["id"] for t in L._held_terms(parsed["terms"])]


class Binary:
    capability_id, provider = "acquired.x.tool", "installed:/usr/bin/tool"

    def __init__(self, copyright_text):
        self.provenance = {"license_assessment": L.binary_assessment("tool", copyright_text)}


def p0_attaches(field):
    return L.attach_check(Binary(f"Format: x\n\nFiles: *\nCopyright: a\nLicense: {field}\n"), "P0")[0]


# -- SPDX-1: a DEP-5 "with" addition stricter than its base license ----------------------------------------------

@pytest.mark.parametrize("field, cls", [
    ("Apache-2.0 with Commons-Clause", X), ("Apache-2.0 with Commons Clause", X), ("MIT with SSPL-1.0", X),
    ("BSD-3-clause with Commons-Clause restriction", X), ("GPL-2+ with Commons-Clause exception", X),
    ("Custom-License with Commons-Clause", X),                   # an unknown base never hides the addition
    # an exception grants a permission: the base license keeps its class
    ("GPL-2+ with OpenSSL exception", S), ("GPL-3+ with Autoconf-data exception", S),
    ("GPL-2.0-only WITH Classpath-exception-2.0", W), ("Apache-2.0 WITH LLVM-exception", P)])
def test_a_dep5_addition_is_classified_and_only_an_exception_keeps_the_base_class(field, cls):
    parsed = deb(field)
    assert parsed["class"] == cls
    assert bool(held(parsed)) is (cls in (N, X))


def test_a_binary_whose_license_carries_a_restrictive_addition_is_held_under_p0():
    assert p0_attaches("Apache-2.0 with Commons-Clause") is False
    assert p0_attaches("GPL-2+ with OpenSSL exception") is True


# -- SPDX-2: within one License field, an unknown name must not mask a restrictive one ---------------------------

@pytest.mark.parametrize("field, cls, is_held", [
    ("non-free and custom", U, True), ("custom and non-free", U, True), ("non-free, and custom", U, True),
    ("AGPL-3+ and Sundry", U, True), ("GPL-2+ and (custom or non-free)", X, True),
    ("(MIT OR AGPL-3.0-only) AND SSPL-1.0", X, True), ("(MIT OR Apache-2.0) AND Unicode-DFS-2016", P, False),
    ("MIT or non-free", P, False),                               # an alternative GREG may take avoids it
    ("MIT or AGPL-3+ and non-free", P, False),                   # "and" binds tighter than "or"
    ("custom", U, False)])                                       # unknown alone: P0's prior behaviour, not a hold
def test_an_unknown_name_never_masks_a_restrictive_one(field, cls, is_held):
    parsed = deb(field)
    assert (parsed["class"], bool(held(parsed))) == (cls, is_held)


def test_an_unparseable_field_is_unknown_and_still_shows_its_restrictive_names():
    parsed = deb("SSPL-1.0 and (custom")
    assert parsed["class"] == U and held(parsed) == ["SSPL-1.0 and (custom"]
    a = assess(classifiers=[MITC], text="SSPL-1.0 AND (MIT")
    assert a["verdict"] == "FOUNDER_REVIEW" and a["class"] == X


def test_on_a_tie_or_elects_the_alternative_without_a_known_restriction():
    """OR elects the alternative GREG would rely on (on a tie, one without a known restriction), whatever the order.
    Under P0 the hold is monotone (verification of 083c91ea, finding 8): with no cleared alternative, a known
    restriction in any alternative holds, so a stricter alternative never releases a hold. An unknown alternative
    is not evidence that the restriction can be avoided."""
    parsed = deb("(AGPL-3+ and custom) or other-custom")
    assert parsed["class"] == U and held(parsed) == ["(AGPL-3+ and custom) or other-custom"]
    assert assess("(AGPL-3.0-only AND LicenseRef-A) OR LicenseRef-B")["restrictive"] == []
    assert assess("LicenseRef-B OR (AGPL-3.0-only AND LicenseRef-A)")["restrictive"] == []
    for weaker, stricter in (("non-free or Sundry", "(non-free and Sundry) or Sundry"),
                             ("MIT or AGPL-3+", "(MIT and non-free) or AGPL-3+")):
        assert not p0_attaches(stricter) or p0_attaches(weaker), (weaker, stricter)
    assert p0_attaches("non-free or Sundry") is False and p0_attaches("(non-free and Sundry) or Sundry") is False
    assert p0_attaches("MIT or AGPL-3+") is True                # a cleared alternative is relied on


def test_a_binary_whose_field_pairs_a_restriction_with_an_unknown_is_held_under_p0():
    assert p0_attaches("non-free and custom") is False
    assert p0_attaches("custom") is True                        # undeterminable: unchanged


# -- SPDX-3: classifiers are read beside a License-Expression ------------------------------------------------

@pytest.mark.parametrize("expression, classifiers, verdict, cls", [
    ("MIT", ["License :: Other/Proprietary License"], "FOUNDER_REVIEW", X),
    ("MIT", ["License :: Free for non-commercial use"], "FOUNDER_REVIEW", X),
    ("Apache-2.0", ["License :: OSI Approved :: GNU Affero General Public License v3"], "FOUNDER_REVIEW", N),
    ("MIT", ["License :: OSI Approved", MITC], "CLEARED", P),
    ("MIT", ["License :: OSI Approved :: Academic Free License (AFL)"], "CLEARED", P),   # unrecognised: informational
    ("MIT OR AGPL-3.0-only", [MITC, "License :: OSI Approved :: GNU Affero General Public License v3"],
     "CLEARED", P)])                                             # classifiers naming the alternatives agree
def test_a_stricter_classifier_beside_an_expression_counts(expression, classifiers, verdict, cls):
    a = assess(expression, classifiers)
    assert (a["verdict"], a["class"]) == (verdict, cls)


def test_a_disagreeing_less_strict_classifier_is_recorded_as_uncertainty():
    a = assess("GPL-3.0-or-later", [MITC])
    assert (a["verdict"], a["class"]) == ("CLEARED_WITH_OBLIGATIONS", S)
    assert any("disagree" in u for u in a["uncertainty"])


# -- SPDX-4: a short License field beside a primary declaration --------------------------------------------------

@pytest.mark.parametrize("classifier, field, cls", [
    (APACHE, "Apache-2.0 WITH Commons-Clause", X), (APACHE, "Apache 2.0 with Commons Clause", X),
    (MITC, "SSPL", X), (MITC, "CC BY-NC 4.0", X), (MITC, "ELv2", X), (MITC, "Elastic License 2.0", X),
    (MITC, "BSL 1.1", X), (MITC, "Business Source License 1.1", X), (MITC, "AGPLv3+", N),
    (MITC, "GNU Affero GPL v3", N), (MITC, "LicenseRef-Proprietary", U)])
def test_restrictive_spellings_and_unclassified_spdx_in_the_license_field_count(classifier, field, cls):
    a = assess(classifiers=[classifier], text=field)
    assert (a["verdict"], a["class"]) == ("FOUNDER_REVIEW", cls)


def test_boost_and_free_text_beside_a_classifier_are_not_mistaken_for_restrictions():
    assert assess(classifiers=[MITC], text="BSL-1.0")["verdict"] == "CLEARED"       # Boost, not Business Source
    assert L._debian_class("BSL") != X
    assert assess(classifiers=[MITC], text="MIT, see LICENSE.txt")["verdict"] == "CLEARED"


# -- SPDX-5: restrictive families at every version -------------------------------------------------------------

@pytest.mark.parametrize("name, cls", [
    ("CC-BY-NC-3.0", X), ("CC-BY-NC-SA-2.0", X), ("CC-BY-ND-3.0", X), ("CC-BY-NC-ND-2.5", X),
    ("AGPL-1.0", N), ("AGPL-1.0-or-later", N), ("AGPL-1.0-only", N)])
def test_restrictive_license_families_are_classified_at_every_version(name, cls):
    assert L._debian_class(name) == cls
    assert assess(name)["class"] == cls


def test_a_family_rule_never_clears_anything():
    assert L._debian_class("CC-BY-SA-3.0") == U and L._debian_class("GPL-2-with-something") == U


# -- SPDX-6: a second License line in one DEP-5 paragraph ------------------------------------------------------

def test_a_second_license_line_in_one_paragraph_is_not_dropped():
    p = L.dep5("Format: x\n\nFiles: *\nCopyright: a\nLicense: AGPL-3+\nFiles: lib/*\nCopyright: b\nLicense: Expat\n")
    assert p["class"] == N and held(p) == ["AGPL-3+"]
    assert [(t["id"], t["files"]) for t in p["terms"]] == [("AGPL-3+", ["*"]), ("Expat", ["lib/*"])]
    q = L.dep5("Format: x\n\nFiles: *\nCopyright: a\nLicense: SSPL-1.0\nLicense: Expat\n")
    assert q["class"] == X and held(q) == ["SSPL-1.0"] and [t["id"] for t in q["terms"]] == ["SSPL-1.0", "Expat"]


# -- SPDX-7: an inclusive phrase is not a restriction ---------------------------------------------------------

@pytest.mark.parametrize("field, verdict", [
    ("MIT. Free for commercial and non-commercial use.", "CLEARED"),
    ("MIT; free for both commercial and non-commercial purposes", "CLEARED"),
    ("MIT, commercial and/or non-commercial use permitted", "CLEARED"),
    ("Free for non-commercial use only", "FOUNDER_REVIEW"),
    ("For non-commercial use. Commercial use requires a license.", "FOUNDER_REVIEW")])
def test_an_inclusive_commercial_phrase_is_not_a_non_commercial_restriction(field, verdict):
    assert assess(classifiers=[MITC], text=field)["verdict"] == verdict


# -- section VII: AND, OR, WITH, precedence, variants, unknowns --------------------------------------------------

def test_and_obligations_are_conjunctive():
    a = assess("MIT AND GPL-3.0-only")
    assert a["obligations"] == sorted({L.OBLIGATIONS[P], L.OBLIGATIONS[S]})
    q = L.qualify_use([a], USE, {})
    assert [t["id"] for t in q["terms"]] == ["MIT", "GPL-3.0-only"] and len(q["obligations"]) == 2


def test_or_takes_one_whole_alternative_and_never_mixes_terms_across_alternatives():
    a = assess("MIT OR GPL-3.0-only")
    assert a["class"] == P and a["obligations"] == [L.OBLIGATIONS[P]]
    q = L.qualify_use([a], USE, {})
    assert q["verdict"] == L.COMPATIBLE and q["obligations"] == [L.OBLIGATIONS[P]]
    assert [t["id"] for t in q["terms"]] == ["MIT"] and [t["id"] for t in q["not_elected"]] == ["GPL-3.0-only"]


@pytest.mark.parametrize("expression, use, verdict", [
    ("GPL-3.0-only OR MIT", {**USE, "interaction": "linked"}, L.COMPATIBLE),
    ("GPL-3.0-only OR AGPL-3.0-only", {**USE, "interaction": "linked"}, L.UNCERTAIN),
    ("AGPL-3.0-only OR BUSL-1.1", USE, L.COMPATIBLE),
    ("AGPL-3.0-only OR BUSL-1.1", {**USE, "network": "serves_users"}, L.UNCERTAIN),
    ("BUSL-1.1 OR LicenseRef-Acme", USE, L.UNCERTAIN)])
def test_a_component_is_usable_when_one_alternative_is_usable_in_the_intended_context(expression, use, verdict):
    assert L.qualify_use([assess(expression)], use, {})["verdict"] == verdict


class PythonManifest:
    capability_id, provider = "acquired.x.p", "installed:python:p==1.0"

    def __init__(self, assessment):
        self.provenance = {"distribution": "p", "version": "1.0", "license_assessment": assessment}


def _clearance(manifest, **over):
    q = L.capability_qualification(manifest)
    return {"assessment_digest": q["assessment_digest"], "use": q["use"], "basis": "read LICENSE-ACME: internal use",
            "obligations_accepted": q["obligations"], **over}


def test_a_not_open_alternative_the_use_does_not_take_needs_no_permission_evidence():
    held_pkg = PythonManifest(assess("(MIT OR SSPL-1.0) AND LicenseRef-Acme"))
    assert held_pkg.provenance["license_assessment"]["verdict"] == "FOUNDER_REVIEW"      # the LicenseRef is unread
    q = L.capability_qualification(held_pkg)
    assert q["verdict"] == L.UNCERTAIN and "SSPL-1.0" not in [t["id"] for t in q["terms"]]
    ok, why, record = L.founder_attach_check(held_pkg, {"license_clearance": _clearance(held_pkg)}, "D-LIC-1", "P0")
    assert ok, why
    assert record["elected_terms"] == ["MIT", "LicenseRef-Acme"]           # the clearance names what it relies on
    # where every alternative is not open, a signature is not enough: the rights holder's permission is
    every = PythonManifest(assess("(Elastic-2.0 OR SSPL-1.0) AND MIT"))
    ok, why, _ = L.founder_attach_check(every, {"license_clearance": _clearance(every)}, "D-LIC-1", "P0")
    assert not ok and "third-party rights" in why


@pytest.mark.parametrize("expression, cls", [
    ("MIT OR Apache-2.0 AND BUSL-1.1", P), ("(MIT OR Apache-2.0) AND BUSL-1.1", X),
    ("GPL-2.0-only", S), ("GPL-2.0-or-later", S), ("GPL-2.0+", S), ("AGPL-3.0-or-later", N),
    ("GPL-2.0-only WITH Classpath-exception-2.0", W), ("LicenseRef-Acme WITH Classpath-exception-2.0", U)])
def test_precedence_parentheses_variants_and_exceptions(expression, cls):
    assert assess(expression)["class"] == cls


def test_an_unknown_identifier_is_named_and_never_cleared_and_never_hides_a_restriction():
    a = assess("MIT AND LicenseRef-Acme")
    assert a["verdict"] == "FOUNDER_REVIEW" and any("LicenseRef-Acme" in u for u in a["uncertainty"])
    a = assess("SSPL-1.0 AND LicenseRef-Acme")
    assert a["class"] == U and a["restrictive"] == ["SSPL-1.0"] and "SSPL-1.0" in a["reason"]
    assert assess("MIT OR LicenseRef-Acme")["verdict"] == "CLEARED"       # GREG may take MIT


@pytest.mark.parametrize("expression, category", [
    ("MIT", "open_source"), ("AGPL-3.0-only", "open_source"), ("BUSL-1.1", "source_available"),
    ("SSPL-1.0", "source_available"), ("Elastic-2.0", "source_available"), ("CC-BY-NC-4.0", "restricted_use"),
    ("JSON", "restricted_use"), ("LicenseRef-Acme", "unclassified")])
def test_open_source_source_available_restricted_use_and_unclassified_are_distinguished(expression, category):
    a = assess(expression)
    assert a["categories"] == [category]
    q = L.qualify_use([a], USE, {})
    assert q["terms"][0]["category"] == category
    if category == "source_available":
        assert "source-available" in q["reason"]


def test_dep5_records_which_files_each_license_covers_and_the_assumption_it_rests_on():
    text = ("Format: x\nLicense: GPL-2+\n\nFiles: *\nCopyright: a\nLicense: GPL-2+\n\n"
            "Files: lib/vendored/*\n src/third_party/*\nCopyright: b\nLicense: Expat\n\n"
            "Files: debian/*\nCopyright: c\nLicense: GPL-2+\n\nLicense: Expat\n Permission is hereby granted...\n")
    p = L.dep5(text)
    assert [(t["stanza"], t["files"], t["id"]) for t in p["terms"]] == [
        ("header", None, "GPL-2+"), ("files", ["*"], "GPL-2+"),
        ("files", ["lib/vendored/*", "src/third_party/*"], "Expat"), ("files", ["debian/*"], "GPL-2+")]
    a = L.binary_assessment("tool", text)
    assert a["verdict"] == "CLEARED_WITH_OBLIGATIONS" and any("Files stanza" in u for u in a["uncertainty"])


def test_a_header_summary_that_disagrees_with_the_files_stanzas_is_recorded_and_both_apply():
    a = L.binary_assessment("tool", "Format: x\nLicense: Expat\n\nFiles: *\nCopyright: a\nLicense: AGPL-3+\n")
    assert a["verdict"] == "FOUNDER_REVIEW" and any("header" in u for u in a["uncertainty"])
    agree = L.binary_assessment("tool", "Format: x\nLicense: GPL-3+\n\nFiles: *\nCopyright: a\nLicense: GPL-3+\n")
    assert not any("header" in u for u in agree["uncertainty"])


def test_a_files_stanza_without_a_license_is_unclassified_not_ignored():
    p = L.dep5("Format: x\n\nFiles: *\nCopyright: a\nLicense: MIT\n\nFiles: blob/*\nCopyright: b\n")
    assert p["class"] == U and p["terms"][-1]["files"] == ["blob/*"]


def test_the_structured_use_verdict_states_reasons_and_uncertainty():
    q = L.qualify_use([assess("GPL-3.0-or-later AND LicenseRef-Acme")], USE, {"distribution": "p"})
    assert q["verdict"] == L.UNCERTAIN and "LicenseRef-Acme" in q["reason"]
    assert any("LicenseRef-Acme" in u for u in q["uncertainty"]) and q["limits"] == L.LIMITS
    clean = L.qualify_use([assess("GPL-3.0-or-later")], USE, {})
    assert clean["verdict"] == L.COMPATIBLE and clean["reason"] == "every declared term permits this use"


# -- exhaustive: the evaluator against an independent DNF expansion -------------------------------------------
# Every expression of three atoms in seven shapes, in both SPDX and DEP-5 syntax. The oracle expands the test's own
# tree into disjunctive normal form; it shares no code with the parser or the evaluator.

ATOMS = {"spdx": (("MIT", P), ("GPL-3.0-only", S), ("AGPL-3.0-only", N), ("BUSL-1.1", X), ("LicenseRef-Acme", U)),
         "dep5": (("Expat", P), ("GPL-3+", S), ("AGPL-3+", N), ("non-free", X), ("Sundry", U))}
SHAPES = (("and", 0, ("and", 1, 2)), ("or", 0, ("or", 1, 2)), ("or", ("and", 0, 1), 2), ("or", 0, ("and", 1, 2)),
          ("and", ("or", 0, 1), 2), ("and", 0, ("or", 1, 2)), ("or", ("and", 0, 1), ("and", 1, 2)))
RANK = {c: i for i, c in enumerate((P, W, S, N, X, U))}


def _render(shape, names, dialect, top=True):
    if isinstance(shape, int):
        return names[shape]
    op, a, b = shape
    word = op.upper() if dialect == "spdx" else op
    text = f"{_render(a, names, dialect, False)} {word} {_render(b, names, dialect, False)}"
    return text if top else f"({text})"


def _dnf(shape, classes):
    if isinstance(shape, int):
        return [[shape]]
    op, a, b = shape
    left, right = _dnf(a, classes), _dnf(b, classes)
    return left + right if op == "or" else [x + y for x in left for y in right]


CASES = [(d, s, combo) for d in ATOMS for s in SHAPES for combo in itertools.product(range(5), repeat=3)]


@pytest.mark.parametrize("dialect, shape, combo", CASES)
def test_the_evaluator_matches_an_independent_dnf_expansion(dialect, shape, combo):
    names = [ATOMS[dialect][i][0] for i in combo]
    classes = [ATOMS[dialect][i][1] for i in combo]
    text = _render(shape, names, dialect)
    conjunctions = [[classes[i] for i in conj] for conj in _dnf(shape, classes)]
    expected = min((max(c, key=RANK.get) for c in conjunctions), key=RANK.get)
    some_clear = any(all(RANK[c] <= RANK[S] for c in conj) for conj in conjunctions)
    every_restricted = all(any(c in (N, X) for c in conj) for conj in conjunctions)
    if dialect == "spdx":
        a = L.assess(FakeDist("p", text))
        cls, cleared, restricted = a["class"], a["auto_attach"], bool(a["restrictive"])
    else:
        p = deb(text)
        cls, cleared, restricted = p["class"], RANK[p["class"]] <= RANK[S], bool(held(p))
    assert cls == expected, text
    assert cleared is some_clear, text                   # an unknown never clears; one clear alternative does
    if every_restricted:
        assert restricted, text                          # an unavoidable restriction is never masked
    if some_clear:
        assert not restricted, text                      # an avoidable one is not reported as binding
    # the use verdict elects one whole alternative: its terms form one DNF conjunction
    q = L.qualify_use([a if dialect == "spdx" else {"parts": [{"terms": p["terms"]}]}], USE, {})
    elected = sorted(t["id"] for t in q["terms"])
    assert any(elected == sorted({names[i] for i in conj}) or elected == sorted(names[i] for i in conj)
               for conj in _dnf(shape, classes)), text


# -- independent verification of 083c91ea (workflow verify:licensing, 2026-10-30): ten findings -------------------

@pytest.mark.parametrize("field", ["Commercial and non-commercial use require a separate license",
                                   "Commercial or non-commercial use prohibited without permission",
                                   "prohibited noncommercial OR commercial"])
def test_v1_a_restriction_that_contains_the_inclusive_phrase_is_still_read(field):
    """Regression against a1d2abf: the inclusive mask cleared these beside an MIT classifier."""
    assert assess(classifiers=[MITC], text=field)["verdict"] == "FOUNDER_REVIEW"


def test_v2_a_license_line_before_its_files_line_belongs_to_that_stanza():
    """Regression against a1d2abf: the License was cut off, so P0 attached an AGPL binary."""
    p = L.dep5("Format: x\n\nCopyright: a\nLicense: AGPL-3+\nFiles: *\n")
    assert p["class"] == N and held(p) == ["AGPL-3+"]
    assert L.attach_check(Binary("Format: x\n\nCopyright: a\nLicense: AGPL-3+\nFiles: *\n"), "P0")[0] is False
    q = L.dep5("Format: x\nLicense: MIT\nFiles: *\nLicense: SSPL-1.0\n")       # header then Files, no blank line
    assert held(q) == ["SSPL-1.0"] and [t["stanza"] for t in q["terms"]] == ["header", "files"]


@pytest.mark.parametrize("field", ["Apache-2.0 with Commons Clause (see LICENSE)", "Business Source License 1.1 (see below)",
                                   "Server Side Public License (MongoDB)", "Elastic License 2.0 (see LICENSE)"])
def test_v3_an_unparseable_field_keeps_its_multi_word_restrictive_names(field):
    assert p0_attaches(field) is False


@pytest.mark.parametrize("field", ["Elastic-2.0 (see LICENSE.txt)", "Elastic-2.0, see LICENSE", "SSPLv1", "BUSLv1.1"])
def test_v4_other_spellings_of_listed_not_open_licenses_count_beside_a_classifier(field):
    a = assess(classifiers=[MITC], text=field)
    assert a["verdict"] == "FOUNDER_REVIEW" and a["class"] == X, field


def test_v5_an_unparseable_expression_still_reads_the_declarations_beside_it():
    a = assess("MIT AND", ["License :: Other/Proprietary License"])
    assert "Other/Proprietary License" in a["restrictive"]
    assert L.qualify_use([a], USE, {})["verdict"] == L.INCOMPATIBLE        # D-LIC-1 would need permission evidence
    b = assess("MIT AND", text="Commons Clause applies")
    assert any("commons" in r.lower() for r in b["restrictive"])


@pytest.mark.parametrize("expression, classifiers, verdict", [
    ("MIT", ["License :: Shareware"], "FOUNDER_REVIEW"),
    ("MIT", ["License :: Free To Use But Restricted"], "FOUNDER_REVIEW"),
    ("MIT", ["License :: Aladdin Free Public License (AFPL)"], "FOUNDER_REVIEW"),
    ("MIT", ["License :: Repoze Public License"], "FOUNDER_REVIEW"),             # non-OSI, not listed: unknown terms
    ("MIT OR BUSL-1.1", ["License :: Free for non-commercial use"], "FOUNDER_REVIEW"),
    ("MIT OR BUSL-1.1", ["License :: Other/Proprietary License"], "FOUNDER_REVIEW")])
def test_v6_a_restrictive_or_unknown_classifier_beside_an_expression_is_never_silent(expression, classifiers, verdict):
    assert assess(expression, classifiers)["verdict"] == verdict


def test_v6_an_unrecognised_osi_classifier_beside_an_expression_is_recorded():
    a = assess("MIT", ["License :: OSI Approved :: Academic Free License (AFL)"])
    assert a["verdict"] == "CLEARED" and any("not classified by GREG" in u for u in a["uncertainty"])


@pytest.mark.parametrize("field", ["AGPL-3+-with-customer-terms", "Affero-Custom-Terms",
                                   "AGPL-3+ with Additional-Use-Restriction"])
def test_v7_a_name_only_like_a_known_family_is_never_compatible_under_p4c(field):
    copyright_text = f"Format: x\n\nFiles: *\nCopyright: a\nLicense: {field}\n"
    assert L.attach_check(Binary(copyright_text), "P0")[0] is False           # P0 still holds it
    assert L.attach_check(Binary(copyright_text), "P4c")[0] is False          # P4c no longer reads it as AGPL-3.0
    q = L.qualify_use([L.binary_assessment("tool", copyright_text)], USE, {})
    assert q["verdict"] == L.UNCERTAIN and any("not in GREG's tables" in u for u in q["uncertainty"])
    assert L.attach_check(Binary("Format: x\n\nFiles: *\nCopyright: a\nLicense: AGPL-3+\n"), "P4c")[0] is True


def test_v8_the_use_election_does_not_depend_on_operand_order_or_ignore_class():
    one = L.qualify_use([assess("(AGPL-3.0-only AND LicenseRef-A) OR LicenseRef-B")], USE, {})
    two = L.qualify_use([assess("LicenseRef-B OR (AGPL-3.0-only AND LicenseRef-A)")], USE, {})
    assert [t["id"] for t in one["terms"]] == [t["id"] for t in two["terms"]] == ["LicenseRef-B"]
    for expression in ("GPL-2.0-only OR MIT", "MIT OR GPL-2.0-only"):
        q = L.qualify_use([assess(expression)], USE, {})
        assert [t["id"] for t in q["terms"]] == ["MIT"], expression           # equal verdicts: the less strict class


def test_v9_deep_nesting_fails_closed_instead_of_raising():
    deep = "(" * 200 + "SSPL-1.0" + ")" * 200
    assert p0_attaches(deep) is False
    assert assess(classifiers=[MITC], text=deep)["verdict"] == "FOUNDER_REVIEW"
