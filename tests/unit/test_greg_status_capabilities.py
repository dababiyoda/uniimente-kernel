"""Read-only interface inventory reflects durable canonical lifecycle state."""
from dataclasses import replace
import json

from greg import remote
from greg.body import Body, status
from greg.capabilities import BUILTINS
from greg.cognition.catalog import FAMILIES, SEED_FAMILIES
from greg.console import Console
from greg.founder import sign_read
from tests.greg_fixtures import make_body, signed


def _states(snapshot):
    return {row['capability_id']:row['state'] for row in snapshot['capabilities']}


def test_disabled_defaults_and_signed_detach_are_truthful_across_restart_and_interfaces(tmp_path):
    home,key,body_id,_=make_body(tmp_path)
    with Body(home) as body:
        attach=signed(key,body_id,'CAPABILITY_ATTACH',{'capability_id':'cognition.graph'})
        assert body.apply(attach)['status']=='APPLIED'
        assert body.apply(signed(key,body_id,'CAPABILITY_DETACH',{'capability_id':'cognition.graph'}))['status']=='APPLIED'
        assert body.apply(signed(key,body_id,'CAPABILITY_DETACH',{'capability_id':'cognition.solve'}))['status']=='APPLIED'
    with Body(home) as body:
        assert body.registry.state['cognition.graph']=='DETACHED'
        assert body.registry.state['cognition.solve']=='DETACHED'
        # Replaying the earlier signed attach cannot resurrect the later detach.
        body.apply(attach)
        assert body.registry.state['cognition.graph']=='DETACHED'
        before=(home/'ledger.jsonl').read_bytes()
        expected=dict(body.registry.state)
        direct=status(home)
        assert _states(direct)==expected
        assert _states(Console(home).snapshot()['status'])==expected
        assert {r['capability_id']:r['state'] for r in Console(home).context().capabilities}==expected
        now=body.clock()
        headers=sign_read(key,body_id=body_id,method='GET',path='/api/status',now=now)
        code,_,payload=remote.handle(home,'GET','/api/status',headers,b'',now=now)
        assert code==200 and _states(json.loads(payload)['data'])==expected
        assert (home/'ledger.jsonl').read_bytes()==before
        for family in set(FAMILIES)-SEED_FAMILIES-{'graph'}:
            assert expected['cognition.'+family]=='VERIFIED'
        if 'foundry.query' in expected:assert expected['foundry.query']=='VERIFIED'
        assert 'permission grant' in direct['capability_inventory_limits']


def test_observer_preserves_recorded_quarantine_without_opening_writer_or_generated_adapter(tmp_path,monkeypatch):
    home,_,_,_=make_body(tmp_path)
    with Body(home) as body:
        # A canonical owner records a formed descriptor and containment. This
        # metadata fixture is not a generated-code qualification claim.
        base=BUILTINS['cognition.graph'][0]
        manifest=replace(base,capability_id='built:status-fixture',provider='built:status-fixture',
                         function='fixture.read',cognitive_profile={})
        body.journal.record('capability.registered',{'manifest':manifest.to_dict(),'state':'VERIFIED',
                                                   'origin':{'kind':'built'}},key='status-fixture')
        body.journal.record('capability.state',{'capability_id':manifest.capability_id,'state':'QUARANTINED',
                                              'why':'fixture source failed integrity'},key='status-quarantine')
        body.journal.record('capability.state',{'capability_id':'cognition.estimation','state':'QUARANTINED',
                                              'why':'fixture containment'},key='builtin-quarantine')
    before=(home/'ledger.jsonl').read_bytes()
    def forbidden(*a,**kw):raise AssertionError('read-only status must not initialize the writable Body')
    monkeypatch.setattr(Body,'open',forbidden)
    observed=_states(status(home))
    assert observed['built:status-fixture']=='QUARANTINED'
    assert observed['cognition.estimation']=='QUARANTINED'
    assert (home/'ledger.jsonl').read_bytes()==before
