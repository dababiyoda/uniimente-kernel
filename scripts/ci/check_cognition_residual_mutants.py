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
MEDIA = 'tests/unit/test_greg_media_case.py'
FABRIC = 'tests/unit/test_greg_task_fabric.py'
MUTANTS = [
 ('optimality not attacked by a second engine', 'greg/cognition/verification.py',
  'certificate["status"] != "REFUTED")', 'True)',
  'test_a_feasible_but_not_optimal_claim_is_refuted_by_a_second_engine'),
 ('infeasibility taken on trust', 'greg/cognition/verification.py',
  'certificate["status"] != "REFUTED")', 'True)',
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
 ('planning time reaches the first step and so the settled claim', 'greg/cognition/budget.py',
  '        self.started = None\n', '        self.started = clock()\n',
  'test_planning_time_before_the_first_step_never_reaches_its_limit', BUDGET),
 ('the first step reads the clock twice and loses microseconds', 'greg/cognition/budget.py',
  'remaining, cost = self.remaining(now), self.cost_range()', 'remaining, cost = self.remaining(), self.cost_range()',
  'test_planning_time_before_the_first_step_never_reaches_its_limit', BUDGET),
 ('an optional re-run is treated as required', 'greg/cognition/compiler.py',
  'limit = budget.allot(f"sensitivity:{key}", required=False)', 'limit = budget.allot(f"sensitivity:{key}", required=True)',
  'test_one_budget_covers_the_whole_compiled_decision', BUDGET),
 ('every re-run gets the whole budget again', 'greg/cognition/compiler.py',
  '                      "geometry": {**hint, "latency_limit": limit}, **extra}, registry=registry, journal=journal,',
  '                      "geometry": hint, **extra}, registry=registry, journal=journal,',
  'test_one_budget_covers_the_whole_compiled_decision', BUDGET),
 ('local compute recorded as free', 'greg/cognition/compiler.py',
  'budget.done("answer", cpu_seconds=_cpu_delta(cpu_started))', 'budget.done("answer", cpu_seconds=0.0)',
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
  'if _negated(cw, claim) != _negated(sw, joined):', 'if False:',
  'test_each_kind_of_change_is_refuted_and_the_claim_is_not_answered', MEDIA),
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
  'test_an_edited_record_rejects_even_a_faithful_document', FABRIC),
 ("the record's contract replaces the signed one", 'greg/workers.py',
  'spec = signed if signed is not None else order["acceptance"].get("bound_claims")',
  'spec = order["acceptance"].get("bound_claims")',
  'test_the_signed_contract_applies_when_the_record_is_edited', FABRIC),
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
