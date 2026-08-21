"""The five separations, made executable.

    function identity     is not  organ identity
    organ identity        is not  workload identity
    workload identity     is not  authority
    authority             is not  obligation
    obligation continuity is not  permission inheritance

Each is a test that fails if the separation collapses.
"""
from __future__ import annotations

import pytest

from regeneration import (CandidateFormer, CapabilityPool, Deficit,
                          FunctionContract, FunctionRegistry, ObligationState,
                          RegenerationError, succeed)

FID = "function:evidence-routing"


def contract() -> FunctionContract:
    return FunctionContract(
        function_id=FID, description="route evidence to the right store",
        inputs=("evidence_packet",), valid_outputs=("routing_receipt",),
        service_level_target="99% routed within one cycle",
        evidence_required=("independent_readback",),
        consequence_ceiling="internal_write",
        failure_conditions=("no provider", "malformed output"),
        independent_verification="readback from the store, not the router",
        termination_conditions=("function withdrawn by the founder",))


PIPE = {"capabilities": ["ingest.a", "decide.a", "emit.a"],
        "control_topology": "pipeline", "communication": "direct",
        "verification": "readback", "memory_distribution": "central",
        "resource_allocation": "static", "recovery_behaviour": "restart"}


@pytest.fixture
def reg():
    r = FunctionRegistry()
    r.declare_function(contract())
    return r


def admit(r, topo=PIPE, pred=None, ratified="alfonso_lopez"):
    return r.admit(function_id=FID, topology=topo,
                   workload_identity="workload:a1", ratified_by=ratified,
                   predecessor_organ_id=pred)


# ---------------------------------------------- separation 1: function/organ

def test_function_identity_outlives_the_organ(reg):
    a = admit(reg)
    reg.retire(a.organ_id, reason="damaged")
    assert reg.function(FID).function_id == FID       # still declared
    assert reg.is_retired(a.organ_id)


def test_function_cannot_be_silently_redefined(reg):
    with pytest.raises(RegenerationError) as e:
        reg.declare_function(contract())
    assert e.value.code == "function_already_declared"


# ------------------------------------------ separation 2: organ/workload id

def test_organ_identity_and_workload_identity_are_distinct(reg):
    a = admit(reg)
    assert a.organ_id != a.workload_identity
    assert a.function_id != a.organ_id


def test_retired_organ_identity_is_never_reused(reg):
    a = admit(reg)
    reg.retire(a.organ_id, reason="damaged")
    b = admit(reg)
    assert b.organ_id != a.organ_id


# ------------------------------------------- separation 3: identity/authority

def test_successor_cannot_inherit_the_predecessors_authority_record(reg):
    a = admit(reg)
    a.authority_record_id = "auth-000123"
    alt = dict(PIPE, capabilities=["ingest.b", "decide.b", "emit.b"],
               control_topology="fan_out_vote")
    with pytest.raises(RegenerationError) as e:
        reg.admit(function_id=FID, topology=alt, workload_identity="w2",
                  ratified_by="alfonso_lopez", predecessor_organ_id=a.organ_id,
                  authority_record_id="auth-000123")
    assert e.value.code == "inherited_authority"


def test_an_organ_cannot_ratify_its_own_admission(reg):
    for who in ("UNIIMENTE", "omnimorph", "self", ""):
        with pytest.raises(RegenerationError) as e:
            admit(reg, ratified=who)
        assert e.value.code == "self_ratified_organ"


# ------------------------------------------ separation 4: authority/obligation

def test_open_obligations_block_retirement(reg):
    """Dissolving the body must not discharge the duty."""
    a = admit(reg)
    reg.incur(function_id=FID, organ_id=a.organ_id, description="reconcile batch 7")
    with pytest.raises(RegenerationError) as e:
        reg.retire(a.organ_id, reason="damaged")
    assert e.value.code == "open_obligations_block_retirement"


def test_discharge_requires_evidence(reg):
    a = admit(reg)
    ob = reg.incur(function_id=FID, organ_id=a.organ_id, description="d")
    with pytest.raises(RegenerationError) as e:
        reg.discharge(ob.obligation_id, by_organ=a.organ_id, evidence_ref="")
    assert e.value.code == "unevidenced_discharge"


# -------------------------- separation 5: obligation continuity != permission

def test_obligations_transfer_but_authority_does_not(reg):
    a = admit(reg)
    a.authority_record_id = "auth-A"
    ob = reg.incur(function_id=FID, organ_id=a.organ_id, description="settle X")

    alt = dict(PIPE, capabilities=["ingest.b", "decide.b", "emit.b"],
               control_topology="fan_out_vote", verification="dual_read")
    b = reg.admit(function_id=FID, topology=alt, workload_identity="w2",
                  ratified_by="alfonso_lopez", predecessor_organ_id=a.organ_id)

    moved = reg.transfer_obligations(function_id=FID, to_organ_id=b.organ_id)
    assert len(moved) == 1
    assert reg.obligations[ob.obligation_id].incurred_by_organ == b.organ_id
    assert a.organ_id in reg.obligations[ob.obligation_id].transfer_history
    # The duty moved. The permission did not.
    assert b.authority_record_id is None
    assert b.authority_record_id != a.authority_record_id


# ------------------------------------------------ material difference

def test_a_restart_under_a_new_name_is_refused(reg):
    """The central false success: same topology, different label."""
    a = admit(reg)
    renamed = dict(PIPE)                       # identical values
    with pytest.raises(RegenerationError) as e:
        reg.admit(function_id=FID, topology=renamed, workload_identity="w2",
                  ratified_by="alfonso_lopez", predecessor_organ_id=a.organ_id)
    assert e.value.code == "topology_not_materially_different"


def test_swapping_one_component_is_not_enough(reg):
    a = admit(reg)
    one_change = dict(PIPE, capabilities=["ingest.b", "decide.a", "emit.a"])
    with pytest.raises(RegenerationError) as e:
        reg.admit(function_id=FID, topology=one_change, workload_identity="w2",
                  ratified_by="alfonso_lopez", predecessor_organ_id=a.organ_id)
    assert e.value.code == "topology_not_materially_different"


def test_material_difference_compares_values_not_names(reg):
    a = dict(PIPE)
    b = dict(PIPE, capabilities=list(reversed(PIPE["capabilities"])))
    assert FunctionRegistry.material_difference(a, b) == set()


# ------------------------------------------------ candidate former

def test_the_former_does_not_admit_or_authorize():
    former = CandidateFormer(CapabilityPool({"ingest": ("ingest.a",)}))
    assert not hasattr(former, "admit")
    assert not hasattr(former, "issue")
    assert not hasattr(former, "authorize")


def test_the_former_never_proposes_an_unavailable_capability():
    pool = CapabilityPool({"ingest": ("ingest.a", "ingest.b"),
                           "decide": ("decide.a", "decide.b"),
                           "emit": ("emit.a", "emit.b")})
    former = CandidateFormer(pool, seed=1)
    d = Deficit(function_id=FID, unavailable_capabilities=("decide.a",),
                symptom="provider_unavailable", detected_at_episode=0)
    for c in former.form(d, PIPE):
        assert "decide.a" not in c.topology["capabilities"]


def test_the_former_returns_nothing_when_a_role_cannot_be_filled():
    pool = CapabilityPool({"ingest": ("ingest.a",), "decide": ("decide.a",)})
    former = CandidateFormer(pool)
    d = Deficit(function_id=FID, unavailable_capabilities=("decide.a",),
                symptom="gone", detected_at_episode=0)
    assert former.form(d, None) == []


def test_lineage_and_distinct_forms_are_recorded(reg):
    a = admit(reg)
    alt = dict(PIPE, capabilities=["ingest.b", "decide.b", "emit.b"],
               control_topology="fan_out_vote")
    reg.admit(function_id=FID, topology=alt, workload_identity="w2",
              ratified_by="alfonso_lopez", predecessor_organ_id=a.organ_id)
    lin = reg.function_lineage(FID)
    assert len(lin) == 2
    assert lin[1]["predecessor"] == a.organ_id
    assert reg.distinct_forms(FID) == 2
