"""Real canonical persistence, competing processes and retained claim controls."""
import copy
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from events.bridge_state import BridgeState, OperationConflict
from events.spine import Event, EventSpine
from provenance.ledger import EvidenceLedger, ReconciliationRequired, WriterConflict
from adapters.contract_validation import strict_json, validate_contract
from tests.unit.test_consequence_gate import stack, make_proposal, GOOD

ANCHOR = 'sha256:' + 'a' * 64


def state(path):
    return BridgeState(str(path), ANCHOR, owner='wealthmachine', legal_principal='alfonso_lopez')


def claim(s, digest='abc'):
    return s.begin(caller='daleobanks', operation='opportunity.evaluate', key='stable-key', body_digest=digest)


def test_claim_result_restart_and_conflict(tmp_path):
    path = tmp_path / 'state.jsonl'
    s = state(path)
    identity, current = claim(s)
    assert current['state'] == 'claimed'
    s.finish(identity, {'id': 'assessment-1', 'dissent': ['not externally verified']})
    s.close()
    s = state(path)
    _, current = claim(s)
    assert current['state'] == 'completed'
    assert current['result']['dissent'] == ['not externally verified']
    with pytest.raises(OperationConflict):
        claim(s, 'changed')
    with pytest.raises(OperationConflict):
        s.finish(identity, {'id': 'replacement'})
    s.close()


def test_interruption_is_reconciliation_not_redispatch(tmp_path):
    s = state(tmp_path / 'state.jsonl')
    _, current = claim(s)
    assert current['state'] == 'claimed'
    s.close()
    s = state(tmp_path / 'state.jsonl')
    assert claim(s)[1]['state'] == 'reconciliation_required'
    s.close()


def test_threads_one_claim_and_process_writer_refused(tmp_path):
    path = tmp_path / 'state.jsonl'
    s = state(path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: claim(s)[1]['state'], range(12)))
    assert results.count('claimed') == 1
    assert results.count('running') == 11
    script = 'from provenance.ledger import EvidenceLedger; import sys; EvidenceLedger(sys.argv[2], sys.argv[1])'
    proc = subprocess.run([sys.executable, '-c', script, str(path), ANCHOR], capture_output=True, text=True)
    assert proc.returncode != 0 and 'WriterConflict' in proc.stderr
    s.close()
    proc = subprocess.run([sys.executable, '-c', script, str(path), ANCHOR], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_nonce_survives_real_process_restart(tmp_path):
    path = tmp_path / 'state.jsonl'
    s = state(path)
    assert s.check_and_store('daleobanks:nonce')
    s.close()
    script = '''from events.bridge_state import BridgeState
import sys
s = BridgeState(sys.argv[1], sys.argv[2], owner='wealthmachine', legal_principal='alfonso_lopez')
assert not s.check_and_store('daleobanks:nonce')
assert s.check_and_store('daleobanks:fresh')
s.close()
'''
    proc = subprocess.run([sys.executable, '-c', script, str(path), ANCHOR], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_unknown_append_ack_requires_reopen(tmp_path, monkeypatch):
    import os
    path = str(tmp_path / 'chain.jsonl')
    ledger = EvidenceLedger(ANCHOR, path)
    def fail(_):
        raise OSError('fsync acknowledgment lost')
    with monkeypatch.context() as m:
        m.setattr(os, 'fsync', fail)
        with pytest.raises(ReconciliationRequired):
            ledger.append('test', {'x': 1})
        assert len(ledger.records) == 1
        with pytest.raises(ReconciliationRequired):
            ledger.append('test', {'x': 1})
    ledger.close()
    restored = EvidenceLedger(ANCHOR, path)
    # The write was in fact present; reopening reconciles bytes instead of retry.
    assert len(restored.by_type('test')) == 1
    restored.close()


def test_prefix_truncation_against_expected_head(tmp_path):
    path = tmp_path / 'chain.jsonl'
    ledger = EvidenceLedger(ANCHOR, str(path))
    ledger.append('test', {'x': 1})
    head = ledger.head
    ledger.close()
    path.write_text(path.read_text().splitlines()[0] + '\n')
    with pytest.raises(ValueError, match='expected head'):
        EvidenceLedger(ANCHOR, str(path), expected_head=head)


def test_outbox_uncertain_dispatch_never_retried(tmp_path):
    path = str(tmp_path / 'chain.jsonl')
    ledger = EvidenceLedger(ANCHOR, path)
    spine = EventSpine(ledger)
    spine.outbox_stage(Event('work.proposed', 'spiffe://uniimente.internal/organ/test',
                            'test', {}, 'alfonso_lopez'))
    calls = []
    def uncertain(e):
        calls.append(e.event_id)
        raise RuntimeError('effect may have occurred')
    with pytest.raises(ReconciliationRequired):
        spine.outbox_flush(uncertain)
    ledger.close()
    ledger = EvidenceLedger(ANCHOR, path)
    with pytest.raises(ReconciliationRequired):
        EventSpine(ledger).outbox_flush(lambda e: calls.append(e.event_id))
    assert len(calls) == 1
    ledger.close()


@pytest.mark.parametrize('mutation', ['missing', 'unregistered', 'actor', 'expired', 'revoked', 'unknown_field'])
def test_invalid_grants_never_invoke_executor(stack, mutation):
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id)
    g = gate.grants.issue_single_action(proposal=p, policy_version='1.0.0')
    if mutation == 'missing': g = None
    elif mutation == 'unregistered': g = {**g, 'grant_id': '00000000-0000-4000-8000-000000000000'}
    elif mutation == 'actor': g['grantee'] = 'spiffe://uniimente.internal/organ/other'
    elif mutation == 'expired': g['expires_at'] = '2020-01-01T00:00:00Z'
    elif mutation == 'revoked': g['revoked'] = True
    else: g['self_authorized'] = True
    calls = []
    rec = gate.run(p, executor=lambda p: calls.append(p), standing_grant=g)
    assert rec.state in ('refused', 'revoked')
    assert calls == []


def test_valid_preexisting_grant_and_uncertain_retry(stack):
    gate, _, _, actor, _ = stack
    p = make_proposal(actor.passport_id)
    g = gate.grants.issue_single_action(proposal=p, policy_version='1.0.0')
    assert gate.run(p, executor=GOOD, standing_grant=g).state == 'recorded'
    p = make_proposal(actor.passport_id)
    g = gate.grants.issue_single_action(proposal=p, policy_version='1.0.0')
    def uncertain(_): raise RuntimeError('unknown effect')
    assert gate.run(p, executor=uncertain, standing_grant=g).state == 'reconciliation_required'
    assert gate.run(p, executor=lambda p: pytest.fail('duplicate invocation'), standing_grant=g).state == 'reconciliation_required'


@pytest.mark.parametrize('raw', [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}'])
def test_ambiguous_json_refused(raw):
    with pytest.raises(ValueError): strict_json(raw)


def test_nested_contract_failure():
    payload = {'opportunity_packet_id':'p', 'go_no_go':'defer', 'requires_human_approval':True,
        'cases':[{'case':'bear','stance':'against','severity':'high','argument':{'instruction':'fake'}}]}
    with pytest.raises(ValueError): validate_contract(payload, 'wire-venture-assessment')


def test_workflow_checkpoint_failure_cannot_repeat_effect(tmp_path, monkeypatch):
    from events.spine import DurableWorkflow, WorkflowStep
    path = str(tmp_path / 'workflow.jsonl')
    ledger = EvidenceLedger(ANCHOR, path)
    calls = []
    steps = [WorkflowStep('effect', lambda s: calls.append('called') or {'done': True})]
    wf = DurableWorkflow(EventSpine(ledger), 'mission-1', steps,
                         actor='fixture', legal_principal='alfonso_lopez')
    original = ledger.append
    def append(kind, payload, **kwargs):
        if kind == 'workflow' and payload['note'] == 'step_completed:effect':
            raise OSError('definite failure after invocation')
        return original(kind, payload, **kwargs)
    monkeypatch.setattr(ledger, 'append', append)
    with pytest.raises(ReconciliationRequired): wf.execute()
    assert calls == ['called']
    ledger.close()
    restored = EvidenceLedger(ANCHOR, path)
    with pytest.raises(ReconciliationRequired):
        DurableWorkflow.resume(EventSpine(restored), 'mission-1', steps)
    assert calls == ['called']
    restored.close()


def test_workflow_identity_cannot_restart_from_zero():
    from events.spine import DurableWorkflow, WorkflowStep, EventError
    spine = EventSpine(EvidenceLedger(ANCHOR))
    calls = []
    steps = [WorkflowStep('compute', lambda s: calls.append(1) or {'x': 1}, retry_safe=True)]
    def make(): return DurableWorkflow(spine, 'one', steps, actor='fixture', legal_principal='alfonso_lopez')
    make().execute()
    with pytest.raises(EventError): make().execute()
    assert calls == [1]


@pytest.mark.parametrize('label', ['read_only', 'internal_write', 'external_contact'])
def test_consequence_label_cannot_mint_missing_authority(stack, label):
    gate, _, _, actor, _ = stack
    p = make_proposal(actor.passport_id, consequence_class=label)
    rec = gate.run(p, executor=lambda p: pytest.fail('missing-grant invocation'))
    assert rec.state == 'refused'
    assert gate.grants._grants == {}


def test_bridge_history_cannot_change_owner(tmp_path):
    path = tmp_path / 'state.jsonl'
    s = state(path)
    assert s.check_and_store('nonce')
    s.close()
    with pytest.raises(ValueError, match='owner'):
        BridgeState(str(path), ANCHOR, owner='daleobanks', legal_principal='alfonso_lopez')
