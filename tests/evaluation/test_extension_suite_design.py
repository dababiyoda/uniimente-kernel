"""Independent oracle/design checks; native qualification runs separately after freeze."""
from collections import Counter
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

PATH=Path(__file__).resolve().parents[2]/'scripts/evaluate_cognition_extensions.py'
SPEC=importlib.util.spec_from_file_location('extension_evaluation',PATH)
evaluation=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(evaluation)


def test_structural_extension_inputs_are_pure_opaque_and_keep_full_denominator(monkeypatch):
    monkeypatch.setattr(evaluation,'reason',lambda *a,**kw:pytest.fail('generation may not execute a candidate'))
    monkeypatch.setattr(Path,'write_text',lambda *a,**kw:pytest.fail('generation is pure'))
    suite=evaluation.generate_suite()
    assert suite==evaluation.generate_suite()
    assert len(suite['cases'])==100
    assert set(Counter(c['stratum'] for c in suite['cases']).values())=={20}
    assert set(Counter(c['group'] for c in suite['cases']).values())=={5}
    assert len({c['group'] for c in suite['cases']})==20
    for case in suite['cases']:
        assert set(case['request'])=={'problem_id','operation','data','geometry'}
        assert case['request']['problem_id'].startswith('extension:')
        assert case['stratum'] not in case['request']['problem_id']
        assert case['request']['geometry']['latency_limit']==10
        assert case['request']['geometry']['compute_limit']==100000
    assert 'alias' in suite['search_scope']


def test_original_input_oracles_handle_parallel_zero_unreachable_and_continuous_vertices():
    graph={'edges':[['s','a',3],['s','a',1],['a','t',.5],['s','t',2]],'start':'s','goal':'t'}
    assert evaluation.shortest_oracle(graph)==1.5
    assert evaluation.shortest_oracle({**graph,'goal':'unreachable'}) is None
    flow={'nodes':['s','a','t'],'edges':[['s','a',2],['s','a',3],['a','a',99],['a','t',4]],'source':'s','sink':'t'}
    assert evaluation.flow_oracle(flow)==4
    lp={'variables':{'x':[-2,2],'y':[-2,2]},'constraints':[{'coefficients':{'x':1,'y':2},'op':'==','rhs':.5}],
        'objective':{'coefficients':{'x':1,'y':1},'sense':'min'}}
    assert evaluation.linear_oracle(lp)==-.75
    infeasible={'variables':{'x':[0,1]},'constraints':[{'coefficients':{'x':1},'op':'>=','rhs':2}],
                'objective':{'coefficients':{'x':1},'sense':'min'}}
    assert evaluation.linear_oracle(infeasible) is None


def test_missing_or_contaminated_extension_freeze_never_executes(tmp_path,monkeypatch):
    monkeypatch.setattr(evaluation,'SUITE',tmp_path/'suite.json')
    monkeypatch.setattr(evaluation,'FREEZE',tmp_path/'freeze.json')
    monkeypatch.setattr(evaluation,'reason',lambda *a,**kw:pytest.fail('unfrozen execution forbidden'))
    with pytest.raises(RuntimeError,match='CONTAMINATED_EVALUATION'):evaluation.assess(tmp_path/'result.json')
    evaluation.SUITE.write_text(json.dumps(evaluation.generate_suite()))
    evaluation.freeze()
    changed=json.loads(evaluation.SUITE.read_text());changed['cases'][0]['expected']['state']='ABSTAIN'
    evaluation.SUITE.write_text(json.dumps(changed))
    with pytest.raises(RuntimeError,match='CONTAMINATED_EVALUATION'):evaluation.assess(tmp_path/'result.json')
    assert not (tmp_path/'result.json').exists()


def test_freeze_preserves_existing_records_and_binds_exact_source_environment(tmp_path,monkeypatch):
    monkeypatch.setattr(evaluation,'SUITE',tmp_path/'suite.json')
    monkeypatch.setattr(evaluation,'FREEZE',tmp_path/'freeze.json')
    evaluation.SUITE.write_text(json.dumps(evaluation.generate_suite()))
    record=evaluation.freeze()
    assert record['budget']=={'global_seconds':900,'per_invocation_seconds':10,'compute_limit':100000,'spend_usd':0,'model_calls':0}
    assert 'signed founder attachment' in record['attachment']
    assert record['source_digests']['scripts/evaluate_cognition_extensions.py'].startswith('sha256:')
    assert record['environment']['python']
    before=evaluation.FREEZE.read_bytes()
    with pytest.raises(RuntimeError,match='refusing to replace'):evaluation.freeze()
    assert evaluation.FREEZE.read_bytes()==before


def test_repertoire_generation_has_native_subscopes_and_no_consciousness_or_field_claims(monkeypatch):
    from scripts.cognition_repertoire_cases import generate_suite
    monkeypatch.setattr(evaluation,'reason',lambda *a,**kw:pytest.fail('pure repertoire generation may not run methods'))
    suite=generate_suite()
    assert len(suite['cases'])==220 and len(suite['families'])==11
    assert set(Counter(c['stratum'] for c in suite['cases']).values())=={20}
    assert all(len(families)==4 for families in suite['families'].values())
    assert len({c['group'] for c in suite['cases']})==44
    assert all(c['request']['problem_id'].startswith('repertoire:') and 'expected' not in c['request'] for c in suite['cases'])
    collective=[c for c in suite['cases'] if c['stratum']=='collective']
    assert {c['expected']['state'] for c in collective}=={'NONE','NO_QUORUM'}
    assert all(0<=row['weight']<=1 for c in collective for row in c['request']['data']['observations'])
    assert all(c['expected']['state']=='HUMAN_REVIEW_REQUIRED' for c in suite['cases'] if c['stratum']=='human')
    assert 'unauthenticated' in suite['evidence_limits'] and 'not superiority' in suite['evidence_limits']
    assert not evaluation.matches({'value':True},{'value':1})
