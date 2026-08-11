"""§4.14 router — the three properties that would actually break if regressed.

Deliberately short. The router's value is that origin cannot buy a selection,
that losing an implementation does not delete it, and that a frozen evaluator
notices drift. Everything else is exercised by the live episode.
"""
from __future__ import annotations

import pytest

from capabilities.router import (
    CapabilityRouter,
    Implementation,
    NoImplementationAvailable,
    RouterError,
)

CAP = "test.behaviour"


def _impl(ident, **kw):
    return Implementation(implementation_id=ident, capability=CAP,
                          provider=lambda: ident, **kw)


def test_origin_cannot_influence_selection():
    """The founder's correction, made structural rather than editorial.

    Two implementations identical in every scored dimension, differing only in
    where they came from. Whichever is registered first must win, because the
    scorer cannot see origin at all — a generated mechanism gets no head start
    for sounding advanced, and a retrieved one none for being conventional.
    """
    for first, second in (("GENERATED", "RETRIEVED"), ("RETRIEVED", "GENERATED")):
        router = CapabilityRouter()
        router.register(_impl("a", origin=first, cost=1.0, evidence_maturity="tested"))
        router.register(_impl("b", origin=second, cost=1.0, evidence_maturity="tested"))
        chosen, _ = router.select(CAP)
        assert chosen.implementation_id == "a", (
            f"origin changed the outcome: {first} vs {second}"
        )


def test_cheaper_and_better_evidenced_wins():
    """Non-vacuity: the scorer must actually discriminate on what it can see."""
    router = CapabilityRouter()
    router.register(_impl("expensive", cost=9.0, evidence_maturity="verified_by_execution"))
    router.register(_impl("cheap", cost=1.0, evidence_maturity="verified_by_execution"))
    assert router.select(CAP)[0].implementation_id == "cheap"


def test_restoration_finds_a_replacement_without_deleting_the_lost_one():
    """§12: losing a function quarantines an implementation, never removes it."""
    router = CapabilityRouter()
    router.register(_impl("canonical", lifecycle="ACTIVE", origin="CANONICAL"))
    router.register(_impl("preserved", lifecycle="FALLBACK", origin="RETRIEVED"))

    replacement, decision = router.restore(CAP, unavailable="canonical")

    assert replacement.implementation_id == "preserved"
    assert decision.origin_of_chosen == "RETRIEVED"
    survivors = {i.implementation_id: i.lifecycle for i in router.implementations(CAP)}
    assert survivors["canonical"] == "QUARANTINED", "the lost implementation was deleted"


def test_a_capability_with_nothing_serviceable_raises_rather_than_returning_empty():
    router = CapabilityRouter()
    router.register(_impl("only", lifecycle="QUARANTINED"))
    with pytest.raises(NoImplementationAvailable):
        router.select(CAP)
    with pytest.raises(NoImplementationAvailable):
        router.select("never.registered")


def test_the_router_grants_no_authority():
    router = CapabilityRouter()
    router.register(_impl("a"))
    router.select(CAP)
    assert router.describe()["authority_granted"] is False
    assert all(d["authority_granted"] is False for d in router.describe()["decisions"])


def test_duplicate_registration_is_refused():
    router = CapabilityRouter()
    router.register(_impl("a"))
    with pytest.raises(RouterError):
        router.register(_impl("a"))


# --- evaluator freeze --------------------------------------------------------

def test_the_evaluator_is_frozen_and_unchanged():
    from runtime.evaluator import freeze

    status, detail = freeze.verify()
    assert status == "FROZEN_AND_UNCHANGED", f"evaluator drifted: {detail}"


def test_the_freeze_detects_drift():
    """Negative control. A hash guard never observed to fail cannot fail."""
    from runtime.evaluator import freeze

    original = dict(freeze.FROZEN_DIGESTS)
    try:
        freeze.FROZEN_DIGESTS["isolation.py"] = "0" * 64
        assert freeze.verify()[0] == "DRIFTED"
        freeze.FROZEN_DIGESTS.clear()
        assert freeze.verify()[0] == "NOT_FROZEN", "empty must not read as agreement"
    finally:
        freeze.FROZEN_DIGESTS.clear()
        freeze.FROZEN_DIGESTS.update(original)
