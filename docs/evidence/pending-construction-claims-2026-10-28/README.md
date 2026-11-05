# Pending construction outcomes, one per signed claim (#205 adopted onto #196), 2026-10-28

**Parent:** BODY + ORGANS + MIND = GREG / UNIIMENTE. This increment covers outcome intake for constructed capabilities. It does not close the parent.

**Claim:** [#96 comment 6473634602](https://github.com/dababiyoda/uniimente-kernel/issues/96#issuecomment-6473634602), session `session_01KucyfnwWG7Lgp8QvCTKeHg`.
**Founder intent:** INTENT-20261001-FULL-MACHINE-COMPLETION; INTENT-20261019-UPWARD-ASCENT; founder directive 2026-10-28 ("TRUE ABSOLUTE OPUS MAXIMUS", §4 "continue into the adjacent construction-outcome… requirements", §11 "make outcomes change later decisions").

## Sources

| Item | Revision |
| --- | --- |
| Base: #196 integration head | `4e970f2d490dd63676b38ee622c721b3169f9722` |
| Adopted: #205 (Codex a60f90b8f5e5) | `583e5f3156b7ae941a3ec8cf381b3fef572f9748`, merged clean. Neither of its source files changed between its base `fa80ace7` and `4e970f2d`. |
| Settlement rules (unchanged) | `measured_outcomes`, `world_met`, `REALIZATION_RELATIVE_TOLERANCE`, `record_realization` from `4c7a3a97` |

## What changed

1. **#205 is joined to the current candidate.** Pending construction objectives appear in `greg cognition calibration`. `greg realize RECEIPT --objective-value N --key K` emits the signed scalar REALIZATION, and the forecast form `--value` keeps its list shape. This is #205 as written.
2. **Review finding, fixed: the view counted receipts, while settlement counts signed claims.** `measured_outcomes` credits a construction only through a signed check's observation of its receipt, and it settles once per claim identity (mission, command, check, signed input, method, geometry). #205's `awaiting_realization` instead listed every ledger receipt holding a construction answer. On a real body this produced:
   - **Persistent missions asked again and again for one answer.** An infinite-closure mission re-verifies its answer every cadence. On the probe run, 14 observations left 13 pending rows for one claim. After the founder reported one row, 12 still asked for the same answer. Goal Gravity's `awaiting_realization` count (`greg/gravity.py`) inflated the same way.
   - **A second report silently erased the first.** A rounded figure reported on a sibling row (1.1 against 1.0) became a conflict, and the claim's real outcome was then scored as neither.
   - **Some reports could never settle.** A construction answer that no signed check observed (or that a check does not bind: another sensor, producer or input) was offered for a report. The body would accept and record that report, and it would never change competence.

   The fix: `_construction_claims` enumerates claims through settlement's own `_constructed_outcome` and `_outcome_identity`, without the appraisal, so the view and settlement cannot drift apart. Each pending claim is offered once, on its latest receipt, with `claim`, `receipts_for_claim` and a `settles` note. It leaves the list once any of its receipts carries a realization. Forecast rows are unchanged: each forecast is a distinct prediction with its own horizon.

`record_realization`, the tolerance rule, the scoring, signing and authority are unchanged. A report on an unobserved receipt is still accepted and recorded if someone sends it. The view simply no longer invites one (see residual 2).

## What GREG can do now that it could not before

On the integrated candidate, the founder sees each construction answer still waiting for its world outcome **once**, including answers that a persistent goal keeps re-verifying. One signed `greg realize … --objective-value` report settles that claim exactly once and changes the method's settled competence: in the real-body test, `(count, correct)` goes to `(1, 0)` and the certificate verdict is kept beside it. Before this, #205 was not on the candidate. Without the fix, the same body listed 7 to 13 pending reports for one answer.

## Evidence

All runs are local, Python 3.11.17, on this branch's working tree (#196 `4e970f2d` + #205 + the fix).

- [before.txt](before.txt): with #205's settlement code as merged, the three new tests **fail** (3 failed, 24 passed). One signed claim was offered as 7 pending reports, an unobserved receipt was offered, and a claim stayed offered after a sibling report.
- [after.txt](after.txt): **108 passed**. The run covers #205's six scoped files plus `test_greg_condition_competence_hooks.py`, `test_greg_failure_closure.py`, `test_cognition_multi_claim_settlement.py` and `test_greg_cognition_mission.py`.
- [mutants.txt](mutants.txt): two mutants of the fix, each caught by 2 tests. M1 offers every receipt of a claim; M2 keeps a claim offered after a sibling receipt was reported.
- The real-body test, `test_a_persistent_mission_reobserving_one_answer_asks_once_and_one_signed_report_settles_it_once`, runs this sequence: a founder-signed infinite mission; Capability Genesis constructs `selection.closure` and auto-attaches it read-only under the signed scope; re-observation; the read-only CLI view; the signed scalar CLI report; more ticks; `measured_outcomes` and `competence`.
- #205's own fixture tests listed a bare receipt that no mission observed, which is the trap above. The fixture now records the witness, registration and observation that a body records.

The full local suite and Canonical CI on the pushed head are recorded separately in the PR. The realized values are **synthetic** test inputs. No real-world outcome, founder-device run or positive learning dividend is claimed.

## Deliberation (self-review, one worker; independent review pending)

- **Builder:** the smallest correct fix reuses settlement's identity function rather than restating it. One view row per claim matches how the claim settles.
- **Adversary:** (a) If identity rules change in `measured_outcomes`, the view follows automatically, because both call `_constructed_outcome`. The appraisal requirement, however, is applied only in settlement, so a claim from a mission that never appraises VERIFIED is still offered. That is accepted: its report settles when the mission appraises, and refusing it would hide a real pending outcome. (b) Conflicting reports remain possible through hashes typed by hand. Residual 1.
- **Operator:** read-only, with no new state. The cost is one pass over `mission.observed`, the same order as `measured_outcomes`.
- **Beneficiary (founder):** fewer, truthful asks. A persistent goal no longer multiplies one question, and no report the founder makes is silently discarded by the view's own invitation.
- **Constitutional:** no authority, signing, tolerance or acceptance change. The view still creates nothing (`authority_created: false`).
- **Pass 1:** the per-receipt view becomes a per-claim view, and the dangling-report trap is closed at the point of invitation.
- **Pass 2:** attacked residuals: (1) a conflicting second report through a hand-typed sibling hash, and (2) a report on an unobserved receipt sent anyway. Both are kept as named residuals rather than solved by a rule change outside this claim's scope.
- **Alternatives considered:** do nothing (keeps the trap); change `record_realization` to refuse unobserved receipts (a rule change, outside scope, needs the integrator); dedupe by compile receipt id (wrong, because every re-observation has a distinct compile receipt id; measured 13 distinct ids for one claim).
- **Decision:** retain, as a child draft for the integrator.

## Residuals

1. `record_realization` accepts a different value on a sibling receipt of an already-reported claim and records a conflict (scored as neither). The view no longer invites it. Refusing it outright is a settlement rule change for the integrator.
2. `record_realization` accepts a report on a construction receipt that no signed check observed, and that report never settles. The proposed rule: refuse with a reason. This is for the integrator, not done here.
3. A positive learning dividend still needs real realized outcomes. None is reachable from this environment.

## Rollback

Revert the merge commit of #205 and the fix commit. Retained REALIZATION facts stay readable, because the body contract is unchanged.

## Review fixes (cross-session review by `session_01Kucyfoabgsg6W8H8xj4qea`, 2026-10-28, on `aa83bb78`)

The reviewer is the same model family, so this is not fully independent. It found no blocking defect and two low findings; both are fixed in the view, and no settlement rule changes.

1. **A corrected report no longer vanishes.** A second, different value, even on the same receipt, makes `_world_settled` score the claim as neither. The claim then disappeared from the view, from `measured_outcomes` and from `competence`, with nothing saying so. It is now listed as `kind: "objective_conflict"`, with the claim, the conflicting values, their event ids and "scored as neither". It offers no `report_with`, because no further report resolves it.
2. **"Settles" follows the mission's appraisal.** Each row carries `mission_appraisal`. `settles` reads "once for the claim" only while the mission's latest appraisal counts for settlement; otherwise it says a report is recorded and scores nothing until a VERIFIED appraisal. The appraisal rule is now one helper, `_settling_appraisals`, which `measured_outcomes` and the view both call, so the two cannot drift.

Evidence:
- [review-fixes-before.txt](review-fixes-before.txt): the new and updated tests fail on `aa83bb78` (3 failed, 26 passed).
- [review-fixes-after.txt](review-fixes-after.txt): 110 related tests pass, and the combined-machine test passes with real organs (WMI #47).

## Follow-up to the 2026-10-28 directive on #210

1. **Wording now matches the shared rule.** A row's `settles` names the eligible settling appraisal: VERIFIED, or VERIFIED_UNMET (a verified failure closure, never promoted to success) with the required checks. A new test covers VERIFIED_UNMET and a later REFUTED.
2. **The answer-version alias is reproduced and pinned, not fixed here.** `_outcome_identity` binds mission, check, input, method and version, not the answer. In a fixture with two different certified answers to one claim (promised 2, then 4), a report on the first is credited to the later answer: `world.promised == 2` on the promise-4 outcome, and the later answer is no longer asked for. For today's constructions this is reasoned to be unreachable, because each objective is a certified optimum whose value is unique per input and version. The fix (versioned answer snapshots plus a selection or dispute rule) is settlement semantics, owned by the #196 integrator. `test_a_report_on_one_answer_never_settles_a_different_later_answer_of_the_same_claim` is a **strict xfail**: it records the defect and turns into a failure the moment the fix lands.
