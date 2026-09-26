"""Synthetic workload authority, not authenticated founder enrollment."""
import pytest
from compiler.ucl_compiler import compile_constitution
from egregore.local_mission import ROOT
from egregore.runtime import StandingCognitionRuntime
from egregore.contracts import ContractError
from identity.machine_passport import PassportRegistry
from policy.consequence_gate import ConsequenceGate, GrantIssuer
from provenance.commit_witness import WitnessSigner
from provenance.ledger import EvidenceLedger


def test_resume_requires_exact_preexisting_grant_and_reconstructs(tmp_path):
    compiled=compile_constitution(str(ROOT)); path=str(tmp_path/'ledger')
    ledger=EvidenceLedger(compiled.constitution_hash,path); passports=PassportRegistry(); grants=GrantIssuer()
    actor=passports.issue(kind='agent',creator='synthetic-test',owner_organ='kernel',legal_principal='alfonso_lopez',
        declared_capabilities=['cognition.resume'],budget_ceiling_usd=0,consequence_class='internal_write').passport_id
    gate=ConsequenceGate(compiled=compiled,ledger=ledger,passports=passports,grants=grants,signer=WitnessSigner(env='development'))
    runtime=StandingCognitionRuntime(ledger=ledger,proposers={},evaluators={}); runtime.suspend(actor=actor,reason='stop')
    with pytest.raises(ContractError): runtime.resume(actor=actor,authorization_hash='sha256:'+'a'*64)
    grant=grants.issue_single_action(proposal=runtime.resume_proposal(actor),policy_version='1.0.0')
    with pytest.raises(ContractError): runtime.resume(actor=actor,gate=gate,grant=dict(grant,objective='another stop'))
    runtime.resume(actor=actor,gate=gate,grant=grant); assert not runtime.is_suspended; ledger.close()
    ledger=EvidenceLedger(compiled.constitution_hash,path)
    restored=StandingCognitionRuntime(ledger=ledger,proposers={},evaluators={}); assert not restored.is_suspended
    restored.suspend(actor=actor,reason='new stop')
    gate=ConsequenceGate(compiled=compiled,ledger=ledger,passports=passports,grants=grants,signer=WitnessSigner(env='development'))
    with pytest.raises(ContractError): restored.resume(actor=actor,gate=gate,grant=grant)
    assert restored.is_suspended; ledger.close()


def test_legacy_bare_hash_resume_cannot_clear_stop():
    ledger=EvidenceLedger('sha256:'+'b'*64); runtime=StandingCognitionRuntime(ledger=ledger,proposers={},evaluators={})
    runtime.suspend(actor='synthetic',reason='stop')
    ledger.append(runtime.RESUME_RECORD,{'actor':'fake-founder','authorization_hash':'sha256:'+'a'*64})
    assert StandingCognitionRuntime(ledger=ledger,proposers={},evaluators={}).is_suspended


def test_comparison_retains_ties_and_regressions():
    from egregore.brief_learning import compare
    cases=[dict(id='one',findings=[dict(id='dep',kind='dependency')],expected='dep')]
    assert compare(cases)['decision']=='no_improvement'
    cases[0]['findings'].append(dict(id='auth',kind='authority'))
    assert compare(cases)['decision']=='regress'
