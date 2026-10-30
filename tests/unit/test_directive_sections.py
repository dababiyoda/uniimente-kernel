"""The 2026-10-28 directive's completion is computed and conjunctive (founder, 2026-10-30: "That is done when we
completely build the prompt").

acceptance/directive-sections.json holds one record per section 1..77 with the source's exact heading and the
section's testable asks. These tests hold the static check to every way the map could claim more than this tree
shows: a missing or duplicated section, a heading or an excerpt that is not the source's, a cited node that does not
resolve or collect, a contract function or mission requirement that does not exist, a tier or coverage claimed above
what the cited evidence can establish, an open ask without a blocker, a founder or external tier blamed on building,
an unknown or cyclic unit, and a DONE section with an open ask. Each is shown on a deliberately broken copy of the
map. The cited tests are not run here; ``python -m acceptance directive --collect`` and ``--outcomes`` do that.

The second round (review findings MWB-1..10, F1..F9) adds: the asks are pinned, so one cannot be deleted or moved out of
the build residual; a DONE section answers every listed line; a helper in a test file is not evidence; a guard that
fell short in a run guards nothing; a Mission L requirement is capped by its trace; a founder or external blocker a
test could reach cites its record; and every gap-map unit is attached to an ask, or closed.
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


def account_every_line(doc):
    """Set every unanswered listed line aside, so a verdict depends on the asks alone."""
    for s, text in ((s, d.source_sections(SOURCE)[s["n"]][1]) for s in doc["sections"]):
        s.setdefault("not_asks", []).extend({"line": line, "reason": "test"} for line in d.accounted_lines(s, text)[1])
    return doc


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


def test_an_ask_cannot_require_less_than_a_test_or_quote_too_little(world):
    doc = copy.deepcopy(world[0])
    section(doc, 13)["asks"][0]["required_tier"] = "IMPLEMENTED"      # would be met with no evidence at all
    assert any("required_tier" in p for p in check(doc, world))
    doc = copy.deepcopy(world[0])
    section(doc, 13)["asks"][0]["excerpt"] = "the"                    # would match almost any section
    assert any("excerpt" in p for p in check(doc, world))


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
    assert rep["build_residual"] == 0 and rep["listed_lines_unaccounted"] > 0
    assert rep["prompt_completely_built"] is False   # listed lines no ask answers yet keep it false
    account_every_line(doc)
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


# -- round 2: the asks are pinned (MWB-1, MWB-7) --------------------------------------------------------------------

def test_a_deleted_or_relabelled_ask_is_refused(world):
    doc = copy.deepcopy(world[0])                     # deleting an open founder ask would turn its section DONE
    section(doc, 16)["asks"] = [a for a in section(doc, 16)["asks"] if a["id"] != "S16.A3"]
    assert "pin: S16.A3 is pinned and missing from the map: an ask is retired, never deleted" in check(doc, world)
    buildable = first(world[0], world, lambda a, raw: not a["met"] and raw["blocker"]["class"] == "BUILDABLE_NOT_BUILT")
    for blocker in ({"class": "EXTERNAL", "reason": "x", "record": "gap:I.G3"},
                    {"class": "PRINCIPLE", "reason": "x", "guarded_by": d.UNGUARDED}):
        doc = copy.deepcopy(world[0])
        ask(doc, buildable)["blocker"] = blocker
        assert (f"pin: {buildable} is pinned BUILDABLE_NOT_BUILT; an open ask's blocker moves only to "
                f"BUILDABLE_NOT_BUILT, not to {blocker['class']}") in check(doc, world)
    founder = first(world[0], world, lambda a, raw: not a["met"] and raw["blocker"]["class"] == "FOUNDER_ONLY"
                    and raw["required_tier"] in d.BEYOND_TESTS)
    doc = copy.deepcopy(world[0])                     # toward the build residual is always allowed
    ask(doc, founder)["blocker"] = {"class": "BUILDABLE_NOT_BUILT", "reason": "x"}
    assert not any(p.startswith(f"pin: {founder}") for p in check(doc, world))
    doc = copy.deepcopy(world[0])
    section(doc, 13)["asks"].append({**copy.deepcopy(section(doc, 13)["asks"][0]), "id": "S13.A99"})
    assert "pin: S13.A99 is not pinned; add it to acceptance/directive-asks.pin.json" in check(doc, world)
    rep = d.directive_report(world[0], world[1], world[2])          # the reviewer's extreme: drop every open ask
    met = {a["id"] for s in rep["sections"] for a in s["asks"] if a["met"]}
    doc = copy.deepcopy(world[0])
    for s in doc["sections"]:
        s["asks"] = [a for a in s["asks"] if a["id"] in met] or s["asks"][:1]
    dropped = [p for p in check(doc, world) if p.endswith("is pinned and missing from the map: an ask is retired, never deleted")]
    assert len(dropped) == sum(len(s["asks"]) for s in world[0]["sections"]) - sum(len(s["asks"]) for s in doc["sections"])


def test_the_pin_ratchets_against_a_base(world):
    base = {"version": "directive-asks-pin/1", "asks": {"S1.A1": "FOUNDER_ONLY", "S1.A2": "BUILDABLE_NOT_BUILT",
                                                       "S1.A3": "EXTERNAL"}}
    head = {"version": "directive-asks-pin/1", "asks": {"S1.A1": "BUILDABLE_NOT_BUILT", "S1.A2": "EXTERNAL",
                                                       "S1.A4": "PRINCIPLE"}}
    assert d.pin_ratchet_problems(base, head) == [
        "pin: S1.A2 was pinned BUILDABLE_NOT_BUILT at the base; it may move only to BUILDABLE_NOT_BUILT, not to EXTERNAL",
        "pin: S1.A3 was pinned at the base and is gone"]
    assert d.pin_ratchet_problems(base, base) == []
    pin = d.load_map(d.PIN)
    bad = {**pin, "asks": {**pin["asks"], "S1.A1": "DONE_ANYWAY"}}
    assert any(p.startswith("pin: directive-asks.pin.schema.json: asks/S1.A1: 'DONE_ANYWAY' is not one of")
               for p in d.directive_problems(world[0], world[1], world[2], pin=bad))
    assert d.pin_at("no-such-ref-for-the-directive-pin") == (None, "pin: cannot read git ref "
                                                                   "no-such-ref-for-the-directive-pin")


def test_an_ask_is_retired_never_deleted(world):
    successor = first(world[0], world, lambda a, raw: a["met"] and raw["required_tier"] == "UNIT_VERIFIED")
    opened = first(world[0], world, lambda a, raw: not a["met"] and raw["required_tier"] == "UNIT_VERIFIED"
                   and raw["blocker"]["class"] == "BUILDABLE_NOT_BUILT")
    doc = copy.deepcopy(world[0])
    ask(doc, opened)["retired"] = {"reason": "the same obligation, asked better", "superseded_by": successor}
    rows = {a["id"]: a for s in d.directive_report(doc, world[1], world[2])["sections"] for a in s["asks"]}
    assert rows[opened]["met"] is True and rows[opened]["retired"] == {"superseded_by": successor}
    assert not any(opened in p for p in check(doc, world) if not p.startswith("section"))
    beyond = first(world[0], world, lambda a, raw: raw["required_tier"] in d.BEYOND_TESTS)
    doc = copy.deepcopy(world[0])                     # a successor that asks less cannot carry it
    ask(doc, beyond)["retired"] = {"reason": "x", "superseded_by": successor}
    assert any(p.startswith(f"section {beyond.split('.')[0][1:]} {beyond}: its successor {successor} requires "
                            f"UNIT_VERIFIED") for p in check(doc, world))
    for gone, message in (({"reason": "x", "superseded_by": "S1.A99"}, "which is not a live ask"),
                          ({"reason": "x"}, "exactly one of superseded_by or record"),
                          ({"reason": "x", "record": "docs/intent/INTENT-0030-effect-not-metaphor.md#no such words"},
                           "quotes words that are not in docs/intent/INTENT-0030-effect-not-metaphor.md")):
        doc = copy.deepcopy(world[0])
        ask(doc, beyond)["retired"] = gone
        assert any(beyond in p and message in p for p in check(doc, world)), gone
    doc = copy.deepcopy(world[0])                     # withdrawn by a founder intent record: kept, not counted
    ask(doc, beyond)["retired"] = {"reason": "x", "record": "docs/intent/INTENT-20261030-BUILD-BEFORE-DEVICE-RUN.json#"
                                   "VEPMC (directive section 57) is not redefined"}
    rep = d.directive_report(doc, world[1], world[2])
    assert [r["id"] for r in rep["retired"]] == [beyond] and rep["summary"]["asks_retired"] == 1
    assert not any(beyond in p for p in check(doc, world) if not p.startswith("section"))


# -- round 2: records hold founder and external blockers, guards are evidence (MWB-7) -------------------------------

def test_a_founder_or_external_blocker_a_test_could_reach_cites_its_record(world):
    reachable = first(world[0], world, lambda a, raw: not a["met"] and raw["blocker"]["class"] == "FOUNDER_ONLY"
                      and raw["required_tier"] in d.TEST_TIERS)
    doc = copy.deepcopy(world[0])
    del ask(doc, reachable)["blocker"]["record"]
    assert any(f"{reachable}: a test can reach" in p and "a FOUNDER_ONLY blocker cites the record" in p
               for p in check(doc, world))
    for record, message in (("gap:I.G3", "is a external gap, which does not hold a FOUNDER_ONLY blocker"),
                            ("gap:A.G1", "is not an open gap that building cannot close"),
                            ("gap:A.G99", "names no missions.json gap"),
                            ("docs/no/such/file.md#words", "names no file"),
                            ("acceptance/missions.json#words nobody ever wrote there", "quotes words that are not in"),
                            ("acceptance/directive-sections.json#S1.A1", "is the map or its pin")):
        doc = copy.deepcopy(world[0])
        ask(doc, reachable)["blocker"]["record"] = record
        assert any(f"{reachable}: record {record!r} {message}" in p for p in check(doc, world)), record
    buildable = first(world[0], world, lambda a, raw: not a["met"] and raw["blocker"]["class"] == "BUILDABLE_NOT_BUILT")
    doc = copy.deepcopy(world[0])
    ask(doc, buildable)["blocker"]["record"] = "gap:I.G1"
    assert any(f"{buildable}: only a FOUNDER_ONLY or EXTERNAL blocker cites a record" in p for p in check(doc, world))


def test_a_principle_guard_is_resolved_and_among_its_evidence(world):
    principle = first(world[0], world, lambda a, raw: not a["met"] and raw["blocker"]["class"] == "PRINCIPLE")
    unrelated = "tests/unit/test_founder_correction_20261030.py::test_the_directive_is_kept_whole_and_its_digest_matches"
    doc = copy.deepcopy(world[0])
    ask(doc, principle)["blocker"]["guarded_by"] = [unrelated]
    assert any(f"{principle}: guard {unrelated} is not among the ask's own evidence" in p for p in check(doc, world))
    doc = copy.deepcopy(world[0])
    ask(doc, principle)["blocker"]["guarded_by"].append("tests/unit/test_founder_correction_20261030.py::test_gone")
    assert any(f"{principle}: guard tests/unit/test_founder_correction_20261030.py::test_gone: test_gone is not "
               f"defined" in p for p in check(doc, world))


def test_a_guard_that_fell_short_in_a_run_leaves_its_principle_unguarded(world):
    doc, manifest, contract = world
    cited = d.cited_nodes(doc)
    passed = {n: {"outcome": "passed", "reason": ""} for n in d._manifest_nodes(manifest) + cited}
    principle = first(doc, world, lambda a, raw: not a["met"] and raw["blocker"]["class"] == "PRINCIPLE")
    guard = ask(doc, principle)["blocker"]["guarded_by"][0]
    before = d.directive_report(doc, manifest, contract, passed)["summary"]
    for outcomes in ({**passed, guard: {"outcome": "failed", "reason": "broken"}},
                     {k: v for k, v in passed.items() if not d.covers(guard, k)}):        # never ran
        rep = d.directive_report(doc, manifest, contract, outcomes)
        row = next(a for s in rep["sections"] for a in s["asks"] if a["id"] == principle)
        assert row["guard_observed"] and d._builds_can_close(row)
        assert rep["summary"]["open_by_blocker"]["PRINCIPLE_UNGUARDED"] > before["open_by_blocker"]["PRINCIPLE_UNGUARDED"]
        assert rep["summary"]["build_residual"] > before["build_residual"]


def test_a_run_reopened_ask_with_no_blocker_counts_against_the_build(world):
    doc, manifest, contract = world
    doc = account_every_line(copy.deepcopy(doc))
    for s in doc["sections"]:
        for a in s["asks"]:
            b = a.get("blocker")
            if b and (b["class"] == "BUILDABLE_NOT_BUILT" or b.get("guarded_by") == d.UNGUARDED):
                a["blocker"] = {"class": "EXTERNAL", "reason": "test"}
    cited = d.cited_nodes(doc)
    passed = {n: {"outcome": "passed", "reason": ""} for n in d._manifest_nodes(manifest) + cited}
    assert d.directive_report(doc, manifest, contract, passed)["summary"]["prompt_completely_built"] is True
    met = first(doc, world, lambda a, raw: a["met"] and d.ask_nodes(raw) and not raw.get("blocker"))
    node = d.ask_nodes(ask(doc, met))[0]
    s = d.directive_report(doc, manifest, contract, {**passed, node: {"outcome": "failed", "reason": "x"}})["summary"]
    assert s["open_by_blocker"]["NONE_NAMED"] >= 1 and s["build_residual"] >= 1
    assert s["prompt_completely_built"] is False


# -- round 2: listed lines, Mission L's trace, helpers, units (MWB-2/F2, MWB-5, MWB-3, MWB-9/F6) -------------------

def test_a_done_section_answers_every_listed_line(world):
    assert section(world[0], 13)["status"] == "DONE"
    doc = copy.deepcopy(world[0])
    del next(a for a in section(doc, 13)["asks"] if a["id"] == "S13.A3")["lines"]
    found = check(doc, world)
    assert any(p.startswith("section 13: DONE is claimed with 11 listed line(s) no ask answers") for p in found)
    rows = d.directive_report(doc, world[1], world[2])["sections"]
    assert next(s for s in rows if s["n"] == 13)["status"] == "PARTIAL"
    assert d.section_status([{"met": True}], ["* a line"]) == "PARTIAL"
    doc = copy.deepcopy(world[0])
    section(doc, 13)["not_asks"] = [{"line": "* what should be ported;", "reason": "x"},
                                    {"line": "* not a line of section 13;", "reason": "x"}]
    found = check(doc, world)
    assert "section 13: '* what should be ported;' is both answered by an ask and set aside in not_asks" in found
    assert any("not_asks names '* not a line of section 13;'" in p for p in found)
    doc = copy.deepcopy(world[0])
    section(doc, 13)["asks"][0]["lines"] = ["* clears the active gate;"]                     # a line of section 15
    assert any("'* clears the active gate;' is not a listed line of section 13" in p for p in check(doc, world))
    assert d.listed_lines("x\n* a;\nDo not b.\nNever c.\n* a;\nDO WORK.\n") == ["* a;", "Do not b.", "Never c."]


def test_a_mission_l_requirement_is_capped_by_its_trace(world):
    doc, manifest, contract = world
    l3 = {"id": "S2.A99", "required_tier": "UNIT_VERIFIED", "coverage": "covered", "evidence": ["mission:L.L3"]}
    rep = d.evidence_report(manifest, contract, None)
    floor = d.lowest([x["status"] for x in rep["missions"]["L"]["trace"]])
    assert d.rank(rep["missions"]["L"]["requirements"]["L3"]["status"]) > d.rank(floor)
    assert d.ask_status(l3, rep, None)["tier"] == floor
    mission_l = next(m for m in manifest["missions"] if m["id"] == "L")
    body = next(x for x in mission_l["trace"] if x["link"] == "Body")["proof"]
    tests = set(next(r for r in mission_l["requirements"] if r["id"] == "L3")["tests"])
    outcomes = {n: {"outcome": "passed", "reason": ""} for n in d._manifest_nodes(manifest)}
    outcomes.update({n: {"outcome": "failed", "reason": "x"} for n in body if n not in tests})
    got = d.ask_status(l3, d.evidence_report(manifest, contract, outcomes), outcomes)
    assert got["tier"] == "IMPLEMENTED" and got["coverage"] == "partial" and got["met"] is False


def test_an_ask_never_covers_more_than_the_contract_function_it_cites(world):
    rep = d.evidence_report(world[1], world[2], None)
    partial = next(f["id"] for f in rep["contract"] if f["coverage"] == "partial")
    got = d.ask_status({"id": "S1.A99", "required_tier": "UNIT_VERIFIED", "coverage": "covered",
                        "evidence": [f"contract:{partial}"]}, rep, None)
    assert got["coverage"] == "partial" and got["met"] is False


def test_a_helper_inside_a_wholesale_cited_file_is_not_evidence(world):
    helper = "tests/unit/test_autonomy.py::_authority"
    doc = copy.deepcopy(world[0])
    target = first(world[0], world, lambda a, raw: not a["met"] and raw["blocker"]["class"] == "BUILDABLE_NOT_BUILT"
                   and raw["required_tier"] == "UNIT_VERIFIED")
    ask(doc, target).update(evidence=[helper], tier="UNIT_VERIFIED", coverage="covered")
    del ask(doc, target)["blocker"]
    assert any(f"{helper}: _authority is not a test pytest collects" in p for p in check(doc, world))
    assert helper in d.cited_nodes(doc) and "tests/unit/test_autonomy.py" in d.cited_nodes(doc)
    assert d.collect_problems([helper]) == [f"{helper}: collects nothing"]
    guard_only = {"sections": [{"asks": [{"evidence": [], "blocker": {"guarded_by": ["tests/unit/test_x.py::test_y"]}}]}]}
    assert d.cited_nodes(guard_only) == ["tests/unit/test_x.py::test_y"]


def test_prerequisites_are_listed_before_the_units_that_need_them(world):
    rows = d.directive_report(*world)["buildable_in_dependency_order"]
    listed = [r["unit"] for r in rows]
    for prerequisite in ("MW-A", "MU-A"):            # no ask of their own; WU-02 needs both
        row = rows[listed.index(prerequisite)]
        assert row["prerequisite_only"] is True and row["asks"] == []
        assert listed.index(prerequisite) < listed.index("WU-02")
    assert listed.index("S38-A") < listed.index("WU-03")


def test_every_unit_is_attached_to_an_open_ask_or_closed(world):
    doc = copy.deepcopy(world[0])
    doc["units"].append({"id": "S1-Z", "title": "x", "source": "x", "depends_on": []})
    assert any(p.startswith("unit S1-Z: no open ask names it") for p in check(doc, world))
    doc["units"][-1]["closed_by"] = "a commit"
    assert not any(p.startswith("unit S1-Z") for p in check(doc, world))
    named = first(world[0], world, lambda a, raw: not a["met"] and raw["blocker"].get("unit"))
    doc = copy.deepcopy(world[0])
    unit = next(u for u in doc["units"] if u["id"] == ask(doc, named)["blocker"]["unit"])
    unit["closed_by"] = "a commit"
    assert f"unit {unit['id']}: closed by a commit, yet an open ask still names it" in check(doc, world)


# -- round 2: the source and the map's own structure (MWB-8, MWB-6/F4) ----------------------------------------------

def test_the_source_is_the_directive_and_a_wrong_one_is_reported_not_raised(world, tmp_path, monkeypatch):
    other = "docs/intent/sources/EGREGORE-2026-09-25-source.md"
    doc = copy.deepcopy(world[0])
    doc["source"]["directive"] = other
    assert check(doc, world) == [f"source: this map reads {d.SOURCE}, not {other}"]
    (tmp_path / d.SOURCE).parent.mkdir(parents=True)
    (tmp_path / d.SOURCE).write_text("no fence here\n", encoding="utf-8")
    assert d.directive_problems(world[0], world[1], world[2], root=tmp_path) == [
        f"source: {d.SOURCE} holds no four-backtick text fence"]
    (tmp_path / d.SOURCE).write_text("````text\nno sections\n````\n", encoding="utf-8")
    found = d.directive_problems(world[0], world[1], world[2], root=tmp_path)
    assert "source: expected sections 1..77 in the directive, found 0" in found
    assert "pin: no acceptance/directive-asks.pin.json: the set of asks is not pinned" in found
    real = d.source_sections
    monkeypatch.setattr(d, "source_sections", lambda path: {n: v for n, v in real(path).items() if n != 40})
    assert "source: expected sections 1..77 in the directive, found 76" in check(world[0], world)


def test_the_map_keeps_its_own_structure(world):
    doc = copy.deepcopy(world[0])
    doc["sections"][3], doc["sections"][4] = doc["sections"][4], doc["sections"][3]
    assert "sections must be in the directive's order" in check(doc, world)
    doc = copy.deepcopy(world[0])
    section(doc, 13)["asks"][0]["id"] = "S14.A99"
    assert any("S14.A99: an ask id names its own section (S13.A<k>)" in p for p in check(doc, world))
    doc = copy.deepcopy(world[0])
    section(doc, 13)["asks"][0]["owner_paths"] = ["greg/no_such_module.py"]
    assert any("owner path greg/no_such_module.py does not exist" in p for p in check(doc, world))
    doc = copy.deepcopy(world[0])
    doc["units"].append(copy.deepcopy(doc["units"][0]))
    assert "units: a unit id is listed twice" in check(doc, world)
    doc = copy.deepcopy(world[0])
    opened = first(world[0], world, lambda a, raw: not raw["evidence"])
    ask(doc, opened)["tests_tier"] = "UNIT_VERIFIED"
    assert any(f"{opened}: tests_tier names the tier of the ask's own test nodes, and it cites none" in p
               for p in check(doc, world))
    done = copy.deepcopy(world[0])                    # every present section DONE, but not all 77 present
    done["sections"] = [s for s in done["sections"] if s["status"] == "DONE"]
    s = d.directive_report(done, world[1], world[2])["summary"]
    assert all(x == 0 for k, x in s["by_status"].items() if k != "DONE") and s["every_section_done"] is False


def test_the_cli_collects_every_cited_node_and_ratchets_the_pin(world, monkeypatch, capsys):
    monkeypatch.setattr(cli, "problems", lambda manifest, contract: [])
    monkeypatch.setattr(d, "load_map", lambda path=d.DIRECTIVE_MAP: world[0] if path == d.DIRECTIVE_MAP
                        else json.loads(Path(path).read_text()))
    seen = []
    monkeypatch.setattr(d, "collect_problems", lambda nodes: seen.append(list(nodes)) or ["x: collects nothing"])
    assert cli.main(["directive", "--collect"]) == 2
    assert seen == [d.cited_nodes(world[0])] and "x: collects nothing" in capsys.readouterr().out
    monkeypatch.setattr(d, "collect_problems", lambda nodes: [])
    assert cli.main(["directive", "--collect"]) == 0
    assert f"all {len(d.cited_nodes(world[0]))} distinct cited nodes collect" in capsys.readouterr().out
    pinned = d.load_map(d.PIN)
    for answer, code, said in (((None, None), 0, "no pin at base: nothing to ratchet against"),
                               ((None, "pin: cannot read git ref base"), 2, "pin: cannot read git ref base"),
                               (({**pinned, "asks": {**pinned["asks"], "S1.A99": "EXTERNAL"}}, None), 2,
                                "pin: S1.A99 was pinned at the base and is gone"),
                               ((pinned, None), 0, "the pinned asks hold against base")):
        monkeypatch.setattr(d, "pin_at", lambda ref, answer=answer: answer)
        assert cli.main(["directive", "--against", "base"]) == code, said
        assert said in capsys.readouterr().out
