# ADR: Fourth increment of the Goal Gravity loop — founder return report, host-trigger wake schedule, open-attempt guard, third-issuance provenance

- Decision ID: ADR-GOAL-GRAVITY-003
- Status: proposed (draft PR #160, fourth increment; adoption into `main` is a founder decision)
- Date: 2026-10-14
- Decision owner: Alfonso Lopez
- Deliberation level: Standard (additive read-only projections, one bounded edit to the loop's per-move path, no authority or contract change)
- Founder intent references: `INTENT-20261013-GOAL-GRAVITY`, `INTENT-20261014-founder-return-report`, `INTENT-20261014-host-trigger-wake-schedule`, the fourteen records in `docs/intent/INTENT-20261014-egregore-synthesis-materials.json`, `INTENT-0030`, `SR001-FOUNDER-LOOP-ENTRY`
- Deliberation record: `docs/collaboration/deliberation-goal-gravity-fourth-increment-2026-10-14.json` (validator exit 0)
- Supersedes: none (additive to ADR-GOAL-GRAVITY-001 and -002)
- Superseded by: none

## Problem

**Observations.** On 2026-10-14 the founder issued the Goal Gravity directive a third time, in a new session
(`session_01TnTfFXr93jtNSzVD9SWeGx`), together with five supplementary essays, a founder-voiced "at full intended
maturity" statement, the 2026-09-05 external audit and three AI-generated PDFs (all preserved with lineage; see
`docs/intent/sources/GOAL-GRAVITY-DIRECTIVE-2026-10-13-source.md`, "Third issuance"). Draft PR #160 already carried
targets A–I in three increments (767 tests, CI green, mergeable). Its per-goal `status()` and global `measures()` did
not answer the founder's own acceptance scene — one report after a multi-day absence of what executed with receipts,
what was prepared, what policy blocked, what is unknown, what waits for him, what it cost and what was learned — and
nothing told a host scheduler when to call `turn()` (entry gate G5/P1).

**Reproduced defect.** While writing the report's tests, a defect in the third increment reproduced on `6ce6b3f`
(`tests/evidence/goal-gravity-20261013/defect-repro-increment-4.log`): a goal with an open attempt (`unknown`) woke again
without a grant; the classifier prepared the route; the loop wrote a fresh `planned` intervention record for the same
route; `_latest_by_route` then reported `planned`, the reconciliation blocker was dropped, and on the next turn with a
grant the executor ran a second time and the Gate recorded a second dispatch claim under the attempt-suffixed proposal
id. The same path overwrote `executed` routes, which lost their receipt in `status()` and became unverifiable.

**Inference.** The residual CapabilityDeficit this issuance exposes is (a) the return report, (b) the wake-schedule view,
(c) the open-attempt guard. The supplementary materials are mechanism sources and aspirations that need lifecycle
states, not new architecture.

## Decision

Build the residual as a fourth increment on `claude/goal-gravity-loop-20261013` (no parallel lineage, per directive §22):

1. `egregore/absence.py` — `AbsenceReporter.report(since, until)`: a deterministic, idempotent fold of ledger records whose
   logical time falls in the window: turns, executed moves (with receipt hashes, reconciliation flags and any independent
   verification as of the window end), prepared moves, Gate refusals, classifier withholding, open attempts as of the end,
   reconciliations, discrepancies, verifications, decisions waiting / deferred / information items, founder activity
   (`away` when none fell in the window), money as declared estimates with reconciliation flags and an explicit "not a
   bank statement" note, retention, learning, deficits, intersections, advancement, capability lifecycle, evidence tier and
   a deterministic headline. Recorded once per identical content as `egregore.return_report`; kind `information`;
   requests nothing. Exposed as `GoalGravityLoop.return_report`.
2. `egregore/schedule.py` — `WakeSchedule.entries/next_trigger`: cadence due times for sleeping goals and resurface times
   for deferred asks, the earliest of them, and a stable `trigger_id_for`; appends nothing, runs nothing. Exposed as
   `GoalGravityLoop.wake_schedule`.
3. `egregore/gravity.py` — the prior-attempt guard moves before classification: a route whose latest record is an open or
   completed attempt is never re-classified, never re-asked, never re-dispatched; the entry keeps the note the earlier
   tests pin (`already attempted; no duplicate consequential action`) and adds a `disposition`. `reconcile()` remains the
   only release path.
4. `egregore/closure.py` — the authority closure inspects the two new components; the evidence closure asserts the report
   is ledger-derived information (no executed move without a receipt, prepared never counted as executed, `requests_nothing`).
5. Provenance and records — the supplementary materials verbatim
   (`docs/intent/sources/EGREGORE-SYNTHESIS-MATERIALS-2026-10-14-source.md`), the audit verbatim with a Kernel-side
   disposition table (`docs/collaboration/UNIIMENTE-AUDIT-2026-09-05-external.md`), fourteen intent records with lifecycle
   states, this ADR, the deliberation record, evidence logs.

## Effect compilation

- **Founder expression.** "You disappear from operational involvement for several days. When you return, UNIIMENTE does
  not merely tell you, 'I completed 842 tasks'. It tells you: Three authorized missions remained active [...] $18,430 moved
  through authorized budgets; every movement reconciled. Two actions were blocked by policy. One decision exceeds
  delegated authority and is waiting for you. Here are the receipts, causal evidence, failures, financial results, and what
  the institution learned."
- **Intended effect.** One truthful digest of a window from durable records; a host can discover due work from durable
  state; no route with an unknown outcome is ever hidden or retried blindly.
- **Literal requirements.** The report's content classes above; the six evidence states; the window semantics.
- **Metaphor / aspiration.** "$18,430 moved" and "closed one paying customer" describe settlement and commercial closure the
  ledger does not record; the report labels money as estimates and says no settlement record exists.
- **Simplest viable mechanism.** A fold of records the loop, Gate, attention router and retention already write. That is
  what was built; no new record type except the report's own.
- **Existing mechanisms searched.** `status()`, `measures()`, `_founder_burden()`, `compounding_report()`, `advancement`
  reports, `due_for_review()`; DALEOBANKS digest/operator_line as mechanism sources (not wired).
- **Residual deficit.** Cross-goal windowed digest; wake-schedule view; the guard.
- **Falsification.** A prepared move counted as executed; an executor's `validation_status` counted as verification; two
  loops over one ledger producing different reports; a second record for identical content; a schedule listing a paused
  or revoked goal; a second dispatch of a route whose first outcome is unknown.

## Alternatives

| Alternative | Benefits | Liabilities | Disposition |
|---|---|---|---|
| Fourth increment on #160 (selected) | one canonical lineage; folds existing records; reversible | more code on an unruled draft | EXPERIMENT |
| Stacked child PR | isolated review | 119th open draft; strands on a base ruling | rejected; revive if the founder wants increment-level units |
| New PR off main | mergeable alone | must recreate #160's substrate: the parallel GREG the directive forbids | rejected |
| Fold into #173 | one lineage | 315 uninspected commits awaiting its own ruling | rejected; revive on founder adoption of #173 |
| Do nothing | no risk to the loop | intentions lost; duplicate-dispatch path latent; P1 view absent | rejected |

## Five-role debate, two passes, dissent

See the deliberation record. All five roles recommend EXPERIMENT. Dissent preserved: the Adversarial Reviewer asks that
the guard and its two regression tests be separable from the new features if a reviewer requests it; the Evidence and
Welfare Guardian notes the scene is served in form, not substance, until one real consequence under a founder-issued
grant appears in a real return report.

## Adversarial review of this increment

An independent review workflow (five dimension reviewers, three refuting skeptics per finding; `confirmed` needs two of
three) ran against the uncommitted increment before push. Its findings and dispositions are in
`tests/evidence/goal-gravity-20261013/review-increment-4.json`; confirmed findings are fixed with regression tests in the
commit that follows the implementation commit, as in the third increment. See the PR body's fourth-increment section for
the table.

## Evidence tier

IMPLEMENTED, UNIT-TESTED, INTEGRATION-TESTED on synthetic JSONL ledgers with test passports, the development witness key,
scripted executors and test-minted grants. Not SANDBOX-VERIFIED, not EXTERNALLY VERIFIED, not FOUNDER-ACCEPTED. No host
scheduler has called `turn()` on its own clock. CMC, VDM and VEPMC remain 0.

## Not achievable in this increment (preserved targets with blocking dependency)

- A delivery channel for the report (none is contacted): founder channel decision and authentication (G6).
- A host trigger that fires the schedule: founder selection (G5).
- A report of settlement or payment: no settlement record type exists on the ledger; organ-side payment adapters.
- The scene's "closed one paying customer" and "restored the function in canary": commercial closure and a capability
  builder lineage (#129/#164/#137) remain blocked as the earlier ADRs state.

## Rollback and kill criteria

Revert the fourth-increment commit; records remain as evidence. Kill if any path lets the report or schedule be cited as
authority, if the guard ever admits a second dispatch of an unknown-outcome route, if the founder rules the lineage
non-canonical, or if a real return report misstates its counts against the ledger.
