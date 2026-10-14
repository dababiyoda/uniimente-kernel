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
