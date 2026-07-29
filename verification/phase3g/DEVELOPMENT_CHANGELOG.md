# Phase 3G development changelog

Development is the only phase in which defects may be found and repaired.
Every run is preserved. No result here is a gate claim.

| Run | Mechanism change | success | amplification | notes |
|---|---|---|---|---|
| R1 | first experiment layer | 27/48 | 52.29 | episode 0 dispatched exactly 3000 events |
| R2 | edge-triggered readiness; hop budgets; need-generation closure | 21/48 | 47.65 | spin fixed (max 79 events); success fell because R1's "successes" included spinning episodes |
| R3 | evidence-selected repair frontier + iterative widening; isolated twin probe; **relay routing** | 17/48 | **1.94** | amplification threshold met |

## R2 — edge-triggered readiness

`_deliver()` scheduled any fully bonded, unproduced unit after every event. A
unit whose pull returned `NotYet` produced nothing and was immediately
requeued, spinning to `max_events`. Readiness is now edge-triggered: scheduled
only on the transition from unmet to satisfied.

Two failed attempts, recorded rather than hidden:

- capping relay fanout at 3 neighbours stopped needs reaching any producer and
  broke formation entirely (0/48 healthy). Reverted.
- a hop budget of 6 was below the contract chain depth of 7 and also broke
  formation. Set from the structure: 40 formation, 14 repair.

## R3 — local bounded routing

Three changes, and one wrong hypothesis:

1. **Evidence-selected frontier.** During ordinary formation each unit records,
   per required type, which neighbours returned offers and which of those
   settled. On repair it starts from neighbours it has itself seen settle,
   excluding the failed route, and widens one ring at a time against a search
   budget. No provider index, no target topology.

2. **Isolated twin probe.** The pre-repair semantic-loss probe previously ran on
   the scored organ, mutating receipts, messages, memory, produced values and
   need state. It now runs on a twin rebuilt from the same seed with the same
   victim and damage, repair prohibited, then discarded.

   **My hypothesis that the probe was inflating amplification was wrong.**
   Isolating it left amplification at 47.06.

3. **Relay routing — the actual cause.** Bounding only the *originating*
   emission left every intermediate unit forwarding a relayed need to all its
   neighbours. Relays are now routed through the same evidence frontier.
   Amplification 47.06 -> 1.94.

## Outstanding before freeze

- restoration 17/48; the dominant remaining failure is a settled replacement
  that does not complete downstream re-execution within the work item;
- three staged damage classes still NOT EXERCISED: `stale_supplier_return`,
  `repeated_failure_across_two_repairs`, `supplier_returns_during_cooldown`;
- the runner does not yet refuse to run on a dirty working tree.
