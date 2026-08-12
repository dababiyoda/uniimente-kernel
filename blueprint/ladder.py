"""The hardening ladder: six rungs, and a reality axis kept separate from it.

Doctrine (LADDER): a technology's maturity is not a word someone chose. It is
the highest rung whose evidence actually resolves. Rungs are cumulative — a
technology at PROVEN satisfies every requirement of every rung below it.

The two axes are orthogonal on purpose:

    rung     — how far the capability has been carried, and what proves it.
    reality  — whether the thing that exists is running code, a simulation,
               or still only a written design.

Conflating them is how a specification becomes a production claim. A
BLUEPRINT_ONLY technology can be described in exhaustive detail and still be
nothing; an IMPLEMENTED technology can run every day and still be unproven
because no organ declares it and no contract types its boundary.

HARDENED requires an externally observable, reconciled consequence. Nothing
in this institution has one yet — the Single Bottleneck Metric stands at zero
verified outcomes. The top rung is therefore currently unreachable by
construction, and that is the honest state, not a defect in the ladder.
"""
from __future__ import annotations

from enum import Enum


class LadderError(ValueError):
    """A rung was claimed without the evidence that rung requires. Fails closed."""


class Rung(str, Enum):
    """Maturity. Cumulative and strictly ordered."""

    BLUEPRINT = "BLUEPRINT"      # specified in writing; no code claimed
    SKETCHED = "SKETCHED"        # code exists on disk
    BUILT = "BUILT"              # executable tests exercise it
    EXERCISED = "EXERCISED"      # it runs inside the institution's own loop
    PROVEN = "PROVEN"            # typed at its boundary and declared by an organ
    HARDENED = "HARDENED"        # an external consequence was observed and reconciled


class Reality(str, Enum):
    """What the artifact actually is. Never inferred from the rung."""

    BLUEPRINT_ONLY = "BLUEPRINT_ONLY"   # a design; no executable artifact
    SIMULATED = "SIMULATED"             # executes only against fixtures or a model
    IMPLEMENTED = "IMPLEMENTED"         # real code on real institutional data


class EvidenceKind(str, Enum):
    """The kinds of proof a rung may require. Each one resolves or it does not."""

    SPEC_DOCUMENT = "SPEC_DOCUMENT"              # a committed design document
    IMPLEMENTATION_PATH = "IMPLEMENTATION_PATH"  # a file or package that exists
    TEST_NODE = "TEST_NODE"                      # a named test that exists and runs
    CLOSURE_MODULE = "CLOSURE_MODULE"            # registered in a closure registry
    CONTRACT_SCHEMA = "CONTRACT_SCHEMA"          # a JSON Schema types its boundary
    MANIFEST_CAPABILITY = "MANIFEST_CAPABILITY"  # an organ declares it in its manifest
    EXTERNAL_OUTCOME = "EXTERNAL_OUTCOME"        # a reconciled real-world consequence


RUNG_ORDER: tuple[Rung, ...] = (
    Rung.BLUEPRINT,
    Rung.SKETCHED,
    Rung.BUILT,
    Rung.EXERCISED,
    Rung.PROVEN,
    Rung.HARDENED,
)

# What each rung adds on top of every rung beneath it.
_RUNG_ADDS: dict[Rung, frozenset[EvidenceKind]] = {
    Rung.BLUEPRINT: frozenset({EvidenceKind.SPEC_DOCUMENT}),
    Rung.SKETCHED: frozenset({EvidenceKind.IMPLEMENTATION_PATH}),
    Rung.BUILT: frozenset({EvidenceKind.TEST_NODE}),
    Rung.EXERCISED: frozenset({EvidenceKind.CLOSURE_MODULE}),
    Rung.PROVEN: frozenset({EvidenceKind.CONTRACT_SCHEMA,
                            EvidenceKind.MANIFEST_CAPABILITY}),
    Rung.HARDENED: frozenset({EvidenceKind.EXTERNAL_OUTCOME}),
}


def _cumulative() -> dict[Rung, frozenset[EvidenceKind]]:
    out: dict[Rung, frozenset[EvidenceKind]] = {}
    seen: set[EvidenceKind] = set()
    for rung in RUNG_ORDER:
        seen |= _RUNG_ADDS[rung]
        out[rung] = frozenset(seen)
    return out


RUNG_REQUIREMENTS: dict[Rung, frozenset[EvidenceKind]] = _cumulative()


def required_evidence(rung: Rung) -> frozenset[EvidenceKind]:
    """Every evidence kind a technology must supply to stand at `rung`."""
    try:
        return RUNG_REQUIREMENTS[rung]
    except KeyError as exc:  # pragma: no cover - Rung is a closed enum
        raise LadderError(f"unknown rung {rung!r}") from exc


def rung_index(rung: Rung) -> int:
    return RUNG_ORDER.index(rung)


def rung_at_or_above(rung: Rung, floor: Rung) -> bool:
    return rung_index(rung) >= rung_index(floor)


def highest_supported_rung(kinds: frozenset[EvidenceKind]) -> Rung | None:
    """The highest rung whose full requirement set is covered by `kinds`.

    Returns None when not even BLUEPRINT is supported. This is the only
    function permitted to award a rung, and it awards strictly: eleven of
    twelve is eleven of twelve.
    """
    awarded: Rung | None = None
    for rung in RUNG_ORDER:
        if required_evidence(rung) <= kinds:
            awarded = rung
        else:
            break
    return awarded


def next_rung(rung: Rung | None) -> Rung | None:
    """The rung immediately above `rung`, or None at the top."""
    if rung is None:
        return RUNG_ORDER[0]
    i = rung_index(rung)
    return RUNG_ORDER[i + 1] if i + 1 < len(RUNG_ORDER) else None


def missing_for(rung: Rung, kinds: frozenset[EvidenceKind]) -> frozenset[EvidenceKind]:
    """Exactly which evidence kinds are absent for a claim of `rung`."""
    return required_evidence(rung) - kinds
