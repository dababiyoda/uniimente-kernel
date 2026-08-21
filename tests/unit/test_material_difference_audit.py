"""Adversarial audit of the Gate E/F material-difference predicate.

PRESERVED, NOT FIXED. These tests document what the current predicate actually
measures, including where it is wrong. `regeneration.FunctionRegistry` is left
untouched so PR #57 and PR #58 remain exactly as reported.

Finding: the predicate measures ATTRIBUTE DISTANCE across seven named
dimensions. It has no concept of why the predecessor failed, so it cannot
distinguish "escaped the cause" from "looks different".
"""
from __future__ import annotations

from regeneration import FunctionRegistry as FR

BASE = {"capabilities": ["ingest.a", "decide.a", "emit.a"],
        "control_topology": "pipeline", "communication": "direct",
        "verification": "readback", "memory_distribution": "central",
        "resource_allocation": "static", "recovery_behaviour": "restart"}


def test_audit_measures_attributes_not_causal_structure():
    """It compares 7 named keys. No key describes a failure mode."""
    assert set(FR.MATERIAL_DIMENSIONS) == {
        "capabilities", "control_topology", "communication", "verification",
        "memory_distribution", "resource_allocation", "recovery_behaviour"}
    for d in FR.MATERIAL_DIMENSIONS:
        assert "fail" not in d and "cause" not in d and "redundan" not in d


def test_audit_true_positive_renaming_is_correctly_ignored():
    """The one thing it gets right: reordering/renaming is not difference."""
    b = dict(BASE, capabilities=list(reversed(BASE["capabilities"])))
    assert FR.material_difference(BASE, b) == set()


# ---------------------------------------------------------------- FALSE ACCEPTS

def test_audit_false_accept_different_graph_same_single_point_of_failure():
    """DEFECT. Both forms have exactly one verifier and no redundancy.

    The causal vulnerability that killed the predecessor is reproduced
    identically, yet the predicate reports 3 differences and admits it.
    """
    successor = dict(BASE,
                     capabilities=["ingest.b", "decide.b", "emit.b"],
                     resource_allocation="elastic",
                     recovery_behaviour="reassign")
    diff = FR.material_difference(BASE, successor)
    assert len(diff) >= 2                     # admitted
    # ...yet both are a single unredundant chain:
    assert BASE["control_topology"] == successor["control_topology"] == "pipeline"
    assert BASE["verification"] == successor["verification"] == "readback"


def test_audit_false_accept_decorative_capability_plus_cosmetic_flip():
    """DEFECT. Adding one unused capability + flipping one label = 2 dims."""
    successor = dict(BASE,
                     capabilities=BASE["capabilities"] + ["telemetry.noop"],
                     resource_allocation="elastic")
    assert len(FR.material_difference(BASE, successor)) == 2      # admitted
    # The functional chain is byte-identical.
    assert set(BASE["capabilities"]) <= set(successor["capabilities"])


# ---------------------------------------------------------------- FALSE REFUSALS

def test_audit_false_refusal_when_the_old_form_is_still_the_right_answer():
    """DEFECT. Damage elsewhere; the predecessor form remains viable and
    cheapest. The predicate refuses it purely for being the same."""
    assert len(FR.material_difference(BASE, dict(BASE))) == 0     # refused


def test_audit_false_refusal_of_a_genuine_causal_fix_that_looks_similar():
    """DEFECT. Adding redundancy to the single verifier removes the actual
    vulnerability but touches only ONE dimension, so it is refused."""
    fixed = dict(BASE, verification="checksum_quorum")
    diff = FR.material_difference(BASE, fixed)
    assert diff == {"verification"}
    assert len(diff) < 2                       # refused, though it fixed the cause


def test_audit_threshold_is_a_default_argument_not_a_registered_hypothesis():
    """The threshold of 2 was a default parameter, not pre-registered."""
    import inspect
    sig = inspect.signature(FR.admit)
    assert sig.parameters["minimum_material_difference"].default == 2
