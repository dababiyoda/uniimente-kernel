# 5K-T1c/T1d/T2c — exact-execution audit

Evidence only. No runtime file, no active test and no marker was changed on this
branch to produce it. Candidate runtime diffs existed only inside disposable git
worktrees at `b6c9e0c` and are preserved here as `.patch` artifacts.

Every verdict below is **pytest's own verdict on the repository's own test
file**, read back out of the JUnit XML pytest itself wrote. Nothing is mirrored,
reconstructed or approximated. That distinction is the whole point of this
round: the previous two audits were mirrored harnesses, and both produced
classifications that had to be withdrawn.

```
python verification/phase3g/audit-patches/make_candidate.py <label> <worktree> <factor>...
python verification/phase3g/audit-patches/run_candidate.py  <label> <worktree>
python verification/phase3g/audit-patches/summarize.py
```

Head: `b6c9e0c`.

---

## Gate 1 — baseline parity. MET.

```
875 passed, 1 skipped, 20 xfailed in 14.64s        (0 failed)
BASELINE_TARGET_PASSES = 5 / 5   in solo, batched, module AND full-suite shape
```

Required signature reproduced exactly, so candidate results are admissible.

## Gate 2 — instrumentation parity. MET.

The audit counter added to every candidate changes no outcome: `instr` alone
reproduces `875 / 1 / 20 / 0` and 5/5 targets. A counter that moved a result
would have contaminated every cell below.

*(The first attempt failed this gate, correctly. `LEGACY_PROJECTION_DECISION_READS`
already exists in the runtime and already tracks the `_search` projection, with
two active specs requiring it to be 0. The audit counter was renamed
`LEGACY_TERMINAL_PROJECTION_DECISION_READS`. The collision is itself a finding —
see §6.)*

---

## 1. The premise of 5K does not survive contact with pytest

The five cases named across the last several sessions as "the five regressions"
**pass in every candidate, in every run shape.**

| case | baseline | 5g-reader | 5g-writer | 5g | 5l | 5gl |
|---|---|---|---|---|---|---|
| `test_A_diamond_convergence_opens_one_canonical_node` | pass | pass | pass | pass | pass | pass |
| `test_J_amplification_scales_with_units_not_paths[0.7]` | pass | pass | pass | pass | pass | pass |
| `test_J_amplification_scales_with_units_not_paths[0.8]` | pass | pass | pass | pass | pass | pass |
| `test_J_amplification_scales_with_units_not_paths[0.9]` | pass | pass | pass | pass | pass | pass |
| `test_lineage_accumulates_and_a_real_cycle_closes_positively` | pass | pass | pass | pass | pass | pass |

`REGRESSED_CASES_FROM_THE_PRIOR_SET = 0`.

The stale helper `_per_key_edge_uniqueness` never fires, and the reason is
readable in the source: `_record_outcome` **assigns**
`search_edge_terminals[edge] = {... "outcomes": [t]}` rather than appending, so
an accepted outcome overwrites whatever the control channel wrote. The array can
never hold two entries. The MODE-10 "legacy helper violation" reported in
`CLOSURE_TRUTH_AUDIT.md` was an artifact of a mirrored fixture that appended
where the runtime assigns.

**Everything the last three sessions built on that regression set was built on a
measurement error.** This is the third mirrored-harness artifact in a row, and
the pattern is now the finding: a harness that re-implements an assertion tests
the harness.

---

## 2. The real regression set is two cases, and one mechanism causes them

```
                 suite totals            XPASS(strict)   assertion    regressions
                                          pre-registered  failures    vs baseline
baseline    875 pass  1 skip 20 xfail  0        0            0            0
instr       875 pass  1 skip 20 xfail  0        0            0            0
5g-reader   875 pass  1 skip 16 xfail  4        4            0            0
5g-writer   873 pass  1 skip 16 xfail  6        4            2            2
5g          873 pass  1 skip 16 xfail  6        4            2            2
5l          875 pass  1 skip 15 xfail  5        5            0            0
5gl         873 pass  1 skip 11 xfail 11        9            2            2
```

Three mechanisms were separated so each could be charged individually:

- **MECHANISM 1 — writer cleanup** (`writer`): `_record_control` stops writing
  the legacy projection.
- **MECHANISM 2 — decision-authority migration** (`reader`): `deliver_search`,
  `_reconcile_closed_children` and `replay_search_edge` stop treating membership
  in `search_edge_terminals` as proof an edge was answered, and read
  `search_edge_lifecycle[edge]["accepted_outcome"]`.
- **MECHANISM 3 — author-direction classification** (`direction`):
  `_record_terminal` classifies by the edge's probe roles against the message's
  **author** (`from_unit`), not by kind membership.

The two regressed cases appear in `5g-writer`, `5g` and `5gl`; they are absent
from `5g-reader` and `5l`. **Mechanism 1 alone is the cause. Mechanisms 2 and 3
each produce zero assertion failures.**

That ordering is the reverse of what the previous audit concluded. It reported
"5L must not land before 5G". Measured against real execution, the reader
migration and the direction change are each independently clean, and the writer
cleanup is the only one that owes a test correction.

---

## 3. Both regressions are stale readers, proved by paired controls

Both read the legacy projection looking for `SearchCommitted` —

```python
# test_an_exact_proposal_replay_settles_only_once:1021
commits = [x for x in o.search_edge_terminals.get(kids[0], {}).get(
    "outcomes", []) if _kind(x) == "SearchCommitted"]

# test_two_competing_proposals_race_through_real_child_edges:1121
win_outs  = o.search_edge_terminals.get(win_edge,  {}).get("outcomes", [])
lose_outs = o.search_edge_terminals.get(lose_edge, {}).get("outcomes", [])
```

`PARENT_CONTROL_KINDS = ("SearchCommitted", "SearchCancelled", "SearchNeedClosed")`.
`SearchCommitted` is in that set and in no other. Both assertions are asking
**"did the parent command this edge"** — a control fact — of a store that, after
mechanism 1, holds accepted outcomes only. Neither is asserting closure.

The classification is not an argument. It is two runs:

| control | runtime | predicate | read location | result |
|---|---|---|---|---|
| positive | **5G** | unchanged | `search_edge_lifecycle[edge]["accepted_control"]` | **2 passed** |
| negative | **baseline** | unchanged | `search_edge_lifecycle[edge]["accepted_control"]` | **2 passed** |

The positive control shows the fact still exists under 5G. The negative control
shows the relocation is runtime-neutral — it asserts the same thing in both
worlds, which is exactly what separates *"this reader is stale"* from *"this
test was weakened until it passed."* Both relocated assertions demand a positive
(`len(commits) == 1`; `win_outs == ["SearchCommitted"]`), so neither can be
satisfied by finding nothing.

```
REGRESSIONS_CLASSIFIED   2
UNEXPLAINED_REGRESSIONS  0
```

The relocation patch is preserved as `audit-patches/probe-read-relocation.patch`.
It is a **measurement instrument, not a proposed edit** — no test file on this
branch was touched.

---

## 4. Nine pre-registered specifications go green

pytest reports a strict-xfail that starts passing as a *failure*. That is the
mechanism working: these were registered as predictions before any runtime
change existed, and Git ancestry proves it.

**Mechanism 2 (reader) alone turns 4 green:**

- `test_a_closed_non_root_node_owes_nothing`
- `test_every_commanded_edge_ends_with_an_accepted_child_outcome`
- `test_no_closed_node_finishes_with_children_outstanding`
- `test_accepted_settlement_reconciles_every_outstanding_child_allocation`

**Mechanism 3 (direction) alone turns 5 green:**

- `test_a_receiver_emitted_need_closed_is_an_outcome`
- `test_a_stranger_owning_neither_end_reaches_neither_channel`
- `test_classification_is_by_role_and_never_by_kind_membership`
- `test_exact_replay_is_inert_in_whichever_channel_the_role_selects[receiver-accepted_outcome]`
- `test_the_two_forms_do_not_share_a_channel_on_one_edge`

**Together: 9.** The two sets are disjoint and neither interferes with the
other's specs.

`test_every_commanded_edge_ends_with_an_accepted_child_outcome` passing under
mechanism 2 is the substantive one: it is the proof-closed-terminality property
this whole line of work exists to establish.

---

## 5. Decision authority, measured rather than asserted

```
LEGACY_TERMINAL_PROJECTION_DECISION_READS

baseline / instr     4782      <- positive control: the runtime asks the legacy
                                  projection a DECISION question 4782 times per suite
5g-writer            5025      <- MORE. Emptying the store of commands makes the
                                  runtime consult it more often, not less
5g-reader               0
5g                      0
5l                   4782      <- direction classification touches no reader
5gl                     0
```

This settles the question raised against the previous round. `search_edge_terminals`
**did** hold runtime decision authority at head, at three sites, 4782 times per
suite — and mechanism 1 alone does not remove it. Only the reader migration does.

The counter is measured by a plugin that wraps `Counters.incr` to accumulate a
total no `reset()` clears. The wrapper is behaviourally inert: every tapped run
reproduces its untapped totals exactly.

---

## 6. A second defect surfaced, unasked

```
TERMINALS_WITH_UNRECONCILED_CHILDREN

baseline / 5l          810
5g-reader / 5g-writer / 5g / 5gl    0
```

At head, `_reconcile_closed_children` reads the legacy projection, finds the
parent's **own command** sitting in it, correctly refuses to close a child
allocation against evidence the child never produced, and leaves the liability
open — 810 times per suite run. The guard is working exactly as written. What it
is guarding against is a store that keeps commands and answers in one array.
Under any candidate that separates them, it never trips.

And the counter-name collision that failed Gate 2 is the same finding stated
differently: the repository already asserts, in two active specs, that the
`_search` projection holds no decision authority. `search_edge_terminals` is a
second legacy projection that **does** hold decision authority and had no
counter at all.

---

## 7. What did not move

```
DUPLICATE_SUBTREES_OPENED              0   in every candidate
UNAUTHENTICATED_TERMINAL_EMISSIONS     9   in every candidate
UNKNOWN_EDGE_TERMINAL_EMISSIONS       76   in every candidate
DUPLICATE_TERMINAL_RESOLUTIONS         1   in every candidate
```

Structural convergence is untouched. 2D is unweakened — identical refusal counts
in every cell. No stop condition triggered.

---

## 7b. A stale integrity manifest, found by running it

`sha256sum -c CHECKSUMS.txt` had apparently never been run. It fails at `b6c9e0c`,
and it failed before this commit:

```
stored at 1d7349c   ee53ca29543f...  DEVELOPMENT_RESULTS.json
actual   at b6c9e0c bcb32473fcac...  DEVELOPMENT_RESULTS.json
```

The **manifest** is stale, not the artifact. `CHECKSUMS.txt` was last written at
`1d7349c`, where the stored hash was correct. `DEVELOPMENT_RESULTS.json` was then
rewritten seven times without the manifest following:

```
1d7349c  ee53ca2954  <- manifest written here, matched
b529d58  f4eef65eb3
e254dc0  afa9ae9f93
1feda54  3ed68e3ef3
01d6666  4cef23f387
f6370c2  25ae17bfa9
aed2243  5452b44 20d
b8a16c6  bcb32473fc  <- current content ("R6: clean reproducible development run")
```

Nothing was lost: every intermediate version is preserved in Git and the lineage
above is recoverable from it. The manifest has been rebuilt against actual bytes
and now verifies clean for all 20 entries. The superseded hash is recorded here
rather than silently overwritten, because a checksum that stopped being
maintained is itself evidence about how this branch was verified.

An integrity manifest nobody executes is a claim, not a check.

## 8. Not established

- That these exact 5G/5L edits are the ones that should land. This audit
  **measured** them; it did not authorize them, and no runtime change was
  committed to the branch.
- Anything about Gates F and G, which remain **UNMEASURED**.
- R8, which remains **prohibited**.

## 9. Next, in order

1. **5K-T3, tests only.** Relocate the two stale reads to the canonical control
   channel — the relocation is already proved runtime-neutral at baseline, so it
   lands and stays green *before* any runtime change.
2. **5L runtime**, then **5G runtime** — in that order, which this audit reverses
   again from the previous one, because mechanism 3 is clean standalone and
   mechanism 1 is the only one carrying a test debt.
3. **Markers**, in their own commit, once the specs are genuinely passing.

`_exact_assertions` in `closure_truth_audit.py` is retired as a classification
authority and marked as such. It is preserved, not deleted: it is the record of
how a mirrored harness produces confident wrong answers, and it is the reason
this round runs the real node IDs instead.
