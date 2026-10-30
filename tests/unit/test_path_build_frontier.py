"""The build frontier beside the acceptance frontier (founder correction of 2026-10-30).

"Continue building and doing the prompt verbatim. No real Chromebook run is needed. That is done when we
completely build the prompt" (INTENT-20261030-BUILD-BEFORE-DEVICE-RUN). The device run moved to the end of the
build; it was not redefined. So the build is read on its own axis, from the predicates' ``structurally_met``,
and a test key, a fixture or a rehearsal moves only that axis: ``achieved``, the one operationally primary node
and VEPMC still move only at the founder tier.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
import re

import pytest

from greg import cli, metrics
from greg import path as devpath
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace

ROOT = Path(__file__).resolve().parents[2]
PLACEMENTS = ROOT / "docs/collaboration/DEVELOPMENTAL-INHERITANCE-2026-09-30.json"
PLACEMENT = "n1.vepmc_is_final_acceptance_not_build_gate"
CORRECTION = "INTENT-20261030-BUILD-BEFORE-DEVICE-RUN"
PREDICATE_NODES = {"N1", "N2", "N3", "N4", "N6", "N7"}


def greg(*argv) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cli.main([str(a) for a in argv])
        except SystemExit as exc:                      # argparse refusals exit; the CLI returns otherwise
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def note(home, mid: str) -> dict:
    target = workspace(home, mid) / "n.txt"
    return mission(mid, checks=[note_check("n", target, "x")], strategies=[], capabilities=["fs.read"],
                   ceiling="read_only")


def rows(status: dict) -> dict:
    return {r["id"]: r for r in status["nodes"]}


def one_primary(status: dict, where: dict) -> str:
    """Exactly one node is operationally primary, and it is position()'s active node."""
    primary = [r["id"] for r in status["nodes"] if r["operationally_primary"]]
    assert primary == [where["active"]["id"]] == [status["acceptance_frontier"]["id"]], primary
    assert status["acceptance_frontier"]["operationally_primary"] is True
    assert status["achieved"] == where["achieved"]
    assert status["built"][:len(status["achieved"])] == status["achieved"]   # acceptance never runs ahead of the build
    return primary[0]


def test_a_fresh_body_has_both_frontiers_at_n1_and_the_cli_prints_them(tmp_path):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        status, where = devpath.build_status(body.journal), devpath.position(body.journal)
    assert status["build_frontier"]["id"] == status["acceptance_frontier"]["id"] == "N1"
    assert one_primary(status, where) == "N1" and status["achieved"] == status["built"] == ["N0"]
    assert status["acceptance_frontier"]["status"] == devpath.ACCEPTANCE_PENDING
    by_id = rows(status)
    assert by_id["N0"]["build"] == devpath.STRUCTURALLY_BUILT and by_id["N1"]["build"] == devpath.BUILD_OPEN
    assert {i for i, r in by_id.items() if r["build"] == devpath.NO_PREDICATE} == {"N5", "N8", "N9", "N10"}
    assert status["structural_depth"] == 0 and status["built_ahead"] == []
    assert CORRECTION in status["sequencing"] and CORRECTION in devpath.load()["intent"]

    code, out, _ = greg("--home", home, "path", "--build")
    printed = json.loads(out)
    assert code == 0 and printed["build_frontier"]["id"] == printed["acceptance_frontier"]["id"] == "N1"
    assert printed["acceptance_frontier"]["status"] == "founder acceptance pending (final step)"
    assert [r["build"] for r in printed["nodes"]] == [r["build"] for r in status["nodes"]]
    code, out, _ = greg("--home", home, "path")                       # the plain view is unchanged
    assert code == 0 and "build_frontier" not in json.loads(out) and json.loads(out)["active"]["id"] == "N1"
    code, _, err = greg("--home", home, "path", "--build", "--node", "N3")
    assert code == 2 and "not allowed with" in err


def test_without_a_body_ledger_nothing_is_built_and_the_frontiers_say_why():
    status = devpath.build_status(None)
    n1 = rows(status)["N1"]
    assert n1["build"] == devpath.BUILD_OPEN and n1["why"] == "no body ledger here: measure on the body"
    assert status["build_frontier"]["id"] == status["acceptance_frontier"]["id"] == "N1"


def test_test_key_closures_move_only_the_build_frontier(tmp_path, monkeypatch):
    """The setup of test_structural_closures_cannot_advance_the_external_primary_gate, with real missions signed
    by a test key: N1 and N2 are structurally met, so the build reaches N3, and the founder's path does not move."""
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        for mid in ("m:brief", "m:genesis"):
            drop(home, signed(key, body_id, "MISSION", note(home, mid), now=clock.now))
        body.tick()
        journal = body.journal
        real_vepmc = metrics.vepmc
        counted = {"VEPMC": 1, "external_confirmation_required": "x",
                   "missions": [{"mission_id": "m:brief", "counts": True, "missing": []}]}
        monkeypatch.setattr(metrics, "vepmc", lambda j: counted)
        status = devpath.build_status(journal)
        assert status["build_frontier"]["id"] == "N2" and one_primary(status, devpath.position(journal)) == "N1"

        counted["missions"].append({"mission_id": "m:genesis", "counts": True, "missing": []})
        journal.record("deficit.opened", {"deficit_id": "d3", "mission_id": "m:genesis", "function": "h"}, key="d3")
        journal.record("deficit.resolved", {"deficit_id": "d3", "capability_id": "built:abc", "mission_id": "m:genesis"},
                       key=["d3", "resolved"])
        journal.record("mission.achieved", {"mission_id": "m:genesis"}, key=["m:genesis", "achieved"])
        status, where = devpath.build_status(journal), devpath.position(journal)
        tiers, real = metrics.founder_tier(journal), real_vepmc(journal)
    assert status["build_frontier"]["id"] == "N3" and status["built"] == ["N0", "N1", "N2"]
    assert one_primary(status, where) == "N1" and where["active"]["id"] == "N1"
    assert status["achieved"] == where["achieved"] == ["N0"]                       # achieved is unchanged
    by_id = rows(status)
    for node in ("N1", "N2"):
        assert by_id[node]["build"] == devpath.STRUCTURALLY_BUILT and by_id[node]["counted"]
        assert by_id[node]["evidence_level"] == metrics.STRUCTURAL_CANDIDATE
    assert where["active"]["measurement"]["not_founder_tier"] == {m: metrics.NOT_FOUNDER_TIER
                                                                   for m in ("m:brief", "m:genesis")}
    assert {tiers[m]["tier"] for m in ("m:brief", "m:genesis")} == {metrics.STRUCTURAL_CANDIDATE}
    assert real["founder_tier_count"] == 0 and real["VEPMC"] == 0                   # the device run is untouched
    assert status["structural_depth"] == 2                                        # N1 and N2, both guarded


def _structural_only(monkeypatch, names):
    """Every named predicate structurally met with a test key: real structure, never the founder tier."""
    for name in names:
        monkeypatch.setitem(devpath.PREDICATES, name, lambda journal: devpath._tiered(
            {"value": 0, "structural_value": 1}, structural=True, passed=[],
            refused={"m:test-key": metrics.NOT_FOUNDER_TIER}))


def test_a_node_without_a_predicate_stops_the_build(monkeypatch):
    _structural_only(monkeypatch, list(devpath.PREDICATES))
    journal = object()                                   # the predicates are replaced; no ledger is read
    status = devpath.build_status(journal)
    by_id = rows(status)
    assert status["build_frontier"]["id"] == "N5" and by_id["N5"]["build"] == devpath.NO_PREDICATE
    assert by_id["N5"]["evidence_level"] == "NONE" and "met" not in status["build_frontier"]["measurement"]
    assert status["built"] == ["N0", "N1", "N2", "N3", "N4"]
    for node in ("N6", "N7"):                           # measured past the frontier: reported, never counted
        assert not by_id[node]["counted"] and node not in status["built"]
    assert [r["id"] for r in status["built_ahead"]] == ["N6", "N7"]
    assert status["structural_depth"] == 4
    # The founder's path: still N1, nothing achieved, nothing met ahead.
    assert status["achieved"] == ["N0"] and status["acceptance_frontier"]["id"] == "N1"
    assert sum(r["operationally_primary"] for r in status["nodes"]) == 1 and by_id["N1"]["operationally_primary"]


def test_a_founder_tier_closure_moves_the_acceptance_frontier_and_never_past_the_build(monkeypatch):
    _structural_only(monkeypatch, list(devpath.PREDICATES))
    monkeypatch.setitem(devpath.PREDICATES, "vepmc_at_least_one", lambda journal: devpath._tiered(
        {"value": 1, "structural_value": 1}, structural=True, passed=["m:founder"], refused={}))
    status = devpath.build_status(object())
    assert status["achieved"] == ["N0", "N1"] and status["acceptance_frontier"]["id"] == "N2"
    assert status["build_frontier"]["id"] == "N5" and rows(status)["N1"]["evidence_level"] == metrics.FOUNDER_TIER
    assert [r["id"] for r in status["nodes"] if r["operationally_primary"]] == ["N2"]


def test_the_build_depth_counts_only_mutation_guarded_nodes(monkeypatch):
    _structural_only(monkeypatch, list(devpath.PREDICATES))
    monkeypatch.setattr(devpath, "mutation_guarded", lambda gate=None: {"N1", "N2", "N4"})
    status = devpath.build_status(object())
    assert status["built"][-1] == "N4" and status["structural_depth"] == 2          # N3 unguarded stops the count
    assert [r["mutation_guarded"] for r in status["nodes"][:5]] == [False, True, True, False, True]


def test_n1_counts_only_a_closure_that_meets_all_nine_conditions(tmp_path, monkeypatch):
    home, *_ = make_body(tmp_path)
    monkeypatch.setattr(metrics, "vepmc", lambda j: {"VEPMC": 0, "external_confirmation_required": "x", "missions": [
        {"mission_id": "m:half", "counts": False, "missing": ["interruption_survived", "founder_accepted"]}]})
    with Body(home) as body:
        n1 = devpath.vepmc_at_least_one(body.journal)
        status = devpath.build_status(body.journal)
    assert n1["structurally_met"] is False and n1["closest_closure"]["mission_id"] == "m:half"
    assert rows(status)["N1"]["build"] == devpath.BUILD_OPEN and status["build_frontier"]["id"] == "N1"


def test_n7_needs_a_transplant_that_was_faster_or_cheaper(monkeypatch):
    from greg import venture_books
    slower = {"procedure_id": "sop-x", "from_venture": "leases", "to_venture": "audits", "faster_or_cheaper": False,
              "why_not": ["no measure fell"]}
    monkeypatch.setattr(venture_books, "transfers", lambda journal: [slower])
    monkeypatch.setattr(venture_books, "books", lambda journal: [
        {"venture": "audits", "currency": "USD", "surplus_for_reinvestment": "400.00", "cases": ["c1"]}])
    result = devpath.venture_compounding(None)
    assert result["structurally_met"] is False and result["missing"][0].startswith("no transplant was faster")


def test_mutation_guarded_reads_the_gate_and_covers_every_node_predicate(tmp_path):
    assert devpath.mutation_guarded() == PREDICATE_NODES
    assert {n["id"] for n in devpath.load()["nodes"] if n.get("predicate")} == PREDICATE_NODES
    assert devpath.mutation_guarded(tmp_path / "absent.py") == set()               # no gate in this install
    weird = tmp_path / "gate.py"
    weird.write_text("MUTANTS = [(name, 'N1') for name in 'ab']\n")             # not plain literals: never read
    assert devpath.mutation_guarded(weird) == set()
    weird.write_text("MUTANTS = [('a', 'N9', 'f', 'old', 'new', 't'), ('b', None, 'f', 'o', 'n', 't')]\n")
    assert devpath.mutation_guarded(weird) == {"N9"}


def _missing_rehearsals(data: dict) -> list:
    missing = []
    for node in data["nodes"]:
        for ref in node.get("rehearsal", []):
            file, name = ref.split("::")
            source = ROOT / file
            if not source.exists() or not re.search(rf"^def {re.escape(name)}\(", source.read_text(), re.M):
                missing.append(ref)
    return missing


def test_every_rehearsal_reference_names_a_test_that_exists():
    """Checked here, not in validate(): `greg path` loads the path on installs that ship without tests/."""
    data = devpath.load()
    assert {n["id"] for n in data["nodes"] if n.get("rehearsal")} == PREDICATE_NODES
    assert _missing_rehearsals(data) == []
    bad = copy.deepcopy(data)
    bad["nodes"][1]["rehearsal"] = ["tests/unit/test_no_such_file.py::test_nothing"]
    devpath.validate(bad)                                                          # the load does not look
    assert _missing_rehearsals(bad) == ["tests/unit/test_no_such_file.py::test_nothing"]
    for shape in ("tests/unit/x.py::t", [], ["tests/unit/x.py"]):
        bad["nodes"][1]["rehearsal"] = shape
        with pytest.raises(devpath.PathError, match="rehearsal"):
            devpath.validate(bad)


def test_the_correction_is_placed_on_n1_and_cannot_change_the_destination():
    record = json.loads(PLACEMENTS.read_text())
    devpath.validate_placements(record, devpath.load())
    [placement] = [p for p in record["placements"] if p["id"] == PLACEMENT]
    assert placement["node"] == "N1" and placement["intended_effect_status"] == "active"
    assert placement["classification"] == "SUPERSEDED_IMPLEMENTATION_ASSUMPTION"
    assert set(placement["changed_axes"]) <= {"sequence", "timing", "immediate_priority"}
    assert placement["lineage"][0].startswith(CORRECTION)
    for change, message in ((lambda p: p["changed_axes"].append("final_intended_effect"), "changes the destination"),
                            (lambda p: p.update(classification="GENUINELY_OBSOLETE"), "genuine obsolescence"),
                            (lambda p: p.update(intended_effect_status="superseded"), "explicit founder decision")):
        variant = copy.deepcopy(record)
        change(next(p for p in variant["placements"] if p["id"] == PLACEMENT))
        with pytest.raises(devpath.PathError, match=message):
            devpath.validate_placements(variant)
