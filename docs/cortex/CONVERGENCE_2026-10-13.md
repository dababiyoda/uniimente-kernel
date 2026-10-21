# Polyintelligence Seed Genome v0.1 — convergence record (2026-10-13)

Branch `claude/polyintelligence-seed-genome-v0.1-20261013` · base `main` @ `19fa33c` · carries PR #141 at `ebc2130`
unchanged, then cortex 0.1.6 · intent `INTENT-20261013-polyintelligence-seed-genome-v0.1`.

This record answers the eight questions of the anti-literalization gate (`docs/FOUNDER_EFFECT_COMPILER.md`) for the
founder's 2026-10-13 directive and says exactly what this branch adds, adopts, recombines and leaves open.

## 1. Founder expression and lineage

The message is preserved byte for byte (preface verbatim, rebuild rule for the rest, sha256 `de5db69c…`) in
`docs/intent/sources/POLYINTELLIGENCE-SEED-GENOME-FOUNDER-EXPRESSION-2026-10-13.md`. Its operative parts:

- "Build this: … in GitHub" + the Goal set ("maximize evidence, institutional leverage, accountability, deterrence,
  victim protection, and minimal collateral harm … anchoring the entire framework at its absolute meniscus …
  impermeable, self-reinforcing shield of total systemic dominance");
- the directive's own translation rules: *meniscus* = the frontier of the verified permission, rights, safety,
  resource and evidence envelope with margins kept; *impermeable shield* = layered prevention, bounded failure,
  independent verification, recoverability, demonstrated attack resistance; *systemic dominance* = superior lawful
  capability, accepted proof, reliable service, reusable assets, participant benefit, durable optionality — none of
  which licenses control over people, resistance to shutdown or promises of perfection;
- "The intended engineering result is a Competency Compiler";
- the review's closing proposal, "Polyintelligence Seed Genome v0.1 … Implement only: …", and its eight corrections
  (section 63), which "Build this" adopts as the approved scope;
- "NOTHING IS DISCONNECTED, everything is modular and part of the whole."

## 2. Intended observable effect

The same GREG can take materially different problem geometries, select materially different computation, return
proof typed to the epistemic class, abstain when no class can legitimately answer, and be compared against an
always-LLM baseline on a frozen suite, all without gaining any authority. The effect is measured by the frozen
held-out comparison and by the runtime binding tests, not by resemblance to any metaphor.

## 3. Literal requirements versus metaphor

Literal: the contracts and organs the review lists; a baseline comparison; a competency ledger per geometry; hooks
for later families; a PR in GitHub. Metaphor: cortex, organ, genome, seed, egregore, meniscus, shield, dominance.
Every biological concept on a genome must compile to a mechanism, state, interface, feedback loop, test and failure
condition or registration is refused (`cortex/genome.py`; enforced by test).

## 4. What already existed (searched before building)

Sixteen open draft pull requests implement overlapping seeds (thirteen when this work began; #161, #162 and #163 were
opened by parallel sessions the same day); two of them are main-compatible, and two further main-based lineages are
adjacent. The full inventory with each
lineage's own measured results and a disposition is `docs/cortex/COGNITION_LINEAGES.json`
(`tests/unit/test_cognition_lineages.py`). Decision:

| Lineage | Disposition | Why |
| --- | --- | --- |
| #141 `cortex/` (main-based, 27 commits, CI green, frozen eval, 26/26 mutants) | **PRODUCTIZE** — base of this branch | Implements the review's approved list almost entirely: ProblemGeometry, IntelligenceGenome profile, 13 epistemic classes, proof classes, harm vector, receipts, abstention, deterministic router, Semantic/Fermi/Formal(+certified optimization)/Evidence-Causal organs, adversarial verifier, reverse translation + counterexample search, frozen baseline harness, CompetenceLedger (method × version × geometry × conditions), 28 reserved disabled families |
| #139 `egregore/cognition` (main-based) | **RECOMBINE** | Its `CortexProposer` seam is the one thing #141 lacked: a binding into `StandingCognitionRuntime`. Ported with credit as `egregore/cortex_proposer.py`, with the runtime test #139 did not have. The rest stays a registered competing implementation |
| #140, #142, #143, #145, #151, #153, #154, #155, #156, #157, #158, #161, #162, #163 (carry #137) | **RETAIN_AS_EVIDENCE** (+ mechanism source) | They cannot reach `main` before #137 is decided. Their results are registered as their own claims; the mechanisms worth porting afterwards are named per lineage. #162 calls itself evidence-only and not a merge candidate |
| #160 Goal Gravity (main-based) | ADJACENT | Not a cognition seed; a natural caller of the proposer. A trial merge conflicts at three append-only sites (closure registry, intent ledger, verifier criteria); keeping both sides passes the full suite and verifier V1–V5 |
| #129 Capability Genesis Loop (main-based) | ADJACENT | Not a cognition seed: the recurrence-verified capability-formation loop a cortex abstention's `capability_deficit` hands off to. A trial merge is textually clean and passes the full suite; the adapter from a receipt's geometry deficit to its per-cycle deficit kinds is not built |

Another implementation written from scratch was the obvious move and the wrong one: it would have duplicated
#141 and #139 and violated "one authority, many governed capabilities" (`UNIIMENTE_FINAL_BUILD_ORDER.md` §3, §9).

## 5. Residual CapabilityDeficit closed on this branch

1. **The declared baselines had never run.** Every lineage reports `always_llm` / `llm_committee` as `NOT_RUN`
   because no model is reachable from the evaluation process, so every exit was `INCONCLUSIVE`.
   `cortex/evaluation/replay.py` lets the unchanged frozen harness, scorer and exit rule run those arms from a
   recorded transcript: a reply is keyed by `sha256(system + NUL + user)`, so it can only serve the exact prompt
   the frozen arm would have sent; a missing reply is an error on that item, never a guess; the model's provenance
   replaces the harness's local-model disclosure on the results. The replies were produced by tool-free
   frontier-model agents (one fresh context per item/arm/role, every reply from one Anthropic frontier model, labelled frontier-model-A) and audited post
   hoc. Result on the 42 frozen held-out items: routed seed 1.000 with no critical error; always-LLM 0.905 with two;
   committee 0.929 with one. The frozen rule needs a paired-gain lower bound above 0.05 and found 0.024 and 0.000, so
   the verdict is `GAIN_ABSENT`; the kill criterion is not met because the seed holds the critical-error advantage.
   Details: `tests/evidence/cortex-seed-v0.1.6/` and `SEED_EXPERIMENT_REPORT.md` § 0.1.6.
2. **Four defects in 0.1.5, found by an independent code read and reproduced before being fixed** (regression
   tests in `tests/unit/test_cortex_defect_fixes.py`): wrong-version settlement; composed routes settled under the
   first part's geometry; routes dropped by the composition cap described as "not required"; an expiring mandate
   passing `founder_scope` without an `as_of`. Cortex 0.1.6 was frozen before its reported run.
3. **No caller on `main`.** `egregore/cortex_proposer.py` attaches the cortex to the standing cognition runtime's
   existing proposer slot: every receipt is ledgered (abstentions are traces too), `recommend` becomes a
   `draft.prepare` review candidate, `handoff` becomes a `human.adjudicate` candidate, both `internal_write` with
   `execution_authority: none`; the semantic organ's model budget is clamped to what the proposer may spend.
4. **The lineages were disconnected from one another.** The registry above connects them without merging them.
5. **The founder's words were not yet preserved for this message.** They are, with a byte-exact rebuild test.

## 6. Why this beats the simplest viable alternative

Simplest viable: open a PR that re-labels #141 as "approved". It would leave the exit `INCONCLUSIVE`, the four
defects live, no caller on `main`, and sixteen lineages uncoordinated. Strongest competitor: #143's bridge on the
#137 stack, which has the only measured gain (narrow, against run baselines, no model arm) but cannot reach `main`
until #137 does. Do nothing: the seed stays off `main` and the directive stays unexecuted. Reversible experiment:
this branch — additive commits, no activation, revert restores `main`.

## 7. What remains open (not silently narrowed)

- No real outcome has settled competence; `CompetenceLedger` is in-memory and the causal-memory writer does not
  exist yet (reader finding, `cortex/memory.py` L199).
- The held-out suite is self-authored and structured-only; a free-text, externally authored suite is the next
  evidence step (review C1 exit: "router materially outperforms always-LLM baseline on a frozen cross-geometry
  suite").
- The semantic organ has never run against a live local model; in the reported run it was served by a recorded
  transcript of the baseline model.
- The composition cap (two routes) is now disclosed, not lifted; lifting it is 0.1.7 work with its own freeze.
- Mechanisms from the lineages that carry #137 (one-entry bridge, open-source engine certification, Layer-5 compile
  with mental-model operators, genome admission harness, lawful leverage foundry, resilience projection, second-engine
  solver cross-checks, legitimacy records, selective-disclosure evidence packages) are queued behind the #137 decision.
- The handoff from a receipt's unverified `capability_deficit` to #129's recurrence-verified loop needs an adapter and
  #129 on `main`; until then a cortex abstention reaches that loop only as a runtime silence streak.
- VEPMC stays 0; nothing here runs on the founder's Chromebook. Per the 2026-10-02 completion correction, that is
  the required device proof and the primary node, and it does not pause buildable software.

## 8. Falsification

The claimed effect is false if, on the frozen held-out suite with both declared baselines `RUN`, the exit is
`GAIN_ABSENT` on two frozen versions with no critical-error advantage (kill criterion inherited from
`deliberation-polyintelligence-cortex-20260930.json`), or if any receipt or candidate is found asserting authority,
or if the cortex is found importing an actuator. The first condition is now testable for the first time.

## Authority

No new authority. No external consequence. Building ≠ installation ≠ activation ≠ consequence authority. Merging,
attaching the proposer to a live runtime, and promoting any organ are founder decisions.
