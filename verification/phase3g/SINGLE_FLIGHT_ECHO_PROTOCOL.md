# Single-Flight Echo Search — protocol

Pre-registration. Committed **before** implementation, before tests, before any
result. Replaces the duplicated branch tree recorded as failed in
`HIERARCHICAL_BRANCH_ATTEMPT.md`.

## 1. What the failure actually proved

The hierarchical attempt made **path identity** equivalent to **duplicate
computation**. Every arrival carrying a distinct branch identity opened a fresh
subtree, so work scaled with the number of paths rather than the number of units.

The tension is therefore *not* identity versus bounded traffic. It is **path
identity versus duplicate work**. Identity can be preserved without recomputing
the same local search.

Measured cost of getting that wrong: `UNACKNOWLEDGED_TERMINAL_BRANCHES = 57`,
`REPAIR_AMPLIFICATION_MAX = 526.71` against a ceiling of 12, and bounded
exhaustions regressing 10 → 3.

## 2. The invariant

> For one semantic search generation, each unit performs **at most one**
> canonical local search computation.

A later arrival carrying the same semantic search must not open another subtree.
It registers, refunds, and terminates.

Two established primitives, mutated:

- **single-flight duplicate suppression** — concurrent callers sharing a key use
  one in-flight operation instead of duplicating work;
- **diffusing-computation termination detection** — delegated work propagates
  outward and completion signals echo backward, so the initiator can determine
  that the distributed computation has terminated.

## 3. SearchKey — semantics only

Immutable, and contains every field that can change what the search *means*:

```
need_id
work_item_generation
origin_unit
origin_slot
wanted_type
causal_refusal_digest        (digest of `refused`)
must_differ_from_digest      (digest of the sibling exclusions)
constraint_generation        (policy / prohibition generation)
```

Deliberately **excluded**, because they identify transport paths and not distinct
semantic work:

```
branch_id / edge_id
immediate sender
path lineage
```

Same SearchKey ⇒ same local computation. Any differing semantic field ⇒ a
separate search.

## 4. First-arrival adoption

Per unit, one `CanonicalSearchNode` per SearchKey:

```
search_key
status                  OPEN | ANSWERED | EXHAUSTED | CLOSED
adopted_parent_edge     immutable after adoption
adopted_parent_sender   immutable after adoption
incoming_allocation
local_reserve
neighbours_tried
children_opened / children_outstanding / children_completed
eligible_offer
returned_credit / consumed_credit / cancelled_credit
terminal_signal_sent
```

On the first valid arrival the unit adopts that sender and incoming edge as the
canonical parent, records the allocation, evaluates local eligibility **once**,
and opens **at most one** child frontier with unique child edge ids.

## 5. Duplicate arrival

Same SearchKey at a unit that already owns a node: do not forward, do not create
children, do not replace the adopted parent, do not touch the offer return
route. Return exactly one `SearchCoalesced` and refund that branch's unspent
allocation exactly once. The duplicate branch is terminal; the canonical
adopted-parent branch remains live and represents the shared subcomputation.

Exact replay of the same incoming edge is idempotently ignored after one
response.

## 6. Cycles and cross-edges

```
this unit already in the arriving lineage   -> SearchCycleClosed
                                               not registered as a parent
                                               not forwarded

not in lineage, SearchKey already present   -> SearchCoalesced
                                               no new subtree
```

One distributed search wave, not one tree per path.

## 7. Explicit return-edge identity

`reverse` is keyed by `need_id` alone, so a later arrival **overwrites the
earlier return route**, and `Offer` carries no edge identity — duplicate
suppression could be correct while the result travelled home through the wrong
parent. Every child search message carries `search_key`, `edge_id`,
`parent_edge_id`, `return_to`. Every offer and terminal signal carries
`search_key`, the `edge_id` being answered, the outcome type, and refund or
consumption evidence. The return edge of a canonical node is immutable after
adoption.

## 8. Typed terminal outcomes

No boolean bolted onto `__exhausted__`. Distinct types:

```
SearchOffer   SearchExhausted   SearchCoalesced
SearchCycleClosed   SearchNeedClosed   SearchCancelled
```

Each incoming edge receives exactly one. **Only `SearchExhausted` contributes to
proof that a canonical subtree found no eligible provider.** `SearchCoalesced`
means "this path created no additional work because equivalent work is already
active" — it is not evidence of exhaustion.

## 9. Echo termination

A canonical node reports `SearchExhausted` to its adopted parent only when it
cannot supply an eligible offer, every child it *actually opened* is terminal,
none remains in flight, no eligible untried local neighbour remains, no offer was
observed, and its local credit ledger reconciles. It does not wait on duplicate
or cross-edge branches it has already answered with `SearchCoalesced`. A
successful offer travels the adopted-parent chain. Settlement closes the wave and
cancels remaining children idempotently.

## 10. Two distinct failure outcomes

```
SEARCH_SPACE_EXHAUSTED   every eligible local route in the bounded wave explored,
                         every canonical child terminated, no eligible offer
                         exists in the explored space

SEARCH_BUDGET_EXHAUSTED  legal credit ended before the eligible local search
                         space was closed
```

Only the first may count as proved no-replacement exhaustion. The second yields
an attributable budget escalation and may **not** claim that no replacement
exists. R6 conflated these.

## 11. Credit accounting

Per canonical node:

```
incoming_allocation == local_reserve + child_allocations_in_flight
                       + local_consumption + returned_to_parent + cancelled
```

Per duplicate arrival:

```
duplicate_allocation == duplicate_refund + duplicate_handling_cost
```

A duplicate contributes no second child allocation. Per SearchKey across the
organ:

```
root_initial_credits == root_reserve + canonical_child_allocations_in_flight
                        + all_consumed + all_returned + all_cancelled
```

No cross-edge, replay, offer, echo or closure may refund twice.

## 12. Message-complexity invariant

Per SearchKey: a unit opens at most one canonical node; a directed unit-to-unit
edge is probed at most once; a probe receives at most one terminal response; a
duplicate arrival creates zero descendants; a canonical node sends at most one
terminal result to its adopted parent.

Metrics: `UNIQUE_CANONICAL_SEARCH_NODES`, `CANONICAL_SEARCH_EXPANSIONS`,
`COALESCED_DUPLICATE_ARRIVALS`, `CYCLE_EDGES_CLOSED`,
`DUPLICATE_SUBTREES_OPENED`, `DIRECTED_SEARCH_EDGES_PROBED`,
`TERMINAL_ECHOS_SENT`, `OFFER_RETURN_ROUTE_MISMATCHES`, `ORPHANED_SEARCH_EDGES`.

Single Bottleneck Metric:

```
CANONICAL_SEARCH_EXPANSIONS / UNIQUE_CANONICAL_SEARCH_NODES == 1.0
```

Required: `DUPLICATE_SUBTREES_OPENED = 0`,
`OFFER_RETURN_ROUTE_MISMATCHES = 0`, `ORPHANED_SEARCH_EDGES = 0`,
`PREMATURE_TERMINATION_SIGNALS = 0`, `CREDIT_LEDGER_FAILURES = 0`,
`REPAIR_AMPLIFICATION_MAX <= 12`.

## 13. Known risk, tested rather than assumed

First-arrival adoption can make bounded search coverage sensitive to **arrival
order**: whichever path reaches a unit first becomes the adopted parent and
shapes the wave. Unit-ID permutation and randomised delivery-order tests are
therefore mandatory, not optional, and a coverage difference across orderings is
a finding to report rather than a nuisance to suppress.

## 14. Scope limits for the first implementation

- no shared credit pooling across duplicate arrivals;
- formation keeps the R6 mechanism untouched — single-flight applies to repair
  only, and a formation non-regression test asserts the healthy-run event and
  message counts stay materially unchanged;
- no polling, timers, queue-emptiness tests, global provider index, or central
  supervisor.

## 15. Sequence

1. restore R6 runtime files — done, commit `5b6be94`;
2. commit this protocol before implementation — this commit;
3. add failing adversarial tests A–J;
4. implement;
5. commit implementation;
6. verify clean tree;
7. run the original diagnostic development cohort only;
8. `DEVELOPMENT_RESULTS_R8.json`;
9. commit results separately.

R7 is permanently the preserved failed hierarchical attempt and will not be
reused.
