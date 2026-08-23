"""Is the institution healthy *now*? — the live counterpart to a sealed experiment.

`evolution/repair/spec.py` is a historical experiment. Under DEC-OM-002 Option A
it now reads the byte-identical freeze-time corpus, so it answers exactly one
question: **can the Package 3 run be reproduced?**

That remedy has an adversarial weakness the founder named when approving it: a
frozen experiment that always passes could be mistaken for evidence that the
live institution is fine. It is not evidence of that and never was — it stopped
looking at the live institution the moment it was repointed.

This module is the other half. It reads the **live** `organs/` directory through
the **live** linker and reports what is actually there. It deliberately does not
import a single expectation from the sealed spec:

- it never asserts `unresolved_count == 7`;
- it has no pass/fail seal;
- it holds no frozen table.

Those absences are the design. The historical expectation of 7 described the
three manifests published at one commit. More organs are published now, and a
live check that demanded 7 would be re-running the sealed experiment under a
different name — which is the confusion the founder ruled must never be
possible.

Deliberately, no count of organs appears in this docstring. The reading below
reports whatever is actually on disk; a number written into prose here would be
one more thing that drifts silently, which is the family of defect this module
exists to answer.

## What a reading means

`unresolved` rows are **not defects**. The linker reports fields it cannot
resolve rather than inventing them, so a growing count usually means the
institution grew, not that it broke. The health signal is in the *kind* of
finding: an untyped edge, an unproduced contract or an overlapping authority is
a structural problem; an unresolved field is an open question with an owner.

A caller wanting a verdict has to look at the report and decide. This module
refuses to collapse that into a number, because a single green light over six
organs is exactly the kind of summary that hides the thing worth seeing.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from linker.linker import InstitutionalLinker
from linker.manifest import load_all

KERNEL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIVE_ORGANS = os.path.join(KERNEL_ROOT, "organs")


@dataclass(frozen=True)
class LiveReading:
    """What the live institution looks like right now. No verdict attached."""

    organ_count: int
    edges: int
    unresolved: int
    #: Structural findings. Unlike `unresolved`, each of these is a real defect:
    #: something is produced that nothing types, consumed that nothing produces,
    #: or claimed by two organs at once.
    untyped: tuple[str, ...]
    unproduced: tuple[str, ...]
    unconsumed: tuple[str, ...]
    overlapping_authority: tuple[tuple[str, str], ...]
    fully_connected: bool

    @property
    def structural_findings(self) -> int:
        """The count that would mean something is wrong, as opposed to open."""
        return (len(self.untyped) + len(self.unproduced)
                + len(self.overlapping_authority))

    @property
    def headline(self) -> str:
        return (f"{self.organ_count} organs, {self.edges} typed edges, "
                f"{self.unresolved} unresolved fields, "
                f"{self.structural_findings} structural findings")


def read(organs_dir: str = LIVE_ORGANS) -> LiveReading:
    """Read the live institution. Never compares against a frozen expectation."""
    manifests = load_all(organs_dir)
    report = InstitutionalLinker(manifests).link()
    return LiveReading(
        organ_count=len(manifests),
        edges=len(report.edges),
        unresolved=len(report.unresolved),
        untyped=tuple(sorted(report.untyped)),
        unproduced=tuple(sorted(report.unproduced)),
        unconsumed=tuple(sorted(report.unconsumed)),
        overlapping_authority=tuple(sorted(report.overlapping_authority)),
        fully_connected=report.fully_connected)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI entry
    """`python -m evolution.repair.live_health`"""
    reading = read()
    print("=" * 74)
    print("LIVE INSTITUTION HEALTH — organs/ as it stands today")
    print("=" * 74)
    print(f"  {reading.headline}")
    print()
    print(f"  organs                 {reading.organ_count}")
    print(f"  typed edges            {reading.edges}")
    print(f"  unresolved fields      {reading.unresolved}   (open questions, not defects)")
    print(f"  untyped edges          {len(reading.untyped)}")
    print(f"  unproduced contracts   {len(reading.unproduced)}")
    print(f"  overlapping authority  {len(reading.overlapping_authority)}")
    print(f"  fully connected        {reading.fully_connected}")

    if reading.overlapping_authority:
        print()
        print("  overlapping authority:")
        for organ, claim in reading.overlapping_authority:
            print(f"    {organ} -> {claim}")

    print()
    print("This is the LIVE institution. It carries no frozen expectation and no")
    print("seal. The sealed Package 3 experiment answers a different question —")
    print("whether a historical run reproduces — and neither reading may be")
    print("presented as the other.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
