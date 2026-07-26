# Authority Duplication Report

**Required check 3.** Automated: `scripts/ci/check_authority_singleton.py`.

Enforces the authority half of `UNIIMENTE_FINAL_BUILD_ORDER` §3 — *one authority, many governed capabilities.* It does **not** restrict multiple capability implementations, which the build order explicitly preserves.

## Result on `release/canonical-v1`: PASS

| Governed artifact | Found | Path |
|---|---|---|
| Constitution | 1 | `constitution/constitution.ucl` |
| Consequence Gate | 1 | `policy/consequence_gate.py` |
| Authority matrix | 1 | `authority/authority-matrix.yaml` |
| Legal principals | 1 | `authority/legal-principals.yaml` |
| Organ registry | 1 | `identity/organ-registry.yaml` |
| Agent registry | 1 | `identity/agent-registry.yaml` |

Additionally verified: none of the ten integration-only directories — `egregore`, `foundry`, `omnimorph`, `organs`, `linker`, `business`, `adapters`, `integration`, `developmental`, `morphogenesis` — defines any authority file of its own. They consume governance; they do not fork it.

**This was the decisive open question from Pass 2 and it is now closed by evidence.**

## Limitation

The check is filename-based. A second gate implemented under a different filename would not be detected. Strengthening it to detect behavioural duplicates is deferred, with the trigger being any PR that adds a module importing or re-implementing gate semantics.
