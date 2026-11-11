"""The authority office runs a capability's own registered adapter, or nothing.

Attach state is keyed by capability id (tests/unit/test_greg_authority_attach_state.py). The id alone does not
settle what runs: ``AuthorityOffice.act`` executes the adapter its caller hands it. Before this, a founder-DETACHED
``artifact.store`` (internal_write) ran through the office when its adapter was presented under the ATTACHED
``artifact.inspect`` manifest (read_only): DONE, an artifact retained, and a grant and receipt in the name of the
read-only capability. These tests drive the office directly on a real body, as that file does.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from greg.artifacts import ArtifactStore
from greg.body import Body
from greg.capabilities import CapabilityError, InvocationContext
from greg.lightcone import LightCone
from tests.greg_fixtures import horizon, make_body, signed, workspace

RAW = b"bytes a detached capability must not retain\n"
ADDRESS = "sha256:36e23d6cf2b7eafa664d41ee529106249e119fe6ac20f7d700adbbe1c4080b53"


def _office_act(body: Body, home: Path, data: Path, *, manifest, adapter, ctx_manifest, params, attempt="direct"):
    cone = LightCone(capabilities=frozenset({manifest.capability_id}), targets=("artifact:reports",),
                     max_consequence_class="read_only", budget_usd=0.0, horizon=horizon())
    ctx = InvocationContext(workspace=workspace(home, "m:direct-office"), read_roots=(data,), secrets=body.secrets,
                            manifest=ctx_manifest, journal=body.journal, artifact_root=body.layout.artifacts)
    return body.office.act(mission_id="m:direct-office", cone=cone, command_digest="sha256:" + "0" * 64,
                           manifest=manifest, adapter=adapter, ctx=ctx, params=params, target="artifact:reports",
                           cost_usd=0.0, expected_outcome="observation captured", evidence_refs=[],
                           attempt=attempt, spent_usd=0.0, approved_scopes=set())


def _events(body, kind):
    return [r.payload for r in body.ledger.by_type("event") if r.payload.get("type") == kind]


def _retained(body) -> bool:
    try:
        ArtifactStore(body.layout.artifacts).read(ADDRESS)
    except CapabilityError:
        return False
    return True


@pytest.fixture
def world(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    source = data / "report.bin"
    source.write_bytes(RAW)
    with Body(home) as body:
        body.boot()
        yield body, key, body_id, home, data, source


def test_a_detached_adapter_does_not_run_under_an_attached_manifest(world):
    """The reproduced defect: the write capability the founder detached, presented as the read-only one."""
    body, key, body_id, home, data, source = world
    body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "artifact.store"}))
    inspect = body.registry.manifests["artifact.inspect"]
    grants_before = len(_events(body, "greg.authority.grant_issued"))
    out = _office_act(body, home, data, manifest=inspect, adapter=body.registry.adapters["artifact.store"],
                      ctx_manifest=body.registry.manifests["artifact.store"],
                      params={"namespace": "reports", "path": str(source)})
    assert out.status == "REFUSED" and "adapter presented for artifact.inspect" in out.reasons[0]
    assert out.receipt_hash is None and not _retained(body)                       # no effect
    assert len(_events(body, "greg.authority.grant_issued")) == grants_before      # no passport, grant or dispatch
    [event] = _events(body, "greg.authority.refused_unattached")
    assert event["capability"] == "artifact.inspect" and event["proposal_id"] == out.proposal_id


def test_an_attached_adapter_does_not_run_under_another_attached_manifest(world):
    """Both attached: the receipt would still name a capability that did not run, at a class it does not have."""
    body, _, _, home, data, source = world
    out = _office_act(body, home, data, manifest=body.registry.manifests["artifact.inspect"],
                      adapter=body.registry.adapters["artifact.store"],
                      ctx_manifest=body.registry.manifests["artifact.store"],
                      params={"namespace": "reports", "path": str(source)})
    assert out.status == "REFUSED" and not _retained(body)


def test_the_context_cannot_name_a_different_capability(world):
    """An adapter learns which capability it runs as from ``ctx.manifest``; the caller does not choose that."""
    body, _, _, home, data, _ = world
    inspect = body.registry.manifests["artifact.inspect"]
    out = _office_act(body, home, data, manifest=inspect, adapter=body.registry.adapters["artifact.inspect"],
                      ctx_manifest=body.registry.manifests["artifact.store"],
                      params={"namespace": "reports", "address": ADDRESS})
    assert out.status == "REFUSED" and "invocation context names artifact.store" in out.reasons[0]


def test_a_manifest_that_differs_from_the_registered_one_is_refused(world):
    """Same id, different declared facts: not the capability this body registered and the founder attached."""
    body, _, _, home, data, _ = world
    registered = body.registry.manifests["artifact.inspect"]
    forged = replace(registered, description=registered.description + " (edited)")
    out = _office_act(body, home, data, manifest=forged, adapter=body.registry.adapters["artifact.inspect"],
                      ctx_manifest=forged, params={"namespace": "reports", "address": ADDRESS})
    assert out.status == "REFUSED" and "not the one registered" in out.reasons[0]


def test_the_registered_capability_still_runs(world):
    body, _, _, home, data, _ = world
    inspect = body.registry.manifests["artifact.inspect"]
    out = _office_act(body, home, data, manifest=inspect, adapter=body.registry.adapters["artifact.inspect"],
                      ctx_manifest=inspect, params={"namespace": "reports", "address": ADDRESS})
    assert out.status == "DONE" and out.receipt_hash
    assert not _events(body, "greg.authority.refused_unattached")


def test_an_equal_copy_of_the_registered_manifest_still_runs(world):
    """Identity is by content: a manifest rebuilt from its record (as a restart rebuilds them) is the same one."""
    body, _, _, home, data, _ = world
    inspect = body.registry.manifests["artifact.inspect"]
    copy = replace(inspect)
    assert copy is not inspect
    out = _office_act(body, home, data, manifest=copy, adapter=body.registry.adapters["artifact.inspect"],
                      ctx_manifest=copy, params={"namespace": "reports", "address": ADDRESS})
    assert out.status == "DONE"


def test_a_detach_survives_a_restart_at_the_office(tmp_path):
    """Founder detaches -> the body stops -> a new process boots: the office still refuses, and says so again."""
    home, key, body_id, data = make_body(tmp_path)
    with Body(home) as body:
        body.boot()
        body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "artifact.inspect"}))
    with Body(home) as body:
        body.boot()
        assert body.registry.state["artifact.inspect"] == "DETACHED"
        inspect = body.registry.manifests["artifact.inspect"]
        out = _office_act(body, home, data, manifest=inspect, adapter=body.registry.adapters["artifact.inspect"],
                          ctx_manifest=inspect, params={"namespace": "reports", "address": ADDRESS})
        assert out.status == "REFUSED" and "DETACHED" in out.reasons[0]
        assert _events(body, "greg.authority.refused_unattached")
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "artifact.inspect"}))
        again = _office_act(body, home, data, manifest=inspect, adapter=body.registry.adapters["artifact.inspect"],
                            ctx_manifest=inspect, params={"namespace": "reports", "address": ADDRESS}, attempt="b")
        assert again.status == "DONE"
