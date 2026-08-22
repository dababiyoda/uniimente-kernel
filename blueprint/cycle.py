"""Cycle-over-cycle audit of the ladder: did raising a rung unlock anything?

Doctrine (CYCLE AUDIT): a maturity ladder is a scoreboard, and scoreboards get
gamed. PR #71 named the failure mode against its own work and declared a kill
condition for it — *the ladder is killed if a cycle raises rungs without moving
the frontier* — then computed nothing. A kill condition that only exists in
prose cannot fire. This module makes it falsifiable.

The distinction it draws is narrow and worth stating precisely. Raising a
technology's rung is not the same as making the institution more capable. A rung
rises when evidence resolves. Capability rises when a *ceiling* rises — when
something downstream gains headroom it did not have — or when a reconciled
external outcome appears. A cycle that does the first without the second raised
a number.

    SUBSTANTIVE          rungs rose, and something downstream gained headroom
    CEREMONY_SUSPECTED   rungs rose, and nothing did
    REGRESSION           a rung fell; this outranks every other reading
    NO_CHANGE            the tree moved but the ladder did not
    RECALIBRATED         the rules changed, so the rungs are not comparable

Two run-level readings sit beside the per-cycle verdicts. `kill_condition_fired`
catches rungs rising without unlocking. `stall_condition_fired` catches the
opposite and equally stuck case — nothing unlocking at all, cycle after cycle —
which the first reading is blind to, because a cycle that claims no rung cannot
be ceremony by its definition.

RECALIBRATED outranks everything, because it is the one case where the numbers
moved for a reason that is not about the institution at all. When the evidence
standard is tightened — as it was when CLOSURE_MODULE stopped resolving on a
textual registration and began requiring a commit-pinned passing closure report —
rungs can fall with nothing having decayed, and a loosened rule would raise them
with nothing having been built. Reading either as a cycle result would make the
audit lie in the direction of whoever last edited the rules.

CEREMONY_SUSPECTED is a suspicion, not a verdict on the work's worth. A
technology with no dependents can be genuinely valuable and still unlock
nothing — leverage 0 is a fact about the dependency graph, not about quality.
What the reading forbids is *calling that progress on the critical path*.

Two structural honesty properties, both enforced rather than promised:

1. A snapshot is derived from `critical_path.compute()`. There is no code path
   that accepts a rung, a count, or a verdict from a caller. `rung_counts` is a
   property, not a field, so a serialized snapshot cannot disagree with its own
   readings.
2. A snapshot is anchored to a commit and is never overwritten. Re-reading the
   same tree must produce the same answer, so a second snapshot of a commit
   already on record is refused rather than merged — history is appended to, per
   Final Build Order §4.5, never rewritten.

This module reports. It grants nothing, activates nothing, and promotes nothing.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from blueprint.critical_path import compute
from blueprint.evidence import EVIDENCE_STANDARD, KERNEL_ROOT
from blueprint.ladder import RUNG_ORDER, Rung, rung_index

SNAPSHOT_DIR = os.path.join(KERNEL_ROOT, "blueprint", "snapshots")
SCHEMA_VERSION = 2

#: A reading not anchored to a tree is not evidence. Short SHAs are accepted
#: because git prints them, but the anchor must at least look like one.
_COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")
_FILENAME_RE = re.compile(r"^(?P<seq>\d{4})-(?P<commit>[0-9a-f]{7,40})\.json$")

#: How the reading was obtained. A backfilled reading is historical in what it
#: measured and current in what recorded it; conflating the two would let a
#: reconstruction pass as a contemporaneous observation.
PROVENANCE = ("live", "backfill")

#: The absence of a rung. Distinct from the bottom rung: the ladder refuses to
#: round an unsupported claim up to BLUEPRINT, so "nothing resolves" sorts below
#: BLUEPRINT rather than equal to it.
UNSUPPORTED = "UNSUPPORTED"


class SnapshotError(ValueError):
    """A snapshot could not be anchored, or would overwrite the past. Fails closed."""


def _position(awarded: str | None) -> int:
    """Order an awarded rung, with the absence of one sorting below every rung."""
    if awarded is None or awarded == UNSUPPORTED:
        return -1
    return rung_index(Rung(awarded))


# --------------------------------------------------------------------- reading


@dataclass(frozen=True)
class TechnologyReading:
    """One technology as the ladder read it at one commit."""

    technology_id: int
    awarded: str | None
    ceiling: str
    can_advance: bool
    #: The next rung needs a reconciled external consequence, so no build
    #: session can advance it however clear its dependencies are.
    #:
    #: Defaults False so the snapshots written before this distinction existed
    #: still load. Their frontier stays as it was read at that commit, which is
    #: the honest record — rewriting history to match a later instrument would
    #: destroy the very comparison these snapshots exist to support.
    awaiting_external: bool = False

    def __post_init__(self) -> None:
        if self.awarded is not None and self.awarded not in {r.value for r in RUNG_ORDER}:
            raise SnapshotError(
                f"#{self.technology_id} carries {self.awarded!r}, which is not a rung"
            )
        if self.ceiling not in {r.value for r in RUNG_ORDER}:
            raise SnapshotError(
                f"#{self.technology_id} carries ceiling {self.ceiling!r}, not a rung"
            )


@dataclass(frozen=True)
class Snapshot:
    """The whole ladder at one commit. Derived, anchored, and append-only."""

    commit: str
    taken_at: str
    provenance: str
    readings: tuple[TechnologyReading, ...]
    #: The evidence standard in force when these rungs were awarded. Rungs from
    #: different standards are not comparable; `compare` reports RECALIBRATED
    #: rather than pretending a tightened rule is a capability regression.
    standard: str = EVIDENCE_STANDARD
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not _COMMIT_RE.match(self.commit or ""):
            raise SnapshotError(
                f"a snapshot must be anchored to a commit; got {self.commit!r}. "
                "An unanchored ladder reading cannot be reproduced, so it is not "
                "evidence."
            )
        if self.provenance not in PROVENANCE:
            raise SnapshotError(
                f"provenance must be one of {list(PROVENANCE)}; got {self.provenance!r}"
            )
        if not self.readings:
            raise SnapshotError("a snapshot with no readings is not a reading")
        ids = [r.technology_id for r in self.readings]
        if len(set(ids)) != len(ids):
            raise SnapshotError("a snapshot reads each technology once, not twice")

    # Everything below is derived. None of it is stored, so a serialized
    # snapshot has no way to carry a count that contradicts its own readings.
    @property
    def by_id(self) -> dict[int, TechnologyReading]:
        return {r.technology_id: r for r in self.readings}

    @property
    def rung_counts(self) -> dict[str, int]:
        counts = {r.value: 0 for r in RUNG_ORDER}
        counts[UNSUPPORTED] = 0
        for reading in self.readings:
            counts[reading.awarded or UNSUPPORTED] += 1
        return counts

    @property
    def frontier(self) -> frozenset[int]:
        """Work a build session could actually take.

        One definition, shared with `critical_path.frontier`. This used to
        reimplement it as `can_advance` alone, which is a dependency test — so a
        technology whose only remaining rung needs an external consequence
        counted as available work. That matters here more than anywhere: this
        frontier feeds the stall detector, and a permanently-parked technology
        inflating it would mask exactly the stall it exists to catch.
        """
        return frozenset(r.technology_id for r in self.readings
                         if r.can_advance and not r.awaiting_external)

    @property
    def hardened(self) -> frozenset[int]:
        return frozenset(r.technology_id for r in self.readings
                         if r.awarded == Rung.HARDENED.value)

    def to_obj(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "commit": self.commit,
            "taken_at": self.taken_at,
            "provenance": self.provenance,
            "standard": self.standard,
            "readings": [
                {"technology_id": r.technology_id, "awarded": r.awarded,
                 "ceiling": r.ceiling, "can_advance": r.can_advance}
                for r in sorted(self.readings, key=lambda r: r.technology_id)
            ],
        }

    @classmethod
    def from_obj(cls, obj: dict) -> Snapshot:
        version = obj.get("schema_version")
        if version not in (1, SCHEMA_VERSION):
            raise SnapshotError(
                f"snapshot schema version {version!r} is not 1 or {SCHEMA_VERSION}; "
                "refusing to read a format this code does not define"
            )
        # Version 1 predates the standard field. Those readings were taken when
        # CLOSURE_MODULE resolved on textual registration, so their standard is
        # "1" by fact rather than by default. The file is not rewritten: history
        # is read through an adapter, never amended.
        standard = obj.get("standard", "1" if version == 1 else EVIDENCE_STANDARD)
        return cls(
            commit=obj["commit"],
            taken_at=obj["taken_at"],
            provenance=obj["provenance"],
            standard=standard,
            schema_version=version,
            readings=tuple(
                TechnologyReading(
                    technology_id=int(r["technology_id"]),
                    awarded=r["awarded"],
                    ceiling=r["ceiling"],
                    can_advance=bool(r["can_advance"]),
                    awaiting_external=bool(r.get("awaiting_external", False)),
                )
                for r in obj["readings"]
            ),
        )


def take(commit: str, root: str = KERNEL_ROOT, provenance: str = "live") -> Snapshot:
    """Read the ladder at `root` and anchor the reading to `commit`.

    The only way to construct a snapshot of real state. Every field comes from
    `compute()`; nothing is passed in but the anchor.
    """
    report = compute(root)
    readings = tuple(
        TechnologyReading(
            technology_id=status.technology_id,
            awarded=status.awarded_rung.value if status.awarded_rung else None,
            ceiling=status.ceiling.value,
            can_advance=status.can_advance,
            awaiting_external=report.needs_external_reality(status),
        )
        for status in sorted(report.statuses.values(), key=lambda s: s.technology_id)
    )
    return Snapshot(
        commit=commit,
        taken_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        provenance=provenance,
        readings=readings,
    )


# --------------------------------------------------------------------- storage


def _existing(directory: str) -> list[tuple[int, str, str]]:
    """(sequence, commit, path) for every snapshot on record, in order."""
    if not os.path.isdir(directory):
        return []
    out = []
    for name in sorted(os.listdir(directory)):
        match = _FILENAME_RE.match(name)
        if match:
            out.append((int(match.group("seq")), match.group("commit"),
                        os.path.join(directory, name)))
    return sorted(out)


def save(snapshot: Snapshot, directory: str = SNAPSHOT_DIR) -> str:
    """Append a snapshot. Refuses to overwrite, and refuses a duplicate commit.

    Two readings of one tree must agree, so a second reading of a commit
    already on record is either noise or an amendment to the past. Both are
    refused: §4.5 creates new versions and never overwrites.
    """
    on_record = _existing(directory)
    for _, commit, path in on_record:
        if snapshot.commit.startswith(commit) or commit.startswith(snapshot.commit):
            raise SnapshotError(
                f"commit {snapshot.commit} is already on record as "
                f"{os.path.basename(path)}; the past is appended to, not amended"
            )
    seq = (on_record[-1][0] + 1) if on_record else 1
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{seq:04d}-{snapshot.commit[:7]}.json")
    if os.path.exists(path):        # pragma: no cover - guarded by the seq scan
        raise SnapshotError(f"refusing to overwrite {path}")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(snapshot.to_obj(), fh, indent=2, sort_keys=True)
        fh.write("\n")
    return path


def load_all(directory: str = SNAPSHOT_DIR) -> tuple[Snapshot, ...]:
    """Every snapshot on record, oldest first."""
    out = []
    for _, _, path in _existing(directory):
        with open(path, encoding="utf-8") as fh:
            out.append(Snapshot.from_obj(json.load(fh)))
    return tuple(out)


# ------------------------------------------------------------------ comparison


class Verdict(str, Enum):
    NO_CHANGE = "NO_CHANGE"
    RECALIBRATED = "RECALIBRATED"
    SUBSTANTIVE = "SUBSTANTIVE"
    CEREMONY_SUSPECTED = "CEREMONY_SUSPECTED"
    REGRESSION = "REGRESSION"


@dataclass(frozen=True)
class CycleComparison:
    """What one cycle did to the ladder, and whether it unlocked anything."""

    before: str
    after: str
    rungs_raised: tuple[tuple[int, str, str], ...] = ()
    rungs_lowered: tuple[tuple[int, str, str], ...] = ()
    ceilings_raised: tuple[tuple[int, str, str], ...] = ()
    frontier_entered: tuple[int, ...] = ()
    frontier_left: tuple[int, ...] = ()
    outcomes_gained: int = 0
    appeared: tuple[int, ...] = ()
    withdrawn: tuple[int, ...] = ()
    standard_before: str = EVIDENCE_STANDARD
    standard_after: str = EVIDENCE_STANDARD

    @property
    def unlocked(self) -> bool:
        """Did anything downstream gain headroom, or did an outcome land?

        Frontier *departures* deliberately do not count. A technology reaching
        its ceiling leaves the frontier, which looks like movement and is the
        opposite of it.
        """
        return bool(self.ceilings_raised or self.frontier_entered
                    or self.outcomes_gained)

    @property
    def recalibrated(self) -> bool:
        """Did the rules change between these two readings?"""
        return self.standard_before != self.standard_after

    @property
    def verdict(self) -> Verdict:
        if self.recalibrated:
            # A tightened rule lowers rungs without anything having decayed, and
            # a loosened one raises them without anything having been built.
            # Neither is a cycle result, so no other verdict may be inferred.
            return Verdict.RECALIBRATED
        if self.rungs_lowered:
            return Verdict.REGRESSION
        if not self.rungs_raised:
            return Verdict.NO_CHANGE if not self.unlocked else Verdict.SUBSTANTIVE
        return Verdict.SUBSTANTIVE if self.unlocked else Verdict.CEREMONY_SUSPECTED

    @property
    def headline(self) -> str:
        if self.recalibrated:
            return (f"{self.before[:7]} -> {self.after[:7]}  "
                    f"{self.verdict.value}: evidence standard "
                    f"{self.standard_before} -> {self.standard_after}; rungs are "
                    f"not comparable across standards "
                    f"({len(self.rungs_raised)} up, {len(self.rungs_lowered)} down "
                    "under the new rules)")
        return (f"{self.before[:7]} -> {self.after[:7]}  {self.verdict.value}: "
                f"{len(self.rungs_raised)} rung(s) raised, "
                f"{len(self.ceilings_raised)} ceiling(s) raised, "
                f"{len(self.frontier_entered)} entered the frontier, "
                f"{self.outcomes_gained} external outcome(s) gained")


def compare(before: Snapshot, after: Snapshot) -> CycleComparison:
    """Diff two ladder readings. Computes nothing that is not in the snapshots."""
    old, new = before.by_id, after.by_id
    shared = sorted(set(old) & set(new))

    raised, lowered, ceilings = [], [], []
    for tech_id in shared:
        a, b = old[tech_id], new[tech_id]
        if _position(b.awarded) > _position(a.awarded):
            raised.append((tech_id, a.awarded or UNSUPPORTED, b.awarded or UNSUPPORTED))
        elif _position(b.awarded) < _position(a.awarded):
            lowered.append((tech_id, a.awarded or UNSUPPORTED, b.awarded or UNSUPPORTED))
        if rung_index(Rung(b.ceiling)) > rung_index(Rung(a.ceiling)):
            ceilings.append((tech_id, a.ceiling, b.ceiling))

    return CycleComparison(
        before=before.commit,
        after=after.commit,
        rungs_raised=tuple(raised),
        rungs_lowered=tuple(lowered),
        ceilings_raised=tuple(ceilings),
        frontier_entered=tuple(sorted((after.frontier - before.frontier) & set(shared))),
        frontier_left=tuple(sorted((before.frontier - after.frontier) & set(shared))),
        outcomes_gained=len(after.hardened) - len(before.hardened),
        appeared=tuple(sorted(set(new) - set(old))),
        withdrawn=tuple(sorted(set(old) - set(new))),
        standard_before=before.standard,
        standard_after=after.standard,
    )


def history(snapshots: tuple[Snapshot, ...] | None = None,
            directory: str = SNAPSHOT_DIR) -> tuple[CycleComparison, ...]:
    """Every consecutive comparison on record."""
    snaps = load_all(directory) if snapshots is None else snapshots
    return tuple(compare(a, b) for a, b in zip(snaps, snaps[1:]))


#: How many consecutive cycles may pass without anything downstream gaining
#: headroom before the run is called a stall. Preparatory cycles are legitimate —
#: building an instrument, recording a decision, tightening a gate — so the
#: threshold is deliberately looser than the ceremony one. Five in a row is no
#: longer a run of preparation.
STALL_THRESHOLD = 5


def consecutive_without_unlock(comparisons: tuple[CycleComparison, ...]) -> int:
    """Trailing cycles in which nothing downstream gained headroom.

    The blind spot this closes. `kill_condition_fired` only fires when rungs
    *rise* without unlocking, so a project where rungs never rise at all reads as
    permanently healthy: NO_CHANGE, NO_CHANGE, NO_CHANGE. The instrument reported
    all-clear through thirteen consecutive cycles in which no ceiling rose, no
    technology entered the frontier and no external outcome landed.

    A cycle that raises no rung is not thereby innocent. Building the measuring
    apparatus is worth doing and does not move the thing being measured, and a
    long enough run of it is a stall whatever the commit log says.
    """
    run = 0
    for comparison in reversed(comparisons):
        if comparison.unlocked:
            break
        run += 1
    return run


def stall_condition_fired(comparisons: tuple[CycleComparison, ...],
                          threshold: int = STALL_THRESHOLD) -> bool:
    """Has the institution gone `threshold` cycles without unlocking anything?

    Reported, never acted on — the same discipline as the kill condition. Only a
    raised ceiling or a reconciled external outcome clears it; no amount of
    further internal work will.
    """
    return consecutive_without_unlock(comparisons) >= threshold


def consecutive_ceremony(comparisons: tuple[CycleComparison, ...]) -> int:
    """How many cycles in a row raised rungs and unlocked nothing, most recent first."""
    run = 0
    for comparison in reversed(comparisons):
        if comparison.verdict is Verdict.CEREMONY_SUSPECTED:
            run += 1
        else:
            break
    return run


def kill_condition_fired(comparisons: tuple[CycleComparison, ...],
                         threshold: int = 2) -> bool:
    """The condition PR #71 declared against its own instrument.

    *"If two consecutive cycles raise rungs without raising the frontier, the
    ladder is measuring test-writing, not capability."* Reported, never acted
    on: killing an instrument is a founder decision, not a computation.
    """
    return consecutive_ceremony(comparisons) >= threshold


# ------------------------------------------------------------------- git anchor


def head_commit(root: str = KERNEL_ROOT) -> str:
    """Resolve HEAD by reading `.git`. No subprocess, no network.

    Raises rather than guessing. A caller that cannot determine the commit must
    pass one explicitly instead of recording an unanchored reading.
    """
    dot_git = os.path.join(root, ".git")
    if os.path.isfile(dot_git):                     # a worktree points elsewhere
        with open(dot_git, encoding="utf-8") as fh:
            gitdir = fh.read().strip()
        if not gitdir.startswith("gitdir:"):
            raise SnapshotError(f"{dot_git} is not a gitdir pointer")
        dot_git = gitdir.split(":", 1)[1].strip()
    if not os.path.isdir(dot_git):
        raise SnapshotError(f"no git metadata at {dot_git}")

    with open(os.path.join(dot_git, "HEAD"), encoding="utf-8") as fh:
        head = fh.read().strip()
    if not head.startswith("ref:"):
        if _COMMIT_RE.match(head):
            return head
        raise SnapshotError(f"unreadable HEAD: {head!r}")

    ref = head.split(":", 1)[1].strip()
    # A worktree's refs live in the *common* directory, one level up from its gitdir.
    for base in (dot_git, os.path.dirname(os.path.dirname(dot_git))):
        loose = os.path.join(base, ref)
        if os.path.isfile(loose):
            with open(loose, encoding="utf-8") as fh:
                return fh.read().strip()
        packed = os.path.join(base, "packed-refs")
        if os.path.isfile(packed):
            with open(packed, encoding="utf-8") as fh:
                for line in fh:
                    parts = line.split()
                    if len(parts) == 2 and parts[1] == ref:
                        return parts[0]
    raise SnapshotError(f"cannot resolve {ref} under {dot_git}")


# -------------------------------------------------------------------------- CLI


_RULE = "=" * 78


def _print_history(comparisons: tuple[CycleComparison, ...],
                   snapshots: tuple[Snapshot, ...]) -> None:
    print(_RULE)
    print("LADDER CYCLE AUDIT — did raising a rung unlock anything?")
    print(_RULE)
    if not snapshots:
        print("\nNo snapshots on record. Take one with:")
        print("    python -m blueprint.cycle take")
        return

    print(f"\n{len(snapshots)} snapshot(s) on record:\n")
    for snap in snapshots:
        counts = snap.rung_counts
        print(f"  {snap.commit[:7]}  {snap.taken_at}  {snap.provenance:<8} "
              f"std={snap.standard}  frontier={len(snap.frontier):<3} "
              f"HARDENED={len(snap.hardened)}  UNSUPPORTED={counts[UNSUPPORTED]}")

    if not comparisons:
        print("\nOne snapshot is not a cycle. Nothing to compare yet.")
        return

    print(f"\n{len(comparisons)} cycle(s):\n")
    for comparison in comparisons:
        print(f"  {comparison.headline}")
        for tech_id, was, now in comparison.rungs_raised:
            print(f"        rung   #{tech_id:<3} {was} -> {now}")
        for tech_id, was, now in comparison.rungs_lowered:
            print(f"        FELL   #{tech_id:<3} {was} -> {now}")
        for tech_id, was, now in comparison.ceilings_raised:
            print(f"        ceil   #{tech_id:<3} {was} -> {now}")
        if comparison.frontier_entered:
            print(f"        opened {list(comparison.frontier_entered)}")
        if comparison.frontier_left:
            print(f"        closed {list(comparison.frontier_left)} "
                  "(reached its ceiling; not progress downstream)")

    stalled = consecutive_without_unlock(comparisons)
    if stall_condition_fired(comparisons):
        print(f"\n{_RULE}")
        print(f"STALL — {stalled} consecutive cycles unlocked nothing downstream.")
        print("No ceiling rose, nothing entered the frontier, no external outcome")
        print("landed. Preparatory work is legitimate and this is longer than a run")
        print("of preparation. Only a raised ceiling or a reconciled external")
        print("outcome clears this; more internal building will not.")

    run = consecutive_ceremony(comparisons)
    print(f"\n{_RULE}")
    if kill_condition_fired(comparisons):
        print(f"KILL CONDITION FIRED — {run} consecutive CEREMONY_SUSPECTED cycles.")
        print("PR #71 declared: if two consecutive cycles raise rungs without")
        print("raising the frontier, the ladder is measuring test-writing rather")
        print("than capability. Retiring or reworking the instrument is a founder")
        print("decision. This report does not make it.")
    elif run:
        print(f"{run} consecutive CEREMONY_SUSPECTED cycle(s); the kill condition "
              "fires at 2.")
    else:
        print("Kill condition not fired.")
    print(_RULE)
    print("This report describes institutional state. It grants nothing, "
          "activates nothing,")
    print("and kills nothing.")


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m blueprint.cycle",
        description="Cycle-over-cycle audit of the hardening ladder.")
    parser.add_argument("command", nargs="?", default="history",
                        choices=("history", "take"),
                        help="history (default): every cycle on record. "
                             "take: append a snapshot of the current tree.")
    parser.add_argument("--commit", default=None,
                        help="anchor for `take`; defaults to HEAD read from .git")
    parser.add_argument("--root", default=KERNEL_ROOT,
                        help="tree to read the ladder from")
    parser.add_argument("--out", default=SNAPSHOT_DIR,
                        help="snapshot directory to append to")
    parser.add_argument("--provenance", default="live", choices=PROVENANCE,
                        help="live: read at this commit now. "
                             "backfill: a historical tree read after the fact.")
    args = parser.parse_args(argv)

    if args.command == "take":
        commit = args.commit or head_commit(args.root)
        snapshot = take(commit, root=args.root, provenance=args.provenance)
        path = save(snapshot, args.out)
        counts = snapshot.rung_counts
        print(f"recorded {os.path.relpath(path, KERNEL_ROOT)}")
        print(f"  commit      {snapshot.commit}")
        print(f"  provenance  {snapshot.provenance}")
        print(f"  frontier    {len(snapshot.frontier)}")
        print(f"  HARDENED    {len(snapshot.hardened)}")
        print(f"  rungs       {counts}")
        return 0

    snapshots = load_all(args.out)
    _print_history(history(snapshots), snapshots)
    return 0


if __name__ == "__main__":           # pragma: no cover - CLI entry
    raise SystemExit(main())
