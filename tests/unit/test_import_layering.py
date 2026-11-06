"""Package layering ratchets (shared with scripts/repo_review.py).

1. The published boundary distribution (adapters, contracts, events, provenance)
   imports only itself: consumers install nothing else.
2. No new two-way dependency between top-level packages.

Both are shrink-only: a new violation fails, and a kept violation that has been
removed also fails until its entry is deleted from the KEPT table, so the
tables can only get shorter. Ordinary one-way imports are not ratcheted.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("repo_review", ROOT / "scripts" / "repo_review.py")
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


def test_boundary_matches_published_distribution():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    line = next(l for l in pyproject.splitlines() if l.strip().startswith("packages"))
    for name in review.BOUNDARY:
        assert f'"{name}"' in line
    assert line.count('"') == 2 * len(review.BOUNDARY)


def test_no_new_and_no_stale_two_way_package_imports():
    pairs = review.two_way_pairs(review.import_edges(ROOT))
    assert review.ratchet(pairs, review.KEPT_TWO_WAY) == {"new": [], "gone": []}


def test_no_new_and_no_stale_boundary_imports():
    found = review.boundary_violations(review.import_edges(ROOT))
    assert review.ratchet(found, review.KEPT_BOUNDARY) == {"new": [], "gone": []}


def test_every_kept_entry_states_a_reason():
    for table in (review.KEPT_TWO_WAY, review.KEPT_BOUNDARY):
        assert all(isinstance(r, str) and len(r) > 20 for r in table.values())


def _tree(tmp_path, files):
    for rel, text in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return tmp_path


def test_planted_cycle_is_caught(tmp_path):
    root = _tree(tmp_path, {"alpha/__init__.py": "import beta\n",
                            "beta/__init__.py": "",
                            "beta/late.py": "def f():\n    from alpha import x\n"})
    pairs = review.two_way_pairs(review.import_edges(root))
    assert pairs == {("alpha", "beta")}
    assert review.ratchet(pairs, {})["new"] == [("alpha", "beta")]


def test_planted_boundary_escape_is_caught_even_when_lazy(tmp_path):
    root = _tree(tmp_path, {"provenance/__init__.py": "",
                            "provenance/x.py": "def g():\n    import greg.missions\n",
                            "greg/__init__.py": ""})
    assert review.boundary_violations(review.import_edges(root)) == {("provenance", "greg")}


def test_removed_kept_entry_must_be_deleted(tmp_path):
    root = _tree(tmp_path, {"alpha/__init__.py": "", "beta/__init__.py": ""})
    pairs = review.two_way_pairs(review.import_edges(root))
    assert review.ratchet(pairs, {("alpha", "beta"): "was a cycle"})["gone"] == [("alpha", "beta")]


def test_boundary_distribution_works_installed_alone(tmp_path):
    """Install only the published packages and import every module, as a consumer would.

    Also pins S-2's fix: the witness genome is readable as plain data, and the
    deprecated kernel-only wrapper fails with a message that names the cause.
    """
    import shutil
    import subprocess
    import sys
    for pkg in review.BOUNDARY:
        shutil.copytree(ROOT / pkg, tmp_path / pkg, ignore=shutil.ignore_patterns("__pycache__"))
    probe = (
        "import importlib, pkgutil, sys\n"
        "sys.path.insert(0, '.')  # -I leaves only stdlib and the copied packages\n"
        f"for pkg in {list(review.BOUNDARY)!r}:\n"
        "    importlib.import_module(pkg)\n"
        "    for m in pkgutil.walk_packages([pkg], pkg + '.'):\n"
        "        importlib.import_module(m.name)\n"
        "import provenance.witness as w\n"
        "assert w.GENOME_SPEC['name'] == 'provenance.append_only_witness'\n"
        "try:\n"
        "    w.capability_genome()\n"
        "except ImportError as e:\n"
        "    assert 'GENOME_SPEC' in str(e), e\n"
        "else:\n"
        "    raise SystemExit('capability_genome() should need the kernel package')\n"
    )
    r = subprocess.run([sys.executable, "-I", "-W", "ignore::DeprecationWarning", "-c", probe],
                       cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
