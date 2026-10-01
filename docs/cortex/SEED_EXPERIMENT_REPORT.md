# GREG Polyintelligence Architecture — Seed Experiment v0.1: report

Cortex version 0.1.4 · branch `claude/polyintelligence-cortex-primitives-20260930` · base `main` @ `19fa33c`
· 2026-10-01

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
| Repository verification | **Verified** | Full suite on this branch; verifier v2 V1–V5 PASS; CI check scripts pass; cortex, traceability and register tests and the 22-mutant check pass. Stacked on PR #137 head `3d2bb17`: clean merge, no conflicts, full suite passes (see [Stacking on PR #137](#stacking-on-pr-137)). |
| Chromebook verification | **Not verified** | No device in this session. The cortex is not part of the Body 1 install and needs nothing from it. |
| Founder use | **None** | No founder has run a cortex problem. |
| Reboot verification | **Not verified** | The cortex keeps no runtime state across restarts; its competence ledger is in memory and settled outcomes would live in Kernel `CausalMemory`. Nothing was rebooted. |

**VEPMC: 0 before, 0 after.** VEPMC 0→1 remains the operational priority; it lives on PR #137 and only the
founder's run on the founder's Chromebook can move it. This branch touches no startup, persistence or mission
code and adds no step to the Chromebook path.

### Stacking on PR #137

To show the cortex cannot delay VEPMC, this branch was trial-merged onto PR #137's head in a scratch worktree.

- Merge: clean, no conflicts.
- Full suite on the stack: **1297 passed, 12 skipped** (isolated venv with both branches' requirements; the
  container's system `cryptography` 41.0.7 panics on import, so the system interpreter cannot run #137's tests).
- PR #137 alone, same venv: **1201 passed, 12 skipped**. The stack adds exactly the cortex tests (+96) and no
  new skip or failure. (Stack measured at `3faea61`; re-measured at the final head before the PR is opened.)

## What was built

See [`README.md`](README.md) for the full map. In short: five contracts; an `IntelligenceGenome` projection with 5
seed organs and 28 reserved, disabled families; hard gates before Pareto ranking; Semantic, Fermi, Formal (Z3, with
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
refuses if any input changed. Five versions were frozen and run; all manifests and results are kept.

| Version | Change (disclosed) | Found by |
| --- | --- | --- |
| 0.1 | initial freeze and run | — |
| 0.1.1 | victim protection wired into routing, verifier and receipt (v0.1 parsed it but never acted on it) | traceability audit against item 8 |
| 0.1.2 | Z3 5.1 reports an exhausted timeout as `canceled`; v0.1.1 called it `INCONCLUSIVE` instead of `TIMEOUT`. An undecided violating-witness check counted as agreement. Formal organ → 0.1.1 | solver probe against item 7 |
| 0.1.3 | Exit rule tightened to the prompt's wording: *cross-geometry* gain (no geometry group worse, gain on ≥ 2), cost and p95 latency within declared ratios; a verified gain only makes promotion proposable, founder ratification promotes. Done before any declared baseline ran | traceability audit against item 11 |
| 0.1.4 | Review-pass-2 primitives the seed lacked: Formal 0.2.0 certified optimization; receipt accountability (strongest counterargument, falsifiers, missing information); victim-protection situation (unknown harm is a gap that forces handoff; identity-free receipts); four reserved families | verbatim register of review passes 1–2 |

Held-out results were **identical item for item** across all five versions: no held-out item exercises the
changed paths, and the exit change only matters once baselines run. That is a coverage gap, recorded under limitations; the paths are covered by unit and mutation tests.

**Held-out results (cortex 0.1.4, `tests/evidence/cortex-seed-v0.1.4/heldout-results.json`):**

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
