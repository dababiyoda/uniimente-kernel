"""Six real source mutations in an isolated copy; require targeted assertions to fail.

No mutation is performed in the checkout or against its frozen evaluation.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MUTANTS = [
 ('removed permission', 'greg/authority.py', 'if outside and scope not in approved_scopes:', 'if False:',
  'test_missing_permission_then_signed_approval_and_revocation_survive_restart'),
 ('dropped constraint', 'cortex/seed/methods.py', "for c in d['constraints']:", "for c in d['constraints'][:1]:",
  'test_real_heterogeneous_methods_and_separate_verifier'),
 ('UNKNOWN relabeled', 'cortex/seed/methods.py', "if status == 'UNKNOWN':", 'if False:', 'test_solver_unknown_preserved'),
 ('replaced source', 'cortex/seed/verify.py', "assert r['source_digests'] == {i: s['sha256'] for i, s in items.items()}, 'source replacement'",
  'pass', 'test_verifier_rejects_replaced_source_digest'),
 ('duplicate settlement guard', 'greg/cognition.py', '    if prior:\n', '    if False:\n',
  'test_outcome_corrections_are_idempotent_and_cannot_edit_policy'),
 ('paid key activates unconfigured method', 'greg/cognition.py', "if c['kind'] == 'semantic' and not c['data'].get('model'):",
  "if c['kind'] == 'semantic' and not c['data'].get('model') and not os.environ.get('OPENAI_API_KEY'):",
  'test_missing_model_never_uses_paid_key'),
]


def main():
    bad = 0
    with tempfile.TemporaryDirectory(prefix='greg-cognitive-mutants-') as temp:
        repo = Path(temp) / 'repo'
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns('.git', '__pycache__', '.pytest_cache'))
        for name, rel, old, new, test in MUTANTS:
            path = repo / rel
            original = path.read_text()
            if old not in original:
                print('STALE', name); bad += 1; continue
            path.write_text(original.replace(old, new))
            try:
                run = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-x', '-p', 'no:cacheprovider',
                    'tests/unit/test_greg_cognition.py::' + test], cwd=repo,
                    env={**os.environ, 'PYTHONPATH': str(repo)}, capture_output=True, text=True, timeout=45)
                # Import errors and infrastructure crashes cannot count as caught safeguards.
                caught = run.returncode == 1 and 'FAILED tests/unit/test_greg_cognition.py::' in run.stdout and 'ERROR collecting' not in run.stdout
                print('CAUGHT' if caught else 'SURVIVED_OR_INVALID', name, run.stdout.strip().splitlines()[-1:])
                bad += not caught
            finally:
                path.write_text(original)
    print(f'{len(MUTANTS)} mutants; {bad} survived, stale, or invalid')
    return int(bool(bad))


if __name__ == '__main__':
    raise SystemExit(main())
