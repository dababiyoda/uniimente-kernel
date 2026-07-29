# Phase 3G restoration-lifecycle trace

Traced at head `e254dc0`, development episode 0 (`supplier_disappearance`),
before any mechanism change.

## The stated hypothesis is FALSIFIED

> A replacement bond can settle without causing the replacement supplier to
> execute for the current work item.

Not what happens. In the same episode, one affected consumer completed the
whole path:

```
verify.7  bonds={0: receive.3}   receipts: settled(receive.0) -> reopened
                                            -> settled(receive.3)
          produced this item: yes
```

Settlement → activation → production works. `receive.3` was a previously
unused alternative, it settled, it executed, and `verify.7` produced.

## The actual causal break

The other affected consumer never settled anything:

```
verify.1  bonds={}   open_needs={0: 'verify.1:0:1'}
          requires: CLEAN
          refused:  ['receive.0']
          search tried:   ['@env', '@sink', 'authorise.12']
          offers received: 0
          credits left:    15.0 of 18
          expansion round: 0
```

`verify.1`'s only CLEAN-producing neighbour is `receive.0` — the unit that just
failed and is now refused. Its route memory holds exactly one entry, for
`receive.0`. With that excluded the evidence frontier is empty, so the fallback
took the first three neighbours in id order — `@env`, `@sink`, `authorise.12` —
none of which produce CLEAN.

It then had 15 unspent credits and never widened.

**Why it never widened:** `widen()` is called from `Unit.step()`, and `step()`
runs only when a message arrives. `verify.1` emitted its needs, received no
offer in reply, and therefore was never scheduled again. Iterative widening is
driven by the one event that cannot occur when the search finds nobody.

```
need emitted -> no producer in the frontier -> no offer returns
             -> no message arrives -> unit is never stepped
             -> widen() never runs -> search stalls holding budget
```

## What this means

The bottleneck is **search continuation**, not settlement, not activation, and
not discovery reach in general. `verify.7` proves the restoration path works
end to end when the first frontier happens to contain a producer.

The event-driven design is correct in refusing to poll. The defect is that
widening was attached to an *inbound* event rather than to the unit's own
outstanding obligation. A unit with an open need and unspent credits has a real
local reason to continue searching; it currently has no way to act on it.

## Constraint on the fix

The correction must not become polling. A candidate shape: a search round is a
first-class bounded object that yields a *continuation* the runtime can
schedule exactly once per round, charged to the need's own credits, ending when
credits are exhausted or the need settles. That keeps activity finite and
attributable, and it never re-enters the whole-organ pattern.

Not implemented in this session: the mechanism choice should be made
deliberately, not appended to a trace.
