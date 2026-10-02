"""#18 Knowledge graph: Signal -> Evidence -> Assumption -> Decision -> Authority -> Action
-> Receipt -> Outcome -> Capability -> Capital, with typed, schema-checked edges.

An edge outside the typed structural schema is refused. Labels describe supplied
records; they do not prove causation, factual support, benefit or authority.
``why(node)`` walks backwards through recorded dependencies;
``impact(node)`` walks forwards through recorded dependencies; ``shared(kind)`` finds
nodes of one type that feed several ventures (shared chokepoints).
``from_greg(events)`` builds the graph from GREG's own journal, so "why did GREG
do this?" is answered from retained events, not a new authority plane.
"""
from __future__ import annotations

import json
from collections import deque
from pathlib import Path

KINDS = ("Signal", "Evidence", "Assumption", "Decision", "Authority", "Action", "Receipt", "Outcome",
         "Capability", "Capital", "Venture")
SCHEMA = {  # (source kind, relation, target kind)
    ("Signal", "observed_as", "Evidence"), ("Evidence", "supports", "Assumption"),
    ("Evidence", "supports", "Decision"), ("Assumption", "underlies", "Decision"),
    ("Evidence", "challenges", "Assumption"), ("Decision", "requested", "Authority"),
    ("Authority", "authorizes", "Action"), ("Decision", "plans", "Action"),
    ("Action", "produced", "Receipt"), ("Receipt", "measured_as", "Outcome"),
    ("Outcome", "validates", "Capability"), ("Outcome", "refutes", "Assumption"),
    ("Capability", "earns", "Capital"), ("Venture", "uses", "Capability"), ("Venture", "pursues", "Decision"),
}


class GraphError(ValueError):
    """Unknown node kind, dangling edge or an edge outside the causal schema."""


class Graph:
    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.out: dict[str, list] = {}
        self.inn: dict[str, list] = {}

    def add(self, node_id: str, kind: str, **attrs) -> None:
        if kind not in KINDS:
            raise GraphError(f"unknown node kind {kind!r}")
        if node_id in self.nodes and self.nodes[node_id]["kind"] != kind:
            raise GraphError(f"{node_id} already exists as {self.nodes[node_id]['kind']}")
        self.nodes.setdefault(node_id, {"kind": kind}).update(attrs)
        self.out.setdefault(node_id, [])
        self.inn.setdefault(node_id, [])

    def link(self, source: str, relation: str, target: str) -> None:
        for node in (source, target):
            if node not in self.nodes:
                raise GraphError(f"dangling edge: {node} is not a node")
        triple = (self.nodes[source]["kind"], relation, self.nodes[target]["kind"])
        if triple not in SCHEMA:
            raise GraphError(f"edge {triple} is outside the causal schema")
        if (relation, target) not in self.out[source]:
            self.out[source].append((relation, target))
            self.inn[target].append((relation, source))

    def _walk(self, start: str, edges: dict) -> list[dict]:
        if start not in self.nodes:
            raise GraphError(f"unknown node {start}")
        seen, order, queue = {start}, [], deque([(start, 0)])
        while queue:
            node, depth = queue.popleft()
            for relation, nxt in edges[node]:
                if nxt not in seen:
                    seen.add(nxt)
                    order.append({"node": nxt, "kind": self.nodes[nxt]["kind"], "via": relation, "depth": depth + 1})
                    queue.append((nxt, depth + 1))
        return order

    def why(self, node: str) -> list[dict]:
        return self._walk(node, self.inn)

    def impact(self, node: str) -> list[dict]:
        return self._walk(node, self.out)

    def shared(self, kind: str) -> list[dict]:
        """Nodes of ``kind`` reached by two or more ventures: shared chokepoints and reusable assets."""
        ventures = [n for n, v in self.nodes.items() if v["kind"] == "Venture"]
        reach: dict[str, set] = {}
        for venture in ventures:
            for hit in self.impact(venture):
                if hit["kind"] == kind:
                    reach.setdefault(hit["node"], set()).add(venture)
        return sorted(({"node": n, "ventures": sorted(v)} for n, v in reach.items() if len(v) > 1),
                      key=lambda row: (-len(row["ventures"]), row["node"]))

    def to_dict(self) -> dict:
        return {"nodes": self.nodes, "edges": sorted([s, r, t] for s, rows in self.out.items() for r, t in rows)}

    @classmethod
    def from_dict(cls, value: dict) -> "Graph":
        graph = cls()
        for node, attrs in value["nodes"].items():
            graph.add(node, **attrs)
        for s, r, t in value["edges"]:
            graph.link(s, r, t)
        return graph


def from_greg(events) -> Graph:
    """Project event ancestry; this is not causal identification or permission."""
    g = Graph()
    for e in events:
        p, kind = e["payload"], e["type"].removeprefix("greg.")
        if kind == "mission.registered":
            g.add(f"decision:{p['mission_id']}", "Decision", label=p["spec"].get("founder_expression", "")[:120])
        elif kind == "decision.requested":
            g.add(f"authority:{p['request_id']}", "Authority", status="requested", scope=p.get("scope_digest"))
            g.link(f"decision:{p['mission_id']}", "requested", f"authority:{p['request_id']}")
        elif kind == "decision.answered":
            g.add(f"authority:{p['request_id']}", "Authority", status=p["answer"])
        elif kind == "mission.action" and p.get("status") == "DONE":
            action = f"action:{e['event_id']}"
            g.add(action, "Action", capability=p.get("capability"), action_id=p.get("action_id"))
            g.link(f"decision:{p['mission_id']}", "plans", action)
            approved = [n for n, v in g.nodes.items() if v["kind"] == "Authority" and v.get("status") == "approve"
                        and v.get("scope") and v.get("scope") == p.get("scope_digest")]
            for authority in approved:
                g.link(authority, "authorizes", action)
            if p.get("receipt"):
                g.add(f"receipt:{p['receipt']}", "Receipt")
                g.link(action, "produced", f"receipt:{p['receipt']}")
        elif kind == "mission.appraised":
            outcome = f"outcome:{e['event_id']}"
            g.add(outcome, "Outcome", verdict=p.get("verdict"), mission=p.get("mission_id"))
            for s, rows in list(g.out.items()):
                if g.nodes[s]["kind"] == "Action" and f"decision:{p.get('mission_id')}" in [x for _, x in g.inn[s]]:
                    for _, receipt in rows:
                        g.link(receipt, "measured_as", outcome)
    return g


def _load(root: Path) -> Graph:
    path = Path(root) / "graph.json"
    return Graph.from_dict(json.loads(path.read_text())) if path.exists() else Graph()


def _save(root: Path, graph: Graph) -> None:
    Path(root).mkdir(parents=True, exist_ok=True)
    (Path(root) / "graph.json").write_text(json.dumps(graph.to_dict(), sort_keys=True, indent=1))


def _apply_add(args, root):
    g = _load(root)
    for node in args.get("nodes", []):
        g.add(node["id"], node["kind"], **node.get("attrs", {}))
    for s, r, t in args.get("edges", []):
        g.link(s, r, t)
    _save(root, g)
    return {"nodes": len(g.nodes)}


QUERY_OPS = {"why": lambda a, r: {"causes": _load(r).why(a["node"])},
             "impact": lambda a, r: {"effects": _load(r).impact(a["node"])},
             "shared": lambda a, r: {"shared": _load(r).shared(a["kind"])}}
APPLY_OPS = {"add": _apply_add}


def exercise(root) -> dict:
    g = Graph()
    for n, k in (("sig:late-payments", "Signal"), ("ev:interviews", "Evidence"), ("as:proof-delays-pay", "Assumption"),
                 ("dec:build-verifier", "Decision"), ("auth:founder-ok", "Authority"), ("act:pilot", "Action"),
                 ("rcpt:pilot-1", "Receipt"), ("out:paid-in-2d", "Outcome"), ("cap:proof-verifier", "Capability"),
                 ("capital:invoice-1", "Capital"), ("v:freight", "Venture"), ("v:clinics", "Venture")):
        g.add(n, k)
    for s, r, t in (("sig:late-payments", "observed_as", "ev:interviews"), ("ev:interviews", "supports", "as:proof-delays-pay"),
                    ("as:proof-delays-pay", "underlies", "dec:build-verifier"), ("dec:build-verifier", "requested", "auth:founder-ok"),
                    ("auth:founder-ok", "authorizes", "act:pilot"), ("act:pilot", "produced", "rcpt:pilot-1"),
                    ("rcpt:pilot-1", "measured_as", "out:paid-in-2d"), ("out:paid-in-2d", "validates", "cap:proof-verifier"),
                    ("cap:proof-verifier", "earns", "capital:invoice-1"), ("v:freight", "uses", "cap:proof-verifier"),
                    ("v:clinics", "uses", "cap:proof-verifier")):
        g.link(s, r, t)
    try:
        g.link("out:paid-in-2d", "authorizes", "act:pilot")
        bad_edge_refused = False
    except GraphError:
        bad_edge_refused = True
    roots = [row["node"] for row in g.why("capital:invoice-1") if not g.inn[row["node"]]]
    return {"why_capital_reaches_signal": "sig:late-payments" in roots, "why_depth": max(r["depth"] for r in g.why("capital:invoice-1")),
            "impact_of_signal": [r["kind"] for r in g.impact("sig:late-payments")],
            "shared_capabilities": g.shared("Capability"), "bad_edge_refused": bad_edge_refused}
