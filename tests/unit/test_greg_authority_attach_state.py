"""The authority office itself denies execution of a capability the founder has not left ATTACHED.

Behaviour B (2026-11-04): "Grant revocation is separate: the Kernel must deny affected execution immediately."
Before this, only ``MissionEngine._resolve`` consulted attach state, so a caller that reached ``AuthorityOffice.act``
another way ran a DETACHED capability (DONE, with a receipt). These tests drive the office directly on a real body.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from greg.body import Body
from greg.capabilities import InvocationContext
from greg.lightcone import LightCone
from tests.greg_fixtures import horizon, make_body, signed


def _act(body: Body, tmp: Path, note: Path, cid: str = "fs.read", attempt: str = "direct"):
    manifest, adapter = body.registry.manifests[cid], body.registry.adapters[cid]
    cone = LightCone(capabilities=frozenset({cid}), targets=("fs:*",), max_consequence_class="read_only",
                     budget_usd=0.0, horizon=horizon())
    ctx = InvocationContext(workspace=tmp / "ws", read_roots=(str(tmp),), secrets=None, manifest=manifest)
    return body.office.act(mission_id="m:direct-office", cone=cone, command_digest="sha256:" + "0" * 64,
                           manifest=manifest, adapter=adapter, ctx=ctx, params={"path": str(note)},
                           target="fs:" + str(note), cost_usd=0.0, expected_outcome="observation captured",
                           evidence_refs=[], attempt=attempt, spent_usd=0.0, approved_scopes=set())


@pytest.fixture
def world(tmp_path):
    home, key, body_id, _ = make_body(tmp_path, read_roots=[str(tmp_path)])
    note = tmp_path / "n.txt"
    note.write_text("hello")
    with Body(home) as body:
        body.boot()
        yield body, key, body_id, tmp_path, note


def _events(body, kind):
    return [r.payload for r in body.ledger.by_type("event") if r.payload.get("type") == kind]


def test_an_attached_capability_still_runs_through_the_office(world):
    body, _, _, tmp, note = world
    out = _act(body, tmp, note)
    assert out.status == "DONE" and out.receipt_hash
    assert not _events(body, "greg.authority.refused_unattached")


def test_a_detached_capability_is_refused_by_the_office_before_any_grant(world):
    body, key, body_id, tmp, note = world
    assert body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "fs.read"}))["result"]["state"] \
        == "DETACHED"
    grants_before = len(_events(body, "greg.authority.grant_issued"))
    out = _act(body, tmp, note)
    assert out.status == "REFUSED" and "DETACHED" in out.reasons[0] and out.receipt_hash is None
    assert len(_events(body, "greg.authority.grant_issued")) == grants_before     # no passport, grant or dispatch
    assert body.office.prior(out.proposal_id) == (None, None)
    [event] = _events(body, "greg.authority.refused_unattached")
    assert event["capability"] == "fs.read" and event["proposal_id"] == out.proposal_id


def test_a_retained_receipt_is_not_reused_once_the_capability_is_detached(world):
    """A DONE kept from before the detach is not served again through the office: execution is denied now."""
    body, key, body_id, tmp, note = world
    assert _act(body, tmp, note, attempt="kept").status == "DONE"
    body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "fs.read"}))
    assert _act(body, tmp, note, attempt="kept").status == "REFUSED"


@pytest.mark.parametrize("state", ["QUARANTINED", "VERIFIED", "DISCOVERED"])
def test_every_state_but_attached_is_refused(world, state):
    body, _, _, tmp, note = world
    body.registry.set_state("fs.read", state)
    out = _act(body, tmp, note)
    assert out.status == "REFUSED" and state in out.reasons[0]


def test_an_unregistered_capability_is_refused(world):
    body, _, _, tmp, note = world
    manifest, adapter = body.registry.manifests["fs.read"], body.registry.adapters["fs.read"]
    del body.registry.manifests["fs.read"], body.registry.state["fs.read"]
    cone = LightCone(capabilities=frozenset({"fs.read"}), targets=("fs:*",), max_consequence_class="read_only",
                     budget_usd=0.0, horizon=horizon())
    ctx = InvocationContext(workspace=tmp / "ws", read_roots=(str(tmp),), secrets=None, manifest=manifest)
    out = body.office.act(mission_id="m:direct-office", cone=cone, command_digest="sha256:" + "0" * 64,
                          manifest=manifest, adapter=adapter, ctx=ctx, params={"path": str(note)},
                          target="fs:" + str(note), cost_usd=0.0, expected_outcome="observation captured",
                          evidence_refs=[], attempt="unregistered", spent_usd=0.0, approved_scopes=set())
    assert out.status == "REFUSED" and "not registered" in out.reasons[0]


def test_reattach_restores_execution_and_requalification_alone_does_not(world):
    """Permission returns only by the founder's signed attach, never by a later passing reading."""
    body, key, body_id, tmp, note = world
    body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "fs.read"}))
    assert _act(body, tmp, note, attempt="a").status == "REFUSED"
    body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "fs.read"}))
    assert _act(body, tmp, note, attempt="b").status == "DONE"


def test_an_office_without_a_registry_runs_nothing(world):
    """Was "keeps its earlier behaviour" (DONE). An office that cannot check a registry now fails closed, so no
    construction or later mutation can silently switch the attach check off."""
    body, _, _, tmp, note = world
    body.office.registry = None
    out = _act(body, tmp, note, attempt="no-registry")
    assert out.status == "REFUSED" and "without a capability registry" in out.reasons[0]
