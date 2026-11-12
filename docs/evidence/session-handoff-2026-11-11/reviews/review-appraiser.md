# Independent review of the appraiser detached-sensor unit (bf8e4b9f), 2026-11-12

Verdict: sound_with_fixes. Reviewer's worktrees: scratchpad/ra-head (bf8e4b9f), ra-base (8d205324), ra-mid (09eba869).
Probes: scratchpad/ra-probes/, logs scratchpad/ra-logs/. Run a probe on either tree with:
  mkdir -p $S/ra-tmp; cd $S/<ra-base|ra-head> && TMPDIR=$S/ra-tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:$S/ra-probes $S/venv/bin/python $S/ra-probes/<probe>.py

Confirmed: claim 1 (base runs the detached adapter in all three world states; head runs none and records UNAVAILABLE
once; branch tests on base 31 failed, 4 passed; on head 43 passed). Claim 3 (base crash-loops with EventError on
mission.unmet after detach/attach, and ALSO when the founder simply answers the NO_STRATEGY ask, and on
QUARANTINED -> VERIFIED -> ATTACH with a restart; head is fine). Claim 4 (gate 26/26; integrity; acceptance).
Claim 2 partly: the morning report shows the reason; Mission Control's Proof list shows UNAVAILABLE without the
reason text, and after a re-appraisal lists several rows for one mission with no closure identity (p4_standing.py, p13).

F1 (medium). The automatic re-appraisal after re-attach judges an old closure against the later world and records it
as failure evidence. p13_unmet_then_achieved.py: a failure closure waits while its sensor is detached; the founder
does the work and re-attaches; the mission achieves. Head ledger order: UNAVAILABLE (failure closure), VERIFIED
(achievement), REFUTED (failure closure: "status: world no longer matches"). Downstream on head:
sop.verified_appraisals lacks the mission; metrics.vepmc appraised_verified [False]; routing refuted 1 verified 0;
settling appraisal {}; autonomy.failures gains ('refuted','nudge'). Base: VERIFIED_UNMET then VERIFIED, all
downstream readers positive. p4_standing.py drift: a standing hold waits, the world drifts while detached, re-attach
-> REFUTED, autonomy failure, corrections APPRAISAL_REFUTED, routing refuted 1; base VERIFIED.
Cause: (a) the re-appraisal re-reads the world at re-attach time with no bound on the delay; (b) several readers take
the ledger-latest appraisal per mission whatever closure it names (sop.verified_appraisals, metrics.vepmc,
routing.track_record, settlement._settling_appraisals, acceptance.report). Part (b) predates the branch
(p13b_retry_window.py shows it on both trees inside the 3-tick retry window); the branch makes the window unbounded
and founder-triggered.
Suggested: a deferred re-appraisal must not write REFUTED from a world re-read once the mission has later
observations, actions or closures (keep UNAVAILABLE, or re-appraise only on the founder's command); and the
per-mission readers should key on the closure they mean, not on ledger order.

F2 (low-medium). A not-run sensor turns an unrelated refutation into an effect refutation in routing.
ra-probes/pt/test_ra_routing_blame.py: brief edited after delivery, brief.freshness detached. Base: checks false
['deliveries_bound_to_evidence'], routing refuted 0. Head: also 'world_reobserved' false, routing refuted 1 for
brief.engineering. Cause: checks["world_reobserved"] = reobserved and not unmeasured; routing.EFFECT_CHECKS reads a
False there as the capability's fault. Suggested: routing ignores world_reobserved when the appraisal carries
unmeasured_checks, or the appraiser reports "not measured" apart from False.

F3 (low-medium). sop.trend and greg path N4 count UNAVAILABLE as a failed appraisal (p6_sop_reader.py): fourth SOP run
UNAVAILABLE -> compounding False, "quality not held", quality_failures [{'appraisal': 'UNAVAILABLE'}].
compounding.retained_reuse words any non-VERIFIED appraisal as "(appraisal rejected it)" (read, not run). The reader
predates the branch; a plain founder detach now reaches it. Suggested: an appraisal with not_run is "not yet
appraised" there.

F4 (low). 15 further mutants, 6 survived (ra-probes/my_mutants.py, logs my-mutants.log, my-mutants-2.log):
B4 removes `*again` in the "body died before the final record" branch of _appraise_closure: on the mutated copy
p10_kill_before_final.py crashes with EventError on mission.appraised every tick after restart (same crash-loop class
as claim 3, ungated). A7 removes delivery gating for everything but brief.engineering (venture.assess,
organs.exchange untested). E1 "one failure closure per action count" becomes "one per mission ever": no test pins a
second failure closure at a higher action count. B10, A5, B14: little or no effect.

F5 (low). After the founder answers the NO_STRATEGY ask the mission re-blocks each cadence on the answered request:
over 10 ticks, 10 observed, 10 blocked, 10 unblocked, 10 receipts (p5c_churn.py). Base crashed on this path.
Suggested: when the answered request is the one the engine would raise again, keep the blocker.

F6 (informational, same on both trees). A method nested inside an attached cognition.solve sensor, detached after
closure: REFUTED and no re-appraisal after re-attach (p7_nested.py). A function-named sensor: nothing is re-run on
either tree and the closure is VERIFIED with world_reobserved True (p8_function_sensor.py). An unavailable binary:
the adapter is called and REFUTED recorded; head checks attach state, not manifest.available()
(p11_unavailable_binary.py). The new gate's anchors are not statically checked.

Clean: re-attach is appraised exactly once in seven variants (p3_reattach.py); QUARANTINED, VERIFIED, DISCOVERED run
nothing on head; Body.appraise is the only spawn of the appraiser; settlement credits nothing under UNAVAILABLE
(p9_settlement.py); 819 gate anchors inspected, none stale.
Not run: the whole suite; organ deliveries (no checkouts); bubblewrap; the merge with 41fcc41f; a DETACH arriving
while an appraiser child runs.
