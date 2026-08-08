<!-- GENERATED FILE — DO NOT EDIT BY HAND -->
<!-- source: planning/graph/nodes/ via planning/compiler/render.py -->
<!-- graph-digest: c355a9a137b04ff3b0b5aaa4df60fa574dfe0d8d49242bdf0402bcfa124f14a8 -->
<!-- projection: INSPECTION_TRUTH -->


# SP-0 — Inspection Truth Freeze

Measured 2026-08-08 against live repositories and the GitHub API. This is the
frozen evidence base for the whole round: **no recommendations appear here.**

Where the canonical prompt and the repositories disagree, both readings are
recorded and the disagreement is itself a node. Sources that could not be
reached are listed as unavailable and may never be cited as evidence — a
mechanical check (`unavailable_sources_not_cited_as_evidence`) enforces this
rather than trusting the author.

**27 nodes** projected from graph digest `c355a9a137b04ff3`. Regenerate with `python planning/compiler/render.py`.

## repository (6)

### `repo.build-your-own-x` — dababiyoda/build-your-own-x — read-only mechanism anatomy atlas

**Evidence:** `verified_by_execution`
- `dababiyoda/build-your-own-x` @ `aa17439b62f3` · via `git rev-parse HEAD`

- **region**: LEFT
- **lifecycle_role**: HISTORICAL
- **default_branch**: master
- **head**: aa17439b62f384511a5561ce308e9598b94d8989
- **write_policy**: FORBIDDEN — read-only for this assignment

_Relates to: `intent.byox.mechanism_atlas`_

### `repo.daleobanks` — dababiyoda/DALEOBANKS — perception, media, distribution, early cash engine

**Evidence:** `verified_by_execution`
- `dababiyoda/DALEOBANKS` @ `1ba3b85474af` · via `git rev-parse HEAD; git ls-remote --heads origin | wc -l`

- **region**: RIGHT
- **default_branch**: main
- **head**: 1ba3b85474af60c1c0b1f34159f464cf69011e18
- **remote_branches**: 51
- **open_prs**: 9
- **github_description_is_stale**: yes
- **stale_description_note**: The GitHub repo description still reads "a production-grade, self-evolving AI agent that operates on Twitter/X" — materially narrower than Override §18, which defines DALEOBANKS as a global multilingual lifestyle brand, media network and primary early cash engine. Recorded as a discrepancy, not resolved by this round (changing it is an outward-facing write).

_Relates to: `intent.daleobanks_role`_

### `repo.pumpstation` — dababiyoda/PumpStation — regenerative social-economic OS (Venture Cell)

**Evidence:** `verified_by_execution`
- `dababiyoda/PumpStation` @ `df6a732f4441` · via `git rev-parse HEAD; git log --oneline -2`

- **region**: RIGHT
- **default_branch**: main
- **head**: df6a732f44412c626098ee9591b9d19f420d02dd
- **remote_branches**: 11
- **open_prs**: 10
- **presence**: existing_but_disconnected
- **github_description_is_stale**: yes
- **stale_description_note**: Repo description still describes "a real-time, decentralized memecoin coordination platform". Override §20 explicitly supersedes this. main itself is still the older memecoin/wallet application — the newer doctrine lives only in unmerged branches. This is the §28 named conflict, recorded on both sides.

_Relates to: `intent.pumpstation_role`, `intent.supersession_matrix`_

### `repo.research-in` — dababiyoda/RESEARCH-IN — open research hub (sixth organ, role underived)

**Evidence:** `verified_by_execution`
- `dababiyoda/RESEARCH-IN` @ `576913809432` · via `git rev-parse HEAD; list_pull_requests(state=open)`

- **region**: RIGHT
- **default_branch**: main
- **head**: 576913809432fc1dd47a245a14184988607e27eb
- **remote_branches**: 23
- **open_prs**: 11
- **presence**: existing_but_disconnected
- **stated_purpose**: Per its GitHub description: a free global hub that ingests serious PDFs, datasets, hypotheses and experiments and makes them searchable, discussable and remixable, so no human re-does solved work.
- **role_status**: UNRESOLVED
- **role_note**: Override §21 forbids inventing this organ's role. Evidence so far establishes the product (research ingestion/search) but NOT its institutional role, owner, authority, or interfaces. All eleven open PRs are codex/* from 2025-06 based on main @ 30c099f9 — an ancestor of the current head — so the open-PR surface is roughly fourteen months stale and does not describe current intent.

_Relates to: `intent.research_in_role`_

### `repo.uniimente-kernel` — dababiyoda/uniimente-kernel — constitutional Kernel

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `8cb3074a4a83` · via `git rev-parse HEAD; python -m pytest -q -p no:randomly` · (release commit 'UNIIMENTE canonical-v1 Kernel release')

- **region**: CENTER
- **default_branch**: main
- **head**: 8cb3074a4a837c89aada9bdb5351d7d9b3e4a9c1
- **remote_branches**: 65
- **open_prs**: 26
- **role**: constitutional law, authority, proof, identity, governance, institutional memory, capability composition, evolution, continuity
- **baseline_suite**: 495 passed in 6.22s (Python 3.11.15)

_Relates to: `intent.topology.three_region`, `intent.golden_kernel_cockpit`_

### `repo.wealthmachineintelligence` — dababiyoda/WealthMachineIntelligence — commercial and strategic cognition

**Evidence:** `verified_by_execution`
- `dababiyoda/WealthMachineIntelligence` @ `6549984a22a1` · via `git rev-parse HEAD; git ls-remote --heads origin | wc -l`

- **region**: RIGHT
- **default_branch**: main
- **head**: 6549984a22a171f68b268b775f19192aee599609
- **remote_branches**: 34
- **open_prs**: 13

_Relates to: `intent.wmi_role`_

## repository unavailable (3)

### `repo.unavailable.chario_obvio` — CHARIO / OBVIO — named in the prompt, not reachable this session

**Evidence:** `unresolved`
- _no evidence reference — this node is explicitly unresolved_

- **reason**: Repository discovery denied; not in session scope; never inspected.

### `repo.unavailable.ivio_nemt` — IVIO-NEMT — named in the prompt, not reachable this session

**Evidence:** `unresolved`
- _no evidence reference — this node is explicitly unresolved_

- **reason**: Repository discovery was attempted via the claude-code-remote list_repos tool and the call was denied in this session. The repository is not attached to the session scope and was never inspected. Per prompt §8.6, absence of inspection is recorded rather than substituted with inference.
- **do_not_claim**: No file, commit, test or capability of IVIO-NEMT may be cited by this round.
- **partial_substitute**: Kernel-side IVIO artifacts DO exist and were inspected: PR #45 (build/ivio-v1-contracts, 1b52a7a7) adds IVIO v1 proof-to-settlement contracts and a compiler; PR #53 (strategy/cvo-001-venture-selection, 7a784655) records a venture-selection decision titled "IVIO excluded, C9 recommended (PLAN ONLY)". These are Kernel claims about IVIO, not evidence from the IVIO repository.

### `repo.unavailable.tgh_control_rail` — TGH-CONTROL-RAIL — named in the prompt, not reachable this session

**Evidence:** `unresolved`
- _no evidence reference — this node is explicitly unresolved_

- **reason**: Repository discovery denied; not in session scope; never inspected.

## source unavailable (1)

### `source.unavailable.founder_briefs` — Three referenced briefs absent from the workspace

**Evidence:** `unresolved`
- _no evidence reference — this node is explicitly unresolved_

- **missing**:
  - Branch · Egregore and UNIIMENTE System.txt
  - Proof to Settlement Egregore.pdf
  - Branch · Continue Egregore Work.txt
- **reason**: Cited in founder messages but never present on disk in this session. A filesystem search across the workspace returned nothing.
- **reconstruction_route**: Kernel branch agent/proof-to-settlement-trust-rail (e09c2088, PR #35 "Add the OpenClaw proof-to-settlement trust rail"), docs/EGREGORE_V1_INTEGRATION_PROGRAM.md on main, and the integration/* branches. Anything not reconstructable from those stays an explicit unresolved field.

## pull request (5)

### `pr.daleobanks.65` — DALEOBANKS PR #65 — canonical lifestyle brand and founder-intent lineage

**Evidence:** `verified_by_execution`
- `dababiyoda/DALEOBANKS` @ `2394127f6036` · via `list_pull_requests(state=open)`

- **repo**: dababiyoda/DALEOBANKS
- **number**: 65
- **branch**: agent/canonical-media-brand-architecture
- **head**: 2394127f603636da789a30c765ad756d58a7a82f
- **base_sha**: 1ba3b85474af60c1c0b1f34159f464cf69011e18
- **state**: open
- **draft**: yes
- **scope**: documentation-only founder-intent consolidation
- **status_note**: High-priority founder-intent source. NOT merged runtime truth.

_Relates to: `intent.daleobanks_role`_

### `pr.kernel.53.ivio_excluded` — Kernel PR #53 — CVO-001 venture selection: IVIO excluded, C9 recommended (PLAN ONLY)

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `7a7846559f23` · via `list_pull_requests(state=open)`

- **repo**: dababiyoda/uniimente-kernel
- **number**: 53
- **branch**: strategy/cvo-001-venture-selection
- **head**: 7a7846559f23682983898975ba89174a99c50c10
- **state**: open
- **draft**: yes
- **significance**: A prior venture-selection round already EXCLUDED IVIO and recommended an alternative labelled C9. The canonical prompt §24 asks whether IVIO-NEMT remains the strongest first economic wedge and says not to assume it. This PR is direct repository evidence that an earlier evidence-based pass answered "no". Its reasoning must be read before the economic-closure decision, and the IVIO repository itself is unavailable to check the other side.

_Relates to: `repo.unavailable.ivio_nemt`_

### `pr.kernel.66` — PR #66 — Phase 3G: author-direction classification + canonical decision authority

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `a6f14d344f2c` · via `pull_request_read(get); pull_request_read(get_check_runs); git rev-list --count main..origin/claude/uniimente-repo-audit-jpytcy`

- **repo**: dababiyoda/uniimente-kernel
- **number**: 66
- **branch**: claude/uniimente-repo-audit-jpytcy
- **head**: a6f14d344f2ca073fd334a885e5c2bdb921d082e
- **base_ref**: main
- **base_sha**: 8cb3074a4a837c89aada9bdb5351d7d9b3e4a9c1
- **state**: open
- **draft**: yes
- **merged**: no
- **mergeable_state**: clean
- **commits**: 133
- **changed_files**: 240
- **additions**: 145317
- **deletions**: 2
- **comments**: 9
- **created_at**: 2026-07-31T11:52:25Z
- **updated_at**: 2026-08-08T06:47:36Z
- **checks**: 5/5 success
- **check_names**:
  - 1 · Kernel and organ tests
  - 2 · Contract schema references resolve
  - 3 · One source of authority
  - 4 · Developmental work stays sealed
  - ancestry
- **suite_local**: 924 passed · 1 skipped · 24 xfailed · 0 failed
- **suite_ci_merge_ref**: 922 passed · 3 skipped · 24 xfailed · 0 failed
- **suite_note**: The two compositions differ because CI runs on the merge ref and the Git-ancestry pre-registration checks skip under a shallow checkout. They are recorded separately and must never be collapsed into one number.
- **gate_f**: UNMEASURED
- **gate_g**: UNMEASURED
- **r8**: NOT_RUN
- **r8_eligibility**: NOT_ELIGIBLE
- **write_policy**: ZERO_WRITES — founder-directed for this round

_Relates to: `intent.track_a_track_b`, `intent.round_authority`_

### `pr.pumpstation.16` — PumpStation PR #16 — SIWE wallet auth fix + executable admission gate

**Evidence:** `verified_by_execution`
- `dababiyoda/PumpStation` @ `618d49e20435` · via `list_pull_requests(state=open)`

- **repo**: dababiyoda/PumpStation
- **number**: 16
- **branch**: claude/uniimente-system-design-hczheq
- **head**: 618d49e20435c03f6adde6e6401983ca94712f5a
- **base_sha**: df6a732f44412c626098ee9591b9d19f420d02dd
- **state**: open
- **draft**: yes
- **note**: Substrate, not the whole final product. No treasury, token, DeFi or real-value operation authorized.

_Relates to: `intent.pumpstation_role`_

### `pr.wmi.30` — WMI PR #30 — Constitutional Control Layer (Phase 0 doctrine foundation)

**Evidence:** `verified_by_execution`
- `dababiyoda/WealthMachineIntelligence` @ `14e7bba896e6` · via `list_pull_requests(state=open)  ->  head confirmed, prompt value matched`

- **repo**: dababiyoda/WealthMachineIntelligence
- **number**: 30
- **branch**: claude/wmi-doctrine-roadmap-vfcrh0
- **head**: 14e7bba896e60f31c6dc5885a477ff7e100d64c6
- **base_sha**: 6549984a22a171f68b268b775f19192aee599609
- **state**: open
- **draft**: yes
- **authority_risk**: Titled a "Constitutional Control Layer" inside a non-Kernel organ. Override §19 forbids WMI becoming a parallel Constitution, authority root, identity root or Consequence Gate. Classification required in SP-2 — preserve the mechanisms, refuse the authority.
- **disposition_candidates**:
  - adapter_to_kernel
  - specialist_implementation
  - test_oracle
  - historical_donor
  - local_organ_control_beneath_kernel
  - prohibited_duplicate_authority

_Relates to: `intent.wmi_role`_

## finding (5)

### `anatomy.kernel_is_a_library_not_a_running_system` — The Kernel is a governed component library plus benchmark harnesses — there is no running institution

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `8cb3074a4a83` · via `find . -name __main__.py; ls .github/workflows; ast import analysis over 22 packages`

- **measurement**:
  - **python_packages**: 22
  - **total_entrypoints**: 3
  - **entrypoints**:
    - developmental/__main__.py — TARGET_FORM_001 benchmark runner
    - evolution/migration/__main__.py — migration experiment runner
    - evolution/repair/__main__.py — repair experiment runner
  - **servers_or_daemons**: 0
  - **operating_loops**: 0
  - **external_effect_paths_exercised**: 0
  - **ci_jobs**: 4
- **statement**: There is no server, no daemon, no scheduler and no operating loop anywhere in the Kernel. What exists is a well-tested library of institutional components, three experiment runners, and four CI guards (full suite + institutional verifier, contract $ref resolution, authority singleton, sealed developmental work). This is not a criticism — it is the precise reason nothing has ever reached reality, and it makes the strategic question tractable.
- **consequence**: "Connect the organism" cannot mean wiring more modules to each other. Nothing is running to be connected. The missing element is an execution surface that carries a real input to a real consequence, not more components.

_Relates to: `repo.uniimente-kernel`, `intent.anti_self_deception`_

### `capability.genuinely_absent` — What is genuinely absent, after classification

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `8cb3074a4a83` · via `ast import analysis across 22 packages; linker edge report; find -name __main__.py`

- **statement**: After classifying all 22 packages by import connectivity, very little of the prompt's "expected missing machinery" is actually absent. The genuine gaps are narrower and more specific than the brief anticipated.
- **genuinely_absent**:
  - an execution surface: any loop, service or scheduled process that carries an input to a consequence
  - organ manifests for PumpStation and RESEARCH-IN (2 of 6 organs are invisible to the linker)
  - builder/evaluator process isolation and held-out case confinement
  - a capability router selecting among competing implementations at runtime
  - any external-effect path that has ever been exercised (0 verified outcomes)
- **already_exists_contrary_to_brief**:
  - Whole-Body Closure Controller — closure/whole_body.py, most-connected module
  - Capability registry — five registries under closure/
  - Universal Compatibility Membrane — adapters/ (built, unwired)
  - Institutional Linker — linker/, executable, produces real edge reports
  - Institutional compiler — compiler/, imported by closure/evolution/policy
  - Mechanism/strategy tooling — evolution/strategy_tree.py, evolution/spider_web.py
  - Developmental compiler + candidate builders — evolution/repair/, evolution/migration/
  - Protected evaluator — evolution/repair/spec.py frozen-spec mechanism
  - OMNIMORPH composition — omnimorph/engine.py, imported by closure and foundry
  - Asymmetric Advantage Foundry — foundry/ (12 modules, 20 test refs)

_Relates to: `discrepancy.missing_machinery_premise`, `anatomy.kernel_is_a_library_not_a_running_system`_

### `decision.controlling_fact` — The controlling fact — nothing has ever crossed into reality

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `8cb3074a4a83` · path `docs/release/canonical-v1/00-README.md` · via `linker report; find -name __main__.py; pytest`

- **statement**: Across six repositories, 184 branches, 69 open pull requests and 517 passing tests, the number of externally verified consequences is zero. Not low — zero. The canonical-v1 release record states it, the linker confirms no organ consumes a kernel grant, and there is no server, daemon or loop that could produce one.
- **why_this_orders_everything**: Every autonomy threshold, evidence gate, routing weight and calibration constant in the system is uncalibrated theory until one loop closes against something outside the repository. That makes "which loop can close first, with the fewest external dependencies" the only question whose answer changes what to build tomorrow.

_Relates to: `anatomy.kernel_is_a_library_not_a_running_system`, `bridge.status_a_through_h`_

### `pr.kernel.66.dissent` — Preserved dissent: the conventional durable workflow engine still wins

**Evidence:** `verified_by_inspection`
- `dababiyoda/uniimente-kernel` @ `a6f14d344f2c` · → PR #66 body, section 'Dissent — unchanged'

- **statement**: PR #66's own body records, unchanged across the workstream: "The conventional durable workflow engine still wins on the evidence available. Supervisor, static dependency graph, explicit state, targeted retries, amplification near one. None of this work is evidence about that comparison — it establishes correctness prerequisites and measurement integrity. R8 decides it."
- **significance**: This is the single most consequential sentence in the workstream for the Track A / Track B decision. The morphogenetic substrate has NOT beaten the conventional baseline, and the branch's own author says so. Override §9 requires exactly this: Track B may replace Track A components only after proving better results and paying complexity rent. On present evidence it has not.

_Relates to: `pr.kernel.66`, `intent.track_a_track_b`, `intent.anti_self_deception`_

### `pr.kernel.66.latest_finding` — RA-2 — the legacy `_search` ledger is load-bearing for canonical repair

**Evidence:** `verified_by_inspection`
- `dababiyoda/uniimente-kernel` @ `a6f14d344f2c` · path `verification/phase3g/REPAIR_AUTHORITY_DESIGN_A_FALSIFIED.md`

- **source_commit**: a6f14d344f2ca073fd334a885e5c2bdb921d082e
- **measurement**: 924 passed / 0 failed  ->  904 passed / 21 failed, XPASS(strict) = 0
- **interpretation**: Zero strict XPASS means all twenty-one are real regressions, not earned activations. Removing the legacy ledger is not an authority removal; it is a behavioural change to repair, credit accounting, bounded-exhaustion escalation and the second-repair projection.
- **corrected_framing**: The defect is NOT "a disabled subsystem retains an authority it should not have". It is that the canonical repair path is not independent of the legacy repair path: they share state, and the legacy ledger is a live participant in canonical repair rather than a residue of a completed migration.
- **eliminated_designs**:
  - A
  - E
  - H
- **surviving_designs**:
  - B
  - C
  - D
  - F
- **leading_hypothesis**: B + D — separate the ledger's bookkeeping from its authority and centralise retirement. NOT ADOPTED.
- **uncommitted_work**: The DUAL_REPAIR_SEARCHES detector reordering is correct and independent of Design A's failure, but was not committed because it arrived inside a falsified candidate. It still requires its own negative control.
- **runtime_changed**: no

_Relates to: `pr.kernel.66`, `intent.anti_self_deception`_

## discrepancy (5)

### `discrepancy.issue67_stale` — Issue #67 records a hold point three findings out of date

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `8cb3074a4a83` · via `issue_read(get, 67)`

- **claimed_head**: 0ccda5c8030b0e1ea010a838694cdf514cd0babb
- **claimed_suite**: 886 passed · 1 skipped · 11 xfailed · 0 failed
- **actual_head**: a6f14d344f2ca073fd334a885e5c2bdb921d082e
- **actual_suite**: 924 passed · 1 skipped · 24 xfailed · 0 failed
- **claimed_bottleneck**: pre-arrival controls reaching a receiver before the search edge is adopted
- **actual_status**: pre-arrival control is IMPLEMENTED AND ADVERSARIALLY VERIFIED (PA-1..PA-5); the bottleneck moved twice since
- **comments**: 7
- **note**: The issue body is the durable resumption marker, so its staleness is more consequential than the PR body's: a session reloading from it would resume at a bottleneck that was closed weeks ago.
- **resolution**: RECORDED_ONLY

### `discrepancy.missing_machinery_premise` — Most "expected missing machinery" already exists on main

**Evidence:** `verified_by_inspection`
- `dababiyoda/uniimente-kernel` @ `8cb3074a4a83` · via `ls closure/ foundry/ omnimorph/ egregore/ evolution/ developmental/ linker/ compiler/ adapters/`

- **prompt_claim**: §10 of the earlier canonical prompt lists INSTITUTIONAL ANATOMY GRAPH, UNIVERSAL COMPATIBILITY MEMBRANE, CAPABILITY EXTRACTION AND REGISTRY, MECHANISM ATLAS, DEVELOPMENTAL COMPILER, CANDIDATE BUILDERS, PROTECTED EVALUATOR FIREWALL, SANDBOX/INCUBATOR, LINEAGE AND CAPABILITY ROUTER, WHOLE-BODY CLOSURE CONTROLLER and PROOF-TO-SETTLEMENT REALITY PATH as expected missing machinery.
- **measured**: main at 8cb3074 already contains closure/ (whole_body.py plus five registries), foundry/ (12 modules incl. advantage.py, composition.py, tribunal.py), omnimorph/engine.py, egregore/ (closure, contracts, drift, gate_adapter, resources, runtime), evolution/ (30 modules incl. strategy_tree.py, spider_web.py and the repair/ laboratory), developmental/ (MICA/CDPE), linker/, compiler/, adapters/, contracts/ (12 schemas), organs/ (3 manifests).
- **consequence**: The same prompt says "Test this diagnosis rather than assuming it." On this evidence the diagnosis does not hold as written. The real question is almost never "does it exist" but which of existing-and-connected / existing-but-disconnected / genuinely-absent applies. SP-3 resolves this per component; nothing may be proposed for construction before that classification.

_Relates to: `repo.uniimente-kernel`, `intent.malleability`_

### `discrepancy.pr66_body_stale` — PR #66 body describes head 15623a9; actual head is a6f14d3

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `a6f14d344f2c` · via `pull_request_read(get) vs git rev-parse origin/claude/uniimente-repo-audit-jpytcy`

- **claimed**: Head 15623a9
- **actual**: a6f14d344f2ca073fd334a885e5c2bdb921d082e
- **commits_behind_body**: 1
- **also_stale**: The body's "next active bottleneck" section names "truthful and exclusive authority over root-generation retirement". Commit a6f14d3 (RA-2) supersedes that framing — the coupling is broader than retirement authority. The body's stated bottleneck is therefore superseded by its own branch tip.
- **resolution**: RECORDED_ONLY — zero writes to PR #66 this round

_Relates to: `pr.kernel.66`, `pr.kernel.66.latest_finding`_

### `discrepancy.stacked_pr_backlog` — 69 open PRs across five repos, many stacked on non-default bases

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `8cb3074a4a83` · via `list_pull_requests(state=open) across all five repositories`

- **totals**:
  - **uniimente-kernel**: 26
  - **WealthMachineIntelligence**: 13
  - **RESEARCH-IN**: 11
  - **PumpStation**: 10
  - **DALEOBANKS**: 9
  - **total**: 69
- **structural_problem**: A large fraction target another feature branch rather than the default branch, forming chains that can only land in order. Kernel PRs 15->16->17->18->19->20->22 ->23->24->25->26 form one such chain; WMI 15->16->18->22 and 17->19->20->21->23 ->24 form two more; PumpStation 7->13->14->15 forms a fourth.
- **stale_base_problem**: Kernel PRs 44, 45, 46 and 35 are based on 3d9b5779 — the ARCHIVED main (archive/main-2026-07-19), not the current 8cb3074. PR 21 is based on 8a0b65cd, older still. PR 51 targets release/canonical-v1. These cannot merge cleanly without rebasing, and their diffs no longer describe the current tree.
- **note**: This is not a tidiness observation. It is the mechanical reason capability lands slowly: the institution's throughput is gated by chain order and stale bases, not by whether the work is good. It belongs in the strategic tree as a real constraint.

### `discrepancy.suite_495_vs_924` — 495 (main) and 924 (PR #66) are different branches, not a contradiction

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `8cb3074a4a83` · via `python -m pytest -q -p no:randomly  ->  495 passed in 6.22s`

- **main_suite**: 495 passed in 6.22s
- **pr66_suite**: 924 passed · 1 skipped · 24 xfailed
- **note**: The canonical prompt §8.1 presents 924/1/24 immediately under the kernel-main heading, which reads as if it were main's figure. Measured directly: main at 8cb3074 runs 495 passed. The 429-test difference is the PR #66 branch's own verification corpus, which lives only on that branch (verification/ does not exist on main at all). Both numbers are real. Collapsing them would overstate main's tested surface by ~87%.

_Relates to: `repo.uniimente-kernel`, `pr.kernel.66`_

## assumption (2)

### `round.branch_deviation` — Planning branch: harness-designated name used instead of the suggested one

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `8cb3074a4a83` · via `git rev-parse --abbrev-ref HEAD; git ls-remote --heads origin`

- **suggested**: planning/uniimente-whole-system-reconciliation-v1
- **used**: claude/super-planning-prompt-h8l0oj
- **rationale**: The session harness mandates this branch and forbids pushing elsewhere without explicit permission. §28 of the canonical prompt permits "a more appropriate existing planning branch"; this branch already exists locally and on origin at 8cb3074 and was created for this round. Conservative assumption, labelled per §0.
- **reversible**: yes

### `round.pr66_zero_writes` — PR #66 receives zero writes; the corrective comment is generated inert

**Evidence:** `asserted`
- `founder-upload` @ `1fd49e07437d` · (founder direction recorded in session, 2026-08-08)

- **rationale**: §34 of the canonical prompt permits one optional evidence-grounded correction comment. The founder directed zero writes and an inert founder-ready patch instead. The narrower instruction governs. PR66_PROPOSED_SYNC holds the exact replacement body and comment; applying either is a later explicit founder action.

_Relates to: `pr.kernel.66`, `discrepancy.pr66_body_stale`_
