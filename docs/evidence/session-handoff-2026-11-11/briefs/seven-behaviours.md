# Brief: the composed machine's acceptance mission (seven behaviours, one mission)

You are writing ONE integration test file (plus the smallest helpers it needs) in the UNIIMENTE Kernel repository.
Work only in the worktree named in the message that sent you here. Commit locally. Push nothing. Post nothing.

## Why

The founder (2026-11-12, verbatim): "Prove that the composed machine can: Execute an authorized mission through
its actual entry point. Preserve correct outcomes through interruption and restart. Respect capability identity
and device revocation. Preserve completed work when a dependency fails. Distinguish uncertainty, timeout, refusal,
failure, and refutation. Bind an appraisal to the specific closure and evidence it actually evaluates. Explain its
outcome, costs, remaining uncertainty, and next step." And the combined experiment: "interrupt a mission,
invalidate one supporting observation, remove its preferred tool, and preserve an already completed effect."
Also: "Green results on separate branches do not establish compatibility."

The worktree is a composed tree: the integration line plus about a dozen open heads merged together. Each head has
its own tests. Nothing yet shows the seven behaviours on one mission on this tree. Your test is that evidence. It is
an acceptance test of what exists: **you change no product code.** If the machine fails a behaviour, that is a
finding to record, not something to patch here.

## What to build

`tests/integration/test_composed_machine_acceptance.py`. Real processes where the claim needs them.

Read first, and reuse their helpers rather than writing new ones:
- `tests/integration/test_whole_machine_trace_process.py` (a `greg run` Body as its own OS process; the founder acts
  through `greg decide`, a separate process; the founder reads with `greg foundry trace|why|changed`);
- `tests/integration/test_one_machine_ten_steps.py` (SIGKILL mid-operation, restart, appraiser as a process; it needs
  supervisord and solvers, which this container may lack: do not depend on either);
- `tests/unit/test_greg_revoked_device_authority.py` (how a device key is enrolled, signs a DECISION, is revoked);
- `tests/unit/test_greg_retained_receipt.py` and `test_greg_retained_receipt_history.py` (how a Gate receipt is
  classified DONE / REFUSED / FAILED / UNCERTAIN and recovered after a restart);
- the tests that detach a capability and show the office refuses to run or receipt it under another identity
  (grep `detach` in `tests/unit/test_greg_*attach*`, `test_greg_capability_identity*` or similar);
- `tests/integration/test_greg_compensation.py`;
- `greg/templates.py` (`workspace_note`, `engineering_brief`) for mission shapes; `greg/appraisal.py` for what the
  separate appraiser re-derives; `greg/mission_control.py` and `greg foundry trace` for the account.

Design ONE founder-signed mission (per-test Ed25519 key; never a real key) whose route has at least:
- **effect A**: an approved internal write that completes and is receipted early;
- **effect B**: a second approved step whose preferred capability is later detached;
- **check C**: a success check read through a sensor whose observation you can later make false or unreadable.

Then drive this sequence on a body that runs as its own OS process, started through the CLI (`python -m greg
--home <tmp> ...`), with every founder act a separate CLI process:

1. **Entry point.** Mission signed and submitted through the CLI; the body process picks it up. Assert from the
   ledger, not from in-process objects.
2. **Device approval and revocation.** A device key approves A; A runs and is receipted. The same device approves B.
   The founder revokes the device before B is dispatched. Assert: A's receipt and effect stand; B does not run on the
   revoked approval; the mission asks again under a new request id; the founder key (or re-approval) lets B proceed.
3. **Interruption.** SIGKILL the body process while B's dispatch is in flight (find how existing tests make a
   capability block long enough to be killed mid-dispatch; do not sleep-and-hope). Restart the body. Assert: the
   interrupted dispatch is classified UNCERTAIN (not DONE, not FAILED), nothing is redispatched blind, the founder is
   asked to reconcile (or the Gate's own record settles it, whichever the composed tree does: record which), effect A
   is not replayed (exactly one receipt, one file write, by content and by count), and no cost is booked twice.
4. **Preferred tool removed.** Detach B's capability (the founder-signed way). Assert: the office refuses to run or
   receipt B under that identity; the refusal is recorded as a REFUSAL, distinct from a failure; completed A still
   stands; the mission's state names what it now needs (an attach decision, another route, or a typed blocker).
5. **Observation invalidated.** After the mission has reached a closure (or a decision that rested on check C), make
   C's observation false. Assert what the machine does: it must not keep counting the earlier reading as current.
   Then make C unreadable (the sensor errors or its capability faults). Assert: an unreadable reading is recorded as
   unmeasured, not as a failed check, and no strategy is blamed for it.
6. **Five outcomes kept apart.** By the end, the ledger must hold, for this one mission, at least one instance each
   of: an UNCERTAIN outcome (step 3), a timeout that is not a measured failure (make a sensor or step exceed its limit;
   if the composed tree has no path that records a timeout distinctly, say so and mark that one assertion as the
   documented gap, see "Known gaps"), a REFUSAL (step 4), a measured FAILURE (a check that reads false), and a
   REFUTATION (run the separate appraiser on a closure whose deliverable you tampered with, then restore it and show
   VERIFIED again). Assert the five are distinguishable by a field a reader can name, and that none was folded into
   another.
7. **Appraisal bound to its closure.** The mission closes more than once in this story (or closes, reopens, closes).
   Assert that each appraisal record names the closure it judged (closure id / ledger position / evidence digest) and
   that a verdict on the earlier closure is not read as a verdict on the later one by `greg foundry trace`,
   `greg vepmc`, `greg routing`, the SOP trend and the acceptance report. Where a reader takes "the latest appraisal
   for the mission" regardless of closure, that is a known defect on this tree (see "Known gaps").
8. **The account.** Run the founder-facing readers as CLI processes (`greg status`, `greg decisions`,
   `greg foundry trace <mission>`, `greg blockers`, Mission Control's data if it has a non-browser reader) and assert
   they state, truthfully for this ledger: the outcome; every action and what it cost (zero model spend here, and the
   count of dispatches); what is still uncertain; what happens next or what decision is waited on.

## Known gaps: how to record a behaviour the tree does not have

Three units that repair known defects may or may not be on this tree: (a) a compile or sensor the host stalled is
read as a measured failure; (b) several readers take the latest appraisal per mission whatever closure it judged;
(c) the appraiser re-reads a detached sensor. For an assertion that fails because of one of these (or any other
real defect you find):

- First make sure it is the machine and not your test: reduce it to the smallest reproduction and read the code path.
- Keep the assertion exactly as strict as the founder's sentence. Do not weaken it, delete it, or skip it.
- Mark that one assertion's test `@pytest.mark.xfail(strict=True, reason="<one sentence: the defect, file:line>")` so
  the file passes today, fails loudly the day the defect is fixed (strict), and the gap is counted. Put each such gap
  in its own small test function that shares the scenario fixture, so one gap does not hide the rest.
- List every gap in your report with its reproduction.

Never count a missing dependency as a pass: if something needs bubblewrap, supervisord, a browser or solver packages
that this container lacks, do not `skip` silently. Either build the scenario without it, or make the test fail with
the dependency named unless an environment variable says the dependency is expected to be absent, following how
`GREG_REQUIRE_BROWSER` is used on this tree (grep for it).

## Rules

- No product code changes. Test file, and helpers under `tests/` only. If you believe a helper belongs in
  `tests/greg_fixtures.py`, add it there.
- Never edit `constitution/*.ucl`, `authority/*.yaml`, `identity/*.yaml`, `policy/consequence_gate.py`,
  `governance/integrity/*`.
- Python: `/tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad/venv/bin/python`. Never
  `pip install`. One pytest process at a time; the machine has 4 CPUs and is shared. Kill only pids you started,
  never by name. Every subprocess you start in a test must be reaped in a `finally` (terminate, then kill).
- No sleeps as synchronization: poll the ledger or a file with a deadline, as the existing process tests do.
- The whole file should run in a few minutes. Deterministic: run it three times in a row before you report, and
  report all three results.
- Mission ids match `^m:[a-z0-9][a-z0-9._-]{2,80}$`. `Body` is a context manager.
- Read every number you report from output. Write plainly. No model name in any file or commit. They/them for any
  person whose pronouns are not stated. Commit trailer, exactly:
  `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`
  `Claude-Session: https://claude.ai/code/session_01Kucyfm9exT5imDVYvHTYSv`

## Report (raw facts)

1. Commit SHA and the file list.
2. For each of the eight steps: the assertion(s), passed / strict-xfail (gap) / could not build (why).
3. Every gap: the founder's sentence it falls short of, the defect in one sentence, file:line, the smallest
   reproduction, and which known unit (a/b/c above) it belongs to, or "new".
4. The three consecutive run results, each with its last output line and wall time.
5. Anything you could not determine, and anything about the composed tree that surprised you.
