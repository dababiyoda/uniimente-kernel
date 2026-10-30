"""The 2026-10-28 directive's completion is computed and conjunctive (founder, 2026-10-30: "That is done when we
completely build the prompt").

acceptance/directive-sections.json holds one record per section 1..77 with the source's exact heading and the
section's testable asks. These tests hold the static check to every way the map could claim more than this tree
shows: a missing or duplicated section, a heading or an excerpt that is not the source's, a cited node that does not
resolve or collect, a contract function or mission requirement that does not exist, a tier or coverage claimed above
what the cited evidence can establish, an open ask without a blocker, a founder or external tier blamed on building,
an unknown or cyclic unit, and a DONE section with an open ask. Each is shown on a deliberately broken copy of the
map. The cited tests are not run here; ``python -m acceptance directive --collect`` and ``--outcomes`` do that.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import acceptance.__main__ as cli
from acceptance import directive as d

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs/intent/sources/OPUS-MAXIMUS-MASTER-BUILD-DIRECTIVE-2026-10-28-source.md"


@pytest.fixture(scope="module")
def world():
    return d.defaults()


def check(doc, world):
    return d.directive_problems(doc, world[1], world[2])


def section(doc, n):
    return next(s for s in doc["sections"] if s["n"] == n)


def ask(doc, ask_id):
    return next(a for s in doc["sections"] for a in s["asks"] if a["id"] == ask_id)


def first(doc, world, predicate):
    """The first ask whose computed status satisfies ``predicate``: picked from the map, so the tests follow it."""
    rep = d.directive_report(doc, world[1], world[2])
    return next(a["id"] for s in rep["sections"] for a in s["asks"] if predicate(a, ask(doc, a["id"])))


def test_the_map_is_sound_and_covers_every_section(world):
    doc = world[0]
    assert check(doc, world) == []
    assert [s["n"] for s in doc["sections"]] == list(range(1, 78))
    source = d.source_sections(SOURCE)
    assert [s["heading"] for s in doc["sections"]] == [source[n][0] for n in range(1, 78)]
    ids = [a["id"] for s in doc["sections"] for a in s["asks"]]
    assert len(ids) == len(set(ids)) and all(s["asks"] for s in doc["sections"])
    rep = d.directive_report(doc, world[1], world[2])
    summary = rep["summary"]
    assert sum(summary["by_status"].values()) == 77
    assert summary["asks"] == len(ids) and summary["asks_met"] < summary["asks"]
    # The truth on this tree: buildable asks are open, so the prompt is not completely built, and not every section
    # is DONE.
    assert summary["build_residual"] > 0 and summary["prompt_completely_built"] is False
    assert summary["every_section_done"] is False


def test_the_source_holds_two_copies_of_the_same_77_headings():
    first_copy, second_copy = d.copies(d.fenced(SOURCE))
    assert [n for n, _, _ in first_copy] == list(range(1, 78))
    assert [(n, h) for n, h, _ in first_copy] == [(n, h) for n, h, _ in second_copy]
    assert d.source_sections(SOURCE)[13][0] == "NEVER SAY ONLY “OUTDATED”"
    # A numbered line inside a section (section 73's report items, section 21's ladder) is not a heading.
    assert "1. SOURCE COVERAGE MANIFEST" in d.source_sections(SOURCE)[73][1]


def test_a_changed_source_is_refused(world):
    doc = copy.deepcopy(world[0])
    doc["source"]["sha256"] = "0" * 64
    assert any("no longer matches the digest" in p for p in check(doc, world))


def test_a_missing_or_duplicated_section_is_refused(world):
    doc = copy.deepcopy(world[0])
    doc["sections"] = [s for s in doc["sections"] if s["n"] != 40]
    assert "section 40: missing" in check(doc, world)
    doc = copy.deepcopy(world[0])
    doc["sections"].insert(41, copy.deepcopy(section(doc, 41)))
    found = check(doc, world)
    assert "section 41: duplicated (2 records)" in found
    assert any("duplicate ask id" in p for p in found)
    doc = copy.deepcopy(world[0])
    extra = copy.deepcopy(section(doc, 77))
    extra["n"] = 78
    doc["sections"].append(extra)
    assert "section 78: the directive has no such section" in check(doc, world)


def test_a_heading_that_does_not_match_the_source_is_refused(world):
    doc = copy.deepcopy(world[0])
    section(doc, 13)["heading"] = "NEVER SAY ONLY OUTDATED"
    assert any(p.startswith("section 13: heading") and "does not match the source" in p for p in check(doc, world))


def test_an_excerpt_that_is_not_verbatim_in_its_section_is_refused(world):
    doc = copy.deepcopy(world[0])
    target = section(doc, 13)["asks"][0]
    target["excerpt"] = "A correction should normally produce rerouting, not wholesale invalidation."   # section 12
    assert any("excerpt is not verbatim in section 13" in p for p in check(doc, world))
    target["excerpt"] = "Outdated in which respect?"                                                     # a paraphrase
    assert any("excerpt is not verbatim in section 13" in p for p in check(doc, world))


def test_a_cited_node_that_does_not_resolve_or_collect_is_refused(world):
    doc = copy.deepcopy(world[0])
    section(doc, 13)["asks"][0]["evidence"].append("tests/unit/test_developmental_inheritance.py::test_no_such_test")
    assert any("test_no_such_test is not defined" in p for p in check(doc, world))
    doc = copy.deepcopy(world[0])
    section(doc, 13)["asks"][0]["evidence"].append("tests/unit/no_such_file.py")
    assert any("no_such_file.py: no such test file" in p for p in check(doc, world))
    real = "tests/unit/test_founder_correction_20261030.py::test_the_directive_is_kept_whole_and_its_digest_matches"
    found = d.collect_problems([real, "tests/unit/test_founder_correction_20261030.py::test_not_there",
                                "tests/unit/no_such_file.py"])
    assert found == ["tests/unit/test_founder_correction_20261030.py::test_not_there: collects nothing",
                     "tests/unit/no_such_file.py: collects nothing"]


def test_an_unknown_contract_function_or_mission_requirement_is_refused(world):
    doc = copy.deepcopy(world[0])
    section(doc, 13)["asks"][0]["evidence"] += ["contract:BODY-NOWHERE", "mission:A.R99"]
    found = check(doc, world)
    assert any("contract:BODY-NOWHERE names no completion-contract function" in p for p in found)
    assert any("mission:A.R99 names no mission requirement" in p for p in found)


def test_a_tier_above_what_the_evidence_can_establish_is_refused(world):
    unit_only = first(world[0], world, lambda a, raw: a["met"] and a["tier"] == "UNIT_VERIFIED"
                      and raw.get("tests_tier") is None and all(e.startswith("tests/") for e in raw["evidence"]))
    for claimed in ("SANDBOX_VERIFIED", "BODY_VERIFIED", "FOUNDER_ACCEPTED", "COMMERCIAL_OUTCOME_VERIFIED"):
        doc = copy.deepcopy(world[0])
        ask(doc, unit_only)["tier"] = claimed
        assert any(f"{unit_only}: tier {claimed} is claimed above what its evidence can establish (UNIT_VERIFIED)" in p
                   for p in check(doc, world)), claimed
    doc = copy.deepcopy(world[0])                     # its own unit nodes cannot be declared BODY_VERIFIED
    ask(doc, unit_only)["tests_tier"] = "BODY_VERIFIED"
    assert any(f"{unit_only}: tests_tier BODY_VERIFIED needs a cited node that drives a real Body process" in p
               for p in check(doc, world))
    body = first(world[0], world, lambda a, raw: a["tier"] == "BODY_VERIFIED")
    doc = copy.deepcopy(world[0])                     # a stale, lower claim is also refused: the tier is computed
    ask(doc, body)["tier"] = "UNIT_VERIFIED"
    assert any(f"{body}: tier UNIT_VERIFIED is not what its evidence computes (BODY_VERIFIED)" in p
               for p in check(doc, world))


def test_coverage_above_what_an_ask_cites_is_refused(world):
    rep = d.evidence_report(world[1], world[2], None)
    capped = next(a["id"] for s in world[0]["sections"] for a in s["asks"]          # cites a partial requirement
                  if d.ask_status({**a, "coverage": "covered"}, rep, None)["coverage"] == "partial")
    doc = copy.deepcopy(world[0])
    ask(doc, capped)["coverage"] = "covered"
    assert any(f"{capped}: coverage 'covered' is claimed above what it cites ('partial')" in p
               for p in check(doc, world))


def test_done_is_refused_while_an_ask_is_open(world):
    partial = next(s for s in world[0]["sections"] if s["status"] == "PARTIAL")
    doc = copy.deepcopy(world[0])
    section(doc, partial["n"])["status"] = "DONE"
    found = check(doc, world)
    assert any(p.startswith(f"section {partial['n']}: DONE is claimed with an open ask (") for p in found)
    opened = next(s for s in world[0]["sections"] if s["status"] == "OPEN")
    doc = copy.deepcopy(world[0])
    section(doc, opened["n"])["status"] = "PARTIAL"
    assert f"section {opened['n']}: status PARTIAL is not what its asks compute (OPEN)" in check(doc, world)


def test_a_founder_or_external_tier_needs_a_founder_or_external_blocker(world):
    beyond = first(world[0], world, lambda a, raw: raw["required_tier"] in d.BEYOND_TESTS)
    doc = copy.deepcopy(world[0])
    ask(doc, beyond)["blocker"] = {"class": "BUILDABLE_NOT_BUILT", "reason": "write a test"}
    assert any(f"{beyond}: no build or test reaches" in p for p in check(doc, world))
    # However strong the tests, an ask that requires the founder or the outside world is never met by them.
    rep = d.evidence_report(world[1], world[2], None)
    strongest = {"id": "S1.A9", "required_tier": "FOUNDER_ACCEPTED", "coverage": "covered",
                 "evidence": ["mission:A.R5", "mission:A.R8"]}
    got = d.ask_status(strongest, rep, None)
    assert got["tier"] == "BODY_VERIFIED" and got["coverage"] == "covered" and got["met"] is False


def test_an_open_ask_names_its_blocker_and_a_met_ask_names_none(world):
    met = first(world[0], world, lambda a, raw: a["met"])
    opened = first(world[0], world, lambda a, raw: not a["met"] and raw["blocker"]["class"] == "BUILDABLE_NOT_BUILT")
    doc = copy.deepcopy(world[0])
    ask(doc, met)["blocker"] = {"class": "EXTERNAL", "reason": "x"}
    assert any(f"{met}: a met ask names a blocker (EXTERNAL)" in p for p in check(doc, world))
    doc = copy.deepcopy(world[0])
    del ask(doc, opened)["blocker"]
    assert any(f"{opened}: an open ask" in p and "names no blocker class" in p for p in check(doc, world))
    doc = copy.deepcopy(world[0])
    ask(doc, opened)["blocker"] = {"class": "FOUNDER_ONLY", "reason": "x", "unit": "WU-01"}
    assert any(f"{opened}: only a BUILDABLE_NOT_BUILT ask names a gap-map unit" in p for p in check(doc, world))
    doc = copy.deepcopy(world[0])
    ask(doc, opened)["blocker"] = {"class": "PRINCIPLE", "reason": "x"}
    assert any(f"{opened}: a PRINCIPLE names the tests that guard it, or UNGUARDED" in p for p in check(doc, world))
    doc = copy.deepcopy(world[0])
    ask(doc, opened)["blocker"] = {"class": "EXTERNAL", "reason": "x", "guarded_by": "UNGUARDED"}
    assert any(f"{opened}: only a PRINCIPLE names guards" in p for p in check(doc, world))


def test_units_are_known_and_acyclic(world):
    opened = first(world[0], world, lambda a, raw: not a["met"] and raw["blocker"].get("unit"))
    doc = copy.deepcopy(world[0])
    ask(doc, opened)["blocker"]["unit"] = "WU-99"
    assert any(f"{opened}: unit WU-99 is not in the units table" in p for p in check(doc, world))
    doc = copy.deepcopy(world[0])
    units = {u["id"]: u for u in doc["units"]}
    units["WU-01"]["depends_on"] = ["WU-02"]          # WU-02 already depends on WU-01
    assert "units: the dependency graph has a cycle" in check(doc, world)
    units["WU-01"]["depends_on"] = ["WU-77"]
    assert "unit WU-01: depends on unknown unit WU-77" in check(doc, world)


def test_completion_is_conjunctive_and_only_building_can_close_the_build_verdict(world):
    rows = [{"met": True}, {"met": True}]
    assert d.section_status(rows) == "DONE"
    assert d.section_status(rows + [{"met": False}]) == "PARTIAL"
    assert d.section_status([{"met": False}]) == "OPEN"
    doc = copy.deepcopy(world[0])
    for s in doc["sections"]:                        # pretend everything buildable were blocked elsewhere instead
        for a in s["asks"]:
            b = a.get("blocker")
            if b and (b["class"] == "BUILDABLE_NOT_BUILT" or b.get("guarded_by") == d.UNGUARDED):
                a["blocker"] = {"class": "EXTERNAL", "reason": "test"}
    rep = d.directive_report(doc, world[1], world[2])["summary"]
    assert rep["build_residual"] == 0 and rep["prompt_completely_built"] is True
    assert rep["every_section_done"] is False         # founder and external asks still keep sections open
    doc["sections"] = doc["sections"][:-1]
    assert d.directive_report(doc, world[1], world[2])["summary"]["prompt_completely_built"] is False


def test_buildable_asks_are_listed_in_dependency_order(world):
    doc = world[0]
    rep = d.directive_report(doc, world[1], world[2])
    listed = [row["unit"] for row in rep["buildable_in_dependency_order"]]
    assert listed and listed[-1] is None              # asks with no gap-map unit come last
    deps = {u["id"]: u["depends_on"] for u in doc["units"]}
    for unit in listed:
        for dep in deps.get(unit, []):
            if dep in listed:
                assert listed.index(dep) < listed.index(unit), (dep, unit)
    assert d.unit_order([{"id": "B", "depends_on": ["A"]}, {"id": "C", "depends_on": []},
                         {"id": "A", "depends_on": ["C"]}]) == ["C", "A", "B"]


def test_a_run_recomputes_tiers_and_a_failed_node_reopens_its_section(world):
    doc, manifest, contract = world
    cited = [e for s in doc["sections"] for a in s["asks"] for e in a["evidence"] if e.startswith("tests/")]
    passed = {n: {"outcome": "passed", "reason": ""} for n in d._manifest_nodes(manifest) + cited}
    static = d.directive_report(doc, manifest, contract)
    ran = d.directive_report(doc, manifest, contract, passed)
    assert ran["ran"] and [s["status"] for s in ran["sections"]] == [s["status"] for s in static["sections"]]
    done = next(s for s in static["sections"] if s["status"] == "DONE")
    target = next(a for a in done["asks"] if any(e.startswith("tests/") for e in ask(doc, a["id"])["evidence"]))
    node = next(e for e in ask(doc, target["id"])["evidence"] if e.startswith("tests/"))
    failed = {**passed, node: {"outcome": "failed", "reason": "assert"}}
    rerun = d.directive_report(doc, manifest, contract, failed)
    row = next(a for s in rerun["sections"] for a in s["asks"] if a["id"] == target["id"])
    assert row["met"] is False and row["tier"] == d.SHORT_FLOOR and row["observed"]
    assert next(s for s in rerun["sections"] if s["n"] == done["n"])["status"] != "DONE"
    skipped = {**passed, node: {"outcome": "skipped", "reason": "no toolchain"}}   # a skip is not a pass
    row = next(a for s in d.directive_report(doc, manifest, contract, skipped)["sections"]
               for a in s["asks"] if a["id"] == target["id"])
    assert row["met"] is False


def test_the_cli_prints_counts_and_refuses_an_unsound_map(world, monkeypatch, capsys):
    proc = subprocess.run([sys.executable, "-m", "acceptance", "directive"], cwd=ROOT, capture_output=True, text=True,
                          timeout=300, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "directive: 77 sections (DONE " in proc.stdout and "prompt completely built: NO" in proc.stdout
    assert "BUILDABLE_NOT_BUILT asks in dependency order:" in proc.stdout
    broken = copy.deepcopy(world[0])
    broken["sections"] = broken["sections"][1:]
    monkeypatch.setattr(cli, "problems", lambda manifest, contract: [])     # the missions are checked elsewhere
    monkeypatch.setattr(d, "load_map", lambda path=None: broken)
    assert cli.main(["check"]) == 2
    out = capsys.readouterr().out
    assert "directive map is unsound:" in out and "section 1: missing" in out
    monkeypatch.setattr(d, "load_map", lambda path=None: world[0])
    assert cli.main(["directive", "--out", os.devnull]) == 0
    assert json.loads(json.dumps(d.directive_report(*world)))["summary"]["sections"] == 77
