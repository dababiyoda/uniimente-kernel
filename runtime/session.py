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
    """What one traversal added, reported against the chain rather than claimed.

    Carries the bridge's **own run object** in `run`, unwrapped and unflattened.
    `BridgeRun`, `VentureRun` and `ExperimentRun` each report things this
    summary does not — rejected branches, granted-versus-requested budget,
    whether a kill condition fired — and a wrapper that dropped them would be
    the silent information loss `adapters/` forbids by name. What is *added*
    here is stated instead: chain growth, causal depth, and the reality flag.
    """

    #: "A", "B" or "C" — which bridge produced `run`.
    bridge: str
    completed: bool
    halted_at: str | None
    reason: str
    event_ids: tuple[str, ...]
    records_before: int
    records_after: int
    #: The bridge's own result, complete. Nothing here is a re-derivation of it.
    run: object
    #: Ancestry depth, where the bridge exposes a walker. Only Bridge A does, so
    #: this is None for B and C rather than a zero that would read as "no
    #: ancestry" — absent and empty are different findings.
    causal_depth: int | None = None
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
        return self._record("A", result, before,
                            causal_depth=len(causal_chain(result, self.runtime.ledger)))

    def traverse_venture_to_experiment(self, assessment: dict, tree, audit, *,
                                       decisive_unknown: str,
                                       selected_branch_id: str,
                                       selection_reason: str,
                                       metric: str, baseline: float,
                                       threshold: float, direction: str,
                                       **kw) -> TraversalRecord:
        """Bridge B over this session's durable ledger.

        `tree` and `audit` are the **caller's analysis** and stay the caller's.
        A session that generated its own strategy tree would be inventing the
        institutional judgement the bridge exists to refuse to proceed without —
        and the measurement parameters are the caller's for the same reason the
        bridge states: nothing can derive a threshold from an assessment, and
        inventing one is the fabricated field `adapters/` forbids.
        """
        from bridges.venture_to_experiment import run

        before = len(self.runtime.ledger.records)
        result = run(assessment, tree, audit,
                     decisive_unknown=decisive_unknown,
                     selected_branch_id=selected_branch_id,
                     selection_reason=selection_reason,
                     metric=metric, baseline=baseline, threshold=threshold,
                     direction=direction, ledger=self.runtime.ledger, **kw)
        return self._record("B", result, before)

    def traverse_experiment_to_reality(self, spec, *, measure, actor=None,
                                       **kw) -> TraversalRecord:
        """Bridge C over this session's durable ledger, gate and passports.

        `actor` defaults to a passport minted from *this session's* registry,
        which is the point: after a restart there is no actor until one is
        issued again, so a caller cannot accidentally carry a stale identity
        across a process boundary by holding on to an id.

        `measure` is the caller's instrument, unchanged. This method mints no
        grant — Bridge C never funds itself, and neither does its composition
        root.
        """
        from bridges.experiment_to_reality import run

        if actor is None:
            actor = self.runtime.passports.issue(
                kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
                legal_principal="alfonso_lopez",
                declared_capabilities=list(spec.required_capabilities),
                budget_ceiling_usd=5.0,
                consequence_class="internal_write").passport_id

        before = len(self.runtime.ledger.records)
        result = run(spec, gate=self.runtime.gate,
                     passports=self.runtime.passports, actor=actor,
                     measure=measure, ledger=self.runtime.ledger, **kw)
        return self._record("C", result, before)

    def _record(self, bridge: str, result, before: int, *,
                causal_depth: int | None = None) -> TraversalRecord:
        return TraversalRecord(
            bridge=bridge,
            completed=result.completed,
            halted_at=result.halted_at.name if result.halted_at else None,
            reason=result.reason,
            event_ids=tuple(result.event_ids),
            records_before=before,
            records_after=len(self.runtime.ledger.records),
            run=result,
            causal_depth=causal_depth)

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
