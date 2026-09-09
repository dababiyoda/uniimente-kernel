# adapters — the Universal Compatibility Membrane (first ring)

Contract-version adapters between the preserved DALEOBANKS↔WealthMachine wire
protocol v1.1 and the kernel's canonical contracts. Kernel is the sole semantic owner of
bridge transport, schema validation, event identity and durable recovery. The
organs consume the pinned `uniimente-kernel-boundaries` package (0.1.1); their
local security modules are compatibility re-exports, not independent engines.

Rules every adapter here follows (Final Build Order §8):

- **Declared mapping.** `FIELD_MAPPING`, `INFORMATION_LOST`, `INFORMATION_ADDED`
  and assumptions are module-level facts, inspectable without running anything.
- **No fabricated fields.** Canonical fields the wire cannot supply
  (`budget_owner`, `governing_bottleneck`, …) come back as explicit `unresolved`
  entries; `resolve()` completes them only with an attributed institutional
  identity, and only for the named fields.
- **Identity from transport, never payload.** `created_by`/`assessed_by` derive
  from the HMAC-verified service identity. A payload cannot name its own author.
- **No authority inflation.** `requires_human_approval` stays true and
  `execution_authority` stays false; the adapter asserts them and refuses
  payloads that argue otherwise.
- **Both sides validated.** Input against the wire schema, output against the
  canonical schema. Fail closed in both directions.

Modules:

- `bridge_transport.py` — canonical exact-context HMAC and nonce verification.
  Transport protocol 2 is distinct from wire schema 1.1. Durable application
  idempotency belongs to `events/bridge_state.py`, not the transport nonce.
  Historical mirrors remain in Git; active consumers use thin re-exports.
- `contract_validation.py` — strict JSON and Draft 2020-12 schema validation,
  including required date-time format validation.
- `daleobanks_opportunity.py` — wire OpportunityPacket 1.1 → canonical
  OpportunityPacket, with `AdaptationResult` carrying the unresolved set.
- `wealthmachine_assessment.py` — wire VentureAssessment 1.1 → canonical
  VentureAssessment, mapping the adversarial committee case-for-case.
