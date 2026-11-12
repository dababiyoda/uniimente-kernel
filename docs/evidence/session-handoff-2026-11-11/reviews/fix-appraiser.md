# Fix round report: the appraiser runs no detached sensor (2026-11-12)

Recorded by the commissioning session from the fix-round agent's hand-back at about 03:35 UTC. These are the
agent's claims unless marked "checked by the session".

- Head `bfaf210c8547dc34c58ac7de3fd502ac03c1d724` on `claude/appraiser-detached-sensor-20261111`; three commits on
  `bf8e4b9f` (`ba2e0267`, `61bc6fb2`, `bfaf210c`). Logs: `scratchpad/fix-logs/before`, `final2`, `gates-final`.
- Files since `bf8e4b9f`: `greg/appraisal.py`, `body.py`, `routing.py`, `sop.py`, `compounding.py`, `corrections.py`,
  `mission_control.py`, the unit's gate (26 to 66 mutants), the residual gate (one mutant added, one re-anchored),
  the effect-call allowlist pin of `Body.appraise`, two test files.

## Findings of the review (`review-appraiser.md`) and what was done

| Finding | Reproduced on `bf8e4b9f` | Change |
|---|---|---|
| F1(a) a late re-read refutes a closure for a world that changed later | yes (probe p13; p4 drift) | an appraisal is late when an earlier appraisal of the same closure ran nothing; a late disagreeing reading is UNAVAILABLE with `appraised_late`, final; waiting closures are appraised before new ones |
| F2 routing blames a check the appraiser could not measure | yes | the appraiser names `not_established`; `routing.track_record` skips those checks |
| F3 UNAVAILABLE read as a failed appraisal by the SOP trend and compounding | yes | `sop.awaiting_appraisal`; the trend treats such a mission as pending; compounding says "not yet appraised" |
| Proof list rows indistinguishable | yes | each row names its closure; UNAVAILABLE rows carry the reason |
| F4 three surviving mutants (B4, E1, A7) | code already right | tests added; each mutant now caught |
| F5 an answered NO_STRATEGY ask re-blocks every cadence | yes (10 ticks, 10 block/unblock pairs) | **not fixed**: the fix is at the decision site, outside this unit |
| F1(b) readers take the ledger-latest appraisal per mission | yes, same on base, `bf8e4b9f` and head (`p13b_retry_window.py`) | **not fixed**: a separate unit, specified below |

## The founder's ruling of 2026-11-12 on a late appraisal mismatch

1. Stale, never a refutation: as F1(a).
2. A separately valid refutation is kept and named: stale readings live in `appraised_late.stale`; `refuted_by` names
   the checks that refuted; corrections list only those.
3. Fresh appraisal: the stale verdict records which later closure will be appraised, or that none will (mission ended).
4. Grants nothing: a test holds a second mission on an approval throughout; autonomy level, asks, approvals,
   blockers and lifecycle are identical before and after each UNAVAILABLE appraisal.

## Agent's verification on `bfaf210c`

31 test files in the solver environment: 522 passed, 9 skipped (organ checkouts, bubblewrap). Thirteen gates run to
completion: appraiser gate 66/66; residual 88/88 (first attempt printed BASELINE_FAILS at load average 14, rerun
passed); cortex groups 34/34; whole-output 160/160; effect-call allowlist 117/117; ask-terms 62/62; evidence
corrections 41/41; node revoke 35/35; fail-closed build instrument 29/29; typed blockers 28/28; standing approval
21/21; capability disposition 18/18; worker appraisal 12 caught. The stale-anchor scan missed one real stale anchor
(a line turned into an `elif`); `test_repo_health_gates` caught it and it was re-anchored.

## Specification for the separate unit F1(b)

Key each reader on the closure it means: `sop.verified_appraisals`, `metrics.vepmc` (two sites), `acceptance.report`
(the achievement's own appraisal, or the newest hold's for a standing mission); `routing.track_record` (per closure
window, as `autonomy._closure_windows` does); `settlement._settling_appraisals` and `latest_verdict`. Decide the retry
window: a first appraisal retried after runs without a verdict also reads a later world. Two residuals of the same
class on this head: a retry of the stale appraisal landing after the achievement's VERIFIED; `autonomy.report` takes
the first appraisal of a closure.

## Specification for the separate unit F5

After the founder answers a NO_STRATEGY ask, each cadence the mission re-observes, the same answered request id is
returned, `_block` records it, and `_blocker_resolved` lifts it on the next tick. Fix in `_blocker_resolved` or at the
NO_STRATEGY site: when the request the engine would raise is the answered one and failing/failed/excluded are
unchanged, keep the mission waiting. Test: no facts added over 10 hourly ticks.

## Behaviour that differs beyond the findings (agent's list)

Waiting closures are appraised first; appraisals may carry `not_established`, `appraised_late`, `refuted_by`; an
on-demand appraisal of a closure that once waited is judged late too; a late "could not be re-measured" is stale; a
REFUTED whose only failing effect check was left open no longer lowers routing reliability; the Proof table has two
more columns. Mission Control browser tests were not run.

## For the founder (agent's list)

1. A late reading that still agrees is recorded VERIFIED and credited. A strict reading of "cannot establish a
   timely appraisal" might want it marked.
2. A stale-final UNAVAILABLE is still worded by the SOP trend and compounding as a failed or rejected appraisal.
3. F1(b) with its retry-window rule, and F5, as their own units.

## Incident

The agent used `pkill -f check_whole_output_mutants.py` once and killed another worker's gate run; that worker
restarted it. Workers stop processes by pid only since.
