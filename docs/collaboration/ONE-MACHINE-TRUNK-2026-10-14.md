# One-machine integration trunk — 2026-10-14

Status: **draft for founder review**. Nothing here is merged, deployed or activated.
Founder intent: `docs/intent/INTENT-20261014-ONE-MACHINE.json` (source:
`docs/intent/sources/ONE-MACHINE-CORRECTIVE-DIRECTIVE-2026-10-14-source.md`).
Branch: `claude/greg-one-machine` (head at this revision: `4ed91f7`). Evidence: `tests/evidence/one-machine-20261014/`.

## 1. Trunk selection (measured, not assumed)

Ancestry, refreshed on 2026-10-14 at 12:38 UTC, counting commits not contained in #175 `e34dfe0`:

| Lineage | Head | Commits not in #175 | What they are |
|---|---|---|---|
| main | d64a6c9 | 0 | #165 and #170 included |
| #173 | b6d9f20 | 0 | #175 is its descendant (+6) |
| #164 | c6f6370 | 0 | RECOMBINE; already in #173 |
| #172 | cda9818 | 8 | #169 increment 3 (5), recovery patch-equivalent to 7cc8187 (1), merge (1), clock fix (1) |
| #169 | 3356be9 | 6 | the same increment 3, plus an alternative clock fix |
| #176 | 1c109ff | 6 | the same increment 3, plus a third alternative clock fix |
| #129 | 9309fd8 | 5 | egregore Genesis Loop, swappable parts |
| #157 | f66f860 | 7 | cancellable, OS-confined workers (+cortex convergence) |
| #143 | 6fa9b89 | 28 | seed-genome stack on a base before Foundry-55 (44/55) |
| #166, #171, #174 | 6dd27fd, 98143d6, e253262 | 3, 2, 1 | witness, organ bridge, per-organ keys (this session) |

**Selected trunk:** #175 `e34dfe0`. It is the descendant with the broadest history (main, #173, #164 and the original #172 construction line) and the smallest integration burden. #169's unique behavior arrives through the #172 head, which already merged it.

## 2. Imported lineages: provenance and decisions

| Source (commit) | Mechanism | Trunk equivalent before | Missing behavior | Conflicts and resolution | Proving tests | Rejected / restore |
|---|---|---|---|---|---|---|
| #172 `cda9818` carrying #169 `858610d..9c46810` | Whole loop on one path: Foundry page, memory, fixture commerce, attacks; #26 relay confining `http.get`; money columns; §13 attack map; #165/#170 router registration | none | all of it | `foundry/completion.yaml` systems 9/10, `greg/capabilities.py` InvocationContext, `greg/missions.py` observation: independent additions, both kept | acceptance, adversarial machine, confined egress, first mission, mission control, venture rehearsal (130 passed at the merge) | #169 `3356be9`, #176 `1c109ff`: alternative 2-line clock fixes, superseded by `cda9818`; restore by cherry-picking either one |
| #172 `32f99ce` | governed recovery | `7cc8187` (patch-equivalent) | none | resolved by git as identical | test_greg_capability_recovery (9) | — |
| #174 `e253262` | per-organ bridge keys; identity isolation claim | shared key only | isolated sender identity | none | test_per_organ_bridge_keys | — |
| #166 `6dd27fd` | witnessed append-only checkpoints (RFC 6962/9162), cross-organ harness | `greg/anchor.py` RFC 3161 anchoring (complementary) | witness cosigning, split-view evidence | none | test_append_only_witness, test_cross_organ_mission | — |
| #171 `98143d6` | organ exchanges observable by #44; dataplane redelivery fix; mission-trace binding | none | organ facts on GREG's journal | two latent laundering paths found by merging into the canonical body (section 3) | test_greg_organ_bridge (15) | — |
| #157 `f66f860` (partial) | `supervised_run` cancellation and bounded output; trusted git metadata during collection | blocking `subprocess.run`; no metadata protection | STOP mid-work; worker git metadata cannot run in GREG | — | test_one_machine_attacks: STOP and git-hook attacks fail on the previous code | **Not ported:** `greg/worker_isolation.py` (bubblewrap PID/user/IPC namespaces, read-only root). It refuses every worker on hosts without bubblewrap, including macOS. Founder decision; restore by porting the module and calling `prepare_worker` in `ClaudeCodeWorker.run` / `CliAgentWorker.run` |
| #129, #143 | Genesis Loop / seed genome | partial (see gap map) | under investigation in this run | not merged | — | preserved on their branches |

## 3. Defects found by integrating, and fixed

1. **Organ appraisal laundering.** `organ_bridge.record_appraisal` wrote `mission.appraised: REPRODUCED`. The body skips closure appraisal for any mission id that already has one, and VEPMC and routing read the latest. The organ appraisal now uses `organ.appraised`.
2. **Organ observation corruption.** Organ messages were `mission.observed`, which the mission engine rebuilds check state from, so it crashed with `KeyError: check_id`. Now `organ.observed`.
3. **Mind → Hands handoff impossible after Genesis.** The answer existed only in a re-observation receipt, and bindings read action receipts only. Added check-sourced bindings: a strategy may bind the receipt of the latest *passing* observation of a check it requires.
4. **Founder reconciliation crashed Mission Control and the Morning Tribunal.** No test had ever answered a reconciliation.
5. **Mission traces mis-ordered.** Timestamps came from different clocks. Traces now follow ledger sequence.
6. **STOP waited for in-flight workers** (up to 3600 s).
7. **Worker-planted git hooks/filters executed inside GREG's collection.**
8. **Silent provider-side model substitution.** `fallbacks="default"` re-ran refused requests on a provider-chosen model.
9. **Frozen-history tests failed in shallow checkouts.** This explains part of the #173/#175 discrepancy (`suite-discrepancy.json`).

## 4. Founder-reserved decisions (not taken by this run)

- Merge of this trunk, and which convergence line is canonical upstream.
- Worker OS confinement policy: adopt #157's bubblewrap-required envelope (refuses on hosts without it, including macOS), or allow a labeled lower-assurance mode per host. Organ stages are now Landlock-confined where the kernel supports it; where it does not (macOS, older kernels) they run with `filesystem_confined: false` stated in the receipt, and whether to refuse instead is the same founder decision.
- Organ pin upgrade from `uniimente-kernel-boundaries` 4999acff so organ identities are isolated (per-organ keys need organ-side support).
- The first VEPMC device: Mac or Chromebook. The source conflict is preserved, not resolved.
- Re-admission of recovered capabilities under existing mission scopes (#175's open question).
- Any provider fallback list (`anthropic_fallback_models`). Default: none.
- Goal Gravity engagement: whether Goal Gravity may leave lower-ranked signed missions dormant (it only orders them today), and which runtime is canonical (`greg/gravity.py` on the Body path or `egregore.GoalGravityLoop`, ADR-GOAL-GRAVITY-001).
- Persistent-outage policy: whether a capability that keeps timing out is re-classified as faulty after N strikes and re-formed, or always escalated (default: escalated).
- Merging DALEOBANKS #89 (measurement truth; merges cleanly, 416 pass) and its public-persona clause.
- Binding the Kernel grant into DALEOBANKS's publish seam, and any LIVE arming.
- VEPMC fixture exclusion: implemented as enforcement of the metric's own definition ("fixture results are never external VEPMC evidence"); the founder may confirm or regress it.

## 5. Completion map: BODY + ORGANS + MIND (executable evidence only)

Tier legend: **proven-sandbox** = exercised end to end by `test_one_machine.py` and re-derived by `scripts/verify_one_machine.py` (16/16 checks) on synthetic founder keys; **tested** = unit or integration tests only; **absent** = no code on this trunk. Nothing here is founder-accepted, live, or VEPMC (VEPMC = 0).

| Organ of the machine | Status | Evidence | Next residual |
|---|---|---|---|
| Founder authority (signed mission via inbox, interface detached) | proven-sandbox | appraisal `founder_signature_verified`, `arrived_via_inbox` | Alfonso's real key on the designated device |
| Goal Gravity selecting work | proven-sandbox (ordering) | `gravity.ranked` before the first action; verifier `selected_by_goal_gravity` | engagement (founder ruling); sensing feed |
| Mind (Competency Compiler, non-LLM, certified) | proven-sandbox | verifier re-derives the optimum by exhaustive search, no GREG import | founder-correction learning (Stage 9 shows capability reuse only) |
| Capability Genesis (deficit → construct → resume) | proven-sandbox | `deficit.opened` → `capability.state` → `deficit.resolved`; reuse after restart | #129 shadow trial, dossier/ratify, failure-pattern detector |
| Cause classification before repair | tested | `test_an_outage_is_not_a_capability_fault_and_opens_no_deficit` | persistent-outage policy (founder) |
| Organs (DALEOBANKS ↔ WealthMachine, separate processes) | proven-sandbox | live exchange; second-process reproduction; bound to a receipt; Landlock-confined | per-organ identity (pin upgrade); a non-same-code verifier |
| Hands (real worker, isolated clone, GREG-run acceptance) | proven-sandbox | patch digest, fresh-clone re-apply, its test re-run | OS confinement (#157, founder) |
| Interruption (real SIGKILL, reconciliation, no duplicate) | proven-sandbox | one receipted DONE commission; founder reconciliation recorded | — |
| Independent appraisal | proven-sandbox | separate-process `greg.appraisal` VERIFIED; verifier REDERIVED | a different machine or organization |
| Mission Control from runtime evidence | proven-sandbox | traces from ledger sequence; sandbox row distinct from VEPMC | founder-device rendering |
| Measurement truth (VEPMC) | tested | fixture exclusion; nine conditions unchanged | the first real closure (founder device, founder acceptance) |
| Compensation of executed effects | in progress | — | founder decision on uncompensable classes |
| Venture Cell lifecycle (dispute, refund, obligation) | absent on the mission path | rehearsal is fixture-only and now never counts | founder approval gate before sale; dispute/refund route |
| External consequence (Bridge C/D) | absent by authority | template constraint "nothing is sent, published, merged or paid" | founder-authorized bounded experiment |

## 6. Adversarial review of the trunk delta (2026-10-14, after d0355a4)

Seven review dimensions ran as separate agents over `b0b8907..d0355a4`: authority laundering, worker security, organ capability, engine semantics, model policy, verifier honesty and observability. Each finding names a concrete failure path. The skeptic-verification phase of that workflow was cut short by a session limit, so I verified every finding I fixed by reproducing it: each fix carries a test that fails on the code before it and passes after. The worker-security agent itself was stopped by a provider safeguard; the authority-laundering agent covered the same worker surface.

| Severity | Finding | Fix (commit) | Proving test |
|---|---|---|---|
| critical | An isolated child could replace `tools/offline_test.py` on disk; every later isolated child imported it at fork time and ran with full network while reporting isolation | The filter is loaded into the body's memory at import; children import nothing (`e6fae6d`) | `test_a_child_that_rewrites_the_network_filter_cannot_disable_isolation_for_later_children` (old code: `NETWORK OPEN`) |
| high | Worker test code run by GREG's acceptance could rewrite the clone's `.git` (gpg program, hooks) that GREG's own git then ran | `.git` digest re-checked after the restore and after acceptance; signing disabled (`14944f1`) | `test_attack_worker_test_code_rewrites_git_metadata_during_greg_acceptance` |
| high | Organ stages could write anywhere: DALEOBANKS could rewrite WealthMachine's code, so REPRODUCED proved nothing | Committed HEAD snapshots; Landlock confines each stage to its own code, interpreter and the store; WealthMachine snapshot digest re-checked (`e24efa2`, `8f772ad`) | `test_a_confined_organ_stage_reaches_only_its_code_and_the_store`, `test_an_organ_that_rewrites_the_other_organs_code_is_refused` |
| high | Fallback chains: spend bound covered one attempt; cost ignored refused attempts | Budget split across the chain; every `usage.iterations` entry booked (`19a28d4`) | `test_the_spend_bound_covers_every_attempt_of_the_fallback_chain` |
| high | Reconciling a function-named strategy wrote `capability: None`; resilience, routing knowledge and the morning tribunal raised `TypeError` | Capability copied from the reconciled dispatch; readers tolerate None (`ce7d04a`) | `test_reconciling_a_function_named_strategy_names_the_dispatched_capability` |
| high (pre-existing) | `reconcile_executed` booked $0 for a paid action; the budget gate admitted spend past the signed envelope | The signed cap is booked (`6d506ce`) | `test_a_paid_action_reconciled_as_executed_books_its_signed_cap_against_the_budget` |
| medium | Organ facts recorded before the Gate receipt satisfied `organ.status` even after `reconcile_not_executed` | `organ_bridge.bound_facts`: only facts a DONE receipt (or founder reconciliation) vouches for count (`e24efa2`) | `test_facts_from_an_exchange_that_never_completed_do_not_count` |
| medium | The worker was handed `CERTIFIED_PLAN_JSON` when the gate only required `state == ANSWERED` | The certified label is set only after the certificate; the gate requires it (`a073dea`) | `test_the_answered_gate_admits_only_a_certified_answer` |
| medium | The Kernel signed the re-derivation as DALEOBANKS's isolated identity when per-organ keys were configured | The re-derivation reuses DALEOBANKS's own signed message (`8f772ad`) | `test_live_exchange_never_signs_as_an_organ_when_per_organ_keys_are_configured` |
| medium | STOP could not end an organ exchange (up to 3 × 900 s); organ children outlived a killed body | Supervised stages, parent-death signal, one time bound (`8f772ad`) | `test_founder_stop_ends_an_in_flight_organ_exchange` |
| medium | Routing counted one interrupted dispatch twice; a receipt-less reconciliation counted as success | One outcome per attempt; `founder_reconciled` excluded from reliability (`ce7d04a`) | `test_routing_counts_one_outcome_per_attempt_*` |
| medium (pre-existing) | A binding silently fell back to an older receipt after a reconciled execution | `Unbound` / `BindingError` instead (`f4a8129`) | `test_a_signed_binding_never_falls_back_past_a_reconciled_execution` |
| medium | A withheld substituted answer's billed cost was never booked; billed build attempts without a candidate escaped the build budget | Booked on `ModelSubstitution` and `genesis.unbuilt` (`f58ed46`, `f3b4fab`) | `test_a_withheld_substitution_is_still_booked_against_the_budget`, `test_a_withheld_build_attempt_is_booked_against_the_signed_build_budget` |
| low (×12) | Appraisal identity collapse, trace not checked, missing-field "reproduced", contract validation absent, interpreter provenance, "no opportunity" booked as a fault, metric stages unbound, verifier passing on a skipped re-derivation, unknown served model reported as requested, config plumbing, Haiku long-prompt price, tribunal/SOP/critique handling of receipt-less reconciliations | `e24efa2`, `8f772ad`, `a073dea`, `19a28d4`, `aa5a7a5`, `ba0c0f5`, `02884c3` | listed in `tests/evidence/one-machine-20261014/adversarial-matrix.json` |

Not fixed, stated: a fallback attempt fed a declined attempt's partial text can exceed the per-attempt bound (the booked cost stays correct); refusals carry no cost; resilience still counts UNCERTAIN plus RECONCILED_NOT_EXECUTED as two failures; two strategies with identical params, target and cost share a proposal id (pre-existing); a worker daemon that outlives the worker can still race a check (no PID namespace until #157 confinement).

## 7. Gap map (seven investigators and a critic) and what was closed

| Rank | Gap | Status on this trunk |
|---|---|---|
| — | VEPMC counted a fixture rehearsal (critical, measurement truth) | **Closed** `8fb5ee7`: closures with fixture evidence never count; the nine conditions are unchanged |
| 1 | Genesis treated host outages as capability faults (quarantine, re-formation, budget) | **Closed** `4baff73`: failures typed where raised; only `executor_error` is evidence against a capability |
| 5 / Stage 2 | Nothing selected work on the mission path | **Closed (ordering)** `3e1043d`: Goal Gravity ranks the signed missions each tick, records each change, verifier re-derives it. Engagement of only the top candidate is founder-reserved |
| 3 | `daleobanks.outcome` reads an unverified organ file as institutional truth | In progress (separate branch, verified before merge) |
| Defect 12 | Ledger cannot tell which device class ran a closure | In progress (informational only; VEPMC unchanged) |
| 4 / Defect 7 | No compensation for executed effects of abandoned missions | In progress |
| 2 | Kernel grant never reaches DALEOBANKS's publish seam (metadata key mismatch; organ-local grant authority) | Open: cross-repository, and LIVE arming is founder-reserved |
| Defect 9 | DALEOBANKS rewards its own generated text (PR #89 fixes it, merges cleanly, 416 pass) | Founder-reserved: merging #89 |
| Defect 2 rest | #129 shadow trial, dossier/ratify, failure-pattern detector | Open: port only typed classes was the recommended slice (done) |

## 8. Rollback

Every change is a separate commit on `claude/greg-one-machine`. Reverting any one leaves the others intact; reverting the whole branch is deleting the branch. No data migration was introduced. The new event types `organ.observed` and `organ.appraised` are additive, and readers tolerate their absence.
