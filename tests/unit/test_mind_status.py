"""The reality ledger (scripts/mind_status.py): one label per mechanism, from frozen evidence only (section 31 item 17).

Checked against independent sources of truth rather than the generator's own code: the Competency Compiler's
actual routing rows for the same evidence (a genome is supported exactly when the compiler routes it on fresh
positive evidence), greg/path.json's frontier records, the live catalog, and fixture indexes that move one fact
at a time (a version bump, an external verification, a significant loss).
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from greg import path as devpath
from greg.cognition import compiler
from greg.cognition.catalog import CORTEX_ENTRIES, FAMILIES
from greg.cognition.composition import RECIPES
from greg.cognition.genomes import library

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import mind_status as M  # noqa: E402

SUPPORTED = ("HELDOUT_SUPPORTED", "SIMULATED", "EXTERNALLY_VERIFIED")


def _rows(status: dict) -> dict:
    return {r["id"]: r for r in status["mechanisms"]}


def _fixture(tmp_path, change) -> Path:
    index = json.loads(M.INDEX.read_text())
    change(index)
    out = tmp_path / "index.json"
    out.write_text(json.dumps(index))
    return out


def test_every_mechanism_has_exactly_one_known_label_and_none_is_left_out():
    status = M.status()
    rows = status["mechanisms"]
    assert len({r["id"] for r in rows}) == len(rows)
    assert all(r["label"] in M.LABELS and r["basis"] for r in rows)
    assert sum(status["counts"].values()) == len(rows) and set(status["counts"]) == set(M.LABELS)
    ids = _rows(status)
    assert {f"cognition.{f}" for f in library.executables()} <= {i for i, r in ids.items() if r["kind"] == "genome"}
    assert {f"cognition.{f}" for f in FAMILIES} <= set(ids)                   # genome or catalog family, never absent
    assert set(CORTEX_ENTRIES) <= set(ids) and {f"recipe.{r}" for r in RECIPES} <= set(ids)
    assert {f"frontier.{b['id']}" for b in devpath.load()["frontier_backcasts"]} <= set(ids)


def test_genome_labels_agree_with_what_the_compiler_routes_on():
    """Supported exactly when the compiler routes the genome on fresh positive frozen evidence."""
    rows = _rows(M.status())
    evidence = compiler.evidence_index()
    for family, item in library.executables().items():
        data = {k: 0 for k in item.genome.required_inputs}
        routed = [c for c in compiler.candidates(data, compiler.CompetencyGeometry(), evidence)
                  if c["method"] == f"cognition.{family}"]
        assert routed, family
        positive = routed[0]["status"] in M.POSITIVE and not routed[0].get("stale_evidence")
        assert (rows[f"cognition.{family}"]["label"] in SUPPORTED) == positive, (family, routed[0])


def test_nothing_is_externally_verified_today_and_simulated_worlds_are_never_called_heldout_supported():
    status = M.status()
    assert status["counts"]["EXTERNALLY_VERIFIED"] == 0
    for row in status["mechanisms"]:
        if row["kind"] != "genome":
            continue
        g = library.genome(row["id"].removeprefix("cognition."))
        simulated = g.epistemic_class == "physical" or g.evidence_type in ("simulation", "control_trace",
                                                                          "developmental_trace")
        if row["label"] in ("SIMULATED", "HELDOUT_SUPPORTED"):
            assert (row["label"] == "SIMULATED") == simulated, row["id"]
    assert _rows(status)["cognition.develop_repair"]["label"] != "HELDOUT_SUPPORTED"   # a simulated lattice only


def test_a_version_bump_makes_positive_evidence_stale_while_negative_evidence_persists(tmp_path):
    def bump(index):
        for family in ("basal_kalman", "flow_maxflow", "collective_quorum", "flow_reinforce_greedy"):
            index["genomes"][family]["version"] = "0.0.0-old"
    fixture = _fixture(tmp_path, bump)
    rows = _rows(M.status(index_path=fixture))
    for family in ("basal_kalman", "flow_maxflow"):        # positive -> stale -> BUILT, version kept on the row
        row = rows[f"cognition.{family}"]
        assert row["label"] == "BUILT" and row["heldout"]["current"] is False
        assert row["heldout"]["version_measured"] == "0.0.0-old" and "needs re-admission" in row["basis"]
    assert rows["cognition.collective_quorum"]["label"] == "UNRESOLVED"       # EXPERIMENTAL persists
    assert "persists until a re-admission" in rows["cognition.collective_quorum"]["basis"]
    assert rows["cognition.flow_reinforce_greedy"]["label"] == "BUILT"        # SUPERSEDED persists
    assert "refuted" in rows["cognition.flow_reinforce_greedy"]["basis"]
    # the compiler reads the same fixture the same way
    evidence = json.loads(fixture.read_text())
    data = {k: 0 for k in library.genome("flow_maxflow").required_inputs}
    routed = next(c for c in compiler.candidates(data, compiler.CompetencyGeometry(), evidence)
                  if c["method"] == "cognition.flow_maxflow")
    assert routed["status"] == "UNEVALUATED" and routed["stale_evidence"]


def test_external_verification_counts_only_for_the_current_version(tmp_path):
    current = library.genome("flow_maxflow").version

    def verify(index):
        index["genomes"]["flow_maxflow"]["external_verification"] = [{"ref": "receipt:x", "version": current}]
        index["genomes"]["queue_erlang"]["external_verification"] = [{"ref": "receipt:y", "version": "0.0.1"}]
        index["recipes"]["bayes_then_voi"]["external_verification"] = [{"ref": "receipt:z"}]
    rows = _rows(M.status(index_path=_fixture(tmp_path, verify)))
    assert rows["cognition.flow_maxflow"]["label"] == "EXTERNALLY_VERIFIED"
    assert rows["cognition.queue_erlang"]["label"] == "HELDOUT_SUPPORTED"     # an old version's check does not count
    assert rows["recipe.bayes_then_voi"]["label"] == "EXTERNALLY_VERIFIED"


@pytest.mark.parametrize("wins, losses, label", [(17, 13, "UNRESOLVED"), (2, 15, "BUILT")])
def test_a_recipe_without_lift_is_unresolved_unless_significantly_worse(tmp_path, wins, losses, label):
    def change(index):
        index["recipes"]["forecast_then_allocate"].update(wins=wins, losses=losses)
    rows = _rows(M.status(index_path=_fixture(tmp_path, change)))
    assert rows["recipe.forecast_then_allocate"]["label"] == label


@pytest.mark.parametrize("verdict, label", [("GAIN", "HELDOUT_SUPPORTED"), ("REGRESSION", "BUILT"),
                                            ("NO_SIGNIFICANT_DIFFERENCE", "UNRESOLVED")])
def test_the_p4_route_is_labelled_from_its_frozen_verdict(tmp_path, verdict, label):
    def change(index):
        index["routing"]["conditional_competence"]["verdict"] = verdict
    rows = _rows(M.status(index_path=_fixture(tmp_path, change)))
    assert rows["routing.conditional_competence"]["label"] == label


def test_a_missing_index_is_reported_and_nothing_is_supported(tmp_path):
    status = M.status(index_path=tmp_path / "absent.json")
    assert status["missing_sources"] and status["generated_from"]["evidence_index"]["present"] is False
    assert all(r["label"] not in SUPPORTED for r in status["mechanisms"])


def test_a_verdict_for_a_genome_no_longer_in_the_library_is_unresolved_not_dropped(tmp_path):
    def change(index):
        index["genomes"]["retired_probe"] = {"status": "DEFAULT_FOR_GEOMETRY", "version": "1.0.0", "history": []}
    row = _rows(M.status(index_path=_fixture(tmp_path, change)))["cognition.retired_probe"]
    assert row["label"] == "UNRESOLVED" and row["heldout"]["status"] == "DEFAULT_FOR_GEOMETRY"


def test_a_catalog_family_without_an_executor_is_unresolved(monkeypatch):
    monkeypatch.setitem(FAMILIES, "unbuilt_probe", (3, ("unbuilt_op",), ("estimate",), "bounded_estimate", None))
    row = _rows(M.status())["cognition.unbuilt_probe"]
    assert row["label"] == "UNRESOLVED" and row["executor"] is None


def test_frontier_records_stay_frontier_and_the_descendant_is_never_claimed():
    rows = _rows(M.status())
    frontier = {b["id"]: b for b in devpath.load()["frontier_backcasts"]}
    for record_id, record in frontier.items():
        row = rows[f"frontier.{record_id}"]
        assert row["label"] == "FRONTIER" and row["buildability_status"] == record["buildability_status"]
    descendants = [i for i, b in frontier.items() if b["buildability_status"] == "SCIENCE_FICTION_DESCENDANT"]
    assert descendants == ["substrate_independent_developmental_intelligence"]
    reserved = [r for r in rows.values() if r["kind"] == "reserved_cortex_family"]
    assert reserved and all(r["label"] == "UNRESOLVED" for r in reserved)


def test_the_cli_prints_the_same_json_and_writes_nothing():
    watched = [M.INDEX, M.PATH, ROOT / "cortex" / "genome.py"]
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in watched]
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "mind_status.py")], cwd=ROOT, env=env,
                         capture_output=True, text=True, timeout=300, check=True)
    assert json.loads(out.stdout) == json.loads(json.dumps(M.status()))
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in watched] == before
    assert M.status() == copy.deepcopy(M.status())                      # deterministic: no clock, no randomness
