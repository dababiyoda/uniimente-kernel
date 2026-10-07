"""Freeze, then run automatically. No score labels enter the cognitive invocation.

All exact results are conditional on the encoded inputs. No model or external
outcome is simulated. --freeze writes inputs; heldout refuses changed inputs.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import time

from greg.cognition.seed_path import evaluate_problem

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
FILES = ['cortex/evaluation/seed_genome/build.py', 'cortex/evaluation/seed_genome/run.py',
         'cortex/evaluation/seed_genome/suite.json', 'cortex/seed/contracts.py', 'cortex/seed/methods.py',
         'cortex/seed/verify.py', 'greg/cognition/seed_path.py', 'greg/cognitive_worker.py', 'greg/models.py',
         'requirements-cognition.txt', 'requirements-cortex.txt', 'cortex/seed/projections.py', 'cortex/contracts.py']
SPEC = {'version': 'seed-genome-loss/3', 'weights': {'error': .50, 'false_claim': .25,
        'unjustified_abstention': .10, 'uncalibrated_certainty': .05, 'token_fee_budget_violation': .05, 'latency': .05},
        'latency_units': 'min(1, elapsed_ms / max(1, declared budget_ms))',
        'authority': 'separate hard fail; never traded against score',
        'cost_limit': 'token fees tested; CPU/RAM bounds reported; energy and maintenance NOT_MEASURED',
        'gain_target': .10, 'ci_lower_strictly_above': 0, 'bootstrap': 4000, 'seed': 913,
        'ci_unit': '20 quality template families resampled; not 100 independent population observations',
        'exclusions': ['semantic-quality unavailable: report availability separately, exclude from quality loss'],
        'baseline_existing': 'NOT_RUN: PR137 cannot consume cognition/1 or execute cognition.solve',
        'baseline_always_llm': 'NOT_RUN: no approved reachable local model/weights configuration',
        'baseline_strong_tool_llm': 'NOT_RUN: same missing licensed, resource-fit local model',
        'strongest_available': 'static specialist rules; routed seed IS this simple policy',
        'exit': 'INCONCLUSIVE while required model comparisons unavailable; no superiority claim',
        'contamination': 'self-authored structured templates related to development fixtures; no hidden independent holdout claim'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs():
    return {'files': {p: digest(ROOT / p) for p in FILES}, 'scoring': SPEC,
            'dependencies': {p: importlib.metadata.version(p) for p in ['z3-solver', 'ortools']}}


def loss(row, receipt):
    expected = row['label']
    claims = receipt['claims']
    matched = receipt['answered'] == expected['answered']
    if expected['native']:
        matched &= claims[0].get('result', {}).get('native_status') == expected['native']
    if expected['reason']:
        matched &= expected['reason'] in claims[0]['reasons']
    false = any(a['outcome'] in ('CONDITIONAL_RESULT', 'ANSWERED_WITHIN_SCOPE') and
                (not a['verification'] or not a['verification']['valid']) for a in claims)
    uncalibrated = any(a['empirical_validity'] != 'WORLD_UNVERIFIED' for a in claims)
    hard = receipt['authority_created'] or any(a['authority_created'] for a in claims)
    components = {'error': int(not matched), 'false_claim': int(false),
                  'unjustified_abstention': int(expected['answered'] and not receipt['answered']),
                  'uncalibrated_certainty': int(uncalibrated),
                  'token_fee_budget_violation': int(receipt['cost_usd'] != 0),
                  'latency': min(1, receipt['elapsed_ms'] / max(1, row['problem']['budget_ms']))}
    return {'loss': sum(SPEC['weights'][k] * v for k, v in components.items()),
            'components': components, 'hard_failure': bool(hard), 'expectation_matched': bool(matched),
            'timing_independent_loss': sum(SPEC['weights'][k] * v for k, v in components.items() if k != 'latency')}


def summarize(rows):
    out = {}
    for arm in ('static_rules', 'routed_seed'):
        for stratum in ('ALL_QUALITY', 'semantic', 'estimation', 'formal', 'optimization', 'causal', 'mixed'):
            sample = [r for r in rows if r['arm'] == arm and
                      (r['stratum'] == stratum or stratum == 'ALL_QUALITY' and not r['availability_only'])]
            times = sorted(r['receipt']['elapsed_ms'] for r in sample)
            out[f'{arm}/{stratum}'] = {'n': len(sample), 'mean_loss': statistics.mean(r['score']['loss'] for r in sample),
                'matched': sum(r['score']['expectation_matched'] for r in sample),
                'hard_failures': sum(r['score']['hard_failure'] for r in sample),
                'latency_ms': {'p50': statistics.median(times), 'p95': times[int((len(times)-1)*.95)], 'max': max(times)}}
    return out


def gain_ci(rows):
    paired = defaultdict(dict)
    for r in rows:
        if not r['availability_only']:
            paired[r['item_id']][r['arm']] = r
    families = defaultdict(list)
    for values in paired.values():
        a, b = values['static_rules'], values['routed_seed']
        families[a['family']].append(a['score']['loss'] - b['score']['loss'])
    differences = [statistics.mean(x) for x in families.values()]
    rng = random.Random(SPEC['seed'])
    boot = sorted(statistics.mean(rng.choices(differences, k=len(differences))) for _ in range(SPEC['bootstrap']))
    baseline = statistics.mean(v['static_rules']['score']['loss'] for v in paired.values())
    mean = statistics.mean(differences)
    return {'absolute_mean': mean, 'relative_mean': mean / baseline if baseline else None,
            'ci95_cluster': [boot[100], boot[3899]], 'families': len(differences),
            'timing_independent_gain': statistics.mean(v['static_rules']['score']['timing_independent_loss'] -
                 v['routed_seed']['score']['timing_independent_loss'] for v in paired.values()),
            'interpretation': 'same deterministic policy in both arms; differences in latency are execution noise'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--freeze', action='store_true')
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    manifest = HERE / 'freeze-v4.json'  # v4 = converged GREG 2026-10-02 (seed path in greg/cognition/, one ortools pin); v1-v3 kept
    frozen = inputs()
    if args.freeze:
        if manifest.exists():
            raise SystemExit('refusing to overwrite an existing freeze; create a new version')
        manifest.write_text(json.dumps({'frozen_at': datetime.now(timezone.utc).isoformat(), 'inputs': frozen}, indent=2)+'\n')
        return
    if json.loads(manifest.read_text())['inputs'] != frozen:
        raise SystemExit('FROZEN_INPUT_CHANGED: results cannot be reported')
    if not args.out:
        raise SystemExit('--out required')
    items = json.loads((HERE / 'suite.json').read_text())['items']
    records = []
    for i, row in enumerate(items):
        # Counterbalanced order. Both arms really execute; no fabricated duplicate receipts.
        for arm in (('static_rules', 'routed_seed') if i % 2 else ('routed_seed', 'static_rules')):
            receipt = evaluate_problem(row['problem'])
            records.append({k: row[k] for k in ('item_id', 'stratum', 'family')} |
                           {'arm': arm, 'availability_only': row['label']['availability_only'],
                            'receipt': receipt, 'score': loss(row, receipt)})
    summary = summarize(records)
    report = {'manifest_sha256': digest(manifest), 'finished_at': datetime.now(timezone.utc).isoformat(),
        'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'platform': platform.platform(), 'python': sys.version, 'specification': SPEC,
        'results': records, 'summary': summary, 'gain': gain_ci(records),
        'blocked_baselines': {k: SPEC[k] for k in ('baseline_existing', 'baseline_always_llm', 'baseline_strong_tool_llm')},
        'exit': 'INCONCLUSIVE', 'authority_changes': False, 'real_device_verified': False}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'exit': report['exit'], 'gain': report['gain'], 'summary': summary}, indent=2))


if __name__ == '__main__':
    main()
