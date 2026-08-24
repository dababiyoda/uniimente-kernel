"""A composition root: something that actually boots and then does work.

`runtime/__init__.py` composes the institution. This is the first caller that
*uses* one — the difference between building a capability and adopting it, which
is the distinction the whole `identity/pki/` sequence was held to and which this
module exists to satisfy rather than assert.

Before this, `bridges.signal_to_venture.run` was handed a fresh in-memory
`EvidenceLedger` on every call, so a traversal's evidence died with the process
that produced it. Bridge A had always *accepted* an injected ledger; nothing had
ever injected a durable one. Now:

    python -m runtime var/institution --rehearse
    python -m runtime var/institution        # the traversal is still there

The second command reads back the first command's four events, their causal
ancestry and the verified chain, from a different process.

## What a session holds, and for how long

Same asymmetry as `boot`, one layer up:

    the ledger, spine, causal memory    durable, shared across sessions
    the identity mesh                   re-minted per session

`InternalMesh` issues one workload certificate per declared service. Those are
short-lived credentials for exactly the reason passports are, so a session mints
its own rather than reloading anyone else's. A session shares one mesh across
its traversals — which is what `signal_to_venture.run`'s `mesh` parameter was
for — and lets that mesh die with the session.

## Not an autonomous loop

`traverse` runs when called. Nothing here schedules, retries, polls, or runs
unattended, and a traversal on fixtures is a rehearsal: it produces no external
consequence, and `BridgeRun` says so in its own type rather than leaving a
reader to infer it.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from runtime import InstitutionalRuntime

__all__ = ["Session", "FIXTURE_PACKET", "FIXTURE_ASSESSMENT"]

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FIXTURES = os.path.join(_ROOT, "tests", "fixtures")
FIXTURE_PACKET = os.path.join(_FIXTURES, "wire_opportunity_packet.json")
FIXTURE_ASSESSMENT = os.path.join(_FIXTURES, "wire_venture_assessment.json")


@dataclass(frozen=True)
class TraversalRecord:
    """What one traversal added, reported against the chain rather than claimed."""

    completed: bool
    halted_at: str | None
    reason: str
    event_ids: tuple[str, ...]
    causal_depth: int
    records_before: int
    records_after: int
    #: Always False. A fixture traversal is a rehearsal; nothing external moved.
    proves_external_reality: bool = False


class Session:
    """One booted institution, driving real cross-organ work."""

    def __init__(self, runtime: InstitutionalRuntime, mesh=None):
        from identity.mesh import InternalMesh

        self.runtime = runtime
        #: Re-minted per session, never reloaded. See the module docstring.
        self.mesh = mesh or InternalMesh()

    @classmethod
    def open(cls, state_dir, *, env: str = "development") -> "Session":
        return cls(InstitutionalRuntime.boot(state_dir, env=env))

    # ------------------------------------------------------------- traversal
    def traverse_signal_to_venture(self, packet: dict, assessment: dict, *,
                                   answers: dict | None = None) -> TraversalRecord:
        """Bridge A over this session's durable ledger and shared mesh.

        The one line that matters: `ledger=self.runtime.ledger`. Everything the
        traversal learns lands in a chain that outlives the process.
        """
        from bridges.signal_to_venture import KERNEL, causal_chain, run

        before = len(self.runtime.ledger.records)
        result = run(packet, assessment,
                     ledger=self.runtime.ledger, mesh=self.mesh,
                     resolver_answers=answers or {"governing_bottleneck": "buyer access"},
                     resolved_by=KERNEL)
        return TraversalRecord(
            completed=result.completed,
            halted_at=result.halted_at.name if result.halted_at else None,
            reason=result.reason,
            event_ids=tuple(result.event_ids),
            causal_depth=len(causal_chain(result, self.runtime.ledger)),
            records_before=before,
            records_after=len(self.runtime.ledger.records))

    def rehearse(self) -> TraversalRecord:
        """One traversal on the committed wire fixtures. Consequence-inert."""
        with open(FIXTURE_PACKET, encoding="utf-8") as handle:
            packet = json.load(handle)
        with open(FIXTURE_ASSESSMENT, encoding="utf-8") as handle:
            assessment = json.load(handle)
        return self.traverse_signal_to_venture(packet, assessment)

    # ----------------------------------------------------------------- recall
    def history(self) -> list[dict]:
        """Every spine event in the chain, including earlier processes'."""
        return [{"event_id": e.event_id, "type": e.type, "source": e.source}
                for e in self.runtime.spine.replay()]

    def close(self, *, sealed_by: str, reason: str):
        return self.runtime.shutdown(sealed_by=sealed_by, reason=reason)
