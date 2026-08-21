# PA-0 — pre-arrival control handling: exact diagnosis

Measured against the real runtime at `0ccda5c`, through the repository's own
fixtures and its own delivery entry points. No mirrored model: this imports
`substrate.v5`, builds a real organ, uses the real `_pair()` / `_open()` helpers
from `test_substrate_v5_direction_classification`, and calls the real
`deliver_terminal` and `deliver_search`.

## Reproduction (PA-0B — corrected)

```
python verification/phase3g/prearrival_diagnose.py                  # exits 0 only if every assertion holds
python verification/phase3g/prearrival_diagnose.py --negative-control
```

Machine-readable results: `PREARRIVAL_DIAGNOSIS.json`,
`PREARRIVAL_DIAGNOSIS_NEGATIVE_CONTROL.json`.

**The first committed version of this instrument was defective and its result is
withdrawn.** It recorded snapshots and asserted nothing, hardcoded three absolute
developer paths, and — decisively — omitted the `context=` argument the reported
measurement depended on. The corrected measurement existed only in an uncommitted
shell heredoc, so the written diagnosis and the executable artifact disagreed and
the repository could not reproduce its own conclusion. Seventh instance of the
instrument-liveness defect in this workstream, this time inside the evidence
artifact itself.

The instrument now **exits nonzero unless every assertion holds**, derives its
paths from `__file__`, and was executed in four working directories:

```
/home/user/uniimente-kernel                      PASS   0 failed assertions
/home/user/uniimente-kernel/verification/phase3g PASS   0 failed assertions
/                                                PASS   0 failed assertions
/tmp/uni-pa0b-port  (clean disposable worktree)  PASS   0 failed assertions
```

**Negative control.** `--negative-control` drops `context=` from the late
SearchNeed. T2 then fails as required:

```
T2 canonical node exists                        FAILED
T2 adopted_parent_edge == the pre-arrival edge  FAILED
observed: node_exists False, accepted_outcome SearchContextRejected
verdict: CORRECT — T2 adoption assertions failed as required
```

That is what proves the instrument distinguishes a **valid late adoption** from a
**context-rejected non-adoption** — the precise confusion its first version could
not have detected, because it was silently running the rejected path.

---

## The window

`adopted_parent_edge` is written exactly once, at node creation
(`substrate/v5.py:876`). There is no separate adoption step — **the node is the
adoption**. So the pre-arrival window is precisely:

> a parent control reaches a receiver before that receiver's canonical node for
> the control's `SearchKey` exists.

## Measured sequence

```
T0  probe created by sender, node absent
    node False · adopted_edge None · accepted_control None · edge open

T1  parent emits SearchCancelled on the edge it legitimately opened
    ORPHANED_SEARCH_EDGES 1
    node False · accepted_control None · edge open
    ^^ nothing else changed. No lifecycle record. No refusal returned.

T2  the SearchNeed finally arrives, node opens and adopts THAT SAME EDGE
    UNIQUE_CANONICAL_SEARCH_NODES 1
    node True · adopted_edge e/pa/clean · accepted_control None · edge open
    ^^ the T1 control is gone. The node now waits for a command it already
       received and discarded.

T3  the same control replayed AFTER the node exists
    SEARCH_CONTROLS_RECORDED 3 — it works, and cascades to child edges
```

## Classification

**SILENT LOSS.** Not rejection, not inert replay, not duplicate processing, not
unauthenticated acceptance, not lifecycle divergence, not credit divergence.

The control is discarded with a counter increment and nothing else:

- no refusal terminal travels back, so the sender cannot learn it was dropped;
- no lifecycle record is created, so the receiver retains no evidence it happened;
- the edge stays `open` on both ends.

Case 2 (`e/pa/never`, node never opens) is the same, permanently: the parent's
edge reads `terminal_status: open` forever, holding an allocation it can never
reconcile against evidence that was destroyed on arrival.

Correctly, nothing is currently *wrong* in the credit ledger — the defect is
**loss**, not corruption. A pending mechanism must not trade the first for the
second.

---

## The finding that constrains the design

`deliver_terminal` checks node existence at line 2720, **before** any sender
authentication at lines 2723-2729. Measured consequence, forged sender in the
pre-arrival window:

```
legitimate parent, pre-arrival   ORPHANED_SEARCH_EDGES 1   UNAUTHENTICATED_TERMINAL_CONTROLS 0
FORGED stranger,  pre-arrival    ORPHANED_SEARCH_EDGES 1   UNAUTHENTICATED_TERMINAL_CONTROLS 0
```

**Identical counter, identical state.** The forgery is refused — but for the
wrong reason, and it is indistinguishable in the evidence record from a
legitimate control. The authentication check never runs at all.

Today that ordering is harmless, because the branch drops everything. It becomes
a live vulnerability the moment a pending state is introduced: a pending
mechanism that mirrors the current order — hold first, authenticate at adoption —
would admit forged controls into the pending store, and an attacker could seed a
receiver with controls for edges it has not yet adopted.

**The window is fully authenticable.** `probe_exists: True` in every measured
case, including the forged one. The sender-owned probe is created when the sender
opens the edge, so every fact needed to authenticate — both endpoints, the
`SearchKey`, the committed allocation — is already present before the node
exists.

So the design constraint is not a preference:

> Authenticate against the sender-owned probe FIRST, then hold. Never hold first
> and authenticate at adoption.

This inverts the current statement order and is the reason the mechanism can be
fail-closed without loosening anything.

---

## What PA-1 must therefore cover

The forged-sender case is not one test among fifteen — it is the case that
decides whether the mechanism is safe. Its paired positive control (identical
shape, legitimate sender, must be held and later applied) is what stops the
negative from passing against a runtime that holds nothing.

## Not established

Nothing here is a runtime change. Gate F UNMEASURED, Gate G UNMEASURED,
R8 PROHIBITED. No external effect. This commit is diagnosis only.
