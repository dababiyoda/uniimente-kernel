# ADE-1 standing cognition

This package implements the useful core of the ADE-1 blueprint as a bounded
UNIIMENTE organ. It is continuously schedulable, restartable, evidence-bound,
resource-bounded, and capable of multi-organ deliberation. It is not a legal
person, sovereign actor, autonomous treasurer, or self-preserving process.

The invariant is simple:

> Standing cognition may produce a candidate. Only the kernel Consequence Gate
> may turn a bound proposal into an external effect.

## What is implemented

- Content-addressed telemetry envelopes with duplicate suppression and
  contradiction retention.
- Idempotent cognition ticks that rebuild from the Evidence Ledger.
- Deterministic proposer/evaluator deliberation with required Guardian and
  Treasury assessments, explicit vetoes, preserved dissent, and isolated organ
  failure.
- Hard model-call and estimated-cost ceilings with conservation and hibernation.
- An unconditional suspend path and hash-authorized resume path.
- Immutable self-change proposals with tests and rollback declarations, but no
  self-apply function.
- A narrow adapter into the existing `policy.engine.Proposal` and
  `ConsequenceGate.run` path.
- Five-closure checks, an output schema, and adversarial unit tests.

## What is intentionally absent

- Private keys, wallet signing, swaps, transfers, staking, or treasury control.
- Direct social publishing or external API execution.
- A legal principal named UNIIMENTE.
- Attention-driven permission or budget expansion.
- Automatic prompt, policy, model, code, or infrastructure mutation.
- Claims of consciousness, life, sovereign intent, or cryptographic truth.

## Scheduler integration

Temporal, cron, a block trigger, or another durable scheduler can call `tick`.
The scheduler must supply a globally stable `trigger_id`; retrying that ID with
the same inputs returns the recorded cycle, while changing the inputs under the
same ID is retained as a conflict and refused.

```python
cycle = runtime.tick(
    trigger_id="temporal:ade1:2026-07-22T12:00Z",
    signal_ids=signal_ids,
    resources=ResourceGovernor(
        max_model_calls=12,
        max_estimated_cost_usd=0.25,
    ),
    call_costs={
        "proposer:strategist": 0.04,
        "evaluator:guardian": 0.02,
        "evaluator:treasury": 0.01,
    },
)
```

The runtime stops at `cycle.selected_candidate_id`. A separate, explicitly
accountable service may bind that candidate to a real machine passport and
legal principal with `bind_for_gate`, then call `submit_through_gate`. No other
effect path belongs in this package.

## Active inference boundary

This release does not label multi-agent voting as active inference. A future
active-inference organ must declare a generative probabilistic model, latent
states, observations, preferences, posterior approximation, and a testable
free-energy objective. Until then, this implementation is accurately described
as bounded deliberation.

## Local open-source draft model

`egregore.local_model.LocalDraftProposer` supplies an optional local Qwen
proposer through the existing constructor's proposer mapping. It uses Ollama,
llama.cpp, vLLM or LocalAI's loopback /v1 protocol, rejects hosted URLs and
redirects, and makes no paid fallback calls. A legacy OpenAI key is ignored.

The model supplies only draft objective/text; source/evidence references and
fixed internal proposal scope come from the adapter. Confidence is zero pending
the existing required evaluators. Call limits, suspension, idempotent replay and
the Consequence Gate remain owned by the existing runtime.

See [the researched stack and setup](../docs/OPEN_SOURCE_STACK.md).
Use a positive existing resource cost ceiling even for zero-token-fee local
inference: a zero ceiling means hibernation in ResourceGovernor. Hardware and
electricity are real costs; zero provider token fees are not unlimited resources.
No server, scheduler or production activity starts by importing this adapter.

## Goal Gravity loop (INTENT-20261013-GOAL-GRAVITY)

The founder's 2026-10-13 directive compiles to one behavioral property of the
standing runtime: **an authorized persistent goal is an attractor for relevant
perception, backcasting, preparation, capability formation and action.** The
loop lives in this package because it extends the canonical GREG runtime on
`main`; it is not a parallel GREG, Kernel, mission authority, identity or
evidence plane.

| Target (directive §24) | Module | What it does |
|---|---|---|
| A Persistent Goal Registry + C wake/sleep | `goals.py` | content-addressed `GoalSpec` + ledgered `GoalState`; dormant at zero model cost; wakes from relevant evidence, favorable intersection or review cadence; founder control surface (stop, change, lower, never-tactic, mute domain, ask-before, forget route, revoke capability) |
| B Goal Relevance Router | `relevance.py` | deterministic wake-condition matching (subject, tag, domain, metric threshold) |
| D Backcast GPS adapter | `gps.py` | goal → active node → active gate → SBM → exit evidence → next moves, reusing the morphogenesis target-state arithmetic |
| E Intervention Classifier | `interventions.py` | `EXECUTE_AUTONOMOUSLY / PREPARE_FOR_FOUNDER / REQUEST_EVIDENCE / WAIT / ESCALATE / ABSTAIN` via the canonical policy engine; records `CapabilityDeficit`s with goal lineage |
| F Experience Integration | `experience.py` | `ExperienceEvent`s into a provenance-backed world model; contradictions retained side by side; measurable experience surface (not a consciousness score) |
| G Favorable Intersection Detector | `intersections.py` | cross-domain weak-signal convergence inside a goal's window; observed, never acted on directly |
| H Asymmetry Retention | `retention.py` | durable assets anchored to ledgered outcomes; reusable capabilities registered as bounded Capability Genomes; other goals' deficits resolved |
| I Founder Attention Router | `attention.py` | urgency × marginal-value routing, dedupe, batching, manipulation guard (every ask carries a no-cost option); answers recorded, refusals remembered |
| the loop | `gravity.py` | `GoalGravityLoop.turn()` composes the above; idempotent per `trigger_id`; executes at most one move per goal per turn and only through `ConsequenceGate.run` (which must share the ledger) with a caller-supplied pre-existing grant; `reconcile()` closes attempted/unknown moves from the Gate's own records or an accountable resolution; `verify_outcome()` grants `externally_verified` only to an independent verifier citing evidence; `measures()` reports identity, agency, intelligence and the experiential surface separately |
| cognition seam | `cognition_seam.py` | `GoalProposer` registers with the standing runtime; when a `StandingCognitionRuntime` is attached every awake goal's deliberation runs through its `tick` (goal context in, candidates out, guardian/treasury vetoes honored, model calls metered by a per-goal governor carved out of the turn's budget); a vetoed or unselected move is prepared, never executed |
| contract enforcement | `contract_check.py` | goal-record, goal-state, experience-event and capability-deficit records are validated (JSON Schema 2020-12, fail-closed formats) on every write; outside the pinned boundary-package allowlist |
| Competency Compiler mount (2026-10-14) | `competency.py` | `GoalCompetencyRouting` mounts `main`'s `capabilities.router.CapabilityRouter` on the loop: a gate's `problem_class` becomes a `ProblemSpec`, the router selects the smallest competent mechanism or composition by epistemic method, the routing decision is ledgered and folded back after restart, an epistemic deficit becomes a typed `CapabilityDeficit` (missing methods) and a WAIT, and only an independent verifier's confirm/refute updates calibration |
| typed evidence | `experience.py`, `gps.py` | every observation may declare an epistemic `method`; what it `establishes` comes from the router's method table; a gate's exit evidence must establish what its problem class admits; human-only methods enter only through the founder-answer path and are stripped and marked untrusted anywhere else |
| advancement monitor | `advancement.py` | per-goal trajectory, stall onset, behind-target detection and structured friction (open attempts, unknown decisions, unmet dependencies, missing capabilities, routing deficits, founder decisions, no declared move); one mature report per stall episode at the founder's chosen intensity (`minimal / standard / active`) with no-cost `pause` and `lower priority` answers |
| derived sensorium | `sensorium.py` | eight institution-level modalities derived from the ledger (open deficits, evidence conflicts, open obligations, opportunity density, ledger integrity, consequence refusal rate, relationship changes, goals behind target) emitted as signals only when they change; six external modalities declared unobserved with what each requires |
| opportunity package | `opportunity.py` | on a transition into a favorable state, a ledgered package of satisfied factors (with evidence and baseline deltas), threats, contested factors (excluded from the score), position and dry-run options; packaging never acts |
| capability acquisition | `acquisition.py` | an 11-rung acquisition ladder over existing capabilities, the open-source catalog and infrastructure leads; qualification runs the genome's declared repository tests (plus any added) under a sanitized environment with an independent evaluator and refuses envelope widening, a mismatched registered genome or human-only methods; attach requires the founder's ledgered acceptance, lands at `CANARY`, replays after restart and in every loop on the ledger, and can be detached |
| goal intake | `intake.py` | a founder statement becomes a section-27 draft with every unknown marked `unresolved`; authorization refuses missing authority and seeds confirm/plan gates whose assumptions stay marked unresolved |
| organ observation adapters | `organ_signals.py` | DALEOBANKS `OpportunityPacket` and WMI `VentureAssessment` outputs become typed signals with declared field mappings, information lost/added and assumptions; trust is `attributed` only for a `verify_headers` result bound to the raw body it verified and to the producing organ, otherwise `untrusted`; WMI scores are typed `simulation`, never evidence of the world |

Contracts: `contracts/goal-record.schema.json`, `contracts/goal-state.schema.json`, `contracts/experience-event.schema.json`,
`contracts/capability-deficit.schema.json`.
Tests: `tests/unit/test_goal_gravity.py` (section-25 scenarios), `tests/unit/test_goal_gravity_seams.py` (cognition seam,
deficit classes, reconciliation, independent verification, section-20 controls, section-13 attention),
`tests/unit/test_goal_gravity_competency.py` (router mount, typed evidence, epistemic deficits, calibration, restart),
`tests/unit/test_goal_gravity_advancement.py`, `tests/unit/test_goal_gravity_sensorium.py`,
`tests/unit/test_goal_gravity_controls.py` (intensity, effect-level refusal, mute at sensing, founder burden),
`tests/unit/test_goal_gravity_opportunity.py`, `tests/unit/test_goal_gravity_acquisition.py`,
`tests/unit/test_goal_gravity_intake.py`, `tests/unit/test_goal_gravity_organs.py`,
`tests/unit/test_goal_gravity_review.py` (one regression test per confirmed adversarial-review finding),
`tests/integration/test_goal_gravity_acceptance.py` (section-33 chain) and
`tests/integration/test_goal_gravity_process_kill.py` (SIGKILL after dispatch and before the gate, torn-tail characterization). Five closures: `goal_gravity_closures()` in
`closure.py`, registered on the integration registry.

Evidence tier of the current implementation: IMPLEMENTED, UNIT-TESTED, INTEGRATION-TESTED on synthetic ledgers with
test passports and the development witness key. Not SANDBOX-VERIFIED against a live sensor, not EXTERNALLY VERIFIED,
not FOUNDER-ACCEPTED. "GREG advances goals" here means: it classifies, prepares, and when a pre-existing grant exists
it submits one bounded move through the Gate and records the receipt. It does not mean a scheduler ran.

### Buildability standard (14 conditions)

- **Existing mechanism**: ledger-hydrated state machines, deterministic rule matching, policy evaluation, hash-chained records; no novel science and no model calls in the loop itself.
- **Defined interface**: `GoalRegistry.authorize/wake/sleep/transition/record_preference/revoke`; `WorldModel.integrate/belief/experience_surface`; `GoalRelevanceRouter.route`; `BackcastGPSAdapter.fix`; `InterventionClassifier.classify`; `FavorableIntersectionDetector.detect`; `AsymmetryRetention.retain`; `FounderAttentionRouter.route/answer`; `GoalGravityLoop.turn/status/founder_answer`.
- **Bounded authority**: every service object reports `execution_authority == "none"` and retains no gate, executor or grant between turns; goals carry declared lineage, not authentication; execution only through the Gate with a caller-supplied grant; the loop never issues grants; evidence references handed to policy are ledger hashes (authorization record, experience records, receipts), never labels.
- **Available dependencies**: Python 3 stdlib + `provenance.ledger`, `policy.engine`, `morphogenesis.contracts`, `capabilities.genome`, `capabilities.router` (optional mount; without it the loop still recognizes human-only gates from the router's problem table).
- **Security model**: instruction-shaped signal text stays data; founder preferences and refusals are enforced before policy; duplicate consequential moves are refused by durable `attempted` records plus the Gate's dispatch claim; asks without a no-cost option are suppressed.
- **Failure modes**: `GoalError`, `ExperienceError`, `ContractViolation`, `IntegrityConflict` (conflicting goal content, conflicting signal content, conflicting trigger reuse); gate refusals become `failed`, executor exceptions become `unknown` with a sticky reconciliation blocker and an information item (emergency when the move was external); a negative or unreconciled outcome blocks the goal with a discrepancy record; a route is re-dispatched only after an accountable reconciliation and then under an attempt-numbered proposal id.
- **Acceptance tests**: `tests/unit/test_goal_gravity*.py`, `tests/integration/test_goal_gravity_acceptance.py`, `tests/integration/test_goal_gravity_process_kill.py`, `goal_gravity_closures()`.
- **Recovery path**: rebuild from the ledger; an `attempted` move without a result is never retried blindly; `stop_pushing`/`revoke` halt a goal from any state.
- **Resource ceiling**: a hibernating `ResourceGovernor` processes no goal; conserve mode wakes priority 1–2 only and records every deferral as a resource deficit; each goal's `resource_budget` bounds its deliberation per turn; dormant goals consume nothing between turns.
- **Operating cost**: O(goals × signals) deterministic matching per turn; one ledger append per transition; no external calls.
- **Legal operator**: the goal's declared legal principal (never UNIIMENTE); Alfonso remains root authority.
- **Handoff state**: the ledger is the handoff; `GoalGravityLoop.status()` renders the section-27 fields for any goal.
- **Replaceable**: thresholds, cadences, attention policy and intervention specs are data; proposers/evaluators and sensors plug in through the existing standing-cognition and signal contracts.

### Not achievable in this increment (classified, with the blocking dependency)

- **Capability builder**: acquisition stops at plan, qualify and founder-answered attach. No code-generating builder is wired; #164 RECOMBINE is the natural builder but `main` has no optimization problem class for it.
- **Isolation boundary**: qualification runs a pytest subprocess with a sanitized environment and a timeout. That is not a sandbox. Untrusted candidates need a microVM or container facility that this repository does not have.
- **Scheduler**: the founder-loop entry gate holds activation (G5). No trigger or supervisor component is added before founder selection.
- **Real verified outcomes**: every calibration in tests comes from a synthetic verifier. Router reliability on real problems is unmeasured.
- **Founder authentication**: chat text, hashes and shared keys never authenticate Alfonso (G6). Founder answers are attributed, not authenticated.
- **Live organ transport**: the adapters accept canonical organ outputs. No live DALEOBANKS or WMI transport is connected, so organ signals are untrusted unless signed headers verify.
- **Router taxonomy**: the eight problem classes are `main`'s. Extending them is a router-owner decision, not a loop decision.
- **Torn-tail repair**: a partially written final ledger line refuses to load. That is characterized by test, not repaired.
