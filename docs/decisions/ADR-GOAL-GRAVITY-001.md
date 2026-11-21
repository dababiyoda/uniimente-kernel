# ADR: Implement the Goal Gravity loop on the canonical standing runtime

- Decision ID: ADR-GOAL-GRAVITY-001
- Status: proposed (draft PR; adoption into `main` is a founder decision)
- Date: 2026-10-13
- Decision owner: Alfonso Lopez
- Deliberation level: Constitutional (touches the canonical runtime package and adds shared contract files)
- Founder intent references: `INTENT-20261013-GOAL-GRAVITY`, `INTENT-0030`, `SR001-FOUNDER-LOOP-ENTRY`, `INTENT-0027`, `INTENT-0028`
- Deliberation record: `docs/collaboration/deliberation-goal-gravity-2026-10-13.json` (validator exit 0)
- Supersedes: none (additive)
- Superseded by: none

## Problem

**Observations.** The 2026-10-13 founder directive (verbatim in
`docs/intent/sources/GOAL-GRAVITY-DIRECTIVE-2026-10-13-source.md`) names nine literal targets (section 24 A–I),
fourteen deterministic scenarios (section 25), fourteen founder-facing fields (section 27) and an acceptance chain
(section 33). Kernel `main` (`19fa33c`, 626 tests green) carries standing cognition, the durable workflow spine, the
hash-chained ledger, the policy engine and Consequence Gate, causal memory, the capability genome registry and the
morphogenesis target-state contracts. It carries **no** goal persistence, relevance routing, wake/sleep, executable
Backcast GPS, intervention classification, world-model integration, intersection detection, retention or attention
routing. Fifty open draft PRs form stacked GREG lineages off `main` with overlapping, unmerged mechanisms
(`greg/missions.py`, `greg/asks.py`, `greg/genesis.py` on #114/#137; `greg/gravity.py` on #158; the Goal Chase
sandbox on #93/#97/#109).

**Inference.** On the canonical line the residual CapabilityDeficit is targets A–I themselves.

**Unresolved claims.** Which draft mechanisms should be ported onto the canonical loop first; which durable scheduler
owns the trigger clock; founder authentication and key custody (SR001 G6).

**Proposed action.** Build A–I as additive modules inside `egregore/` composed over the existing ledger, policy
engine, Gate and genome registry; preserve and credit the draft lineages; open a draft PR; adopt only on founder
decision.

## Baseline and evidence

| Claim | Claim class | Evidence tier | Source and location | Finding | Limitation |
| --- | --- | --- | --- | --- | --- |
| `main` baseline green | observation | unit_test | `python -m pytest -q` on `19fa33c` | 626 passed, 4 skipped | synthetic suite |
| No goal substrate on `main` | observation | primary_source | `egregore/`, `memory/`, `capabilities/`, `docs/BACKCAST_GPS.md` read in full | no goal record, wake condition, GPS code or classifier exists | none |
| Draft lineages carry overlapping mechanisms | observation | primary_source | PR bodies #158/#137/#114/#101; worktrees of #158/#137/#159/#114/#97/#109 | `greg/` exists only on drafts; #158's gravity is a one-turn read-only command | drafts not re-executed here |
| Section-25 scenarios pass | implementation | unit_test | `tests/unit/test_goal_gravity.py` | 20 passed | deterministic, model-free |
| Section-33 chain passes | implementation | sandbox_execution | `tests/integration/test_goal_gravity_acceptance.py` | 1 passed; executor called once; outreach prepared, never executed; capability retained; later goal unblocked | JSONL ledger, test passport, development witness key |
| Suite and verifier green after change | implementation | unit_test / deterministic_fixture | `tests/evidence/goal-gravity-20261013/` | 647 passed; verifier V1–V5 PASS incl. `egregore-goal-gravity` closures | synthetic |
| Second increment green | implementation | unit_test | `tests/unit/test_goal_gravity_seams.py` + the above (`tests/evidence/goal-gravity-20261013/pytest-full-suite-increment-2.log`) | seam, deficits, reconciliation, verification, controls, attention pass; full suite and verifier rerun recorded | synthetic; test-minted grants |
| External effect through this loop | unresolved_claim | other | none | zero; CMC/VEPMC unchanged at 0 | not claimed |

## Alternatives

- **Current baseline:** standing cognition + Gate with no goal substrate. Every target MISSING.
- **Do nothing:** targets stay MISSING on the only canonical line; the PR graph keeps growing. May win only on a founder freeze instruction.
- **Simplest viable alternative:** a goal registry alone (target A). Persists intent, never acts; fails section 33.
- **Strongest competing architecture:** stack on #137's mission engine (strongest existing durability and asks). Rejected because it is unmerged and would be a second mission authority plane relative to `egregore/runtime.py` + the Gate until reconciled. Revival: founder adoption of #137; then the canonical registry feeds `greg/missions.py` through a typed adapter.
- **Also rejected:** stack on #158 (four drafts deep; deepens the parallel `greg/` runtime); documentation-only (directive sections 23 and 32 forbid stopping at documentation).
- **Reversible experiment (selected):** this draft PR. Additive modules and contracts, revertable in one commit; nothing activates.

## Reuse map (search before build)

| Need | Reused from `main` | How |
| --- | --- | --- |
| Durable, restart-safe goal state | `provenance.ledger.EvidenceLedger`; `StandingCognitionRuntime._hydrate` pattern | goal/world/turn records hydrate from `ledger.records` |
| Signals | `egregore.contracts.SignalEnvelope` | typed observations ride in `payload["observations"]`; text stays data |
| Idempotent turns | cognition `trigger_id` + request hash + conflict record | `GoalGravityLoop.turn` |
| Deliberation | `StandingCognitionRuntime.tick` (proposers, guardian/treasury evaluators, selection with dissent, metered calls) | `egregore/cognition_seam.py`; per-goal governor carved from the turn budget |
| Record contracts | JSON Schema 2020-12 via `jsonschema` with `rfc3339-validator` | `egregore/contract_check.py` on every goal/state/experience/deficit write |
| Policy verdicts | `policy.engine.evaluate` | `InterventionClassifier.classify` |
| Execution | `policy.consequence_gate.ConsequenceGate.run` with a caller-supplied pre-existing grant | at most one move per goal per turn |
| No duplicate consequential action | durable `attempted` intervention record + the Gate's `grant_dispatch` claim | `_already_attempted` (latest record per route); `reconcile()` reads the Gate's `action.*` events; re-dispatch only after reconciliation under an attempt-numbered proposal id |
| SBM gap arithmetic | `morphogenesis.contracts.MetricTarget` / `MorphogeneticEngine._error` | `gps.metric_error` |
| Reusable capabilities | `capabilities.genome.GenomeRegistry` | `AsymmetryRetention.retain` registers bounded genomes |
| Drift visibility | the Gate's own `action.committed` events | proposal-id prefix `egregore:goal:<goal23>:<route23>` |
| Compressed founder asks | the shape of #137's `greg/asks.py` (options, no-cost option, no manufactured urgency), re-expressed on `main` | `FounderAttentionRouter` |

## Reconciliation adapters (preserved lineages)

| Lineage | Mechanism | Disposition |
| --- | --- | --- |
| #158 `greg/gravity.py` | one-turn `greg gravity --situation` (GPS → Foundry → Gate proposals → VOI → one ask) | preserved; if merged, its turn can call `GoalGravityLoop.turn` for persistence and consume `status()`; the Foundry/VOI stages are additive proposers |
| #114/#137 `greg/missions.py`, `greg/asks.py`, `greg/genesis.py`, `greg/lightcone.py` | persistent missions, kill -9 recovery, founder asks, Genesis builder, authority light cone | preserved; if adopted, missions consume goals from `GoalRegistry` and answer asks via `founder_answer`; Genesis attaches genomes that `AsymmetryRetention` already recognises |
| #93/#97/#109 Goal Chase | obligations, due triggers, autonomous recovery proofs (SR001 P1–P7) | preserved; its durable trigger/supervisor is the intended caller of `turn()`; its proofs remain the activation gate |

## Five-role review

| Role | Position | Material concerns | Evidence | Recommendation |
| --- | --- | --- | --- | --- |
| Founder-Intent Steward | faithful reading: literal targets built, metaphors compiled to effects, rhetoric quoted not claimed | over-literalizing "coincidence production"; shrinking the destination | intent record; source file | EXPERIMENT |
| Systems Architect | one ledger, one Gate, one policy engine; goals are data; no new authority object | proposal-id convention; external grant supply | `gravity.py`, `interventions.py`, `consequence_gate.py` | EXPERIMENT |
| Adversarial Reviewer | strongest attack is "third lineage"; countered by canonical composition and credited preservation | third-lineage risk; narrow sensorium; evidence-asset inflation | authority-boundary and restart tests | EXPERIMENT |
| Operator and Maintainer | stdlib only; 30 s suite; closures on the verifier; rollback is one revert | ledger growth; serial processing | README; `gravity_registry.py` | EXPERIMENT |
| Evidence and Welfare Guardian | no external effects; no-cost options; refusals remembered; tiers stated | wording discipline; per-goal mute only | `attention.py`, `experience.py` | EXPERIMENT |

## Pass 1

- Intended outcome: authorized goals become persistent attractors on the canonical runtime (see deliberation).
- Advantages: A1 one substrate on the pinned line; A2 structural authority boundary; A3 outcome-anchored compounding; A4 budgeted attention.
- Disadvantages: D1 overlap with drafts (high, governance); D2 narrow sensorium (medium, modularity); D3 external grant supply (medium, evidence); D4 proposal-id convention (low, protective); D5 evidence-asset inflation (low, evidence).
- Comparisons and rejected alternatives: as above, with revival evidence recorded.

## Pass 2

- Attack summary: de facto mission system rots the drafts; prepare-only turns mistaken for progress; goal specs read as authority; ledger growth; fixture overfit; rhetoric mistaken for achievement.
- New weaknesses W1–W6 and strengthening responses: in the deliberation record.
- Disposition of every Pass-1 disadvantage: D1 accepted (owner Alfonso; trigger: ruling on the PR graph); D2 accepted (owner kernel maintainers; trigger: first proposer on the relevance path); D3, D4, D5 resolved.
- Final strengthened design: nine additive modules, two additive contracts outside the pinned allowlist, five closures, verbatim source, intent record, this ADR; nothing activates.
- Residual risks: permanent duplication; narrow sensorium; ledger growth. Owners and triggers recorded.
- Recommendation: NEEDS_FOUNDER_DECISION (adoption into `main`).

## Second increment (same day, after the completeness critique)

The independent critique (`docs/collaboration/goal-gravity-completeness-critique-2026-10-13.md`) and a 53-finding review
of the first commit were triaged; the dispositions are tabled at the top of the critique. What changed in the design:

- **Deliberation seam.** `egregore/cognition_seam.py` registers a `GoalProposer` with `StandingCognitionRuntime`; when a
  runtime is attached, every awake goal's candidates come out of its `tick` (guardian/treasury vetoes honored, a
  vetoed or unselected move is prepared, never executed), metered by a per-goal `ResourceGovernor` carved out of the
  turn's budget. Without a runtime the loop runs in declared-move mode and says so in every record.
- **Deviation recorded.** `GoalGravityLoop.turn` accepts `gate` and `executor` for one turn, whereas
  `StandingCognitionRuntime.tick` must never accept an executor (asserted on `main`). The runtime proposes; the loop is
  the accountable projection that submits one selected, policy-allowed move to the Gate and retains none of gate,
  executor or grant between turns (`goal_gravity_closures.authority`; seam test on `vars(loop)`). The Gate must write
  to the same ledger the loop reads.
- **Evidence is real.** Policy sees ledger hashes (the goal's authorization record, experience records relevant to the
  goal, receipts) and a confidence that is the world model's relevance-weighted belief confidence capped by the
  caller's attestation; with no world evidence the caller's value stands alone and is labelled `caller_attested_only`.
- **Contracts enforced.** goal-record, goal-state, experience-event and capability-deficit records are validated on
  every write (`egregore/contract_check.py`, JSON Schema 2020-12, fail-closed formats). They stay outside the pinned
  boundary-package allowlist on purpose; the intent record's wording was corrected accordingly.
- **Every deficit class (section 21).** capability, resource (conserve deferrals, goal budget, grant limit),
  relationship (`PlanNode.requires_relationships`) and proof (evidence floor, unmet goal dependencies) deficits are
  recorded; the goal stays blocked, never closed.
- **Reconciliation and verification.** `reconcile()` closes `attempted`/`unknown` moves from the Gate's own
  `action.*` events (executed/failed) or from an accountable resolution recorded with its author; the Gate's dispatch
  claim is keyed on the proposal id, so a re-dispatch after reconciliation carries an attempt suffix and is never a
  replay. `externally_verified` is never the executor's own claim: `verify_outcome()` requires a verifier other than
  the executing actor and at least one evidence reference.
- **Attention (section 13).** Quiet hours batch everything but emergencies; `defer` re-surfaces after the goal's review
  cadence; `accept` is recorded as not-a-grant; the preference is written before the answer record; information items
  cover favorable intersections (on the transition), drift, a contradicted bottleneck metric, unknown outcomes
  (emergency when external) and outcome discrepancies.
- **Founder controls (section 20).** `change_goal` pauses and `supersede()` replaces with lineage; `ask_before`,
  `forget_route`, `revoke_capability` and a foreign legal principal are enforced before policy.
- **Measurement (section 19).** `measures()` reports persistent identity, agency, intelligence ("not measured here")
  and the experiential surface separately; subjective consciousness stays unresolved and unclaimed.

Evidence tier after the increment is unchanged: IMPLEMENTED / UNIT-TESTED / INTEGRATION-TESTED on synthetic ledgers
with test passports, the development witness key and grants minted by the tests from the loop's own proposals
(`docs/founder-loop-entry-gate.json` forbidden shortcut 4). No external effect. Nothing activates.

## Dissent

- Adversarial Reviewer: "a third goal/mission lineage; the directive forbids a parallel GREG". Threshold: if #137 or #158 merges, reconcile through the adapters above within one release or regress this loop. Owner: Alfonso. Trigger: ruling on the PR graph.
- Adversarial Reviewer (second increment): after the seam the loop is still a second trigger-keyed engine consuming the first's candidates, not a stage of `tick`. Threshold: a scheduler driving both with separate clocks, or the two conflict records disagreeing. Owner: Alfonso. Trigger: first durable scheduler integration.
- Systems Architect: grant supply should become a typed request to the existing issuer rather than a caller mapping. Threshold: first scheduler integration with ambiguous grant provenance. Owner: kernel maintainers.
- Systems Architect (second increment): four parallel-plane risks stay open and are connected by convention, not adapters: `WorldModel` beside `CausalMemory`/`StateObservation`; `PlanNode` beside `StrategyBranch`/`ExperimentSpec`; goal refusals not consulted by the Gate or the Ratifier; deficit lifecycle vocabulary beside #137's and the genome registry's. Owner: kernel maintainers. Trigger: first organ-fed observation adapter; first Gate proposal whose effect digest matches a refused route.
- Evidence Guardian: every EXISTING status is synthetic; test-minted grants; CMC/VDM/VEPMC remain 0. Threshold: one real consequence under a founder-issued grant, verified by `verify_outcome()` from an independent party.
- Constitutional Reviewer: the `executor` deviation at the loop boundary must stay visible and verified. Threshold: the closure authority check and the seam test keep proving nothing retains an executor, gate or grant; a scheduler holding a long-lived executor for the loop is a violation.
- Operator: #137 remains the only lineage with kill -9 and torn-tail tests, a Genesis builder with frozen oracles and a single ask writer; end-to-end Capability Genesis on `main` stays open until the founder rules on #137. Owner: Alfonso.

## Authority impact

- Changes authority: no. Every object reports `execution_authority == "none"`; goals carry declared lineage, not authentication; execution only through the Gate with caller-supplied grants; the loop never issues grants.
- Authorized-human approval required: yes, for adoption into `main` and for any activation (scheduler, sensors, real grants).
- Approval state: pending.
- Approver: Alfonso Lopez.

## Decision

`NEEDS_FOUNDER_DECISION` for adoption. The implementation stands as a reversible `EXPERIMENT` on a draft branch.
