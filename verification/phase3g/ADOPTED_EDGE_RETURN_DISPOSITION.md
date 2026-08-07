# LC-1 — adopted-parent-edge return: disposition

Tests and evidence only. No runtime file changed. `substrate/v5.py` is
byte-identical to `bc13bc3`.

```
python -m pytest -q -p no:randomly --runxfail \
  tests/unit/test_substrate_v5_single_flight_echo.py::test_H_each_answered_node_returns_its_proposal_through_its_adopted_edge
python verification/phase3g/adopted_edge_return_negative_control.py
python verification/phase3g/adopted_edge_return_negative_control.py --verify-results
```

Machine-readable results: `ADOPTED_EDGE_RETURN_NEGATIVE_CONTROL.json`.

## Verdict

**Test defect, confirmed. Not a runtime defect.** The corrected test passes
against the runtime exactly as it stands, so nothing was implemented against it.

LC-0 predicted this at `test_defect_probability 0.95` / `runtime 0.05`,
`classification_confidence high`. That prediction is recorded as correct.

Node renamed, because the old name asserted the thing that was wrong:

```
test_H_each_answered_node_returns_its_offer_through_its_adopted_edge      (ba75a1f)
test_H_each_answered_node_returns_its_proposal_through_its_adopted_edge   (here)
```

`REMAINING_LIFECYCLE_INVENTORY.json` still carries the old node id. That file
records the state at `ba75a1f` and is left intact rather than edited to match a
later name; this section is the mapping between them.

## What was wrong

The old filter searched `search_edge_terminals` for records whose outcomes
contained `SearchCommitted`, and called those "SearchOffer terminals". Two
independent reasons it could never match:

1. `SearchCommitted` is a **parent control**. The active 2D rule forbids a child
   from emitting one upward on its adopted parent edge, so the filter demanded
   exactly the message the protocol prohibits.
2. Since the lifecycle/projection separation, `search_edge_terminals` holds
   **accepted outcomes only**, and a proposal is a NONTERMINAL. No proposal can
   appear there in any direction.

There is no `SearchOffer` type in the protocol. The canonical name is
`SearchProposal`, carried as `("__proposal__", SearchKey, edge_id, payload)`.
No alias was added to keep the old wording alive.

The route a node chose is recorded in one place — the message it put in its own
outbox — so the corrected test reads it there. Arrival is captured separately at
`deliver_proposal`, because a sender-side trace alone would pass against a
runtime whose messages never leave the outbox, and cannot show that the unit the
sender NAMED is the unit that received it.

## Three fixtures, and why each is required

The negative control is what forced the third one.

| fixture | seed | supplies | proposals | relays | pre-emission contest | upward edges inspected |
|---|---|---|---|---|---|---|
| `n_auth=4 density=1.0` | 0 | pre-registered; competing arrival at an answering node | 2 | 0 | 0 | 2 |
| `n_auth=5 density=0.8` | 0 | a genuine relay hop | 4 | 1 | 0 | 4 |
| `n_auth=3 density=0.6` | 5 | a node proposing while already holding a second arrival | 14 | 7 | 2 | 1 |

The three are kept together rather than reduced to the largest. The third is
strong on routing and weak on the upward-control channel — only one of its
fourteen adopted parent edges carried a recorded outcome — so the first two are
what actually inspect that channel.

## Two defects the negative control found in the corrected test

Both were in work written during this same task, and neither would have been
visible from a passing test.

**`most_recent_incoming_edge` escaped.** The candidate returns evidence through
the last edge that arrived instead of the adopted one — the `reverse[need_id]`
capture defect itself. It escaped because in the first two fixtures **every**
proposing node still had exactly one arrival at the moment it emitted: the
competing arrival lands *after* the proposal. The broken candidate therefore
emitted precisely what the correct one would have. An attack that cannot change
the output is not evidence of coverage, and the run that looked like coverage
was a no-op. Fixed by adding the third fixture, and by measuring
`pre_emission_contested` so the shape cannot silently vanish again.

**Every attack reported the same failure.** A group-level "all proposals used
one edge" check ran ahead of the per-record clauses and short-circuited them, so
alias substitution and origin-jumping both surfaced as one generic
unstable-route message. The test still failed, but it had stopped naming *which*
route was wrong, which is the one thing it exists to do. Fixed by ordering the
per-record clauses first; the group-level stability check now runs last.

A third finding is not a defect but a correction to my model of the protocol: a
relayed proposal's `source_edge_id` is **not rewritten at each hop**. A proposal
relayed twice still carries the edge its original supplier answered on, so the
emitting unit is generally neither the source node nor the unit that opened the
source edge. The attribution check was replaced with the path property itself —
the emitter must stand on the adopted return path walked from that source.

## Result

```
most_recent_incoming_edge   CAUGHT   wrong_edge         n_auth=3 density=0.6
non_adopted_alias           CAUGHT   wrong_edge         all three fixtures
jump_to_origin              CAUGHT   wrong_destination  n_auth=5, n_auth=3
positive control            PASSED   all three fixtures
```

`jump_to_origin` keeps the adopted edge and changes only the destination. A
candidate that changed both would be rejected on the edge first and the report
would never show that a wrong destination is discriminated at all.

The control runs in CI (`preregistration.yml`) under `--verify-results`. An
instrument nobody executes is a claim; this is the eighth place in this
workstream where that rule applied.

## Not established

No runtime change. The other ten strict xfails are untouched. Gate F
**UNMEASURED**, Gate G **UNMEASURED**, R8 **PROHIBITED**, no external effect.
