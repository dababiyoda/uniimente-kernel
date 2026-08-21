# Key Custody Readiness

**PRODUCTION custody is disabled in this pass and cannot be enabled by code on this branch.**

## Environments

| | ephemeral keys | institutional authority | external effects |
|---|---|---|---|
| `TEST` | allowed | no | no |
| `DEVELOPMENT` | allowed | no | no |
| `SHADOW` | **refused** | no | no |
| `PRODUCTION` | **disabled** | — | — |

`SHADOW` refuses generated keys deliberately: a shadow run must use an auditable key identifier so its signatures can be traced afterwards. A key that vanishes when the process exits cannot be audited.

## Enforced by tests

- `Ed25519SigningProvider.generate(..., environment=SHADOW)` raises `ephemeral_key_refused`
- a `test-` prefixed key id refuses to load outside `TEST` (`test_key_outside_test`)
- `PRODUCTION` raises `production_custody_disabled` at both construction and `from_env()`
- missing signing infrastructure raises `SigningUnavailable` — **there is no development fallback key**, unlike the previous signer's hardcoded `b"uniimente-dev-witness-key"`
- `VerificationRegistry` has no `sign` method and stores public key bytes only; a static test fails the build if any signing surface appears on it
- a static test fails the build on key-like assignments anywhere under `aperture/`

## Blockers before PRODUCTION may be enabled

Each requires a decision or an artifact that no build session can supply.

1. **Custodian** — a named legal or operational holder of the private key. This is a legal decision.
2. **HSM or KMS provider** implementing `SigningProvider`. The interface exists; no implementation does.
3. **Rotation procedure** — the registry supports `supersedes` chains; the operational runbook does not exist.
4. **Revocation distribution** — how signed snapshots reach effectors in production.
5. **Backup and recovery** — what happens when the key is lost, not merely compromised.
6. **Compromise procedure** — who declares it, who publishes the revocation, what happens to in-flight certificates.
7. **Founder authorization** — separate and explicit.

Until all seven exist, RC1's trust root is an in-process key and the architecture is a candidate, not a deployment.
