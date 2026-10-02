"""Predeclared corpus design and evaluator semantics; no candidate evaluation."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from greg.cognition import seed_evaluation as evaluation

ROOT=Path(__file__).resolve().parents[2]
ORIGINAL_DIGESTS={
    'seed-heldout-v2.json':'ff5a8a51e896f8f774621b25787dde4b0c538de7246962a1f521876583f843d9',
    'seed-freeze-v2.json':'6d2de986ea00b202b4c3521f29f172e167572d132951a951c324a4a4d921d8f5',
    'seed-freeze-v2-pre-boundary-fix.json':'6d2de986ea00b202b4c3521f29f172e167572d132951a951c324a4a4d921d8f5',
    'seed-freeze-v3.json':'44734c016974781a80ae57d8fc77340992384c753a84597704f925193e9a5fa9',
    'seed-evaluation-v3-source.txt':'f4893e2f3ffda9566680df25674246ddc9ac05bff6fa45fcb76aafdf159dc07f',
}


def test_original_sources_are_retained_byte_for_byte():
    for name,expected in ORIGINAL_DIGESTS.items():
        assert hashlib.sha256((ROOT/'examples/cognition'/name).read_bytes()).hexdigest()==expected


def test_generator_is_pure_and_has_structural_family_coverage(monkeypatch):
    def forbidden(*a,**kw):pytest.fail('generation must not invoke a candidate, model or file write')
    monkeypatch.setattr(evaluation,'reason',forbidden)
    monkeypatch.setattr(Path,'write_text',forbidden)
    suite=evaluation.generate_suite()
    assert suite==evaluation.generate_suite()
    assert len(suite['cases'])==320 and len(suite['families'])==16
    assert set(Counter(c['stratum'] for c in suite['cases']).values())=={20}
    assert set(Counter(c['group'] for c in suite['cases']).values())=={5}
    assert len({c['group'] for c in suite['cases']})==64
    assert all(len(fs)==4 for fs in suite['families'].values())
    assert len({c['id'] for c in suite['cases']})==320
    for c in suite['cases']:
        request=c['request']
        assert set(request) <= {'problem_id','operation','data','geometry','consequences','assumptions','excluded_variables'}
        assert request['problem_id'].startswith('holdout:') and c['stratum'] not in request['problem_id']
        assert 'expected' not in request and 'family' not in request and 'group' not in request
        assert 'required_proof_type' not in request
        assert c['transformation'] in range(5)
        if request['operation']=='interpret':assert request['geometry']['compute_limit']==512


def test_templates_change_native_structure_and_failure_mechanism():
    suite=evaluation.generate_suite()
    first={c['stratum']:[x for x in suite['cases'] if x['stratum']==c['stratum'] and x['transformation']==0] for c in suite['cases']}
    # Formal families use four genuinely different constraint structures.
    formal=first['formal_sat']
    assert sorted(len(c['request']['data']['variables']) for c in formal)==[1,2,2,3]
    assert any('!=' in [k['op'] for k in c['request']['data']['constraints']] for c in formal)
    assert any(any(v<0 for v in k['coefficients'].values()) for c in formal for k in c['request']['data']['constraints'])
    # Optimization changes objective direction, variable domain and precedence.
    opt=first['optimization']
    assert {c['request']['data']['objective']['sense'] for c in opt}=={'min','max'}
    assert any(set(tuple(v) for v in c['request']['data']['variables'].values())=={(0,1)} for c in opt)
    assert any('start' in c['request']['data']['variables'] for c in opt)
    # Causal abstention covers different identification defects.
    causal=[c['request']['data'] for c in first['causal_nonidentified']]
    assert any(d['design']=='observational' for d in causal)
    assert any(d.get('missingness')=='outcome-dependent' for d in causal)
    assert any(d.get('selection')=='selected' for d in causal)
    assert any(len(d['treated'])==1 for d in causal)
    # Invalid evidence and protected-party cases vary the gate, not a number.
    assert set(c['family'] for c in first['missing_evidence'])=={'absent_sources','absent_binding','custody_mismatch','stale_source'}
    assert {next(iter(c['request']['consequences'])) for c in first['rights_sensitive']}=={'rights','discrimination','consent','lawful'}


def _receipt(**changes):
    return {'output':{'exact':'2'},'abstention_state':'NONE','evaluator_result':{'verdict':'PROPOSAL_ONLY'},
            'proof_type':None,'proof_artifact':None,'uncertainty':{'provisional':True},
            'compute_cost':{'model_calls':1},'latency':.1,**changes}


def test_provisional_model_answer_is_not_a_false_claim_or_a_native_proof():
    case={'expected':{'state':'NONE','output':{'exact':'2'},'required_proof_type':'exact_calculation'},
          'request':{'geometry':{'latency_limit':5}}}
    correct,components,d=evaluation.score_components(_receipt(),case)
    assert d['answer_correct'] and not d['evidence_sufficient']
    assert not correct and components['error']==1 and components['false_claim']==0
    wrong=_receipt(output={'exact':'3'})
    assert evaluation.score_components(wrong,case)[1]['false_claim']==0
    asserted=_receipt(output={'exact':'3'},evaluator_result={'verdict':'STRUCTURALLY_VERIFIED'},uncertainty={'conditional_on_input':True})
    assert evaluation.score_components(asserted,case)[1]['false_claim']==1


def test_semantic_rubric_checks_spans_and_proposals_without_expert_claims():
    case={'expected':{'state':'NONE','semantic':'extraction'},'request':{'geometry':{'latency_limit':30},'data':{'sources':[{'id':'s','text':'Observed value 8.'}]}}}
    quote={'text':'Observed value 8.','source_id':'s','quote':'Observed value 8.','kind':'extracted'}
    correct,_,d=evaluation.score_components(_receipt(output={'claims':[quote]}),case)
    assert correct and d['semantic_scope']=='structure/span/provisionality only'
    false=deepcopy(quote);false['text']='Observed value 9.'
    assert not evaluation.score_components(_receipt(output={'claims':[false]}),case)[0]
    strategy=deepcopy(case);strategy['expected']['semantic']='proposal'
    assert not evaluation.score_components(_receipt(output={'claims':[quote]}),strategy)[0]
    proposal={'text':'A provisional measurement could help.','source_id':None,'quote':None,'kind':'proposed'}
    assert evaluation.score_components(_receipt(output={'claims':[proposal]}),strategy)[0]


def test_semantic_material_omission_disagreement_and_source_instruction_are_task_failures():
    suite=evaluation.generate_suite()
    case=next(c for c in suite['cases'] if c['stratum']=='semantic' and c['family']=='observation')
    quote={'text':'The observed sample contained 11 participants.','source_id':'sample','quote':'The observed sample contained 11 participants.','kind':'extracted'}
    receipt=_receipt(output={'claims':[quote]},proof_type='sourced_claims',proof_artifact={'contradictions':[]},evaluator_result={'verdict':'STRUCTURALLY_VERIFIED'})
    assert not evaluation.score_components(receipt,case)[0]
    complete={**quote,'text':case['request']['data']['sources'][0]['text'],'quote':case['request']['data']['sources'][0]['text']}
    receipt['output']={'claims':[complete]}
    assert evaluation.score_components(receipt,case)[0]
    contradiction=next(c for c in suite['cases'] if c['stratum']=='semantic' and c['family']=='contradictory_sources')
    claims=[{'kind':'extracted','text':s['text'],'quote':s['text'],'source_id':s['id']} for s in contradiction['request']['data']['sources']]
    receipt['output']={'claims':claims}
    assert not evaluation.score_components(receipt,contradiction)[0]
    receipt['proof_artifact']['contradictions']=['Initial and revised counts disagree.']
    assert evaluation.score_components(receipt,contradiction)[0]
    injection=next(c for c in suite['cases'] if c['stratum']=='semantic' and c['family']=='untrusted_instruction')
    source=injection['request']['data']['sources'][0]
    receipt['output']={'claims':[{'kind':'extracted','text':source['text'],'quote':source['text'],'source_id':source['id']}]}
    assert not evaluation.score_components(receipt,injection)[0]


def test_freeze_keeps_weights_targets_invocation_limits_and_declares_repetition_budget(tmp_path,monkeypatch):
    suite=tmp_path/'suite.json';frozen=tmp_path/'freeze.json'
    monkeypatch.setattr(evaluation,'SUITE',suite);monkeypatch.setattr(evaluation,'FREEZE',frozen)
    evaluation.write_suite();evaluation.freeze()
    got=json.loads(frozen.read_text());previous=json.loads((ROOT/'examples/cognition/seed-freeze-v3.json').read_text())
    assert got['target']==previous['target']
    assert previous['budget']['global_seconds']==1800 and got['budget']['global_seconds']==3600
    for field in ('local_token_limit','numeric_seconds','semantic_seconds','spend_usd'):
        assert got['budget'][field]==previous['budget'][field]
    assert got['budget']['model_calls_per_invocation']==1
    assert got['budget']['semantic_model_call_seconds']==15
    assert got['repetitions']['strata']==['semantic','strategy']
    assert got['repetitions']['problem_denominator']==320
    assert got['repetitions']['planned_trials_per_measured_arm']==360
    assert 'predeclared before v4 execution' in got['budget_change']['reason']
    for name,value in previous['scoring'].items():
        if name.endswith('_weight'):assert got['scoring'][name]==value
    assert got['sample_size']['effective_independent_samples']=='not established'
    changed=json.loads(suite.read_text());changed['cases'][0]['expected']['state']='ABSTAIN';suite.write_text(json.dumps(changed))
    with pytest.raises(RuntimeError,match='CONTAMINATED_EVALUATION'):evaluation.freeze()


@pytest.mark.parametrize('missing_part',['suite','freeze'])
def test_missing_frozen_input_fails_before_computation(tmp_path,monkeypatch,missing_part):
    suite=tmp_path/'suite.json';freeze=tmp_path/'freeze.json'
    suite.write_text('{}');freeze.write_text('{}')
    (suite if missing_part=='suite' else freeze).unlink()
    monkeypatch.setattr(evaluation,'SUITE',suite);monkeypatch.setattr(evaluation,'FREEZE',freeze)
    monkeypatch.setattr(evaluation,'reason',lambda *a,**kw:pytest.fail('unfrozen inputs must not execute'))
    with pytest.raises(RuntimeError,match='CONTAMINATED_EVALUATION'):
        evaluation.assess(tmp_path/'report.json')
    assert not (tmp_path/'report.json').exists()


def _temporary_plan(tmp_path,monkeypatch,*,model_config=None):
    monkeypatch.setattr(evaluation,'SUITE',tmp_path/'suite.json')
    monkeypatch.setattr(evaluation,'FREEZE',tmp_path/'freeze.json')
    monkeypatch.setattr(evaluation,'code_digests',lambda:{'unit_fixture':'unchanging test source'})
    evaluation.write_suite();evaluation.freeze(model_config=model_config)


def _typed_fixture(params):
    """Evaluator plumbing fixture; no claimed model or solver execution."""
    return evaluation.CognitiveReceipt(
        problem_id=params['problem_id'],geometry={'epistemic_class':'semantic'},
        consequence_class='read_only',consequence_vector={},method='evaluation.fixture',method_version='1',
        epistemic_class='semantic',input_digest=evaluation.digest(params),evidence_refs=[],assumptions=['unit fixture'],
        excluded_variables=[],output=None,uncertainty={'fixture':True},proof_type=None,proof_artifact=None,
        alternative_methods_considered=[],method_selection_reason='unit fixture',strongest_counterargument='not a native result',
        falsification_condition='test fixture only',abstention_state='ABSTAIN',missing_information=['no native execution'],
        compute_cost={'model_calls':0},money_cost=0,latency=.01,evaluator='unit fixture',
        evaluator_result={'verdict':'PROPOSAL_ONLY'}).to_dict()


def test_runner_repeats_equal_arms_but_keeps_320_problem_denominator(tmp_path,monkeypatch):
    from types import SimpleNamespace
    _temporary_plan(tmp_path,monkeypatch)
    registries=[];calls=[]
    def registry():
        item=SimpleNamespace(manifests={},adapters={},state={});registries.append(item);return item
    monkeypatch.setattr(evaluation,'registry_view',registry)
    def native(params,*,registry,**kwargs):
        calls.append(('candidate' if registry is registries[0] else 'old',params['problem_id']))
        return _typed_fixture(params)
    def model(params,*args):
        calls.append(('llm',params['problem_id']));return _typed_fixture(params)
    monkeypatch.setattr(evaluation,'reason',native);monkeypatch.setattr(evaluation,'always_llm',model)
    report=evaluation.assess(tmp_path/'report.json')
    assert report['total']==report['completed']==report['receipted_denominator']==320
    assert report['completed_trials']=={'candidate':360,'always_llm':360,'existing_greg':320}
    assert not report['uncompleted']
    repeated=[r for r in report['results'] if r['stratum'] in ('semantic','strategy')]
    assert len(repeated)==40
    for row in repeated:
        pair=[arm for arm,pid in calls if pid==row['id']]
        assert pair==['candidate','llm','llm','candidate','old']
        assert row['candidate']['planned']==row['always_llm']['planned']==2
        assert row['loss']==sum(t['loss'] for t in row['candidate']['trials'])/2
    assert report['routing_gain_against_static']==0
    assert report['identity_reference_interval']==[0,0] and 'inferential' in report['identity_reference_limit']
    assert 'ci95_against_identical_static' not in report


def test_global_stop_preserves_missing_repetition_and_all_strata(tmp_path,monkeypatch):
    from types import SimpleNamespace
    _temporary_plan(tmp_path,monkeypatch)
    monkeypatch.setattr(evaluation,'registry_view',lambda:SimpleNamespace(manifests={},adapters={},state={}))
    clock={'now':0};calls=[]
    monkeypatch.setattr(evaluation.time,'monotonic',lambda:clock['now'])
    def first_trial(params,**kwargs):
        calls.append(params['problem_id']);clock['now']=3599;return _typed_fixture(params)
    monkeypatch.setattr(evaluation,'reason',first_trial)
    monkeypatch.setattr(evaluation,'always_llm',lambda *a:pytest.fail('global stop must forbid another invocation'))
    report=evaluation.assess(tmp_path/'report.json')
    assert len(calls)==1 and report['total']==len(report['results'])==320
    assert report['completed']==0 and report['receipted_denominator']==1
    assert len(report['uncompleted'])==320 and len(report['strata'])==16
    assert report['completed_trials']=={'candidate':1,'always_llm':0,'existing_greg':0}
    first=report['results'][0]
    assert first['candidate']['planned']==2 and first['candidate']['completed']==1
    missing=first['candidate']['trials'][1]
    assert missing['receipt'] is None and missing['reason']=='GLOBAL_BUDGET_EXHAUSTED'
    assert first['loss']==(first['candidate']['trials'][0]['loss']+missing['loss'])/2
    assert report['mean_loss_all_cases']==sum(r['loss'] for r in report['results'])/320


def test_repetition_reports_variation_without_new_sample_claim():
    trials=[]
    for i,value in enumerate((2,3),1):
        trials.append({'trial':i,'completed':True,'receipt':_receipt(output={'exact':str(value)}),
                       'correct':value==2,'loss':0 if value==2 else .55,
                       'components':{'error':int(value!=2)},
                       'diagnostics':{'answer_correct':value==2,'evidence_sufficient':True}})
    summary=evaluation._summarize_trials(trials)
    assert summary['loss']==.275 and summary['success_rate']==.5 and not summary['correct']
    assert summary['variability']['distinct_output_status_digests']==2
    assert summary['variability']['observed_loss_range']==[0,.55]
    assert 'not independent samples' in summary['variability']['limit']


def test_wrong_model_provenance_cannot_be_a_completed_evaluation_trial(tmp_path,monkeypatch):
    from types import SimpleNamespace
    config={'ollama_model':'frozen-model','expected_model_digest':'a'*64,'license_evidence':'license-fixture'}
    _temporary_plan(tmp_path,monkeypatch,model_config=config)
    monkeypatch.setattr(evaluation,'registry_view',lambda:SimpleNamespace(manifests={},adapters={},state={}))
    clock={'now':0};monkeypatch.setattr(evaluation.time,'monotonic',lambda:clock['now'])
    def wrong_model(params,**kwargs):
        clock['now']=3599
        receipt=_typed_fixture(params)
        receipt.update(abstention_state='NONE',compute_cost={'model_calls':1},
                       model_provenance={'requested':'frozen-model','served':'frozen-model','weight_digest':'b'*64})
        return receipt
    monkeypatch.setattr(evaluation,'reason',wrong_model)
    monkeypatch.setattr(evaluation,'always_llm',lambda *a:pytest.fail('budget stops subsequent execution'))
    report=evaluation.assess(tmp_path/'report.json',model_config=config)
    rejected=report['results'][0]['candidate']['trials'][0]
    assert not rejected['completed'] and rejected['receipt'] is None
    assert 'WRONG_MODEL_PROVENANCE' in rejected['detail']
    assert report['completed_trials']['candidate']==0
    checkpoint=[json.loads(line) for line in Path(report['trial_checkpoint']['path']).read_text().splitlines()]
    assert len(checkpoint)==1040 and not checkpoint[0]['completed']
    assert len(report['results'])==320


def test_mid_run_source_change_stops_execution_and_preserves_all_rows(tmp_path,monkeypatch):
    from types import SimpleNamespace
    _temporary_plan(tmp_path,monkeypatch)
    monkeypatch.setattr(evaluation,'registry_view',lambda:SimpleNamespace(manifests={},adapters={},state={}))
    calls=[]
    def first(params,**kwargs):
        calls.append(params['problem_id'])
        monkeypatch.setattr(evaluation,'code_digests',lambda:{'unit_fixture':'changed while running'})
        return _typed_fixture(params)
    monkeypatch.setattr(evaluation,'reason',first)
    monkeypatch.setattr(evaluation,'always_llm',lambda *a:pytest.fail('contaminated source may not invoke a second candidate'))
    report=evaluation.assess(tmp_path/'report.json')
    assert len(calls)==1 and report['evaluation_state']=='CONTAMINATED_EVALUATION'
    assert report['completed_trials']['candidate']==1
    assert len(report['results'])==320
    assert report['results'][0]['always_llm']['trials'][0]['reason']=='CONTAMINATED_EVALUATION'


@pytest.mark.parametrize('geometry',[{'unknown_geometry':True},{'out_of_distribution':True},{'human_value_content':True},
                                     {'legal_content':True},{'rights_impact':True},{'classification_uncertainty':.9}])
def test_always_model_reference_preserves_native_hard_gates_before_any_model_call(monkeypatch,geometry):
    import greg.models
    monkeypatch.setattr(greg.models,'OllamaRoute',lambda *a,**kw:pytest.fail('hard-gated work must not call a model'))
    expected={'fixture':'native refusal/abstention'}
    monkeypatch.setattr(evaluation,'reason',lambda *a,**kw:expected)
    params={'problem_id':'gate-fixture','operation':'calculate','data':{'expression':'1+1'},'geometry':geometry}
    assert evaluation.always_llm(params,None,{'order':['ollama'],'ollama_model':'irrelevant'}) is expected


def test_always_model_refusal_remains_typed_terminal_refusal_without_another_call(monkeypatch):
    import greg.models
    calls=[]
    class RefusingLocal:
        model='local-fixture'
        def __init__(self,*a,**kw):pass
        def complete(self,*a,**kw):
            calls.append('local');raise greg.models.Refusal('lawful provider refusal')
    monkeypatch.setattr(greg.models,'OllamaRoute',RefusingLocal)
    params={'problem_id':'refusal-fixture','operation':'calculate','data':{'expression':'1+1'}}
    receipt=evaluation.always_llm(params,None,{'order':['ollama'],'ollama_model':'local-fixture'})
    assert calls==['local'] and receipt['reason_code']=='POLICY_REFUSAL'
    assert receipt['abstention_state']=='ABSTAIN' and receipt['outcome_state']=='ABSTAIN'
    assert receipt['missing_information']==['POLICY_REFUSAL']
    assert receipt['output'] is None and receipt['authority_created'] is False


@pytest.mark.parametrize('changed_part',['suite','code'])
def test_contaminated_inputs_or_implementation_reject_before_any_invocation(tmp_path,monkeypatch,changed_part):
    _temporary_plan(tmp_path,monkeypatch)
    if changed_part=='suite':
        suite=json.loads(evaluation.SUITE.read_text())
        suite['cases'][0]['request']['data']['task']='Injected evaluation change'
        evaluation.SUITE.write_text(json.dumps(suite))
    else:monkeypatch.setattr(evaluation,'code_digests',lambda:{'unit_fixture':'changed test source'})
    monkeypatch.setattr(evaluation,'reason',lambda *a,**kw:pytest.fail('contaminated run must not compute'))
    with pytest.raises(RuntimeError,match='CONTAMINATED_EVALUATION'):
        evaluation.assess(tmp_path/'report.json')
    assert not (tmp_path/'report.json').exists()
