"""The Capability Router: chooses a candidate, authorizes nothing.

Doctrine (ROUTER, FBO §4.14): select among implementations by verified accuracy,
evidence maturity, latency, cost, privacy, domain fit, current health, failure
history, authority requirements, reversibility and environmental conditions.
Record the decision so it can later be compared with what actually happened.

What this implementation is careful about:

**It returns a decision; it never acts on one.** `route()` yields a
`RoutingDecision` naming the selected candidate, the full ranking, the score
breakdown, and every candidate refused and why. Nothing in this module calls the
Consequence Gate, mints a grant, or invokes a capability. An AST test asserts
that and would fail on an import of `policy.consequence_gate`.

**Refusal beats a bad choice.** A request whose consequence class exceeds a
candidate's authority ceiling does not down-rank that candidate — it removes it.
A request no candidate can satisfy returns a decision with `selected=None` and
the reason per candidate. The router never returns "the least bad option" for a
request that should not proceed at all.

**Its weights are declared, not learned.** `RoutingCriteria` carries explicit
weights with defaults chosen by hand. `evidence_maturity` outranks `speed`
because an institution that routes to the fastest unproven implementation has
optimized the wrong quantity. Every decision reports
`weights_are_declared_not_learned = True` until real outcomes exist to fit them.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from discovery.service import (
    CONSEQUENCE_ORDER,
    CapabilityAdvertisement,
    CapabilityDiscoveryService,
)

# Evidence maturity mirrors the blueprint ladder, weakest to strongest, so the
# router and the blueprint speak one vocabulary.
MATURITY_ORDER = ("BLUEPRINT", "SKETCHED", "BUILT", "EXERCISED", "PROVEN", "HARDENED")


class RouterError(ValueError):
    """The route could not be computed. Fails closed; returns no fallback."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Candidate:
    """One implementation that could serve a request.

    `authority_ceiling` is what the candidate's organ is permitted at most. It is
    a constraint on selection, never a permission this router confers.
    """

    candidate_id: str
    organ_id: str
    contract: str
    authority_ceiling: str = "read_only"
    requires_kernel_gate: bool = True
    evidence_maturity: str = "BLUEPRINT"
    reversible: bool = True
    healthy: bool = True
    observed_failures: int = 0
    cost_units: float = 0.0
    latency_ms: float = 0.0
    lifecycle: str = "ACTIVE"

    def __post_init__(self) -> None:
        if self.authority_ceiling not in CONSEQUENCE_ORDER:
            raise RouterError(
                f"candidate {self.candidate_id}: unknown authority ceiling "
                f"{self.authority_ceiling!r}"
            )
        if self.evidence_maturity not in MATURITY_ORDER:
            raise RouterError(
                f"candidate {self.candidate_id}: unknown evidence maturity "
                f"{self.evidence_maturity!r}"
            )
        if self.observed_failures < 0 or self.cost_units < 0 or self.latency_ms < 0:
            raise RouterError(
                f"candidate {self.candidate_id}: negative cost, latency or failure count"
            )

    @classmethod
    def from_advertisement(cls, ad: CapabilityAdvertisement, contract: str,
                           **overrides) -> Candidate:
        """Build a candidate from a discovery advertisement.

        Maturity defaults to BLUEPRINT: discovery reports what an organ declares,
        and a declaration is not evidence. A caller with real evidence supplies it.
        """
        base = {
            "candidate_id": ad.capability_id,
            "organ_id": ad.organ_id,
            "contract": contract,
            "authority_ceiling": ad.max_consequence_class,
            "requires_kernel_gate": ad.requires_kernel_gate,
            "lifecycle": ad.lifecycle,
        }
        base.update(overrides)
        return cls(**base)


@dataclass(frozen=True)
class RoutingCriteria:
    """What the request needs, and how much each property is worth.

    Weights are hand-set. They are not fitted to outcomes, because there are no
    outcomes to fit them to.
    """

    contract: str
    consequence_class: str = "read_only"
    require_reversible: bool = False
    max_cost_units: float | None = None
    max_latency_ms: float | None = None
    minimum_maturity: str = "BLUEPRINT"

    weight_maturity: float = 4.0
    weight_health: float = 3.0
    weight_reversibility: float = 2.0
    weight_reliability: float = 2.0
    weight_cost: float = 1.0
    weight_speed: float = 1.0

    def __post_init__(self) -> None:
        if self.consequence_class not in CONSEQUENCE_ORDER:
            raise RouterError(f"unknown consequence class {self.consequence_class!r}")
        if self.minimum_maturity not in MATURITY_ORDER:
            raise RouterError(f"unknown minimum maturity {self.minimum_maturity!r}")
        if not self.contract or not self.contract.strip():
            raise RouterError("a routing request must name a contract")


@dataclass(frozen=True)
class ScoredCandidate:
    candidate_id: str
    score: float
    breakdown: dict


@dataclass(frozen=True)
class RoutingDecision:
    """A recommendation and its complete rationale. Confers nothing.

    `selected` may be None. That is a valid, final answer meaning no candidate
    may serve this request — not an invitation to retry with weaker criteria.
    """

    contract: str
    consequence_class: str
    selected: str | None
    ranking: tuple[ScoredCandidate, ...]
    refused: tuple[tuple[str, str], ...]     # (candidate_id, reason)
    decided_at: str
    criteria: dict
    weights_are_declared_not_learned: bool = True
    authorizes: None = None                  # explicit: a decision is not a grant
    #: Where the selected implementation came from, carried for audit only.
    #: Rehomed from PR #70, where `Implementation.origin` was correct and was
    #: deliberately kept out of the scorer's reach so a mechanism could not win
    #: for resembling a metaphor. That separation is preserved: this field is
    #: written to the decision AFTER selection and is absent from
    #: `Implementation.selectable_view()`, which is the only projection a scorer
    #: sees.
    selected_origin: str | None = None

    @property
    def is_refusal(self) -> bool:
        return self.selected is None

    def explain(self) -> str:
        lines = [
            f"contract={self.contract} consequence_class={self.consequence_class}",
            f"selected={self.selected or 'NONE — no candidate may serve this request'}",
        ]
        for s in self.ranking:
            lines.append(f"  rank {s.candidate_id}: {s.score:.3f} {s.breakdown}")
        for cid, reason in self.refused:
            lines.append(f"  refused {cid}: {reason}")
        lines.append(
            "this decision grants no authority; execution still requires a "
            "capability grant and the Consequence Gate"
        )
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """The canonical typed boundary, matching `contracts/routing-decision`.

        Ratified as canonical by FOUNDER-RULING-2026-08-22 ruling 4: there is
        one typed RoutingDecision owned by the Kernel, and organ adapters
        consume it rather than copying it into a parallel shape. The schema sets
        `additionalProperties: false`, so a field added here without being added
        there fails validation instead of quietly becoming a second dialect.

        `authorizes` is typed `null` and `grants_issued` is `const 0`. Both are
        required: the absence of authority is asserted at the boundary rather
        than left to be inferred from the absence of a field.
        """
        return {
            "contract": self.contract,
            "consequence_class": self.consequence_class,
            "selected": self.selected,
            "ranking": [asdict(s) for s in self.ranking],
            "refused": [list(r) for r in self.refused],
            "decided_at": self.decided_at,
            "criteria": self.criteria,
            "weights_are_declared_not_learned": self.weights_are_declared_not_learned,
            "authorizes": self.authorizes,
            "grants_issued": 0,
            "selected_origin": self.selected_origin,
        }


class DecisionRouter:
    """Ranks candidates for a contract. Records every decision it makes."""

    def __init__(self, discovery: CapabilityDiscoveryService | None = None):
        self._discovery = discovery
        self._decisions: list[RoutingDecision] = []

    # -- candidate sourcing -------------------------------------------------
    def candidates_for(self, contract: str) -> tuple[Candidate, ...]:
        """Candidates drawn from the discovery directory, if one was supplied."""
        if self._discovery is None:
            raise RouterError(
                "no discovery service supplied; pass candidates to route() explicitly"
            )
        return tuple(
            Candidate.from_advertisement(ad, contract)
            for ad in self._discovery.implementations_of(contract)
        )

    # -- scoring ------------------------------------------------------------
    @staticmethod
    def _admissible(c: Candidate, crit: RoutingCriteria) -> str | None:
        """Return a refusal reason, or None when the candidate may compete."""
        if c.contract != crit.contract:
            return f"serves {c.contract}, not {crit.contract}"
        if CONSEQUENCE_ORDER.index(crit.consequence_class) > \
                CONSEQUENCE_ORDER.index(c.authority_ceiling):
            return (f"request is {crit.consequence_class}; candidate ceiling is "
                    f"{c.authority_ceiling}")
        if MATURITY_ORDER.index(c.evidence_maturity) < \
                MATURITY_ORDER.index(crit.minimum_maturity):
            return (f"evidence maturity {c.evidence_maturity} below required "
                    f"{crit.minimum_maturity}")
        if crit.require_reversible and not c.reversible:
            return "request requires a reversible implementation"
        if not c.healthy:
            return "candidate is unhealthy"
        if c.lifecycle in ("QUARANTINED", "HISTORICAL", "SUPERSEDED"):
            return f"lifecycle {c.lifecycle} is not routable"
        if crit.max_cost_units is not None and c.cost_units > crit.max_cost_units:
            return f"cost {c.cost_units} exceeds ceiling {crit.max_cost_units}"
        if crit.max_latency_ms is not None and c.latency_ms > crit.max_latency_ms:
            return f"latency {c.latency_ms}ms exceeds ceiling {crit.max_latency_ms}ms"
        return None

    @staticmethod
    def _score(c: Candidate, crit: RoutingCriteria,
               worst_cost: float, worst_latency: float) -> tuple[float, dict]:
        maturity = MATURITY_ORDER.index(c.evidence_maturity) / (len(MATURITY_ORDER) - 1)
        health = 1.0 if c.healthy else 0.0
        reversibility = 1.0 if c.reversible else 0.0
        reliability = 1.0 / (1.0 + c.observed_failures)
        cost = 1.0 - (c.cost_units / worst_cost if worst_cost > 0 else 0.0)
        speed = 1.0 - (c.latency_ms / worst_latency if worst_latency > 0 else 0.0)

        breakdown = {
            "maturity": round(maturity * crit.weight_maturity, 4),
            "health": round(health * crit.weight_health, 4),
            "reversibility": round(reversibility * crit.weight_reversibility, 4),
            "reliability": round(reliability * crit.weight_reliability, 4),
            "cost": round(cost * crit.weight_cost, 4),
            "speed": round(speed * crit.weight_speed, 4),
        }
        return round(sum(breakdown.values()), 4), breakdown

    # -- routing ------------------------------------------------------------
    def route(self, criteria: RoutingCriteria,
              candidates: tuple[Candidate, ...] | list[Candidate] | None = None
              ) -> RoutingDecision:
        """Rank admissible candidates and record the decision.

        Returns a decision even when nothing is admissible. It never executes,
        never grants, and never widens the criteria to find a winner.
        """
        pool = tuple(candidates) if candidates is not None \
            else self.candidates_for(criteria.contract)

        refused: list[tuple[str, str]] = []
        admissible: list[Candidate] = []
        for c in pool:
            reason = self._admissible(c, criteria)
            if reason is None:
                admissible.append(c)
            else:
                refused.append((c.candidate_id, reason))

        worst_cost = max((c.cost_units for c in admissible), default=0.0)
        worst_latency = max((c.latency_ms for c in admissible), default=0.0)

        scored = []
        for c in admissible:
            score, breakdown = self._score(c, criteria, worst_cost, worst_latency)
            scored.append(ScoredCandidate(c.candidate_id, score, breakdown))
        # Deterministic: score descending, then candidate id.
        scored.sort(key=lambda s: (-s.score, s.candidate_id))

        decision = RoutingDecision(
            contract=criteria.contract,
            consequence_class=criteria.consequence_class,
            selected=scored[0].candidate_id if scored else None,
            ranking=tuple(scored),
            refused=tuple(sorted(refused)),
            decided_at=_now(),
            criteria={
                "minimum_maturity": criteria.minimum_maturity,
                "require_reversible": criteria.require_reversible,
                "max_cost_units": criteria.max_cost_units,
                "max_latency_ms": criteria.max_latency_ms,
            },
        )
        self._decisions.append(decision)
        return decision

    # -- the record ---------------------------------------------------------
    @property
    def decisions(self) -> tuple[RoutingDecision, ...]:
        """Every decision made, in order. FBO §4.14 requires they be recorded."""
        return tuple(self._decisions)

    def outcomes_compared(self) -> int:
        """How many routing decisions have been compared against real outcomes.

        Zero, and it will stay zero until the institution produces a verified
        external outcome. Reported rather than omitted so the router's weights
        are never mistaken for learned ones.
        """
        return 0
