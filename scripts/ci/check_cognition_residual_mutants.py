"""Seven source mutations that remove the residual safeguards; each targeted test must fail.

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
MUTANTS = [
 ('optimality not attacked by a second engine', 'greg/cognition/verification.py',
  'checks[OBLIGATIONS[claim] + "_found"] = certificate["status"] == "CERTIFIED"', 'checks[OBLIGATIONS[claim] + "_found"] = True',
  'test_a_feasible_but_not_optimal_claim_is_refuted_by_a_second_engine'),
 ('infeasibility taken on trust', 'greg/cognition/verification.py',
  'checks[OBLIGATIONS[claim] + "_found"] = certificate["status"] == "CERTIFIED"', 'checks[OBLIGATIONS[claim] + "_found"] = True',
  'test_an_infeasibility_claim_about_a_feasible_model_is_refuted'),
 # Review 2026-11-17: a check named for a finding exists only when Z3 decided; a certificate binds what it settled.
 ('an unrun second engine reported as a finding', 'greg/cognition/verification.py',
  'if certificate["status"] in ("CERTIFIED", "REFUTED"):\n                ' + 'checks[OBLIGATIONS[claim] + "_found"] = certificate["status"] == "CERTIFIED"',
  'if True:\n                ' + 'checks[OBLIGATIONS[claim] + "_found"] = certificate["status"] != "REFUTED"',
  'test_the_real_verifier_worker_without_z3_certifies_nothing_and_claims_no_finding'),
 ('certification read from a status alone', 'greg/cognition/composition.py',
  'return certified_for(solved.get("evaluator_result"), model, solved.get("proof_artifact"), claim)',
  'return ((solved.get("evaluator_result") or {}).get("certificate") or {}).get("status") == "CERTIFIED"',
  'test_a_certificate_counts_only_for_its_own_problem_candidate_claim_and_verifier'),
 ('a certificate for another problem accepted', 'greg/cognition/verification.py',
  'and binding.get("problem") == digest(data) ', '',
  'test_a_certificate_counts_only_for_its_own_problem_candidate_claim_and_verifier'),
 ('a certificate for another candidate accepted', 'greg/cognition/verification.py',
  'and binding.get("candidate") == digest(proof)', 'and True',
  'test_a_certificate_counts_only_for_its_own_problem_candidate_claim_and_verifier'),
 ('a certificate from a changed verifier accepted', 'greg/cognition/verification.py',
  'and binding.get("verifier") == {"module": __name__, "source": VERIFIER_SOURCE}', '',
  'test_a_certificate_counts_only_for_its_own_problem_candidate_claim_and_verifier'),
 ('a certificate for another obligation accepted', 'greg/cognition/verification.py',
  'and binding.get("obligation") == OBLIGATIONS[claim]', 'and True',
  'test_a_certificate_counts_only_for_its_own_problem_candidate_claim_and_verifier'),
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
]


def main():
    bad = 0
    with tempfile.TemporaryDirectory(prefix='greg-residual-mutants-') as temp:
        repo = Path(temp) / 'repo'
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns('.git', '__pycache__', '.pytest_cache'))
        for name, rel, old, new, test in MUTANTS:
            path = repo / rel
            original = path.read_text()
            if original.count(old) != 1:
                print('STALE', name); bad += 1; continue
            path.write_text(original.replace(old, new))
            try:
                run = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-x', '-p', 'no:cacheprovider',
                                      f'{TESTS}::{test}'], cwd=repo, env={**os.environ, 'PYTHONPATH': str(repo)},
                                     capture_output=True, text=True, timeout=120)
                caught = run.returncode == 1 and f'FAILED {TESTS}::' in run.stdout and 'ERROR collecting' not in run.stdout
                print('CAUGHT' if caught else 'SURVIVED_OR_INVALID', name, run.stdout.strip().splitlines()[-1:])
                bad += not caught
            finally:
                path.write_text(original)
    print(f'{len(MUTANTS)} mutants; {bad} survived, stale, or invalid')
    return int(bool(bad))


if __name__ == '__main__':
    raise SystemExit(main())
