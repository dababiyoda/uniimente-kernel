"""A check is decided over the whole output its receipt kept, and only over that (directive 2026-10-22, VI and VIII).

    python scripts/ci/check_whole_output_mutants.py

Each mutant removes one safeguard of greg/missions.py ``judge_receipt`` and its callers (engine sensor, refusal
watch, appraiser re-derivation and preconditions, Goal Gravity), of the receipt bound it reads, or of the rule that
a check the evidence could not decide is neither pursued nor certified as failed (engine and appraiser). The named test
must fail for every mutant. Mutants are applied to a scratch copy of the repository, never to the working tree.
Exit status 1 if any mutant survives or no longer applies.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
T = "tests/unit/test_greg_whole_output_judgment.py::"
U = "tests/unit/test_greg_unmeasured_not_failed.py::"
MUTANTS = [
    ("a check the prefix cannot decide is never read over the whole", "greg/missions.py",
     "    if verdict != INSUFFICIENT or record is None:\n        return verdict, detail",
     "    if True:\n        return verdict, detail",
     T + "test_a_required_phrase_past_16_kib_closes_the_mission_without_asking_and_is_verified"),
    ("a foreign artifact is read as the receipt's own output", "greg/missions.py",
     '    if bounded(whole) != result.get("output"):', "    if False:",
     T + "test_damaged_or_foreign_evidence_never_decides"),
    ("a whole read from the store still counts a list at the limit as cut", "greg/missions.py",
     "    partial = not whole and isinstance(value, list)", "    partial = isinstance(value, list)",
     T + "test_over_a_kept_whole_the_verdict_is_the_verdict_on_the_value_uncut"),
    ("an item past the limit of a whole list is unknown, not absent", "greg/missions.py",
     "        elif not whole and isinstance(value, list) and part.isdigit()",
     "        elif isinstance(value, list) and part.isdigit()",
     T + "test_over_a_kept_whole_the_verdict_is_the_verdict_on_the_value_uncut"),
    ("a declared-incomplete output is judged whole once read from the store", "greg/missions.py",
     '    declared = isinstance(output, dict) and output.get("complete") is False and path != "complete"',
     '    declared = not whole and isinstance(output, dict) and output.get("complete") is False and path != "complete"',
     T + "test_a_declared_incomplete_output_stays_monotone_over_its_whole"),
    ("the engine judges its sensor by the prefix only", "greg/missions.py",
     '"output_artifact": outcome.output_artifact}, self.artifact_root)\n                if detail.startswith',
     '"output_artifact": outcome.output_artifact}, None)\n                if detail.startswith',
     T + "test_a_required_phrase_past_16_kib_closes_the_mission_without_asking_and_is_verified"),
    ("the refusal watch judges a decline by the prefix only", "greg/missions.py",
     '"output_artifact": outcome.output_artifact}, self.artifact_root)\n        # Evidence that cannot decide',
     '"output_artifact": outcome.output_artifact}, None)\n        # Evidence that cannot decide',
     T + "test_a_refusal_written_past_16_kib_of_a_note_is_honored"),
    ("the outcome drops the receipt's artifact record", "greg/authority.py",
     '                                 output_artifact=result.get("output_artifact"), **base)', "**base)",
     T + "test_a_required_phrase_past_16_kib_closes_the_mission_without_asking_and_is_verified"),
    ("the appraiser re-derives a closure from the prefix only", "greg/appraisal.py",
     'verdict, detail = judge_receipt(check["predicate"], receipt.payload["result"], artifacts)',
     'verdict, detail = judge_receipt(check["predicate"], receipt.payload["result"], None)',
     T + "test_a_required_phrase_past_16_kib_closes_the_mission_without_asking_and_is_verified"),
    ("the appraiser checks a precondition by the prefix only", "greg/appraisal.py",
     'predicates[check_id], receipt.payload["result"], artifacts)[0])',
     'predicates[check_id], receipt.payload["result"], None)[0])',
     T + "test_a_precondition_decided_over_the_whole_gates_the_strategy_and_the_appraiser_agrees"),
    ("Goal Gravity recomputes a long observation from the prefix only", "greg/goal_gravity.py",
     'value, _ = evaluate_receipt(check["predicate"], receipt.payload.get("result", {}), artifacts)',
     'value, _ = evaluate_receipt(check["predicate"], receipt.payload.get("result", {}), None)',
     T + "test_goal_gravity_reads_a_long_observation_as_the_engine_decided_it"),
    ("a passing check's reading resets the sensor-failure streak", "greg/missions.py",
     "                if obs[\"check_id\"] not in errors:\n                    continue\n",
     "                if obs[\"check_id\"] not in errors:\n                    break\n",
     T + "test_one_unmeasurable_check_beside_a_passing_one_still_reaches_the_founder"),
    ("a lone surrogate past the cut fails the action", "greg/authority.py",
     '    return value.encode("utf-8", "surrogatepass")', "    return value.encode()",
     T + "test_a_lone_surrogate_past_the_cut_no_longer_fails_the_action_and_is_judged"),
    # a check the evidence could not decide is neither pursued nor certified as failed (review of #196, J1 and J2)
    ("an unmeasured check is pursued beside a measured failure", "greg/missions.py",
     "        return self._pursue(m, now, failing - errors, evidence)",
     "        return self._pursue(m, now, failing, evidence)",
     U + "test_an_unmeasured_check_is_not_pursued_beside_a_measured_failure"),
    ("a precondition the observation could not measure is taken as met", "greg/missions.py",
     '            if set(s.get("requires", [])) & (failing | unmeasured):',
     '            if set(s.get("requires", [])) & failing:',
     U + "test_a_strategy_requiring_an_unmeasured_check_stays_held"),
    ("the appraiser reads undecided receipt bytes as the claimed failure", "greg/appraisal.py",
     "            if verdict == INSUFFICIENT:\n                # Bytes that cannot decide",
     "            if False:\n                # Bytes that cannot decide",
     U + "test_the_appraiser_does_not_certify_a_failure_its_receipt_cannot_decide"),
    ("the appraiser reads an undecided re-reading of the world as a measurement", "greg/appraisal.py",
     "                    now_ok = None if now_verdict == INSUFFICIENT else now_verdict == TRUE",
     "                    now_ok = now_verdict == TRUE",
     U + "test_an_undecided_re_reading_of_the_world_is_not_a_reobserved_failure"),
]


def main() -> int:
    bad = 0
    with tempfile.TemporaryDirectory(prefix="greg-whole-output-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        for name, relative, old, new, node in MUTANTS:
            path = repo / relative
            original = path.read_text(encoding="utf-8")
            if original.count(old) != 1:
                print("STALE   ", name)
                bad += 1
                continue
            path.write_text(original.replace(old, new), encoding="utf-8")
            try:
                run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", node],
                                     cwd=repo, env={**os.environ, "PYTHONPATH": str(repo)},
                                     capture_output=True, text=True, timeout=600)
            finally:
                path.write_text(original, encoding="utf-8")
            caught = run.returncode == 1 and "FAILED " in run.stdout and "ERROR collecting" not in run.stdout
            print("CAUGHT  " if caught else "SURVIVED", name)
            bad += not caught
    print(f"{len(MUTANTS)} mutants, {bad} survived or stale")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
