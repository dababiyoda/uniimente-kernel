"""The Mind evidence index cites frozen files by digest: recompute every digest and every cited verdict.

docs/evidence/greg-mind-evidence-index.json is what the Competency Compiler routes on and what
scripts/mind_status.py labels from. This test recomputes, with its own code (hashlib and a pointer walk, never
scripts/build_mind_evidence_index.py):

* the sha256 of every listed source. A source absent from the checkout fails, naming every absent path and
  whether the clone is shallow; a shallow clone still holds every file of its commit, so absence is a defect;
* every genome, recipe and routing row against the file and pointer it cites, and every genome history entry
  against its own admission run; every cited file must be a listed, digested source;
* that every source names a source commit present in this repository. A shallow clone may not hold a commit
  outside its fetched depth: those commits are then reported by an explicit skip (``pytest -rs``), never passed.

Not verified: that a frozen run reproduces (its own harness re-runs it) or that the source commit is the code
that produced the file (the harness records that inside the file).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "docs" / "evidence" / "greg-mind-evidence-index.json"
ADMISSION = "docs/evidence/greg-genome-admission"


def _index() -> dict:
    return json.loads(INDEX.read_text())


def _shallow() -> bool | None:
    """True or False from git; None when git history is not available at all."""
    try:
        out = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=ROOT, capture_output=True,
                             text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return None if out.returncode else out.stdout.strip() == "true"


def test_every_listed_source_recomputes_to_its_recorded_sha256():
    sources = _index()["sources"]
    assert sources, "the index lists no frozen sources"
    absent, changed = [], []
    for source in sources:
        file = ROOT / source["path"]
        if not file.is_file():
            absent.append(source["path"])
        elif "sha256:" + hashlib.sha256(file.read_bytes()).hexdigest() != source["sha256"]:
            changed.append(source["path"])
    assert not absent, (f"index sources absent from this checkout (shallow clone: {_shallow()}); a shallow clone "
                        f"still has every file of its commit, so these are missing, not unfetched: {absent}")
    assert not changed, f"frozen sources changed after the index was built (rebuild or restore): {changed}"
    assert len({s['path'] for s in sources}) == len(sources), "a source is listed twice"


def _cite(ref: str, listed: set, problems: list):
    """'path#a.b' -> the value at keys a, b of that JSON file; records why when it cannot."""
    rel, _, fragment = ref.partition("#")
    if rel not in listed:
        problems.append(f"{ref}: cites a file that is not a listed, digested source")
        return None
    value = json.loads((ROOT / rel).read_text())
    for key in fragment.split(".") if fragment else []:
        if not isinstance(value, dict) or key not in value:
            problems.append(f"{ref}: pointer does not resolve at {key!r}")
            return None
        value = value[key]
    return value


def test_every_cited_verdict_matches_the_source_it_cites():
    index = _index()
    listed = {s["path"] for s in index["sources"]}
    problems = []
    for family, row in index["genomes"].items():
        cited = _cite(row["evidence"], listed, problems)
        if cited is not None and (cited.get("status"), cited.get("version")) != (row["status"], row.get("version")):
            problems.append(f"{family}: index {row['status']}@{row.get('version')} but source "
                            f"{cited.get('status')}@{cited.get('version')}")
        history = row.get("history") or []
        if not history or (history[-1]["status"], history[-1]["version"]) != (row["status"], row.get("version")):
            problems.append(f"{family}: the latest history entry must be the deciding run")
        for entry in history:
            run = _cite(f"{ADMISSION}/{entry['run']}/results.json#genomes.{family}", listed, problems)
            if run is not None and (run.get("status"), run.get("version")) != (entry["status"], entry["version"]):
                problems.append(f"{family}: history {entry} disagrees with its run")
    for recipe, row in index["recipes"].items():
        cited = _cite(row["evidence"], listed, problems)
        if cited is None:
            continue
        lift = bool(cited["lift"])
        expected = {"lift": lift, "status": "VPL_LIFT" if lift else "NO_LIFT", "wins": cited["routed_wins"],
                    "losses": cited["routed_losses"], "p_one_sided": cited["sign_test_p_one_sided"],
                    "prefer": None if lift else cited["best_constituent"]}
        observed = {k: row.get(k) for k in expected}
        if observed != expected:
            problems.append(f"recipe {recipe}: index {observed} but source {expected}")
    for name, row in index["routing"].items():
        cited = _cite(row["evidence"], listed, problems)
        if cited is not None and cited.get("verdict") != row["verdict"]:
            problems.append(f"routing {name}: index {row['verdict']} but source {cited.get('verdict')}")
    assert not problems, problems


def test_every_source_names_a_commit_present_in_this_repository():
    sources = _index()["sources"]
    unnamed = [s["path"] for s in sources if not s.get("source_commit")]
    assert not unnamed, f"frozen sources without a source commit: {unnamed}"
    shallow = _shallow()
    if shallow is None:
        pytest.skip("git history unavailable: source commits not verified for " +
                    ", ".join(sorted({s['source_commit'][:12] for s in sources})))
    absent = sorted({s["source_commit"] for s in sources
                     if subprocess.run(["git", "cat-file", "-e", f"{s['source_commit']}^{{commit}}"], cwd=ROOT,
                                       capture_output=True, timeout=30).returncode != 0})
    if absent and shallow:
        pytest.skip(f"shallow clone: {len(absent)} source commit(s) outside the fetched depth were not verified: "
                    f"{absent}")
    assert not absent, f"source commits absent from a full clone: {absent}"


def _flip_genome_status(index):
    row = index["genomes"][sorted(index["genomes"])[0]]
    row["status"] = "NICHE_CAPABILITY" if row["status"] == "DEFAULT_FOR_GEOMETRY" else "DEFAULT_FOR_GEOMETRY"


DIGESTS = test_every_listed_source_recomputes_to_its_recorded_sha256
VERDICTS = test_every_cited_verdict_matches_the_source_it_cites
COMMITS = test_every_source_names_a_commit_present_in_this_repository


@pytest.mark.parametrize("corrupt, check, needle", [
    (lambda i: i["sources"][0].update(sha256="sha256:" + "0" * 64), DIGESTS, "changed"),
    (lambda i: i["sources"][0].update(path="docs/evidence/nowhere.json"), DIGESTS, "absent"),
    (_flip_genome_status, VERDICTS, "but source"),
    (lambda i: next(iter(i["recipes"].values())).update(wins=10 ** 6), VERDICTS, "but source"),
    (lambda i: i["sources"].pop(), VERDICTS, "not a listed"),
    (lambda i: i["sources"][0].pop("source_commit"), COMMITS, "without a source commit"),
])
def test_the_checks_fail_on_a_corrupted_index(tmp_path, monkeypatch, corrupt, check, needle):
    """Each check is falsifiable: a corrupted copy of the real index must fail it."""
    index = _index()
    corrupt(index)
    fake = tmp_path / "index.json"
    fake.write_text(json.dumps(index))
    monkeypatch.setitem(globals(), "INDEX", fake)
    with pytest.raises(AssertionError, match=needle):
        check()
