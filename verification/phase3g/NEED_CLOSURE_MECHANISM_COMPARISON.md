# NC-2 — need-closure mechanism: eight designs compared

Design comparison only. Read after `NEED_CLOSURE_CAUSAL_DIAGNOSIS.md`.
`substrate/v5.py` is byte-identical to `bc13bc3` at the time of writing.

## The finding that decides most of this

**The descendant machinery already exists and is already reachable.**
`_close_wave_from_parent` (`substrate/v5.py:2619`) does the whole child side:

```
wave_cancelled guard        applies exactly once; replay returns before the counter
PARENT_CONTROLS_APPLIED     incremented at the single application point
status -> CLOSED            for every non-commit kind
cascade                     SearchCancelled to every outstanding child edge,
                            through this node's OWN child_targets — hop by hop,
                            never a direct write to a distant source
_seal(..., "need_closed")   the reason is ALREADY distinguished from "cancelled"
                            when the inbound kind is SearchNeedClosed
_reconcile_closed_children  closes child edges whose outcome the organ records
_acknowledge_to_parent      reports what became of the credit, only once every
                            child of mine has itself acknowledged
```

So `SearchNeedClosed` is not a kind that needs inventing, and the cascade is not
a mechanism that needs building. **What is missing is the initiation.** No code
path ever emits `SearchNeedClosed` at an abandoned root, because
`_settle_pending_roots` reaches that root and executes a bare `continue`.

That single fact eliminates most of the candidate space on implementation cost
alone, and it means the honest change is small.

## The eight candidates

| | design | verdict |
|---|---|---|
| A | root-local tombstone only | REJECTED |
| B | proposal-rejection fan-out | REJECTED |
| C | generic `SearchCancelled` cascade | REJECTED |
| **D** | **`SearchNeedClosed` causal cascade** | **SELECTED** |
| E | structured-concurrency scope cancellation | FOLDED INTO D |
| F | two-phase distributed abort | REJECTED |
| G | reference-counted obligation tombstone | PARTIALLY FOLDED INTO D |
| H | central supervisor cleanup | REJECTED (baseline) |

### Scored

`stores` = additional truth stores. `global` = global knowledge required.
`amp` = message amplification. Lower is better except where noted.

| axis | A | B | C | **D** | E | F | G | H |
|---|---|---|---|---|---|---|---|---|
| additional truth stores | 0 | 0 | 0 | **0** | 0 | 1 | 1 | 1 |
| generation binding | no | no | no | **yes** | yes | yes | yes | no |
| identity binding | n/a | yes | yes | **yes** | yes | yes | yes | no |
| SearchKey binding | no | yes | yes | **yes** | yes | yes | yes | no |
| credit correctness | **fails** | partial | yes | **yes** | yes | yes | yes | unsafe |
| proposal correctness | fails | partial | partial | **yes** | yes | yes | yes | unsafe |
| replay behaviour | n/a | weak | idempotent | **idempotent** | idempotent | complex | idempotent | none |
| late-message behaviour | n/a | weak | inert | **inert** | inert | ambiguous | inert | none |
| partition behaviour | n/a | n/a | stays open | **stays open** | stays open | blocks | stays open | false close |
| amplification | 0 | ∝proposals | ∝edges | **∝edges** | ∝edges | 2×edges | ∝edges | ∝units |
| memory bound | O(1) | O(props) | O(1) | **O(1)** | O(1) | O(edges) | O(gens) | O(roots) |
| pre-arrival compatible | n/a | no | yes | **yes** | yes | no | yes | no |
| implementation cost | trivial | medium | small | **small** | medium | large | medium | small |
| testability | poor | medium | good | **good** | good | poor | good | poor |
| global knowledge | none | none | none | **none** | none | none | none | **required** |

### Why each loser lost

**A — root-local tombstone only.** The root marks itself closed and nothing
else happens. Descendants never learn, credit never returns, and the observable
state is *worse* than today: the root would report closed while its subtree
still holds 18.0 credit in flight. It converts a visible stranding into an
invisible one, which is the trade PA-0 already rejected for the pre-arrival
window.

**B — proposal-rejection fan-out.** Rejects each outstanding proposal
individually. Misses every branch that never produced a proposal — and at
`_damaged(3, 0.6)` the abandoned roots hold 6 outstanding children against 6
outstanding proposals, so branches without proposals exist. It also says the
wrong thing: a source learns *your candidate lost*, when the truth is *the
obligation no longer exists*. It would have to be followed by a second
mechanism for the childless branches, which is D with extra steps.

**C — generic `SearchCancelled` cascade.** Nearly right, and it is what D's
cascade already degrades to below the first hop. Rejected as the *initiating*
kind only: `_seal` distinguishes `"need_closed"` from `"cancelled"` purely by
the inbound kind, so initiating with `SearchCancelled` would erase the one
recorded fact that separates "this need is gone" from "this wave lost". The
semantic loss is real and it is free to avoid.

**F — two-phase distributed abort.** Prepare, acknowledge readiness, commit.
Doubles amplification, needs a per-edge prepared state, and blocks on a
partitioned child instead of leaving the edge explicitly unresolved. Nothing in
the measured evidence requires atomicity across descendants — closure is not a
transaction, and each edge's outcome is independently owned. Rejected as
unjustified by evidence, not as wrong.

**H — central supervisor cleanup.** A scanner outside the protocol closes
abandoned roots. Requires global knowledge, creates a second closure authority,
and would close on silence — the one inference specification 23 forbids.
Recorded as the conventional baseline it is, and it loses on authority before
it loses on anything else.

### What E and G contribute

**E (structured concurrency)** is the correct *description* of D rather than a
rival: scope completes elsewhere → cancel descendants → join descendant
completions → close. The join is the part D must not skip, and it is why the
root may not go straight to `CLOSED`. Folded in as the state machine.

**G (reference-counted tombstone)** contributes the resurrection guard. Closure
must be bound to `need_id`, which already carries the generation
(`unit:slot:activation`), so a later reopen mints a *different* need_id and a
*different* SearchKey, and the closed node cannot be revived. That property
falls out of the existing identity scheme — no generation registry is needed,
which is why G's separate store is dropped while G's guarantee is kept.

## The selected mechanism

**Generation-bound closure initiation + the existing structured cascade + a
distributed completion join.**

```
OPEN / PROPOSAL_PENDING
        │  obligation generation retired (NC-0 predicate), node holds liability
        ▼
CLOSING_NEED_SATISFIED_ELSEWHERE
        │  every outstanding child edge answered by its own receiver
        ▼
CLOSED
```

`COMMITTED` is not overloaded. An abandoned root did not accept a proposal and
must not claim it did.

**Downward:** `SearchNeedClosed`, on each outstanding child edge, to that
edge's own target, through `_emit_terminal`, which already proves direction and
destination before anything is recorded. Below the first hop the existing
cascade continues as `SearchCancelled`, which is accurate there — a relay's
wave did close — and whether the kind should propagate unchanged is left as a
measurement for NC-3 rather than assumed here.

**Upward:** unchanged. The child's own `_acknowledge_to_parent` and the
edge-outcome channel already carry completion, and `_seal(..., "need_closed")`
already records why. Introducing a new upward kind would add a second way to
say what `search_edge_lifecycle` already says, and the direction rule stays
exactly as it is — channel follows the authenticated endpoint role, never the
kind.

**The join.** The root may leave `CLOSING_NEED_SATISFIED_ELSEWHERE` only when
`children_outstanding` is empty and `child_allocations_in_flight` is zero. A
partitioned child leaves the root in `CLOSING` with the unresolved edge
explicit — no timer, no retry, no completion inferred from silence.

Constraints honoured: existing canonical node and lifecycle; no second global
registry; no timer; no global provider index; deterministic replay preserved by
the existing `wave_cancelled` guard; 2D direction enforcement untouched;
command/outcome separation untouched; external effects zero.

## Two strengthening passes

**Pass 1 — strengthen.** The advantage is that almost none of this is new code:
initiation is the only missing piece, and every hazardous part (authentication,
direction, exactly-once, credit reconciliation, replay) is already built and
already under test. The main disadvantage found in pass 1 is that
`_close_wave_from_parent` sets `CLOSED` immediately, so reusing it wholesale
would close the root before descendants answer and would satisfy specifications
12 and 25 only by accident. Redesigned: the root uses its own initiation that
sets `CLOSING`, and the transition to `CLOSED` is driven by the existing
child-completion path.

**Pass 2 — attack the strengthened design.** Three residual risks.

1. *Closing a root that should stay live.* The predicate reads
   `open_needs[slot] != need_id`, and specifications 17 and 18 already hold
   against unrelated and stale-generation bonds — they are active, not
   pre-registered, so a regression here goes red immediately.
2. *`CLOSING` becoming a permanent state.* If a child never answers, the root
   stays `CLOSING` forever. This is deliberate and is specification 26, but it
   means `CLOSING` must be counted and visible, not silently equivalent to
   closed. The metric therefore reports abandoned roots with open liabilities
   rather than roots "closed".
3. *Initiation firing repeatedly.* `_settle_pending_roots` runs on every step.
   Initiation must be idempotent; the existing `wave_cancelled` /
   `terminal_signal_sent` flags are the guard, and specification 04 counts
   cascades against roots.

Residual risks accepted, each with a named specification. **Verdict: `RETAIN`.**

## Not established

Nothing is implemented. Whether the closure kind should propagate unchanged
below the first hop is an open measurement for NC-3, not an assumption. Gate F
**UNMEASURED**, Gate G **UNMEASURED**, R8 **PROHIBITED**, no external effect.
