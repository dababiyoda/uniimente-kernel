# Capability Genesis Loop

Status: **EXPERIMENT** (sandbox tier; no live case yet)  
Intent: `docs/intent/INTENT-0031-capability-genesis-loop.json`  
Deliberation: `docs/collaboration/deliberation-genesis-2026-10-13.json` (validator exit 0)  
Code: `egregore/genesis.py` over `egregore/parts.py`; tests `tests/unit/test_egregore_genesis.py`

## 1. Founder expression and compiled effect

Exact founder wording (2026-10-13) is preserved in INTENT-0031. In short: use the
mechanism foundry on build-your-own-x to make "a new digital developmental
substrate" for the Egregore; build it up to spider-web hegemony; maximize evidence,
institutional leverage, accountability, deterrence, victim protection and minimal
collateral harm; stay inside safety and legality; organize the work with the
collaboration protocol.

Compiled under INTENT-0030 (preserve the effect, not the metaphor):

| Founder phrase | Literal requirement kept | Compiled effect |
|---|---|---|
| "build your own x … do not clone tutorial products" | Mine the fork for primitives; build nothing that a tutorial already is | Seven primitives extracted and mutated (§3); no Git, DB, OS or container was rebuilt |
| "digital developmental substrate" | none (metaphor) | The shared state and lifecycle on which capability formation runs: deficit → candidates → trial → dossier → ratified binding → reusable genome |
| "anti-fragile, durable compounding asymmetric leverage" | none | Each formation leaves a genome and a rung-1 reuse path; failures become classified evidence; the loop gets cheaper per use |
| "maximize evidence" | yes | Content-addressed deficits and dossiers; trial samples; verifier tiers |
| "institutional leverage" | yes | Retained capabilities are portable genomes other organs can instantiate within envelope |
| "accountability" | yes | Every transition names an actor; bindings carry Gate receipts |
| "deterrence" | yes | Forged/replayed records are ignored; self-promotion impossible; doctrinal refusal blocks retain |
| "victim protection, minimal collateral harm" | yes | Required Guardian/Treasury cannot be emptied; shadows have no influence; rollback exists; stop is free |
| "impermeable shield … total systemic dominance" | none (metaphor) | Non-bypassability *inside* UNIIMENTE: no part changes without the Gate. Dominance over people or markets is not a goal and is not claimed |
| "spider-web hegemony" | the method | Applied to the internal formation transaction (§6). Market-level hegemony needs a governing external transaction that does not exist yet: **Stage-gate** |

## 2. The invention

**Name.** Capability Genesis Loop.  
**Identity.** A governed case lifecycle that turns standing cognition's own recorded
failures into ladder-ordered, shadow-trialled, human-ratified capability changes whose
outcomes become reusable genomes.

**Why it is different from what existed.** The parts board (PR #129) lets a human swap
a part. The evolution loop runs market-shaped improvement cycles. The genome registry
stores capabilities. None of them is triggered by the Egregore's own evidence, none
enforces that cheaper real mechanisms were considered first, and none turns a retained
change into the cheapest candidate for the next deficit. The loop does only that
connecting work and adds no authority.

**Emergent capability.** A new state the institution can maintain: an open, evidence-
bearing *formation case* with an admissibility record, a growing trial dossier whose hash
is what a human approves, and a terminal outcome that feeds the next case. No source
mechanism maintains that state alone.

## 3. Source mechanisms and mutations (build-your-own-x as atlas)

| Build-your-own-x category | Primitive extracted | Mutation applied | New behavior |
|---|---|---|---|
| Git | content addressing of objects | *object substitution*: the addressed object is a **deficit claim** and a **dossier**, not a file tree | Two identical failure patterns are one case; a dossier can be approved only as read |
| Database (write-ahead log) | replay to rebuild state | *authority mutation*: replay applies a "retained" label only when the authorized binding it names exists | Forged or replayed decision records are history, never state |
| Operating system | capability tokens | *moment relocation*: the token (Gate grant) is required at shadow and bind, never at observe/propose/stop | Stopping and observing are free; changing behavior is not |
| Distributed systems (quorum) | threshold agreement | *object substitution*: quorum becomes **verifier tier**; hypothesis-only tiers cannot retain | A model's opinion of a model cannot promote a model |
| Emulator / VM | run the same input on two machines | *information mutation*: shadow output is recorded, compared and never selected | Trial without influence |
| Package manager | dependency resolution order | *incentive mutation*: candidates are admissible only in resourcefulness-ladder order; `new_architecture` last | The anti-literalization gate becomes executable |
| Immune system (biology, via developmental research) | detect → contain → learn | *dynamic mutation*: failures in trial become classified learning artifacts (`evolution.failure_analysis`); `doctrinal_refusal` is lethal to the candidate | Never route around doctrine |

Each row changed incentives, authority or consequence, not only implementation.
Explaining the loop needs no repository names: deficits open cases; candidates enter in
cheapest-first order; shadows run without influence; a reviewed hash binds under a grant;
retained parts become genomes.

## 4. Topology

```mermaid
flowchart LR
  C[CognitionCycles on ledger] --> D[DeficitDetector]
  D -->|content-addressed deficit| O[observe: case OPEN]
  O --> P[propose: ladder-ordered candidates]
  P -->|Gate grant| S[shadow bind on PartsBoard]
  S --> R[shadow_run per tick]
  R -->|shadow_result records| T[record_trials: aggregate]
  T --> X[dossier: content hash]
  X -->|human reads hash| V{ratify}
  V -->|retain + verifier tier + Gate grant| B[active bind]
  B --> G[CapabilityGenome registered]
  G -->|rung 1 next time| P
  V -->|regress / kill: no grant| E[terminal, preserved]
  B --> N[rollback_target kept]
```

Feedback loops: (1) retained genome → cheaper next case; (2) failure classes → dossier
→ ratifier judgment; (3) recurrence count → case priority for humans.

## 5. Authority, incentives, failure

- **Authority.** Unchanged. Observe, propose, aggregate, regress, kill, close: no grant.
  Shadow and retain: `PartsBoard.change` through the Consequence Gate with a
  single-action grant bound to the slot's ledger head. The loop has no code path that
  binds without a grant (`tests/unit/test_egregore_genesis.py`).
- **Incentives.** Recording a cheaper rung as `searched_none` is free but attributed;
  the ratifier sees who said so (dissent recorded: this is self-reported). A candidate
  that fails in trial still produces a classified failure record, so failure is cheaper
  than concealment.
- **Failure and recovery.** Malformed ledger history is skipped on hydrate and kept as
  history. Parts whose code is not registered after restart are reported `resolved:
  false`, never guessed. Rollback uses the board's prior part. Terminal cases refuse
  further operations; a new deficit opens a new case.

## 6. Spider-web applied honestly

**Governing transaction (internal).** Alfonso must obtain a verified new or repaired
cognition capability, but completion is unreliable because fitness proof (shadow
evidence), eligibility (which mechanisms are admissible), routing (which slot) and
settlement (ratified binding) are not connected.

**Thesis.** Become the only path by which a standing-cognition part changes, by
controlling admissibility at proposal time, issuing a content-addressed dossier, and
tying it to a Gate-granted binding and a registered genome, while a bypass (editing code
by hand) cannot produce a receipt, a genome or a reusable rung-1 candidate.

**Four super-nodes.** Eligibility = ladder admission and slot match. Default routing =
slots and shadow-before-active. Proof/Truth = deficit ids, shadow_result records,
dossier hash, verifier tier. Settlement = Gate grant → binding record → genome.

**17-item checksum.** 1 bounded failure ✔ · 2 mandate-capable actor ✔ (Alfonso, internal
only) · 3 accepted artifact ✔ (dossier hash, accepted by the Gate path) · 4 downstream
consequence ✔ (binding changes cognition) · 5 eligibility ✔ · 6 default routing ✔ ·
7 proof→settlement ✔ · 8 NBOC trajectory **unresolved** (no live cases; natural
denominator = part changes; target 100 % through the loop) · 9 capital physics **n/a**
(zero fees; compute is real but unmeasured) · 10 incumbent self-harm **n/a** (no
external incumbent) · 11 four loops ✔ internal only · 12 governance/kill ✔ · 13 business
form ✔ (Tool inside an institution; not a market) · 14 intelligence flywheel **partial**
(failure classes and genomes; no live data) · 15 network effects **none claimed** ·
16 five-outcome **below gate**: Commercial 0, Strategic 3, Regenerative 3,
Institutional 4, Capital 0 · 17 capital continuity **n/a**.

**Decision: Stage-gate.** The internal control layer is complete and tested; nothing at
market level is claimed. The external wedge requires the founder to designate the first
venture cell's governing transaction (SR-INTENT-3 boundary). Until then, "hegemony" means
only: inside UNIIMENTE, no cognition part changes except through this proof-bound path.

## 7. Omnidirectional consequences (compressed)

| Perspective | Effect | Design response |
|---|---|---|
| Founder | Fewer hand edits; a dossier to read instead of code | Dossier is one JSON object with a hash |
| Future contributor | New vocabulary (cases, rungs) | One README table; states are the minimum for restart |
| Affected parties of Egregore proposals | Candidates cannot widen consequence class; evaluators cannot be emptied | Observed classes enter the genome envelope; `requires_human` for financial/irreversible |
| Hostile insider | Could forge records or false ladders | Forgeries ignored on hydrate; ladders attributed; retain needs grant + tier |
| Model vendor | Any local model is one `PartSpec` | Hosted models are not offered as parts (INTENT-20260930) |
| The system under degradation | Shadow server down → classified `transient`, not harm | Transient failures do not block retain; others do |
| Future descendant organs | Genomes are portable | `GenomeRegistry.may_instantiate` bounds them |

## 8. Adversarial analysis (what was attacked and what happened)

Each guard was deleted in turn; a test failed each time: cheaper-rung requirement,
`new_architecture` admission, doctrinal-refusal block, forged retained decision, dossier
integrity, minimum samples, foreign shadow results, hypothesis-only retain. Residual:
self-reported ladder outcomes (dissent recorded, owner named, trigger: first
`new_architecture` candidate).

## 9. Novelty boundary

- Known primitives: content addressing, WAL replay, capability tokens, canary/shadow,
  verifier tiers, package resolution order, failure classification.
- Known combinations: canary + rollback; feature flags + approvals.
- Mutated mechanisms: ladder-ordered admissibility as an executable anti-literalization
  gate; dossier-hash-bound ratification; replay-safe "retained" labels; failure classes
  as lethal-to-candidate evidence.
- Likely novelty: the interaction topology in which a cognition organ's own recorded
  failures open evidence-bearing formation cases that end in portable genomes, under an
  authority model where every behavior change needs a grant and every stop is free.
  Components are known; the mutated interaction appears structurally distinct from
  located precedents (feature-flag services, MLOps model registries, canary controllers,
  which do not bind admissibility to a resourcefulness ladder or decisions to a reviewed
  content hash). No patent or freedom-to-operate claim is made.

## 10. Evidence

| Claim | Tier | Reference | Finding |
|---|---|---|---|
| Loop retains only through a Gate-granted binding and registers a genome; a second mission reuses it | unit test (real Gate, grants, passports, ledger; fake proposers) | `test_mission_pauses_capability_forms_mission_resumes_and_second_case_reuses_it` | pass |
| Guards are load-bearing | sandbox execution | mutation runs 2026-10-13 (8 original + 11 correction guards) | each removal fails a test; one equivalent mutant removed as dead code |
| No kernel regression | unit tests | `python -m pytest` 2026-10-13 (after correction) | 666 passed, 4 skipped, 2 failed; the 2 (`test_migration_spec_frozen`, `test_repair_spec_frozen`) fail identically on `main` in this shallow clone and passed in GitHub CI on the prior head |
| The loop achieves the founder's destination in reality | **none** | no live case | unproven |

## 11. Build path and kill test

1. **Now (this PR, draft):** code, tests, records. Decision EXPERIMENT.
2. **First live case (next):** run a real local model (`local_draft_part`) in shadow
   against a real deficit on real signals; aggregate ≥ 3 samples; founder ratifies with
   `qualified_human_review`. Measurable result: one case reaches RETAINED or REGRESSED
   with a dossier the founder actually read.
3. **Compounding check:** open a second deficit in the same slot; the retained part must
   appear as the rung-1 candidate; ticks-to-decision must fall.
4. **Kill test:** if a retained binding ever appears without a Gate receipt, or a forged
   record changes live state after restart, or the first live case shows the loop changed
   no decision a human would have made anyway, kill the loop and keep the record.

## 11a. Correction increment (external review, 2026-10-13)

A reviewer reproduced four defects at head `00765bc` with isolated synthetic
dependencies. Each is now a regression test; each guard was removed in turn and a test
failed (one surviving mutant was an equivalent mutant and the dead clause was removed).

| Reproduced defect | Correction | Regression test |
|---|---|---|
| The same part id accepted a different callable | `PartSpec.artifact_digest` is computed from the callable's bytecode, constants, defaults, closure and public state (`egregore/artifact.py`) and is part of `part_id`; `register` refuses code that does not match a bound spec, before and after restart; `model_digest` joins identity | `test_same_description_with_different_code_is_a_different_part`, `test_registering_mismatched_code_under_a_bound_identity_is_refused`, `test_model_digest_is_part_of_identity` |
| Three timeouts produced "ready for ratification" | Attempts, successes and typed failure classes are counted apart; readiness needs successful evaluations on distinct cycles **and** the deficit's target evidence (restorations where the active part produced nothing); non-mechanical targets need a strong verifier tier | `test_three_timeouts_never_make_a_case_ready_or_retainable`, `test_three_successes_on_one_cycle_are_one_evaluation`, `test_successes_without_restoration_do_not_meet_a_restoration_target`, `test_non_mechanical_target_needs_a_strong_verifier` |
| Killing a case left its shadow running | `PartsBoard.stop_shadow` is a ledgered, grant-free stop direction mirroring `suspend` (never touches active parts); regress, kill and close call it; `shadow_run` then has nothing to run | `test_stop_shadow_is_grant_free_effective_and_leaves_active_safeguards`, `test_kill_and_close_stop_shadow_execution_and_keep_safeguards` |
| "connection refused" became `doctrinal_refusal` | `egregore/failures.py`: classification by exception type only (`DoctrinalRefusal`, `CapabilityMissing`, `ResourceExhausted`, transport errors → `transient`); runtime and shadow failures carry `failure_class`; messages are never consulted | `test_shadow_failures_are_typed_by_exception_not_message`, `test_component_failure_is_attributed_by_typed_class_not_message` |

The two larger gaps:

- **Legitimate refusal vs functional failure.** `diagnose()` attributes a deficit to the
  proposal, evidence, permission, infrastructure, resources, policy, evaluator, component or a
  missing slot before anyone may propose a replacement. A Guardian vetoing with objections is
  working (`responsible: proposal`, `legitimate_refusal: true`); replacing it is refused
  unless the human records an evidence-bearing override. Unexplained vetoes against peer
  approval point at the evaluator. The diagnosis is deterministic rules over cited cycles and
  is labelled a prior for the human, not a verdict.
- **Candidate discovery.** `discover()` gathers leads cheapest rung first from retained
  genomes and the genome registry, parts already described for the slot (incl. rollback
  target), the audited open-source catalog (license, stars, archived, pushed_at) plus an
  optional search service, and the existing commissioning path (`ChangeProposal` through
  `runtime.propose_change`). The search itself is a ledger record. `searched_none` must cite a
  discovery record of the case that consulted that rung and found nothing; if discovery found
  leads, `searched_none` is refused. The ladder is a decision prior: a later rung may hold a
  candidate alongside a cheaper one, and `new_architecture` may be admitted over a cheaper
  candidate, through a recorded exception with evidence.
- **Missions.** A deficit may carry the goal it blocks (`goal_id`, `objective`,
  `parent_trigger_id`); the goal is paused, not closed (`egregore.mission_paused_for_deficit`)
  and resumes with the outcome and genome key when the case ends
  (`egregore.mission_resumed`). `verify_outcome()` re-scans later cycles for the same deficit
  and records an internally verified outcome, labelled as not externally verified. This is a
  seam for the goal records in open PR #160 (which block on `missing_capabilities` and unblock
  on genome registration); no mission engine was added.

**Measured reuse** (`test_mission_pauses_capability_forms_mission_resumes_and_second_case_reuses_it`):
mission A adopts a drafter from the open-source rung (ladder depth 3, one new part
registration, 3/3 trial successes); after a rollback recreates the deficit, mission B finds the
retained part as a rung-1 lead (depth 0, zero new registrations, 3/3 successes, no more ledger
records than A). Measured: search depth and registration effort fall at equal reliability.
Wall-clock time and compute cost were not measured in the sandbox.

## 12. Final decisions

- Foundry: **EXPERIMENT** (unchanged after the correction increment). Next action: first live shadow case. Measurable: one case
  reaches a terminal state with a read dossier. Evidence: ledger records + founder
  ratification. Stage gate: before any claim beyond sandbox. Termination: kill test above.
- Spider-web: **Stage-gate** (internal control complete; external wedge needs a founder
  decision on the first venture transaction).
- Collaboration protocol: **EXPERIMENT**; constitutional questions (external wedge,
  model evaluators, grant-free shadow detach) returned as NEEDS_FOUNDER_DECISION items in
  INTENT-0031 `unresolved_questions`.
