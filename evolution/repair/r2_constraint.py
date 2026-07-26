"""Candidate R2-constraint — generate the whole candidate space, then test it.

MATERIAL DIFFERENCE FROM THE ORIGINAL AND FROM R1. Neither of those ever
considers an edge that does not exist. R2 enumerates every conceivable
(producer, contract, consumer) triple across all organs and all named contracts
— including the overwhelming majority that are wrong — and filters that space
through an ordered list of named, self-explaining constraints. Refusals are not
counted; they are *classified* from which constraint a declaration violated.

Two consequences, both intended:

  - It is quadratic in organ count where the others are linear in declarations.
    That is a real cost and the meter will charge for it.
  - Every rejection carries the name of the constraint that rejected it, so the
    output explains itself. The original approximates this with counters.

Richer diagnostics must not be able to buy a better correctness score, which is
why `FunctionOutput` excludes the diagnostics field from comparison.

This module does not import the original or R1.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from itertools import product
from typing import Callable

from evolution.repair.candidate import FunctionOutput

#: Lift the runtime disable, withdraw R2 as provider, re-register the original.
ROLLBACK_STEPS = 3


@dataclass(frozen=True)
class World:
    """Everything a constraint may consult. Declarative input, no methods that
    decide anything."""
    organs: tuple[str, ...]
    produces: dict[str, frozenset[str]]     # organ -> contracts
    consumes: dict[str, frozenset[str]]     # organ -> contracts
    typed: frozenset[str]


@dataclass(frozen=True)
class EdgeAssignment:
    producer: str
    contract: str
    consumer: str


@dataclass(frozen=True)
class Declaration:
    organ: str
    contract: str
    role: str                                # "produces" | "consumes"


@dataclass(frozen=True)
class Constraint:
    """A named predicate that can say why it failed."""
    name: str
    because: str
    holds: Callable[[object, World], bool]


# -- constraints over the edge space ---------------------------------------
# Order matters: the first violation is the reported one, so the most
# fundamental reason for rejection is checked first.

EDGE_CONSTRAINTS: tuple[Constraint, ...] = (
    Constraint("distinct_organs",
               "an organ cannot form an edge with itself",
               lambda a, w: a.producer != a.consumer),
    Constraint("contract_is_typed",
               "no schema file exists for this contract",
               lambda a, w: a.contract in w.typed),
    Constraint("producer_declares_production",
               "the producer does not declare it produces this contract",
               lambda a, w: a.contract in w.produces.get(a.producer, frozenset())),
    Constraint("consumer_declares_consumption",
               "the consumer does not declare it consumes this contract",
               lambda a, w: a.contract in w.consumes.get(a.consumer, frozenset())),
)

# -- constraints over the declaration space --------------------------------

DECLARATION_CONSTRAINTS: tuple[Constraint, ...] = (
    Constraint("declared_contract_is_typed",
               "the organ names a contract that has no schema file",
               lambda d, w: d.contract in w.typed),
    Constraint("produced_contract_has_a_consumer",
               "the organ produces a contract no organ consumes",
               lambda d, w: d.role != "produces" or any(
                   d.contract in w.consumes.get(o, frozenset()) for o in w.organs)),
    Constraint("consumed_contract_has_a_producer",
               "the organ consumes a contract no organ produces",
               lambda d, w: d.role != "consumes" or any(
                   d.contract in w.produces.get(o, frozenset()) for o in w.organs)),
)

#: Which refusal a violated declaration constraint becomes. The mapping is the
#: whole of the refusal logic — there is no counter anywhere in this module.
_VIOLATION_TO_REFUSAL = {
    "declared_contract_is_typed": "untyped",
    "produced_contract_has_a_consumer": "unconsumed",
    "consumed_contract_has_a_producer": "unproduced",
}


def _first_violation(item, world: World, constraints) -> Constraint | None:
    for constraint in constraints:
        if not constraint.holds(item, world):
            return constraint
    return None


class ConstraintSatisfaction:
    """Generate-and-test resolver. Every answer explains itself."""

    candidate_id = "R2-constraint"
    mechanism = ("full candidate-space enumeration filtered by ordered named "
                 "constraints; refusals classified from violations")

    def _world(self, manifests: list, contracts_dir: str) -> World:
        suffix = ".schema.json"
        typed = frozenset(n[: -len(suffix)] for n in os.listdir(contracts_dir)
                          if n.endswith(suffix))
        return World(
            organs=tuple(m.organ_id for m in manifests),
            produces={m.organ_id: frozenset(m.produces) for m in manifests},
            consumes={m.organ_id: frozenset(m.consumes) for m in manifests},
            typed=typed,
        )

    def resolve(self, manifests: list, contracts_dir: str) -> FunctionOutput:
        world = self._world(manifests, contracts_dir)
        named = frozenset().union(*world.produces.values(), frozenset()) | \
            frozenset().union(*world.consumes.values(), frozenset())

        explanations: list[str] = []

        # ---- edge space: generate everything conceivable, then test -------
        edges = set()
        rejected = 0
        for producer, contract, consumer in product(world.organs, sorted(named),
                                                    world.organs):
            assignment = EdgeAssignment(producer, contract, consumer)
            violation = _first_violation(assignment, world, EDGE_CONSTRAINTS)
            if violation is None:
                edges.add((producer, contract, consumer))
            else:
                rejected += 1
        explanations.append(
            f"edge space: {len(edges)} satisfied all {len(EDGE_CONSTRAINTS)} "
            f"constraints, {rejected} rejected")

        # ---- declaration space: classify each violation ------------------
        refusals: dict[str, set[tuple[str, str]]] = {
            "untyped": set(), "unconsumed": set(), "unproduced": set()}

        for manifest in manifests:
            for role in ("produces", "consumes"):
                for contract in getattr(manifest, role):
                    declaration = Declaration(manifest.organ_id, contract, role)
                    violation = _first_violation(declaration, world,
                                                 DECLARATION_CONSTRAINTS)
                    if violation is None:
                        continue
                    kind = _VIOLATION_TO_REFUSAL[violation.name]
                    refusals[kind].add((manifest.organ_id, contract))
                    explanations.append(
                        f"{manifest.organ_id} {role} {contract}: {kind} — "
                        f"{violation.because}")

        unresolved = {(m.organ_id, q) for m in manifests for q in m.unresolved}
        overlapping = {(m.organ_id, cap["capability_id"])
                       for m in manifests for cap in m.capabilities
                       if cap.get("lifecycle") == "SPECIALIZED"}

        return FunctionOutput.normalize(
            edges=edges, untyped=refusals["untyped"],
            unconsumed=refusals["unconsumed"], unproduced=refusals["unproduced"],
            unresolved=unresolved, overlapping_authority=overlapping,
            diagnostics=tuple(explanations),
        )


def factory() -> ConstraintSatisfaction:
    return ConstraintSatisfaction()
