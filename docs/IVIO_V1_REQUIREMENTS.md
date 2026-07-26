# Reality Compiler requirement and invariants ledger

Status: canonical build ledger for the proof-to-settlement program
Last reconciled: 2026-07-22
Authority order: founder instruction -> Doctrine.txt -> newer proof-to-settlement blueprints -> existing ratified kernel constitution -> older exploratory egregore documents

## System objective

Build a human-sovereign institutional control plane that converts a bounded proposal into an authorized action, captures independently checkable evidence of what happened, reconciles expected and actual consequence, and only then permits settlement or another external state change.

The control point is accepted proof plus reconciliation, not model intelligence. Models and agents may sense, extract, propose, rank, and simulate. They do not become legal principals, issue their own authority, or sit directly on the settlement path.

## Single Bottleneck Metric

Number of governed IVIO cases that end in one independently verified external decision change with:

- 100% identity, legal-principal, authorization, provenance, budget, and outcome coverage;
- zero unauthorized external effects;
- no hidden manual reconstruction; and
- measured founder intervention time.

Baseline: 0.
First target: 1.

Internal test counts, generated content, simulated revenue, and UI completion do not move this metric.

## Non-negotiable invariants

1. UNAUTHORIZED_EXTERNAL_EFFECTS = 0.
2. UNIIMENTE is infrastructure, never a legal person, account owner, contracting party, or autonomous treasury principal.
3. Alfonso's reserved authority cannot be delegated, inferred, widened, or self-amended.
4. Models reason; organs propose; policies and accountable humans authorize; the Consequence Gate controls commit.
5. Every consequential instruction names a legal principal, actor identity, action, resource, parameter bounds, data rights, budget, TTL, evidence threshold, approval source, expected effect, receipt, reconciliation contract, reversibility class, compensation path, and kill conditions.
6. Approval binds to immutable compiled bytes, not mutable UI text.
7. Authority is revalidated at commit time. Expired, revoked, replayed, mutated, or mismatched authority fails closed.
8. External callbacks are evidence to reconcile, never authority to improvise.
9. Settlement cannot begin without the required proof checklist or a signed, unexpired exception decision.
10. Every duplicate delivery is harmless by construction.
11. Negative, contradictory, rejected, disputed, and invalidated evidence remains queryable.
12. LIVE, SANDBOX, SIMULATED, and PROPOSED states are explicit and cannot be silently upgraded.
13. PHI and sensitive data are referenced through minimized projections and protected storage; idempotency keys contain no personal data.
14. Cryptographic integrity proves artifact integrity and signer binding, not underlying truth.
15. Autonomy expands only for an exact action envelope after externally verified outcomes; severe failure demotes immediately.
16. No organ may alter its own authority, policy, Constitution, verifier result, or reality status.
17. Every external action path must be observable, stoppable, replayable, and recoverable.
18. If complexity does not improve externally verified outcomes or reduce founder burden, expansion stops.

## Source reconciliation

| Source idea | Disposition | Executable interpretation |
|---|---|---|
| Proof-to-Settlement Rail First | Adopted | IVIO is the first vertical; one real external acceptance precedes platform expansion |
| Reality Compiler and Institutional ISA | Adopted | Deterministic compiler produces one immutable instruction artifact and never authorizes it |
| Reality Git | Adopted incrementally | SHA-256 content binding now; object store and external checkpoint anchoring later |
| Consequence Stream | Adopted | Existing event spine becomes the only semantic state transition path |
| Capability Cells | Adopted after contract/workflow proof | Exact imports, egress, resources, secrets, identity, TTL, and kill conditions |
| Outcome credentials | Adopted | W3C VC-shaped portable outcome claims with status and evidence hashes |
| Settlement router | Adopted after payable-ready proof | Adapter-based; no custom payment rail or blockchain |
| Continuous heartbeat | Translated | Scheduled sensing, reconciliation, memory maintenance, and health checks; no prompt-free external authority |
| Metabolic energy | Translated | Compute, cash, time, and storage budgets with conservation modes; no survival objective |
| Active inference/homeostasis | Translated | Bounded control variables for anomaly, coherence, backlog, and resource pressure; cannot change facts or authority |
| Dual-tier memory/dreaming | Translated | Evidence-preserving consolidation and causal memory; raw records and contradictions never decay silently |
| Ego or unified intent | Translated | Deterministic proposal arbitration and founder-facing explanation; no consciousness claim |
| Autonomous wallet/treasury | Rejected | Accountable legal owner, explicit budget grant, dual control, reconciliation, and revocation |
| Self-preservation or immutable survival logic | Rejected | Human shutdown outranks continuity; black-start recovery preserves evidence, not autonomy |
| Self-modification | Rejected as production authority | Changes are proposed on branches, tested in twins, reviewed, ratified, and deployed through CI |
| Attention harvesting as vitality | Rejected as governing objective | Attention may be a market signal, never a survival or authority input |
| Token/NFT/DAO as core substrate | Deferred/rejected for pilot | Use only if a later shared-trust boundary proves blockchain is necessary |
| General Foundry first | Rejected | Capability Genome Foundry remains dormant until the first rail proves external acceptance |

## Dependency graph

1. IVIO v1 contracts and deterministic instruction compiler.
2. Cross-repository contract parity and generated language bindings.
3. CHARIO append-only ride events and deterministic case projection.
4. Payable-ready proof checklist plus signed exception state machine.
5. TGH-CONTROL-RAIL projection-backed Action Inbox, Trip Case, Variance Console, and Proof Packet.
6. Outcome credential issuance and verifier interface.
7. Settlement intent, idempotent adapter, receipt ingestion, and reconciliation.
8. Crash, replay, stale approval, duplicate callback, invalidation, privacy, and black-start tests.
9. One supervised live case with a named verifier and pre-agreed acceptance criteria.
10. Only after external proof: WMI branch scoring, DALEOBANKS proposal-only signals, wider cells, precedent, autonomy, Foundry, and additional rails.

No item may claim the exit evidence of a later item.

## Milestone A acceptance: canonical contracts and compiler

- One versioned schema package defines Case, OutcomeEvent, EvidenceBlob, CompiledInstruction, CapabilityGrant, ExceptionRequest, ExceptionDecision, ActionAttempt, Receipt, OutcomeCredential, SettlementIntent, SettlementReceipt, ReconciliationRecord, Invalidation, and MetricsSample.
- Draft 2020-12 schema validation passes for every object.
- Same input produces the same compiled bytes and digest.
- Any material input mutation produces a different digest.
- Unknown fields, floats, ambiguous money, missing authority, UNIIMENTE as principal, overlapping data rights, and live irreversible actions fail closed.
- The compiler cannot approve, grant, execute, mark payable-ready, or settle.
- SettlementIntent structurally requires payable-ready proof, verifier receipt, Commit Witness digest, and idempotency key.
- Negative evidence and invalidation are first-class objects.
- GitHub Actions runs the full unit suite with immutable action SHAs and read-only permissions.

## Program stop conditions

Pause expansion and preserve evidence if any of the following occurs:

- an action bypasses the Consequence Gate;
- a component widens or changes its own authority;
- an external effect lacks a named legal principal;
- a stale or mutated approval reaches execution;
- negative evidence is deleted or hidden;
- a settlement callback creates a duplicate consequence;
- a credential is treated as truth without verifier rules;
- PHI appears in an unauthorized projection or identifier;
- the founder cannot stop the affected rail; or
- six weeks of engineering produce no credible route to a named external verifier.

## External standards and security references

- [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12) defines the validation dialect.
- [CloudEvents 1.0 specification](https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md) supplies the portable event-envelope semantics used by OutcomeEvent.
- [W3C Verifiable Credentials Data Model 2.0](https://www.w3.org/TR/vc-data-model-2.0/) and [W3C Data Integrity 1.0](https://www.w3.org/TR/vc-data-integrity/) bound the OutcomeCredential envelope and proof shape; neither substitutes for verifier rules about truth.
- [RFC 8785](https://www.rfc-editor.org/info/rfc8785/) motivates invariant JSON hashing. UNIIMENTE-C14N-v1 is a narrower, separately named profile and does not claim general JCS compatibility.
- [NIST SP 800-207](https://csrc.nist.gov/pubs/sp/800/207/final) supports resource-focused, continuously evaluated access decisions rather than trust from network location.
- [GitHub secure-use guidance](https://docs.github.com/en/actions/reference/security/secure-use) supports pinning third-party Actions to full commit SHAs.
- [Stripe idempotent requests](https://docs.stripe.com/api/idempotent_requests) demonstrates provider-side retry safety; IVIO still requires its own receipt ingestion and reconciliation before institutional finality.
