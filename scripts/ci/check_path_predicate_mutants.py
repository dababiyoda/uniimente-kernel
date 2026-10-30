"""Every node predicate on the developmental path, and the build frontier read from them, fails a test when weakened.

The build frontier (`greg path --build`, greg/path.py build_status) counts a node from its predicate's
``structurally_met``. A predicate that could be weakened with no failing test would let the build look further
along than it is, so each predicate in greg/path.py PREDICATES has at least one weakening mutant here, and
greg.path.mutation_guarded reads this list (parsed, never imported), counting a mutant only while it is live: its
text occurs once in its file, its replacement differs, and its named test is defined. That read shows a mutant is
listed and live; only a run of this gate shows it is caught. The rest guard the build frontier itself: structural
evidence must never set ``met`` or join ``achieved``, the acceptance frontier says "final step" only when its node
is built, and the liveness read itself.

Each mutant runs in a scratch copy of the repository, never the checkout, under ``python -B`` with
PYTHONDONTWRITEBYTECODE=1 and every ``__pycache__`` purged first, so no bytecode left by the checkout or by an
earlier mutant can run in place of the mutated source. The named tests must pass unmutated first; a mutant counts
as caught only when its named test fails, never on an import or collection error.
"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
# (name, node whose predicate it weakens or None for the build frontier, file, old, new, test that must fail).
# Plain literals only: greg.path.mutation_guarded reads this list with ast.literal_eval.
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
     '        if not defined:\n',
     '        if False:\n',
     "tests/unit/test_path_build_frontier.py::test_a_stale_no_op_or_untested_mutant_guards_nothing"),
    # WU01-F3: a gate whose MUTANTS is a literal but not a list reads as nothing; it never crashes greg path --build.
    ("an unhashable literal crashes the gate read", None, "greg/path.py",
     '            except (ValueError, TypeError, MemoryError, RecursionError):',
     '            except ValueError:',
     "tests/unit/test_path_build_frontier.py::test_a_malformed_gate_guards_nothing_and_never_crashes_the_cli"),
    ("a literal that is not a list is read as the list", None, "greg/path.py",
     '            return list(mutants) if isinstance(mutants, (list, tuple)) else []\n',
     '            return list(mutants)\n',
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
]


def coverage_problems() -> list:
    """Every node with a ledger predicate has a mutant here, and every named node has a predicate."""
    nodes = {n["id"]: n for n in json.loads((ROOT / "greg/path.json").read_text())["nodes"]}
    with_predicate = {i for i, n in nodes.items() if n.get("predicate")}
    named = {m[1] for m in MUTANTS if m[1] is not None}
    return ([f"no mutant weakens {i}'s predicate" for i in sorted(with_predicate - named)]
            + [f"{i} has no predicate to weaken" for i in sorted(named - with_predicate)])


def purge_bytecode(repo: Path) -> None:
    for directory in [d for d in repo.rglob("__pycache__") if d.is_dir()]:
        shutil.rmtree(directory)


def pytest(repo: Path, *nodes: str) -> subprocess.CompletedProcess:
    purge_bytecode(repo)
    return subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *nodes],
                          cwd=repo, env={**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"},
                          capture_output=True, text=True, timeout=600)


def main() -> int:
    problems = coverage_problems()
    for problem in problems:
        print("UNCOVERED", problem)
    invalid, caught_count = len(problems), 0
    with tempfile.TemporaryDirectory(prefix="greg-path-predicate-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        baseline = pytest(repo, *sorted({m[5] for m in MUTANTS}))
        if baseline.returncode != 0:
            print("BASELINE_FAILS: the named tests must pass before any mutant can count as caught")
            print(baseline.stdout[-4000:])
            return 1
        for name, _node, relative, old, new, test in MUTANTS:
            path = repo / relative
            original = path.read_text()
            if original.count(old) != 1:
                print("STALE", name)
                invalid += 1
                continue
            if new == old:                                  # a no-op weakens nothing; it can never be caught
                print("NO_OP", name)
                invalid += 1
                continue
            path.write_text(original.replace(old, new))
            try:
                run = pytest(repo, test)
            finally:
                path.write_text(original)
            caught = (run.returncode == 1 and f"FAILED {test}" in run.stdout
                      and "ERROR collecting" not in run.stdout and "error" not in run.stdout.splitlines()[-1])
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name)
            invalid += not caught
            caught_count += caught
    print(f"{caught_count}/{len(MUTANTS)} caught")
    return int(bool(invalid))


if __name__ == "__main__":
    raise SystemExit(main())
