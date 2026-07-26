# IVIO v1 proof-to-settlement contracts

This package is the canonical cross-organ language for one governed case path:

    Case -> OutcomeEvent/EvidenceBlob -> CompiledInstruction -> CapabilityGrant
         -> ActionAttempt -> Receipt -> OutcomeCredential -> SettlementIntent
         -> SettlementReceipt -> ReconciliationRecord

Exceptions and invalidations are first-class branches, not comments or mutable flags. MetricsSample makes founder sovereignty, proof quality, and settlement integrity measurable.

## Authority boundary

These schemas describe facts and proposed authority. They do not authorize external action.

- A compiled instruction is a hash-bound proposal artifact.
- An approval must bind to the compiled instruction digest.
- A capability grant is exact, expiring, revocable, non-transferable, and single-use.
- Execution still requires commit-time revalidation through the Consequence Gate.
- A receipt is evidence to reconcile, never permission to improvise.
- A settlement intent requires explicit payable_ready=true, a proof-checklist digest, a verifier receipt, and a Commit Witness digest.
- UNIIMENTE is never a legal principal.
- LIVE, SANDBOX, SIMULATED, and PROPOSED states are explicit and cannot be silently upgraded.

## Canonical integrity profile

UNIIMENTE-C14N-v1 is a deliberately narrow deterministic JSON profile:

- UTF-8;
- lexicographically sorted printable-ASCII object keys;
- no insignificant whitespace;
- safe-range integers only;
- no floating-point values;
- money in integer minor units;
- SHA-256 digest computed with the top-level integrity field omitted.

The profile is inspired by the purpose of [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785.html), but it is intentionally named separately because it narrows the accepted JSON domain and does not claim general JCS compatibility.

The Python reference implementation is reality/ivio.py. Other language implementations must pass the same wire vectors before contract parity is claimed.

canonicalization-vectors.json is the normative starter vector set. The Python and dependency-free Node verifiers both reproduce its exact UTF-8 bytes and SHA-256 digests and refuse the same out-of-profile inputs.

## Standards alignment

- JSON Schema Draft 2020-12 is the validation dialect.
- OutcomeEvent carries CloudEvents-compatible core semantics while adding legal principal, policy, causal, evidence, sensitivity, idempotency, and reality-status fields.
- OutcomeCredential uses the W3C Verifiable Credentials Data Model v2 context and a Data Integrity proof-shaped envelope.
- Cryptographic verification proves integrity and issuer binding. It does not prove that the underlying event was true.
- External callbacks and payment APIs require separate idempotency and reconciliation; provider success is not institutional finality.

## Versioning

schema.json is the only normative schema source for ivio.v1. manifest.json maps wire object_type values to definitions.

A breaking field, meaning, required property, enum, or state change requires a new major namespace. Additive changes require a new manifest version plus parity tests in every consuming organ. Unknown fields fail closed.

## Verification

Run:

~~~bash
python3 -m pytest tests/unit/test_ivio_v1.py -q
python3 -m pytest tests/unit -q
~~~

The acceptance suite proves schema validity, one valid instance per object, deterministic compilation and hashing, mutation detection, strict unknown-field refusal, explicit payable-ready gating, negative-evidence retention, and refusal of unsafe instruction forms.

## Deliberate exclusions

This milestone does not deploy a payment adapter, emit a live credential, move money, expose PHI, or activate a cell. It creates the shared language required before CHARIO, TGH-CONTROL-RAIL, WealthMachineIntelligence, or DALEOBANKS may participate in the IVIO pilot.
