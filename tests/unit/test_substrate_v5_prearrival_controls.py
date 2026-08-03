"""PA-1: authenticated parent controls that arrive before their search node.

PRE-REGISTERED BEFORE THE CORRESPONDING RUNTIME CHANGE. Every specification is
strict xfail: an implementation that satisfies one early is a suite failure
until the marker is removed in a separate, reviewable activation commit.

The defect at PA-0/PA-0B is SILENT LOSS, not credit corruption. A parent-owned
control can traverse the real Terminal dispatch path before the receiver has
adopted the SearchKey. The receiver currently checks for the node first and
drops the control as orphaned, even though the sender-owned probe already binds
the edge, key, allocation, source and destination.

These tests require the smallest safe repair:

* authenticate against the sender-created probe before retaining anything;
* retain one full control and at most one conflict fingerprint in the existing
  per-edge lifecycle record (never a second pending dictionary or queue);
* distinguish sender-side emission from actual receiver-side arrival;
* apply the held command exactly once, immediately after valid node adoption;
* preserve the context gate, replay idempotence, credit conservation, edge
  isolation, and first-command-wins semantics.
"""
from __future__ import annotations

import dataclasses
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pytest

import substrate.v5 as v5
from substrate.v5 import C, Capability, Contract, Organ, Terminal, Unit, reset


prearrival = pytest.mark.xfail(
    strict=True,
    reason="PA-1 pre-registration: authenticated pre-arrival controls not implemented",
)


def _ctx(**updates) -> v5.SearchContext:
    values = dict(
        causally_refused_sources=frozenset(),
        must_differ_from_suppliers=frozenset(),
        maximum_supplier_cost=20.0,
        cooldown_excluded_suppliers=frozenset(),
        constraint_generation=1,
        policy_snapshot=("policy/prearrival/v1",),
    )
    values.update(updates)
    return v5.SearchContext(**values)


def _unit(uid: str, produces: str) -> Unit:
    return Unit(
        uid,
        Capability(
            f"cap/{uid}", (), produces, lambda: uid, 1.0,
            f"domain/{uid}", f"class/{uid}",
        ),
    )


def _rig():
    parent = _unit("parent", "PARENT")
    receiver = _unit("receiver", "WANTED")
    attacker = _unit("attacker", "ATTACK")
    other = _unit("other", "WANTED")
    organ = Organ(
        [parent, receiver, attacker, other],
        Contract("prearrival", "INPUT", "OUTPUT", lambda _v: True),
    )
    organ.connect(parent.unit_id, receiver.unit_id)
    organ.connect(parent.unit_id, other.unit_id)
    organ.connect(attacker.unit_id, receiver.unit_id)
    return organ, parent, receiver, attacker, other


def _key(ctx: v5.SearchContext, suffix: str = "a") -> v5.SearchKey:
    return v5.SearchKey.build(
        need_id=f"need/prearrival/{suffix}",
        work_item_generation=7,
        origin_unit="parent",
        origin_slot=0,
        wanted_type="WANTED",
        context=ctx,
    )


def _wire(organ: Organ, parent: Unit, receiver: Unit, *, suffix: str = "a",
          allocation: float = 6.0):
    """Create the actual search tuple and Terminal found in a Unit outbox."""
    ctx = _ctx()
    key = _key(ctx, suffix)
    edge = f"edge/prearrival/{suffix}"
    parent._record_probe(
        edge, parent.unit_id, receiver.unit_id, key, allocation=allocation,
    )
    parent.outbox.append((
        receiver.unit_id,
        ("__search__", key, edge, allocation, (parent.unit_id,), ctx),
    ))
    control = parent._emit_terminal(
        "SearchCancelled", key, edge, receiver.unit_id,
        reason="parent_wave_closed",
    )
    emitted = list(parent.outbox)
    parent.outbox.clear()
    assert len(emitted) == 2, "the fixture did not emit one search and one control"
    search_msg = emitted[0][1]
    control_msg = emitted[1][1]
    assert isinstance(search_msg, tuple) and search_msg[0] == "__search__"
    assert isinstance(control_msg, Terminal) and control_msg is control
    return ctx, key, edge, search_msg, control_msg


def _deliver(receiver: Unit, sender: str, message) -> None:
    """Use the production Unit.step dispatch seam; do not call the handler."""
    receiver.inbox.append((sender, message))
    receiver.step({})


def _lifecycle(organ: Organ, edge: str) -> dict:
    rec = organ.search_edge_lifecycle.get(edge)
    assert rec is not None, f"no canonical lifecycle record for {edge}"
    return rec


def _counter(name: str) -> int:
    assert name in C.d, f"missing live counter {name}"
    return C[name]


def _assert_held(organ: Organ, receiver: Unit, key: v5.SearchKey, edge: str,
                 control: Terminal) -> None:
    rec = _lifecycle(organ, edge)
    assert rec["accepted_control"] == control
    assert rec.get("prearrival_control_state") == "held"
    assert key not in receiver.canonical_searches
    edge_state = organ.search_edges[edge]
    assert edge_state["terminal_status"] == "open"
    assert edge_state["terminal_outcome"] is None
    assert edge not in organ.search_edge_terminals


def _assert_applied(organ: Organ, receiver: Unit, key: v5.SearchKey,
                    edge: str) -> dict:
    node = receiver.canonical_searches.get(key)
    assert node is not None, "the authenticated search was not adopted"
    assert node["adopted_parent_edge"] == edge
    assert node["wave_cancelled"] is True
    assert node["terminal_signal_sent"] is True
    assert node["status"] == "CLOSED"
    assert node["local_candidate"] is None
    assert node["children_opened"] == []
    assert _lifecycle(organ, edge).get("prearrival_control_state") == "applied"
    return node


@prearrival
def test_real_outbox_reordering_applies_without_sender_replay():
    organ, parent, receiver, _attacker, _other = _rig()
    _ctx0, key, edge, search, control = _wire(organ, parent, receiver)
    reset()

    # The transport delivers the two objects in reverse order. The sender emits
    # and transmits the control exactly once.
    _deliver(receiver, parent.unit_id, control)
    _deliver(receiver, parent.unit_id, search)

    _assert_applied(organ, receiver, key, edge)
    assert _counter("PREARRIVAL_CONTROLS_HELD") == 1
    assert _counter("PREARRIVAL_CONTROLS_APPLIED") == 1
    assert _counter("PREARRIVAL_CONTROL_REPLAYS") == 0
    assert C["ORPHANED_SEARCH_EDGES"] == 0


@prearrival
def test_legitimate_prearrival_control_is_held_without_premature_mutation():
    organ, parent, receiver, _attacker, _other = _rig()
    _ctx0, key, edge, _search, control = _wire(organ, parent, receiver)
    reset()

    _deliver(receiver, parent.unit_id, control)

    _assert_held(organ, receiver, key, edge, control)
    assert _counter("PREARRIVAL_CONTROLS_HELD") == 1
    assert _counter("PREARRIVAL_CONTROLS_APPLIED") == 0
    assert C["PARENT_CONTROLS_APPLIED"] == 0


@prearrival
def test_held_control_applies_exactly_once_after_adoption():
    organ, parent, receiver, _attacker, _other = _rig()
    _ctx0, key, edge, search, control = _wire(organ, parent, receiver)
    reset()
    _deliver(receiver, parent.unit_id, control)
    _deliver(receiver, parent.unit_id, search)
    before = (
        C["PARENT_CONTROLS_APPLIED"],
        _counter("PREARRIVAL_CONTROLS_APPLIED"),
        dict(organ.search_edges[edge]),
    )

    _deliver(receiver, parent.unit_id, search)

    _assert_applied(organ, receiver, key, edge)
    after = (
        C["PARENT_CONTROLS_APPLIED"],
        _counter("PREARRIVAL_CONTROLS_APPLIED"),
        dict(organ.search_edges[edge]),
    )
    assert before == after
    assert before[0:2] == (1, 1)


@prearrival
def test_exact_replay_before_adoption_is_inert_and_counted():
    organ, parent, receiver, _attacker, _other = _rig()
    _ctx0, key, edge, _search, control = _wire(organ, parent, receiver)
    reset()

    _deliver(receiver, parent.unit_id, control)
    _deliver(receiver, parent.unit_id, control)

    _assert_held(organ, receiver, key, edge, control)
    rec = _lifecycle(organ, edge)
    assert rec["controls"] == [control]
    assert rec["control_conflicts"] == []
    assert _counter("PREARRIVAL_CONTROLS_HELD") == 1
    assert _counter("PREARRIVAL_CONTROL_REPLAYS") == 1


@prearrival
def test_exact_replay_after_adoption_is_inert_and_counted():
    organ, parent, receiver, _attacker, _other = _rig()
    _ctx0, key, edge, search, control = _wire(organ, parent, receiver)
    reset()
    _deliver(receiver, parent.unit_id, control)
    _deliver(receiver, parent.unit_id, search)
    before = dict(receiver.canonical_searches[key])

    _deliver(receiver, parent.unit_id, control)

    assert receiver.canonical_searches[key] == before
    assert C["PARENT_CONTROLS_APPLIED"] == 1
    assert _counter("PREARRIVAL_CONTROLS_APPLIED") == 1
    assert _counter("PREARRIVAL_CONTROL_REPLAYS") == 1


@prearrival
def test_forged_sender_is_rejected_and_paired_legitimate_control_is_held():
    organ, parent, receiver, attacker, _other = _rig()
    _ctx0, key, edge, _search, control = _wire(organ, parent, receiver)
    reset()

    _deliver(receiver, attacker.unit_id, control)
    rec = _lifecycle(organ, edge)
    assert rec.get("prearrival_control_state") in (None, "")
    assert key not in receiver.canonical_searches
    assert C["UNAUTHENTICATED_TERMINAL_CONTROLS"] == 1
    assert _counter("PREARRIVAL_CONTROLS_HELD") == 0

    _deliver(receiver, parent.unit_id, control)
    _assert_held(organ, receiver, key, edge, control)
    assert _counter("PREARRIVAL_CONTROLS_HELD") == 1


@prearrival
def test_wrong_search_key_cannot_allocate_pending_state():
    organ, parent, receiver, _attacker, _other = _rig()
    ctx, _key0, edge, _search, _control = _wire(organ, parent, receiver)
    wrong = _key(ctx, "wrong")
    forged = Terminal(
        "SearchCancelled", wrong, edge, 0.0, 0.0,
        parent.unit_id, receiver.unit_id, "wrong_key", "",
    )
    reset()

    _deliver(receiver, parent.unit_id, forged)

    assert wrong not in receiver.canonical_searches
    assert _lifecycle(organ, edge).get("prearrival_control_state") in (None, "")
    assert C["UNAUTHENTICATED_TERMINAL_CONTROLS"] == 1
    assert _counter("PREARRIVAL_CONTROLS_HELD") == 0


@prearrival
def test_probe_for_another_destination_cannot_allocate_pending_state():
    organ, parent, receiver, _attacker, other = _rig()
    ctx = _ctx()
    key = _key(ctx, "destination")
    edge = "edge/prearrival/destination"
    parent._record_probe(edge, parent.unit_id, other.unit_id, key, allocation=6.0)
    forged = Terminal(
        "SearchCancelled", key, edge, 0.0, 0.0,
        parent.unit_id, receiver.unit_id, "wrong_destination", "",
    )
    reset()

    _deliver(receiver, parent.unit_id, forged)

    assert edge not in organ.search_edge_lifecycle
    assert C["UNAUTHENTICATED_TERMINAL_CONTROLS"] == 1
    assert _counter("PREARRIVAL_CONTROLS_HELD") == 0


@prearrival
def test_wrong_claimed_source_cannot_mark_a_control_held():
    organ, parent, receiver, attacker, _other = _rig()
    _ctx0, key, edge, _search, control = _wire(organ, parent, receiver)
    forged = dataclasses.replace(control, from_unit=attacker.unit_id)
    reset()

    _deliver(receiver, parent.unit_id, forged)

    assert key not in receiver.canonical_searches
    assert _lifecycle(organ, edge).get("prearrival_control_state") in (None, "")
    assert C["UNAUTHENTICATED_TERMINAL_CONTROLS"] == 1
    assert _counter("PREARRIVAL_CONTROLS_HELD") == 0


@prearrival
def test_wrong_claimed_receiver_cannot_mark_a_control_held():
    organ, parent, receiver, _attacker, other = _rig()
    _ctx0, key, edge, _search, control = _wire(organ, parent, receiver)
    forged = dataclasses.replace(control, to_unit=other.unit_id)
    reset()

    _deliver(receiver, parent.unit_id, forged)

    assert key not in receiver.canonical_searches
    assert _lifecycle(organ, edge).get("prearrival_control_state") in (None, "")
    assert C["UNAUTHENTICATED_TERMINAL_CONTROLS"] == 1
    assert _counter("PREARRIVAL_CONTROLS_HELD") == 0


@prearrival
def test_child_outcome_kind_in_parent_direction_is_rejected():
    organ, parent, receiver, _attacker, _other = _rig()
    ctx = _ctx()
    key = _key(ctx, "direction")
    edge = "edge/prearrival/direction"
    parent._record_probe(edge, parent.unit_id, receiver.unit_id, key, allocation=6.0)
    wrong_direction = Terminal(
        "SearchExhausted", key, edge, 6.0, 0.0,
        parent.unit_id, receiver.unit_id, "wrong_direction", "",
    )
    reset()

    _deliver(receiver, parent.unit_id, wrong_direction)

    assert edge not in organ.search_edge_lifecycle
    assert C["UNAUTHENTICATED_TERMINAL_CONTROLS"] == 1
    assert _counter("PREARRIVAL_CONTROLS_HELD") == 0


@prearrival
def test_first_full_command_identity_wins_a_same_kind_conflict():
    organ, parent, receiver, _attacker, _other = _rig()
    _ctx0, key, edge, search, control = _wire(organ, parent, receiver)
    conflict = dataclasses.replace(control, reason="different_command_identity")
    assert conflict.kind == control.kind and conflict != control
    reset()

    _deliver(receiver, parent.unit_id, control)
    _deliver(receiver, parent.unit_id, conflict)

    rec = _lifecycle(organ, edge)
    assert rec["accepted_control"] == control
    assert rec["controls"] == [control]
    assert len(rec["control_conflicts"]) == 1
    fingerprint = rec["control_conflicts"][0]
    assert isinstance(fingerprint, str) and len(fingerprint) == 64
    assert _counter("PREARRIVAL_CONTROL_CONFLICTS") == 1

    _deliver(receiver, parent.unit_id, search)
    _assert_applied(organ, receiver, key, edge)
    assert _lifecycle(organ, edge)["accepted_control"] == control


@prearrival
def test_repeated_conflicts_are_counted_but_retained_state_is_bounded():
    organ, parent, receiver, _attacker, _other = _rig()
    _ctx0, key, edge, _search, control = _wire(organ, parent, receiver)
    reset()
    _deliver(receiver, parent.unit_id, control)

    for index in range(25):
        conflict = dataclasses.replace(control, reason=f"conflict/{index}")
        _deliver(receiver, parent.unit_id, conflict)

    rec = _lifecycle(organ, edge)
    assert rec["accepted_control"] == control
    assert rec["controls"] == [control]
    assert len(rec["control_conflicts"]) == 1
    assert len([x for x in organ.search_edge_terminal_conflicts
                if x[0] == edge]) <= 1
    assert _counter("PREARRIVAL_CONTROL_CONFLICTS") == 25
    _assert_held(organ, receiver, key, edge, control)


@prearrival
def test_pending_state_is_isolated_by_edge_and_requires_actual_delivery():
    organ, parent, receiver, _attacker, _other = _rig()
    _ctx_a, key_a, edge_a, search_a, control_a = _wire(
        organ, parent, receiver, suffix="isolation-a",
    )
    _ctx_b, key_b, edge_b, search_b, control_b = _wire(
        organ, parent, receiver, suffix="isolation-b",
    )
    reset()

    # Both controls were emitted and recorded sender-side, but only A is
    # actually delivered. Emission alone must never become receiver authority.
    _deliver(receiver, parent.unit_id, control_a)
    _deliver(receiver, parent.unit_id, search_b)

    node_b = receiver.canonical_searches.get(key_b)
    assert node_b is not None
    assert node_b["wave_cancelled"] is False
    assert _lifecycle(organ, edge_b).get("prearrival_control_state") in (None, "")
    assert _lifecycle(organ, edge_b)["accepted_control"] == control_b

    _deliver(receiver, parent.unit_id, search_a)
    _assert_applied(organ, receiver, key_a, edge_a)
    assert receiver.canonical_searches[key_b]["wave_cancelled"] is False


@prearrival
def test_failed_context_gate_preserves_hold_until_a_valid_adoption():
    organ, parent, receiver, _attacker, _other = _rig()
    ctx, key, edge, search, control = _wire(organ, parent, receiver)
    bad = ("__search__", key, edge, 6.0, (parent.unit_id,),
           _ctx(policy_snapshot=("forged/policy",)))
    assert not bad[5].matches(key)
    reset()
    _deliver(receiver, parent.unit_id, control)

    _deliver(receiver, parent.unit_id, bad)
    _assert_held(organ, receiver, key, edge, control)
    assert key not in receiver.canonical_searches
    assert _counter("PREARRIVAL_CONTROLS_APPLIED") == 0

    _deliver(receiver, parent.unit_id, search)
    _assert_applied(organ, receiver, key, edge)
    assert _counter("PREARRIVAL_CONTROLS_HELD") == 1
    assert _counter("PREARRIVAL_CONTROLS_APPLIED") == 1
