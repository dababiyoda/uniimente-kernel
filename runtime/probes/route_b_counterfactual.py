"""Four-state, consequence-inert Route B counterfactual.

This probe executes the real DALEOBANKS producer and the real
WealthMachineIntelligence consumer at the exact revisions pinned by the Kernel
organ manifests. It never uses ``WealthMachineClient`` on the decisive path.
The local mock is exercised only as a hostile bypass control and must be
rejected by callable provenance.

The probe moves no money, publishes nothing, opens no network connection, and
grants no authority. It proves only the P3 routing geometry. It is not a
developmental closure and must not increment VERIFIED_DEVELOPMENTAL_CLOSURES.
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
import os
from pathlib import Path
import socket
import subprocess
import sys
import types


DALEOBANKS_ID = "spiffe://uniimente.internal/organ/daleobanks"
WEALTHMACHINE_ID = "spiffe://uniimente.internal/organ/wealthmachine"
CONTRACT = "wire-opportunity-packet"
WMI_HANDLER_REF = (
    "src.services.opportunity_intake."
    "OpportunityIntakeService.evaluate_packet"
)


class NetworkDeniedSocket(socket.socket):
    def connect(self, *args, **kwargs):
        raise AssertionError("Route B probe attempted network access")

    def connect_ex(self, *args, **kwargs):
        raise AssertionError("Route B probe attempted network access")


class CaptureLedger:
    def __init__(self) -> None:
        self.records: list[tuple[str, dict]] = []

    def record(self, event: str, payload: dict | None = None) -> dict:
        entry = {"event": event, "payload": payload or {}}
        self.records.append((event, entry["payload"]))
        return entry


def _tripwire(name: str):
    def fail(*args, **kwargs):
        raise AssertionError(f"Route B producer touched unrelated service: {name}")
    return fail


def _install_daleobanks_import_boundaries() -> None:
    ledger_module = types.ModuleType("services.ledger")
    ledger_module.DecisionLedger = type("DecisionLedger", (), {})
    ledger_module.get_ledger = _tripwire("decision ledger")
    sys.modules["services.ledger"] = ledger_module

    logging_module = types.ModuleType("services.logging_utils")
    logging_module.get_logger = logging.getLogger
    sys.modules["services.logging_utils"] = logging_module

    firewall_module = types.ModuleType("services.prompt_firewall")
    firewall_module.get_firewall = _tripwire("prompt firewall")
    sys.modules["services.prompt_firewall"] = firewall_module

    bridge_module = types.ModuleType("services.bridge_security")
    bridge_module.BridgeSecurityError = type("BridgeSecurityError", (ValueError,), {})
    bridge_module.NonceCache = type("NonceCache", (), {})
    bridge_module.build_headers = _tripwire("bridge build_headers")
    bridge_module.signing_key = _tripwire("bridge signing_key")
    bridge_module.verify_headers = _tripwire("bridge verify_headers")
    sys.modules["services.bridge_security"] = bridge_module


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kernel", required=True, type=Path)
    parser.add_argument("--daleobanks", required=True, type=Path)
    parser.add_argument("--wealthmachine", required=True, type=Path)
    return parser.parse_args()


def _require_checkout(path: Path, marker: str) -> Path:
    resolved = path.resolve()
    if not (resolved / marker).is_file():
        raise SystemExit(f"required pinned checkout missing {marker}: {resolved}")
    return resolved


def _checkout_revision(path: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(f"source checkout has no verifiable git HEAD: {path}")
    return completed.stdout.strip()


def main() -> int:
    args = _arguments()
    kernel = _require_checkout(args.kernel, "linker/linker.py")
    daleobanks = _require_checkout(args.daleobanks, "services/idea_refinery.py")
    wealthmachine = _require_checkout(
        args.wealthmachine, "src/services/opportunity_intake.py"
    )

    for path in (wealthmachine, daleobanks, kernel):
        sys.path.insert(0, str(path))

    socket.socket = NetworkDeniedSocket
    _install_daleobanks_import_boundaries()

    from db.models import Idea
    from services.idea_refinery import IdeaRefinery
    from services.venture_protocol import packet_to_wire
    from services.wealthmachine_client import WealthMachineClient
    from src.services.opportunity_intake import OpportunityIntakeService

    from events.spine import EventSpine
    from linker.linker import InstitutionalLinker
    from linker.manifest import load_manifest
    from provenance.ledger import EvidenceLedger
    from runtime.contract_events import ContractEventRouter, ContractRouteError

    manifests = [
        load_manifest(kernel / "organs/daleobanks.manifest.yaml"),
        load_manifest(kernel / "organs/wealthmachine.manifest.yaml"),
    ]
    by_id = {manifest.organ_id: manifest for manifest in manifests}
    report = InstitutionalLinker(
        manifests, contracts_dir=str(kernel / "contracts")
    ).link()
    route_edges = [
        edge for edge in report.edges
        if (edge.producer, edge.contract, edge.consumer)
        == (DALEOBANKS_ID, CONTRACT, WEALTHMACHINE_ID)
    ]
    if len(route_edges) != 1:
        raise AssertionError(f"expected one exact Route B edge, observed {len(route_edges)}")

    idea = Idea(
        raw_text="Build a financial independence checklist for immigrants.",
        risk_flags=[],
    )
    packet = IdeaRefinery._opportunity_from(
        object(), idea, "Build a financial independence checklist for immigrants."
    )
    if packet is None:
        raise AssertionError("real producer returned no OpportunityPacket")
    wire = packet_to_wire(packet)

    producer_revision = by_id[DALEOBANKS_ID].raw["source"]["commit"]
    consumer_revision = by_id[WEALTHMACHINE_ID].raw["source"]["commit"]
    if _checkout_revision(daleobanks) != producer_revision:
        raise AssertionError(
            "DALEOBANKS checkout does not match its kernel manifest pin"
        )
    if _checkout_revision(wealthmachine) != consumer_revision:
        raise AssertionError(
            "WealthMachine checkout does not match its kernel manifest pin"
        )

    def ready_router(current_report):
        ledger = EvidenceLedger("sha256:track-a-route-b-consequence-inert")
        spine = EventSpine(ledger)
        service = OpportunityIntakeService()
        router = ContractEventRouter(spine, current_report)
        binding = router.bind(
            producer=DALEOBANKS_ID,
            contract=CONTRACT,
            consumer=WEALTHMACHINE_ID,
            handler=service.evaluate_packet,
            handler_ref=WMI_HANDLER_REF,
            producer_revision=producer_revision,
            consumer_revision=consumer_revision,
            consequence_class="INERT",
        )
        return ledger, router, binding

    scope_router = ContractEventRouter(
        EventSpine(EvidenceLedger("sha256:track-a-route-b-scope-guard")), report
    )
    try:
        scope_router.bind(
            producer=DALEOBANKS_ID,
            contract=CONTRACT,
            consumer=WEALTHMACHINE_ID,
            handler=OpportunityIntakeService().evaluate_packet,
            handler_ref=WMI_HANDLER_REF,
            producer_revision=producer_revision,
            consumer_revision=consumer_revision,
            consequence_class="EXTERNAL",
        )
    except ContractRouteError as exc:
        non_inert_error = str(exc)
    else:
        raise AssertionError("non-inert handler classification was accepted")

    # STATE A: healthy baseline. The linker proves the exact edge and the real
    # WMI consumer receives the real DALEOBANKS wire packet.
    ledger_a, router_a, binding_a = ready_router(report)
    result_a = router_a.deliver(
        producer=DALEOBANKS_ID,
        contract=CONTRACT,
        consumer=WEALTHMACHINE_ID,
        body=wire,
        actor="runtime:track-a-route-b",
        legal_principal="alfonso_lopez",
    )
    assert result_a.output["opportunity_packet_id"] == wire["id"]
    assert result_a.output["requires_human_approval"] is True
    assert ledger_a.verify_chain()[0] is True

    # STATE B: remove only the target edge. Registration must fail before the
    # consumer can run, so no assessment can be attributed to the route.
    damaged = copy.deepcopy(report)
    damaged.edges = [
        edge for edge in damaged.edges
        if (edge.producer, edge.contract, edge.consumer)
        != (DALEOBANKS_ID, CONTRACT, WEALTHMACHINE_ID)
    ]
    ledger_b = EvidenceLedger("sha256:track-a-route-b-disabled")
    router_b = ContractEventRouter(EventSpine(ledger_b), damaged)
    service_b = OpportunityIntakeService()
    try:
        router_b.bind(
            producer=DALEOBANKS_ID,
            contract=CONTRACT,
            consumer=WEALTHMACHINE_ID,
            handler=service_b.evaluate_packet,
            handler_ref=WMI_HANDLER_REF,
            producer_revision=producer_revision,
            consumer_revision=consumer_revision,
            consequence_class="INERT",
        )
    except ContractRouteError as exc:
        state_b_error = str(exc)
    else:
        raise AssertionError("disabled linker edge still materialized a route")
    assert len(ledger_b.records) == 1

    # STATE C: the real DALEOBANKS local mock can create a valid-looking
    # assessment. It is intentionally kept outside the decisive path, and the
    # router rejects it when it is mislabeled as the WMI implementation.
    os.environ["WEALTHMACHINE_MODE"] = "mock"
    mock_ledger = CaptureLedger()
    mock_client = WealthMachineClient(ledger=mock_ledger)
    mock_assessment = mock_client.evaluate(packet)
    assert mock_assessment.opportunity_packet_id == wire["id"]
    ledger_c = EvidenceLedger("sha256:track-a-route-b-bypass")
    router_c = ContractEventRouter(EventSpine(ledger_c), report)
    try:
        router_c.bind(
            producer=DALEOBANKS_ID,
            contract=CONTRACT,
            consumer=WEALTHMACHINE_ID,
            handler=mock_client.evaluate,
            handler_ref=WMI_HANDLER_REF,
            producer_revision=producer_revision,
            consumer_revision=consumer_revision,
            consequence_class="INERT",
        )
    except ContractRouteError as exc:
        state_c_error = str(exc)
    else:
        raise AssertionError("local mock bypass was accepted as the WMI consumer")
    assert len(ledger_c.records) == 1

    # STATE D: restore the exact edge. The real WMI path becomes available
    # again and the completion event is causally bound to the request event.
    ledger_d, router_d, binding_d = ready_router(report)
    result_d = router_d.deliver(
        producer=DALEOBANKS_ID,
        contract=CONTRACT,
        consumer=WEALTHMACHINE_ID,
        body=wire,
        actor="runtime:track-a-route-b",
        legal_principal="alfonso_lopez",
    )
    result_records = ledger_d.by_type("event")
    result_payloads = [record.payload for record in result_records]
    completed = [
        payload for payload in result_payloads
        if payload["type"] == "contract.delivery_completed"
    ]
    assert len(completed) == 1
    assert completed[0]["causal_parent"] == result_d.request_event_id
    assert result_d.output["opportunity_packet_id"] == wire["id"]
    assert result_d.output["requires_human_approval"] is True
    assert ledger_d.verify_chain()[0] is True

    print(json.dumps({
        "classification": "SANDBOX_EXECUTION_CONSEQUENCE_INERT",
        "closure_count_delta": 0,
        "external_effects": 0,
        "network": "DENIED",
        "source_revisions_verified": True,
        "scope_guards": {
            "non_inert_binding_refused": True,
            "refused": non_inert_error,
        },
        "route": binding_a.provenance(),
        "states": {
            "A_HEALTHY": {
                "assessment": True,
                "packet_id_matches": True,
                "requires_human_approval": True,
            },
            "B_EDGE_DISABLED": {
                "assessment": False,
                "refused": state_b_error,
            },
            "C_LOCAL_MOCK_BYPASS": {
                "lookalike_assessment_exists": True,
                "accepted_by_router": False,
                "refused": state_c_error,
            },
            "D_EDGE_RESTORED": {
                "assessment": True,
                "packet_id_matches": True,
                "requires_human_approval": True,
                "causal_receipt": True,
            },
        },
        "same_binding_after_restore": binding_a == binding_d,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
