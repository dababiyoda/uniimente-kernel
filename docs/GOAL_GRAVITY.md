# Goal Gravity: authorized goals as persistent attractors

Status: IMPLEMENTED on `main`'s canonical standing runtime (draft PR); adoption and activation are founder decisions.
Intent: `INTENT-20261013-GOAL-GRAVITY` (`docs/intent/INTENT-20261013-GOAL-GRAVITY.md`).
Verbatim founder source: `docs/intent/sources/GOAL-GRAVITY-DIRECTIVE-2026-10-13-source.md`.
Decision record: `docs/decisions/ADR-GOAL-GRAVITY-001.md`; deliberation `docs/collaboration/deliberation-goal-gravity-2026-10-13.json`.

> Preserve the effect. Do not literalize the metaphor. "Coincidence production" compiles to persistent goal memory +
> situational awareness + preparation + timing + option creation. Nothing here controls chance, claims experience, or
> creates authority.

## 1. The loop in one read

```text
Sense -> Experience -> Backcast -> Detect Gate -> Manufacture Leverage
-> Execute/Prepare/Escalate -> Create Favorable Intersection -> Verify -> Compound -> Recalculate -> Repeat
```

`GoalGravityLoop.turn(trigger_id, now, signals, resources, grants, gate, executor)` performs one idempotent turn:

1. **Sense -> Experience.** Each `SignalEnvelope` (the existing standing-cognition contract) carries typed
   observations in `payload["observations"]`. The `WorldModel` integrates them into provenance-backed beliefs and
   records an `ExperienceEvent` (signal + source + time + context + confidence + goal relevance + what changed).
   Disagreeing sources are retained side by side as a contradiction; agreeing sources corroborate.
2. **Match events against goals.** The `GoalRelevanceRouter` scores each signal against every goal's declared wake
   conditions (subject, tag, domain, metric threshold). Founder mutes and stops are honoured before anything wakes.
3. **Favorable intersections.** Weak signals touching a goal's opportunity factors are combined inside the goal's
   window; a cross-domain score at or above the goal's threshold wakes the goal and records an observation.
4. **Wake/sleep.** Goals wake from relevant evidence, a favorable intersection or their review cadence; a
   hibernating `ResourceGovernor` wakes nothing; conserve mode processes priority 1–2 only. Dormant goals cost nothing.
5. **Backcast.** `BackcastGPSAdapter.fix` computes current position, the active node, the active gate, the single
   bottleneck metric gap, the exit evidence still missing, missing capabilities and the candidate next moves.
6. **Classify.** Every candidate move is classified by the canonical policy engine into
   `EXECUTE_AUTONOMOUSLY / PREPARE_FOR_FOUNDER / REQUEST_EVIDENCE / WAIT / ESCALATE / ABSTAIN`.
   A missing capability records a `CapabilityDeficit` with the goal's lineage and leaves the goal blocked, not closed.
7. **Execute / prepare / escalate.** At most one `EXECUTE_AUTONOMOUSLY` move per goal per turn is submitted through
   `ConsequenceGate.run` with the caller's pre-existing grant. Everything else is written as prepared work. Every
   move carries an evidence state: `planned`, `attempted`, `executed`, `externally_verified`, `failed`, `unknown`.
8. **Drift.** Actions committed in a goal's name on routes the authorized plan never declared are made visible.
9. **Protect attention.** Prepared and escalated moves become compressed decisions with options, a no-cost option,
   evidence references and an effort estimate. The `FounderAttentionRouter` dedupes, batches and suppresses by
   urgency and marginal value. Answers are recorded; a refusal suppresses that exact route; "never use this
   tactic" suppresses the family.
10. **Compound.** A recorded positive outcome retains its receipt as a durable evidence asset automatically. Richer
    retention (`AsymmetryRetention.retain`) registers reusable capabilities as bounded Capability Genomes and
    resolves other goals' missing capabilities, making them measurably cheaper.
11. **Recalculate.** Goal state (position, active node, gate, SBM, blockers, evidence) is written as a ledgered
    transition; the goal returns to dormant or blocked; the turn is recorded and replayable.

Founder control surface (`GoalRegistry.record_preference`): `stop_pushing`, `change_goal`, `lower_priority`,
`never_use_tactic`, `do_not_monitor`, `ask_before`, `forget_route`, `revoke_capability`, plus `revoke`.
Founder-facing status (`GoalGravityLoop.status`) renders the section-27 fields for any goal.

## 2. Evidence tier per target (section 26 vocabulary)

| Target | State on this branch | Tier | Proof | Not yet |
|---|---|---|---|---|
| A Persistent Goal Registry | IMPLEMENTED | UNIT-TESTED, INTEGRATION-TESTED | survival across JSONL restart | FOUNDER-ACCEPTED |
| B Goal Relevance Router | IMPLEMENTED | UNIT-TESTED | wake / irrelevant-rejection tests | learned routing; live sensors |
| C Wake/Sleep Runtime | IMPLEMENTED | UNIT-TESTED | dormant cost zero; cadence wake; hibernation | a durable scheduler calling `turn()` without a human tick (SR001 P1) |
| D Backcast GPS adapter | IMPLEMENTED | UNIT-TESTED, INTEGRATION-TESTED | node advance on observed evidence | route re-planning beyond the declared plan |
| E Intervention Classifier | IMPLEMENTED | UNIT-TESTED, INTEGRATION-TESTED | authority-boundary test; Gate execution under grant | standing grants issued by the founder |
| F Experience Integration | IMPLEMENTED | UNIT-TESTED | contradiction retained; experience surface measured | any claim beyond functional access to reality |
| G Favorable Intersection Detector | IMPLEMENTED | UNIT-TESTED, INTEGRATION-TESTED | three weak cross-domain signals wake a goal | real-world intersections |
| H Asymmetry Retention | IMPLEMENTED | UNIT-TESTED, INTEGRATION-TESTED | capability registered; later goal unblocked | retention from an externally verified outcome |
| I Founder Attention Router | IMPLEMENTED | UNIT-TESTED | 306 signals -> at most two immediate asks; dedupe; manipulation guard | a real founder channel (none is contacted) |
| Capability Genesis link | PARTIAL | UNIT-TESTED | deficit recorded with lineage; goal blocked not closed; unblocks on genome registration | search/compose/build of the missing capability (the drafts' Genesis builder) |
| Section-33 chain | IMPLEMENTED | INTEGRATION-TESTED (synthetic) | `tests/integration/test_goal_gravity_acceptance.py` | SANDBOX-VERIFIED with a live sensor; EXTERNALLY VERIFIED; FOUNDER-ACCEPTED |

Never say "GREG experiences reality" for this code: it integrates typed observations into beliefs with provenance.
Never say "GREG creates coincidences": it detects declared factor convergence inside a window. Never say "GREG
autonomously advances goals" unless a Gate receipt exists for the move; otherwise it prepared.

## 3. Repository concept map (section 22)

<!-- CONCEPT-MAP: filled from the multi-reader inspection; see section 3 below -->

## 4. Preserved future targets with the blocking dependency (section 32.14)

| Target | Why not now | Blocking dependency |
|---|---|---|
| 24/7 operation, dormant goals woken by real time | nothing here installs a scheduler | founder activation decision; a bounded host trigger (cron / APScheduler as DALEOBANKS already runs / Temporal) per `docs/founder-loop-entry-gate.json` G5, P1 |
| Alien sensorium / 100000 senses | no live sources are wired | authorized data access and per-source `SignalEnvelope` adapters (DALEOBANKS perception and ContextPackets, WMI market monitor, public feeds) |
| Learned relevance and model-backed proposers | rule baseline only | local open-source model route (INTENT-20260930) attached through standing-cognition proposers; must beat the rule baseline on held-out signals |
| Autonomous execution at scale | the loop holds no grants | founder-issued standing grants through the existing issuer; the Gate consumes, never fills in |
| Capability Genesis builder | deficit detection only | reconciliation of the drafts' Genesis/builder lineage (#114/#137) or a bounded coding-agent route under the Capability Genesis contract |
| Founder authentication for goal authorization | goals carry declared lineage only | SR001 G6: canonical founder key custody and revocation |
| External verification of outcomes | synthetic executors | a real outcome adapter with `validation_status: externally_verified` |
| Cross-organ goal feeds | organs untouched | typed adapters from DALEOBANKS/WMI wire contracts into observations (no copied governance) |
| Physical embodiment | out of scope | authorized device/robotics interfaces under the Gate |
| Richer Experience Surface metrics (recall, cross-modal inference, prediction calibration) | seven metrics implemented | calibration data from real predictions (`CausalMemory.calibrate` is the intended consumer) |

## 5. How the loop is called

```python
from egregore import GoalGravityLoop, GoalSpec, ResourceGovernor
loop = GoalGravityLoop(ledger=ledger, compiled=compiled, passports=passports,
                       actor=passport_id, legal_principal="alfonso_lopez", genomes=genome_registry)
goal_id = loop.registry.authorize(spec, now=now)                      # declared lineage, dormant
turn = loop.turn(trigger_id="scheduler:2026-11-22T10", now=now, signals=signals,
                 resources=ResourceGovernor(max_model_calls=4, max_estimated_cost_usd=0.05),
                 grants={"research.brief": grant}, gate=gate, executor=executor, evidence_confidence=0.9)
loop.status(goal_id, now=now)                                        # section-27 fields
loop.founder_answer(item_id, decision="refuse", actor="alfonso_lopez", note="not now", now=now)
```

A scheduler must supply a globally stable `trigger_id`; retrying it with the same inputs returns the recorded turn,
and changing the inputs under the same id is refused and retained as a conflict.
