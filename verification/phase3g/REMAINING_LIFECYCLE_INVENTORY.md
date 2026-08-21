# LC-0 — exact remaining lifecycle inventory

Evidence only. No runtime file, no test file, no marker changed.

Head `ba75a1f`. Every entry below was produced by executing the **real pytest node
ID** individually under `--runxfail`, not by reading the PR summary and not by any
mirrored fixture. The stale PR body is not a source here; repository truth is.

```
python -m pytest -q -rxXs -p no:randomly
python -m pytest -q -p no:randomly --runxfail --tb=line <node-id>
```

```
local suite   901 passed · 1 skipped · 11 xfailed · 0 failed
```

CI runs on the merge ref and may report **more skips than local**, because the
Git-ancestry pre-registration checks skip under a shallow checkout. The two
compositions are recorded separately and must not be collapsed into one number —
a single reconciled figure would hide exactly the class of divergence this
workstream keeps finding.

---

## The eleven, with first causal divergence

| # | node | first divergence | likely owner |
|---|---|---|---|
| 1 | `every_applied_control_receives_a_child_owned_completion` | `assert 1 == 0` — one applied control has no child completion | LC-2 |
| 2 | `every_coalesced_inbound_edge_closes_on_its_own_edge` | 1 coalesced alias never closed on its own edge | LC-2 |
| 3 | `every_closed_child_edge…carries_child_evidence` | **no child edge closed at all** — denominator empty | LC-2 |
| 4 | `canonical_lifecycle_and_its_projection_cannot_diverge` | the named counter **does not exist** | LC-3 |
| 5 | `two_inbound_edges_coalescing…close_separately` | no lifecycle record for `e/sep/coal/1` | LC-2 |
| 6 | `B_an_actual_cycle_is_closed_exactly_once` | `CYCLE_EDGES_CLOSED` fired, **no edge recorded the outcome** | LC-5A |
| 7 | `F_unsatisfiable_join_proves_space_exhausted` | fully explored wave reported as **budget shortfall** | LC-5B |
| 8 | `G_credit_starvation_never_claims_no_replacement` | `assert 0 >= 1` | LC-5B |
| 9 | `H_each_answered_node_returns_its_offer` | filters `SearchCommitted`, claims `SearchOffer` | LC-1 |
| 10 | `commit_and_cancel_reach_the_proposal_source_edge_multi_hop` | proposal correlated **only at the root** | LC-4 |
| 11 | `unit_id_permutation_preserves_semantics` | renaming units changed behaviour | LC-8 |

Owning-mechanism assignments are **hypotheses with stated probabilities** in the
JSON, not findings. Four of the eleven are more likely test or fixture defects
than runtime defects, and saying so before implementing anything is the point of
this phase.

---

## Four structural findings the per-test table does not show

**#6 and #7 are plausibly one fault seen twice.** `CYCLE_EDGES_CLOSED` increments
while no edge records the outcome — a semantic success counter moving before the
canonical lifecycle accepted the corresponding evidence. And F reports a *fully
explored* wave as a *budget* shortfall, which is G's confusion inverted. The
provisional shared primitive is **evidence-bound terminal commit**: derive the
claim, validate edge/direction/key/destination, record the accepted outcome,
close credit, and only then move the success metric. LC-4, LC-5 and LC-6 may be
one mechanism rather than three, and the factorial audit is what would decide it.

**#4 names a counter that does not exist, so it is currently unfalsifiable.**
No runtime can satisfy it as written. Under the instrument-liveness rule that
makes it the weakest item in the set — a specification nothing can satisfy is not
a pending feature, it is an instrument that cannot observe its own subject. It
also sits awkwardly beside `5G-V`, which already proves by consequence that a
*hostile* projection changes nothing. A divergence counter that must read zero on
a healthy run and fire under deliberate corruption is a narrower claim than the
one already established, and may be redundant coverage rather than a gap.

**#3's failure message is a non-vacuity guard firing, not a bug report.** The
spec refuses to pass with an empty denominator. That is the discipline working as
designed, and it means LC-2 must produce *real* closed child edges before its
ratio means anything at all.

**#8 and #10 fail on their own positive controls.** `assert 0 >= 1`, and "the
accepted proposal was correlated only at the root, so multi-hop closure was never
exercised". Both are fixture-debt suspects before they are runtime defects, and
treating either as a runtime failure first would be implementing against a test
that never reached the behaviour it names.

---

## The skip

```
tests/unit/test_substrate_v5_distinct_replacement.py:516
    test_widening_requires_the_whole_round_to_have_completed
    two skip points: line 525 "reopen did not create a need"
                     line 528 "no branches were opened"  <- the one that fires
```

Classification is **unresolved**. Whether this is obsolete legacy coverage, a
fixture that never opens a branch on the canonical path, or a genuine missing
widening behaviour is not determined by this phase and is not guessed here.

---

## Not established

No runtime change is authorized by this commit and none was made. Gate F
**UNMEASURED**, Gate G **UNMEASURED**, R8 **PROHIBITED**, no external effect.
