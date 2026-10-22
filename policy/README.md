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
  `evidence_freshness_reasons()` resolves evidence refs against a register.
- `consequence_gate.py` — the gate: lifecycle states from
  `workflows/approval-lifecycle.yaml`, `GrantIssuer` (single-action grants,
  contract-exact; its own records are never handed out: holders get copies,
  and an edited copy is an altered grant; a child grant is refused unless it
  is a subset of a known, live, unconsumed parent whose whole lineage is live,
  per `authority/authority-matrix.yaml` `child_grants: strict_subset_of_parent`
  and `revocation: immediate_and_propagating`), `BudgetOffice` (explicit reservations, released on every
  failure path), commit-time revalidation (grant fresh/unrevoked/unused,
  effect hash and granted authority bound, proposal unchanged since
  admission, identity still valid, policy still ALLOWs or a human approval
  held for this exact proposal covers its REQUIRE_HUMAN reasons, witness
  signature verifies).

## Hard rules (enforced in tests)

- expired grant / revoked grant at commit → fail closed
- unknown or stale evidence → fail closed at evaluation and again at commit
  when the Gate is built with an `evidence` register of
  `contracts/evidence.schema.json` packets: a ref must resolve to one
  contract-valid packet, either by packet id or, for a `sha256:<64 hex>`
  content address (the form every in-repo producer emits), by the packet's
  `raw_content_hash` (none, or several different packets, refuses); a packet is
  stale at the earlier of its optional `fresh_until` and `captured_at` +
  `EVIDENCE_MAX_AGE[consequence class]` (#21).
  Without a register, evidence refs are opaque digests checked for presence only.
  **This rule is unarmed on every canonical path today**: no production
  `ConsequenceGate` construction passes `evidence=` (GREG's AuthorityOffice,
  the closure registries, the egregore sandboxes and missions, foundry
  kernel_stack), so those paths have no stale-evidence protection until a
  register is wired. `docs/decisions/SR002-GATE-HARDENING-01.json`
  (`evidence_register.armed_at`) lists every armed construction, and a test
  holds that list to the code.
- effect mismatch at commit → hard refusal + incident on the ledger
- consequence class (or any authority-relevant field) changed between
  admission and commit, or REQUIRE_HUMAN at commit without a matching
  approval → hard refusal; authority mismatches raise an incident (#55)
- from admission on the Gate acts on its own deep copy of the proposal: the
  witness, the dispatch claim's effect digest, the executor's argument and the
  outcome are all the admitted proposal's. A change to the caller's object is
  refused at commit and again inside the ledger lock before the dispatch claim;
  after the claim it cannot reach the effect. A proposal that cannot be
  canonicalised (e.g. mixed key types) is refused, never raised (#55 follow-up)
- child grant beyond its parent (actions, spending, counterparties, legal
  actor, prohibitions, lifetime, consequence class, action class, objective)
  or of an unknown/revoked/expired/consumed parent or ancestor → refused at
  issuance (`GrantRefused`, #12)
- spending is delegated, not copied: a parent's children together hold at
  most its limit and the parent may then spend only what it has not delegated;
  revoking a grant revokes its descendants; a revoked, expired or consumed
  ancestor refuses a descendant at admission and at commit (#12 follow-up)
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
- **Acceptance tests**: `tests/unit/test_consequence_gate.py` (happy path + adversarial cases).
- **Recovery path**: every failure path releases the budget reservation and records the refusal; replay from ledger.
- **Resource ceiling**: grants expire in 15 minutes; approvals in 72 hours; single-use grants consumed once.
- **Operating cost**: two policy evaluations + one HMAC per action; measurable and constant.
- **Legal operator**: the legal principal on the proposal (validated against `authority/legal-principals.yaml`; never UNIIMENTE).
- **Handoff state**: `ActionRecord.trajectory` + ledger events reconstruct every decision without hidden context.
- **Replaceable**: executors and approvers are injected callables; the gate outlives any adapter.

## Orthogonal closures

Verified by `closure/kernel_registry.py` → module `consequence_gate`.
