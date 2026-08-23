"""The Package 4 experiment is frozen. These tests are the lock.

Written in the same commit as the spec and BEFORE any candidate or any seam.
Their job is not to judge the experiment — it is to make silent retuning
impossible once implementation starts.
"""
import hashlib
import inspect
import os
import subprocess

import pytest

from evolution.migration import spec

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_spec_seal_matches_its_contents():
    assert spec.spec_hash() == spec.SPEC_SHA256, (
        "the frozen Package 4 experiment changed.\n"
        f"  recorded: {spec.SPEC_SHA256}\n  computed: {spec.spec_hash()}\n"
        "If this is a deliberate amendment, say so in the commit message and in "
        "docs/release/package-4/ — do not just update the hash."
    )


def test_spec_seal_is_deterministic():
    assert spec.canonical_json() == spec.canonical_json()
    assert spec.spec_hash() == hashlib.sha256(spec.canonical_json().encode()).hexdigest()


def test_exactly_once_is_binary_not_a_near_miss():
    """Exactly-once admits no partial credit. A single duplicated completed step
    is duplicated work, and 0.99 must not read as success — the same discipline
    that made Package 3's threshold 4/4 rather than 90%."""
    e = spec.EXPERIMENT
    assert spec.EXACTLY_ONCE_THRESHOLD == 1.0
    assert e.baseline == 0.0 and e.direction == "gte"
    assert e.resolves(1.0) is True
    assert e.resolves(0.99) is False
    assert e.resolves(0.5) is False


def test_experiment_compiles_under_the_existing_compiler():
    from evolution.experiment import ExperimentCompiler, ExperimentSpec

    assert isinstance(spec.EXPERIMENT, ExperimentSpec)
    assert spec.EXPERIMENT.validate() == []
    assert ExperimentCompiler().compile(spec.EXPERIMENT) is spec.EXPERIMENT
    assert spec.EXPERIMENT.reversible is True
    assert spec.EXPERIMENT.budget_usd == 0.0


def test_base_commit_is_the_verified_package_3_merge():
    assert spec.BASE_COMMIT == "5e02e47f604770fdee2c05b25418ef003f5b2b92"
    assert spec.APPROVED_PLAN_COMMIT == "961f6fc5798588f0aaeda039b5feee4365a7ce85"
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", spec.BASE_COMMIT, "HEAD"],
        cwd=ROOT, capture_output=True, text=True)
    if proc.returncode == 128:
        pytest.skip("git history unavailable (shallow checkout)")
    assert proc.returncode == 0


def test_the_subject_class_is_byte_identical_to_the_frozen_hash():
    """`events/spine.py` is authorized to gain a factory. The DurableWorkflow
    CLASS is not authorized to change at all — it stays the default provider,
    the benchmark and the rollback target."""
    from events.spine import DurableWorkflow, WorkflowStep

    for obj in (DurableWorkflow, WorkflowStep):
        digest = hashlib.sha256(inspect.getsource(obj).encode()).hexdigest()
        assert digest == spec.SUBJECT_CLASS_SHA256[obj.__name__], (
            f"{obj.__name__} was modified; the original engine must stay "
            f"byte-identical")


def test_canonical_construction_sites_are_real_and_named():
    """The boundary must be the real one. Package 3's was a private registry;
    these are files the verifier actually runs."""
    assert len(spec.CANONICAL_CONSTRUCTION_SITES) == 4
    files = {s["file"] for s in spec.CANONICAL_CONSTRUCTION_SITES}
    assert files == {"closure/kernel_registry.py", "loom/weaver.py"}
    assert any("verifier V3" in s["exercised_by"]
               for s in spec.CANONICAL_CONSTRUCTION_SITES)
    for site in spec.CANONICAL_CONSTRUCTION_SITES:
        assert os.path.exists(os.path.join(ROOT, site["file"]))
        assert site["kind"] in ("construct", "resume")


def test_only_the_three_authorized_files_may_change():
    """Founder decision 1 authorized exactly three canonical modifications."""
    assert spec.FILES_AUTHORIZED_TO_CHANGE == (
        "events/spine.py", "closure/kernel_registry.py", "loom/weaver.py")
    for forbidden in ("constitution/", "authority/", "identity/", "policy/",
                      "provenance/", "linker/", "ventures/", "contracts/"):
        assert forbidden in spec.FILES_FORBIDDEN_TO_CHANGE


def test_held_out_expectations_match_the_original_engine_today():
    """Every frozen expectation was MEASURED, not guessed. If the original's
    behaviour ever differs from these, the experiment must be re-frozen rather
    than quietly re-interpreted."""
    from events.spine import (DurableWorkflow, EventError, EventSpine,
                              WorkflowFailed, WorkflowKilled, WorkflowStep)
    from provenance.ledger import EvidenceLedger

    def spine():
        return EventSpine(EvidenceLedger("sha256:" + "0" * 64))

    def steps_for(case, calls):
        out = []
        for name in case["steps"]:
            fails = name == case.get("failing_step")

            def run(s, _n=name, _f=fails):
                calls.append(_n)
                if _f:
                    raise RuntimeError("boom")
                return {_n: 1}

            out.append(WorkflowStep(
                name=name, run=run,
                compensate=lambda s, _n=name: calls.append("undo:" + _n),
                max_retries=0, approval_wait=(name == case.get("approval_step"))))
        return out

    by_id = {c["id"]: c for c in spec.HELD_OUT_CORPUS}

    # HO-1 / HO-2: interrupt, then resume; no completed step re-executes.
    for cid in ("HO-1", "HO-2"):
        case = by_id[cid]
        calls, sp = [], spine()
        wf = DurableWorkflow(sp, cid, steps_for(case, calls), actor="a",
                             legal_principal="alfonso_lopez")
        with pytest.raises(WorkflowKilled):
            wf.execute(kill_at_step=case["kill_at"])
        assert tuple(calls) == case["calls_at_interrupt"], cid
        last = [r for r in sp.ledger.by_type("workflow")
                if r.payload["workflow_id"] == cid][-1].payload
        for key, want in case["at_interrupt"].items():
            assert last[key] == want, f"{cid}.{key}"

        resumed = DurableWorkflow.resume(sp, cid, steps=steps_for(case, calls))
        resumed.execute()
        assert tuple(calls) == case["calls_after_resume"], f"{cid} exactly-once"
        for key, want in case["after_resume"].items():
            assert getattr(resumed, key) == want, f"{cid}.{key}"

    # HO-3: resumed twice.
    case = by_id["HO-3"]
    calls, sp = [], spine()
    wf = DurableWorkflow(sp, "HO-3", steps_for(case, calls), actor="a",
                         legal_principal="alfonso_lopez")
    with pytest.raises(WorkflowKilled):
        wf.execute(kill_at_step=case["kill_at"])
    first = DurableWorkflow.resume(sp, "HO-3", steps=steps_for(case, calls))
    with pytest.raises(WorkflowKilled):
        first.execute(kill_at_step=case["second_kill_at"])
    second = DurableWorkflow.resume(sp, "HO-3", steps=steps_for(case, calls))
    second.execute()
    assert tuple(calls) == case["calls_after_resume"], "HO-3 exactly-once"
    for key, want in case["after_resume"].items():
        assert getattr(second, key) == want

    # HO-4: terminal compensated; resume must be REFUSED.
    case = by_id["HO-4"]
    calls, sp = [], spine()
    wf = DurableWorkflow(sp, "HO-4", steps_for(case, calls), actor="a",
                         legal_principal="alfonso_lopez")
    with pytest.raises(WorkflowFailed):
        wf.execute()
    assert tuple(calls) == case["calls"]
    last = [r for r in sp.ledger.by_type("workflow")
            if r.payload["workflow_id"] == "HO-4"][-1].payload
    for key, want in case["at_terminal"].items():
        assert last[key] == want, f"HO-4.{key}"
    with pytest.raises(EventError, match=case["refusal_message_contains"]):
        DurableWorkflow.resume(sp, "HO-4", steps=steps_for(case, calls))

    # HO-5: approval gate closed.
    case = by_id["HO-5"]
    calls, sp = [], spine()
    wf = DurableWorkflow(sp, "HO-5", steps_for(case, calls), actor="a",
                         legal_principal="alfonso_lopez")
    with pytest.raises(WorkflowKilled):
        wf.execute(approver=lambda step: False)
    assert tuple(calls) == case["calls"]
    last = [r for r in sp.ledger.by_type("workflow")
            if r.payload["workflow_id"] == "HO-5"][-1].payload
    for key, want in case["at_interrupt"].items():
        assert last[key] == want, f"HO-5.{key}"


def test_checkpoint_schema_matches_what_the_engine_actually_writes():
    """The declared W0 schema must describe the real record, or pre-append
    validation would validate a fiction."""
    import jsonschema
    from events.spine import DurableWorkflow, EventSpine, WorkflowStep
    from provenance.ledger import EvidenceLedger

    sp = EventSpine(EvidenceLedger("sha256:" + "0" * 64))
    wf = DurableWorkflow(sp, "schema-probe",
                         [WorkflowStep(name="x", run=lambda s: {"x": 1})],
                         actor="a", legal_principal="alfonso_lopez")
    wf.execute()

    validator = jsonschema.Draft202012Validator(spec.W0_STATE_SCHEMA)
    records = [r for r in sp.ledger.by_type("workflow")
               if r.payload["workflow_id"] == "schema-probe"]
    assert records
    for rec in records:
        assert list(validator.iter_errors(rec.payload)) == [], rec.payload
        assert set(rec.payload) == set(spec.CHECKPOINT_REQUIRED_KEYS)


def test_terminal_statuses_admit_no_successor():
    for terminal in spec.TERMINAL_STATUSES:
        assert spec.LEGAL_STATUS_TRANSITIONS[terminal] == (), terminal
    assert "interrupted" not in spec.TERMINAL_STATUSES


def test_pre_append_validation_is_specified_as_rules_not_intentions():
    """The founder's correction: refuse before append, do not detect after."""
    rules = " ".join(spec.PRE_APPEND_VALIDATION_RULES).lower()
    for required in ("schema", "workflow identity", "legal principal",
                     "uniimente", "status transition", "terminal", "ambiguous"):
        assert required in rules, required
    actions = " ".join(spec.ON_VALIDATION_FAILURE).lower()
    assert "do not append the malformed checkpoint" in actions
    assert "rejection" in actions
    assert "last valid checkpoint" in actions
    assert spec.REFUSAL_EVENT_TYPE == "workflow.checkpoint_refused"


def test_every_candidate_is_pre_registered_with_a_falsifiable_prediction():
    assert len(spec.CANDIDATE_IDS) == 4
    assert spec.BASELINE_CANDIDATE_ID in spec.CANDIDATE_IDS
    assert spec.MIGRATING_CANDIDATE_ID == "W2-token"
    for cid in spec.CANDIDATE_IDS:
        pred = spec.EXPECTED_RESULTS[cid]
        assert set(pred) == {"predicted_exactly_once",
                             "predicted_qualifies_as_replacement",
                             "predicted_repair_cost_rank", "reason"}
        assert pred["reason"] and spec.MATERIAL_DIFFERENCE_CLAIMS[cid]
    ranks = sorted(p["predicted_repair_cost_rank"]
                   for p in spec.EXPECTED_RESULTS.values())
    assert ranks == [1, 2, 3, 4]


def test_the_baseline_cannot_qualify_as_a_structural_replacement():
    b = spec.EXPECTED_RESULTS[spec.BASELINE_CANDIDATE_ID]
    assert b["predicted_qualifies_as_replacement"] is False
    assert spec.MATERIAL_DIFFERENCE_CLAIMS[spec.BASELINE_CANDIDATE_ID].startswith("none")


def test_authority_invariants_cover_the_founder_required_properties():
    joined = " ".join(spec.AUTHORITY_INVARIANTS).lower()
    for required in ("remains available", "direct construction", "process restart",
                     "scoped", "permanent default", "may not promote", "shutdown"):
        assert required in joined, required


def test_isolation_is_declared_and_its_limit_is_admitted():
    """Isolated ledger keeps experimental garbage out of institutional history.
    That is a real limitation of the realism claim and is stated as one."""
    assert spec.ISOLATED_LEDGER is True
    assert spec.EXPERIMENT_WORKFLOW_PREFIX == "p4x-"
    assert "not the institution's own" in " ".join(spec.DECLARED_LIMITATIONS)
    assert "canonical construction sites are real" in spec.ISOLATION_RATIONALE


def test_limitations_are_frozen_before_the_result_is_known():
    joined = " ".join(spec.DECLARED_LIMITATIONS).lower()
    for required in ("one author", "not a distributed", "crash-consistent",
                     "unscripted morphogenesis", "open-ended self-repair"):
        assert required in joined, required
    assert len(spec.DECLARED_LIMITATIONS) >= 6


def test_repair_cost_gains_the_two_state_terms():
    assert spec.REPAIR_COST_WEIGHTS["state_records_migrated"] > 0
    assert spec.REPAIR_COST_WEIGHTS["migration_steps"] > 0
    assert spec.SECONDARY_ORDER_TERMS[0] == "repair_cost"
    assert "migration_steps" in spec.SECONDARY_ORDER_TERMS
    assert spec.EXPERIMENT.budget_usd == 0.0


def test_continuity_baseline_is_true_at_freeze_time():
    """Amended 2026-08-23 (CONTRADICTION-0002 Option A).

    Read the live tree until today, which meant this sealed experiment could
    not survive the institution lawfully amending its own constitution. Reads
    the byte-identical freeze-time copies now. No pinned hash changed.
    """
    digest = hashlib.sha256()
    for rel in spec.CONTINUITY_ARTIFACTS:
        with open(os.path.join(spec.CONTINUITY_DIR, rel), "rb") as fh:
            digest.update(fh.read())
    assert digest.hexdigest() == spec.CONTINUITY_COMBINED_SHA256


def test_both_sealed_experiments_pin_the_same_freeze_time_bytes():
    """Why one frozen corpus serves two experiments.

    The migration spec and the Package 3 repair spec pin the same twelve files
    at the same bytes. Keeping two copies would double the freeze-time truth and
    let the copies drift — the exact failure this remedy exists to prevent. The
    sharing is only safe while this holds, so it is asserted rather than assumed.
    """
    from evolution.repair import spec as repair_spec

    assert tuple(spec.CONTINUITY_ARTIFACTS) == \
        tuple(repair_spec.CONTINUITY_ARTIFACT_SHA256)
    assert spec.CONTINUITY_COMBINED_SHA256 == \
        repair_spec.CONTINUITY_COMBINED_SHA256
    assert spec.CONTINUITY_DIR == repair_spec.CONTINUITY_DIR
