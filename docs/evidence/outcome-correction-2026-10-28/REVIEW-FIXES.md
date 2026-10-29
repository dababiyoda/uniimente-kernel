# Review fixes for the correction round (2026-10-28)

**Review:** `session_01Kucyfoabgsg6W8H8xj4qea`'s re-review of #210, posted on #196 at
[comment 6481186880](https://github.com/dababiyoda/uniimente-kernel/pull/196#issuecomment-6481186880). It found
eleven settlement defects (S1 to S11) and five items on the experiment record. Each finding came with a probe and
two skeptics' verdicts, and was re-run on #196 `917404cf`. All reviewers are the same model family as the author,
so this is cross-session review, not independent review.

- **Fixed by:** `session_01KucyfnwWG7Lgp8QvCTKeHg` (#210's author), on a fresh branch from #196 `917404cf`, under
  the existing #96 claim.
- **Unchanged:** authority, merges and spending.

## The settlement defects: fixes, and what the second review found still open

| # | Defect | Fix | Test (fails on `917404cf`, passes here; for S8 and S11 see the footnote) |
|---|---|---|---|
| S1 | A resolution counted on a bare `command.accepted` digest, never checked against what the founder signed | `_resolutions` counts a resolution only when its digest names a verified REALIZATION envelope whose signed body equals it (same receipt, resolves and accept), and at most once per signed command. `goal_gravity` now verifies REALIZATION envelopes (`EVIDENCE_KINDS`: envelope, fresh nonce and signed validity) without making them goal or mission facts. | `test_s1_…`; on a real body, `test_greg_outcome_resolution_signed.py` |
| S2 | A partial invalidation adjudicated the founder's own report | An invalidation must name every live report (record time). A state is `adjudicated` only when a fact a resolution accepted holds the value (replay). | `test_s2_…`; on a real body: refused |
| S3 | A matching independent report after a conflict was dropped, so the dispute dead-ended; re-reports after an invalidation were deduplicated against rejected facts | Each new report is its own fact, keyed by source and value. Deduplication is only against live facts. | `test_s3_…` (both sequences) |
| S4 | An older-signed resolution delivered later overrode a newer one | Resolutions are ordered by the verified envelope's `issued_at`, then journal order. **Partly open (second review F4):** the order compares `issued_at` as a string, and record time checks a resolution against delivery order, not signing order. **Completed in #221 (F4):** instants, and an older-signed resolution on any of the same facts is refused with the reason. Inbox read order fixed in #221 after the review of #221 (G4-a: `inbox_stamp`). | `test_s4_…` |
| S5 | `reconcile` wrote false invalidations of superseded legacy rows on later passes | A legacy identity counts as succeeded on every pass | `test_s5_…` (reproduces the false invalidation on `917404cf`) |
| S6 | A dispute hid a certain failure (the signed check failed) and could lift a demotion | A disputed answer whose check failed is scored wrong. Its row has no decision value (`hold`). | `test_s6_…` |
| S7 | Decision value counted disputes that cannot settle | Only disputes whose mission holds a settling appraisal are weighed. Others are held, naming the appraisal. | `test_s7_…` |
| S8 | `hold` missed Laplace rank flips | Flags a flip of the Laplace rank against every other settled method. **Partly open (second review F3):** a co-eligible fit with no settled outcome (read at 0.5 by the compiler) and an exact tie are not compared. **Completed in #221 (F3).** | `test_s8_…`* |
| S9 | Unsigned facts were eligible to be accepted | Only a fact carried by a verified REALIZATION envelope whose signed body is that report can be accepted. Each report row shows its `signed_command`, except a signed report that omits `source`, which shows none (second review F7; fixed in #221). | `test_s9_…` |
| S10 | `answer_version` hashed the engine label, so an engine upgrade split one answer | The version hashes the answer fields only (`ANSWER_PROVENANCE_FIELDS` excluded). **Introduced a defect (second review F1):** records written by `917404cf` carry the old digest, and the first tick after an upgrade invalidates them. **Fixed in #221 (F1)**; two old versions of one answer are merged by a `merged_into` row (F1-a, after the review of #221), except on a body `8e91315c` reconciled (round 3, F1-r3-1). | `test_s10_…` |
| S11 | Unadjusted Fisher against the compiler's Holm | The preference bound runs the compiler's own `_settled_preference` on both extreme count maps. **Not fixed (second review F2):** it is called on two methods at a time, so Holm adjusts over one challenger, and the result equals the old unadjusted test on every count map probed. **Fixed in #221 (F2):** Holm over every co-eligible family. The review of #221's F2-a, F2-b and F2-d are fixed and F2-c narrowed; open: round 3's F2R-1 to F2R-4. | `test_s11_…`* |

\* S8 and S11 fail on `917404cf` because the weighing function's signature changed, not by a behavioural
assertion. That is weak fail-before evidence, recorded as such. The second review found that a behavioural
fail-before exists for S8 on the public path (signed reports on a real body, the row read from
`awaiting_realization`), and that none can exist for S11 until it is fixed, because its change alters no result.
#221's `test_f2_…` is that fail-before for S11 (it fails on `8e91315c`).

**Shared-file change:** `greg/goal_gravity.py` gains `EVIDENCE_KINDS = ("REALIZATION",)`, about 8 lines in 4
spots. Its consumers of `VERIFIED_KINDS` are unchanged. The integrator was told before review.

## The experiment record, corrected

- **Prediction 2:** the test now also asserts, as a check added after the run, that the compiler's existing
  selection rule decided: its settled-outcome preference names the construction as `against` and `flow_maxflow`
  as `preferred`, at selection level `preferred_by_settled_outcomes`. (Corrected 2026-10-29, R2: this entry first
  called that rule "the frozen rule"; the frozen rule is the declared scoring rule, and it is unchanged.)
- **Prediction 5:** missed as worded. The method total is (5 of 11), not (4 of 10). The ten reported claims are
  (4 of 10), and six of them were corrected. The README now says so, in its body and its section heading.
- **Prediction 8:** missed as worded on one point. The declaration said "two founder attaches", but the setup
  records three: one founder command and two signed read-only `auto_attach`. The test asserts the `by` text of
  those three ATTACHED events, which is weaker than the declared safeguard (second review R6).
- **Raw logs:** the final run of the test as committed is recorded in `run-final.txt`, with `git rev-parse HEAD`
  and the test file's sha256. Run 1's log stays a tail, as the review noted. It is kept as found and marked as
  such here.
- **Ablation:** the test's stand-in for `_resolutions` takes the new `signed` argument. Before this fix, arm
  B-after would have raised `TypeError`, not ablated.

Unchanged: the declaration (`3886d727`), the frozen rule and the arms. #213 is untouched.

## Second review: record corrections (R1-R6), 2026-10-29

**Review:** `session_01Kucyfoabgsg6W8H8xj4qea`'s review of #219's fix round, posted on #196 at
[comment 6485774890](https://github.com/dababiyoda/uniimente-kernel/pull/196#issuecomment-6485774890). Each finding
went to two skeptics; same model family, so cross-session, not independent, review. Record items R1-R6 are corrected
here by the reviewer, under the split agreed with the author; the settlement findings F1-F8 are the author's (below).

| # | Finding | Correction |
|---|---|---|
| R1 | The README heading still said "run 2 passed", and "the ten corrected claims" should read "the ten reported claims" | Heading names the met and missed predictions; "reported claims", six corrected. The test docstring's "verbatim" claim is in the test file and is the author's to correct with the F fixes. |
| R2 | "The frozen rule" named the compiler's selection rule as well as the declared scoring rule | Prediction 2's added check is labelled as the existing selection rule, checked after the run (README and above). The test comment is the author's. |
| R3 | `mutants-review.txt` counted N9 as caught, but N9 did not compile; the gate counted any non-zero exit as CAUGHT | `mutants-review.py` now marks INVALID a missing target, a mutant that does not compile, a run with no failed test and a run over its time limit. It refuses a modified `greg/`, `tests/` or gate, or a `settlement.py` that differs from HEAD's; checks the baseline first; disables bytecode; and restores `settlement.py` on SIGINT, SIGTERM and SIGHUP. It records HEAD and the sha256 of `settlement.py` and the three test files, not of every module the tests import. N9 replaces only the condition. `mutants-review.txt` is re-recorded: 13 of 14 caught, N2 MISSED, not equivalent (a test is owed). Re-recorded again on #221's fixes: 22 of 24 caught; N2 caught, N6 harmless on the production path, N18 (F3's tie) missed. After the fixes for the review of #221 (`5b4e293f`, N25-N36 added, multi-file targets): 32 of 36 caught; N6 harmless; N27, N33 and N35 missed. |
| R4 | The README described the mechanism as it was before S1, S2, S4, S6-S9 | Updated to the code at `8e91315c`, with the open gaps F1-F6 marked where a statement depends on them. The limit that the Fisher comparison is unadjusted stays: it is still true (F2). Updated again to #221's code: the unadjusted-Fisher limit is replaced, and the open items of the review of #221 are marked ([comment 6491739752](https://github.com/dababiyoda/uniimente-kernel/pull/221#issuecomment-6491739752)). Updated again to `5b4e293f` with round 3's open items ([comment 6499707581](https://github.com/dababiyoda/uniimente-kernel/pull/221#issuecomment-6499707581)). |
| R5 | Only `run-final.txt` was bound to the fixed code; `broad-review-fixes.txt` names no commit or command | The README separates evidence on the fixed code (`run-final.txt`, `integrator-intake-runs.txt`, `mutants-review.txt`) from evidence on the earlier code, and says that `broad-review-fixes.txt` is an unbound snapshot. `mutants.txt` is labelled as run at `90c1b118`. |
| R6 | Prediction 8's setup guard compares only the `by` text of ATTACHED events | Recorded above; the stricter assertion is in the test file and is the author's. |

## Second review (F1-F8)

_To be filled by `session_01KucyfnwWG7Lgp8QvCTKeHg` with the settlement fixes for F1-F8._
