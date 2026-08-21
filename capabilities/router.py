"""§4.14 — the Capability Router. The venue where implementations compete.

`GenomeRegistry` holds capability *specifications*. Nothing in the kernel held
capability *implementations*, so nothing could choose between them: a grep for
`FALLBACK`/`SUPERSEDED`/`CANARY` across non-test kernel code returned nothing,
and `SPECIALIZED` appeared only as a manifest field the linker reads. §9 says
preserve competing implementations and route work according to context; §4.3
says SUPERSEDED means a stronger default exists, not deletion. Neither was
executable. This is that machinery.

**The founder's mechanism-neutrality rule, expressed as code rather than as a
comment.** `Implementation.origin` records where an implementation came from —
canonical, retrieved from preservation, recomposed, or generated. It is written
to every routing decision so the history is auditable. It is **not reachable by
the scorer**: `_candidate_view()` strips it before scoring, so a mechanism
cannot win for resembling a metaphor, and cannot lose for being boring. Cost,
health and evidence maturity decide. `test_origin_cannot_influence_selection`
fails the build if that ever stops being true.

The router grants no authority. It chooses which of several already-registered
implementations performs a named behavior, records why, and never widens what
that behavior is permitted to do.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Callable

#: §4.3 lifecycle statuses. SUPERSEDED and HISTORICAL remain selectable in
#: principle — that is the whole point of preserving them — but only when
#: nothing healthier is available.
LIFECYCLES = (
    "DISCOVERED", "SPECIFIED", "WRAPPED", "TESTED", "SANDBOXED", "SHADOW",
    "CANARY", "ACTIVE", "SPECIALIZED", "FALLBACK", "SUPERSEDED", "HISTORICAL",
    "QUARANTINED",
)

#: Lifecycles that may serve live work, cheapest-first. QUARANTINED is absent
#: by design: a quarantined implementation is never selected, whatever it costs.
SELECTABLE = ("ACTIVE", "CANARY", "SPECIALIZED", "FALLBACK", "SUPERSEDED", "HISTORICAL")

#: Where an implementation came from. Recorded for audit; never scored.
ORIGINS = ("CANONICAL", "RETRIEVED", "RECOMPOSED", "GENERATED")

EVIDENCE_MATURITY = ("none", "asserted", "tested", "verified_by_execution")


class RouterError(ValueError):
    """Registration or selection failed. Fails closed."""


class NoImplementationAvailable(RuntimeError):
    """No registered implementation of this capability can serve.

    Distinct from "the capability is not registered at all": the caller must be
    able to tell an unknown behavior from a known behavior whose every
    implementation is unhealthy or quarantined.
    """


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Implementation:
    """One way of performing a named behavior."""

    implementation_id: str
    capability: str
    provider: Callable          # () -> the object performing the behavior
    lifecycle: str = "ACTIVE"
    origin: str = "CANONICAL"
    #: Relative cost of using this implementation. Ordering, not currency —
    #: "find before create" is expressed here, as a number the router can
    #: compare, rather than as a rule about which kind of mechanism wins.
    cost: float = 1.0
    evidence_maturity: str = "tested"
    #: Optional liveness check. A registered implementation that cannot answer
    #: is not selectable; silence is not health.
    health: Callable[[], bool] | None = None
    notes: str = ""

    def validate(self) -> list[str]:
        problems = []
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
        if self.health is None:
            return True
        try:
            return bool(self.health())
        except Exception:
            return False


@dataclass(frozen=True)
class RoutingDecision:
    """Why this implementation was chosen. §4.14 requires decisions be recorded
    so they can later be compared with outcomes."""

    capability: str
    chosen: str | None
    reason: str
    considered: tuple[str, ...] = ()
    rejected: tuple[tuple[str, str], ...] = ()      # (implementation_id, why)
    origin_of_chosen: str | None = None
    at: str = field(default_factory=_now)

    def describe(self) -> dict:
        return {
            "capability": self.capability,
            "chosen": self.chosen,
            "origin_of_chosen": self.origin_of_chosen,
            "reason": self.reason,
            "considered": list(self.considered),
            "rejected": [{"implementation": i, "why": w} for i, w in self.rejected],
            "at": self.at,
            "authority_granted": False,
        }


class CapabilityRouter:
    """Selects among registered implementations of a named behavior."""

    def __init__(self, ledger=None) -> None:
        self.ledger = ledger
        self._implementations: dict[str, list[Implementation]] = {}
        self.decisions: list[RoutingDecision] = []

    # -- registration -------------------------------------------------------
    def register(self, implementation: Implementation) -> Implementation:
        problems = implementation.validate()
        if problems:
            raise RouterError(f"invalid implementation: {problems}")
        bucket = self._implementations.setdefault(implementation.capability, [])
        if any(i.implementation_id == implementation.implementation_id for i in bucket):
            raise RouterError(
                f"implementation {implementation.implementation_id!r} already "
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
        previous one is demoted, remaining selectable if the default fails.
        """
        if lifecycle not in LIFECYCLES:
            raise RouterError(f"unknown lifecycle {lifecycle!r}")
        bucket = self._implementations.get(capability, [])
        for index, impl in enumerate(bucket):
            if impl.implementation_id == implementation_id:
                updated = replace(impl, lifecycle=lifecycle)
                bucket[index] = updated
                self._record("capabilities.lifecycle_changed", {
                    "capability": capability, "implementation": implementation_id,
                    "from": impl.lifecycle, "to": lifecycle})
                return updated
        raise RouterError(f"no implementation {implementation_id!r} for {capability!r}")

    def implementations(self, capability: str) -> list[Implementation]:
        return list(self._implementations.get(capability, []))

    # -- selection ----------------------------------------------------------
    @staticmethod
    def _candidate_view(impl: Implementation) -> tuple:
        """The ONLY facts the scorer may see.

        ``origin`` is deliberately absent. This is the founder's correction made
        structural: a mechanism cannot be preferred for resembling a metaphor,
        and cannot be penalised for being conventional, because the selector
        cannot tell which it is.
        """
        return (
            SELECTABLE.index(impl.lifecycle),
            impl.cost,
            -EVIDENCE_MATURITY.index(impl.evidence_maturity),
            impl.implementation_id,          # deterministic tie-break
        )

    def select(self, capability: str) -> tuple[Implementation, RoutingDecision]:
        """Choose the cheapest healthy implementation. Records the decision."""
        bucket = self._implementations.get(capability)
        if not bucket:
            decision = RoutingDecision(capability, None,
                                       "no implementation is registered for this capability")
            self._remember(decision)
            raise NoImplementationAvailable(
                f"capability {capability!r} has no registered implementation"
            )

        rejected, eligible = [], []
        for impl in bucket:
            if impl.lifecycle not in SELECTABLE:
                rejected.append((impl.implementation_id, f"lifecycle {impl.lifecycle}"))
            elif not impl.healthy():
                rejected.append((impl.implementation_id, "failed health check"))
            else:
                eligible.append(impl)

        if not eligible:
            decision = RoutingDecision(
                capability, None, "every registered implementation is unavailable",
                considered=tuple(i.implementation_id for i in bucket),
                rejected=tuple(rejected))
            self._remember(decision)
            raise NoImplementationAvailable(
                f"capability {capability!r} is registered but unserviceable: {rejected}"
            )

        chosen = min(eligible, key=self._candidate_view)
        decision = RoutingDecision(
            capability, chosen.implementation_id,
            (f"cheapest healthy implementation at lifecycle {chosen.lifecycle} "
             f"(cost {chosen.cost}, evidence {chosen.evidence_maturity})"),
            considered=tuple(i.implementation_id for i in bucket),
            rejected=tuple(rejected),
            origin_of_chosen=chosen.origin)
        self._remember(decision)
        return chosen, decision

    def resolve(self, capability: str):
        """Select, then build the object that performs the behavior."""
        chosen, _ = self.select(capability)
        return chosen.provider()

    # -- restoration --------------------------------------------------------
    def restore(self, capability: str, *, unavailable: str) -> tuple[Implementation, RoutingDecision]:
        """A named implementation has been lost. Find another way to perform it.

        This is "self-healing" with the metaphor removed: detect the loss, mark
        the lost implementation unavailable *without deleting it* (§12), select
        a replacement from whatever remains, and record what happened. Nothing
        is generated here — generation is one more implementation that may be
        registered and will then compete on the same terms as the rest.
        """
        bucket = self._implementations.get(capability, [])
        if not any(i.implementation_id == unavailable for i in bucket):
            raise RouterError(
                f"cannot mark {unavailable!r} unavailable: not registered for {capability!r}"
            )
        self.set_lifecycle(capability, unavailable, "QUARANTINED")
        self._record("capabilities.function_lost", {
            "capability": capability, "implementation": unavailable})
        chosen, decision = self.select(capability)
        self._record("capabilities.function_restored", {
            "capability": capability,
            "replacement": chosen.implementation_id,
            "origin": chosen.origin,
            "replaced": unavailable})
        return chosen, decision

    # -- recording ----------------------------------------------------------
    def _remember(self, decision: RoutingDecision) -> None:
        self.decisions.append(decision)
        self._record("capabilities.routing_decision", decision.describe())

    def _record(self, event_type: str, payload: dict) -> None:
        if self.ledger is not None:
            self.ledger.append("event", {"type": event_type, **payload})

    def describe(self) -> dict:
        return {
            "capabilities": {
                name: [
                    {"implementation": i.implementation_id, "lifecycle": i.lifecycle,
                     "origin": i.origin, "cost": i.cost,
                     "evidence": i.evidence_maturity, "healthy": i.healthy()}
                    for i in impls
                ]
                for name, impls in sorted(self._implementations.items())
            },
            "decisions": [d.describe() for d in self.decisions],
            "authority_granted": False,
        }
