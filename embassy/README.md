# embassy

Layer 7 — the Agent Embassy: foreign agents (MCP/A2A) present here, never inside.

## Organs

- `gate.py` — `AgentEmbassy`: `present()` admits a foreign agent as a
  guest with a short-lived `connector` passport — minimum privilege by
  construction: zero budget, consequence ceiling `internal_write`,
  TTL ≤ 3600s, identity carrying zero authority. `request()` re-expresses
  every guest request as a Proposal routed through the Consequence Gate;
  anything beyond the ceiling (external_contact, financial,
  irreversible) or above zero budget is refused at the embassy, before
  the gate is consulted. Revoked guests are refused instantly.

## Recorded proof

`tests/unit/test_embassy.py` (7 tests): minimum-privilege passports,
TTL clamping, admission ledgered, read-only request through the real
gate to `recorded`, external-contact and cost-bearing requests refused
at the boundary, revoked guest refused.

## Buildability standard (14 conditions)

- **Existing mechanism**: API gateway + guest tenancy + short-lived credentials — standard, no novel science.
- **Defined interface**: `present(...) -> passport`; `request(passport_id, proposal, executor) -> ActionRecord`.
- **Bounded authority**: guests hold none; the embassy grants nothing beyond a passport; the Consequence Gate remains the sole path to effects.
- **Available dependencies**: `identity.machine_passport`, `policy.consequence_gate`, `provenance.ledger`.
- **Security model**: ceiling + zero-budget enforced before gate consultation; refusal ledgered; TTL clamped; revocation instant.
- **Failure modes**: `EmbassyRefused` (invalid identity, class above ceiling, budget above zero, admission failure).
- **Acceptance tests**: `tests/unit/test_embassy.py` (7 tests).
- **Recovery path**: guest passports expire within an hour; revocation is immediate; no cleanup debt accumulates.
- **Resource ceiling**: one passport per admission; ledger appends per admission/request.
- **Operating cost**: constant per request; gate does the heavy lifting.
- **Legal operator**: Alfonso (legal principal for admitted guests; the institution never is).
- **Handoff state**: ledgered admission + routing records reconstruct all guest traffic.
- **Replaceable**: passports, gate, ledger all injected; ceilings are module constants.

## Orthogonal closures

Verified by `closure/kernel_registry.py` → module `embassy`.
