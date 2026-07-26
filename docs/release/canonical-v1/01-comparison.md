# Candidate versus Archived Main

**Archived main:** `archive/main-2026-07-19` → `3d9b5779a7093d6ddd07f225c8329ead6d0c6393` (2026-07-19)
**Candidate:** `release/canonical-v1` → `a4fa43e8c74b56130314c21736dfaf767567f3de` (2026-07-22)
**Baseline CI commit:** `8b55efa6393d811ff544d22006f441f03dc8dc19` (the only change to the candidate)

## Divergence

| Measure | Value |
|---|---|
| Commits ahead of archived main | **80** |
| Commits behind archived main | **0** |
| Files changed | 106 |
| Files added | 93 |
| Files modified | 13 |
| **Files deleted** | **0** |

**The candidate strictly contains archived main.** Zero deletions — nothing on main is lost. This satisfies the preservation rule in `UNIIMENTE_FINAL_BUILD_ORDER` §2 and §12 without exception.

## The 13 modified files

**Seven contract schemas** — all differ from main by exactly one change: the `$defs` block moved from `properties.$defs` to the document root.

```
context-packet · decision · event · opportunity-packet
outcome · venture-assessment · venture-cell-charter
```

On main these `$ref`s do not resolve, and because `additionalProperties: false` is set, `$defs` is additionally declared a legal field on instances. The candidate's versions are correct.

**This is recorded as evidence, not as a decision.** Per founder correction, only `outcome.schema.json` is settled (two independent efforts produced byte-identical output). The other six each require an individual compatibility test — comparing required fields, allowed values, reference behaviour, fixtures, producers and consumers — before being declared settled. That work is **not** part of Package 1.

**Six code, test and verifier files**

| File | Change |
|---|---|
| `capabilities/genome.py` | +1 / −0 |
| `closure/kernel_registry.py` | +73 / −0 |
| `loom/ratify.py` | +16 / −13 |
| `tests/unit/test_closure.py` | +28 / −20 |
| `verifier/v2/criteria.json` | +61 / −56 |
| `verifier/v2/verify.py` | +33 / −28 |

## Baseline state of the candidate

Measured locally on `8b55efa` before any remediation:

```
pytest              305 passed, 0 failed
verifier V1-V5      PASS  (V1 45/45 artifacts, V2 284 unit tests,
                           V3 20 modules closed, V4 false-closure detected,
                           V5 18 READMEs declare buildability)
check 2 contracts   13 schemas, 12 local refs, all resolve
check 3 authority   exactly one of each governed artifact
check 4 sealed      external_effects=0, SIMULATED_NOT_AUTHORIZED,
                    verdict MECHANICS_VALIDATED_NOT_PRODUCTION_AUTHORIZED
```

**No baseline failures were found, and therefore none were fixed.** The authoritative record is the two GitHub CI runs, not this local run.
