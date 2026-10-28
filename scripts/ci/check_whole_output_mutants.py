"""A check is decided over the whole output its receipt kept, and only over that (directive 2026-10-22, VI and VIII).

    python scripts/ci/check_whole_output_mutants.py

Each mutant removes one safeguard: of greg/missions.py ``judge_receipt`` and its callers (engine sensor, refusal
watch, appraiser re-derivation and preconditions, Goal Gravity); of the receipt bound it reads; of the rule that a
check the evidence could not decide is neither pursued nor certified as failed (engine and appraiser); of the judge's
limits on declared-incomplete outputs, on paths into a receipt's prefix record and on numbers that are not finite;
or of greg/pipeline.py's handoffs and inspection. The named test
must fail for every mutant. Mutants are applied to a scratch copy of the repository, never to the working tree.
Exit status 1 if any mutant survives or no longer applies.

Mutants run one after another in one copy, so no run may see another's bytecode. Python reuses a cached .pyc when
the source has the same size and the same whole-second mtime. Two mutants of one file with equal size deltas,
written within a second of each other, therefore ran the earlier mutant's code: CI reported the refusal-watch mutant
SURVIVED on c74360cf although its test fails on that mutant. A stale .pyc could as easily fail a test for a mutant
that does not break it. Each run writes no bytecode, and any cache a child process wrote (a confined worker gets a
clean environment) is removed first.
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
H = "tests/unit/test_greg_handoff_evidence.py::"
W = "tests/unit/test_greg_judge_incomplete_wrappers.py::"
MUTANTS = [
    ("a check the prefix cannot decide is never read over the whole", "greg/missions.py",
     "    if verdict != INSUFFICIENT or record is None:\n        return verdict, detail",
     "    if True:\n        return verdict, detail",
     T + "test_a_required_phrase_past_16_kib_closes_the_mission_without_asking_and_is_verified"),
    ("a foreign artifact is read as the receipt's own output", "greg/missions.py",
     '    if bounded(whole) != result.get("output"):', "    if False:",
     T + "test_damaged_or_foreign_evidence_never_decides"),
    ("a list at the limit read from the store is taken as all of it", "greg/missions.py",
     "    partial = isinstance(value, list) and len(value) == RECEIPT_LIST_LIMIT\n",
     "    partial = not whole and isinstance(value, list) and len(value) == RECEIPT_LIST_LIMIT\n",
     T + "test_a_list_at_the_limit_reads_the_same_kept_whole_or_re_read"),
    ("an item past a whole list at the limit reads as absent", "greg/missions.py",
     "        elif isinstance(value, list) and part.isdigit() and len(value) == RECEIPT_LIST_LIMIT:",
     "        elif not whole and isinstance(value, list) and part.isdigit() and len(value) == RECEIPT_LIST_LIMIT:",
     T + "test_a_list_at_the_limit_reads_the_same_kept_whole_or_re_read"),
    ("a declared-incomplete output is judged whole once read from the store", "greg/missions.py",
     "    declared, vouched = _declared(output, path)\n",
     "    declared, vouched = _declared(output, path) if not whole else (False, False)\n",
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
     "        return self._pursue(m, now, failing - self.inconclusive, evidence)",
     "        return self._pursue(m, now, failing, evidence)",
     U + "test_an_unmeasured_check_is_not_pursued_beside_a_measured_failure"),
    ("a check whose sensor the capability refused is no longer pursued", "greg/missions.py",
     "        return self._pursue(m, now, failing - self.inconclusive, evidence)",
     "        return self._pursue(m, now, failing - errors, evidence)",
     "tests/integration/test_greg_adversarial_machine.py::"
     "test_a_more_profitable_offer_that_pressures_buyers_is_refused_and_the_plain_one_is_sold"),
    ("a precondition the observation could not measure is taken as met", "greg/missions.py",
     '            if set(s.get("requires", [])) & unproven:',
     '            if set(s.get("requires", [])) & failing:',
     U + "test_a_strategy_requiring_an_unmeasured_check_stays_held"),
    ("the appraiser reads undecided receipt bytes as the claimed failure", "greg/appraisal.py",
     "            elif verdict == INSUFFICIENT:\n                # Bytes that cannot decide",
     "            elif False:\n                # Bytes that cannot decide",
     U + "test_the_appraiser_does_not_certify_a_failure_its_receipt_cannot_decide"),
    ("the appraiser reads an undecided re-reading of the world as a measurement", "greg/appraisal.py",
     "                    now_ok = None if now_verdict == INSUFFICIENT or (now_verdict != TRUE and unanswered(output)) "
     "\\\n                        else now_verdict == TRUE",
     "                    now_ok = now_verdict == TRUE",
     U + "test_an_undecided_re_reading_of_the_world_is_not_a_reobserved_failure"),
    # a declared-incomplete output limits every verdict; a path never steps into a receipt's prefix record (J8, J9)
    ("a cut string of an incomplete output is judged as if complete", "greg/missions.py",
     '        if declared and not vouched and not (op == "count_gte" and verdict == TRUE):',
     "        if False:",
     W + "test_a_long_text_from_an_incomplete_observation_keeps_only_monotone_verdicts"),
    ("a field an incomplete output has not reached reads as absent", "greg/missions.py",
     "        if declared:       # a field the observation has not reached yet is not an absent field",
     "        if False:",
     W + "test_a_field_an_incomplete_observation_has_not_reached_is_not_absent"),
    ("a field the capability vouches for is no longer judged", "greg/missions.py",
     '            vouched = vouched and isinstance(node.get("decided"), list) and rest in node["decided"]',
     "            vouched = False",
     W + "test_a_complete_output_and_a_vouched_field_are_judged_as_before"),
    ("a path steps into the receipt's record of a cut string", "greg/missions.py",
     '        if not whole and _cut(value) and (recorded_cut or part == "prefix"):',
     "        if False:",
     W + "test_a_path_into_the_receipts_prefix_record_decides_nothing"),
    # review of #209: what else a verdict, a closure or an appraisal must not claim
    ("a signed value of another type crashes the tick over a whole text", "greg/missions.py",
     "    searchable = isinstance(value, list) or (isinstance(value, str) and isinstance(expected, str))",
     "    searchable = isinstance(value, (str, list))",
     T + "test_a_signed_value_of_another_type_fails_the_check_and_never_crashes_the_tick"),
    ("a signed value of another type crashes the tick over a cut text", "greg/missions.py",
     '        if op in ("contains", "not_contains") and not isinstance(expected, str):',
     "        if False:",
     T + "test_a_signed_value_of_another_type_fails_the_check_and_never_crashes_the_tick"),
    ("a member kept as a prefix is compared as its wrapper", "greg/missions.py",
     "    cut = None if whole else _cut(kept)", "    cut = None",
     T + "test_a_cut_below_the_judged_value_never_decides_as_its_wrapper"),
    ("a nested list at the limit is compared as all of it", "greg/missions.py",
     "        return False if False in pairs else None if (at_limit or None in pairs) else True",
     "        return False if False in pairs else None if None in pairs else True",
     T + "test_a_cut_below_the_judged_value_never_decides_as_its_wrapper"),
    ("a reading reused after a restart is judged on its prefix", "greg/authority.py",
     '                                 cost_usd=cost_usd, output_artifact=receipt.payload["result"].get("output_artifact"),',
     "                                 cost_usd=cost_usd,",
     T + "test_a_reading_reused_after_a_restart_keeps_the_whole_output_its_receipt_kept"),
    ("the appraiser re-derives a bind by artifact from the prefix", "greg/appraisal.py",
     '_set_path(params, edge["param"], bound_value(edge, result.get("output"), whole,',
     '_set_path(params, edge["param"], bound_value(edge, result.get("output"), None,',
     T + "test_the_appraiser_re_derives_a_bind_by_artifact_from_the_whole_output"),
    ("the failure closure names an abstaining check as measured", "greg/missions.py",
     '                unread = failing & (set(getattr(self, "sensor_errors", ())) | set(getattr(self, "unread", ())))',
     '                unread = failing & set(getattr(self, "sensor_errors", ()))',
     U + "test_an_abstaining_sensor_is_pursued_but_never_certified_as_failed"),
    ("the failure closure names a refused read as measured", "greg/missions.py",
     '                unread = failing & (set(getattr(self, "sensor_errors", ())) | set(getattr(self, "unread", ())))',
     '                unread = failing & set(getattr(self, "unread", ()))',
     U + "test_a_refused_sensor_is_never_named_a_measured_failure"),
    ("the appraiser reads an abstaining receipt as the claimed failure", "greg/appraisal.py",
     '            elif not passed and unanswered(receipt.payload["result"].get("output")):',
     "            elif False:",
     U + "test_the_appraiser_does_not_certify_a_failure_on_an_abstaining_receipt"),
    ("the appraiser reads an abstaining re-reading as the failure", "greg/appraisal.py",
     "now_verdict == INSUFFICIENT or (now_verdict != TRUE and unanswered(output))",
     "now_verdict == INSUFFICIENT",
     U + "test_the_appraiser_does_not_certify_a_failure_on_an_abstaining_receipt"),
    ("the sensor-failure streak counts readings, not rounds", "greg/missions.py",
     '                if obs.get("at") not in rounds or obs.get("at") is None:', "                if True:",
     U + "test_three_unmeasured_checks_are_one_round_not_three"),
    ("preparation dispatches a strategy whose precondition it saw failing", "greg/missions.py",
     '        unproven = failing | unmeasured | set(getattr(self, "observed_failing", ()))',
     "        unproven = failing | unmeasured",
     U + "test_preparation_holds_a_strategy_whose_precondition_is_observed_failing"),
    ("a record the sensor itself returned is refused as the receipt's own", "greg/missions.py",
     "    verdict, detail = judge(predicate, output, recorded_cut=record is not None)",
     "    verdict, detail = judge(predicate, output)",
     T + "test_a_check_on_a_record_another_receipt_kept_closes_and_is_verified"),
    ("the appraiser re-reads a fresh output as if a receipt had cut it", "greg/appraisal.py",
     '                    now_verdict, now_detail = judge(check["predicate"], output, whole=True)',
     '                    now_verdict, now_detail = judge(check["predicate"], output)',
     T + "test_a_check_on_a_record_another_receipt_kept_closes_and_is_verified"),
    ("a receipt that recorded a cut has its record read as data", "greg/missions.py",
     '        if not whole and _cut(value) and (recorded_cut or part == "prefix"):',
     '        if not whole and _cut(value) and part == "prefix":',
     W + "test_a_record_the_sensor_itself_returned_is_read_as_data"),
    # review of #196, J3, J4, J6: handoffs and numbers
    ("inspection drops the producer's incompleteness", "greg/pipeline.py",
     '        out["complete"] = False\n', "        pass\n",
     H + "test_an_inspected_value_keeps_its_producers_incompleteness"),
    ("incompleteness is read only at the top of the output", "greg/missions.py",
     "    for i in range(len(parts) + 1):\n        rest = ", "    for i in range(1):\n        rest = ",
     H + "test_incompleteness_declared_inside_an_output_limits_the_fields_below_it"),
    ("a handoff binds a value its receipt did not keep whole", "greg/pipeline.py",
     "            if held and observe is None:", "            if False:",
     H + "test_a_value_the_receipt_did_not_keep_whole_is_never_handed_on"),
    ("a number that is not finite reaches the ledger", "greg/authority.py",
     "    if isinstance(value, float) and not math.isfinite(value):", "    if False:",
     H + "test_a_number_that_is_not_finite_is_receipted_and_measures_nothing"),
    ("a number that is not finite is judged as a reading", "greg/missions.py",
     "    if (not whole and _non_finite(value)) or (isinstance(value, float) and value != value):", "    if False:",
     H + "test_a_number_that_is_not_finite_is_receipted_and_measures_nothing"),
    ("a NaN nested in a value is decided over the whole output", "greg/missions.py",
     "    if (not whole and _non_finite(kept)) or (isinstance(kept, float) and kept != kept):\n        return None",
     "    if not whole and _non_finite(kept):\n        return None",
     H + "test_a_nan_inside_a_value_is_no_reading_over_the_whole_output_either"),
    ("the failure closure drops a check the evidence could not decide", "greg/missions.py",
     "sorted(unread | unmeasured)} if unread | unmeasured else {}",
     "sorted(unread)} if unread else {}",
     U + "test_an_unmeasured_check_is_not_pursued_beside_a_measured_failure"),
    ("an undecided whole-output reading is called decided", "greg/missions.py",
     'how = "still undecided" if verdict == INSUFFICIENT else "decided"',
     'how = "decided"',
     H + "test_a_number_that_is_not_finite_is_receipted_and_measures_nothing"),
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
            for cache in list(repo.rglob("__pycache__")):
                shutil.rmtree(cache, ignore_errors=True)
            path.write_text(original.replace(old, new), encoding="utf-8")
            try:
                run = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", node],
                                     cwd=repo, env={**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"},
                                     capture_output=True, text=True, timeout=600)
            finally:
                path.write_text(original, encoding="utf-8")
            caught = run.returncode == 1 and "FAILED " in run.stdout and "ERROR collecting" not in run.stdout
            print("CAUGHT  " if caught else "SURVIVED", name)
            if not caught:                           # say why, so a survivor in CI can be diagnosed from its log
                print("\n".join("    " + line for line in (run.stdout + run.stderr).strip().splitlines()[-15:]))
            bad += not caught
    print(f"{len(MUTANTS)} mutants, {bad} survived or stale")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
