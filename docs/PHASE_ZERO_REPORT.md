# Phase Zero Report — Institutional Connection and Capability Preservation

Date: 2026-07-20. All claims below have executable evidence (test runs recorded in
the organ manifests) or name the exact missing dependency. Nothing was deleted.

## Evidence-based current state (as found)

| Organ | Commit | Tests | State as found |
|---|---|---|---|
| uniimente-kernel | `3d9b577` | 170/172 → **172/172** | 2 tests failed on the shipped tree: `contracts/outcome.schema.json` (and 6 more contracts) had `$defs` nested inside `properties`, so every `#/$defs/hash` reference resolved to nowhere. Fixed in place; all 9 contracts now pass Draft 2020-12 schema checks. |
| DALEOBANKS | `829c5f2` | **293/293** | Green once `requirements.txt` deps and any `OPENAI_API_KEY` value are present (suite runs offline in dry-run mode). |
| WealthMachineIntelligence | `6549984` | **41/41** | Green once deps installed (tensorflow/transformers not required by the suite). |

**Key discovery:** Bridge A's periphery already exists and is real. DALEOBANKS ships
a signed bridge client (`services/wealthmachine_client.py`) and WMI ships the signed
intake (`src/services/opportunity_intake.py`), sharing mirrored
`bridge_security.py` / `venture_protocol.py` modules (verified field-for-field
compatible in-session; only docstrings differ). What was missing was the **kernel's
end**: no kernel identity in the transport, no typed bridge contracts in the kernel,
no adapter between the wire protocol and the canonical contracts, and no recorded
cross-organ causal episode.

**Overlapping authority found (preserved, not deleted):** DALEOBANKS
`services/constitution.py` and WMI `src/services/risk_management.py` are organ-local
governance implementations. Both are registered `SPECIALIZED` in their manifests and
flagged by the linker as overlapping authority; the kernel control plane remains the
canonical authority path.

## What Phase Zero built (this PR)

- **Doctrine installed**: `CLAUDE.md` (permanent operating order) importing
  `docs/UNIIMENTE_FINAL_BUILD_ORDER.md` (preservation + integration override) and
  `docs/CANONICAL_EXECUTION_ORDER.md` (execution/reconciliation order).
- **Contract repairs**: misplaced `$defs` fixed in 7 canonical schemas.
- **Wire protocol formalized, not replaced**: `contracts/wire-opportunity-packet.schema.json`
  and `contracts/wire-venture-assessment.schema.json` register the organs' existing
  v1.1 protocol as typed, preserved peripheral contracts.
- **Organ Manifests** (`organs/*.manifest.yaml` + `contracts/organ-manifest.schema.json`):
  evidence-grounded self-descriptions of all three organs — capabilities with source
  commits and lifecycle states, contracts consumed/produced, prohibited actions,
  authority ceilings (`may_self_promote` is unrepresentable as true), verified test
  counts, and explicit `unresolved` questions.
- **Institutional Linker** (`linker/`): resolves typed edges from manifests using the
  contracts directory as the only contract registry; reports untyped references,
  disconnected edges, open questions, and overlapping authority. Registered as the
  14th kernel module in the five-closure registry.
- **Compatibility membrane, first ring** (`adapters/`):
  - `bridge_transport.py` — third mirror of the organs' transport security, adding
    the `kernel` identity;
  - `daleobanks_opportunity.py` — wire→canonical packet adapter with declared field
    mapping/loss/assumptions; missing underwriting facts return as explicit
    `unresolved` fields, resolvable only by an attributed institutional identity;
  - `wealthmachine_assessment.py` — wire→canonical assessment adapter mapping the
    adversarial committee case-for-case; refuses authority inflation and truncated
    committees.
- **Executable fixtures** (`tests/fixtures/`): wire packet + assessment produced by
  running DALEOBANKS's own protocol and scorer in-session (provenance recorded).
- **One complete causal episode** (`tests/integration/test_phase_zero_connection.py`):
  signed DALEOBANKS packet → verify → adapt → attributed human resolution → signed
  WMI assessment → adapt → outcome → `CausalMemory.ancestry` reconstructs the full
  four-event chain on a verifiable ledger. 21 integration/adversarial tests; full
  suite 193/193.

## Phase Zero exit evidence

- No implementation deleted anywhere (kernel diff is purely additive except the
  7-schema `$defs` repair).
- Every meaningful cross-organ contract is typed; the linker reports zero untyped
  references over the real manifests.
- Overlapping authorities identified and governed (SPECIALIZED + linker flag).
- One complete three-organ workflow recorded as a causal episode with a green,
  tamper-evident ledger chain.

## Exact blockers (external dependencies — all technical preparation done)

1. **Peer-repo change**: DALEOBANKS and WMI must add `"kernel"` to
   `KNOWN_IDENTITIES` in their `bridge_security.py` mirrors before kernel-signed
   messages verify on their side. One-line change per repo; recorded in both
   manifests as `unresolved`.
2. **Constitutional ratification** of the doctrine documents by the founder.
3. **Credentials**: `WEALTHMACHINE_SIGNING_KEY` shared secret for production
   transport; platform credentials for DALEOBANKS live mode; a deployed
   `WEALTHMACHINE_URL` for http (non-mock) bridge mode.
4. **External consequences** (payments, customer actions, live posting) require the
   above plus human authorization at the consequence gate.

## Next gates in dependency order

1. Bridge B (Venture-to-Experiment): assessment → strategy tree → spider-web audit
   → ExperimentSpec → capability grant, inside the kernel (all components exist;
   the composition and tests do not yet).
2. Kernel-side intake service exposing the verified-transport + adapter path as an
   actual endpoint (embassy pattern), so organs can deliver instead of tests.
3. Capability discovery service over the manifests (linker already provides the
   read model).
4. Peer-repo PRs: add kernel identity; anchor organ-local ledgers to the kernel
   evidence chain.
