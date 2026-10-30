"""A check is decided over the whole output its receipt kept, and only over that (directive 2026-10-22, VI and VIII).

    python scripts/ci/check_whole_output_mutants.py

Each mutant removes one safeguard: of greg/missions.py ``judge_receipt`` and its callers (engine sensor, refusal
watch, appraiser re-derivation and preconditions, Goal Gravity); of the receipt bound it reads; of the rule that a
check the evidence could not decide is neither pursued nor certified as failed (engine and appraiser); of the judge's
limits on declared-incomplete outputs, on paths into a receipt's prefix record and on numbers that are not finite;
of greg/pipeline.py's handoffs and inspection; or of faithful text: one normalization form on both sides of every
comparison and in every field path, decoding without replacement, cut output declared cut and searched only where no
continuation can renormalize it, and files refused before they are buffered or read through a link swapped in
(greg/textform.py, greg/capabilities.py, greg/business_loop.py). The named test
must fail for every mutant. Mutants are applied to a scratch copy of the repository, never to the working tree.
Exit status 1 if any mutant survives or no longer applies.

Mutants run one after another in one copy, so no run may see another's bytecode. Python reuses a cached .pyc when
the source has the same size and the same whole-second mtime. Two mutants of one file with equal size deltas,
written within a second of each other, therefore ran the earlier mutant's code: CI reported the refusal-watch mutant
SURVIVED on c74360cf although its test fails on that mutant. A stale .pyc could as easily fail a test for a mutant
that does not break it. Each run writes no bytecode, any cache a child process wrote (a confined worker gets a clean
environment) is removed first, and every write is dated to its own whole second, earlier than any file the copy
started with, so a .pyc written for another version cannot match even if a process that outlived its run wrote it
after the purge. Each run's whole process group is killed when it ends, however it ends. This defends against caches
written in good faith by any process at any time; a test written to forge a cache could as easily rewrite the
sources, and no gate run in place stops it.

Verdicts come from pytest's own per-test reports, written by a small plugin outside the copy, never from its text:
a line a test prints, a colour code or a quieter summary cannot change one. A mutant is caught only when its own
named test fails, not as an expected failure, and only after that test passed on the unmutated copy, run alone
exactly as its mutants are: a test that already fails, skips, is expected to fail, or passes only after another
test, would otherwise read as catching every mutant aimed at it.
"""
from pathlib import Path
import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
T = "tests/unit/test_greg_whole_output_judgment.py::"
U = "tests/unit/test_greg_unmeasured_not_failed.py::"
H = "tests/unit/test_greg_handoff_evidence.py::"
W = "tests/unit/test_greg_judge_incomplete_wrappers.py::"
F = "tests/unit/test_greg_faithful_text.py::"
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
     "    declared, vouched, cut_sides = _declared(output, path)\n",
     "    declared, vouched, cut_sides = _declared(output, path) if not whole else (False, False, frozenset())\n",
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
    # faithful text evidence (tests/unit/test_greg_faithful_text.py): one normalization form, faithful decoding,
    # declared cuts, refusal before buffering
    ('text is compared in its code points, not as NFC', "greg/textform.py",
     'return unicodedata.normalize("NFC", text)',
     'return text',
     F + 'test_a_forbidden_name_in_another_normalization_form_is_found'),
    ('a kept prefix is searched past its last normalization boundary', "greg/missions.py",
     '            probe = _stable(text)\n',
     '            probe = text\n',
     F + 'test_a_prefix_ending_before_an_accent_no_longer_contains_the_bare_letter'),
    ('the stable part keeps the starter the rest may compose with', "greg/textform.py",
     '            return prefix[:i]\n    return ""',
     '            return prefix[:i + 1]\n    return ""',
     F + 'test_the_stable_part_of_a_prefix_starts_the_normalized_whole_whatever_follows'),
    ('a starter that composes backwards is taken as a boundary', "greg/textform.py",
     ' and not {ord(first), ord(char)} & backward',
     '',
     F + 'test_the_stable_part_of_a_prefix_starts_the_normalized_whole_whatever_follows'),
    ('a character whose decomposition starts with a mark is taken as a boundary', "greg/textform.py",
     'first = unicodedata.normalize("NFD", char)[0]',
     'first = char',
     F + 'test_the_stable_part_of_a_prefix_starts_the_normalized_whole_whatever_follows'),
    ('Hangul jamo are taken as boundaries', "greg/textform.py",
     'seconds = set(range(0x1161, 0x1176)) | set(range(0x11A8, 0x11C3))',
     'seconds = set()',
     F + 'test_the_stable_part_of_a_prefix_starts_the_normalized_whole_whatever_follows'),
    ('a long string equal as text is called different by its digest', "greg/missions.py",
     'return None if _canon(expected).startswith(_canon(_stable(cut["prefix"]))) else False',
     'return False',
     F + 'test_a_long_string_equal_as_text_is_never_called_different_by_its_digest'),
    ('a long string differing in its kept part is left undecided', "greg/missions.py",
     'return None if _canon(expected).startswith(_canon(_stable(cut["prefix"]))) else False',
     'return None',
     F + 'test_a_long_string_equal_as_text_is_never_called_different_by_its_digest'),
    ('a whole string is compared in its code points', "greg/missions.py",
     'return isinstance(expected, str) and _canon(kept) == _canon(expected)',
     'return kept == expected',
     F + 'test_a_forbidden_name_in_another_normalization_form_is_found'),
    ("two keys spelling one text decide an object's equality", "greg/missions.py",
     'return keys if len(keys) == len(mapping) else None',
     'return keys',
     F + 'test_two_keys_spelling_one_text_decide_nothing'),
    ('a whole text is searched in its code points', "greg/missions.py",
     '        value, expected = _canon(value), _canon(expected)',
     '        pass',
     F + 'test_a_forbidden_name_in_another_normalization_form_is_found'),
    ("an unreadable field's reason is not shown to the founder", "greg/missions.py",
     'return why if isinstance(why, str) else None',
     'return None',
     F + 'test_an_unreadable_contract_is_asked_about_not_certified'),
    ('UTF-8 holding NUL is read as text', "greg/capabilities.py",
     'if codec in ("utf-8", "utf-8-sig") and "\\x00" in text:',
     'if False:',
     F + 'test_an_unreadable_contract_is_asked_about_not_certified'),
    ('a byte-order mark is ignored', "greg/capabilities.py",
     'codec = next((name for mark, name in BYTE_ORDER_MARKS if data.startswith(mark)), "utf-8")',
     'codec = "utf-8"',
     F + 'test_a_forbidden_clause_in_a_utf16_contract_keeps_the_mission_open'),
    ('bytes are decoded with replacement characters', "greg/capabilities.py",
     'text = codecs.getincrementaldecoder(codec)().decode(data, final=not cut)',
     'text = data.decode(codec, errors="replace")',
     F + 'test_a_statement_in_another_encoding_is_not_reported_unmatched'),
    ('a character split by a cut is refused', "greg/capabilities.py",
     'decode(data, final=not cut)',
     'decode(data, final=True)',
     F + 'test_a_cut_stream_drops_only_a_split_character'),
    ('unreadable text is not declared incomplete', "greg/capabilities.py",
     '"text_unreadable": how, "complete": False, "decided": sorted([*out, "text_unreadable"])}\n\n\ndef bounded_read',
     '"text_unreadable": how}\n\n\ndef bounded_read',
     F + 'test_an_unreadable_contract_is_asked_about_not_certified'),
    ('an oversized file is read before its stated size is checked', "greg/capabilities.py",
     '        if info.st_size > MAX_READ_BYTES:\n            raise CapabilityError(refusal)\n',
     '',
     F + 'test_an_oversized_file_is_refused_before_it_is_read'),
    ('a file that misstates its size is read whole', "greg/capabilities.py",
     'data = stream.read(MAX_READ_BYTES + 1)',
     'data = stream.read()',
     F + 'test_a_file_that_misstates_its_size_is_read_no_further_than_the_ceiling'),
    ('a FIFO is read as a file', "greg/capabilities.py",
     '    if not stat.S_ISREG(info.st_mode):                  # checked on the descriptor, before Python wraps it\n'
     '        os.close(fd)\n'
     '        raise CapabilityError(f"{path.name} is not a regular file")\n',
     '',
     F + 'test_a_fifo_swapped_in_for_a_file_is_refused_without_blocking'),
    ('a directory where a file should be is read as a missing file', "greg/capabilities.py",
     '    if not path.exists():   # absence is a measurement of the world; a directory or FIFO there is a failed read',
     '    if not path.is_file():  # absence is a measurement of the world; a directory or FIFO there is a failed read',
     F + 'test_a_directory_or_fifo_where_a_file_was_expected_is_a_failed_read_not_an_absent_file'),
    ('the founder is not told that a checked path does not exist', "greg/missions.py",
     '        gone = "; the path does not exist" if isinstance(output, dict) and output.get("exists") is False else ""',
     '        gone = ""',
     F + 'test_a_check_on_a_missing_file_says_the_path_does_not_exist'),
    ('command output cut at the ceiling is vouched for', "greg/capabilities.py",
     'held += [name] if cut or text is None else []',
     'held += [name] if text is None else []',
     F + 'test_command_output_cut_or_unreadable_decides_only_what_more_could_not_undo'),
    ('a page cut by the DOM limit is vouched for', "greg/capabilities.py",
     '            if dom_cut or not whole]',
     '            if not whole]',
     F + 'test_a_page_cut_by_the_dom_limit_decides_only_what_more_could_not_undo'),
    ('a cut title is vouched for', "greg/capabilities.py",
     '("title", len(title) <= 300)',
     '("title", True)',
     F + 'test_a_page_longer_than_the_kept_text_decides_only_what_more_could_not_undo'),
    ('a fetched page is decoded with replacement characters', "greg/capabilities.py",
     '"trust": "untrusted-external-data", "egress": route}, body)',
     '"trust": "untrusted-external-data", "egress": route, "text": body.decode("utf-8", "replace")}, b"")',
     F + 'test_a_fetched_page_is_read_faithfully_or_not_at_all[utf16-unmarked]'),
    ('a case reference signed in one normalization form misses a statement in the other', "greg/business_loop.py",
     'wanted = canon(reference)',
     'wanted = reference',
     F + 'test_a_statement_in_another_encoding_is_not_reported_unmatched'),
    ('an oversized statement is read before it is refused', "greg/business_loop.py",
     'data = bounded_read(path, "statement exceeds read ceiling")',
     'data = path.read_bytes()',
     F + 'test_an_oversized_statement_is_refused_before_it_is_read'),
    # review of #228 (session_01Kucyfm2rRpECfxggpZqMes): its finding 5 and the safeguards it found unguarded, and the
    # fixes for findings 1, 3 and 4 and its suspicions
    ('a kept prefix is searched with the phrase in the form it was signed', "greg/missions.py",
     '            if _canon(expected) in _canon(probe):',
     '            if expected in _canon(probe):',
     F + 'test_a_kept_prefix_is_searched_in_either_form_of_the_phrase'),
    ('a statement row is matched in the form it was exported', "greg/business_loop.py",
     'if wanted not in canon(row.get(columns["reference"]) or ""):',
     'if wanted not in (row.get(columns["reference"]) or ""):',
     F + 'test_a_statement_in_another_encoding_is_not_reported_unmatched'),
    ('an unreadable statement is parsed as an empty one', "greg/business_loop.py",
     '    if text is None:\n        # a statement read with replacement characters',
     '    if False:\n        # a statement read with replacement characters',
     F + 'test_a_statement_in_another_encoding_is_not_reported_unmatched'),
    ('a stderr tail that begins mid-character is refused', "greg/capabilities.py",
     '            data = data[next((i for i in range(min(4, len(data))) if not 0x80 <= data[i] < 0xC0), 0):]\n',
     '            pass\n',
     F + 'test_command_output_cut_or_unreadable_decides_only_what_more_could_not_undo'),
    ('object keys are compared by code points', "greg/missions.py",
     '    keys = {_canon(k) if isinstance(k, str) else k: k for k in mapping}',
     '    keys = {k: k for k in mapping}',
     F + 'test_a_forbidden_name_in_another_normalization_form_is_found'),
    ('a text the capability cut at its end is searched whole', "greg/missions.py",
     '            value = _stable(value) if "end" in cut_sides else value\n',
     '            value = value\n',
     F + 'test_a_text_the_capability_cut_itself_is_searched_only_where_no_continuation_can_renormalize'),
    ('a text the capability kept as its end is searched with its leading marks', "greg/missions.py",
     '            value = _stable_tail(value) if "start" in cut_sides else value\n',
     '            value = value\n',
     F + 'test_a_text_the_capability_cut_itself_is_searched_only_where_no_continuation_can_renormalize'),
    ('a cut side the judge does not know is read as no cut', "greg/missions.py",
     'sides |= {side} if side in ("start", "end") else ({"start", "end"} if side is not None else set())',
     'sides |= {side} if side in ("start", "end") else set()',
     F + 'test_a_text_the_capability_cut_itself_is_searched_only_where_no_continuation_can_renormalize'),
    ('a kept prefix of a tail the capability cut keeps its leading marks', "greg/missions.py",
     '                probe = _stable_tail(probe)\n',
     '                pass\n',
     F + 'test_command_output_cut_before_an_accent_does_not_contain_the_bare_letter'),
    ('command output does not say where it was cut', "greg/capabilities.py",
     '        cut_at |= {name: "end" if name == "stdout" else "start"} if cut and text is not None else {}\n',
     '',
     F + 'test_command_output_cut_before_an_accent_does_not_contain_the_bare_letter'),
    ('a cut page does not say where it was cut', "greg/capabilities.py",
     ', "cut_at": dict.fromkeys(held, "end")}',
     '}',
     F + 'test_a_page_cut_by_the_dom_limit_decides_only_what_more_could_not_undo'),
    ('a tail keeps the marks of a character it did not keep', "greg/textform.py",
     '    return next((suffix[i:] for i in range(len(suffix)) if _segment_start(suffix[i], backward)), "")',
     '    return suffix',
     F + 'test_a_text_the_capability_cut_itself_is_searched_only_where_no_continuation_can_renormalize'),
    ('a field path names only a key in its own form', "greg/missions.py",
     '    keys = [key for key in mapping if isinstance(key, str) and _canon(key) == wanted]',
     '    keys = [part] if part in mapping else []',
     F + 'test_a_field_path_names_a_key_in_either_normalization_form'),
    ('two keys spelling the path are read as one', "greg/missions.py",
     '    if len(keys) > 1:\n        raise LookupError',
     '    if False:\n        raise LookupError',
     F + 'test_a_field_path_names_a_key_in_either_normalization_form'),
    ('an incomplete observation under a key in another form is not seen', "greg/missions.py",
     '                node = _member(node, parts[i], path)       # the key the judged path reads, in either form',
     '                node = node[parts[i]]',
     F + 'test_a_field_path_names_a_key_in_either_normalization_form'),
    ('UTF-16 behind a UTF-8 mark is read with its NUL bytes', "greg/capabilities.py",
     '    if codec in ("utf-8", "utf-8-sig") and "\\x00" in text:',
     '    if codec == "utf-8" and "\\x00" in text:',
     F + 'test_a_utf8_mark_before_utf16_bytes_is_refused_like_unmarked_utf8'),
    ('a link swapped in after the roots were checked is followed', "greg/capabilities.py",
     'fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)',
     'fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)',
     F + 'test_a_link_swapped_in_after_the_path_was_checked_is_not_followed'),
    ('git output that is not UTF-8 crashes the sensor', "greg/capabilities.py",
     '    except UnicodeDecodeError as exc:   # a commit subject',
     '    except KeyError as exc:   # a commit subject',
     F + 'test_a_repository_whose_history_is_not_utf8_is_a_failed_read_not_a_crash'),
    ('an undecidable whole comparison reads as FALSE', "greg/missions.py",
     '        return INSUFFICIENT if ok is None else TRUE if ok else FALSE',
     '        return TRUE if ok else FALSE',
     F + 'test_an_undecidable_whole_comparison_is_never_false'),
]


REPORTER = """\
import json, os

_rows = []


def pytest_runtest_logreport(report):
    _rows.append([report.nodeid, report.when, report.outcome, hasattr(report, "wasxfail")])


def pytest_sessionfinish(session, exitstatus):
    with open(os.environ["WHOLE_OUTPUT_GATE_REPORT"], "w", encoding="utf-8") as out:
        json.dump(_rows, out)
"""


def _pytest(repo: Path, nodes: list[str], tools: Path) -> tuple[int, str, list | None]:
    """One pytest run in its own session, read through pytest's own reports (a plugin outside the copy writes each
    test's outcome per phase), never through its text. The session is killed when the run ends, however it ends, so
    nothing it started can write a cache, or anything else, while the next mutant is in place."""
    report = tools / "report.json"
    report.unlink(missing_ok=True)
    proc = subprocess.Popen([sys.executable, "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
                             "-p", "whole_output_gate_reporter", *nodes],
                            cwd=repo, env={**os.environ, "PYTHONPATH": f"{repo}{os.pathsep}{tools}",
                                           "PYTHONDONTWRITEBYTECODE": "1", "WHOLE_OUTPUT_GATE_REPORT": str(report)},
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    out = None
    try:
        out = proc.communicate(timeout=600)[0]
    except subprocess.TimeoutExpired:
        pass
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
    if out is None:
        out = proc.communicate()[0] + "\ntimed out after 600 s"
    rows = json.loads(report.read_text(encoding="utf-8")) if report.exists() else None
    return proc.returncode, out, rows


def _mine(node: str, rows: list | None) -> list:
    """The reports for this node: the node itself, any of its parameters, or the tests inside it."""
    return [r for r in rows or [] if r[0] == node or r[0].startswith((node + "[", node + "::"))]


def _passes(node: str, rows: list | None) -> bool:
    """Every phase of every test under the node passed, none as an expected failure, and at least one test ran."""
    mine = _mine(node, rows)
    return any(when == "call" for _, when, _, _ in mine) and all(o == "passed" and not x for _, _, o, x in mine)


def _fails(node: str, rows: list | None) -> bool:
    """A test under the node failed in some phase, and not as an expected failure."""
    return any(o == "failed" and not x for _, _, o, x in _mine(node, rows))


def _caches(repo: Path) -> list[Path]:
    """Every ``__pycache__`` entry in the copy, including a link (dangling or not), without following links."""
    found = []
    for top, dirs, files in os.walk(repo):
        found += [Path(top) / name for name in dirs + files if name == "__pycache__"]
    return found


def _purge(repo: Path) -> None:
    """Remove every bytecode cache in the copy; a link is removed, not followed. A directory a running process
    re-creates meanwhile is harmless (writes are dated apart), but a link that survives stops the gate."""
    for cache in _caches(repo):
        if cache.is_symlink() or not cache.is_dir():
            cache.unlink(missing_ok=True)
        else:
            shutil.rmtree(cache, ignore_errors=True)
    left = [cache for cache in _caches(repo) if cache.is_symlink() or not cache.is_dir()]
    if left:
        raise SystemExit(f"cannot remove the bytecode cache {left[0]}")


def _write(path: Path, text: str, clock: list[int]) -> None:
    """Write, then date the file to its own whole second: one apart from every other write, all of them earlier than
    any file the copy started with. CPython keys a cached .pyc on the source's whole-second mtime and size, so no
    cache written for another version can match this one, and no write is dated in the future."""
    path.write_text(text, encoding="utf-8")
    clock[0] += 1
    os.utime(path, (clock[0], clock[0]))


def _tail(out: str) -> str:
    return "\n".join("    " + line for line in out.strip().splitlines()[-15:])


def main() -> int:
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))      # a stopped gate still kills its pytest session
    bad = 0
    with tempfile.TemporaryDirectory(prefix="greg-whole-output-mutants-", ignore_cleanup_errors=True) as temp:
        repo, tools = Path(temp) / "repo", Path(temp) / "tools"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        tools.mkdir()
        (tools / "whole_output_gate_reporter.py").write_text(REPORTER, encoding="utf-8")
        oldest = min(int(p.stat().st_mtime) for p in repo.rglob("*") if p.is_file())
        clock = [oldest - 2 * len(MUTANTS) - 2]
        for node in dict.fromkeys(node for *_, node in MUTANTS):
            _purge(repo)
            code, out, rows = _pytest(repo, [node], tools)
            if code != 0 or not _passes(node, rows):
                print(f"BASELINE {node} does not pass alone on the unmutated copy, so no mutant aimed at it can be judged")
                print(_tail(out))
                return 1
        for name, relative, old, new, node in MUTANTS:
            path = repo / relative
            original = path.read_text(encoding="utf-8")
            if original.count(old) != 1:
                print("STALE   ", name)
                bad += 1
                continue
            _purge(repo)
            _write(path, original.replace(old, new), clock)
            try:
                code, out, rows = _pytest(repo, [node], tools)
            finally:
                _write(path, original, clock)
            caught = code == 1 and _fails(node, rows)
            print("CAUGHT  " if caught else "SURVIVED", name)
            if not caught:                           # say why, so a survivor in CI can be diagnosed from its log
                print(_tail(out))
            bad += not caught
    print(f"{len(MUTANTS)} mutants, {bad} survived or stale")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
