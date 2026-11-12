# Independent review: brief.intake (885b7b7a, base 0b0bb6d3), 2026-11-12

Reviewer: a separate agent process on the same model (a second process, not an independent operator). Probes:
`scratchpad/ri-probes/probes/`, run from `scratchpad/ri-probes/tree` (git archive 885b7b7a) with
`TMPDIR=scratchpad/ri-probes/tmp`. Reproduced by the commissioning session at 15:36 UTC: F4 (p5b_planted_before:
tick 1 ACHIEVED, actions [], appraisal VERIFIED) and F5 (p7_rename: mover "ready to take", only tests/test_extra.py run,
skipped []).

| id | severity | defect | where |
|---|---|---|---|
| F1 | high | supervised-floor environment failure reported as the head's own and held | intake.py:517-519 (fixed in b032f38a) |
| F2 | high | 291/273 conflict split 7 + 6 by the same cause | intake_rehearsal.py:260-267 (partly addressed in b032f38a: reported not checked; still not measured as conflict) |
| F3 | medium | synchronous, no overall time budget (tick held 1 h 43 min) | intake.py:60,172 |
| F4 | high | a hand-written md + twin pair closes the mission ACHIEVED/VERIFIED with no action | intake_status intake.py:747-766; appraisal REOBSERVABLE |
| F5 | high | a renamed-and-edited test file is neither run nor listed; unit ready | --diff-filter=AM, intake_rehearsal.py:200; intake.py:246 |
| F6 | medium | git reads outside read roots (upward discovery; .git file; alternates) | intake.py:331, 190-219 |
| F7 | medium | a head containing a held head is "take after <held>" | intake.py:556-564 |
| F8 | medium | STOP during the last run still delivers; interrupted run labelled "envelope unavailable"/"refused before it ran" | intake.py:269, 292-295; workers.py:924-925 |
| F9 | medium | textual-conflict verdict depends on unit order, unstated | intake.py:651-654, 514-516 |
| F10 | medium | stale failing check + any passing check -> ready; "in_progress" string -> no result; skipped/neutral only -> ready; DIFFERENT result not listed; cancelled -> failed | intake.py:466-478, 529-531, 707-712 |
| F11 | low | prefix SHA / missing head_sha -> stale; "success"/"1 passed" -> DIFFERENT result | intake.py:438-450 |
| F12 | medium | mutation gate has no baseline (fixed for the shared runner in #307) | mutation_harness.py |
| F13 | medium | survivors k (unmeasured FAILED not unchecked), o (stale checks don't hold), q (twin unlinked not refused), n (scratch of earlier attempt) | intake.py:539-540, 531, 407, 334 |
| F14 | low | all-deselected file reads errored, not not run | intake_rehearsal.py:57; intake.py:321-323 |
| F15 | low | file names a composed tree that no longer exists | intake.py:703 |
| F16 | low | malformed --intake JSON prints a traceback | cli.py:846 |
| F17 | low (reading) | keep_both writes side files to process TMPDIR | intake_rehearsal.py:123 |

Sound: repository-configured programs (none run, 15 kinds); SHA validation; forged/flooded pytest output; CLI move;
allowlist entries; tests pass (integration 7/7, unit 41/41 under short TMPDIR).
Not checked: bubblewrap; SIGKILL mid-capability; double signing; appraiser binding of params; .pth/sitecustomize.
Founder questions: ACHIEVED/VERIFIED with no check run; identical selection cannot be re-signed; no claims never
blocks ready; union/behind-base are notes only; internal_write capability starts heads' code.
