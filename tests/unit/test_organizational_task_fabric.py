"""Phase-2 tests for the replay-derived organizational task fabric.

The suite includes negative controls. Passing proves contract/state invariants
on the canonical EventSpine; it does not prove cross-organ closure or topology
superiority.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from events.spine import EventSpine, SPIFFE_PREFIX
from events.task_fabric import (
    AuthorityViolation,
    BudgetExceeded,
    InvalidTransition,
    ReconciliationRequired,
    TaskFabric,
    TaskFabricError,
)
from provenance.ledger import EvidenceLedger


ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
GENESIS = "sha256:" + "0" * 64
TASK_ID = "4cb51f42-2e8a-49c1-bcdd-af49494b1099"
MISSION_ID = "f57302c3-0aaa-45e2-b1c7-f0fb5d372b39"
WORKER = SPIFFE_PREFIX + "worker/wmi-evaluator"
REPLACEMENT = SPIFFE_PREFIX + "worker/wmi-replacement"
COORDINATOR = SPIFFE_PREFIX + "organ/wealthmachine"
EVALUATOR = SPIFFE_PREFIX + "worker/independent-evaluator"
SOURCE = SPIFFE_PREFIX + "organ/kernel-task-fabric"
DIGEST = "sha256:" + "a" * 64


def _validator(name: str) -> Draft202012Validator:
    with (CONTRACTS / name).open(encoding="utf-8") as handle:
        document = json.load(handle)
    Draft202012Validator.check_schema(document)
    return Draft202012Validator(document, format_checker=FormatChecker())


def _fabric(path: str | None = None) -> TaskFabric:
    return TaskFabric(
        EventSpine(EvidenceLedger(GENESIS, path=path)),
        source_identity=SOURCE,
    )


def _envelope(**changes) -> dict:
    value = {
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "mission_id": MISSION_ID,
        "founder_intent_ref": "INTENT-OM-2026-08-28",
        "subgoal_ref": "subgoal:venture-evaluation",
        "parent_task_id": None,
        "idempotency_key": "task-create-1",
        "objective": "Evaluate one internal opportunity with independent dissent.",
        "required_capability": "opportunity.evaluate",
        "created_by": COORDINATOR,
        "legal_principal": "Alfonso Lopez",
        "authority_refs": ["authority:internal-sandbox-only"],
        "consequence_class": "internal_write",
        "external_effect_policy": "none",
        "resource_budget": {
            "budget_ceiling_usd": 5,
            "compute_ceiling": 10,
            "model_call_ceiling": 3,
        },
        "context_policy": {
            "permitted_data_classes": ["public", "synthetic"],
            "context_refs": ["context:opportunity-1"],
            "prohibited_context": ["credentials"],
        },
        "tool_policy": {
            "permitted_tools": ["tool:read-corpus"],
            "prohibited_tools": ["tool:publish", "tool:payment"],
        },
        "evidence_requirements": ["typed result", "independent assessment"],
        "prohibited_actions": ["publish", "move_money", "contact_external_party"],
        "sensitivity": "internal",
        "created_at": "2026-08-30T10:00:00Z",
        "acceptance_authority_ref": "human:alfonso",
        "independent_evaluation_required": True,
        "authority_invariants": {
            "organization_may_create_authority": False,
            "worker_may_inherit_authority": False,
            "consequence_gate_bypass_permitted": False,
        },
    }
    value.update(changes)
    return value


def _lease(*, lease_id: str = "2104c412-0ee5-423f-9a42-4f96d88b1f45",
           worker: str = WORKER, replaces: str | None = None, **changes) -> dict:
    value = {
        "schema_version": "1.0",
        "lease_id": lease_id,
        "task_id": TASK_ID,
        "mission_id": MISSION_ID,
        "worker_identity": worker,
        "issued_by": COORDINATOR,
        "capability": "opportunity.evaluate",
        "capability_grant_ref": "grant:opportunity-evaluate",
        "authority_refs": ["authority:internal-sandbox-only"],
        "permitted_tools": ["tool:read-corpus"],
        "permitted_data_classes": ["public"],
        "context_refs": ["context:opportunity-1"],
        "resource_budget": {
            "budget_ceiling_usd": 4,
            "compute_ceiling": 8,
            "model_call_ceiling": 2,
        },
        "issued_at": "2026-08-30T10:01:00Z",
        "expires_at": "2026-08-30T10:06:00Z",
        "consequence_ceiling": "internal_write",
        "output_contract_ref": "contract:venture-assessment-v1",
        "heartbeat_interval_seconds": 30,
        "termination_condition": "task terminal, lease expiry or explicit revocation",
        "replaces_lease_id": replaces,
        "one_task_only": True,
        "authority_inheritance": False,
    }
    value.update(changes)
    return value


def _to_queue(fabric: TaskFabric) -> None:
    fabric.create_task(_envelope(), transition_key="create")
    fabric.transition(TASK_ID, "ADMITTED", actor=COORDINATOR,
                      transition_key="admit")
    fabric.transition(TASK_ID, "QUEUED", actor=COORDINATOR,
                      transition_key="queue")


def _to_running(fabric: TaskFabric) -> None:
    _to_queue(fabric)
    fabric.issue_lease(_lease(), transition_key="lease")
    fabric.transition(
        TASK_ID,
        "RUNNING",
        actor=WORKER,
        worker_identity=WORKER,
        lease_id=_lease()["lease_id"],
        observed_at="2026-08-30T10:02:00Z",
        transition_key="run",
    )


@pytest.mark.parametrize(
    ("name", "document"),
    [
        ("task-envelope.schema.json", _envelope()),
        ("worker-lease.schema.json", _lease()),
    ],
)
def test_phase2_contract_examples_are_valid(name: str, document: dict):
    _validator(name).validate(document)


@pytest.mark.parametrize(
    ("name", "document"),
    [
        ("task-envelope.schema.json", _envelope()),
        ("worker-lease.schema.json", _lease()),
    ],
)
def test_phase2_contracts_fail_closed_on_unknown_fields(name: str, document: dict):
    document["unowned_semantic"] = True
    with pytest.raises(Exception):
        _validator(name).validate(document)


def test_task_receipt_schema_validates_emitted_receipts():
    fabric = _fabric()
    receipt = fabric.create_task(_envelope(), transition_key="create")
    _validator("task-receipt.schema.json").validate(receipt.to_dict())


def test_full_internal_lifecycle_and_clean_dissolution():
    fabric = _fabric()
    _to_running(fabric)
    fabric.transition(
        TASK_ID,
        "SUBMITTED",
        actor=WORKER,
        worker_identity=WORKER,
        lease_id=_lease()["lease_id"],
        result_digest=DIGEST,
        evidence_refs=("evidence:result",),
        tool_refs=("tool:read-corpus",),
        resource_usage={"cost_usd": 1, "compute_used": 2, "model_calls": 1},
        consequence_status="not_attempted",
        transition_key="submit",
    )
    fabric.transition(
        TASK_ID,
        "VERIFIED",
        actor=EVALUATOR,
        assessment_refs=("assessment:independent",),
        dissent_refs=("dissent:none-material",),
        dissent_preserved=True,
        transition_key="verify",
    )
    fabric.transition(TASK_ID, "CLOSED", actor=COORDINATOR,
                      transition_key="close")
    assert fabric.tasks() == {TASK_ID: "CLOSED"}
    assert [r.state for r in fabric.receipts(TASK_ID)] == [
        "CREATED", "ADMITTED", "QUEUED", "LEASED",
        "RUNNING", "SUBMITTED", "VERIFIED", "CLOSED",
    ]
    ready, reasons = fabric.dissolution_readiness(MISSION_ID)
    assert ready and not reasons
    event = fabric.dissolve_mission(
        MISSION_ID,
        actor=COORDINATOR,
        transition_key="dissolve",
        evidence_refs=("evidence:all-task-receipts",),
    )
    assert event.type == "mission.organization_dissolved"


def test_restart_rebuilds_exact_state_without_redispatch(tmp_path):
    path = str(tmp_path / "task-ledger.jsonl")
    first = _fabric(path)
    _to_running(first)
    head = first.spine.ledger.head
    count = len(first.spine.ledger.records)

    resumed = _fabric(path)

    assert resumed.tasks() == {TASK_ID: "RUNNING"}
    assert [r.state for r in resumed.receipts(TASK_ID)] == [
        "CREATED", "ADMITTED", "QUEUED", "LEASED", "RUNNING"
    ]
    assert resumed.spine.ledger.head == head
    assert len(resumed.spine.ledger.records) == count
    assert resumed.spine.ledger.verify_chain()[0]


def test_duplicate_command_is_idempotent_and_conflicting_reuse_fails():
    fabric = _fabric()
    first = fabric.create_task(_envelope(), transition_key="same")
    count = len(fabric.spine.ledger.by_type("event"))

    second = fabric.create_task(_envelope(), transition_key="same")

    assert second.event_id == first.event_id
    assert len(fabric.spine.ledger.by_type("event")) == count
    changed = _envelope(objective="different content under same key")
    with pytest.raises(TaskFabricError, match="idempotency key"):
        fabric.create_task(changed, transition_key="same")


def test_invalid_and_stale_transitions_fail_closed():
    fabric = _fabric()
    fabric.create_task(_envelope(), transition_key="create")
    with pytest.raises(InvalidTransition):
        fabric.transition(TASK_ID, "RUNNING", actor=WORKER,
                          transition_key="skip")
    assert fabric.tasks()[TASK_ID] == "CREATED"


def test_worker_lease_cannot_widen_authority_tools_or_budget():
    fabric = _fabric()
    _to_queue(fabric)
    widened = _lease(
        authority_refs=["authority:internal-sandbox-only", "authority:publish"],
        permitted_tools=["tool:read-corpus", "tool:publish"],
    )
    with pytest.raises(AuthorityViolation):
        fabric.issue_lease(widened, transition_key="widen")
    too_large = _lease(
        lease_id="dc253e56-4bba-4897-bef1-5992f9466162",
        resource_budget={
            "budget_ceiling_usd": 50,
            "compute_ceiling": 8,
            "model_call_ceiling": 2,
        },
    )
    with pytest.raises(BudgetExceeded):
        fabric.issue_lease(too_large, transition_key="overspend")


def test_replacement_requires_fresh_lease_and_no_implicit_inheritance():
    fabric = _fabric()
    _to_queue(fabric)
    original = _lease()
    fabric.issue_lease(original, transition_key="lease")
    fabric.expire_lease(
        TASK_ID,
        observed_at="2026-08-30T10:07:00Z",
        transition_key="expire",
        evidence_ref="evidence:lease-expired",
    )
    fabric.transition(TASK_ID, "QUEUED", actor=COORDINATOR,
                      transition_key="requeue")
    with pytest.raises(TaskFabricError, match="fresh lease_id"):
        fabric.issue_lease(
            _lease(worker=REPLACEMENT, replaces=original["lease_id"]),
            transition_key="reuse-id",
        )
    replacement = _lease(
        lease_id="01619a32-ed66-4897-9262-f5d44d5586dc",
        worker=REPLACEMENT,
        replaces=original["lease_id"],
    )
    receipt = fabric.issue_lease(replacement, transition_key="replacement")
    assert receipt.worker_identity == REPLACEMENT
    assert receipt.authority_refs == tuple(_envelope()["authority_refs"])


def test_uncertain_external_effect_cannot_retry_blindly():
    fabric = _fabric()
    _to_running(fabric)
    with pytest.raises(ReconciliationRequired):
        fabric.transition(
            TASK_ID,
            "FAILED",
            actor=WORKER,
            transition_key="bad-failure",
            consequence_status="uncertain",
            evidence_refs=("evidence:ack-lost",),
        )
    fabric.transition(
        TASK_ID,
        "RECONCILIATION_REQUIRED",
        actor=WORKER,
        worker_identity=WORKER,
        lease_id=_lease()["lease_id"],
        transition_key="uncertain",
        consequence_status="uncertain",
        evidence_refs=("evidence:ack-lost",),
    )
    with pytest.raises(ReconciliationRequired):
        fabric.transition(
            TASK_ID,
            "RETRY_ELIGIBLE",
            actor=COORDINATOR,
            transition_key="blind-retry",
            evidence_refs=("evidence:still-unknown",),
        )
    receipt = fabric.transition(
        TASK_ID,
        "RETRY_ELIGIBLE",
        actor=EVALUATOR,
        transition_key="reconciled-retry",
        consequence_status="reconciled",
        evidence_refs=("evidence:confirmed-no-effect",),
    )
    assert receipt.state == "RETRY_ELIGIBLE"


def test_worker_cannot_verify_own_result_and_dissent_must_be_preserved():
    fabric = _fabric()
    _to_running(fabric)
    fabric.transition(
        TASK_ID,
        "SUBMITTED",
        actor=WORKER,
        worker_identity=WORKER,
        lease_id=_lease()["lease_id"],
        result_digest=DIGEST,
        transition_key="submit",
    )
    with pytest.raises(AuthorityViolation, match="verify its own"):
        fabric.transition(
            TASK_ID,
            "VERIFIED",
            actor=WORKER,
            assessment_refs=("assessment:self",),
            dissent_preserved=True,
            transition_key="self-verify",
        )
    with pytest.raises(TaskFabricError, match="preserve dissent"):
        fabric.transition(
            TASK_ID,
            "VERIFIED",
            actor=EVALUATOR,
            assessment_refs=("assessment:independent",),
            dissent_preserved=False,
            transition_key="hide-dissent",
        )


def test_resource_envelope_is_cumulative():
    fabric = _fabric()
    _to_running(fabric)
    with pytest.raises(BudgetExceeded):
        fabric.transition(
            TASK_ID,
            "SUBMITTED",
            actor=WORKER,
            worker_identity=WORKER,
            lease_id=_lease()["lease_id"],
            result_digest=DIGEST,
            resource_usage={"cost_usd": 6, "compute_used": 1, "model_calls": 1},
            transition_key="over-budget",
        )
    assert fabric.tasks()[TASK_ID] == "RUNNING"


def test_poison_output_is_quarantined_and_not_retryable():
    fabric = _fabric()
    _to_running(fabric)
    fabric.transition(
        TASK_ID,
        "QUARANTINED",
        actor=EVALUATOR,
        evidence_refs=("evidence:poison-output",),
        transition_key="quarantine",
    )
    with pytest.raises(InvalidTransition):
        fabric.transition(
            TASK_ID,
            "RETRY_ELIGIBLE",
            actor=COORDINATOR,
            evidence_refs=("evidence:retry-request",),
            transition_key="retry-poison",
        )
    fabric.transition(
        TASK_ID,
        "TERMINATED",
        actor=COORDINATOR,
        transition_key="terminate-poison",
    )
    assert fabric.tasks()[TASK_ID] == "TERMINATED"


def test_dissolution_refuses_active_tasks_and_open_obligations():
    fabric = _fabric()
    _to_running(fabric)
    ready, reasons = fabric.dissolution_readiness(
        MISSION_ID, open_obligation_refs=("obligation:1",)
    )
    assert not ready
    assert "mission has non-terminal tasks" in reasons
    assert "mission has active worker leases" in reasons
    assert "mission has open obligations" in reasons
    with pytest.raises(TaskFabricError, match="cannot dissolve"):
        fabric.dissolve_mission(
            MISSION_ID,
            actor=COORDINATOR,
            transition_key="too-early",
            evidence_refs=("evidence:partial",),
        )


def test_expired_lease_cannot_start_and_expiry_becomes_retry_eligible():
    fabric = _fabric()
    _to_queue(fabric)
    fabric.issue_lease(_lease(), transition_key="lease")
    with pytest.raises(TaskFabricError, match="expired lease"):
        fabric.transition(
            TASK_ID,
            "RUNNING",
            actor=WORKER,
            worker_identity=WORKER,
            lease_id=_lease()["lease_id"],
            observed_at="2026-08-30T10:07:00Z",
            transition_key="late-start",
        )
    receipt = fabric.expire_lease(
        TASK_ID,
        observed_at="2026-08-30T10:07:00Z",
        transition_key="expire",
        evidence_ref="evidence:ttl-observed",
    )
    assert receipt.state == "RETRY_ELIGIBLE"


def test_external_task_requires_gate_policy_negative_control():
    document = _envelope(consequence_class="external",
                         external_effect_policy="none")
    with pytest.raises(Exception):
        _validator("task-envelope.schema.json").validate(document)
    with pytest.raises(AuthorityViolation):
        _fabric().create_task(document, transition_key="external")
