"""The institutional knowledge graph: every node names where it came from.

Doctrine (KNOWLEDGE GRAPH, FBO §4.15): one graph connects repository, commit,
file, contract, capability, organ, evidence, decision and outcome, so that any
question about the institution can be answered by traversal rather than by
someone's recollection.

The rule that makes it trustworthy is narrow and absolute:

    A node with no provenance is refused.

Provenance is not a label. It is the source kind and the exact locator the node
was derived from — a manifest path, a schema file, an arsenal entry. Nothing
enters this graph because it seemed true.

Consequences, stated rather than discovered later:

- The graph is a **read-only projection**. Building it mutates nothing and it
  exposes no writer for callers. Rebuild it to see change.
- Its output is **not a typed institutional contract**, so it may not cross an
  organ boundary. That is a named gap in the blueprint, not an oversight here.
- The Evidence -> Claim -> Outcome -> Revenue tail of §4.15 has **no populated
  sources**: verified external outcome count is zero. Those node kinds exist in
  the vocabulary and are deliberately empty, which is a truthful statement about
  the institution rather than a missing feature of the graph.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum

from discovery.service import CapabilityDiscoveryService, DiscoveryError
from foundry.arsenal import ARSENAL
from linker.manifest import ORGANS_DIR

KERNEL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class GraphError(ValueError):
    """A node or edge could not be admitted. Fails closed."""


class NodeKind(str, Enum):
    """The §4.15 chain. Kinds with no populated source stay empty on purpose."""

    REPOSITORY = "repository"
    COMMIT = "commit"
    FILE = "file"
    CONTRACT = "contract"
    CAPABILITY = "capability"
    ORGAN = "organ"
    TECHNOLOGY = "technology"
    LEGAL_PRINCIPAL = "legal_principal"
    # Populated only once the institution produces them:
    EVIDENCE = "evidence"
    DECISION = "decision"
    OUTCOME = "outcome"
    REVENUE = "revenue"


UNPOPULATED_KINDS = frozenset({
    NodeKind.EVIDENCE, NodeKind.DECISION, NodeKind.OUTCOME, NodeKind.REVENUE,
})


@dataclass(frozen=True)
class Provenance:
    """Where a node came from. Both fields are required and both are checked."""

    source_kind: str      # "organ_manifest" | "contract_schema" | "arsenal" | ...
    locator: str          # the exact file or entry it was derived from

    def __post_init__(self) -> None:
        if not self.source_kind or not self.source_kind.strip():
            raise GraphError("provenance requires a source_kind")
        if not self.locator or not self.locator.strip():
            raise GraphError("provenance requires a locator")


@dataclass(frozen=True)
class Node:
    kind: NodeKind
    node_id: str
    label: str
    provenance: Provenance
    attributes: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, NodeKind):
            raise GraphError(f"unknown node kind {self.kind!r}")
        if not self.node_id or not self.node_id.strip():
            raise GraphError("a node requires a node_id")
        if not isinstance(self.provenance, Provenance):
            raise GraphError(
                f"node {self.node_id!r} has no provenance; a node with no "
                "provenance is refused"
            )

    @property
    def key(self) -> str:
        return f"{self.kind.value}:{self.node_id}"


@dataclass(frozen=True)
class Edge:
    source: str          # node key
    relation: str
    target: str          # node key
    provenance: Provenance

    def __post_init__(self) -> None:
        if not self.relation or not self.relation.strip():
            raise GraphError("an edge requires a relation")
        if not isinstance(self.provenance, Provenance):
            raise GraphError(
                f"edge {self.source} -> {self.target} has no provenance; refused"
            )


class InstitutionalKnowledgeGraph:
    """Nodes, edges, and traversal. No writer is exposed to callers after build."""

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._out: dict[str, list[Edge]] = {}
        self._in: dict[str, list[Edge]] = {}
        self._sealed = False

    # -- construction (used by `build`; sealed afterwards) -----------------
    def add_node(self, node: Node) -> Node:
        if self._sealed:
            raise GraphError("the graph is sealed; rebuild it to reflect change")
        existing = self._nodes.get(node.key)
        if existing is not None and existing != node:
            raise GraphError(
                f"conflicting definitions for {node.key}: "
                f"{existing.provenance.locator} vs {node.provenance.locator}"
            )
        self._nodes[node.key] = node
        self._out.setdefault(node.key, [])
        self._in.setdefault(node.key, [])
        return node

    def add_edge(self, edge: Edge) -> Edge:
        if self._sealed:
            raise GraphError("the graph is sealed; rebuild it to reflect change")
        for end in (edge.source, edge.target):
            if end not in self._nodes:
                raise GraphError(
                    f"edge references unknown node {end!r}; the graph never "
                    "invents an endpoint"
                )
        if edge not in self._out[edge.source]:
            self._out[edge.source].append(edge)
            self._in[edge.target].append(edge)
        return edge

    def seal(self) -> InstitutionalKnowledgeGraph:
        self._sealed = True
        return self

    # -- reads -------------------------------------------------------------
    @property
    def sealed(self) -> bool:
        return self._sealed

    def __len__(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return sum(len(v) for v in self._out.values())

    def node(self, key: str) -> Node:
        try:
            return self._nodes[key]
        except KeyError as exc:
            raise GraphError(f"unknown node {key!r}") from exc

    def nodes(self, kind: NodeKind | None = None) -> tuple[Node, ...]:
        items = sorted(self._nodes.values(), key=lambda n: n.key)
        if kind is None:
            return tuple(items)
        return tuple(n for n in items if n.kind is kind)

    def out_edges(self, key: str) -> tuple[Edge, ...]:
        return tuple(self._out.get(key, ()))

    def in_edges(self, key: str) -> tuple[Edge, ...]:
        return tuple(self._in.get(key, ()))

    def neighbours(self, key: str, relation: str | None = None) -> tuple[Node, ...]:
        edges = self.out_edges(key)
        if relation is not None:
            edges = tuple(e for e in edges if e.relation == relation)
        return tuple(self._nodes[e.target] for e in edges)

    def path_exists(self, source: str, target: str, max_depth: int = 12) -> bool:
        """Breadth-first reachability. Bounded so a cycle cannot hang a caller."""
        if source not in self._nodes or target not in self._nodes:
            return False
        seen = {source}
        frontier = [source]
        for _ in range(max_depth):
            nxt: list[str] = []
            for key in frontier:
                for edge in self._out.get(key, ()):
                    if edge.target == target:
                        return True
                    if edge.target not in seen:
                        seen.add(edge.target)
                        nxt.append(edge.target)
            if not nxt:
                return False
            frontier = nxt
        return False

    def unpopulated(self) -> tuple[str, ...]:
        """Node kinds in the §4.15 vocabulary with no instances. Honest emptiness."""
        return tuple(sorted(
            k.value for k in NodeKind if not self.nodes(k)
        ))

    def summary(self) -> dict:
        counts = {k.value: len(self.nodes(k)) for k in NodeKind}
        return {
            "nodes": len(self),
            "edges": self.edge_count,
            "by_kind": counts,
            "unpopulated_kinds": list(self.unpopulated()),
            "sealed": self._sealed,
        }


# --------------------------------------------------------------------------
# Build: real sources only
# --------------------------------------------------------------------------

def _contracts_provenance(name: str) -> Provenance:
    return Provenance("contract_schema", f"contracts/{name}.schema.json")


def build(root: str = KERNEL_ROOT,
          organs_dir: str | None = None) -> InstitutionalKnowledgeGraph:
    """Project the institution into a graph from manifests, contracts and the arsenal.

    Every node carries the file it was derived from. Nothing is added because it
    would make the graph look complete.
    """
    organs_dir = organs_dir or os.path.join(root, "organs")
    graph = InstitutionalKnowledgeGraph()

    try:
        directory = CapabilityDiscoveryService(organs_dir=organs_dir)
    except DiscoveryError as exc:
        raise GraphError(f"cannot project a graph over an invalid directory: {exc}") from exc

    # -- contracts ---------------------------------------------------------
    contracts_dir = os.path.join(root, "contracts")
    contract_names: set[str] = set()
    if os.path.isdir(contracts_dir):
        for fname in sorted(os.listdir(contracts_dir)):
            if not fname.endswith(".schema.json"):
                continue
            name = fname[: -len(".schema.json")]
            contract_names.add(name)
            with open(os.path.join(contracts_dir, fname), encoding="utf-8") as fh:
                try:
                    schema = json.load(fh)
                except json.JSONDecodeError as exc:
                    raise GraphError(f"contract {name} is unreadable: {exc}") from exc
            graph.add_node(Node(
                kind=NodeKind.CONTRACT, node_id=name,
                label=str(schema.get("title", name)),
                provenance=_contracts_provenance(name),
                attributes={"schema_id": schema.get("$id", "")},
            ))

    # -- organs and their capabilities -------------------------------------
    for organ in directory.organs:
        manifest_locator = f"organs/{organ.name}.manifest.yaml"
        organ_prov = Provenance("organ_manifest", manifest_locator)
        organ_node = graph.add_node(Node(
            kind=NodeKind.ORGAN, node_id=organ.organ_id, label=organ.name,
            provenance=organ_prov,
            attributes={
                "status": organ.status,
                "role": organ.role,
                "max_consequence_class": organ.max_consequence_class,
                "may_self_promote": organ.may_self_promote,
                "requires_kernel_gate": organ.requires_kernel_gate,
            },
        ))

        if organ.repository:
            repo_node = graph.add_node(Node(
                kind=NodeKind.REPOSITORY, node_id=organ.repository,
                label=organ.repository, provenance=organ_prov,
            ))
            graph.add_edge(Edge(repo_node.key, "hosts", organ_node.key, organ_prov))

        for cap in organ.capabilities:
            cap_node = graph.add_node(Node(
                kind=NodeKind.CAPABILITY, node_id=cap.capability_id,
                label=cap.description or cap.capability_id,
                provenance=organ_prov,
                attributes={"lifecycle": cap.lifecycle,
                            "implementation_path": cap.implementation_path},
            ))
            graph.add_edge(Edge(organ_node.key, "offers", cap_node.key, organ_prov))

            if cap.implementation_path:
                file_node = graph.add_node(Node(
                    kind=NodeKind.FILE, node_id=cap.implementation_path,
                    label=cap.implementation_path, provenance=organ_prov,
                ))
                graph.add_edge(Edge(cap_node.key, "implemented_by",
                                    file_node.key, organ_prov))

            for contract in cap.produces:
                key = f"{NodeKind.CONTRACT.value}:{contract}"
                if key in {n.key for n in graph.nodes(NodeKind.CONTRACT)}:
                    graph.add_edge(Edge(cap_node.key, "produces", key, organ_prov))
            for contract in cap.consumes:
                key = f"{NodeKind.CONTRACT.value}:{contract}"
                if key in {n.key for n in graph.nodes(NodeKind.CONTRACT)}:
                    graph.add_edge(Edge(key, "consumed_by", cap_node.key, organ_prov))

    # -- technologies ------------------------------------------------------
    # Every node first, then every edge. Two arsenal entries (#34 -> #44 and
    # #37 -> #38) depend on a higher id, so a single ordered pass would silently
    # drop those edges — and a graph that quietly loses an edge is worse than one
    # that refuses to build.
    arsenal_prov = Provenance("arsenal", "foundry/arsenal.py")
    for spec in sorted(ARSENAL.values(), key=lambda s: s.id):
        graph.add_node(Node(
            kind=NodeKind.TECHNOLOGY, node_id=str(spec.id), label=spec.name,
            provenance=arsenal_prov,
            attributes={"category": spec.category, "status": spec.status,
                        "consequence_class": spec.consequence_class},
        ))
    for spec in sorted(ARSENAL.values(), key=lambda s: s.id):
        source = f"{NodeKind.TECHNOLOGY.value}:{spec.id}"
        for dep in spec.dependencies:
            graph.add_edge(Edge(source, "depends_on",
                                f"{NodeKind.TECHNOLOGY.value}:{dep}", arsenal_prov))

    return graph.seal()
