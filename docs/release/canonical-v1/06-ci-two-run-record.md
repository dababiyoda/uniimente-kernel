# Two-Run Canonical CI Record

**Certified commit:** `f59361386ea3de32ba01c60871a4ea04dca01d12`
Both runs executed against this exact SHA. No code, contract, architecture, boundary,
Constitution, authority, or developmental logic changed between them.

## Runs

| | Run 1 | Run 2 |
|---|---|---|
| Run ID | `30187309654` | `30187437500` |
| Run number | 1 | 2 |
| Attempt | 1 | 1 |
| Event | `pull_request` | `workflow_dispatch` |
| Head SHA | `f593613` | `f593613` |
| Started | 2026-07-26T04:08:44Z | 2026-07-26T04:13:26Z |
| Completed | 2026-07-26T04:09:07Z | 2026-07-26T04:13:45Z |
| Duration | 23s | 19s |
| **Conclusion** | **success** | **success** |

Run 2 is an independent run with its own run ID and its own runners — not a re-attempt
of run 1.

## The four required checks

| Check | Run 1 | Run 2 |
|---|---|---|
| 1 · Kernel and organ tests | success (7s) | success (15s) |
| 2 · Contract schema references resolve | success (13s) | success (11s) |
| 3 · One source of authority | success (7s) | success (7s) |
| 4 · Developmental work stays sealed | success (11s) | success (13s) |

## Measured results

| Measure | Run 1 | Run 2 | Identical |
|---|---|---|---|
| pytest, full suite | **305 passed** in 1.87s | **305 passed** in 2.29s | yes |
| Verifier V1 canonical artifacts | PASS 45/45 | PASS 45/45 | yes |
| Verifier V2 unit tests | PASS 284 passed | PASS 284 passed | yes |
| Verifier V3 modules closed | PASS 20 modules | PASS 20 modules | yes |
| Verifier V4 false-closure detection | PASS | PASS | yes |
| Verifier V5 buildability READMEs | PASS 18 | PASS 18 | yes |
| Schema refs | 13 schemas, 12 refs, all resolve | same | yes |
| Sealed state | `external_effects=0`, `SIMULATED_NOT_AUTHORIZED` | same | yes |
| TARGET_FORM_001 artifact | uploaded | uploaded | yes |

## Differences between the two runs

**None substantive.** Every check, count, and verdict is identical.

Non-substantive differences, recorded for completeness:

- wall-clock timings differ by a few seconds
- different runner instances (run 1: `1000001585–1588` range differs from run 2's)
- trigger event differs by construction (`pull_request` vs `workflow_dispatch`)
- verifier run-record filenames differ (they embed a timestamp)
- both runs emitted the same Node 20 deprecation warning from
  `actions/checkout@v4` and `actions/setup-python@v5` — an upstream GitHub notice,
  not a repository failure

## Head-SHA provenance

Writing this record necessarily creates a new commit, so the branch head moves past the
certified SHA. **The two certified runs above are against `f593613`, not against the head
that carries this file.** A third run will fire automatically on the record-keeping commit.
That third run is corroborating, not the certification — the two-run evidence for Package 1
is runs `30187309654` and `30187437500` on `f593613`.
