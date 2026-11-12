# Independent review of the correction-containment credit unit (b01d319f), 2026-11-12

Verdict: sound_with_fixes. Reviewer's worktrees: scratchpad/rc-head (b01d319f), rc-base (8d205324); rc-fix is a plain
copy with a one-line patch (F3). Probes scratchpad/rc-probes, logs scratchpad/rc-logs. Run a probe with:
  cd $S/rc-head && RC_TMP=$S/rc-tmp PYTHONPATH=$S/rc-head:$S/rc-probes $S/venv/bin/python $S/rc-probes/<probe>.py
(for the base, replace both rc-head by rc-base; create $S/rc-tmp first).

Confirmed: claim 1 (p01_claim1.py: base credit [2,2] before and after the reject; head [2,2] then [1,1]); the head's
test file on base 11 failed, 23 passed; claim 3 (p02_targets.py step E); gate 50/50; solver environment 305 passed,
1 skipped (organ checkouts); integrity, acceptance, repo-health, layering, allowlist all pass; no set_state, grant or
approval write in the diff.

F1 HIGH. A standing mission's own next read gives the rejected answer its credit back. p03c_standing_fresh.py: after
the reject credit {}; after the mission's next cadence read credit {"cognition.swarm": [1,1]}, requalified 0, claim
NEEDS_REVIEW; settled rows: settled, withheld, settled. p03b_standing.py: the hold cites reading 2 and reading 3
already existed, so credit never drops. Cause: settle() in greg/cognition/settlement.py lets any later reading whose
receipt is not listed settle the same claim identity again. Contradicts MC-0003 "that claim's credit stays withheld".
Suggested: withhold by claim identity plus answer digest while an unrequalified FOUNDER_REJECTED stands on any reading
of that claim. No test covers a standing mission (mutant R8).

F2 HIGH, founder decision. The byte-identical rejected answer earns credit again through a new mission.
p03_redelivery.py: same check signed as m:again, same answer (fitness identical), credit [1,1] -> [2,2]. Cause: claim
identity includes mission_id and command_digest. Question: should a rejection withhold the answer (input digest,
check, method, version, answer digest) across missions?

F3 HIGH, regression. A host stall on a later mission withholds a correct method's credit and asks the founder.
p05_timeout.py with argument timeout or crash: run_isolated raises TimeoutExpired (or exit 137) for the solver worker
while a second mission asks the same signed question. The reading: passed false, state UNKNOWN, abstentions
["UNKNOWN: ['TIMEOUT']"], no abstention_state key. Head: causes [["REPLICATION_FAILED","m:first","good"]], credit
[2,2] -> [1,1], asks ["NO_STRATEGY","EVIDENCE_CORRECTION"], still withheld after 2400 s of healthy host; returned only
at m:second's 3600 s cadence read. Base: the same false cause and ask, but credit stays [2,2]. Cause: a compile
receipt carries `state`, not `abstention_state`, so missions.unanswered returns None and the read counts as measured;
corrections.no_method_ran excuses only CAPABILITY_DEFICIT. Fix tried in rc-fix, one line in corrections.no_method_ran:
`output.get("state") not in (None, "ANSWERED", "WORLD_UNVERIFIED") or output.get("abstention_state") == "CAPABILITY_DEFICIT"`
-> causes [], credit stays [2,2], no correction ask; the unit file still passes 34/34. Keep REFUTED a real negative;
add tests for UNKNOWN/TIMEOUT and ABSTAIN.

F4 MEDIUM. A reject and an SOP_RATIFY in the same inbox tick ratify a proposal that rests on the rejected run
(p06b_inbox.py, p06_order.py a). Cause: ratify reads recorded evidence.correction rows and propagate runs after
ingest_inbox. Same one-tick lag for compile decisions (p06 e). Suggested: run corrections.propagate when a CRITIQUE
is applied, or have ratify read rejections directly as sop.trend does.

F5 MEDIUM. Several signed rejections have no effect and tell the founder nothing (p02_targets.py steps A-D,
p10_failures.py step 1): rejecting the earlier uncited reading of the same claim, the mission.appraised event, the
cognition.settled row, or the registration -> causes [], credit unchanged. Rejecting an unmet closure or its failing
reading -> causes [], credit stays [2,1]: a failure the founder disputes keeps counting against the method.
`greg critique EVENT_ID` accepts any retained event. Suggested: map a rejected reading, settled row or appraisal to its
claim, or refuse the critique with a reason.

F6 MEDIUM (the builder's question 4, with numbers). Readers left alone still credit rejected runs (p12_q3_q4.py,
p07_readers.py, p13_precedents.py): routing reliability of fs.write stays 0.8 after the founder rejects all three
runs (verified 3; greg/missions.py:1002 scores strategies with it). Earned autonomy stays level RECOMMENDER,
verified 3, verified_since_last_failure 3, founder_interventions 0. memory.precedents: locally_appraised_mission_count
2 -> 0, but action_evidence.count stays 2. A procedure ratified before the rejections stays RATIFIED and runnable,
baseline verified_outcomes 3, and sop.instantiate still builds a mission. MC-0003 does not say this.

F7 LOW. Unsigned rows are followed, and a bare evidence.requalified row lifts a founder rejection (p04_forge.py, rows
written with journal.record directly). No untrusted writer was found. Read, not run: CRITIQUE is in DEVICE_KINDS
(greg/founder.py:74), so a delegated device key can withhold credit. Suggested: _containing ignores requalification
for FOUNDER_REJECTED and requires command_digest to match a command.accepted.

F8 LOW. A dependent that binds a contained reading after the correction is recorded is never marked (p09_journal.py
cases 5 and 6): the stored `affected` is frozen at record time, so the result depends on tick timing.

F9. 8 of 17 extra mutants survive the unit's file (rc-probes/rc_mutants.py; rc-logs/rc-mutants*.txt): R1 the
construction branch skips the filter; R2 a contained failure still counts against the method; R3 once withheld, a
later uncontained reading never settles again; R4 withheld_by.class hard-coded; R7 contained_receipts lists only the
root; R8 a hold is never a contained mission; R11 any unanswered compilation is no replication; R16 reconcile names an
unrelated cause. R1 and R2 remove withholding for a whole class of outcome.

The builder's four founder questions as the code behaves: (1) rejecting an achievement withholds the whole claim,
including the failure the appraiser verified under the earlier unmet closure; (2) a later accept lifts nothing;
(3) after four clean runs the proposal is still the one with the rejected mission and ratify is refused;
(4) see F6.

MC-0003: "that claim's credit stays withheld" is false (F1); "which procedures are proposed or ratified" has the F4
window; "other abstentions were not examined" understates F3.

Clean: a correction before the appraisal is never credited (p14); restart identical; double reject idempotent;
fail-then-pass before the first tick requalifies in one propagation; the compiler's evidence index is a committed
file, not body state.
Not run: CI; the whole suite; a device-signed CRITIQUE; any founder device.
