# LC-2a — edge-scoped liability: exact diagnosis

Evidence only. No runtime file, no test file, no marker changed.

```
python verification/phase3g/edge_liability_diagnose.py
python verification/phase3g/edge_liability_diagnose.py --verify-results
```

Machine-readable results: `EDGE_LIABILITY_DIAGNOSIS.json`. The instrument exits
nonzero unless every finding below still holds, and it carries its own negative
control: it deliberately strands one edge and must report the count rising. A
zero-stranding result from an audit that cannot see a stranding is worth
nothing, and the first version of this control produced exactly that — it
dropped one call instead of one edge, the next outcome on that edge closed it,
and the injected defect healed itself.

## The four specifications

```
test_every_applied_control_receives_a_child_owned_completion   assert 1 == 0
test_every_coalesced_inbound_edge_closes_on_its_own_edge       assert 0 == 1
test_every_closed_child_edge_..._carries_child_evidence        assert 0 > 0
test_two_inbound_edges_coalescing_to_one_node_close_separately assert None is not None
```

## Finding 1 — the defect is real, and it is not where the tests look

Every LC-2 specification runs `_damaged(4, density=1.0)` or the synthetic
`_pair()`. Measured across three densities:

| fixture | seed | edges opened | answered | **stranded** | nodes holding children outstanding |
|---|---|---|---|---|---|
| `n_auth=4 density=1.0` | 0 | 6 | 6 | **0** | 0 |
| `n_auth=5 density=0.8` | 0 | 5 | 5 | **0** | 0 |
| `n_auth=3 density=0.6` | 5 | 39 | 26 | **13** | 10 |

At the density the specifications use, **every edge is already answered by its
receiving endpoint**. The runtime is correct there. The stranded-liability
defect those tests describe is real and reproducible — 13 of 39 edges, five
distinct parents left waiting, ten canonical nodes holding
`children_outstanding` forever — but only at sparse density, which no LC-2
fixture reaches.

So these four tests cannot fail for the reason their docstrings give. Whatever
is failing them is something else, and Findings 2 and 3 are what it is.

## Finding 2 — five of the seven metric counters can never move

```
CLOSED_CHILD_EDGES                              declared, incremented 0 times
CLOSED_CHILD_EDGES_WITH_ACCEPTED_CHILD_OUTCOME  declared, incremented 0 times
CLOSED_CHILD_EDGES_WITHOUT_CHILD_EVIDENCE       declared, incremented 0 times
PARENT_CONTROLS_RECORDED_AS_CHILD_OUTCOMES      declared, incremented 0 times
OUTCOME_SLOT_OCCUPIED_BY_CONTROL                declared, incremented 0 times
CHILD_EDGES_RECONCILED_FROM_EVIDENCE            incremented, reads 0 on all three
TERMINALS_WITH_UNRECONCILED_CHILDREN            incremented, reads 0 on all three
```

`test_every_closed_child_edge_..._carries_child_evidence` asserts on all seven.
Its denominator guard — `CLOSED_CHILD_EDGES > 0` — is the assertion that fires,
and it fires because the counter is dead, not because no edge closed: six edges
reached `terminal_status == "terminal"` in the same run.

Three of its remaining assertions are **vacuously satisfied** by counters
nothing can increment. The guard is doing its job: it refuses to let the ratio
pass with an empty denominator, and it is the only thing standing between this
specification and a green result that means nothing.

`TERMINALS_WITH_UNRECONCILED_CHILDREN` reads 0 on the sparse fixture while ten
nodes hold children outstanding. It is incremented somewhere, but not on this
path, so it does not currently measure what its name claims.

## Finding 3 — one writer, so two of the counters cannot disagree

`terminal_status = "terminal"` is written in exactly one place,
`_record_outcome` (`substrate/v5.py:1421`), which is reached only for
outcome-channel terminals — receiver to opener, direction already established
by `_may_emit`. Measured consequence, all three fixtures:

```
edges marked terminal WITHOUT an accepted child outcome    0
```

Since the 5B/5G separation the runtime **structurally cannot** close a child
edge without child evidence. So `CLOSED_CHILD_EDGES` and
`CLOSED_CHILD_EDGES_WITH_ACCEPTED_CHILD_OUTCOME` would be equal by construction
if both were incremented at that one site, and
`CLOSED_CHILD_EDGES_WITHOUT_CHILD_EVIDENCE` would be a constant zero.

That is the trap to avoid. Incrementing all three there would turn
`assert WITH_ACCEPTED == closed` and `assert WITHOUT_EVIDENCE == 0` into
assertions that two names for one increment agree with each other — three more
instruments that cannot observe their own subject, added deliberately this
time. The metric has to be **derived from edge state at measurement time**, as
this instrument's `audit()` derives it, so that a future path which closes an
edge some other way is detectable rather than uncounted.

## Finding 4 — the coalesced edge is not the stranded one

`test_two_inbound_edges_coalescing_to_one_node_close_separately` says the second
arrival "is precisely the edge that strands a parent today". Measured on its own
fixture, immediately after its two `deliver_search` calls:

```
e/sep/coal/2  (coalesced, non-adopted)  accepted_outcome SearchCoalesced
                                        from_unit = the receiving endpoint  ✓
e/sep/coal/1  (ADOPTED)                 no lifecycle record at all
                                        node status OPEN, reason candidate_silent
```

The premise is inverted. The coalesced edge is answered correctly and
immediately. The **adopted** edge is the one with no record — and legitimately
so at that instant: the node returned `SearchPending`, the search is still in
progress, and an adopted edge is answered when the node resolves, not when it
is opened. The test reads both edges at a moment when only one of them can yet
have an answer.

That does not make the adopted edge safe. In this fixture nothing ever resolves
the node — the candidate is silent — so the adopted edge stays open forever.
The specification is pointing at a real hazard and measuring it at the wrong
time, which is why it reports a missing record rather than a stranding.

## What LC-2 therefore has to be

Not "close the coalesced edge": that already happens. The mechanism owed is a
**continuation for the adopted edge** — the liability a node accepts when it
adopts a parent edge must be discharged on that same edge when the node reaches
any terminal condition, including the conditions the sparse fixture reaches and
the dense one does not.

Three things must be true of it, and each is a way the obvious implementation
goes wrong:

1. it must not close an edge on the opener's assertion, which is the conflation
   the whole 5B split removed;
2. its metric must be derived, not a family of counters incremented together at
   one site, or the specification measures its own bookkeeping;
3. it must distinguish *legitimately still open* from *permanently stranded*,
   which the current fixtures cannot do because they never drive a search to a
   conclusion.

The design comparison and the mechanism are LC-2b and LC-2c. Nothing here
authorizes either.

## Not established

No runtime change and none was made. `substrate/v5.py` is byte-identical to
`bc13bc3`. The four specifications remain strict xfail. Gate F **UNMEASURED**,
Gate G **UNMEASURED**, R8 **PROHIBITED**, no external effect.
