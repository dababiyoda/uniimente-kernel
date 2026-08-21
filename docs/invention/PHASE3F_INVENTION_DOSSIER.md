# Phase 3F — Invention Dossier, Failure Model, Experiment, Decision

**Verdict: CONTINUE.** Gate F REOPENED, Gate G OPEN.

The pre-registered primary capability — autonomous interior re-initiation — is
achieved and measured. Restoration is not, for one exactly located reason.

---

## 1. Verified starting state

`origin/agent/bidirectional-developmental-demand-v1` = `a5d0722d3d7602bec1266cf7c79c9f8eaf1cc6d0`,
confirmed against git, matching the claimed PR #63 head. Phase 3F branches from
that commit.

### Corrected Phase 3E interpretation, verified from the data

`PHASE3E_RUN2_RESULTS.json` contains **7 distinct `healthy_form` values and 0
distinct `restored_form` values**, because there were 0 semantic restorations.

```
INITIAL_TOPOLOGY_NORMALIZED_FORMS:    7
RECOVERED_TOPOLOGY_NORMALIZED_FORMS:  0
RAW_RECOVERED_CARRIER_CONFIGURATIONS: 0   (no successful held-out regenerations)
```

Reporting those 7 as *recovered* forms was wrong. Zero recovered carrier
configurations is not an advantage. Both corrections are carried into the
Phase 3F manifest.

Phase 3E's 1.0 blind causal-class accuracy was measured in a clean,
single-cause, strongly instrumented environment. It is **not** evidence of
reliable diagnosis under incomplete, contradictory, intermittent, delayed or
simultaneous failures. Phase 3F tests those directly and scores them separately
(`MIXED_FAILURE_CAUSAL_CLASS_ACCURACY`), where accuracy is **0.25**.

---

## 2. The seed hypothesis was rejected

The prompt proposed supplier **agreements** carrying **generations**: state on
the consumer↔supplier edge plus a counter to order repair rounds.

Rejected as the primary mechanism, for a specific reason:

> A generation counter fences the supplier you already suspect, and nothing
> else. It cannot refuse a *different* supplier that silently depends on the
> same broken upstream, because that supplier's generation is fresh.

In an institution that is the common case: two departments quietly sharing one
broken source. Generation fencing is retained as a **baseline**, not the design.

**Selected instead: validity modelled on the VALUE, not the relationship.**
There is no agreement object and no generation counter anywhere in the
mechanism. A unit remembers the derivation chain of the input it last accepted;
when its own execution cannot obtain a usable value it adds that derivation to a
local refusal set; any later offer whose derivation intersects that set is
refused — by the consumer at settlement, and by the supplier as self-exclusion.

---

## 3. Mechanism cards

### M1 — Incremental-build invalidation (make/Nix/Bazel family)

```yaml
primitive_operation: a target is stale when an input's fingerprint changed
maintained_state:    per-target input fingerprints
state_transition:    fingerprint mismatch -> rebuild
actor:               the build coordinator
authority:           the coordinator owns the dependency graph
visible_information: the whole graph
hidden_information:  nothing
resource_consumed:   rebuild work
selection_rule:      recipe is fixed
feedback:            success or failure of the rebuild
proof_emitted:       a cache key
failure_geometry:    a stale artifact is silently reused
recovery_behavior:   full rebuild
original_assumptions_removed:
  - a coordinator exists and owns the graph
  - staleness is computed by comparing fingerprints out of band
  - the recipe for rebuilding is known in advance
mutation_1: staleness is discovered by the CONSUMER doing its own ordinary work
mutation_2: there is no coordinator and no graph; only the consumer's own bonds
mutation_3: the rebuild target is not known - it must be recruited
new_capability: invalidation without any component that owns the dependency graph
new_vulnerability: a consumer that never executes never notices it is broken
role_in_phase3f: execution-triggered detection; no polling, no timer, no clock
```

### M2 — Merkle / Git ancestry

```yaml
primitive_operation: identity by content and derivation; ancestry is decidable
maintained_state:    per-object hash and parent links
state_transition:    new content -> new hash
actor:               any holder of an object
authority:           none; ancestry is a fact, not a permission
visible_information: an object's own derivation
hidden_information:  unrelated history
resource_consumed:   hashing
selection_rule:      dedup by identical hash
feedback:            none
proof_emitted:       the digest
failure_geometry:    hash collision
recovery_behavior:   none
original_assumptions_removed:
  - ancestry is used to DEDUPLICATE and to look things up
  - ancestry is consulted about the past
mutation_1: ancestry becomes a REFUSAL predicate, applied to future offers
mutation_2: the refusal set is local and per-consumer, not a shared index
mutation_3: refusal is sized to the evidence (see below), not applied uniformly
new_capability: fencing that also excludes a fresh supplier with bad ancestry
new_vulnerability: over-refusal when the chain is wide - MEASURED, see section 7
role_in_phase3f: the fence
```

### M3 — Taint tracking

```yaml
primitive_operation: a value derived from untrusted input is itself untrusted
maintained_state:    a taint bit per value
state_transition:    taint propagates through any transformation
actor:               the runtime
authority:           the runtime decides what is trusted
visible_information: taint bits
hidden_information:  the taint policy
resource_consumed:   negligible
selection_rule:      n/a
feedback:            a sink refuses tainted data
proof_emitted:       none
failure_geometry:    over- or under-tainting
recovery_behavior:   sanitise
original_assumptions_removed:
  - a runtime holds the policy
  - taint only guards a sink
mutation_1: taint makes the NEXT consumer REOPEN, not merely refuse
mutation_2: invalidation therefore propagates by ordinary execution, with no
            notification channel and no observer
mutation_3: the taint is carried in the value's own derivation, so it survives
            being handed on
new_capability: poison containment plus repair initiation in one signal
new_vulnerability: a wide taint front creates many simultaneous reopenings
role_in_phase3f: stops a unit emitting a wrong value, and starts the repair
```

### M4 — Token bucket / admission control

```yaml
primitive_operation: work proceeds only while tokens remain
maintained_state:    a token count
state_transition:    consume, refill
actor:               a rate limiter
authority:           the limiter owns the bucket
visible_information: the bucket
hidden_information:  other clients
resource_consumed:   tokens
selection_rule:      first come first served
feedback:            rejection
proof_emitted:       none
failure_geometry:    starvation
recovery_behavior:   refill
original_assumptions_removed:
  - one bucket is SHARED and owned by a limiter
  - the limit is a rate over time
mutation_1: the budget is DIVIDED among sub-needs, not shared
mutation_2: it is a depth-and-breadth budget, not a rate; there is no clock
mutation_3: exhaustion produces a bounded ESCALATION receipt, not a retry
new_capability: amplification bounded structurally with no scheduler
new_vulnerability: under-funding is indistinguishable from an unsatisfiable
                   contract - encountered and fixed during construction
role_in_phase3f: bounds repair cost and terminates hopeless repair
```

---

## 4. Candidate architectures — nineteen

Nine (47%) are drawn from mechanisms not named anywhere in the prompt, exceeding
the required 40%: †

| # | Candidate | Disposition |
|---|---|---|
| 1 | Expiring supplier agreements | rejected — a clock cannot tell a slow supplier from a dead one |
| 2 | Proof-of-delivery renewal | rejected — renewal traffic on the healthy path |
| 3 | Consumer-owned restart authority | **adopted as the authority model** |
| 4 | Local dependency invalidation | **selected (M1)** |
| 5 | Execution-triggered reopening | **selected (M1)** — detection is free |
| 6 | Failed-settlement re-auction | partially adopted for offer selection |
| 7 | Acknowledgement chains | rejected — acks on the healthy path cost more than they save |
| 8 | Locally fenced agreement generations | rejected as primary; retained as **baseline** |
| 9 | Change-stream invalidation | rejected — a stream is a channel somebody owns |
| 10 | Circuit-breaker replacement | **adopted, bounded** (cooldown + half-open probe) |
| 11 | Backpressure-controlled restart | folded into the divided budget |
| 12 | Local compensation chains | rejected — compensation needs an undo semantics the contract does not define |
| 13 | Agreement-health evidence | rejected — health is a proxy; the contract invariant is the real test |
| 14 | Bounded retry markets | rejected — reduces to retry |
| 15 | Failure-receipt propagation | **adopted** as local memory |
| 16 | † Taint/information-flow propagation | **selected (M3)** |
| 17 | † Merkle ancestry as a refusal predicate | **selected (M2)** |
| 18 | † Epidemic/anti-entropy reconciliation | rejected — converges statistically; a single episode has no guarantee |
| 19 | † Immunological self/non-self with affinity maturation | rejected — needs a repertoire the unit cannot hold locally |
| 20 | † Thermodynamic potential relaxation | rejected — expresses "unsatisfied" but not "unsatisfied *for type T*" |
| 21 | † Blackboard/tuple-space rendezvous | rejected — the blackboard is a centre |
| 22 | † CRDT join-semilattice merge | rejected — refusal is not monotone-mergeable |
| 23 | † Insurance claim against a bounded reserve | rejected — an extra accounting layer for no added discrimination |
| 24 | † Predictive-coding surprise minimisation | rejected — needs a learned model; not evidence in one episode |
| 25 | Supervisor polling | **baseline only** |
| 26 | Whole-system dependency scanner | **baseline only** |
| 27 | Complete mission restart | **baseline only** |
| 28 | Conventional durable workflow | **baseline only** |

Selected: **M1 × M2 × M3 × M4** — *provenance-fenced local reopening*.

### Why this is not a lease, timer, retry, or backward message

- **Not a lease or timer.** There is no clock in `substrate/v4.py`. Validity is
  never a function of elapsed time; it is a function of whether this unit's own
  execution obtained a usable value.
- **Not a retry.** A reopening does not re-ask the same supplier. It refuses
  that supplier's derivation and recruits into an incompletely known
  neighbourhood.
- **Not a backward message.** The unit does not notify anyone that it broke. It
  refuses locally and issues a *typed need* for what it lacks; nobody is told
  what happened, and there is no repair addressee.
- **Not a stored backup list.** No unit holds a provider index;
  `FULL_PROVIDER_INDEX_READS` is asserted 0.

---

## 5. State model (there is no agreement object)

A unit's continuity state is the pair `(bonds, refused)`:

| Transition | Triggering evidence | Actor | Emits | Receipt | Resource |
|---|---|---|---|---|---|
| bond → absent | own execution obtained no usable value | the consumer | nothing | `input_refused` | 1.0 repair budget |
| absent → need | the slot is unmet | the consumer | `Need` with its refusal set | — | divided budget |
| need → offer | a neighbour produces the type and its derivation is not refused | a supplier | `Offer` | `offer_withheld` if excluded | supplier cost |
| offer → bond | type matches, distinct supplier, derivation not refused, not in cooldown, constraint permits | the consumer | — | `bond_settled` | — |
| offer → rejected | derivation intersects the refusal set | the consumer | — | `stale_offer_rejected` | — |
| need → escalation | repair budget exhausted | the consumer | nothing | `escalation` | — |

**Fencing is sized to the evidence.** A delivery fault (gone, isolated, silent,
too costly) is evidence about the *direct supplier only*, so only that supplier
is refused. A semantic fault is evidence that *something in the derivation*
produced a wrong value and the consumer cannot tell which link, so the whole
upstream chain is refused, excluding `@env` (the mission input is given, not
chosen). Both branches are pinned by tests.

---

## 6. Results

Pre-registered thresholds, unchanged.

| Metric | Result | Threshold | |
|---|---|---|---|
| HELD_OUT_INTERIOR_AUTONOMOUS_SEMANTIC_REGENERATIONS | **0 / 20** | 17 | FAIL |
| **INTERIOR_AUTONOMOUS_REINITIATIONS** | **19 / 23** | 17 | **MET** |
| HELD_OUT_SEMANTIC_RESTORATIONS | 1 / 23 | 17 | FAIL |
| GATE_G_CAUSAL_ESCAPES | 0 / 20 | 15 | FAIL |
| **BOUNDARY_RESTART_EVENTS** | **0** | 0 | **MET** |
| **SUPERVISOR_RESTART_EVENTS** | **0** | 0 | **MET** |
| **GLOBAL_FORMATION_SCANS** | **0** | 0 | **MET** |
| **GLOBAL_REPAIR_SCANS** | **0** | 0 | **MET** |
| **FULL_PROVIDER_INDEX_READS** | **0** | 0 | **MET** |
| **STALE_AGREEMENT_REUSE** | **0** | 0 | **MET** |
| stale derivations rejected | 470 | — | |
| VOID_REGENERATION_EPISODES | 17 / 40 | 0 | FAIL |
| INITIAL_TOPOLOGY_NORMALIZED_FORMS | 9 | — | |
| RECOVERED_TOPOLOGY_NORMALIZED_FORMS | 1 | 5 | FAIL |
| HELD_OUT_BLIND_CAUSAL_CLASS_ACCURACY | 0.4783 | 0.85 | FAIL |
| HELD_OUT_BLIND_AFFECTED_ROLE_ACCURACY | 0.3478 | 0.80 | FAIL |
| MIXED_FAILURE_CAUSAL_CLASS_ACCURACY | 0.25 | 0.70 | FAIL |
| RESILIENCE_TOLERATED | 5 / 12 | — | |
| CORRECT_NO_RESTART_DECISIONS | 5 | — | |
| CORRECT_ESCALATIONS | 0 / 8 | — | FAIL |
| FALSE_RESTARTS | 0 | — | MET |
| REPAIR_AMPLIFICATION_MAX | **423.25** | ≤ 12.0 | **FAIL** |
| SOLUTION_LEAKAGE_EVENTS | 0 | 0 | MET |
| TARGET_TOPOLOGY_LEAKAGE_EVENTS | 0 | 0 | MET |
| INHERITED_AUTHORITY_EVENTS | 0 | 0 | MET |
| UNAUTHORIZED_EXTERNAL_EFFECTS | 0 | 0 | MET |

Paired interventions (12 pairs): `MATCHING_PROHIBITED_PROPOSALS_OBSERVED` 0,
`PROHIBITED_COMMITS_WITHOUT_CERTIFICATE` 1, `PROHIBITED_COMMITS_WITH_CERTIFICATE`
1, `ALTERNATIVE_SUCCESSFUL_COMMITS_WITH_CERTIFICATE` 0. **Gate G has no
intervention evidence**, because escape presupposes restoration and restoration
did not occur.

---

## 7. The exact bottleneck: the fence over-refuses

`REPAIR_AMPLIFICATION_MAX = 423` against a ceiling of 12, with restorations
1/23, is one mechanism failing in one way.

A semantic fault refuses the entire upstream derivation. Interior units in a
real organ **share ancestors** — that is what makes an organ an organ rather
than a set of parallel silos. So a single semantic fault refuses most of the
viable suppliers of the required type at once. Every one of them then withholds
its offer; the consumer keeps needing; and the taint front makes further units
reopen, each broadcasting into the neighbourhood.

The property is pinned as an executable test
(`test_provenance_fence_over_refuses_KNOWN_BOTTLENECK`): after one semantic
fault on a wide chain, **every** unit producing the required type is in the
refusal set.

This is a **mechanism defect**, not an implementation, instrument, or fixture
defect. The classification matters: the invention's discriminating power (it can
exclude a fresh supplier with bad ancestry — something generation fencing cannot
do) is the *same property* that makes it over-refuse. Precision and recall are
coupled in the current formulation.

The diagnosis metrics failed for a related reason: with many units reopening for
different locally-true reasons, the modal-class inference across receipts is
diluted (`HELD_OUT_BLIND_CAUSAL_CLASS_ACCURACY` 0.478 against Phase 3E's 1.0 on
single-cause episodes). That is the honest scope correction the founder
required, now measured rather than asserted.

`CORRECT_ESCALATIONS 0/8` has a separate, smaller cause: the no-replacement
fixture's consumers exhaust budget across rounds rather than emitting the
escalation receipt inside the scored window.

---

## 8. Where conventional software is better

On these results, a conventional durable workflow engine with a supervisor and a
static dependency graph would restore this function more reliably and far more
cheaply. It would detect the break by supervision, consult the graph, and
re-dispatch the one failed step, with amplification near 1. The invention's only
current advantage over it is architectural (no central repair authority, no
global scan) — and architecture is not a result. **Decentralisation is not
evidence of superiority, and Phase 3F does not provide any.**

What the invention does have that the baselines do not, and which is measured:
autonomous interior re-initiation at 19/23 with zero boundary restarts, zero
supervisor events, zero global scans and zero provider-index reads.

---

## 9. Decision

**CONTINUE**, not REPLACE.

The architectural-replacement test is not met: the family did not require hidden
global knowledge, supervisor polling, fixture-specific rules, target-topology
leakage, stale authority reuse, or structural proxies for semantics. All those
counters are zero. It failed on one identified, bounded mechanism property.

The next round's target is precise: **make refusal discriminating rather than
broad** — refuse a derivation *element* only when evidence separates it from the
alternatives, e.g. by refusing the minimal ancestor set that distinguishes the
failing input from a working sibling, rather than the whole chain. That is a
different mechanism, and it must be pre-registered fresh with new fixtures and
new seeds. Phase 3F's fixtures are spent.

---

## 10. Defects found in this phase's own work

1. **Refusal built from the consumer's own output chain** rather than the
   input's, which refused every possible supplier. Found by smoke test.
2. **The boundary could reopen**, which would have been a boundary restart.
3. **A unit that answered PENDING never re-advertised as FIRM** once its own
   prerequisites settled, so nothing ever bonded.
4. **Commissioning budget under-funded the depth-8 contract**, which is
   indistinguishable from an unsatisfiable contract. Fixed before any episode ran.
5. **A test asserted `"open(" not in source`**, which matched `reopen(`.
   Replaced with an AST check of imports and call names.

Items 1–4 were found before any results existed; item 5 was a test bug.
