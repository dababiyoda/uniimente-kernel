"""The converged Mind (Track B, 2026-10-14): one entry, one evolution controller, one admission source.

PR #155 and PR #158 built the 2026-10-07 directive in parallel. These checks pin what the convergence decided
(docs/collaboration/MIND-LINEAGE-RECONCILIATION-2026-10-14.md) so a later change cannot silently reopen it:

* the two families' namespaces stay disjoint on the one solver table;
* exactly one protected-evolution controller is reachable from GREG's runtime;
* archival copies of the eight colliding frozen paths are byte-identical to the commits they claim;
* PR #155's frozen held-out verdicts change the Competency Compiler's routing, and the genome inventory reads
  the same index the compiler routes on;
* one Landlock grant path covers both lineages' runtime library lists.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "docs" / "collaboration" / "lineage-archive"
LINEAGES = {"pr155-ef5f078": "ef5f078", "pr158-a832c73": "a832c73"}
COLLIDED = ("cortex/evaluation/composition_lift/freeze-v2.json", "cortex/evaluation/composition_lift/freeze-v3.json",
            "cortex/evaluation/composition_lift/run_v2.py", "cortex/evaluation/composition_lift/run_v3.py",
            "cortex/evaluation/learned_routing/freeze-v3.json", "cortex/evaluation/learned_routing/run_v3.py",
            "cortex/evaluation/learned_routing/suite-v3.json",
            "docs/evidence/greg-protected-evolution/2026-10-14/README.md")


def test_repertoire_and_genome_families_share_one_solver_table_without_a_name_clash():
    from greg.cognition import catalog, solvers
    from greg.cognition.genomes import library
    from greg.cognition.repertoire import REPERTOIRE
    genomes = set(library.catalog_families())
    assert not set(REPERTOIRE) & genomes
    assert set(REPERTOIRE) | genomes <= set(solvers.SOLVERS) | {"semantic"}
    assert set(REPERTOIRE) <= set(catalog.FAMILIES)


def _imports_module(path: Path, module: str) -> bool:
    tree = ast.parse(path.read_text(errors="ignore"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[-1] == module:
            return True
        if isinstance(node, ast.ImportFrom) and any(a.name == module for a in node.names):
            return True
        if isinstance(node, ast.Import) and any(a.name.split(".")[-1] == module for a in node.names):
            return True
    return False


def test_one_evolution_controller_is_reachable_from_runtime():
    """greg.cognition.evolution is the controller; the #155 routing-genome mechanism is an isolated alternative
    imported only by its historical runner (and its own tests)."""
    importers = sorted(str(p.relative_to(ROOT)) for base in ("greg", "cortex", "scripts", "foundry")
                       for p in (ROOT / base).rglob("*.py") if _imports_module(p, "evolution_routing"))
    assert importers == ["cortex/evaluation/evolution/run.py"], importers
    from greg.cognition import evolution
    assert hasattr(evolution, "cycle") and hasattr(evolution, "SealedEvaluator")


def _git_blob_sha(commit: str, path: str) -> str | None:
    out = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True, timeout=60)
    return hashlib.sha256(out.stdout).hexdigest() if out.returncode == 0 else None


def test_archived_frozen_files_are_byte_identical_to_their_source_commits():
    absent = [c for c in LINEAGES.values() if subprocess.run(
        ["git", "cat-file", "-e", f"{c}^{{commit}}"], cwd=ROOT, capture_output=True, timeout=30).returncode]
    if absent:
        pytest.skip(f"git history does not hold {absent}: archival identity not verified on this checkout")
    mismatched = []
    for folder, commit in LINEAGES.items():
        for path in COLLIDED:
            copy = ARCHIVE / folder / path
            if not copy.is_file() or hashlib.sha256(copy.read_bytes()).hexdigest() != _git_blob_sha(commit, path):
                mismatched.append(f"{folder}/{path}")
    assert not mismatched, mismatched
    # #158's file occupies each original path (its live tests import those runners)
    for path in COLLIDED:
        assert (ROOT / path).read_bytes() == (ARCHIVE / "pr158-a832c73" / path).read_bytes(), path


def _rows(data: dict) -> dict:
    from greg.cognition import compiler as C
    return {r["method"]: r for r in C.candidates(data, C.CompetencyGeometry(), C.evidence_index())}


def test_frozen_negative_verdicts_from_pr155_change_the_compilers_routing():
    observations = _rows({"observations": [1, 2, 3, 40]})
    for method in ("cognition.pattern", "cognition.collective"):       # REJECTED on held-out seeds
        assert observations[method]["status"] == "REJECTED"
        assert "frozen admission status REJECTED" in observations[method]["rejected"]
    assert "cognition.robust_pattern" not in observations                # ambiguous signature: never inferred
    simulate = _rows({"seed": 1, "samples": 10, "steps": 3, "step_probability": 0.5})
    assert simulate["cognition.simulation"]["rejected"]
    blackbox = _rows({"function": "sphere", "shift": [0.0], "bounds": [[-1, 1]], "budget": 100, "seed": 1})
    assert blackbox["cognition.blackbox"]["status"] == "SUPERSEDED" and blackbox["cognition.blackbox"]["rejected"]
    assert (blackbox["cognition.swarm"]["status"], blackbox["cognition.swarm"]["rejected"]) == \
        ("DEFAULT_FOR_GEOMETRY", None)
    crowd = _rows({"classes": ["a", "b"], "labels": [[0, 0, "a"]]})
    assert (crowd["cognition.crowd"]["status"], crowd["cognition.crowd"]["rejected"]) == ("EXPERIMENTAL", None)


def test_a_structural_label_changes_no_route():
    """ALIAS or SUPERSEDED_BY_CANONICAL_ORGAN is not a held-out verdict: the family routes as before."""
    rows = _rows({"factors": {"a": 2.0}})
    assert rows["cognition.estimation"]["status"] == "UNEVALUATED"


def test_the_genome_inventory_reads_the_index_the_compiler_routes_on():
    from greg.cognition import genome_library as lib
    from greg.cognition.compiler import evidence_index
    from greg.cognition.genomes import library
    index, genomes = evidence_index(), library.executables()
    entries = {e.genome_id: e for e in lib.inventory()}
    checked = 0
    for family, row in index["genomes"].items():
        if family in genomes and row.get("version") in (None, genomes[family].genome.version):
            entry = entries[f"cognition.{family}"]
            assert (entry.admission, entry.layer) == (row["status"], genomes[family].genome.layer), family
            checked += 1
    for family, row in index["operations"].items():
        if f"cognition.{family}" in entries:
            assert entries[f"cognition.{family}"].admission == lib.STRUCTURAL.get(row["raw_status"],
                                                                                  row["raw_status"])
            checked += 1
    assert checked >= 40
    assert lib.check() == []


def test_one_landlock_grant_path_covers_both_lineages_runtime_libraries():
    from greg import isolation
    assert not hasattr(isolation, "GLIBC_RUNTIME")
    pr158 = ("libc", "libm", "librt", "libdl", "libpthread", "libutil")
    assert {f"{name}.so*" for name in pr158} <= set(isolation.RUNTIME_LIBRARIES)
