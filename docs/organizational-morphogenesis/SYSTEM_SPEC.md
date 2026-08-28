# Phase-1 System Specification

## Scope

This specification defines the shared semantics required before an
Organizational Morphogenesis runtime may be implemented. It adds no executor.

## Canonical seams

| Concern | Owner | Phase-1 artifact |
|---|---|---|
| Mission boundary and geometry | `contracts/` | `mission-contract.schema.json` |
| Organizational design | `omnimorph/` (proposed) | `orchestration-genome.schema.json`; compiler deferred |
| Durable work | `events/` | Existing Event Spine/DurableWorkflow; unchanged |
| Organizational evidence | `provenance/` | `topology-episode.schema.json`; recorder deferred |
| Authority and acceptance | `governance/` plus existing Gate | References only; unchanged |
| Capability supply | `capabilities/` | Existing Capability Genomes; unchanged |
| Routing recommendation | `routing/` | Existing non-authorizing route decisions; unchanged |

## Contract semantics

### MissionContract

One immutable mission boundary contains founder-intent lineage, objective,
beneficiaries, legal principal, existing authority references, deadline,
resource ceilings, consequence ceiling, capability needs, evidence/success
conditions, risk/data constraints, prohibited actions, reversibility, kill and
escalation rules, external-effect policy, acceptance authority, closure,
organization policy and inspectable ProblemGeometry.

The mission contract constrains every organization. No organization may edit
it. External-contact, financial or irreversible ceilings require
`gate_required` policy.

### OrchestrationGenome

A versioned genome describes nodes, event edges, bounded coordinator rights,
worker pools, task policy, communication, independent evaluators, resources,
failure, governed reconfiguration, dissolution, metrics, static/do-nothing
fallback, kill conditions and existing authority references.

Its digest is SHA-256 over RFC 8785 canonical JSON excluding the `digest`
field. The digest does not prove correctness; it binds identity to content.

Allowed states are `hypothesis`, `experiment_candidate`, `validated` and
`retired`. `validated` requires at least one executed TopologyEpisode reference
and the claim `SUPPORTED_BY_EXECUTED_EPISODES`. This is necessary, not
sufficient; repeated independent evidence is an experiment policy requirement.

### TopologyEpisode

Only actual execution may satisfy this contract. It records mission geometry,
genome/capability versions, worker/provider composition, task graph, resources,
messages, failures, reconfiguration, dissent, quality, cost, latency, recovery,
closure, lineage, authority outcomes and preservation disposition.

`verified_durable_mission_closure=true` is schema-valid only with deliberate
interruption evidence, exact restart, zero lost/duplicate consequential tasks,
complete lineage/dissent, a closure receipt and zero authority/external-effect
invariant violations. A simulation or model prediction cannot use the record.

## Task lifecycle target (deferred to Phase 2)

`CREATED → ADMITTED → QUEUED → LEASED → RUNNING → SUBMITTED → VERIFIED → CLOSED`

Failure exits are `RETRY_ELIGIBLE`, `RECONCILIATION_REQUIRED`, `QUARANTINED`
and `TERMINATED`. At-least-once delivery plus idempotency is permitted.
Exactly-once delivery is not claimed. Unknown external-effect state always
routes to reconciliation before retry.

No TaskEnvelope, TaskReceipt or WorkerLease contract is added in Phase 1,
because their canonical integration depends on the unresolved runtime seam.

## Power invariants

1. Organization design has no mission, execution or consequence authority.
2. Coordinators may decompose, sequence, prioritize, route, request workers,
   allocate already-authorized internal resources, synthesize, request
   reconfiguration and escalate—nothing more.
3. Workers receive one task, minimum context and a time/resource-limited lease.
4. Workers and replacements never inherit coordinator/failed-worker authority.
5. Required evaluators are structurally independent; dissent cannot be hidden.
6. Only the canonical Gate/legal-principal path may authorize external effects.
7. A selected or high-performing topology never creates authority.

## Phase gates

| Phase | Entry | Exit evidence | Rollback | Kill condition |
|---|---|---|---|---|
| 0 truth reconciliation | Founder directive | Frozen inspection ledger | Close branch | Material source unavailable or ownership fabricated |
| 1 semantics/preregistration | Phase 0 frozen | Three schemas, negative controls, experiment freeze, ownership proposal | Revert inert files | Contract duplicates an existing owner or creates authority |
| 2 task-fabric seam | Explicit owner decision | Existing Event Spine carries durable task lifecycle/leases through restart | Disable seam and use DurableWorkflow baseline | Second spine/runtime truth appears |
| 3 compiler | Phase-2 receipts | Deterministic geometry → materially different candidate genomes and transparent scorecards | Emit static only | LLM intuition becomes sole selector |
| 4 comparison | Corpus/hash/thresholds sealed | Preserved TopologyEpisodes for every candidate and failure | Stop runs; retain evidence | Threshold changed after held-out observation |
| 5 canonical integration | Dynamic mechanism earns acceptance | Narrow integration plus static fallback | Revert winner integration | Added complexity exceeds verified advantage |
| 6 WealthMachine migration | Phase-5 evidence and organ owner approval | Shadow closure using real interface | Restore fixed roster | Quality/evidence/authority regression |
| 7 DALEOBANKS shadow | WMI result and one identity preserved | Internal-only shadow episodes | Disable shadow | Publication or identity fragmentation |
| 8 RailScout native | Executable RailScout owner exists | Evidence tasks converge through canonical synthesis | Static read-only research | Giant unbounded context or noncanonical runtime |
| 9 Venture Cell composition | Repeated cross-geometry evidence | Founder-ratified bounded phenotype composition | Static cell charter | Organization receives financial authority |

No phase inherits a pass from its predecessor.

## Migration

There is no Phase-1 migration. Later migration is adapter-first and shadow-only:

1. resolve `runtime/` ownership;
2. consume canonical contracts without copying them into organs;
3. run new paths beside current organ baselines;
4. compare receipts under identical envelopes;
5. integrate only an earned mechanism;
6. remove a shim only after its canonical source, owner, expiry trigger and
   removal condition are recorded.

## Rollback

The branch is inert. Before consumers exist, rollback is a scoped revert of the
three schemas, test and documentation while retaining the deliberation and
negative evidence. The existing DurableWorkflow and current organ flows remain
unchanged throughout.
