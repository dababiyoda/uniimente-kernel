<!-- GENERATED FILE — DO NOT EDIT BY HAND -->
<!-- source: planning/graph/nodes/ via planning/compiler/render.py -->
<!-- graph-digest: c65a4d773a988a1c54da122175adc896c5bb2033a49f3813f0c4da5aadc3a36d -->
<!-- projection: WHOLE_SYSTEM_BACKCAST_GPS -->


# Backcast GPS — Destination to Active Node

Backcast from a falsifiable destination to the node that is active today. Each
node names its gate, its Single Bottleneck Metric with baseline and target, its
exit evidence, and its pivot and kill conditions.

Nodes 6 and beyond are deliberately not expanded. Every one is gated on Node 5,
and expanding them now would produce roadmap fiction rather than a plan. Override
§2 preserves those aspirations; honesty defers the node.

**6 nodes** projected from graph digest `c65a4d773a988a1c`. Regenerate with `python planning/compiler/render.py`.

## backcast node (6)

### `backcast.destination` — Long-range destination — falsifiable form

**Evidence:** `derived`
- _no evidence reference — this node is explicitly unresolved_

- **destination**: A founder-governed institution that finances its own development from lawful regenerative ventures, constructs missing capabilities from its preserved substrate under protected evaluation, closes those capabilities against external reality, and increases the capability of the participants and institutions it touches — without ever acquiring sovereignty of its own.
- **falsifiable_because**: Each clause names a countable: verified developmental closures, clean verified outcomes, contribution margin, participant capability deltas, and zero unauthorized external effects. A destination that cannot be counted cannot be backcast to.
- **not_promised**: This is a destination, not a forecast. No probability is claimed.

_Relates to: `intent.regenerative_civilization`, `intent.infinite_goal_chase`, `intent.closure_ladder`_

### `backcast.node_1_computational_closure` — Node 1 — first verified developmental closure (ACTIVE)

**Evidence:** `derived`
- _no evidence reference — this node is explicitly unresolved_

- **status**: ACTIVE
- **outcome**: one capability deliberately disabled and restored by generated candidates under a protected evaluator
- **gate**: builder/evaluator process isolation and held-out confinement do not yet exist
- **sbm**:
  - **name**: VERIFIED_DEVELOPMENTAL_CLOSURES
  - **baseline**: 0
  - **target**: 1
- **entry_condition**: evolution/repair/ laboratory present and frozen — SATISFIED
- **exit_evidence**: 4/4 edge triples restored; linker/ byte-identical to pinned hashes; lineage and rollback recorded; negative control fires
- **durable_assets**: a working developmental engine; first Capability Genome; reusable evaluator firewall
- **dependencies**: none_external
- **time_range**: days to weeks
- **capital_range**: zero
- **founder_attention_range**: under 1 hour — review of the closure record only
- **accelerators**: the frozen spec, hashed subject files and 4/4 threshold already exist
- **delays**: process isolation is real engineering, not configuration
- **pivot_condition**: if isolation proves impractical in-process, move candidates to containers before running the experiment — never relax the evaluator
- **kill_condition**: if a candidate can read or alter the evaluator, stop; the result would be worthless

_Relates to: `decision.final`, `capability.evolution_laboratory`, `capability.evaluator_firewall_partially_exists`_

### `backcast.node_2_generalization` — Node 2 — second closure on an unrelated capability

**Evidence:** `derived`
- _no evidence reference — this node is explicitly unresolved_

- **status**: NEXT
- **outcome**: the same engine closes a function it was not tuned for
- **gate**: Node 1 complete
- **sbm**:
  - **name**: VERIFIED_DEVELOPMENTAL_CLOSURES
  - **baseline**: 1
  - **target**: 2
- **why_it_matters**: This node, not Node 1, is what distinguishes a developmental engine from a bespoke repair script. It is also the falsification test for Track A's premise, which is why it is a node rather than a nice-to-have.
- **kill_condition**: if the second closure requires re-tuning the engine, the engine is overfit; report that plainly and re-run the route tournament

_Relates to: `backcast.node_1_computational_closure`, `decision.final`_

### `backcast.node_3_institutional_closure` — Node 3 — first institutional closure (cross-organ workflow)

**Evidence:** `derived`
- _no evidence reference — this node is explicitly unresolved_

- **status**: BLOCKED
- **outcome**: a generated or existing capability participates in a complete cross-organ workflow, end to end
- **gate**: Two of six organs have no manifest, adapters/ is unwired, and no organ consumes a kernel-issued grant. All three are engineering, none is blocked externally.
- **sbm**:
  - **name**: CLOSED_CROSS_ORGAN_BRIDGES
  - **baseline**: 0
  - **target**: 1
- **exit_evidence**: one recorded causal episode spanning at least three organs with typed contracts and a reconciled outcome
- **dependencies**:
  - backcast.node_1_computational_closure
  - bridge.two_organs_invisible
  - capability.adapters_membrane_orphaned

_Relates to: `bridge.status_a_through_h`, `intent.closure_ladder`_

### `backcast.node_4_economic_closure` — Node 4 — first economic closure (externally accepted, paid, reconciled)

**Evidence:** `derived`
- _no evidence reference — this node is explicitly unresolved_

- **status**: BLOCKED_ON_FOUNDER
- **outcome**: a named buyer accepts a delivered artifact, pays, and the outcome reconciles
- **gate**: FD-1 — DALEOBANKS publication authority; or an alternative wedge the founder names
- **sbm**:
  - **name**: CLEAN_VERIFIED_OUTCOME_COUNT
  - **baseline**: 0
  - **target**: 1
- **required_definition**:
  - named buyer or stakeholder
  - accepted artifact
  - precommitted acceptance criteria
  - external evidence
  - payment or enforceable commitment
  - delivery, acceptance, reconciliation
  - contribution margin
  - zero unauthorized effects
  - zero unresolved critical harm
- **why_it_cannot_be_engineered_around**: Every remaining blocker is a founder-supplied input: legal operator, payment account, customer consent, public identity, live credentials. No build session creates any of them.

_Relates to: `route.05_daleobanks_cash_engine`, `decision.founder_decisions_required`, `intent.daleobanks_role`_

### `backcast.node_5_flywheel` — Node 5 — DALEOBANKS free cash flow funds UNIIMENTE development

**Evidence:** `derived`
- _no evidence reference — this node is explicitly unresolved_

- **status**: BLOCKED
- **outcome**: recurring revenue exceeds obligations and reserves; surplus funds compute, tools and experiments
- **sbm**:
  - **name**: DALEOBANKS_FREE_CASH_FLOW_AVAILABLE_TO_FUND_UNIIMENTE
  - **baseline**: 0
  - **target**: > 0
- **gate**: Node 4
- **note**: Nodes 6 and beyond — multiple profitable Venture Cells, self-financed research, first physical embodiment — are real destinations preserved in the aspiration registry. They are not expanded here because every one of them is gated on Node 5, and expanding them now would produce roadmap fiction rather than a plan. Override §2 preserves the aspiration; honesty defers the node.

_Relates to: `intent.economic_research_flywheel`, `intent.embodiments_long_range`, `backcast.node_4_economic_closure`_
