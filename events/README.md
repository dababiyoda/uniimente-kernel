# events

Layer 4 — the durable institutional nervous system.

## Organs

- `spine.py` — `Event`: CloudEvents-compatible fact envelope (namespaced
  type, spiffe source for internal emissions, sensitivity classification,
  UNIIMENTE never legal principal). `EventSpine`: append-only event log
  on the evidence ledger with pub/sub, idempotent inbox (duplicate
  deliveries dropped, never re-ledgered), transactional outbox (staged
  events flush only through a mediator — in production, the Consequence
  Gate — and refused events stay staged, ledgered as refused), and
  replay (the stream rebuilds from the ledger; memory is never truth).
- `spine.py` — `DurableWorkflow`: checkpointed step sequences on the
  ledger. Kill at any step → `WorkflowKilled` → `resume()` reconstructs
  cursor + state from checkpoints and completes without re-executing
  finished steps and without manual restatement. Approval-wait steps
  block until a human approver ratifies. Steps that exhaust retries
  trigger reverse-order, best-effort compensation; every failure and
  every compensation is ledgered (negative evidence is never deleted).

- `task_fabric.py` — Phase-2 consequence-inert task reducer. It accepts explicit
  commands, appends one transition to the existing `EventSpine`, and rebuilds
  task state, lease history and `TaskReceipt` views from replay. `WorkerLease`
  narrows one immutable task; it never grants authority. Unknown external-effect
  state requires reconciliation before retry. It is not a scheduler, queue,
  worker loop, topology selector or replacement workflow engine.

## Recorded proof

`tests/unit/test_events.py` (11 tests): schema refusals, emit→replay
round-trip, ingest idempotency, outbox refusal staging, kill-and-resume
without restatement, reverse compensation, approval gating.

## Buildability standard (14 conditions)

- **Existing mechanism**: event logs, sagas, outbox/inbox patterns — all industry-standard, no novel science.
- **Defined interface**: `EventSpine.emit/ingest/subscribe/replay/outbox_stage/outbox_flush`; `DurableWorkflow.execute/resume`; typed dataclasses throughout.
- **Bounded authority**: the spine moves facts, never authority; external delivery is mediated (production: the Consequence Gate); events cannot name UNIIMENTE as principal.
- **Available dependencies**: Python 3 stdlib + `provenance.ledger`.
- **Security model**: schema validation fails closed; non-spiffe internal emissions refused; confidential failures classified; outbox requires a mediator decision per event.
- **Failure modes**: `EventError` (schema/principal/source), `WorkflowKilled` (interruption), `WorkflowFailed` (retries exhausted after compensation); all ledgered.
- **Acceptance tests**: `tests/unit/test_events.py` (11 tests).
- **Recovery path**: `DurableWorkflow.resume(workflow_id)` from ledger checkpoints; compensation runs reverse-order automatically.
- **Resource ceiling**: replay bounded by ledger size; outbox bounded by staged count; retries bounded per step (`max_retries`).
- **Operating cost**: one ledger append per event/checkpoint; dispatch is in-memory.
- **Legal operator**: Alfonso (every event names its legal principal; the institution never is one).
- **Handoff state**: the ledger IS the handoff — a fresh process replays the full stream and resumes any interrupted workflow from checkpoints. *This line was two claims, and only one of them was true when it was written.* `DurableWorkflow.resume` did rebuild cursor and state from checkpoints. The spine's own in-process state did not: the idempotent inbox started empty (fixed 2026-08-23) and the transactional outbox was a plain list, so a staged, unflushed delivery was ledgered as owed and then forgotten (fixed 2026-08-24). Both are now derived from the ledger, and the sentence is earned rather than aspirational.
- **Replaceable**: ledger, mediator, approver, and step callables are all injected; the spine survives any swap.

## Orthogonal closures

Verified by `closure/kernel_registry.py` → module `events`.
