"""``brief.intake``: the intake recommendation, its five words for a test, and what it never says.

Founder requirement of 2026-11-12: "Given selected open changes, produce an evidence-backed intake recommendation,
identify behavioral conflicts, prepare a reversible composition, execute the relevant checks, and explain what
remains unproven."

Every test builds the small real Git repository of ``tests/intake_fixtures.py``; the merges, exports, ancestry reads
and deliveries are real. Where a test is about what GREG does with a test outcome, ``Script`` stands in for
``greg.workers.run_tests`` and starts no process, so the test is fast and says exactly which outcome it means.
Real pytest inside the real worker envelope (or the ``supervised`` floor on a host without one), and the same
mission through a real Body, the Gate and the independent appraiser, are in
``tests/integration/test_greg_intake_mission.py``.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil

import pytest

from greg import intake, intake_rehearsal, workers
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext
from greg.templates import TEMPLATES, intake_recommendation
from tests.intake_fixtures import (PKG, REFUSED, TOTAL, Script, branch, breaks_with_steeper, build_repo, git,
                                   outcome, state)

BROKEN, SLOW = "tests/test_broken.py", "tests/test_slow.py"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """The fixture repository, built once: each test works on its own copy."""
    path = tmp_path_factory.mktemp("intake-template") / "repo"
    return path, build_repo(path)


@pytest.fixture
def repo(tmp_path, built):
    path = tmp_path / "data" / "repo"
    shutil.copytree(built[0], path, symlinks=True)
    return path, dict(built[1])


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
                     ({"units": [{"name": "a", "sha": shas["label"]}, {"name": "A", "sha": shas["steeper"]}]}, "once"),
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


def test_a_path_that_is_not_a_repository_is_a_refusal_not_an_unknown_outcome(repo, tmp_path, monkeypatch):
    """A refusal is a CapabilityError: the Gate records it and nothing is left uncertain. Before this was caught, a
    missing directory raised OSError out of the capability, which the Gate can only record as an unknown outcome."""
    path, shas = repo
    (path.parent / "plain").mkdir()
    for where in (path.parent / "plain", path.parent / "missing"):
        script = Script()
        monkeypatch.setattr(workers, "run_tests", script)
        with pytest.raises(CapabilityError, match="not a git repository|could not be carried out"):
            intake.intake_recommendation(params(where, shas, ["label"]), context(tmp_path))
        assert script.calls == [] and delivered(tmp_path) == []
        assert not (tmp_path / "workspace" / "intake-scratch").exists()


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
    cannot add a line or a heading to the recommendation. The marker's path is short whatever the temporary directory
    is: the command is cut at 240 characters, and a long path pushed "$(touch " past the cut (review of 387e8417,
    R10)."""
    path, shas = repo
    marker = Path("/tmp") / f"gi-{os.getpid()}-{tmp_path.name[-12:]}"
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


def test_a_claim_about_a_test_that_gave_no_result_here_was_not_re_executed(repo, tmp_path, monkeypatch):
    """``slow``'s author claims its test passes. Here it timed out: that neither confirms nor contradicts the claim,
    so the claim is "claimed, not re-executed here", never "DIFFERENT result"."""
    path, shas = repo
    claims = {"slow": {"head_sha": shas["slow"], "validation": [
        {"command": "pytest tests/test_slow.py", "result": "pass", "evidence": "local"}]}}
    out = run(tmp_path, path, shas, ["slow"], Script({SLOW: "timeout"}), monkeypatch, claims=claims)
    lines = section(Path(out["path"]).read_text(), "5. Claims matched to executed evidence")
    assert '- **slow**: "pytest tests/test_slow.py" (claimed: pass): **claimed, not re-executed here** (its tests ' \
           "were not among those run and measured here: tests/test_slow.py)." in lines
    assert "DIFFERENT" not in lines and out["recommendations"]["slow"].startswith("not checked: ")


def test_a_unit_left_out_for_a_textual_conflict_was_not_tested_in_the_merge_and_is_held(repo, tmp_path, monkeypatch):
    path, shas = repo
    out = run(tmp_path, path, shas, ["steeper", "flat"], Script(), monkeypatch)
    assert out["inputs"]["rehearsal"]["textual_conflicts"] == {"flat": ["pkg.py", "tests/test_base.py"]}
    assert out["recommendations"] == {      # which of the two is left out depends on the order: steeper says so too
        "steeper": "ready to take (in the listed order; flat, listed after it, conflicts with it textually and is held)",
        "flat": "hold: textual conflict with what was merged before it, in pkg.py, tests/test_base.py"}
    text = Path(out["path"]).read_text()
    assert "| flat | `tests/test_base.py` | passed | not run (the unit was left out of the merge for a textual " \
           "conflict) |" in text
    assert out["counts"]["test_runs"] == {"passed": 3, "failed": 0, "timed_out": 0, "not_run": 1, "errored": 0}


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
    return out, Path(out["path"]).read_text(), shas, before == state(path), path


def test_each_case_lands_in_its_section_with_its_word(full):
    out, text, shas, untouched, _ = full
    assert untouched, "the rehearsal changed the repository it reads"
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
    assert "- **flat** was left out of the merged tree: it conflicts with what was merged before it (directly with " \
           "steeper; which of them is left out depends on the listed order) in `pkg.py`, `tests/test_base.py`" in textual
    assert "Merged, in this order: steeper, consumer, label2, label, broken, slow, old." in textual
    # (d) the behavioural conflict a clean merge does not reveal: the test, whose test it is, and the named cause
    behavioural = section(text, "4. Behavioural conflicts a clean merge does not reveal")
    assert "- `tests/test_total.py::test_total`, a test of **consumer**: passes on its own head, fails on the merged " \
           "tree. Cause: **steeper**; passes when this head is left out." in behavioural
    assert "Failing on their own head before the merge, inside the test envelope (not a composition problem, and not " \
           "separated from the confinement: run them outside it before reading them as defects):\n" \
           "- `tests/test_broken.py::test_never_passed` " \
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
    assert got["broken"] == "hold: a check failed for this revision"      # its lint failed for this exact head;
    assert next(u for u in intake.assess(out["inputs"])["units"] if u["name"] == "broken")["not_checked"][0].startswith(             # its own-head failure is not the reason
        "its own test fails on its own head inside the test envelope (tests/test_broken.py)")
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
    assert "- **broken** also: its own test fails on its own head inside the test envelope " \
           "(tests/test_broken.py); a failure there is not separated from the confinement" in summary
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
    assert out["recommendations"]["broken"].startswith("not checked: its own test fails on its own head inside")


def test_a_cause_is_named_only_from_a_rerun_that_gave_a_result(repo, tmp_path, monkeypatch):
    """Leaving ``steeper`` out, the rerun times out. A timeout is not "passes when this head is left out": no cause
    is named, the note says why, and ``steeper`` is not put on hold for something nobody measured. Nor is it ready:
    a timeout establishes neither its part nor its innocence, so it is not checked (review of 387e8417: no head may
    read ready while a measured failure has not ruled it out)."""
    path, shas = repo

    def total(tree):
        return "timeout" if tree == "without-steeper" else breaks_with_steeper(tree)
    out = run(tmp_path, path, shas, ["steeper", "consumer", "label"], Script({TOTAL: total}), monkeypatch)
    [conflict] = out["inputs"]["rehearsal"]["behavioural_conflicts"]
    assert conflict["caused_by"] == [] and conflict["not_measured_without"] == ["steeper"]
    assert conflict["note"] == "the cause was not found: the test gave no result with steeper left out"
    assert out["recommendations"]["steeper"] == (
        "not checked: consumer's test tests/test_total.py::test_total fails on the merged tree, and the search for its "
        "cause gave no result with this head left out")
    assert out["recommendations"]["label"] == "ready to take"           # measured: the test still fails without it
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


def test_a_file_from_another_renderer_is_not_judged_but_sent_back_for_a_fresh_recommendation(repo, tmp_path,
                                                                                               monkeypatch):
    """A receipt whose inputs name another renderer cannot be re-derived by this one. Re-rendering it with today's
    rules would refute a file that was true when written (or certify one by rules it was not written under); the
    appraiser says it is stale and that a fresh recommendation is needed."""
    path, shas = repo
    out = run(tmp_path, path, shas, ["steeper", "consumer"], Script({TOTAL: breaks_with_steeper}), monkeypatch)
    old = json.loads(json.dumps(out))
    old["inputs"]["renderer"] = "greg.intake.render/1"
    old["inputs_digest"] = intake.digest(old["inputs"])
    ok, why = intake.verify_delivery(old, tmp_path / "out")
    assert ok is False and why == ("rendered by greg.intake.render/1; this appraiser renders greg.intake.render/4: the "
                                   "file is not re-derivable here, so a fresh recommendation is needed, not a verdict "
                                   "on it")
    assert intake.verify_delivery(out, tmp_path / "out")[0] is True


def test_a_test_failing_on_its_own_head_in_the_envelope_never_holds_and_never_readies_the_unit(repo, tmp_path,
                                                                                            monkeypatch):
    """2026-11-12, twelve real heads: five units were held "its own test fails on its own head" and every one of those
    files passed on its own head outside the envelope (a denied localhost socket; a temporary directory inside the
    tree). A failure on the head's own tree is not separated from the confinement: not checked, never held as the
    head's defect, never ready. A behavioural conflict, measured as a difference inside one envelope, still holds."""
    path, shas = repo
    script = Script({BROKEN: lambda tree: ("fail", ["test_never_passed"]), TOTAL: breaks_with_steeper})
    out = run(tmp_path, path, shas, ["steeper", "consumer", "broken"], script, monkeypatch)
    got = out["recommendations"]
    assert got["broken"].startswith("not checked: its own test fails on its own head inside the test envelope")
    assert got["consumer"].startswith("hold: behavioural conflict") and got["steeper"].startswith("hold: behavioural")
    text = Path(out["path"]).read_text()
    assert "not separated from the confinement" in section(text, "8. What remains unproven")
    assert "even to localhost" in section(text, "8. What remains unproven")


def test_a_second_delivery_never_overwrites_the_first(repo, tmp_path, monkeypatch):
    path, shas = repo
    first = run(tmp_path, path, shas, ["label"], Script(), monkeypatch)
    again = run(tmp_path, path, shas, ["label"], Script(), monkeypatch)             # the same result: the same file
    other = run(tmp_path, path, shas, ["consumer"], Script(), monkeypatch)
    assert first["path"] == again["path"] and first["sha256"] == again["sha256"]
    assert Path(other["path"]).name == Path(first["path"]).name.replace(".md", "-2.md")
    assert len(delivered(tmp_path)) == 2 and intake.verify_delivery(first, tmp_path / "out")[0]
    assert Path(other["twin"]).name == Path(other["path"]).name.replace(".md", ".json")


def status(tmp_path, digest, *, ledger=None, **more) -> dict:
    ctx = InvocationContext(workspace=tmp_path / "workspace", read_roots=(), secrets=None,
                            manifest=BUILTINS["brief.intake_status"][0], deliver_root=tmp_path / "out", journal=ledger)
    return intake.intake_status({"request_digest": digest, **more}, ctx)


def test_the_sensor_counts_only_an_intact_recent_recommendation_for_exactly_this_request(repo, tmp_path, monkeypatch):
    path, shas = repo
    receipts, receipted = [], [0.0]

    def status(tmp_path, digest, **more):                    # every delivery below was receipted, as the Gate does
        return globals()["status"](tmp_path, digest, ledger=Ledger(receipts, hours_ago=receipted[0]), **more)
    mine = intake.request_digest(params(path, shas, ["label"]))
    assert status(tmp_path, mine) == {"kind": "intake", "request_digest": mine, "matching": 0, "for_other_requests": 0,
                                      "too_old": 0, "unusable": 0, "not_delivered_by_greg": 0, "latest": None,
                                      "age_hours": None}
    other = run(tmp_path, path, shas, ["consumer"], Script(), monkeypatch)        # a recommendation about other heads
    receipts.append(other)
    assert status(tmp_path, mine)["matching"] == 0 and status(tmp_path, mine)["for_other_requests"] == 1
    assert status(tmp_path, other["request_digest"])["matching"] == 1
    out = run(tmp_path, path, shas, ["label"], Script(), monkeypatch)
    receipts.append(out)
    seen = status(tmp_path, mine)
    assert seen["matching"] == 1 and seen["latest"] == Path(out["path"]).name and seen["sha256"] == out["sha256"]
    assert seen["for_other_requests"] == 1
    # the same heads with another timeout, or other claims, are another request
    assert status(tmp_path, intake.request_digest(params(path, shas, ["label"], timeout_seconds=9)))["matching"] == 0
    # too old: by its receipt's time on the ledger, which a touch of the file does not change (review of 387e8417, R9)
    md, twin = Path(out["path"]), Path(out["twin"])
    receipted[0] = 49
    os.utime(md, None)
    assert status(tmp_path, mine)["matching"] == 0 and status(tmp_path, mine)["too_old"] == 1
    assert status(tmp_path, mine, max_age_hours=72)["matching"] == 1
    receipted[0] = 0
    old = md.stat().st_mtime - 49 * 3600                     # and an old file under a recent receipt is recent
    os.utime(md, (old, old))
    assert status(tmp_path, mine)["matching"] == 1 and status(tmp_path, mine)["too_old"] == 0
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
    assert f"Composed tree id: `{out['inputs']['composed_tree']}`" in text
    named = intake.request({**params(path, shas, ["label"]),
                            "units": [{"name": "label", "sha": shas["label"], "tests": ["tests/test_base.py"]}]})
    assert "--tests label=tests/test_base.py" in intake.recipe(named)


def test_the_rehearsal_module_starts_no_test_itself(repo, tmp_path):
    """Running a head's tests runs that head's code, so ``intake_rehearsal.rehearse`` has no runner of its own: the
    caller must pass one. The command line passes its unconfined one; the capability passes the confined one."""
    path, shas = repo
    with pytest.raises(TypeError, match="run"):
        intake_rehearsal.rehearse(path, shas["base"], [intake_rehearsal.Unit("label", shas["label"])], [], 30,
                                  tmp_path / "scratch")
    assert not hasattr(intake_rehearsal, "run_tests") and "import sys" not in Path(intake_rehearsal.__file__).read_text()


# -- the independent review of 885b7b7a (2026-11-12): each finding, pinned -------------------------------------------

class Ledger:
    """What the sensor is handed: a read-only view of the canonical ledger (``greg.ventures.LedgerReader`` has the
    same shape). ``outputs`` are what ``brief.intake`` returned, each kept under a Gate witness and receipt, as the
    Consequence Gate writes them; ``other`` are receipts of another capability."""

    def __init__(self, outputs=(), *, other=(), hours_ago=0.0, result_class="positive"):
        from datetime import timedelta
        from types import SimpleNamespace as Record
        from greg import briefs
        when = (briefs.NOW() - timedelta(hours=hours_ago)).isoformat().replace("+00:00", "Z")
        self.records = {"witness": [], "receipt": []}
        for index, (capability, output) in enumerate([("brief.intake", o) for o in outputs]
                                                     + [("fs.read", o) for o in other]):
            self.records["witness"].append(Record(payload={"witness_id": f"w{index}", "capability": capability},
                                                  ts_utc=when))
            self.records["receipt"].append(Record(payload={"witness_id": f"w{index}", "result": {
                "result_class": result_class, "output": output}}, ts_utc=when))
        self.ledger = self

    def by_type(self, record_type):
        return list(self.records.get(record_type, []))


def test_a_pair_in_the_delivery_folder_that_greg_did_not_deliver_closes_nothing(repo, tmp_path, monkeypatch):
    """F4. A hand-written Markdown file and twin, planted before the mission arrived, closed it ACHIEVED and the
    appraiser VERIFIED it, with no action. The sensor now counts only a recommendation that GREG delivered under a
    Gate receipt (``brief.intake``'s witness on the canonical ledger) and that is still exactly what that receipt
    renders (the appraiser's own ``verify_delivery``). A copy re-derivable byte for byte but not receipted is not
    GREG's delivery; without the ledger the sensor refuses rather than guess."""
    path, shas = repo
    out = run(tmp_path, path, shas, ["label"], Script(), monkeypatch)
    mine = out["request_digest"]
    folder = tmp_path / "out" / "briefs"
    md, twin = Path(out["path"]), Path(out["twin"])
    # the probe's pair: a Markdown file and a twin naming this request, with no inputs
    planted = folder / "2026-01-01-intake-brief.md"
    planted.write_text("# Intake recommendation\n\n| label | ready to take |\n")
    planted.with_suffix(".json").write_text(json.dumps({
        "markdown": planted.name, "markdown_sha256": hashlib.sha256(planted.read_bytes()).hexdigest(),
        "request": out["inputs"]["request"], "request_digest": mine}))
    # a re-derivable copy under another name: every byte is what the receipt's inputs render, and GREG wrote none
    copy = folder / "2026-01-02-intake-brief.md"
    copy.write_bytes(md.read_bytes())
    copy.with_suffix(".json").write_bytes(intake.twin_bytes(out["inputs"], md.read_text(), copy.name))
    seen = status(tmp_path, mine, ledger=Ledger())
    assert seen["matching"] == 0 and seen["latest"] is None
    assert seen["not_delivered_by_greg"] == 3                    # the planted pair, the copy and GREG's own (unreceipted)
    # a receipt of another capability with the same output shape is not a delivery of this one
    assert status(tmp_path, mine, ledger=Ledger(other=[out]))["matching"] == 0
    seen = status(tmp_path, mine, ledger=Ledger([out]))
    assert seen["matching"] == 1 and seen["latest"] == md.name and seen["not_delivered_by_greg"] == 2
    # the receipted file, edited after delivery: no longer what its receipt renders
    md.write_text(md.read_text() + "\nall good\n")
    twin.write_bytes(intake.twin_bytes(out["inputs"], md.read_text(), md.name))   # even with a matching twin
    seen = status(tmp_path, mine, ledger=Ledger([out]))
    assert seen["matching"] == 0 and seen["unusable"] == 1
    with pytest.raises(CapabilityError, match="canonical ledger"):
        status(tmp_path, mine)


def test_the_engine_and_the_appraiser_hand_the_sensor_a_ledger_it_cannot_write(tmp_path):
    from greg import appraisal, missions
    source = Path(missions.__file__).read_text()
    assert '"brief.intake_status"' in source.split("def _context", 1)[1].split("def ", 1)[0]
    assert "brief.intake_status" in Path(appraisal.__file__).read_text().split("cap in REOBSERVABLE", 1)[1][:2000]


def test_a_renamed_copied_or_retyped_test_file_is_run_by_both_callers(repo, tmp_path, monkeypatch):
    """F5. ``--diff-filter=AM`` with git's rename detection on dropped a renamed-and-edited test file: neither run nor
    listed. The listing turns rename and copy detection off, so a renamed or copied file is an added one, and takes a
    type change too. The command line reads the same function."""
    path, shas = repo
    big = "import pkg\n\n" + "".join(f"\ndef test_p{i}():\n    assert pkg.price({i}) == {2 * i}\n" for i in range(30))
    (path / "tests" / "test_base.py").write_text(big)
    git(path, "add", "-A")
    git(path, "commit", "-qm", "prep")
    shas["base"] = git(path, "rev-parse", "HEAD")
    git(path, "config", "diff.renames", "copies")                    # a person's configuration, the command line's git
    git(path, "checkout", "-q", "-b", "mover")
    git(path, "mv", "tests/test_base.py", "tests/test_pricing.py")
    (path / "tests" / "test_pricing.py").write_text(big.replace("== 4", "== 5"))
    (path / "tests" / "test_copied.py").write_text(big)
    (path / "tests" / "real.py").write_text("def test_r():\n    assert True\n")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "mover")
    shas["mover"] = git(path, "rev-parse", "HEAD")
    git(path, "checkout", "-q", "-b", "retyped", shas["base"])
    (path / "tests" / "test_base.py").unlink()
    os.symlink("real.py", path / "tests" / "test_base.py")
    (path / "tests" / "real.py").write_text("def test_r():\n    assert True\n")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "retyped")
    shas["retyped"] = git(path, "rev-parse", "HEAD")
    git(path, "checkout", "-q", "base")
    assert "R" in git(path, "diff", "--name-status", shas["base"], shas["mover"])     # git itself calls it a rename
    assert intake_rehearsal.changed_tests(path, shas["base"], shas["mover"]) == ["tests/test_copied.py",
                                                                                 "tests/test_pricing.py"]
    assert intake_rehearsal.changed_tests(path, shas["base"], shas["retyped"]) == ["tests/test_base.py"]
    script = Script()
    out = run(tmp_path, path, shas, ["mover", "retyped"], script, monkeypatch)
    assert ("own-mover", "tests/test_pricing.py", "supervised") in script.calls
    assert ("own-retyped", "tests/test_base.py", "supervised") in script.calls
    assert out["inputs"]["skipped_tests"] == {"mover": [], "retyped": []}


def test_git_reads_only_the_named_repository_inside_the_read_roots(tmp_path, monkeypatch):
    """F6. The path was inside the read roots, and git read a repository outside them: by searching upward from a
    plain directory, through a ``.git`` file, or through an alternate object store. Each is refused, and a linked
    worktree whose repository is inside the roots still works."""
    outer = tmp_path / "outside" / "repo"
    shas = build_repo(outer)
    monkeypatch.setattr(workers, "run_tests", Script())
    granted = outer / "granted"
    granted.mkdir()
    cases = {"a plain directory inside a repository": (granted, granted)}
    pointer = tmp_path / "b" / "repo"
    pointer.mkdir(parents=True)
    (pointer / ".git").write_text(f"gitdir: {outer / '.git'}\n")
    cases["a .git file pointing outside"] = (pointer, pointer.parent)
    alternate = tmp_path / "c" / "repo"
    alternate.mkdir(parents=True)
    git(alternate, "init", "-q")
    (alternate / ".git" / "objects" / "info" / "alternates").write_text(str(outer / ".git" / "objects") + "\n")
    cases["an alternate object store outside"] = (alternate, alternate.parent)
    included = tmp_path / "d" / "repo"
    shutil.copytree(outer, included, symlinks=True)
    git(included, "config", "include.path", str(tmp_path / "elsewhere.cfg"))
    cases["a configuration include"] = (included, included.parent)
    for why, (where, root) in cases.items():
        ctx = context(tmp_path / why.replace(" ", "-"), read_root=root)
        with pytest.raises(CapabilityError, match="outside the read roots|not a git repository|includes"):
            intake.intake_recommendation(params(where, shas, ["label"]), ctx)
    linked = tmp_path / "e"
    shutil.copytree(outer, linked / "repo", symlinks=True)
    git(linked / "repo", "worktree", "add", "-q", str(linked / "tree"), shas["label"])
    out = intake.intake_recommendation(params(linked / "tree", shas, ["label"]), context(tmp_path / "e-ctx",
                                                                                        read_root=linked))
    assert out["recommendations"] == {"label": "ready to take"}


def test_a_head_that_contains_a_held_head_is_held_too(repo, tmp_path, monkeypatch):
    """F7. ``label2`` contains ``label``. With ``label`` held, ``label2`` was "take after label": taking it takes
    ``label``'s held code. It inherits the hold, and says from which head."""
    path, shas = repo
    claims = {"label": {"head_sha": shas["label"],
                        "checks": [{"name": "ci", "head_sha": shas["label"], "conclusion": "failure"}]}}
    out = run(tmp_path, path, shas, ["label", "label2"], Script(), monkeypatch, claims=claims)
    assert out["recommendations"]["label"] == "hold: a check failed for this revision"
    assert out["recommendations"]["label2"] == ("hold: it contains label, which is held (a check failed for this "
                                                "revision); taking it takes that code")


def test_a_stop_during_the_last_run_delivers_nothing(repo, tmp_path, monkeypatch):
    """F8. STOP pressed while the merged tree's test ran: the run ended "refused", nothing checked STOP afterwards,
    and the recommendation was delivered with that file "refused before it ran"."""
    path, shas = repo
    stopped = []

    def run_tests(tests, cwd, *, timeout, stop_check=None, confinement="required"):
        if Path(cwd).name == "composed":
            stopped.append(True)
            return [{**outcome("refused", tests[0][-1], timeout),
                     "tail": "acceptance confinement refused: stop requested; worker and its process namespace "
                             "terminated"}]
        return [outcome("pass", tests[0][-1], timeout)]
    monkeypatch.setattr(workers, "run_tests", run_tests)
    with pytest.raises(CapabilityError, match="stop requested"):
        intake.intake_recommendation(params(path, shas, ["label"]),
                                     context(tmp_path, stop_check=lambda: bool(stopped), read_root=path.parent))
    assert stopped and delivered(tmp_path) == []


@pytest.mark.parametrize("tail, word, why", [
    ("acceptance confinement refused: stop requested; worker and its process namespace terminated", "not run",
     "interrupted by a stop request; no result"),
    ("acceptance confinement refused: worker exceeded the bounded stdout/stderr ceiling and was stopped", "errored",
     "stopped when its output passed the output ceiling; no result was read")])
def test_a_run_that_started_is_never_called_refused_before_it_ran(tail, word, why):
    """F8. Both of these ran, inside the envelope or the supervised floor, and were stopped: neither is "envelope
    unavailable" nor "refused before it ran"."""
    result = {**outcome("refused", "tests/test_x.py", 30), "tail": tail}
    for host in (True, False):
        got, nodes, _ = intake.classify(result, "tests/test_x.py", 30, envelope=lambda: host)
        assert got == {"state": word, "measured": False, "why": why} and nodes == []


def test_a_textual_conflict_that_depends_on_the_order_is_said_on_both_units(repo, tmp_path, monkeypatch):
    """F9. ``steeper`` and ``flat`` rewrite the same line. Whichever is listed first is merged and the other is
    held; the first was "ready to take" and said nothing of it."""
    path, shas = repo
    for first, second in (("steeper", "flat"), ("flat", "steeper")):
        out = run(tmp_path / first, path, shas, [first, second], Script(), monkeypatch)
        assert out["recommendations"][first] == (f"ready to take (in the listed order; {second}, listed after it, "
                                                 "conflicts with it textually and is held)")
        assert out["recommendations"][second].startswith("hold: textual conflict with what was merged before it")
        assert out["inputs"]["rehearsal"]["textual_conflicts_with"] == {second: [first]}
        text = Path(out["path"]).read_text()
        assert f"- **{second}** was left out of the merged tree: it conflicts with what was merged before it " \
               f"(directly with {first}; which of them is left out depends on the listed order) in" \
            in section(text, "3. Textual conflicts")


def check_claims(repo, tmp_path, monkeypatch, record, name="case"):
    path, shas = repo
    out = run(tmp_path / name, path, shas, ["label"], Script(), monkeypatch, claims={"label": record})
    return out["recommendations"]["label"], intake.assess(out["inputs"])["units"][0], Path(out["path"]).read_text()


def test_check_results_are_read_per_check_name_and_in_the_words_a_hosting_service_uses(repo, tmp_path, monkeypatch):
    """F10 and F11, checks: a stale failing check is not cleared by an unrelated passing one; "in_progress",
    "queued", "pending" are running; a cancelled, skipped or neutral check is no result, and checks that gave only
    those leave the unit not checked; a check SHA that is a prefix of the unit's of at least 12 hex digits names it."""
    path, shas = repo
    label, steeper = shas["label"], shas["steeper"]
    got, _, _ = check_claims(repo, tmp_path, monkeypatch, {"checks": [
        {"name": "ci", "head_sha": steeper, "conclusion": "failure"},
        {"name": "lint", "head_sha": label, "conclusion": "success"}]}, "stale")
    assert got == "hold: stale: check ci has results only for another head"
    for word in ("in_progress", "queued", "pending", "waiting", "requested"):
        got, unit, _ = check_claims(repo, tmp_path, monkeypatch, {"checks": [
            {"name": "ci", "head_sha": label, "conclusion": word},
            {"name": "lint", "head_sha": label, "conclusion": "success"}]}, word)
        assert got == "not checked: a check is still running for this revision", word
        assert [c["status"] for c in unit["checks"]] == ["still running", "passed"]
    for words in (["skipped", "neutral"], ["cancelled"]):
        got, unit, _ = check_claims(repo, tmp_path, monkeypatch, {"checks": [
            {"name": f"c{i}", "head_sha": label, "conclusion": w} for i, w in enumerate(words)]}, words[0] + "-only")
        assert got == ("not checked: every check supplied for this revision concluded without a result ("
                       + ", ".join(words) + ")"), words
    got, _, _ = check_claims(repo, tmp_path, monkeypatch, {"checks": [
        {"name": "ci", "head_sha": label, "conclusion": "success"},
        {"name": "docs", "head_sha": label, "conclusion": "skipped"}]}, "pass-and-skip")
    assert got == "ready to take"
    got, unit, _ = check_claims(repo, tmp_path, monkeypatch, {"checks": [
        {"name": "ci", "head_sha": label[:12], "conclusion": "success"}]}, "prefix12")
    assert got == "ready to take" and unit["checks"][0]["status"] == "passed"
    got, unit, _ = check_claims(repo, tmp_path, monkeypatch, {"checks": [
        {"name": "ci", "head_sha": label[:7], "conclusion": "success"}]}, "prefix7")
    assert got == "hold: stale: check ci has results only for another head"
    assert unit["checks"][0]["detail"].startswith(f"it names head {label[:7]}, shorter than 12 hex digits")


def test_claims_are_read_in_the_words_people_write_and_a_different_result_is_never_ready(repo, tmp_path, monkeypatch):
    """F10 and F11, claims: "success" and "1 passed" are a pass; a claim this run contradicts keeps the unit from
    ready and is listed in section 8; a claim SHA that is a 12-digit prefix of the unit's names it."""
    path, shas = repo
    label = shas["label"]
    for i, (said, head) in enumerate((("success", label), ("1 passed", label), ("3 passed in 0.2s", label),
                                      ("PASSED", label[:12]))):
        got, unit, _ = check_claims(repo, tmp_path, monkeypatch, {"head_sha": head, "validation": [
            {"command": "pytest tests/test_shout.py", "result": said}]}, f"said{i}")
        assert unit["claims"][0]["status"] == "re-executed here: same result", said
        assert got == "ready to take"
    got, unit, text = check_claims(repo, tmp_path, monkeypatch, {"head_sha": label, "validation": [
        {"command": "pytest tests/test_shout.py", "result": "fail"}]}, "different")
    assert unit["claims"][0]["status"] == "re-executed here: DIFFERENT result"
    assert got == "not checked: a claim's result differs from what ran here: \"pytest tests/test_shout.py\" " \
                  "(claimed fail; here pass)"
    assert '- **label**: re-executed here: DIFFERENT result: "pytest tests/test_shout.py"' in \
        section(text, "8. What remains unproven")
    got, unit, _ = check_claims(repo, tmp_path, monkeypatch, {"head_sha": label, "validation": [
        {"command": "pytest tests/test_shout.py", "result": "flaky"}]}, "unreadable")
    assert unit["claims"][0]["status"] == "claimed result is not a pass or a fail"
    assert got.startswith("not checked: a claim's result differs from what ran here")
    got, unit, _ = check_claims(repo, tmp_path, monkeypatch, {"validation": [
        {"command": "pytest tests/test_shout.py", "result": "pass"}]}, "nohead")
    assert unit["claims"][0]["status"] == "stale: the claim names no head; this unit is " + label
    assert got == "hold: stale: its claims name another head or none"


def test_a_failure_whose_failing_tests_are_not_named_leaves_the_unit_not_checked(repo, tmp_path, monkeypatch):
    """F13 survivor k: a failure on the merged tree whose failing tests the kept output does not name is a failure,
    not a whole measurement: no conflict can be named from it, and the unit is not ready."""
    path, shas = repo

    def run_tests(tests, cwd, *, timeout, stop_check=None, confinement="required"):
        file = tests[0][-1]
        if Path(cwd).name == "composed":
            return [{**outcome("pass", file, timeout), "returncode": 1, "passed": False,
                     "tail": "...output cut...\n2 failed, 1 passed in 0.1s\n"}]
        return [outcome("pass", file, timeout)]
    monkeypatch.setattr(workers, "run_tests", run_tests)
    out = intake.intake_recommendation(params(path, shas, ["label"]), context(tmp_path, read_root=path.parent))
    assert out["inputs"]["rehearsal"]["behavioural_conflicts"] == []
    assert out["recommendations"]["label"] == ("not checked: tests/test_shout.py failed on the merged tree (2 failing, "
                                               "0 named in the kept output)")


def test_check_results_only_for_another_head_hold_the_unit(repo, tmp_path, monkeypatch):
    """F13 survivor o."""
    path, shas = repo
    got, unit, _ = check_claims(repo, tmp_path, monkeypatch, {"checks": [
        {"name": "ci", "head_sha": shas["steeper"], "conclusion": "success"}]})
    assert got == "hold: stale: check ci has results only for another head"
    assert unit["checks"][0]["status"] == "result is for another head (stale)"


def test_a_twin_already_there_with_other_bytes_is_never_overwritten(repo, tmp_path, monkeypatch):
    """F13 survivor q."""
    path, shas = repo
    folder = tmp_path / "out" / "briefs"
    folder.mkdir(parents=True)
    from greg import briefs
    there = folder / f"{briefs.NOW().date().isoformat()}-intake-brief.json"
    there.write_text("not this recommendation's twin\n")
    with pytest.raises(CapabilityError, match="already exists with different content; nothing was overwritten"):
        run(tmp_path, path, shas, ["label"], Script(), monkeypatch)
    assert there.read_text() == "not this recommendation's twin\n"


def test_an_earlier_attempts_scratch_is_removed_before_the_rehearsal(repo, tmp_path, monkeypatch):
    """F13 survivor n: what a killed process leaves in the mission's scratch never blocks or joins a new attempt."""
    path, shas = repo
    leftover = tmp_path / "workspace" / "intake-scratch" / "trees" / "own-label" / "half.py"
    leftover.parent.mkdir(parents=True)
    leftover.write_text("raise SystemExit('never run')\n")
    out = run(tmp_path, path, shas, ["label"], Script(), monkeypatch)
    assert out["recommendations"] == {"label": "ready to take"} and not leftover.exists()


def test_a_file_whose_every_test_was_deselected_was_not_run():
    """F14."""
    file = "tests/test_x.py"
    result = {**outcome("pass", file, 30), "returncode": 5, "passed": False, "tail": "\n3 deselected in 0.01s\n"}
    got, _, _ = intake.classify(result, file, 30)
    assert got == {"state": "not run", "measured": False, "why": "no test in the file ran to a result: 3 deselected "
                                                                 "in 0.01s"}


def test_the_composed_tree_is_named_as_an_identity_not_as_something_to_fetch(repo, tmp_path, monkeypatch):
    """F15. The merge's objects live in the mission's scratch and are removed with it."""
    path, shas = repo
    out = run(tmp_path, path, shas, ["steeper", "consumer"], Script({TOTAL: breaks_with_steeper}), monkeypatch)
    text = section(Path(out["path"]).read_text(), "7. Reproducible recipe")
    tree = out["inputs"]["composed_tree"]
    assert f"Composed tree id: `{tree}`. Its objects were written only to the mission's scratch, which was removed: " \
           "nothing in the repository holds them, so it cannot be fetched." in text
    with pytest.raises(Exception):
        git(path, "cat-file", "-e", tree)


def test_keeping_both_sides_works_inside_the_missions_scratch(repo, tmp_path, monkeypatch):
    """F17. The scratch index of a keep-both-sides resolution was made in the process's temporary directory."""
    path, shas = repo
    (path / "steps.txt").write_text("step base\n")
    git(path, "add", ".")
    git(path, "commit", "-qm", "steps")
    shas = {**shas, "base": git(path, "rev-parse", "HEAD")}
    for name in ("alpha", "beta"):
        shas[name] = branch(path, name, {"steps.txt": f"step base\nstep {name}\n"})
    git(path, "checkout", "-q", "base")
    made, real = [], intake_rehearsal.tempfile.TemporaryDirectory

    def spy(*args, **kwargs):
        made.append(kwargs.get("dir"))
        return real(*args, **kwargs)
    monkeypatch.setattr(intake_rehearsal.tempfile, "TemporaryDirectory", spy)
    out = run(tmp_path, path, shas, ["alpha", "beta"], Script(), monkeypatch, union=["steps.txt"])
    assert out["inputs"]["rehearsal"]["kept_both_sides"] == {"beta": ["steps.txt"]}
    assert made and all(d is not None and (tmp_path / "workspace") in Path(d).parents for d in made)


def test_one_invocation_has_a_time_budget_across_all_its_files(repo, tmp_path, monkeypatch):
    """F3 (the ceiling only). Each file's timeout bounded one file; a selection of many files could hold the body's
    turn for hours. One invocation now has a budget across every file it runs; a file that would start after it is
    spent is not run, and says why."""
    path, shas = repo
    now = [0.0]
    monkeypatch.setattr(intake, "_monotonic", lambda: now[0])
    monkeypatch.setattr(intake, "MAX_INVOCATION_SECONDS", 100)
    seen = []

    def run_tests(tests, cwd, *, timeout, stop_check=None, confinement="required"):
        seen.append(timeout)
        now[0] += 60
        return [outcome("pass", tests[0][-1], timeout)]
    monkeypatch.setattr(workers, "run_tests", run_tests)
    out = intake.intake_recommendation(params(path, shas, ["label", "consumer"], timeout_seconds=90),
                                       context(tmp_path, read_root=path.parent))
    assert seen == [90, 40]                     # the second file gets what is left of the budget, never more
    assert out["recommendations"]["label"] == "not checked: tests/test_shout.py not run on the merged tree (the " \
                                              "invocation's time budget of 100s was spent before it started)"


def test_a_test_file_the_merged_tree_holds_in_another_heads_version_is_not_compared(repo, tmp_path, monkeypatch):
    """F18, two real runs on 2026-11-12: with a head (303-old) and its own descendant (303) in one selection, the
    merged tree held the descendant's version of their shared test file, so 303-old's own test never met 304, and
    303-old read "ready to take"; without the descendant the conflict with 304 showed. Here ``old`` asserts the old
    price, its descendant ``newer`` relaxes that same test, and ``steeper`` changes the price. The merged-tree result
    for ``old``'s file is not a measurement of ``old``: not run, naming whose version ran, and ``old`` is not checked.
    """
    path, shas = repo
    rule = "tests/test_rule.py"
    shas["old"] = branch(path, "old-rule", {rule: "import pkg\n\n\ndef test_rule():\n    assert pkg.price(2) == 4\n"})
    shas["newer"] = branch(path, "newer-rule", {rule: "import pkg\n\n\ndef test_rule():\n    assert pkg.price(2) in "
                                                      "(4, 6)\n"}, start="old-rule")
    git(path, "checkout", "-q", "base")
    out = run(tmp_path, path, shas, ["steeper", "old", "newer"], Script(), monkeypatch)
    why = "the merged tree holds newer's version of this file, not old's: its own version was not run against the merge"
    assert out["recommendations"]["old"] == f"not checked: {rule} not run on the merged tree ({why})"
    assert out["inputs"]["rehearsal"]["not_compared"] == [{"unit": "old", "file": rule, "note": why}]
    assert out["recommendations"]["newer"] == "take after old"
    assert f"- `{rule}` (from old): {why}" in intake_rehearsal.markdown(out["inputs"]["rehearsal"])


def test_a_failure_in_another_heads_version_of_a_file_is_compared_under_a_head_that_runs_it(repo, tmp_path,
                                                                                            monkeypatch):
    """F18 kept, without silence. When the merged tree holds exactly ``newer``'s version of ``old``'s test file, the
    result there is not ``old``'s, and is compared under ``newer``, which runs that file. When ``newer`` runs other
    files (its tests named in the mission), nobody would compare it: the file then counts as merged from several
    versions, and a failure in it is a conflict that holds both."""
    path, shas = repo
    rule = "tests/test_rule.py"
    shas["old"] = branch(path, "old-rule", {rule: "import pkg\n\n\ndef test_rule():\n    assert pkg.price(2) == 4\n"})
    shas["newer"] = branch(path, "newer-rule", {rule: "import pkg\n\n\ndef test_rule():\n    assert pkg.price(2) in "
                                                      "(4, 5)\n"}, start="old-rule")
    git(path, "checkout", "-q", "base")
    fails = Script({rule: lambda tree: ("fail", ["test_rule"]) if tree in ("composed", "without-old") else "pass"})
    out = run(tmp_path / "runs", path, shas, ["steeper", "old", "newer"], fails, monkeypatch)
    report = out["inputs"]["rehearsal"]
    assert [(c["unit"], c.get("shared_with")) for c in report["behavioural_conflicts"]] == [("newer", None)]
    assert out["recommendations"]["newer"].startswith("hold: behavioural conflict: its test tests/test_rule.py")
    assert out["recommendations"]["old"].startswith("not checked: tests/test_rule.py not run on the merged tree")
    assert_a_measured_failure_is_never_silence(out)
    named = {**params(path, shas, ["steeper", "old"]), "units": [
        {"name": "steeper", "sha": shas["steeper"]}, {"name": "old", "sha": shas["old"]},
        {"name": "newer", "sha": shas["newer"], "tests": ["tests/test_shout.py"]}]}
    monkeypatch.setattr(workers, "run_tests", fails)
    out = intake.intake_recommendation(named, context(tmp_path / "named", read_root=path.parent))
    report = out["inputs"]["rehearsal"]
    assert report["not_compared"] == []
    assert [(c["unit"], c["shared_with"]) for c in report["behavioural_conflicts"]] == [("old", ["newer"])]
    assert out["recommendations"]["newer"] == ("hold: behavioural conflict: tests/test_rule.py::test_rule fails on the "
                                               "merged tree, in tests/test_rule.py, which it edited too; whose test it "
                                               "is was not separated")
    assert_a_measured_failure_is_never_silence(out)


# -- the second independent review of 387e8417 (2026-11-12): each finding, pinned -----------------------------------

SHARED = "tests/test_shared.py"
FILLER = "".join(f"\n\ndef test_filler_{i}():\n    assert pkg.label({i}) == 'item-{i}'\n" for i in range(6))
STEEP = PKG.replace("n * 2", "n * 3")
TEST_A = "\n\ndef test_a():\n    assert pkg.price(2) == 4\n"


def shared_file(path, shas) -> dict:
    """The base gains one test file that several heads add tests to (R1's and R2's selections)."""
    git(path, "checkout", "-q", "base")
    (path / SHARED).write_text("import pkg\n" + FILLER)
    git(path, "add", ".")
    git(path, "commit", "-qm", "a shared test file")
    return {**shas, "base": git(path, "rev-parse", "HEAD")}


def implicated(report) -> set:
    """Every head a measured behavioural conflict implicates: the head whose test it is (each head whose edits the
    merged test file holds, where that is not separated), each head named as its cause, and each head with which the
    cause search gave no result."""
    names = set()
    for conflict in report["behavioural_conflicts"]:
        names |= {conflict["unit"], *conflict["caused_by"], *conflict.get("shared_with", ()),
                  *conflict.get("not_measured_without", ())}
    return names - {intake_rehearsal.ON_BASE, "(also)"}


def assert_a_measured_failure_is_never_silence(out) -> None:
    """The invariant: a failure measured on the merged tree is a conflict, no head it implicates reads ready or take
    after, and the recommendation never says that none was measured."""
    report = out["inputs"]["rehearsal"]
    assert report["behavioural_conflicts"] and report["clean"] is False
    for name in implicated(report):
        assert out["recommendations"][name].startswith(("hold: ", "not checked: ")), (name, out["recommendations"])
    assert "None was measured in the tests that ran." not in Path(out["path"]).read_text()


def test_a_failure_in_a_test_file_several_heads_edited_is_measured_and_holds_every_head_it_implicates(
        repo, tmp_path, monkeypatch):
    """R1. ``a`` appends a test that relies on today's price to a shared test file, ``c`` adds a test at the top of the
    same file, ``b`` changes the price. The merged tree holds that file merged from ``a``'s and ``c``'s versions;
    ``a``'s test passes on its own head and fails there. F18 dropped the measured failure (the file was not byte for
    byte either head's): ``b``, which caused it, read "ready to take" and section 4 said none was measured. It is a
    behavioural conflict again; whose test it is is not separated from the file, so each head whose edits the file
    holds is held and says so, and the cause is searched among the heads that did not edit it."""
    path, shas = repo
    shas = shared_file(path, shas)
    shas["a"] = branch(path, "a-shared", {SHARED: "import pkg\n" + FILLER + TEST_A})
    shas["c"] = branch(path, "c-shared", {SHARED: "import pkg\n\n\ndef test_c():\n    assert pkg.label(0) == 'item-0'\n"
                                                  + FILLER})
    shas["b"] = branch(path, "b-price", {"pkg.py": STEEP,
                                         "tests/test_b.py": "import pkg\n\n\ndef test_b():\n    assert pkg.price(1) == 3\n"})
    git(path, "checkout", "-q", "base")
    script = Script({SHARED: lambda tree: ("fail", ["test_a"]) if tree in ("composed", "without-c") else "pass"})
    out = run(tmp_path, path, shas, ["a", "c", "b"], script, monkeypatch)
    report, node = out["inputs"]["rehearsal"], f"{SHARED}::test_a"
    assert [(c["test"], c["unit"], c["shared_with"], c["caused_by"]) for c in report["behavioural_conflicts"]] == [
        (node, "a", ["c"], ["b"]), (node, "c", ["a"], ["b"])]
    assert report["not_compared"] == []
    assert report["behavioural_conflicts"][0]["note"] == (
        "passes when this head is left out; the merged tree holds this file merged from a's version and the edits of "
        "c: whose test it is was not separated, and c was not left out (without a head that edited the file, the test "
        "may not be there)")
    got = out["recommendations"]
    assert got["a"] == ("hold: behavioural conflict: tests/test_shared.py::test_a fails on the merged tree and did not "
                        "fail on its own head; the merged tree holds that file merged from its version and the edits "
                        "of c, so whose test it is was not separated (cause: b)")
    assert got["c"] == ("hold: behavioural conflict: tests/test_shared.py::test_a fails on the merged tree, in "
                        "tests/test_shared.py, which it edited too; whose test it is was not separated")
    assert got["b"] == ("hold: behavioural conflict: merging it breaks tests/test_shared.py::test_a, in a file a and c "
                        "edited")
    assert_a_measured_failure_is_never_silence(out)
    # a head that edited the file is never left out to look for the cause: without it the test may not be there
    assert not [call for call in script.calls if call[0] in ("without-a", "without-c")]
    behavioural = section(Path(out["path"]).read_text(), "4. Behavioural conflicts a clean merge does not reveal")
    assert f"- `{node}`, in a test file **a** edited: did not fail on its own head, fails on the merged tree. Cause: " \
           "**b**; passes when this head is left out; the merged tree holds this file merged from a's version" \
        in behavioural


def test_a_head_behind_a_base_that_edited_its_test_file_is_still_blamed_on_the_base(repo, tmp_path, monkeypatch):
    """R2. ``behind`` adds a test to the shared file; the line then changes the price and edits the top of that file.
    One head: the merged tree holds the file merged from ``behind``'s version and the base's edit. F18 dropped the
    failure, saying "several heads' versions" of a file only the base and one head had touched, and ``behind`` went
    from hold (cause: the base) to not checked. With only a header added by the base, it is ready, as before F18."""
    path, shas = repo
    shas = shared_file(path, shas)
    shas["behind"] = branch(path, "behind-shared", {SHARED: "import pkg\n" + FILLER + TEST_A})
    for name, files in (("moved", {"pkg.py": STEEP, SHARED: "# the line moved\nimport pkg\n" + FILLER}),
                        ("header", {SHARED: "# a header only\nimport pkg\n" + FILLER})):
        line = dict(shas, base=branch(path, f"line-{name}", files))
        git(path, "checkout", "-q", "base")
        fails = Script({SHARED: lambda tree: ("fail", ["test_a"]) if tree == "composed" else "pass"})
        out = run(tmp_path / name, path, line, ["behind"], fails if name == "moved" else Script(), monkeypatch)
        report = out["inputs"]["rehearsal"]
        assert report["not_compared"] == []
        if name == "header":
            assert out["recommendations"] == {"behind": "ready to take"} and report["behavioural_conflicts"] == []
            continue
        [conflict] = report["behavioural_conflicts"]
        assert conflict["caused_by"] == ["(the base)"] and conflict["shared_with"] == ["(the base)"]
        assert conflict["note"] == ("fails as soon as this head is merged onto the base, with no other head: the line "
                                    "has moved since it branched; the merged tree holds this file merged from behind's "
                                    "version and the edits of the base")
        assert out["recommendations"]["behind"].startswith(
            "hold: behavioural conflict: tests/test_shared.py::test_a fails on the merged tree and did not fail on its "
            "own head; the merged tree holds that file merged from its version and the edits of the base")
        assert out["recommendations"]["behind"].endswith("(cause: (the base))")
        assert_a_measured_failure_is_never_silence(out)


_WATCHED: dict = {}


def _audit(event, args):
    if event == "open" and _WATCHED.get("targets") and isinstance(args[0], (str, bytes, os.PathLike)):
        try:
            if os.path.realpath(args[0]) in _WATCHED["targets"]:
                _WATCHED["seen"].append(os.fsdecode(args[0]))
        except (OSError, ValueError, TypeError):
            pass


@pytest.mark.parametrize("name", ["mem", "far", "long"])
def test_a_test_file_a_head_turned_into_a_link_is_never_followed_in_gregs_own_process(name, repo, tmp_path, monkeypatch):
    """R3. A head's test file that is a link was followed in GREG's own process, outside the envelope: F18 read both
    trees' copies, so a link to /proc/self/mem refused every recommendation in the selection as a transient fault
    (EIO), and a link to a file outside the read roots was opened and read; the runner's own look-up raised for a
    link to a name too long to resolve, again a transient refusal. Versions are compared by git's tree entries, a
    file is found with lstat, and a link is run, like any test file, only inside the envelope."""
    path, shas = repo
    outside = tmp_path / "outside" / "secret_test.py"            # outside the read root (tmp_path / "data")
    outside.parent.mkdir()
    outside.write_text("def test_secret():\n    assert True\n")
    target = {"mem": "/proc/self/mem", "far": str(outside), "long": "x" * 300}[name]
    git(path, "checkout", "-q", "-b", name, "base")
    os.symlink(target, path / "tests" / f"test_{name}.py")
    git(path, "add", "-A")
    git(path, "commit", "-qm", name)
    shas[name] = git(path, "rev-parse", "HEAD")
    git(path, "checkout", "-q", "base")
    if not _WATCHED:
        import sys
        sys.addaudithook(_audit)          # a hook cannot be removed: it records only while a test watches
    _WATCHED.update(targets={str(outside.resolve()), "/proc/self/mem"}, seen=[])
    try:
        script = Script()
        out = run(tmp_path, path, shas, ["label", name], script, monkeypatch)
        seen = list(_WATCHED["seen"])
    finally:
        _WATCHED["targets"] = None
    assert out["recommendations"] == {"label": "ready to take", name: "ready to take"}
    assert seen == []
    assert (f"own-{name}", f"tests/test_{name}.py", "supervised") in script.calls     # run, inside the envelope
    assert intake._absent(tmp_path, "tests/x/test_y.py") == "the file does not exist in this tree"


def test_only_a_passed_or_failed_result_for_this_head_makes_a_check_name_current(repo, tmp_path, monkeypatch):
    """R4. A check name counted as current for this head as soon as any row of that name named it, a cancelled one
    included: a cancelled re-run masked the stale failure of the same check, and another passing check made the unit
    ready. Only a passed or failed result for this head makes the name current."""
    path, shas = repo
    label, steeper = shas["label"], shas["steeper"]
    for word in ("cancelled", "skipped", "neutral", "stale", None, "IN_PROGRESS"):
        got, _, _ = check_claims(repo, tmp_path, monkeypatch, {"checks": [
            {"name": "ci", "head_sha": steeper, "conclusion": "failure"},
            {"name": "ci", "head_sha": label, "conclusion": word},
            {"name": "lint", "head_sha": label, "conclusion": "success"}]}, f"r4-{word}")
        assert got == "hold: stale: check ci has results only for another head", word
    # a passed or a failed result for this head is current: the other head's result no longer makes the name stale
    got, _, _ = check_claims(repo, tmp_path, monkeypatch, {"checks": [
        {"name": "ci", "head_sha": steeper, "conclusion": "failure"},
        {"name": "ci", "head_sha": label, "conclusion": "success"}]}, "r4-current-pass")
    assert got == "ready to take"
    got, _, _ = check_claims(repo, tmp_path, monkeypatch, {"checks": [
        {"name": "ci", "head_sha": steeper, "conclusion": "success"},
        {"name": "ci", "head_sha": label, "conclusion": "failure"}]}, "r4-current-fail")
    assert got == "hold: a check failed for this revision"
    _, unit, _ = check_claims(repo, tmp_path, monkeypatch, {"checks": [
        {"name": "ci", "head_sha": label, "conclusion": "Queued"}]}, "r4-case")
    assert unit["checks"][0]["status"] == "still running"            # a hosting service's word, in any letter case


def test_a_failing_check_that_names_no_head_holds_like_a_claim_that_names_none(repo, tmp_path, monkeypatch):
    """R5. A failing check with no head read as "no result": it neither held nor kept the unit from ready, and
    section 6 never said it failed. It holds now, as a claim naming no head does, and keeps the stricter rule: a pass
    of the same name for this head does not clear it, since it may be this revision's own failure."""
    path, shas = repo
    label = shas["label"]
    for i, also in enumerate(([{"name": "lint", "head_sha": label, "conclusion": "success"}],
                              [{"name": "ci", "head_sha": label, "conclusion": "success"}])):
        got, _, text = check_claims(repo, tmp_path, monkeypatch, {"checks": [
            {"name": "ci", "head_sha": "", "conclusion": "failure"}] + also}, f"r5-{i}")
        assert got == "hold: stale: check ci concluded failure and names no head"
        assert '- **label**: check "ci": **no result for this exact head** (it names no head; concluded failure).' \
            in section(text, "6. Missing or stale appraisals")
    got, _, _ = check_claims(repo, tmp_path, monkeypatch, {"checks": [            # one that did not fail: no result
        {"name": "ci", "head_sha": "", "conclusion": "success"},
        {"name": "lint", "head_sha": label, "conclusion": "success"}]}, "r5-pass")
    assert got == "ready to take"


def gc(repo: Path) -> None:
    git(repo, "-c", "gc.auto=0", "repack", "-adq")
    git(repo, "prune-packed")


LINKED = ["linked pack files", "a linked pack directory", "linked loose object directories", "a linked config",
          "a linked info/attributes", "a linked alternates listing naming a store inside", "a .git link to a file outside",
          "core.attributesFile outside", "mailmap.file outside", "an alternate store inside with linked pack files"]


def linked_case(tmp_path: Path, why: str) -> tuple[Path, dict]:
    """A repository inside the read roots (``tmp_path / "roots"``) that leads git outside them, as ``why`` says."""
    outside = tmp_path / "outside"
    outer = outside / "repo"
    shas = build_repo(outer)
    attrs = outside / "attrs"
    attrs.write_text("tests/** export-ignore\n")
    where = tmp_path / "roots" / "repo"
    if why in ("linked pack files", "a linked pack directory", "linked loose object directories",
               "a linked alternates listing naming a store inside", "an alternate store inside with linked pack files"):
        where.mkdir(parents=True)
        git(where, "init", "-q")
        objects = where / ".git" / "objects"
        if why == "an alternate store inside with linked pack files":     # the store is listed; its packs are links
            store = tmp_path / "roots" / "store.git"
            git(tmp_path / "roots", "init", "-q", "--bare", str(store))
            (objects / "info" / "alternates").write_text(f"{store / 'objects'}\n")
            objects = store / "objects"
        if why == "linked loose object directories":                    # build_repo leaves its objects loose
            for sub in (outer / ".git" / "objects").iterdir():
                if len(sub.name) == 2:
                    os.symlink(sub, objects / sub.name)
            return where, shas
        if why == "a linked alternates listing naming a store inside":
            shutil.copytree(outer / ".git" / "objects", tmp_path / "roots" / "store")
            (outside / "alternates").write_text(f"{tmp_path / 'roots' / 'store'}\n")
            os.symlink(outside / "alternates", objects / "info" / "alternates")
            return where, shas
        gc(outer)
        if why == "a linked pack directory":
            shutil.rmtree(objects / "pack")
            os.symlink(outer / ".git" / "objects" / "pack", objects / "pack")
        else:
            for pack in (outer / ".git" / "objects" / "pack").iterdir():
                os.symlink(pack, objects / "pack" / pack.name)
        return where, shas
    if why == "a .git link to a file outside":
        shutil.copytree(outer, tmp_path / "roots" / "real", symlinks=True)
        where.mkdir(parents=True)
        (outside / "dotgit").write_text(f"gitdir: {tmp_path / 'roots' / 'real' / '.git'}\n")
        os.symlink(outside / "dotgit", where / ".git")
        return where, shas
    shutil.copytree(outer, where, symlinks=True)
    if why == "a linked config":
        (where / ".git" / "config").unlink()
        os.symlink(outer / ".git" / "config", where / ".git" / "config")
    elif why == "a linked info/attributes":
        (where / ".git" / "info").mkdir(exist_ok=True)
        os.symlink(attrs, where / ".git" / "info" / "attributes")
    elif why == "core.attributesFile outside":
        git(where, "config", "core.attributesFile", str(attrs))
    else:
        git(where, "config", "mailmap.file", str(outside / "mailmap"))
    return where, shas


@pytest.mark.parametrize("why", LINKED)
def test_git_reads_nothing_a_link_in_the_repository_leads_outside_the_read_roots(why, tmp_path, monkeypatch):
    """R6. The pin checked only the git directory, a worktree's repository and the alternate stores. A pack file, the
    pack directory or a loose object directory linked from outside was read (a commit that exists only outside was
    tested and recommended), as were a configuration, an ``info/attributes`` or an alternates listing linked from
    outside, a ``.git`` link to a file outside, and a file the configuration names (``core.attributesFile``: its
    export-ignore emptied the exported tree). Each is refused now."""
    where, shas = linked_case(tmp_path, why)
    monkeypatch.setattr(workers, "run_tests", Script())
    with pytest.raises(CapabilityError, match="outside the read roots"):
        intake.intake_recommendation(params(where, shas, ["label"]), context(tmp_path / "ctx",
                                                                             read_root=tmp_path / "roots"))
    assert delivered(tmp_path / "ctx") == []


def test_inside_the_read_roots_a_packed_repository_and_a_shared_clone_are_read(tmp_path, monkeypatch):
    """R6, the other side: the layouts git makes itself, inside the read roots, are still read, and a hooks directory
    linked from elsewhere (as hook managers do) refuses nothing, since no hook is read or run."""
    root = tmp_path / "roots"
    shas = build_repo(root / "packed")
    gc(root / "packed")
    (tmp_path / "hooks").mkdir()
    shutil.rmtree(root / "packed" / ".git" / "hooks", ignore_errors=True)
    os.symlink(tmp_path / "hooks", root / "packed" / ".git" / "hooks")
    git(root, "clone", "-q", "--shared", str(root / "packed"), str(root / "shared"))   # its objects: an alternate
    monkeypatch.setattr(workers, "run_tests", Script())
    for where in (root / "packed", root / "shared"):
        out = intake.intake_recommendation(params(where, shas, ["label"]), context(tmp_path / where.name,
                                                                                    read_root=root))
        assert out["recommendations"] == {"label": "ready to take"}


def test_alternate_stores_are_counted_by_nesting_and_resolved_from_their_store(tmp_path, monkeypatch):
    """R7 and R8 (M7). Seven alternate stores side by side, all inside the read roots, were refused as nesting
    "deeper than git follows them": the pin counted stores. It counts nesting now. A relative alternate is resolved
    from the store that lists it, as git resolves it, never from the process's working directory."""
    roots = tmp_path / "roots"
    shas = build_repo(roots / "repo")
    monkeypatch.setattr(workers, "run_tests", Script())
    stores = []
    for i in range(7):
        git(roots, "init", "-q", "--bare", f"store{i}.git")
        stores.append(roots / f"store{i}.git" / "objects")
    listing = roots / "repo" / ".git" / "objects" / "info" / "alternates"
    listing.write_text("".join(f"{store}\n" for store in stores))
    out = intake.intake_recommendation(params(roots / "repo", shas, ["label"]), context(tmp_path / "side",
                                                                                        read_root=roots))
    assert out["recommendations"] == {"label": "ready to take"}
    # nested seven deep: git ignores the listings past the fifth level, so the rehearsal refuses
    listing.write_text(f"{stores[0]}\n")
    for upper, lower in zip(stores, stores[1:]):
        (upper / "info" / "alternates").write_text(f"{lower}\n")
    with pytest.raises(CapabilityError, match="nest deeper than git follows them"):
        intake.intake_recommendation(params(roots / "repo", shas, ["label"]), context(tmp_path / "deep",
                                                                                       read_root=roots))
    for store in stores:
        (store / "info" / "alternates").unlink(missing_ok=True)
    # relative to its store, the line leads outside the roots; from this process's directory it would lead inside
    (tmp_path / "objs").mkdir()
    listing.write_text("../../../../objs\n")                  # objects -> .git -> repo -> roots -> tmp_path / objs
    deep = roots / "a" / "b" / "c" / "d"
    deep.mkdir(parents=True)
    monkeypatch.chdir(deep)
    with pytest.raises(CapabilityError, match="alternate object store is outside the read roots"):
        intake.intake_recommendation(params(roots / "repo", shas, ["label"]), context(tmp_path / "rel-out",
                                                                                       read_root=roots))
    # and a relative line leading to a store inside the roots is read, wherever the process is
    listing.write_text("../../../store0.git/objects\n")
    monkeypatch.chdir(tmp_path)
    out = intake.intake_recommendation(params(roots / "repo", shas, ["label"]), context(tmp_path / "rel-in",
                                                                                        read_root=roots))
    assert out["recommendations"] == {"label": "ready to take"}


def test_a_worktree_whose_repository_is_outside_the_read_roots_is_refused(tmp_path, monkeypatch):
    """R8 (M6). A linked worktree whose own git directory is inside the read roots, and whose repository
    (``commondir``) is outside: git reads that repository's configuration and references there. Refused. A ``.git``
    file naming a git directory relative to the worktree is read from the worktree, wherever the process is."""
    roots = tmp_path / "roots"
    shas = build_repo(roots / "main")
    monkeypatch.setattr(workers, "run_tests", Script())
    common = tmp_path / "outside" / "common.git"
    common.mkdir(parents=True)
    for name in ("HEAD", "config", "refs", "packed-refs"):
        source = roots / "main" / ".git" / name
        if source.is_dir():
            shutil.copytree(source, common / name)
        elif source.exists():
            shutil.copy(source, common / name)
    os.symlink(roots / "main" / ".git" / "objects", common / "objects")
    gitdir = roots / "wt-git"
    gitdir.mkdir()
    (gitdir / "HEAD").write_text(shas["label"] + "\n")
    (gitdir / "commondir").write_text(f"{common}\n")
    tree = roots / "tree"
    tree.mkdir()
    (gitdir / "gitdir").write_text(f"{tree / '.git'}\n")
    (tree / ".git").write_text(f"gitdir: {gitdir}\n")
    with pytest.raises(CapabilityError, match="the repository this worktree belongs to is outside the read roots"):
        intake.intake_recommendation(params(tree, shas, ["label"]), context(tmp_path / "wt", read_root=roots))
    (tree / ".git").write_text("gitdir: ../main/.git\n")       # relative: from the worktree, not from the process
    monkeypatch.chdir(tmp_path)
    out = intake.intake_recommendation(params(tree, shas, ["label"]), context(tmp_path / "rel", read_root=roots))
    assert out["recommendations"] == {"label": "ready to take"}


def test_a_claim_names_a_head_only_by_a_prefix_and_reads_an_error_count_as_a_failure(repo, tmp_path, monkeypatch):
    """R8 (M2, M3). Twelve hex digits from the middle of the unit's SHA name another head, never this one. "1 passed,
    1 error" and "3 passed, 2 errors" are failures, so a claim saying either about a test that passes here is a
    different result, never the same one."""
    path, shas = repo
    label = shas["label"]
    middle = label[5:17]
    got, unit, _ = check_claims(repo, tmp_path, monkeypatch, {"head_sha": middle, "validation": [
        {"command": "pytest tests/test_shout.py", "result": "pass"}]}, "m2-claim")
    assert got == "hold: stale: its claims name another head or none"
    got, unit, _ = check_claims(repo, tmp_path, monkeypatch, {"checks": [
        {"name": "ci", "head_sha": middle, "conclusion": "success"}]}, "m2-check")
    assert got == "hold: stale: check ci has results only for another head"
    assert unit["checks"][0]["status"] == "result is for another head (stale)"
    for said in ("1 passed, 1 error in 0.20s", "3 passed, 2 errors"):
        assert intake._claimed(said) == "fail", said
        got, unit, _ = check_claims(repo, tmp_path, monkeypatch, {"head_sha": label, "validation": [
            {"command": "pytest tests/test_shout.py", "result": said}]}, f"m3-{said[:9]}")
        assert unit["claims"][0]["status"] == "re-executed here: DIFFERENT result", said


def test_only_a_positive_receipt_of_brief_intake_is_a_delivery(repo, tmp_path, monkeypatch):
    """R8 (M10). A receipt the Gate classed as anything but positive is not a delivery, whatever output it carries."""
    path, shas = repo
    out = run(tmp_path, path, shas, ["label"], Script(), monkeypatch)
    for result_class in ("negative", "unknown", "uncertain"):
        seen = status(tmp_path, out["request_digest"], ledger=Ledger([out], result_class=result_class))
        assert seen["matching"] == 0 and seen["not_delivered_by_greg"] == 1, result_class
    assert status(tmp_path, out["request_digest"], ledger=Ledger([out]))["matching"] == 1
