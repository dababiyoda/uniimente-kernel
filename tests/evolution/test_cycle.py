"""WP-05 EvolutionCycle + append_many suite — the engine and its substrate.

append_many correctness is proven against the WP-04 fake-DBAPI discipline
extended with counters (CountingConnection from the pinned bench harness):
byte-identical records vs sequential append (THE hash-parity test), empty
no-op, TypeError on non-KernelModel, all-or-nothing mid-batch rollback,
seq/prev_hash continuity, per-element spine_seq, and the 13-op profile.

Engine tests drive the compiled WP-02 constitution + WP-01 gate on a file
spine with the BenchmarkAdapter; every refusal must leave the spine
byte-identical (fail closed).
"""
from __future__ import annotations

import pytest

from kernel.adapters.benchmark import BenchmarkAdapter
from kernel.authority.approvals import ApprovalService
from kernel.contracts.action import ActionIntent
from kernel.contracts.evolution import AuditFinding, ExperimentSpec
from kernel.crypto.hashing import canonical_json
from kernel.evolution import CycleError, EvolutionCycle
from kernel.gate.pipeline import Gate
from kernel.spine import GENESIS_HASH, PostgresSpine, Spine, SpineError
from kernel.ucl import Constitution, compile_policy_fn
from kernel.ucl.version import constitution_version_from_dir, policy_version

from scripts.run_evolution_cycle import make_branches, pinned_protocol
from scripts.wp05_bench import (
    BASELINE_OPS,
    CANDIDATE_OPS,
    CountingConnection,
    FAKE_DSN,
    PINNED_EVENTS,
    TABLE,
)
from tests.ucl.conftest import _locate_constitution_dir

# ---------------------------------------------------------- append_many


def pg_spine(store=None) -> tuple[PostgresSpine, CountingConnection]:
    if store is None:
        store = {}
    conn = CountingConnection(store)
    spine = PostgresSpine(FAKE_DSN, table=TABLE, connect=lambda dsn: conn)
    conn.reset()  # DDL is construction, not workload
    return spine, conn


def test_10_append_many_hash_parity_with_sequential_append():
    """THE critical test: one batch == N sequential appends, byte-identical."""
    batch_spine, _ = pg_spine()
    seq_spine, _ = pg_spine()
    batch = batch_spine.append_many(list(PINNED_EVENTS))
    sequential = [seq_spine.append(e) for e in PINNED_EVENTS]
    assert batch == sequential
    assert canonical_json(batch) == canonical_json(sequential)
    assert batch_spine.verify_chain() is True
    assert seq_spine.verify_chain() is True


def test_11_append_many_empty_list_is_noop():
    spine, conn = pg_spine()
    assert spine.append_many([]) == []
    assert conn.op_count == 0  # spine untouched: no lock, no head, no commit
    assert spine.next_seq == 0


def test_12_append_many_rejects_non_kernel_model_elements():
    spine, _ = pg_spine(store := {})
    with pytest.raises(TypeError, match="KernelModel"):
        spine.append_many([PINNED_EVENTS[0], {"not": "a model"}])
    with pytest.raises(TypeError, match="KernelModel"):
        spine.append_many(["InstitutionalEvent"])
    assert store[TABLE] == []  # refusal happens before any DB op


def test_13_append_many_all_or_nothing_rollback_on_mid_batch_failure():
    spine, conn = pg_spine(store := {})
    spine.append(PINNED_EVENTS[0])  # one committed record first
    conn.reset()
    head_before = spine.get(0)["record_hash"]
    conn.fail_at_insert = 3  # the 4th insert of the batch fails
    with pytest.raises(SpineError, match="append_many failed"):
        spine.append_many(list(PINNED_EVENTS))
    # Rolled back: no partial rows, head unchanged, chain still verifies.
    assert len(store[TABLE]) == 1
    assert conn.rollbacks >= 1
    assert spine.get(0)["record_hash"] == head_before
    assert spine.next_seq == 1
    assert spine.verify_chain() is True


def test_14_append_many_chain_continuity_and_next_seq_after_batch():
    spine, _ = pg_spine()
    first = spine.append(PINNED_EVENTS[0])
    batch = spine.append_many(list(PINNED_EVENTS[1:]))
    assert [r["seq"] for r in batch] == list(range(1, 10))
    assert batch[0]["prev_hash"] == first["record_hash"]
    for prev, rec in zip(batch, batch[1:]):
        assert rec["prev_hash"] == prev["record_hash"]
    assert spine.next_seq == 10
    assert spine.verify_chain() is True
    assert batch[-1]["prev_hash"] != GENESIS_HASH


def test_15_append_many_assigns_spine_seq_per_element():
    spine, _ = pg_spine()
    assert all(e.spine_seq == -1 for e in PINNED_EVENTS)  # not yet sequenced
    records = spine.append_many(list(PINNED_EVENTS))
    assert [r["payload"]["spine_seq"] for r in records] == list(range(10))
    # The caller's frozen models are never mutated.
    assert all(e.spine_seq == -1 for e in PINNED_EVENTS)


def test_16_append_many_op_profile_is_one_lock_one_head_n_inserts_one_commit():
    spine, conn = pg_spine()
    spine.append_many(list(PINNED_EVENTS))
    assert conn.op_count == CANDIDATE_OPS == 13
    assert conn.trace == ["lock", "head"] + ["insert"] * 10 + ["commit"]


# ------------------------------------------------------------- the engine


def build_world(tmp_path):
    """Compiled constitution + gate + BenchmarkAdapter + cycle, file spine."""
    constitution_dir = _locate_constitution_dir()
    model = Constitution.from_directory(constitution_dir, current_state="normal")
    versions = {
        "policy_version": policy_version(model),
        "constitution_version": constitution_version_from_dir(constitution_dir),
    }
    policy_fn = compile_policy_fn(model, **versions)
    spine = Spine(tmp_path / "spine")
    authority = ApprovalService(approver_id="founder")
    gate = Gate(
        versions["policy_version"],
        versions["constitution_version"],
        authority,
        spine,
        policy_fn=policy_fn,
    )
    adapter = BenchmarkAdapter(witness_public_key=authority.public_key)
    gate.register_adapter(adapter.adapter_id, adapter.public_key_hex)
    cycle = EvolutionCycle(
        gate, spine, authority, actor_id="uniimente-kernel", organ_id="evolution-organ"
    )
    return {
        "spine": spine,
        "authority": authority,
        "gate": gate,
        "adapter": adapter,
        "cycle": cycle,
    }


def make_spec(branch_id: str) -> ExperimentSpec:
    return ExperimentSpec(
        branch_id=branch_id,
        metric_id="pg_spine_bulk_append_ops",
        metric_unit="connection_ops",
        baseline_value=float(BASELINE_OPS),
        threshold_improvement=0.5,
        direction="decrease",
        harness_ref="scripts/wp05_bench.py",
        workload_id="append10-pinned-events",
        pre_registered=True,
    )


def make_intent(spec: ExperimentSpec) -> ActionIntent:
    return ActionIntent(
        actor_id="uniimente-kernel",
        organ_id="evolution-organ",
        legal_principal="Uniimente Ltd",
        objective="WP-05 test: measure append_many vs sequential append op counts",
        action_type="evolution_experiment",
        resource="kernel",
        target="bench://wp05/pg-spine-bulk-append",
        payload={"experiment_spec_id": spec.id},
        consequence_class="C2",
        evidence_ids=[],
        expected_outcome=canonical_json(pinned_protocol()),
        rollback=None,
        expiry_minutes=30,
    )


def spine_kinds(spine) -> list[str]:
    return [r["kind"] for r in spine.iter()]


def test_17_propose_tree_seals_branches_then_tree_in_order(tmp_path):
    w = build_world(tmp_path)
    branches = list(make_branches())
    drafts = list(branches)
    tree = w["cycle"].propose_tree("objective", "wp05", "rule", branches)
    assert spine_kinds(w["spine"]) == [
        "StrategyBranch",
        "StrategyBranch",
        "StrategyBranch",
        "StrategyTree",
    ]
    payloads = [r["payload"] for r in w["spine"].iter()]
    assert all(p["tree_id"] == tree.id for p in payloads[:3])
    assert payloads[3]["branch_ids"] == [b.id for b in drafts]
    # Drafts are never mutated (frozen discipline).
    assert all(b.tree_id == "" for b in drafts)


def test_18_select_refuses_killed_branch_and_empty_eligibility(tmp_path):
    w = build_world(tmp_path)
    cycle = w["cycle"]
    branches = list(make_branches())
    tree = cycle.propose_tree("objective", "wp05", "rule", branches)
    b1, b2, b3 = branches
    # Kill the highest-expected_value branch (b1): it must be ineligible even
    # though it would win on expected_value.
    cycle.audit(b1.id, "operator", [AuditFinding(dimension="d", attack="a", result="fail")])
    cycle.audit(b2.id, "operator", [AuditFinding(dimension="d", attack="a", result="fail")])
    cycle.audit(b3.id, "operator", [AuditFinding(dimension="d", attack="a", result="fail")])
    before = w["spine"].next_seq
    with pytest.raises(CycleError, match="no selectable branch"):
        cycle.select(tree, list(cycle._audits.values()))
    assert w["spine"].next_seq == before  # refusal appended nothing


def test_19_selection_rule_picks_b1_among_passing(tmp_path):
    w = build_world(tmp_path)
    cycle = w["cycle"]
    branches = list(make_branches())
    tree = cycle.propose_tree("objective", "wp05", "rule", branches)
    b1, b2, b3 = branches
    audits = [
        cycle.audit(b1.id, "operator", [AuditFinding(dimension="d", attack="a", result="pass")]),
        cycle.audit(b2.id, "operator", [AuditFinding(dimension="d", attack="a", result="fail")]),
        cycle.audit(b3.id, "operator", [AuditFinding(dimension="d", attack="a", result="fail")]),
    ]
    selected = cycle.select(tree, audits)
    assert selected.id == b1.id  # B2/B3 killed; B1 also wins on expected_value
    (event,) = [r for r in w["spine"].iter() if r["kind"] == "STRATEGY_SELECTED"]
    assert event["refs"]["branch_id"] == b1.id
    assert event["refs"]["tree_id"] == tree.id
    # Audit-killed branches are refused even if somehow passing the rule:
    # B3 fails risk/reversibility bounds anyway; B2's audit killed it.


def test_20_experiment_must_be_registered_before_execution(tmp_path):
    w = build_world(tmp_path)
    cycle, gate, authority, adapter = (
        w["cycle"],
        w["gate"],
        w["authority"],
        w["adapter"],
    )
    branches = list(make_branches())
    tree = cycle.propose_tree("objective", "wp05", "rule", branches)
    b1 = branches[0]
    spec = make_spec(b1.id)
    intent = make_intent(spec)

    before = w["spine"].next_seq
    approval = authority.issue_approval(gate.fingerprint(intent))
    with pytest.raises(CycleError, match="not registered"):
        cycle.run_experiment(intent, adapter, approval)
    assert w["spine"].next_seq == before  # refusal appended nothing

    # After registration the gate loop runs, and the spec record precedes the
    # intent record on the spine (order enforced via seq numbers).
    spec_record = cycle.register_experiment(spec)
    approval = authority.issue_approval(gate.fingerprint(intent))
    episode = cycle.run_experiment(intent, adapter, approval)
    assert episode.closed and episode.close_reason == "completed"
    (intent_record,) = [
        r for r in w["spine"].iter() if r["kind"] == "ActionIntent"
    ]
    assert spec_record["seq"] < intent_record["seq"]


def test_21_retain_requires_threshold_met(tmp_path):
    w = build_world(tmp_path)
    cycle = w["cycle"]
    branches = list(make_branches())
    cycle.propose_tree("objective", "wp05", "rule", branches)
    b1 = branches[0]
    before = w["spine"].next_seq
    with pytest.raises(CycleError, match="retain requires threshold_met"):
        cycle.decide(b1, decision="retain", rationale="r", threshold_met=False)
    assert w["spine"].next_seq == before  # spine untouched
    decision = cycle.decide(b1, decision="retain", rationale="r", threshold_met=True)
    assert decision.decision == "retain"
    assert decision.loop_id == cycle.loop_id


def test_22_kill_decisions_sealed_for_killed_branches(tmp_path):
    w = build_world(tmp_path)
    cycle = w["cycle"]
    branches = list(make_branches())
    tree = cycle.propose_tree("objective", "wp05", "rule", branches)
    b1, b2, b3 = branches
    audits = [
        cycle.audit(b1.id, "operator", [AuditFinding(dimension="d", attack="a", result="pass")]),
        cycle.audit(b2.id, "operator", [AuditFinding(dimension="d", attack="a", result="fail")]),
        cycle.audit(b3.id, "operator", [AuditFinding(dimension="d", attack="a", result="fail")]),
    ]
    cycle.select(tree, audits)
    d2 = cycle.decide(b2, decision="kill", rationale="audit killed: ADR-1 violation")
    d3 = cycle.decide(b3, decision="kill", rationale="audit killed: writer multiplication")
    decisions = [r for r in w["spine"].iter() if r["kind"] == "RetainRegressKillDecision"]
    assert [r["payload"]["id"] for r in decisions] == [d2.id, d3.id]
    assert all(r["payload"]["decision"] == "kill" for r in decisions)
    assert all(r["payload"]["loop_id"] == cycle.loop_id for r in decisions)


def test_23_aborted_cycle_seals_no_capsule_contract(tmp_path):
    w = build_world(tmp_path)
    cycle = w["cycle"]
    branches = list(make_branches())
    cycle.propose_tree("objective", "wp05", "rule", branches)
    loop = cycle.seal_aborted("operator aborted the cycle")
    assert loop.status == "aborted"
    assert loop.capsule_id == ""  # the only honest empty capsule_id (ADR-8)
    kinds = spine_kinds(w["spine"])
    assert "ClosureLoop" in kinds
    assert "EvolutionCapsule" not in kinds
    assert "CYCLE_ABORTED" in kinds
    assert w["spine"].verify_chain() is True
