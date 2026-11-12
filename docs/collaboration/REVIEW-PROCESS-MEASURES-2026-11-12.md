# Review process measures, 2026-11-11 to 2026-11-12 (one session's units)

Founder, 2026-11-12: "Keep independent review and turn those findings into reusable engineering improvements ...
Track whether the defect class recurs in later units. Test whether the improved process catches problems earlier.
Preserve review cost, integration delay, and escaped defects alongside test counts. Your stale-anchor scan is a
candidate improvement. Demonstrate where it helps and where semantic conflicts still escape it."

Scope and coverage: units built in session `session_01Kucyfm9exT5imDVYvHTYSv`. Costs are read from the session's
task notifications; the transcript before the first context compaction is partly summarized, so earlier per-agent
costs are incomplete and are marked "not recorded". Reviewers are separate agent processes on the same model (a
second process, not an independent operator).

## 1. Where each escaped defect was caught

"Escaped" means the unit's author had committed it as finished and its own tests and gate passed.

| Unit | Defect | Caught by | When (relative to the author's "done") |
|---|---|---|---|
| #294 | a mutant anchor in another gate left stale by the fix round | CI job 10 | about 1 h after push |
| #298 | a mutant that lost its only test | CI job 6 | after push |
| #300 | a stored draft patch could no longer apply (import line rewrapped) | CI jobs 1 and 9 | 75 min after push |
| #301 | a late re-read refuted a true closure; routing blamed unmeasured checks | independent review | before PR |
| #301 | a failure closure appraised after a restart is REFUTED for a world that changed since | the composed-machine acceptance test (#306) | after PR, on the candidate |
| #301 | a line turned into `elif` stranded a mutant anchor | the repository's own health test (the scan missed it) | before push |
| #303 | a standing mission and a new mission regained a rejected answer's credit; a host stall cost credit | independent review (9 findings, 3 high) | before PR |
| #303 | a test asserted another unit's old defect (passes alone, fails beside #304) | composing the two units (1 failed, 329 passed) | after PR |
| #303 | rejection reaches an unrelated action; relabelled re-signing escapes; REFUTED read as failed replication | second independent review | after the first fix round |
| #303 gate | 81 of 81 "caught" on a tree where its own test file failed | composing; reading the gate output by hand | after PR |
| #304 | a reading the host stopped could pass a check | independent review (13 findings) | before PR |
| #304 | a declined reading, and a direct-route timeout, still pass `absent` and close VERIFIED | second independent review (2 high) | after the first fix round |
| #305 | five false holds (the test envelope, not the code) | running the mission on 12 real heads, then re-running outside the envelope | after build, before PR |
| #305 | a planted file pair closes the mission VERIFIED with no action; a renamed test is skipped | independent review (17 findings, 2 high reproduced by the session) | after PR |
| #305 | a head and its descendant in one selection hide the old head's test | the pre-registered second case | after PR |
| #305 fix round | F18 (a fix for the first review) hides a measured behavioural conflict whenever another head or the base also edited the broken test's file; the head that caused it reads 'ready to take' and the command line exits 0 clean | second independent review (R1, high; reproduced by a skeptic) | after the fix round was pushed |
| #305 fix round | a cancelled re-run masks a stale failure; symlinked packs and `core.attributesFile` escape the pin; F18 reads head-controlled links in GREG's process; six mutants of new code survive a gate printing 42/42 | the same review (R2-R4, R6, R8, medium) | after push |
| #307 | the planted-mode baseline runs with `-x` and never sees a later failing test; nothing pins per-copy isolation | independent review (F1, F2, medium) | after push; CI green |
| #305 second fix round | a link check that walks one hop: a directory link to a place inside the roots, whose own entries link outside, still let git read packs, loose objects, `info/attributes` and an alternates listing from outside; the alternate depth was counted one level off from the git that runs | independent re-check of `b42d10f6` (R6 still reproduced; one new low) | after the second fix round, before push |
| #307 fix round | the new summary parser read words, not structure: a planted test whose message carried "short test summary info" turned a survivor into a catch | independent re-check of `9de5075b` (new low) | after the fix round, before push |
| #305 third round | **a boundary re-derived in Python instead of enforced by the kernel**: the pin re-implements git's parsing and path resolution and differs from git in six high ways (alternates and `commondir` parsing, FIFO listings, stores under skipped `hooks/`, long resolved paths, `.gitattributes` through a work-tree link a head can commit); all six present on every head since the first | independent re-check of `c6e79087` (escape lens; the layout lens found two false refusals the round introduced) | after three fix rounds; the structural fix (confine git in the Landlock envelope) is round 4 |
| #305 third round | a guard that a lower layer happens to cover: the "list each real directory once" rule had no test that needed it, because the kernel's 40-link limit ended a single loop anyway | the intake mutation gate (64/65) | before push |
| #311 | a path the body cannot look at raised `OSError` out of every tick; a 45 s timeout and missing bubblewrap were untyped refusals; a helper still writing the killed browser's profile turned the timeout into an unknown outcome | independent review (M1-M3, medium) | after push; CI green |
| #312 | open asks are not re-checked when a detach or re-attach changes what the selection would run (an approve of one strategy runs another; a moot ask blocks the mission); the alternative chosen may itself be unattached, and a re-attach no longer unblocks (regression) | independent review (X1-X5, medium, each reproduced by a skeptic) | after push |
| #304 | the ten-step one-machine test failed once in job 1 with a torn ledger tail (`partial or blank history record`); #304 does not touch the ledger | CI job 1 | after push; root cause under investigation |
| operational slice (orchestration) | **a finding list cut short on its way to the fixer**: the review confirmed 35 findings in three lenses; the workflow passed the fix agent the first 20,000 characters, so 13 confirmed findings (one lens's F7-F14, another's F1-F9) were never received; the fixer said so | the fix agent's own report ("the finding list I received was cut off during F6") | after the first fix round; the second round reads the whole review file itself |
| operational slice, case 2 | the transfer worked without product code, but the rule language has no lookup, loop or conditional, so case 2's rulebook is 2,199 generated lines tied to one contract; a duplicate has no route of its own; a payment is read for a declined case; a later draw's payment is never counted; needs are static, so extra facts are asked for | the pre-registered withheld case and its frozen naive baseline (12/12 against GREG's 11/12) | after case 1 was built and reviewed |
| #308 | `a995c3ce` (the session's own fix for job 11) moved job 8's two `GITHUB_ENV` lines into a new shell: job 8 ran with the browser variables empty and **passed** | independent review (F1, medium) | after push; **CI green**, so only review could see it |
| candidate `e0f84ed1` | a genome test raced the clock (UNKNOWN after 18,110 of 20,000 states on a loaded runner) | CI job 1 | after push; #309 |
| #291 + #273 | #273's call site refused beside #291 (13 of 17 tests) | composing by hand (2026-11-11); found again unaided by the intake mission (2026-11-12) | before intake |

Every independently reviewed unit in this window had at least one high-severity defect its author's tests did not
catch (#301, #303, #304, #305, and the earlier rounds of #294 and #300). In three units (#303, #304, #305) a
second pass found further high or medium defects after the first fix round. In #305 the second pass's high finding
was caused by a fix for the first (F18): fixes to decision logic need the same review as the logic. #307 and #308
(tooling) each had medium findings; #308's was invisible to CI because the job it broke still passed.

## 2. The stale-anchor scan: where it helps, where it cannot

`stale_anchor_scan.py` compares the gate anchors that matched a changed file on the base with the same file on the
head.

- **Helped:** the functional-reconstitution gate's anchor, caught before a push. `gates_for_changes.py`, its
  companion, now also checks stored patches a test names; run on `934a9f77` it flags the patch #300's CI later
  failed on, and it passes `0aa09c87` (retrospective: it did not exist when #300 was pushed).
- **Missed (a syntactic case it should catch):** #301's line turned into `elif`; the health test caught it.
- **Cannot see by construction (semantic conflicts):** #291/#273 (both units' anchors and tests intact; a call
  site meets a new refusal); #303's test pinning #304's old behaviour; the envelope false holds; every high
  finding of the reviews above. None is an anchor problem.
- **Noise:** on large merges it reports dozens of generic suspects (43 on the candidate `e0f84ed1`, all generic
  strings or anchors deliberately retargeted). A person still reads each.

Verdict: a cheap guard for one narrow class (an edit strands another gate's anchor). It does not detect
behaviour conflicts and should not be read as a compatibility check.

## 3. What now catches classes earlier, and the evidence

| Class | Earlier catch now in place | Evidence that it catches |
|---|---|---|
| a stored patch left unable to apply | `gates_for_changes.py` patch check | flags `934a9f77` (the #300 head CI failed on) |
| a gate judging mutants on a failing tree | shared runner baseline run (#307) | the new test fails without it; prevents the 81/81 reading on the three gates using the runner |
| a behaviour conflict between open units | the intake mission (#305) and the composed candidate (#299) | the mission found #291/#273 unaided (cause named); its follow-up case found #303-old/#304 unaided |
| a confined test failure read as a code defect | #305 `b032f38a` (own-head failure in the envelope is not checked) | on the first run's recorded inputs: false holds 5 to 0, true holds kept |
| a test that pins another unit's old defect | the intake mission, when the selection holds no descendant of the old head (F18 in fix) | pre-registered case: missed with the descendant present, found without it |

Not yet shown: that any of these caught a defect in a unit built **after** it existed. The first unit to test that
is the operational slice (built after all five), whose review results will be recorded here.

## 4. Cost and delay (recorded where read)

| Run | Tokens | Tool calls | Wall time |
|---|---:|---:|---:|
| intake mission build | 692,721 | 42 | 113 min |
| intake mission independent review | 378,936 | 67 | 26 min |
| composed-machine acceptance test build | 683,890 | 54 | 45 min |
| #303/#304 second fix-round review | 438,583 | 116 | 33 min |
| review of #305's fix round, #307 and #308 (13 agents, each finding re-checked by a skeptic) | 3,899,583 | 430 | 76 min |
| revoked-device, appraiser and two authority fixes (one workflow) | 4,944,815 | 1,104 | 223 min |
| credit, goal intake and two acceptance locks (one workflow) | 3,212,433 | 692 | 128 min |
| representation-repair design panel | 1,680,096 | 158 | 27 min |
| second #305 fix round and #307 fix round, each re-checked (4 agents) | 1,680,289 | 267 | 100 min |
| #311 fix round and independent re-check (2 agents) | 877,905 | 184 | 66 min |
| #312 independent review (7 agents, each finding verified) | 2,113,240 | 180 | 27 min |
| #305 round-3 re-check (2 lenses) | 740,673 | 109 | 29 min |
| operational slice: build, withheld case, three-lens review, fix, transfer measurement, naive baseline (8 agents) | 3,563,099 | 634 | 324 min |
| earlier single-unit reviews and fix rounds | not recorded | | |

Integration delay: none of these units has reached the integration line (`8d205324` unchanged since 2026-11-11);
the delay to intake is the integrator's and the founder's, not measured here. Time from a unit's first finished
commit to the report holding its last high or medium finding so far (commit times from git; report times when the
session read them): #304 `0f2b5052` 02:44 to 15:44 UTC, 13 h; #303 `b01d319f` 18:52 (11-11) to 15:44 (11-12),
21 h; #305 `885b7b7a` 10:16 to 15:43 UTC, 5 h 27 min. The first two spans include a stop of about six hours
when the session's usage limit halted every agent (03:45 to about 10:00 UTC).

## 5. What this changes in the procedure

1. Every unit gets an independent review before it is called finished; a second review after any fix round that
   changes decision logic (three of three such units had further findings).
2. Every unit is composed and its tests run on the candidate before its PR is called ready; the intake mission is
   the tool, with F18 fixed.
3. `gates_for_changes.py` and the baseline runner run before every push; the stale-anchor scan stays, labelled as a
   narrow guard.
4. This file records, for the operational slice and each later unit, which of its defects the earlier catches
   found and which still escaped to review or CI.
