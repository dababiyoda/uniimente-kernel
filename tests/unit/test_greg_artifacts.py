"""Real signed GREG missions share one receipt-bound, content-addressed object."""
from dataclasses import replace
import hashlib
from pathlib import Path

import pytest

from greg.artifacts import ArtifactStore, inspect, materialize, store
from greg.body import Body
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext
from tests.greg_fixtures import Clock, drop, make_body, mission, signed, workspace


def _address(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _inspect_check(namespace: str, address: str) -> dict:
    return {"check_id": "retained", "description": "addressed bytes are still present",
            "sensor": {"capability": "artifact.inspect", "target": f"artifact:{namespace}",
                       "params": {"namespace": namespace, "address": address}},
            "predicate": {"op": "equals", "field": "present", "value": True}}


def _ctx(body, data: Path, capability: str, target: str, *, mid: str = "m:artifacts"):
    return InvocationContext(workspace=workspace(body.layout.home, mid), read_roots=(data,),
                             secrets=body.secrets, manifest=BUILTINS[capability][0],
                             journal=body.journal, artifact_root=body.layout.artifacts, target=target)


def test_founder_signed_import_survives_restart_and_materializes_in_later_mission(tmp_path):
    home, founder, body_id, data = make_body(tmp_path)
    raw = b"a real\x00binary artifact\n"
    source = data / "report.bin"
    source.write_bytes(raw)
    address = _address(raw)
    import_spec = mission("m:import", checks=[_inspect_check("reports", address)],
                          strategies=[{"action_id": "retain", "capability": "artifact.store",
                                       "params": {"namespace": "reports", "path": str(source)},
                                       "target": "artifact:reports", "advances": ["retained"],
                                       "rationale": "retain the scoped report for future missions",
                                       "expected_outcome": "artifact retained"}],
                          capabilities=["artifact.store", "artifact.inspect"],
                          targets=("artifact:reports",))
    drop(home, signed(founder, body_id, "MISSION", import_spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(5):
            body.tick()
            clock.advance(1)
        assert body.engine.book.missions["m:import"].status == "ACHIEVED"
        assert any(e.payload.get("mission_id") == "m:import" and e.payload.get("verdict") == "VERIFIED"
                   for e in body.journal.replay("mission.appraised"))
        assert ArtifactStore(body.layout.artifacts).read(address) == raw
        actions = [e for e in body.journal.replay("mission.action") if e.payload.get("mission_id") == "m:import"]
        assert len(actions) == 1 and actions[0].payload["status"] == "DONE"
        assert body.ledger.find(actions[0].payload["receipt"]).payload["result"]["output"]["address"] == address

    dest = workspace(home, "m:reuse") / "restored.bin"
    check = {"check_id": "same-bytes", "description": "original bytes recovered",
             "sensor": {"capability": "fs.read", "target": "fs:restored.bin", "params": {"path": str(dest)}},
             "predicate": {"op": "equals", "field": "sha256", "value": address[7:]}}
    reuse_spec = mission("m:reuse", checks=[check],
                         strategies=[{"action_id": "restore", "capability": "artifact.materialize",
                                      "params": {"namespace": "reports", "address": address,
                                                 "relative_path": "restored.bin"},
                                      "target": "workspace:restored.bin", "advances": ["same-bytes"],
                                      "rationale": "recover the exact earlier report",
                                      "expected_outcome": "artifact restored"}],
                         capabilities=["artifact.materialize", "fs.read"],
                         targets=("workspace:restored.bin", "fs:restored.bin"))
    drop(home, signed(founder, body_id, "MISSION", reuse_spec))
    with Body(home, clock=clock) as body:
        for _ in range(5):
            body.tick()
            clock.advance(1)
        assert dest.read_bytes() == raw
        assert body.engine.book.missions["m:reuse"].status == "ACHIEVED"
        assert any(e.payload.get("mission_id") == "m:reuse" and e.payload.get("verdict") == "VERIFIED"
                   for e in body.journal.replay("mission.appraised"))
        assert len([e for e in body.journal.replay("mission.action")
                    if e.payload.get("mission_id") == "m:reuse" and e.payload["status"] == "DONE"]) == 1
        cross = _ctx(body, data, "artifact.inspect", "artifact:other")
        assert inspect({"namespace": "other", "address": address}, cross)["present"] is False
        dest.write_bytes(b"changed")
        with pytest.raises(CapabilityError, match="replace different bytes"):
            materialize({"namespace": "reports", "address": address, "relative_path": "restored.bin"},
                        replace(_ctx(body, data, "artifact.materialize", "workspace:restored.bin",
                                     mid="m:reuse"), workspace=dest.parent))


def test_corrupt_bytes_refute_prior_local_appraisal(tmp_path):
    home, founder, body_id, data = make_body(tmp_path)
    source = data / "x"
    source.write_bytes(b"original")
    address = _address(b"original")
    spec = mission("m:corruption", checks=[_inspect_check("proof", address)],
                   strategies=[{"action_id": "retain", "capability": "artifact.store",
                                "params": {"namespace": "proof", "path": str(source)},
                                "target": "artifact:proof", "advances": ["retained"],
                                "rationale": "retain source bytes", "expected_outcome": "retained"}],
                   capabilities=["artifact.store", "artifact.inspect"], targets=("artifact:proof",))
    drop(home, signed(founder, body_id, "MISSION", spec))
    with Body(home) as body:
        for _ in range(4):
            body.tick()
        assert body.appraise("m:corruption")["verdict"] == "VERIFIED"
        ArtifactStore(body.layout.artifacts).path(address).write_bytes(b"altered")
        verdict = body.appraise("m:corruption")
        assert verdict["verdict"] == "REFUTED"
        assert verdict["checks"]["world_reobserved"] is False


def test_no_receipt_no_read_and_no_cross_namespace_inheritance(tmp_path):
    home, _, _, data = make_body(tmp_path)
    source = data / "x"
    source.write_bytes(b"private-bytes")
    address = _address(b"private-bytes")
    with Body(home) as body:
        ctx = _ctx(body, data, "artifact.store", "artifact:alpha")
        assert store({"namespace": "alpha", "path": str(source)}, ctx)["address"] == address
        # An orphaned write, e.g. crash after dispatch but before the Gate receipt,
        # has bytes on disk but no usable institutional provenance.
        assert not inspect({"namespace": "alpha", "address": address},
                           replace(ctx, manifest=BUILTINS["artifact.inspect"][0]))["present"]
        assert not inspect({"namespace": "beta", "address": address},
                           replace(ctx, manifest=BUILTINS["artifact.inspect"][0],
                                   target="artifact:beta"))["present"]
        with pytest.raises(CapabilityError, match="no successful Gate receipt"):
            materialize({"namespace": "alpha", "address": address, "relative_path": "x"},
                        replace(ctx, manifest=BUILTINS["artifact.materialize"][0], target="workspace:x"))


def test_store_refuses_escape_target_swap_corruption_and_overwrite(tmp_path):
    home, founder, body_id, data = make_body(tmp_path)
    source = data / "x"
    source.write_bytes(b"value")
    address = _address(b"value")
    outside = tmp_path / "secret"
    outside.write_text("not in read roots")
    with Body(home) as body:
        ctx = _ctx(body, data, "artifact.store", "artifact:notes")
        with pytest.raises(CapabilityError, match="signed target"):
            store({"namespace": "other", "path": str(source)}, ctx)
        with pytest.raises(CapabilityError, match="outside permitted roots"):
            store({"namespace": "notes", "path": str(outside)}, ctx)
        (data / "link").symlink_to(outside)
        with pytest.raises(CapabilityError, match="outside permitted roots"):
            store({"namespace": "notes", "path": str(data / "link")}, ctx)
        with pytest.raises(CapabilityError, match="invalid sha256"):
            inspect({"namespace": "notes", "address": "sha256:../escape"},
                    replace(ctx, manifest=BUILTINS["artifact.inspect"][0]))
        store({"namespace": "notes", "path": str(source)}, ctx)
        path = ArtifactStore(body.layout.artifacts).path(address)
        path.write_bytes(b"other")
        with pytest.raises(CapabilityError, match="disagree"):
            store({"namespace": "notes", "path": str(source)}, ctx)
        with pytest.raises(CapabilityError, match="disagree"):
            ArtifactStore(body.layout.artifacts).read(address)
        path.unlink()
        assert store({"namespace": "notes", "path": str(source)}, ctx)["created"] is True
        assert store({"namespace": "notes", "path": str(source)}, ctx)["created"] is False
        path.unlink()
        path.symlink_to(outside)
        with pytest.raises(CapabilityError, match="regular file"):
            ArtifactStore(body.layout.artifacts).read(address)
        with pytest.raises(CapabilityError, match="regular file"):
            store({"namespace": "notes", "path": str(source)}, ctx)


def test_artifact_quota_bounds_total_disk_growth(tmp_path, monkeypatch):
    import greg.artifacts as artifacts

    monkeypatch.setattr(artifacts, "MAX_OBJECTS", 1)
    store = ArtifactStore(tmp_path / "objects")
    assert store.put(b"first")[1] is True
    assert store.put(b"first")[1] is False  # reuse costs no new object
    with pytest.raises(CapabilityError, match="quota exhausted"):
        store.put(b"second")
    assert not store.path(_address(b"second")).exists()


def test_gate_refuses_unscoped_import_and_signed_detach_survives_restart(tmp_path):
    from greg.lightcone import LightCone
    from tests.greg_fixtures import horizon

    home, founder, body_id, data = make_body(tmp_path)
    source = data / "x"
    source.write_bytes(b"x")
    with Body(home) as body:
        manifest, adapter = BUILTINS["artifact.store"]
        ctx = _ctx(body, data, "artifact.store", "artifact:notes")
        cone = LightCone.from_dict({"capabilities": ["fs.read"], "targets": ["artifact:notes"],
                                    "max_consequence_class": "internal_write", "budget_usd": 0,
                                    "horizon": horizon()})
        before = len(body.office.grants._grants)
        out = body.office.act(mission_id="m:blocked", cone=cone, command_digest="sha256:test",
                              manifest=manifest, adapter=adapter, ctx=ctx,
                              params={"namespace": "notes", "path": str(source)}, target="artifact:notes",
                              cost_usd=0, expected_outcome="artifact retained", evidence_refs=[],
                              attempt=0, spent_usd=0, approved_scopes=set())
        assert out.status == "OUTSIDE_SCOPE" and len(body.office.grants._grants) == before
        assert not ArtifactStore(body.layout.artifacts).path(_address(b"x")).exists()
        assert body.apply(signed(founder, body_id, "CAPABILITY_DETACH",
                                 {"capability_id": "artifact.store"}))["status"] == "APPLIED"
    with Body(home) as body:
        assert body.registry.state["artifact.store"] == "DETACHED"
        assert not body.registry.usable("artifact.store")[0]
