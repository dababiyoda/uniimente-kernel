# adapters — the Universal Compatibility Membrane (first ring)

Contract-version adapters between the preserved DALEOBANKS↔WealthMachine wire
protocol v1.1 and the kernel's canonical contracts, plus the kernel-side mirror of
the organs' bridge transport security.

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

- `bridge_transport.py` — third mirror of the organs' `bridge_security.py`
  (HMAC, nonce replay guard, skew window, idempotency, version floor), adding
  `kernel` to the known identities. Peers adding `kernel` to their mirrors is a
  recorded cross-repo dependency, not assumed.
- `daleobanks_opportunity.py` — wire OpportunityPacket 1.1 → canonical
  OpportunityPacket, with `AdaptationResult` carrying the unresolved set.
- `wealthmachine_assessment.py` — wire VentureAssessment 1.1 → canonical
  VentureAssessment, mapping the adversarial committee case-for-case.
