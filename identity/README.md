# identity

Layer 2 — Machine Identity and Authority. SPIFFE-style machine passports for
every process, agent, workflow, connector, organ, and Venture Cell.

The separation (non-negotiable): identity ≠ authority ≠ legal responsibility
≠ capability ≠ budget ≠ consequence. A passport proves what a thing is. It
never grants what it may do. Authority arrives only through a CapabilityGrant
evaluated against compiled constitutional policy.

## Files

- `organ-registry.yaml`, `agent-registry.yaml`, `service-identities.yaml` — registries (Phase 1)
- `machine_passport.py` — executable passport system (this build)

## Interface

- `PassportRegistry.issue(kind, creator, owner_organ, legal_principal, declared_capabilities, budget_ceiling_usd, consequence_class, ttl_seconds=None) -> MachinePassport`
- `PassportRegistry.verify(passport_id, at=None) -> (bool, reason)` — identity check only; never an authorization decision
- `PassportRegistry.inspect(passport_id) -> dict` — the six questions: what it is, who created it, which organization owns it, what it may do, which entity bears liability, when its authority expires
- `PassportRegistry.revoke(passport_id, reason, revoker)` — immediate

`MachinePassport.authority` is always `None` by construction.

## Buildability standard (14 conditions)

- **Existing mechanism**: registry + short-lived credentials (SPIFFE/SPIRE pattern).
- **Defined interface**: issue/verify/inspect/revoke, typed dataclass, RFC 3339 timestamps.
- **Bounded authority**: zero. Passports cannot authorize; `authority` is `None` by construction.
- **Available dependencies**: Python 3 stdlib only.
- **Security model**: short TTLs (registry ceiling), immediate revocation, `UNIIMENTE` refused as legal principal, unknown identities fail closed.
- **Failure modes**: unknown identity, expired passport, revoked passport, TTL overflow, prohibited principal — all explicit, all fail closed.
- **Acceptance tests**: `tests/unit/test_identity.py`.
- **Recovery path**: reissue; passports are ephemeral by design and never primary state.
- **Resource ceiling**: TTL ceiling (default 3600s); in-memory registry bounded by issuance rate.
- **Operating cost**: O(1) issue/verify; zero external calls.
- **Legal operator**: the legal principal named on each passport (never the institution itself).
- **Handoff state**: `to_dict` serializes every passport; registry state is reconstructable from the ledger of issuances.
- **Replaceable**: swap for SPIRE issuance later; the verify/inspect contract is the stable interface.

## Orthogonal closures

Verified by `closure/kernel_registry.py` → module `identity`.
