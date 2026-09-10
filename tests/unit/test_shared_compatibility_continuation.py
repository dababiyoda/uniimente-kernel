"""Negative controls for SR-001 continuation; original failing run is retained."""
import copy

import pytest

from events import engine as seam
from events.spine import EventSpine, WorkflowKilled, WorkflowStep, durable_workflow, resume_workflow
from evolution import compatibility
from evolution.migration import migrate, spec as migration_spec
from evolution.migration.engines import TokenEngine
from evolution.migration.harness import subject_class_intact
from evolution.migration.schema import make_validator
from evolution.repair import spec as repair_spec
from provenance.ledger import EvidenceLedger


def fixture():
    sp = EventSpine(EvidenceLedger("sha256:isolated-compatibility-fixture"))
    steps = [WorkflowStep(n, lambda s, n=n: {n: 1}, retry_safe=True) for n in ("a", "b")]
    wid = "p4x-continuation"
    migrate.prepare_fixture_rollback(sp, wid, steps, actor="synthetic",
                                     legal_principal="fixture_principal")
    with seam.activate(TokenEngine, provider_id="W2-token", workflow_ids=[wid],
                       activated_by="fixture", validator=make_validator(
                           step_names=["a", "b"], prior_status_fn=lambda: None)):
        with pytest.raises(WorkflowKilled):
            durable_workflow(sp, wid, steps, actor="synthetic",
                             legal_principal="fixture_principal").execute(kill_at_step="b")
    return sp, wid, steps, sp.ledger.by_type("workflow")[-1]


def test_retained_migration_is_idempotent_and_preserves_source():
    sp, wid, steps, source = fixture()
    snapshot = copy.deepcopy(source)
    first = migrate.restore_fixture_checkpoint(sp, wid, steps, source_hash=source.hash)
    head, count = sp.ledger.head, len(sp.ledger.records)
    assert migrate.restore_fixture_checkpoint(sp, wid, steps, source_hash=source.hash) == first
    assert (head, count) == (sp.ledger.head, len(sp.ledger.records))
    assert source == snapshot and source in sp.ledger.records
    assert source.hash in first.payload["note"]
    assert sp.ledger.by_type("fixture_migration_contract")[0].hash in first.payload["note"]
    resumed = resume_workflow(sp, wid, steps).execute()
    assert resumed.state == {"a": 1, "b": 1}
    with pytest.raises(migrate.MigrationRefused, match="stale"):
        migrate.restore_fixture_checkpoint(sp, wid, steps, source_hash=source.hash)


@pytest.mark.parametrize("attack", ["fabricated", "altered", "missing_plan", "uncertain",
                                  "wrong_actor", "changed_contract", "ambiguous"])
def test_invalid_migration_never_appends_a_v2_checkpoint(attack):
    sp, wid, steps, source = fixture()
    source_hash = source.hash
    if attack == "fabricated":
        source_hash = "DOES_NOT_EXIST"
    elif attack == "altered":
        source.payload["state"]["a"] = 999
    elif attack == "missing_plan":
        # Rebuild a valid chain with no plan: hashing alone is insufficient.
        sp = EventSpine(EvidenceLedger("sha256:isolated-compatibility-fixture"))
        source_hash = sp.ledger.append("workflow", source.payload).hash
    elif attack in ("uncertain", "wrong_actor", "ambiguous"):
        p = copy.deepcopy(source.payload)
        if attack == "uncertain":
            p["note"] = "killed_during:b"
        elif attack == "wrong_actor":
            p["actor"] = "other"
        else:
            p["completed_steps"] = ["b"]
        source_hash = sp.ledger.append("workflow", p).hash
    else:
        steps[1].max_retries += 1
    before = len(sp.ledger.records)
    with pytest.raises((migrate.MigrationRefused, ValueError)):
        migrate.restore_fixture_checkpoint(sp, wid, steps, source_hash=source_hash)
    assert len(sp.ledger.records) == before
    assert not any(r.payload.get("schema_version") == "2" for r in sp.ledger.by_type("workflow"))


def test_live_history_and_retroactive_safety_declarations_are_refused(tmp_path):
    sp, wid, steps, _ = fixture()
    with pytest.raises(migrate.MigrationRefused, match="precede"):
        migrate.prepare_fixture_rollback(sp, wid, steps, actor="synthetic",
                                         legal_principal="fixture_principal")
    steps[0].retry_safe = False
    with pytest.raises(migrate.MigrationRefused, match="harmless"):
        migrate.prepare_fixture_rollback(sp, "p4x-new", steps, actor="synthetic",
                                         legal_principal="fixture_principal")
    ledger = EvidenceLedger("sha256:fixture", str(tmp_path / "history.jsonl"))
    try:
        with pytest.raises(migrate.MigrationRefused, match="in-memory"):
            migrate.prepare_fixture_rollback(EventSpine(ledger), "p4x-new", steps,
                                             actor="synthetic", legal_principal="fixture_principal")
    finally:
        ledger.close()


def test_continuation_does_not_reseal_old_experiments_or_follow_unreviewed_drift(monkeypatch):
    assert repair_spec.spec_hash() == repair_spec.SPEC_SHA256
    assert migration_spec.spec_hash() == migration_spec.SPEC_SHA256
    assert compatibility.WORKFLOW_CLASS_SHA256 != migration_spec.SUBJECT_CLASS_SHA256
    assert subject_class_intact()
    monkeypatch.setitem(compatibility.WORKFLOW_CLASS_SHA256, "DurableWorkflow", "0" * 64)
    assert not subject_class_intact()
