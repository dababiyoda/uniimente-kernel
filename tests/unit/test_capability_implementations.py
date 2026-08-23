"""Lifecycle machinery rehomed from PR #70, and the split that motivated it.

FOUNDER-RULING-2026-08-22, ruling 4 (DEC-OM-001): `routing/decision_router.py`
is the canonical selector, PR #70's lifecycle machinery is preserved rather than
discarded, and *"a router decides; it does not instantiate or execute"* — so
provider construction moves downstream to a caller holding the capability and
crossing the Consequence Gate.

The tests that matter here are the ones asserting the SPLIT, because the split
is the whole ruling. PR #70's `resolve()` was three lines that selected an
implementation and then called `chosen.provider()`; it is the most natural
method to write and the exact point where a component that recommends becomes a
component that acts.
"""
from __future__ import annotations

import ast
import os

import pytest

from capabilities.implementations import (
    EVIDENCE_MATURITY,
    LIFECYCLES,
    ORIGINS,
    SELECTABLE,
    Implementation,
    ImplementationError,
    ImplementationRegistry,
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _impl(iid="impl-a", capability="linker.resolve", **kwargs) -> Implementation:
    return Implementation(implementation_id=iid, capability=capability,
                          provider=lambda: {"built": iid}, **kwargs)


@pytest.fixture
def registry() -> ImplementationRegistry:
    return ImplementationRegistry()


# ---------------------------------------------------- the split, asserted
def test_the_registry_cannot_construct_anything():
    """No method on the registry calls a provider.

    Structural rather than behavioural: the failure this prevents is someone
    adding a convenient `resolve()` back, which no behavioural test would catch
    because the new method would work.
    """
    path = os.path.join(ROOT, "capabilities", "implementations.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "provider"]
    assert not calls, (
        "the registry calls provider(); construction belongs downstream of the "
        "Consequence Gate, in capabilities/instantiate.py"
    )


def test_the_router_cannot_construct_anything():
    path = os.path.join(ROOT, "routing", "decision_router.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr in ("provider", "resolve", "instantiate")]
    assert not calls, f"the canonical router constructs or executes: {calls}"


def test_the_selectable_view_hides_both_provider_and_origin():
    """Two exclusions, two different reasons, both load-bearing.

    `provider` is absent because a selector that could reach the constructor
    could call it. `origin` is absent because a mechanism must not win for
    resembling a metaphor nor lose for being conventional — PR #70's rule,
    preserved.
    """
    view = _impl(origin="GENERATED").selectable_view()
    assert "provider" not in view
    assert "origin" not in view
    assert set(view) == {"implementation_id", "capability", "lifecycle",
                         "cost", "evidence_maturity", "healthy"}


def test_origin_is_recorded_even_though_it_is_never_scored(registry):
    """Auditable, and unreachable by the scorer. Both, not one."""
    registry.register(_impl("gen-1", origin="GENERATED"))
    assert registry.get("linker.resolve", "gen-1").origin == "GENERATED"
    assert any(t.get("origin") == "GENERATED" for t in registry.transitions())


# ------------------------------------------------------- lifecycle machinery
def test_superseding_demotes_without_deleting(registry):
    """§4.3: SUPERSEDED means a stronger default exists, not that anything went.

    The demoted implementation stays registered and stays selectable, which is
    the entire point of preserving it — it is the fallback when the new default
    fails.
    """
    registry.register(_impl("old"))
    registry.register(_impl("new"))
    registry.set_lifecycle("linker.resolve", "old", "SUPERSEDED")

    ids = {i.implementation_id for i in registry.implementations("linker.resolve")}
    assert ids == {"old", "new"}
    assert registry.get("linker.resolve", "old").lifecycle == "SUPERSEDED"
    assert "old" in {i.implementation_id
                     for i in registry.serviceable("linker.resolve")}


def test_quarantined_implementations_are_never_serviceable(registry):
    registry.register(_impl("bad"))
    registry.mark_unavailable("linker.resolve", "bad", reason="key compromised")
    assert registry.serviceable("linker.resolve") == []
    # Still registered. §12: it stops being active, not institutional memory.
    assert registry.get("linker.resolve", "bad").lifecycle == "QUARANTINED"


def test_marking_unavailable_records_the_reason(registry):
    registry.register(_impl("bad"))
    registry.mark_unavailable("linker.resolve", "bad", reason="key compromised")
    reasons = [t.get("reason") for t in registry.transitions() if "reason" in t]
    assert "key compromised" in reasons


def test_there_is_no_way_to_unregister_an_implementation(registry):
    """Deletion is the one lifecycle transition the Build Order forbids."""
    assert not hasattr(registry, "unregister")
    assert not hasattr(registry, "remove")
    assert not hasattr(registry, "delete")


def test_an_implementation_cannot_promote_itself(registry):
    """Lifecycle lives on the registry, not on the record.

    FBO §4.4: no module may activate itself or widen its own authority. A frozen
    record with no mutator is how that is enforced rather than requested.
    """
    registry.register(_impl("a"))
    impl = registry.get("linker.resolve", "a")
    with pytest.raises(Exception):
        impl.lifecycle = "ACTIVE"  # type: ignore[misc]
    assert not hasattr(impl, "promote")
    assert not hasattr(impl, "set_lifecycle")


# ------------------------------------------------------------------ health
def test_a_health_check_that_raises_counts_as_unhealthy():
    """An exception is not an inconclusive result.

    Treating a throwing probe as "probably fine" is how an unserviceable
    implementation stays selected through an incident.
    """
    def explode() -> bool:
        raise RuntimeError("cannot reach dependency")

    impl = Implementation("x", "cap", provider=lambda: None, health=explode)
    assert impl.healthy() is False


def test_no_health_check_means_healthy_and_that_is_a_choice():
    assert _impl().healthy() is True


def test_serviceable_distinguishes_unknown_from_unserviceable(registry):
    """The distinction PR #70 got right and is preserved.

    An unknown capability is a programming error; a known capability with no
    healthy implementation is an operational condition. A caller that cannot
    tell them apart will retry the wrong one.
    """
    with pytest.raises(ImplementationError, match="no registered implementation"):
        registry.serviceable("never.registered")

    registry.register(_impl("only", health=lambda: False))
    assert registry.serviceable("linker.resolve") == []


# ------------------------------------------------------------- validation
@pytest.mark.parametrize("kwargs,expected", [
    ({"lifecycle": "INVENTED"}, "unknown lifecycle"),
    ({"origin": "SOMEWHERE"}, "unknown origin"),
    ({"evidence_maturity": "vibes"}, "unknown evidence maturity"),
    ({"cost": -1.0}, "cost must not be negative"),
])
def test_invalid_implementations_are_refused_at_registration(registry, kwargs,
                                                             expected):
    with pytest.raises(ImplementationError, match=expected):
        registry.register(_impl(**kwargs))


def test_a_non_callable_provider_is_refused(registry):
    bad = Implementation("x", "cap", provider="not callable")  # type: ignore[arg-type]
    with pytest.raises(ImplementationError, match="provider must be callable"):
        registry.register(bad)


def test_duplicate_registration_is_refused(registry):
    registry.register(_impl("a"))
    with pytest.raises(ImplementationError, match="already"):
        registry.register(_impl("a"))


def test_the_vocabularies_are_preserved_from_pr_70():
    """The ruling said preserve, and these are the values it preserved.

    Pinned because a later edit that quietly dropped QUARANTINED from LIFECYCLES
    or added it to SELECTABLE would be a security change wearing the clothes of
    a tidy-up.
    """
    assert "QUARANTINED" in LIFECYCLES
    assert "QUARANTINED" not in SELECTABLE
    assert set(SELECTABLE) <= set(LIFECYCLES)
    assert ORIGINS == ("CANONICAL", "RETRIEVED", "RECOMPOSED", "GENERATED")
    assert EVIDENCE_MATURITY[0] == "none"
    assert EVIDENCE_MATURITY[-1] == "verified_by_execution"
