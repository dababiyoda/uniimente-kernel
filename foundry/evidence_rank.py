"""What the evidence says about a technology, for anyone choosing between them.

Doctrine (EVIDENCE-RANKED SELECTION): `TechnologySpec.status` is a hand-written
word — `executable`, `partial`, `target` — bound to no proof. The Foundry
Composer used it as the *primary* sort key when choosing which technology covers
a control surface, so the institution selected what it had described most
confidently rather than what it had actually built.

The divergence is measurable, not hypothetical. On this repository:

    #31 Web servers         status=executable (best rank)  evidence=BLUEPRINT
    #14 Institutional shell status=target     (worst rank) evidence=EXERCISED

So the old key would preferentially select a technology with nothing built, and
deprioritise one that runs inside the institution's own loop with tests and a
registered closure.

#25 Cognitive router is the instructive near-miss. Its *awarded* rung is
EXERCISED, but it stands on #19 Recommender systems, which is BLUEPRINT, so its
*constrained* rung is BLUEPRINT and it is not reported as under-claimed. That is
the intended reading: something whose foundation is missing should not be
selected as though it were ready to attach, however good its own evidence is.

This module supplies the missing signal. It does not delete the old one:
`status` is preserved and demoted to a secondary ranked term, per Final Build
Order §9 and §12. Where the two disagree the disagreement is *recorded on the
plan* rather than averaged away, per §8's rule against silent translation.

Two scoping facts worth stating plainly:

1. The table describes *this repository*. A caller may hand the Composer a
   synthetic arsenal; the evidence is still about the real technologies, and an
   id the ladder does not know is reported UNKNOWN rather than assumed sound.
2. `blueprint` is imported lazily. `blueprint.critical_path` imports
   `foundry.arsenal`, which runs `foundry/__init__`, which imports
   `foundry.composition` — a module-level import here would close that ring.

This module ranks. It grants nothing, activates nothing, and selects nothing on
its own: it returns an ordering key that a caller may use.
"""
from __future__ import annotations

from dataclasses import dataclass

#: Lower is weaker. The absence of a rung sorts below every rung, because the
#: ladder refuses to round an unsupported claim up to BLUEPRINT.
UNSUPPORTED = -1
UNKNOWN = -2

_RUNG_STRENGTH = {
    "BLUEPRINT": 0, "SKETCHED": 1, "BUILT": 2,
    "EXERCISED": 3, "PROVEN": 4, "HARDENED": 5,
}

#: The rung at which a technology has code that a named test actually exercises.
BUILDABLE_FLOOR = _RUNG_STRENGTH["BUILT"]

#: A claim of `executable` at or below this rung is an over-claim: the word says
#: it runs, the evidence says it is a design or an unexercised sketch.
_OVER_CLAIM_CEILING = _RUNG_STRENGTH["SKETCHED"]


@dataclass(frozen=True)
class TechnologyEvidence:
    """One technology's claimed status beside what its evidence supports."""

    technology_id: int
    claimed_status: str
    awarded: str | None
    constrained: str | None
    ceiling: str | None

    @property
    def strength(self) -> int:
        """How strong this technology is, counting the foundation beneath it.

        The constrained rung is used in preference to the awarded one: a
        capability standing above a weak dependency cannot be attached at its
        own advertised strength, and the Composer is choosing something to
        attach.
        """
        rung = self.constrained or self.awarded
        if rung is None:
            return UNSUPPORTED
        return _RUNG_STRENGTH.get(rung, UNSUPPORTED)

    @property
    def buildable(self) -> bool:
        """Is there code here that a named test exercises?"""
        return self.strength >= BUILDABLE_FLOOR

    @property
    def disagreement(self) -> str | None:
        """How the written status and the resolved evidence conflict, if they do."""
        if self.claimed_status == "executable" and self.strength <= _OVER_CLAIM_CEILING:
            return (
                f"#{self.technology_id} is written 'executable' but its evidence "
                f"supports only {self.awarded or 'nothing'}; the word claims it runs "
                "and no test exercises it"
            )
        if self.claimed_status == "target" and self.strength >= _RUNG_STRENGTH["EXERCISED"]:
            return (
                f"#{self.technology_id} is written 'target' but its evidence supports "
                f"{self.awarded}; it already runs inside the institution's own loop"
            )
        return None


@dataclass(frozen=True)
class UnknownTechnology(TechnologyEvidence):
    """An id the ladder does not cover. Never assumed sound."""

    @property
    def strength(self) -> int:
        return UNKNOWN

    @property
    def disagreement(self) -> str | None:
        return (
            f"#{self.technology_id} is not covered by the evidence ladder, so its "
            f"status {self.claimed_status!r} is unverifiable here"
        )


def evidence_table() -> dict[int, TechnologyEvidence]:
    """Read the ladder once. Lazy import: see the module docstring."""
    from blueprint.critical_path import compute
    from foundry.arsenal import ARSENAL

    report = compute()
    table: dict[int, TechnologyEvidence] = {}
    for technology_id, status in report.statuses.items():
        spec = ARSENAL.get(technology_id)
        table[technology_id] = TechnologyEvidence(
            technology_id=technology_id,
            claimed_status=spec.status if spec else "unknown",
            awarded=status.awarded_rung.value if status.awarded_rung else None,
            constrained=status.constrained_rung.value if status.constrained_rung else None,
            ceiling=status.ceiling.value if status.ceiling else None,
        )
    return table


def evidence_for(technology_id: int, table: dict[int, TechnologyEvidence],
                 claimed_status: str = "unknown") -> TechnologyEvidence:
    """The row for a technology, or an explicit UNKNOWN. Never a silent default."""
    found = table.get(technology_id)
    if found is not None:
        return found
    return UnknownTechnology(technology_id=technology_id,
                             claimed_status=claimed_status,
                             awarded=None, constrained=None, ceiling=None)


def selection_rank(evidence: TechnologyEvidence) -> int:
    """Sort key fragment, lower is better, so stronger evidence sorts first."""
    return -evidence.strength


def disagreement_notes(technology_ids, table: dict[int, TechnologyEvidence],
                       arsenal=None) -> tuple[str, ...]:
    """Every claim/evidence conflict among the selected technologies."""
    notes = []
    for technology_id in technology_ids:
        claimed = "unknown"
        if arsenal is not None and technology_id in arsenal:
            claimed = arsenal[technology_id].status
        conflict = evidence_for(technology_id, table, claimed).disagreement
        if conflict:
            notes.append(f"evidence_disagreement: {conflict}")
    return tuple(notes)


def rung_map(technology_ids, table: dict[int, TechnologyEvidence]) -> dict[int, str]:
    """The evidence rung per technology, as a plain string for the plan record."""
    out: dict[int, str] = {}
    for technology_id in technology_ids:
        evidence = evidence_for(technology_id, table)
        if isinstance(evidence, UnknownTechnology):
            out[technology_id] = "UNKNOWN"
        else:
            out[technology_id] = evidence.constrained or evidence.awarded or "UNSUPPORTED"
    return out
