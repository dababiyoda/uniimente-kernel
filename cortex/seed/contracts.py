"""Versioned cognition data inside Capability Genome; none of these types authorizes work."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import json
import math
import re

VERSION = 'cognition/1'
METHODS = {'semantic': 'ollama-grounded/1', 'estimation': 'interval-product/1',
           'formal': 'z3-bounded-linear/1', 'optimization': 'cp-sat-bounded-linear/1',
           'causal': 'randomized-two-arm/1', 'evidence': 'source-binding/1'}
PROOFS = {'semantic': 'source_bound_interpretation', 'estimation': 'scenario_bounds',
          'formal': 'finite_model', 'optimization': 'bounded_optimum',
          'causal': 'conditional_effect', 'evidence': 'source_binding'}
OUTCOMES = {'ANSWERED_WITHIN_SCOPE', 'CONDITIONAL_RESULT', 'ABSTAIN', 'WAIT',
            'REQUEST_EVIDENCE', 'SMALL_EXPERIMENT', 'ESCALATE'}
REASONS = {'UNKNOWN_GEOMETRY', 'NO_ELIGIBLE_METHOD', 'INSUFFICIENT_EVIDENCE', 'WORLD_UNVERIFIED',
           'NON_IDENTIFIABLE', 'FORMALIZATION_INCOMPLETE', 'MODEL_INVALID', 'SOLVER_UNKNOWN',
           'TIMEOUT', 'BUDGET_EXHAUSTED', 'CONTRADICTION', 'OUT_OF_DISTRIBUTION',
           'HUMAN_JUDGMENT_REQUIRED', 'AUTHORITY_REQUIRED', 'POLICY_REFUSAL', 'CAPABILITY_UNAVAILABLE'}
EXPOSURES = ('physical', 'financial', 'legal_rights', 'privacy', 'reputational', 'discrimination',
             'third_party', 'disclosure', 'irreversibility', 'dependency', 'systemic', 'tail_risk')


class InvalidProblem(ValueError):
    pass


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)) or len(str(value)) > 40:
        raise InvalidProblem('bounded numeric literal required')
    try:
        n = Decimal(str(value))
    except InvalidOperation as exc:
        raise InvalidProblem('numeric literal required') from exc
    if not n.is_finite() or abs(n) > Decimal('1e12') or (n and abs(n) < Decimal('1e-12')):
        raise InvalidProblem('nonfinite or out-of-scope number')
    return n


def integer(n):
    if type(n) is not int or abs(n) > 1000000:
        raise InvalidProblem('bounded integer required')
    return n


def linear(data, *, optimize=False):
    """No executable expressions; maximum 50,000 assignments permits diverse verification."""
    if set(data) - {'variables', 'constraints', 'objective', 'coverage'}:
        raise InvalidProblem('unknown formalization field')
    variables = data['variables']
    if not isinstance(variables, dict) or not 1 <= len(variables) <= 12:
        raise InvalidProblem('1..12 variables required')
    size = 1
    for name, bounds in variables.items():
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,31}', name) or len(bounds) != 2:
            raise InvalidProblem('invalid variable')
        lo, hi = map(integer, bounds)
        if hi < lo or hi - lo > 32:
            raise InvalidProblem('invalid domain')
        size *= hi - lo + 1
    if size > 50000:
        raise InvalidProblem('verification search ceiling exceeded')
    constraints = data['constraints']
    if not isinstance(constraints, list) or len(constraints) > 64:
        raise InvalidProblem('constraint ceiling exceeded')
    ids = set()
    for c in constraints:
        if set(c) != {'id', 'coefficients', 'op', 'rhs'} or c['op'] not in ('<=', '>=', '=='):
            raise InvalidProblem('invalid constraint')
        if not isinstance(c['id'], str) or not c['id'] or c['id'] in ids:
            raise InvalidProblem('constraint IDs must be unique')
        ids.add(c['id'])
        _coefficients(c['coefficients'], variables)
        integer(c['rhs'])
    coverage = data['coverage']
    if set(coverage) != {'represented', 'omissions', 'assumptions', 'reviewed'}:
        raise InvalidProblem('explicit formalization coverage required')
    if set(coverage['represented']) != ids or coverage['omissions'] or coverage['reviewed'] is not True:
        raise InvalidProblem('FORMALIZATION_INCOMPLETE')
    if not isinstance(coverage['assumptions'], list):
        raise InvalidProblem('assumptions required')
    if optimize:
        obj = data['objective']
        if set(obj) != {'direction', 'coefficients'} or obj['direction'] not in ('min', 'max'):
            raise InvalidProblem('invalid objective')
        _coefficients(obj['coefficients'], variables)
    elif 'objective' in data:
        raise InvalidProblem('formal feasibility cannot claim optimization')
    return size


def _coefficients(c, variables):
    if not isinstance(c, dict) or not c or set(c) - set(variables):
        raise InvalidProblem('unknown variable in expression')
    for n in c.values():
        integer(n)


@dataclass(frozen=True)
class CognitiveCapabilityProfile:
    """Optional Genome extension. Availability/authorization remain runtime checks."""
    method_id: str
    epistemic_class: str
    proof_class: str
    scope: str
    dependencies: tuple = ()
    owner: str = 'uniimente-kernel'
    version: str = VERSION
    limits: str = 'bounded internal advice; empirical applicability unverified'
    memory_scope: str = 'canonical mission ledger'
    update_rule: str = 'append verified conditional outcomes; no automatic promotion'
    authority_ceiling: str = 'read_only'
    health: str = 'checked_per_invocation'
    shutdown: str = 'bounded subprocess; canonical STOP blocks subsequent invocations'
    observations: tuple = ('signed problem inputs', 'native solver artifacts', 'independent checks')
    local_state: str = 'ephemeral bounded subprocess'
    target_state: str = 'typed conditional result or explained non-answer'
    permitted_transitions: tuple = ('eligible -> compute -> verify -> retain', 'ineligible -> abstain/escalate')
    recruitment: str = 'declared geometry plus canonical mission grant; no score-based eligibility'
    inhibition: str = 'unknown exposure, refusal, exhausted verification budget, STOP, unavailable dependency'
    activation_state: str = 'catalogued builtin; invocation requires signed mission scope'
    evidence_requirements: tuple = ('original signed problem', 'typed artifact', 'separate verifier verdict')
    failure_signatures: tuple = ('timeout', 'missing dependency', 'invalid model', 'source mismatch', 'scope mismatch')
    abstention_rules: tuple = ('no admissible method -> abstain', 'unresolved harm -> human judgment', 'refusal -> stop composition')
    escalation: str = 'existing GREG mission decision path; no software professional stand-in'
    budget_envelope: str = '0..10s including verification; worker <=2GiB AS, <=12 CPU seconds; no paid calls'
    lineage: tuple = ('PR137 canonical GREG', 'PR141 canonical Cortex', 'POLYINTELLIGENCE-SEED-2026-10-01')
    conditions_of_validity: str = 'input assumptions only; WORLD_UNVERIFIED'
    execution_permissions: str = 'canonical Gate per mission/target, distinct from inferential scope'
    failure_diversity: str = 'solver versus stdlib rederivation; shared data, author, repository, Python'
    benchmark_history: tuple = ()

    def validate(self):
        return [] if (METHODS.get(self.epistemic_class) == self.method_id and
                      PROOFS.get(self.epistemic_class) == self.proof_class and
                      self.authority_ceiling == 'read_only') else ['invalid cognition profile']


def validate_problem(p):
    if not isinstance(p, dict) or len(json.dumps(p, allow_nan=False).encode()) > 32768:
        raise InvalidProblem('problem exceeds 32KiB')
    required = {'schema_version', 'problem_id', 'objective', 'consequence', 'budget_ms', 'claims'}
    if set(p) != required or p['schema_version'] != VERSION:
        raise InvalidProblem('unsupported problem contract')
    if not isinstance(p['problem_id'], str) or not p['problem_id'] or not isinstance(p['objective'], str):
        raise InvalidProblem('problem identity and objective required')
    if type(p['budget_ms']) is not int or not 0 <= p['budget_ms'] <= 10000:
        raise InvalidProblem('budget must be 0..10000ms including mandatory verification')
    consequence = p['consequence']
    if set(consequence) != {'class', 'exposures', 'human_judgment', 'policy_refusal'}:
        raise InvalidProblem('explicit consequence assessment required')
    if consequence['class'] not in ('read_only', 'internal_write', 'external_contact', 'financial', 'irreversible'):
        raise InvalidProblem('unknown consequence')
    if set(consequence['exposures']) != set(EXPOSURES):
        raise InvalidProblem('all exposure dimensions required; null means unknown')
    for v in consequence['exposures'].values():
        if v is not None and (type(v) is not int or not 0 <= v <= 3):
            raise InvalidProblem('severity must be null or integer 0..3')
    if any(type(consequence[k]) is not bool for k in ('human_judgment', 'policy_refusal')):
        raise InvalidProblem('explicit judgment/refusal flags required')
    if not isinstance(p['claims'], list) or not 1 <= len(p['claims']) <= 8:
        raise InvalidProblem('1..8 subclaims required')
    ids = set()
    for c in p['claims']:
        if set(c) != {'claim_id', 'kind', 'data', 'conditions'} or not isinstance(c['data'], dict):
            raise InvalidProblem('invalid claim contract')
        if not isinstance(c['claim_id'], str) or not c['claim_id'] or c['claim_id'] in ids:
            raise InvalidProblem('distinct claim IDs required')
        if not isinstance(c['conditions'], dict) or not isinstance(c['kind'], str):
            raise InvalidProblem('invalid conditions')
        ids.add(c['claim_id'])
    return p


def validate_artifact(a):
    if a['outcome'] not in OUTCOMES or set(a['reasons']) - REASONS or a['authority_created'] is not False:
        raise InvalidProblem('invalid outcome/authority')
    if a['proof_class'] != PROOFS.get(a['kind'], 'none'):
        raise InvalidProblem('epistemic type mismatch')
    if a['outcome'] in ('ANSWERED_WITHIN_SCOPE', 'CONDITIONAL_RESULT') and a.get('result') is None:
        raise InvalidProblem('answered claim without artifact')
    if a['empirical_validity'] != 'WORLD_UNVERIFIED':
        raise InvalidProblem('seed cannot establish world validity')
    return a
