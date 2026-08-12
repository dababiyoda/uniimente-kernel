"""The seams must be satisfied by real classes, and must omit what they omit.

Two failure modes matter here, and `isinstance` against a runtime Protocol
catches neither on its own:

1. A seam drifts from the implementation and Part 2 builds to a shape the kernel
   no longer has. Caught by checking every Protocol member is actually present
   with a compatible signature.
2. A seam quietly grows an execution method, and a component typed against
   `Selector` gains a way to invoke a provider. Caught by asserting the absence
   is still there.
"""
from __future__ import annotations

import inspect

import pytest

from discovery.service import (
    CapabilityAdvertisement,
    CapabilityDiscoveryService,
    DiscoveryQuery,
)
from knowledge.graph import InstitutionalKnowledgeGraph, Node, build
from routing.decision_router import (
    Candidate,
    DecisionRouter,
    RoutingCriteria,
    RoutingDecision,
)
from seams import (
    PART_2_BINDINGS,
    CapabilityAdvertisementLike,
    CapabilityDirectory,
    ProvenanceGraph,
    ProvenanceNodeLike,
    RoutingDecisionLike,
    Selector,
)

# Every method the seam declares must exist on the implementation with a
# compatible parameter list — presence alone is what isinstance checks, and it
# is not enough.
PAIRS = [
    (CapabilityDirectory, CapabilityDiscoveryService),
    (Selector, DecisionRouter),
    (ProvenanceGraph, InstitutionalKnowledgeGraph),
    (CapabilityAdvertisementLike, CapabilityAdvertisement),
    (RoutingDecisionLike, RoutingDecision),
    (ProvenanceNodeLike, Node),
]


def _protocol_methods(protocol) -> list[str]:
    return sorted(
        name for name in getattr(protocol, "__protocol_attrs__", ())
        if callable(getattr(protocol, name, None))
    )


@pytest.mark.parametrize("protocol,implementation",
                         PAIRS, ids=[p.__name__ for p, _ in PAIRS])
def test_every_seam_is_satisfied_by_a_real_kernel_class(protocol, implementation):
    for name in getattr(protocol, "__protocol_attrs__", ()):
        assert hasattr(implementation, name), (
            f"{implementation.__name__} is missing {name!r} required by "
            f"{protocol.__name__}; the seam has drifted from the implementation"
        )


@pytest.mark.parametrize("protocol,implementation",
                         PAIRS, ids=[p.__name__ for p, _ in PAIRS])
def test_seam_method_signatures_are_compatible(protocol, implementation):
    """Presence is not enough — a renamed parameter breaks a caller silently."""
    for name in _protocol_methods(protocol):
        declared = getattr(protocol, name, None)
        actual = getattr(implementation, name, None)
        if not (inspect.isfunction(declared) and inspect.isfunction(actual)):
            continue        # properties and attributes are covered by the test above
        want = [p for p in inspect.signature(declared).parameters if p != "self"]
        got = list(inspect.signature(actual).parameters)
        got = [p for p in got if p != "self"]
        missing = [p for p in want if p not in got]
        assert not missing, (
            f"{implementation.__name__}.{name} is missing parameter(s) {missing} "
            f"declared by {protocol.__name__}.{name}"
        )


def test_live_instances_satisfy_the_runtime_protocols():
    directory = CapabilityDiscoveryService()
    assert isinstance(directory, CapabilityDirectory)
    assert isinstance(directory.capabilities[0], CapabilityAdvertisementLike)

    router = DecisionRouter()
    assert isinstance(router, Selector)
    decision = router.route(RoutingCriteria(contract="evidence"),
                            [Candidate("a", "organ", "evidence",
                                       evidence_maturity="PROVEN")])
    assert isinstance(decision, RoutingDecisionLike)

    graph = build()
    assert isinstance(graph, ProvenanceGraph)
    assert isinstance(graph.nodes()[0], ProvenanceNodeLike)


def test_the_selector_seam_offers_no_way_to_invoke_anything():
    """The absence is the contract. BLK-1 turns on exactly this.

    A Part 2 component typed against `Selector` must not be able to reach a
    provider through the seam, however the underlying implementation is written.
    """
    forbidden = ("resolve", "execute", "invoke", "run", "call", "apply",
                 "provider", "instantiate")
    attrs = set(getattr(Selector, "__protocol_attrs__", ()))
    assert not (attrs & set(forbidden)), (
        f"the Selector seam exposes execution surface: {sorted(attrs & set(forbidden))}"
    )
    # And the canonical implementation must not offer it either.
    for name in forbidden:
        assert not hasattr(DecisionRouter, name), (
            f"DecisionRouter grew a {name!r} method; the decision-only invariant is gone"
        )


def test_the_directory_seam_offers_no_way_to_grant_anything():
    forbidden = ("grant", "authorize", "approve", "issue", "mint", "activate")
    attrs = set(getattr(CapabilityDirectory, "__protocol_attrs__", ()))
    leaked = [a for a in attrs if any(f in a.lower() for f in forbidden)]
    assert leaked == [], f"the directory seam exposes authority surface: {leaked}"


def test_the_graph_seam_exposes_no_writer():
    forbidden = ("add_node", "add_edge", "seal", "delete", "update")
    attrs = set(getattr(ProvenanceGraph, "__protocol_attrs__", ()))
    assert not (attrs & set(forbidden)), (
        "the graph seam exposes mutation; a consumer must rebuild to see change"
    )


def test_every_part_2_component_names_a_seam_that_exists():
    for component, seam_name in PART_2_BINDINGS.items():
        assert seam_name in {p.__name__ for p, _ in PAIRS}, (
            f"Part 2 component {component!r} binds to {seam_name!r}, which is not "
            "a seam with a verified implementation"
        )


def test_the_directory_seam_reports_the_identity_split():
    """A loader must be able to tell discovery from identity (BLK-5)."""
    rec = CapabilityDiscoveryService().identity_reconciliation()
    for key in ("identity_registered", "manifests_published",
                "registered_without_manifest",
                "manifested_without_identity_registration"):
        assert key in rec
    assert isinstance(DiscoveryQuery(), DiscoveryQuery)
