"""Operation-family admission v3 (review of #179, M17): a live harness re-admits #155's operation families on the
converged tree, under a freeze that binds the solver closures it measures."""
from __future__ import annotations

import json

import pytest

from cortex.evaluation.genome_admission import run as V1
from cortex.evaluation.genome_admission import run_ops_v3 as R

pytestmark = pytest.mark.filterwarnings("ignore::RuntimeWarning")


def test_the_harness_reuses_lineage_benchmarks_and_the_frozen_rule_unchanged():
    from cortex.evaluation.genome_admission import run_v2 as V2
    assert {f: b for f, (b, _) in R.BENCHMARKS.items()} == {**V1.BENCHMARKS, **V2.BENCHMARKS}
    prereg = json.loads(R.PREREG.read_text())
    assert prereg["seeds"] == [R.SEEDS.start, R.SEEDS.stop - 1] == [5001, 5040]
    assert prereg["families"] == sorted(R.BENCHMARKS)
    assert sorted(prereg["structural_not_measured"]) == sorted(V1.STRUCTURAL)


def test_every_benchmarked_family_binds_its_solver_closure():
    bound = R.closures()
    assert set(bound) == set(R.BENCHMARKS)
    assert all(v and v["closure_sha256"].startswith("sha256:") for v in bound.values())
    assert R.inputs()["solver_closures"] == bound


def test_a_changed_solver_closure_changes_the_frozen_inputs(monkeypatch):
    before = R.inputs()
    real = R.closures()
    changed = {**real, "graph": {**real["graph"], "closure_sha256": "sha256:" + "0" * 64}}
    monkeypatch.setattr(R, "closures", lambda: changed)
    assert R.inputs() != before


def test_the_run_refuses_a_dirty_tree_and_unfrozen_or_changed_inputs(monkeypatch, tmp_path):
    monkeypatch.setattr(R, "dirty", lambda: [" M greg/cognition/solvers.py"])
    monkeypatch.setattr("sys.argv", ["run_ops_v3", "--out", str(tmp_path / "r.json")])
    with pytest.raises(SystemExit, match="DIRTY_TREE"):
        R.main()
    monkeypatch.setattr(R, "dirty", lambda: [])
    monkeypatch.setattr(R, "MANIFEST", tmp_path / "missing.json")
    with pytest.raises(SystemExit, match="NOT_FROZEN"):
        R.main()
    stale = tmp_path / "freeze.json"
    stale.write_text(json.dumps({"inputs": {**R.inputs(), "seeds": [1, 40]}}))
    monkeypatch.setattr(R, "MANIFEST", stale)
    with pytest.raises(SystemExit, match="FROZEN_INPUT_CHANGED"):
        R.main()
    assert not (tmp_path / "r.json").exists()


def test_the_freeze_refuses_to_overwrite(monkeypatch, tmp_path):
    existing = tmp_path / "freeze.json"
    existing.write_text("{}")
    monkeypatch.setattr(R, "dirty", lambda: [])
    monkeypatch.setattr(R, "MANIFEST", existing)
    monkeypatch.setattr("sys.argv", ["run_ops_v3", "--freeze"])
    with pytest.raises(SystemExit, match="refusing to overwrite"):
        R.main()
    assert existing.read_text() == "{}"


def test_measure_reports_every_family_and_the_sparse_geometry_on_development_seeds():
    measured = R.measure(seeds=range(1, 3))           # development seeds only; never the held-out range
    assert set(R.BENCHMARKS) | set(V1.STRUCTURAL) == set(measured["families"])
    for family in R.BENCHMARKS:
        row = measured["families"][family]
        assert row["n"] == 2 and row["status"] in ("REJECTED", "SUPERSEDED", "DEFAULT_FOR_GEOMETRY", "EXPERIMENTAL")
    assert measured["crowd_sparse"]["n"] == 2 and measured["crowd_sparse"]["candidate"].startswith("Dawid-Skene")
