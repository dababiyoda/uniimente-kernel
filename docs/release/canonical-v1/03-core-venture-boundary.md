# Core versus Venture Boundary Report

**Candidate:** `release/canonical-v1` @ `a4fa43e` (baseline CI at `8b55efa`)
**Rule being enforced:** UNIIMENTE may create and govern ventures. No venture may define UNIIMENTE.
**Machine-readable form:** `boundary.json` in this directory.

---


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
| `closure/` | **core** | Closure checks |
| `verifier/` | **core** | V1–V5 |
| `observability/`, `sandbox/` | **core** | Build targets |
| `sdk-python/`, `sdk-typescript/` | **core** | Organ integration |
| `developmental/` | **developmental research** | MICA/CDPE TARGET_FORM_001 |
| `morphogenesis/` | **core** | Engine/contracts |
| `foundry/` | **generic extension candidate** | Must prove genericity before entering core |
| `omnimorph/` | **generic extension candidate** | Same |
| `business/` | **generic extension candidate** | Same |
| `egregore/` | **generic extension candidate** | ADE-1 standing cognition |
| `adapters/` | **venture-specific adapter** | Correct location for domain translation |
| `linker/` | **core** | Cross-organ edge resolution |
| `organs/` | **core** | Organ manifests |
| `integration/` | **core** | Integration manifest |
| `contracts/` | **mixed** | See contract inventory |
| `tests/` | **mixed** | Shared mechanism tests |
| `docs/` | **mixed** | 7 of 12 mention a venture domain |
| `scripts/ci/` | **core** | Added by Package 1; fully generic |

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

## Open boundary questions for the founder

1. **`foundry/`, `omnimorph/`, `business/`, `egregore/`** are classified *generic extension candidate*, not core. Each must prove genericity before entering the core. Do you want that proof required before or after the canonical merge?
2. **`docs/TARGET_FORM_001.md`** references venture domains. TARGET_FORM_002 must not. Should 001's documentation be re-scoped, or preserved as-is with 002 written clean?
