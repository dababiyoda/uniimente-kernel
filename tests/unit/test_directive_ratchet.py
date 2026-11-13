"""The directive map ratchets against a base as an allow-list: what remains to build shrinks only through new or
changed executable evidence (review of #249, findings 1-2, and three adversarial reviews of the ratchet).

Each earlier version listed what was forbidden, and each review found an edit nobody had listed that shrank the
residual with no test changed: declaring coverage on an ask or in a mission requirement, lowering a tier, retiring
asks into a met, new, founder-only or about-to-close successor, withdrawing by any intent file, hanging unanswered
lines on met asks, re-guarding a principle with an old test, and editing the directive source itself. Every one of
those attacks is a test below; so is each legitimate change that must still pass.
"""
from __future__ import annotations

import copy
import json
import re
import subprocess

import pytest

from acceptance import directive as d
from acceptance import rank

ATTACKED = ("S1.A2", "S3.A1", "S5.A1")          # the asks the #249 review closed by editing their coverage
PIN_PATH = d.PIN.relative_to(d.ROOT).as_posix()


@pytest.fixture(scope="module")
def world():
    return d.defaults()


def ask(doc, ask_id):
    return next(a for s in doc["sections"] for a in s["asks"] if a["id"] == ask_id)


def met(doc, world, manifest=None):
    rep = d.directive_report(doc, manifest or world[1], world[2])
    return {a["id"] for s in rep["sections"] for a in s["asks"] if a["met"]}


def ids(problems):
    return [m.group(1) for p in problems if (m := re.match(r"ratchet: (S\d+\.A\d+)", p))]


def ratchet(head, world, read_head=None, manifest=None, base=None, pin=None):
    tree = d.read_tree()
    read = read_head or tree
    if pin is not None:
        text, inner = json.dumps(pin), read
        read = lambda p: text if p == PIN_PATH else inner(p)              # noqa: E731
    return d.evidence_ratchet_problems(base or world, (head, manifest or world[1], world[2]), tree, read)


def edited(path, replace):
    """A head reader where one file's text is replaced by ``replace(text)``."""
    tree = d.read_tree()
    return lambda p: replace(tree(p)) if p == path else tree(p)


def add_statement(node):
    """A head reader in which the test function ``node`` names gains a statement."""
    path, name = node.split("::")[0], re.sub(r"\[.*\]$", "", node.split("::")[-1])
    return edited(path, lambda t: re.sub(rf"(def {re.escape(name)}\(.*?\).*?:\n)", r"\1    assert True\n", t,
                                         count=1, flags=re.S))


def change_cited_function(ask_record, world):
    return add_statement(next(n for n in d.evidence_nodes(ask_record, world[1], world[2]) if "::" in n))


def declared_covered(world, aids=ATTACKED):
    head = copy.deepcopy(world[0])
    for aid in aids:
        a = ask(head, aid)
        a["coverage"] = "covered"
        a.pop("blocker", None)
    return head


def open_buildable(world):
    rep = d.directive_report(world[0], world[1], world[2])
    return [a["id"] for s in rep["sections"] for a in s["asks"]
            if not a["met"] and (a["blocker"] or {}).get("class") == "BUILDABLE_NOT_BUILT"]


def test_the_reviewed_asks_are_open_at_the_base_and_the_edit_alone_closes_them(world):
    """The precondition: without the ratchet, a declaration alone closes them."""
    before, after = met(world[0], world), met(declared_covered(world), world)
    assert not before & set(ATTACKED) and set(ATTACKED) <= after


# -- closing ----------------------------------------------------------------------------------------------------

def test_declaring_coverage_without_new_evidence_is_refused(world):
    assert ids(ratchet(declared_covered(world), world)) == list(ATTACKED)


def test_lowering_the_required_tier_without_new_evidence_is_refused(world):
    rep = d.directive_report(world[0], world[1], world[2])
    for row in (a for s in rep["sections"] for a in s["asks"]):
        if row["met"] or "retired" in row or row["tier"] in (d.NO_EVIDENCE, d.BLOCKED) \
                or rank(row["tier"]) >= rank(row["required_tier"]):
            continue
        head = copy.deepcopy(world[0])
        ask(head, row["id"]).update(required_tier=row["tier"], coverage="covered")
        if row["id"] in met(head, world):
            break
    else:
        pytest.fail("no open ask in the map is closed by lowering its required tier")
    assert ids(ratchet(head, world)) == [row["id"]]


def test_declaring_coverage_in_a_mission_requirement_closes_nothing(world):
    """Review 1, finding 1: the same claim one level down closed 15 asks with no test changed."""
    manifest, head = copy.deepcopy(world[1]), copy.deepcopy(world[0])
    reqs = {(m["id"], r["id"]): r for m in manifest["missions"] for r in m["requirements"]}
    before = met(world[0], world)
    for s in head["sections"]:
        for a in s["asks"]:
            cited = [e.partition(":")[2] for e in a.get("evidence", []) if e.startswith("mission:")]
            if a["id"] in before or not cited:
                continue
            for ref in cited:
                reqs[tuple(ref.split(".", 1))]["coverage"] = "covered"
            a["coverage"] = "covered"
            a.pop("blocker", None)
    closed = met(head, world, manifest) - before
    assert len(closed) >= 3
    assert closed <= set(ids(ratchet(head, world, manifest=manifest)))


def test_an_ask_closes_when_the_test_function_it_cites_changed(world):
    head = declared_covered(world, ("S5.A1",))
    assert ratchet(head, world, change_cited_function(ask(world[0], "S5.A1"), world)) == []


def test_a_comment_elsewhere_in_a_cited_file_does_not_close_an_ask(world):
    """Review 3, N-a: a change to a file credits only the nodes whose own source changed."""
    head = declared_covered(world, ("S5.A1",))
    node = next(n for n in d.evidence_nodes(ask(world[0], "S5.A1"), world[1], world[2]) if "::" in n)
    assert ids(ratchet(head, world, edited(node.split("::")[0], lambda t: t + "\n# touched\n"))) == ["S5.A1"]


def test_an_ask_closes_when_it_cites_a_test_that_is_new_in_this_change(world):
    head = declared_covered(world, ("S5.A1",))
    ask(head, "S5.A1")["evidence"].append("tests/unit/test_brand_new_evidence.py::test_it")
    tree = d.read_tree()
    assert ratchet(head, world, lambda p: "def test_it():\n    pass\n" if p.endswith("brand_new_evidence.py")
                   else tree(p)) == []


def test_citing_old_unchanged_evidence_does_not_close_an_ask(world):
    head = declared_covered(world, ("S5.A1",))
    already = sorted(met(world[0], world))[0]
    ask(head, "S5.A1")["evidence"] += ask(world[0], already)["evidence"]
    assert ids(ratchet(head, world)) == ["S5.A1"]


def test_an_ask_that_cites_only_a_mission_requirement_closes_on_that_requirements_tests(world):
    """The requirement's own tests are followed: changing one of them is the ask's evidence."""
    rep = d.directive_report(world[0], world[1], world[2])
    open_ids = {a["id"] for s in rep["sections"] for a in s["asks"] if not a["met"]}
    a = next(a for s in world[0]["sections"] for a in s["asks"] if a["id"] in open_ids and a.get("evidence")
             and all(r.startswith("mission:") for r in a["evidence"]) and "retired" not in a
             and any("::" in n for n in d.evidence_nodes(a, world[1], world[2])))
    head, manifest = copy.deepcopy(world[0]), copy.deepcopy(world[1])
    reqs = {(m["id"], r["id"]): r for m in manifest["missions"] for r in m["requirements"]}
    for ref in (r.partition(":")[2] for r in a["evidence"]):
        reqs[tuple(ref.split(".", 1))]["coverage"] = "covered"
    ask(head, a["id"]).update(coverage="covered", required_tier="IMPLEMENTED")
    ask(head, a["id"]).pop("blocker", None)
    assert a["id"] in met(head, world, manifest)
    assert ids(ratchet(head, world, manifest=manifest)) == [a["id"]]
    assert ratchet(head, world, change_cited_function(a, world), manifest=manifest) == []


def test_an_ask_that_cites_only_a_contract_function_closes_on_its_requirements_tests(world):
    """Review 1, F6 (a false refusal): a contract function's evidence is requirement ids; their tests count."""
    rep = d.directive_report(world[0], world[1], world[2])
    open_ids = {a["id"] for s in rep["sections"] for a in s["asks"] if not a["met"]}
    a = next(a for s in world[0]["sections"] for a in s["asks"] if a["id"] in open_ids and a.get("evidence")
             and all(r.startswith("contract:") for r in a["evidence"]) and "retired" not in a)
    functions = {f["id"]: f for f in world[2]["functions"]}
    head, manifest = copy.deepcopy(world[0]), copy.deepcopy(world[1])
    reqs = {(m["id"], r["id"]): r for m in manifest["missions"] for r in m["requirements"]}
    for ref in (r.partition(":")[2] for r in a["evidence"]):
        for req_ref in functions[ref]["evidence"]:
            reqs[tuple(req_ref.split(".", 1))]["coverage"] = "covered"
    ask(head, a["id"]).update(coverage="covered", required_tier="IMPLEMENTED")
    ask(head, a["id"]).pop("blocker", None)
    assert a["id"] in met(head, world, manifest)
    assert ids(ratchet(head, world, manifest=manifest)) == [a["id"]]
    assert ratchet(head, world, change_cited_function(a, world), manifest=manifest) == []


# -- retiring and withdrawing: the founder's at merge -------------------------------------------------------------

@pytest.mark.parametrize("successor", ["S1.A1", "S3.A1", "S1.A9"])
def test_any_new_retirement_of_an_open_ask_is_the_founders(world, successor):
    """Into a met ask (review 1), an open one (review 3 showed open successors are how the residual was emptied),
    or one created in the same change (review 1)."""
    head = copy.deepcopy(world[0])
    if successor == "S1.A9":
        next(s for s in head["sections"] if s["n"] == 1)["asks"].append(
            {**copy.deepcopy(ask(head, "S1.A2")), "id": "S1.A9"})
    ask(head, "S1.A2")["retired"] = {"superseded_by": successor}
    problems = [p for p in ratchet(head, world) if p.startswith("ratchet: S1.A2")]
    assert len(problems) == 1 and d.FOUNDER_AT_MERGE in problems[0]


def test_withdrawing_an_open_ask_by_a_record_is_refused(world):
    """Review 1, finding 3: any intent file emptied the residual."""
    head = copy.deepcopy(world[0])
    targets = open_buildable(world)[:5]
    for aid in targets:
        ask(head, aid)["retired"] = {"record": "docs/intent/INTENT-20261030-BUILD-BEFORE-DEVICE-RUN.json#Continue"}
    assert ids(ratchet(head, world)) == targets


def test_re_pointing_or_reinstating_a_retirement_is_refused_and_an_unchanged_one_passes(world):
    """Review 1, findings 4 and 5."""
    base = copy.deepcopy(world[0])
    ask(base, "S1.A2")["retired"] = {"superseded_by": "S3.A1"}
    based = (base, world[1], world[2])
    repointed = copy.deepcopy(base)
    ask(repointed, "S1.A2")["retired"] = {"superseded_by": "S1.A1"}
    assert ids(ratchet(repointed, world, base=based)) == ["S1.A2"]
    assert ratchet(copy.deepcopy(base), world, base=based) == []
    withdrawn = copy.deepcopy(world[0])
    ask(withdrawn, "S5.A1")["retired"] = {"record": "docs/intent/INTENT-20261030-BUILD-BEFORE-DEVICE-RUN.json#x"}
    assert ids(ratchet(declared_covered(world, ("S5.A1",)), world, base=(withdrawn, world[1], world[2]))) == ["S5.A1"]


def test_retiring_many_asks_into_one_successor_then_closing_it_closes_none_of_them(world):
    """Review 2, N1: 150 asks retired into one successor and closed by one touched file (met 77 to 228)."""
    head = declared_covered(world, ("S5.A1",))
    targets = [a for a in open_buildable(world) if a != "S5.A1"][:20]
    for aid in targets:
        ask(head, aid)["retired"] = {"superseded_by": "S5.A1"}
    found = ids(ratchet(head, world, change_cited_function(ask(world[0], "S5.A1"), world)))
    assert sorted(found) == sorted(targets)                                   # the successor's own closure stands


def test_retiring_into_a_new_founder_only_ask_is_refused(world):
    """Review 3, C1: a new FOUNDER_ONLY successor took the residual and the lines to 0 with no test edited."""
    head, pin = copy.deepcopy(world[0]), copy.deepcopy(d.load_map(d.PIN))
    targets = open_buildable(world)[:6]
    s1 = next(s for s in head["sections"] if s["n"] == 1)
    s1["asks"].append({**copy.deepcopy(ask(head, "S1.A2")), "id": "S1.A99", "required_tier": "FOUNDER_ACCEPTED",
                       "blocker": {"class": "FOUNDER_ONLY", "reason": "x"}})
    pin["asks"]["S1.A99"] = "FOUNDER_ONLY"
    for aid in targets:
        ask(head, aid)["retired"] = {"superseded_by": "S1.A99"}
    found = ids(ratchet(head, world, pin=pin))
    assert "S1.A99" in found and set(targets) <= set(found)


def test_editing_a_retired_asks_evidence_closes_nothing(world):
    """Review 3, B1: a retired ask's declared evidence fed the check but not its status."""
    head = copy.deepcopy(world[0])
    ask(head, "S1.A2")["retired"] = {"superseded_by": "S1.A1"}
    ask(head, "S1.A2")["evidence"] = ["tests/unit/test_brand_new_evidence.py::test_it"]
    tree = d.read_tree()
    found = ratchet(head, world, lambda p: "def test_it():\n    pass\n" if p.endswith("brand_new_evidence.py")
                    else tree(p))
    assert ids(found) == ["S1.A2"]


# -- new asks ---------------------------------------------------------------------------------------------------

def test_a_new_ask_is_pinned_buildable_and_meets_only_on_changed_evidence(world):
    """Review 3, N-b: an ask new at the head was skipped by the ratchet entirely."""
    head, pin = copy.deepcopy(world[0]), copy.deepcopy(d.load_map(d.PIN))
    s1 = next(s for s in head["sections"] if s["n"] == 1)
    s1["asks"].append({**copy.deepcopy(ask(head, "S1.A1")), "id": "S1.A98"})        # met on old evidence
    pin["asks"]["S1.A98"] = "BUILDABLE_NOT_BUILT"
    assert "S1.A98" in met(head, world)
    assert ids(ratchet(head, world, pin=pin)) == ["S1.A98"]
    assert ratchet(head, world, change_cited_function(ask(world[0], "S1.A1"), world), pin=pin) == []
    s1["asks"][-1].update(coverage="partial", blocker={"class": "BUILDABLE_NOT_BUILT", "reason": "x"})
    assert ratchet(head, world, pin=pin) == []                                       # a new open obligation


def test_a_new_ask_may_not_be_retired_at_birth(world):
    head, pin = copy.deepcopy(world[0]), copy.deepcopy(d.load_map(d.PIN))
    next(s for s in head["sections"] if s["n"] == 1)["asks"].append(
        {**copy.deepcopy(ask(head, "S1.A2")), "id": "S1.A97", "retired": {"superseded_by": "S1.A2"}})
    pin["asks"]["S1.A97"] = "BUILDABLE_NOT_BUILT"
    found = ratchet(head, world, pin=pin)
    assert ids(found) == ["S1.A97"] and "new and retired at once" in found[0]


# -- listed lines -----------------------------------------------------------------------------------------------

def _unanswered(doc):
    texts = d.source_sections(d.ROOT / doc["source"]["directive"])
    return {s["n"]: d.accounted_lines(s, texts[s["n"]][1])[1] for s in doc["sections"]}


def test_answering_listed_lines_with_asks_already_met_is_refused(world):
    """Review 2, N2: hanging unanswered lines on met asks took 655 unaccounted lines to 0."""
    head, before = copy.deepcopy(world[0]), met(world[0], world)
    lines, moved = _unanswered(world[0]), 0
    for s in head["sections"]:
        holder = next((a for a in s["asks"] if a["id"] in before and "retired" not in a), None)
        if holder and lines[s["n"]]:
            holder.setdefault("lines", []).extend(lines[s["n"]][:2])
            moved += len(lines[s["n"]][:2])
    assert moved >= 4
    problems = [p for p in ratchet(head, world) if not p.startswith("ratchet: this change")]
    assert len(problems) == moved and all(p.startswith("ratchet: section ") for p in problems)


def test_a_line_answered_by_an_open_buildable_ask_passes_and_by_an_open_founder_ask_does_not(world):
    """Review 3, C1: an open founder-only ask was accepted as answering any line."""
    rep = d.directive_report(world[0], world[1], world[2])
    rows = {a["id"]: a for s in rep["sections"] for a in s["asks"]}
    lines = _unanswered(world[0])

    def holder(cls):
        for s in world[0]["sections"]:
            for a in s["asks"]:
                if lines[s["n"]] and "retired" not in a and not rows[a["id"]]["met"] \
                        and (rows[a["id"]]["blocker"] or {}).get("class") == cls:
                    return s["n"], a["id"]
        pytest.fail(f"no open {cls} ask in a section with an unanswered line")

    for cls, refused in (("BUILDABLE_NOT_BUILT", 0), ("FOUNDER_ONLY", 1)):
        n, aid = holder(cls)
        head = copy.deepcopy(world[0])
        ask(head, aid).setdefault("lines", []).append(lines[n][0])
        assert len(ratchet(head, world)) == refused, cls


def test_setting_a_listed_line_aside_is_refused(world):
    head = copy.deepcopy(world[0])
    lines = _unanswered(world[0])
    s = next(s for s in head["sections"] if lines[s["n"]])
    s.setdefault("not_asks", []).append({"line": lines[s["n"]][0], "reason": "not an obligation"})
    problems = ratchet(head, world)
    assert len(problems) == 1 and d.FOUNDER_AT_MERGE in problems[0]


# -- the source -------------------------------------------------------------------------------------------------

def test_editing_the_directive_source_or_its_digest_is_refused(world):
    """Review 3, A1: re-bulleting the source and its digest took the listed lines from 655 to 44."""
    found = ratchet(copy.deepcopy(world[0]), world, edited(d.SOURCE, lambda t: t.replace("\n* ", "\n• ", 5)))
    assert len(found) == 1 and found[0].startswith("ratchet: the directive source")
    head = copy.deepcopy(world[0])
    head["source"] = {**head["source"], "sha256": "0" * 64}
    assert ratchet(head, world)[0].startswith("ratchet: the directive source")


# -- guards -----------------------------------------------------------------------------------------------------

def test_guarding_an_unguarded_principle_with_an_unchanged_test_is_refused(world):
    """Review 2, N4."""
    base = copy.deepcopy(world[0])
    principle = next(a for s in base["sections"] for a in s["asks"]
                     if (a.get("blocker") or {}).get("class") == "PRINCIPLE" and a["id"] not in met(base, world)
                     and any("::" in g for g in a["blocker"]["guarded_by"]))
    guard = principle["blocker"]["guarded_by"]
    principle["blocker"]["guarded_by"] = d.UNGUARDED
    head = copy.deepcopy(base)
    ask(head, principle["id"])["blocker"]["guarded_by"] = guard
    based = (base, world[1], world[2])
    assert ids(ratchet(head, world, base=based)) == [principle["id"]]
    assert ratchet(head, world, add_statement(next(g for g in guard if "::" in g)), base=based) == []


# -- plumbing ---------------------------------------------------------------------------------------------------

def test_an_unchanged_map_raises_nothing(world):
    assert ratchet(copy.deepcopy(world[0]), world) == []


def test_a_base_map_this_schema_cannot_read_is_reported_not_raised(world):
    """Review 1, finding 7."""
    base = copy.deepcopy(world[0])
    del ask(base, "S1.A1")["coverage"]
    problems = ratchet(copy.deepcopy(world[0]), world, base=(base, world[1], world[2]))
    assert len(problems) == 1 and "cannot be read by this tree's directive schema (KeyError" in problems[0]


def test_node_text_is_the_named_syntax_tree_and_none_when_it_is_absent():
    text = "import x\n\ndef test_a():\n    assert 1\n\nclass TestB:\n    def test_c(self):\n        pass\n"
    assert d.node_text(text, "f.py::test_a") == d.node_text("def test_a():  # why\n\n    assert 1\n", "f.py::test_a")
    assert d.node_text(text, "f.py::TestB::test_c") != d.node_text(text, "f.py::test_a")
    assert d.node_text(text, "f.py::test_missing") is None and d.node_text(None, "f.py::test_a") is None
    assert d.node_text("def (", "f.py::x") == "def ("


def test_a_comment_or_layout_never_counts_as_evidence_even_for_a_whole_file_node():
    """Review 4, F1: a whole-file node was raw text, so one comment closed 130 asks and answered 655 lines."""
    text = "def test_a():\n    assert 1\n"
    assert d.node_text(text, "f.py") == d.node_text(text + "\n# reviewed\n\n\n", "f.py")
    assert d.node_text(text, "f.py") != d.node_text(text + "def test_b():\n    assert 2\n", "f.py")


def test_parametrize_cases_count_and_the_last_definition_is_the_one_read():
    """Review 4, N2 (a false refusal) and N3."""
    one = "import pytest\n@pytest.mark.parametrize('x', [1])\ndef test_a(x):\n    assert x\n"
    assert d.node_text(one, "f.py::test_a") != d.node_text(one.replace("[1]", "[1, 2, 3]"), "f.py::test_a")
    real = "def test_a():\n    assert 1\n"
    assert d.node_text("def test_a():\n    pass\n\n" + real, "f.py::test_a") == d.node_text(real, "f.py::test_a")


def test_a_comment_in_a_whole_file_the_map_cites_closes_nothing(world):
    """Review 4, F1, end to end: the ask cites a whole file and only a comment in it changed."""
    head = declared_covered(world, ("S5.A1",))
    whole = next(n for s in world[0]["sections"] for a in s["asks"] for n in a.get("evidence", [])
                 if n.startswith("tests/") and "::" not in n)
    ask(head, "S5.A1")["evidence"] = [whole]
    assert ids(ratchet(head, world, edited(whole, lambda t: t + "\n# reviewed\n"))) == ["S5.A1"]
    assert ratchet(head, world, edited(whole, lambda t: t + "\n\ndef test_reviewed():\n    assert 2\n")) == []


def test_one_change_closes_at_most_the_budget_of_asks(world):
    """Review 4, N1: one trivial new test cited by every open ask closed all 130 of them."""
    targets = open_buildable(world)[:d.CLOSE_BUDGET + 1]
    head = declared_covered(world, targets)
    new = "tests/unit/test_brand_new_evidence.py::test_it"
    for aid in targets:
        ask(head, aid)["evidence"] = [new]
        ask(head, aid)["required_tier"] = "UNIT_VERIFIED"
    tree = d.read_tree()
    reader = lambda p: "def test_it():\n    pass\n" if p.endswith("brand_new_evidence.py") else tree(p)  # noqa: E731
    closed = met(head, world) - met(world[0], world)
    assert len(closed) > d.CLOSE_BUDGET
    found = ratchet(head, world, reader)
    assert [p for p in found if p.startswith("ratchet: this change closes")] and not ids(found)
    for aid in targets[d.CLOSE_BUDGET:]:
        ask(head, aid).update(coverage="partial", blocker={"class": "BUILDABLE_NOT_BUILT", "reason": "x"})
    if len(met(head, world) - met(world[0], world)) <= d.CLOSE_BUDGET:
        assert ratchet(head, world, reader) == []


def test_an_ask_that_closes_may_not_take_on_new_lines_and_lines_are_budgeted(world):
    lines = _unanswered(world[0])
    head = declared_covered(world, ("S5.A1",))
    ask(head, "S5.A1").setdefault("lines", []).append(lines[5][0] if lines[5] else lines[1][0])
    found = ratchet(head, world, change_cited_function(ask(world[0], "S5.A1"), world))
    assert any("closes in this change and also takes on" in p for p in found)
    rep = d.directive_report(world[0], world[1], world[2])
    rows = {a["id"]: a for s in rep["sections"] for a in s["asks"]}
    head = copy.deepcopy(world[0])
    moved = 0
    for s in head["sections"]:
        holder = next((a for a in s["asks"] if "retired" not in a and not rows[a["id"]]["met"]
                       and (rows[a["id"]]["blocker"] or {}).get("class") == "BUILDABLE_NOT_BUILT"), None)
        if holder and lines[s["n"]]:
            holder.setdefault("lines", []).extend(lines[s["n"]])
            moved += len(lines[s["n"]])
    assert moved > d.LINE_BUDGET
    found = ratchet(head, world)
    assert found == [f"ratchet: this change newly answers {moved} listed lines; more than {d.LINE_BUDGET} in one "
                     f"change is {d.FOUNDER_AT_MERGE}"]


def test_every_node_an_asks_evidence_reaches_is_a_test_node(world):
    for s in world[0]["sections"]:
        for a in s["asks"]:
            assert all(n.startswith("tests/") and not n.endswith("]") for n in d.evidence_nodes(a, world[1], world[2]))


def test_the_base_map_is_read_from_git_and_a_ref_without_one_reads_none(tmp_path):
    """From a repository of its own, so the test holds in a copy of this tree without .git."""
    repo = tmp_path / "repo"
    paths = [p.relative_to(d.ROOT) for p in (d.DIRECTIVE_MAP, d.MANIFEST, d.CONTRACT)]
    for rel in paths:
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_bytes((d.ROOT / rel).read_bytes())
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false"]
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(git + ["-C", str(repo), "add", "-A"], check=True)
    subprocess.run(git + ["-C", str(repo), "commit", "-qm", "map"], check=True)
    assert d.map_at("no-such-ref-for-the-directive-map", repo) is None
    base = d.map_at("HEAD", repo)
    assert base is not None and len(base[0]["sections"]) == d.SECTIONS
    assert d.read_at("HEAD", repo)("no/such/file.py") is None


def test_the_cli_refuses_what_the_evidence_ratchet_refuses(world, monkeypatch, capsys):
    from acceptance import __main__ as cli
    pin = d.load_map(d.PIN)
    monkeypatch.setattr(d, "pin_at", lambda ref: (pin, None))
    monkeypatch.setattr(d, "map_at", lambda ref: world)
    monkeypatch.setattr(d, "evidence_ratchet_problems", lambda *a, **k: ["ratchet: S5.A1 was open at the base"])
    assert cli.main(["directive", "--against", "base"]) == 2
    assert "ratchet: S5.A1 was open at the base" in capsys.readouterr().out
    monkeypatch.setattr(d, "evidence_ratchet_problems", lambda *a, **k: [])
    assert cli.main(["directive", "--against", "base"]) == 0
    assert "every ask closed since cites new or changed evidence" in capsys.readouterr().out
