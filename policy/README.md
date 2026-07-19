# policy

Layer 3 — Consequence Gate and Commit Witness. The ONE boundary through
which every external effect passes.

## The pipeline (exact)

```
Proposal → identity → legal principal → evidence → policy
→ approval → budget reservation → capability → Commit Witness
→ commit-time revalidation → execution → receipt → postcondition
→ reconciliation → outcome
```

## Files

- `engine.py` — policy evaluator. Deny by default, structured refusal
  reasons, `explain()` states which law applies, who is authorized, what
  remains missing, what may happen, what must not happen, and why.
- `consequence_gate.py` — the gate: lifecycle states from
  `workflows/approval-lifecycle.yaml`, `GrantIssuer` (single-action grants,
  contract-exact), `BudgetOffice` (explicit reservations, released on every
  failure path), commit-time revalidation (grant fresh/unrevoked/unused,
  effect hash bound, identity still valid, policy still allows, witness
  signature verifies).

## Hard rules (enforced in tests)

- expired grant / revoked grant / stale evidence at commit → fail closed
- effect mismatch at commit → hard refusal + incident on the ledger
- missing outcome record → blocks autonomy promotion
- any executor exception → `failed`, budget released, evidence preserved
- models recommend; this code authorizes

## Buildability standard (14 conditions)

- **Existing mechanism**: transaction-processor + capability-security pattern; HMAC-signed witnesses.
- **Defined interface**: `ConsequenceGate.run(proposal, executor, approver=None, standing_grant=None) -> ActionRecord`.
- **Bounded authority**: the gate cannot act; it can only authorize through the pipeline and refuses closed.
- **Available dependencies**: Python 3 stdlib + kernel modules (compiler, identity, provenance).
- **Security model**: every effect revalidated at the durability boundary; witnesses HMAC-signed; key from environment (`UNIIMENTE_WITNESS_KEY`), dev fallback only under `UNIIMENTE_ENV=development`.
- **Failure modes**: refused, denied, expired, revoked, failed — all terminal non-executing states, all ledgered.
- **Acceptance tests**: `tests/unit/test_consequence_gate.py` (happy path + 12 adversarial cases).
- **Recovery path**: every failure path releases the budget reservation and records the refusal; replay from ledger.
- **Resource ceiling**: grants expire in 15 minutes; approvals in 72 hours; single-use grants consumed once.
- **Operating cost**: two policy evaluations + one HMAC per action; measurable and constant.
- **Legal operator**: the legal principal on the proposal (validated against `authority/legal-principals.yaml`; never UNIIMENTE).
- **Handoff state**: `ActionRecord.trajectory` + ledger events reconstruct every decision without hidden context.
- **Replaceable**: executors and approvers are injected callables; the gate outlives any adapter.

## Orthogonal closures

Verified by `closure/kernel_registry.py` → module `consequence_gate`.
