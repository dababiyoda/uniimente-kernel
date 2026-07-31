# 5K-T2b — corrected closure-truth audit

Evidence only. No runtime file, no active test, no marker changed.
Source: `verification/phase3g/closure_truth_audit.py` → `CLOSURE_TRUTH_AUDIT_V2.json`.

## Correction 2 is CONFIRMED, and was a defect in my harness

Verified in source at `substrate/v5.py:2703`, inside `deliver_terminal`:

```python
# The parent OBSERVES the child's closure, so the child's edge carries
# its one terminal outcome even when the emitting side is a harness.
self._record_terminal(Terminal(kind, key, edge_id, credited, 0.0,
                               node["child_targets"].get(edge_id, ""),  # from = CHILD
                               self.unit_id, "", proposal_id))          # to   = PARENT
```

`self` is the parent; the author is the child. My first harness classified from
`self.unit_id`, so a child-authored outcome was routed to the control channel.

The corrected classifier compares the terminal's endpoints against the
sender-created probe. Measured, every mode:

```
AUDIT_CLASSIFICATIONS_BY_AUTHOR_DIRECTION      6 / 8 / 6 / 8 / 7 / 9
AUDIT_CLASSIFICATIONS_BY_RECORDER_IDENTITY     0   (all cells)
AUDIT_UNCLASSIFIABLE_EDGE_MESSAGES             0   (all cells)
AUDIT_OBSERVED_CHILD_OUTCOMES                  1-2 (nonzero denominator)
AUDIT_OBSERVED_CHILD_OUTCOMES_AS_CONTROL       0   (all cells)
```

## Correction 1's stated evidence is NOT reproducible

The correction asserts the density-1.0 cycle edge records
`accepted_control = SearchCycleClosed`, `accepted_outcome = SearchCycleClosed`,
`legacy_outcome_count = 2`. It does not — in any of the four modes:

```
root:reconcile.13:0:1/r0/c0/r0/c0/r0/c0
  accepted_control  : null
  accepted_outcome  : SearchCycleClosed
  legacy_len        : 1
  control_conflicts : 0
  outcome_conflicts : 0
```

The single MODE-10 legacy violation in the V1 audit was produced by **my broken
classifier**, not by the role rule and not on the cycle edge. With the classifier
corrected, `legacy_helper_violations = 0` in every cell. So `test_lineage`'s
regression is **not** explained by a stale length assertion on the cycle edge.

## Amplification is not implicated

The V1 harness divided TOTAL messages; the test divides the repair DELTA:
`amp = (o.messages - before) / len(o.units)`.

```
                 delta   amp     ceiling
MODE_00 d=0.8      16    0.94      12
MODE_11 d=0.8      18    1.06      12
MODE_00 d=1.0      18    1.06      12
MODE_11 d=1.0      21    1.24      12
```

`amp <= 12` passes in every mode with an order of magnitude to spare. The
ceiling needs no revision, and the honest changes cost +2/+3 messages.

## MODE_11 acceptance

```
MODE_11_LIFECYCLE_CONFLICTS            0   (all cells)
MODE_11 edges with accepted outcome    5/5, 5/5, 6/6
DUPLICATE_SUBTREES_OPENED              0
duplicate probes                       0
LEGACY_REPAIR_NEED_MESSAGES            0
UNAUTHORIZED_EXTERNAL_EFFECTS          0
INHERITED_AUTHORITY_EVENTS             0
```

Under both honest changes together, every transport edge closes on child-owned
evidence with no conflict in either channel.

## THE METRIC IS NOT MET, and the reason is my harness

`_exact_assertions` reproduces the runtime faithfully but does **not** reproduce
the five tests' fixtures. Two proofs that it does not:

1. `A.coalesced_positive` fails at density 1.0 in **MODE 00** — current head —
   where `test_A` passes. A reproduction that fails at head is not reproducing
   the test.
2. `LIN.cycle_closed_positive` fails at densities 0.8/0.9 in all modes;
   `test_lineage` uses density 1.0 only, where every LIN assertion passes in all
   four modes.

So no mode reproduces any of the five observed regressions.

```
REGRESSED_CASES                     5
REGRESSED_CASES_CLASSIFIED          0
UNEXPLAINED_REGRESSIONS             5
```

The V1 classification (`STALE_PROJECTION_ASSERTIONS = 4`) is **withdrawn**: it
rested on the MODE-10 violation my own classifier manufactured. The corrected
classification of the reviewer (`= 5`) is **not confirmed either**, because its
stated cycle-edge evidence does not exist in any mode.

## Next

The harness must execute the five tests' **own** fixtures — same seeds, same
density, same helper — rather than approximating them, before any assertion can
be classified. No runtime edit is authorized; none was made. 5K-T3, 5G and 5L
all remain blocked.

R8 prohibited. Gates F and G UNMEASURED.
