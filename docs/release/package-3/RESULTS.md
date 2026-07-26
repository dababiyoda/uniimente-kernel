# Package 3 — Results

**Experiment:** `package3-governed-functional-replacement-v1`
**Frozen spec seal:** `6f6d7dab40cf023dd69995511a3db298482c31b0bb39675d4a5c47f7c4ab7f4a`
**Base:** `release/canonical-v1` @ `cb234faf932d239d79b0e7ab28e54f576b8a15bf`
**Machine-readable evidence:** `EVIDENCE_RECORD.json` (regenerate with
`python -m evolution.repair`)

---

## The three questions, answered separately

The founder required these kept apart rather than blended into one verdict.

### 1. Did a structurally different replacement restore the function?

**Yes.** Three independent implementations each restored the function exactly:

- **4 of 4** required edge triples, on the live corpus
- every declared refusal correct — 1 unproduced, 0 untyped, 11 unconsumed,
  7 unresolved carried verbatim, 2 overlapping authorities,
  `fully_connected = False`
- all **four held-out cases** matched their frozen expectations exactly
- verified by the blind detector, which never learned which implementation it
  was watching

### 2. Was the replacement better than restoring the original?

**No.** Restoring the original is **3.8× cheaper** on the frozen repair-cost
meter and needs **one rollback step instead of three.**

| Candidate | Score | Qualifies | Lines | New deps | Decisions | ms | Rollback | Repair cost |
|---|---|---|---|---|---|---|---|---|
| `B0-restore` | 1.0 | no — *is* the original | 20 | 0 | 0 | 0.063 | 1 | **70.03** |
| `R1-contract-index` | 1.0 | yes | 68 | 1 | 6 | 0.040 | 3 | **267.02** |
| `R3-local-rule` | 1.0 | yes | 117 | 0 | 14 | 0.226 | 3 | **323.11** |
| `R2-constraint` | 1.0 | yes | 124 | 2 | 10 | 0.147 | 3 | **364.07** |

Repair cost is in **repair points, not dollars.** This package spent **$0.00.**

### 3. Which method should remain the operational default?

**The original.** `R1-contract-index` is retained as a **proven fallback**, not
as a replacement.

Decision: **`regress`** — the improvement was proven and its promotion was
declined. Recorded verbatim in the evidence:

> Functional replacement is PROVEN … Promotion is nonetheless DECLINED:
> restoring the original is the cheapest and safest repair … The original
> therefore remains the operational default and `R1-contract-index` is retained
> as a proven fallback, not as a replacement. **Recommendation only: this
> decision promotes nothing and activates nothing.**

---

## Predictions: 2 of 4 fully held. One was plainly wrong.

Pre-registered in commit 1, before any candidate existed.

| Candidate | Predicted score | Actual | Predicted cost rank | Actual | Held |
|---|---|---|---|---|---|
| `B0-restore` | 1.0 | 1.0 | 1 | 1 | yes |
| `R1-contract-index` | 1.0 | 1.0 | 2 | 2 | yes |
| `R2-constraint` | 1.0 | 1.0 | 3 | **4** | no |
| `R3-local-rule` | **0.0** | **1.0** | 4 | **3** | **no** |

### The R3 prediction was wrong, and this is the most interesting result

I froze R3 at `predicted_function_score = 0.0`, predicting the local rule would
fail HO-4's global negative. **It scored 1.0 on every corpus.**

The reasoning was sound; the conclusion did not follow from it. A cell really can
only conclude *"no producer among cells I have heard from"* — but at full
reachability within the round budget that coincides **exactly** with *"no cell
produces it."* **The Package 2 hub-dependence finding does not transfer to this
topology.** The frozen spec required this outcome be reported as a failed
prediction, so it is reported rather than edited.

Because the result is surprising, it was attacked rather than accepted. The
alternative explanation — that R3's "cells" are decoration around a secretly
global computation — is ruled out: **partitioning the message graph on HO-3 makes
the identical local rule return 2 edges instead of 4**, losing precisely
`(a,z,c)` and `(a,z,d)`, the two whose consumers became unreachable. A globally
informed implementation could not lose them. A cell in isolation commits nothing
at all.

So the honest reading is stronger than my prediction, not weaker: a mechanism
with **no global resolver at all** restored the function exactly.

---

## Continuity

Unchanged at every stage — before disable, **while the function was absent**,
after install, after rollback:

```
c1d621a80671d1f39f75e3d525561b45795a978d7d15b1eee7d43546140e63aa
```

Twelve artifacts: five constitution `.ucl` files, three `authority/` registries,
three `identity/` registries, `policy/consequence_gate.py`.

**While the function was absent:** the Constitution still compiled with
`deny_by_default` intact, shutdown still returned `shutdown_complete`, and the
original's bytes were still on disk. A system that cannot be governed or stopped
mid-repair has failed whether or not it repairs.

| Gate | Result |
|---|---|
| 4/4 exact edge triples | pass (all four candidates) |
| all required refusals | pass |
| all four held-out cases | pass |
| materially different from the original | pass (R1, R2, R3) |
| constitution / identity / authority / legal-principal / gate unchanged | pass |
| memory and prior evidence readable and verifying | pass — chain intact, 31 records |
| shutdown succeeds | pass, including while absent |
| original available for rollback | pass — byte-identical throughout |
| unauthorized external effects | **zero**, enforced out-of-process |

---

## The removal was real

A `sys.meta_path` finder refused to locate the package and evicted it from
`sys.modules`. Plain `import`, `importlib.import_module`, and transitive imports
all raise. Nothing was deleted from disk, which is exactly why rollback is one
step.

Detected loss symptom: `provider_failed — capability raised while resolving
(ComponentUnavailable)`. Note what the symptom does **not** say: no module name,
no file path, no `"No module named 'linker'"`. The detector records the exception
*type* and discards the *message*, because the message would hand it the identity
of the failed module. That costs real diagnostic value and is the price of the
blindness being genuine.

**Detection controls, all passing:**

1. detects the real loss
2. silent when healthy — no false positive on any of the five corpora
3. **never reports recovery from incomplete output** — parametrized over all four
   ways to drop one edge; 3/4 = 0.75 and `restored` requires *zero* symptoms
4. catches an invented edge (all four required plus one fabricated)
5. catches correct edges with refusal behaviour stripped — a guesser wearing the
   right output shape

---

## Selection was not performed by the author

Primary ranking is the existing `evolution/comparison.py` at the frozen
threshold. **All four candidates tie at 1.0**, and because `cost_usd` and
`duration_days` are legitimately `0` for every candidate, their score tuples are
*identical*. The named "champion by primary metric" is therefore whichever tied
candidate sorted first — **not a finding**, and flagged as
`champion_is_tie_arbitrary: true` in the record rather than quietly reported as a
result.

The frozen secondary order — `repair_cost`, `decision_points`, `runtime_ms`,
`rollback_steps`, `new_source_lines` — is what discriminates, and it produced a
strict total order with no ties.

The decision is a `RetainRegressKillDecision`, which **structurally cannot**
authorize promotion on a hypothesis-only verifier.

---

## Spider-Web audit: INCOMPLETE, correctly

Verdict `INCOMPLETE`. Missing: `real_beneficiary`, `buyer_or_mandate_actor`,
`lawful_permission_path`, `external_consequence`, `participant_benefit`,
`fundable_reliability`. Failed sides: `settlement_capital_physics`,
`distribution_entanglement_counterposition`.

Package 3 is an internal invention proof. It has no buyer, no beneficiary, and no
external consequence. Marking those satisfied to obtain a green audit is exactly
the fabricated field the build order forbids, so the audit was answered
truthfully and comes out incomplete.

---

## Limitations — carried forward, not trimmed

Frozen before the result was known, plus two discovered during implementation.

1. **All four candidates were authored in one session by one author.**
   "Materially different" is bounded by one author's imagination. A stronger
   version would source a candidate from outside the session.
2. **The replaced component is stateless.** This answers *can function be
   restored* and says nothing about whether durable state survives replacement.
3. **The candidate set is fixed in advance.** Nothing generates novel
   implementations, so **this is not unscripted morphogenesis.**
4. Detection is blind to which module failed, but the capability contract it
   checks against was written by the same author as the candidates.
5. The held-out corpus is held out **in time** (frozen before candidates
   existed), not by an independent party.
6. No external effect, deployment, spending, or real-world data. The strongest
   verifier available is a deterministic invariant — nothing here is externally
   verifiable evidence.
7. **"Installation" registers the winner in this experiment's own provider
   registry.** It does **not** rewrite the kernel's live import path:
   `closure/kernel_registry.py` still imports the original directly and the
   harness never edits it. A test asserts this.
8. **Manifest loading is not replaced.** YAML parsing and schema validation are
   performed once by the original loader before the disable; only edge
   resolution is replaced, keeping the experiment's variable single.

`runtime_ms` varies slightly between runs, so `EVIDENCE_RECORD.json` is not
byte-reproducible. Every other field is.

---

## What this is, stated plainly

A **governed functional-replacement experiment.** It is **not** autonomous
regeneration, **not** unscripted morphogenesis, and **not** open-ended
self-repair. Nothing in this package generated a novel implementation, granted
itself authority, produced an external effect, or promoted anything.

What it does establish: UNIIMENTE can lose a working specialist function, notice
that loss without being told what broke, evaluate materially different
replacements with machinery it already had, install one, verify the restoration
blindly, roll back to the original, and come out the other side with its
Constitution, identity, authority, evidence chain and shutdown untouched.

And the boring answer won on cost. That is recorded as the recommendation.
