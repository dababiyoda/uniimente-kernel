# ADR: a revoked device's unused authority authorizes nothing

- Decision ID: ADR-20261111-revoked-device-authority
- Status: proposed. A sandbox draft on the local branch `claude/revoked-device-authority-20261111`, based on the
  integration head `8d205324` (#196). Not pushed, not merged; adoption is a founder decision.
- Date: 2026-11-11
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
(`tests/unit/test_greg_revoked_device_authority.py`, first test). Of the 19 tests of that file that need no new
module, 17 fail on `8d205324`, 2 of them only because they read the new `MissionBook.voided` table; the 2 that pass
pin behaviour that already held.

## What a device may sign, and where authority is used

| A device may sign | What it changes | Does it authorize a later effect? |
| --- | --- | --- |
| DECISION `approve` on an APPROVAL ask | adds the exact scope to the mission's `approved_scopes` | Yes. Unpaid: it stands for the mission's lifetime, every time the mission selects that scope. Paid: it funds one run and is used up when that run is recorded (`MissionBook.consumed`). |
| DECISION `reconcile_executed` / `reconcile_not_executed` | settles one interrupted dispatch when the engine records it | Yes, until recorded: "not executed" releases the reservation and lets the action be dispatched again. |
| DECISION `reject` | rejects the scope, fails the strategy | No. It only narrows. |
| DECISION on an answer-only ask (HUMAN_WORK, CAPABILITY_ATTACH, COMPENSATION, EVIDENCE_CORRECTION, HUMAN_JUDGMENT, NO_STRATEGY, SENSOR_FAILURE) | a record; a HUMAN_JUDGMENT answer decides that one question for cognition | No Gate effect by itself. |
| LIFECYCLE | pauses, resumes, abandons or supersedes a mission | Not a grant: the mission runs under its own founder-signed mandate. |
| BODY_PAUSE, BODY_RESUME, BODY_STOP | pauses, resumes or stops the body | Not a grant. |
| CRITIQUE | evidence; may exclude a strategy | No. It narrows. |
| GOAL_CONTROL (narrowing controls only) | stops, lowers or narrows a goal | No. |

A device never signs MISSION, GOAL, CAPABILITY_ATTACH, DEVICE_ENROLL, DEVICE_REVOKE, key rotation or node
commands, and a mission's `pre_approved_steps` are inside the founder-signed MISSION.

The signer of every accepted command is on the ledger (`command.accepted`: `founder_key_id`, `signer`, the whole
signed envelope). An answer counts only as the mission fold re-derives it from a signature-verified DECISION at its
own ledger position (`MissionBook`, `goal_gravity.founder_facts`). Authority is used in one place:
`AuthorityOffice.act` admits an action outside the cone, or one the Constitution requires a human for, only if its
exact scope is in the mission's `approved_scopes`.

Two rules already held and are unchanged: a revoked key signs nothing new (`FounderVerifier`, "founder key not
enrolled or revoked"), so a DECISION signed before the revocation and delivered after it is refused; and a key
delegated again verifies only what it signs after the new delegation (`signed_not_before`).

## Decision

**The rule lives in the mission fold.** At the ledger position of a `device.revoked` record,
`MissionBook._revoked` voids every answer that key signed which still authorizes something not yet done
(`unused_authority`): an `approve` of an APPROVAL ask that is not used up, and a `reconcile_*` answer the engine has
not recorded. For each:

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
every completed action. And what authorizes nothing: rejections and answer-only records.

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
is read from the ledger as the revocation left it, so it is the same whenever it is built. It also reads the Gate's own grant records, so a dispatch
the mission had not recorded yet when the key was revoked is listed too. It rewrites nothing and
revokes nothing further. The answer to its ask is only recorded, and only the founder key gives it.

**The separate appraiser** (`greg/appraisal.py`). An approved action ran honestly only if an approval of its exact
scope was in force when the Gate dispatched it: signed by a founder key, or by a device key not revoked between its
answer and that dispatch (the position of the grant's record). A body without this rule is refuted; an action
dispatched before the revocation is still verified after it.

## Ledger records

| Record | New or changed | Fields |
| --- | --- | --- |
| `greg.device.revoked` | one optional field | `device_key_id`, `command_digest`, `at`; `suspected_compromise: true` only when the founder signed it |
| `greg.decision.withdrawn` | an existing type, new fields for this cause | `request_id`, `mission_id`, `voids_answer: true`, `voids_approval: true` (approvals only), `why`, `voided_by: {device_key_id, signer, revocation_event, revocation_command[, restore_id]}`, `kind`, `answer`, `answer_command`, `at`. Identity: request, `device-revoked`, revocation event |
| `greg.device.integrity_review` | new | `review_id`, `status: OPEN_FOR_FOUNDER_REVIEW`, `device: {device_key_id, label, delegations}`, `revocation: {event_id, command_digest, at, suspected_compromise}`, `commands[]` (digest, kind, signer, times, channel, `signature_verifies`, and per kind: request, answer, mission, scope, `standing`; lifecycle state; critique; goal control), `effects[]` (what rested on a command: action, attempt, status, capability, scope, receipt, cost, `rested_on`), `voided_by_this_revocation`, `missions`, `receipts`, `scopes`, `read_through`, `unknown`, `history_rewritten: false`, `revokes_further: false`, `authority_created: false`, `at` |
| `greg.decision.requested` | an existing type, new kind | `kind: DEVICE_INTEGRITY_REVIEW`, `mission_id: null`, evidence: the review event, counts, the first 20 rows of each list |

`greg status` gains `security.device_revocations` (what each revocation voided, the review's state). `greg device
revoke KEY --suspected-compromise` signs the field; `greg device reviews` reads the records.

## A dispatch already in flight

A revocation takes effect when the body records it: its next inbox read, at most one turn after the file arrives
(a new inbox file wakes the body). During a dispatch the body reads only BODY_STOP, as before. So:

- A dispatch the Gate claimed before the revocation was recorded runs to its end and keeps its receipt. If the
  body died inside it, the restarted body settles it from the Gate's own record, as before: a receipt is reused, a
  claim without a receipt is UNCERTAIN and goes to reconciliation. The appraiser places it at the grant's record,
  before the revocation, and verifies it.
- Nothing new is dispatched on the voided approval. A retry after `reconcile_not_executed` is a new effect and
  waits for a new approval.
- Mission steps later in the same turn still use the approvals as that turn began. Interrupting a turn or a
  dispatch is #273's subject and is not changed here.

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
  restore; a device answering the review.
- Operator: the turn pays one fold step and a few lookups. A review is one fold over the ledger prefix, built once.
- Beneficiary: the founder is asked again once per voided decision; nothing is undone behind his back.
- Constitutional: it only narrows. No protected artifact, no grant, no new command kind, no new authority path.

## Open questions for the founder (each with the default this draft implements)

1. **Rejections a revoked device signed.** Default: they stand (a rejection authorizes nothing). The review lists
   them. Alternative: ask again.
2. **Answer-only records a revoked device signed**, above all a HUMAN_JUDGMENT answer, which keeps deciding its
   question for cognition. Default: they stand and are listed. Voiding a HUMAN_JUDGMENT answer needs a change in
   the compiler: its request id is derived from the question and cannot be asked again under a new id.
3. **A mission or the body that a revoked device resumed, or a mission it abandoned** (compensations run after an
   abandon). Default: nothing is paused or undone; the review lists the command. Alternative: re-pause what the
   device resumed until the founder key resumes it.
4. **A standing approval on a mission that already closed.** Default: its remainder is voided and recorded like
   any other (one rule, no exception). Alternative: skip closed missions to keep the ledger quieter.
5. **Who closes a review, and what an answer does.** Default: only the founder key; the answer is only recorded.
   Alternative: a `reject` pauses the missions the review names.
6. **When a review opens.** Default: only when the founder signs `suspected_compromise: true` with the revocation.
   A suspicion that arises after a plain revocation has no command yet (the key is no longer delegated).
7. **Expiry and founder-key rotation.** Default: an unused approval of a device whose delegation merely expired,
   or of a founder key since rotated out, keeps standing. The policy sentence names revocation only.
8. **Timing.** Default: the revocation takes effect at the body's next inbox read, not at the moment of signing.
9. **Older ledgers.** Default: an appraisal run from now on refutes a closure whose action was dispatched on a
   revoked device's approval, also when that happened before this rule existed. Recorded appraisals are not
   rewritten.

## Limits

- A command the body refused is not attributed to a key in the review: the ledger keeps its digest and reason, not
  its signer.
- The review lists a device-signed resume, not everything a mission did after it.
- A ledger shows what a key signed, never who held it.
- A replay-only stand-in book (no ledger, tests only) reads the signer a record states, unverified.
- SOP proposals (`greg/sop.py`) still count a device's approvals as history when proposing a pre-approvable step;
  the founder ratifies any such step with his own key.
- Not run here: the whole test suite (about 90 minutes), the other mutation gates, the phone page in a browser.

## Rollback

Revert the branch. Bodies that recorded `decision.withdrawn` rows with `voided_by` keep them as history; the
previous fold treats their `voids_approval` rows as it treats a restore's. `device.integrity_review` rows and
review asks become unread data.
