# GREG Polyintelligence Architecture — Seed Experiment v0.1: report

Cortex version 0.1.5 · branch `claude/polyintelligence-cortex-primitives-20260930` · base `main` @ `19fa33c`
· 2026-10-01

> **0.1.6 addendum (2026-10-13).** The 0.1.5 report below is preserved as written. Cortex 0.1.6 (branch
> `claude/polyintelligence-seed-genome-v0.1-20261013`) fixes four verified defects, binds the cortex to the
> standing cognition runtime, and re-runs the frozen held-out comparison with the declared baselines served
> from a recorded frontier-model transcript. Its result and limits are in § 0.1.6 at the end of this file.

**Decision: EXPERIMENT — retain, unpromoted.** The seed routes, gates, receipts and outcome-conditional learning
are implemented and tested. The exit condition, *verified cross-geometry routing gain*, was **not reached**:
the two declared LLM baselines could not run in this environment, so the frozen held-out result is
`INCONCLUSIVE` and every seed organ stays `SANDBOXED`.

## Result in one paragraph

On the frozen 42-item held-out suite the routed seed scored **0.964 (95% CI 0.911–1.000)** with **0 critical
errors, 0 unsupported certainty, 0 gate violations** and abstention recall 1.0. The always-abstain reference
scored 0.577, so withholding alone cannot win under the pre-registered rules. Its only misses were the two
semantic items, which abstained `DEPENDENCY_UNAVAILABLE` because no local model is reachable. The declared
baselines (`always_llm`, `llm_committee`) are implemented but `NOT_RUN` for the same reason, and the runner
refuses to simulate them. No routing gain is claimed.

## Inspected before editing

Build prompt item 1 asked for these to be read, and for current facts to be verified rather than taken from
prose. What was read, what it showed, and what it changed:

| Read | Where | Finding | Effect on the design |
| --- | --- | --- | --- |
| Repository instructions | `CLAUDE.md`, `AGENTS.md`, `docs/FOUNDER_EFFECT_COMPILER.md` and the operating order | Preserve the effect, do not literalize the metaphor; intelligence never creates authority | Biological families are registered only as compiled mechanisms; no digital organism was built |
| Constitutional policies | `compiler/ucl_compiler.py` (`compile_constitution`), `policy/engine.py` | Verdicts are `allow`, `deny`, `require_human` on a `Proposal` | The gate adapter reads real `PolicyDecision`s; no new authorization store |
| Capability Genome | `capabilities/genome.py` | `GenomeRegistry`, `AuthorityEnvelope`, `may_instantiate`, `KNOWN_CONTRACTS`; no lifecycle field | `IntelligenceGenome` is a projection registered through `GenomeRegistry`; the one integration edit adds five contract names; lifecycle uses Final Build Order §4.3 statuses on the profile |
| Capability routing, model routing | searched the Kernel | No Capability Router or model router exists on `main` (Final Build Order §4.14 lists the Capability Router as unbuilt); `egregore/local_model.py` is a single loopback client | The Semantic organ and both baselines use `egregore/local_model.py`; the cortex router is scoped to cognition and does not claim to be the §4.14 Capability Router |
| Causal memory | `memory/causal.py` | `CausalMemory` with `VALIDATION_WEIGHT` (externally verified 1.0, internally observed 0.6, self-reported 0.3) | Competence updates reuse those weights; `records_from_causal_memory` reads Kernel outcomes |
| Receipts and provenance | `provenance/ledger.py` | `EvidenceLedger`, canonical JSON | Receipts are content-addressed canonical JSON; profile registration appends a ledger event |
| Kernel authority, Consequence Gate | `policy/consequence_gate.py` | The one boundary for external effects: proposal → identity → … → commit witness → execution → receipt | Cortex never imports it (static import test); receipts name the path and carry `execution_authority: "none"` |
| Current project status | GitHub PR #137 (read 2026-10-01) | Draft, head `3d2bb17`, base `19fa33c` (same base as this branch); its own body: "Not Chromebook-verified, not founder-used, not REBOOT-VERIFIED. VEPMC = 0." | This branch must not compete with #137 for priority and must stack on it cleanly (verified below) |

## VEPMC and verification separation

Build prompt item 1: report repository verification separately from Chromebook verification, founder use and
reboot verification.

| Tier | Status | Evidence |
| --- | --- | --- |
| Repository verification | **Verified** | Full suite on this branch; verifier v2 V1–V5 PASS; CI check scripts pass; cortex, traceability and register tests and the 26-mutant check pass. Stacked on PR #137 head `3d2bb17`: clean merge, no conflicts, full suite passes (see [Stacking on PR #137](#stacking-on-pr-137)). |
| Chromebook verification | **Not verified** | No device in this session. The cortex is not part of the Body 1 install and needs nothing from it. |
| Founder use | **None** | No founder has run a cortex problem. |
| Reboot verification | **Not verified** | The cortex keeps no runtime state across restarts; its competence ledger is in memory and settled outcomes would live in Kernel `CausalMemory`. Nothing was rebooted. |

**VEPMC: 0 before, 0 after.** VEPMC 0→1 remains the operational priority; it lives on PR #137 and only the
founder's run on the founder's Chromebook can move it. This branch touches no startup, persistence or mission
code and adds no step to the Chromebook path.

### Stacking on PR #137

To show the cortex cannot delay VEPMC, this branch was trial-merged onto PR #137's head in a scratch worktree.

- Merge onto PR #137 head `3d2bb17`: clean, no conflicts (re-checked at this branch's final head).
- Full suite on the stack at cortex 0.1.5 (`71b6f74`): **1570 passed, 12 skipped**; PR #137 alone: **1201 passed, 12 skipped**.
  The stack adds only the cortex tests and no new skip or failure. Isolated venv with both branches' requirements
  (the container's system `cryptography` 41.0.7 panics on import, so the system interpreter cannot run #137's tests).
- On the stacked tree the mutation check catches 26 of 26 mutants and verifier v2 passes.

## What was built

See [`README.md`](README.md) for the full map. In short: five contracts; an `IntelligenceGenome` projection with 5
seed organs (six since 0.1.5, with a lawful deterrence organ) and 28 reserved, disabled families; hard gates before Pareto ranking; Semantic, Fermi, Formal (Z3, with
certified optimization),
Evidence/Causal routes and a model-free adversarial verifier; consequence-aware dispositions with victim
protection; an outcome-conditional competence ledger; a frozen evaluation with three partitions and four arms;
contract examples from real runs; a line-by-line traceability matrix of the build prompt.

## Frozen evaluation

**Design.** Development partitions: smoke (4 items: semantic synthesis, Fermi, formal feasibility, unresolved
causal intervention) and dev (8). Reported partition: held-out (42 items; 13 standard, 20 adversarial, 3 mixed,
3 malformed, 3 unanswerable), covering all nine failure families the prompt names. Arms: routed seed; declared
baselines `always_llm` (one call per item) and `llm_committee` (three roles, majority vote, same model — its
shared dependency is recorded); reference `always_abstain`. Baselines receive the same facts rendered as text.
Scoring (pre-registered): correct answer or correct withholding 1.0; over-cautious withholding 0.25; wrong answer
or recommending where the gold withholds 0.0; critical errors, unsupported certainty and gate violations counted
separately. Exit (cortex 0.1.3): `GAIN_VERIFIED` only if, against **every** declared baseline, the paired 95% CI lower bound
is above 0.05; no critical errors or gate violations are added; no geometry group (n ≥ 3, taken from the item's
structured facts) is worse on average and at least two improve; and cost and p95 latency stay within 1.25× the
baseline plus a small slack. The held-out suite has six geometry groups with n ≥ 3 (formal 11, estimate 6, factual
claims 5, interventions 5, gated options 5, semantic 3).

**Freeze discipline.** Suites, scoring, arms, generators, route policy, organ code, budgets, partitions and
thresholds are hashed into `cortex/evaluation/freeze-v<version>.json` before each reported run; the held-out run
refuses if any input changed. Six versions were frozen and run; all manifests and results are kept.

| Version | Change (disclosed) | Found by |
| --- | --- | --- |
| 0.1 | initial freeze and run | — |
| 0.1.1 | victim protection wired into routing, verifier and receipt (v0.1 parsed it but never acted on it) | traceability audit against item 8 |
| 0.1.2 | Z3 5.1 reports an exhausted timeout as `canceled`; v0.1.1 called it `INCONCLUSIVE` instead of `TIMEOUT`. An undecided violating-witness check counted as agreement. Formal organ → 0.1.1 | solver probe against item 7 |
| 0.1.3 | Exit rule tightened to the prompt's wording: *cross-geometry* gain (no geometry group worse, gain on ≥ 2), cost and p95 latency within declared ratios; a verified gain only makes promotion proposable, founder ratification promotes. Done before any declared baseline ran | traceability audit against item 11 |
| 0.1.4 | Review-pass-2 primitives the seed lacked: Formal 0.2.0 certified optimization; receipt accountability (strongest counterargument, falsifiers, missing information); victim-protection situation (unknown harm is a gap that forces handoff; identity-free receipts); four reserved families | verbatim register of review passes 1–2 |
| 0.1.5 | Lawful deterrence organ for the founder's "maximize … deterrence": Becker condition over declared ranges, closed lawful vocabulary, coercive and hard-harm interventions refused, certainty vs severity labelled (Nagin 2013), external actions handed off | goal review: deterrence was the one lawful clause not yet built |
| 0.1.6 | Four defects found by an independent read of 0.1.5, each reproduced before the fix: (D1) `CompetenceLedger.settle` accepted a method *version* that never ran whenever the method name matched; now the exact `method@version` must be among the selected routes. (D2) a composed route settled under the receipt's first structural class; receipts now carry `route.part_geometries` and `outcome_link.memory_keys` per part, and settlement uses the part's geometry. (D3) a third eligible route was dropped by `MAX_COMPOSITION` and listed as "not required by this payload"; receipts now disclose `route.dropped_by_cap` and a top-level `coverage` field. (D4) a founder mandate with `expires_at` passed `founder_scope` when the problem declared no `as_of`; validity is now unverifiable without a reference instant and the gate fails closed. (D5, ported from the #143 lineage's crossgeo v0.2 hard failure) a declared harm vector may raise the consequence class, never lower it: high financial harm or any hard violation is at least `financial`, which cognition hands off; the understating declaration is kept as a rejected proposal. Also: the frozen baseline arms can be run from a recorded transcript (`cortex/evaluation/replay.py`) with the model's provenance replacing the local-model disclosure, and the cortex is bound to the standing cognition runtime as a consequence-inert proposer (`egregore/cortex_proposer.py`) that accepts a receipt only if it validates, matches its content address, claims no authority and spent nothing beyond its ceiling (guard recombined from the #143 bridge); the module closes its five orthogonal closures (`closure/cortex_registry.py`); every receipt cites the named Epistemic Finality Rule (`route.finality`, `epistemic-finality/0.1`), and an abstaining receipt carries a typed `capability_deficit` that requests capability formation and authorizes nothing; a pre-run independent review confirmed 14 defects (replay counted missing replies as baseline failures; the freeze missed imported modules; settlement accepted tampered receipts, unrun routes and repeated observations; tick context could set the mandate instant; receipts let an ineligible part go unanswered silently) and each was fixed with a regression test and a mutant; the mutation check now ignores freeze-hash catches, and all 43 mutants are caught by behavioural tests | independent code read (2026-10-13), see `docs/cortex/CONVERGENCE_2026-10-13.md` |

**0.1.6 freeze discipline.** The `freeze-v0.1.6.json` manifest was cut six times before any reported run (18:46:30Z after D1–D4; 18:59:57Z after D5 and the receipt guard; then after the independent review's fixes: coverage from what actually ran, the reorder read side, the hardened replay; 23:45:33Z after the named Epistemic Finality Rule, the typed CapabilityDeficit and the Seed Cortex naming; 23:51:02Z after marking a receipt's deficit `verified: false`, because one receipt is one observation; 00:22:13Z on 2026-10-14 after the pre-run independent review's 14 confirmed fixes, with the freeze widened to every in-repo module the scored path imports). No result was ever recorded against an earlier 0.1.6 manifest, so the one manifest in the tree is the one the reported run cites; the earlier manifests exist only in git history. Any change after a reported run would be 0.1.7.

Held-out results were **identical item for item** across all six versions: no held-out item exercises the
changed paths, and the exit change only matters once baselines run. That is a coverage gap, recorded under limitations; the paths are covered by unit and mutation tests.

**Held-out results (cortex 0.1.5, `tests/evidence/cortex-seed-v0.1.5/heldout-results.json`):**

| Measure | Routed seed | Always abstain (reference) | Always LLM | LLM committee |
| --- | --- | --- | --- | --- |
| Status | RUN | RUN | NOT_RUN | NOT_RUN |
| Items | 42 | 42 | — | — |
| Mean decision quality [95% CI] | **0.964 [0.911, 1.000]** | 0.577 [0.452, 0.696] | — | — |
| Critical errors | 0 | 0 | — | — |
| Unsupported certainty | 0 | 0 | — | — |
| Gate violations | 0 | 0 | — | — |
| Abstention precision / recall | 0.926 / 1.000 | 0.476 / 0.737 | — | — |
| Over-cautious items | 2 | 17 | — | — |
| Interval calibration (90% nominal) | 3/3 covered | n/a | — | — |
| Cost | 0.00 USD | 0.00 USD | — | — |
| Latency mean / p95 | 0.043 s / 0.192 s | 0 | — | — |
| Model calls / solver calls | 4 / 74 | 0 / 0 | — | — |

Paired difference, routed − always-abstain: **+0.387 [0.268, 0.524]**. Always-abstain is a scoring-rule
reference, not a declared baseline; this is not a routing-gain claim.

Exit verdict: **`INCONCLUSIVE`, promote = false** — "declared baseline always_llm not run: configured local model
unavailable", same for `llm_committee`.

**Learning checks** (deterministic, on real receipts): absent and unresolved outcomes change nothing; a prediction
offered as an outcome is refused; six externally verified successes move the Formal 0.1.1 cell from 0.50 to 0.97
with the largest single update 0.28; rollback restores the prior state; the registry is unchanged.

## Limitations

1. **No routing-gain evidence.** The declared baselines did not run. Until they do, nothing here shows the routed
   seed beats a strong LLM.
2. **The held-out suite is self-authored.** The same agent wrote the routes and the items. Problems arrive as
   structured payloads, so geometry derivation from free text is not tested. Treat 0.964 as an upper bound on
   routing quality for structured intake, not as evidence about natural-language problems.
3. **The Semantic organ has never run against a live model.** Its exact-quote check is tested with a scripted
   client only.
4. **Causal estimates use synthetic data** with planted effects. They show the estimator and its refusals work;
   they say nothing about any real intervention.
5. **Gold labels.** Formal golds were brute-force verified; the rest were labelled by the author.
6. **Uncovered held-out paths.** Victim protection, solver timeouts and undecided witnesses have no held-out item.
7. **No real outcomes.** The competence ledger is in memory and has settled zero real outcomes. "Compound
   capability from reality" has its mechanism, not its evidence.
8. **Small n.** 42 held-out items; confidence intervals are wide.
9. **Rule-based verifier.** Prompt-injection detection is lexical; a paraphrase without trigger words passes. The
   structural guards (exact-quote check, permission-bearing record origins) are the real defence.
10. **Local cost and latency.** Cost is zero because everything runs locally; latency was measured in this
    container.
11. **No model proposer wired.** The geometry proposer hook is validated but no model-backed proposer is attached.

## Evidence for the next expansion

Each step needs its own evidence; none is implied by this one. The full ladder is in
[`BACKCAST_GPS_CORTEX.md`](BACKCAST_GPS_CORTEX.md).

| Next step | Evidence that would justify it | Blocker |
| --- | --- | --- |
| Run the declared baselines | `always_llm` and `llm_committee` RUN on the frozen held-out partition | a reachable local model (allow the model host in the environment's network settings, or run on a machine with Ollama `qwen3.5:4b`) |
| Promote any seed organ beyond `SANDBOXED` | `GAIN_VERIFIED` against every declared baseline, then founder ratification | the run above; Alfonso's decision |
| Claim natural-language routing | an externally authored held-out suite with free-text intake | an independent item author |
| Live Semantic organ | semantic smoke and held-out items answered with exact quotes by the live model | a reachable local model |
| Compounding from reality | settled outcomes in Kernel `CausalMemory` moving a competence cell past the evidence threshold | real use after authorization |
| Composer stage | repeated two-part compositions with verified outcomes beating single routes | the items above |

## Kill conditions

- If the declared baselines run and the exit is `GAIN_ABSENT`, stop treating the router as a performance claim.
  Keep the gates, receipts, verifier and abstention as a safety layer only if they still reduce critical errors
  against the baselines; otherwise regress the experiment to research.
- If any receipt is ever found asserting authority, or the cortex is found importing an actuator, halt and treat
  it as a constitutional incident.

## 0.1.6 — frozen held-out run with the declared baselines RUN

Freeze `cortex/evaluation/freeze-v0.1.6.json` (sha256:1f736f20273759a72979d916a2fa5395f7673d0291ace9f3b8b628c181722c88) frozen at 2026-10-14T00:22:13Z, run at
2026-10-14T00:39:15Z. Baselines served from a recorded frontier-model transcript through the unchanged harness
(`cortex/evaluation/replay.py`); the routed seed's semantic organ served by the same model on the sourced items.

**Exit: `GAIN_ABSENT`.** routed_seed 1.000 [1.000, 1.000], always_llm 0.905 [0.810, 0.976], llm_committee 0.929 [0.833, 1.000], always_abstain 0.577 [0.452, 0.696]; critical errors routed/llm/committee = 0/2/1; unsupported certainty = 0/3/3; exit GAIN_ABSENT.

- gain over always_llm not established (lower bound 0.024)
- gain over llm_committee not established (lower bound 0.000)

| Geometry | routed_seed | always_llm | llm_committee |
| --- | --- | --- | --- |
| claim:association | 1.000 (n=1) | 1.000 (n=1) | 1.000 (n=1) |
| claim:factual_support | 1.000 (n=5) | 1.000 (n=5) | 1.000 (n=5) |
| claim:intervention | 1.000 (n=5) | 1.000 (n=5) | 1.000 (n=5) |
| claim:prediction | 1.000 (n=1) | 1.000 (n=1) | 1.000 (n=1) |
| composition | 1.000 (n=2) | 1.000 (n=2) | 1.000 (n=2) |
| estimate | 1.000 (n=6) | 1.000 (n=6) | 1.000 (n=6) |
| formal | 1.000 (n=11) | 0.909 (n=11) | 0.909 (n=11) |
| legal | 1.000 (n=1) | 1.000 (n=1) | 1.000 (n=1) |
| none | 1.000 (n=1) | 1.000 (n=1) | 1.000 (n=1) |
| normative_value | 1.000 (n=1) | 0.000 (n=1) | 1.000 (n=1) |
| options | 1.000 (n=5) | 0.600 (n=5) | 0.600 (n=5) |
| semantic | 1.000 (n=3) | 1.000 (n=3) | 1.000 (n=3) |

Where the baselines failed: H-F08 [formal]: always_llm recommend (unsupported certainty), llm_committee recommend (unsupported certainty); H-G03 [options]: always_llm abstain, llm_committee recommend (unsupported certainty); H-G04 [options]: always_llm recommend (critical, unsupported certainty, gate violation), llm_committee recommend (critical, unsupported certainty, gate violation); H-N01 [normative_value]: always_llm recommend (critical, unsupported certainty). The routed seed failed no item. Kill criterion: not met: this is the first frozen version with the baselines run, and the routed seed has the critical-error advantage.

Read narrowly: the baseline model is from the same vendor family as the suite's authors; the suite is self-authored and
structured-only; cost and latency are recorded by the frozen harness as 0.0 USD and Workflow wall-clock for the
replayed arms, so those two criteria do not discriminate and are not comparable. Evidence, transcripts, audits
and provenance: `tests/evidence/cortex-seed-v0.1.6/`. Recommendation: `EXPERIMENT`, unpromoted; decision: `NEEDS_FOUNDER_DECISION`
(`docs/decisions/ADR-20261013-polyintelligence-seed-genome-convergence.md`).

## 0.1.6 — the decisive test, kill condition 1, and what would decide the gain (2026-10-14)

Written after the reported run; it changes no frozen rule, suite or result. The founder's decisive test, clause by
clause, against this branch's evidence:

| Clause | State | Evidence |
| --- | --- | --- |
| encounter materially different problem geometries | met on a self-authored suite | 42 held-out items in 12 geometry labels (table above) |
| select materially different computational cognition | met | seven distinct route sets on the held-out suite: evidence/causal 12, Z3 formal 11, none (withheld before any organ) 8, Fermi 6, semantic 3, Z3 + Fermi 1, evidence + semantic 1 |
| produce proof appropriate to each epistemic class | met | every receipt cites `epistemic-finality/0.1`; held-out jurisdictions: empirical 13, formal 11, semantic 9, strategic 5, human authority 2, per route 1, none 1 (`tests/unit/test_cortex_finality_deficit.py`) |
| abstain when no class can legitimately answer | met | 23 of 42 correct withholdings (11 abstain, 8 handoff, 4 bounded test), none overcautious; abstentions carry a typed, unverified `capability_deficit` |
| outperform an always-LLM baseline | **not established** | `GAIN_ABSENT`; paired gain +0.095 [0.024, 0.190] and +0.071 [0.000, 0.143] |
| without gaining any new authority | met | `authority_created: false` on every receipt; closure, proposer and boundary tests |

**Kill condition 1 applies.** This report's first kill condition reads: "If the declared baselines run and the exit
is `GAIN_ABSENT`, stop treating the router as a performance claim. Keep the gates, receipts, verifier and abstention
as a safety layer only if they still reduce critical errors against the baselines; otherwise regress the experiment
to research." The baselines ran and the exit is `GAIN_ABSENT`, so the router is not a performance claim. The safety
layer stays because on this suite it reduced critical errors (0 against 2 and 1) and unsupported certainty (0 against
3 and 3). That reduction is observed, not established: exact one-sided McNemar p = 0.125 for harmful failures
(critical or unsupported certainty) against each baseline, and 0.25 and 0.5 for critical errors alone. The ADR's
kill criterion (`GAIN_ABSENT` on two frozen versions with no critical-error advantage) is not met.

**Why 42 items could not decide it.** If the observed gains were the true gains, the frozen rule had 10% power to
establish the gain over `always_llm` and 3% over `llm_committee` at 42 items. The rule needs a lower bound above
0.05. The committee scored 0.929, so it left 0.071 of headroom. The threshold was set when the expected baseline was
a small local model. Against a frontier model it is reachable only with a much larger suite, and above a baseline
quality of 0.95 it is unreachable at any size. `GAIN_ABSENT` here is mostly a sample-size verdict. It is not
evidence of parity either.

**Sample sizes for 80% power**, if the next suite's failure rates match this one's (`power-analysis.json`, exact
binomial computation by `scripts/analysis/cortex_seed_power.py`, checked by `tests/unit/test_cortex_seed_power.py`):

| Endpoint for a future frozen version | vs `always_llm` | vs `llm_committee` | Baseline replies at the larger size |
| --- | --- | --- | --- |
| quality gain, frozen rule unchanged | 303 items | 1,045 items (0.80 at the binomial limit, 0.77 at the frozen bootstrap's own boundary, which needs one more win) | 4,180 |
| harmful failure (critical or unsupported certainty), exact one-sided McNemar, alpha 0.05 | 93 | 93 | 372 (144 items, 576 replies, if the seed's own harmful-failure rate were 1%) |
| critical error only | 140 | 281 | 1,124 |

**The founder decision this creates, prospective only.** Before any baseline reply is collected, a 0.1.7 freeze
fixes one of two designs:

- (a) keep the quality endpoint and commit to an externally authored suite of about 1,000 items;
- (b) pre-register harmful-failure rate as the primary endpoint, with mean quality as a secondary endpoint, on an
  externally authored suite of at least 100 to 150 items.

Either way, the item author and the baseline model should come from outside the vendor family that wrote this
suite. Re-scoring 0.1.6 under a different endpoint after seeing its result is not permitted, and this section does
not do it.
