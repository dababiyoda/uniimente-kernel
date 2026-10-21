"""Self-authored engineering suite. No independent or population representativeness claim.

Four held-out template families per stratum, five numeric transformations each.
All relatives remain in heldout; development tests are a disclosed related source.
Freeze AFTER implementation and BEFORE evaluation; do not optimize to this suite.
"""
import copy
import hashlib
import json
from pathlib import Path
from cortex.seed.contracts import VERSION, EXPOSURES

HERE = Path(__file__).parent


def problem(kind, data, pid):
    return {'schema_version': VERSION, 'problem_id': pid, 'objective': 'Bounded engineering evaluation',
            'consequence': {'class': 'read_only', 'exposures': dict.fromkeys(EXPOSURES, 0),
                            'human_judgment': False, 'policy_refusal': False},
            'budget_ms': 10000, 'claims': [{'claim_id': 'c1', 'kind': kind, 'data': data, 'conditions': {}}]}


def linear(family, n, impossible=False, optimize=False):
    variables = {'x': [0, 8], 'y': [0, 8]}
    if family == 0:  # allocation / capacity
        constraints = [('capacity', {'x': 1, 'y': 1}, '<=', n + 3), ('minimum', {'x': 1}, '>=', 10 if impossible else n)]
    elif family == 1:  # fixed-order start scheduling (no disjunction claim)
        constraints = [('precedence', {'x': 1, 'y': -1}, '<=', -(n + 1)), ('deadline', {'y': 1}, '<=', n if impossible else 8)]
    elif family == 2:  # inventory balance
        constraints = [('balance', {'x': 2, 'y': 1}, '==', n * 2 + 3), ('storage', {'x': 1, 'y': 1}, '<=', 1 if impossible else 8)]
    else:  # staffing coverage
        constraints = [('coverage', {'x': 2, 'y': 3}, '>=', 100 if impossible else n + 9), ('headcount', {'x': 1, 'y': 1}, '<=', 7)]
    c = [{'id': i, 'coefficients': coef, 'op': op, 'rhs': rhs} for i, coef, op, rhs in constraints]
    d = {'variables': variables, 'constraints': c, 'coverage': {'represented': [x['id'] for x in c],
         'omissions': [], 'assumptions': ['bounded declared integer model'], 'reviewed': True}}
    if optimize:
        d['objective'] = {'direction': 'min' if family > 1 else 'max', 'coefficients': {'x': n + 1, 'y': 2}}
    return d


def estimate(family, n):
    unit = ({'items': 1, 'hour': -1}, {'items': 1}, {'meter': 1}, {'bytes': 1})[family]
    f = [{'name': 'quantity', 'low': n + 1, 'high': n + 3, 'unit': unit, 'power': 1},
         {'name': 'duration_or_scale', 'low': 2, 'high': 4,
          'unit': {'hour': 1} if family == 0 else {}, 'power': 1}]
    if family == 2:
        f[1]['power'] = -1
    return {'factors': f, 'output_unit': {'items': 1} if family == 0 else unit,
            'assumptions': ['nonnegative declared scenario bounds'], 'anchors': [],
            'dependencies': ['joint bounds are scenarios; independence is not asserted']}


def sources(n):
    text = f'Reviewed synthetic report {n}: observed inventory is {n + 13}. This is a test input.'
    return {'sources': [{'id': 's', 'text': text, 'sha256': hashlib.sha256(text.encode()).hexdigest(),
                        'observed_at': '2026-10-01T00:00:00Z', 'max_age_seconds': 315360000,
                        'provenance': 'self-authored engineering fixture', 'quality': 'reviewed_input'}],
            'bindings': [{'source_id': 's', 'quote': f'inventory is {n + 13}', 'stance': 'supports'}]}


def causal(family, n):
    a = [n + i / 2 for i in range(6 if family < 2 else 32)]
    return {'design': 'randomized_two_arm' if family != 1 else 'observational',
            'treatment': [x + 2 for x in a], 'control': a, 'population': 'synthetic held-out arms',
            'estimand': 'sample_average_treatment_effect',
            'assumptions': {'random_assignment': True, 'no_interference': True, 'consistent_measurement': True},
            'assignment_evidence': 'generator specification, not field randomization',
            'missingness': 'unknown' if family == 3 else 'none',
            'selection_limits': 'synthetic data only', 'data_tier': 'synthetic'}


def build():
    rows = []
    for stratum in ('semantic', 'estimation', 'formal', 'optimization', 'causal', 'mixed'):
        for family in range(4):
            for n in range(5):
                pid = f'{stratum}-family{family}-variant{n}'
                label = {'answered': True, 'native': None, 'reason': None, 'availability_only': False}
                if stratum == 'semantic':
                    p = problem('semantic', sources(n), pid)  # no approved model identity/weights
                    label.update(answered=False, reason='CAPABILITY_UNAVAILABLE', availability_only=True)
                elif stratum == 'estimation':
                    p = problem('estimation', estimate(family, n), pid)
                elif stratum in ('formal', 'optimization'):
                    impossible = family == 2
                    p = problem(stratum, linear(family, n, impossible, stratum == 'optimization'), pid)
                    label['native'] = ('UNSAT' if impossible else 'SAT') if stratum == 'formal' else ('INFEASIBLE' if impossible else 'OPTIMAL')
                    if stratum == 'formal' and family == 3:
                        p['budget_ms'] = 1
                        label.update(answered=False, native=None, reason='BUDGET_EXHAUSTED')
                elif stratum == 'causal':
                    p = problem('causal', causal(family, n), pid)
                    if family in (1, 3):
                        label.update(answered=False, reason='NON_IDENTIFIABLE')
                else:
                    p = problem('evidence', sources(n), pid)
                    if family == 0:
                        p['claims'].append(problem('estimation', estimate(0, n), pid)['claims'][0] | {'claim_id': 'estimate'})
                    elif family == 1:
                        p['claims'][0]['kind'] = 'ambiguous'
                        label.update(answered=False, reason='UNKNOWN_GEOMETRY')
                    elif family == 2:
                        p['claims'][0]['data']['sources'] = []
                        label.update(answered=False, reason='INSUFFICIENT_EVIDENCE')
                    else:
                        p['consequence']['exposures']['legal_rights'] = None
                        label.update(answered=False, reason='HUMAN_JUDGMENT_REQUIRED')
                rows.append({'item_id': pid, 'stratum': stratum, 'family': f'{stratum}/{family}',
                             'partition': 'heldout', 'problem': p, 'label': label})
    return {'generator_version': 'seed-genome-engineering/1', 'items': rows,
            'limits': ['self-authored', 'structured declared geometries', '20 semantic availability cases do not evaluate model quality',
                       'related development fixture patterns disclosed', '5 formal budget-unknown cases; native UNKNOWN tested separately']}


if __name__ == '__main__':
    (HERE / 'suite.json').write_text(json.dumps(build(), indent=2) + '\n')
