# HANDOFF — Work Package WP-01: Consequence Gate Vertical Slice

**Date:** 2026-07-20 · **Repo:** dababiyoda/uniimente-kernel · **Branch:** build/consequence-gate
**Production cycle:** SPECIFY → SOURCE → DESIGN → IMPLEMENT → TEST → ATTACK → VERIFY → DOCUMENT → COMMIT → HAND OFF

## 1. Current state (what exists now)
`kernel/` Python package implementing Order One of the UNIIMENTE FINAL BUILD ORDERS:
- **20 versioned institutional contracts** (`kernel/contracts/`): frozen pydantic v2
  models covering InstitutionalEvent, EvidencePacket, ContextPacket,
  OpportunityPacket, VentureAssessment, ActionIntent, PolicyDecision,
  ApprovalRecord, CapabilityGrant, AutonomyLicense, CommitWitness,
  ExecutionReceipt, ReconciliationRecord, OutcomeRecord, DecisionEpisode,
  RegenerativeImpactRecord, IncidentRecord, OrganCharter, BusinessGenome,
  SwarmContract. Registry: `kernel.contracts.CONTRACTS`.
- **Event spine** (`kernel/spine/`): append-only, hash-chained JSONL log
  (seq/prev_hash/record_hash, fsync on append) + Merkle day-sealing.
  `verify_chain()` detects single-bit tamper and truncation.
- **Consequence Gate** (`kernel/gate/`): the full 15-stage pipeline
  (PROPOSE→IDENTIFY→CLASSIFY→EVALUATE→APPROVE→RESERVE→ISSUE→WITNESS→
  REAUTHORIZE→EXECUTE→RECEIPT→VERIFY→RECONCILE→OUTCOME→MEMORY).
  Fail-closed `GateRefusal` hierarchy. Injectable `policy_fn` and `clock`
  (deterministic, replayable decision traces). Stage interceptors for testing.
- **Authority** (`kernel/authority/`): founder-signed Ed25519 approvals over
  fingerprint+approver+nonce; nonce replay protection; expiry.
- **Adapters** (`kernel/adapters/`): protocol refuses execution without a
  current verified CommitWitness; BoundedAdapter re-verifies the witness
  itself (defense in depth); EchoAdapter = bounded simulated research action.
- **Crypto** (`kernel/crypto/`): Ed25519 sign/verify, canonical-JSON SHA-256.
- **Tests** (`tests/gate/`): contracts, spine, happy path, hostile suite.

## 2. Verification evidence
- `python3 -m pytest -q tests/gate` → **36 passed** (verified locally twice,
  then re-verified against the exact content of this branch after push).
- Hostile suite (12/12): payload mutation, target substitution, approval replay,
  stale evidence, expired grant, revoked grant, split-budget evasion,
  cross-organ capability use, duplicate execution (one_use grant),
  forged receipt, direct adapter call without witness, restart during
  uncertain effect (no double-execute, refusal recorded, chain verifies).
- Happy path: C2 research intent → REQUIRE_HUMAN → founder approval →
  execution → reconciliation → closed DecisionEpisode; chain verifies.
- State label: **implemented, locally tested. NOT merged, NOT externally
  validated, NOT production-proven.**

## 3. Architecture decisions (ADR summary)
1. Determinism over convenience: injectable clock everywhere; hashing never
   depends on wall time. Rationale: replayable law is the product.
2. Durability via spine, not stores: GrantStore/BudgetLedger/nonces are
   in-memory for the slice; double-execution protection is carried by the
   spine EXECUTE_BEGIN marker so restart cannot re-execute.
3. Policy as injected function, default C0/C1 PERMIT, C2 REQUIRE_HUMAN,
   C3+ DENY. The UCL compiler (WP-02) will replace the default.
4. Single-segment spine; rotation deferred.
5. Stage interceptors: test-only hooks per pipeline stage; hostile tests
   tamper between stages exactly where an attacker would.

## 4. Known limitations
- In-memory grant/budget/nonce stores (durability via spine only).
- Budget caps are gate defaults, not constitution-derived.
- No UCL compiler yet: `.ucl` files in `constitution/` are still dead text.
- EchoAdapter simulates; no real external adapter wired.
- No Postgres backend; spine is file-based.

## 5. Next active bottleneck (Order One, Days 31–90)
Close ONE external loop: Evidence → Assessment → Policy → Approval →
Capability → Action → Receipt → Outcome → DecisionEpisode against a REAL
adapter (a DALEOBANKS read-only research action over HTTP), producing one
observed external result.

## 6. Exact next actions for the next agent
1. WP-02: `kernel/ucl/` — lexer/parser/evaluator for the five existing
   `constitution/*.ucl` files; compile to the gate's `policy_fn`. Golden
   OpportunityPacket test (from WealthMachineIntelligence `venture_protocol`)
   must return PERMIT/DENY/ESCALATE with replayable trace. SPEC first.
2. WP-03: real adapter integration: wrap one DALEOBANKS read-only capability
   in `kernel/adapters/http_research.py` with declared egress allowlist;
   run the full loop once against reality; capture the Proof Capsule.
3. WP-04: Postgres spine backend (append-only tables) behind the same
   `Spine` interface; rebuild-from-spine drill.
Do NOT open Loom/Rabbit-Hole/Swarm work until WP-03's external loop closes.

## 7. Rollback
Delete branch `build/consequence-gate` or revert its merge commit. No
production systems consume this package yet; blast radius is zero.

## 8. Unresolved assumptions
- Founder signing key management is local test keys; hardware-backed founder
  key (per crypto roadmap) is a human action for Alfonso.
- The constitution's own ratification (status: unratified) awaits Alfonso's
  signature of constitution v1.0.0.

## 9. References
- Build orders: UNIIMENTE_FINAL_BUILD_ORDERS (Orders One, XVII).
- Spec: /mnt/agents/work/egregore-build-plan/SPEC.md (v0.1.0).
- Verifier: /mnt/agents/work/egregore-build-plan/verifier/v5 + runs/.
