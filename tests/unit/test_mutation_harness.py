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
