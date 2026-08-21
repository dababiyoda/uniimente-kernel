# Trust Root Migration — HMAC to asymmetric

The previous witness model signed with **HMAC-SHA256 under a shared secret**, with a development fallback that was a hardcoded literal (`b"uniimente-dev-witness-key"`). Those records are institutional memory. They are not deleted. They are also not granted attribution they cannot support.

## The distinction that governs everything here

> An HMAC record can establish that a value is **consistent** with a historical shared-secret implementation.
> It cannot establish **who** produced it, because every party able to verify was equally able to produce it.

Symmetric verification and symmetric forgery are the same capability. That is not a flaw in the old implementation's coding; it is what the primitive is. Under Ed25519 the verifier holds a public key and cannot sign, so attribution becomes meaningful for the first time.

## Classification vocabulary

Implemented in [`aperture/legacy.py`](../../aperture/legacy.py) and enforced by tests.

| Classification | Meaning | May authorize a new effect |
|---|---|---|
| `LEGACY_INTEGRITY_CHECKED` | matches the historical shared secret; consistent, unattributed | **No** |
| `LEGACY_UNVERIFIABLE` | preserved and readable; the secret is gone or does not match | **No** |
| `MIGRATION_ATTESTED` | the present institution reviewed and admitted it to the record | **No** |
| `CANONICAL_ASYMMETRIC` | signed under the current Ed25519 root | Yes |

`AUTHORIZING_CLASSIFICATIONS` is exactly `{CANONICAL_ASYMMETRIC}`, asserted by `test_legacy_records_can_never_authorize`. `LegacyRecord.authorizes_new_effect()` returns `False` for every legacy classification, and `aperture.legacy` exposes no code path that returns an `AuthorizationCertificate`. The rule is structural, not procedural.

## What a migration attestation says, and what it must never say

A migration attestation records that **the current institution reviewed a historical record and admitted it**. It is a statement about the reviewer, made now.

It must never imply that the current signer witnessed the original event. The current signing key did not exist then. Re-signing an old record under the new root would manufacture exactly the false attribution this migration exists to prevent — it would look like proof and be a forgery of history.

So the attestation carries two explicit flags, both permanently false:

```json
{ "claims_original_witness": false, "confers_authority": false }
```

## Key custody, rotation, revocation

- **Custody.** `SigningProvider` is an interface. `Ed25519SigningProvider` is the in-process implementation for tests and low-risk deployments; HSM or KMS implementations satisfy the same interface without the rest of the system knowing.
- **No development fallback.** `from_env()` raises `SigningUnavailable` when the key is absent. A build that cannot find a signing key must not be able to authorize anything. Asserted by `test_defect_7_no_hardcoded_development_signing_key`, and a static check forbids key-like assignments anywhere under `aperture/`.
- **Rotation.** `VerificationRegistry.register(..., supersedes=...)` records the chain. Certificates name their `key_id`, so a certificate signed by an old key remains checkable against the key it names.
- **Revocation.** `revoke()` marks a key; verification then raises `KeyRevoked` rather than returning False, because a revoked key is an institutional condition and not a byte mismatch. Asserted by `test_key_revocation_after_issuance_refuses`.
- **Algorithm binding.** `algorithm` and `key_id` are inside the signing input, so a certificate cannot be replayed under a downgraded algorithm claim.

**Private keys are never committed.** Nothing in this repository contains key material, and the static test would fail the build if it did.

## Honest residuals

- **Custody is not deployed.** RC1's trust root is an in-process key. Until an HSM or KMS provider is wired in, concentrating authority into one key concentrates catastrophe into one key.
- **No historical records have actually been migrated.** The classification machinery is implemented and tested; it has not been run over the real ledger, because that ledger is not part of this branch.
- **The revocation window is real.** A certificate is valid for its TTL, and an effector that cannot reach the registry cannot learn of a revocation within that window. Short TTLs (default 900s) bound the exposure. This is the accepted cost of partition safety.
