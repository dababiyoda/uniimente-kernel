# RA-2 — Design A implemented and falsified

Evidence only. `substrate/v5.py` is unchanged; the candidate was built, measured
and reverted. Third mechanism falsified by running it in this workstream, and
the most informative of the three.

## The candidate

The authorization's preferred hypothesis, and the smallest apparent remedy:

```python
def _emit_need(slot):
    nid = f"{unit}:{slot}:{activation}"
    open_needs[slot] = nid
    # self._search[nid] = new_search_ledger()      <- REMOVED
    _open_repair_root(slot, nid)
```

with the misordered `DUAL_REPAIR_SEARCHES` detector moved after
`_open_repair_root` so it inspects the postcondition — one live generation
holding both a canonical root and a legacy ledger — instead of checking for a
canonical root that its own call had not yet created.

The reasoning was sound on its face: with no ledger, `step()`'s legacy loop reads
`self._search.get(nid)` as `None` and calls neither `widen` nor
`_prove_exhaustion`, so the authority is removed rather than guarded and no
owner flag or second registry is needed.

## Result

```
924 passed · 1 skipped · 24 xfailed · 0 failed     before
904 passed · 0 skipped · 24 xfailed · 21 failed    after

XPASS(strict) among the 21:   0
```

**Zero XPASS.** Every one of the twenty-one is a real regression, not an earned
activation. The candidate is reverted.

## What broke, and why it matters

Four failures are outside the need-closure family and are the substantive ones:

```
test_ledger_invariant_holds_across_a_full_repair
test_bounded_exhaustion_counter_fires_with_attributable_escalation
test_legacy_projection_is_inert_across_a_SECOND_real_repair
test_widening_requires_the_whole_round_to_have_completed
```

The last is the long-standing **skip** — it stopped skipping and started
failing, which is itself a measurement: the skip's guard ("no branches were
opened") was being satisfied *through the legacy ledger*.

Seventeen are need-closure specifications, and they fail for a reason worth
stating precisely: **removing the legacy authority removed the cause of the
abandonment**, so `_abandoned()` found no abandoned root and its non-vacuity
guard fired. The mechanism and its subject are coupled — one of the three
retirements in the fixture existed *because* `_prove_exhaustion` retired it.

## The corrected finding

The legacy `_search` ledger is not a dormant shadow that merely *also* retires
generations. It is **load-bearing for the canonical repair path itself**:
widening, credit accounting, bounded-exhaustion escalation and the second-repair
projection all read it. NC-4B measured that corrupting it changes canonical
outcomes; this measures the stronger fact that *removing* it changes them too,
in four independent places that have nothing to do with retirement.

So the framing in NC-4A/4B needs one correction. The defect is not "a disabled
subsystem retains an authority it should not have". It is:

> The canonical repair path is not actually independent of the legacy repair
> path. They share state, and the legacy ledger is a live participant in
> canonical repair, not a residue of a completed migration.

That is a larger and more honest problem than the one Design A was scoped to
fix, and it is why the smallest-looking remedy is not small.

## What this eliminates from the design space

- **Design A (remove the ledger)** — REJECTED by measurement. Not an authority
  removal; a behavioural change to repair, credit and widening.
- **Design E (remove the legacy repair path entirely)** — strictly larger than
  A, so it inherits A's breakage and is rejected on the same evidence.
- **Design H (supervisor ownership)** — already rejected on authority grounds.

What survives, and must now be compared on evidence rather than preference:

- **B** — an explicit owner on the need generation, with legacy functions
  refusing a canonical-owned one. Keeps the ledger's *bookkeeping* role while
  removing its *decision* role, which is the distinction the measurement forces.
- **C** — owner field inside `_search`, same separation, different placement.
- **D** — one central retirement primitive, with the ledger retained.
- **F** — legacy path as a test-only adapter, production path narrowed.

B and D together are now the leading hypothesis: separate the ledger's
bookkeeping from its authority, and centralise retirement so that only one
primitive may pop `open_needs`. Neither is adopted here.

## The detector

Its reordering is *correct* and independent of Design A's failure — it was
checking for a canonical root on the line before the call that creates it, so
its zero could never have been evidence. That correction should land on its own,
with the negative control the authorization specifies: insert a legacy ledger
after canonical root creation and require the detector to fire. It is not
committed here because it arrived inside a falsified candidate, and a correct
change smuggled in with a reverted one is not reviewable.

## Not established

No runtime change. `CANONICAL_ROOTS_RETIRED_BY_LEGACY_AUTHORITY` is still 1 and
`canonical_repair_is_independent_of_legacy_ledger` is still FALSE. Gate F
**UNMEASURED**, Gate G **UNMEASURED**, R8 **PROHIBITED**, no external effect. No
development freeze is claimed.
