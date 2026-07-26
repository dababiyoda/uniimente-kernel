# Contract Inventory

**Candidate:** `release/canonical-v1` @ `a4fa43e`. Inventory only — **no contract decisions are made in Package 1**, and no IVIO contracts are added.

## On the candidate (13 schemas)

| Schema | Class | State |
|---|---|---|
| `capability-grant` | core | Byte-identical across every branch inspected |
| `evidence` | core | Byte-identical across every branch inspected |
| `context-packet` | core | `$defs` relocated vs main — **needs compatibility test** |
| `decision` | core | `$defs` relocated vs main — **needs compatibility test** |
| `event` | core | `$defs` relocated vs main — **needs compatibility test** |
| `opportunity-packet` | core | `$defs` relocated vs main — **needs compatibility test** |
| `venture-assessment` | core | `$defs` relocated vs main — **needs compatibility test** |
| `venture-cell-charter` | core | `$defs` relocated vs main — **needs compatibility test** |
| `outcome` | core | **Settled** — two independent efforts produced byte-identical output |
| `organ-manifest` | core | Candidate-only addition |
| `egregore-cognition` | generic extension candidate | Belongs to ADE-1 |
| `wire-opportunity-packet` | venture-specific adapter | Registered peripheral wire protocol v1.1 |
| `wire-venture-assessment` | venture-specific adapter | Registered peripheral wire protocol v1.1 |

## Deliberately NOT on the candidate

| Schemas | Source | Why excluded from Package 1 |
|---|---|---|
| `ivio/v1/*` (3) | PR #45 | **IVIO is a Venture Cell.** Preserved as separate venture integration; must not enter core |
| `settlement-*`, `verified-outcome-credential`, `verifier-attestation` (5) | PR #35 | **Generic extension candidate.** Preserved inactive; may not enter core until two distinct Venture Cells need the same mechanism with no hidden domain assumptions |

## Decision rule for the six unsettled schemas

Each requires, individually, before being declared settled:

1. required-field comparison
2. allowed-value comparison
3. reference-behaviour verification
4. existing-fixture validation
5. producer and consumer identification
6. wire-compatibility preservation unless a recorded migration proves a break is necessary
7. one test per decision

**Evidence available now:** each diff versus main is confined to the `$defs` relocation, with no field, type, or requirement change. That is *supporting* evidence. It does not substitute for the seven steps, per founder correction.

## One generic item eligible for copying into core

PR #45's `tests/unit/test_contract_schema_refs.py` is domain-neutral and may be copied into core on its own merits. Package 1 ships a standalone equivalent (`scripts/ci/check_schema_refs.py`) so the baseline has the check without pre-merging #45.
