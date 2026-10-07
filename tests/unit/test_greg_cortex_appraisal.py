"""Retained founder scope and package certificates survive a read-only appraisal.

Laboratory Ed25519 keys authenticate test scope, not Alfonso's identity.
"""
import pytest

from greg.appraisal import _read_only_cognition_registry
from greg.body import Body
from greg.cortex_bridge import dependency_deficits, run
from tests.greg_fixtures import Clock, make_body, signed
from tests.unit.test_greg_cortex_convergence import problem, spec


def projection(body):
    seq = {r.payload.get('event_id'): r.seq for r in body.ledger.by_type('event')}
    before = body.ledger.head
    registry, authorized = _read_only_cognition_registry(body.journal, body.ledger, seq)
    assert body.ledger.head == before  # projection never attaches or records lifecycle events
    return registry, authorized


@pytest.mark.parametrize('function', ['graph.shortest_path', 'graph.max_flow', 'lp.optimize'])
def test_appraiser_rebuilds_founder_scope_and_rechecks_package_certificate(tmp_path, function):
    pytest.importorskip('networkx')
    pytest.importorskip('scipy')
    home, key, bid, _ = make_body(tmp_path)
    p = problem(function)
    with Body(home) as body:
        body.apply(signed(key, bid, 'MISSION', spec(p, function, True)))
        parent = body.engine.book.missions['m:typed-cortex']
        acquired = body.genesis.resolve(mission=parent, function=function, purpose='signed detour', now=Clock()())
        registry, authorized = projection(body)
        assert authorized and registry.state[acquired.capability_id] == 'ATTACHED'
        assert run(p, registry=registry)['answered']
        body.apply(signed(key, bid, 'CAPABILITY_DETACH', {'capability_id': acquired.capability_id}))
        registry, authorized = projection(body)
        assert authorized and registry.state[acquired.capability_id] == 'DETACHED'
        assert dependency_deficits(p, registry) == [function]


def test_appraiser_requires_signed_attach_after_qualification(tmp_path):
    pytest.importorskip('networkx')
    home, key, bid, _ = make_body(tmp_path)
    function = 'graph.shortest_path'
    p = problem(function)
    with Body(home) as body:
        body.apply(signed(key, bid, 'MISSION', spec(p, function, False)))
        parent = body.engine.book.missions['m:typed-cortex']
        assert body.genesis.resolve(mission=parent, function=function, purpose='qualification', now=Clock()()) is None
        acquired = body.registry.by_function(function)[0]
        registry, authorized = projection(body)
        assert authorized and registry.state[acquired.capability_id] == 'VERIFIED'
        body.apply(signed(key, bid, 'CAPABILITY_ATTACH', {'capability_id': acquired.capability_id}))
        registry, authorized = projection(body)
        assert authorized and run(p, registry=registry)['answered']


def test_unsigned_attachment_event_cannot_enable_appraisal(tmp_path):
    pytest.importorskip('networkx')
    home, key, bid, _ = make_body(tmp_path)
    function = 'graph.shortest_path'
    p = problem(function)
    with Body(home) as body:
        body.apply(signed(key, bid, 'MISSION', spec(p, function, False)))
        parent = body.engine.book.missions['m:typed-cortex']
        body.genesis.resolve(mission=parent, function=function, purpose='qualification', now=Clock()())
        acquired = body.registry.by_function(function)[0]
        body.journal.record('capability.state', {'capability_id': acquired.capability_id, 'state': 'ATTACHED',
                            'by': 'founder-signed mission auto_attach (read_only)', 'mission_id': parent.mission_id,
                            'deficit_id': 'hostile-test'}, key='hostile-unapproved-attach')
        registry, authorized = projection(body)
        assert not authorized and registry.state[acquired.capability_id] == 'VERIFIED'
        assert dependency_deficits(p, registry) == [function]
