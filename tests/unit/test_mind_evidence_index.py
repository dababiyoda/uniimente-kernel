"""The evidence index reads the admission harness's own output shape, so admitted statuses reach routing."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import build_mind_evidence_index as B  # noqa: E402


def test_admission_statuses_reach_the_index_in_the_harness_shape(tmp_path, monkeypatch):
    run = tmp_path / B.ADMISSION / "run-x"
    run.mkdir(parents=True)
    (run / "results.json").write_text(json.dumps({
        "schema": "greg-genome-admission/1", "source_commit": "abc",
        "genomes": {"basal_kalman": {"status": "DEFAULT_FOR_GEOMETRY"}, "collective_market": {"status": "SUPERSEDED"}}}))
    monkeypatch.setattr(B, "ROOT", tmp_path)
    index = B.build()
    assert index["genomes"] == {
        "basal_kalman": {"status": "DEFAULT_FOR_GEOMETRY", "version": None,
                         "evidence": f"{B.ADMISSION}/run-x/results.json#genomes.basal_kalman",
                         "history": [{"run": "run-x", "status": "DEFAULT_FOR_GEOMETRY", "version": None}]},
        "collective_market": {"status": "SUPERSEDED", "version": None,
                              "evidence": f"{B.ADMISSION}/run-x/results.json#genomes.collective_market",
                              "history": [{"run": "run-x", "status": "SUPERSEDED", "version": None}]}}
    assert not any("admission" in m for m in index["missing_sources"])


def test_a_missing_admission_run_is_listed_never_invented(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "ROOT", tmp_path)
    index = B.build()
    assert index["genomes"] == {} and any("admission" in m for m in index["missing_sources"])


def test_a_later_run_decides_and_every_run_stays_in_the_history(tmp_path, monkeypatch):
    for run, status, version in (("2026-01-01-v1", "DEFAULT_FOR_GEOMETRY", "1.0.0"),
                                 ("2026-01-02-v2", "NICHE_CAPABILITY", "1.0.1")):
        path = tmp_path / B.ADMISSION / run
        path.mkdir(parents=True)
        (path / "results.json").write_text(json.dumps({"source_commit": run, "genomes": {
            "develop_constraint_release": {"status": status, "version": version}}}))
    monkeypatch.setattr(B, "ROOT", tmp_path)
    row = B.build()["genomes"]["develop_constraint_release"]
    assert (row["status"], row["version"]) == ("NICHE_CAPABILITY", "1.0.1")
    assert [(h["run"], h["status"], h["version"]) for h in row["history"]] == [
        ("2026-01-01-v1", "DEFAULT_FOR_GEOMETRY", "1.0.0"), ("2026-01-02-v2", "NICHE_CAPABILITY", "1.0.1")]
