# P8 cycle 6 design pilots (constraint release, review seeds 3500-3999 only)

These pilots are design knowledge for cycle 6. They are not evidence for the cycle and they decide nothing about
any configuration. Every instance comes from review seeds 3500-3999; no P8-reserved, admission or spent seed is
generated (`scripts/p8_cr6_selection_pilot.py`, `guard`).

## Pilot 1 (2026-10-16): seven selection rules on one search

**Question, declared before any pilot instance was generated:** which rule for choosing a cycle's one candidate from
a cover/1 search lineage most often yields a candidate that passes the unchanged train-gain and stress gates and then
wins the unchanged held-out step? The seven rules are in `RULES` in the script; none was added after looking.

**Design:** three 60-item train sets (3500-3559, 3560-3619, 3620-3679) × search seeds 101, 102, 103 = 9 simulated
cycles. Every rule is applied to the same lineage, so the comparison is paired. Each pick is measured on a fresh
260-item pool (3740-3999), resampled 2,000 times at n = 180 and n = 240 (`lineages-T*.json`, `summary.json`).

**Result.** P(RETAIN) is the mean over the 9 cycles at alpha 0.05, n = 180, and is 0 when a cycle stops before the
held-out step.

| Rule | Advances | Passes stress | P(RETAIN) n=180 | n=240 |
|---|---:|---:|---:|---:|
| mean/1 (cycles 1-5) | 9 | 9 | **0.554** | **0.614** |
| stress-mean/1 | 9 | 9 | 0.554 (same picks as mean/1) | 0.614 |
| trimmed/1 | 9 | 9 | 0.548 | 0.607 |
| median/1 | 9 | 7 | 0.496 | 0.559 |
| stress-signtest/1 | 9 | 9 | 0.343 | 0.396 |
| signtest/1 | 9 | 6 | 0.201 | 0.231 |
| netwins/1 | 9 | 6 | 0.201 | 0.231 |

- **The hypothesis behind cycle 6 is refuted.** Cycle 5's REJECT was read as "the argmin of near-tied train means
  picks the wrong configuration". No declared alternative beats `mean/1`. The sign-test rules are the worst: they
  favour configurations that win many items by small margins, and those fail the stress gate or lose on the pool.
- **`signtest/1` was coded before this pilot ran** (`evolution.py` modified 08:02 UTC; the first lineage file was
  written at 08:37). That code is kept in git history as lineage (the commit before this README) and reverted from the
  tree. It is never frozen.
- **The train draw is what decides.** Under `mean/1`, P(RETAIN) by train set is 0.229, 0.567 and 0.865. The search
  seed matters less. On the unlucky set the cover finds restart-heavy configurations, but a non-restart operator
  variant has the lowest train mean.
- Cycle 5's specific failure, a `mean/1` pick failing the lean stress set, did not recur in these 9 cycles.

## Pilot 2 (declared 2026-10-21, before it ran): train-set size

**Question:** does a 120-item train set, rather than 60, raise P(RETAIN) under the unchanged `mean/1`?

**Design, fixed here:**

- Train sets: 3500-3619 and 3620-3739, each 120 items.
- Search seeds: 101, 102 and 103.
- The pool is the same 3740-3999.
- Script and rules are unchanged.
- That makes 6 simulated cycles.

**What cycle 6 takes from it, declared now:**

1. **Selection:** `mean/1`, unchanged. A rule is adopted only if it beats `mean/1` by at least 0.10 P(RETAIN) in both
   pilots, which pilot 1 already rules out.
2. **Train size:** 120 items if pilot 2's `mean/1` P(RETAIN) at n = 240 and alpha 0.05 exceeds pilot 1's (0.614), and
   no 120-item train set falls below pilot 1's worst set (0.229). Otherwise 60 items, as in cycle 5.
3. **Held-out size:** 240. Pilot 1 shows 240 retains more often than 180 under every rule.
4. The rule, the gates and the thresholds are unchanged. Whatever the pilot shows, it is disclosed in cycle 6's
   pre-registration.
