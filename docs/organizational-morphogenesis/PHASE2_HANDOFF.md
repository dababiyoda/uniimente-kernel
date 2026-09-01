# Phase-2 Organizational Task-Fabric Handoff

Status: **EXPERIMENTAL / CONSEQUENCE-INERT**. Phase 2 is implemented on
`agent/organizational-task-fabric-phase2` in draft PR #90, stacked on draft
PR #88. No merge, deployment, organ migration, topology promotion, external
effect or authority expansion occurred.

## 1. Inspected scope

This phase inherits the frozen Phase-0 inspection ledger in
`INSPECTION_LEDGER.md`, which records the exact snapshots inspected for
`uniimente-kernel`, DALEOBANKS, WealthMachineIntelligence, PumpStation,
RAILSCOUT, the named PRs, founder sources and external precedents.

For the Phase-2 decision, the following were re-opened and inspected:

- draft PR #88 and its Phase-1 contracts, system specification, ownership
  proposal, decision record and handoff;
- PR #70 `runtime/ADR-P3-ROUTE-B.md` and `runtime/contract.py`;
- PR #87 `events/spine.py`, `runtime/session.py` and runtime ownership
  claims;
- current `events/spine.py`, `events/README.md`,
  `tests/unit/test_events.py`, `tests/unit/test_restart_resume.py`,
  `provenance/ledger.py`, `contracts/event.schema.json` and
  `contracts/capability-grant.schema.json`;
- draft PR #90, its changed-file set, commit heads and canonical workflow runs
  #232, #234, #236 and #239.

PR #70 and PR #87 remain open competing composition experiments. No runtime
winner was inferred or selected.

## 2. Canonical ownership

| Semantic | Canonical owner |
|---|---|
| Mission/constitutional authority | `governance/` and existing legal-principal mechanisms |
| Shared task/lease/receipt contracts | `contracts/` |
| Durable task-transition truth | existing `events/EventSpine` |
| Task-state replay projection | `events/task_fabric.py` |
| Fixed workflow baseline | existing `events/DurableWorkflow` |
| Evidence and future materialized receipt views | `provenance/` |
| Organization design | proposed `omnimorph/`; no executor in this phase |
| Runtime composition | **UNRESOLVED** between PR #70 and PR #87 |
| Consequence authority | existing Consequence Gate plus accountable legal principal |

`runtime/` does not own task semantics, authority, identity, evidence or
consequence policy. The Phase-2 ownership addendum does not amend either runtime
branch.

## 3. Mechanisms extracted

- Event sourcing and replay-derived state;
- idempotent inbox/outbox and content-bound command deduplication;
- fixed durable workflow checkpoints as the protected baseline;
- time/resource/context-bounded one-task eligibility;
- least-authority subset checks;
- independent result evaluation and dissent preservation;
- reconciliation before retry after uncertain effects;
- poison-output quarantine and controlled dissolution readiness.

## 4. Material mutations

- A task queue became explicit state transitions on the existing Event Spine;
  no new queue service was created.
- A permanent worker role became a fresh, expiring, one-task WorkerLease.
- Supervisor authority became coordinator identity checks plus no grant minting.
- At-least-once delivery became transition-key idempotency plus command-content
  conflict detection, without an exactly-once claim.
- A retry policy became a fail-closed reconciliation state for uncertain
  effects.
- A completion claim became a replay-bound TaskReceipt view; it is not outcome
  evidence or a TopologyEpisode.
- Dissolution became an explicit readiness gate over terminal tasks, active
  leases, obligations and evidence.

## 5. Candidate architectures preserved

Static DurableWorkflow, WMI fixed roster, centralized, hierarchical, hybrid and
do-not-instantiate remain preregistered. Decentralized/developmental forms stay
deferred until evidence justifies the additional amplification.

## 6. Baseline and strongest competitor

The existing static DurableWorkflow remains the default, fallback and strongest
competitor. It wins ties. Phase 2 does not replace or modify it.

## 7. Exactly two strengthening passes

`DECISION-OM-TASK-FABRIC-2026-08-30` contains one five-role constitutional
review with exactly:

1. Structural Ascent: five advantages, five disadvantages, baseline,
   do-nothing, simplest alternative, strongest competitor and reversible test.
2. Adversarial Compounding: replay/order, time, evaluator capture, evidence
   theater and failure amplification attacks, with every Pass-1 disadvantage
   dispositioned.

The record validates with the collaboration protocol. No third pass occurred.

## 8. Selected design

Three fail-closed contracts plus one explicit-command, replay-derived reducer.
Every durable transition is an ordinary event on the existing Event Spine. The
reducer has no scheduler, worker loop, queue service, topology selector,
automatic retry or external-effect path.

## 9. Files added or changed

- `contracts/task-envelope.schema.json`
- `contracts/worker-lease.schema.json`
- `contracts/task-receipt.schema.json`
- `events/task_fabric.py`
- `tests/unit/test_organizational_task_fabric.py`
- `events/README.md`
- `docs/organizational-morphogenesis/SYSTEM_SPEC.md`
- `docs/organizational-morphogenesis/PHASE2_TASK_FABRIC_ADR.md`
- `docs/collaboration/ARCHITECTURE-OWNERSHIP-OM-PHASE2.yaml`
- `docs/collaboration/deliberation-organizational-task-fabric-2026-08-30.json`
- this handoff

## 10. Intentionally unchanged

`runtime/`, `omnimorph/` implementation, `egregore/`, `routing/`,
`governance/`, `provenance/` storage, identity registries, Capability
Genomes, Consequence Gate, organ repositories, credentials, schedules and
deployment configuration.

No TopologyDecision, ReconfigurationProposal, organization compiler, adapter,
worker executor or organ migration was added.

## 11. Tests and commands actually run

- Canonical CI run #234 on the initial reducer: **1,337 passed, 2 skipped**;
  institutional verifier V1-V5 passed.
- Canonical CI run #239 after actor/role hardening:
  **1,338 passed, 2 skipped**.
- Run #239 institutional verifier:
  V1 45/45 artifacts, V2 **1,197 passed, 2 skipped**, V3 all named modules
  closed, V4 false-closure/gate-loop probes passed, V5 19 buildability READMEs.
- Contract-reference job passed.
- Single-authority job passed.
- Developmental-sealing job passed.
- Collaboration validator:
  `validate_deliberation.py phase2-deliberation.json` → valid after repair.

## 12. Failed tests and negative evidence

- Canonical run #232 was cancelled by a superseding branch commit; it is not
  counted as passing evidence.
- The first collaboration-validator run failed with **13 closed-vocabulary
  errors** in evidence tiers, response types and weakness categories. The
  record was corrected without changing the decision and then validated.
- No cross-organ mission, topology comparison, provider outage, split-brain
  coordinator, live state migration or external-effect reconciliation was
  executed.
- The conventional durable workflow still has the stronger available
  reliability/cost/amplification evidence.

## 13. Evidence tiers

| Claim | Tier |
|---|---|
| Contract shape and fail-closed unknown fields | unit test |
| Normal/adversarial task lifecycle | unit test |
| Restart reconstruction and duplicate suppression | durable local fixture in canonical CI |
| One-source-of-authority repository check | canonical CI |
| Phase-2 deliberation structure | collaboration validator |
| Dynamic topology advantage | hypothesis only |
| Cross-organ durable closure | no evidence |
| External/commercial effect | no evidence |

## 14. Current reality

`EXPERIMENTAL / CONTRACT-AND-REDUCER TESTED`.

Not LIVE, PROVEN, HARDENED, morphogenetically superior, autonomous,
commercially successful or externally accepted.

## 15. Single Bottleneck Metric

`Verified Durable Mission Closures: 0 → 0`.

Phase 2 proves a restart-safe task seam. It does not execute the required
DALEOBANKS → Kernel → WealthMachine → independent evaluator mission.

## 16. Remaining blockers

- a new linked decision before Phase 3;
- deterministic ProblemGeometry-to-candidate compilation;
- independently sealed corpus, thresholds and failure injections;
- real canonical DALEOBANKS and WealthMachine adapters;
- a runtime composition decision only when integration actually requires it;
- one deliberate interrupted cross-organ episode and closure receipt;
- broader attacks: split brain, provider outage, queue starvation, priority
  inversion, task-graph cycles and state migration.

## 17. Dissent

The task reducer may still be unnecessary if the fixed DurableWorkflow can
carry the same comparison more simply. The task fabric has earned only a
bounded Phase-2 experiment. If later work ties the static form while adding
complexity, regress to static.

## 18. Rollback

Close draft PR #90 or revert its three contracts, reducer, tests and linked
documents. Retain the deliberation, failed validator output and reasons. PR
#70, PR #87, EventSpine, DurableWorkflow and organ repositories remain intact.

## 19. Kill criteria

Kill or reconfigure if the seam becomes a scheduler or second workflow truth;
widens/inherits authority; permits worker/coordinator self-verification; retries
uncertain effects blindly; loses replay exactness or lineage; bypasses the
Consequence Gate; edits runtime ownership implicitly; or costs more complexity
than the experimental capability justifies.

## 20. Continuation

Future Claude, Kimi, ChatGPT or human work must begin from PR #90 and this
record, recheck current heads, preserve PR #70/#87 competition, retain static
workflow as the baseline, and open a **new linked deliberation** before Phase 3.
Do not amend either frozen two-pass decision. Do not merge, deploy, migrate an
organ, activate external effects or claim VDM=1 without the required episode.
