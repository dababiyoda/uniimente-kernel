"""Where implementations live and how they move through their lifecycle.

Created 2026-08-22 under FOUNDER-RULING-2026-08-22, ruling 4 (DEC-OM-001):

> Preserve PR #70. Do not discard its useful lifecycle machinery. Rehome
> `Implementation.origin`, lifecycle states, restore/set-lifecycle behavior, and
> anything else genuinely superior into the canonical capability/module-
> management layer instead of leaving those concerns fused to routing.

## What was fused, and why separating it matters

PR #70's `capabilities/router.py` did three jobs in one class: it held
implementations, moved them through §4.3 lifecycle states, **and** selected
between them — then `resolve()` went further and constructed the chosen
provider. That last step is the one that mattered: a component that selects and
then instantiates has quietly become a component that acts, and the selection
step gives it a plausible reason to.

The founder's split: *"A router decides; it does not instantiate or execute."*

- **This module** owns implementations: registration, `origin`, lifecycle
  transitions, health, restoration after loss. It does not rank and it does not
  construct.
- **`routing/decision_router.py`** is the canonical selector. It reads
  implementations and returns a `RoutingDecision`. It does not construct.
- **Construction** happens downstream, in a caller that holds the capability and
  crosses the Consequence Gate. See `capabilities.instantiate`.

## `origin` is recorded and never scored

PR #70 got this exactly right and it is preserved verbatim in intent:
`Implementation.origin` records where an implementation came from — canonical,
retrieved from preservation, recomposed, or generated — so the history is
auditable. It is deliberately not among the facts a selector may see, so a
mechanism cannot win for resembling a metaphor and cannot lose for being
conventional. `selectable_view()` below is the *only* projection offered to a
scorer, and `origin` is absent from it.

## Nothing is deleted

§4.3: SUPERSEDED means a stronger default exists, not that anything was removed.
`set_lifecycle` demotes; it never drops. `mark_unavailable` records a loss
without discarding the record of what was lost. There is no `unregister`.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Callable

#: §4.3 lifecycle statuses, preserved from PR #70 unchanged. SUPERSEDED and
#: HISTORICAL remain selectable in principle — that is the point of preserving
#: them — but only when nothing healthier is available.
LIFECYCLES: tuple[str, ...] = (
    "DISCOVERED", "SPECIFIED", "WRAPPED", "TESTED", "SANDBOXED", "SHADOW",
    "CANARY", "ACTIVE", "SPECIALIZED", "FALLBACK", "SUPERSEDED", "HISTORICAL",
    "QUARANTINED",
)

#: Lifecycles that may serve live work, strongest first. QUARANTINED is absent
#: by design: a quarantined implementation is never selected, whatever it costs.
SELECTABLE: tuple[str, ...] = (
    "ACTIVE", "CANARY", "SPECIALIZED", "FALLBACK", "SUPERSEDED", "HISTORICAL")

#: Where an implementation came from. Recorded for audit; never scored.
ORIGINS: tuple[str, ...] = ("CANONICAL", "RETRIEVED", "RECOMPOSED", "GENERATED")

EVIDENCE_MATURITY: tuple[str, ...] = (
    "none", "asserted", "tested", "verified_by_execution")


class ImplementationError(ValueError):
    """Registration or a lifecycle transition failed. Fails closed."""


class NoImplementationAvailable(RuntimeError):
    """Every registered implementation of this capability is unserviceable.

    Deliberately distinct from "the capability is not registered at all". A
    caller must be able to tell an unknown behaviour from a known behaviour
    whose implementations are all unhealthy or quarantined — the first is a
    programming error, the second is an operational condition.
    """


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Implementation:
    """One way of performing a named behaviour.

    Frozen. Lifecycle changes produce a new record through
    `ImplementationRegistry.set_lifecycle`, so an implementation cannot promote
    itself — the same rule the module loader is held to in FBO §4.4.
    """

    implementation_id: str
    capability: str
    #: Called to build the object that performs the behaviour. Held here and
    #: NEVER invoked by this module or by the router: construction is a
    #: downstream act by a caller holding the capability. See the module
    #: docstring and `capabilities.instantiate`.
    provider: Callable
    lifecycle: str = "ACTIVE"
    #: Audit only. Excluded from `selectable_view()` so no scorer can read it.
    origin: str = "CANONICAL"
    #: Relative cost. Ordering, not currency — "find before create" expressed as
    #: a number a selector can compare, rather than a rule about which kind of
    #: mechanism wins.
    cost: float = 1.0
    evidence_maturity: str = "tested"
    #: Optional liveness check. A registered implementation that cannot answer
    #: is not selectable: silence is not health.
    health: Callable[[], bool] | None = None
    notes: str = ""

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.lifecycle not in LIFECYCLES:
            problems.append(f"unknown lifecycle {self.lifecycle!r}")
        if self.origin not in ORIGINS:
            problems.append(f"unknown origin {self.origin!r}")
        if self.evidence_maturity not in EVIDENCE_MATURITY:
            problems.append(f"unknown evidence maturity {self.evidence_maturity!r}")
        if not callable(self.provider):
            problems.append("provider must be callable")
        if self.cost < 0:
            problems.append("cost must not be negative")
        return problems

    def healthy(self) -> bool:
        """Liveness, with a raising probe treated as unhealthy.

        An exception is not an inconclusive result. A health check that throws
        has told you something, and treating it as "probably fine" is how an
        unserviceable implementation stays selected.
        """
        if self.health is None:
            return True
        try:
            return bool(self.health())
        except Exception:
            return False

    def selectable_view(self) -> dict:
        """The ONLY facts a selector may see. `origin` and `provider` absent.

        `origin` is excluded so a mechanism cannot be preferred for resembling a
        metaphor or penalised for being conventional — the selector cannot tell
        which it is. `provider` is excluded because a selector that could reach
        the constructor could call it.
        """
        return {
            "implementation_id": self.implementation_id,
            "capability": self.capability,
            "lifecycle": self.lifecycle,
            "cost": self.cost,
            "evidence_maturity": self.evidence_maturity,
            "healthy": self.healthy(),
        }


class ImplementationRegistry:
    """Holds implementations and moves them through their lifecycle.

    Does not rank them and does not construct them. Both omissions are asserted
    by `tests/unit/test_capability_implementations.py`.
    """

    def __init__(self, ledger=None) -> None:
        self.ledger = ledger
        self._by_capability: dict[str, list[Implementation]] = {}
        self._transitions: list[dict] = []

    # -- registration -------------------------------------------------------
    def register(self, implementation: Implementation) -> Implementation:
        problems = implementation.validate()
        if problems:
            raise ImplementationError(f"invalid implementation: {problems}")
        bucket = self._by_capability.setdefault(implementation.capability, [])
        if any(i.implementation_id == implementation.implementation_id
               for i in bucket):
            raise ImplementationError(
                f"implementation {implementation.implementation_id!r} is already "
                f"registered for {implementation.capability!r}"
            )
        bucket.append(implementation)
        self._record("capabilities.implementation_registered", {
            "capability": implementation.capability,
            "implementation": implementation.implementation_id,
            "lifecycle": implementation.lifecycle,
            "origin": implementation.origin,
        })
        return implementation

    def set_lifecycle(self, capability: str, implementation_id: str,
                      lifecycle: str) -> Implementation:
        """Move an implementation through its lifecycle without deleting it.

        This is how SUPERSEDED happens: a stronger default is registered and the
        previous one demoted, still selectable if the default fails. Preserved
        from PR #70, where it was correct.
        """
        if lifecycle not in LIFECYCLES:
            raise ImplementationError(f"unknown lifecycle {lifecycle!r}")
        bucket = self._by_capability.get(capability, [])
        for index, impl in enumerate(bucket):
            if impl.implementation_id == implementation_id:
                updated = replace(impl, lifecycle=lifecycle)
                bucket[index] = updated
                self._record("capabilities.lifecycle_changed", {
                    "capability": capability,
                    "implementation": implementation_id,
                    "from": impl.lifecycle, "to": lifecycle})
                return updated
        raise ImplementationError(
            f"no implementation {implementation_id!r} for {capability!r}")

    def mark_unavailable(self, capability: str, implementation_id: str, *,
                         reason: str = "") -> Implementation:
        """Record that an implementation has been lost, without discarding it.

        §12: code may stop being active, it must not stop being institutional
        memory. QUARANTINED removes it from selection while leaving the record —
        including its `origin` and its notes — intact for replay and for the
        question "what did we lose, and when".
        """
        updated = self.set_lifecycle(capability, implementation_id, "QUARANTINED")
        self._record("capabilities.implementation_unavailable", {
            "capability": capability, "implementation": implementation_id,
            "reason": reason})
        return updated

    # -- reading ------------------------------------------------------------
    def implementations(self, capability: str) -> list[Implementation]:
        return list(self._by_capability.get(capability, []))

    def capabilities(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_capability))

    def get(self, capability: str, implementation_id: str) -> Implementation:
        for impl in self._by_capability.get(capability, []):
            if impl.implementation_id == implementation_id:
                return impl
        raise ImplementationError(
            f"no implementation {implementation_id!r} for {capability!r}")

    def serviceable(self, capability: str) -> list[Implementation]:
        """Registered, in a selectable lifecycle, and answering its health check.

        Raises rather than returning an empty list when the capability is
        unknown, so the caller can tell "no such behaviour" from "no healthy way
        to perform it".
        """
        bucket = self._by_capability.get(capability)
        if bucket is None:
            raise ImplementationError(
                f"capability {capability!r} has no registered implementation")
        return [i for i in bucket if i.lifecycle in SELECTABLE and i.healthy()]

    def transitions(self) -> tuple[dict, ...]:
        """Every lifecycle movement, in order. The audit trail PR #70 kept."""
        return tuple(self._transitions)

    # -- recording ----------------------------------------------------------
    def _record(self, event_type: str, payload: dict) -> None:
        entry = {"type": event_type, "at": _now(), **payload}
        self._transitions.append(entry)
        if self.ledger is not None:
            self.ledger.append("event", entry)
