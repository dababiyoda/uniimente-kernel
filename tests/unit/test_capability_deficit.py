"""A deficit must be verified before anything reconfigures itself.

Founder clarification 2026-09-09: `morphogenesis` means capability formation or
reconfiguration after a **verified** CapabilityDeficit. These are the checks
that make "verified" mean something.
"""
from __future__ import annotations

from capabilities.deficit import RESOLUTION_LADDER, CapabilityDeficit, verify_against_router
from capabilities.router import ORIGINS, CapabilityRouter, Implementation

CAP = "test.capability"


def _router(lifecycle="ACTIVE"):
    r = CapabilityRouter()
    r.register(Implementation("impl", CAP, lambda: "served", lifecycle=lifecycle))
    return r


def test_an_asserted_deficit_authorises_nothing():
    """Three facts required. A bare claim is not one of them."""
    bare = CapabilityDeficit(CAP)
    assert bare.status == "UNVERIFIED"
    assert not bare.morphogenesis_authorized()
    assert len(bare.missing_evidence()) == 3


def test_each_missing_fact_blocks_on_its_own():
    full = dict(required_by="mission-1", failed_invocation="deliver()",
                failure_error="boom", unserviceable_reason="nothing serviceable")
    assert CapabilityDeficit(CAP, **full).morphogenesis_authorized()
    for drop in full:
        partial = {k: v for k, v in full.items() if k != drop}
        assert not CapabilityDeficit(CAP, **partial).morphogenesis_authorized(), drop


def test_a_healthy_implementation_means_the_capability_is_not_missing():
    """The anti-twitch control.

    Something failed, but the capability is still serviceable — so the failure
    is not a deficit and reconfiguring would treat a symptom.
    """
    deficit = verify_against_router(
        CAP, required_by="mission-1", failed_invocation="deliver()",
        failure_error="boom", router=_router())
    assert deficit.status == "UNVERIFIED"
    assert not deficit.morphogenesis_authorized()


def test_an_unserviceable_capability_verifies():
    deficit = verify_against_router(
        CAP, required_by="mission-1", failed_invocation="deliver()",
        failure_error="boom", router=_router(lifecycle="QUARANTINED"))
    assert deficit.status == "VERIFIED"
    assert "impl" in deficit.examined


def test_verification_cannot_be_overridden():
    """No force flag exists. A bypass would make the precondition decorative."""
    import inspect

    sig = inspect.signature(CapabilityDeficit.morphogenesis_authorized)
    assert list(sig.parameters) == ["self"]


def test_every_rung_of_the_ladder_has_an_origin_the_router_can_name():
    """An enum that cannot name an option cannot route to it."""
    expected = {
        "EXISTING_CAPABILITY": {"CANONICAL", "RETRIEVED"},
        "CONVENTIONAL_WORKFLOW": {"CONVENTIONAL"},
        "COMMODITY_OR_EXTERNAL": {"ACQUIRED"},
        "MECHANISM_RECOMBINATION": {"RECOMPOSED"},
        "NEW_ARCHITECTURE": {"GENERATED"},
    }
    assert set(expected) == set(RESOLUTION_LADDER)
    for rung, origins in expected.items():
        assert origins <= set(ORIGINS), f"{rung} has no routable origin"
    assert ORIGINS.index("ACQUIRED") < ORIGINS.index("GENERATED"), (
        "buying before building must be expressible as cheaper"
    )
