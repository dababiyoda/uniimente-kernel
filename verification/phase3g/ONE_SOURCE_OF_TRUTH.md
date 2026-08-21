# 5G-V — one source of truth, verified by consequence

`search_edge_lifecycle` is the only independently written lifecycle record.
`search_edge_terminals` is a strict derivation of its accepted-outcome channel
and holds no decision authority.

Two independent arguments, because either one alone is defeatable.

---

## 1. Static — what the source says

Every reference to `search_edge_terminals` in `substrate/v5.py` after `4330d41`:

```
1395  WRITE   o.search_edge_terminals[t.edge_id] = {...}   in _record_outcome
3596  init    self.search_edge_terminals: dict = {}
816, 1361, 1392, 1557, 1879                                 comments
```

**Zero reads.** `LEGACY_TERMINAL_PROJECTION_DECISION_SITES = 0`. No surviving
reference can influence replay, adoption, coalescence, closure, reconciliation,
credit, routing or settlement, because no surviving reference reads it at all.

Three sites did, until `b878d2c`:

| site | what it decided | what it read |
|---|---|---|
| `deliver_search` | inert replay, ahead of cycle / closed-Need / coalescing / context / adoption | `edge_id in search_edge_terminals` |
| `_reconcile_closed_children` | whether a child liability may close | `search_edge_terminals[edge]["outcomes"][0]` |
| `replay_search_edge` | whether a replay is a no-op | `edge_id in search_edge_terminals` |

The control path also wrote that store, so a parent's own command satisfied all
three. **A command is not an answer**, and all three now read
`search_edge_lifecycle[edge]["accepted_outcome"]`.

## 2. Dynamic — what the runtime does when the projection lies

Static inventory is only as current as the last person who read it. A read
added tomorrow makes the table above wrong and nothing reports it. So the
property is also proved by consequence, in
`tests/unit/test_substrate_v5_projection_inertness.py`.

Two identical organs take the same damage and the same **two** repairs. One has
its compatibility projection replaced by a hostile mapping: every write is
forged on arrival and an earlier entry is destroyed as it goes. Not merely
emptied — an emptied store answers "no such edge", which a reader might handle
correctly by accident. This answers with confident wrong data.

If any decision still consults it, the twins must diverge. They do not:

```
nodes · settlement · messages · events · accepted_controls
accepted_outcomes · conflicts · credit          all identical
```

**Two repairs, not one.** Corrupting a projection and then running an item on an
already-repaired organ may initiate no repair at all, so the store never goes
near a decision and the comparison proves nothing. The second damage is chosen
inside the active dependency cone and the test asserts it opened new canonical
nodes and drove `REPAIR_REOPENS > 0` before it compares anything.

### The guard is load-bearing, and that was measured

A guard that cannot fail is worth nothing, so it was run against the runtime it
is meant to catch:

| control | runtime | result |
|---|---|---|
| positive | current (`4330d41`) | **2 passed** — a hostile projection changes nothing |
| negative | pre-migration (`7c29c93`) | **fails on divergence**, naming `accepted_outcomes` |

The negative run diverges concretely: the hostile twin opens extra edges
(`/r0/c0/r1/c0`, `/r0/c2/r1/c0`) and settles two edges differently, because the
corrupted store no longer suppresses the replays it was silently deciding.

**The first attempt at this instrument failed its own negative control**, and
the failure was informative. `_HostileProjection` overrode `__setitem__` only,
while the historical control path wrote through `setdefault` — so against the
very runtime it needed to distinguish, the corruption did not land and the test
reported "the hostile projection does not actually hold forged data" instead of
divergence. It now intercepts both write paths.

## 3. What is written, not only what is read

Paired with the above, because "inert" must not be satisfiable by a store that
quietly accumulates commands nobody happens to read *yet*:

```
PROJECTION_ENTRIES                                    13
PROJECTION_ENTRIES_NOT_DERIVED_FROM_ACCEPTED_OUTCOME   0
```

Every entry is the identical object held in that edge's `accepted_outcome`, and
an edge that was only commanded does not appear at all.

A consequence to state rather than let someone rediscover as a bug: the
`outcomes` array is now always length 0 or 1 by construction. **That is a
projection shape, not a lifecycle invariant**, and asserting it as one is
exactly what produced the mirrored audits' phantom regression set.

---

## Final acceptance — canonical live-repair fixture, two real repairs

```
PARENT_CONTROLS_RECORDED_AS_CHILD_OUTCOMES     0    LIFECYCLE_CONTROL_CONFLICTS   0
OUTCOME_SLOT_OCCUPIED_BY_CONTROL               0    LIFECYCLE_OUTCOME_CONFLICTS   0
COMMANDED_EDGES_WITHOUT_ACCEPTED_OUTCOME       0    DUPLICATE_ACCEPTED_OUTCOMES   0
CLOSED_NODES_WITH_CHILDREN_OUTSTANDING         0    DUPLICATE_SUBTREES_OPENED     0
CLOSED_CHILD_EDGES_WITHOUT_CHILD_EVIDENCE      0    DUAL_REPAIR_SEARCHES          0
UNCLASSIFIABLE_TERMINAL_RECORDINGS             0    DUPLICATE_CANONICAL_ROOTS     0
UNAUTHENTICATED_TERMINAL_EMISSIONS             0    UNAUTHORIZED_EXTERNAL_EFFECTS 0
UNKNOWN_EDGE_TERMINAL_EMISSIONS                0    INHERITED_AUTHORITY_EVENTS    0
DUPLICATE_TERMINAL_RESOLUTIONS                 0    TERMINALS_WITH_UNRECONCILED_CHILDREN 0
CANONICAL_LIVE_REPAIR_LEGACY_NEED_MESSAGES     0

FORMATION_EVENTS      16          FORMATION_MESSAGES     1012
CHECKSUM_ENTRIES_VERIFIED 20      CHECKSUM_FAILURES         0
```

**The zeros are non-vacuous, and this is the number that shows it:**

```
COMMANDED_EDGES                            10
COMMANDED_EDGES_WITHOUT_ACCEPTED_OUTCOME    0
```

Ten commanded edges, every one ending in an accepted child outcome. A runtime
that commanded nothing would post the same zero above and mean nothing by it.

Positive activity on the same run, so "clean" is not "idle":

```
REPAIR_REOPENS 1 · REPAIR_REOPENS_WITH_CANONICAL_ROOT 1 · CANONICAL_ROOTS_CREATED 1
UNIQUE_PROPOSAL_DECISIONS 1 · ELIGIBLE_PROPOSALS_COMMITTED 1
SEARCH_CONTROLS_RECORDED 6 · TERMINAL_ECHOS_SENT 8 · result valid
```

### Two items reported honestly rather than asserted

- **`COMMANDED_EDGES_WITHOUT_ACCEPTED_OUTCOME` is not a runtime counter.** It is
  computed from the lifecycle above, and it is enforced continuously by the
  active specification `test_every_commanded_edge_ends_with_an_accepted_child_outcome`,
  activated in `48a5d4b`. Reporting it as a counter would imply an increment
  site that does not exist.
- **`LEGACY_REPAIR_NEED_MESSAGES` is scoped, deliberately.** Zero is required on
  the canonical live-repair fixture, where it is meaningful. It is *not* required
  across a full-suite accumulated total, because formation tests intentionally
  exercise the preserved legacy path and a global zero would demand deleting
  behaviour that is correct.

---

## Suite

```
886 passed · 1 skipped · 11 xfailed · 0 failed
```

884 was the predicted final composition after `5G-RM`; the two additional passes
are this commit's own guards. `5G-W` moved the composition by nothing at all,
which is the evidence that the writer cleanup removed no decision weight.

## Not established

- Gate F: **UNMEASURED**. Gate G: **UNMEASURED**. R8: **PROHIBITED**.
- This establishes protocol correctness and measurement integrity. It says
  nothing about architectural superiority — the conventional durable workflow
  engine remains the strongest current comparison, and R8 is what would decide
  it.
- Pre-arrival edge handling is not begun. The remaining six lifecycle
  specifications are not resumed.
