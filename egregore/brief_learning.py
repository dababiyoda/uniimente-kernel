"""Fixed presentation comparison; no effect on policy, grants or dispatch."""
from evolution.comparison import Comparison, IsolatedResult

BASELINE = {'dependency': 0, 'authority': 1, 'learning': 2}
CANDIDATE = {'authority': 0, 'dependency': 1, 'learning': 2}


def rank(findings, security_first=False):
    order = CANDIDATE if security_first else BASELINE
    return sorted(findings, key=lambda f: (order.get(f['kind'], 99), f['id']))


def compare(cases):
    if not cases:
        raise ValueError('separate held-out cases required')
    rows = []
    for case in cases:
        if case['expected'] not in {f['id'] for f in case['findings']}:
            raise ValueError('invalid held-out label')
        rows.append({'case': case['id'], 'expected': case['expected'],
            'baseline': rank(case['findings'])[0]['id'],
            'candidate': rank(case['findings'], True)[0]['id']})
    baseline = sum(r['baseline'] == r['expected'] for r in rows) / len(rows)
    candidate = sum(r['candidate'] == r['expected'] for r in rows) / len(rows)
    winner = Comparison(baseline=baseline, threshold=1.0, direction='gte').champion([
        IsolatedResult('security-first', 'presentation', candidate, rows, 0, 0)])
    return {'rows': rows, 'baseline_accuracy': baseline, 'candidate_accuracy': candidate,
        'decision': 'retain' if winner else 'regress' if candidate < baseline else 'no_improvement',
        'scope': 'brief ordering only', 'authority_change': False, 'model_calls': 0,
        'external_cost_usd': 0, 'participant_benefit': 'not measured'}


def brief(report, previous=None, security_first=False):
    findings = rank(report.get('findings', []), security_first)
    old = set(previous.get('coverage', [])) if previous else set()
    return {'goal': 'Inspect approved snapshots and identify the highest-priority evidenced integration blocker',
        'what_changed': sorted(set(report.get('coverage', [])) - old),
        'change_meaning': 'commit/file binding changes; not a claim that every file changed bytes',
        'blocker': findings[0] if findings else None, 'other_findings': findings[1:],
        'next_action': findings[0]['next_action'] if findings else 'No blocker detected by bounded checks; expand independent integration verification.',
        'source_scope': report['source_scope'], 'limits': report.get('limits'),
        'ordering': 'security-first' if security_first else 'unchanged baseline'}
