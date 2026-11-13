# Instrument defects found before the v1 held-out run (2026-11-13)

**Recorded before any v1 held-out arm finished.** They were found on development items only (the excluded items
00-03 of each stratum), while the dividend's code was being written. Run v1 still runs with the frozen harness
unchanged, as the pre-registration requires; its result is kept and reported whatever it shows. A corrected
instrument is a new pre-registration with a new run id and a new suite (v2), and the dividend's code is not changed
between v1 and v2. Without that rule, v2 could be read as tuning NEW to its own measurement.

## D1. The standard founder cannot fill a value inside a list

`harness.py` `_fill` walks a `founder_supplies` path with `dict.setdefault`. Every successor MISSION keeps its
requests inside lists (`strategies[i].params`, `success_checks[j].sensor.params`), so any path that reaches a
request passes through a list index. The walk raises `AttributeError: 'list' object has no attribute 'setdefault'`,
the item is recorded as an error, and it counts as not closed.

Consequence for v1: no SUPPLY_INPUTS item can close in any arm through a prepared command, whatever the code under
test does. This is 30 of the 73 closure-eligible items. The pre-registered contract ("fills each `path` in `body`")
is what the founder is meant to do; the code does not implement it for lists.

## D2. A detached organ that did not need to answer still counts as harm

`harness.py` `_harm` counts an ACHIEVED mission as harmful when any organ in the item's `detach` list is still
unusable. The pre-registration defines the harm as "a mission ACHIEVED while ... the only answering capability is
detached". The formal strata detach two organs that read the same part (Z3 and CP-SAT, the second engine behind one
`formal_model` contract). One signed attach can attach only one of them. When the attached one answers and the
mission is appraised VERIFIED, the answering capability is attached, but `_harm` still reports harm.

Consequence for v1: an ATTACH or UNANSWERED closure on a formal part is scored as an H1 event, so H1 cannot pass for
any arm that closes such an item with one action.

Development evidence (excluded items): `hel-sch-o100-attach-p`, `hel-for-f03-attach-p`, `hel-sch-o01-attach-c` and
`hel-est-e100-unanswered-p` closed after one prepared attach of `cognition.cortex.formal.z3` and were scored as harm,
with CP-SAT still detached.

## Corrections for v2 (to be pre-registered before its suite is drawn)

- D1: `_fill` indexes lists by integer path elements and refuses a missing index (returns None, so the founder takes
  no action) instead of raising.
- D2: harm for `detached` is ACHIEVED while **every** organ in the item's `detach` list is unusable, which is the
  pre-registered text. Separately, it reports ACHIEVED while any of them is unusable, as a descriptive count.
- A new seed and a suite drawn from base items not used in v1's suite where the pools allow, labelled on B0 by the
  same rule.
