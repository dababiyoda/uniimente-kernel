# ADR: a revoked device's unused authority authorizes nothing

- Decision ID: ADR-20261111-revoked-device-authority
- Status: proposed. A sandbox draft on the branch `claude/revoked-device-authority-20261111` (draft pull request
  #300), stacked on #294 (`1643932e`), which is based on the integration head `8d205324` (#196). Not merged;
  adoption is a founder decision.
- Date: 2026-11-11; fix round 2026-11-12 after an independent review (see "Independent review and fix round")
- Decision owner: Alfonso Lopez
- Founder intent: `INTENT-20261111-REVOKED-DEVICE-AUTHORITY`
  ([verbatim source](../intent/sources/REVOKED-DEVICE-AUTHORITY-2026-11-11-source.md))
- Deliberation record: [two passes, five roles](../collaboration/deliberation-revoked-device-authority-20261111.json)
- Protected artifacts touched: none. `python -m governance.integrity --check` is clean.

## The defect

A device key (a phone) is a delegation: the founder key grants it some of `DEVICE_KINDS` until an expiry
(`greg/founder.py`). On `8d205324`, a DECISION the phone signed and the body accepted kept its effect after the
founder revoked the phone. Reproduced on a real body: the phone approves a write, the founder revokes the phone,
both reach the body before its next turn, and the write runs with a grant marked `founder_approved_scope: true`
(`tests/unit/test_greg_revoked_device_authority.py`, first test). The test file, copied unchanged onto a worktree
of `8d205324`, fails 42 of its 50 tests there; the first fails on the assertion that the write did not run. Many of
the 42 also read tables or a module that only this change adds. The 8 that pass pin behaviour that already held: a
completed act keeps its receipt and closure, a decision delivered after the revocation is refused, a dispatch the
founder reconciles as executed keeps its approval, and a revocation body with an unknown field is refused (5 cases).

This draft was built in two sessions. The first was stopped before it could report; the second read its work as
an unverified draft, attacked it, and found one more defect of the same kind, reproduced before it was fixed: the
first draft voided approvals of APPROVAL asks only, and a revoked device's approve of a SENSOR_SCOPE ask kept
admitting observations outside the cone (two further Gate grants after the revocation, both marked
`founder_approved_scope: true`).

## What a device may sign, and where authority is used

| A device may sign | What it changes | Does it authorize a later effect? |
| --- | --- | --- |
| DECISION `approve` on an APPROVAL ask | adds the exact scope to the mission's `approved_scopes` | Yes. Unpaid: it stands for the mission's lifetime, every time the mission selects that scope. Paid: it funds one run and is used up when that run is recorded (`MissionBook.consumed`). |
| DECISION `approve` on a SENSOR_SCOPE ask | adds the observation's exact scope to the mission's `approved_scopes` | Yes. It stands for the mission's lifetime: every later observation of that check is granted on it. |
| DECISION `reconcile_executed` / `reconcile_not_executed` | settles one interrupted dispatch when the engine records it | Yes, until recorded: "not executed" releases the reservation and lets the action be dispatched again. |
| DECISION `reject` | rejects the scope, fails the strategy | No. It only narrows. |
| DECISION on an answer-only ask (HUMAN_WORK, ACCOUNT_ACCESS, CAPABILITY_ATTACH, CAPABILITY_DISPOSITION, COMPENSATION, EVIDENCE_CORRECTION, HUMAN_JUDGMENT) or one that only lets the mission look again or closes the ask (NO_STRATEGY, SENSOR_FAILURE, COMPUTE, BODY_AVAILABILITY) | a record; a HUMAN_JUDGMENT answer decides that one question for cognition | No Gate effect by itself. |
| LIFECYCLE | pauses, resumes, abandons or supersedes a mission | Not a grant, but ending a mission starts the compensations signed with its executed strategies, one Gate dispatch per turn. Those not yet dispatched when the key is revoked are held (see "A mission the revoked key ended"). A resume is open question 3. |
| BODY_PAUSE, BODY_RESUME, BODY_STOP | pauses, resumes or stops the body | Not a grant. |
| CRITIQUE | evidence; may exclude a strategy | No. It narrows. |
| GOAL_CONTROL (narrowing controls only) | stops, lowers or narrows a goal | No. |

A device never signs MISSION, GOAL, CAPABILITY_ATTACH, DEVICE_ENROLL, DEVICE_REVOKE, key rotation or node
commands, and a mission's `pre_approved_steps` are inside the founder-signed MISSION.

The signer of every accepted command is on the ledger (`command.accepted`: `founder_key_id`, `signer`, the whole
signed envelope). An answer counts only as the mission fold re-derives it from a signature-verified DECISION at its
own ledger position (`MissionBook`, `goal_gravity.founder_facts`). Authority is used in one place:
`AuthorityOffice.act` admits an action, a compensation or an observation outside the cone, or one the Constitution
requires a human for, only if its exact scope is in the mission's `approved_scopes`.

Every kind of founder ask raised anywhere in `greg/` is in exactly one class in `greg/missions.py`
(`GATE_SCOPE_ASKS`, `RECONCILIATION_ASKS`, `NO_AUTHORITY_ASKS`, with `greg.asks.ANSWER_ONLY_RECORDS` and
`NOT_ANSWERABLE`). A test scans the source for ask kinds and fails when one is unclassified or in two classes, so a
new kind cannot be added without deciding what a revocation does to its answers.

Two rules already held and are unchanged: a revoked key signs nothing new (`FounderVerifier`, "founder key not
enrolled or revoked"), so a DECISION signed before the revocation and delivered after it is refused; and a key
delegated again verifies only what it signs after the new delegation (`signed_not_before`).

## Decision

**The rule lives in the mission fold.** At the ledger position of a `device.revoked` record,
`MissionBook._revoked` voids every answer that key signed which still authorizes something not yet done
(`unused_authority`): an `approve` of an ask whose scope the Gate honours (APPROVAL, SENSOR_SCOPE) that is not used
up, and a `reconcile_*` answer the engine has not recorded. For each:

- the approved scope leaves the mission's `approved_scopes`;
- the request counts as withdrawn and used up, so the mission asks again under a new request id, which the founder
  or a device still delegated DECISION can answer;
- `MissionBook.voided` says which device and which revocation did it;
- the answer stays in `MissionBook.answers`, and its command and every receipt stay on the ledger.

Because the fold derives this from the revocation record alone, it holds after a restart, in the engine's book, in
a fresh `MissionBook` and in the re-derived book of `goal_gravity.founder_facts`, whatever else was or was not
written. Nothing later reverses it: delegating the key again revives no voided answer. A founder-key answer is
never voided here, whatever key a `device.revoked` row names.

**What is not voided.** What was used: a paid approval whose run happened, a reconciliation the engine recorded,
every completed action and observation, and an approval a failed run or a restore had already withdrawn. And what
authorizes nothing: rejections and answer-only records.

**A mission the revoked key ended.** A device delegated LIFECYCLE may abandon or supersede a mission. The mission
then compensates each executed effect that was signed with a compensation, one Gate dispatch per turn. The first
draft let those dispatches go on after the key was revoked, on nothing but the revoked key's command (reproduced by
the independent review). The founder's sentence covers this: a compensation not yet dispatched is future execution.
So, at the `device.revoked` record, the fold marks every mission that key's own LIFECYCLE command ended
(`MissionState.compensation_hold`). From then on:

- the mission stays ended; the abandon is completed history and is not undone;
- a compensation the Gate dispatched before the revocation is recorded from the Gate's own record (done, refused
  or unknown), as for any mission;
- a compensation the Gate had not dispatched runs only on an approval of its exact scope. The engine asks for it
  (an APPROVAL ask marked `compensation`, naming the key and the revocation); approve runs it once, reject records
  that the effect stands. A device still delegated DECISION can answer it, like every ask this policy raises again;
- delegating the key again lifts nothing.

A mission the founder or another device ended is not held, and neither is one the key only paused or resumed.
Who ended a mission is read from the `command.accepted` record of the LIFECYCLE command, as the lifecycle record
itself is applied as recorded; that reading can only hold a compensation back, never authorize one.

**The trail** (`greg/revocation.py` `settle`). The body calls it when it records a revocation and at the start of
every turn. It writes one `decision.withdrawn` per voided answer, from what the fold derived. A body that stopped
between the revocation and its trail finishes it on the next turn; each record has one identity, so it is written
once. If another withdrawal of the same request is already the record (a restore's), no second one is added.

**The engine.** A voided reconciliation answer is new: no reconciliation ask was ever withdrawn before. A live
mission asks about the same dispatch again before it observes or runs anything; an ended mission asks again before
anything is undone, and records nothing in the voided answer's name.

**A suspected compromise.** `DEVICE_REVOKE` takes one optional field, `suspected_compromise`, which is exactly
`true` when given. A plain revocation is validated, recorded and answered exactly as before. With the field, the
body also records one `device.integrity_review` and one founder ask (`DEVICE_INTEGRITY_REVIEW`), shown where
pending decisions already show (`greg status`, Mission Control, the morning report, the phone channel). The review
is read from the ledger as the revocation left it, so it is the same whenever it is built. It also reads the
Gate's own grant records, so a dispatch the mission had not recorded yet when the key was revoked is listed too,
and so is each observation read under a SENSOR_SCOPE approval. It rewrites nothing and revokes nothing further.
The answer to its ask is only recorded, and only the founder key gives it.

The review lists as resting on an approval of the key only what that approval authorized: the dispatches the Gate
granted for its exact scope between the approval's acceptance and the point where it stopped standing (a
withdrawal, the revocation that voided it, or the paid run that used it), whenever the mission recorded them. A
dispatch the founder approved afterwards is not the key's. For a mission the key ended it lists the compensations
run before the revocation and, as held, those with no record yet.

A suspicion often comes after the key was revoked. The founder then signs `DEVICE_REVOKE` for the revoked key
again with `suspected_compromise: true`. That record revokes and voids nothing more (`marks_revocation` names the
revocation it is about) and opens the review of that revocation, once; a second one is refused. A plain
`DEVICE_REVOKE` of a key that is not delegated is refused with the same words as before.

A review is a reading over everything the key signed. If the reading itself fails, the failure is recorded as the
review (`status: COULD_NOT_BE_BUILT`, the error, empty lists), the founder is still asked, and the body's turn goes
on: the void does not depend on the review, and the body settles the trail before it checks whether it is paused,
so a reading that raised would otherwise stop even a held body.

**The separate appraiser** (`greg/appraisal.py`). An approved action ran honestly only if an approval of its exact
scope was in force when the Gate dispatched it: signed by a founder key, or by a device key not revoked between its
answer and that dispatch (the position of the grant's record). A body without this rule is refuted; an action
dispatched before the revocation is still verified after it.

## Ledger records

| Record | New or changed | Fields |
| --- | --- | --- |
| `greg.device.revoked` | two optional fields | `device_key_id`, `command_digest`, `at`; `suspected_compromise: true` only when the founder signed it; `marks_revocation` (the event id of the standing revocation) only on a suspicion signed after the key was revoked |
| `greg.decision.withdrawn` | an existing type, new fields for this cause | `request_id`, `mission_id`, `voids_answer: true`, `voids_approval: true` (APPROVAL and SENSOR_SCOPE approvals only), `why`, `voided_by: {device_key_id, signer, revocation_event, revocation_command[, restore_id]}`, `kind`, `answer`, `answer_command`, `at`. Identity: request, `device-revoked`, revocation event |
| `greg.device.integrity_review` | new | `review_id`, `status: OPEN_FOR_FOUNDER_REVIEW` (or `COULD_NOT_BE_BUILT` with `error`), `device: {device_key_id, label, delegations}`, `revocation: {event_id, command_digest, at, suspected_compromise[, marks_revocation]}`, `commands[]` (digest, kind, signer, times, channel, `signature_verifies`, and per kind: request, answer, mission, scope, `standing`; lifecycle state; critique; goal control), `effects[]` (what rested on a command: an action, a compensation, an observation or a Gate grant, with attempt, status, capability, scope, receipt, cost, `rested_on`), `voided_by_this_revocation`, `missions`, `receipts`, `scopes`, `read_through`, `unknown`, `history_rewritten: false`, `revokes_further: false`, `authority_created: false`, `at` |
| `greg.decision.requested` | an existing type, new kind | `kind: DEVICE_INTEGRITY_REVIEW`, `mission_id: null`, evidence: the review event, counts, the first 20 rows of each list |

`greg status` gains `security.device_revocations`: what each revocation voided, the review's state,
`resumed_and_still_running` (the missions, and the body, that the key resumed and that still run; see open
question 3), `ended_missions_held` (each mission the revocation holds that still has a compensation without a
record, with the ask that decides it) and, under a review, `suspected_key_delegated_again`. A DEVICE_ENROLL of a
key once revoked as a suspected compromise is accepted and its result carries a `warning` and the key's reviews
(open question 14). `greg device revoke KEY --suspected-compromise` signs the field; `greg device reviews` reads the
records.

## A dispatch already in flight

A revocation takes effect when the body records it: its next inbox read, at most one turn after the file arrives
(a new inbox file wakes the body). During a dispatch the body reads only BODY_STOP, as before. So:

- A dispatch the Gate claimed before the revocation was recorded runs to its end and keeps its receipt. If the
  body died inside it, the restarted body settles it from the Gate's own record, as before: a receipt is reused, a
  claim without a receipt is UNCERTAIN and goes to reconciliation. The appraiser places it at the grant's record,
  before the revocation, and verifies it.
- The same holds for a compensation. In the first draft it did not: a compensation the Gate had completed, whose
  record the body lost, was asked about again after the revocation and could be recorded DECLINED. The engine now
  reads the Gate's record of the compensation's one proposal before anything else
  (`MissionEngine._dispatched_compensation`, built once on the retained-receipt branch and merged here at
  `1bde5e16`; this branch adds no second reading of a receipt). A receipt is recorded by its result (DONE, or
  REFUSED with its reason), a claim without a receipt as UNCERTAIN, and the founder is asked only about one that
  did not complete.
- Nothing new is dispatched on the voided approval. A retry after `reconcile_not_executed` is a new effect and
  waits for a new approval.
- Mission steps later in the same turn still use the approvals as that turn began: a DEVICE_REVOKE file that
  reaches the inbox while a turn runs does not stop a dispatch of that turn that has not started yet (reproduced
  by the independent review with two missions). With workers that run for minutes a turn can be long. This is open
  question 13. Interrupting a turn or a dispatch is #273's subject and is not changed here.

## Alternatives considered

1. **Write the withdrawals when the command is applied, as a restore does, and let the fold read only them.**
   Rejected: a body that dies between `device.revoked` and the withdrawals keeps the approval for good, because the
   re-sent command is refused (the key is no longer delegated).
2. **Remove voided answers from `MissionBook.answers`.** Rejected: the separate appraiser reads that table for
   history, and an action completed before the revocation would be refuted.
3. **Reopen the same request instead of asking again.** Rejected: every surface and the command path assume one
   answer per request; the restore and the standing-approval regression already withdraw and ask again, and this
   reuses their mechanism.
4. **Do nothing in the fold and refuse at the Gate.** Rejected: `AuthorityOffice` receives a set of scope digests
   and cannot tell who approved one; the fold is where an answer's signer is known.

## Review notes

- Builder: one rule, one place, derived from one record; it reuses `decision.withdrawn` with `voids_approval`.
- Adversary: tried and covered by tests: approve then revoke in one inbox read; a paused body; a decision signed
  before and delivered after; the same envelope re-sent; the key delegated again; a second device; a forged
  revocation row naming the founder key; a body stopped between the revocation and its trail; a trail written
  after a new approval of the same scope; an unrecorded reconciliation on a live and on an ended mission; a
  restore; a device answering the review. Second session: a SENSOR_SCOPE approval (found open, fixed); an approval a
  failed run had already withdrawn; a second revocation record of the same key; a review reading that raises; a
  dispatch reconciled as executed after the revocation; a suspicion after the revocation. Both sessions are the
  builder's side. An independent review followed; see the next section.
- Operator: the turn pays one fold step and a few lookups. A review is one fold over the ledger prefix, built once.
- Beneficiary: the founder is asked again once per voided decision; nothing is undone behind his back.
- Constitutional: it only narrows. No protected artifact, no grant, no new command kind, no new authority path.

## Independent review and fix round (2026-11-12)

An independent reviewer attacked head `f35b7986` on real bodies (verdict: sound with fixes; the core rule held
under a 160-seed random search). Its findings, each reproduced before it was changed:

1. A compensation completed before the revocation was asked again and could be recorded DECLINED. Fixed by the
   merge of the retained-receipt branch (see "A dispatch already in flight").
2. The review listed founder-approved dispatches as resting on the device. Fixed: attribution is bounded by where
   each approval stopped standing.
3. A device-signed ABANDON kept dispatching compensations after the revocation. Decided from the founder's
   sentence and built: they are held (see "A mission the revoked key ended"). The founder may overrule this
   (open question 12).
4. Sixteen of the reviewer's eighteen further mutants survived. Each now has a test in
   `tests/unit/test_greg_revoked_device_review.py` and is in the gate's second list, except one that no longer
   has a line to remove; the gate file says why.

Two smaller points: a revocation waiting in the inbox (not changed; open question 13) and a suspected key
delegated again (now said on the result and in the status; open question 14).

## Open questions for the founder (each with the default this draft implements)

1. **Rejections a revoked device signed.** Default: they stand (a rejection authorizes nothing). The review lists
   them. Alternative: ask again.
2. **Answer-only records a revoked device signed**, above all a HUMAN_JUDGMENT answer, which keeps deciding its
   question for cognition. Default: they stand and are listed. Voiding a HUMAN_JUDGMENT answer needs a change in
   the compiler: its request id is derived from the question and cannot be asked again under a new id.
3. **A mission or the body that a revoked device resumed.** Default: nothing is paused. A test pins this: the
   founder pauses a mission, the phone resumes it, the phone is revoked, and the mission's write then runs. The
   review lists each resume, and `greg status` lists what the key resumed that still runs, also after a plain
   revocation. Alternative: put back the pause the device lifted until the founder key (or another delegated
   device) resumes it. This is the most consequential open question: under the alternative reading, a resume is
   authority to execute. The fix round decided the neighbouring case the other way (a mission the device
   abandoned: its compensations are held, question 12); the two defaults now differ, and the founder may want
   them aligned.
4. **A standing approval on a mission that already closed.** Default: its remainder is voided and recorded like
   any other (one rule, no exception). Alternative: skip closed missions to keep the ledger quieter.
5. **Who closes a review, and what an answer does.** Default: only the founder key; the answer is only recorded.
   Alternative: a `reject` pauses the missions the review names.
6. **When a review opens.** Default: when the founder signs `suspected_compromise: true`, with the revocation or
   afterwards for a key already revoked (once per revocation). Nothing opens one by itself. Alternatives: a
   separate command kind for a later suspicion; a review for every revocation.
7. **Expiry and founder-key rotation.** Default: an unused approval of a device whose delegation merely expired,
   or of a founder key since rotated out, keeps standing. The policy sentence names revocation only.
8. **Timing.** Default: the revocation takes effect at the body's next inbox read, not at the moment of signing.
9. **Older ledgers.** Default: an appraisal run from now on refutes a closure whose action was dispatched on a
   revoked device's approval, also when that happened before this rule existed. Recorded appraisals are not
   rewritten.

10. **A review whose reading fails.** Default: recorded once as `COULD_NOT_BE_BUILT` with the error, the founder is
    asked, and it is not built again by itself. Alternative: stop the body until it can be built.
11. **Observations.** A SENSOR_SCOPE approval is voided like an APPROVAL (the Gate honours both). The separate
    appraiser re-derives approvals for actions only, as before; it does not check that an out-of-cone observation
    was read under an approval in force. Default: left as it was. Alternative: extend the appraiser.

12. **A mission a revoked device ended.** Default (fix round): its compensations not yet dispatched are held
    and each is put to the founder as an APPROVAL of its exact scope; a device still delegated DECISION can
    answer it, like every re-asked approval. Alternatives: let them run (the first draft: they were signed by the
    founder with the mission, and ending a mission is not a Gate approval); or let only the founder key answer.
13. **A revocation that arrives during a turn.** Default: it takes effect at the next inbox read; dispatches of
    the running turn that have not started still run on the approvals as the turn began. To close it, the body
    would authenticate pending DEVICE_REVOKE commands in the between-steps inbox read that already takes
    BODY_STOP, and the engine would re-read each mission from the rebuilt book before its step and before each
    compensation. Not done here: it applies a command ahead of its inbox order (a DEVICE_ENROLL and a
    DEVICE_REVOKE of one key waiting together would refuse the revocation unless it is only taken early for a key
    delegated now), and it changes the turn loop that #273 also changes.
14. **A key revoked as a suspected compromise and delegated again.** Default (fix round): accepted, since the
    founder's own key signs it; the result carries a warning and the key's reviews, and the status shows the new
    delegation under the review. Alternative: refuse while the review is unanswered, or always.

## Limits

- A command the body refused is not attributed to a key in the review: the ledger keeps its digest and reason, not
  its signer.
- The review lists a device-signed resume, not everything a mission did after it.
- A body that stops after it applied a device's LIFECYCLE command and before it recorded the command's acceptance
  refuses the re-read file (the mission is already ended). The command then has no acceptance record: the review
  does not list it and the fold holds nothing for it. This predates the fix round.
- The separate appraiser judges closures. An abandoned mission has none, so the appraiser does not re-derive the
  hold on its compensations.
- A ledger shows what a key signed, never who held it.
- A replay-only stand-in book (no ledger, tests only) reads the signer a record states, unverified.
- SOP proposals (`greg/sop.py`) still count a device's approvals as history when proposing a pre-approvable step;
  the founder ratifies any such step with his own key.
- `resumed_and_still_running` reads the signer a `command.accepted` record states, as the review does.
- Run for this draft: 78 test files, this one (50 tests) and 77 neighbours (device, decisions, approvals,
  reconciliation, restore, goal gravity, appraisal, remote, the health, packaging and integrity gates): 1164 passed,
  109 skipped, 2 failed, both `recombined_native_game` tests that fail on `8d205324` in this container; the mutation
  gate: 68 of 68 mutants caught; `python -m governance.integrity --check`; `python -m acceptance check`;
  `python -m acceptance directive --against 8d205324`.
- Not run here: the whole test suite (about 90 minutes), the other mutation gates, hosted CI, the phone page in a
  browser. No independent review.
- Run for the fix round (2026-11-12, in this container, the two bullets above describe the first draft): 36 test
  files (the two of this unit, the four of the retained-receipt branch, every test file that names a revocation,
  a device or a delegation, the blocker, standing-approval, allowlist, health, packaging and integrity gates):
  812 passed, 3 skipped (no playwright, no bubblewrap, no black-start environment), 1 failed for a missing numpy in
  that environment and passed in the solver environment (14 passed); after the last test change the two files of
  this unit and the health gates again: 98 passed. `scripts/ci/check_revoked_device_mutants.py`: 69 of 69 and 43
  of 43 mutants caught. `scripts/ci/check_retained_receipt_mutants.py`: 31 of 31 and 8 of 8.
  `python -m governance.integrity --check`: 13 protected artifacts, all as authorized. `python -m acceptance
  check` and `python -m acceptance directive --against 8d205324`: exit 0. The reviewer's random-interleaving probe,
  40 seeds: 40 passed (it does not cover an abandon).
- Not run for the fix round: the whole test suite, the other mutation gates, hosted CI, the phone page in a
  browser. The fix round has not been independently reviewed.

## Rollback

Revert the branch. Bodies that recorded `decision.withdrawn` rows with `voided_by` keep them as history; the
previous fold treats their `voids_approval` rows as it treats a restore's. `device.integrity_review` rows and
review asks become unread data.
