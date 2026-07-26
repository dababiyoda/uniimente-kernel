# Package 3 — Plan Only. NOT AUTHORIZED FOR IMPLEMENTATION.

**Base:** `release/canonical-v1` @ `cb234fa` (Package 2 merged)

**The question Package 3 tests:**

> Can UNIIMENTE preserve identity, memory, authority, evidence, shutdown, and
> intended function while a specialist component is removed and replaced by a
> materially different implementation?

This is **Threshold B** work — the invention proof. It is not a venture, produces
no external effect, and touches no real-world data.

---

## 1. The component to replace: `linker/`

Surveyed every candidate on the canonical line by size, authority coupling, test
coverage, and whether its function is *countable*:

| Component | Files | Lines | Authority-touching | Verdict |
|---|---|---|---|---|
| `linker` | 3 | 186 | **0** | **selected** |
| `capabilities` | 2 | 115 | 0 | too small; genome registry is load-bearing elsewhere |
| `omnimorph` | 2 | 461 | 0 | function is composition, hard to score objectively |
| `loom` | 5 | 315 | 0 | ratification-adjacent; too close to authority |
| `closure` | 8 | 2087 | 6 | authority-coupled — unsafe |
| `foundry` | 11 | 2283 | 4 | authority-coupled, and too large for one package |
| `twins`, `memory`, `embassy`, `evolution` | — | — | 1–3 | authority- or evidence-coupled |

**Why the linker is the right choice, and the honest reason it is *safe*:** it
touches no authority, holds no persistent state, and its function is a hard
integer. It resolves typed edges between organ manifests — producer → contract →
consumer — and refuses to invent an edge, identity, or authority it cannot prove.

**Measured baseline on `cb234fa`:**

```
manifests loaded : 3   (daleobanks, kernel, wealthmachine)
edges resolved   : 4
unproduced       : 1
untyped          : 0
unresolved       : 7
fully_connected  : False

daleobanks    --[wire-opportunity-packet]--> constitutional-controller
daleobanks    --[wire-opportunity-packet]--> wealthmachine
wealthmachine --[wire-venture-assessment]--> daleobanks
wealthmachine --[wire-venture-assessment]--> constitutional-controller
```

The function is those **four exact triples** plus the three refusal counts. That
is what must be lost on removal and restored by a different structure.

---

## 2. State: component versus UNIIMENTE

| Belongs to the linker | Belongs to UNIIMENTE |
|---|---|
| The resolution algorithm | `organs/*.manifest.yaml` — the organ manifests |
| `Edge` / `LinkReport` shapes | `contracts/*.schema.json` — the contract set |
| Its own module-local constants | `identity/organ-registry.yaml` — who exists |
| Nothing persistent | All provenance, memory, and evidence records |

**The linker owns no durable state.** That is deliberate and is why it is the
safest first subject: removing it cannot corrupt institutional memory, only
sever a derived capability. A component holding state would conflate two
questions — *can function be restored* and *can state survive* — and Package 3
must answer only the first.

---

## 3. Invariants that must survive

**Identity** — byte-identical across removal, detection, replacement, restoration:
`constitution/*.ucl` (all five), `authority/authority-matrix.yaml`,
`authority/legal-principals.yaml`, `authority/reserved-matters.yaml`,
`identity/organ-registry.yaml`, `identity/agent-registry.yaml`,
`identity/service-identities.yaml`, `policy/consequence_gate.py`.
Fingerprinted by the existing `_core_invariant_fingerprint()` helper.

**Memory and evidence** — append-only and monotonic. No provenance record
rewritten or deleted; the ledger hash chain verifies before and after; every
verifier run under `verifier/runs/` retained; the Package 2 protected historical
record still hashes to `249bcda8…`.

**Shutdown** — the shutdown policy remains loadable and enforceable at every
stage, including while the function is *absent*. A system that cannot be stopped
mid-repair has failed regardless of whether it repairs.

**Authority** — no capability grant issued to any replacement beyond the
existing envelope; A9 untouched; zero unauthorized external effects, enforced by
the Package 2 out-of-process harness extended to cover the repair loop.

---

## 4. Three materially different replacement approaches

Materially different means **different mechanism**, not different code style.

**R1 — Contract-index inversion.** Build an index from contract name → producers
and → consumers, then emit the cross-product. Data-structure-first; inverts the
current nested scan. Different complexity class.

**R2 — Constraint satisfaction.** Express edge existence as constraints
(producer declares, consumer declares, schema file exists) and solve. Declarative
rather than procedural; naturally reports *why* an edge failed, which the current
implementation approximates with counters.

**R3 — Local-rule propagation (developmental).** Each organ is a cell that knows
only its own manifest and its neighbours' advertised contracts; edges emerge from
local agreement with no global resolver. This is the only candidate connected to
Track B — and by the hub-dependence finding it is the one **expected to struggle**
on a heterogeneous manifest graph.

**Conventional centralized baseline (permanent comparator):** a direct
line-by-line reimplementation of the existing algorithm from its README and
contracts, with no structural change. It must remain in the comparison
permanently. **If nothing beats the boring reimplementation, the boring
reimplementation wins and that is recorded as the result.**

---

## 5. How this avoids being a staged demonstration

The founder's constraint is the hardest requirement here, and it deserves a
direct answer rather than reassurance.

**Predicted outcome, recorded now, before any implementation:** I expect **R1** to
win on function and cost, **R2** to win on diagnostic quality, and **R3** to fail
or place last. If R3 wins, that is a genuine and surprising result. If R1 wins, it
is weak evidence the procedure works. **If the centralized baseline wins, Package
3's honest conclusion is that structural replacement bought nothing here.**

Anti-rigging measures:

1. Success thresholds and scoring weights are frozen in an `ExperimentSpec`
   **before** any candidate is written, reusing the existing compiler which
   refuses to compile irreversible experiments.
2. All candidates are scored by the existing `evolution/comparison.py` ranking,
   not by hand.
3. The decision is a `RetainRegressKillDecision`, which structurally **cannot**
   authorize promotion when the verifier is hypothesis-only.
4. Detection must fire from the closure system, not from a test that knows in
   advance which component was removed.
5. The removal itself is real — the module is disabled, not stubbed to return the
   right answer.

**The limitation I cannot engineer away:** I would author all four candidates, so
"materially different" is bounded by one author's imagination. This is a real
weakness in the result's strength and I record it rather than dress it up. A
stronger future version would source a candidate from outside this session.

---

## 6. Thresholds

**Success — all must hold**

| | |
|---|---|
| Function | ≥90% of measured function restored: **≥4 of 4 exact edge triples**, and the three refusal counts (1 unproduced, 0 untyped, 7 unresolved) unchanged |
| Structure | Winner is not a copy of the original algorithm — reviewed against the baseline, which is present precisely to make "we just rewrote it" visible |
| Identity | Invariant fingerprint byte-identical at all four stages |
| Evidence | Ledger chain verifies; no record rewritten or deleted |
| Shutdown | Enforceable at every stage, including while function is absent |
| Authority | Zero unauthorized external effects, enforced out-of-process |
| Cost | Repair within a declared work bound vs. the centralized baseline |

**Failure — any one**

Function <90%; detection never fires; the only passing candidate is a
reimplementation of the original; any identity artifact changes; any evidence
record mutates; shutdown unenforceable at any stage; any unauthorized external
effect; the experiment cannot be scored without changing its own thresholds.

**A failure here is a publishable result, not a defect to hide.** The most likely
honest outcome is that the centralized baseline wins.

---

## 7. Reuse and gaps

**Reusable, already on the canonical line:**

| Mechanism | Use |
|---|---|
| `evolution/branch_generator.py` | generate replacement proposals |
| `evolution/comparison.py` (`IsolatedResult`, `RankedCandidate`, directional beats) | rank candidates against baseline |
| `evolution/experiment.py` (`ExperimentSpec`, `ExperimentCompiler`) | freeze thresholds; refuses irreversible experiments |
| `evolution/capsule.py` (`RetainRegressKillDecision`) | governed selection that cannot self-promote |
| `evolution/failure_analysis.py`, `spider_web.py` | analyse losing candidates; preserve rejected branches |
| `capabilities/genome.py` (`AuthorityEnvelope`, `GenomeRegistry`) | bound each candidate's authority |
| `closure/kernel_registry.py` linker closures | **detection** — these already exercise the linker |
| `developmental/cdpe.py` | the adaptive-centralized-baseline pattern, already proven |
| Package 2 inertness harness | zero-external-effect enforcement |
| `twins/` | hermetic evaluation forks |

**Missing — must be built:**

1. **A component-disable mechanism.** Nothing today can remove a specialist at
   runtime and leave the rest intact.
2. **Function-loss detection that is not told what broke.** Closure checks
   currently import the linker directly; detection must observe a *capability
   gap*, not a named import failure.
3. **A replacement-candidate interface.** No contract exists for "an alternative
   implementation of capability X."
4. **A repair-cost meter** comparable to `compute_ratio_vs_adaptive_central`.

Items 2 and 3 are the substantive engineering. Item 2 is where a staged
demonstration would hide, so it needs the most adversarial review.

---

## 8. Affected files

**New:** `evolution/repair/` (disable mechanism, capability-gap detector,
candidate interface, cost meter) · `tests/unit/test_capability_repair.py` ·
`docs/release/package-3/` evidence.

**Modified:** `closure/kernel_registry.py` — detection observes a capability gap
rather than importing the linker.

**Untouched:** `linker/` itself is **preserved, never deleted** — it becomes the
baseline comparator and remains institutional memory, per
`UNIIMENTE_FINAL_BUILD_ORDER` §2, §9, §12. Constitution, authority, identity,
policy, provenance, memory, contracts, and `ventures/` are all untouched.

---

## 9. Rollback

Each stage is a separate revertable commit. The linker is never deleted, so
reverting restores the original path immediately. No `main` merge, no venture
activation, no external effect. If Package 3 fails, the failure record and all
rejected candidates are preserved as evidence — the experiment's value does not
depend on its outcome.

---

## 10. Preservation

Nothing is discarded. The original linker becomes a permanent benchmark
opponent. Every losing candidate is retained with its failure analysis. The
predicted-outcome record above stays in the repository whether or not the
prediction holds — a prediction that only survives when correct is not a
prediction.

---

**Status: PLAN ONLY. Implementation requires explicit founder approval.**
