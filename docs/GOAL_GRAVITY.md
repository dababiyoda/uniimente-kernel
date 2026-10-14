# Goal Gravity: authorized goals as persistent attractors

Status: IMPLEMENTED on `main`'s canonical standing runtime (draft PR); adoption and activation are founder decisions.
Intent: `INTENT-20261013-GOAL-GRAVITY` (`docs/intent/INTENT-20261013-GOAL-GRAVITY.md`).
Verbatim founder source: `docs/intent/sources/GOAL-GRAVITY-DIRECTIVE-2026-10-13-source.md`.
Decision record: `docs/decisions/ADR-GOAL-GRAVITY-001.md`; deliberation `docs/collaboration/deliberation-goal-gravity-2026-10-13.json`.
GREG body binding: `docs/decisions/ADR-GOAL-GRAVITY-002-greg-binding.md` (section 6 below).

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
| Capability Genesis link | PARTIAL | UNIT-TESTED | typed `capability-deficit` record with lifecycle and resume disposition; goal blocked not closed; resolved copy on genome registration | search/compose/build of the missing capability (the drafts' Genesis builder) |
| Standing-cognition seam | IMPLEMENTED | UNIT-TESTED | tick records, guardian veto -> prepared, model-proposer candidate classified, per-goal budget metered | a model-backed proposer beating the rule baseline |
| Evidence states and verification | IMPLEMENTED | UNIT-TESTED | Gate cut after dispatch never re-dispatched; `reconcile()` from Gate events or accountable resolution; `verify_outcome()` independent only | a real externally verified instance |
| Section-33 chain | IMPLEMENTED | INTEGRATION-TESTED (synthetic) | `tests/integration/test_goal_gravity_acceptance.py` | SANDBOX-VERIFIED with a live sensor; EXTERNALLY VERIFIED; FOUNDER-ACCEPTED |

Never say "GREG experiences reality" for this code: it integrates typed observations into beliefs with provenance.
Never say "GREG creates coincidences": it detects declared factor convergence inside a window. Never say "GREG
autonomously advances goals" unless a Gate receipt exists for the move; otherwise it prepared.

## 3. Repository concept map (section 22)

Statuses use the directive's section-22 vocabulary (EXISTING / PARTIAL / DUPLICATED / MISSING / SUPERSEDED /
EXPERIMENTAL) and tiers use section 26. "EXISTING" means *works on this tree with tests*; it is never a claim of
external effect. The inspection record behind this table is
`docs/collaboration/goal-gravity-concept-map-2026-10-13.json` (full per-row evidence) and the completeness critique
`docs/collaboration/goal-gravity-completeness-critique-2026-10-13.md` (what the record got wrong, with dispositions).

| # | Concept | `main` 19fa33c | Draft lineages | Organs | This branch now | Tier now | Residual deficit |
|---|---|---|---|---|---|---|---|
| 0 | A. Persistent Goal Registry | MISSING | see record | WMI: MISSING; src/core/performance.py SMARTGoal is a per-agent cycle-counter homonym, not ... | EXISTING | UNIT-TESTED, INTEGRATION-TESTED | goal-record and goal-state records validated on write (`egregore.contract_check`); `supersede` for change-goal; no cross-process kill test; founder authentication is declared lineage only |
| 1 | B. Goal Relevance Router | MISSING | see record | WMI: MISSING; packet fields signal_type/audience/customer_segment/urgency ... | EXISTING | UNIT-TESTED | declared-match only; no organ observation adapter; no learned relevance |
| 2 | C. Goal Wake/Sleep Runtime | PARTIAL | see record | WMI: MISSING (src/services/market_monitor.py MarketMonitor.start is an unwired ... | EXISTING (in-process) | UNIT-TESTED | conserve mode wakes priority 1-2 only and records every deferral; no durable scheduler/host (HOLD_ACTIVATION) |
| 3 | D. Backcast GPS Adapter | MISSING | see record | WMI: MISSING; src/services/phase_management.py PhaseGate/PhaseManager is a venture-level ... | EXISTING | UNIT-TESTED, INTEGRATION-TESTED | moves ordered by CausalMemory precedent; later-node satisfaction flags `route_changed`; no re-planning beyond the declared plan; no ExperimentSpec/StrategyTree binding |
| 4 | E. Intervention Classifier | PARTIAL | see record | WMI: contract-bound verdict enum go\|defer\|kill\|needs_more_evidence ... | EXISTING | UNIT-TESTED, INTEGRATION-TESTED | dependency, revoked-capability and foreign-principal cases added; EXECUTE still needs a caller-supplied grant from the existing issuer (process-memory only) |
| 5 | F. Experience Integration | PARTIAL | see record | WMI: PARTIAL and reusable: adversarial cases[] (stance/severity/resolved, never averaged) ... | EXISTING | UNIT-TESTED | content conflicts refused, stale readings ignored, effects recorded; no organ adapter; belief confidence not derived from CausalMemory |
| 6 | G. Favorable Intersection Detector | MISSING | see record | WMI: MISSING (EmergingTechAgent averages impact/maturity plus a count bonus; adversarial ... | EXISTING | UNIT-TESTED, INTEGRATION-TESTED | threat factors subtract; founder-muted domains excluded; thresholds uncalibrated; no organ factor source |
| 7 | H. Asymmetry Retention | PARTIAL | see record | WMI: PARTIAL, organ-local in-memory (business_loop LoopRecord.history/learning, ... | EXISTING | UNIT-TESTED, INTEGRATION-TESTED | outcome bound to the goal's own executed move; genome envelope capped at the goal ceiling; registry re-hydrated from ledger; no externally verified outcome yet |
| 8 | I. Founder Attention Router | MISSING | see record | WMI: MISSING (requires_human_approval const; notify_role only logs). | EXISTING | UNIT-TESTED | quiet hours, defer-with-cadence, information and emergency items added; marginal value still rule-based; no delivery adapter |
| 9 | Capability Genesis connected to Goal Gravity | MISSING | see record | WMI: MISSING (manifest unresolved: venture cell charters not yet requested, Bridge B). | PARTIAL | UNIT-TESTED | typed `capability-deficit` records with lifecycle and resume disposition; resolution on genome registration; no search/build/sandbox route (builder lineage #137 awaits ruling) |
| 10 | Founder refusal/corrections recorded and not re-proposed unchanged | PARTIAL | see record | WMI: MISSING (only compliance refusals retained in influencer_company drafts and ... | PARTIAL | UNIT-TESTED | refusals, forgotten routes and revoked capabilities enforced before policy for goal-originated moves; not consulted by the Gate or the Ratifier |
| 11 | Restart continuity without duplicate consequential action | EXISTING | see record | WMI: EXISTING for evaluation admission only via kernel BridgeState (test_signed_bridge.py ... | EXISTING | UNIT-TESTED | latest-record route release; attempt-numbered re-dispatch only after accountable reconciliation; no process-kill test |
| 12 | Evidence state distinction planned/attempted/executed/externally verified/failed/unknown | PARTIAL | see record | WMI: PARTIAL (LoopRecord.stage ladder with settled_simulated vs executed; 'unknown until ... | EXISTING | UNIT-TESTED | `reconcile()` derives executed/failed from the Gate's own events; `externally_verified` requires an independent verifier with evidence; zero real instances |
| 13 | Experience Surface metrics | MISSING | see record | WMI: MISSING. | PARTIAL | UNIT-TESTED | `measures()` reports identity/agency/intelligence/experiential surface separately; intelligence is 'not measured here'; no ground-truth wake precision |
| 14 | §25 scenario 1: Persistent goal survival | MISSING | see record | see record | EXISTING | UNIT-TESTED | in-process ledger reopen only |
| 15 | §25 scenario 2: Dormant wake | MISSING | see record | MISSING | EXISTING | UNIT-TESTED | declared-match materiality |
| 16 | §25 scenario 3: Irrelevant event rejection | MISSING | see record | MISSING | EXISTING | UNIT-TESTED | rejection cost at scale unmeasured |
| 17 | §25 scenario 4: Cross-signal convergence | MISSING | see record | MISSING | EXISTING | UNIT-TESTED, INTEGRATION-TESTED | threshold uncalibrated |
| 18 | §25 scenario 5: Authority boundary | EXISTING | see record | WMI: requires_human_approval const (adapter refuses authority inflation). | EXISTING | UNIT-TESTED, INTEGRATION-TESTED | no ceiling-narrowing invariant on transition |
| 19 | §25 scenario 6: Capability deficit | MISSING | see record | MISSING | PARTIAL | UNIT-TESTED | detection, typed record and resume only |
| 20 | §25 scenario 7: Goal drift | PARTIAL | see record | MISSING | EXISTING | UNIT-TESTED | proposal-id convention; drift surfaced as a high-urgency information item |
| 21 | §25 scenario 8: Founder refusal | PARTIAL | see record | DALEOBANKS pending-only dedupe (gap); WMI none. | EXISTING | UNIT-TESTED | byte-identical route hash |
| 22 | §25 scenario 9: Restart continuity | EXISTING | see record | WMI/DALEOBANKS: BridgeState idempotency for admission only. | EXISTING | UNIT-TESTED | gate cut after dispatch covered; no process kill |
| 23 | §25 scenario 10: Evidence integrity | PARTIAL | see record | PARTIAL | EXISTING | UNIT-TESTED | independent verification path exists; no real instance |
| 24 | §25 scenario 11: Compounding | PARTIAL | see record | PARTIAL | PARTIAL | UNIT-TESTED, INTEGRATION-TESTED | `work_to_first_actionable` measures work units; synthetic goals only |
| 25 | §25 scenario 12: Attention conservation | MISSING | see record | DALEOBANKS SMS per request with no batching (risk). | EXISTING | UNIT-TESTED | rule-based marginal value; no delivery channel |
| 26 | §25 scenario 13: Sensor contradiction | PARTIAL | see record | WMI adversarial cases preserve dissent (reusable); DALEOBANKS world model has no ... | EXISTING | UNIT-TESTED | synthetic sources only |
| 27 | §25 scenario 14: Experience-to-learning | PARTIAL | see record | DALEOBANKS reflection/consolidation change organ-local priors; WMI none. | PARTIAL | UNIT-TESTED | classification input changes with beliefs; CausalMemory orders moves; no learning from a real outcome |

## 4. Preserved future targets with the blocking dependency (section 32.14)

| Target | Why not now | Blocking dependency |
|---|---|---|
| 24/7 operation, dormant goals woken by real time | nothing here installs a scheduler | founder activation decision; a bounded host trigger (cron / APScheduler as DALEOBANKS already runs / Temporal) per `docs/founder-loop-entry-gate.json` G5, P1 |
| Alien sensorium / 100000 senses | no live sources are wired | authorized data access and per-source `SignalEnvelope` adapters (DALEOBANKS perception and ContextPackets, WMI market monitor, public feeds) |
| Learned relevance and model-backed proposers | rule baseline only | local open-source model route (INTENT-20260930) attached through standing-cognition proposers; must beat the rule baseline on held-out signals |
| Autonomous execution at scale | the loop holds no grants | founder-issued standing grants through the existing issuer; the Gate consumes, never fills in |
| Capability Genesis builder | deficit detection only | reconciliation of the drafts' Genesis/builder lineage (#114/#137) or a bounded coding-agent route under the Capability Genesis contract |
| Founder authentication for goal authorization | standalone goals carry declared lineage only; on the GREG body a goal is admitted only from a founder-signed Ed25519 `GOAL` (section 6) | SR001 G6: canonical founder key custody and revocation for the founder's real key |
| External verification of outcomes | synthetic executors | a real outcome adapter with `validation_status: externally_verified` |
| Cross-organ goal feeds | organs untouched | typed adapters from DALEOBANKS/WMI wire contracts into observations (no copied governance) |
| Physical embodiment | out of scope | authorized device/robotics interfaces under the Gate |
| Richer Experience Surface metrics (recall, cross-modal inference, prediction calibration) | seven metrics implemented | calibration data from real predictions (`CausalMemory.calibrate` is the intended consumer) |
| Merge of this PR and any lifecycle beyond TESTED | adoption is not a build-session decision | founder decision on `deliberation-goal-gravity-2026-10-13.json` (NEEDS_FOUNDER_DECISION, level constitutional) |
| End-to-end Capability Genesis on `main` (search -> build -> sandbox -> independent verify -> attach -> resume) | only detection, typed record and resume exist here | founder ruling on PR #137's `greg/genesis.py` lineage or an instruction to re-derive it; attach authority is a founder CAPABILITY_ATTACH-class decision |
| OS-supervised host surviving SIGKILL without a human calling `turn()` | nothing here installs a supervisor | `docs/founder-loop-entry-gate.json` HOLD_ACTIVATION (G5) and an operations environment |
| Any EXTERNALLY VERIFIED compounding, attention-conservation or experience-to-learning evidence (CMC/VEPMC > 0) | synthetic executors and test-minted grants only | a real consequence under a founder-issued grant, a real counterparty response, independent appraisal |
| Real founder authentication for authorization, answers and refusals | chat text, hashes, shared keys and the committed demo key never authenticate Alfonso | SR001 G6 founder enrollment outside this package |
| DALEOBANKS perception as kernel-valid context-packet experience | schema mismatch (source/risk enums, stakes/incentives arrays, provenance shape) | an adapter with declared loss, a DALEOBANKS manifest refresh, `rfc3339-validator` in CI |
| Asymmetry retention fed from WMI validation plans / next actions / monetization paths | no versioned contract for those fields | a venture-assessment 1.2 contract and adapter field mapping with declared loss |
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
```

A scheduler must supply a globally stable `trigger_id`; retrying it with the same inputs returns the recorded turn,
and changing the inputs under the same id is refused and retained as a conflict.

## 6. On the GREG body (ADR-GOAL-GRAVITY-002)

One canonical persistent operating path. The egregore loop is used unchanged in its semantics and hosted in **body
mode**; the GREG binding (`greg/goal_gravity.py`) is thin and holds no authority of its own.

```text
founder-signed GOAL --Body.apply (Ed25519, nonce, TTL)--> GoalRegistry on the one body ledger (<home>/ledger.jsonl)
Body.tick: ingest inbox -> stop/pause -> goal_gravity.tick -> MissionEngine.tick -> appraisal -> anchor
goal_gravity.tick (nothing at all without a goal record):
  admission  founder_facts: each retained GOAL / GOAL_CONTROL is re-judged at its own ledger position (key valid
             there, this body, nonce unused, accepted inside its signed validity, and the same check_goal /
             check_control Body.apply ran); anything else stays on the ledger, quarantined (stop_pushing by the
             admission check)
  guard      every signed closure (revoke, supersede), stop / change, narrowing preference and priority floor is
             restored if an unsigned record widened it
  settle     a signature-verified DECISION for exactly that request and answer, rejecting a goal move's exact
             scope, is also the goal's route refusal
  sense      mission observations (check predicate recomputed from the Gate receipt of that check's own sensor
             read; a claim that differs is untrusted, a foreign receipt is no evidence), separate-process
             appraisals, greg.path nodes, non-quarantined intake (untrusted; judged by what its text names)
  reopen     a completed goal whose plan node an attributed observation shows regressed is dormant again
  loop       GoalGravityLoop.turn(gate=None, executor=None, grants=None); on a body ledger anything else raises
               awake goal  -> MissionEngine.observe_now(mission): its next read-only look, sooner (timing only);
                              a mission waiting on your APPROVAL then re-observes and repairs its other checks
                              inside its cone while the decision stays open
               decision    -> MissionEngine.request_decision: the mission's own APPROVAL for the exact scope
                              (refused, and noticed once, while the mission is paused or closed)
               information -> greg.goal.notice (no ask)
MissionEngine -> AuthorityOffice -> ConsequenceGate remains the only execution path.
```

| Concern | Canonical owner on the body |
|---|---|
| goal persistence | `egregore.goals.GoalRegistry` on `Body.ledger` (stray records quarantined, `greg.goal.record_quarantined`) |
| goal authentication | `greg.founder.FounderVerifier` via `Body.apply`; `goal_gravity.signed_commands` / `admitted` re-verify every tick |
| mission lifecycle | `MissionEngine` (signed LIFECYCLE); a goal never pauses, resumes or abandons a mission |
| execution | `MissionEngine -> AuthorityOffice.act -> ConsequenceGate.run` under the mission's signed light cone |
| founder asks | `greg.asks.record` through the engine (`request_decision`); answers only as signed DECISION commands |
| attention routing | `FounderAttentionRouter` with the hosted `BodyAttentionStore` (no `egregore.founder_ask/answer` records) |
| backcast | per goal `egregore.gps`; developmental position `greg.path`, fed in as `greg.path.<node>` observations |
| one-turn analysis | `greg gravity --situation` (#158), contract unchanged (`dormant`); the label `paused` is added alongside |
| intake relevance | `goal_gravity.BodyRelevanceRouter` (egregore `GoalRelevanceRouter.score` hook): untrusted intake counts by the mission and goal subjects its text names |
| preparation while you decide | `MissionEngine._prepare` (only after a goal's pull; a mission no goal is bound to behaves as before) |

**GOAL body** (founder key only):
`{"goal": <GoalSpec fields without goal_id/authority/execution_authority>, "missions": [<signed mission ids>],
"max_consequence_class": <no higher than the bound missions' cones>}`. The body derives the authority block from the
signature (`authorization_ref` = command digest, `authorized_at` = body clock). Each declared move must name
`{"mission_id", "action_id"}` of a static strategy of a bound mission, restate its capability, target, manifest
consequence class and cost exactly, and lie **outside** that mission's cone (inside-cone work is the mission's own).
A move may not name a strategy the founder excluded by a signed critique or a scope the founder rejected, and its
strategy must advance a check the mission's own loop pursues (any rung of an infinite mission's ladder, otherwise
any success check): the mission would never run anything else, so an approve of it could change nothing. An
identical intent is refused, and so is a GOAL signed before the founder revoked or superseded a goal with the same
intent; `supersedes` replaces an admitted goal and keeps the old one as `superseded`. A GOAL or GOAL_CONTROL the body
verifies and then rejects consumes its nonce, so the retained file cannot be re-dropped later.

**GOAL_CONTROL body**: `{"goal_id", "kind", "value"?, "reason"?}` with kind in the egregore preference kinds plus
`revoke`. A delegated device key may only narrow (`stop_pushing` true, `lower_priority`, `never_use_tactic`,
`do_not_monitor`, `ask_before`, `forget_route`, `revoke_capability`); resuming, `change_goal` and `revoke` need the
founder key.

**Waking.** Mission observations wake a goal through its `subject` conditions (a goal derived from a mission wakes
on its mission id). Untrusted intake (`greg.dataplane.ingest`, e.g. `greg.body.ingest_external`) is judged by its text: an item that names a
goal's subject (a bound mission's id or the last segment of it, the base name of any sensor or strategy target such
as `c.txt`, a relevant entity) matches the goal's subject conditions on any channel, and its channel then counts
for the goal's `domain` / `tag` conditions too; an item that names none of them is noise for that goal whatever
channel it came on. Matching is whole words after case-folding; it is lexical, not semantic.

**Preparation while you decide.** When a goal wakes and its mission is waiting on your answer to an APPROVAL, the
pull lets the mission re-observe its current checks through the Gate and repair the failing checks the awaited move
does not advance, using only static strategies inside its signed cone. Nothing new is asked, the blocker stays,
and the awaited move runs only after your signed approve, once. One pull is pending at a time; it is served
(`greg.mission.prepared`) once nothing more can be prepared, and another needs another wake. A mission no goal is
bound to waits exactly as before.

**Completion.** Completion is observation-tier and never terminal: a completed goal is reopened when an attributed
observation shows one of its plan nodes regressed (for a goal of an infinite mission the surfaces say "holding").
Founder controls still apply to a completed goal: a stop or change pauses it; a narrowing is recorded and it stays
completed; revoke closes it.

**Operating it without code:**

```text
greg gravity authorize --from-mission m:watch --print-only > goal.json   review (and edit) the derived GOAL
greg gravity authorize goal.json --key K                       sign exactly the reviewed file into the inbox
greg gravity authorize --from-mission m:watch --key K          or derive and sign in one step
greg gravity authorize goal.json --supersedes <goal-id-prefix> --key K   replace an admitted goal (kept as superseded)
greg gravity goals                                             read-only, safe while the body runs
greg gravity evidence <goal-id-prefix>                         ledger hashes behind one goal
greg gravity control <goal-id-prefix> --kind stop_pushing --value true --key K
greg decide <request_id> approve|reject --key K                answers stay on the one path (console, phone too)
```

`status()` lists missions under `missions` (and the legacy `goals` key for older clients, labelled in `keys`) and
persistent goals under `gravity`; the phone, the console ("Persistent goals") and the morning report (`goal_gravity`)
read those projections.

**Not claimed.** The loop never executes on a body; missions do all execution through the Gate. Goal completion is
observation-tier (attributed ledger observations recomputed from Gate receipts and appraisals), never external
verification. A goal never pulls a paused or terminal mission; a mission waiting on your decision is pulled only to
re-observe and repair its other checks inside its cone. Intake relevance is a lexical match on names the signed
mission and goal declare, not an understanding of the text. Evidence for this section:
`tests/unit/test_greg_goal_gravity.py` (including `test_mission_F_end_to_end_while_the_decision_is_open`),
`tests/unit/test_greg_goal_gravity_authority.py`, `tests/unit/test_greg_goal_gravity_founder_effect.py`,
`tests/unit/test_goal_gravity_body_mode.py` and the `greg-goal-gravity`
closures (IMPLEMENTED / UNIT-TESTED on temporary bodies with a test key; no external effect; nothing activates until
the founder signs a GOAL on a real body).
