# 5K-T2 — closure-truth audit: assertion-level causal classification

Evidence only. No runtime file, no active test, no marker was changed to produce
this. Every number is from `verification/phase3g/closure_truth_audit.py`,
recorded in `CLOSURE_TRUTH_AUDIT.json`.

Command:

```
python verification/phase3g/closure_truth_audit.py
```

Head at time of audit: `23b0607`. Suite: `875 passed · 1 skipped · 20 xfailed ·
0 failed`.

---

## The four-mode matrix

```
                         msgs  legacy_viol  lineage  cycles  outcomes/edges  dupes
density=0.8  MODE_00      973       0          2       0         3/5           0
             MODE_10      973       1          2       0         3/5           0
             MODE_01      975       0          2       0         5/5           0
             MODE_11      975       0          2       0         5/5           0
density=0.9  MODE_00     1083       0          2       0         3/5           0
             MODE_10     1083       1          2       0         3/5           0
             MODE_01     1085       0          2       0         5/5           0
             MODE_11     1085       0          2       0         5/5           0
density=1.0  MODE_00     1159       0          3       1         3/6           0
             MODE_10     1159       1          3       1         3/6           0
             MODE_01     1162       0          3       1         6/6           0
             MODE_11     1162       0          3       1         6/6           0
```

`MODE_00` head · `MODE_10` role classification only · `MODE_01` outcome-only
projection only · `MODE_11` both.

---

## Four findings, each decided by a column rather than by argument

### 1. Structural convergence is invariant across all four modes

`DUPLICATE_SUBTREES_OPENED = 0` in every cell. Canonical nodes, expansions,
coalesced arrivals and probe uniqueness do not move. **Neither candidate change
alters what the substrate computes.**

This settles the question that blocked both 5G and 5L: the regressions are *not*
in convergence, so `test_A`'s convergence core is untouched and remains a valid
active invariant.

### 2. Lineage accumulation and cycle closure are also invariant

`lineage` is 2, 2, 3 and `cycles` is 0, 0, 1 — identical in all four modes at
every density. The cycle at density 1.0 still occurs and still closes exactly
once under both honest changes.

**This falsifies my own earlier hypothesis.** I reported that the honest
changes might have pruned the branch before the cycle. They do not. Whatever
made `test_lineage` regress, it is not loss of lineage depth and not loss of
cycle traversal.

### 3. Role classification adds ZERO messages. The projection change adds 2–3.

```
MODE_00 -> MODE_10   +0   +0   +0
MODE_00 -> MODE_01   +2   +2   +3
MODE_11 == MODE_01   975 1085 1162
```

So the amplification question belongs entirely to the projection change, and its
size is two or three messages on a base of ~1000 — with every duplicate-work
detector at zero (`DUPLICATE_SUBTREES_OPENED = 0`, no duplicate probes,
`LEGACY_REPAIR_NEED_MESSAGES = 0`).

**`amp <= 12` is not what fails.** A change of +2/1159 cannot move a ratio
bounded at 12 across a threshold. The ceiling does not need revisiting, and this
audit does not propose revisiting it.

### 4. The stale helper fires in exactly one cell — and it is MODE 10

```
legacy_helper_violations   MODE_00: 0   MODE_10: 1   MODE_01: 0   MODE_11: 0
```

`_per_key_edge_uniqueness` requires every probed edge to hold exactly one item
in the legacy `outcomes` array. In MODE 10 the receiver-emitted
`SearchNeedClosed` correctly moves to the outcome channel while the control path
*still* writes the projection, so that edge accumulates two entries and the
helper rejects it.

The helper is measuring **projection shape**, not closure. In MODE 11 — where the
control path stops writing the projection — it reads zero again.

---

## Assertion-level classification

| test | assertion | classification | evidence |
|---|---|---|---|
| `test_A` | convergence: unique nodes, expansions == nodes, no duplicate subtree, coalesced > 0, probe uniqueness | **VALID_INVARIANT** — keep active | identical in all four modes |
| `test_A` | `_per_key_edge_uniqueness`: `len(terminals[edge]["outcomes"]) == 1` | **STALE_PROJECTION_ASSERTION** | fires only in MODE 10; reads projection shape, not accepted outcomes |
| `test_J` | `_per_key_edge_uniqueness` (same helper) | **STALE_PROJECTION_ASSERTION** | same cell, same cause |
| `test_J` | `amp <= 12` | **NOT IMPLICATED** — keep unchanged | message delta is +0 (role) / +2–3 (projection) on ~1000 |
| `test_lineage` | `max lineage depth >= 2` | **VALID_INVARIANT** — keep active | 2/2/3 in all modes |
| `test_lineage` | end-to-end cycle traversal and closure | **NOT IMPLICATED by these changes** | `cycles` identical in all modes |

**`UNEXPLAINED_REGRESSIONS = 0` is NOT yet claimable.** Three of the five
regressed cases (`test_J` at each density) are explained by the stale helper.
`test_A` is explained by the same helper. `test_lineage` is **not** explained by
this matrix — its lineage and cycle quantities are invariant, so its failure must
come from an assertion this audit did not isolate.

```
STALE_PROJECTION_ASSERTIONS      4   (test_A, test_J x3)
INCIDENTAL_COVERAGE_ASSERTIONS   0   (none demonstrated)
VALID_RUNTIME_INVARIANT_FAILURES 0
UNEXPLAINED                      1   (test_lineage)
                                ---
                                 5
```

The Single Bottleneck Metric is therefore **not met**: `UNEXPLAINED_REGRESSIONS
= 1`, not 0. No runtime edit is authorized, and none was made.

---

## The one thing this audit changed about the plan

The honest-evidence direction is better supported than before, not worse:

- **closure improves markedly.** Edges carrying a child-owned accepted outcome go
  from `3/5, 3/5, 3/6` to `5/5, 5/5, 6/6`. Under MODE 11 *every* transport edge
  closes on real child evidence.
- it costs 2–3 messages per run,
- it changes no computation, no lineage, no cycle behaviour, and creates no
  duplicate work.

And the two changes are **not** independently safe: MODE 10 alone is what breaks
the helper. MODE 11 does not. So 5L must not land before 5G — the ordering I
attempted was backwards.

---

## Stop conditions checked

None triggered. Structural convergence unchanged; lineage ≥ 2 throughout; no
duplicate computation; scheduler ordering identical (message counts move only by
the deltas above); no global topology required; no 2D rule touched.

`LEGACY_REPAIR_NEED_MESSAGES = 0`, `UNAUTHORIZED_EXTERNAL_EFFECTS = 0`,
`INHERITED_AUTHORITY_EVENTS = 0`, `UNSUPPORTED_CHILD_CANCELLATION_CREDIT = 0` in
every cell.

---

## Next, in order, and not before

1. **Isolate `test_lineage`'s failing assertion.** It is the one unexplained
   case, and the metric cannot be met until it is classified.
2. 5K-T3, tests only: migrate the stale helper — split
   `_per_key_edge_uniqueness` into probe-uniqueness and canonical-lifecycle
   integrity, so a convergence test asserts convergence and closure is asserted
   where closure lives.
3. 5G runtime, then 5L runtime — **in that order**, which this audit reverses
   from the earlier plan.
4. Markers.

R8 remains prohibited. Gates F and G remain UNMEASURED.
