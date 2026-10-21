"""Real signed test missions and files; no model, device or external-outcome claim."""
from copy import deepcopy
import pytest
from greg.body import Body
from greg.pipeline import resolve, BindingError, PendingInput
from tests.greg_fixtures import make_body, signed, drop, Clock, horizon, workspace


def binding(action='read', field='text', kind='string'):
    return {'$from_action': {'action_id': action, 'field': field, 'type': kind}}


def build_mission(home, source):
    output = workspace(home, 'm:pipeline') / 'copied.txt'
    return {'mission_id': 'm:pipeline', 'founder_expression': 'Read the source and retain its exact text.',
        'intended_effect': 'Typed receipt data reaches the next stage automatically.',
        'priority': 50, 'closure': {'kind': 'bounded'},
        'success_checks': [
            {'check_id': 'read', 'description': 'source was read in this mission',
             'sensor': {'capability': 'pipeline.inspect', 'target': 'pipeline:read',
                        'params': binding()['$from_action']},
             'predicate': {'op':'equals', 'field':'available', 'value':True}},
            {'check_id': 'copied', 'description': 'file contains the exact retained source text',
             'sensor': {'capability':'fs.read', 'target':'fs:copy', 'params':{'path':str(output)}},
             'predicate': {'op':'equals','field':'text','value':'Evidence 42\n'}}],
        'strategies': [
            {'action_id':'read','capability':'fs.read','target':'fs:source','params':{'path':str(source)},
             'advances':['read'],'rationale':'read existing local source'},
            {'action_id':'copy','capability':'fs.write','target':'workspace:copied.txt',
             'params':{'relative_path':'copied.txt','content':binding()},
             'requires':['read'],'advances':['copied'],'rationale':'consume exact typed producer output'}],
        'light_cone': {'capabilities':['pipeline.inspect','fs.read','fs.write'],
            'targets':['pipeline:read','fs:*','workspace:copied.txt'],
            'max_consequence_class':'internal_write','budget_usd':0,'horizon':horizon()}}


def test_handoff_survives_body_restart_and_is_appraised(tmp_path):
    home,key,bid,data=make_body(tmp_path)
    source=data/'source.txt';source.write_text('Evidence 42\n')
    spec=build_mission(home,source);drop(home,signed(key,bid,'MISSION',spec))
    clock=Clock()
    with Body(home,clock=clock) as body:
        body.tick();clock.advance(1)
        assert len(body.journal.replay('mission.action'))==1
    source.write_text('Later source state\n')  # downstream consumes retained bytes, never a path copy/re-read
    with Body(home,clock=clock) as body:
        for _ in range(4):body.tick();clock.advance(1)
        actions=body.journal.replay('mission.action')
        assert len(actions)==2
        assert actions[-1].payload['input_bindings'][0]['action_event']==actions[0].event_id
        assert body.journal.replay('mission.achieved')
        appraisals=body.journal.replay('mission.appraised')
        assert appraisals and appraisals[-1].payload['verdict']=='VERIFIED'
        assert (workspace(home,'m:pipeline')/'copied.txt').read_text()=='Evidence 42\n'
        with pytest.raises(PendingInput):resolve({'content':binding()},body.journal,'m:other')
        with pytest.raises(BindingError,match='type'):resolve({'content':binding(kind='integer')},body.journal,'m:pipeline')
        with pytest.raises(BindingError,match='scope'):resolve({'tools':binding()},body.journal,'m:pipeline')
        with pytest.raises(BindingError,match='field'):resolve({'content':binding(field='missing')},body.journal,'m:pipeline')


def test_binding_is_data_and_cannot_recurse_as_instructions(tmp_path):
    home,key,bid,data=make_body(tmp_path)
    with Body(home) as body:
        malformed = binding()
        malformed['$from_action']['type'] = []
        with pytest.raises(BindingError, match='supported type'):
            resolve({'content':malformed},body.journal,'m:absent')
        with pytest.raises(PendingInput):resolve({'content':binding()},body.journal,'m:absent')
        with pytest.raises(BindingError):resolve({'content':{'$from_action':binding()['$from_action'],'provider':'other'}},body.journal,'m:absent')
        for key in ('repo','base','max_budget_usd','acceptance','credentials','url','argv','provider'):
            with pytest.raises(BindingError,match='scope'):resolve({key:binding()},body.journal,'m:absent')
