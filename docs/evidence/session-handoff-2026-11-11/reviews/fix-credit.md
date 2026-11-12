# Fix round report: a rejected answer stops earning credit (2026-11-12)

Recorded by the commissioning session from the fix-round agent's hand-back, read at 11:17 UTC on 2026-11-12. These
are the agent's claims unless marked "checked by the session". Reproductions on `b01d319f`:
`scratchpad/cf-logs/before/`; the same probes on the final head: `scratchpad/cf-logs/after/`.

- Head `9097b276635742dfdcad98dfbae1dd78b3fddb5c` on `claude/correction-containment-credit-20261111`; two commits on
  `b01d319f` (`29c6c2cc`, `9097b276`).
- Files since `b01d319f`: `greg/corrections.py`, `greg/cognition/settlement.py`, `greg/routing.py`,
  `greg/autonomy.py`, `greg/precedents.py`, `greg/sop.py`, `greg/tribunal.py`, `greg/cli.py`, the unit's test file
  and gate, `docs/mechanisms/MC-0003-correction-containment-credit.md`, a comment and step name in the CI workflow.
  Not touched: `greg/missions.py`, `greg/body.py`, `greg/founder.py`, any protected artifact.

## Review findings (`review-credit.md`) and what was done

| Finding | On `b01d319f` | On the final head |
|---|---|---|
| F1 a standing mission's own later readings earn the rejected answer its credit back | credit `{}` then `(1,1)` again at the next cadence | stays `{}` |
| F2 the same answer through a new mission earns credit | `(1,1)` to `(2,2)` | `(1,1)`; the new mission is NEEDS_REVIEW |
| F3 a host stall or killed solver on a later mission is recorded REPLICATION_FAILED and costs the first answer its credit | credit `(2,2)` to `(1,1)`, an EVIDENCE_CORRECTION ask | no cause, credit `(2,2)` |
| F4 a rejection and a ratification in one inbox tick: the procedure is ratified | ratified | refused in the same tick |
| F5 rejections that map to no reading change nothing and say nothing | silent | every accepted rejection says what credit it changed, or that it changed none and why |
| F6 routing reliability, autonomy level and precedents still credit a rejected mission | reliability 0.8, RECOMMENDER, verified 3 | 0.5, SHADOW, verified 0, `founder_rejected` 3 |
| F7 an unsigned critique row is followed; a bare requalified row lifts a rejection | both happen | neither has any effect |
| F8 a dependent that appears after the correction was recorded is not contained | not contained | contained |
| F9 seven surviving mutants | — | each killed by a test; all seven in the gate |

The final test file on a copy of `b01d319f`: 21 failed, 26 passed.

## The founder's decision of 2026-11-12 on rejected-answer credit

| Phrase | How it is met |
|---|---|
| "withhold unsupported success credit" | F1 and F2 |
| "Scope ... to the relevant answer, evidence, task conditions, and version" | a rejection reaches the identical answer in a new mission and nothing else: four "does not reach" cases (another question, other inputs, another version, an unrelated mission) |
| "Permit explicit requalification when justified" | a later signed CRITIQUE with verdict accept lifts the withholding for that answer only; evidence alone, an unsigned accept row and a bare `evidence.requalified` row lift nothing; a rejection signed after the accept stands again |
| "avoid ... an unexplained permanent prohibition across unrelated missions" | the unrelated mission is untouched, the rejection can be lifted, and every withholding states its reason |

Identity of "the same answer": within a mission, the same check with the same answer digest. Across missions, for
GREG's own computations, the same signed sensor (instrument, params, predicate, without the check's label) answered
by the same method and version with the same result. A world reading (a file, a URL) is the same claim only within
its own mission. Answers that embed per-run values never match.

## The one reader

The unit's own `ANSWERED`, `no_method_ran` and `answered` are gone. `held_no_answer(output)` calls
`greg.missions.unanswered`. One interim half remains, marked for deletion: on this branch `unanswered` reads only
`abstention_state`, so a compilation whose `state` is an abstention class is put to the same reader as
`{"abstention_state": state}` until the compile-unread unit extends the reader.

## Agent's verification on `9097b276`

Unit file 47 passed; the unit's gate 81 of 81 (419 s); solver environment, 14 files: 329 passed, 1 skipped; base
environment, 45 files: 797 passed, 8 failed (missing solver packages; the same 8 fail on `b01d319f` there and pass
in the solver environment), 3 skipped. Gates: cathedral 160/160; compute closure 51/51; node revoke 35/35; standing
approval 21/21; typed blockers 28/28; cortex groups 33, 0 survived or stale; residual 86, 0 survived; seed gate exit
1 on the `constraint` mutant of a file the unit did not touch (also on `b01d319f`; the gate is in no workflow).
`governance.integrity --check` clean. A real stale anchor was caught mid-work by the repository's health test and
the line restored.

## Where credit, a score or a level can now be raised (agent's list)

A stall no longer withholds credit; a rejected failure stops counting against its method (the one place a rejection
raises a share); a signed acceptance returns withheld credit; unsigned critique rows no longer withhold; a standing
mission whose current hold delivers a different answer than the rejected one is no longer contained.

## For the founder (agent's list)

- A delegated device key may sign CRITIQUE, so a device can withhold credit, requalify it, and remove a failure
  from a method's count. Should requalification need the founder key?
- Any signed accept of a rejected answer lifts it, including a routine morning accept, with no confirmation step.
- A procedure ratified before the rejections stays ratified and runnable.
- No new ask is raised when a later mission re-delivers a rejected answer.
- Rejecting an achievement also withholds a verified failure of the same claim under an earlier unmet closure.

## Incident

An empty node list made pytest start the whole suite inside the reviewer's read-only worktree; it ran about 25
minutes before the agent killed it. The worktree is clean.
