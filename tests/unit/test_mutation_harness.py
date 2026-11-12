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
