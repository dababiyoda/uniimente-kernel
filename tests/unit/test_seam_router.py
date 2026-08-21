"""P3 — the seam must route, and must not quietly become a second grant path.

These tests fail the build if the router starts inventing routes, stops failing
closed, collapses Geometry B into per-contract event types, or acquires the
ability to authorise anything. They use synthetic organs so they measure the
mechanism rather than the DALEOBANKS/WMI checkouts; the real cross-repository
episode lives in ``tests/integration/test_p3_counterfactual.py``.
"""
from __future__ import annotations

import ast
import os

import pytest

from events.spine import EventSpine
from linker.linker import Edge
from provenance.ledger import EvidenceLedger
from runtime.seam.binding import BindingError, ConsumerBinding, OrganEntryPoint
from runtime.seam.router import (
    CONTRACT_DELIVERY_EVENT,
    BypassDetected,
    ContractRouter,
    RouteNotEstablished,
)
from runtime.seam.topology import DisabledEdgeResolution, EdgeResolutionUnavailable

SEAM_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "runtime", "seam",
)

PRODUCER = "spiffe://uniimente.internal/organ/alpha"
CONSUMER = "spiffe://uniimente.internal/organ/beta"
CONTRACT = "test-contract"


class _FakeTopology:
    """A topology that proves exactly the edges it is told to prove."""

    def __init__(self, edges):
        self.edges = list(edges)

    @property
    def provider_id(self) -> str:
        return "test.FakeTopology"

    def resolve_edges(self):
        return list(self.edges)


def _spine() -> EventSpine:
    return EventSpine(EvidenceLedger(constitution_hash="test"))


def _edge() -> Edge:
    return Edge(producer=PRODUCER, consumer=CONSUMER, contract=CONTRACT,
                schema_path="/contracts/test-contract.schema.json")


def _binding(module="runtime.seam._probe_consumer", attribute="Consumer",
             organ=CONSUMER, contract=CONTRACT, forbidden=()) -> ConsumerBinding:
    return ConsumerBinding(
        organ_id=organ, contract=contract,
        entry_point=OrganEntryPoint(
            organ_id=organ,
            repository_root=os.path.dirname(os.path.dirname(SEAM_DIR)),
            module=module, attribute=attribute, forbidden_fragments=forbidden,
        ),
        construct=True, method="receive",
        declared_by="test", reason="test",
    )


# --- structure AND semantics, never one alone -------------------------------

def test_route_needs_a_proven_edge(tmp_path):
    """A binding with no matching edge is refused, with a reason."""
    router = ContractRouter(_spine(), _FakeTopology([]), [_binding()])
    assert router.materialise() == []
    assert len(router.refused) == 1
    assert "no linker-proven edge" in router.refused[0][1]


def test_route_needs_a_resolvable_binding():
    """A proven edge alone routes nothing; the consumer must actually exist."""
    router = ContractRouter(
        _spine(), _FakeTopology([_edge()]),
        [_binding(module="runtime.seam._does_not_exist")],
    )
    assert router.materialise() == []
    assert "did not import" in router.refused[0][1]


def test_edge_and_binding_together_materialise_one_route():
    router = ContractRouter(_spine(), _FakeTopology([_edge()]), [_binding()])
    routes = router.materialise()
    assert len(routes) == 1
    assert routes[0].contract == CONTRACT
    assert routes[0].consumer == CONSUMER


# --- fail closed ------------------------------------------------------------

def test_unavailable_edge_resolution_establishes_no_route():
    router = ContractRouter(_spine(), DisabledEdgeResolution(), [_binding()])
    assert router.materialise() == []
    assert router.topology_error
    with pytest.raises(RouteNotEstablished):
        router.deliver(CONTRACT, {}, producer=PRODUCER,
                       actor="test", legal_principal="alfonso_lopez")


def test_delivery_before_materialise_is_refused():
    """An unexamined topology must not be deliverable against."""
    router = ContractRouter(_spine(), _FakeTopology([_edge()]), [_binding()])
    with pytest.raises(RouteNotEstablished, match="materialise"):
        router.deliver(CONTRACT, {}, producer=PRODUCER,
                       actor="test", legal_principal="alfonso_lopez")


def test_unavailable_is_an_exception_not_an_empty_list():
    """'The capability is gone' must not be reachable as 'nothing to route'."""
    assert issubclass(EdgeResolutionUnavailable, RuntimeError)
    with pytest.raises(EdgeResolutionUnavailable):
        DisabledEdgeResolution().resolve_edges()


# --- Geometry B -------------------------------------------------------------

def test_one_event_type_for_every_contract():
    """Contract names are data. They never become event-type namespaces."""
    spine = _spine()
    router = ContractRouter(spine, _FakeTopology([_edge()]), [_binding()])
    router.materialise()
    receipt = router.deliver(CONTRACT, {"n": 1}, producer=PRODUCER,
                             actor="test", legal_principal="alfonso_lopez")
    assert receipt.event_type == CONTRACT_DELIVERY_EVENT
    emitted = spine.replay(CONTRACT_DELIVERY_EVENT)
    assert len(emitted) == 1
    assert emitted[0].payload["contract"] == CONTRACT
    assert CONTRACT not in emitted[0].type


def test_handler_filters_on_payload_not_on_type():
    """With one event type, a handler must ignore contracts that are not its own."""
    spine = _spine()
    other = Edge(producer=PRODUCER, consumer=CONSUMER, contract="other-contract",
                 schema_path="/contracts/other.schema.json")
    router = ContractRouter(spine, _FakeTopology([_edge(), other]),
                            [_binding(), _binding(contract="other-contract")])
    router.materialise()
    receipt = router.deliver("other-contract", {"n": 2}, producer=PRODUCER,
                             actor="test", legal_principal="alfonso_lopez")
    assert receipt.contract == "other-contract"
    assert receipt.delivered


# --- non-vacuity and bypass detection ---------------------------------------

def test_delivery_records_which_files_actually_ran():
    router = ContractRouter(_spine(), _FakeTopology([_edge()]), [_binding()])
    router.materialise()
    receipt = router.deliver(CONTRACT, {"n": 3}, producer=PRODUCER,
                             actor="test", legal_principal="alfonso_lopez")
    assert receipt.witness_files, "the execution witness recorded nothing"
    assert receipt.executed_in(SEAM_DIR), "the consumer's own file never ran"


def test_bypass_is_detected_by_execution():
    """The detector must fire on what ran, not on what was importable."""
    router = ContractRouter(
        _spine(), _FakeTopology([_edge()]),
        [_binding(forbidden=("_probe_consumer.py",))],
    )
    router.materialise()
    with pytest.raises(BypassDetected):
        router.deliver(CONTRACT, {"n": 4}, producer=PRODUCER,
                       actor="test", legal_principal="alfonso_lopez")


def test_importable_bypass_alone_does_not_block_a_route():
    """Regression: an earlier version refused any binding while a forbidden
    module sat in sys.modules. That made the bypass negative control poison
    every state after it, and would have made the seam unusable in any
    workspace where the other organ is checked out."""
    import runtime.seam._probe_consumer  # noqa: F401  (now certainly imported)

    router = ContractRouter(
        _spine(), _FakeTopology([_edge()]),
        [_binding(forbidden=("nothing_that_runs.py",))],
    )
    assert len(router.materialise()) == 1


def test_binding_refuses_a_module_from_another_repository():
    """Shadowing must be caught: organs share top-level package names."""
    ep = OrganEntryPoint(organ_id=CONSUMER, repository_root=SEAM_DIR,
                         module="json", attribute="loads")
    with pytest.raises(BindingError, match="outside the declared repository"):
        ep.resolve()


# --- the seam grants no authority -------------------------------------------

AUTHORITY_SURFACE = ("authority", "policy", "constitution", "aperture", "identity")


def _authority_imports(source: str, label: str) -> list[str]:
    """Import roots from ``source`` that touch the authority surface.

    Parsed rather than grepped: a substring search for 'policy' matches
    'policy_version' in an event field and would cry wolf, and a guard that
    cries wolf gets disabled.
    """
    found = []
    for node in ast.walk(ast.parse(source)):
        roots = []
        if isinstance(node, ast.Import):
            roots = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots = [node.module.split(".")[0]]
        found += [f"{label}: {r}" for r in roots if r in AUTHORITY_SURFACE]
    return found


def test_seam_never_imports_the_authority_surface():
    """Structural truth, runtime semantics and authority stay three layers."""
    offenders = []
    for name in sorted(os.listdir(SEAM_DIR)):
        if name.endswith(".py"):
            path = os.path.join(SEAM_DIR, name)
            offenders += _authority_imports(open(path, encoding="utf-8").read(), name)
    assert not offenders, f"the seam reached into the authority surface: {offenders}"


def test_the_authority_guard_can_actually_fire():
    """Negative control. Without it, a clean sheet could mean a dead parser."""
    assert _authority_imports("from authority.matrix import x", "synthetic")
    assert _authority_imports("import policy", "synthetic")
    # ...and does not fire on the field name that would defeat a grep.
    assert not _authority_imports(
        "policy_version = None\nfrom events.spine import Event", "synthetic"
    )


def test_receipts_can_never_report_a_grant():
    router = ContractRouter(_spine(), _FakeTopology([_edge()]), [_binding()])
    router.materialise()
    receipt = router.deliver(CONTRACT, {"n": 5}, producer=PRODUCER,
                             actor="test", legal_principal="alfonso_lopez")
    assert receipt.authority_granted is False
    assert receipt.describe()["authority_granted"] is False


def test_events_never_name_uniimente_as_legal_principal():
    router = ContractRouter(_spine(), _FakeTopology([_edge()]), [_binding()])
    router.materialise()
    with pytest.raises(Exception):
        router.deliver(CONTRACT, {}, producer=PRODUCER,
                       actor="test", legal_principal="UNIIMENTE")
