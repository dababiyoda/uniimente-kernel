"""State migration: `cursor: int` <-> `completed_steps + next_step`.

The adapter rules in the build order §8 require every adapter to declare its
field mapping, information lost, information added, assumptions, validation,
failure behavior and rollback. All of that is stated here and asserted by tests
rather than left in prose.

THE ASSUMPTION THAT MATTERS: step names are unique within a workflow. When they
are not, the reverse migration is genuinely ambiguous — a name maps to more than
one index — and this module REFUSES. A migration that guesses is worse than one
that stops, because the guess silently re-executes or skips real work.
"""
from __future__ import annotations

from dataclasses import dataclass, field

#: Declared per build order §8. Read by the evidence record, not decoration.
ADAPTER_DECLARATION = {
    "source_contract": "workflow-checkpoint-w0 (cursor: int)",
    "destination_contract": "workflow-checkpoint-w2 (completed_steps + next_step)",
    "field_mapping": {
        "cursor -> completed_steps": "names of steps[:cursor]",
        "cursor -> next_step": "steps[cursor].name, or null at the end",
        "workflow_id/status/state/note/actor/legal_principal/at": "carried verbatim",
    },
    "information_added": "step NAMES, taken from the declared step list — never "
                         "invented, and unavailable from the W0 payload alone",
    "information_lost": "none, when step names are unique",
    "assumptions": ["step names are unique within a workflow",
                    "the step list at migration time is the step list that "
                    "produced the checkpoint"],
    "validation": "pre-append, via evolution.migration.schema",
    "failure_behavior": "refuse; leave the source checkpoint untouched; append a "
                        "rejection record instead of a migrated one",
    "rollback": "reverse migration back to cursor, or simply resume the original "
                "engine from the untouched source checkpoint",
    "lineage": "Package 4, base commit 5e02e47",
}

#: Keys that must survive in both directions. Losing one is state loss.
REQUIRED_CARRIED_KEYS = ("workflow_id", "status", "state", "note", "actor",
                         "legal_principal", "at")


class MigrationRefused(ValueError):
    """The migration will not proceed. Fails closed; nothing was written."""


@dataclass
class MigrationResult:
    payload: dict | None
    ambiguous: bool = False
    reason: str = ""
    lost_keys: tuple = ()
    records_migrated: int = 0
    steps: int = 0
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"ambiguous": self.ambiguous, "reason": self.reason,
                "lost_keys": sorted(self.lost_keys),
                "records_migrated": self.records_migrated,
                "migration_steps": self.steps, "notes": list(self.notes),
                "payload": self.payload}


def _duplicate_names(step_names) -> list[str]:
    seen, dupes = set(), []
    for name in step_names:
        if name in seen and name not in dupes:
            dupes.append(name)
        seen.add(name)
    return dupes


def forward(payload: dict, step_names) -> MigrationResult:
    """W0 -> W2. Position by index becomes position by name."""
    names = list(step_names)
    cursor = payload.get("cursor")

    if not isinstance(cursor, int) or not (0 <= cursor <= len(names)):
        return MigrationResult(
            payload=None, ambiguous=True,
            reason=f"cursor {cursor!r} does not resolve against {len(names)} steps")

    dupes = _duplicate_names(names)
    if dupes:
        # Forward alone would survive duplicates, but the migration is only
        # useful if it can come back. Refusing here rather than at the reverse
        # means the bad state never exists in the first place.
        return MigrationResult(
            payload=None, ambiguous=True,
            reason=f"duplicate step names {dupes} make the reverse migration "
                   f"ambiguous; refusing rather than guessing")

    migrated = {k: payload[k] for k in REQUIRED_CARRIED_KEYS if k in payload}
    lost = tuple(k for k in REQUIRED_CARRIED_KEYS if k not in migrated)
    migrated["completed_steps"] = names[:cursor]
    migrated["next_step"] = names[cursor] if cursor < len(names) else None

    return MigrationResult(
        payload=migrated, lost_keys=lost, records_migrated=1, steps=1,
        notes=[f"cursor {cursor} -> completed {names[:cursor]}, "
               f"next {migrated['next_step']!r}"])


def reverse(payload: dict, step_names) -> MigrationResult:
    """W2 -> W0. The direction where ambiguity would silently corrupt work."""
    names = list(step_names)
    dupes = _duplicate_names(names)
    if dupes:
        return MigrationResult(
            payload=None, ambiguous=True,
            reason=f"duplicate step names {dupes}: a name maps to more than one "
                   f"index, so the cursor cannot be recovered without guessing")

    nxt = payload.get("next_step", "__missing__")
    if nxt == "__missing__":
        return MigrationResult(payload=None, ambiguous=True,
                               reason="no next_step to reverse")
    if nxt is None:
        cursor = len(names)
    elif nxt in names:
        cursor = names.index(nxt)
    else:
        return MigrationResult(
            payload=None, ambiguous=True,
            reason=f"next_step {nxt!r} is not a declared step")

    # Cross-check against completed_steps: the two must agree, or the checkpoint
    # is internally inconsistent and reversing it would launder the corruption.
    completed = payload.get("completed_steps")
    if completed is not None and list(completed) != names[:cursor]:
        return MigrationResult(
            payload=None, ambiguous=True,
            reason=f"completed_steps {list(completed)} disagrees with the "
                   f"position implied by next_step ({names[:cursor]})")

    restored = {k: payload[k] for k in REQUIRED_CARRIED_KEYS if k in payload}
    lost = tuple(k for k in REQUIRED_CARRIED_KEYS if k not in restored)
    restored["cursor"] = cursor
    return MigrationResult(payload=restored, lost_keys=lost, records_migrated=1,
                           steps=1, notes=[f"next {nxt!r} -> cursor {cursor}"])


def round_trip(payload: dict, step_names) -> MigrationResult:
    """Forward then reverse. Must return the original exactly, or it is lossy.

    This is the compatibility gate: a migration that cannot round-trip is not
    allowed to activate, because rollback would not restore the prior state.
    """
    fwd = forward(payload, step_names)
    if fwd.payload is None:
        return fwd
    back = reverse(fwd.payload, step_names)
    if back.payload is None:
        return back

    differences = {k for k in set(payload) | set(back.payload)
                   if payload.get(k) != back.payload.get(k)}
    if differences:
        return MigrationResult(
            payload=None, ambiguous=True,
            reason=f"round trip is lossy; fields differ: {sorted(differences)}",
            lost_keys=tuple(differences))
    return MigrationResult(payload=back.payload, records_migrated=1, steps=2,
                           notes=["round trip exact"])
