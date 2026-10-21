"""The pre-registered re-admission of #155's control, game, information and probabilistic verdicts on the merged
solvers (cortex/evaluation/genome_admission/run_operations.py).

Development seeds and tmp evidence directories only: no held-out instance is generated here. The run itself happens
once, at the commit that adds its freeze (docs/evidence/greg-genome-admission/<run id>/PREREGISTRATION.md).
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from cortex.evaluation.genome_admission import run as run155
from cortex.evaluation.genome_admission import run_operations as R
from greg.cognition.contracts import CognitionError
from greg.cognition.genomes import admission
from greg.cognition.solvers import SOLVERS

ROOT = Path(__file__).resolve().parents[2]
MEASURED = ("DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY", "COMPOSITION_ONLY", "EXPERIMENTAL", "SUPERSEDED", "REJECTED")


def test_the_runner_reproduces_pr155s_benchmarks_on_development_seeds(monkeypatch):
    """#155's generators and arms, verbatim: on seeds 0-9, with #155's geometry at the merged native ceiling, each
    arm's metric equals cortex/evaluation/genome_admission/run.py BENCHMARKS[f](seed) exactly, under #155's names.
    The geometry is the one change from #155's, and every candidate output passes the verifier."""
    assert {k: v for k, v in run155.GEOMETRY.items() if R.GEOMETRY[k] != v} == {"compute_limit": 200000}
    assert R.GEOMETRY == {"compute_limit": 100000, "latency_limit": 10.0}
    monkeypatch.setattr(run155, "GEOMETRY", R.GEOMETRY)
    for family in R.FAMILIES:
        item = R.ITEMS[family]
        for seed in admission.DEV_SEEDS:
            expected = run155.BENCHMARKS[family](seed)
            data, truth = item.instance(seed)
            out = item.solve(data, {"latency_s": 5.0, "compute": 100000})
            assert out["status"] == "ANSWER", (family, seed)
            measured = {"candidate": item.metric(data, truth, out["output"]),
                        "baseline": item.metric(data, truth, item.baseline(data)),
                        "competitor": item.metric(data, truth, item.competitor(data))}
            assert measured == {arm: expected[arm] for arm in measured}, (family, seed)
            assert item.names == expected["names"]
            assert item.verify(data, out["output"], out["certificate"])["structurally_verified"], (family, seed)
        assert len(item.solve(item.instance(0)[0], None)["certificate"]) == (120 if family == "control" else 1)


def test_pr155s_geometry_crashes_the_merged_solvers_and_the_declared_geometry_does_not():
    """The defect that leaves #155's harness unable to re-measure: compute_limit 200000 exceeds the merged native
    ceiling, so the same request raises CognitionError; at the runner's geometry every family answers."""
    for family in R.FAMILIES:
        item = R.ITEMS[family]
        request = item.request(item.instance(0)[0])
        with pytest.raises(CognitionError, match=r"integer in \[1, 100000\] required"):
            SOLVERS[family](request, run155.GEOMETRY)
        with pytest.raises(CognitionError):
            run155.BENCHMARKS[family](0)
        assert SOLVERS[family](request, R.GEOMETRY)["status"] == "ANSWER"


def test_a_refuted_candidate_output_is_scored_wrong_and_never_wins(monkeypatch):
    """Every solver answer behind a candidate output is checked by greg.cognition.verification.verify. A forged
    value-of-information decision, or one forged PID step in 120, is refuted: scored wrong, below abstaining, with
    no win against either arm, and the rule rejects it."""
    real_information, real_control = SOLVERS["information"], SOLVERS["control"]

    def information(data, geometry):
        answer = real_information(data, geometry)
        return {**answer, "output": {**answer["output"], "acquire": not answer["output"]["acquire"]}}
    calls = []

    def control(data, geometry):
        answer = real_control(data, geometry)
        calls.append(None)
        if len(calls) % 120 == 0:            # the last step of each episode
            answer = {**answer, "output": {**answer["output"], "correction": answer["output"]["correction"] + 1e-3}}
        return answer
    monkeypatch.setitem(SOLVERS, "information", information)
    monkeypatch.setitem(SOLVERS, "control", control)
    for family in ("information", "control"):
        item = R.ITEMS[family]
        rows = admission.evaluate(item, admission.DEV_SEEDS)
        arms = [r["arms"]["candidate"] for r in rows]
        assert all(a["category"] == "wrong" and a["refuted"] and a["quality"] < R.ABSTAIN_QUALITY for a in arms), family
        status, detail = admission.decide(item, rows)
        assert status == "REJECTED" and detail["vs_baseline"]["wins"] == detail["vs_competitor"]["wins"] == 0
        assert R.rule_155(rows)["vs_baseline"]["wins"] == 0


def test_a_freeze_refuses_spent_development_p8_and_pr155_seeds_and_an_existing_freeze(tmp_path, monkeypatch):
    """The freeze lives under the genome harness's evidence tree (here the repository's, for its spent seeds); the
    held-out seeds are named, never defaulted; a refused freeze writes nothing."""
    monkeypatch.setattr(R, "EVIDENCE", tmp_path)
    refused = {1200: "spent by an earlier admission freeze", 1190: "spent", 0: "development", 7000: "P8-reserved",
               2001: "drawn by a #155 run", 3011: "#155", 1001: "#155"}
    for start, why in refused.items():
        with pytest.raises(SystemExit, match=why):
            R.main(["--freeze", f"r-{start}", "--heldout-start", str(start)])
        assert not (tmp_path / f"r-{start}").exists()
    with pytest.raises(SystemExit, match="--heldout-start"):
        R.main(["--freeze", "r-default"])
    R.main(["--freeze", "r1", "--heldout-start", "9000"])
    frozen = json.loads((tmp_path / "r1" / "freeze.json").read_text())
    assert frozen["inputs"]["heldout_seeds"] == list(range(9000, 9030))
    assert (frozen["inputs"]["rule"], frozen["inputs"]["rule_155"]) == (admission.RULE, R.RULE_155)
    assert frozen["inputs"]["geometry"] == R.GEOMETRY and frozen["inputs"]["families"] == list(R.FAMILIES)
    assert {R.RUNNER, "cortex/evaluation/genome_admission/run.py", "greg/cognition/genomes/admission.py",
            "greg/cognition/solvers.py", "greg/cognition/contracts.py", "greg/cognition/verification.py",
            "greg/cognition/worker.py", "greg/cognition/cortex.py"} <= set(frozen["inputs"]["code"])
    with pytest.raises(SystemExit, match="existing re-admission freeze"):
        R.main(["--freeze", "r1", "--heldout-start", "9100"])


def test_a_negative_start_cannot_alias_refused_seeds(tmp_path, monkeypatch):
    """random.Random(-s) is seeded exactly as random.Random(s), so a negative start would redraw #155's spent
    instances (-1030..-1001 alias 1001-1030) or a development seed (-38 reaches -9). The freeze refuses any negative
    seed, and a run re-checks the frozen seeds."""
    import random
    assert random.Random(-1011).random() == random.Random(1011).random()
    monkeypatch.setattr(R, "EVIDENCE", tmp_path)
    for start in (-1030, -38, -1):
        with pytest.raises(SystemExit, match="negative seeds"):
            R.main(["--freeze", f"neg{start}", "--heldout-start", str(start)])
        assert not (tmp_path / f"neg{start}").exists()
    assert R.refusals(range(-1030, -1000)) and R.refusals(range(-38, -8))
    assert R.refusals(range(9000, 9030)) == []


def _git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo, check=True,
                          capture_output=True, text=True).stdout.strip()


def test_a_run_inside_the_repository_is_bound_to_its_committed_pre_registration(tmp_path, monkeypatch):
    """Only a run directory inside the repository can be cited by the evidence index, so only there is the binding
    enforced: an uncommitted or edited freeze, or uncommitted changes elsewhere, refuse the run; a committed freeze in
    a clean tree runs, and source_commit is the commit that added the freeze. Seeds a later freeze spent are refused
    unless they are this run's own."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "README").write_text("x\n")
    _git(repo, "add", "README")
    _git(repo, "commit", "-qm", "base")
    evidence = repo / "evidence"
    monkeypatch.setattr(R, "REPO", repo)
    monkeypatch.setattr(R, "EVIDENCE", evidence)
    monkeypatch.setattr(admission, "EVIDENCE", evidence)
    monkeypatch.setattr(admission, "evaluate", lambda item, heldout: [])
    monkeypatch.setattr(admission, "decide",
                        lambda item, rows: ("EXPERIMENTAL", {"vs_baseline": {}, "vs_competitor": {}}))
    monkeypatch.setattr(R, "smoke", lambda family, seed: {"verifier": "STRUCTURALLY_VERIFIED"})
    monkeypatch.setattr(R, "rule_155", lambda rows: {"status": "EXPERIMENTAL"})
    R.main(["--freeze", "ops", "--heldout-start", "9000"])
    with pytest.raises(SystemExit, match="commit freeze.json"):
        R.main(["--run", "ops"])
    _git(repo, "add", "evidence/ops/freeze.json")
    _git(repo, "commit", "-qm", "pre-register ops")
    prereg = _git(repo, "rev-parse", "HEAD")
    (repo / "README").write_text("edited after the pre-registration\n")
    with pytest.raises(SystemExit, match="outside the run directory"):
        R.main(["--run", "ops"])
    _git(repo, "checkout", "-q", "README")
    manifest = evidence / "ops" / "freeze.json"
    pristine = manifest.read_text()
    manifest.write_text(pristine.replace('"frozen_at": "', '"frozen_at": "edited '))
    with pytest.raises(SystemExit, match="differs from the committed"):
        R.main(["--run", "ops"])
    manifest.write_text(pristine)
    later = evidence / "later"                                   # a later freeze spending this run's seeds
    later.mkdir()
    (later / "freeze.json").write_text(json.dumps({"inputs": {"heldout_seeds": [9005]}}))
    _git(repo, "add", "evidence/later/freeze.json")
    _git(repo, "commit", "-qm", "a later freeze")
    with pytest.raises(SystemExit, match="spent by an earlier admission freeze"):
        R.main(["--run", "ops"])
    _git(repo, "rm", "-q", "evidence/later/freeze.json")
    _git(repo, "commit", "-qm", "drop it")
    report = R.run("ops")
    head = _git(repo, "rev-parse", "HEAD")
    assert (report["pre_registered"], report["source_commit"], report["freeze_commit"]) == (True, head, prereg)
    assert report["seed_refusals"] == [] and report["freeze_sha256"] == R._sha(manifest)
    outside = R.preregistration(tmp_path / "elsewhere")
    assert outside == {"pre_registered": False, "reason": "the run directory is outside the repository"}


def test_a_re_admission_freeze_spends_its_seeds_for_every_later_admission(tmp_path, monkeypatch):
    """spent_seeds() scans the genome harness's evidence tree, where this runner writes its freeze: once frozen, its
    seeds are refused by a later re-admission and by the genome harness alike."""
    monkeypatch.setattr(R, "EVIDENCE", tmp_path)
    monkeypatch.setattr(admission, "EVIDENCE", tmp_path)
    R.main(["--freeze", "ops", "--heldout-start", "9000"])
    assert set(range(9000, 9030)) <= admission.spent_seeds()
    with pytest.raises(SystemExit, match="spent by an earlier admission freeze"):
        R.main(["--freeze", "ops-2", "--heldout-start", "9015"])
    with pytest.raises(SystemExit, match="spent"):
        admission.main(["--freeze", "genome-2", "--only", "flow_maxflow", "--heldout-start", "9010"])


def test_the_run_refuses_changed_frozen_inputs_and_never_overwrites_results(tmp_path, monkeypatch):
    """--run reproduces the freeze's inputs or refuses (a hashed file edited after the freeze, a tampered digest or
    protocol field); it refuses an existing results.json and leaves it untouched."""
    monkeypatch.setattr(R, "EVIDENCE", tmp_path)
    R.main(["--freeze", "r1", "--heldout-start", "9000"])
    path = tmp_path / "r1" / "freeze.json"
    pristine = path.read_text()
    sha = R._sha
    monkeypatch.setattr(R, "_sha", lambda p: "sha256:" + "e" * 64 if p.name == "solvers.py" else sha(p))
    with pytest.raises(SystemExit, match="FROZEN_INPUT_CHANGED"):             # solvers.py edited after the freeze
        R.main(["--run", "r1"])
    monkeypatch.setattr(R, "_sha", sha)
    for edit in (lambda i: i["code"].update({R.RUNNER: "sha256:" + "0" * 64}),
                 lambda i: i["geometry"].update(compute_limit=200000)):
        frozen = json.loads(pristine)
        edit(frozen["inputs"])
        path.write_text(json.dumps(frozen))
        with pytest.raises(SystemExit, match="FROZEN_INPUT_CHANGED"):
            R.main(["--run", "r1"])
    path.write_text(pristine)
    (tmp_path / "r1" / "results.json").write_text("{}\n")
    with pytest.raises(SystemExit, match="refusing to overwrite"):
        R.main(["--run", "r1"])
    assert (tmp_path / "r1" / "results.json").read_text() == "{}\n"


def test_the_results_carry_families_not_genomes_and_route_through_the_evidence_index(tmp_path, monkeypatch):
    """A run on development seeds 0-1 (the freeze is written directly: --freeze refuses development seeds) writes the
    shape the index builder reads through OPERATION_RUNS, and no "genomes" key its genome loop would ingest. Each
    family's row cites the run and binds the solver closure at the run's source commit, which is the code now."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_mind_evidence_index as B
    from greg.cognition import compiler as C
    monkeypatch.setattr(R, "EVIDENCE", tmp_path / B.ADMISSION)
    run = tmp_path / B.ADMISSION / "dev-run"
    run.mkdir(parents=True)
    (run / "freeze.json").write_text(json.dumps({"frozen_at": "dev", "inputs": R.inputs(admission.DEV_SEEDS[:2])}))
    R.main(["--run", "dev-run"])
    results = json.loads((run / "results.json").read_text())
    assert "genomes" not in results and list(results["families"]) == list(R.FAMILIES)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert (results["schema"], results["source_commit"], results["rule"]) == (R.SCHEMA, head, admission.RULE)
    assert results["finished_at"] and results["geometry"] == R.GEOMETRY
    assert results["freeze_sha256"] == "sha256:" + hashlib.sha256((run / "freeze.json").read_bytes()).hexdigest()
    for family, row in results["families"].items():
        assert row["status"] in MEASURED and row["rule_155_status"] in MEASURED and row["n"] == 2
        assert (row["candidate"], row["baseline"], row["competitor"]) == R.ITEMS[family].names
        assert [r["seed"] for r in row["heldout"]] == [0, 1]
        assert not any(r["arms"]["candidate"].get("refuted") for r in row["heldout"])
        smoke = row["canonical_path"]
        assert (smoke["verifier"], smoke["authority_created"]) == ("STRUCTURALLY_VERIFIED", False), smoke
    monkeypatch.setattr(B, "ROOT", tmp_path)
    monkeypatch.setattr(B, "OPERATION_RUNS", ((f"{B.ADMISSION}/dev-run/results.json", "families", None),))
    index = B.build()
    assert index["genomes"] == {} and [s["path"] for s in index["sources"]] == [f"{B.ADMISSION}/dev-run/results.json"]
    for family in R.FAMILIES:
        op, row = index["operations"][family], results["families"][family]
        assert (op["raw_status"], op["competitor"], op["baseline"]) == (row["status"], row["competitor"],
                                                                          row["baseline"])
        assert op["evidence"] == f"{B.ADMISSION}/dev-run/results.json#families.{family}"
        assert op["code"]["closure_sha256"] == C.solver_code(family)["closure_sha256"], family
