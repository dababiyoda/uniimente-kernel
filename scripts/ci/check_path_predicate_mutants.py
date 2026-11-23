"""Every node predicate on the developmental path, and the build frontier read from them, fails a test when weakened.

The build frontier (`greg path --build`, greg/path.py build_status) counts a node from its predicate's
``structurally_met``. A predicate that could be weakened with no failing test would let the build look further
along than it is, so each predicate in greg/path.py PREDICATES has at least one weakening mutant here.
greg.path.mutation_guarded reads this list (parsed, never imported) and counts a mutant only while it is live: its
text occurs once in its file, inside its node's predicate (or a function that predicate calls) in greg/path.py, its
replacement differs, and its named test is defined. This gate runs exactly that read, never a list of its own, so
what the build frontier counts and what runs here cannot differ (review WU01-ATK-2). A mutant the read would not
count fails the gate as NOT_LIVE and is not run. The read shows a mutant is listed and live; only a run of this gate
shows it is caught. The rest guard the build frontier itself: structural evidence must never set ``met`` or join
``achieved``, the acceptance frontier says "final step" only when its node is built, the liveness read, and this
gate's own rule for what counts as caught.

Each mutant runs in a scratch copy of the repository, never the checkout, under ``python -B`` with
PYTHONDONTWRITEBYTECODE=1 and every ``__pycache__`` purged first, so no bytecode left by the checkout or by an
earlier mutant can run in place of the mutated source. The named tests must pass unmutated first. A mutant counts
as caught only when its named test fails on behaviour (review WU01-ATK-1): a mutated module that does not import
is INVALID and never run, and a test that fails on a syntax or import error (raised by a module it loads lazily,
after collection) is INVALID, never caught.
"""
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from greg import path as devpath  # noqa: E402  (the one reader of the list below)

# (name, node whose predicate it weakens or None for the build frontier, file, old, new, test that must fail).
# Plain literals only, bound once and named nowhere else in this file: main() runs the list greg.path reads
# (greg.path._gate_mutants), and that read is empty for a gate that names its list twice.
MUTANTS = [
    ("N1 counts a closure missing VEPMC conditions", "N1", "greg/path.py",
     '    counted = [r["mission_id"] for r in rows if r["counts"]]\n',
     '    counted = [r["mission_id"] for r in rows]\n',
     "tests/unit/test_path_build_frontier.py::test_n1_counts_only_a_closure_that_meets_all_nine_conditions"),
    ("N2 counts a builtin capability as a novel one", "N2", "greg/path.py",
     '                and data.get("capability_id") not in BUILTINS and mid in counted\n',
     '                and mid in counted\n',
     "tests/unit/test_developmental_inheritance.py::test_structural_closures_cannot_advance_the_external_primary_gate"),
    ("N3 counts a payment that was never reconciled", "N3", "greg/path.py",
     '        if not (observed and observed[-1]["passed"]):\n            missing.append("payment_reconciled")\n',
     '        if False:\n            missing.append("payment_reconciled")\n',
     "tests/unit/test_greg_business_case.py::test_n3_refuses_a_case_where_greg_acted_outward_or_a_person_never_did"),
    ("N4 counts a procedure the trend refused", "N4", "greg/path.py",
     '        missing = list(p.get("why_not", [])) + [f"sop_run_not_{c}" for c in off_body]\n',
     '        missing = [f"sop_run_not_{c}" for c in off_body]\n',
     "tests/unit/test_greg_sop_compounding.py::"
     "test_a_ratified_procedure_runs_without_a_model_or_an_approval_stop_and_closes_n4"),
    ("N6 counts a person's step closed without observed evidence", "N6", "greg/path.py",
     '            if not any(withdrawn.get(e.payload["request_id"], "").startswith(OBSERVED)'
     ' for e in by_step.get(step, [])):\n',
     '            if not by_step.get(step, []):\n',
     "tests/unit/test_greg_shared_work.py::test_n6_refuses_crafted_histories"),
    ("N7 counts a transplant that was neither faster nor cheaper", "N7", "greg/path.py",
     '    proven = [t for t in moved if t["faster_or_cheaper"]]\n',
     '    proven = list(moved)\n',
     "tests/unit/test_path_build_frontier.py::test_n7_needs_a_transplant_that_was_faster_or_cheaper"),
    ("N7 counts a venture with no surplus to reinvest", "N7", "greg/path.py",
     '              and venture_books.reinvestable(b)]\n',
     ']\n',
     "tests/unit/test_greg_venture_books.py::test_n7_needs_surplus_in_the_venture_the_capability_moved_into"),
    ("a structural closure sets met", None, "greg/path.py",
     '    met = bool(structural and passed)\n',
     '    met = bool(structural)\n',
     "tests/unit/test_path_build_frontier.py::test_test_key_closures_move_only_the_build_frontier"),
    ("a structural node joins achieved", None, "greg/path.py",
     '            passed = measured["met"]\n',
     '            passed = measured["structurally_met"]\n',
     "tests/unit/test_path_build_frontier.py::test_test_key_closures_move_only_the_build_frontier"),
    ("a node without a predicate counts as built", None, "greg/path.py",
     '        elif not node.get("predicate"):\n            status = NO_PREDICATE\n',
     '        elif not node.get("predicate"):\n            status = STRUCTURALLY_BUILT\n',
     "tests/unit/test_path_build_frontier.py::test_a_node_without_a_predicate_stops_the_build"),
    ("a node built past the frontier is counted", None, "greg/path.py",
     '        if frontier is None and status == STRUCTURALLY_BUILT:\n',
     '        if status == STRUCTURALLY_BUILT:\n',
     "tests/unit/test_path_build_frontier.py::test_a_node_without_a_predicate_stops_the_build"),
    ("an unmeasured predicate node counts as built", None, "greg/path.py",
     '            status = STRUCTURALLY_BUILT if measured.get("structurally_met") else BUILD_OPEN\n',
     '            status = STRUCTURALLY_BUILT\n',
     "tests/unit/test_path_build_frontier.py::test_a_fresh_body_has_both_frontiers_at_n1_and_the_cli_prints_them"),
    ("the build depth counts an unguarded node", None, "greg/path.py",
     '        if not (node.get("predicate") and row["counted"] and row["mutation_guarded"]):\n',
     '        if not (node.get("predicate") and row["counted"]):\n',
     "tests/unit/test_path_build_frontier.py::test_the_build_depth_counts_only_mutation_guarded_nodes"),
    ("every node reads as guarded whatever the gate lists", None, "greg/path.py",
     '    return {m[1] for m, why in _mutant_liveness(Path(gate or MUTANT_GATE)) if not why and m[1] is not None}\n',
     '    return {"N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8"}\n',
     "tests/unit/test_path_build_frontier.py::test_mutation_guarded_reads_the_gate_and_covers_every_node_predicate"),
    # Review of 2026-10-30 (WU01-F1, F1): a listed mutant guards its node only while it can still run as written.
    ("a stale mutant still guards its node", None, "greg/path.py",
     '        if found is not None and found != 1:\n',
     '        if False:\n',
     "tests/unit/test_path_build_frontier.py::test_a_stale_no_op_or_untested_mutant_guards_nothing"),
    ("a no-op mutant still guards its node", None, "greg/path.py",
     '        if new == old:\n            why.append("no-op',
     '        if False:\n            why.append("no-op',
     "tests/unit/test_path_build_frontier.py::test_a_stale_no_op_or_untested_mutant_guards_nothing"),
    ("a mutant naming no test still guards its node", None, "greg/path.py",
     '        if not _test_defined(root, test):\n',
     '        if False:\n',
     "tests/unit/test_path_build_frontier.py::test_a_stale_no_op_or_untested_mutant_guards_nothing"),
    # WU01-F3: a gate whose MUTANTS is a literal but not a list reads as nothing; it never crashes greg path --build.
    ("an unhashable literal crashes the gate read", None, "greg/path.py",
     '    except (ValueError, TypeError, MemoryError, RecursionError):',
     '    except ValueError:',
     "tests/unit/test_path_build_frontier.py::test_a_malformed_gate_guards_nothing_and_never_crashes_the_cli"),
    ("a literal that is not a list is read as the list", None, "greg/path.py",
     '    return list(mutants) if isinstance(mutants, (list, tuple)) else []\n',
     '    return list(mutants)\n',
     "tests/unit/test_path_build_frontier.py::test_a_malformed_gate_guards_nothing_and_never_crashes_the_cli"),
    # WU01-F2: the acceptance frontier says "final step" only when its node is built.
    ("the acceptance status ignores the build", None, "greg/path.py",
     '"status": ACCEPTANCE_STATUS[by_id[active["id"]]["build"]],',
     '"status": ACCEPTANCE_PENDING,',
     "tests/unit/test_path_build_frontier.py::test_the_acceptance_status_follows_the_acceptance_nodes_build"),
    # WU01-F4, F3: a repository node is built only when its attestation says ACHIEVED.
    ("a repository node counts as built whatever its attestation", None, "greg/path.py",
     '            status = STRUCTURALLY_BUILT if node["attested"].startswith("ACHIEVED") else BUILD_OPEN\n',
     '            status = STRUCTURALLY_BUILT\n',
     "tests/unit/test_path_build_frontier.py::test_a_repository_node_not_attested_achieved_stops_the_build"),
    # WU01-ATK-2 (a): the read is the list the gate runs, so a gate that names its list again reads as nothing.
    ("a gate that names its list again is still read", None, "greg/path.py",
     '    for node in ast.walk(tree):\n        if ((isinstance(node, ast.Name) and node.id == "MUTANTS"',
     '    for node in []:\n        if ((isinstance(node, ast.Name) and node.id == "MUTANTS"',
     "tests/unit/test_path_build_frontier.py::test_a_gate_that_could_run_another_list_guards_nothing"),
    ("the gate runs its own list, not the one the build frontier reads", None,
     "scripts/ci/check_path_predicate_mutants.py",
     '    liveness = devpath._mutant_liveness(gate)\n',
     '    liveness = [(m, []) for m in MUTANTS]\n',
     "tests/unit/test_path_build_frontier.py::test_mutation_guarded_reads_the_gate_and_covers_every_node_predicate"),
    ("the gate runs a mutant the build frontier would not count", None, "scripts/ci/check_path_predicate_mutants.py",
     '    live = [m for m, why in liveness if not why]\n',
     '    live = [m for m, why in liveness]\n',
     "tests/unit/test_path_build_frontier.py::test_the_gate_runs_only_what_the_build_frontier_counts"),
    # WU01-ATK-2 (b): a node-tagged mutant guards its node only from inside that node's predicate.
    ("a mutant off its node's predicate still guards it", None, "greg/path.py",
     '        if node is not None and found == 1:\n',
     '        if False:\n',
     "tests/unit/test_path_build_frontier.py::test_a_mutant_off_its_nodes_predicate_guards_nothing"),
    ("a mutant in another file guards by line number", None, "greg/path.py",
     '            on_source = (root / relative).resolve() == (root / PREDICATE_SOURCE).resolve()\n',
     '            on_source = True\n',
     "tests/unit/test_path_build_frontier.py::test_a_mutant_off_its_nodes_predicate_guards_nothing"),
    ("a predicate's helpers are not part of it", None, "greg/path.py",
     '                todo += [n.id for n in ast.walk(functions[name])',
     '                todo += [n.id for n in []',
     "tests/unit/test_path_build_frontier.py::test_a_mutant_off_its_nodes_predicate_guards_nothing"),
    ("every function is part of every predicate", None, "greg/path.py",
     '        reached, todo = set(), [start] if start in functions else []\n',
     '        reached, todo = set(), list(functions)\n',
     "tests/unit/test_path_build_frontier.py::test_a_mutant_off_its_nodes_predicate_guards_nothing"),
    # WU01-ATK-2 (c): a named test is one pytest would collect, found in the parsed file, not in its text.
    ("a def in a docstring counts as a test", None, "greg/path.py",
     '        if not _test_defined(root, test):\n',
     '        if not re.search(rf"^\\s*def {re.escape(test.split(\'::\')[-1].split(\'[\')[0])}\\(",'
     ' (root / test.partition("::")[0]).read_text(), re.M):\n',
     "tests/unit/test_path_build_frontier.py::test_only_a_test_pytest_would_collect_makes_a_mutant_live"),
    ("a helper counts as a test", None, "greg/path.py",
     '    return bool(parts) and parts[-1].startswith("test") and any(',
     '    return bool(parts) and any(',
     "tests/unit/test_path_build_frontier.py::test_only_a_test_pytest_would_collect_makes_a_mutant_live"),
    ("a nested function counts as a test", None, "greg/path.py",
     '    found = [s for s in body if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))]\n',
     '    found = [s for s in ast.walk(tree) if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))]\n',
     "tests/unit/test_path_build_frontier.py::test_only_a_test_pytest_would_collect_makes_a_mutant_live"),
    # WU01-ATK-1: a mutant that breaks an import is never counted as caught, however lazily the test imports it.
    ("a mutated module that does not import is run and counted", None, "scripts/ci/check_path_predicate_mutants.py",
     '                broken = unloadable(repo, relative)\n',
     '                broken = None\n',
     "tests/unit/test_path_build_frontier.py::test_the_gate_never_counts_a_mutant_that_breaks_an_import_as_caught"),
    ("a test failing on an import error counts as a catch", None, "scripts/ci/check_path_predicate_mutants.py",
     '            failed_on_import = IMPORT_FAILURE.search(run.stdout)\n',
     '            failed_on_import = None\n',
     "tests/unit/test_path_build_frontier.py::test_the_gate_never_counts_a_mutant_that_breaks_an_import_as_caught"),
]

# A failure the test raised as one of these is an import that broke, not a predicate that was weakened.
IMPORT_FAILURE = re.compile(r"^E\s+(SyntaxError|IndentationError|TabError|ImportError|ModuleNotFoundError)\b", re.M)


def coverage_problems(root: Path, live: list) -> list:
    """Every node with a ledger predicate has a live mutant here."""
    nodes = json.loads((root / "greg/path.json").read_text())["nodes"]
    named = {m[1] for m in live if m[1] is not None}
    return [f"no live mutant weakens {n['id']}'s predicate" for n in nodes
            if n.get("predicate") and n["id"] not in named]


def purge_bytecode(repo: Path) -> None:
    for directory in [d for d in repo.rglob("__pycache__") if d.is_dir()]:
        shutil.rmtree(directory)


def environment(repo: Path) -> dict:
    return {**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"}


def pytest(repo: Path, *nodes: str) -> subprocess.CompletedProcess:
    purge_bytecode(repo)
    return subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *nodes],
                          cwd=repo, env=environment(repo), capture_output=True, text=True, timeout=600)


def unloadable(repo: Path, relative: str) -> str | None:
    """Why the mutated Python file does not import under its dotted name, or None when it imports."""
    if Path(relative).suffix != ".py":
        return None
    purge_bytecode(repo)
    module = ".".join(Path(relative).with_suffix("").parts)
    run = subprocess.run([sys.executable, "-B", "-c", f"import importlib; importlib.import_module({module!r})"],
                         cwd=repo, env=environment(repo), capture_output=True, text=True, timeout=120)
    return None if run.returncode == 0 else (run.stderr.strip().splitlines() or [f"exit {run.returncode}"])[-1]


def main() -> int:
    gate = ROOT / "scripts" / "ci" / Path(__file__).name
    # The list the build frontier reads, and the only list run here.
    liveness = devpath._mutant_liveness(gate)
    if not liveness:
        print("UNREADABLE: greg.path reads no mutants from", gate)
        return 1
    live = [m for m, why in liveness if not why]
    for name, reason in devpath.mutant_problems(gate):
        print("NOT_LIVE", f"{name}: {reason}")
    problems = coverage_problems(ROOT, live)
    for problem in problems:
        print("UNCOVERED", problem)
    invalid, caught_count = len(problems) + len(liveness) - len(live), 0
    if not live:
        print(f"0/{len(liveness)} caught")
        return 1
    with tempfile.TemporaryDirectory(prefix="greg-path-predicate-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        baseline = pytest(repo, *sorted({m[5] for m in live}))
        if baseline.returncode != 0:
            print("BASELINE_FAILS: the named tests must pass before any mutant can count as caught")
            print(baseline.stdout[-4000:])
            return 1
        for name, _node, relative, old, new, test in live:
            path = repo / relative
            original = path.read_text()
            if original.count(old) != 1:                # changed since the read: never run a mutant blind
                print("STALE", name)
                invalid += 1
                continue
            path.write_text(original.replace(old, new))
            try:
                broken = unloadable(repo, relative)
                run = None if broken else pytest(repo, test)
            finally:
                path.write_text(original)
            if broken:
                print("INVALID", f"{name}: the mutated module does not import ({broken})")
                invalid += 1
                continue
            failed_on_import = IMPORT_FAILURE.search(run.stdout)
            last = (run.stdout.strip().splitlines() or ["error"])[-1]
            caught = (run.returncode == 1 and f"FAILED {test}" in run.stdout and "ERROR collecting" not in run.stdout
                      and "error" not in last and not failed_on_import)
            if failed_on_import:
                print("INVALID", f"{name}: its test failed on {failed_on_import.group(1)}, not on behaviour")
            else:
                print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name)
            invalid += not caught
            caught_count += caught
    print(f"{caught_count}/{len(liveness)} caught")
    return int(bool(invalid))


if __name__ == "__main__":
    raise SystemExit(main())
