#!/usr/bin/env python3
"""PA-5 executable evidence for authenticated pre-arrival parent controls.

The parity twin uses the same two edges in both runs. Run A delivers edge A in
normal order and edge B in reversed order; run B swaps those orders. This makes
the observation counters equal by construction while still requiring each
edge's final lifecycle, credit, and wire messages to be order-independent.

The instrument also pairs a forged delivery with the legitimate sender, floods
exact replays and full-identity conflicts, and proves that emission on one edge
cannot apply on another. It writes nothing. ``--verify-results`` compares the
live measurement with the committed JSON. ``--negative-control`` deliberately
removes the reversed delivery from run B and succeeds only when parity fails.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import pathlib
import sys
from typing import Any


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import substrate.v5 as v5  # noqa: E402
from substrate.v5 import (  # noqa: E402
    C,
    Capability,
    Contract,
    Organ,
    Terminal,
    Unit,
    reset,
)


RUNTIME_COMMIT = "f8a887bb60aa9790968050411e373755f7e4b119"
MARKER_COMMIT = "767dbfa9cab1ae5382e6f67e1f663908ca0eaec0"
FROZEN_TEST_SHA256 = (
    "0648a9c3d1a0862608bbca0e5f3d97989b7e602a6ad949ca147e8f92b045e531"
)
RESULTS = HERE / "PREARRIVAL_CONTROL_RESULTS.json"

CHECKS: list[str] = []
FAILURES: list[str] = []


def check(label: str, condition: bool) -> None:
    CHECKS.append(label)
    if not condition:
        FAILURES.append(label)


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def context() -> v5.SearchContext:
    return v5.SearchContext(
        causally_refused_sources=frozenset(),
        must_differ_from_suppliers=frozenset(),
        maximum_supplier_cost=20.0,
        cooldown_excluded_suppliers=frozenset(),
        constraint_generation=1,
        policy_snapshot=("policy/prearrival/pa5",),
    )


def unit(uid: str, produces: str) -> Unit:
    return Unit(
        uid,
        Capability(
            f"cap/{uid}", (), produces, lambda: uid, 1.0,
            f"domain/{uid}", f"class/{uid}",
        ),
    )


def rig(*, attacker: bool = False):
    parent = unit("parent", "PARENT")
    receiver = unit("receiver", "OTHER")
    units = [parent, receiver]
    hostile = unit("attacker", "ATTACK") if attacker else None
    if hostile is not None:
        units.append(hostile)
    organ = Organ(
        units,
        Contract("prearrival-pa5", "INPUT", "OUTPUT", lambda _value: True),
    )
    organ.connect(parent.unit_id, receiver.unit_id)
    receiver.refused.add(parent.unit_id)
    if hostile is not None:
        organ.connect(hostile.unit_id, receiver.unit_id)
        receiver.refused.add(hostile.unit_id)
    return organ, parent, receiver, hostile


def key_for(ctx: v5.SearchContext, suffix: str) -> v5.SearchKey:
    return v5.SearchKey.build(
        need_id=f"need/prearrival/pa5/{suffix}",
        work_item_generation=8,
        origin_unit="parent",
        origin_slot=0,
        wanted_type="WANTED",
        context=ctx,
    )


def wire(parent: Unit, receiver: Unit, suffix: str, allocation: float = 6.0):
    ctx = context()
    key = key_for(ctx, suffix)
    edge = f"edge/prearrival/pa5/{suffix}"
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
    search = parent.outbox[-2][1]
    emitted_control = parent.outbox[-1][1]
    del parent.outbox[-2:]
    if emitted_control is not control:
        raise AssertionError("wire did not capture the emitted Terminal object")
    return key, edge, search, control


def deliver(receiver: Unit, sender: str, message: Any) -> None:
    receiver.inbox.append((sender, message))
    receiver.step({})


def terminal_snapshot(terminal: Terminal | None) -> dict[str, Any] | None:
    if terminal is None:
        return None
    return {
        "kind": terminal.kind,
        "edge_id": terminal.edge_id,
        "refund": terminal.refund,
        "handling_cost": terminal.handling_cost,
        "from_unit": terminal.from_unit,
        "to_unit": terminal.to_unit,
        "reason": terminal.reason,
        "proposal_id": terminal.proposal_id,
    }


def node_snapshot(receiver: Unit, key: v5.SearchKey) -> dict[str, Any]:
    node = receiver.canonical_searches[key]
    return {
        "status": node["status"],
        "adopted_parent_edge": node["adopted_parent_edge"],
        "adopted_parent_sender": node["adopted_parent_sender"],
        "wave_cancelled": node["wave_cancelled"],
        "terminal_signal_sent": node["terminal_signal_sent"],
        "ack_sent": node["ack_sent"],
        "children_opened": list(node["children_opened"]),
        "children_outstanding": sorted(node["children_outstanding"]),
        "local_candidate": terminal_snapshot(node.get("local_candidate")),
        "credit": {
            name: round(float(node[name]), 9)
            for name in (
                "incoming_allocation",
                "local_reserve",
                "child_allocations_in_flight",
                "cancelled_credit",
                "consumed_credit",
                "child_refunds_received",
                "returned_credit",
                "returned_to_parent",
            )
        },
    }


def lifecycle_snapshot(organ: Organ, edge: str) -> dict[str, Any]:
    rec = organ.search_edge_lifecycle[edge]
    edge_state = organ.search_edges[edge]
    return {
        "accepted_control": terminal_snapshot(rec.get("accepted_control")),
        "accepted_outcome": terminal_snapshot(rec.get("accepted_outcome")),
        "prearrival_control_state": rec.get("prearrival_control_state"),
        "controls_retained": len(rec["controls"]),
        "control_conflicts_retained": len(rec["control_conflicts"]),
        "outcomes_retained": len(rec["outcomes"]),
        "edge_terminal_status": edge_state["terminal_status"],
        "edge_terminal_outcome": edge_state["terminal_outcome"],
        "edge_refunded_credit": edge_state["refunded_credit"],
        "edge_consumed_credit": edge_state["consumed_credit"],
    }


def outbox_snapshot(receiver: Unit) -> list[dict[str, Any]]:
    messages = []
    for to, message in receiver.outbox:
        if isinstance(message, tuple) and message and message[0] == "__search_ack__":
            messages.append({
                "to": to,
                "kind": message[0],
                "edge_id": message[2],
                "refund": message[3],
                "consumed": message[4],
            })
        elif isinstance(message, Terminal):
            messages.append({"to": to, "terminal": terminal_snapshot(message)})
        else:
            messages.append({"to": to, "kind": str(message[0])})
    return sorted(messages, key=lambda item: json.dumps(item, sort_keys=True))


def nonzero_counters() -> dict[str, int]:
    return {name: C[name] for name in v5.COUNTER_NAMES if C[name]}


def run_twin(orders: dict[str, str]) -> dict[str, Any]:
    organ, parent, receiver, _ = rig()
    wired = {suffix: wire(parent, receiver, suffix) for suffix in ("a", "b")}
    reset()
    for suffix in ("a", "b"):
        key, _edge, search, control = wired[suffix]
        sequence = (search, control) if orders[suffix] == "normal" else (
            control, search,
        )
        for message in sequence:
            deliver(receiver, parent.unit_id, message)
        check(f"twin.{suffix}.node_exists", key in receiver.canonical_searches)

    return {
        "nodes": {
            suffix: node_snapshot(receiver, wired[suffix][0])
            for suffix in ("a", "b")
        },
        "lifecycles": {
            suffix: lifecycle_snapshot(organ, wired[suffix][1])
            for suffix in ("a", "b")
        },
        "wire_messages": outbox_snapshot(receiver),
        "counters": nonzero_counters(),
    }


def parity_twin(*, negative: bool) -> dict[str, Any]:
    left = run_twin({"a": "normal", "b": "reversed"})
    right_orders = ({"a": "normal", "b": "normal"} if negative else
                    {"a": "reversed", "b": "normal"})
    right = run_twin(right_orders)
    # The receiver-arrival state deliberately records history: a normal-order
    # edge remains None while a reordered one reaches "applied". Compare every
    # other lifecycle fact per edge, and compare that history as a multiset
    # across the swapped pair. Erasing it would turn the new evidence into the
    # same emission/delivery conflation PA-3 was built to prevent.
    left_semantic = {
        edge: {name: value for name, value in lifecycle.items()
               if name != "prearrival_control_state"}
        for edge, lifecycle in left["lifecycles"].items()
    }
    right_semantic = {
        edge: {name: value for name, value in lifecycle.items()
               if name != "prearrival_control_state"}
        for edge, lifecycle in right["lifecycles"].items()
    }
    left_arrival_states = sorted(
        lifecycle["prearrival_control_state"] or "none"
        for lifecycle in left["lifecycles"].values()
    )
    right_arrival_states = sorted(
        lifecycle["prearrival_control_state"] or "none"
        for lifecycle in right["lifecycles"].values()
    )
    parity = {
        "nodes": left["nodes"] == right["nodes"],
        "lifecycles": (
            left_semantic == right_semantic
            and left_arrival_states == right_arrival_states
        ),
        "wire_messages": left["wire_messages"] == right["wire_messages"],
        "counters": left["counters"] == right["counters"],
    }
    for dimension, same in parity.items():
        check(f"twin.{dimension}_parity", same)
    return {
        "parity": parity,
        "arrival_state_multisets": {
            "left": left_arrival_states,
            "right": right_arrival_states,
        },
        "left": left,
        "right": right,
    }


def adversarial_flood() -> dict[str, Any]:
    organ, parent, receiver, attacker = rig(attacker=True)
    assert attacker is not None
    key, edge, search, control = wire(parent, receiver, "adversarial")
    reset()

    deliver(receiver, attacker.unit_id, control)
    forged_state = organ.search_edge_lifecycle[edge].get(
        "prearrival_control_state",
    )
    check("adversarial.forged_did_not_hold", forged_state is None)
    check("adversarial.forged_counted_once",
          C["UNAUTHENTICATED_TERMINAL_CONTROLS"] == 1)

    deliver(receiver, parent.unit_id, control)
    for _ in range(32):
        deliver(receiver, parent.unit_id, control)
    for index in range(32):
        deliver(
            receiver,
            parent.unit_id,
            dataclasses.replace(control, reason=f"conflict/{index}"),
        )
    before_adoption = lifecycle_snapshot(organ, edge)
    check("adversarial.one_control_retained",
          before_adoption["controls_retained"] == 1)
    check("adversarial.one_conflict_retained",
          before_adoption["control_conflicts_retained"] == 1)
    check("adversarial.global_conflict_bounded",
          len([item for item in organ.search_edge_terminal_conflicts
               if item[0] == edge]) == 1)
    check("adversarial.replays_counted",
          C["PREARRIVAL_CONTROL_REPLAYS"] == 32)
    check("adversarial.conflicts_counted",
          C["PREARRIVAL_CONTROL_CONFLICTS"] == 32)

    deliver(receiver, parent.unit_id, search)
    after_adoption = lifecycle_snapshot(organ, edge)
    node = node_snapshot(receiver, key)
    check("adversarial.legitimate_applied",
          after_adoption["prearrival_control_state"] == "applied")
    check("adversarial.closed_exactly_once",
          C["PARENT_CONTROLS_APPLIED"] == 1
          and C["PREARRIVAL_CONTROLS_APPLIED"] == 1)
    check("adversarial.no_duplicate_application",
          C["DUPLICATE_CONTROL_APPLICATIONS"] == 0)
    check("adversarial.no_unauthorized_effect",
          C["UNAUTHORIZED_EXTERNAL_EFFECTS"] == 0)
    return {
        "forged_receiver_state": forged_state,
        "before_adoption": before_adoption,
        "after_adoption": after_adoption,
        "node": node,
        "retained_global_conflicts": len([
            item for item in organ.search_edge_terminal_conflicts
            if item[0] == edge
        ]),
        "counters": nonzero_counters(),
    }


def cross_edge_isolation() -> dict[str, Any]:
    organ, parent, receiver, _ = rig()
    key_a, edge_a, search_a, control_a = wire(parent, receiver, "isolation-a")
    key_b, edge_b, search_b, _control_b = wire(
        parent, receiver, "isolation-b",
    )
    reset()

    deliver(receiver, parent.unit_id, control_a)
    deliver(receiver, parent.unit_id, search_b)
    b_before = {
        "node": node_snapshot(receiver, key_b),
        "lifecycle": lifecycle_snapshot(organ, edge_b),
    }
    check("isolation.emission_is_not_delivery",
          b_before["lifecycle"]["prearrival_control_state"] is None)
    check("isolation.other_edge_not_applied",
          not b_before["node"]["wave_cancelled"])

    deliver(receiver, parent.unit_id, search_a)
    a_after = {
        "node": node_snapshot(receiver, key_a),
        "lifecycle": lifecycle_snapshot(organ, edge_a),
    }
    b_after = {
        "node": node_snapshot(receiver, key_b),
        "lifecycle": lifecycle_snapshot(organ, edge_b),
    }
    check("isolation.delivered_edge_applied",
          a_after["lifecycle"]["prearrival_control_state"] == "applied")
    check("isolation.undelivered_edge_still_open",
          b_after["lifecycle"]["prearrival_control_state"] is None
          and not b_after["node"]["wave_cancelled"])
    check("isolation.no_cross_edge_read",
          C["PREARRIVAL_CONTROLS_APPLIED"] == 1)
    return {
        "edge_a_after": a_after,
        "edge_b_before": b_before,
        "edge_b_after": b_after,
        "counters": nonzero_counters(),
    }


def measure(*, negative: bool = False) -> dict[str, Any]:
    CHECKS.clear()
    FAILURES.clear()
    twin = parity_twin(negative=negative)
    adversarial = adversarial_flood()
    isolation = cross_edge_isolation()
    return {
        "assertions_run": len(CHECKS),
        "assertions_failed": list(FAILURES),
        "twin": twin,
        "adversarial_flood": adversarial,
        "cross_edge_isolation": isolation,
        "verdict": "PASS" if not FAILURES else "FAIL",
    }


def envelope(measurement: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": "phase3g-pa5-prearrival-adversarial-twin",
        "runtime_commit": RUNTIME_COMMIT,
        "marker_commit": MARKER_COMMIT,
        "instrument_sha256": sha256(pathlib.Path(__file__).resolve()),
        "runtime_sha256": sha256(ROOT / "substrate" / "v5.py"),
        "frozen_test_sha256_with_markers": FROZEN_TEST_SHA256,
        "active_test_sha256": sha256(
            ROOT / "tests" / "unit" / "test_substrate_v5_prearrival_controls.py"
        ),
        "measurement": measurement,
        "evidence_scope": (
            "in-memory authenticated transport reordering, replay/conflict "
            "bounds, edge isolation, lifecycle, credit, and wire parity"
        ),
        "not_claimed": [
            "durable crash recovery",
            "Gate F",
            "Gate G",
            "R8",
            "deployment",
            "external settlement effect",
        ],
    }


def verify_results(actual: dict[str, Any], path: pathlib.Path) -> bool:
    expected = json.loads(path.read_text())
    comparable = (
        "instrument_sha256",
        "runtime_sha256",
        "frozen_test_sha256_with_markers",
        "active_test_sha256",
        "measurement",
    )
    matches = all(expected.get(name) == actual.get(name) for name in comparable)
    check("results.committed_measurement_matches", matches)
    return matches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    parser.add_argument(
        "--verify-results", nargs="?", const=str(RESULTS), default=None,
    )
    args = parser.parse_args()

    measured = measure(negative=args.negative_control)
    actual = envelope(measured)
    if args.negative_control:
        detected = "twin.counters_parity" in measured["assertions_failed"]
        actual["negative_control_detected"] = detected
        print(json.dumps(actual, indent=2, sort_keys=True))
        return 0 if detected else 1

    if args.verify_results:
        if not verify_results(actual, pathlib.Path(args.verify_results)):
            actual["measurement"]["verdict"] = "FAIL"
        else:
            actual["committed_results_verified"] = True
    print(json.dumps(actual, indent=2, sort_keys=True))
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
