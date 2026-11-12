# Builder's report: a compile receipt that did not answer is no measured failure (2026-11-12)

Recorded by the commissioning session from the builder agent's hand-back at about 02:50 UTC. These are the
builder's claims. An independent review was commissioned at 02:53 UTC; nothing here is confirmed by it yet.

- Head `0f2b50523bfc90ef5b00b58a73fbc8f563c5a823` on `claude/compile-unanswered-unread-20261112`, one commit on
  `b9a34259` (#298). Local only.
- Files (9, +955/-17): `greg/missions.py`, `greg/cognition/compiler.py`, `budget.py`, `cortex.py`, `bridge.py`,
  `settlement.py`, `.github/workflows/canonical-ci.yml`, new `scripts/ci/check_compile_unanswered_mutants.py`, new
  `tests/unit/test_greg_compile_unanswered.py`. Outputs under `scratchpad/cu-out/`, probes under `cu-probes/`.

## The one reader (`greg/missions.py:576`)

A compile receipt is recognised by `schema` starting `greg-competency-compilation/`.

| State | Read as |
|---|---|
| ANSWERED with result; WORLD_UNVERIFIED with result; HUMAN_JUDGMENT_RECORDED; REFUTED | measurement |
| PLANNED | not an abstention; read as before |
| WORLD_UNVERIFIED without result; HUMAN_JUDGMENT_REQUIRED; PROHIBITED; ABSTAIN; FORMALIZATION_INCOMPLETE; CAPABILITY_DEFICIT; UNKNOWN; EVIDENCE_EXPIRED; UNIDENTIFIED; HUMAN_REVIEW_REQUIRED; solver statuses; STAGE_ABSTAINED; TRANSLATION_FAILED; NO_RECIPE; TIMEOUT | unanswered |

The rule is open-ended: anything not in the first two rows is unanswered. PLANNED and HUMAN_JUDGMENT_RECORDED are
the builder's calls from reading the code.

## The typed field

Timeout and exhausted budget already had inner reason codes. An abnormal worker exit had none (text only, with
`reason_code: INSUFFICIENT_EVIDENCE`). Added: `budget.note_host_stop` (a context variable) noted at the three worker
launch sites (`cortex._numeric`, `cortex.independent_verify`, `bridge.run_worker`); `compiler._host_stop` builds the
receipt's `host_stop`; schema 0.3; `settlement.COMPILE_SCHEMAS` accepts 0.2 and 0.3. `cortex.py::reason` was not
edited because its source is bound by 16 digests in the evidence index.

## Before and after (builder's runs)

New test file on `0a16997b`: 17 failed, 5 passed. On head: 22 passed (solver environment); 21 passed, 1 skipped
without Z3.

| Case | Before | After |
|---|---|---|
| Timeout or crash, sensor only, host back at 62 s | BLOCKED, NO_STRATEGY at 0 s; next read at 3658 s | SENSOR_RETRY twice, read at 93 s, ACHIEVED, no question |
| Host never recovers | NO_STRATEGY at once | SENSOR_RETRY, SENSOR_RETRY, WAITING, BLOCKED; one SENSOR_FAILURE |
| Same stall with a strategy | compile DONE, marked failed, routing outcome "ineffective", appraisal REFUTED | no action, nothing failed, no routing outcome |
| REFUTED receipt; ANSWERED with a false predicate | measured failure | the same |
| PROHIBITED | "field absent"; unmet names the check as failing | "sensor inconclusive (PROHIBITED)"; unmeasured; appraisal VERIFIED_UNMET |
| Exhausted budget | BLOCKED at once | retry path, typed `budget_exceeded`, one SENSOR_FAILURE |

The session's own stall probe recovers the host at 124 s: head asks one SENSOR_FAILURE question at 93 s, which the
body withdraws at 124 s.

## Gates (builder's runs)

New gate 38/38 and 3/3; whole-output 162, 0 survived or stale; unmeasured-check 4/4 and 5/5; reconstitution 4/4;
ask-terms 62/62; cognition budget 3/3; cognition residual 86, 0 survived; cortex gate five groups 108, 0 survived or
stale; seed gate 6 of 7 in the solver environment (the `constraint` mutant survives identically on `8d205324`).

## Admitted by the builder

- Every unanswered compile reading is now "sensor inconclusive (STATE)"; `measured()` readers skip it.
- New `declined` key on `mission.observed`; "declined" means a person's refusal elsewhere.
- A host-stopped direct cortex receipt (not through the compiler) is still pursued as a failure.
- A stall that arrives after a strategy ran still leaves that strategy in `m.failed` (read, not run).
- An engine that deterministically exhausts its signed budget is retried three times, then asked about.
- No docs changed.

## Questions it raised

1. Whether PLANNED and HUMAN_JUDGMENT_RECORDED read correctly.
2. Whether a host-stopped direct cortex receipt should take the retry path (needs an edit to `cortex.py::reason`
   and re-binding 16 digests).
3. The key name `declined`.
4. Other branches that compare the compile schema to `/0.2` must accept 0.3.
5. Whether three rounds at 30 s and 60 s is the right patience (a host down longer than about 91 s asks once).
6. The seed gate's surviving `constraint` mutant on the integration line.
7. The new gate adds 41 mutants to job 10 (about 20 minutes on a loaded machine).
