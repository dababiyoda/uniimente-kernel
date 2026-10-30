"""A standing approval must fall on failure evidence, and the earned-autonomy fold must stay at or below its ceiling.

Each mutant removes one safeguard of greg/autonomy.py or its body hook in a scratch copy of the tree; a behavioral test
must then fail. Bytecode is never written and every __pycache__ is purged before each run, so no mutant is judged
against a stale compiled module.
"""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[2]
TESTS = "tests/unit/test_greg_standing_approval_regression.py"
INEFFECTIVE = f"{TESTS}::test_an_ineffective_run_regresses_its_standing_approval_and_the_scope_is_asked_again"
REFUTED = f"{TESTS}::test_a_refuted_closure_regresses_the_approval_its_runs_used"
FRESH = f"{TESTS}::test_an_approval_given_after_the_regression_stands_until_its_own_run_fails"
TWICE = f"{TESTS}::test_a_run_named_by_two_failures_is_regressed_once"
CRASH = f"{TESTS}::test_regression_finishes_after_a_crash_between_its_two_records"
CLIMB = f"{TESTS}::test_the_earned_level_climbs_to_supervised_canary_and_no_higher_and_grants_nothing"
FRESH_REFUTED = f"{TESTS}::test_an_approval_given_after_a_refuted_regression_stands_until_its_own_run_fails"
WINDOW = f"{TESTS}::test_a_refutation_regresses_only_the_approvals_of_runs_inside_its_closure_window"
DROP = f"{TESTS}::test_an_ineffective_in_cone_run_drops_the_tuple_to_shadow"
WILSON = f"{TESTS}::test_supervised_canary_also_needs_the_wilson_bound_after_earlier_refutations"
ORDER = f"{TESTS}::test_runs_are_ordered_by_where_they_ran_not_by_when_their_verdicts_landed"
COST = f"{TESTS}::test_the_failure_fold_the_body_runs_every_tick_grows_n_log_n_with_a_standing_history"
RECONCILED = f"{TESTS}::test_a_run_the_founder_reconciled_as_executed_and_proven_ineffective_regresses_its_approval"
RECONCILED_OK = f"{TESTS}::test_a_reconciled_run_that_worked_keeps_its_standing_approval"
COMPENSATION = f"{TESTS}::test_compensations_are_counted_against_the_run_tuple_and_judge_nothing"
UNMET = f"{TESTS}::test_an_effective_run_closed_by_an_unmet_closure_stays_unappraised"
WINDOW_RUNS = "for run in ran[bisect_right(ats, start):bisect_left(ats, closure)]:"
MUTANTS = [
    ("body hook removed", "greg/body.py",
     "        autonomy.regress(self.journal, self.engine.book, now)"
     "   # failure evidence withdraws a standing approval first\n", "", INEFFECTIVE),
    ("ineffective evidence ignored", "greg/autonomy.py",
     'if p.get("verdict") == "ineffective" and run is not None', 'if False and run is not None', INEFFECTIVE),
    ("refuted closures ignored", "greg/autonomy.py", 'if verdict != "REFUTED" or mid not in own:', "if True:",
     REFUTED),
    ("withdrawal does not void", "greg/autonomy.py", '"voids_approval": True,', '"voids_approval": False,',
     INEFFECTIVE),
    ("approvals asked after the failed run withdrawn too", "greg/autonomy.py",
     'or not pos.get(fact_id("decision.requested", rid), ran_at) < ran_at)', "or False)", FRESH),
    ("one rid regressed twice in a call", "greg/autonomy.py", " or rid in handled\n", "\n", TWICE),
    ("retained regression not reused after a crash", "greg/autonomy.py",
     'journal.retained("autonomy.regressed", key) or ', "", CRASH),
    ("evidence lifts a tuple above the earned ceiling", "greg/autonomy.py",
     '        return "SUPERVISED_CANARY"\n', '        return "BOUNDED_AUTONOMY"\n', CLIMB),
    ("a refuted run does not drop the level", "greg/autonomy.py",
     'SEVERE = ("refuted", "ineffective")', 'SEVERE = ("ineffective",)', CLIMB),
    # review round 1 (WU09-F1, F2, R-1, R-2)
    ("a refuted window reaches runs before its start", "greg/autonomy.py",
     WINDOW_RUNS, "for run in ran[:bisect_left(ats, closure)]:", WINDOW),
    ("a refuted window reaches runs after its closure", "greg/autonomy.py",
     WINDOW_RUNS, "for run in ran[bisect_right(ats, start):]:", FRESH_REFUTED),
    ("an ineffective run does not drop the level", "greg/autonomy.py",
     'SEVERE = ("refuted", "ineffective")', 'SEVERE = ("refuted",)', DROP),
    ("canary ignores the Wilson bound", "greg/autonomy.py",
     'if recent >= CANARY_MIN_VERIFIED and evidence["wilson_lower"] >= CANARY_MIN_WILSON:',
     "if recent >= CANARY_MIN_VERIFIED:", WILSON),
    ("a verified run placed where its verdict landed", "greg/autonomy.py",
     'r["outcomes"].append((at, kind))  # the run',
     'r["outcomes"].append((judged[4] if judged else at, kind))  # the run', ORDER),
    ("every run rescanned for each refuted window", "greg/autonomy.py",
     WINDOW_RUNS, "for run in [r for a, r in zip(ats, ran) if start < a < closure]:", COST),
    # review round 2 (WU09-ATK-1, ATK-2, TF-1)
    ("a founder-reconciled run is never judged", "greg/autonomy.py",
     "    out += _reconciled_ineffective(journal, pos, runs, own)\n", "", RECONCILED),
    ("a passing observation does not decide a reconciled run", "greg/autonomy.py",
     '                if o.get("passed"):\n                    break\n', "", RECONCILED_OK),
    ("the report drops failure evidence naming a reconciled run", "greg/autonomy.py",
     "            if kind is not None:\n", "            if False:\n", RECONCILED),
    ("every compensation counted as settled", "greg/autonomy.py",
     'settled = closed.get((p.get("mission_id"), p.get("action_id"))) in ("DONE", "FOUNDER_DECIDED")',
     "settled = True", COMPENSATION),
    ("a later closure judges a run made before its window opened", "greg/autonomy.py",
     "judged = windows[i] if i < len(windows) and windows[i][2] < at else None",
     "judged = windows[i] if i < len(windows) else None", ORDER),
    ("a verified-unmet closure judges its runs verified", "greg/autonomy.py",
     'kind = "verified" if judged is not None and judged[1] == "VERIFIED" else None',
     'kind = "verified" if judged is not None and judged[1] in ("VERIFIED", "VERIFIED_UNMET") else None', UNMET),
]


def purge(repo: Path):
    for cache in repo.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def pytest(repo: Path, node: str):
    purge(repo)
    return subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", node],
                          cwd=repo, env={**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"},
                          capture_output=True, text=True, timeout=600)


def main():
    invalid = 0
    with tempfile.TemporaryDirectory(prefix="greg-standing-approval-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        baseline = pytest(repo, TESTS)
        if baseline.returncode != 0:
            print("BASELINE_FAILS", baseline.stdout[-2000:])
            return 1
        print("BASELINE_PASSES")
        for name, relative, old, new, node in MUTANTS:
            path = repo / relative
            original = path.read_text()
            if original.count(old) != 1:
                print("STALE", name); invalid += 1; continue
            path.write_text(original.replace(old, new))
            try:
                run = pytest(repo, node)
            finally:
                path.write_text(original)
            caught = (run.returncode == 1 and f"FAILED {TESTS}::" in run.stdout
                      and "ERROR collecting" not in run.stdout)
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name)
            invalid += not caught
    print(f"{len(MUTANTS) - invalid}/{len(MUTANTS)} caught")
    return int(bool(invalid))


if __name__ == "__main__":
    raise SystemExit(main())
