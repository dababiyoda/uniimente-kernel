# ChatGPT brief — Opus Maximus Part 2

This document is a convenience. **`handoff/contract.json` is canonical.** Where the
two disagree, the contract wins.

## Where to work

| | |
|---|---|
| Repository | `dababiyoda/uniimente-kernel` |
| Branch | `claude/opus-maximus-audit-eay0ek` |
| Base | `main` @ `8cb3074a4a837c89aada9bdb5351d7d9b3e4a9c1` |
| Part 1 head SHA | recorded in `handoff/SEAL.json` as `frozen_at_commit` |
| Contract | `handoff/contract.json` |
| Schemas | `handoff/schemas/*.schema.json` |
| Vectors | `handoff/vectors/*.json` |
| Bundle manifest | `handoff/BUNDLE_MANIFEST.json` |
| Seal | `handoff/SEAL.json` |
| Conformance | `python -m handoff.conform` |

Peer repositories, same branch name: `dababiyoda/DALEOBANKS` (base `1ba3b85`) and
`dababiyoda/WealthMachineIntelligence` (base `6549984`). Both received a one-line
transport-identity change and one narrow fail-closed test. Nothing else.

## Verify the seal before you build

```bash
git fetch origin claude/opus-maximus-audit-eay0ek
git checkout claude/opus-maximus-audit-eay0ek
pip install -r requirements-dev.txt
python -m handoff.conform
```

The seal is a **bundle** seal. `handoff/BUNDLE_MANIFEST.json` lists sorted
path + SHA-256 for every contract file, every schema, every vector, and the three
pre-existing canonical schemas the bundle depends on. The bundle digest is the
SHA-256 of that manifest file's bytes. `handoff/SEAL.json` records commit A's SHA
plus that digest — a second commit, because a file cannot contain the SHA of the
commit containing it. Conformance verifies both halves and refuses if any sealed
file drifted.

If `python -m handoff.conform` does not print `CONFORMANT`, stop and report it.
Do not build against a bundle that does not verify.

## What Claude built

- **`blueprint/`** — the Opus Maximus hardening ladder over the 55-technology
  Foundry arsenal. Six rungs (`BLUEPRINT → SKETCHED → BUILT → EXERCISED → PROVEN →
  HARDENED`) and a separate reality axis (`BLUEPRINT_ONLY | SIMULATED |
  IMPLEMENTED`). Every evidence reference resolves against the real tree or the
  rung is refused. `python -m blueprint` prints the ladder, the unblocked frontier
  ranked by leverage, and what is blocked by which dependency.
- **`discovery/`** — Capability Discovery Service (#27). Read-only over
  `organs/*.manifest.yaml`. Discovery does not grant access; an AST test enforces it.
- **`knowledge/`** — Institutional Knowledge Graph (#18). A node with no provenance
  is structurally unconstructible.
- **`routing/decision_router.py`** — decision-only selector (#25). Returns a
  `RoutingDecision`; never invokes a provider. **Read BLK-1 before touching this.**
- **`organs/pumpstation.manifest.yaml`**, **`organs/research-in.manifest.yaml`** —
  two organs the linker previously could not see.
- **`closure/nervous_system_registry.py`** — five closures for each of the four.

## What you build

Your paths, per the ownership matrix. Nothing outside them.

| Component | Tech | Path | Frozen interface |
|---|---|---|---|
| Governed module loader | FBO §4.4 | `moduleloader/` | `discovery.service.CapabilityDiscoveryService.lookup` / `.offers`; `handoff/schemas/capability-request.schema.json`. Must support inspect, validate, install, attach, activate, pause, shadow, compare, replace, rollback, detach, export-state, import-state, archive, restore. |
| MCP boundary | #28 | `boundary/` | `handoff/schemas/boundary-envelope.schema.json`, `protocol: "mcp"` |
| A2A boundary | #29 | `boundary/` | same schema, `protocol: "a2a"` |
| Containment tiers | #9, #10, #11 | `containment/` | `handoff/schemas/containment-requirement.schema.json` |

Report your work as `handoff/schemas/evidence-record.schema.json` documents, one per
component, each citing the bundle digest.

## Invariants you must not weaken

INV-1 through INV-7 in the contract, in full. The short form:

- Authentication is not authorization. A perfectly signed envelope has zero authority.
- Inbound becomes a **proposal**. There is no execute path from the boundary.
- Unknown organ, unknown capability, unknown protocol version → **rejected**, never
  approximated and never downgraded. Exact version match, both directions.
- No arbitrary dynamic imports. Pinned allowlist, checked before any import runs.
- No external consequence without a founder-approved, narrow, revocable capability
  plus Kernel authorization at the Consequence Gate.
- No module attaches itself, activates itself, widens its own authority, alters its
  own approval requirements, prevents detachment, hides state, or resists shutdown.
- Isolation that is only a policy check must say `enforcement_kind: policy_only`.
  Report `granted_tier: UNAVAILABLE` rather than claiming a tier the host lacks —
  your existing scaffold already does this correctly and should keep doing it.

## Known blockers — read these before claiming anything

**BLK-1 — the canonical selector is unresolved.** You were right. `capabilities/router.py`
in draft PR #70 has `resolve()` returning `chosen.provider()`, which instantiates code
and does not satisfy the decision-only invariant. Claude's `routing/decision_router.py`
is decision-only and AST-asserted. **Both are preserved; neither is promoted.**
Technology #25 is **not closed**, and no conformance report may say it is. The
migration path, if the founder makes the decision router canonical: `resolve()` moves
out of the router to a caller holding a grant, `select()` becomes a decision-only
adapter, and PR #70's lifecycle machinery (`Implementation.origin`, `LIFECYCLES`,
`restore`, `set_lifecycle`) is rehomed rather than discarded. Founder decision.

**BLK-2 — CONTRADICTION-0001.** The sealed Package 3 repair experiment measures
`organs/*.manifest.yaml` as a live glob and pins `unresolved_count = 7`. Publishing
the two approved manifests takes it to 17, failing 20 tests. No sealed file was
modified. `python -m pytest` on this branch is **541 passed, 20 failed**, and all 20
are this. See `docs/CONTRADICTION-0001-live-corpus-vs-organ-growth.md` for the three
options and their costs. Founder decision.

**BLK-3 — the shared HMAC secret.** All three bridge mirrors share one
`WEALTHMACHINE_SIGNING_KEY`. Adding `"kernel"` to `KNOWN_IDENTITIES` makes it a
*recognized claimed identity*, not a cryptographically isolated per-service identity:
any holder of the shared secret can assert any known identity. Per-service keys or
mTLS is recorded as a hardening step under technologies #7 and #26. Do not describe
the transport as providing per-service identity isolation.

**BLK-4 — organ status vocabulary.** `contracts/organ-manifest.schema.json` admits
only `active | planned | this_repository`. It cannot express "code exists in a real
repository, but the organ is registered and not attached". Both new manifests record
`planned` plus the contradiction under `unresolved`. Widening the enum is a contract
change and needs the founder.

**BLK-5 — organ counting.** You were right about this too. There are **five** organ
manifests, not six: three on `main` plus PumpStation and RESEARCH-IN. Separately,
`identity/organ-registry.yaml` registers **eight** organ identities, of which five
have no manifest, while the two new manifests have no identity registration. Run
`CapabilityDiscoveryService().identity_reconciliation()` for the exact split. A
manifest is **discovery-only**: it implies neither institutional identity nor
activation. Never write "all six organs resolve".

**BLK-6 — cross-repository evidence binding.** Blueprint evidence locators are
kernel-relative, so capabilities implemented in DALEOBANKS and WealthMachine cannot
be bound to an implementation path from here. They stand at `BLUEPRINT` in the ladder
even where real code exists. Claude owns this gap.

## Merge order

1. `uniimente-kernel` — this bundle and the Part 1 components. Shared source of truth.
2. `DALEOBANKS` — transport identity only.
3. `WealthMachineIntelligence` — transport identity only.
4. Your Part 2 — opens only after the kernel branch exists and your conformance
   report cites this bundle's digest.

## Acceptance

Your return is accepted when the conformance report references the frozen bundle
digest from `handoff/SEAL.json` **and** every acceptance vector passes — or names the
exact unsatisfied vector without weakening it.

Editing a vector to make it pass, editing a schema to admit a payload it previously
refused, claiming a rung above what the evidence resolves, or claiming technology #25
closed are all conformance failures.
