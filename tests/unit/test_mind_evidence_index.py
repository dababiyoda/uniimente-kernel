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
                         "history": [{"run": "run-x", "status": "DEFAULT_FOR_GEOMETRY", "version": None}],
                         "code": None},      # no source commit recorded: no solver closure to bind
        "collective_market": {"status": "SUPERSEDED", "version": None,
                              "evidence": f"{B.ADMISSION}/run-x/results.json#genomes.collective_market",
                              "history": [{"run": "run-x", "status": "SUPERSEDED", "version": None}],
                              "code": None}}
    # the genome harness's run is present; PR #155's operation runs are absent from this tmp root and listed
    assert not any("no frozen held-out admission run" in m for m in index["missing_sources"])
    assert {rel for rel, _, _ in B.OPERATION_RUNS} <= set(index["missing_sources"])


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


def test_a_later_family_decides_a_recipe_and_earlier_verdicts_stay_in_its_history(tmp_path, monkeypatch):
    runs = (("a.json", {"F3": "graph_then_allocate"}, True, 11), ("b.json", {"F7": "graph_then_allocate"}, False, 3))
    for name, families, lift, wins in runs:
        family = next(iter(families))
        (tmp_path / name).write_text(json.dumps({"source_commit": name, "summary": {family: {
            "lift": lift, "best_constituent": "greedy", "routed_wins": wins, "routed_losses": 0,
            "sign_test_p_one_sided": 0.01}}}))
    monkeypatch.setattr(B, "ROOT", tmp_path)
    monkeypatch.setattr(B, "P6_RUNS", tuple((name, families) for name, families, _, _ in runs))
    row = B.build()["recipes"]["graph_then_allocate"]
    assert (row["family"], row["status"], row["prefer"]) == ("F7", "NO_LIFT", "greedy")
    assert [(h["family"], h["status"], h["wins"]) for h in row["history"]] == [("F3", "VPL_LIFT", 11)]


def test_operation_verdicts_route_only_when_measured_and_the_latest_run_decides(tmp_path, monkeypatch):
    """PR #155 lineage: a measured held-out verdict routes; a structural label is kept and routes as UNEVALUATED;
    a later file (including a one-family file) decides and every run stays in the history."""
    v1, v2, single = "v1.json", "v2.json", "one.json"
    (tmp_path / v1).write_text(json.dumps({"source_commit": "a", "families": {
        "pattern": {"status": "REJECTED"}, "search": {"status": "ALIAS"}, "crowd": {"status": "NOT_RUN"}}}))
    (tmp_path / v2).write_text(json.dumps({"source_commit": "b", "families": {"crowd": {"status": "DEFAULT_FOR_GEOMETRY"}}}))
    (tmp_path / single).write_text(json.dumps({"source_commit": "c", "status": {"status": "EXPERIMENTAL"}}))
    monkeypatch.setattr(B, "ROOT", tmp_path)
    monkeypatch.setattr(B, "OPERATION_RUNS", ((v1, "families", None), (v2, "families", None),
                                              (single, "status", "crowd")))
    ops = B.build()["operations"]
    assert (ops["pattern"]["status"], ops["pattern"]["measured"]) == ("REJECTED", True)
    assert (ops["search"]["status"], ops["search"]["raw_status"], ops["search"]["measured"]) == \
        ("UNEVALUATED", "ALIAS", False)
    assert (ops["crowd"]["status"], ops["crowd"]["evidence"]) == ("EXPERIMENTAL", f"{single}#status")
    assert [h["status"] for h in ops["crowd"]["history"]] == ["NOT_RUN", "DEFAULT_FOR_GEOMETRY", "EXPERIMENTAL"]


def test_another_harness_file_in_the_admission_directory_is_not_a_genome_source(tmp_path, monkeypatch):
    """PR #155's admission runs live under the same directory with a "families" key: the genome glob skips them
    (they enter through OPERATION_RUNS), so no source is listed twice."""
    run = tmp_path / B.ADMISSION / "2026-10-14"
    run.mkdir(parents=True)
    (run / "results.json").write_text(json.dumps({"source_commit": "x", "families": {"pattern": {"status": "REJECTED"}}}))
    monkeypatch.setattr(B, "ROOT", tmp_path)
    monkeypatch.setattr(B, "OPERATION_RUNS", ((f"{B.ADMISSION}/2026-10-14/results.json", "families", None),))
    index = B.build()
    paths = [s["path"] for s in index["sources"]]
    assert paths == [f"{B.ADMISSION}/2026-10-14/results.json"] and index["genomes"] == {}
    assert index["operations"]["pattern"]["status"] == "REJECTED"


def test_a_p_value_rounded_to_zero_by_its_harness_is_recomputed_exactly_from_the_counts(tmp_path, monkeypatch):
    """Review 2026-10-14: run_v4 rounds the sign-test p to six decimals, so F7's 92-0 was recorded as 0.0 and the
    index made 0.0 graph_then_allocate's deciding p. The index recomputes the exact p from the frozen counts and
    keeps the source's rounded value beside it, never as the p."""
    runs = (("a.json", "F3", 11, 0, 0.000488), ("b.json", "F7", 92, 0, 0.0))
    for name, family, wins, losses, rounded in runs:
        (tmp_path / name).write_text(json.dumps({"source_commit": name, "summary": {family: {
            "lift": True, "best_constituent": "greedy", "routed_wins": wins, "routed_losses": losses,
            "sign_test_p_one_sided": rounded}}}))
    monkeypatch.setattr(B, "ROOT", tmp_path)
    monkeypatch.setattr(B, "P6_RUNS", (("a.json", {"F3": "graph_then_allocate"}), ("b.json", {"F7": "graph_then_allocate"})))
    row = B.build()["recipes"]["graph_then_allocate"]
    assert row["p_one_sided"] == 2.0 ** -92 and row["p_one_sided"] > 0 and row["p_one_sided_as_recorded"] == 0.0
    [earlier] = row["history"]
    assert earlier["p_one_sided"] == 2.0 ** -11 and earlier["p_one_sided_as_recorded"] == 0.000488
    assert B.exact_sign_p(13, 4) == sum(__import__("math").comb(17, k) for k in range(13, 18)) / 2 ** 17
    assert B.exact_sign_p(0, 0) == 1.0
