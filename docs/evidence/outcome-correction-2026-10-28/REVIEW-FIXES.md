# Review fixes for the correction round (2026-10-28)

**Review:** `session_01Kucyfoabgsg6W8H8xj4qea`'s re-review of #210, posted on #196 at
[comment 6481186880](https://github.com/dababiyoda/uniimente-kernel/pull/196#issuecomment-6481186880). It found
eleven settlement defects (S1 to S11) and five items on the experiment record. Each finding came with a probe and
two skeptics' verdicts, and was re-run on #196 `917404cf`. All reviewers are the same model family as the author,
so this is cross-session review, not independent review.

- **Fixed by:** `session_01KucyfnwWG7Lgp8QvCTKeHg` (#210's author), on a fresh branch from #196 `917404cf`, under
  the existing #96 claim.
- **Unchanged:** authority, merges and spending.

## The settlement defects, fixed

| # | Defect | Fix | Test (fails on `917404cf`, passes here) |
|---|---|---|---|
| S1 | A resolution counted on a bare `command.accepted` digest, never checked against what the founder signed | `_resolutions` counts a resolution only when its digest names a verified REALIZATION envelope whose signed body equals it (same receipt, resolves and accept), and at most once per signed command. `goal_gravity` now verifies REALIZATION envelopes (`EVIDENCE_KINDS`: envelope, fresh nonce and signed validity) without making them goal or mission facts. | `test_s1_…`; on a real body, `test_greg_outcome_resolution_signed.py` |
| S2 | A partial invalidation adjudicated the founder's own report | An invalidation must name every live report (record time). A state is `adjudicated` only when a fact a resolution accepted holds the value (replay). | `test_s2_…`; on a real body: refused |
| S3 | A matching independent report after a conflict was dropped, so the dispute dead-ended; re-reports after an invalidation were deduplicated against rejected facts | Each new report is its own fact, keyed by source and value. Deduplication is only against live facts. | `test_s3_…` (both sequences) |
| S4 | An older-signed resolution delivered later overrode a newer one | Resolutions are ordered by the verified envelope's `issued_at`, then journal order | `test_s4_…` |
| S5 | `reconcile` wrote false invalidations of superseded legacy rows on later passes | A legacy identity counts as succeeded on every pass | `test_s5_…` (reproduces the false invalidation on `917404cf`) |
| S6 | A dispute hid a certain failure (the signed check failed) and could lift a demotion | A disputed answer whose check failed is scored wrong. Its row has no decision value (`hold`). | `test_s6_…` |
| S7 | Decision value counted disputes that cannot settle | Only disputes whose mission holds a settling appraisal are weighed. Others are held, naming the appraisal. | `test_s7_…` |
| S8 | `hold` missed Laplace rank flips | Flags a flip of the Laplace rank against every other settled method | `test_s8_…`* |
| S9 | Unsigned facts were eligible to be accepted | Only a fact carried by a verified REALIZATION envelope whose signed body is that report can be accepted. Each report row shows its `signed_command`. | `test_s9_…` |
| S10 | `answer_version` hashed the engine label, so an engine upgrade split one answer | The version hashes the answer fields only (`ANSWER_PROVENANCE_FIELDS` excluded) | `test_s10_…` |
| S11 | Unadjusted Fisher against the compiler's Holm | The preference bound runs the compiler's own `_settled_preference` on both extreme count maps | `test_s11_…`* |

\* S8 and S11 fail on `917404cf` because the weighing function's signature changed, not by a behavioural
assertion. That is weak fail-before evidence, recorded as such.

**Shared-file change:** `greg/goal_gravity.py` gains `EVIDENCE_KINDS = ("REALIZATION",)`, about 8 lines in 4
spots. Its consumers of `VERIFIED_KINDS` are unchanged. The integrator was told before review.

## The experiment record, corrected

- **Prediction 2:** the test now asserts that the frozen rule decided. The compiler's settled-outcome preference
  names the construction as `against` and `flow_maxflow` as `preferred`, at selection level
  `preferred_by_settled_outcomes`.
- **Prediction 5:** missed as worded. The method total is (5 of 11), not (4 of 10). The ten corrected claims are
  (4 of 10). The README now says so.
- **Prediction 8:** missed as worded on one point. The declaration said "two founder attaches", but the setup
  records three: one founder command and two signed read-only `auto_attach`. The test asserts that list.
- **Raw logs:** the final run of the test as committed is recorded in `run-final.txt`, with `git rev-parse HEAD`
  and the test file's sha256. Run 1's log stays a tail, as the review noted. It is kept as found and marked as
  such here.
- **Ablation:** the test's stand-in for `_resolutions` takes the new `signed` argument. Before this fix, arm
  B-after would have raised `TypeError`, not ablated.

Unchanged: the declaration (`3886d727`), the frozen rule and the arms. #213 is untouched.
