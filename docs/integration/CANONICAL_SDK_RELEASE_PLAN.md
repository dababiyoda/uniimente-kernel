# Canonical Kernel SDK Release Plan — `uniimente-kernel-sdk v0.1.0`

## Purpose

Break the mutual branch pin. Organs currently depend on a kernel *branch tip*; neither side can land without breaking the other. A versioned, signed artifact ends that.

## The design constraint that shapes everything

Main's `policy/consequence_gate.py` (355 lines) is **larger and more developed** than the SDK's `gate.py` (254). Same for `events/spine.py` (320) vs `events.py` (259).

**Merging the SDK unmodified would put two gate engines in one repository** — the multiple-active-authority condition, arriving by merge instead of by drift.

> **The SDK is a client. It is never a second engine.**

Where the SDK is ahead (`ledger.py` 272 vs 120, `commit_witness.py` 245 vs 122), the *implementation moves into the canonical root package*. It does not live in two places.

## Release contents — minimum for the first governed transaction

| Module | Role | Backed by |
|---|---|---|
| `contracts.py` | typed objects: identity, principal, evidence, decision, grant, witness, receipt, reconciliation | `contracts/*.schema.json` |
| `gate.py` | **thin client** — proposes to the gate, never decides | `policy/consequence_gate.py` |
| `capability.py` | grant construction + client-side validation | `policy/engine.py` |
| `approval_queue.py` | `ApprovalRequest` distinct from `CapabilityGrant` | new; prior art in DALEOBANKS |
| `commit_witness.py` | witness construction | canonical implementation |
| `events.py` | **thin client** over the spine | `events/spine.py` |
| `ledger.py` | append/verify client | `provenance/ledger.py` |
| `refusal.py` | local veto + degraded-mode interfaces | `constitution/shutdown-policy.ucl` |

**Excluded from v0.1.0**, present on `phase7` but not required for the first transaction: `evolution.py`, `evolution_loop.py` (Track B adjacent), `prompt_firewall.py`, `raw_vault.py`, `heartbeat.py`, `context_packet.py`, `constitution_check.py`. Each is justified on its own merits later. **Do not ship a module because it exists.**

## Versioning and compatibility

- **0.x** — public interface may change on minor; organs pin `==0.1.0` exactly.
- **1.0** — after the first governed transaction, contracts frozen; additive changes bump minor, field removal or enum narrowing bumps major and requires an adapter in `adapters/` declaring information lost.
- **Deprecation** — two minor versions' notice; no silent removal.
- **Provenance** — release cut from a tagged commit on `integration/canonical-v1`; artifact checksum recorded; reproducible from the tag.
- **Rollback** — organs revert to the prior pin. Since the current pin is a branch tip, the first rollback target is `sdk-v0.1.0` itself; there is no earlier version, which is stated rather than hidden.

## Packaging question — unresolved

`sdk-python/` inside the kernel repository is a vendored client of the repository it lives in. That is a real smell.

- **For:** organs need a pip-installable artifact without cloning the kernel; a subdirectory install already works and is what `phase5` pins.
- **Against:** two import paths for one mechanism inside one tree invites exactly the duplication this plan exists to prevent.

**This is Founder Decision B.** The plan is written to work either way: if the SDK stays a subdirectory, the thin-client constraint is what keeps it honest.

## Gate conditions before cutting the tag

1. 679-test merge reproduced on the integration branch.
2. The 65-test delta reconciled (560 + 184 = 744 ≠ 679).
3. Exactly one gate engine in the tree.
4. Exactly one event spine.
5. Grant-namespace collision between SDK and `DALEOBANKS/services/capability.py` ruled out.
