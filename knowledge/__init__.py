"""Institutional Knowledge Graph (Foundry technology #18, FBO §4.15).

One provenance-aware graph over the chain the Final Build Order names:

    Repository -> Branch -> Commit -> File -> Contract -> Capability -> Organ
      -> Agent -> Identity -> Legal Principal -> Permission -> Evidence
      -> Claim -> Contradiction -> Prediction -> Decision -> Action
      -> Receipt -> Outcome -> Learning -> Improvement -> Business
      -> Customer -> Revenue -> Capital Consequence

The kernel can populate the left-hand span from real sources today. The
right-hand span has no populated sources, and the graph says so rather than
inventing placeholder nodes.

    A node with no provenance is refused.

That is the single rule this package exists to enforce. Everything in the graph
names the file, manifest, or contract it came from.
"""
from knowledge.graph import (
    Edge,
    GraphError,
    InstitutionalKnowledgeGraph,
    Node,
    NodeKind,
    Provenance,
    build,
)

__all__ = [
    "Edge", "GraphError", "InstitutionalKnowledgeGraph", "Node", "NodeKind",
    "Provenance", "build",
]
