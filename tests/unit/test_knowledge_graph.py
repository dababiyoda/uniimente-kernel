"""A node with no provenance is refused. That is the graph's only real promise."""
from __future__ import annotations

import pytest

from closure.nervous_system_registry import package_imports
from knowledge.graph import (
    Edge,
    GraphError,
    InstitutionalKnowledgeGraph,
    Node,
    NodeKind,
    Provenance,
    build,
)


@pytest.fixture(scope="module")
def graph() -> InstitutionalKnowledgeGraph:
    return build()


# ------------------------------------------------------------------ the rule
def test_node_without_provenance_is_refused():
    with pytest.raises(GraphError, match="provenance"):
        Node(NodeKind.FILE, "orphan.py", "orphan", None)  # type: ignore[arg-type]


def test_provenance_requires_both_a_source_kind_and_a_locator():
    with pytest.raises(GraphError):
        Provenance("", "somewhere")
    with pytest.raises(GraphError):
        Provenance("organ_manifest", "  ")


def test_every_node_in_the_built_graph_names_where_it_came_from(graph):
    for node in graph.nodes():
        assert node.provenance.source_kind
        assert node.provenance.locator
    sources = {n.provenance.source_kind for n in graph.nodes()}
    assert sources <= {"organ_manifest", "contract_schema", "arsenal"}


def test_an_edge_to_an_unknown_node_is_refused():
    g = InstitutionalKnowledgeGraph()
    prov = Provenance("test", "test")
    a = g.add_node(Node(NodeKind.FILE, "a.py", "a", prov))
    with pytest.raises(GraphError, match="unknown node"):
        g.add_edge(Edge(a.key, "points_to", "file:ghost.py", prov))


def test_an_edge_without_provenance_is_refused():
    prov = Provenance("test", "test")
    with pytest.raises(GraphError):
        Edge("file:a", "rel", "file:b", None)  # type: ignore[arg-type]
    assert Edge("file:a", "rel", "file:b", prov).relation == "rel"


def test_conflicting_definitions_of_one_node_are_refused():
    g = InstitutionalKnowledgeGraph()
    g.add_node(Node(NodeKind.ORGAN, "x", "x", Provenance("organ_manifest", "a.yaml")))
    with pytest.raises(GraphError, match="conflicting"):
        g.add_node(Node(NodeKind.ORGAN, "x", "x", Provenance("organ_manifest", "b.yaml")))


# -------------------------------------------------------------- honest gaps
def test_the_unpopulated_tail_of_the_chain_is_reported_not_faked(graph):
    """FBO §4.15 names Evidence -> Decision -> Outcome -> Revenue. None exist."""
    unpopulated = set(graph.unpopulated())
    assert {"evidence", "decision", "outcome", "revenue"} <= unpopulated, (
        "node kinds with no real source are being populated with placeholders"
    )


def test_the_graph_is_sealed_after_build_and_refuses_mutation(graph):
    assert graph.sealed
    with pytest.raises(GraphError, match="sealed"):
        graph.add_node(Node(NodeKind.FILE, "late.py", "late",
                            Provenance("test", "test")))


def test_the_graph_authorizes_nothing():
    imports = package_imports("knowledge")
    assert not any(i.startswith("policy") for i in imports), (
        f"the knowledge graph imports authority machinery: {sorted(imports)}"
    )
    for name in dir(InstitutionalKnowledgeGraph):
        assert "grant" not in name.lower()
        assert "authorize" not in name.lower()


# -------------------------------------------------------------- real content
def test_the_graph_spans_organs_capabilities_contracts_and_technologies(graph):
    assert len(graph.nodes(NodeKind.ORGAN)) == 5
    assert len(graph.nodes(NodeKind.TECHNOLOGY)) == 55
    assert graph.nodes(NodeKind.CONTRACT)
    assert graph.nodes(NodeKind.CAPABILITY)
    assert graph.edge_count > len(graph.nodes(NodeKind.TECHNOLOGY))


def test_an_organ_reaches_a_contract_through_the_capability_that_produces_it(graph):
    kernel = "organ:spiffe://uniimente.internal/organ/constitutional-controller"
    # kernel --offers--> kernel.consequence_gate --produces--> outcome
    assert graph.path_exists(kernel, "contract:outcome"), (
        "the kernel does not reach the outcome contract by traversal"
    )
    # Consumption points the other way: the contract feeds the capability.
    gate = "capability:kernel.consequence_gate"
    consumed = {e.source for e in graph.in_edges(gate) if e.relation == "consumed_by"}
    assert "contract:capability-grant" in consumed


def test_forward_dependency_edges_are_not_silently_dropped(graph):
    """#34 depends on #44 and #37 on #38 — both point forward in id order."""
    for source, target in ((34, 44), (37, 38)):
        targets = {n.node_id for n in
                   graph.neighbours(f"technology:{source}", relation="depends_on")}
        assert str(target) in targets, (
            f"technology #{source} lost its forward edge to #{target}"
        )


def test_technology_dependency_edges_match_the_arsenal(graph):
    from foundry.arsenal import ARSENAL
    for spec in ARSENAL.values():
        key = f"technology:{spec.id}"
        targets = {n.node_id for n in graph.neighbours(key, relation="depends_on")}
        assert targets == {str(d) for d in spec.dependencies}, (
            f"technology #{spec.id} dependency edges disagree with the arsenal"
        )


def test_traversal_is_bounded_so_a_cycle_cannot_hang_a_caller():
    g = InstitutionalKnowledgeGraph()
    prov = Provenance("test", "test")
    a = g.add_node(Node(NodeKind.FILE, "a", "a", prov))
    b = g.add_node(Node(NodeKind.FILE, "b", "b", prov))
    c = g.add_node(Node(NodeKind.FILE, "c", "c", prov))
    g.add_edge(Edge(a.key, "next", b.key, prov))
    g.add_edge(Edge(b.key, "next", a.key, prov))
    assert g.path_exists(a.key, b.key)
    assert not g.path_exists(a.key, c.key, max_depth=3)
