"""Failure-diverse checker: stdlib only, original input, no method implementation imports.

A separate process rederives bounded calculations. Shared Python runtime, repository,
input data and author are disclosed dependencies. This is not independent empirical review.
"""
from fractions import Fraction
import hashlib
import itertools
import math
from datetime import datetime, timezone

TYPES = {'estimation': 'scenario_bounds', 'formal': 'finite_model', 'optimization': 'bounded_optimum',
         'causal': 'conditional_effect', 'semantic': 'source_bound_interpretation', 'evidence': 'source_binding'}
METHOD_IDS = {'estimation':'interval-product/1', 'formal':'z3-bounded-linear/1',
              'optimization':'cp-sat-bounded-linear/1', 'causal':'randomized-two-arm/1',
              'semantic':'ollama-grounded/1', 'evidence':'source-binding/1'}


def verify(c, a):
    findings = []
    try:
        assert a['claim_id'] == c['claim_id'] and a['kind'] == c['kind'], 'claim substitution'
        assert a['method'] == METHOD_IDS.get(c['kind']), 'method substitution'
        assert a['proof_class'] == TYPES.get(c['kind'], 'none'), 'proof type'
        assert a['authority_created'] is False and a['empirical_validity'] == 'WORLD_UNVERIFIED', 'authority/world claim'
        r, d = a.get('result'), c['data']
        if a['outcome'] not in ('ANSWERED_WITHIN_SCOPE', 'CONDITIONAL_RESULT'):
            assert a['outcome'] in ('ABSTAIN', 'WAIT', 'ESCALATE', 'REQUEST_EVIDENCE', 'SMALL_EXPERIMENT'), 'outcome'
            assert a['reasons'], 'unexplained abstention'
            return result(True, ['Non-answer checked structurally; abstention justification needs evaluation.'])
        assert r is not None, 'missing result'
        kind = c['kind']
        if kind in ('formal', 'optimization'):
            assert r['formalization'] == d and r['coverage'] == d['coverage'], 'omitted/modified constraint'
            assert r['native_status'] not in ('UNKNOWN', 'MODEL_INVALID'), 'unknown relabeled as answer'
            names = list(d['variables'])
            domains = [range(lo, hi + 1) for lo, hi in d['variables'].values()]
            assert math.prod(map(len, domains)) <= 50000, 'verification ceiling'
            feasible = []
            for values in itertools.product(*domains):
                assignment = dict(zip(names, values))
                holds = True
                for constraint in d['constraints']:
                    left = sum(assignment[n] * coefficient for n, coefficient in constraint['coefficients'].items())
                    right = constraint['rhs']
                    holds &= {'<=': left <= right, '>=': left >= right, '==': left == right}[constraint['op']]
                if holds:
                    feasible.append(assignment)
            s = r['native_status']
            assert s in (('SAT', 'UNSAT') if kind == 'formal' else ('OPTIMAL', 'FEASIBLE', 'INFEASIBLE')), 'native status'
            if s in ('UNSAT', 'INFEASIBLE'):
                assert not feasible and r['assignment'] is None, 'counterexample to infeasibility'
            else:
                assert r['assignment'] in feasible, 'invalid assignment'
            if kind == 'optimization' and feasible:
                obj = d['objective']
                values = [sum(x[n] * coef for n, coef in obj['coefficients'].items()) for x in feasible]
                actual = sum(r['assignment'][n] * coef for n, coef in obj['coefficients'].items())
                optimum = (min if obj['direction'] == 'min' else max)(values)
                assert actual == r['objective'] and obj['direction'] == r['direction'], 'objective mismatch'
                if s == 'OPTIMAL':
                    assert actual == optimum and r['gap'] == 0 and r['bound'] == optimum, 'false optimum'
                else:
                    assert (r['bound'] <= optimum if obj['direction'] == 'min' else r['bound'] >= optimum), 'invalid bound'
            findings.append('Exhaustive integer enumeration agrees; real-world translation remains unverified.')
        elif kind == 'estimation':
            lo = hi = Fraction(1)
            unit = {}
            for f in d['factors']:
                l, h = Fraction(str(f['low'])), Fraction(str(f['high']))
                assert 0 <= l <= h and (f['power'] == 1 or l > 0), 'invalid interval'
                lo *= l if f['power'] == 1 else 1 / h
                hi *= h if f['power'] == 1 else 1 / l
                for k, v in f['unit'].items():
                    unit[k] = unit.get(k, 0) + v * f['power']
            assert r['unit'] == d['output_unit'] == {k: v for k, v in unit.items() if v}, 'units'
            assert math.isclose(float(lo), float(r['low']), rel_tol=1e-12, abs_tol=1e-20), 'lower bound'
            assert math.isclose(float(hi), float(r['high']), rel_tol=1e-12, abs_tol=1e-20), 'upper bound'
            assert r['decomposition'] == d['factors'], 'decomposition changed'
            findings.append('Fraction arithmetic agrees with decimal interval propagation; bounds are scenarios.')
        elif kind == 'causal':
            assert d['design'] == 'randomized_two_arm' and d['missingness'] == 'none', 'non-identifiability'
            assert all(d['assumptions'].values()) and d['assignment_evidence'], 'identification assumptions'
            t, ctrl = [[Fraction(str(v)) for v in d[k]] for k in ('treatment', 'control')]
            mt, mc = sum(t) / len(t), sum(ctrl) / len(ctrl)
            se2 = (sum((x - mt) ** 2 for x in t) / (len(t) - 1) / len(t) +
                   sum((x - mc) ** 2 for x in ctrl) / (len(ctrl) - 1) / len(ctrl))
            assert math.isclose(r['effect'], float(mt - mc), abs_tol=1e-10), 'effect mismatch'
            assert math.isclose(r['standard_error'] ** 2, float(se2), abs_tol=1e-10), 'uncertainty mismatch'
            assert r['data_tier'] == d['data_tier'] and r['assumptions'] == d['assumptions'], 'data laundering'
            assert r['population'] == d['population'] and r['estimand'] == d['estimand'], 'scope changed'
            if min(len(t), len(ctrl)) < 30:
                assert r['interval_95'] is None, 'unsupported precision'
            elif r['interval_95']:
                assert math.isclose(r['interval_95'][0], float(mt - mc) - 1.96 * math.sqrt(float(se2)), abs_tol=1e-10), 'interval'
                assert math.isclose(r['interval_95'][1], float(mt - mc) + 1.96 * math.sqrt(float(se2)), abs_tol=1e-10), 'interval'
            findings.append('Exact arm means/variance agree, including reversed treatment sign; design is assumed.')
        elif kind in ('semantic', 'evidence'):
            items = {s['id']: s for s in d['sources']}
            for s in items.values():
                assert hashlib.sha256(s['text'].encode()).hexdigest() == s['sha256'], 'source corruption'
                observed = datetime.fromisoformat(s['observed_at'].replace('Z', '+00:00'))
                assert observed.tzinfo is not None, 'source timezone missing'
                assert 0 <= (datetime.now(timezone.utc) - observed).total_seconds() <= s['max_age_seconds'], 'stale source'
            assert r['source_digests'] == {i: s['sha256'] for i, s in items.items()}, 'source replacement'
            assert r['bindings'], 'unbound output'
            for b in r['bindings']:
                assert b['quote'] and b['quote'] in items[b['source_id']]['text'], 'quote mismatch'
            assert not r['contradiction'] and not any(b['stance'] == 'contradicts' for b in r['bindings']), 'contradiction omitted'
            if kind == 'evidence':
                assert r['bindings'] == d['bindings'], 'evidence omission'
            else:
                assert r['requested_model'] == r['served_model'] == d['model'], 'wrong model'
                assert len(r['model_digest']) == 64 and r['proposal_is_unverified'] is True, 'unsupported semantic claim'
            findings.append('Quotation integrity only; interpretation and source truth require external review.')
        else:
            raise AssertionError('unsupported kind')
        return result(True, findings)
    except (AssertionError, KeyError, ValueError, TypeError, ArithmeticError) as exc:
        return result(False, [str(exc)])


def result(valid, findings):
    return {'valid': valid, 'verifier': 'stdlib-diverse/1', 'findings': findings,
            'authority_created': False, 'independence': 'separate process/algorithm; shared source data, Python, repository and author',
            'scope': 'computational and binding integrity only; no empirical or professional adjudication'}
