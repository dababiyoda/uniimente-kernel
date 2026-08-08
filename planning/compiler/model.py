"""Canonical planning model: load, validate and digest the planning graph.

The graph in ``planning/graph/nodes/`` is the ONLY source of planning truth.
Every artifact under ``docs/planning/uniimente_v1/`` and
``artifacts/planning/uniimente_v1/`` is a projection of it. Nothing in this
module reaches the network, reads credentials, or touches kernel runtime state.

Anti-fabrication rule, enforced in :func:`validate_node` rather than promised:
a node carrying no ``evidence_refs`` must declare ``evidence_status:
unresolved``. Missing information stays visible as an explicit open field; it is
never silently promoted into an assertion.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any, Iterator

import yaml

#: Evidence tiers, strongest first. ``unresolved`` is the only status a node
#: without evidence may hold, and it is a real state rather than a failure: the
#: round is required to surface what it does not know.
EVIDENCE_STATUSES = (
    "verified_by_execution",
    "verified_by_inspection",
    "asserted",
    "unresolved",
)

#: Lifecycle roles from the Founder-Horizon Override §5. Preservation is the
#: default; activation is a separate, narrower decision.
LIFECYCLE_ROLES = (
    "CANONICAL",
    "CHAMPION",
    "SPECIALIST",
    "CHALLENGER",
    "FALLBACK",
    "EXPERIMENTAL",
    "ANCESTOR",
    "FAILED_BUT_INFORMATIVE",
    "COUNTERFACTUAL_TWIN",
    "QUARANTINED",
    "HISTORICAL",
    "SUPERSEDED_OPERATIONALLY",
    "COLD_STORAGE",
)

#: The classification the Override §29.4 requires before anything is proposed
#: for construction. "Absent" must be earned by inspection, not assumed.
PRESENCE_CLASSES = (
    "existing_and_connected",
    "existing_but_disconnected",
    "genuinely_absent",
)

#: Where a component sits in the three-region topology (Override §4).
REGIONS = ("LEFT", "CENTER", "BRIDGE", "RIGHT", "REALITY")


def repo_root() -> str:
    """Absolute path to the kernel checkout.

    Derived from this file's location, never from ``os.getcwd()``. Prompt §31
    requires instruments to run identically from the repository root and from an
    unrelated working directory, so no caller-relative path may leak in here.
    """
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def graph_dir() -> str:
    return os.path.join(repo_root(), "planning", "graph", "nodes")


class GraphError(ValueError):
    """Raised when the planning graph violates its own invariants."""


@dataclass(frozen=True)
class EvidenceRef:
    """A pointer to something that can be checked by a third party."""

    repo: str
    sha: str
    path: str | None = None
    symbol: str | None = None
    command: str | None = None
    note: str | None = None

    def to_dict(self) -> dict:
        out = {"repo": self.repo, "sha": self.sha}
        for key in ("path", "symbol", "command", "note"):
            value = getattr(self, key)
            if value:
                out[key] = value
        return out


@dataclass
class Node:
    """One planning fact, decision, mechanism, aspiration or open question."""

    id: str
    kind: str
    title: str
    evidence_status: str
    body: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[EvidenceRef] = field(default_factory=list)

    @property
    def has_evidence(self) -> bool:
        return bool(self.evidence_refs)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "evidence_status": self.evidence_status,
            "evidence_refs": [ref.to_dict() for ref in self.evidence_refs],
            **self.body,
        }


def validate_node(node: Node) -> list[str]:
    """Return every invariant this node breaks. Empty list means it is sound.

    Returning the full list rather than raising on the first problem is
    deliberate: a partially-built graph should report all of its gaps in one
    pass, so the round can see the true size of what it has not yet grounded.
    """
    problems: list[str] = []
    if not node.id:
        problems.append("node has no id")
    if not node.title:
        problems.append(f"{node.id}: no title")
    if node.evidence_status not in EVIDENCE_STATUSES:
        problems.append(
            f"{node.id}: evidence_status {node.evidence_status!r} "
            f"not one of {EVIDENCE_STATUSES}"
        )
    # The core anti-fabrication rule.
    if not node.has_evidence and node.evidence_status != "unresolved":
        problems.append(
            f"{node.id}: claims {node.evidence_status!r} with zero evidence_refs; "
            "a node with no evidence must be 'unresolved'"
        )
    for ref in node.evidence_refs:
        if not ref.repo or not ref.sha:
            problems.append(f"{node.id}: evidence ref missing repo or sha")
    role = node.body.get("lifecycle_role")
    if role is not None and role not in LIFECYCLE_ROLES:
        problems.append(f"{node.id}: lifecycle_role {role!r} not in {LIFECYCLE_ROLES}")
    presence = node.body.get("presence")
    if presence is not None and presence not in PRESENCE_CLASSES:
        problems.append(f"{node.id}: presence {presence!r} not in {PRESENCE_CLASSES}")
    region = node.body.get("region")
    if region is not None and region not in REGIONS:
        problems.append(f"{node.id}: region {region!r} not in {REGIONS}")
    return problems


def _parse_node(raw: dict, source: str) -> Node:
    missing = [k for k in ("id", "kind", "title", "evidence_status") if k not in raw]
    if missing:
        raise GraphError(f"{source}: node missing required keys {missing}: {raw!r}")
    body = {
        k: v
        for k, v in raw.items()
        if k not in ("id", "kind", "title", "evidence_status", "evidence_refs")
    }
    refs = [EvidenceRef(**ref) for ref in raw.get("evidence_refs", [])]
    return Node(
        id=raw["id"],
        kind=raw["kind"],
        title=raw["title"],
        evidence_status=raw["evidence_status"],
        body=body,
        evidence_refs=refs,
    )


class PlanningGraph:
    """The loaded planning model."""

    def __init__(self, nodes: list[Node]):
        self.nodes = nodes
        self._by_id: dict[str, Node] = {}
        for node in nodes:
            if node.id in self._by_id:
                raise GraphError(f"duplicate node id {node.id!r}")
            self._by_id[node.id] = node

    def __len__(self) -> int:
        return len(self.nodes)

    def __iter__(self) -> Iterator[Node]:
        return iter(self.nodes)

    def get(self, node_id: str) -> Node:
        if node_id not in self._by_id:
            raise GraphError(f"unknown node id {node_id!r}")
        return self._by_id[node_id]

    def has(self, node_id: str) -> bool:
        return node_id in self._by_id

    def of_kind(self, kind: str) -> list[Node]:
        """Nodes of one kind, id-sorted so every projection is deterministic."""
        return sorted(
            (n for n in self.nodes if n.kind == kind), key=lambda n: n.id
        )

    def kinds(self) -> list[str]:
        return sorted({n.kind for n in self.nodes})

    def validate(self) -> list[str]:
        problems: list[str] = []
        for node in sorted(self.nodes, key=lambda n: n.id):
            problems.extend(validate_node(node))
        # Cross-reference integrity: a dangling 'refs' pointer is a silent lie
        # about how well-connected the model is, so it is a hard error.
        for node in sorted(self.nodes, key=lambda n: n.id):
            for target in node.body.get("refs", []) or []:
                if not self.has(target):
                    problems.append(f"{node.id}: refs unknown node {target!r}")
        return problems

    def evidence_summary(self) -> dict[str, int]:
        counts = {status: 0 for status in EVIDENCE_STATUSES}
        for node in self.nodes:
            counts[node.evidence_status] = counts.get(node.evidence_status, 0) + 1
        return counts

    def canonical_json(self) -> str:
        """Stable serialization. Two identical graphs always yield one string."""
        payload = [n.to_dict() for n in sorted(self.nodes, key=lambda n: (n.kind, n.id))]
        return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)

    def digest(self) -> str:
        """sha256 of the canonical form — the provenance stamp on every artifact."""
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def load_graph(directory: str | None = None) -> PlanningGraph:
    """Load every ``*.yaml`` under the node directory into one graph.

    Files are read in sorted order and each may hold a bare list of nodes or a
    mapping with a ``nodes:`` key, so the model can be split by subject without
    the split affecting the resulting digest.
    """
    directory = directory or graph_dir()
    if not os.path.isdir(directory):
        raise GraphError(f"planning graph directory does not exist: {directory}")
    nodes: list[Node] = []
    filenames = sorted(f for f in os.listdir(directory) if f.endswith(".yaml"))
    if not filenames:
        raise GraphError(f"planning graph directory is empty: {directory}")
    for filename in filenames:
        path = os.path.join(directory, filename)
        with open(path, encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)
        if raw is None:
            continue
        entries = raw.get("nodes", []) if isinstance(raw, dict) else raw
        if not isinstance(entries, list):
            raise GraphError(f"{path}: expected a list of nodes, got {type(entries)}")
        for entry in entries:
            nodes.append(_parse_node(entry, path))
    return PlanningGraph(nodes)
