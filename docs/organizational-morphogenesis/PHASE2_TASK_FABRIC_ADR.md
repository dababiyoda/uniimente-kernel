# ADR: Phase-2 Durable Task-Fabric Seam

- Decision: `EXPERIMENT`
- Linked decision: `DECISION-OM-TASK-FABRIC-2026-08-30`
- Parent decision: `DECISION-OM-2026-08-28`
- Authority: Alfonso
- External consequences: none
- Runtime owner selected: no

## Context

PR #70 and PR #87 remain competing runtime-composition experiments. Neither
needs to own the shared semantics of a task, worker lease or transition
receipt. Selecting one merely to implement Phase 2 would silently convert a
composition experiment into constitutional ownership.

The existing `EventSpine` already owns append-only facts, replay,
restart-safe idempotency and mediated outbox behavior. `DurableWorkflow`
already owns fixed checkpointed execution and remains the protected baseline.

## Decision

Place the minimum shared contracts in `contracts/`. Add
`events/task_fabric.py` as a deterministic state reducer whose only durable
writes are ordinary events on the existing Event Spine. Rebuild current state,
lease history and receipts from replay.

The reducer accepts explicit commands. It does not:

- schedule or spawn workers;
- run a queue or background loop;
- retry automatically;
- choose topology;
- mint or resolve authority;
- send external effects;
- replace `DurableWorkflow`;
- modify or choose between the runtime branches.

A WorkerLease can only narrow authority, tools, data, context, resources and
consequence ceiling already present on its TaskEnvelope. Replacement requires
a fresh lease; nothing is inherited implicitly.

## State model

`CREATED → ADMITTED → QUEUED → LEASED → RUNNING → SUBMITTED → VERIFIED → CLOSED`

Failure exits are `FAILED`, `RETRY_ELIGIBLE`,
`RECONCILIATION_REQUIRED`, `QUARANTINED` and `TERMINATED`. An uncertain
effect may only enter `RECONCILIATION_REQUIRED`; retry or termination then
requires explicit reconciled status and evidence.

Exactly-once delivery is not claimed. One caller-supplied transition key plus a
content fingerprint makes repeated commands idempotent and conflicting reuse
fail closed.

## Eight-side hardening

| Side | Phase-2 mechanism |
|---|---|
| 1. Reality/failure | Illegal transitions, stale order, budget breach, poison output and uncertain effects fail closed |
| 2. Power/participants | Mission owner, coordinator, leased worker and independent evaluator remain distinct |
| 3. Eligibility/permission | WorkerLease narrows an immutable TaskEnvelope |
| 4. Default routing/access | Task transitions use the canonical Event Spine |
| 5. Proof/truth/reputation | TaskReceipt is bound to an Event ID and causal parent; replay is truth |
| 6. Resource physics | Cumulative recorded usage cannot exceed the task envelope |
| 7. Distribution/entanglement | Runtime-neutral contracts can be consumed without copying authority |
| 8. Reliability/governance | Restart reconstruction, reconciliation, quarantine, termination and dissolution readiness |

Super-node mapping: WorkerLease → Eligibility; EventSpine transitions → Default
Routing; TaskReceipt/evidence → Proof/Truth; resource envelope and uncertain
effect reconciliation → Resource/Settlement.

## Consequences

This resolves only the semantic-owner dependency for Phase 2. Runtime
composition ownership remains unresolved. Passing tests establish a
consequence-inert task-state seam, not a cross-organ mission closure.

## Rollback and kill

Delete or revert the three schemas, reducer, tests and linked documentation.
Keep the deliberation and failures. Kill the seam if it becomes a scheduler,
adds persistence outside EventSpine, expands authority, permits blind retry,
allows self-verification, edits `runtime/`, or cannot justify its complexity
against the static workflow.
