# Phase 3E — Mechanism Cards, Candidate Architectures, and Results

Verdict: **CONTINUE.** Both gates remain open. One precise bottleneck is named,
pinned as an executable test, and deliberately not repaired.

---

## 1. What PR #62 actually proved, reproduced independently

Every defect below was reproduced from the committed artifacts before this phase
began, not accepted on assertion.

| | Claim | Reproduction |
|---|---|---|
| D0 | The constraint channel was never exercised | `prohibited_attachments_blocked == 0` in `PHASE3D_RESULTS.json`. No held-out recovery was causally attributable to the motif channel. |
| D1 | `execute()` did not execute | `payload` appears only inside the hash; no `Cell2` method computes anything. |
| D2 | Diagnosis was handed ground truth | `partitioned=ep["cause"]`, `resource_starved=ep["cause"]`, `failed_role=<harness choice>`. |
| D3 | The phenotype was declared | `precipitate()` hardcodes `static`, `central`, `direct`, `reassign`. |
| D4 | "38 distinct forms" | Collapses to **one** causal form (`fan_in`, `dual_read`) once capability and carrier names are removed. |

PR #62 is preserved as an honest negative result. Gate F remains **REOPENED**,
Gate G remains **OPEN**.

---

## 2. Mechanism cards

### M1 — On-demand route discovery (AODV)

```yaml
primitive_operation:  broadcast a route request; the reply follows reverse-path state
maintained_state:     need_id -> previous hop
transition:           receive RREQ -> record reverse path -> rebroadcast or reply
visible_information:  destination address, hop count, TTL
hidden_information:   the global topology
failure_geometry:     no route found; the request expires
recovery_behavior:    re-issue with a larger TTL
original_assumptions_removed:
  - a destination ADDRESS exists and is known in advance
  - the responder is a fixed node rather than anything able to satisfy a need
  - the request seeks connectivity, not construction
mutations:
  - the request names a CAPABILITY TYPE, not an address; anything that can
    produce the type may answer, so discovery and construction become one act
  - a responder that cannot yet deliver does not reply - it becomes a requester
  - the TTL is joined by a resource budget, so reach is bought, not counted
new_developmental_role: unmet prerequisites recruit their own suppliers
vulnerability_created:  broadcast amplification if budgets are set too generously
```

### M2 — Reactant scarcity (chemical reaction networks)

```yaml
primitive_operation:  a reaction proceeds only when every reactant is present
maintained_state:     local concentrations
transition:           reactants bind -> product forms
visible_information:  local concentration gradients
hidden_information:   the global reaction network
failure_geometry:     the reaction stalls; reactants accumulate unconsumed
recovery_behavior:    the gradient persists until the missing reactant arrives
original_assumptions_removed:
  - reactants diffuse passively and are never actively sought
  - stalling is silent
mutations:
  - a stalled reaction ACTIVELY emits demand for the specific missing reactant
  - the gradient carries type identity, not just concentration
  - stalling leaves a durable local failure receipt instead of vanishing
new_developmental_role: "what I am missing" becomes a first-class signal
vulnerability_created:  a permanently unsatisfiable need re-emits until expiry
```

### M3 — Two-phase commit

```yaml
primitive_operation:  prepare, then commit only if every participant agreed
maintained_state:     per-participant vote
transition:           prepare -> vote -> commit or abort
visible_information:  the participant list
hidden_information:   other transactions
failure_geometry:     a participant fails between prepare and commit
recovery_behavior:    abort and release
original_assumptions_removed:
  - a COORDINATOR exists and knows every participant
  - the participant set is fixed before the protocol starts
mutations:
  - no coordinator: each consumer settles its own slots independently
  - the participant set is DISCOVERED during the protocol, not enumerated first
  - "prepare" is inherited transitively - a supplier's offer stays non-binding
    while its own sub-needs are unsettled, so the commit barrier is recursive
new_developmental_role: an offer that cannot yet be honoured cannot be bonded
vulnerability_created:  a deep pending chain holds slots open until expiry
```

### M4 — Market settlement

```yaml
primitive_operation:  demand meets supply; price allocates scarcity
maintained_state:     bids, offers, commitments
transition:           bid -> offer -> settle or fail
visible_information:  local prices
hidden_information:   other participants' valuations
failure_geometry:     failed settlement
recovery_behavior:    re-auction
original_assumptions_removed:
  - a central order book or registry of sellers exists
  - price is money rather than a developmental budget
mutations:
  - no registry: suppliers are found only by broadcast into a neighbourhood
  - the "price" is a resource budget that DECREASES along the chain, so depth
    is economically damped and an unaffordable chain silently declines
  - failed settlement is evidence, retained locally, not merely a retry
new_developmental_role: scarcity limits recruitment without a global scheduler
vulnerability_created:  a cheap but semantically wrong supplier can win on price
                        (exercised deliberately by the `misleading_supplier` geometry)
```

### M5 — Content addressing

```yaml
primitive_operation:  identity is the hash of contents
mutations:
  - applied to VALUES, not artifacts: each TypedValue carries its producer and
    its parent digests, so a result is auditable back to its inputs
  - applied to FORM: `normalized_form()` Merkle-labels the dependency geometry
    over capability CLASSES from the sources upward, so cell ids, family names,
    ordering and reserve carriers cannot make two identical forms look different
new_developmental_role: provenance for execution, and a quotient for form identity
vulnerability_created:  none observed; the normalization is lossy by design
```

---

## 3. Candidate architectures — nineteen

| # | Candidate | Disposition |
|---|---|---|
| 1 | Recursive receptor demand | folded into the selection |
| 2 | Reverse-path requirement signals | **selected** (M1) |
| 3 | Unmet-dependency gradients | **selected** (M2) |
| 4 | Local capability auctions | **selected in part** (M4); full bidding rejected as needing a clearing round |
| 5 | Obligation-token propagation | rejected — tokens must be minted by an authority, which reintroduces a centre |
| 6 | Reaction-network recruitment | **selected** (M2) |
| 7 | Stigmergic missing-function traces | rejected — the trace outlives its scope with no expiry owner (same objection as Phase 3C) |
| 8 | Local backward chaining | partially adopted; pure form rejected because unification needs a global proof engine |
| 9 | Bidirectional interface negotiation | rejected — negotiation over interfaces changes types globally |
| 10 | Proof-carrying dependency requests | deferred; the proof obligation exceeds what a cell can verify locally today |
| 11 | Ant-style exploration and reinforcement | rejected — converges statistically, so a single episode has no guarantee |
| 12 | Tension-relaxation recruitment | rejected — expresses "unsatisfied" but not "unsatisfied *for type T*" |
| 13 | Distributed rendezvous | rejected — a rendezvous point is a centre wearing a hat |
| 14 | Graph-rewriting growth | rejected — a rewrite rule set is a construction plan |
| 15 | Demand-driven actor spawning | rejected — spawning creates capability from nothing; the pool must be finite |
| 16 | Hardcoded reverse edges | rejected — the prohibited answer; retained as **baseline** |
| 17 | Global dependency solver | rejected as substrate; retained as **baseline** |
| 18 | Conventional workflow DAG | rejected as substrate; retained as **baseline** |
| 19 | No self-recruitment, repeated random search | retained as **baseline** (this is PR #62's behaviour) |

Candidates 5, 7, 9, 11, 12, 13, 14 and 15 are materially unlike the Phase 3D
signal-and-receptor implementation; eight exceeds the required five.

**Selected: recursive conditional settlement** = M1 × M2 × M3 × M4, with M5 for
provenance and form identity.

### Why this is not "add a backward message"

1. A need is broadcast into an **incompletely known** neighbourhood. No cell
   holds a provider index, so there is nobody to send a backward message *to*.
2. A cell that produces the requested type but has unmet prerequisites **does
   not answer**. It emits its own needs and returns a PENDING offer that cannot
   be bonded. Satisfaction is a nested settlement that recurses arbitrarily
   deep — measured depth 6 in the experiment.
3. Offers carry **accumulated cost**; propagation is damped by economics rather
   than a depth constant.
4. Settlement can **fail**, leaving a local failure receipt that is evidence. A
   backward message has no failure mode of its own.
5. Loop suppression comes from **need lineage**, not a stored DAG.

The protocol answers every required question: demand propagates because a
consumer cannot close; loops are prevented by lineage; duplicates by
`seen_needs`; staleness by TTL and budget; competing suppliers by first firm
offer under local constraint check; explosion by the decreasing budget;
satisfaction stops recruitment because a closed cell emits no further needs;
partitions are handled by refused delivery leaving evidence; the topology is
never reconstructed because no cell holds more than its own bonds; and failed
structures leave `FailureReceipt`s.

---

## 4. Results

### Run 1 — pre-registered, FAILED

| Metric | Result | Threshold |
|---|---|---|
| Self-recruiting semantic regenerations | 1 / 20 | 17 |
| Gate G causal escapes | 0 / 20 | 15 |
| Blind causal-class accuracy | 0.7368 | 0.85 |
| Blind affected-role accuracy | 0.5263 | 0.80 |
| Void held-out episodes | 3 / 40 | 0 |
| Topology-normalized causal forms | 5 | 5 — **met** |
| Healthy semantic outputs held out | 40 / 40 | 40 — **met** |
| Global formation scans | 0 | 0 — **met** |
| Solution leakage events | 0 | 0 — **met** |
| Max self-recruitment depth | 6 | — |

Two causes, both diagnosed, neither repaired against these fixtures:
partitions left no delivery evidence (all 10 partition episodes inferred as
`supplier_loss`), and **a catalogue defect of mine** — several geometries had
exactly one producer of the contract output type, so the pre-registered damage
policy selected it and the function became unrecoverable by construction.

### Run 2 — fresh pre-registration, corrected fixtures, FAILED

| Metric | Run 1 | Run 2 | Threshold |
|---|---|---|---|
| Self-recruiting semantic regenerations | 1 / 20 | **0 / 20** | 17 |
| Gate G causal escapes | 0 / 20 | 0 / 20 | 15 |
| Blind causal-class accuracy | 0.7368 | **1.0000** | 0.85 — **met** |
| Blind affected-role accuracy | 0.5263 | **0.8060** | 0.80 — **met** |
| False causal certificates | 20 | **0** | — |
| Topology-normalized causal forms | 5 | **7** | 5 — **met** |
| Raw carrier configurations | 1 | 0 | — |
| Void held-out episodes | 3 | 7 | 0 |
| Global formation scans | 0 | 0 | 0 — **met** |
| Solution leakage events | 0 | 0 | 0 — **met** |

Blind diagnosis is now **perfect on causal class across 67 episodes**, which is
the D2 defect fully removed: the diagnostician receives only traces, bond
receipts, resource records, failure receipts and delivery evidence, and its
signature is asserted by test to contain no cause parameter.

---

## 5. The Phase 3E bottleneck

**Demand originates only at the boundary.**

```
healthy:                    ACCEPT
damage an INTERIOR carrier: output None
SINK unmet slots:           ()          <- demand() iterates only these
starved interior cells:     ['check.1', 'check.3', 'check.5']
messages emitted by demand: 0           <- regeneration never starts
```

The starved cells *know* they are starved and can name exactly what they are
missing (`missing_capability_classes()`), but nothing re-opens their need. Only
`SINK` can originate demand, and `SINK` is still satisfied because its bond is
formally intact.

This is the mirror of Phase 3D's bottleneck and strictly narrower. Phase 3D
could not recruit backward at all. Phase 3E recruits backward, recursively, six
levels deep — but only from the boundary inward, and only once.

It is pinned as an executable test
(`test_interior_starvation_does_not_reopen_demand_KNOWN_BOTTLENECK`) rather than
repaired, because repairing an instrument and rescoring the same held-out
fixtures is prohibited. Phase 3F should pre-register fresh fixtures and invent
**autonomous interior re-initiation**: a mechanism by which a cell that loses a
bond re-enters the demand protocol on its own, with its own budget, without any
boundary event and without a supervisor polling for starvation.

---

## 6. Defects found in this phase's own work

1. **Type-safety violation in settlement.** A cell re-advertised itself as FIRM
   for every need in its reverse path, including needs it had merely relayed and
   whose type it does not produce — `SINK` bonded to a `NORM` producer while
   demanding `VERDICT`. Found by the first smoke test.
2. **No type check at settlement.** The offered type was never compared with the
   slot's required type.
3. **One supplier could fill both slots of a join**, making "two independent
   checks" one check counted twice.
4. **Partition was not observable.** `partition_around()` deleted the bond and
   `execute()` attempted no delivery, so no evidence of isolation existed.
   Corrected before run 2: the bond is left in place and a refused delivery is
   recorded, which is what a partition actually looks like.
5. **Fixture defect (mine).** Documented in §4.

Items 1–3 were found before any results existed. Items 4–5 were found by run 1
and corrected only under a fresh pre-registration with new seeds and a new
catalogue file, leaving `geometries.py` untouched so run 1 stays reproducible.
