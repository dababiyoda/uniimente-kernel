"""scripts/compose_rehearsal.py finds changes that merge cleanly and break each other, and touches nothing.

Every test builds a small git repository with a base and several branches, and runs the real script on it: the
in-memory merges, the exports and the pytest runs are all real. The synthetic cases:

- ``steeper`` changes what ``price`` returns and updates the base's test with it (and adds a helper that is not a test);
- ``consumer`` adds a test that relies on the old ``price`` (merges cleanly with ``steeper``, breaks in behaviour);
- ``label`` adds an unrelated function and its test (compatible with everything);
- ``flat`` rewrites the same line as ``steeper`` (a textual conflict);
- ``broken`` adds a test that fails on its own head;
- ``one``, ``two`` and ``capped``: two heads each register one more entry, a third asserts at most two entries.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest

from scripts import compose_rehearsal as cr

ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@t"}
PKG = "REGISTRY = ['base']\n\n\ndef price(n):\n    return n * 2\n\n\ndef label(n):\n    return f'item-{n}'\n"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, env=ENV, capture_output=True, text=True, check=True).stdout.strip()


def branch(repo: Path, name: str, files: dict[str, str]) -> str:
    """A branch off the base with ``files`` written and committed. Returns its commit."""
    git(repo, "checkout", "-q", "-b", name, "base")
    for path, text in files.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(text)
        git(repo, "add", path)
    git(repo, "commit", "-qm", name)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "base")
    (repo / "pkg.py").write_text(PKG)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_base.py").write_text("import pkg\n\n\ndef test_price():\n    assert pkg.price(2) == 4\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    branch(repo, "steeper", {"pkg.py": PKG.replace("n * 2", "n * 3"), "tests/helper.py": "FACTOR = 3\n",
                             "tests/test_base.py": "import pkg\n\n\ndef test_price():\n    assert pkg.price(2) == 6\n"})
    branch(repo, "consumer", {"tests/test_total.py":
                              "import pkg\n\n\ndef test_total():\n    assert pkg.price(2) + 1 == 5\n\n\n"
                              "def test_label_untouched():\n    assert pkg.label(1) == 'item-1'\n"})
    branch(repo, "label", {"pkg.py": PKG + "\n\ndef shout(n):\n    return label(n).upper()\n",
                           "tests/test_shout.py": "import pkg\n\n\ndef test_shout():\n    assert pkg.shout(1) == 'ITEM-1'\n"})
    branch(repo, "flat", {"pkg.py": PKG.replace("n * 2", "n * 4"),
                          "tests/test_base.py": "import pkg\n\n\ndef test_price():\n    assert pkg.price(2) == 8\n"})
    branch(repo, "broken", {"tests/test_broken.py": "def test_never_passed():\n    assert 1 == 2\n"})
    branch(repo, "one", {"reg_one.py": "import pkg\npkg.REGISTRY.append('one')\n",
                         "tests/test_one.py": "import pkg, reg_one\n\n\ndef test_one():\n    assert 'one' in pkg.REGISTRY\n"})
    branch(repo, "two", {"reg_two.py": "import pkg\npkg.REGISTRY.append('two')\n",
                         "tests/test_two.py": "import pkg, reg_two\n\n\ndef test_two():\n    assert 'two' in pkg.REGISTRY\n"})
    branch(repo, "capped", {"tests/test_capped.py":
                            "import importlib, pkg\n\n\ndef test_at_most_two_entries():\n"
                            "    for name in ('reg_one', 'reg_two'):\n        try:\n"
                            "            importlib.import_module(name)\n        except ImportError:\n            pass\n"
                            "    assert len(pkg.REGISTRY) <= 2\n"})
    git(repo, "checkout", "-q", "base")
    return repo


def rehearse(repo: Path, tmp_path: Path, *names: str, **kw) -> dict:
    units = [cr.Unit(name, name) for name in names]
    return cr.rehearse(repo, "base", units, kw.get("also", []), 120, tmp_path / f"scratch-{'-'.join(names)}")


def test_a_clean_merge_that_breaks_a_test_is_reported_with_the_head_that_causes_it(repo, tmp_path):
    """The case the script exists for: git reports no conflict, and one head's test fails once the other is in."""
    assert cr.merge(repo, git(repo, "rev-parse", "steeper"), git(repo, "rev-parse", "consumer"), "x")[1:] == ([], [])
    report = rehearse(repo, tmp_path, "steeper", "consumer", "label")
    assert report["merge_order"] == ["steeper", "consumer", "label"] and report["textual_conflicts"] == {}
    assert report["behavioural_conflicts"] == [{"test": "tests/test_total.py::test_total", "unit": "consumer",
                                                "caused_by": ["steeper"],
                                                "note": "passes when this head is left out"}]
    assert report["failing_before_the_merge"] == [] and report["clean"] is False
    by_name = {u["name"]: u for u in report["units"]}
    assert by_name["consumer"]["alone"] == {"counts": {"passed": 2}, "failed": [], "missing": []}
    assert by_name["consumer"]["merged"]["counts"] == {"failed": 1, "passed": 1}     # the other test still passes
    assert by_name["steeper"]["tests"] == ["tests/test_base.py"]                     # the test file it changed
    assert by_name["label"]["merged"] == {"counts": {"passed": 1}, "failed": [], "missing": []}


def test_compatible_heads_are_reported_clean_and_say_what_that_does_not_prove(repo, tmp_path):
    report = rehearse(repo, tmp_path, "consumer", "label")
    assert report["clean"] is True and report["behavioural_conflicts"] == [] and report["textual_conflicts"] == {}
    assert report["limits"][0] == "only the named tests were run: a clean result does not prove the heads are compatible"


def test_a_textual_conflict_is_reported_as_textual_and_the_head_is_left_out_of_the_merge(repo, tmp_path):
    report = rehearse(repo, tmp_path, "steeper", "flat", "label")
    assert report["textual_conflicts"] == {"flat": ["pkg.py", "tests/test_base.py"]}
    assert report["merge_order"] == ["steeper", "label"] and report["clean"] is False
    flat = next(u for u in report["units"] if u["name"] == "flat")
    assert flat["in_merge"] is False and flat["merged"] is None and flat["alone"]["counts"] == {"passed": 1}
    assert report["behavioural_conflicts"] == []


def test_a_test_that_fails_on_its_own_head_is_not_a_composition_problem(repo, tmp_path):
    report = rehearse(repo, tmp_path, "broken", "label")
    assert report["behavioural_conflicts"] == [] and report["clean"] is True
    assert report["failing_before_the_merge"] == [{"test": "tests/test_broken.py::test_never_passed", "unit": "broken"}]


def test_a_failure_that_needs_two_other_heads_names_both_and_no_single_cause(repo, tmp_path):
    report = rehearse(repo, tmp_path, "one", "two", "capped")
    [conflict] = report["behavioural_conflicts"]
    assert conflict["test"] == "tests/test_capped.py::test_at_most_two_entries" and conflict["unit"] == "capped"
    assert conflict["caused_by"] == ["one", "two"]
    assert conflict["note"] == "no single head explains it: it passes with any one of these left out"
    assert rehearse(repo, tmp_path, "one", "capped")["clean"] is True              # either alone is compatible


def test_an_extra_test_file_is_judged_against_the_base(repo, tmp_path):
    """``--also`` runs a file no head changed: failing merged and passing on the base is a conflict; failing on the
    base already is not."""
    report = rehearse(repo, tmp_path, "label", also=["tests/test_base.py"])
    assert report["clean"] is True and report["also"]["merged"]["counts"] == {"passed": 1}
    git(repo, "checkout", "-q", "-b", "silent", "base")           # changes price and updates no test
    (repo / "pkg.py").write_text(PKG.replace("n * 2", "n * 5"))
    git(repo, "commit", "-qam", "silent")
    git(repo, "checkout", "-q", "base")
    report = rehearse(repo, tmp_path, "silent", also=["tests/test_base.py"])
    assert report["behavioural_conflicts"] == [{"test": "tests/test_base.py::test_price", "unit": "(also)",
                                                "caused_by": ["silent"], "note": "passes when this head is left out"}]
    # on a base whose own test already fails, that failure is not blamed on the merge
    stale = cr.rehearse(repo, "broken", [cr.Unit("label", "label")], ["tests/test_broken.py"], 120,
                        tmp_path / "scratch-stale-base")
    assert stale["behavioural_conflicts"] == [] and stale["clean"] is True
    assert stale["failing_before_the_merge"] == [{"test": "tests/test_broken.py::test_never_passed", "unit": "(also)"}]


def test_named_tests_replace_the_changed_ones_and_a_missing_file_is_said(repo, tmp_path):
    units = [cr.Unit("label", "label", tests=["tests/test_base.py", "tests/test_gone.py"])]
    report = cr.rehearse(repo, "base", units, [], 120, tmp_path / "scratch")
    assert report["units"][0]["tests"] == ["tests/test_base.py", "tests/test_gone.py"]
    assert report["units"][0]["merged"] == {"counts": {"passed": 1}, "failed": [], "missing": ["tests/test_gone.py"]}


def test_a_test_file_that_cannot_be_collected_counts_as_failing_not_as_clean(repo, tmp_path):
    git(repo, "checkout", "-q", "-b", "needs", "base")
    (repo / "tests" / "test_needs.py").write_text("import pkg\nfrom pkg import gone\n\n\ndef test_x():\n    assert gone\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "needs")
    git(repo, "checkout", "-q", "base")
    report = rehearse(repo, tmp_path, "needs")
    assert report["failing_before_the_merge"] and report["failing_before_the_merge"][0]["unit"] == "needs"
    assert report["units"][0]["alone"]["failed"], "a collection error was read as nothing failing"


def steps(repo: Path, name: str, extra_file: str | None = None, factor: int = 2) -> None:
    """A branch that appends its own step to a shared list and adds a test that its step is there."""
    files = {"steps.txt": f"step base\nstep {name}\n",
             f"tests/test_step_{name}.py": f"from pathlib import Path\n\n\ndef test_step():\n"
                                           f"    assert 'step {name}' in Path('steps.txt').read_text().splitlines()\n"}
    if extra_file:
        files[extra_file] = PKG.replace("n * 2", f"n * {factor}")
    branch(repo, name, files)
    git(repo, "checkout", "-q", "base")


def test_a_conflict_in_a_named_list_file_is_resolved_by_keeping_both_lines_and_said(repo, tmp_path):
    """Every change to this repository's CI file appends a step at the same place, so any two such changes conflict
    textually and nothing else could be rehearsed. For a file the caller names, both sides' lines are kept."""
    (repo / "steps.txt").write_text("step base\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "steps")
    steps(repo, "alpha")
    steps(repo, "beta")
    units = lambda: [cr.Unit("alpha", "alpha"), cr.Unit("beta", "beta")]      # noqa: E731
    plain = cr.rehearse(repo, "base", units(), [], 120, tmp_path / "plain")
    assert plain["textual_conflicts"] == {"beta": ["steps.txt"]} and plain["kept_both_sides"] == {}
    kept = cr.rehearse(repo, "base", units(), [], 120, tmp_path / "kept", union=("steps.txt",))
    assert kept["textual_conflicts"] == {} and kept["kept_both_sides"] == {"beta": ["steps.txt"]}
    assert kept["merge_order"] == ["alpha", "beta"] and kept["clean"] is True
    assert [u["merged"]["counts"] for u in kept["units"]] == [{"passed": 1}, {"passed": 1}]   # both steps are there
    assert "## Conflicts resolved by keeping both sides' lines" in cr.markdown(kept)
    assert "where both sides' lines were kept in a named file, that resolution was not reviewed by a person" \
        in kept["limits"]


def test_keeping_both_lines_never_covers_a_file_that_was_not_named(repo, tmp_path):
    (repo / "steps.txt").write_text("step base\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "steps")
    steps(repo, "alpha", extra_file="pkg.py", factor=7)
    steps(repo, "gamma", extra_file="pkg.py", factor=9)         # also rewrites the same line of pkg.py, differently
    report = cr.rehearse(repo, "base", [cr.Unit("alpha", "alpha"), cr.Unit("gamma", "gamma")], [], 120,
                         tmp_path / "scratch", union=("steps.txt",))
    assert report["textual_conflicts"] == {"gamma": ["pkg.py", "steps.txt"]} and report["kept_both_sides"] == {}
    assert report["merge_order"] == ["alpha"] and report["clean"] is False


def test_a_head_that_no_longer_works_on_the_line_is_blamed_on_the_base_not_on_its_neighbours(repo, tmp_path):
    """``consumer`` branched before the line changed ``price``. Its own tree passes; merged onto today's line it fails
    whoever else is merged. The cause is the base, and no neighbour is named."""
    git(repo, "checkout", "-q", "-b", "line", "steeper")            # today's line already has the steeper price
    git(repo, "checkout", "-q", "base")
    report = cr.rehearse(repo, "line", [cr.Unit("consumer", "consumer"), cr.Unit("label", "label")], [], 120,
                         tmp_path / "scratch-line")
    assert report["behavioural_conflicts"] == [{
        "test": "tests/test_total.py::test_total", "unit": "consumer", "caused_by": ["(the base)"],
        "note": "fails as soon as this head is merged onto the base, with no other head: the line has moved since "
                "it branched"}]
    assert "caused by **(the base)**" in cr.markdown(report)
    alone = cr.rehearse(repo, "line", [cr.Unit("consumer", "consumer")], [], 120, tmp_path / "scratch-line-alone")
    assert alone["behavioural_conflicts"][0]["caused_by"] == ["(the base)"]        # one head: the base, by definition


def test_a_head_with_no_test_to_run_is_reported_as_not_checked(repo, tmp_path, capsys):
    """``silent`` changes behaviour and changes no test. Nothing was checked for it, and the report says so instead
    of letting it read as compatible."""
    git(repo, "checkout", "-q", "-b", "silent", "base")
    (repo / "pkg.py").write_text(PKG.replace("n * 2", "n * 5"))
    git(repo, "commit", "-qam", "silent")
    git(repo, "checkout", "-q", "base")
    report = rehearse(repo, tmp_path, "silent", "label")
    assert report["unchecked"] == ["silent"] and report["clean"] is True
    assert "No test was run for: **silent**." in cr.markdown(report)
    missing = cr.rehearse(repo, "base", [cr.Unit("label", "label", tests=["tests/test_gone.py"])], [], 120,
                          tmp_path / "scratch-missing")
    assert missing["unchecked"] == ["label"]                    # a named file that does not exist checks nothing
    assert rehearse(repo, tmp_path, "label")["unchecked"] == []


def test_a_run_in_which_pytest_never_started_counts_as_failing(repo, tmp_path):
    """A conftest that raises stops pytest before it collects anything: no test is named as failing and no count is
    printed. That is not a clean result."""
    git(repo, "checkout", "-q", "-b", "crashes", "base")
    (repo / "conftest.py").write_text("raise RuntimeError('boom')\n")
    (repo / "tests" / "test_fine.py").write_text("def test_fine():\n    assert True\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "crashes")
    git(repo, "checkout", "-q", "base")
    report = rehearse(repo, tmp_path, "crashes")
    [failed] = report["units"][0]["alone"]["failed"]
    assert failed.startswith("tests/test_fine.py::(pytest did not run: ")
    assert report["failing_before_the_merge"] == [{"test": failed, "unit": "crashes"}]


def test_the_rehearsal_leaves_the_repository_exactly_as_it_found_it(repo, tmp_path):
    def state():
        return (git(repo, "for-each-ref"), git(repo, "status", "--porcelain"), git(repo, "rev-parse", "HEAD"),
                git(repo, "worktree", "list"), git(repo, "stash", "list"), sorted(p.name for p in repo.iterdir()),
                (repo / ".git" / "index").read_bytes())
    before = state()
    rehearse(repo, tmp_path, "steeper", "consumer", "flat", "one", "two", "capped")
    cr.rehearse(repo, "base", [cr.Unit("steeper", "steeper"), cr.Unit("flat", "flat")], [], 120, tmp_path / "u",
                union=("pkg.py", "tests/test_base.py"))          # the keep-both path uses its own scratch index
    assert state() == before


def test_the_command_line_writes_both_reports_and_exits_1_on_a_conflict_0_when_clean_2_when_misused(repo, tmp_path, capsys):
    out_json, out_md = tmp_path / "r.json", tmp_path / "r.md"
    code = cr.main(["--repo", str(repo), "--base", "base", "--unit", "steeper=steeper", "--unit", "consumer=consumer",
                    "--json", str(out_json), "--markdown", str(out_md), "--timeout", "120"])
    assert code == 1
    report, text = json.loads(out_json.read_text()), out_md.read_text()
    assert report["tool"] == "compose_rehearsal/1" and report["behavioural_conflicts"][0]["caused_by"] == ["steeper"]
    assert "## Tests that pass alone and fail merged" in text
    assert "- `tests/test_total.py::test_total` (from consumer): caused by **steeper**; passes when this head is " \
           "left out." in text
    assert "a clean result does not prove the heads are compatible" in text and capsys.readouterr().out == text + "\n"
    assert cr.main(["--repo", str(repo), "--base", "base", "--unit", "label=label", "--timeout", "120"]) == 0
    assert "No textual or behavioural conflict was found in the tests that were run." in capsys.readouterr().out
    assert cr.main(["--repo", str(repo), "--base", "base"]) == 2                       # no unit
    assert cr.main(["--repo", str(repo), "--base", "base", "--unit", "x=label", "--unit", "x=one"]) == 2
    assert cr.main(["--repo", str(repo), "--base", "base", "--unit", "x=no-such-ref"]) == 2
    assert cr.main(["--repo", str(repo), "--base", "no-such-base", "--unit", "x=label"]) == 2


def test_the_command_line_runs_a_renamed_test_and_names_the_head_a_left_out_one_conflicts_with(repo, tmp_path):
    """Review of 885b7b7a, F5 and F9, on the command line's side of the shared code: a test file renamed and edited
    is run (git's rename detection, even a person's ``diff.renames = copies``, no longer drops it), and a head left
    out for a textual conflict names the earlier head it conflicts with, since which one is left out depends on the
    listed order."""
    git(repo, "config", "diff.renames", "copies")
    git(repo, "checkout", "-q", "-b", "mover", "base")
    git(repo, "mv", "tests/test_base.py", "tests/test_pricing.py")
    moved = repo / "tests" / "test_pricing.py"
    moved.write_text(moved.read_text() + "# moved\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "mover")
    git(repo, "checkout", "-q", "base")
    assert git(repo, "diff", "--name-status", "base", "mover").startswith("R")     # git itself calls it a rename
    [mover] = rehearse(repo, tmp_path, "mover")["units"]
    assert mover["tests"] == ["tests/test_pricing.py"] and mover["alone"]["counts"] == {"passed": 1}
    report = rehearse(repo, tmp_path, "steeper", "flat")
    assert report["textual_conflicts_with"] == {"flat": ["steeper"]}
    assert "- **flat** conflicts with what was merged before it (directly with steeper; which of them is left out " \
           "depends on the listed order) in: `pkg.py`, `tests/test_base.py`" in cr.markdown(report)


SHARED = "tests/test_shared.py"
FILLER = "import pkg\n" + "".join(f"\n\ndef test_filler_{i}():\n    assert pkg.label({i}) == 'item-{i}'\n"
                                  for i in range(6))
TEST_A = "\n\ndef test_a():\n    assert pkg.price(2) == 4\n"


def test_a_failure_in_a_test_file_two_heads_edited_is_a_conflict_and_the_command_exits_1(repo, tmp_path, capsys):
    """Review of 387e8417, R1, on the command line with real pytest. Two heads add tests to one file: ``a`` a test
    that relies on today's price, ``c`` (or the price-changing ``b2`` itself) one at the top. The merged tree holds
    the file merged from both versions, and ``a``'s test fails there. The rehearsal dropped that measured failure
    (the file was neither head's byte for byte), reported clean and exited 0. It is a behavioural conflict again,
    naming the other head whose edits the file holds; that head is not left out to look for the cause."""
    (repo / SHARED).write_text(FILLER)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "a shared test file")
    branch(repo, "a", {SHARED: FILLER + TEST_A})
    branch(repo, "c", {SHARED: FILLER.replace("import pkg\n", "import pkg\n\n\ndef test_c():\n    assert True\n", 1)})
    branch(repo, "b", {"pkg.py": PKG.replace("n * 2", "n * 3"), "tests/test_b.py": "import pkg\n\n\ndef test_b():\n"
                                                                                    "    assert pkg.price(1) == 3\n"})
    branch(repo, "b2", {"pkg.py": PKG.replace("n * 2", "n * 3"),
                        SHARED: FILLER.replace("import pkg\n", "import pkg\n\n\ndef test_b():\n    assert True\n", 1)})
    git(repo, "checkout", "-q", "base")
    node = f"{SHARED}::test_a"
    for units, cause, other in ((["a", "c", "b"], ["b"], "c"), (["a", "b2"], [], "b2")):
        out = tmp_path / f"{'-'.join(units)}.json"
        code = cr.main(["--repo", str(repo), "--base", "base", *[f"--unit={u}={u}" for u in units], "--timeout", "120",
                        "--json", str(out)])
        report, text = json.loads(out.read_text()), capsys.readouterr().out
        assert (code, report["clean"], len(report["not_compared"])) == (1, False, 0), units
        conflict = next(c for c in report["behavioural_conflicts"] if c["test"] == node and c["unit"] == "a")
        assert conflict["caused_by"] == cause and conflict["shared_with"] == [other], units
        assert "No textual or behavioural conflict was found" not in text
        assert f"- `{node}` (from a): caused by **{cause[0] if cause else 'no single head'}**" in text


def test_a_head_behind_a_base_that_edited_its_test_file_is_blamed_on_the_base(repo, tmp_path):
    """Review of 387e8417, R2, with real pytest: ``behind`` adds a test to the shared file, and the line then changes
    the price and edits the top of that file. The merged tree is the line and ``behind`` alone, holding the file
    merged from both. The failure was dropped as "a merge of several heads' versions"; it is the base's again. A line
    that only adds a header to the file breaks nothing, and the report is clean."""
    (repo / SHARED).write_text(FILLER)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "a shared test file")
    branch(repo, "behind", {SHARED: FILLER + TEST_A})
    branch(repo, "line", {"pkg.py": PKG.replace("n * 2", "n * 3"), SHARED: "# the line moved\n" + FILLER})
    branch(repo, "line-header", {SHARED: "# a header only\n" + FILLER})
    git(repo, "checkout", "-q", "base")
    report = cr.rehearse(repo, "line", [cr.Unit("behind", "behind")], [], 120, tmp_path / "moved")
    assert (report["clean"], len(report["not_compared"])) == (False, 0)
    assert [(c["test"], c["caused_by"], c["shared_with"]) for c in report["behavioural_conflicts"]] == [
        (f"{SHARED}::test_a", ["(the base)"], ["(the base)"])]
    quiet = cr.rehearse(repo, "line-header", [cr.Unit("behind", "behind")], [], 120, tmp_path / "header")
    assert quiet["clean"] is True and quiet["behavioural_conflicts"] == [] and quiet["not_compared"] == []
