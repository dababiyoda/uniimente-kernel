"""Motif-conditional constraint: a channel separate from role demand.

THE DEFECT THIS REPLACES

PR #59's `local_inhibition` wrote `Tri.INHIBIT` into the cell's ROLE field.
INHIBIT dominates ACTIVATE by design (Phase 3, to stop over-recruitment), so a
constrained cell could never differentiate at all - not even into a form that
would have escaped. 10 of 11 Gate G failures were "tissue did not fill every
role": the tissue could not form, rather than forming a non-escaping shape.

The error was CHANNEL OVERLOADING. One ternary field was carrying two unrelated
meanings:

    role demand / satisfaction   "is this role wanted or already filled?"
    causal prohibition           "is this local configuration forbidden?"

Separated here. The role channel stays exactly as it was. Constraints live in
their own channel and are evaluated against a PROSPECTIVE LOCAL PROPOSAL, not
against the role.

    role is needed
  + this cell can fill it
  + the proposed attachment would reproduce a prohibited motif
  -> refuse THIS attachment, keep looking

  never: role has a prohibited motif -> role can never differentiate

MECHANISM SELECTION

Ten candidates were compared (docs/invention/PHASE3C_CANDIDATES.md). Selected:
**motif-conditional attachment refusal with constraint-carrying receptors**.

Rejected and why:
  edge-level causal veto      needs both endpoints' state; not locally decidable
  local type refinement       expressive, but changes interfaces globally, so a
                              constraint in one place alters unification everywhere
  stigmergic failure scar     environment-mediated, so the constraint outlives
                              its scope with no expiry mechanism
  resource-gradient deform    conflates "forbidden" with "expensive"; a
                              determined tissue buys its way back into the motif
  factor-graph propagation    correct, but requires a component holding the
                              factor graph - the planner returning by the back door
  admission-only repeat search no local learning at all; this is PR #58's
                              behaviour, which is the baseline being beaten
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from .causal import CausalMotif


@dataclass(frozen=True)
class LocalProposal:
    """What a cell is ABOUT to do, expressed in its own neighbourhood terms.

    Every field is computable by the cell from its own view. Nothing here
    requires knowing the graph, the pool, or another cell's internals.
    """
    own_role: str
    proposed_upstream_count: int
    proposed_sibling_redundancy: int
    proposed_verification_class: str
    proposed_resource_coupling: bool

    def reproduces(self, motif: CausalMotif) -> bool:
        return motif.matches_local(
            role=self.own_role,
            upstream_count=self.proposed_upstream_count,
            redundancy=self.proposed_sibling_redundancy,
            verification_class=self.proposed_verification_class,
            shares_resource=self.proposed_resource_coupling)


class ConstraintReceptor:
    """A cell's constraint channel. Holds motifs; never touches role demand.

    Motifs arrive scoped to a role and expire. A receptor holding a motif for
    `emit` does not prevent the cell from becoming `emit` - it prevents the
    cell from becoming `emit` *in the configuration the motif describes*.
    """

    __slots__ = ("_motifs", "_episodes_seen", "refusals", "admitted")

    def __init__(self) -> None:
        self._motifs: list[tuple[CausalMotif, int]] = []   # (motif, expires_at)
        self._episodes_seen = 0
        self.refusals: list[str] = []
        self.admitted: list[str] = []

    def receive(self, motif: CausalMotif, *, expires_after: int) -> None:
        self._motifs.append((motif, self._episodes_seen + expires_after))

    def tick_episode(self) -> None:
        self._episodes_seen += 1
        self._motifs = [(m, e) for m, e in self._motifs
                        if e > self._episodes_seen]

    def active_for(self, role: str) -> list[CausalMotif]:
        return [m for m, _ in self._motifs if m.role == role]

    def permits(self, proposal: LocalProposal) -> tuple[bool, str]:
        """Evaluate ONE prospective local configuration."""
        for motif in self.active_for(proposal.own_role):
            if proposal.reproduces(motif):
                why = (f"proposed configuration for role {proposal.own_role!r} "
                       f"reproduces a prohibited motif "
                       f"(upstream={proposal.proposed_upstream_count}, "
                       f"redundancy={proposal.proposed_sibling_redundancy}, "
                       f"verification={proposal.proposed_verification_class})")
                self.refusals.append(why)
                return False, why
        self.admitted.append(proposal.own_role)
        return True, "no prohibited motif matches this configuration"

    def role_is_still_available(self, role: str) -> bool:
        """A constrained role must remain reachable by SOME configuration.

        This is the property whose absence caused the PR #59 defect. If every
        configuration of a role were refused, the channel would have collapsed
        back into role suppression.
        """
        motifs = self.active_for(role)
        if not motifs:
            return True
        # Try a redundant, decoupled configuration - the standard escape.
        escape = LocalProposal(own_role=role, proposed_upstream_count=2,
                               proposed_sibling_redundancy=1,
                               proposed_verification_class="redundant_read",
                               proposed_resource_coupling=False)
        return not any(escape.reproduces(m) for m in motifs)


def false_role_suppression_events(receptor: ConstraintReceptor,
                                  roles: Iterable[str]) -> int:
    """Roles rendered entirely unreachable by constraints. Target: 0."""
    return sum(1 for r in roles if not receptor.role_is_still_available(r))
