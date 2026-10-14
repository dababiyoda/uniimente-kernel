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

`GoalGravityLoop.turn(trigger_id, now, signals, resources, grants, gate, executor)` performs one idempotent turn.
When a `StandingCognitionRuntime` is attached (with a `GoalProposer` registered, sharing the ledger), step 6 below
deliberates through its `tick`: the goal is the context, its declared moves and any other proposer's candidates are
assessed by the guardian/treasury evaluators, model calls are metered by a per-goal governor carved out of the turn's
budget, and a vetoed or unselected move is prepared, never executed. Without a runtime the loop runs in declared-move
mode and every record says so.

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
6. **Deliberate and classify.** Every candidate move is classified by the canonical policy engine into
   `EXECUTE_AUTONOMOUSLY / PREPARE_FOR_FOUNDER / REQUEST_EVIDENCE / WAIT / ESCALATE / ABSTAIN`, with the goal's
   refusals, forgotten routes, forbidden tactics, revoked capabilities, ask-before categories and legal principal
   enforced before policy. Policy sees real evidence: the authorization record hash, the experience records relevant to
   the goal and receipts, with confidence capped by the caller's attestation. Every deficit class of section 21 is
   recorded (`capability`, `resource`, `relationship`, `proof`); a missing capability records a typed
   `capability-deficit` with the goal's lineage; an unmet goal dependency waits; the goal stays blocked, never closed.
7. **Execute / prepare / escalate.** At most one `EXECUTE_AUTONOMOUSLY` move per goal per turn is submitted through
   `ConsequenceGate.run` (which must write to the same ledger) with the caller's pre-existing grant. Everything else
   is written as prepared work. Every move carries an evidence state: `planned`, `attempted`, `executed`,
   `externally_verified`, `failed`, `unknown`. A move whose outcome is unknown is a sticky blocker: `reconcile()`
   closes it from the Gate's own `action.*` events or from an accountable resolution recorded with its author, and a
   re-dispatch afterwards carries an attempt suffix so it is never a replay. `externally_verified` is earned only
   through `verify_outcome()` by a verifier other than the executing actor, citing evidence; the executor's own
   `validation_status` is retained as a claim. A negative or unreconciled outcome records a discrepancy and blocks
   the goal.
8. **Drift.** Actions committed in a goal's name on routes the authorized plan never declared are made visible.
9. **Protect attention.** Prepared and escalated moves become compressed decisions with options, a no-cost option,
   evidence references and a computed effort estimate ("GREG recorded a candidate move"; nothing claims execution).
   Information items ("Alfonso should know") carry no ask: a newly favorable intersection, drift, a contradicted
   bottleneck metric, an unknown outcome (emergency when the move was external) and an outcome discrepancy. The
   `FounderAttentionRouter` dedupes, batches and suppresses by urgency and marginal value; quiet hours hold everything
   but emergencies. Answers are recorded with their effect: `refuse` writes the route refusal before the answer;
   `never_use_tactic` writes the preference first; `defer` re-surfaces after the goal's review cadence; `accept` is
   explicitly not a grant; `change` requires a superseding goal.
10. **Compound.** A recorded positive outcome retains its receipt as a durable evidence asset automatically. Richer
    retention (`AsymmetryRetention.retain`) registers reusable capabilities as bounded Capability Genomes and
    resolves other goals' missing capabilities, making them measurably cheaper.
11. **Recalculate.** Goal state (position, active node, gate, SBM, blockers, evidence) is written as a ledgered
    transition; the goal returns to dormant or blocked; the turn is recorded and replayable.

**The Competency Compiler on the loop (third increment, 2026-10-14).** The router on `main` (`capabilities/router.py`,
PR #165) is mounted as `loop.competency` (`egregore/competency.py`) when a `CapabilityRouter` sharing the ledger and
genome registry is passed. A plan node that declares a `problem_class` routes its gate: the router names the
admissible epistemic methods and recruits the smallest competent registered mechanism or composition inside the
goal's ceiling. Routing only tightens classification. A deficit makes every move wait and writes one typed
`capability-deficit` record. A rejected declared mechanism prepares the move. A human-only gate (authorization,
legal) becomes one founder decision, and its answer is the only evidence that can clear it. An unproven mechanism
never runs an external move. Observations carry the epistemic `method` that produced them; what they `establish`
comes from the router's table, and a typed gate clears only on admissible evidence, so a simulation never proves
demand. `verify_outcome(..., verdict=...)` by an independent verifier calibrates every recruited mechanism, and
`refresh()` replays other writers so track records survive restarts and agree across loops. When nothing registered
is competent, `loop.acquisition` plans the resourcefulness ladder from recorded facts and the open-source catalog,
`qualify()` runs a supplied candidate's acceptance tests in a subprocess under an independent evaluator, and only a
founder `accept` attaches it (envelope capped, lifecycle CANARY); the original goal then resumes. There is no
builder: candidates are supplied by a person, a coding agent or another lineage (#129, #164).

Further capabilities added in the same increment:

- **Personal advancement (§5).** Compares the authorized trajectory (`PlanNode.target_by`) with the observed one,
  diagnoses friction from structured fields, and issues one mature, declinable report per stall episode.
  Intensity is set per goal with the `set_intensity` preference.
- **Computational modalities (§8).** The institution perceives its own deficits, conflicts, obligations,
  opportunity density, ledger integrity, refusal rate, relationship changes and lateness. Readings are emitted
  only on change. External modalities are declared unobserved, each with the sensor it needs.
- **Organ signals (§8).** Canonical DALEOBANKS packets and WMI assessments become typed observations. WMI scores
  are simulations.
- **Opportunity package (§12, §28).** Quantifies factors against baselines, keeps contested factors separate and
  dry-run classifies every move.
- **Intake (§27).** Turns "I want X" into a draft with all fourteen fields. Authority is never filled in, and the
  goal starts at two founder gates.
- **Effect-level refusals (§20).** Refusals also bind the identical effect, and muted domains are not stored.

Founder control surface (`GoalRegistry.record_preference`): `stop_pushing`, `change_goal` (pauses; `supersede()`
replaces the immutable spec with lineage), `lower_priority`, `never_use_tactic`, `do_not_monitor` (also excludes the
domain's intersection factors), `ask_before`, `forget_route`, `revoke_capability`, plus `revoke`.
Founder-facing status (`GoalGravityLoop.status`) renders the fourteen section-27 fields for any goal, including
`critical_assumptions`, and splits `next_autonomous_work` from `waiting_work` by the latest classification.
`GoalGravityLoop.measures()` reports persistent identity, agency, intelligence and the experiential surface separately
(section 19); subjective consciousness is "unresolved; not measured; not claimed".

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
| H Asymmetry Retention | IMPLEMENTED | UNIT-TESTED, INTEGRATION-TESTED | outcome bound to the goal's executed move; envelope capped at the goal ceiling; registry re-hydrated after restart; later goal unblocked; `work_to_first_actionable` measured | retention from an externally verified outcome |
| I Founder Attention Router | IMPLEMENTED | UNIT-TESTED | 306 signals -> at most two immediate asks; dedupe; manipulation guard; quiet hours; defer/accept/refuse semantics; information and emergency items | a real founder channel (none is contacted) |
| Capability Genesis link | PARTIAL | UNIT-TESTED | typed `capability-deficit` record with lifecycle and resume disposition; goal blocked not closed; resolved copy on genome registration; search and composition through the acquisition plan; founder-gated attach, replayed after restart, detachable | building the missing capability (the drafts' Genesis builder) |
| Standing-cognition seam | IMPLEMENTED | UNIT-TESTED | tick records, guardian veto -> prepared, model-proposer candidate classified, per-goal budget metered | a model-backed proposer beating the rule baseline |
| Evidence states and verification | IMPLEMENTED | UNIT-TESTED | Gate cut after dispatch never re-dispatched; `reconcile()` from Gate events or accountable resolution; `verify_outcome()` independent only | a real externally verified instance |
| Competency Compiler wiring | IMPLEMENTED | UNIT-TESTED | typed deficit, typed gates, human-only gate decision, verified calibration, two-loop agreement, restart | a real independently verified outcome |
| Capability acquisition (§15) | IMPLEMENTED (no builder) | UNIT-TESTED (qualification runs a pytest subprocess; not a sandbox, not SANDBOX-VERIFIED) | plan → qualify → founder attach → resume | a builder lineage; an isolation facility |
| Personal advancement (§5) | IMPLEMENTED | UNIT-TESTED | stall, missed target, resolution latency, intensity, pause | friction removal beyond preparation |
| Computational modalities (§8) | IMPLEMENTED | UNIT-TESTED | derived readings wake goals; emitted on change only | any external modality |
| Organ signals (§8) | IMPLEMENTED | UNIT-TESTED | WMI score clears a forecast gate, never a demand gate; attributed trust only for a verified transport bound to its body | live organ transport |
| Opportunity package (§12, §28) | IMPLEMENTED | UNIT-TESTED | baseline deltas, contested factors, dry-run options | real due diligence |
| Intake (§27) | IMPLEMENTED | UNIT-TESTED | fourteen fields; authority never filled; two founder gates | a model drafter that beats the template |
| Section-33 chain | IMPLEMENTED | INTEGRATION-TESTED (synthetic) | `tests/integration/test_goal_gravity_acceptance.py` | SANDBOX-VERIFIED with a live sensor; EXTERNALLY VERIFIED; FOUNDER-ACCEPTED |

Never say "GREG experiences reality" for this code: it integrates typed observations into beliefs with provenance.
Never say "GREG creates coincidences": it detects declared factor convergence inside a window. Never say "GREG
autonomously advances goals" unless a Gate receipt exists for the move; otherwise it prepared.

The third increment was attacked by an adversarial review before it was pushed. All 35 findings reproduced on the
first commit and were fixed, each with a regression test (`tests/unit/test_goal_gravity_review.py`). The
independent verifiers did not run. See "Adversarial review of this increment" in `docs/decisions/ADR-GOAL-GRAVITY-002.md`.

## 3. Repository concept map (section 22)

Statuses use the directive's section-22 vocabulary (EXISTING / PARTIAL / DUPLICATED / MISSING / SUPERSEDED /
EXPERIMENTAL) and tiers use section 26. "EXISTING" means *works on this tree with tests*; it is never a claim of
external effect. Rows 0-27 come from the 2026-10-13 inspection record
(`docs/collaboration/goal-gravity-concept-map-2026-10-13.json`, with the completeness critique beside it); the
"This branch now" columns reflect the third increment (2026-10-14). Rows 28+ were added for the Competency
Compiler and the gaps an independent audit found on 2026-10-14.

| # | Concept | `main` | Draft lineages | Organs | This branch now | Tier now | Residual deficit |
|---|---|---|---|---|---|---|---|
| 0 | A. Persistent Goal Registry | MISSING | see record | WMI: MISSING; src/core/performance.py SMARTGoal is a per-agent cycle-counter homonym, not ... | EXISTING | UNIT/INTEGRATION-TESTED | incremental ledger fold (two loops agree); founder authentication is declared lineage only (G6) |
| 1 | B. Goal Relevance Router | MISSING | see record | WMI: MISSING; packet fields signal_type/audience/customer_segment/urgency ... | EXISTING | UNIT-TESTED | declared-match relevance; wake precision/recall measurable on labelled corpora (`evaluate_relevance`); no learned routing |
| 2 | C. Goal Wake/Sleep Runtime | PARTIAL | see record | WMI: MISSING (src/services/market_monitor.py MarketMonitor.start is an unwired ... | EXISTING (in-process) | UNIT-TESTED | no durable scheduler/host (G5 forbids a new one before founder selection) |
| 3 | D. Backcast GPS Adapter | MISSING | see record | WMI: MISSING; src/services/phase_management.py PhaseGate/PhaseManager is a venture-level ... | EXISTING | UNIT/INTEGRATION-TESTED | typed gates (`problem_class`); `route_changed`; `changed_since_last_assessment`; no re-planning beyond the declared plan |
| 4 | E. Intervention Classifier | PARTIAL | see record | WMI: contract-bound verdict enum go|defer|kill|needs_more_evidence ... | EXISTING | UNIT/INTEGRATION-TESTED | Competency Compiler routing tightens classification; EXECUTE still needs a caller-supplied grant |
| 5 | F. Experience Integration | PARTIAL | see record | WMI: PARTIAL and reusable: adversarial cases[] (stance/severity/resolved, never averaged) ... | EXISTING | UNIT-TESTED | observations typed by epistemic method; organ canonical outputs integrate (`organ_signals`); no live organ transport |
| 6 | G. Favorable Intersection Detector | MISSING | see record | WMI: MISSING (EmergingTechAgent averages impact/maturity plus a count bonus; adversarial ... | EXISTING | UNIT/INTEGRATION-TESTED | threats subtract; quantified opportunity package; thresholds uncalibrated |
| 7 | H. Asymmetry Retention | PARTIAL | see record | WMI: PARTIAL, organ-local in-memory (business_loop LoopRecord.history/learning, ... | EXISTING | UNIT/INTEGRATION-TESTED | outcome bound to the goal; envelope capped; registry re-hydrated; no externally verified outcome yet |
| 8 | I. Founder Attention Router | MISSING | see record | WMI: MISSING (requires_human_approval const; notify_role only logs). | EXISTING | UNIT-TESTED | quiet hours, defer/accept/pause/lower semantics, information and emergency items; no delivery channel |
| 9 | Capability Genesis connected to Goal Gravity | MISSING | see record | WMI: MISSING (manifest unresolved: venture cell charters not yet requested, Bridge B). | PARTIAL | UNIT-TESTED (pytest subprocess; not SANDBOX-VERIFIED) | plan → qualify → founder attach → resume works for supplied candidates; no builder (#129/#164/coding agent) |
| 10 | Founder refusal/corrections recorded and not re-proposed unchanged | PARTIAL | see record | WMI: MISSING (only compliance refusals retained in influencer_company drafts and ... | EXISTING | UNIT-TESTED | refusals bind route and identical effect; declared model tactics bound; not consulted by the Gate or the Ratifier |
| 11 | Restart continuity without duplicate consequential action | EXISTING | see record | WMI: EXISTING for evaluation admission only via kernel BridgeState (test_signed_bridge.py ... | EXISTING | INTEGRATION-TESTED (real SIGKILL ×2) | torn ledger tail refuses to open (characterized liveness gap) |
| 12 | Evidence state distinction planned/attempted/executed/externally verified/failed/unknown | PARTIAL | see record | WMI: PARTIAL (LoopRecord.stage ladder with settled_simulated vs executed; 'unknown until ... | EXISTING | UNIT-TESTED | independent verification with a verdict; calibrates the router; zero real instances |
| 13 | Experience Surface metrics | MISSING | see record | WMI: MISSING. | PARTIAL | UNIT-TESTED | trusted modalities count only attributed sources; relevance metrics need real labels |
| 14 | §25 scenario 1: Persistent goal survival | MISSING | see record | see record | EXISTING | INTEGRATION-TESTED | cross-process restart covered by the kill tests |
| 15 | §25 scenario 2: Dormant wake | MISSING | see record | MISSING | EXISTING | UNIT-TESTED | declared-match materiality |
| 16 | §25 scenario 3: Irrelevant event rejection | MISSING | see record | MISSING | EXISTING | UNIT-TESTED | muted domains are not integrated at all |
| 17 | §25 scenario 4: Cross-signal convergence | MISSING | see record | MISSING | EXISTING | UNIT/INTEGRATION-TESTED | contested factors excluded from the score and listed |
| 18 | §25 scenario 5: Authority boundary | EXISTING | see record | WMI: requires_human_approval const (adapter refuses authority inflation). | EXISTING | UNIT/INTEGRATION-TESTED | unproven mechanisms never run external moves |
| 19 | §25 scenario 6: Capability deficit | MISSING | see record | MISSING | PARTIAL | UNIT-TESTED | acquisition chain without a builder |
| 20 | §25 scenario 7: Goal drift | PARTIAL | see record | MISSING | EXISTING | UNIT-TESTED | drift on attempt-numbered ids handled |
| 21 | §25 scenario 8: Founder refusal | PARTIAL | see record | DALEOBANKS pending-only dedupe (gap); WMI none. | EXISTING | UNIT-TESTED | identical effect also refused |
| 22 | §25 scenario 9: Restart continuity | EXISTING | see record | WMI/DALEOBANKS: BridgeState idempotency for admission only. | EXISTING | INTEGRATION-TESTED (real SIGKILL ×2) | no supervisor (G5) |
| 23 | §25 scenario 10: Evidence integrity | PARTIAL | see record | PARTIAL | EXISTING | UNIT-TESTED | verdict-bearing verification; no real instance |
| 24 | §25 scenario 11: Compounding | PARTIAL | see record | PARTIAL | PARTIAL | UNIT/INTEGRATION-TESTED | work measured; attached capability makes a blocked goal executable; synthetic only |
| 25 | §25 scenario 12: Attention conservation | MISSING | see record | DALEOBANKS SMS per request with no batching (risk). | EXISTING | UNIT-TESTED | founder burden measured; rule-based value |
| 26 | §25 scenario 13: Sensor contradiction | PARTIAL | see record | WMI adversarial cases preserve dissent (reusable); DALEOBANKS world model has no ... | EXISTING | UNIT-TESTED | organ-typed contradictions possible through `organ_signals`; no live organ |
| 27 | §25 scenario 14: Experience-to-learning | PARTIAL | see record | DALEOBANKS reflection/consolidation change organ-local priors; WMI none. | PARTIAL | UNIT-TESTED | typed beliefs change decisions; router calibration changes selection after verified outcomes; no real outcome |
| 28 | Competency Compiler: recognize the problem / admissible methods | EXISTING (router, #165) | PARTIAL (#158 compiler, #143 cortex) | MISSING | EXISTING (`competency.py`) | UNIT-TESTED | closed eight-class taxonomy; unclassified gates unrouted and counted |
| 29 | Competency Compiler: smallest competent mechanism or composition | EXISTING (router, inert) | PARTIAL | MISSING | EXISTING (wired) | UNIT-TESTED | coarse move-to-mechanism link via `requires_capabilities` |
| 30 | Competency Compiler: typed evidence | MISSING | PARTIAL | MISSING | EXISTING | UNIT-TESTED | self-declared methods capped by trust; human-only only via founder answers |
| 31 | Competency Compiler: observe outcomes, improve selection | EXISTING (router, no caller) | PARTIAL | MISSING | EXISTING | UNIT-TESTED | router lock-out after one failure (recorded for its owner) |
| 32 | Competency Compiler: generate new bounded capabilities | MISSING | PARTIAL (#129 genesis, #164 RECOMBINE, #137 builder) | MISSING | PARTIAL (qualify + attach, no builder) | UNIT-TESTED (pytest subprocess; not SANDBOX-VERIFIED) | a supplier lineage or coding agent |
| 33 | §5 Personal advancement (trajectory, friction, mature report) | MISSING | MISSING | MISSING | EXISTING | UNIT-TESTED | nothing removes friction automatically beyond preparing work and compressing decisions |
| 34 | §8 Computational modalities (interoception) | MISSING | MISSING | MISSING | EXISTING (8 derived, 6 declared unobserved) | UNIT-TESTED | external modalities need sensors |
| 35 | §12/§28 Opportunity package | MISSING | PARTIAL (#158 Foundry) | PARTIAL (WMI assessment) | EXISTING | UNIT-TESTED | due diligence and people/resources remain prepared work |
| 36 | §27 'I want X' intake | MISSING | PARTIAL (#137 asks) | MISSING | EXISTING | UNIT-TESTED | deterministic draft; a local drafter must beat it |

## 4. Preserved future targets with the blocking dependency (section 32.14)

| Target | Why not now | Blocking dependency |
|---|---|---|
| 24/7 operation, dormant goals woken by real time | nothing here installs a scheduler | founder activation decision; a bounded host trigger (cron / APScheduler as DALEOBANKS already runs / Temporal) per `docs/founder-loop-entry-gate.json` G5, P1 |
| Alien sensorium / 100000 senses | no live sources are wired | authorized data access and per-source `SignalEnvelope` adapters (DALEOBANKS perception and ContextPackets, WMI market monitor, public feeds) |
| Learned relevance and model-backed proposers | rule baseline only | local open-source model route (INTENT-20260930) attached through standing-cognition proposers; must beat the rule baseline on held-out signals |
| Autonomous execution at scale | the loop holds no grants | founder-issued standing grants through the existing issuer; the Gate consumes, never fills in |
| Capability Genesis builder | plan, qualification and founder-gated attach exist; nothing here writes the candidate | reconciliation of a builder lineage (#129 genesis, #164 RECOMBINE, #137 builder) or a bounded coding-agent route under the Capability Genesis contract |
| Founder authentication for goal authorization | goals carry declared lineage only | SR001 G6: canonical founder key custody and revocation |
| External verification of outcomes | synthetic executors | a real outcome adapter with `validation_status: externally_verified` |
| Cross-organ goal feeds | kernel-side adapters from canonical packets and assessments exist (`egregore/organ_signals.py`); organs untouched | a live bridge transport (both organs refuse anything but synthetic localhost today) and a ContextPacket contract reconciliation |
| Physical embodiment | out of scope | authorized device/robotics interfaces under the Gate |
| Richer Experience Surface metrics (recall, cross-modal inference, prediction calibration) | seven metrics implemented | calibration data from real predictions (`CausalMemory.calibrate` is the intended consumer) |
| Merge of this PR and any lifecycle beyond TESTED | adoption is not a build-session decision | founder decision on `deliberation-goal-gravity-2026-10-13.json` (NEEDS_FOUNDER_DECISION, level constitutional) |
| End-to-end Capability Genesis on `main` (search -> build -> sandbox -> independent verify -> attach -> resume) | detection, typed record, search (acquisition plan), qualification by declared tests, founder-gated attach and resume exist here; build and sandbox do not | founder ruling on PR #137's `greg/genesis.py` lineage or an instruction to re-derive it; attach authority is a founder CAPABILITY_ATTACH-class decision |
| OS-supervised host surviving SIGKILL without a human calling `turn()` | nothing here installs a supervisor | `docs/founder-loop-entry-gate.json` HOLD_ACTIVATION (G5) and an operations environment |
| Any EXTERNALLY VERIFIED compounding, attention-conservation or experience-to-learning evidence (CMC/VEPMC > 0) | synthetic executors and test-minted grants only | a real consequence under a founder-issued grant, a real counterparty response, independent appraisal |
| Real founder authentication for authorization, answers and refusals | chat text, hashes, shared keys and the committed demo key never authenticate Alfonso | SR001 G6 founder enrollment outside this package |
| DALEOBANKS perception as kernel-valid context-packet experience | schema mismatch (source/risk enums, stakes/incentives arrays, provenance shape) | an adapter with declared loss, a DALEOBANKS manifest refresh, `rfc3339-validator` in CI |
| Asymmetry retention fed from WMI validation plans / next actions / monetization paths | no versioned contract for those fields | a venture-assessment 1.2 contract and adapter field mapping with declared loss |
| Isolated qualification of generated capabilities | `qualify()` is a subprocess inside this repository | the SR001 isolated verification facility |
| Taxonomy for constructed capabilities (optimization, assignment) | the router's eight classes have no optimization class | a router-owner PR on `main` (needed for #164's reductions) |
| Torn-ledger-tail recovery | the ledger refuses to open after a partial append (fail-closed) | a repair procedure that quarantines the original first |
| `turn()` as a stage of `tick()` (one trigger clock) | today `turn` consumes `tick` candidates as a projection with its own conflict record | founder decision after the first durable scheduler integration (second-increment dissent) |

## 5. How the loop is called

```python
from egregore import GoalGravityLoop, GoalSpec, ResourceGovernor
from egregore.cognition_seam import GoalProposer
from egregore.runtime import StandingCognitionRuntime
runtime = StandingCognitionRuntime(ledger=ledger, proposers={"goal-gravity": GoalProposer(), **other_proposers},
                                   evaluators={"guardian": guardian, "treasury": treasury})
loop = GoalGravityLoop(ledger=ledger, compiled=compiled, passports=passports,
                       actor=passport_id, legal_principal="alfonso_lopez", genomes=genome_registry,
                       cognition=runtime)                            # omit cognition -> declared-move mode
goal_id = loop.registry.authorize(spec, now=now)                      # declared lineage, dormant
turn = loop.turn(trigger_id="scheduler:2026-11-22T10", now=now, signals=signals,
                 resources=ResourceGovernor(max_model_calls=4, max_estimated_cost_usd=0.05),
                 grants={"research.brief": grant}, gate=gate, executor=executor, evidence_confidence=0.9)
loop.status(goal_id, now=now)                                        # the fourteen section-27 fields
loop.founder_answer(item_id, decision="refuse", actor="alfonso_lopez", note="not now", now=now)
loop.reconcile(goal_id, now=now)                                     # close attempted/unknown moves from Gate records
loop.verify_outcome(goal_id, route_hash, verifier="auditor:x", evidence_refs=[...], note="...", now=now)
loop.measures(now=now)                                               # identity / agency / intelligence / surface
# Competency Compiler: pass capability_router=CapabilityRouter(genome_registry, ledger=ledger) to the constructor,
# register competencies with loop.competency.register(Competency(...)), and give plan nodes a problem_class.
plan = loop.acquisition.plan(goal_id, now=now)                       # ladder for an open deficit (no install)
q = loop.acquisition.qualify(goal_id, genome=g, competency=c, acceptance_tests=["tests/..."], evaluator="harness:pytest", now=now)
loop.propose_attach(goal_id, q, now=now)                             # one founder decision; accept attaches
draft = loop.intake.draft("I want X", now=now)                       # section-27 fields; authority stays unresolved
```

A scheduler must supply a globally stable `trigger_id`; retrying it with the same inputs returns the recorded turn,
and changing the inputs under the same id is refused and retained as a conflict.
