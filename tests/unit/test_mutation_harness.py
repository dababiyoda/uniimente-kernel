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
