# loom

Phase 4 — the Automation Loom: the machine authors, the human ratifies, the spine executes.

## Organs

- `pattern.py` — `WorkflowPattern`: workflow definitions as data. Every
  step names its capability, consequence class, compensation, and
  approval gate. Invalid by construction: irreversible/financial/
  external steps without a human gate; side-effecting steps without
  compensation; UNIIMENTE as principal. `hash()` binds the exact
  content — any edit is a new, unratified pattern.
- `ratify.py` — `Ratifier`: submission and ratification/rejection
  ledgered; latest decision wins; rejection preserved forever.
- `weaver.py` — `Weaver`: compiles ratified patterns into durable
  `DurableWorkflow`s on the Layer 4 spine. Unratified patterns never
  weave; unknown operations never weave.
- `canonical.py` — the three agent-authored workflows: daily
  reconciliation, evidence-floor review (human-gated), venture
  validation gate (human-gated).

## Recorded proof

`tests/unit/test_loom.py` (11 tests): pattern contract refusals, hash
binding, unratified-never-weaves, edit-after-ratify invalidation,
rejection preserved, all three canonical workflows end-to-end,
mid-flight kill + resume, approval gate blocking until human ratifies.

## Buildability standard (14 conditions)

- **Existing mechanism**: workflow definitions, approval gates, sagas — standard patterns, no novel science.
- **Defined interface**: `Ratifier.submit/decide/status`; `Weaver.weave(pattern) -> DurableWorkflow`.
- **Bounded authority**: the loom orchestrates; the Consequence Gate authorizes external effects; ratification is human-only.
- **Available dependencies**: Python 3 stdlib + `events.spine`, `provenance.ledger`.
- **Security model**: unratified patterns refused; hash binding makes silent edits impossible; approval gates forced by consequence class.
- **Failure modes**: `PatternError`, `LoomRefused` (unratified, invalid, unknown operation) — all ledgered.
- **Acceptance tests**: `tests/unit/test_loom.py` (11 tests).
- **Recovery path**: woven workflows inherit spine durability: kill → resume from checkpoints; compensation reverse-order.
- **Resource ceiling**: steps bounded per pattern; retries bounded per step; one ledger append per transition.
- **Operating cost**: ratification is one human decision; execution is spine-bounded.
- **Legal operator**: Alfonso (ratifies every pattern; named principal on every workflow).
- **Handoff state**: patterns are data; ledgered submission/ratification/weaving records reconstruct the full trail.
- **Replaceable**: operations registry, approver, spine all injected.

## Orthogonal closures

Verified by `closure/kernel_registry.py` → module `loom`.
