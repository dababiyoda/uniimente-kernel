# ADR: Wire the Competency Compiler into the Goal Gravity loop

- Decision ID: ADR-GOAL-GRAVITY-002 (linked to ADR-GOAL-GRAVITY-001)
- Status: proposed (draft PR #160, third increment; adoption into `main` is a founder decision)
- Date: 2026-10-14
- Decision owner: Alfonso Lopez
- Deliberation level: Constitutional (shared contracts, evidence semantics, a founder-gated attach path)
- Founder intent references: `INTENT-20261013-GOAL-GRAVITY`, `INTENT-20261014-competency-compiler` (main, #165), `INTENT-0030`, `SR001-FOUNDER-LOOP-ENTRY`
- Deliberation record: `docs/collaboration/deliberation-competency-compiler-wiring-2026-10-14.json` (validator exit 0)

## Problem

**Observations.** The directive names the Competency Compiler as its intended engineering result. The sentence
is present in the 2026-10-13 source and the 2026-10-14 re-issue. The first two increments of this PR did not
implement it. PR #165 merged `capabilities/router.py` to `main` on 2026-10-14. Its commit says nothing calls the
router and that wiring waits on the entry gate. In the Goal Gravity loop, any trusted observation cleared any gate.
Verification marked moves externally verified but never informed mechanism choice. A missing capability only
blocked a goal.

**Inference.** The residual deficit is the seam between the two. A gate becomes a problem class, which yields
admissible methods, then a recruited mechanism, then typed evidence, then an independently verified outcome, then
calibration. Add the acquisition path for when nothing registered is competent.

**Unresolved claims.** Whether wiring inert code in a draft PR counts as "runtime composition" under entry gate G1.
That is recorded as a conflict and dissent. The founder decides.

## Decision

Mount the router on the loop as `loop.competency` (`egregore/competency.py`) behind an optional constructor
argument. Leave `capabilities/router.py` selection semantics untouched. The one change to it, made after the
adversarial review below, is that `restore()` replays only outcome events `record_outcome` would itself have accepted.

| Clause of the Competency Compiler sentence | Mechanism on this branch | Falsifying test |
|---|---|---|
| recognizes a problem | `PlanNode.problem_class` (router taxonomy); unclassified gates stay unrouted and are counted | `test_unclassified_gates_are_not_routed_and_the_seam_has_no_authority` |
| determines which epistemic methods can answer it | `capabilities.router.PROBLEM_CLASSES` | `test_a_simulation_cannot_answer_demand_so_the_goal_waits_with_a_typed_deficit` |
| recruits the smallest competent mechanism or composition | `CapabilityRouter.route` (exact cover); routing only tightens classification | `test_a_composition_credits_every_recruited_mechanism_once` |
| produces appropriately typed evidence | observation `method` → `establishes` from the router table; `gps.admissible_evidence` | `test_only_evidence_of_an_admissible_kind_clears_a_typed_gate` |
| respects authority | human-only gates become one founder decision whose answer is the only typed evidence; unproven mechanisms never run external moves | `test_a_human_only_gate_becomes_one_decision_whose_answer_is_the_only_evidence_that_clears_it` |
| observes outcomes | `reconcile()` from Gate events; `verify_outcome(verdict=...)` by an independent verifier | `test_calibration_moves_only_on_independent_verification_and_bad_mechanisms_are_demoted` |
| improves future selection | `record_outcome` on every routed mechanism; `refresh()` replays other writers; survives restart | `test_track_records_survive_restart_and_are_shared_by_two_loops_on_one_ledger` |
| generates new bounded capabilities when the repertoire is insufficient | `egregore/acquisition.py`: ladder plan from recorded facts and the open-source catalog, subprocess qualification under an independent evaluator, founder attach decision, resume. **No builder**: candidates are supplied | `tests/unit/test_goal_gravity_acquisition.py` |

The same increment closes further directive gaps found by an independent audit.

- **§5 personal advancement.** `egregore/advancement.py` adds authorized-versus-observed trajectory, structured
  friction and the mature report. The report is one per stall episode and can always be declined at no cost.
- **§8 interoceptive modalities.** `egregore/sensorium.py` emits readings only when they change. External
  modalities are declared unobserved, each with the sensor it needs.
- **§8 organ signals.** `egregore/organ_signals.py` maps canonical opportunity packets and venture assessments to
  typed observations. WMI scores are typed as simulation.
- **§12 and §28 opportunity package.** `egregore/opportunity.py` adds baseline quantification, separates contested
  factors and dry-run classifies each move.
- **§20 controls.**
  - Refusals bind identical effects, so a reworded or relabelled move stays refused.
  - Declared model tactics are bound by "never use this tactic".
  - Muted domains are not stored.
  - A pause or lower-priority answer takes effect.
  - Intervention intensity can be set per goal.
- **§27 intake.** `egregore/intake.py` turns "I want X" into a draft. Authority is never filled in, and the goal
  starts at two founder gates.
- **§25 scenario 9.** Real SIGKILL tests cover two kill points. A torn ledger tail is characterized as a known
  liveness gap.
- **§9 and §30 measurement.** Wake precision and recall come from labelled corpora. The trusted-modality count now
  excludes untrusted sources. Founder burden is measured.
- **One ledger, many projections.** Every projection is now an incremental fold, so two loops over one ledger agree.

## Reuse map

| Need | Reused | How |
|---|---|---|
| Method taxonomy, competent selection, calibration, deficits | `capabilities/router.py` (main, #165) | selection unchanged; `restore()` hardened (see review); called through `egregore/competency.py` |
| Genome envelopes | `capabilities/genome.py` | candidates and attachments use `CapabilityGenome`; envelope capped at the goal ceiling |
| Open-source search | `docs/open-source/repositories-2026-09-30.json` (main) | read-only leads with license and freshness; nothing installed |
| Organ contracts | `adapters/daleobanks_opportunity.py`, `adapters/wealthmachine_assessment.py` | canonical output only; the boundary package is not modified |
| Consequence classes | `capabilities.genome.CONSEQUENCE_CLASSES` | re-exported by `egregore/goals.py` (one ordering) |
| Resolution ladder | `capabilities.router.RESOLUTION_ORDER` | `interventions.RESOLUTION_ORDER` = router ladder + escalate/abstain |

## Credited lineages (preserved, not ported)

| Lineage | Mechanism | Relation |
|---|---|---|
| #158 `greg/cognition/compiler.py` | Layer 5 Competency Compiler (earlier, same intent) | substrate; not credited by #165; credited here |
| #143 cortex routing, certificate checkers | checked solving, shadow routing | substrate; checkers portable with #164 |
| #164 `greg/recombine.py` | constructs capabilities by certified reduction | the natural builder for `qualify()`; needs an optimization problem class on main |
| #129 `egregore/parts.py`, `egregore/genesis.py` | parts board, genesis ladder, shadow, dossier, ratified bind | mergeable on main; its ratified genomes can become router competencies through `qualify()`/`attach()` |
| #166 append-only witness, cross-organ mission | RFC 9162 consistency, witnessed checkpoints, real organ run | independent; its episode is natural experience input (labelled internal reproduction) |

## Adversarial review of this increment

Four dimension reviewers attacked commit `81c90c7`: authority and safety, competency and typed evidence, ledger
consistency, and evidence honesty. They raised 35 findings, several of them the same defect seen from two
dimensions, each with a reproduction. The four refuting verifiers and the completeness critic did not run, because
the account's usage limit stopped them. Every reproduction was therefore re-run directly, twice: against a clean
checkout of `81c90c7`, where each one reproduced, and against the fixed tree, where none does
(`tests/evidence/goal-gravity-20261013/review-probes-increment-3.log`). Regression tests are in
`tests/unit/test_goal_gravity_review.py` unless another file is named.

| Finding (severity) | Fix |
|---|---|
| Direct `attach()` with no founder answer (major, raised twice) | attach requires the ledgered acceptance of the attach ask for that qualification, by the same actor |
| Attached capability lost on restart or in a second loop (major, raised twice) | `CapabilityAcquisition.sync()` replays attach and detach records without new ledger events; `detach()` added; an acceptance whose attach record was lost completes on the next turn (`test_goal_gravity_acquisition.py`) |
| Competency class or pre-registered genome wider than the envelope shown to the founder (major) | `qualify()` refuses a competency above its genome and a different genome already registered under the same name@version |
| `qualify()` ran caller-chosen tests, not the genome's declared tests (major) | the declared tests always run; callers may only add |
| Forged `routing_outcome` events replayed into calibration (major) | `CapabilityRouter.restore()` replays only outcomes that pass `record_outcome`'s own rules and lists the rest in `unreplayed` (`test_capability_router.py`) |
| A low-trust corroborator relabels a trusted reading (blocking) | across sources one reading wins whole: value, trust and method come from the more trusted reading |
| A lone critique clears `code_correctness`; a non-admitted method clears a gate by sharing a label (major) | admissibility is checked by method, and every `all_of` method needs its own trusted reading about the same subject |
| One goal's founder decision clears another goal's gate; sensor readings veto or re-block a founder decision (major, three cases) | human-only gates read the founder decision recorded for that goal, which no sensor reading can contradict |
| Founder answer consumed by an effect that cannot land; reserved source squatted (major, raised twice) | founder and sensorium sources are reserved at sensing; the effect is checked before the answer is written; a lost effect completes on the next turn |
| Router-less loop spends a routed move's single verification; a suffixed actor verifies itself (major) | routed moves verify only on a router-mounted loop; identities compare before any `@` suffix; mechanisms cannot verify themselves |
| Crash after the verification record strands it (major) | the verification record is the commit point; reads show it applied and the next write path finishes it idempotently |
| One verification per action matched a shared `None` action id (minor) | the verification subject falls back to the move's classification |
| A re-dispatched attempt reconciled from attempt 0's Gate events (blocking) | every outcome record carries its attempt's proposal id |
| Refuted or negative outcome blocked only one turn (minor) | discrepancies stay blockers until `review_discrepancy()` by a party other than the acting agent |
| Epistemic deficits missing for move-less gates and never closed after the gate cleared (minor) | recorded at routing; closed as history when the gate is no longer active |
| A founder-revoked mechanism still recruited (major) | routing withholds it for that goal only and records why |
| A proposer escapes a ban by declaring a tactic or embedding a declared move (major, raised twice) | tactics always carry the proposer handle; only the registered goal proposer may hand over a declared move |
| A muted domain becomes the muting goal's evidence (major) | muted verdicts have zero relevance |
| A superseded goal aborts every matching turn (minor, pre-existing) | relevance skips superseded goals |
| Organ trust not bound to the verified body; identity from payload (major, raised twice) | attributed trust needs the raw body, a matching digest, the producing organ's identity and an identical re-adapted id (`test_goal_gravity_organs.py`) |
| `minimal` intensity still reported late nodes (major) | `minimal` produces no report |
| Status reported the oldest of same-time turns; sensorium hid reopened deficits; contradictions read without folding (minor) | ledger order breaks ties; the latest deficit record decides; the read folds first |
| Closure probe composed no router or retention (minor) | the probe composes both and checks that attach is refused without an answer |
| Tier table claimed SANDBOX-EXECUTED; refusal-rate modality claimed a 30-day window; stale Genesis rows (major and minor) | tiers corrected to UNIT-TESTED; the modality description now says it counts the whole ledger, because Gate events carry no logical time; rows corrected |

What the review did not establish: no verifier independently refuted or confirmed these findings, and the
completeness critic never ran. Areas no reviewer examined in depth are `egregore/intake.py` and
`egregore/opportunity.py` beyond their tests.

## Findings recorded for other owners

- **Router lock-out (router owner).** Under the Beta(1,1) prior, one verified success scores 0.667. Any floor above
  2/3 therefore rejects a once-successful mechanism while still admitting an unproven one. A mechanism with one
  success and one failure scores 0.5, so at the default floor it is rejected permanently. The seam uses the default
  floor, and the property is recorded in `INTENT-20261014-competency-compiler.json`.
- **Boundary package (adapters owner).** `adapters/` ships in the pinned boundary package. Organ-observation
  adapters live in `egregore/` so the package never depends on `egregore`.

## Dissent

- Adversarial reviewer. #165 sequenced the router as inert until the entry gate opens, and wiring it in a draft
  pre-empts that. Threshold: a founder ruling that wiring counts as runtime composition under G1. Owner: Alfonso.
- Evidence guardian. `qualify()` is a subprocess, not isolation, and must never be described as sandboxed
  verification. Threshold: any document or ask that does so. Owner: kernel maintainers.

## Authority impact

Changes authority: no.
- Routing confers none.
- Attaching is not a grant.
- Founder answers are declared lineage (G6), with trust `attributed`, never `verified`.
- Nothing starts a service, contacts anyone or mints a grant outside tests.

## Decision

`NEEDS_FOUNDER_DECISION` for adoption. The implementation stands as a reversible experiment. Evidence tier is
unchanged: IMPLEMENTED, UNIT-TESTED and INTEGRATION-TESTED on synthetic ledgers. Qualification runs repository
tests in a pytest subprocess; that is not a sandbox, so nothing here is SANDBOX-VERIFIED.
Grants are test-minted. CMC and VEPMC remain 0.
