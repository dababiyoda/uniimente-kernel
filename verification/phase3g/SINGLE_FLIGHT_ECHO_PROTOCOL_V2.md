# Single-Flight Echo Search — protocol V2: proposal/commit handshake

Supersedes `SINGLE_FLIGHT_ECHO_PROTOCOL.md`, which is preserved unchanged as
historical provenance. V2 corrects one conceptual error and tightens two
contracts. Everything else in V1 stands.

## 1. The contradiction V2 fixes

V1 treated a candidate offer as a **terminal success**. Acceptance test E was
activated on that basis and asserted:

```
child returns SearchOffer  ->  parent immediately becomes ANSWERED
```

The live-path contract then correctly required:

```
SearchOffer arrives  ->  root calls _settle()
                     ->  rejection leaves the search OPEN
                     ->  other candidate paths remain intact
```

**Both cannot be true.** A candidate cannot be a terminal success, because the
root may reject it for duplicate supplier, stale derivation, cooldown, a
prohibited motif, changed slot state, policy mismatch, or a race with another
accepted candidate. Every one of those is a real rejection path in `_settle`.

The error is mine twice over: I activated E on the wrong model, and the
"an answer short-circuits" change in the primitives commit made a canonical node
go `ANSWERED` and cancel its siblings on a mere proposal — which is precisely the
premature-cancellation defect.

## 2. A proposal is not a terminal outcome

```
candidate found
  -> SearchProposal travels upward through adopted-parent edges
  -> the search wave REMAINS OPEN
  -> root constructs an Offer and calls _settle()
       accepted -> commit, then cancel the remaining wave
       rejected -> preserve or resume the remaining search
```

`SearchProposal` is **evidence of a candidate**. It is not a terminal transport
outcome and it is not proof of restoration.

A `SearchProposal` carries the complete payload the root needs to build an
`Offer`:

```
supplier            supplier_class      offered_type
cost                firm                derivation_chain
search_key          context_digest      source_edge_id
```

It may traverse several adopted-parent edges on the way home. It does **not**:
terminally answer any edge; mark a node `ANSWERED`; cancel siblings; close the
Need; or prove restoration.

## 3. At the root

```
SearchProposal -> construct Offer -> _settle()
```

**Accepted:** record `SearchProposalAccepted`; close the Need generation; send a
commit/closure signal through the canonical wave; explicitly reconcile or cancel
every outstanding allocation; terminally close every still-open transport edge
exactly once; mark the root and the accepted path `COMMITTED`.

**Rejected:** record `SearchProposalRejected` **with the exact refusal reason
from `_settle`**; do not close the Need; do not cancel unrelated children;
preserve the wave; permit remaining proposals or bounded continuation; and return
rejection feedback to the proposing canonical node so it can expand after its own
candidate was refused.

## 4. Terminal outcome contract

`SearchProposal` is not a terminal kind. Every probed transport edge still
receives exactly one **eventual** terminal outcome, drawn from:

```
SearchCommitted        SearchExhausted       SearchBudgetExhausted
SearchCoalesced        SearchCycleClosed     SearchContextRejected
SearchNeedClosed       SearchCancelled
```

A proposal may occur before that terminal outcome. Telemetry is therefore split:

```
Organ.search_edge_events[edge_id]     -> [nonterminal proposals, control events]
Organ.search_edge_terminals[edge_id]  -> exactly one eventual terminal outcome
```

A `SearchProposal` is never stored inside a terminal record.

Node status becomes: `OPEN` → `PROPOSAL_PENDING` → `COMMITTED` | back to `OPEN`
on rejection | `EXHAUSTED` | `CLOSED`.

## 5. SearchContext must be fully bound

V1 bound only the refusal and must-differ digests into `SearchKey`, while the
context also carried `max_supplier_cost` and `cooldown_excluded`. A relay could
therefore alter the cost ceiling or the cooldown set while keeping the same
`SearchKey` — an unenforced constraint wearing a valid identity.

`SearchContext` carries every field used for remote candidate eligibility:

```
causally_refused_sources        must_differ_from_suppliers
maximum_supplier_cost           cooldown_excluded_suppliers
constraint_generation           policy_snapshot
origin_independence_evidence
```

`SearchKey` gains a single deterministic **`context_digest`** covering all of
them, and `SearchContext.matches(key)` verifies the **complete** context, not
just two fields. Digests sort their inputs and use sha256; Python's
process-randomized `hash()` is never used.

Tampering with the cost ceiling, the cooldown set, the constraint generation or
the policy snapshot must yield `SearchContextRejected`.

## 6. Remote eligibility must be proved on the derivation chain

Three positive requirements V1 did not test:

- a producer whose cost exceeds `maximum_supplier_cost` emits no proposal;
- a producer listed in `cooldown_excluded_suppliers` emits no proposal;
- a producer whose **own id is clean** but one of whose **derivation-chain
  ancestors** is in `causally_refused_sources` emits no proposal.

The third is the one that matters: V1's causal-refusal test refused the
candidate's own id, which proves direct exclusion and says nothing about
derivation intersection.

## 7. Corrected credit invariant

V1's reconciliation check added `returned_credit` **and** `local_reserve`, while
the mechanism transfers a refunded child allocation *into* local reserve and also
accumulates it in `returned_credit`. That double-counts the same credit.

Fields are separated by role:

```
child_refunds_received      cumulative AUDIT only, never in the balance
local_reserve               current spendable state
child_allocations_in_flight
consumed_credit
cancelled_credit
returned_to_parent
```

State invariant:

```
incoming_allocation == local_reserve
                     + child_allocations_in_flight
                     + consumed_credit
                     + cancelled_credit
                     + returned_to_parent
```

At terminal closure, `child_allocations_in_flight == 0`.

## 8. Legacy projection is one-way

`open_needs` stays as the generation registry. `_search` survives **only** as a
one-way audit projection:

```
canonical Single-Flight state  ->  legacy-compatible diagnostic fields
legacy fields                  ->  never route, widen, settle, close or alter
                                   canonical search
```

An adversarial test mutates a projected `_search` record after creation and
proves canonical routing and settlement are unchanged. If an existing R6-internal
test genuinely requires `_search` to hold decision authority, that test is
reported explicitly rather than satisfied by recreating dual control.

```
LEGACY_PROJECTION_DECISION_READS = 0
LEGACY_REPAIR_NEED_MESSAGES = 0
DUAL_REPAIR_SEARCHES = 0
```

Formation keeps the legacy `Need` path unchanged, at 16 events and 1012 messages.

## 9. Single Bottleneck Metric

```
PROPOSALS_RESOLVED_WITHOUT_PREMATURE_WAVE_CLOSURE
-------------------------------------------------
TOTAL_SEARCH_PROPOSALS_RECEIVED
```

Target 1.0, with `PREMATURE_PROPOSAL_CANCELLATIONS = 0`,
`UNACCOUNTED_PROPOSALS = 0`, `DUAL_REPAIR_SEARCHES = 0`.

## 10. Sequence

1. **this commit** — protocol V2 and test corrections only, no runtime change;
2. `SearchContext` with full binding, `SearchProposal` payload, proposal/commit
   handshake, edge identity, lineage and unique-round fixes;
3. live repair migration, legacy projection only, no dual routing;
4. marker activation for genuinely satisfied specifications only;

then full suite, clean tree, development cohort, `DEVELOPMENT_RESULTS_R8.json`.
