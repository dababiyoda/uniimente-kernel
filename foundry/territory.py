"""Phase 6 — the Rabbit Hole Engine: Territory Graphs.

Doctrine (The Final Plan, Organ 1): a knowledge domain decomposed into a
directed graph of questions, ordered from "anyone can start here" to
"you are now dangerous." Each node is one artifact per surface, ending
at the exact door the next node opens. Interlinks are explicit in the
content, not hoped for in the algorithm.

    Entry question -> insight -> deeper mechanism -> evidence
    -> opposing case -> practical capability -> useful action

Hard rules encoded here:
  - the graph is a DAG rooted at one entry node; unreachable nodes are
    invalid (a door no path opens is not a door);
  - every rabbit hole has exactly ONE exit that matters, and it leads to
    owned ground (platform attention is rented; the exit converts rent
    into ownership);
  - every node carries an evidence level per the Reality Gradient, a
    correction history, and an expiration date. Content that drops below
    its evidence level is revised or retired, PUBLICLY (ledger events);
  - a funnel extracts at the bottom; a rabbit hole compounds at the
    bottom. The terminal capability node states what the visitor can now
    DO, not what they should now buy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from provenance.commit_witness import sha256_obj

# Draft graphs may be small; production territories are 50-300 nodes.
MIN_NODES = 3
PRODUCTION_MIN_NODES = 50
PRODUCTION_MAX_NODES = 300

# Reality Gradient floor for publishable depth content: below this a node
# may exist as a draft but may not be published (company.py enforces).
PUBLISH_EVIDENCE_FLOOR = 0.7


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TerritoryError(ValueError):
    """Invalid territory. Fails closed; nothing publishes from it."""


@dataclass
class ContentNode:
    node_id: str
    question: str                        # the door this node opens
    artifact: str                        # what is produced (essay/video/tool/dataset)
    capability_taught: str               # what the visitor can DO after this node
    evidence_level: float                # Reality Gradient 0..1
    evidence_refs: list[str] = field(default_factory=list)
    expires_at: datetime | None = None   # evidence has a shelf life
    next_doors: list[str] = field(default_factory=list)   # explicit interlinks
    owned_exit: bool = False             # THE exit that matters
    owned_ground: str = ""               # ledger/newsletter/tool/community you operate
    correction_history: list[dict] = field(default_factory=list)
    retired: bool = False

    def validate(self) -> list[str]:
        problems = []
        for f in ("node_id", "question", "artifact", "capability_taught"):
            if not getattr(self, f):
                problems.append(f"node missing {f}")
        if not 0.0 <= self.evidence_level <= 1.0:
            problems.append(f"evidence_level {self.evidence_level} outside [0,1]")
        if self.owned_exit and not self.owned_ground:
            problems.append("owned exit must lead to owned ground")
        return problems

    def is_stale(self, now: datetime | None = None) -> bool:
        now = now or _now()
        return self.expires_at is not None and now >= self.expires_at


class TerritoryGraph:
    """One territory: a DAG of content nodes rooted at the entry question."""

    def __init__(self, name: str, *, ledger=None):
        self.name = name
        self.ledger = ledger
        self.entry_node_id: str | None = None
        self._nodes: dict[str, ContentNode] = {}

    # -- construction -----------------------------------------------------
    def add(self, node: ContentNode, *, entry: bool = False) -> ContentNode:
        problems = node.validate()
        if problems:
            raise TerritoryError(f"invalid node: {problems}")
        if node.node_id in self._nodes:
            raise TerritoryError(f"duplicate node {node.node_id}")
        self._nodes[node.node_id] = node
        if entry:
            if self.entry_node_id is not None:
                raise TerritoryError("a territory has exactly one entry node")
            self.entry_node_id = node.node_id
        return node

    def node(self, node_id: str) -> ContentNode:
        if node_id not in self._nodes:
            raise TerritoryError(f"no node {node_id} in territory {self.name}")
        return self._nodes[node_id]

    def nodes(self) -> list[ContentNode]:
        return list(self._nodes.values())

    def hash(self) -> str:
        return sha256_obj({
            "territory": self.name, "entry": self.entry_node_id,
            "nodes": sorted(
                (n.node_id, n.question, n.capability_taught, tuple(n.next_doors),
                 n.owned_exit, n.owned_ground) for n in self._nodes.values())})

    # -- structural validation --------------------------------------------
    def validate(self, *, production: bool = False) -> list[str]:
        problems: list[str] = []
        if self.entry_node_id is None:
            problems.append("no entry node: anyone must be able to start somewhere")
            return problems
        n = len(self._nodes)
        floor = PRODUCTION_MIN_NODES if production else MIN_NODES
        if n < floor:
            problems.append(f"{n} nodes < minimum {floor}")
        if production and n > PRODUCTION_MAX_NODES:
            problems.append(f"{n} nodes > maximum {PRODUCTION_MAX_NODES}")
        for node in self._nodes.values():
            for door in node.next_doors:
                if door not in self._nodes:
                    problems.append(f"{node.node_id} opens a door to nowhere: {door}")
        # reachability: a door no path opens is not a door
        reachable = self._reachable(self.entry_node_id)
        unreachable = sorted(set(self._nodes) - reachable)
        if unreachable:
            problems.append(f"unreachable nodes (no path from entry): {unreachable}")
        # acyclicity: depth descends; it does not loop the visitor
        if self._has_cycle():
            problems.append("territory contains a cycle; depth must descend")
        # exactly one exit that matters, on owned ground
        exits = [x for x in self._nodes.values() if x.owned_exit]
        if len(exits) != 1:
            problems.append(f"every rabbit hole has exactly ONE owned exit; found {len(exits)}")
        elif not exits[0].owned_ground:
            problems.append("the owned exit must lead to owned ground")
        return problems

    def _reachable(self, start: str) -> set[str]:
        seen: set[str] = set()
        stack = [start]
        while stack:
            cur = stack.pop()
            if cur in seen or cur not in self._nodes:
                continue
            seen.add(cur)
            stack.extend(self._nodes[cur].next_doors)
        return seen

    def _has_cycle(self) -> bool:
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {nid: WHITE for nid in self._nodes}

        def visit(nid: str) -> bool:
            color[nid] = GRAY
            for door in self._nodes[nid].next_doors:
                if door not in color:
                    continue
                if color[door] == GRAY:
                    return True
                if color[door] == WHITE and visit(door):
                    return True
            color[nid] = BLACK
            return False

        return any(color[nid] == WHITE and visit(nid) for nid in self._nodes)

    # -- the correction layer (public, on the ledger) -----------------------
    def _record(self, event_type: str, payload: dict) -> None:
        if self.ledger is not None:
            self.ledger.append("event", {"type": event_type,
                                         "territory": self.name, **payload})

    def stale_nodes(self, now: datetime | None = None) -> list[ContentNode]:
        return [n for n in self._nodes.values() if not n.retired and n.is_stale(now)]

    def correct(self, node_id: str, *, correction: str, new_evidence_level: float,
                new_evidence_refs: list[str] | None = None) -> ContentNode:
        """Revise a node publicly. The correction history is append-only."""
        node = self.node(node_id)
        entry = {"correction": correction,
                 "previous_evidence_level": node.evidence_level,
                 "new_evidence_level": new_evidence_level,
                 "at": _now().isoformat()}
        node.correction_history.append(entry)
        node.evidence_level = new_evidence_level
        if new_evidence_refs is not None:
            node.evidence_refs = new_evidence_refs
        self._record("foundry.node_corrected", {"node_id": node_id, **entry})
        return node

    def retire(self, node_id: str, *, reason: str) -> ContentNode:
        """Retire a node publicly. Retirement is negative evidence, preserved."""
        node = self.node(node_id)
        node.retired = True
        self._record("foundry.node_retired", {"node_id": node_id, "reason": reason})
        return node

    def publishable(self, node_id: str, now: datetime | None = None) -> tuple[bool, str]:
        """A node publishes only if live, fresh, and above the evidence floor."""
        node = self.node(node_id)
        if node.retired:
            return False, f"{node_id} is retired"
        if node.is_stale(now):
            return False, f"{node_id} evidence expired; revise or retire publicly first"
        if node.evidence_level < PUBLISH_EVIDENCE_FLOOR:
            return False, (f"{node_id} evidence {node.evidence_level} below publish "
                           f"floor {PUBLISH_EVIDENCE_FLOOR}; revise or retire publicly")
        return True, f"{node_id} publishable"
