# Genome admission v9: pre-registration (2026-10-22)

**Status:** pre-registered. This file is committed before `freeze.json`, and both are committed before any held-out
instance is generated. The run refuses to report if any frozen input differs.

v9 re-admits a single genome, `convex_qp_dual` 1.0.0, after an integration fix.

**Background.** In v8 the rule's own decision for it was DEFAULT_FOR_GEOMETRY: 18-4-8 against the baseline (p = 0.002) and 20-0-10 against SciPy `trust-constr`. It was demoted to NICHE because the canonical-path smoke failed: held-out seed 1700's request exceeded GREG's 64 KiB cognitive-request limit.

**The fix.** Commit `93bf43a3` found the binding cause: requests travelled to the solver and verifier worker as one argv string, which Linux caps at 128 KiB. Requests now go on stdin, and the request ceiling is 1 MiB. The genome itself is unchanged at 1.0.0.

**Evidence.** v8's evidence and verdict stay exactly as recorded. v9 is a fresh measurement on fresh seeds, not an edit of v8.

## What is fixed before the run

| Item | Value |
|---|---|
| Run id | `2026-10-22-v9` |
| Family | `convex_qp_dual` 1.0.0 only (`--only convex_qp_dual`) |
| Held-out seeds | 1800-1829 (`--heldout-start 1800`) |
| Rule | `RULE` verbatim, unchanged since v2; `decide()`, `COST_RATIO` 1.25 and `ALPHA` 0.05 unchanged |
| Smoke | one canonical-path smoke on the first held-out seed. A failure blocks DEFAULT, as in v8 |
| Code | the harness's import closure and all of `greg/cognition`, at the commit that adds `freeze.json`, hashed in it. This includes the stdin transport |
| Arms and statistics | as in v4-v8: the dual projected-gradient baseline and the SciPy `trust-constr` competitor, unchanged |
| Run | once, in a clean detached worktree at the freeze commit, pinned to one core. A crash is recorded, never retried |
| Machine | starts only when the 1-minute load is below 1.5; start and end load are recorded |

**Why 1800-1829 are fresh:**
- No genome-admission freeze uses them. The held-out spans used so far are 1000-1029 and 1100-1129 through 1700-1729.
- No #179 freeze uses them; its ranges are 1001-1040, 2001-2040, 3001-3040, 5001-5040 and 6501-6840.
- The antifragility runs use 500-511, 1000-1005 and 6000-6319.
- They are not P8-reserved (7000-9199) and not in a declared development range.
- The harness's spent-seed and reused-instance checks run again at freeze time.

## Disclosures

**While building the fix, these instances were run through the canonical path, for plumbing only:**
- held-out seeds 1700, 1701 and 1702, which v8 had already spent;
- development seed 5, in the new regression test.

No decision rests on them, and no seed in 1800-1829 has been generated.

**The outcome is not guaranteed by v8.** Fresh seeds can move the vs-baseline result, which was well-conditioned 1-0-5 in v8. With 30 fresh instances any of DEFAULT, NICHE or EXPERIMENTAL is possible.

## What the outcome changes, and what it cannot

- **DEFAULT** makes `convex_qp_dual` routable as the default for its geometry, but only if the smoke also passes. Attaching is the founder's decision.
- **Any other verdict** is reported as prominently and recorded as the current-version evidence.
- **Scope.** Every instance is synthetic. A verdict says nothing about a natural workload.
- **No retry.** This is the one re-admission for this fix. If the run fails for any reason, the failure is the record, with no retry under this run id.
