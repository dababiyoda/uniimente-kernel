<!-- GENERATED FILE — DO NOT EDIT BY HAND -->
<!-- source: planning/graph/nodes/ via planning/compiler/render.py -->
<!-- graph-digest: c65a4d773a988a1c54da122175adc896c5bb2033a49f3813f0c4da5aadc3a36d -->
<!-- projection: DEPENDENCY_AWARE_PR_STACK -->


# Implementation Program — PR Stack and Anti-Ruin Boundaries

Five PRs, each based on **current main** — never stacked onto another feature
branch. The 69-PR backlog exists precisely because that rule was not held, and
four kernel PRs are now unmergeable against an archived base.

The anti-ruin boundaries are conservative defaults marked provisional. Alfonso
has not set a risk appetite, and inventing one on his behalf would be the kind of
quiet authority expansion this whole architecture exists to prevent.

**2 nodes** projected from graph digest `c65a4d773a988a1c`. Regenerate with `python planning/compiler/render.py`.

## implementation program (2)

### `program.anti_ruin_boundaries` — Anti-ruin boundaries for the primary track

**Evidence:** `derived`
- _no evidence reference — this node is explicitly unresolved_

- **boundaries**:
  - **maximum_money_at_risk**: zero — the primary track spends nothing
  - **maximum_founder_hours**: under 2 hours per node, for review only
  - **maximum_time_without_new_proof**: one cycle; if Node 1 does not close, re-run the route tournament rather than iterating quietly
  - **maximum_vendor_concentration**: no new provider, platform or model dependency introduced
  - **maximum_external_consequence**: zero — every artifact is consequence-inert
  - **isolation_requirement**: candidates never share a process with the evaluator
  - **escalation_threshold**: any candidate that reads or writes the evaluator halts the experiment immediately
  - **stop_loss**: two consecutive failed closure attempts ends Track A's primary status
  - **minimum_viable_survival_state**: main at 8cb3074 with 495 passing tests; every branch preserved; every proof record intact
- **provisional**: These are conservative defaults, not the founder's stated risk appetite. Alfonso has not set limits; these are marked provisional for his decision rather than presented as policy.

_Relates to: `decision.final`, `intent.round_authority`_

### `program.pr_stack` — Dependency-aware PR stack — against current main, never an archived base

**Evidence:** `derived`
- _no evidence reference — this node is explicitly unresolved_

- **ordering_rule**: Every PR bases on current main. No stacking onto another feature branch. The 69-PR backlog exists precisely because that rule was not held, and four kernel PRs are now unmergeable against an archived base.
- **cap**: no more than 3 open planning-derived PRs at once; land before opening the next
- **stack**:
  - - **id**: P1
    - **title**: Evaluator firewall: process isolation and held-out confinement
    - **repo**: uniimente-kernel
    - **depends_on**: 
    - **acceptance**:
      - builder and evaluator run in separate OS processes
      - candidate write paths confined and enforced by test
      - held-out cases exist and are unreadable from the builder process
      - a negative control forces evaluator failure and is asserted
      - evaluator mutation is detected and fails the run
    - **why_first**: Without it the closure experiment is worthless, so it is a gate rather than a follow-up.
  - - **id**: P2
    - **title**: First developmental closure run: institutional.cross_organ_edge_resolution
    - **repo**: uniimente-kernel
    - **depends_on**: - P1
    - **acceptance**:
      - at least five materially different candidate implementations
      - 4/4 edge triples restored — 3/4 is a failure, not a 75% pass
      - linker/ byte-identical to ORIGINAL_LINKER_PACKAGE_SHA256
      - champion attached in a consequence-inert registry
      - specialists, fallbacks and failures all preserved with lineage
      - rollback demonstrated, not merely described
      - closure record states its ladder tier: COMPUTATIONAL
  - - **id**: P3
    - **title**: Organ manifests for PumpStation and RESEARCH-IN
    - **repo**: uniimente-kernel
    - **depends_on**: 
    - **parallel_with**:
      - P1
      - P2
    - **acceptance**:
      - both manifests validate against contracts/organ-manifest.schema.json
      - linker reports 6 organs, not 4
      - RESEARCH-IN's role is derived from inspected evidence, with unresolved fields left unresolved rather than invented
  - - **id**: P4
    - **title**: Wire the compatibility membrane into one executing path
    - **repo**: uniimente-kernel
    - **depends_on**: - P3
    - **acceptance**:
      - adapters/ imported by at least one non-test module
      - one recorded cross-organ episode using the adapters
      - information lost and added declared per adapter, as the membrane rule requires
  - - **id**: P5
    - **title**: Second developmental closure on an unrelated capability
    - **repo**: uniimente-kernel
    - **depends_on**: - P2
    - **acceptance**:
      - engine closes a function it was not tuned for, with no re-tuning
      - if re-tuning is required, report overfit plainly rather than adjusting and retrying
- **explicitly_not_in_the_stack**:
  - any PR #66 runtime work — frozen
  - any external effect, credential, publication or payment — founder-gated
  - Golden Kernel v2 — authority is not the measured bottleneck
  - new WMI or PumpStation capacity — triage the existing backlog first

_Relates to: `decision.final`, `backcast.node_1_computational_closure`, `discrepancy.stacked_pr_backlog`, `bridge.two_organs_invisible`_
