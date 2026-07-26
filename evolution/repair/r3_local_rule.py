"""Candidate R3-local-rule — no global resolver. Cells, messages, local agreement.

MATERIAL DIFFERENCE. The original, R1 and R2 all hold the whole world in one
place and compute over it. R3 has no such place. Each organ becomes a cell that
knows only its own manifest, exchanges contract advertisements with its
neighbours over a bounded number of rounds, and commits an edge only when two
cells locally agree. The report is the union of what the cells independently
concluded — nothing assembles a global view in order to decide.

THE DEVELOPMENTAL INVARIANT IS RESPECTED. No cell may enumerate the contract
registry: a cell may ask "does a schema exist for *this* contract I declare"
(`_LocalContractProbe.exists`) but cannot list the directory, so it never learns
about contracts it does not itself name. A test asserts by AST that this module
calls no directory-listing function.

THE PREDICTED WEAKNESS, RECORDED BEFORE MEASUREMENT (spec.EXPECTED_RESULTS).
The declared contract requires global negatives — "no organ produces this
contract". A cell can only conclude "no cell I have heard from produces it".
Those coincide exactly when every cell hears from every other within the round
budget, and diverge otherwise. R3 was predicted to score 0.0 and be at risk on
HO-4's orphan consumer for this reason.

The round budget is `spec.R3_ROUND_BUDGET`, fixed before this file was written
so it could not be tuned to the answer.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from evolution.repair.candidate import FunctionOutput
from evolution.repair.spec import R3_ROUND_BUDGET

#: Lift the runtime disable, withdraw R3 as provider, re-register the original.
ROLLBACK_STEPS = 3


class _LocalContractProbe:
    """Point query only. Deliberately offers no way to enumerate.

    A cell that could list the registry would hold global knowledge, which is
    the thing this candidate exists to do without.
    """

    __slots__ = ("_dir",)

    def __init__(self, contracts_dir: str):
        self._dir = contracts_dir

    def exists(self, contract: str) -> bool:
        return os.path.isfile(os.path.join(self._dir, f"{contract}.schema.json"))


@dataclass(frozen=True)
class Advertisement:
    """What one cell tells its neighbours about itself. Nothing more."""
    organ_id: str
    contract: str
    role: str                            # "produces" | "consumes"


@dataclass
class Cell:
    """One organ, with strictly local knowledge."""
    organ_id: str
    produces: tuple[str, ...]
    consumes: tuple[str, ...]
    unresolved: tuple[str, ...]
    specialized: tuple[str, ...]
    probe: _LocalContractProbe
    heard: set[Advertisement] = field(default_factory=set)

    # -- messaging ---------------------------------------------------------

    def advertise(self) -> tuple[Advertisement, ...]:
        """Only what this cell can see about itself. An advertisement is a
        claim, never a grant — a neighbour still decides for itself."""
        return tuple(
            [Advertisement(self.organ_id, c, "produces") for c in self.produces]
            + [Advertisement(self.organ_id, c, "consumes") for c in self.consumes]
        )

    def receive(self, ads) -> int:
        """Absorb neighbour advertisements. Returns how many were new, which is
        how quiescence is detected without a global coordinator."""
        before = len(self.heard)
        self.heard.update(a for a in ads if a.organ_id != self.organ_id)
        return len(self.heard) - before

    # -- local decisions ---------------------------------------------------

    def locally_untyped(self) -> set[tuple[str, str]]:
        """A cell can verify typing only for contracts it itself declares."""
        return {(self.organ_id, c) for c in set(self.produces) | set(self.consumes)
                if not self.probe.exists(c)}

    def _neighbours_consuming(self, contract: str) -> set[str]:
        return {a.organ_id for a in self.heard
                if a.contract == contract and a.role == "consumes"}

    def _neighbours_producing(self, contract: str) -> set[str]:
        return {a.organ_id for a in self.heard
                if a.contract == contract and a.role == "produces"}

    def commit_edges(self) -> set[tuple[str, str, str]]:
        """A producer cell commits an edge to each neighbour that advertised
        consuming the same contract. Local agreement between two cells, with no
        third party adjudicating."""
        return {
            (self.organ_id, contract, consumer)
            for contract in self.produces
            if self.probe.exists(contract)
            for consumer in self._neighbours_consuming(contract)
        }

    def local_unconsumed(self) -> set[tuple[str, str]]:
        """"I produce this and nobody I have heard from consumes it." Sound only
        under full reachability within the round budget."""
        return {(self.organ_id, contract) for contract in self.produces
                if self.probe.exists(contract)
                and not self._neighbours_consuming(contract)
                and contract not in self.consumes}

    def local_unproduced(self) -> set[tuple[str, str]]:
        """The global negative, decided locally. This is the weak point named in
        the module docstring, not an oversight."""
        return {(self.organ_id, contract) for contract in self.consumes
                if self.probe.exists(contract)
                and not self._neighbours_producing(contract)
                and contract not in self.produces}


class LocalRulePropagation:
    """Message-passing resolver. No global view is ever constructed."""

    candidate_id = "R3-local-rule"
    mechanism = ("bounded-round advertisement exchange between cells holding "
                 "only their own manifest; edges commit on local agreement")
    round_budget = R3_ROUND_BUDGET

    def _cells(self, manifests: list, contracts_dir: str) -> list[Cell]:
        probe = _LocalContractProbe(contracts_dir)
        return [
            Cell(organ_id=m.organ_id,
                 produces=tuple(m.produces), consumes=tuple(m.consumes),
                 unresolved=tuple(m.unresolved),
                 specialized=tuple(cap["capability_id"] for cap in m.capabilities
                                   if cap.get("lifecycle") == "SPECIALIZED"),
                 probe=probe)
            for m in manifests
        ]

    def resolve(self, manifests: list, contracts_dir: str) -> FunctionOutput:
        cells = self._cells(manifests, contracts_dir)

        # ---- propagation --------------------------------------------------
        rounds_used = 0
        for _ in range(self.round_budget):
            rounds_used += 1
            # Every cell broadcasts; every other cell absorbs. The bus carries
            # messages and decides nothing.
            traffic = [(cell, cell.advertise()) for cell in cells]
            new = 0
            for sender, ads in traffic:
                for receiver in cells:
                    if receiver is not sender:
                        new += receiver.receive(ads)
            if new == 0:
                break                       # quiescent; further rounds add nothing

        # ---- union of independent local conclusions ------------------------
        edges: set = set()
        untyped: set = set()
        unconsumed: set = set()
        unproduced: set = set()
        unresolved: set = set()
        overlapping: set = set()

        for cell in cells:
            edges |= cell.commit_edges()
            untyped |= cell.locally_untyped()
            unconsumed |= cell.local_unconsumed()
            unproduced |= cell.local_unproduced()
            unresolved |= {(cell.organ_id, q) for q in cell.unresolved}
            overlapping |= {(cell.organ_id, cap) for cap in cell.specialized}

        # An untyped contract yields untyped entries only. A cell knows its own
        # declaration is untyped, so it must retract its own refusal claims for
        # that contract — the contract's typing is local knowledge, so this
        # retraction is local too.
        untyped_pairs = {(organ, contract) for organ, contract in untyped}
        unconsumed -= untyped_pairs
        unproduced -= untyped_pairs

        return FunctionOutput.normalize(
            edges=edges, untyped=untyped, unconsumed=unconsumed,
            unproduced=unproduced, unresolved=unresolved,
            overlapping_authority=overlapping,
            diagnostics=(f"{len(cells)} cells, {rounds_used} of "
                         f"{self.round_budget} rounds used, "
                         f"{sum(len(c.heard) for c in cells)} advertisements "
                         f"absorbed; no global view constructed",),
        )


def factory() -> LocalRulePropagation:
    return LocalRulePropagation()
