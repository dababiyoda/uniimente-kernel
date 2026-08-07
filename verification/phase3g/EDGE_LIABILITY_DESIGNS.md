# LC-2b — edge-scoped liability continuation: nine designs compared

Design comparison only. Nothing here is implemented, and nothing here is
authorized by LC-2a. Read after `EDGE_LIABILITY_DIAGNOSIS.md`.

> **SUPERSEDED BY LC-2b′, BELOW.** The classification this comparison was built
> on was wrong, the error was caught by trying to implement the recommendation,
> and the corrected measurement changes which mechanism is owed. The original
> comparison is preserved rather than rewritten, because the nine designs and
> six axes remain the right frame and the mistake is the more useful record.
> Read §"LC-2b′" at the end first.

## The stranding, classified — WRONG, see LC-2b′

Every one of the 13 stranded edges at `_damaged(3, density=0.6)` seed 5 is an
**adopted** edge whose receiving node is still `status=OPEN`, with the
scheduler queue empty (`events_dispatched 85`, `ready 0`). Nothing is left to
wake them. Three classes:

| class | n | receiver state | reading |
|---|---|---|---|
| **A** | 5 | `outstanding=0 untried=0 tried=0 opened=0 reserve=1.00` | adopted an edge, tried nothing, has nothing left to try, never said so |
| **B** | 7 | `outstanding>=1 inflight=1.00 untried=4..6` | waiting on a child that is itself stranded — cascade from A |
| **C** | 1 | `outstanding=0 untried=5 tried=1 completed=1 reserve=0.00` | credit spent while eligible routes remain |

The split is produced by `classify_stranding()` in the instrument, not read off
by hand — a first pass grouped by `outstanding` alone and reported 6/6/1, which
put the one credit-starved node in with the frontier-empty leaves and hid
exactly the distinction the design turns on.

Class A are the PX-class leaves (`price.2`, `price.5`, `price.8`). Class B
resolves itself the moment A does. Class C is different in kind: it is not
stranded for want of a frontier, it is stranded for want of credit.

**This is where LC-2 and LC-6 meet.** One missing primitive — *a node that can
make no further local progress must discharge its adopted edge with the outcome
that says why* — produces both the stranded liability and the
exhaustion/starvation confusion. Class A's honest outcome is space exhaustion
(`untried == 0`); class C's is budget exhaustion (`untried > 0, reserve == 0`).
The discrimination LC-6's test G demands is `eligible_untried_routes`, which
the node already maintains. LC-0 hypothesised that LC-4, LC-5 and LC-6 might be
one mechanism; the measurement extends that to LC-2 and narrows what the shared
primitive has to be.

## The evaluation axes

1. **Receiver evidence** — does the edge close on what the receiving endpoint
   observed? The 5B split exists because a command is not proof.
2. **Single closure authority** — does it add a second party who may close an
   edge?
3. **Discriminates A from C** — space exhaustion versus credit starvation.
4. **Resolves the cascade** — does B fall out, or need its own machinery?
5. **New message class** — does the wire protocol grow?
6. **Evidence preserved** — is the reason for closure recoverable afterwards?

## The nine

### 1. Opener-side deadline, then self-refund
The opener sets a deadline; on expiry it closes its own edge and reclaims credit.

Fails axis 1 outright. This is precisely the conflation the 5B split removed:
the party owed the answer supplies it. It would also make every stranding
invisible — the ledger would balance while the receiver still believed itself
open, so the two ends would disagree silently, which is worse than the present
state where the disagreement is at least detectable.

### 2. Organ-level reconciler sweep
A worker walks `search_edges` and closes anything unanswered.

Fails axis 2. The organ is not an endpoint of the edge and observed nothing.
This is a second closure authority wearing a maintenance costume, and §5.3 of
the build order puts closure on the canonical path, not beside it.

### 3. Credit TTL / automatic expiry
Allocations carry a lifetime; unspent credit returns when it lapses.

Fails 1 and 6. Credit returns without any statement of what happened, so the
distinction between A and C is destroyed at exactly the moment it becomes
observable. It also converts a *loss* into a *silent balance*, which is the
trade PA-0 explicitly warned against for the pre-arrival window.

### 4. Parent reconciliation probe (pull)
The opener re-probes an unanswered edge; the receiver replies with its current
state.

Satisfies 1 and 2 — the answer still comes from the receiver. Costs a new
message class (axis 5) and, more seriously, does not fix anything by itself: a
class A node asked "what is your state" answers "OPEN", correctly, forever. It
is a diagnostic, not a continuation. Worth keeping as a later *observability*
addition; it is not the mechanism.

### 5. Provisional receipt at adoption
The receiver acknowledges the edge on adoption, and answers again on resolution.

Fails the exactly-one invariant that `_record_outcome` and every LC-2
specification rely on. Two outcomes per edge reintroduces first-wins ambiguity
in a new place, and `_per_key_edge_uniqueness` would have to be weakened to
accept it — weakening a passing invariant to admit a mechanism is the wrong
direction.

### 6. End-of-work-item terminal sweep
When `run_item` drains, every node still OPEN emits on its adopted edge.

Satisfies 1 (the receiver emits) and resolves A. But it locates the decision in
the *driver*, not in the node: closure would then depend on how the harness
happened to run the organ, and a paused or resumed run would produce different
lifecycle records for identical protocol histories. It also cannot resolve B in
one pass — the cascade needs A's answers to already exist — so it needs
iteration to fixpoint inside a driver, which is where quiescence bugs live.

### 7. Canonical Local Frontier Remainder (receiver-side, evaluated per transition)
The node maintains its own remainder — outstanding children, untried eligible
routes, reserve — and whenever a transition leaves the remainder empty it
discharges its adopted edge with the outcome naming *why* it is empty:
`untried == 0` → space exhausted; `untried > 0 and reserve == 0` → budget
exhausted.

Satisfies 1 (the node observed its own frontier), 2 (no new party), 3 (the
distinction is the outcome, not a heuristic), 4 (discharging A schedules its
parent, which re-evaluates, so B falls out by the existing event mechanics), 5
(no new message class — these are existing `CHILD_OUTCOME_KINDS`), and 6 (the
kind records the reason).

Its cost is that "no further local progress" must be evaluated *correctly at
every transition*, and evaluating it too eagerly closes a node that was about
to receive a proposal. That is the real risk and it is testable: the discharge
condition must be false while any child allocation is in flight.

### 8. Scheduler-integrated quiescence hook
Same rule as 7, but evaluated when the scheduler observes the node has no
pending events.

Equivalent in outcome, worse in authority: it makes protocol closure a function
of scheduler state, so a node's lifecycle would depend on dispatch order. The
`unit_id` permutation specification (xfail 11) exists to forbid exactly that
class of dependency.

### 9. Cascade-only: rely on parent cancellation
Do nothing new; when a parent cancels its wave, children close.

Already partially present, and it does not cover the measured case: no parent
cancels here. All 13 edges strand on a run that reaches quiescence without any
cancellation. This is the null design, recorded because "the existing cascade
already handles it" is the assumption the measurement refutes.

## Recommendation

**Design 7**, with design 4 held as a later observability addition and designs
1, 2, 3, 5, 8 rejected on the axes above.

The remainder belongs to the node because the node is the only party that
observed it. Nothing else in the organ can distinguish "this leaf has no
untried route" from "this leaf has not been scheduled yet", and any design that
puts the decision outside the node has to reconstruct that knowledge from
somewhere it does not exist.

## What LC-2c must prove before it is believed

- the discharge condition is **false** while any child allocation is in flight,
  with a fixture that would close early if it were not;
- class A closes with space exhaustion and class C with budget exhaustion, on
  the same run, distinguished by `eligible_untried_routes` and not by which
  test asserted which;
- the cascade resolves B without a sweep, iteration count recorded;
- `_damaged(4, density=1.0)` is **unchanged** — 6 edges, 6 answered, 0 stranded
  — because a mechanism that alters a run which had no defect is doing
  something other than what it claims;
- the formation invariant holds at 16 events / 1012 messages;
- the metric is derived from edge state, per LC-2a finding 3, and a negative
  control strands an edge deliberately and is caught.

---

# LC-2b′ — the correction

Design 7 was implemented and **changed nothing**: 13 stranded before, 13 after.
The runtime change was reverted. That result is what exposed the error above.

## What the stranded nodes actually hold

```
status=OPEN  untried=0  reserve=1.0  opened=[]
eligible_offer=True  local_candidate=set  terminal_signal_sent=False
```

`eligible_offer` is set. These nodes are not frontier-empty — **they proposed
themselves and are waiting for an answer that never comes.** Reclassified with
the proposal test applied before the frontier test:

| class | n | meaning |
|---|---|---|
| **A** | 6 | proposed itself, never answered |
| **A2** | 7 | relayed a proposal, never answered |
| B, C, D | 0 | *none* |

All 13. There is no frontier-exhaustion stranding in this run at all. The
original table read `untried == 0` as "nothing left to try" when it actually
meant "this node stopped expanding because it had already found a candidate".

## Why design 7 could not have worked

`_continue_after_child` refuses to report exhaustion while `eligible_offer`
stands — and it is **right** to refuse, because a candidate is still travelling.
Any mechanism that discharged the adopted edge here would be claiming the search
space is closed while an unresolved proposal is in flight, which is the specific
error that guard exists to prevent. Design 7 was correctly inert.

## Where the defect actually is

`_seal` gives every outstanding proposal a disposition — accepted, or the seal
reason — and writes it into `node["proposal_disposition"]` **at the sealing
node**. The source of a losing proposal is a different unit, on a different
edge, possibly several hops away. Nothing carries the disposition back to it, so
it holds `eligible_offer=True` forever, and with it the parent's committed
credit.

**LC-2's stranded liability is downstream of LC-4's multi-hop disposition
routing.** They are one defect seen from two ends: LC-4 says commit and cancel
must reach the proposal's source edge; LC-2 measures what it costs when they do
not. LC-0's finding on xfail 10 — "the accepted proposal was correlated only at
the root, so multi-hop closure was never exercised" — is the same observation
from the test side.

## Consequence for the execution order

The authorized order runs edge-scoped liability continuation **before**
deterministic multi-hop routing. The measurement inverts that dependency: LC-2
cannot be built first, because the liability it would discharge is held by nodes
that are legitimately waiting, and the thing they wait for is what LC-4 routes.
Per the canonical execution order — *implement the active bottleneck in
dependency order* — LC-4 is the active bottleneck and LC-2 closes behind it.

This is a reordering, not a reduction: nothing in the ladder is dropped.

## What LC-4 must therefore prove

- a losing proposal's disposition reaches its **source node**, not merely the
  sealing node's own dictionary;
- it travels the adopted chain hop by hop, using each relay's own adopted edge —
  the invariant LC-1 already tests and can now be reused rather than restated;
- on arrival the source clears `eligible_offer` and `local_candidate`, which the
  existing path at `deliver_proposal_rejected` already does correctly once the
  message arrives;
- stranded edges at `_damaged(3, density=0.6)` seed 5 fall from 13 toward 0, and
  the residue after routing is re-classified rather than assumed to be zero;
- `_damaged(4, density=1.0)` is unchanged at 6 opened / 6 answered / 0 stranded;
- formation holds at 16 events / 1012 messages.

## Not established

No design is implemented. `substrate/v5.py` is byte-identical to `bc13bc3` —
design 7 was written, measured, found inert, and reverted. All four LC-2
specifications remain strict xfail. Gate F **UNMEASURED**, Gate G
**UNMEASURED**, R8 **PROHIBITED**, no external effect.
