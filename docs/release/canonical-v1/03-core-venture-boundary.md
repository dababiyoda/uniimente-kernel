> Edited historical extract, 2026-09-15: retired-domain references removed by founder instruction. This is not an unchanged release record or a description of current registrations.

# Core versus Venture Boundary Report

**Candidate:** `release/canonical-v1` @ `a4fa43e` (baseline CI at `8b55efa`)
**Rule being enforced:** UNIIMENTE may create and govern ventures. No venture may define UNIIMENTE.
**Machine-readable form:** `boundary.json` in this directory.

---

## Headline finding


**The deepest core is clean.** `tests/unit/test_closure.py`, `test_consequence_gate.py`, and `test_capabilities.py` contain zero healthcare assertions. Constitution, authority, gate, events, provenance, and memory carry no business logic.

This edited extract does not restore deleted material or authorize a venture.

---

## Classification of every top-level path

| Path | Class | Note |
|---|---|---|
| `constitution/` | **core** | 5 `.ucl` files, single supreme law |
| `authority/` | **core** | Registry is core; venture *entries* are data (see below) |
| `identity/` | **core** | Same — generic registries, venture rows |
| `policy/` | **core** | Single Consequence Gate |
| `events/` | **core** | Event spine. `\btrip\b` match was "round-trip" — false positive |
| `provenance/` | **core** | Evidence ledger, Merkle checkpoints |
| `memory/` | **core** | Causal memory |
| `capabilities/` | **core** | Capability genomes |
| `autonomy/` | **core** | A0–A8 ladder |
| `embassy/` | **core** | Foreign-agent admission |
| `affect/` | **core** | Bounded control states |
| `capital/` | **core** | Generic resource control |
| `compiler/` | **core** | UCL compiler |
| `loom/` | **core** | Workflow patterns |
| `twins/` | **core** | Counterfactual forks |
| `evolution/` | **core** | Improvement cycle |
| `closure/` | **core, CONTAMINATED** | See leakage L1, L2 |
| `verifier/` | **core** | V1–V5 |
| `observability/`, `sandbox/` | **core** | Build targets |
| `sdk-python/`, `sdk-typescript/` | **core** | Organ integration |
| `developmental/` | **developmental research** | MICA/CDPE TARGET_FORM_001 |
| `morphogenesis/` | **core + CONTAMINATED** | Engine/contracts are core; see L3 |
| `foundry/` | **generic extension candidate** | Must prove genericity before entering core |
| `omnimorph/` | **generic extension candidate** | Same |
| `business/` | **generic extension candidate** | Same |
| `egregore/` | **generic extension candidate** | ADE-1 standing cognition |
| `adapters/` | **venture-specific adapter** | Correct location for domain translation |
| `linker/` | **core** | Cross-organ edge resolution |
| `organs/` | **core** | Organ manifests |
| `integration/` | **CONTAMINATED manifest** | See L4 |
| `contracts/` | **mixed** | See contract inventory |
| `tests/` | **mixed** | Core tests clean; foundry/omnimorph tests carry domain fixtures |
| `docs/` | **mixed** | 7 of 12 mention a venture domain |
| `scripts/ci/` | **core** | Added by Package 1; fully generic |

---

## Named leakage

### L1 — `closure/advantage_registry.py` · core path, healthcare defaults

```
buyer="facility CFO", beneficiary="patient", pain_owner="case management",
budget_owner="facility CFO", mandate_actor="compliance executive",
recurring_transaction="patient transport discharge"
```

A core closure module carries a specific industry's roles as in-code values. Even as examples, these teach every future reader that the core assumes a healthcare buyer.

**Severity: high** — it is core code, not documentation.
**Disposition:** parameterise, moving the healthcare instance into a venture fixture. Not in Package 1.

### Removed historical entries

Retired-domain findings and former registry descriptions were deleted under the
founder cleanup instruction. Consult the current registries for current state.

---

## The one legitimate prohibited record

`authority/legal-principals.yaml` contains:

```yaml
UNIIMENTE:
  type: not_a_legal_actor
  status: prohibited
```

Enforced structurally by the UCL compiler invariant `never_uniimente_principal`. This is an **actual rejection with lineage**, not an invented entry — a proposal that UNIIMENTE could be a legal principal was considered and refused. It qualifies for the Founder Intent Ledger's `prohibited` state under the stated criterion.

---

## What this means for the corrected build

The corrected order is achievable: the core's *governing* layers are already venture-neutral. Contamination sits in one closure module, one registry demo line, one setpoint file, and one manifest — not in the Constitution, the gate, identity, authority, events, provenance, or memory.

**No remediation is performed in Package 1.** These are recorded for the founder's decision on sequencing.

---

## Open boundary questions for the founder

1. **`foundry/`, `omnimorph/`, `business/`, `egregore/`** are classified *generic extension candidate*, not core. Each must prove genericity before entering the core. Do you want that proof required before or after the canonical merge?
2. **`docs/TARGET_FORM_001.md`** references venture domains. TARGET_FORM_002 must not. Should 001's documentation be re-scoped, or preserved as-is with 002 written clean?
3. **`adapters/`** is the correct home for domain translation. Should L1–L4 relocate there, or to a separate venture repository?
