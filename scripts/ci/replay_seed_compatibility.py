"""Replay original sealed cases against the migrated compatibility adapter.

This is a regression check, not a replacement seal or comparative benchmark.
The original runner still refuses changed source and dependencies. No routing
advantage, latency superiority or external outcome is inferred from this replay.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from greg.cognition import evaluate_problem


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# sha256 of the loss() source segment in the run.py sealed by freeze-v3 (blob 7977b01).
LOSS_V3_SHA256 = '80299c49024e58afa9d449763646c75be4d8e7bfc2b62e6a6eb966c1b412973a'


# The runner freeze run.py currently points at, pinned by manifest digest. Re-freezing the runner
# (a new freeze-vN) is a deliberate re-seal: update this pair in the same change.
RUNNER_FREEZE = ('cortex/evaluation/seed_genome/freeze-v13.json',
                 '5227d4ff8d041afdd774f22ff6b8c7db67e0e8d0a868416eb292583dccb5bcfc')
RUNNER = 'cortex/evaluation/seed_genome/run.py'


def _sealed_loss_sha256(text):
    import ast
    for node in ast.parse(text).body:
        if isinstance(node, ast.FunctionDef) and node.name == 'loss':
            return hashlib.sha256(ast.get_source_segment(text, node).encode()).hexdigest()
    return None


def _literal_spec(text):
    import ast
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', None) == 'SPEC' for t in node.targets):
            return ast.literal_eval(node.value)
    return None


def replay(root=ROOT):
    manifest = root / 'cortex/evaluation/seed_genome/freeze-v3.json'
    if digest(manifest) != '2d3037bc5c89a5117b448241a8869fde72ed5b1d96a89e4e7892a559ae6f8bcd':
        raise ValueError('FROZEN_EVALUATION_CHANGED: original manifest')
    frozen = json.loads(manifest.read_text())['inputs']
    # The labels, scoring implementation and case generator remain sealed. The labels and the
    # generator are sealed by their v3 file digests. run.py's import path, file list and freeze
    # pointer changed when the seed module was renamed (greg/cognition.py ->
    # greg/cognition/seed_path.py) and the runner was re-frozen (v4-v8), so it carries two seals:
    # its scoring equals v3 (loss() byte for byte, SPEC equal to the sealed spec), and its whole
    # file equals the digest the pinned current runner freeze records. Any other edit is refused.
    for name in ('cortex/evaluation/seed_genome/suite.json',
                 'cortex/evaluation/seed_genome/build.py'):
        if digest(root / name) != frozen['files'][name]:
            raise ValueError('FROZEN_EVALUATION_CHANGED: ' + name)
    runner_manifest, runner_manifest_sha256 = RUNNER_FREEZE
    if digest(root / runner_manifest) != runner_manifest_sha256:
        raise ValueError('FROZEN_EVALUATION_CHANGED: ' + runner_manifest)
    if digest(root / RUNNER) != json.loads((root / runner_manifest).read_text())['inputs']['files'][RUNNER]:
        raise ValueError('FROZEN_EVALUATION_CHANGED: ' + RUNNER)
    runner_text = (root / RUNNER).read_text()
    if _sealed_loss_sha256(runner_text) != LOSS_V3_SHA256:
        raise ValueError('FROZEN_EVALUATION_CHANGED: ' + RUNNER + ' loss()')
    if _literal_spec(runner_text) != frozen['scoring']:
        raise ValueError('FROZEN_EVALUATION_CHANGED: ' + RUNNER + ' SPEC')
    source_delta = {p: {'frozen': expected,
                       'current': digest(root/p) if (root/p).is_file() else None}
                    for p,expected in frozen['files'].items()
                    if not (root/p).is_file() or digest(root/p) != expected}
    dependencies = {name: importlib.metadata.version(name) for name in frozen['dependencies']}
    from cortex.evaluation.seed_genome.run import loss
    items = json.loads((root / 'cortex/evaluation/seed_genome/suite.json').read_text())['items']
    rows = []
    for row in items:
        receipt = evaluate_problem(row['problem'])
        score = loss(row, receipt)
        rows.append({'item_id': row['item_id'], 'receipt': receipt,
                     'expectation_matched': bool(score['expectation_matched']),
                     'hard_failure': bool(score['hard_failure']),
                     'false_claim': bool(score['components']['false_claim'])})
    valid = all(r['expectation_matched'] and not r['hard_failure'] and not r['false_claim'] for r in rows)
    return {'kind': 'MIGRATED_SEED_COMPATIBILITY_REPLAY', 'valid': valid,
            'frozen_manifest_sha256': digest(manifest), 'source_delta': source_delta,
            'dependencies': dependencies, 'frozen_dependencies': frozen['dependencies'],
            'original_benchmark_status': 'NOT_COMPARABLE' if source_delta or dependencies != frozen['dependencies'] else 'INPUTS_MATCH',
            'comparative_advantage': 'NOT_MEASURED', 'authority_created': False,
            'founder_device_verified': False,
            'candidate_source': {'greg/cognition/seed_compat.py': digest(ROOT/'greg/cognition/seed_compat.py'),
                                 'greg/cognition/__init__.py': digest(ROOT/'greg/cognition/__init__.py')},
            'cases': rows, 'passed': sum(r['expectation_matched'] for r in rows), 'total': len(rows)}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    report=replay();args.out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:report[k] for k in ('kind','valid','original_benchmark_status','passed','total')}))
    return 0 if report['valid'] else 1


if __name__=='__main__':raise SystemExit(main())
