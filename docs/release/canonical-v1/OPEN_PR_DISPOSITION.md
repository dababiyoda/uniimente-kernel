# canonical-v1 — Open Pull Request Disposition

21 pull requests remain open at the release commit (#50 merged during this
work). **Nothing here is closed, merged, deleted, or rewritten.** Disposition is
a classification, not an action.

A note on method: none of these branches is a commit-ancestor of
`release/canonical-v1`. For the phase/build stack the *content* is nonetheless
present (`policy/consequence_gate.py`, `compiler/ucl_compiler.py`,
`events/spine.py`, `provenance/commit_witness.py`, `sdk-python/` all exist at the
release commit) — it landed through the integration line rather than by merging
these branches. That is precisely "superseded but preserved": the capability
arrived by another path, and the branch is retained as lineage.

## Canonical release surface

| PR | Branch | Note |
|---|---|---|
| **#47** | `release/canonical-v1` → `main` | The release PR. Draft. Merge into `main` NOT authorized. |

## Superseded but preserved — the phase/build development stack

Content present at the release commit; commits are not ancestors. Retained as
institutional memory and historical replay targets per build order §2, §9, §12.

| PR | Branch |
|---|---|
| #11 | `phase2/decision-ledger-extraction` |
| #12 | `phase2/raw-vault-capability-extraction` |
| #13 | `phase2/firewall-context-extraction` |
| #14 | `phase2/guard-heartbeat-approval-extraction` |
| #15 | `phase2/sdk-packaging` |
| #16 | `phase2/sdk-package-absorption` |
| #17 | `phase3/signal-contracts` |
| #18 | `phase4/event-spine` |
| #19 | `phase4/commit-witness` |
| #21 | `build/consequence-gate` |
| #22 | `phase5/consequence-gate` |
| #23 | `phase6/first-evolution-cycle` |
| #24 | `build/ucl-compiler` |
| #25 | `phase7/fast-capability-evolution` |
| #20 | `docs/egregore` (documentation) |
| #44 | `claude/disruptive-design-configs-hi1ab0` — founder-ruled split; findings absorbed into `developmental/`; the duplicate `morphogenesis/` package deliberately not merged |

## Historical fallback — evidence-bearing

| PR | Branch | Why |
|---|---|---|
| #26 | `build/real-adapter-loop` | Carries the single recorded **Verified Mediated External Effect** (real HTTPS GET, receipt `05d804016bee…`, `verify_chain: true`). Preserved as the external-consequence evidence record. Not a Clean Verified Outcome. |

## Venture Cell candidates — registration proposals, not activations

| PR | Branch | State |
|---|---|---|
| #45 | `build/ivio-v1-contracts` | IVIO v1 contracts. **Not integrated.** `IVIO_NEMT_LLC` jurisdiction unconfirmed; may not contract or receive data. |
| #46 | `agent/register-pumpstation-venture-cell` | Proposes an **inactive** PumpStation cell. Not registered in `identity/`, `authority/` or `integration/`. |

## Prohibited from canonical integration

| PR | Branch | Why |
|---|---|---|
| #35 | `agent/proof-to-settlement-trust-rail` | Settlement rail. Settlement activation is explicitly prohibited; this cannot enter a Kernel release. Preserved, not closed. |

## Integrated

| PR | Package | Merge commit |
|---|---|---|
| #48 | Package 2 | `cb234faf932d239d79b0e7ab28e54f576b8a15bf` |
| #49 | Package 3 | `5e02e47f604770fdee2c05b25418ef003f5b2b92` |
| #50 | Package 4 | `526e320475d7b1175c546d48147f9f49f53831e1` |

## Deferred

None. Every open PR falls into a category above.
