<!-- GENERATED FILE — DO NOT EDIT BY HAND -->
<!-- source: planning/graph/nodes/ via planning/compiler/render.py -->
<!-- graph-digest: c65a4d773a988a1c54da122175adc896c5bb2033a49f3813f0c4da5aadc3a36d -->
<!-- projection: WHOLE_SYSTEM_STRATEGIC_TREE -->


# Strategic Tree — Route Tournament and Two Strengthening Passes

Twelve routes: the eleven the brief names, plus one discovered from the measured
absence of any execution entrypoint. Hard gates were applied **before** scoring —
a branch that fails a gate is recorded with its reason and left unscored, so it
cannot be resurrected later on the strength of a number it never earned.

Exactly two strengthening passes, with all five deliberation roles present and
dissent preserved. There is no third pass.

**15 nodes** projected from graph digest `c65a4d773a988a1c`. Regenerate with `python planning/compiler/render.py`.

## strategy gate (1)

### `tree.hard_gates` — Hard gates applied before scoring

**Evidence:** `verified_by_inspection`
- `founder-upload` @ `1fd49e07437d` · → §12 hard gates

- **gates**:
  - violates Constitution or law
  - destroys evidence or branches
  - requires unavailable authority
  - cannot be tested before major cost
  - has no causal connection to the actual egregore
  - relies on impressive naming instead of mechanism
  - cannot beat or complement a conventional baseline
  - creates unbounded blast radius
  - makes the evaluator candidate-controlled
  - depends on a nonexistent external acceptance path with no bridge

## strategy branch (12)

### `route.01_pr66_first` — R1 — Complete PR #66 first

**Evidence:** `verified_by_inspection`
- `dababiyoda/uniimente-kernel` @ `a6f14d344f2c` · path `verification/phase3g/REPAIR_AUTHORITY_DESIGN_A_FALSIFIED.md`

- **causal_mechanism**: Finish the legacy/canonical repair decoupling, then resume the whole-system program from a clean lifecycle.
- **first_wedge**: Adopt design family B+D; separate ledger bookkeeping from retirement authority.
- **time_to_proof**: unknown — three designs already falsified by measurement (A, E, H); two more (LC-2b, LC-2b') falsified before them
- **capital_need**: none
- **founder_attention**: low
- **commercial_value**: none
- **knowledge_value**: high
- **reversibility**: high
- **strongest_counterexample**: The branch's own body records that the conventional durable workflow engine still wins on available evidence, and that none of this work is evidence about that comparison. Completing it therefore cannot establish the thing it exists to establish; only R8 can, and R8 is prohibited until a freeze that keeps receding.
- **fatal_risk**: Five falsified designs in one workstream is a strong prior that the sixth is also wrong; meanwhile 0 bridges close.
- **hard_gate_result**: PASSES_BUT_SCORES_LOW
- **score**: 3
- **disposition**: FREEZE_AS_TRACK_B_RESEARCH

_Relates to: `pr.kernel.66`, `pr.kernel.66.dissent`, `pr.kernel.66.latest_finding`_

### `route.02_phase_zero_first` — R2 — Whole-system Phase Zero reconciliation first

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `8cb3074a4a83` · path `docs/PHASE_ZERO_REPORT.md`

- **causal_mechanism**: Write the two missing organ manifests, wire the adapters, close Bridge A end to end, record one causal episode.
- **first_wedge**: organs/pumpstation.manifest.yaml + organs/research-in.manifest.yaml, then wire adapters/ into a real path.
- **time_to_proof**: days — the parts exist and the linker already reports exactly what is missing
- **capital_need**: none
- **founder_attention**: low
- **commercial_value**: indirect
- **knowledge_value**: medium
- **reversibility**: high
- **strongest_counterexample**: Phase Zero was already declared complete once (docs/PHASE_ZERO_REPORT.md, 2026-07-20) and the organism still has zero closed bridges. Repeating it risks producing a second report rather than a second outcome.
- **attack_survived**: The 2026-07-20 report is honest about what it built and what it did not; the gap is that its adapters were never wired into an executing path. That is a different, smaller task than "redo Phase Zero".
- **hard_gate_result**: PASSES
- **score**: 7
- **disposition**: RETAIN_AS_SUPPORTING_TRACK

_Relates to: `bridge.linker_measured_state`, `bridge.two_organs_invisible`, `capability.adapters_membrane_orphaned`_

### `route.03_track_a_organogenesis` — R3 — Conventional Track A developmental organogenesis first

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `8cb3074a4a83` · path `evolution/repair/spec.py`

- **causal_mechanism**: Disable a real institutional capability, have AI builders generate materially different replacements in isolation, judge them with a frozen evaluator the candidates cannot alter, attach the winner in a consequence-inert registry, verify restoration, preserve lineage and rollback.
- **first_wedge**: institutional.cross_organ_edge_resolution — the target is already declared in evolution/repair/spec.py, the subject (linker/) is already hashed file-by-file, the threshold is already 4/4, and the spec already self-seals via SPEC_SHA256.
- **time_to_proof**: short — the laboratory exists; the missing pieces are process isolation and held-out confinement
- **capital_need**: none
- **founder_attention**: low
- **external_dependencies**: NONE
- **commercial_value**: none_directly
- **knowledge_value**: very_high
- **durable_assets**: a working developmental engine; the first Capability Genome; a reusable evaluator firewall
- **reversibility**: high
- **strongest_counterexample**: It restores a capability whose output nothing consumes. A successful closure proves the BRIDGE region works while the RIGHT region stays inert — precisely the recursive self-deception Override §26 names as the greatest strategic risk.
- **attack_survived**: The objection is real and is answered by labelling, not by argument: this is COMPUTATIONAL closure and must be recorded as such on the §11 ladder. It may never be reported as institutional or economic closure. With that label it is still the only 0→1 proof reachable with zero external dependencies.
- **hard_gate_result**: PASSES
- **score**: 9
- **disposition**: RETAIN_AS_PRIMARY

_Relates to: `capability.evolution_laboratory`, `capability.evaluator_firewall_partially_exists`, `intent.first_developmental_proof`, `intent.closure_ladder`_

### `route.04_proof_to_settlement_first` — R4 — Proof-to-settlement / first paid external outcome first

**Evidence:** `verified_by_inspection`
- `dababiyoda/uniimente-kernel` @ `7a7846559f23` · → PR #53 title: IVIO excluded, C9 recommended (PLAN ONLY)

- **causal_mechanism**: Drive one real transaction to acceptance, payment and reconciliation.
- **first_wedge**: IVIO-NEMT was the presumed wedge.
- **hard_gate_result**: BLOCKED_ON_EXTERNAL_AUTHORITY
- **blocking_evidence**: IVIO-NEMT is not reachable from this session and was never inspected, so no claim about it may be made. Separately, Kernel PR #53 records an earlier evidence-based venture-selection round that EXCLUDED IVIO and recommended an alternative labelled C9. Economic closure additionally requires a named buyer, legal operator, payment account and customer consent — every one of which is a founder-supplied blocker no build session can create.
- **score**: not_scored_hard_gate
- **disposition**: DEFER_PENDING_FOUNDER_DECISION
- **preserved_because**: Economic closure remains the highest-value tier on the ladder; only its route is deferred, not the aspiration.

_Relates to: `repo.unavailable.ivio_nemt`, `pr.kernel.53.ivio_excluded`, `intent.closure_ladder`_

### `route.05_daleobanks_cash_engine` — R5 — DALEOBANKS cash-and-distribution engine first

**Evidence:** `verified_by_inspection`
- `dababiyoda/DALEOBANKS` @ `1ba3b85474af` · → PR #66 'Shadow-mode publication governed by the Reality Aperture (zero real publications)'

- **causal_mechanism**: Publish truthfully, build an owned audience, convert attention into revenue, and use that cash to fund UNIIMENTE development.
- **first_wedge**: shadow-mode publication (DALEOBANKS PR #66) promoted to real publication.
- **time_to_proof**: weeks to months — audience building is slow and cannot be compressed by engineering
- **capital_need**: low
- **founder_attention**: HIGH — brand voice and public risk are founder-reserved
- **commercial_value**: highest_of_any_route
- **knowledge_value**: medium
- **strongest_counterexample**: Requires live platform credentials and the founder's public identity, both of which are explicitly outside this round's authority. The linker already lists "live platform credentials (X/LinkedIn/Mastodon) are external dependencies" as an unresolved field.
- **hard_gate_result**: BLOCKED_ON_EXTERNAL_AUTHORITY
- **score**: not_scored_hard_gate
- **disposition**: DEFER_PENDING_FOUNDER_DECISION
- **strategic_note**: Override §18 states the sequencing consequence directly: a strong system that cannot finance itself remains fragile. This route is deferred on authority, not on merit, and it should be the FIRST thing unblocked when the founder is ready to make a publishing decision. It is the highest-value blocked route.

_Relates to: `intent.daleobanks_role`, `repo.daleobanks`_

### `route.06_golden_kernel_v2` — R6 — Golden Kernel v2 / Reality Covenant first

**Evidence:** `derived`
- _no evidence reference — this node is explicitly unresolved_

- **causal_mechanism**: Rebuild the authority core before anything else consumes it.
- **strongest_counterexample**: The authority core is not the bottleneck. The CI authority-singleton guard passes, the linker reports containment, and the measured problem is that NOTHING CONSUMES the authority that already exists — eleven kernel-produced contracts have zero consumers. Rebuilding an unconsumed authority core produces a better-designed unconsumed authority core.
- **hard_gate_result**: FAILS — no causal connection to the measured bottleneck
- **score**: not_scored_hard_gate
- **disposition**: DEFER

_Relates to: `bridge.linker_measured_state`, `authority.overlaps_measured`_

### `route.07_wmi_first` — R7 — WMI opportunity and portfolio intelligence first

**Evidence:** `derived`
- _no evidence reference — this node is explicitly unresolved_

- **causal_mechanism**: Sharpen commercial cognition so the first venture choice is better.
- **strongest_counterexample**: WMI already has 13 open PRs, six of them stacked on other feature branches rather than main. Adding analysis capacity to an organ that cannot land its existing analysis capacity increases the backlog without increasing throughput.
- **hard_gate_result**: PASSES_BUT_SCORES_LOW
- **score**: 4
- **disposition**: DEFER

_Relates to: `discrepancy.stacked_pr_backlog`, `pr.wmi.30`_

### `route.08_pumpstation_first` — R8route — PumpStation participation economy first

**Evidence:** `derived`
- _no evidence reference — this node is explicitly unresolved_

- **causal_mechanism**: Ship the testnet end-to-end funded job transaction.
- **strongest_counterexample**: PumpStation main is still the older memecoin/wallet application; the regenerative-OS doctrine exists only in unmerged branches, and the repo has no organ manifest, so it is invisible to the linker. It is the least-connected organ being proposed for the most externally-exposed work.
- **regulatory_risk**: high — escrow, settlement and any token surface attract real regulation
- **hard_gate_result**: PASSES_BUT_SCORES_LOW
- **score**: 3
- **disposition**: DEFER

_Relates to: `repo.pumpstation`, `bridge.two_organs_invisible`, `intent.pumpstation_role`_

### `route.09_morphogenetic_substrate` — R9 — Morphogenetic substrate / MICA / CDPE first

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `8cb3074a4a83` · path `docs/developmental/TARGET_FORM_002_SPEC.md`

- **causal_mechanism**: Make the local-competency substrate the foundation of developmental capability.
- **strongest_counterexample**: Measured: morphogenesis/ imports nothing and is imported by nothing (2 test references); developmental/ has 1 test reference and one importer. TARGET_FORM_002 already recorded that recovery degrades monotonically with degree heterogeneity and reaches ZERO on hub-heavy topology. Override §9 forbids Track B gating Track A, and this route is that gating by construction.
- **hard_gate_result**: FAILS — cannot currently beat the conventional baseline, and its own benchmark says so
- **score**: not_scored_hard_gate
- **disposition**: RETAIN_AS_RESEARCH_CHALLENGER
- **preserved_because**: Override §9 also forbids abandoning Track B because conventional mechanisms win today. It stays a registered challenger with a defined re-entry condition, not a deletion.

_Relates to: `capability.morphogenesis_orphaned`, `capability.developmental_mica_cdpe`, `intent.track_a_track_b`_

### `route.10_do_nothing` — R10 — Minimal maintenance / wait for better models

**Evidence:** `derived`
- _no evidence reference — this node is explicitly unresolved_

- **causal_mechanism**: Hold position; let frontier capability improve; spend nothing.
- **genuine_merits**: Costs nothing, risks nothing, destroys nothing, and the 69-PR backlog would stop growing. If the institution's real constraint is founder attention rather than engineering capability, this dominates every build route.
- **strongest_counterexample**: Zero external outcomes is already the status quo after months of work. Waiting produces a larger unlanded backlog and an older stale-base problem, and every calibration constant stays uncalibrated. Model improvement does not close a bridge that no process is running.
- **hard_gate_result**: PASSES
- **score**: 2
- **disposition**: REJECTED_BUT_RECORDED
- **role**: Retained as the mandatory do-nothing baseline every other route must beat.

_Relates to: `decision.controlling_fact`, `discrepancy.stacked_pr_backlog`_

### `route.11_execution_surface_first` — R11 — DISCOVERED: build the execution surface, not more components

**Evidence:** `derived`
- _no evidence reference — this node is explicitly unresolved_

- **origin**: Not in the prompt's list. Generated from the measured absence of any entrypoint.
- **causal_mechanism**: The measured gap is not components but a process that runs. Build the smallest possible governed execution surface — one loop that takes a real input, crosses the Consequence Gate, produces a receipt and reconciles — and let existing components attach to it.
- **strongest_counterexample**: Without a real external target, the "execution surface" is a loop over fixtures, which is a test harness with a grander name. It collapses into R3 unless it has a genuine consequence to carry, and R4/R5 (which supply real consequences) are both blocked on founder authority.
- **hard_gate_result**: PASSES
- **score**: 6
- **disposition**: MERGED_INTO_PRIMARY
- **merge_note**: Its true content — "prefer the thing that executes over the thing that is merely well-formed" — is adopted as a constraint on R3 rather than as a separate route: the developmental closure must run as an actual process with a recorded run, not as a passing test.

_Relates to: `anatomy.kernel_is_a_library_not_a_running_system`_

### `route.12_portfolio` — R12 — Staged portfolio with unequal tracks (RECOMBINED)

**Evidence:** `derived`
- _no evidence reference — this node is explicitly unresolved_

- **construction**: R3 primary, constrained by R11, supported by R2, with R5 held as the first route to unblock.
- **causal_mechanism**: Run one unblocked engineering bottleneck to a real 0→1 proof while the founder-blocked commercial route waits on a decision only the founder can make. Neither waits for the other.
- **why_a_portfolio_rather_than_one_winner**: The two highest-value routes fail for opposite reasons: R5 is blocked on authority, not merit; R3 is unblocked but proves only the lowest tier of the closure ladder. Choosing either alone discards real value. The prompt permits a staged portfolio and forbids manufacturing a single winner.
- **score**: 10
- **disposition**: SELECTED

_Relates to: `route.03_track_a_organogenesis`, `route.02_phase_zero_first`, `route.05_daleobanks_cash_engine`, `route.11_execution_surface_first`_

## strengthening pass (2)

### `deliberation.pass1` — Pass 1 — steelman, amplify, redesign disadvantages

**Evidence:** `derived`
- _no evidence reference — this node is explicitly unresolved_

- **pass_number**: 1
- **subject**: route.12_portfolio
- **roles_present**:
  - **founder_intent_steward**: The portfolio preserves the full horizon. Nothing is deleted; R4, R5, R7, R8 and R9 are deferred with named re-entry conditions, satisfying Override §2 and §28. The primary track advances the §10 milestone directly.
  - **systems_architect**: R3 is the only route whose dependencies are entirely inside the repository. Its laboratory exists: frozen spec, hashed subject files, a 4/4 threshold, a detector told only the capability name. The engineering delta is process isolation and held-out confinement, not new architecture.
  - **adversarial_reviewer**: A computational closure over a capability nobody consumes is exactly the elegant-progress-without-reality failure §26 warns about. If this round recommends it without labelling the tier, it manufactures the deception it was convened to prevent.
  - **operator_maintainer**: 69 open PRs, four based on an archived main. Any new work must land, not queue. A route that adds a 70th unlandable PR is worse than doing nothing.
  - **evidence_welfare_guardian**: Zero external effects, zero participants, zero data subjects in the primary track. Welfare risk is nil precisely because nothing touches anyone — which is also the reason it cannot claim institutional or economic value.
- **baseline_comparison**: Do-nothing (R10) scores 2 and is beaten on knowledge value and on stopping backlog growth.
- **simplest_viable_alternative**: Write the two missing organ manifests and stop (a slice of R2). Cheaper, but produces no closure of any tier and leaves the developmental engine unproven.
- **strongest_competing_architecture**: R5 (DALEOBANKS cash engine) genuinely dominates on commercial value and is the only route that addresses the fragility Override §18 names. It loses here only because it needs a founder authority this round cannot grant.
- **disadvantages_identified**:
  - - **D1**: computational closure risks being read as real progress
  - - **D2**: the target capability's output has no consumer
  - - **D3**: adds to a 69-PR backlog that already cannot drain
  - - **D4**: the evaluator is not yet process-isolated, so "candidates cannot alter it" is not fully true
  - - **D5**: primary track produces no revenue while §18 says financing fragility is real
- **redesigns_applied**:
  - D1 → every closure claim must carry its §11 ladder tier in the artifact itself; 'computational' may never be reported unqualified.
  - D2 → accepted and stated openly rather than engineered away; the closure proves the BRIDGE region, and the artifact says so.
  - D3 → the implementation program is a dependency-ordered stack against current main, never onto an archived base, and PR count is capped.
  - D4 → process isolation and held-out confinement become entry conditions for the closure, not follow-ups.
  - D5 → R5 is designated first-to-unblock and its founder gate is written now, so the decision is ready the moment the founder is.
- **reversible_experiment**: The closure runs in a sandbox against a disabled copy; the original linker is hash-pinned and untouched; rollback is deleting a branch.
- **rejected_alternatives_preserved**:
  - route.01_pr66_first
  - route.06_golden_kernel_v2
  - route.07_wmi_first
  - route.08_pumpstation_first
  - route.09_morphogenetic_substrate
  - route.10_do_nothing

_Relates to: `route.12_portfolio`, `route.03_track_a_organogenesis`, `route.05_daleobanks_cash_engine`, `decision.controlling_fact`_

### `deliberation.pass2` — Pass 2 — attack the strengthened design, then settle

**Evidence:** `derived`
- _no evidence reference — this node is explicitly unresolved_

- **pass_number**: 2
- **subject**: route.12_portfolio
- **attacks**:
  - **bureaucracy**: The planning compiler could become the institution's fourth registry system. Override §27 anticipates this and requires a disposition; one is returned.
  - **centralization**: None added — the round creates no authority and no gate.
  - **fragility**: The portfolio depends on the founder eventually unblocking R5. If that never happens, UNIIMENTE accumulates developmental capability it cannot finance. This is a real, unresolved dependency and is recorded as such rather than assumed away.
  - **overfit**: Tuning the developmental engine to one capability (cross_organ_edge_resolution) risks an engine that only repairs that. Mitigation: the second closure must target an unrelated function, and that requirement is written into the exit criteria rather than left to judgement.
  - **cost**: Near zero — no credentials, no spend, no external surface.
  - **incomprehensibility**: Genuine risk. The kernel already has 22 packages and five registries. The program adds no new package to the runtime.
  - **irreversibility**: None. Every artifact is a branch; every attachment is consequence-inert and detachable.
  - **gaming**: The sharpest attack: a builder that can read the evaluator can satisfy it without solving anything. This is why D4's fix is an entry condition and not a follow-up — without isolation the whole closure is worthless.
  - **dependency**: No new provider, platform or vendor dependency.
  - **theater**: The strongest attack of all. The honest answer is that a computational closure IS a small result, and the round says so in those words rather than dressing it as institutional progress.
- **pass1_disadvantages_revisited**:
  - **D1**: Addressed — ladder tier is now mandatory in every closure artifact.
  - **D2**: Not fixable; stated openly. The capability's output has no consumer and the closure proves the BRIDGE only.
  - **D3**: Addressed — stack ordering rule and PR cap; stale-base PRs are triaged before new ones are opened.
  - **D4**: Promoted from follow-up to entry condition. Without isolation, do not run the experiment.
  - **D5**: Unresolved by engineering. Escalated as the round's primary founder decision.
- **residual_risks**:
  - The founder may never unblock R5, leaving capability without financing.
  - The developmental engine may succeed on one capability and generalize to none.
  - The 69-PR backlog may absorb this work as it absorbed the rest.
  - PR #66's five falsified designs may indicate the underlying lifecycle model is wrong, which freezing does not resolve.
- **rollback**: Delete the planning branch. main is untouched at 8cb3074 throughout.
- **disposition**: RETAIN
- **note**: Exactly two passes. No third pass was run.

_Relates to: `deliberation.pass1`, `route.12_portfolio`, `capability.evaluator_firewall_partially_exists`, `discrepancy.stacked_pr_backlog`_
