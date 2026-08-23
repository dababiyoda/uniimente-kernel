"""Construction, moved downstream of selection and behind the Gate.

FOUNDER-RULING-2026-08-22, ruling 4:

> A router decides; it does not instantiate or execute. [...] Move provider
> construction/execution downstream to a caller possessing the required
> capability and crossing the Consequence Gate.

## Why this is a separate module and not a router method

PR #70's router had `resolve()`, three lines that selected an implementation and
then called `chosen.provider()`. It is the most natural method in the world to
write and it is the exact point where a component that *recommends* becomes a
component that *acts* — with a ranked justification already in hand for why it
was the right thing to do.

Splitting it costs one extra call at every site. What that buys is that the
selector has no reachable path to a constructor: `Implementation.provider` is
absent from `selectable_view()`, the router never receives the object, and the
only code that can construct is here, where a capability and a gate traversal
are required arguments.

## What crossing the Gate means here

Instantiation is internal — no money moves, nothing external is contacted. It
still crosses the Gate, for two reasons that are not ceremony:

1. **A provider is arbitrary code.** `GENERATED` is one of the four origins in
   `capabilities.implementations.ORIGINS`. Constructing a generated
   implementation without a governed step would be the institution running code
   it composed for itself, on its own authority.
2. **The record.** The Gate produces a witness and a receipt. Without it, "which
   implementation did we actually run, under what authority" is answerable only
   from memory.

The consequence class is `internal` and the budget is zero, so this is a cheap
traversal — but a refused one is a refusal, and `instantiate` returns no object
when the Gate says no.
"""
from __future__ import annotations

from dataclasses import dataclass

from capabilities.implementations import (
    Implementation,
    ImplementationError,
    ImplementationRegistry,
)

#: Constructing an implementation changes process state and touches nothing
#: outside it. Stated as a constant so a later caller cannot quietly raise it:
#: an instantiation that needed a higher class would be doing something other
#: than instantiating.
#:
#: The value comes from the institution's one canonical vocabulary — the same
#: tuple `policy.engine`, `capabilities.genome`, `discovery.service` and every
#: organ manifest use. Writing a plausible-sounding `"internal"` here would have
#: type-checked and passed review while meaning nothing to any of them.
CONSEQUENCE_CLASS = "internal_write"

#: Construction costs nothing. A non-zero estimate here would be a claim about
#: spending that instantiation does not make, and the policy engine correctly
#: refuses non-zero cost without a budget authorisation.
ESTIMATED_COST_USD = 0.0


class InstantiationRefused(RuntimeError):
    """The Gate refused, or the implementation is not serviceable.

    Carries the reasons rather than a bare failure: a caller that cannot see why
    construction was refused will retry it.
    """

    def __init__(self, message: str, reasons: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.reasons = reasons


@dataclass(frozen=True)
class Instantiation:
    """What was built, under which authority, with the proof it happened."""

    capability: str
    implementation_id: str
    #: The constructed object. The only place in the institution where a
    #: provider's return value is exposed.
    instance: object
    action_id: str
    witness_id: str | None
    #: Recorded so an auditor can ask "was this a canonical implementation or
    #: one we generated?" without re-reading the registry.
    origin: str


def instantiate(
    registry: ImplementationRegistry,
    capability: str,
    implementation_id: str,
    *,
    gate,
    actor: str,
    legal_principal: str,
    standing_grant=None,
) -> Instantiation:
    """Construct one selected implementation, through the Consequence Gate.

    Takes an `implementation_id` rather than choosing one. Choosing is the
    router's job and this function must not be able to do it — a constructor
    that could also select would have reassembled `resolve()` under a new name.

    Raises `InstantiationRefused` when the implementation is unserviceable or
    the Gate refuses. Never returns a partially built result.
    """
    from policy.engine import Proposal

    implementation = registry.get(capability, implementation_id)

    # Re-checked at construction time, not trusted from selection time. The
    # same discipline the Gate applies at its commit boundary: authority and
    # health are revalidated where the durable act happens, because an
    # implementation can be quarantined between being chosen and being built.
    if implementation.lifecycle not in ("ACTIVE", "CANARY", "SPECIALIZED",
                                        "FALLBACK", "SUPERSEDED", "HISTORICAL"):
        raise InstantiationRefused(
            f"{implementation_id!r} is at lifecycle {implementation.lifecycle} "
            f"and may not be constructed",
            reasons=(f"lifecycle {implementation.lifecycle}",))
    if not implementation.healthy():
        raise InstantiationRefused(
            f"{implementation_id!r} failed its health check at construction time",
            reasons=("failed health check",))

    built: list[object] = []

    def _executor(_proposal) -> dict:
        """Runs inside the Gate. The single call site of `provider()`."""
        built.append(implementation.provider())
        return {"observed_outcome": "constructed",
                "implementation": implementation_id}

    proposal = Proposal(
        actor=actor,
        legal_principal=legal_principal,
        action_class="capability.instantiate",
        objective=f"construct {implementation_id} for {capability}",
        payload={"capability": capability, "implementation": implementation_id},
        target=f"process://kernel/{capability}",
        consequence_class=CONSEQUENCE_CLASS,
        evidence_confidence=_confidence_of(implementation),
        evidence_refs=[f"implementation:{implementation_id}"],
        estimated_cost_usd=ESTIMATED_COST_USD,
        requested_capability=capability,
        expected_outcome="constructed",
    )

    record = gate.run(proposal, executor=_executor, standing_grant=standing_grant)

    if not built:
        raise InstantiationRefused(
            f"the Consequence Gate refused construction of {implementation_id!r}",
            reasons=tuple(record.refusal_reasons))

    return Instantiation(
        capability=capability,
        implementation_id=implementation_id,
        instance=built[0],
        action_id=record.action_id,
        witness_id=record.witness_id,
        origin=implementation.origin,
    )


def _confidence_of(implementation: Implementation) -> float:
    """Map declared evidence maturity onto the proposal's confidence field.

    Coarse and deliberately so. These are the institution's own maturity labels,
    not a measured probability, and the witness records them as what they are.
    Once witness contract v2 is emitted (see CONTRADICTION-0002) this value
    becomes durable and calibratable, at which point the mapping stops being a
    convenience and starts being a claim worth fitting to outcomes.
    """
    return {
        "none": 0.1,
        "asserted": 0.3,
        "tested": 0.6,
        "verified_by_execution": 0.9,
    }.get(implementation.evidence_maturity, 0.1)


__all__ = ["CONSEQUENCE_CLASS", "ESTIMATED_COST_USD", "Instantiation",
           "InstantiationRefused", "ImplementationError", "instantiate"]
