"""Source mutations that remove the residual safeguards; each targeted test must fail.

Mirrors check_greg_cognition_mutants.py: mutations happen in an isolated copy, never in the
checkout, and an import error or crash never counts as a caught safeguard.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TESTS = 'tests/unit/test_cognition_residual_safeguards.py'
DISCLOSURE = 'tests/unit/test_cognition_disclosure.py'
CHARACTERIZE = 'tests/unit/test_cognition_characterize.py'
BUDGET = 'tests/unit/test_cognition_thinking_budget.py'
VENTURES = 'tests/unit/test_greg_ventures.py'
CONSTRUCTED = 'tests/unit/test_greg_constructed_route_rules.py'
WINDOW = 'tests/unit/test_cognition_compile_grant_window.py'
ECONOMICS_BINDING = 'tests/unit/test_greg_ventures_economics_binding.py'
OUTAGE = 'tests/unit/test_greg_outage_retry_cognition.py'
SECRET_FILES = 'tests/integration/test_greg_mcp_secret_files_review.py'
MUTANTS = [
 ('optimality not attacked by a second engine', 'greg/cognition/verification.py',
  'checks["optimality_cross_engine"] = better == "unsat"', 'checks["optimality_cross_engine"] = True',
  'test_a_feasible_but_not_optimal_claim_is_refuted_by_a_second_engine'),
 ('infeasibility taken on trust', 'greg/cognition/verification.py',
  'checks["infeasibility_cross_engine"] = verdict == "unsat"', 'checks["infeasibility_cross_engine"] = True',
  'test_an_infeasibility_claim_about_a_feasible_model_is_refuted'),
 ('unsat core taken on trust', 'greg/cognition/verification.py',
  'checks["unsat_core_recheck"] = cross["unsat_core"]["core_unsat"]', 'checks["unsat_core_recheck"] = True',
  'test_unsat_cores_are_rechecked_and_tested_for_minimality'),
 ('bare assertion permits again', 'greg/cognition/protection.py',
  'blocked = hard or gates["verdict"] != "PASS"',
  'blocked = hard or not (option.get("lawful") is True and option.get("consent") is True)',
  'test_a_bare_lawful_and_consent_assertion_no_longer_permits'),
 ('context settles a gate', 'greg/cognition/legitimacy.py',
  'bearing = [r for r in live if r.permission_bearing]', 'bearing = list(live)',
  'test_records_are_typed_and_context_never_settles_a_gate'),
 ('law without a reviewer', 'greg/cognition/legitimacy.py',
  '(gate != "law" or r.reviewer)', 'True', 'test_records_are_typed_and_context_never_settles_a_gate'),
 ('expired record still counts', 'greg/cognition/legitimacy.py',
  'live = [r for r in mine if r.expires_at is None or _timestamp(r.expires_at, "expires_at") > now]', 'live = list(mine)',
  'test_permission_bearing_records_unblock_and_prohibitions_still_block'),
 # Selective-disclosure evidence packages (directive section 9).
 ('a disagreeing same-input receipt can be left out', 'greg/cognition/disclosure.py',
  '    related = [r for r in journal.ledger.by_type("receipt")', '    related = [r for r in []',
  'test_a_disagreeing_receipt_over_the_same_input_cannot_be_left_out', DISCLOSURE),
 ('a revealed value is not checked against the commitments', 'greg/cognition/disclosure.py',
  'elif disclosure_digest(text) not in item.get("digests", []):', 'elif False:',
  'test_tampering_is_detected_on_the_recipient_side', DISCLOSURE),
 ('weak salts accepted', 'greg/cognition/disclosure.py',
  'salt_ok = len(_unb64(salt)) >= SALT_BYTES', 'salt_ok = True',
  'test_tampering_is_detected_on_the_recipient_side', DISCLOSURE),
 ('a package issued from a broken chain', 'greg/cognition/disclosure.py',
  '    if not intact:', '    if False:', 'test_custody_is_stated_and_a_broken_chain_issues_nothing', DISCLOSURE),
 ('an invented authorized-action reference accepted', 'greg/cognition/disclosure.py',
  'if record is None or record.record_type not in ACTION_RECORD_TYPES:', 'if False:',
  'test_only_valid_retained_receipts_and_real_action_records_are_accepted', DISCLOSURE),
 ('a forged receipt packaged', 'greg/cognition/disclosure.py',
  'return output if _valid_receipt(output) else None', 'return output',
  'test_only_valid_retained_receipts_and_real_action_records_are_accepted', DISCLOSURE),
 ('a dispute recorded without grounds', 'greg/cognition/disclosure.py',
  'if response in ("disputed", "declined", "partially_accepted") and not grounds and not note:', 'if False:',
  'test_an_institutional_response_is_appended_never_edited_in_and_grants_nothing', DISCLOSURE),
 ('a package shortens the limits the recipient is told', 'greg/cognition/disclosure.py',
  '            "does_not_prove": list(LIMITATIONS)}', '            "does_not_prove": list(package.get("limitations", []))}',
  'test_an_unsigned_package_reports_the_verifiers_own_limits', DISCLOSURE),
 # Characterization harness (directive section 5): the measurement must notice a weakened verifier.
 ('error correction counted without the verifier', 'greg/cognition/characterize.py',
  'corrections.append(verdict == "REFUTED")', 'corrections.append(True)',
  'test_a_verifier_that_accepts_everything_shows_up_as_zero_error_correction', CHARACTERIZE),
 # Thinking budget (directive section 12): one budget per decision; required steps kept, optional ones priced.
 ('an optional step starts without room to finish', 'greg/cognition/budget.py',
  'elif not required and cost is not None and cost[1] > remaining:', 'elif False:',
  'test_required_steps_are_never_priced_away_and_optional_ones_must_fit_their_measured_tail', BUDGET),
 ('a step runs below the minimum that can still verify', 'greg/cognition/budget.py',
  'if remaining < MIN_STEP_SECONDS:', 'if False:',
  'test_a_spent_budget_narrows_the_result_instead_of_skipping_required_evidence', BUDGET),
 ('an optional re-run is treated as required', 'greg/cognition/compiler.py',
  'limit = budget.allot(f"sensitivity:{key}", required=False)', 'limit = budget.allot(f"sensitivity:{key}", required=True)',
  'test_one_budget_covers_the_whole_compiled_decision', BUDGET),
 ('every re-run gets the whole budget again', 'greg/cognition/compiler.py',
  '                      "geometry": {**hint, "latency_limit": limit}, **extra}, registry=registry, journal=journal,',
  '                      "geometry": hint, **extra}, registry=registry, journal=journal,',
  'test_one_budget_covers_the_whole_compiled_decision', BUDGET),
 ('local compute recorded as free', 'greg/cognition/cortex.py',
  '"cpu_seconds": _cpu_delta(cpu_started),', '"cpu_seconds": 0.0,',
  'test_local_compute_is_measured_not_assumed_free', BUDGET),
 # The Capability Genesis route on the convergence branch: a formed engine is a required step on the same budget.
 ('a formed engine starts on a spent budget', 'greg/cognition/compiler.py',
  '            receipt["method_or_composition_selected"] = receipt["selection_level"] = None\n'
  '            return "ABSTAIN", None',
  '            limit, budget._open = 0.0, {"step": step, "required": True, "decision": "RUN", "_at": budget.clock()}',
  'test_a_formed_mechanism_is_a_required_step_on_the_same_budget', BUDGET),
 ('a formed engine\'s spend goes unrecorded', 'greg/cognition/compiler.py',
  '            budget.done(step)\n            spent = budget.ledger[-1]["spent_s"]',
  '            budget._open = None\n            spent = 0.0',
  'test_a_formed_mechanism_is_a_required_step_on_the_same_budget', BUDGET),
 ('a formed engine\'s overrun is hidden', 'greg/cognition/compiler.py',
  '            if spent > limit:', '            if False:',
  'test_a_formed_mechanism_is_a_required_step_on_the_same_budget', BUDGET),
 # Fourth review of the Track B merge: a construction answering inside the compiler meets every compile route's rules.
 ('a construction answers a high-consequence request without a formal model', 'greg/cognition/compiler.py',
  '        return finish("FORMALIZATION_INCOMPLETE")\n    request = {key: data[key] for key in chosen["inputs"]}',
  '    request = {key: data[key] for key in chosen["inputs"]}',
  'test_a_high_consequence_construction_answer_needs_a_formal_model_and_is_conditional', CONSTRUCTED),
 ('a high-consequence construction answer is labelled ANSWERED', 'greg/cognition/compiler.py',
  'return finish("WORLD_UNVERIFIED" if high else "ANSWERED", out)', 'return finish("ANSWERED", out)',
  'test_a_high_consequence_construction_answer_needs_a_formal_model_and_is_conditional', CONSTRUCTED),
 ('a construction runs off the decision budget', 'greg/cognition/compiler.py',
  'finish, high=high, budget=budget,', 'finish, high=high, budget=None,',
  'test_the_construction_call_is_a_required_step_on_the_decision_budget', CONSTRUCTED),
 ('the implied geometry ignores constructions', 'greg/cognition/compiler.py',
  '                      + constructed_candidates(data, replace(g, geometry=None), registry)\n', '',
  'test_the_implied_geometry_counts_a_construction_the_declaration_excludes', CONSTRUCTED),
 # The compile and chain routes carry the caller's grant window into every inner run (COG-5).
 ('the compile route drops the caller window', 'greg/cognition/cortex.py',
  'model_config=model_config,\n                            caller_window=caller_window, shared_deadline=shared_deadline,\n'
  '                            shared_compute_limit=shared_compute_limit)', 'model_config=model_config)',
  'test_an_expired_grant_runs_no_mechanism_on_the_compile_route', WINDOW),
 ('the window does not bound the compiled decision', 'greg/cognition/budget.py',
  '            self.total = min(self.total, self.window["seconds"])', '            pass',
  'test_a_live_grant_is_named_on_the_compiled_answer_and_bounds_the_decision', WINDOW),
 ('the compiled answer runs outside the live grant', 'greg/cognition/compiler.py',
  '**extra}, registry=registry, journal=journal, model_config=model_config, **budget.inner)',
  '**extra}, registry=registry, journal=journal, model_config=model_config)',
  'test_a_live_grant_is_named_on_the_compiled_answer_and_bounds_the_decision', WINDOW),
 ('a chain stage runs outside the caller window', 'greg/cognition/composition.py',
  'kw = dict(registry=registry, journal=journal, model_config=model_config, **inner)',
  'kw = dict(registry=registry, journal=journal, model_config=model_config)',
  'test_the_chain_route_carries_the_window_into_every_stage', WINDOW),
 # Section 16 venture case (carried from #143): a revenue figure may not outrun its causal support.
 ('a revenue conclusion drawn from any causal receipt', 'greg/ventures.py',
  '    identified = bool(causal and causal.get("abstention_state") == "NONE"',
  '    identified = bool(causal or causal.get("abstention_state") == "NONE"',
  'test_a_revenue_figure_never_outruns_its_causal_support', VENTURES),
 ('an estimate the Mind abstained on is still shown', 'greg/ventures.py',
  '    if revenue is None or revenue.get("abstention_state") != "NONE":', '    if revenue is None:',
  'test_a_revenue_figure_never_outruns_its_causal_support', VENTURES),
 ('an off-ledger receipt is accepted in a memo', 'greg/ventures.py',
  'if ledger is not None and not any(', 'if False and not any(',
  'test_identified_randomized_support_is_stated_with_its_assumptions_and_a_forged_receipt_is_refuted', VENTURES),
 ('a memo from other economics closes a venture mission', 'greg/ventures.py',
  'if marker in text and _same_economics(text, params):', 'if marker in text:',
  'test_a_memo_from_other_economics_does_not_close_a_mission', ECONOMICS_BINDING),
 ('venture missions with different economics share their cognition questions', 'greg/templates.py',
  'ids = {"revenue": f"venture-revenue-{thread}{suffix}", "causal": f"venture-causal-{thread}{suffix}"}',
  'ids = {"revenue": f"venture-revenue-{thread}", "causal": f"venture-causal-{thread}"}',
  'test_missions_with_different_economics_are_different_missions_with_their_own_questions', ECONOMICS_BINDING),
 ('an outage retry forgets the compile deficit', 'greg/missions.py',
  '                blocker["deficit"] = deficit', '                pass',
  'test_a_mechanism_attached_during_an_outage_backoff_serves_the_waiting_mission[True]', OUTAGE),
 ('Genesis marks as tried what became usable after the compile', 'greg/genesis.py',
  '        tried = compiler_tried(deficit)', '        tried = None',
  'test_a_mechanism_attached_during_an_outage_backoff_serves_the_waiting_mission[True]', OUTAGE),
 # mcp.act's secret_files (#169 46719e4): credentials stay out of records, readable workspaces and bindings.
 ('a server echoing its key writes it into the ledger', 'greg/mcp_tools.py',
  '        tail = _scrub(log.read_text(errors="replace"), handed)[-300:].strip() if log.exists() else ""\n'
  '        what = _scrub(str(cause) if isinstance(cause, GatewayError) else f"{type(cause).__name__}: {cause}", handed)\n'
  '        what, tail = _scrub(" ".join(what.split()), handed), _scrub(" ".join(tail.split()), handed)[-200:]',
  '        tail = log.read_text(errors="replace")[-300:].strip() if log.exists() else ""\n'
  '        what = str(cause) if isinstance(cause, GatewayError) else f"{type(cause).__name__}: {cause}"\n'
  '        what, tail = " ".join(what.split()), " ".join(tail.split())[-200:]',
  'test_a_server_echoing_its_key_file_never_writes_the_key_into_a_record[bad_key]', SECRET_FILES),
 ('a killed call leaves its key file in the workspace', 'greg/body.py',
  'removed = sweep_leftovers(self.layout.workspace)', 'removed = []',
  'test_the_body_removes_call_leftovers_when_it_opens_and_keeps_everything_else', SECRET_FILES),
 ('an earlier output chooses the credential file', 'greg/pipeline.py',
  '"secrets", "secret_files", "bearer", "hosts", "writable"})', '"secrets", "bearer", "hosts", "writable"})',
  'test_an_earlier_actions_output_cannot_choose_a_servers_reach[secret_files]', SECRET_FILES),
 ('a malformed scope is asked about instead of refused', 'greg/missions.py',
  '            if problem is not None:          # refused before anyone is asked: the signed scope cannot run as written',
  '            if False:',
  'test_a_malformed_secret_files_is_refused_before_anyone_is_asked[malformed2]', SECRET_FILES),
 ('the organ bridge is handed the writable journal', 'greg/missions.py',
  'journal=self._ledger_reader() if manifest.capability_id == "venture.assess"',
  'journal=self.journal if manifest.capability_id == "venture.assess"',
  'test_the_organ_bridge_reads_receipts_through_a_handle_with_no_write_method', VENTURES),
]


def main():
    bad = 0
    with tempfile.TemporaryDirectory(prefix='greg-residual-mutants-') as temp:
        repo = Path(temp) / 'repo'
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns('.git', '__pycache__', '.pytest_cache'))
        for name, rel, old, new, test, *tests in MUTANTS:
            target = tests[0] if tests else TESTS
            path = repo / rel
            original = path.read_text()
            if original.count(old) != 1:
                print('STALE', name); bad += 1; continue
            path.write_text(original.replace(old, new))
            try:
                run = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-x', '-p', 'no:cacheprovider',
                                      f'{target}::{test}'], cwd=repo, env={**os.environ, 'PYTHONPATH': str(repo)},
                                     capture_output=True, text=True, timeout=120)
                caught = run.returncode == 1 and f'FAILED {target}::' in run.stdout and 'ERROR collecting' not in run.stdout
                print('CAUGHT' if caught else 'SURVIVED_OR_INVALID', name, run.stdout.strip().splitlines()[-1:])
                bad += not caught
            finally:
                path.write_text(original)
    print(f'{len(MUTANTS)} mutants; {bad} survived, stale, or invalid')
    return int(bool(bad))


if __name__ == '__main__':
    raise SystemExit(main())
