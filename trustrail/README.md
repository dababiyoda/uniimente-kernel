# Proof-to-Settlement Trust Rail

This module turns a reconciled Consequence Gate action into independently
verified proof, a narrowly authorized settlement, and context-scoped
reputation. It is the executable back half of:

`identity -> permission -> action -> proof -> payment -> reputation`

It does not claim that a cryptographic signature makes an off-chain fact true.
An independently ratified verifier must attest to the exact outcome and receipt;
the credential preserves who made that claim and what evidence they cited.

## What is executable now

- `CredentialIssuer` binds one ledgered action, witness, receipt, reconciled
  outcome, policy version, verifier signature, and evidence set.
- `SettlementRouter` requires a legal-principal authority signature, exact
  payer/payee/currency/purpose/adapter/reality binding, amount ceiling, expiry,
  and commit-time credential revalidation.
- `SandboxSettlementAdapter` proves idempotency and reconciliation without moving
  money. `LIVE` is structurally unsupported.
- `ScopedReputationLedger` records evidence only after reconciliation and only
  inside an exact actor/action-class/principal/reality scope. It produces no
  universal reputation score.
- `OpenClawTrustBoundary` selects only pre-registered executors and exposes no
  settlement-commit tool.
- Disputes suspend credentials immediately. Invalidation revokes proof; it does
  not pretend that an already completed external transfer can be erased.

The credential envelope is compatible with the shape of W3C Verifiable
Credentials 2.0, but the development HMAC proof is not a W3C Data Integrity
conformance claim. `contracts/trustrail-v1.context.jsonld` defines the custom
terms; production must inject asymmetric or KMS-backed signers and publish that
context plus a durable status service at the declared schema origin.

## Buildability declaration

| Condition | Declaration |
|---|---|
| existing mechanism | Uses the existing Consequence Gate, Commit Witness, Evidence Ledger, receipts, outcomes, and closure registry. |
| defined interface | Typed Python dataclasses and five JSON Schema contracts define verifier, credential, authorization, intent, and receipt boundaries. |
| bounded authority | Verifiers and settlement signers are human-ratified, scoped, expiring, revocable, and rechecked at commit. |
| available dependencies | Core uses the Python standard library and existing kernel modules; the OpenClaw adapter optionally pins `mcp>=1,<2`. |
| security model | Zero implicit trust, independent verification, deny-by-default adapters, exact effect binding, idempotency, status suspension, and append-only evidence. |
| failure modes | Missing/tampered/expired proof, self-verification, scope mismatch, amount overflow, replay, disputed credential, and bad adapter receipts fail closed. |
| acceptance tests | Unit and adversarial tests cover the full sandbox lifecycle, JSON contracts, no-effect refusals, replay, disputes, and OpenClaw isolation. |
| recovery path | Resolve a dispute as upheld or invalidated; retry failed idempotent submissions; inspect the ledger before introducing a replacement adapter. |
| resource ceiling | In-memory registries are bounded by the host process; each lifecycle appends a small fixed set of records and performs no unbounded search outside the ledger. |
| operating cost | The sandbox adapter costs no money; production signing, storage, verification, and settlement fees must be budgeted per adapter. |
| legal operator | Every settlement binds an explicit legal principal. UNIIMENTE itself is never treated as the liable person. |
| handoff | An operator can replace signers, verifier registrations, adapters, and the MCP host through the documented constructor interfaces. |
| replaceable | All external execution is behind a narrow adapter protocol; blockchain or fiat settlement can be added without replacing policy or evidence. |

## Non-negotiable production gates

Do not install a live adapter until all of the following are independently
reviewed: legal entity/account ownership, KMS or hardware-backed asymmetric keys,
human identity and MFA, durable transactional storage, concurrency control,
secret management, adapter-specific reconciliation/webhook verification,
currency precision, sanctions/fraud controls where applicable, incident response,
backup/restore, external security review, and a live canary with a hard monetary
ceiling and kill switch.

Blockchain remains optional. A shared-trust use case may anchor hashes or settle
through a smart contract, but an oracle/verifier is still required for physical
facts. DAO governance is likewise optional and cannot replace the named legal
principal or the human sovereignty boundary.
