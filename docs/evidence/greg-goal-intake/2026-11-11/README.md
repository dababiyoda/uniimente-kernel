# Goal Gravity counts intake by independent source (S42-B) — evidence, 2026-11-11

Reality tier: a cloud container, per-test founder keys, no founder device, VEPMC 0. Every test drives a real Body in-process with a signed MISSION and a signed GOAL. Nothing here is an external effect or a founder acceptance.

Branch `claude/goal-intake-accumulation-20261111`, on the integration head `8d205324` (PR #196). Local commits only.

## What GREG can do now that it could not

On a founder-signed GOAL, weak reports about the goal's subject from independent sources add up inside the goal's signed window and wake it once. A claim that is copied, repeated by its own source, reworded by one word or denied does not add up. The wake pulls the goal's signed missions to look now. It issues nothing and asks nothing of its own.

## Reproduced first, on the integration head

`fail-before-8d205324.txt`: the two test files of this change run on an unchanged checkout of `8d205324`. 30 fail and 2 pass.

- 21 fail on behaviour. The two reproductions read:
  - three weak reports from three sources: `[False, False, False] == [False, True, False]` (never woke);
  - one claim from four sources: `[True, True, True, True] == [True, False, False, False]` (woke four times).
- 9 cannot run there: they name the new count (`IntakeAccumulation`, the `intake` view).
- 2 pass before and after. They pin what must not change: a quarantined item adds nothing, and a report recorded before the goal is judged alone.

## Counts: right wakes, false alerts, misses

`counts.txt`, from `tests/unit/test_greg_goal_intake_counts.py`. 16 scenarios, 17 wanted wakes, labelled before the first run. The scenarios are the author's, not a sample of real intake.

| Rule | Right wakes | False alerts | Missed |
|---|---|---|---|
| Per item (the integration head's rule) | 10 | 10 | 7 |
| Accumulated by independent source (this change) | 16 | 3 | 1 |

Three scenarios are worse than before, and one is not fixed. All four are in the counts:

- a disagreement by an opposite word ("is broken", "is fine") now adds up: 1 false alert, 0 before;
- passing mentions that report nothing now add up: 1 false alert, 0 before;
- the same sentence when the fault has come back inside the window no longer wakes the goal: 1 miss, 0 before;
- a claim retold in other words by another source still wakes the goal again: 1 false alert, as before.

Ablation (count every item instead of independent sources), on the four repetition scenarios: 10 false alerts, against 8 under the per-item rule and 0 under this change. Accumulation without the source rule is worse than no accumulation.

## The similarity threshold

`predeclared-threshold.txt` was written before any paraphrase test ran: exact normalisation first; word-set Jaccard at 0.8 only if a test showed normalisation alone missed a reworded copy. `stage1-normalisation-only.txt` is that test run on the first stage: the reworded copy and three denials woke the goal. The threshold was then added at 0.8 and not changed. The reworded test sits exactly at 0.8, and a mutant pins that. The file's time stamp is this session's word; the repository cannot prove it.

## Mutation gate

`mutants.txt`: `python scripts/ci/check_goal_intake_mutants.py`, 25 mutants, each caught by a named failing test. Wired into job 10 of `canonical-ci.yml`.

The first run of the gate had 26 mutants and caught 24. Both survivors were real findings and were fixed before the run recorded here:

- the test for a report recorded before its goal passed for another reason (a new goal's first turn reads its mission's checks); the test now uses a goal those readings cannot wake;
- one part of the key under which a count is kept between reports changed nothing a caller can see; it was removed, with its mutant.

## Commands

```
python -m pytest -q -p no:cacheprovider tests/unit/test_greg_goal_intake_accumulation.py tests/unit/test_greg_goal_intake_counts.py
python scripts/ci/check_goal_intake_mutants.py
python -m acceptance check
python -m acceptance directive --against 8d20532464b1533b28d71d8331ca3412a90dbb11
```

## Not run, not claimed

- No founder device, no real intake feed, no real community. The wake path was exercised with hand-written reports.
- The whole test suite was not run (shared container). The goal gravity, data plane, community, directive and acceptance files were.
- `tests/unit/test_goal_gravity_evidence_kinds.py` skips here: it needs networkx, which this container lacks.
- The egregore intersection detector (`opportunity_factors`: capabilities, constraints, timing and resources as beliefs) is unchanged and still has no body-mode test. This change combines intake reports only.
- CI was not run: nothing was pushed.
