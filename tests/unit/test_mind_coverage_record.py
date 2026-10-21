"""The Mind coverage record (docs/collaboration/MIND-COVERAGE-2026-10-21.json) cites only evidence that exists and
uses only the allowed status labels.

Evidence is written three ways:

* ``path``, ``path:line`` or ``path#pointer``: a file or directory in this tree (a cited line must exist);
* ``git:<sha>:<path>:<line>``: a file on PR #179's branch. It is checked with ``git cat-file`` when that commit is
  available locally, and skipped otherwise (a shallow CI checkout does not fetch #179's branch).
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / "docs" / "collaboration" / "MIND-COVERAGE-2026-10-21.json"
STATUSES = ("ABSENT", "INVENTORIED", "IMPLEMENTED", "INTEGRATED", "BENCHMARKED", "ADMITTED", "ATTACHED", "EXERCISED")
VERDICTS = ("MET", "PARTLY_MET", "UNMET")
LINEAGES = ("both", "#158", "#179", "n/a")


@pytest.fixture(scope="module")
def record():
    return json.loads(RECORD.read_text(encoding="utf-8"))


def _items(record):
    for layer in record["layers"].values():
        yield from layer["items"]


def _all_evidence(record):
    for mid, m in record["mechanisms"].items():
        for e in m["evidence"]:
            yield f"mechanism {mid}", e
    for i in _items(record):
        for e in i["evidence"]:
            yield f"item {i['id']}", e
    for s in record["section_31"]:
        yield f"section 31.{s['n']}", s["source"]
        for e in s["evidence"]:
            yield f"section 31.{s['n']}", e
    for f in record["frontier"]:
        for e in f["evidence"]:
            yield f"frontier {f['id']}", e
    for b in record["prioritized_build_list"]:
        for e in b["evidence"]:
            yield f"build {b['id']}", e
    for s in record["standard"]:
        yield "standard", s


def _git_available(sha: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=ROOT,
                          capture_output=True).returncode == 0


def test_every_cited_local_path_exists_and_every_cited_line_is_in_range(record):
    problems = []
    for where, ref in _all_evidence(record):
        if ref.startswith("git:"):
            continue
        path = ref.split("#", 1)[0]
        line = None
        m = re.match(r"^(.*):(\d+)$", path)
        if m:
            path, line = m.group(1), int(m.group(2))
        target = ROOT / path
        if not target.exists():
            problems.append(f"{where}: missing {ref}")
            continue
        if line is not None:
            if not target.is_file():
                problems.append(f"{where}: line cited on a directory {ref}")
            elif line < 1 or line > len(target.read_text(encoding="utf-8").splitlines()):
                problems.append(f"{where}: line out of range {ref}")
    assert not problems, "\n".join(problems)


def test_pr179_references_resolve_when_that_commit_is_present(record):
    refs = [(w, r) for w, r in _all_evidence(record) if r.startswith("git:")]
    assert refs, "the record cites PR #179 lineage evidence"
    by_sha = {}
    for where, ref in refs:
        m = re.match(r"^git:([0-9a-f]{7,40}):(.+?)(?::(\d+))?$", ref)
        assert m, f"{where}: malformed git reference {ref}"
        by_sha.setdefault(m.group(1), []).append((where, m.group(2), m.group(3)))
    checked = 0
    for sha, rows in by_sha.items():
        if not _git_available(sha):
            continue
        for where, path, line in rows:
            out = subprocess.run(["git", "show", f"{sha}:{path}"], cwd=ROOT, capture_output=True, text=True)
            assert out.returncode == 0, f"{where}: {path} missing at {sha}"
            if line:
                assert 1 <= int(line) <= len(out.stdout.splitlines()), f"{where}: line out of range {sha}:{path}:{line}"
            checked += 1
    if not checked:
        pytest.skip("PR #179's commit is not available in this checkout")


def test_every_status_label_is_allowed(record):
    assert set(record["status_ladder"]) == set(STATUSES)
    for mid, m in record["mechanisms"].items():
        assert m["status"] in STATUSES, mid
        for key in ("status_on_158", "status_on_179"):
            assert m[key] is None or m[key] in STATUSES, (mid, key)
        assert m["lineage"] in LINEAGES, mid
    for i in _items(record):
        assert i["status"] in STATUSES, i["id"]
        for key in ("status_on_158", "status_on_179"):
            assert i[key] is None or i[key] in STATUSES, (i["id"], key)
        assert i["lineage"] in LINEAGES, i["id"]
    for f in record["frontier"]:
        assert f["status"] in STATUSES, f["id"]
    for s in record["seed_requirement_crosswalk"]:
        assert s["status"] in STATUSES, s["source_id"]


def test_statuses_are_backed_and_never_inflated(record):
    for i in _items(record):
        if i["status"] == "ABSENT":
            assert i.get("search"), f"{i['id']}: ABSENT needs the search that found nothing"
            assert not i["mechanisms"], f"{i['id']}: ABSENT with a mechanism"
        else:
            assert i["evidence"], f"{i['id']}: a status above ABSENT needs evidence"
        for m in i["mechanisms"]:
            assert m in record["mechanisms"], f"{i['id']}: unknown mechanism {m}"
            # an item never rises above its best direct mechanism; precursors never count
        if i["mechanisms"]:
            best = max((record["mechanisms"][m]["status"] for m in i["mechanisms"]), key=STATUSES.index)
            assert STATUSES.index(i["status"]) <= STATUSES.index(best), i["id"]
    # nothing is founder-attached: the founder has attached no genome
    assert all(m["status"] != "ATTACHED" for m in record["mechanisms"].values())
    exercised = {mid for mid, m in record["mechanisms"].items() if m["status"] == "EXERCISED"}
    assert exercised, "the cortex rehearsal is the recorded exercise"
    for mid in exercised:
        assert any("evidence/" in e and ("ledger" in e or "summary" in e or ".json" in e)
                   for e in record["mechanisms"][mid]["evidence"]), mid


def test_section_31_has_all_seventeen_conditions_quoted_verbatim(record):
    rows = record["section_31"]
    assert [r["n"] for r in rows] == list(range(1, 18))
    source = (ROOT / record["standard"][0]).read_text(encoding="utf-8")
    for r in rows:
        assert r["verdict"] in VERDICTS, r["n"]
        assert f"{r['n']}. {r['condition']}" in source, f"31.{r['n']} is not verbatim"
        assert r["remaining_gap"] and r["evidence"], r["n"]
    counts = record["section_31_counts"]
    assert sum(counts.values()) == 17
    assert counts == {v: sum(1 for r in rows if r["verdict"] == v) for v in VERDICTS}


def test_counts_match_items_and_the_seed_crosswalk_is_complete(record):
    for key, layer in record["layers"].items():
        counted = {}
        for i in layer["items"]:
            counted[i["status"]] = counted.get(i["status"], 0) + 1
        assert counted == layer["counts"], key
    seed = json.loads((ROOT / "docs/cortex/SEED_GENOME_REQUIREMENTS.json").read_text(encoding="utf-8"))
    assert [s["source_id"] for s in record["seed_requirement_crosswalk"]] == [x["source_id"] for x in seed["source_crosswalk"]]
    ids = {i["id"] for i in _items(record)}
    for s in record["seed_requirement_crosswalk"]:
        assert s["coverage_items"] and set(s["coverage_items"]) <= ids, s["source_id"]


def test_frontier_destinations_and_build_list_are_complete(record):
    path = json.loads((ROOT / "greg/path.json").read_text(encoding="utf-8"))
    assert {f["id"] for f in path["frontier_backcasts"]} <= {f["id"] for f in record["frontier"]}
    for f in record["frontier"]:
        assert f["nearest_falsifiable_precursor"], f["id"]
    ranks = [b["rank"] for b in record["prioritized_build_list"]]
    assert ranks == list(range(1, len(ranks) + 1)) and len(ranks) >= 10
    for b in record["prioritized_build_list"]:
        for key in ("scope", "files", "acceptance_test", "falsifier", "effort", "natural_or_synthetic"):
            assert b[key], (b["id"], key)
    assert record["section_6_candidates"]
