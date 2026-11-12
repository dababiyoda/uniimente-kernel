"""The shared mutation-gate runner tells caught, survived and stale mutants apart."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ci"))

import mutation_harness  # noqa: E402


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "src"
    (root / "tests").mkdir(parents=True)
    (root / "guard.py").write_text("def allowed(n):\n    return n < 10  # limit\n")
    (root / "tests" / "test_guard.py").write_text(
        "from guard import allowed\n\ndef test_limit():\n    assert not allowed(10)\n")
    return root


def test_caught_survived_and_stale(tmp_path, capsys):
    root = _repo(tmp_path)
    tests = "tests/test_guard.py"
    assert mutation_harness.run([("guard.py", "drop the limit", "n < 10", "True")], tests,
                                "h-", root=root, purge_dirs=("tests",)) == 0
    assert "CAUGHT drop the limit" in capsys.readouterr().out
    assert mutation_harness.run([("guard.py", "comment only", "# limit", "# l")], tests,
                                "h-", root=root, purge_dirs=("tests",)) == 1
    assert "SURVIVED_OR_INVALID comment only" in capsys.readouterr().out
    assert mutation_harness.run([("guard.py", "gone anchor", "n <= 10", "True")], tests,
                                "h-", root=root, purge_dirs=("tests",)) == 1
    assert "STALE gone anchor" in capsys.readouterr().out
    # the working tree is never touched
    assert "n < 10  # limit" in (root / "guard.py").read_text()


# ---------------------------------------------------------------- what counts as caught
# The rule in run(): pytest exits 1, reports a FAILED test in the named file, and reports no collection error. Each
# case below is a mutant that makes pytest exit non-zero without that, beside a control the same tree does catch (so
# "not caught" is never an artefact of a broken fixture tree).

TESTS = "tests/test_guard.py"


def _tree(tmp_path: Path, guard: str, test: str, ini: str = "") -> Path:
    root = tmp_path / "src"
    (root / "tests").mkdir(parents=True)
    (root / "guard.py").write_text(guard)
    (root / "tests" / "test_guard.py").write_text(test)
    if ini:
        (root / "pytest.ini").write_text(ini)
    return root


def _verdict(root: Path, capsys, name: str, old: str, new: str) -> tuple[int, str]:
    status = mutation_harness.run([("guard.py", name, old, new)], TESTS, "h-", root=root, purge_dirs=("tests",))
    return status, capsys.readouterr().out


def _refused(root: Path, capsys, name: str, old: str, new: str) -> bool:
    status, out = _verdict(root, capsys, name, old, new)
    return status == 1 and f"SURVIVED_OR_INVALID {name}" in out and "0/1 caught" in out


def test_a_mutant_that_only_breaks_the_import_is_not_caught(tmp_path, capsys):
    """pytest exits 2 with a collection error and no FAILED test: nothing ran, so nothing was shown to discriminate."""
    root = _repo(tmp_path)
    assert _verdict(root, capsys, "drop the limit", "n < 10", "True")[0] == 0                     # control
    assert _refused(root, capsys, "break the import", "def allowed(n):",
                    "import no_such_module_for_this_mutant\n\n\ndef allowed(n):")


def test_an_error_outside_a_test_body_is_not_caught(tmp_path, capsys):
    """A fixture that raises gives exit 1 and an ERROR line, not a FAILED test in the named file: the test's own
    assertion never ran, whatever words the error itself prints."""
    root = _tree(tmp_path, "LIMIT = 10\n\n\ndef allowed(n):\n    return n < 10\n",
                 "import pytest\n\nimport guard\n\n\n@pytest.fixture\ndef limit():\n"
                 "    if not hasattr(guard, 'LIMIT'):\n        raise RuntimeError('FAILED to read the limit')\n"
                 "    return guard.LIMIT\n\n\n"
                 "def test_limit(limit):\n    assert not guard.allowed(limit)\n")
    assert _verdict(root, capsys, "drop the limit", "n < 10", "True")[0] == 0                     # control
    assert _refused(root, capsys, "remove what the fixture reads", "LIMIT = 10\n", "")


def test_a_failed_test_beside_a_collection_error_is_not_caught(tmp_path, capsys):
    """Where pytest is told to continue past collection errors it exits 1 with a FAILED test and a collection-error
    section: part of the named file did not run, so the run is not counted. (The runner matches that section's
    heading anywhere in pytest's output, so the heading is not spelled out here: a failing test that shows it would
    itself read as not caught.)"""
    root = _tree(tmp_path, "CASES = (1, 2)\n\n\ndef allowed(n):\n    return n in CASES\n",
                 "import pytest\n\nimport guard\n\n\ndef test_member():\n    assert guard.allowed(1)\n\n\n"
                 "class TestEveryCase:\n    @pytest.mark.parametrize('n', guard.CASES)\n"
                 "    def test_case(self, n):\n        assert guard.allowed(n)\n",
                 ini="[pytest]\naddopts = --continue-on-collection-errors\n")
    assert _verdict(root, capsys, "admit nothing", "n in CASES", "False")[0] == 0                 # control
    assert _refused(root, capsys, "make the cases uncollectable", "CASES = (1, 2)", "CASES = 5")


def test_a_failed_test_in_an_interrupted_run_is_not_caught(tmp_path, capsys):
    """A FAILED test followed by an interrupt gives exit 2: the run did not finish, so it is not counted."""
    root = _tree(tmp_path, "def allowed(n):\n    return n < 10\n",
                 "import pytest\n\nimport guard\n\n\n@pytest.fixture\ndef session():\n    yield\n"
                 "    if guard.allowed(99):\n        raise KeyboardInterrupt\n\n\n"
                 "def test_limit(session):\n    assert not guard.allowed(10)\n")
    assert _verdict(root, capsys, "raise the limit", "n < 10", "n < 11")[0] == 0                  # control
    assert _refused(root, capsys, "drop the limit and interrupt", "n < 10", "True")


def test_an_anchor_at_two_sites_is_stale_not_applied(tmp_path, capsys):
    """The runner never guesses which site a mutant means: more than one occurrence is refused like none."""
    root = _repo(tmp_path)
    status, out = _verdict(root, capsys, "ambiguous anchor", "n", "m")
    assert status == 1 and "STALE ambiguous anchor" in out and "0/1 caught" in out


def test_a_named_test_that_already_fails_judges_no_mutant(tmp_path, capsys):
    """Without a baseline, a test that fails for a reason of its own made every mutant read as caught (81 of 81 on a
    merged tree, 2026-11-12). The runner now refuses to judge: it says so, catches nothing and fails the gate."""
    root = _tree(tmp_path, "def allowed(n):\n    return n < 10\n",
                 "import guard\n\n\ndef test_limit():\n    assert not guard.allowed(10)\n\n\n"
                 "def test_unrelated_and_already_failing():\n    assert guard.allowed(99)\n")
    status, out = _verdict(root, capsys, "drop the limit", "n < 10", "True")
    assert status == 1 and "BASELINE_FAILS tests/test_guard.py" in out and "CAUGHT" not in out
    assert "0/1 caught" in out
    assert "n < 10" in (root / "guard.py").read_text()                 # and nothing was applied anywhere


def test_on_a_planted_tree_only_a_different_failing_test_is_a_catch(tmp_path, capsys):
    """A gate may mutate a tree that is planted to fail. The planted failure is named; it must be the first failure
    before any mutant, and a mutant is caught only when another test of the file fails in its place."""
    guard = "LIMIT = 10\nKEPT = ()\n\n\ndef allowed(n):\n    return n < LIMIT or n in KEPT\n"
    test = ("import guard\n\n\ndef test_planted():\n    assert guard.allowed(50)\n\n\n"
            "def test_kept_list_is_empty():\n    assert guard.KEPT == ()\n")
    root = _tree(tmp_path, guard, test)

    def planted_run(name, old, new, first="test_planted"):
        status = mutation_harness.run([("guard.py", name, old, new)], TESTS, "h-", root=root, purge_dirs=("tests",),
                                      failing_first=first)
        return status, capsys.readouterr().out

    status, out = planted_run("grow the kept list", "KEPT = ()", "KEPT = (50,)")
    assert status == 0 and "CAUGHT grow the kept list" in out          # the planted test passes, the pin fails
    status, out = planted_run("a mutant that changes nothing", "LIMIT = 10", "LIMIT = 11")
    assert status == 1 and "SURVIVED_OR_INVALID" in out                # the planted failure alone is no catch
    status, out = planted_run("grow the kept list", "KEPT = ()", "KEPT = (50,)", first="test_kept_list_is_empty")
    assert status == 1 and "BASELINE_FAILS" in out and "CAUGHT" not in out   # the tree does not fail where it says


def test_on_a_planted_tree_a_later_test_that_already_fails_judges_no_mutant(tmp_path, capsys):
    """The planted baseline runs every named test, not only up to the planted failure. Until a review on 2026-11-12
    it stopped there (``-x``), so a test after the planted one that already failed was never seen, and a mutant that
    only made the planted test pass read as caught by it."""
    root = _tree(tmp_path, "KEPT = ()\n\n\ndef allowed(n):\n    return n in KEPT\n",
                 "import guard\n\n\ndef test_planted():\n    assert guard.allowed(50)\n\n\n"
                 "def test_unrelated_and_already_failing():\n    assert 1 + 1 == 3\n")
    status = mutation_harness.run([("guard.py", "grow the kept list (nothing pins it)", "KEPT = ()", "KEPT = (50,)")],
                                  TESTS, "h-", root=root, purge_dirs=("tests",), failing_first="test_planted")
    out = capsys.readouterr().out
    assert status == 1 and "BASELINE_FAILS tests/test_guard.py" in out and "CAUGHT" not in out
    assert "test_unrelated_and_already_failing" in out and "0/1 caught" in out    # and it says which test


def test_the_planted_test_is_named_whole_never_as_a_prefix(tmp_path, capsys):
    """A test whose name begins with the planted test's name is a different test, in the baseline and in judging."""
    guard = "LIMIT = 10\nKEPT = ()\n\n\ndef allowed(n):\n    return n < LIMIT or n in KEPT\n"
    # A different test, named with the planted name as its prefix, already fails: the baseline refuses the tree.
    root = _tree(tmp_path / "a", guard,
                 "import guard\n\n\ndef test_planted():\n    assert guard.allowed(5)\n\n\n"
                 "def test_planted_other():\n    assert guard.allowed(50)\n\n\n"
                 "def test_pin():\n    assert guard.LIMIT == 10\n")
    status = mutation_harness.run([("guard.py", "raise the limit", "LIMIT = 10", "LIMIT = 99")], TESTS, "h-",
                                  root=root, purge_dirs=("tests",), failing_first="test_planted")
    out = capsys.readouterr().out
    assert status == 1 and "BASELINE_FAILS" in out and "CAUGHT" not in out
    # The pin is named with the planted name as its prefix: a mutant that moves the failure to it is caught.
    root = _tree(tmp_path / "b", guard,
                 "import guard\n\n\ndef test_planted():\n    assert guard.allowed(50)\n\n\n"
                 "def test_planted_pin():\n    assert guard.KEPT == ()\n")
    status = mutation_harness.run([("guard.py", "grow the kept list", "KEPT = ()", "KEPT = (50,)")], TESTS, "h-",
                                  root=root, purge_dirs=("tests",), failing_first="test_planted")
    out = capsys.readouterr().out
    assert status == 0 and "CAUGHT grow the kept list" in out and "1/1 caught" in out


def test_parallel_workers_judge_each_mutant_alone_and_count_the_same(tmp_path, capsys):
    """Three workers, six mutants of one file: each mutant is applied and reverted in its own worker's copy, so a
    caught mutant cannot make a neighbour's run fail and a survivor cannot hide behind one. The verdicts and the
    count equal the one-worker run's."""
    root = _repo(tmp_path)
    tests = "tests/test_guard.py"
    mutants = [("guard.py", "drop the limit", "n < 10", "True"),
               ("guard.py", "comment only", "# limit", "# l"),
               ("guard.py", "raise the limit", "n < 10", "n < 11"),
               ("guard.py", "comment again", "# limit", "# x"),
               ("guard.py", "gone anchor", "n <= 10", "True"),
               ("guard.py", "admit all", "return n < 10", "return n == n")]
    verdicts = {}
    for workers in (1, 3):
        status = mutation_harness.run(mutants, tests, "h-", root=root, purge_dirs=("tests",), workers=workers)
        out = capsys.readouterr().out
        verdicts[workers] = (status, sorted(line for line in out.splitlines() if not line.startswith("BASELINE")))
    assert verdicts[1] == verdicts[3]
    status, lines = verdicts[3]
    assert status == 1 and "3/6 caught" in lines
    assert {"CAUGHT drop the limit", "CAUGHT raise the limit", "CAUGHT admit all", "SURVIVED_OR_INVALID comment only",
            "SURVIVED_OR_INVALID comment again", "STALE gone anchor"} <= set(lines)
    assert "n < 10  # limit" in (root / "guard.py").read_text()


ISOLATION_TEST = '''import os
import subprocess
import sys
import uuid
from pathlib import Path

from guard import allowed

HERE = Path(__file__).resolve().parents[1]            # this scratch copy's root
RUNS = Path(RUNS_DIR)                                 # outside every copy, shared by every run of this file


def test_limit():
    assert not allowed(10)


def test_no_other_copy_uses_this_base_temporary_directory(tmp_path_factory):
    mine = str(tmp_path_factory.getbasetemp().resolve())
    name = uuid.uuid4().hex
    (RUNS / f".{name}").write_text(f"{HERE}\\n{mine}")
    os.replace(RUNS / f".{name}", RUNS / name)        # whole records only: another run may be reading them now
    records = (p.read_text().split("\\n") for p in RUNS.iterdir() if not p.name.startswith("."))
    assert not {root for root, temp in records if temp == mine and root != str(HERE)}


def test_a_process_started_outside_the_copy_imports_this_copy():
    out = subprocess.run([sys.executable, "-c", "import guard; print(guard.__file__)"], cwd=RUNS,
                         capture_output=True, text=True, check=True).stdout
    assert Path(out.strip()).resolve().parent == HERE
'''


def test_each_copy_has_its_own_base_temporary_directory_and_import_path(tmp_path, capsys):
    """Parallel verdicts rely on two isolations besides the copy itself. With one ``--basetemp`` for every copy, a
    review (2026-11-12) saw no-op mutants read as caught on a real gated file (4 and 5 of 6 in two runs), because
    concurrent runs deleted each other's ``tmp_path``; with one ``PYTHONPATH`` for every copy, a process a test starts
    outside its copy imports another copy's code. Here a run fails if any other copy has used its base temporary
    directory, or if such a process imports from anywhere else, so either sharing makes a mutant that changes nothing
    read as caught. The baseline runs in one copy and three mutants run at once, so the comparison spans copies (the
    last assertion checks that it did)."""
    runs = tmp_path / "runs"
    runs.mkdir()
    root = _tree(tmp_path, "def allowed(n):\n    return n < 10  # limit\n",
                 ISOLATION_TEST.replace("RUNS_DIR", repr(str(runs))))
    mutants = [("guard.py", "drop the limit", "n < 10", "True")] + [
        ("guard.py", f"comment only {i}", "# limit", f"# limit {i}") for i in range(3)]
    status = mutation_harness.run(mutants, TESTS, "h-", root=root, purge_dirs=("tests",), workers=3)
    out = capsys.readouterr().out
    assert "CAUGHT drop the limit" in out and "1/4 caught" in out and status == 1              # control, then:
    assert all(f"SURVIVED_OR_INVALID comment only {i}" in out for i in range(3)), out
    records = [p for p in runs.iterdir() if not p.name.startswith(".")]
    assert len({p.read_text().split("\n")[0] for p in records}) >= 2           # the check did span two copies


def test_an_exception_while_judging_one_mutant_loses_no_other_verdict(tmp_path, capsys):
    """A mutant that cannot be judged (here its target is not there; a timeout is handled the same way) reads as not
    caught with its reason. Until a review on 2026-11-12 the exception left the run: mutants not yet started were
    dropped and no count was printed."""
    root = _repo(tmp_path)
    mutants = [("guard.py", "drop the limit", "n < 10", "True"),
               ("missing.py", "a target that is not there", "n < 10", "True"),
               ("guard.py", "comment only", "# limit", "# l")]
    for workers in (1, 3):
        status = mutation_harness.run(mutants, TESTS, "h-", root=root, purge_dirs=("tests",), workers=workers)
        out = capsys.readouterr().out
        assert status == 1 and "1/3 caught" in out and "CAUGHT drop the limit" in out
        assert "SURVIVED_OR_INVALID a target that is not there (not judged: FileNotFoundError" in out
        assert "SURVIVED_OR_INVALID comment only" in out


def test_the_worker_count_comes_from_the_environment_and_is_never_below_one(monkeypatch):
    monkeypatch.setattr(mutation_harness.os, "cpu_count", lambda: 4)
    monkeypatch.setenv("MUTATION_WORKERS", "2")
    assert mutation_harness.default_workers() == 2
    for bad in ("0", "-3", "many", ""):
        monkeypatch.setenv("MUTATION_WORKERS", bad)
        assert 1 <= mutation_harness.default_workers() <= 3


def test_a_worker_count_is_used_only_as_a_whole_number_from_one_to_the_cpus(monkeypatch, capsys):
    """Found by a review on 2026-11-12: a superscript digit passed ``str.isdigit`` and crashed every gate in ``int``,
    ' 2' fell back without a word, and 1000 made one repository copy per mutant. A value outside ASCII digits from 1
    to the CPU count is not used, and the runner says so; an unset or empty value takes the default silently."""
    monkeypatch.setattr(mutation_harness.os, "cpu_count", lambda: 4)
    monkeypatch.setenv("MUTATION_WORKERS", "4")
    assert mutation_harness.default_workers() == 4 and capsys.readouterr().err == ""
    for bad in ("²", "٣", " 2", "2 ", "2.0", "5", "1000", "0", "-3", "many"):
        monkeypatch.setenv("MUTATION_WORKERS", bad)
        assert mutation_harness.default_workers() == 3
        assert f"MUTATION_WORKERS={bad!r} is not a whole number from 1 to 4" in capsys.readouterr().err
    monkeypatch.setenv("MUTATION_WORKERS", "")
    assert mutation_harness.default_workers() == 3 and capsys.readouterr().err == ""
    monkeypatch.delenv("MUTATION_WORKERS")
    assert mutation_harness.default_workers() == 3 and capsys.readouterr().err == ""
