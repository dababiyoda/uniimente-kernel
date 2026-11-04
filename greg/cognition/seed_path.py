"""Deterministic competency selection within the canonical GREG capability invocation.

No scheduler, registry, model provider fallback, authority or learning store here.
Input features are signed declarations, not proof of world truth. Unknown/risky
geometry is kept out of this bounded internal-advice seed.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from greg.capabilities import CapabilityError, _no_network_preexec
from cortex.seed.contracts import (CognitiveCapabilityProfile, EXPOSURES, METHODS, PROOFS,
                                      VERSION, validate_artifact, validate_problem)
from cortex.seed.methods import artifact
from provenance.ledger import sha256_json

ROOT = Path(__file__).resolve().parents[2]
POLICY = 'static-smallest-sufficient/1'


def profile(kind):
    return CognitiveCapabilityProfile(METHODS[kind], kind, PROOFS[kind],
        scope={'formal': 'bounded integer linear feasibility, <=50000 assignments',
               'optimization': 'bounded integer linear allocation, <=50000 assignments',
               'causal': 'declared randomized two-arm sample effect',
               'estimation': 'nonnegative dimensioned interval products',
               'semantic': 'local Ollama quote-bound interpretation only',
               'evidence': 'exact quotation binding and freshness'}[kind],
        dependencies=({'formal': ('z3-solver==5.1.0.0',), 'optimization': ('ortools==9.14.6206',),
                       'semantic': ('operator-configured-local-Ollama-and-licensed-weights',)}.get(kind, ())))


def eligible(p, c):
    risk = p['consequence']
    if risk['policy_refusal']:
        return 'POLICY_REFUSAL'
    if risk['class'] != 'read_only':
        return 'AUTHORITY_REQUIRED'
    if risk['human_judgment'] or any(v is None or v > 0 for v in risk['exposures'].values()):
        return 'HUMAN_JUDGMENT_REQUIRED'
    if c['kind'] not in METHODS:
        return 'UNKNOWN_GEOMETRY'
    if c['conditions'].get('out_of_distribution') is True:
        return 'OUT_OF_DISTRIBUTION'
    module = {'formal': 'z3', 'optimization': 'ortools'}.get(c['kind'])
    if module and importlib.util.find_spec(module) is None:
        return 'CAPABILITY_UNAVAILABLE'
    if c['kind'] == 'semantic' and not c['data'].get('model'):
        return 'CAPABILITY_UNAVAILABLE'
    return None


def _worker(mode, payload, *, timeout, network=False, stop_check=None):
    if stop_check and stop_check():
        raise InterruptedError('canonical stop requested')
    env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PYTHONPATH': str(ROOT),
           'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'}
    cmd = [sys.executable, '-m', 'greg.cognitive_worker', mode]
    if sys.platform == 'darwin' and not network:
        cmd = ['/usr/bin/sandbox-exec', '-p', '(version 1)(allow default)(deny network*)', *cmd]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, cwd=ROOT, env=env,
                            preexec_fn=_no_network_preexec if sys.platform == 'linux' and not network else None)
    deadline = time.monotonic() + max(.001, timeout)
    raw = json.dumps(payload, allow_nan=False).encode()
    try:
        while True:
            if stop_check and stop_check():
                raise InterruptedError('canonical stop requested during computation')
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(cmd, timeout)
            try:
                stdout, stderr = proc.communicate(input=raw, timeout=min(.05, remaining))
                break
            except subprocess.TimeoutExpired:
                raw = None  # communicate retains the pending input across waits
    except BaseException:
        proc.kill()
        proc.communicate()
        raise
    if proc.returncode:
        raise CapabilityError('bounded worker failed: ' + stderr.decode(errors='replace')[-300:])
    if len(stdout) > 131072:
        raise CapabilityError('worker output ceiling exceeded')
    return json.loads(stdout)


def evaluate_problem(p, *, stop_check=None):
    """Pure development computation. Production calls use solve(), after the Gate."""
    validate_problem(p)
    started = time.monotonic()
    deadline = started + p['budget_ms'] / 1000
    outputs = []
    refused = False
    for c in p['claims']:
        reason = 'POLICY_REFUSAL' if refused else eligible(p, c)
        remaining = deadline - time.monotonic()
        verification = None
        if reason:
            outcome = 'ESCALATE' if reason in ('AUTHORITY_REQUIRED', 'HUMAN_JUDGMENT_REQUIRED') else 'ABSTAIN'
            a = artifact(c, outcome=outcome, reasons=[reason])
        elif remaining < .05:
            a = artifact(c, outcome='ABSTAIN', reasons=['BUDGET_EXHAUSTED'])
        else:
            try:
                # Reserve half the remaining allocation for mandatory independent verification.
                allocation = remaining / (len(p['claims']) - len(outputs))
                a = _worker('compute', {'claim': c, 'budget_ms': max(1, int(allocation * 400))},
                            timeout=allocation / 2, network=c['kind'] == 'semantic', stop_check=stop_check)
                validate_artifact(a)
                verification = _worker('verify', {'claim': c, 'artifact': a},
                                       timeout=max(.001, min(allocation / 2, deadline - time.monotonic())),
                                       stop_check=stop_check)
                if not verification['valid']:
                    a = artifact(c, outcome='ABSTAIN', reasons=['CONTRADICTION'])
            except subprocess.TimeoutExpired:
                a = artifact(c, outcome='ABSTAIN', reasons=['TIMEOUT'])
            except InterruptedError:
                a = artifact(c, outcome='WAIT', reasons=['AUTHORITY_REQUIRED'])
            except (CapabilityError, ValueError, KeyError):
                a = artifact(c, outcome='ABSTAIN', reasons=['CAPABILITY_UNAVAILABLE'])
        refused = refused or 'POLICY_REFUSAL' in a['reasons']
        outputs.append({**a, 'verification': verification, 'geometry': {'epistemic_class': c['kind'],
                        'conditions': c['conditions']}, 'eligible_alternatives': [] if reason else [METHODS[c['kind']]],
                        'selection_rationale': reason or 'Only implemented eligible method for this declared geometry; no superiority claim.'})
    answered = all(a['outcome'] in ('ANSWERED_WITHIN_SCOPE', 'CONDITIONAL_RESULT') and
                   a['verification'] and a['verification']['valid'] for a in outputs)
    return {'schema_version': VERSION, 'problem_id': p['problem_id'], 'input_digest': sha256_json(p),
            'policy_version': POLICY, 'consequence': p['consequence'], 'claims': outputs,
            'answered': answered, 'outcome': 'CONDITIONAL_RESULT' if answered else 'ABSTAIN',
            'elapsed_ms': round((time.monotonic() - started) * 1000, 3), 'cost_usd': 0,
            'cost_limits': 'wall time measured; CPU/RAM bounded; energy and maintenance cost unmeasured',
            'authority_created': False, 'execution_mode': 'consequence-inert-computation',
            'next_step': 'Review assumptions before any consequential use.' if answered else
                         'Resolve per-claim reasons; no automatic rerouting or promotion.',
            'verifier_digest': hashlib.sha256((ROOT / 'cortex/seed/verify.py').read_bytes()).hexdigest()}


def solve(params, ctx):
    if ctx.journal is None or not ctx.authority_ref or not ctx.grant_id:
        raise CapabilityError('canonical mission authority and journal required before computation')
    p = validate_problem(params['problem'])
    key = [ctx.mission_id, p['problem_id']]
    for event in ctx.journal.replay('cognition.receipt'):
        r = event.payload
        if [r['mission_id'], r['problem_id']] == key:
            if r['input_digest'] != sha256_json(p):
                raise CapabilityError('problem ID already bound; use a new version')
            return r
    r = evaluate_problem(p, stop_check=ctx.stop_check)
    from cortex.seed.projections import enrich
    enrich(p, r)
    r.update({'receipt_id': sha256_json({'mission': ctx.mission_id, 'problem': p}),
              'mission_id': ctx.mission_id, 'authority_ref': ctx.authority_ref, 'grant_id': ctx.grant_id,
              'kernel_policy_version': ctx.policy_version})
    ctx.journal.record('cognition.receipt', r, key=key, sensitivity='confidential')
    return r


def settle(params, ctx):
    """Append a signed, attributable observation. A declaration is never independent evidence."""
    if ctx.journal is None or not ctx.authority_ref or not ctx.grant_id:
        raise CapabilityError('canonical authority required')
    if set(params) != {'outcome_id', 'receipt_id', 'tier', 'score', 'evidence_refs', 'supersedes', 'conditions'}:
        raise CapabilityError('unsupported outcome fields; protected updates refused')
    if params['tier'] == 'independently_verified':
        raise CapabilityError('independent real-world observation adapter unavailable; computation appraisal is insufficient')
    if params['tier'] not in ('benchmark', 'synthetic', 'reported_observation', 'computation_verified'):
        raise CapabilityError('unknown evidence tier')
    if params['score'] is not None and (type(params['score']) not in (float, int) or not 0 <= params['score'] <= 1):
        raise CapabilityError('score must be null or 0..1')
    receipts = {e.payload['receipt_id']: e for e in ctx.journal.replay('cognition.receipt')}
    receipt = receipts.get(params['receipt_id'])
    if receipt is None or receipt.payload['mission_id'] != ctx.mission_id:
        raise CapabilityError('receipt must belong to this mission')
    refs = params['evidence_refs']
    events = {e.event_id: e for e in ctx.journal.replay()}
    if not refs or any(ref not in events for ref in refs):
        raise CapabilityError('retained observation evidence required')
    if params['tier'] == 'computation_verified':
        if not any(events[ref].type == 'greg.mission.appraised' and
                   events[ref].payload.get('verdict') == 'VERIFIED' and
                   events[ref].payload.get('mission_id') == ctx.mission_id for ref in refs):
            raise CapabilityError('independent appraisal of this mission required')
    outcome = {**params, 'authority_ref': ctx.authority_ref, 'authority_created': False,
               'score_status': 'reported assessment; not authenticated performance',
               'verification_scope': 'computational integrity only' if params['tier'] == 'computation_verified' else 'reported observation',
               'methods': [{'method': c['method'], 'geometry': c['geometry'],
                    'native_version': (c.get('result') or {}).get('version'),
                    'model_digest': (c.get('result') or {}).get('model_digest'),
                    'verifier_digest': receipt.payload['verifier_digest']}
                    for c in receipt.payload['claims']],
               'attribution': 'reported contribution, not proven causal credit'}
    retained = [e.payload for e in ctx.journal.replay('cognition.outcome')]
    prior = next((o for o in retained if o['outcome_id'] == params['outcome_id']), None)
    if prior:
        # Retry can have a new grant/command. Observation content must remain identical.
        if any(prior[k] != v for k, v in params.items()):
            raise CapabilityError('outcome ID reused with different content')
        return prior
    latest = [o for o in retained if o['receipt_id'] == params['receipt_id']]
    if params['supersedes'] != (latest[-1]['outcome_id'] if latest else None):
        raise CapabilityError('correction must supersede the current observation')
    ctx.journal.record('cognition.outcome', outcome, key=params['outcome_id'], sensitivity='confidential')
    return outcome


def status(params, ctx):
    if ctx.journal is None:
        raise CapabilityError('canonical journal required')
    rows = [e.payload for e in ctx.journal.replay('cognition.receipt')
            if e.payload['mission_id'] == ctx.mission_id and e.payload['problem_id'] == params['problem_id']]
    if not rows:
        return {'exists': False, 'answered': False, 'receipt': None}
    r = rows[-1]
    # Reconstruct the original signed problem, not the solver's translation.
    specs = [e.payload['spec'] for e in ctx.journal.replay('mission.registered')
             if e.payload['mission_id'] == ctx.mission_id]
    problems = [s['params']['problem'] for spec in specs for s in spec['strategies']
                if s.get('capability') == 'cognition.seed.solve' and
                s.get('params', {}).get('problem', {}).get('problem_id') == params['problem_id']]
    valid = bool(problems and sha256_json(problems[0]) == r['input_digest'] and r['answered'])
    if valid:
        p = problems[0]
        valid = len(p['claims']) == len(r['claims'])
        for c, a in zip(p['claims'], r['claims']):
            if eligible(p, c):
                valid = False
                break
            try:
                check = _worker('verify', {'claim': c, 'artifact': a}, timeout=2, stop_check=ctx.stop_check)
                valid = valid and check['valid']
            except (CapabilityError, ValueError, subprocess.TimeoutExpired, InterruptedError):
                valid = False
    return {'exists': True, 'answered': valid, 'receipt': r,
            'scope': 'rechecked computation only; not real-world acceptance'}
