# Hierarchical branch accounting — attempt 1, FAILED its required conditions

Recorded as negative evidence. Not landed as progress. R6 remains the last
clean reproducible baseline.

## The audited defects were real

Both confirmed in source before any change:

1. `dataclasses.replace(need, ...)` preserved the parent's `branch_id` for every
   child of a relay fanout, so the first child to exhaust completed the whole
   parent at the origin while its siblings were still searching. The ledger
   stayed arithmetically balanced while the search tree was causally alive.
2. `seen` was keyed `need_id|wanted` and `_forwarded` by `need_id` alone, so two
   legitimate branches of one need reaching the same relay were collapsed and
   one was never acknowledged.

## What was implemented

- unique child branch identities `N#r0b1/c0`, `/c1`, `/c2`;
- per-relay aggregation records owning the subtree they opened, with parent id,
  round, route, allocated credit, local relay cost, child ids, children
  outstanding/completed, child allocations, returned, cancelled, eligible-offer
  flag and status;
- parent reported only when every child is terminal, none answered, none in
  flight;
- branch-aware `seen`, `_forwarded` and `_exhausted_reported`;
- all four terminal outcomes reporting exactly once (EligibleOffer,
  CandidateIneligible, BranchExhausted, NeedClosed);
- recursive tree reconciliation
  `parent_allocation == local_relay_cost + child_allocations`;
- idempotent subtree cancellation on settlement.

## Required conditions: two of four FAIL

| condition | required | measured |
|---|---|---|
| `PREMATURE_PARENT_BRANCH_COMPLETIONS` | 0 | **0** ✓ |
| `TREE_CREDIT_LEDGER_FAILURES` | 0 | **0** ✓ |
| `UNACKNOWLEDGED_TERMINAL_BRANCHES` | 0 | **57** ✗ |
| `REPAIR_AMPLIFICATION_MAX` | ≤ 12 | **526.71** ✗ |

Also regressed: `BOUNDED_DISTINCT_REPLACEMENT_EXHAUSTIONS` 10 → 3, and
`BOUNDED_ESCALATION_PROVEN_EPISODES` 8 → 3. Qualification stayed 19/48.
Independence violations, locality, authority and unauthorised-effect counters
all remained 0.

Full run: `DEVELOPMENT_RESULTS_R7_FAILED_HIERARCHICAL.json`.

## Why it fails — the actual architectural tension

Branch identity and bounded message volume are in direct conflict under this
design. The `seen` collapse that bounded traffic *was* the collapse that lost
branch identity:

```
seen keyed by need        -> one visit per unit per need   -> bounded, identity lost
seen keyed by need+branch -> one visit per unit per BRANCH -> identity kept, traffic
                             scales with branch identities, and each visit
                             re-fans out three more children
```

Two intermediate attempts confirmed this rather than fixing it:

- keying every need by branch also removed the collapse from **formation**,
  which carries 400 credits over 40 hops. The healthy run went from 16 events
  and 1012 messages to the 3000-event cap and 103888 messages, and formation
  stopped succeeding at all. Exempting formation restored it exactly (16 events,
  1012 messages), but repair traffic remained ~44× over the ceiling.
- completing the missing terminal outcomes moved unacknowledged branches 89 → 57
  while amplification rose 469.65 → 526.71, because every added terminal report
  is another message.

So more bookkeeping is not the fix. Each additional branch identity currently
buys a fresh subtree.

## The design this points to, not yet built

A unit that has already forwarded a need must **join** the arriving branch onto
its existing children rather than opening a new subtree: one child set, multiple
parent references, reference-counted termination. Terminating the shared child
set then reports to every registered parent exactly once. That keeps hierarchical
identity, keeps exactly-one-terminal-outcome, and keeps message volume
proportional to needs rather than to branch identities — a DAG with reference
counts, not a tree with duplicated subtrees.

Until that exists, `BOUNDED_ESCALATION_PROVEN` must not be treated as
protocol-level proof of complete distributed exhaustion, exactly as the audit
required.
