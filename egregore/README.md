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
| the loop | `gravity.py` | `GoalGravityLoop.turn()` composes the above; idempotent per `trigger_id`; executes at most one move per goal per turn and only through `ConsequenceGate.run` with a caller-supplied pre-existing grant |

Contracts: `contracts/goal-record.schema.json`, `contracts/experience-event.schema.json`.
Tests: `tests/unit/test_goal_gravity.py` (section-25 scenarios), `tests/integration/test_goal_gravity_acceptance.py`
(section-33 chain). Five closures: `goal_gravity_closures()` in `closure.py`, registered on the integration registry.

Evidence tier of the current implementation: IMPLEMENTED, UNIT-TESTED, INTEGRATION-TESTED on synthetic ledgers with
test passports and the development witness key. Not SANDBOX-VERIFIED against a live sensor, not EXTERNALLY VERIFIED,
not FOUNDER-ACCEPTED. "GREG advances goals" here means: it classifies, prepares, and when a pre-existing grant exists
it submits one bounded move through the Gate and records the receipt. It does not mean a scheduler ran.

### Buildability standard (14 conditions)

- **Existing mechanism**: ledger-hydrated state machines, deterministic rule matching, policy evaluation, hash-chained records; no novel science and no model calls in the loop itself.
- **Defined interface**: `GoalRegistry.authorize/wake/sleep/transition/record_preference/revoke`; `WorldModel.integrate/belief/experience_surface`; `GoalRelevanceRouter.route`; `BackcastGPSAdapter.fix`; `InterventionClassifier.classify`; `FavorableIntersectionDetector.detect`; `AsymmetryRetention.retain`; `FounderAttentionRouter.route/answer`; `GoalGravityLoop.turn/status/founder_answer`.
- **Bounded authority**: every object reports `execution_authority == "none"`; goals carry declared lineage, not authentication; execution only through the Gate with a caller-supplied grant; the loop never issues grants.
- **Available dependencies**: Python 3 stdlib + `provenance.ledger`, `policy.engine`, `morphogenesis.contracts`, `capabilities.genome`.
- **Security model**: instruction-shaped signal text stays data; founder preferences and refusals are enforced before policy; duplicate consequential moves are refused by durable `attempted` records plus the Gate's dispatch claim; asks without a no-cost option are suppressed.
- **Failure modes**: `GoalError`, `ExperienceError`, `IntegrityConflict` (conflicting goal content, conflicting trigger reuse); gate refusals become `failed`, executor exceptions become `unknown` with a reconciliation blocker.
- **Acceptance tests**: `tests/unit/test_goal_gravity.py`, `tests/integration/test_goal_gravity_acceptance.py`, `goal_gravity_closures()`.
- **Recovery path**: rebuild from the ledger; an `attempted` move without a result is never retried blindly; `stop_pushing`/`revoke` halt a goal from any state.
- **Resource ceiling**: a hibernating `ResourceGovernor` processes no goal; conserve mode processes priority 1–2 only; dormant goals consume nothing between turns.
- **Operating cost**: O(goals × signals) deterministic matching per turn; one ledger append per transition; no external calls.
- **Legal operator**: the goal's declared legal principal (never UNIIMENTE); Alfonso remains root authority.
- **Handoff state**: the ledger is the handoff; `GoalGravityLoop.status()` renders the section-27 fields for any goal.
- **Replaceable**: thresholds, cadences, attention policy and intervention specs are data; proposers/evaluators and sensors plug in through the existing standing-cognition and signal contracts.
