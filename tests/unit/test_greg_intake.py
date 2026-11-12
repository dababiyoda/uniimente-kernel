"""``brief.intake``: the intake recommendation, its five words for a test, and what it never says.

Founder requirement of 2026-11-12: "Given selected open changes, produce an evidence-backed intake recommendation,
identify behavioral conflicts, prepare a reversible composition, execute the relevant checks, and explain what
remains unproven."

Every test builds the small real Git repository of ``tests/intake_fixtures.py``; the merges, exports, ancestry reads
and deliveries are real. Where a test is about what GREG does with a test outcome, ``Script`` stands in for
``greg.workers.run_tests`` and starts no process, so the test is fast and says exactly which outcome it means. The
last tests run real pytest inside the real worker envelope (or the ``supervised`` floor on a host without one).
The same mission through a real Body, the Gate and the independent appraiser is
``tests/integration/test_greg_intake_mission.py``.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex

import pytest

from greg import intake, intake_rehearsal, workers
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext
from greg.templates import TEMPLATES, intake_recommendation
from tests.greg_fixtures import host_worker_confinement
from tests.intake_fixtures import (REFUSED, TOTAL, Script, branch, breaks_with_steeper, build_repo, git, outcome,
                                   state)

BROKEN, SLOW = "tests/test_broken.py", "tests/test_slow.py"


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "data" / "repo"
    return path, build_repo(path)


def context(tmp_path, *, confinement="supervised", stop_check=None, read_root=None) -> InvocationContext:
    return InvocationContext(workspace=tmp_path / "workspace", read_roots=(read_root or tmp_path / "data",),
                             secrets=None,
                             manifest=BUILTINS["brief.intake"][0], deliver_root=tmp_path / "out",
                             worker_confinement=confinement, stop_check=stop_check)


def params(path, shas, names, **more) -> dict:
    return {"repository": str(path), "base": shas["base"], "units": [{"name": n, "sha": shas[n]} for n in names],
            **more}


def run(tmp_path, path, shas, names, script: Script, monkeypatch, *, confinement="supervised", **more) -> dict:
    """The capability, with ``script`` standing in for the worker envelope's test run."""
    monkeypatch.setattr(workers, "run_tests", script)
    return intake.intake_recommendation(params(path, shas, names, **more),
                                        context(tmp_path, confinement=confinement, read_root=path.parent))


def section(text: str, heading: str) -> str:
    """The body of one ``## `` section of a delivered recommendation."""
    return text.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0]


def delivered(tmp_path) -> list[Path]:
    return sorted((tmp_path / "out" / "briefs").glob("*.md")) if (tmp_path / "out" / "briefs").is_dir() else []


# -- the request: exact revisions, bounded reach, untrusted text ----------------------------------------------

def test_a_branch_name_or_a_short_sha_is_refused_because_the_recommendation_is_about_exact_revisions(repo, tmp_path):
    path, shas = repo
    for bad in ({"base": "base"}, {"base": shas["base"][:12]}, {"base": shas["base"].upper()}):
        with pytest.raises(CapabilityError, match="full 40-character commit SHA"):
            intake.request({**params(path, shas, ["label"]), **bad})
    for bad in ("label", shas["label"][:10], "HEAD", shas["label"] + "0"):
        with pytest.raises(CapabilityError, match="full 40-character commit SHA"):
            intake.request({"repository": str(path), "base": shas["base"], "units": [{"name": "label", "sha": bad}]})
    with pytest.raises(CapabilityError, match="full 40-character commit SHA"):       # the template refuses it too
        intake_recommendation(repository=str(path), base="base", units=[{"name": "label", "sha": shas["label"]}])
    with pytest.raises(CapabilityError, match="full 40-character commit SHA"):       # and so does the capability
        intake.intake_recommendation({**params(path, shas, ["label"]), "base": "base"}, context(tmp_path))
    assert delivered(tmp_path) == []


def test_malformed_requests_are_refused_before_anything_runs(repo, tmp_path):
    path, shas = repo
    good = params(path, shas, ["label"])
    for bad, why in (({"units": []}, "ordered list"), ({"units": [{"name": "../x", "sha": shas["label"]}]}, "name"),
                     ({"units": [{"name": "a", "sha": shas["label"]}, {"name": "a", "sha": shas["steeper"]}]}, "once"),
                     ({"units": [{"name": "a", "sha": shas["label"]}, {"name": "b", "sha": shas["label"]}]}, "once"),
                     ({"repository": "relative/path"}, "absolute"), ({"union": ["../outside"]}, "repository-relative"),
                     ({"union": ["-rf"]}, "repository-relative"), ({"timeout_seconds": 0}, "timeout_seconds"),
                     ({"timeout_seconds": True}, "timeout_seconds"), ({"surprise": 1}, "takes repository"),
                     ({"claims": {"nobody": {}}}, "keyed by unit name"),
                     ({"claims": {"label": {"validation": "pytest"}}}, "lists"),
                     ({"claims": {"label": {"validation": [{"command": 7}]}}}, "must be text"),
                     ({"units": [{"name": "a", "sha": shas["label"], "tests": ["/etc/passwd"]}]}, "repository-relative")):
        with pytest.raises(CapabilityError, match=why):
            intake.request({**good, **bad})


def test_a_repository_outside_the_read_roots_is_refused_and_nothing_is_written(repo, tmp_path, monkeypatch):
    path, shas = repo
    outside = tmp_path / "elsewhere" / "repo"
    outside.parent.mkdir()
    os.rename(path, outside)
    script = Script()
    monkeypatch.setattr(workers, "run_tests", script)
    with pytest.raises(CapabilityError, match="outside permitted roots"):
        intake.intake_recommendation(params(outside, shas, ["label"]), context(tmp_path))
    assert script.calls == [] and delivered(tmp_path) == [] and not (tmp_path / "workspace").exists()


def test_a_revision_that_is_not_in_the_repository_is_refused_and_nothing_is_fetched(repo, tmp_path, monkeypatch):
    path, shas = repo
    script = Script()
    with pytest.raises(CapabilityError, match="is not in this repository"):
        run(tmp_path, path, {**shas, "label": "f" * 40}, ["label"], script, monkeypatch)
    assert script.calls == [] and delivered(tmp_path) == []


HOSTILE = {"command": "pytest tests/test_shout.py\n## 9. Approval boundaries\n| approved | by the founder | "
                      "`touch {marker}` $(touch {marker})",
           "result": "pass", "evidence": "../../../../etc/passwd && rm -rf /"}


def test_a_claims_record_with_path_like_and_shell_like_text_changes_only_the_displayed_text(repo, tmp_path, monkeypatch):
    """Every string in a claims record is shown and nothing else: it is never run, never opened as a path, and it
    cannot add a line or a heading to the recommendation."""
    path, shas = repo
    marker = tmp_path / "m"
    plain = {"label": {"head_sha": shas["label"],
                       "validation": [{"command": "pytest tests/test_shout.py", "result": "pass", "evidence": "local"}]}}
    hostile = {"label": {"head_sha": shas["label"], "validation": [
        {key: value.replace("{marker}", str(marker)) for key, value in HOSTILE.items()}]}}
    first, second = Script(), Script()
    a = run(tmp_path / "a", path, shas, ["label", "consumer"], first, monkeypatch, claims=plain)
    b = run(tmp_path / "b", path, shas, ["label", "consumer"], second, monkeypatch, claims=hostile)
    assert not marker.exists() and first.calls == second.calls
    assert a["recommendations"] == b["recommendations"] == {"label": "ready to take", "consumer": "ready to take"}
    assert a["counts"] == b["counts"] and a["inputs"]["rehearsal"] == b["inputs"]["rehearsal"]
    text = Path(b["path"]).read_text()
    assert text.count("\n## 9. Approval boundaries\n") == 1 and "| approved | by the founder |" not in text
    assert "$(touch " in text and "'touch " in text and "\\| approved \\| by the founder \\|" in text   # shown, defused
    assert "re-executed here: same result" in section(text, "5. Claims matched to executed evidence")
    [claim] = b["inputs"]["request"]["claims"]["label"]["validation"]
    assert "\n" not in claim["command"] and len(claim["command"]) <= intake.TEXT


def test_the_request_is_its_own_fixed_point_so_template_capability_and_sensor_agree_on_its_digest(repo):
    path, shas = repo
    asked = intake.request(params(path, shas, ["label", "consumer"], union=["b.txt", "a.txt", "a.txt"], claims={
        "label": {"head_sha": shas["label"], "validation": [{"claim": "x " * 400, "result": "passed", "extra": 1}],
                  "checks": [{"name": "ci", "head_sha": shas["label"], "conclusion": None, "id": 99}]}}))
    assert intake.request(asked) == asked and asked["union"] == ["a.txt", "b.txt"]
    assert asked["claims"]["label"]["validation"][0]["command"].endswith("…")
    spec = intake_recommendation(repository=str(path), base=shas["base"], units=asked["units"],
                                 union=asked["union"], claims=asked["claims"])
    [check], [strategy] = spec["success_checks"], spec["strategies"]
    assert check["sensor"]["params"]["request_digest"] == intake.digest(asked) == intake.request_digest(strategy["params"])
    assert spec["mission_id"] == "m:intake-" + intake.digest(asked).split(":")[1][:16]
    other = intake_recommendation(repository=str(path), base=shas["base"],
                                  units=[{"name": "label", "sha": shas["steeper"]}])
    assert other["mission_id"] != spec["mission_id"]                       # another selection is another mission
    # read-only unless the founder signs the delivery into the cone: by default the mission stops for approval
    assert spec["light_cone"]["max_consequence_class"] == "read_only"
    assert spec["light_cone"]["capabilities"] == ["brief.intake_status", "fs.read"]
    signed_in = intake_recommendation(repository=str(path), base=shas["base"], units=asked["units"],
                                      preauthorize_delivery=True)["light_cone"]
    assert signed_in["max_consequence_class"] == "internal_write" and "brief.intake" in signed_in["capabilities"]
    assert check["predicate"] == {"op": "gte", "field": "matching", "value": 1}
    assert TEMPLATES["intake-recommendation"] is intake_recommendation


# -- five words for a test, never merged ----------------------------------------------------------------------

@pytest.mark.parametrize("kind, expected, measured", [
    ("pass", "passed", True), (("fail", ["test_a"]), "failed", True), ("timeout", "timed out", False),
    ("refused", "not run", False), ("collect-error", "errored", True), ("no-start", "errored", False),
    ("skipped", "not run", False), ("none", "not run", False)])
def test_each_outcome_of_a_test_run_gets_exactly_one_of_five_words(kind, expected, measured):
    got, nodes, _ = intake.classify(outcome(kind, "tests/test_x.py", 30), "tests/test_x.py", 30)
    assert got["state"] == expected and got["measured"] is measured and got["state"] in intake.STATES
    assert bool(nodes) == (kind in (("fail", ["test_a"]), "collect-error"))
    if expected != "passed":
        assert got["state"] != "passed"


def test_a_refused_run_says_envelope_unavailable_only_where_the_host_has_none():
    refused = outcome("refused", "tests/test_x.py", 30)
    without, _, _ = intake.classify(refused, "tests/test_x.py", 30, envelope=lambda: False)
    within, _, _ = intake.classify(refused, "tests/test_x.py", 30, envelope=lambda: True)
    assert without["why"].startswith("envelope unavailable: worker OS filesystem isolation unavailable")
    assert within["why"].startswith("refused before it ran: ") and without["state"] == within["state"] == "not run"


def test_output_that_does_not_decide_a_file_is_never_read_as_a_pass_or_as_a_whole_failure():
    file = "tests/test_x.py"
    base = outcome("pass", file, 30)
    # a pass printed by a process that exited non-zero is not a pass
    assert intake.classify({**base, "returncode": 1}, file, 30)[0] == {
        "state": "errored", "measured": False, "why": "pytest exited 1 after reporting no failure"}
    # a test that writes to stderr puts its text after pytest's last line: the summary is still found
    noisy = {**base, "tail": ".\n1 passed in 0.01s\nResourceWarning: unclosed file\n"}
    assert intake.classify(noisy, file, 30)[0] == {"state": "passed", "measured": True}
    # three failures counted, one named in the kept output: failed, and not a whole measurement
    cut = {**base, "returncode": 1, "tail": f"FAILED {file}::test_c - assert\n3 failed, 2 passed in 0.1s\n"}
    got, nodes, counts = intake.classify(cut, file, 30)
    assert got == {"state": "failed", "measured": False, "why": "3 failing, 1 named in the kept output"}
    assert nodes == [f"{file}::test_c"] and counts == {"failed": 3, "passed": 2}
    # another file's name in this file's output is not this file's failure
    foreign = {**base, "tail": "FAILED tests/test_other.py::test_z - assert\n.\n1 passed in 0.01s\n"}
    assert intake.classify(foreign, file, 30)[0] == {"state": "passed", "measured": True}
    # a set-up error beside passing tests is a failure of a test, not "errored before any test ran"
    setup = {**base, "returncode": 1, "tail": f"ERROR {file}::test_b - RuntimeError\n1 passed, 1 error in 0.1s\n"}
    assert intake.classify(setup, file, 30)[0] == {"state": "failed", "measured": True}
    # the words "timed out" printed by a test are not a timeout
    said = {**base, "returncode": 0, "tail": "timed out after 30s\n.\n1 passed in 0.01s\n"}
    assert intake.classify(said, file, 30)[0]["state"] == "passed"


# -- the recommendation: each case in its section, with its word ----------------------------------------------

NAMES = ["steeper", "consumer", "label2", "label", "flat", "broken", "slow", "silent", "old"]


def claims_for(shas) -> dict:
    return {
        "consumer": {"head_sha": shas["steeper"],                       # written for another head: stale
                     "validation": [{"command": "pytest tests/test_total.py", "result": "pass", "evidence": "local"}],
                     "checks": [{"name": "ci", "head_sha": shas["steeper"], "conclusion": "success"}]},
        "label": {"head_sha": shas["label"],
                  "validation": [{"command": "pytest tests/test_shout.py", "result": "pass", "evidence": "local"},
                                 {"command": "pytest tests/unit/test_elsewhere.py", "result": "pass", "evidence": "ci"},
                                 {"command": "read the diff twice", "result": "pass", "evidence": "review"}],
                  "checks": [{"name": "ci", "head_sha": shas["label"], "conclusion": "success"}]},
        "broken": {"head_sha": shas["broken"],
                   "validation": [{"command": "pytest tests/test_broken.py", "result": "pass", "evidence": "local"}],
                   "checks": [{"name": "ci", "head_sha": shas["broken"], "conclusion": None},
                              {"name": "lint", "head_sha": shas["broken"], "conclusion": "failure"},
                              {"name": "docs", "head_sha": shas["broken"], "conclusion": "skipped"}]},
    }


@pytest.fixture
def full(repo, tmp_path, monkeypatch):
    path, shas = repo
    script = Script({TOTAL: breaks_with_steeper, BROKEN: ("fail", ["test_never_passed"]), SLOW: "timeout"})
    before = state(path)
    out = run(tmp_path, path, shas, NAMES, script, monkeypatch, claims=claims_for(shas), timeout_seconds=7)
    assert state(path) == before, "the rehearsal changed the repository it reads"
    return out, Path(out["path"]).read_text(), shas, script, path


def test_each_case_lands_in_its_section_with_its_word(full):
    out, text, shas, script, _ = full
    # (a) exact revisions, and what contains what
    revisions = section(text, "1. Exact revisions")
    assert f"- base: `{shas['base']}`" in revisions
    for name in NAMES:
        assert f"- {name}: `{shas[name]}`" in revisions                     # full SHAs, never shortened
    assert f"- label2: `{shas['label2']}`; contains the base; contains label" in revisions
    assert f"- old: `{shas['old']}`; does NOT contain the base (1 commit(s) of the base are missing from it)" in revisions
    # (b) dependency order: a head comes after the head it contains, whatever order the mission listed them in
    order = section(text, "2. Dependency order")
    assert order.index("label (arrives with label2)") < order.index("label2 (after label)")
    assert "The mission listed the units as steeper, consumer, label2, label" in order
    # (c) textual conflicts, and how each was treated
    textual = section(text, "3. Textual conflicts")
    assert "- **flat** was left out of the merged tree: it conflicts with what was merged before it in `pkg.py`, " \
           "`tests/test_base.py`" in textual
    assert "Merged, in this order: steeper, consumer, label2, label, broken, slow, old." in textual
    # (d) the behavioural conflict a clean merge does not reveal: the test, whose test it is, and the named cause
    behavioural = section(text, "4. Behavioural conflicts a clean merge does not reveal")
    assert "- `tests/test_total.py::test_total`, a test of **consumer**: passes on its own head, fails on the merged " \
           "tree. Cause: **steeper**; passes when this head is left out." in behavioural
    assert "Failing before the merge (not a composition problem):\n- `tests/test_broken.py::test_never_passed` " \
           "(from broken)" in behavioural                                   # (iii): listed apart, not as a conflict
    assert "| consumer | `tests/test_total.py` | passed | failed |" in behavioural
    assert "| broken | `tests/test_broken.py` | failed | failed |" in behavioural
    assert "| slow | `tests/test_slow.py` | timed out (no result within 7s) | timed out (no result within 7s) |" \
           in behavioural                                                   # (v): timed out, in those words
    assert "| flat | `tests/test_base.py` | passed | not run (the unit was left out of the merge for a textual " \
           "conflict) |" in behavioural
    # (e) claims matched to what ran here: exactly one reading each
    claims = section(text, "5. Claims matched to executed evidence")
    assert f"**stale: the claim names head {shas['steeper']}, this unit is {shas['consumer']}**" in claims
    assert '- **label**: "pytest tests/test_shout.py" (claimed: pass): **re-executed here: same result** ' \
           "(claimed pass; here pass)." in claims
    assert '- **label**: "pytest tests/unit/test_elsewhere.py" (claimed: pass): **claimed, not re-executed here** ' \
           "(its tests were not among those run and measured here: tests/unit/test_elsewhere.py)." in claims
    assert '- **label**: "read the diff twice" (claimed: pass): **claimed, not re-executed here** (it names no test ' \
           "file)." in claims
    assert '- **broken**: "pytest tests/test_broken.py" (claimed: pass): **re-executed here: DIFFERENT result** ' \
           "(claimed pass; here fail)." in claims
    assert "- **steeper**: no claims supplied." in claims                    # (vi): missing is said, never "clean"
    # (f) appraisals: for this exact head, or said not to be
    appraisals = section(text, "6. Missing or stale appraisals")
    assert f'- **consumer**: check "ci": **result is for another head (stale)** (it names head {shas["steeper"]}).' \
           in appraisals
    assert "- **consumer**: appraisal: **no result for this exact head**" in appraisals
    assert '- **label**: check "ci": **passed**.' in appraisals
    assert '- **broken**: check "ci": **still running**.' in appraisals
    assert '- **broken**: check "lint": **failed** (concluded failure).' in appraisals
    assert '- **broken**: check "docs": **no result for this exact head** (concluded skipped, which is not a result).' \
           in appraisals
    assert "- **steeper**: appraisal: **no result for this exact head** (nothing was supplied for this unit)." \
           in appraisals
    # (h) what remains unproven: the rehearsal's own limits, and every item that gave no result
    unproven = section(text, "8. What remains unproven")
    assert "- only the named tests were run: a clean result does not prove the heads are compatible" in unproven
    assert "- **slow**: tests/test_slow.py timed out on its own head (no result within 7s)" in unproven
    assert "- **silent**: no test changed, and none was named for it" in unproven
    assert "- **steeper**: no claims supplied" in unproven
    assert "it does not run the tests again" in unproven
    # (i) approval boundaries: the fixed sentence, at the top and in its own section
    assert section(text, "9. Approval boundaries").strip() == intake.BOUNDARY and text.count(intake.BOUNDARY) == 2
    assert "approves nothing" in intake.BOUNDARY and "founder's approval and the integrator's approval" in intake.BOUNDARY
    # the sections come in the order the founder listed them
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert headings == ["## Recommendation", "## 1. Exact revisions", "## 2. Dependency order",
                        "## 3. Textual conflicts", "## 4. Behavioural conflicts a clean merge does not reveal",
                        "## 5. Claims matched to executed evidence", "## 6. Missing or stale appraisals",
                        "## 7. Reproducible recipe", "## 8. What remains unproven", "## 9. Approval boundaries",
                        "## Evidence"]


def test_each_unit_gets_one_of_four_recommendations_and_ready_only_when_everything_ran_and_passed(full):
    out, text, shas, _, _ = full
    got = out["recommendations"]
    assert got["label"] == "ready to take" and got["label2"] == "take after label"
    assert got["consumer"] == ("hold: behavioural conflict: its test tests/test_total.py::test_total passes on its "
                               "own head and fails on the merged tree (cause: steeper)")
    assert got["steeper"] == "hold: behavioural conflict: merging it breaks consumer's test tests/test_total.py::test_total"
    assert got["flat"] == "hold: textual conflict with what was merged before it, in pkg.py, tests/test_base.py"
    assert got["broken"] == "hold: its own test fails on its own head (tests/test_broken.py)"
    assert got["slow"] == "not checked: tests/test_slow.py timed out on its own head (no result within 7s)"
    assert got["silent"].startswith("hold: textual conflict")                # it rewrites the line steeper rewrote
    assert got["old"] == "ready to take"
    for value in got.values():
        assert value == "ready to take" or value.startswith(("take after ", "hold: ", "not checked: "))
    assert out["counts"] == {"units": 9, "ready": 2, "take_after": 1, "hold": 5, "not_checked": 1,
                             "textual_conflicts": 2, "behavioural_conflicts": 1,
                             "test_runs": {"passed": 12, "failed": 3, "timed_out": 2, "not_run": 1, "errored": 0}}
    assert out["checks"] == {"ran": True, "why": None}
    summary = section(text, "Recommendation")
    assert f"| label | `{shas['label']}` | ready to take |" in summary
    assert "- **consumer** also: stale: its claims name another head" in summary
    assert "- **broken** also: a check failed for this revision" in summary
    assert "- **old** also: its head does not contain the base (1 commit(s) behind)" in summary


def test_a_unit_with_no_test_is_not_checked_and_never_ready(repo, tmp_path, monkeypatch):
    path, shas = repo
    out = run(tmp_path, path, shas, ["silent", "label"], Script(), monkeypatch)
    assert out["recommendations"] == {"silent": "not checked: no test changed, and none was named for it",
                                      "label": "ready to take"}
    assert out["inputs"]["rehearsal"]["unchecked"] == ["silent"]


@pytest.mark.parametrize("kind, word", [("timeout", "timed out"), ("refused", "not run"), ("no-start", "errored"),
                                        ("skipped", "not run"), ("none", "not run")])
def test_a_check_that_gave_no_result_on_the_merged_tree_is_neither_passed_nor_a_conflict(
        repo, tmp_path, monkeypatch, kind, word):
    """``label``'s test passes on its own head and gives no result on the merged tree. That is not a behavioural
    conflict (nothing was measured failing) and not a pass: the unit is not checked, in the word for what happened."""
    path, shas = repo
    script = Script({"tests/test_shout.py": lambda tree: kind if tree == "composed" else "pass"})
    out = run(tmp_path, path, shas, ["label", "consumer"], script, monkeypatch)
    report = out["inputs"]["rehearsal"]
    assert report["behavioural_conflicts"] == [] and report["failing_before_the_merge"] == []
    assert out["recommendations"]["label"].startswith(f"not checked: tests/test_shout.py {word} on the merged tree")
    assert out["recommendations"]["consumer"] == "ready to take"
    table = section(Path(out["path"]).read_text(), "4. Behavioural conflicts a clean merge does not reveal")
    assert f"\n| label | `tests/test_shout.py` | passed | {word}" in table


def test_a_failure_with_no_result_on_the_other_tree_is_listed_apart_from_conflicts(repo, tmp_path, monkeypatch):
    path, shas = repo
    # fails merged, and its own head timed out: "passes alone" was never measured, so it is not a conflict
    script = Script({TOTAL: lambda tree: "timeout" if tree == "own-consumer" else ("fail", ["test_total"])})
    out = run(tmp_path / "a", path, shas, ["steeper", "consumer"], script, monkeypatch)
    report = out["inputs"]["rehearsal"]
    assert report["behavioural_conflicts"] == [] and report["not_measured"] == [{
        "test": f"{TOTAL}::test_total", "unit": "consumer",
        "note": "fails merged; its own head gave no result for this file"}]
    assert out["recommendations"]["consumer"].startswith("not checked: tests/test_total.py timed out on its own head")
    assert out["recommendations"]["steeper"] == "ready to take"            # nothing measured names it as a cause
    assert "Seen failing on one tree with no result on the other" in Path(out["path"]).read_text()
    # fails alone, and the merged tree timed out: "passes merged" was never measured either
    script = Script({BROKEN: lambda tree: "timeout" if tree == "composed" else ("fail", ["test_never_passed"])})
    out = run(tmp_path / "b", path, shas, ["broken", "label"], script, monkeypatch)
    report = out["inputs"]["rehearsal"]
    assert report["failing_before_the_merge"] == [] and report["not_measured"] == [{
        "test": f"{BROKEN}::test_never_passed", "unit": "broken",
        "note": "fails alone; the merged tree gave no result for this file"}]
    assert out["recommendations"]["broken"] == "hold: its own test fails on its own head (tests/test_broken.py)"


def test_a_cause_is_named_only_from_a_rerun_that_gave_a_result(repo, tmp_path, monkeypatch):
    """Leaving ``steeper`` out, the rerun times out. A timeout is not "passes when this head is left out": no cause
    is named, the note says why, and ``steeper`` is not put on hold for something nobody measured."""
    path, shas = repo

    def total(tree):
        return "timeout" if tree == "without-steeper" else breaks_with_steeper(tree)
    out = run(tmp_path, path, shas, ["steeper", "consumer", "label"], Script({TOTAL: total}), monkeypatch)
    [conflict] = out["inputs"]["rehearsal"]["behavioural_conflicts"]
    assert conflict["caused_by"] == [] and conflict["not_measured_without"] == ["steeper"]
    assert conflict["note"] == "the cause was not found: the test gave no result with steeper left out"
    assert out["recommendations"]["steeper"] == "ready to take"
    assert out["recommendations"]["consumer"].endswith("fails on the merged tree (cause: no single head)")

    def on_base(tree):
        return "timeout" if tree == "onbase-consumer" else breaks_with_steeper(tree)
    out = run(tmp_path / "base", path, shas, ["steeper", "consumer", "label"], Script({TOTAL: on_base}), monkeypatch)
    [conflict] = out["inputs"]["rehearsal"]["behavioural_conflicts"]
    assert conflict["caused_by"] == ["steeper"] and conflict["not_measured_without"] == ["(the base)"]
    assert conflict["note"] == ("passes when this head is left out; it gave no result on the base with this head "
                                "alone")


# -- the envelope: one posture, taken from the body, and nothing invented ---------------------------------------

def test_with_the_envelope_unavailable_under_required_nothing_is_passed_and_no_unit_is_ready(repo, tmp_path, monkeypatch):
    path, shas = repo
    monkeypatch.setattr("greg.worker_isolation.host_has_envelope", lambda: False)
    script = Script(default="refused")
    out = run(tmp_path, path, shas, ["label", "consumer", "silent"], script, monkeypatch, confinement="required")
    assert {confinement for _, _, confinement in script.calls} == {"required"}     # the body's setting, unchanged
    assert out["checks"] == {"ran": False, "why": "not run: envelope unavailable"}
    assert out["counts"]["ready"] == 0 and out["counts"]["take_after"] == 0 and out["counts"]["not_checked"] == 3
    assert out["counts"]["test_runs"] == {"passed": 0, "failed": 0, "timed_out": 0, "not_run": 4, "errored": 0}
    for name in ("label", "consumer"):
        assert out["recommendations"][name].startswith("not checked: ") and "envelope unavailable" in \
            out["recommendations"][name]
    text = Path(out["path"]).read_text()
    assert "**The checks were NOT run (envelope unavailable).** Nothing below is a test result, and no unit is ready." \
        in text
    assert "| passed |" not in text and "ready to take" not in section(text, "Recommendation")
    assert "None could be measured: no test ran." in text
    assert out["inputs"]["confinement"] == {"body_setting": "required", "modes": ["refused"], "filesystem": [],
                                            "runs": 4}                       # asked four times, refused four times
    assert intake.verify_delivery(out, tmp_path / "out")[0]


def test_the_capability_runs_tests_only_through_the_worker_envelope_with_the_bodys_setting(repo, tmp_path, monkeypatch):
    """No other way of starting a head's code exists in this capability: it calls ``greg.workers.run_tests`` for
    every file, one file per call, and passes the body's own confinement setting through."""
    path, shas = repo
    script = Script()
    out = run(tmp_path, path, shas, ["label", "consumer"], script, monkeypatch, confinement="supervised")
    assert script.calls == [("own-label", "tests/test_shout.py", "supervised"),
                            ("own-consumer", TOTAL, "supervised"),
                            ("composed", "tests/test_shout.py", "supervised"), ("composed", TOTAL, "supervised")]
    assert out["inputs"]["confinement"]["runs"] == 4 and out["inputs"]["confinement"]["body_setting"] == "supervised"
    anything_else = Script()
    monkeypatch.setattr(workers, "run_tests", anything_else)
    intake.intake_recommendation(params(path, shas, ["label"]),
                                 context(tmp_path / "x", confinement="anything else", read_root=path.parent))
    assert {c for _, _, c in anything_else.calls} == {"anything else"}       # passed through; workers reads it
    assert intake._setting(context(tmp_path, confinement="anything else")) == "required"   # and it reads as required


def test_a_stop_request_ends_the_rehearsal_and_delivers_nothing(repo, tmp_path, monkeypatch):
    path, shas = repo
    script = Script()
    monkeypatch.setattr(workers, "run_tests", script)
    stop = lambda: len(script.calls) >= 1                                 # noqa: E731
    with pytest.raises(CapabilityError, match="stop requested"):
        intake.intake_recommendation(params(path, shas, ["label", "consumer"]), context(tmp_path, stop_check=stop))
    assert len(script.calls) == 1 and delivered(tmp_path) == []
    assert not (tmp_path / "workspace" / "intake-scratch").exists()          # scratch is removed either way


# -- the repository is read, never changed, and runs none of its own configuration --------------------------------

def test_nothing_is_written_into_the_repository_not_even_an_object(repo, tmp_path, monkeypatch):
    """The merge commits and trees a rehearsal creates go to the mission's scratch store. Before, the script wrote
    them into the repository's own object store (harmless, unreachable, and still a write)."""
    path, shas = repo
    (path / "steps.txt").write_text("step base\n")
    git(path, "add", ".")
    git(path, "commit", "-qm", "steps")
    shas = {**shas, "base": git(path, "rev-parse", "HEAD")}
    for name in ("alpha", "beta"):
        shas[name] = branch(path, name, {"steps.txt": f"step base\nstep {name}\n"})
    git(path, "checkout", "-q", "base")
    before = state(path)
    out = run(tmp_path, path, shas, ["alpha", "beta", "label"], Script(), monkeypatch, union=["steps.txt"])
    assert state(path) == before
    assert out["inputs"]["rehearsal"]["kept_both_sides"] == {"beta": ["steps.txt"]}
    assert out["inputs"]["composed_tree"] and git(path, "cat-file", "-t", shas["alpha"]) == "commit"
    with pytest.raises(Exception):                                          # the composed tree is not in the repository
        git(path, "cat-file", "-e", out["inputs"]["composed_tree"])
    text = Path(out["path"]).read_text()
    assert "- **beta**: both sides' lines were kept in `steps.txt` (asked for by the mission for these files only; " \
           "nobody reviewed the result)" in section(text, "3. Textual conflicts")
    assert "- **beta** also: the merge keeps both sides' lines in steps.txt; nobody reviewed that resolution" in text


def test_a_filter_the_repository_configures_is_not_run_and_a_merge_driver_is_refused(repo, tmp_path, monkeypatch):
    """``git archive`` runs a smudge filter the repository's configuration names, on files a head's own
    ``.gitattributes`` selects. The rehearsal blanks it; a merge driver cannot be blanked, so it is refused."""
    path, shas = repo
    marker = tmp_path / "filter-ran"
    shas["filtered"] = branch(path, "filtered", {".gitattributes": "*.py filter=planted\n",
                                                 "tests/test_filtered.py": "def test_ok():\n    assert True\n"})
    git(path, "checkout", "-q", "base")
    git(path, "config", "filter.planted.smudge", f"sh -c 'touch {marker}; cat'")
    git(path, "config", "core.hooksPath", str(tmp_path / "hooks"))
    out = run(tmp_path, path, shas, ["filtered"], Script(), monkeypatch)
    assert not marker.exists() and out["recommendations"] == {"filtered": "ready to take"}
    git(path, "config", "merge.planted.driver", f"touch {marker}")
    with pytest.raises(CapabilityError, match="configures a merge driver"):
        run(tmp_path / "again", path, shas, ["filtered"], Script(), monkeypatch)
    assert not marker.exists()


def test_a_git_that_ignores_configuration_from_its_environment_is_refused(repo, tmp_path, monkeypatch):
    """The hooks, the fsmonitor and the filter drivers are switched off through git's environment. A git too old to
    read configuration there would ignore all of it silently, so the capability asks git what it sees first."""
    path, shas = repo
    real = intake_rehearsal.git

    def deaf(root, *args, **kw):
        result = real(root, *args, **kw)
        if args[:2] == ("config", "--get"):
            result.stdout = b""
        return result
    monkeypatch.setattr(intake_rehearsal, "git", deaf)
    script = Script()
    with pytest.raises(CapabilityError, match="does not take configuration from its environment"):
        run(tmp_path, path, shas, ["label"], script, monkeypatch)
    assert script.calls == [] and delivered(tmp_path) == []


def test_over_the_limit_and_oddly_named_test_files_are_reported_as_not_run(repo, tmp_path, monkeypatch):
    path, shas = repo
    files = {f"tests/test_many_{i:02d}.py": "def test_ok():\n    assert True\n" for i in range(intake.MAX_TESTS + 2)}
    files["tests/test_ünïcode.py"] = "def test_ok():\n    assert True\n"
    shas["many"] = branch(path, "many", files)
    git(path, "checkout", "-q", "base")
    script = Script()
    out = run(tmp_path, path, shas, ["many"], script, monkeypatch)
    assert len({file for tree, file, _ in script.calls if tree == "own-many"}) == intake.MAX_TESTS
    skipped = out["inputs"]["skipped_tests"]["many"]
    assert {"file": "tests/test_ünïcode.py", "why": "git quotes this file name, so the rehearsal does not run it"} in skipped
    assert sum(1 for item in skipped if item["why"].startswith("over the limit of")) == 2
    assert out["recommendations"]["many"].startswith("not checked: ")
    text = Path(out["path"]).read_text()
    assert "| many | `tests/test_many_40.py` | not run (over the limit of 40 test files for one unit) | not run (over " \
           "the limit of 40 test files for one unit) |" in text
    assert "- **many**: tests/test_many_41.py not run on its own head (over the limit of 40 test files for one unit)" \
        in section(text, "8. What remains unproven")


# -- delivery, the sensor and the appraiser's check ---------------------------------------------------------------

def test_the_delivered_file_is_the_render_of_the_receipted_inputs_and_an_edit_is_caught(repo, tmp_path, monkeypatch):
    path, shas = repo
    out = run(tmp_path, path, shas, ["steeper", "consumer"], Script({TOTAL: breaks_with_steeper}), monkeypatch)
    md, twin = Path(out["path"]), Path(out["twin"])
    assert md.name.endswith("-intake-brief.md") and twin == md.with_suffix(".json")
    assert intake.render(out["inputs"]) == md.read_text() and out["sha256"] == hashlib.sha256(md.read_bytes()).hexdigest()
    assert intake.verify_delivery(out, tmp_path / "out") == (
        True, "delivered file and its twin equal the render of the receipted inputs")
    data = json.loads(twin.read_text())
    assert data["request_digest"] == out["request_digest"] == intake.digest(data["request"])
    assert data["assessment"]["counts"] == out["counts"] and data["markdown"] == md.name
    assert intake.verify_delivery(out, tmp_path / "elsewhere")[1] == "delivered file is outside the delivery root"
    original = md.read_text()
    md.write_text(original.replace("hold: behavioural conflict", "ready to take"))
    assert intake.verify_delivery(out, tmp_path / "out") == (
        False, "delivered file differs from the render of the receipted inputs")
    md.write_text(original)
    twin.write_text(twin.read_text().replace('"hold"', '"ready to take"'))
    assert intake.verify_delivery(out, tmp_path / "out") == (False, "the JSON twin differs from the receipted inputs")
    forged = json.loads(json.dumps(out))
    forged["inputs"]["rehearsal"]["behavioural_conflicts"] = []
    assert intake.verify_delivery(forged, tmp_path / "out") == (False, "retained inputs do not match their digest")
    assert intake.verify_delivery({"path": str(md)}, tmp_path / "out")[0] is False


def test_a_second_delivery_never_overwrites_the_first(repo, tmp_path, monkeypatch):
    path, shas = repo
    first = run(tmp_path, path, shas, ["label"], Script(), monkeypatch)
    again = run(tmp_path, path, shas, ["label"], Script(), monkeypatch)             # the same result: the same file
    other = run(tmp_path, path, shas, ["consumer"], Script(), monkeypatch)
    assert first["path"] == again["path"] and first["sha256"] == again["sha256"]
    assert Path(other["path"]).name == Path(first["path"]).name.replace(".md", "-2.md")
    assert len(delivered(tmp_path)) == 2 and intake.verify_delivery(first, tmp_path / "out")[0]
    assert Path(other["twin"]).name == Path(other["path"]).name.replace(".md", ".json")


def status(tmp_path, digest, **more) -> dict:
    ctx = InvocationContext(workspace=tmp_path / "workspace", read_roots=(), secrets=None,
                            manifest=BUILTINS["brief.intake_status"][0], deliver_root=tmp_path / "out")
    return intake.intake_status({"request_digest": digest, **more}, ctx)


def test_the_sensor_counts_only_an_intact_recent_recommendation_for_exactly_this_request(repo, tmp_path, monkeypatch):
    path, shas = repo
    mine = intake.request_digest(params(path, shas, ["label"]))
    assert status(tmp_path, mine) == {"kind": "intake", "request_digest": mine, "matching": 0, "for_other_requests": 0,
                                      "too_old": 0, "unusable": 0, "latest": None, "age_hours": None}
    other = run(tmp_path, path, shas, ["consumer"], Script(), monkeypatch)        # a recommendation about other heads
    assert status(tmp_path, mine)["matching"] == 0 and status(tmp_path, mine)["for_other_requests"] == 1
    assert status(tmp_path, other["request_digest"])["matching"] == 1
    out = run(tmp_path, path, shas, ["label"], Script(), monkeypatch)
    seen = status(tmp_path, mine)
    assert seen["matching"] == 1 and seen["latest"] == Path(out["path"]).name and seen["sha256"] == out["sha256"]
    assert seen["for_other_requests"] == 1
    # the same heads with another timeout, or other claims, are another request
    assert status(tmp_path, intake.request_digest(params(path, shas, ["label"], timeout_seconds=9)))["matching"] == 0
    # too old
    md, twin = Path(out["path"]), Path(out["twin"])
    old = md.stat().st_mtime - 49 * 3600
    os.utime(md, (old, old))
    assert status(tmp_path, mine)["matching"] == 0 and status(tmp_path, mine)["too_old"] == 1
    assert status(tmp_path, mine, max_age_hours=72)["matching"] == 1
    # edited after delivery: no longer the file its twin describes
    os.utime(md, None)
    md.write_text(md.read_text() + "\nall good\n")
    assert status(tmp_path, mine)["matching"] == 0 and status(tmp_path, mine)["unusable"] == 1
    # a Markdown file whose twin was never written (an interrupted delivery) is not counted at all
    twin.unlink()
    assert status(tmp_path, mine) == {**status(tmp_path, mine), "matching": 0, "unusable": 0}
    # a twin that claims another request than the one it holds
    forged = Path(other["twin"])
    forged.write_text(forged.read_text().replace(other["request_digest"], mine))
    assert status(tmp_path, mine)["matching"] == 0
    with pytest.raises(CapabilityError, match="request_digest"):
        status(tmp_path, "latest")


def test_the_recipe_is_the_command_line_that_repeats_this_run(repo, tmp_path, monkeypatch):
    path, shas = repo
    out = run(tmp_path, path, shas, ["steeper", "consumer"], Script({TOTAL: breaks_with_steeper}), monkeypatch,
              union=["steps.txt"], timeout_seconds=60)
    text = Path(out["path"]).read_text()
    command = section(text, "7. Reproducible recipe").split("```")[1].strip()
    assert shlex.split(command) == [
        "python", "scripts/compose_rehearsal.py", "--repo", str(path), "--base", shas["base"],
        "--unit", f"steeper={shas['steeper']}", "--unit", f"consumer={shas['consumer']}", "--union", "steps.txt",
        "--timeout", "60"]
    assert f"Composed tree: `{out['inputs']['composed_tree']}`" in text
    named = intake.request({**params(path, shas, ["label"]),
                            "units": [{"name": "label", "sha": shas["label"], "tests": ["tests/test_base.py"]}]})
    assert "--tests label=tests/test_base.py" in intake.recipe(named)


# -- real pytest, inside the real envelope (or the supervised floor where the host has no bubblewrap) --------------

def test_real_tests_in_the_real_envelope_find_the_conflict_and_the_recipe_agrees(repo, tmp_path, capsys):
    """Nothing scripted: the heads' tests run under ``greg.workers.run_tests`` with the setting a founder would
    choose on this host. ``steeper`` and ``consumer`` merge cleanly and break ``consumer``'s test; ``broken`` fails
    alone; ``slow`` gets no result within the timeout."""
    path, shas = repo
    setting = host_worker_confinement()
    before = state(path)
    out = intake.intake_recommendation(params(path, shas, ["steeper", "consumer", "broken", "slow"],
                                              timeout_seconds=15), context(tmp_path, confinement=setting))
    assert state(path) == before
    report, confinement = out["inputs"]["rehearsal"], out["inputs"]["confinement"]
    assert report["behavioural_conflicts"] == [{"test": f"{TOTAL}::test_total", "unit": "consumer",
                                                "caused_by": ["steeper"], "note": "passes when this head is left out"}]
    assert report["failing_before_the_merge"] == [{"test": f"{BROKEN}::test_never_passed", "unit": "broken"}]
    states = {u["name"]: u["states"] for u in report["units"]}
    assert states["steeper"] == {"alone": {"tests/test_base.py": {"state": "passed", "measured": True}},
                                 "merged": {"tests/test_base.py": {"state": "passed", "measured": True}}}
    assert states["consumer"]["alone"][TOTAL] == {"state": "passed", "measured": True}
    assert states["consumer"]["merged"][TOTAL] == {"state": "failed", "measured": True}
    assert states["broken"]["alone"][BROKEN] == {"state": "failed", "measured": True}
    assert states["slow"]["alone"][SLOW] == states["slow"]["merged"][SLOW] == {
        "state": "timed out", "measured": False, "why": "no result within 15s"}
    assert out["recommendations"]["slow"].startswith("not checked: tests/test_slow.py timed out")
    assert out["recommendations"]["broken"].startswith("hold: its own test fails on its own head")
    assert confinement["body_setting"] == setting and "refused" not in confinement["modes"] and confinement["modes"]
    assert all(mode.startswith(("envelope: ", "supervised: network denied")) for mode in confinement["modes"])
    assert out["checks"]["ran"] is True and intake.verify_delivery(out, tmp_path / "out")[0]
    # the recipe, run as a person would (unconfined), reaches the same composition and the same conflict
    from scripts import compose_rehearsal
    asked = {**out["inputs"]["request"], "units": out["inputs"]["request"]["units"][:2]}
    argv = shlex.split(intake.recipe(asked))[2:] + ["--json", str(tmp_path / "by-hand.json")]
    assert compose_rehearsal.main(argv) == 1
    capsys.readouterr()
    by_hand = json.loads((tmp_path / "by-hand.json").read_text())
    assert by_hand["behavioural_conflicts"] == report["behavioural_conflicts"]
    assert by_hand["merge_order"] == ["steeper", "consumer"]


def test_the_rehearsal_module_starts_no_test_itself(repo, tmp_path):
    """Running a head's tests runs that head's code, so ``intake_rehearsal.rehearse`` has no runner of its own: the
    caller must pass one. The command line passes its unconfined one; the capability passes the confined one."""
    path, shas = repo
    with pytest.raises(TypeError, match="run"):
        intake_rehearsal.rehearse(path, shas["base"], [intake_rehearsal.Unit("label", shas["label"])], [], 30,
                                  tmp_path / "scratch")
    assert not hasattr(intake_rehearsal, "run_tests") and "import sys" not in Path(intake_rehearsal.__file__).read_text()
