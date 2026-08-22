"""Bridge E — Learning-to-Evolution, as an adapter rather than a second loop.

The doctrine's Bridge E is measured bottleneck -> eleven strategy branches ->
isolated tests -> failure analysis -> strict baseline comparison ->
ImprovementProposal -> human authorization -> mediated configuration change ->
retain, regress or kill.

**Almost all of that already exists** in `evolution.loop.ClosureLoop.run_cycle`:
the tree with preserved losers, the Spider-Web gate, the compiler, the verifier
with its promotion floor, the baseline comparison, and the retain/regress/kill
decision recorded in a capsule. Writing a `bridges/learning_to_evolution.py`
that redid any of it would be the uncontrolled duplication section 9 forbids.
So this module builds the one piece that is genuinely missing, and leaves the
loop alone.

## The finding

`ClosureLoop.run_cycle` takes an `executor` and calls it directly:

    measured, outcome_class = executor(spec)

Neither `evolution/loop.py` nor `evolution/auto_cycle.py` references the
Consequence Gate anywhere. So the institution's *self-improvement* loop — the
one deciding whether a change to the institution is RETAINed — is the single
path that does not cross the institution's own gate. Section 5.3 says every
external side effect crosses the canonical gate; the evolution loop's executor
is unmediated, and `assurance.side_effects` has been classifying it as such
without anyone reading the classification as the sentence it is.

## What this module does about it

`gate_mediated(...)` returns an executor with exactly the signature
`run_cycle` already expects, so an existing loop becomes governed by passing one
extra argument. Nothing in `evolution/` changes, the unmediated path is
preserved as section 2 requires, and the choice becomes visible at the call site
instead of implicit in its absence.

The property that makes this worth having, rather than a wrapper for its own
sake: **a refused gate must never become a measurement.** `run_cycle` compares
whatever number it receives against the baseline and can emit RETAIN — a
promotion decision. An executor that returned, say, 0.0 on refusal would let a
*refused* action produce a retain-or-regress verdict computed from a number
nobody measured. So this raises `CycleRefused`, which is the exception
`run_cycle` already raises for every other kind of refusal, and the cycle stops
where it should.
"""
from __future__ import annotations

from bridges import experiment_to_reality as bridge_c
from evolution.loop import CycleRefused

#: `ClosureLoop.run_cycle` maps this to KILL. Reserved for a real harm signal,
#: never produced by a refusal — a refusal is an absence of evidence, and KILL
#: is a finding.
HARM = "harm"


def gate_mediated(*, gate, passports, actor: str, measure, ledger,
                  outcome_class: str = "benefit",
                  standing_grant: dict | None = None,
                  target: str | None = None):
    """An executor for `ClosureLoop.run_cycle` that crosses the Consequence Gate.

    Returns `(measured, outcome_class)` — the exact shape `run_cycle` expects —
    so a caller governs an existing cycle by passing this instead of a bare
    callable, and changes nothing else.

    `measure` is the real instrument, and it runs inside the gate's executor
    slot rather than around it: identity, policy, capability, budget, witness
    and commit-time revalidation all happen before it is called, and the receipt
    binds what it produced.

    Raises `CycleRefused` when the gate refuses. That is deliberate and is the
    whole point of the adapter — see the module docstring. Returning a number
    would let a refused action reach a RETAIN.
    """
    def executor(spec):
        run = bridge_c.run(spec, gate=gate, passports=passports, actor=actor,
                           measure=measure, ledger=ledger, target=target,
                           standing_grant=standing_grant)
        if not run.completed:
            raise CycleRefused(
                f"consequence gate refused the evolution experiment: "
                f"{run.halted_at.value if run.halted_at else 'unknown'} — {run.reason}. "
                f"No measurement was taken, so no retain, regress or kill verdict "
                f"may be computed from one.")
        return run.measured, outcome_class

    return executor
