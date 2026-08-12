"""Discovery does not grant access. Everything else here is secondary."""
from __future__ import annotations

import os

import pytest

from closure.nervous_system_registry import package_imports
from discovery.service import (
    CONSEQUENCE_ORDER,
    CapabilityDiscoveryService,
    DiscoveryError,
    DiscoveryQuery,
)

KERNEL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="module")
def directory() -> CapabilityDiscoveryService:
    return CapabilityDiscoveryService()


# ------------------------------------------------------------------ the rule
def test_discovery_grants_no_access(directory):
    """FBO §4.10: 'Discovery does not grant access.' Enforced, not promised."""
    # 1. No method on the service issues, mints, approves or authorizes.
    forbidden = ("grant", "authorize", "approve", "issue", "execute", "mint")
    surface = [n for n in dir(directory) if not n.startswith("_")]
    offenders = [n for n in surface if any(f in n.lower() for f in forbidden)]
    assert offenders == [], f"discovery exposes action-shaped methods: {offenders}"

    # 2. No advertisement carries a grant.
    ad = directory.capabilities[0]
    assert ad.grants is None

    # 3. The directory has issued none and has no way to.
    assert directory.directory()["grants_issued"] == 0

    # 4. Structurally: nothing in the package imports the gate or policy engine.
    imports = package_imports("discovery")
    assert not any(i.startswith("policy") for i in imports), (
        f"discovery imports authority machinery: {sorted(imports)}"
    )


def test_reporting_a_ceiling_is_not_conferring_it(directory):
    ad = directory.lookup("kernel.consequence_gate")
    assert ad.within("read_only") is True
    # `within` answers a question. It hands back no object that permits anything.
    assert ad.within("read_only") is not ad
    assert ad.requires_kernel_gate is True


# ---------------------------------------------------------------- fail closed
def test_unknown_capability_and_organ_are_refused_never_approximated(directory):
    with pytest.raises(DiscoveryError):
        directory.lookup("kernel.does_not_exist")
    with pytest.raises(DiscoveryError):
        directory.organ("spiffe://uniimente.internal/organ/nowhere")


def test_unknown_consequence_class_is_refused(directory):
    with pytest.raises(DiscoveryError):
        directory.offers(DiscoveryQuery(max_consequence_class="godmode"))
    with pytest.raises(DiscoveryError):
        directory.lookup("kernel.consequence_gate").within("godmode")


def test_a_directory_over_an_invalid_source_refuses_to_exist():
    """A partial view of the organism is worse than no view."""
    with pytest.raises(DiscoveryError):
        CapabilityDiscoveryService(organs_dir=os.path.join(KERNEL_ROOT, "contracts"))


def test_duplicate_capability_ids_are_refused():
    from linker.manifest import load_all
    manifests = load_all()
    doubled = list(manifests) + [manifests[0]]
    with pytest.raises(DiscoveryError, match="more than one organ"):
        CapabilityDiscoveryService(manifests=doubled)


# ------------------------------------------------------------------- content
def test_exactly_five_manifests_exist_not_six(directory):
    """Arithmetic, stated so it cannot drift into a slogan.

    `main` carries three manifests. PumpStation and RESEARCH-IN make five. There
    is no sixth manifest, and any claim of "all six organs resolve" is false.
    """
    names = {o.name for o in directory.organs}
    assert names == {"uniimente-kernel", "DALEOBANKS", "WealthMachineIntelligence",
                     "pumpstation", "research-in"}
    assert len(directory.organs) == 5


def test_a_manifest_is_discovery_only_and_is_not_identity_registration(directory):
    """Two registers, neither a subset of the other. Both states are reported."""
    rec = directory.identity_reconciliation()

    assert rec["identity_registered"] == 8
    assert rec["manifests_published"] == 5
    assert len(rec["both"]) == 3

    # Registered but invisible to the linker.
    unmanifested = {e["name"] for e in rec["registered_without_manifest"]}
    assert {"railscout", "ivio_nemt", "personal_command",
            "adversarial_intelligence", "portfolio_governor"} == unmanifested

    # Visible to the linker but not constitutionally recognized.
    unregistered = {e["name"] for e in rec["manifested_without_identity_registration"]}
    assert unregistered == {"pumpstation", "research-in"}, (
        "publishing a manifest must not be mistaken for registering an identity"
    )

    assert "does not imply registered" in rec["note"]


def test_the_two_new_organs_are_planned_and_carry_the_status_contradiction(directory):
    for name in ("pumpstation", "research-in"):
        organ = next(o for o in directory.organs if o.name == name)
        assert organ.status == "planned"
        assert any("STATUS VOCABULARY CONTRADICTION" in u for u in organ.unresolved), (
            f"{name} silently accepted a status that misdescribes it"
        )


def test_unattached_organs_are_excluded_from_offers_by_default(directory):
    attached = {ad.capability_id for ad in directory.offers()}
    everything = {ad.capability_id for ad in
                  directory.offers(DiscoveryQuery(include_unattached_organs=True))}
    assert "pumpstation.wallet_session" in everything
    assert "pumpstation.wallet_session" not in attached, (
        "a planned, unattached organ is being offered as if it were available"
    )


def test_no_organ_may_advertise_self_promotion(directory):
    for organ in directory.organs:
        assert organ.may_self_promote is False
        assert organ.requires_kernel_gate is True


def test_overlapping_governance_authority_is_surfaced_not_resolved(directory):
    overlaps = dict(directory.overlapping_authority())
    caps = set(overlaps.values())
    assert "daleobanks.constitution_service" in caps
    assert "wealthmachine.risk_management" in caps
    # Surfacing is all discovery does; it renders no verdict.
    assert not hasattr(directory, "resolve_authority")


def test_declared_health_is_quoted_as_declared_never_measured(directory):
    ad = directory.lookup("pumpstation.wallet_session")
    assert ad.declared_health.startswith("declared:")
    assert "npm test" in ad.declared_health


def test_offers_narrow_by_every_supplied_field(directory):
    produced = directory.offers(DiscoveryQuery(produces="outcome"))
    assert produced
    assert all("outcome" in ad.produces for ad in produced)
    assert CONSEQUENCE_ORDER[0] == "read_only"
