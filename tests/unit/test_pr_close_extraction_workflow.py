"""The pr-close-extraction workflow runs section 53's close check on every closed PR, from its base, read-only.

GitHub Actions cannot run here, so this reads the workflow and executes its check step as written against a local
`origin` that serves a canonical branch and `pull/<n>/head`, with the event payload GitHub would write. The
judgment itself is tested in test_lineage_map.py::test_close_check_judges_a_closed_pr_by_section_53.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/pr-close-extraction.yml"
RECORD = "docs/collaboration/KERNEL-PR-PLACEMENTS.json"
INHERITANCE = "docs/collaboration/DEVELOPMENTAL-INHERITANCE-2026-09-30.json"
NINE = ("founder_intention", "intended_effect", "useful_mechanisms", "evidence", "negative_evidence",
        "remaining_capability_gap", "canonical_owner", "developmental_node", "prerequisites")


def _workflow():
    data = yaml.safe_load(WORKFLOW.read_text())
    return data, data.get("on", data.get(True))      # YAML 1.1 reads a bare `on` key as True


def test_it_fires_on_close_checks_out_the_base_and_holds_no_write_token():
    data, triggers = _workflow()
    assert triggers == {"pull_request": {"types": ["closed"]}}
    assert data["permissions"] == {"contents": "read"}
    [job] = data["jobs"].values()
    checkout = next(s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout"))
    assert checkout["with"]["ref"] == "${{ github.event.pull_request.base.ref }}"   # never the closed PR's code
    assert checkout["with"]["persist-credentials"] is False
    record = json.loads((ROOT / RECORD).read_text())
    assert f"--canonical-ref {data['env']['CANONICAL_REF']} " in record["method"]   # the line the record names


def _git(cwd, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True).stdout.strip()


def _commit(cwd, name, text):
    path = Path(cwd) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    _git(cwd, "add", name)
    _git(cwd, "commit", "-qm", name)
    return _git(cwd, "rev-parse", "HEAD")


@pytest.mark.skipif(not shutil.which("jq"), reason="the workflow's step uses jq, present on GitHub's runners")
def test_its_step_fails_an_unextracted_close_and_passes_an_extracted_one(tmp_path):
    data, _ = _workflow()
    canonical_ref = data["env"]["CANONICAL_REF"]
    [job] = data["jobs"].values()
    script = next(s for s in job["steps"] if "--close" in str(s.get("run", "")))["run"]

    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-q", "-b", canonical_ref)
    _commit(origin, "scripts/lineage_map.py", (ROOT / "scripts/lineage_map.py").read_text())
    _commit(origin, INHERITANCE, json.dumps({"placements": []}))
    _git(origin, "checkout", "-q", "-b", "side")
    extracted = _commit(origin, "work.py", "a mechanism nobody ported\n")
    unextracted = _commit(origin, "work.py", "a second mechanism nobody ported\n")
    _git(origin, "update-ref", "refs/pull/11/head", extracted)
    _git(origin, "update-ref", "refs/pull/12/head", unextracted)
    _git(origin, "checkout", "-q", canonical_ref)
    _commit(origin, RECORD, json.dumps({"placements": [
        {"number": 11, "head_sha": extracted, "disposition": "SUPERSEDED IMPLEMENTATION", "basis": "replaced",
         "closing": True, "nine": {k: f"answer {k}" for k in NINE}}]}))
    _commit(origin, "canonical.py", "the line moves on\n")

    work = tmp_path / "work"
    _git(tmp_path, "clone", "-q", "-b", canonical_ref, str(origin), str(work))   # the base, as checkout gives it

    def run(number, sha, merged=False):
        label = f"{number}-{'merged' if merged else 'closed'}"
        event = tmp_path / f"event-{label}.json"
        event.write_text(json.dumps({"pull_request": {"number": number, "merged": merged, "head": {"sha": sha}}}))
        temp = tmp_path / f"runner-{label}"
        temp.mkdir()
        env = {**os.environ, "CANONICAL_REF": canonical_ref, "NUMBER": str(number), "GITHUB_EVENT_PATH": str(event),
               "RUNNER_TEMP": str(temp), "GITHUB_STEP_SUMMARY": str(temp / "summary.md")}
        done = subprocess.run(["bash", "-e", "-c", script], cwd=work, env=env, capture_output=True, text=True)
        return done.returncode, json.loads((temp / "verdict.json").read_text()), (temp / "summary.md").read_text()

    code, verdict, summary = run(12, unextracted)
    assert code == 1 and verdict["verdict"] == "CLOSED_WITHOUT_EXTRACTION", verdict
    assert "Section 53 close check" in summary and "CLOSED_WITHOUT_EXTRACTION" in summary
    code, verdict, _ = run(11, extracted)
    assert code == 0 and verdict["verdict"] == "EXTRACTED", verdict
    code, verdict, _ = run(12, unextracted, merged=True)
    assert code == 0 and verdict["verdict"] == "MERGED", verdict
