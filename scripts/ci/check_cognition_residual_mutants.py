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
MEDIA = 'tests/unit/test_greg_media_case.py'
FABRIC = 'tests/unit/test_greg_task_fabric.py'
RESTORE = 'tests/unit/test_greg_restore.py'
FAILURES = 'tests/unit/test_greg_failure_closure.py'
ADVERSARIAL = 'tests/integration/test_greg_adversarial_machine.py'
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
 ('the compiled decision ignores the grant horizon and expiry', 'greg/cognition/budget.py',
  'for bound in ("horizon", "grant_expires_at"):', 'for bound in ():',
  'test_an_expired_grant_runs_no_mechanism_on_the_compile_route', WINDOW),
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
  'test_a_failed_call_scrubs_the_key_from_its_error_and_stderr_on_any_host', SECRET_FILES),
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
  'journal=self._ledger_reader() if manifest.capability_id in ("venture.assess",',
  'journal=self.journal if manifest.capability_id in ("venture.assess",',
  'test_the_organ_bridge_reads_receipts_through_a_handle_with_no_write_method', VENTURES),
 # Section 16 media case: a restatement may not change what its supporting spans say.
 ('a supporting span is accepted without comparing the claim', 'greg/cognition/evidence.py',
  'changed = distortions(claim, support) if support else []', 'changed = []',
  'test_each_kind_of_change_is_refuted_and_the_claim_is_not_answered', MEDIA),
 ('a dropped hedge goes unnoticed', 'greg/cognition/evidence.py',
  'if (hedged_support and not hedged_claim) or stronger:', 'if stronger:',
  'test_a_paraphrase_that_drops_a_hedge_is_held_back_with_the_minds_reason', MEDIA),
 ('negation polarity is not compared', 'greg/cognition/evidence.py',
  '    polarity = _polarity_change(claim, support)\n', '    polarity = None\n',
  'test_each_kind_of_change_is_refuted_and_the_claim_is_not_answered', MEDIA),
 ('a negator elsewhere in a span masks a negated claim', 'greg/cognition/evidence.py',
  '        best = max(overlap, default=0)\n', '        best = 0\n',
  'test_a_negator_elsewhere_in_a_span_does_not_mask_a_negated_claim[nothing_else_changed]', MEDIA),
 ("the verifier's polarity recheck reads the whole span", 'greg/cognition/verification.py',
  '        best = max(shared, default=0)\n', '        best = 0\n',
  'test_a_negator_elsewhere_in_a_span_does_not_mask_a_negated_claim[not_costs]', MEDIA),
 ('a spelled number switches the verifier figure recheck off', 'greg/cognition/verification.py',
  '    return bool(numbers(claim) - numbers(spans)), polarity',
  '    return not any(w in _UNITS for w in words(spans)) and bool(numbers(claim) - numbers(spans)), polarity',
  'test_the_verifier_rechecks_figures_when_a_span_spells_a_number', MEDIA),
 ('the verifier reads a spelled figure as missing', 'greg/cognition/verification.py',
  '        text = spelled(text)\n', '        pass\n',
  'test_the_verifier_does_not_refute_a_figure_the_span_spells_out', MEDIA),
 ('the verifier trusts the reported changes', 'greg/cognition/verification.py',
  'checks["restatement_rechecked"] = (not figure_gap', 'checks["restatement_rechecked"] = True or (not figure_gap',
  'test_the_verifier_refutes_an_answer_that_hides_a_change', MEDIA),
 ("DALEOBANKS ignores the Mind's answer", 'greg/cognition/restatement.py',
  '        if receipt.get("abstention_state") != "NONE":', '        if False:',
  'test_a_paraphrase_that_drops_a_hedge_is_held_back_with_the_minds_reason', MEDIA),
 ('a sentence no receipt covers passes', 'greg/cognition/restatement.py',
  'if any(ch.isalnum() for ch in uncovered):', 'if False:',
  'test_a_sentence_no_receipt_covers_is_held_back', MEDIA),
 ('DALEOBANKS is handed the writable journal', 'greg/missions.py',
  'journal=self._ledger_reader() if manifest.capability_id in ("venture.assess",',
  'journal=self.journal if manifest.capability_id in ("venture.assess",',
  'test_a_faithful_paraphrase_is_verified_claim_by_claim', MEDIA),
 # Section 16 Task Fabric: the evaluator of a worker's document asks the Mind about every sentence.
 ('the evaluator never asks the Mind', 'greg/workers.py',
  '            if spec is not None:', '            if False:',
  'test_a_document_that_changes_what_its_input_says_is_rejected_with_the_minds_reason', FABRIC),
 ("the inputs are read from the worker's tree", 'greg/workers.py',
  'shown = _git(fresh, "show", f"{base}:inputs/{name}", check=False, text=False)',
  'shown = _git(fresh, "show", f":inputs/{name}", check=False, text=False)',
  'test_the_worker_cannot_make_a_distortion_supported_by_editing_its_copy_of_the_input', FABRIC),
 ('the signed contract is not compared with the record', 'greg/workers.py',
  'if signed != order["acceptance"].get("bound_claims"):', 'if False:',
  'test_the_signed_contract_applies_to_an_order_recorded_without_it[faithful]', FABRIC),
 ("the record's contract replaces the signed one", 'greg/workers.py',
  'spec = signed if signed is not None else order["acceptance"].get("bound_claims")',
  'spec = order["acceptance"].get("bound_claims")',
  'test_the_signed_contract_applies_to_an_order_recorded_without_it[hedge_dropped]', FABRIC),
 ("the evaluator ignores the body's registry", 'greg/workers.py',
  'registry=ctx.capability_registry)', 'registry=None)',
  'test_a_quarantined_evidence_family_cannot_accept_a_document', FABRIC),
 ('the engine hands the evaluator no registry', 'greg/missions.py',
  'or manifest.capability_id == "worker.appraise" else None,', 'else None,',
  'test_the_evaluator_gets_the_bodys_registry_and_no_ledger', FABRIC),
 ('the lease omits what the worker is judged by', 'greg/workers.py',
  '             "acceptance": order.acceptance,\n', '',
  'test_the_lease_names_the_acceptance_contract_and_its_evaluator', FABRIC),
 ('the publish request skips the Mind-appraised acceptance', 'greg/templates.py',
  'gates = [c["check_id"] for c in checks]', 'gates = ["draft_verified"]',
  'test_a_worker_drafted_post_that_drops_a_hedge_never_reaches_the_publish_request', FABRIC),
 ("a worker's non-text bytes crash the commission", 'greg/workers.py',
  'patch = _git(clone, "diff", "--cached", "--binary", base_commit, text=False).stdout',
  'patch = _git(clone, "diff", "--cached", "--binary", base_commit).stdout',
  'test_bytes_that_are_not_text_are_a_finding_never_a_crash', FABRIC),
 ("GREG's copy of an input is read in another encoding", 'greg/workers.py',
  'text = shown.stdout.decode("utf-8")', 'text = shown.stdout.decode("latin-1")',
  'test_inputs_are_decoded_as_utf8_whatever_the_bodys_locale', FABRIC),
 # Section 14 restore from a tested backup: a restored body holds, and stale authority cannot drive it.
 ('a restore keeps the device delegations it cannot vouch for', 'greg/recovery.py',
  '        for kid in devices:', '        for kid in []:',
  'test_no_device_delegation_from_before_the_restore_is_usable', RESTORE),
 ('a restore keeps approvals the original may have used', 'greg/recovery.py',
  '        for rid in approvals:', '        for rid in []:',
  'test_an_approval_granted_before_the_restore_is_asked_again', RESTORE),
 ('the engine ignores a voided approval', 'greg/missions.py',
  'if data.get("voids_approval") and request:', 'if False:',
  'test_an_approval_granted_before_the_restore_is_asked_again', RESTORE),
 ('a restored body acts at once', 'greg/recovery.py',
  'body.journal.record("body.paused", {"reason": RESTORE_HOLD, "restore_id": restore_id}, key=[restore_id, "hold"])',
  'pass', 'test_a_restored_body_boots_held_and_takes_no_action', RESTORE),
 ('a command issued before the restore is accepted', 'greg/body.py',
  'if instant(env["issued_at"]) < instant(restore["restored_at"]):', 'if False:',
  'test_a_command_issued_before_the_restore_is_refused_however_it_arrives', RESTORE),
 ('a device releases the restore hold', 'greg/body.py',
  'if kind == "BODY_RESUME" and principal != "founder" and self._restore_hold():', 'if False:',
  'test_only_the_founder_key_releases_the_restore_hold', RESTORE),
 ("the seed's recorded head is not compared", 'greg/recovery.py',
  'if recorded is not None and head != recorded:', 'if False:',
  'test_a_tampered_or_inconsistent_seed_never_boots', RESTORE),
 ('a broken chain is restored', 'greg/recovery.py',
  'raise RestoreError(f"the restored ledger does not verify: {exc}") from exc', 'return None',
  'test_a_tampered_or_inconsistent_seed_never_boots', RESTORE),
 ("the body's layout is not restored", 'greg/recovery.py',
  '    for d in (layout.inbox, layout.processed, layout.rejected, layout.outbox, layout.workspace):',
  '    for d in ():', 'test_a_restored_body_boots_held_and_takes_no_action', RESTORE),
 ('a crafted seed writes outside its target', 'foundry/systems/seed.py',
  'if Path(rel).is_absolute() or root not in (root / rel).resolve().parents:', 'if False:',
  'test_a_seed_someone_else_built_cannot_write_outside_or_plant_keys', RESTORE),
 # The restore meets PR #184's founder-answer re-verification (item 7): its voids hold there too.
 ("the answer check honours a phone the restore voided", 'greg/goal_gravity.py',
  '            devices.pop(p.get("device_key_id"), None)\n        if kind == "greg.founder.enrolled":',
  '            pass\n        if kind == "greg.founder.enrolled":',
  'test_a_restores_voids_hold_where_founder_answers_are_re_verified[voided_phone]', RESTORE),
 ('the answer check counts a command issued before the restore', 'greg/goal_gravity.py',
  '    if facts.restored_at is not None and (issued is None or issued < facts.restored_at):',
  '    if False:',
  'test_a_restores_voids_hold_where_founder_answers_are_re_verified[issued_before_the_restore]', RESTORE),
 ('a goal reads a voided approval as the founder\'s answer', 'greg/goal_gravity.py',
  '            if rid in book.withdrawn:\n', '            if False:\n',
  'test_an_approval_the_restore_voided_does_not_answer_a_goal', RESTORE),
 # Sections 11 and 14: the outcome plane hears failures, each independently appraised, each once.
 ('a failed mission never closes', 'greg/missions.py',
  '            if m.actions_done and not held and not split:', '            if False:',
  'test_a_failed_mission_closes_unmet_and_is_appraised_as_a_verified_failure', FAILURES),
 ('a contested mission closes as a failure', 'greg/missions.py',
  '            if m.actions_done and not held and not split:', '            if m.actions_done and not held:',
  'test_two_qualified_intelligences_that_disagree_are_shown_side_by_side_never_voted', ADVERSARIAL),
 ('settlement hears successes only', 'greg/cognition/settlement.py',
  'if (data.get("verdict") in ("VERIFIED", "VERIFIED_UNMET")', 'if (data.get("verdict") == "VERIFIED"',
  'test_settlement_hears_each_failure_once_and_reconciles_idempotently', FAILURES),
 ('a re-observed failure settles again', 'greg/cognition/settlement.py',
  '"input_digest": digest(check["sensor"].get("params", {})), "problem_id": receipt["problem_id"]}',
  '"input_digest": receipt["input_digest"], "problem_id": receipt["problem_id"]}',
  'test_settlement_hears_each_failure_once_and_reconciles_idempotently', FAILURES),
 ('a forged failure is taken on its word', 'greg/appraisal.py',
  '            if passed == unmet:', '            if not passed and not unmet:',
  'test_a_forged_failure_closure_on_a_passing_mission_is_refuted', FAILURES),
 ('a failure the world no longer shows is accepted', 'greg/appraisal.py',
  '                if now_ok is None or now_ok == unmet:', '                if now_ok is None or (now_ok is False and not unmet):',
  'test_a_failure_the_world_no_longer_shows_is_refuted', FAILURES),
 ('a recurring failure closure is recorded again', 'greg/missions.py',
  '                if self.journal.retained("mission.unmet", closure) is None:', '                if True:',
  'test_a_failure_closure_that_recurs_after_the_founder_answers_is_the_same_closure', FAILURES),
 ('an achievement after an appraised failure is never appraised', 'greg/body.py',
  '                     if not e.payload.get("closure_event")}', '                     }',
  'test_an_achievement_after_a_verified_failure_is_appraised_on_its_own', FAILURES),
 ('the appraiser settles a contested check as a failure', 'greg/appraisal.py',
  '            if unmet and disagreement(receipt.payload["result"].get("output")):', '            if False:',
  'test_a_failure_closure_on_a_contested_check_is_refuted_by_the_appraiser', ADVERSARIAL),
 ('a verified failure reads as a success', 'greg/appraisal.py',
  '"verdict": ("VERIFIED_UNMET" if unmet else "VERIFIED") if verified else "REFUTED",',
  '"verdict": "VERIFIED" if verified else "REFUTED",',
  'test_a_verified_failure_is_never_read_as_a_success', FAILURES),
]


def main():
    bad = 0
    with tempfile.TemporaryDirectory(prefix='greg-residual-mutants-') as temp:
        repo = Path(temp) / 'repo'
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns('.git', '__pycache__', '.pytest_cache'))
        # A mutant is caught only by a test that passes without it: a test already failing would "catch" anything.
        nodes = sorted({f'{tests[0] if tests else TESTS}::{test}' for _, _, _, _, test, *tests in MUTANTS})
        clean = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-rs', '-p', 'no:cacheprovider', *nodes],
                               cwd=repo, env={**os.environ, 'PYTHONPATH': str(repo)}, capture_output=True, text=True,
                               timeout=1800)
        if clean.returncode != 0:
            print('BASELINE_FAILS: the targeted tests must pass on the unmutated tree first')
            print('\n'.join(line for line in clean.stdout.splitlines() if line.startswith(('FAILED', 'ERROR'))))
            return 1
        # A test that skips on this host cannot catch its mutant here either: say so, instead of a survivor.
        skipped = [line for line in clean.stdout.splitlines() if line.startswith('SKIPPED')]
        if skipped:
            print('BASELINE_SKIPPED: every targeted test must run on this host; these skip, so their mutants are unguarded')
            print('\n'.join(skipped))
            return 1
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
