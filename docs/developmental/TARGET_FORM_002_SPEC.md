# TARGET_FORM_002 — Specification (NOT IMPLEMENTED)

Preserved from PR #44 (`claude/disruptive-design-configs-hi1ab0`, commit
`1b4ffbc5df11d0e9246a3ee607ef67610e2e9326`). **Specification only.** No code from
this document is implemented in Package 2. Execution is not authorized.

The duplicate `morphogenesis/` runtime from PR #44 was NOT carried over. Only
findings and method survive; they extend the existing `developmental/`
(MICA/CDPE) system rather than creating a second one.

## The finding this preserves

TARGET_FORM_001 runs on a 12×10 von Neumann lattice — degree-homogeneous,
coefficient of variation 0.00. PR #44 measured functional recovery across a
degree-heterogeneity axis and found:

| topology | degree cv | recovery @10% injury | @20% | @30% |
|---|---|---|---|---|
| lattice | 0.00 | 100% | 100% | 0% |
| small-world | 0.24 | 100% | 0% | 0% |
| scale-free | 1.03 | **0%** | 0% | 0% |

Local rule vs frozen roles vs random reassignment, pooled: lattice 66.7/41.7/0.0,
small-world 33.3/4.2/0.0, scale-free 0.0/0.0/0.0 (median recovery 0.559 / 0.272
/ 0.206).

**Recovery degrades monotonically with degree heterogeneity and reaches zero on
hub-heavy topology.** Differentiation does real work — roughly doubling median
recovery over frozen roles on scale-free — but does not clear a 90% bar.

TARGET_FORM_001's pass and PR #44's failure are **the same finding measured at
two points on one axis**, not a contradiction.

## Interpretation guard

The 20% and 30% scale-free figures say nothing about the local rule: hub-targeted
removal shatters a Barabási–Albert graph to a largest component of 7% of
survivors, and no mechanism routes work through a disconnected substrate. The
interpretable datapoint is 10% injury at 73% connectivity — still 0%, median 0.85.

## What TARGET_FORM_002 must do when authorized

Extend the existing `developmental/` harness along the topology axis, keeping its
methodology intact — frozen contracts, no exact restoration, ≤4× planning work
versus the adaptive centralized baseline, and the centralized comparator retained
permanently.

Generic function only. No IVIO, hospital, trip, facility, billing, or healthcare
framing: `input → verify → transform → deliver`.

Topologies: evenly connected, mildly uneven, strongly hub-dependent, partially
disconnected, redundant, locally rewired.

**Predicted outcome, recorded in advance so it cannot be rationalized later:
failure at high degree heterogeneity.** The experiment's value is locating where
on the axis it breaks.

## Two methodological findings worth more than the result

**A non-discriminating testbed passed everything.** PR #44's first Stage 2 build
returned 100% for the local rule *and* frozen roles *and* random reassignment.
Unbounded random-walk hops made a connected graph effectively fully connected, so
any role placement worked. Fixed with per-cell capacity, a hop budget, and load
in the binding regime. **Without the frozen-roles control this would have shipped
as a success.** Any future experiment must include a control that can expose a
vacuous result.

**Instantaneous sensing thrashed.** ~0.32 role switches per cell per tick, census
collapsing to 1 of 196 in one role. Fixed by integrating demand over time rather
than chasing instantaneous queue length — biologically motivated, since real cells
integrate morphogen exposure. Switching fell ~8×.

## Also preserved, not implemented

The three-clause developmental invariant (no cell may access the complete target
structure, receive a centrally assigned final fate, or use privileged omniscient
state) and its AST checker; the four null baselines (frozen, random, shuffled
neighbours, no diffusion); and the anti-inflation tests that assert the failure so
a future change cannot silently turn it into a pass.

The out-of-process inertness harness WAS extracted and is live at
`tests/unit/test_developmental_inertness.py`.

## Authorization state

`SPECIFICATION_ONLY_NOT_AUTHORIZED`. Execution requires explicit founder approval
and remains blocked pending the bridge rule, which cannot be fully specified until
a real dependency graph exists.
