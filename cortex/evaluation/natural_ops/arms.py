"""Arms for the dependency-control-point family. Every arm returns ``{"cut": list | None, ...}`` with timing.

* ``degree_greedy``   simple baseline, in process, BYPASSES ``reason``: rank intermediate modules by total degree in
                      the relevant subgraph (desc, name asc), delete in that order until T is unreachable, then
                      drop every deleted module (reverse order) whose restoration keeps T unreachable.
* ``betweenness_greedy`` the same with S-T betweenness ranking (NetworkX), BYPASSES ``reason``. The stronger of the
                      two on the development part is the declared baseline; both are reported.
* ``flow_maxflow``    the admitted genome (``solver.graph.max_flow``, DEFAULT_FOR_GEOMETRY) through the canonical
                      ``greg.cognition.cortex.reason`` (isolated worker + independent verifier), on the node-split
                      translation: v -> (v#in -> v#out, capacity 1; S and T uncapacitated), u -> v -> (u#out -> v#in,
                      capacity n + 1). Cut edges are mapped back to modules; a cut edge that is not a unit split arc
                      is an OUTPUT translation failure. A REFUTED receipt is a false answer whatever its cut.
* ``composition``     baseline then genome: the betweenness-greedy cut (the stronger baseline on the development
                      part: 496 vs 395 of 545 optimal; the first development run used degree-greedy here) is accepted when it has exactly one module (the
                      instance has no direct S->T edge, so k >= 1 and a separating single module is optimal; the
                      certificate is the separation check); otherwise the genome runs through ``reason``.
                      Stage 1 bypasses ``reason``; stage 2 is the ``flow_maxflow`` arm.
* ``compiled``        GREG's Competency Compiler (``reason({"compile": ...})``), read-only geometry, on the same
                      node-split data; the selected method is recorded.
* ``practitioner``    ``networkx.minimum_node_cut`` in process, BYPASSES ``reason`` (what an engineer would call).
"""
from __future__ import annotations

from collections import deque
import resource
import time

GENOME_CAPABILITY = "cognition.flow_maxflow"
GENOME_OPERATION = "max_flow"
LATENCY_LIMIT_S = 20.0
_REGISTRY = None


def registry():
    global _REGISTRY
    if _REGISTRY is None:
        from greg.cognition.cortex import registry_view
        _REGISTRY = registry_view()
        _REGISTRY.set_state(GENOME_CAPABILITY, "ATTACHED")   # evaluation-only founder pin, in memory, never the body
    return _REGISTRY


def _adj(edges):
    adj = {}
    for u, v in edges:
        adj.setdefault(u, []).append(v)
        adj.setdefault(v, [])
    return adj


def _reaches(adj, s, t, removed):
    seen, q = {s}, deque([s])
    while q:
        for v in adj.get(q.popleft(), ()):
            if v not in seen and v not in removed:
                if v == t:
                    return True
                seen.add(v)
                q.append(v)
    return False


def _greedy(instance, order):
    adj = _adj(instance["edges"])
    s, t = instance["source"], instance["target"]
    removed = []
    for v in order:
        if not _reaches(adj, s, t, set(removed)):
            break
        removed.append(v)
    if _reaches(adj, s, t, set(removed)):
        return None
    for v in reversed(list(removed)):
        trial = set(removed) - {v}
        if not _reaches(adj, s, t, trial):
            removed.remove(v)
    return sorted(removed)


def degree_order(instance):
    s, t = instance["source"], instance["target"]
    deg = {}
    for u, v in instance["edges"]:
        deg[u] = deg.get(u, 0) + 1
        deg[v] = deg.get(v, 0) + 1
    return sorted((v for v in deg if v not in (s, t)), key=lambda v: (-deg[v], v))


def betweenness_order(instance):
    import networkx as nx
    s, t = instance["source"], instance["target"]
    g = nx.DiGraph(instance["edges"])
    bc = nx.betweenness_centrality_subset(g, [s], [t])
    return sorted((v for v in g if v not in (s, t)), key=lambda v: (-bc[v], v))


def _timed(fn):
    def wrapped(instance):
        r0 = resource.getrusage(resource.RUSAGE_SELF)
        c0 = resource.getrusage(resource.RUSAGE_CHILDREN)
        started = time.perf_counter()
        out = fn(instance)
        out["seconds"] = round(time.perf_counter() - started, 6)
        r1 = resource.getrusage(resource.RUSAGE_SELF)
        c1 = resource.getrusage(resource.RUSAGE_CHILDREN)
        out["cpu_seconds"] = round((r1.ru_utime + r1.ru_stime - r0.ru_utime - r0.ru_stime)
                                   + (c1.ru_utime + c1.ru_stime - c0.ru_utime - c0.ru_stime), 6)
        out.setdefault("money_usd", 0.0)
        return out
    return wrapped


@_timed
def degree_greedy(instance):
    return {"cut": _greedy(instance, degree_order(instance)), "via_reason": False, "subprocesses": 0}


@_timed
def betweenness_greedy(instance):
    return {"cut": _greedy(instance, betweenness_order(instance)), "via_reason": False, "subprocesses": 0}


def split_network(instance):
    s, t = instance["source"], instance["target"]
    nodes = sorted({n for e in instance["edges"] for n in e})
    big = len(nodes) + 1
    edges = [[f"{v}#in", f"{v}#out", big if v in (s, t) else 1] for v in nodes]
    edges += [[f"{u}#out", f"{v}#in", big] for u, v in instance["edges"]]
    return {"edges": edges, "source": f"{s}#in", "sink": f"{t}#out"}


def within_genome_bounds(instance) -> bool:
    from greg.cognition.genomes.flow import MAX_EDGES, MAX_NODES
    net = split_network(instance)
    nodes = {n for e in net["edges"] for n in e[:2]}
    return len(net["edges"]) <= MAX_EDGES and len(nodes) <= MAX_NODES


def back_translate(output):
    """Genome output -> list of modules, or None on an output translation failure."""
    if not isinstance(output, dict) or not isinstance(output.get("cut_edges"), list):
        return None
    cut = []
    for e in output["cut_edges"]:
        if (not isinstance(e, list) or len(e) != 3 or not isinstance(e[0], str) or not isinstance(e[1], str)
                or not e[0].endswith("#in") or e[1] != e[0][:-3] + "#out" or e[2] != 1):
            return None
        cut.append(e[0][:-3])
    return sorted(cut)


def _genome(instance):
    from greg.cognition.contracts import CognitionError
    from greg.cognition.cortex import reason
    params = {"problem_id": f"natops/{instance['instance_id']}/flow_maxflow", "operation": GENOME_OPERATION,
              "data": split_network(instance), "geometry": {"latency_limit": LATENCY_LIMIT_S}}
    in_bounds = within_genome_bounds(instance)
    try:
        r = reason(params, registry=registry())
    except (CognitionError, ValueError, TypeError) as exc:
        return {"cut": None, "via_reason": True, "subprocesses": 0, "state": "REQUEST_REJECTED",
                "translation_failure": "input_request", "missing": [str(exc)[:200]], "in_bounds": in_bounds}
    state = r["abstention_state"]
    out = {"via_reason": True, "subprocesses": 2, "state": state, "method": r["method"],
           "method_version": r["method_version"], "verifier": (r.get("evaluator_result") or {}).get("verdict"),
           "missing": r.get("missing_information"), "in_bounds": in_bounds, "translation_failure": None,
           "genome_id": (r.get("proof_artifact") or {}).get("intelligence_id"),
           "genome_version": (r.get("proof_artifact") or {}).get("version")}
    if state in ("NONE", "REFUTED"):
        cut = back_translate(r.get("output"))
        if cut is None:
            out["translation_failure"] = "output"
        out["cut"] = cut
        out["refuted"] = state == "REFUTED"
    else:
        out["cut"] = None
        if not in_bounds:
            out["translation_failure"] = "input_bounds"
    return out


@_timed
def flow_maxflow(instance):
    return _genome(instance)


@_timed
def composition(instance):
    first = _greedy(instance, betweenness_order(instance))
    if first is not None and len(first) == 1:
        return {"cut": first, "via_reason": False, "subprocesses": 0, "stage": "baseline_certified_k1"}
    out = _genome(instance)
    out["stage"] = "genome"
    return out


@_timed
def compiled(instance):
    from greg.cognition.contracts import CognitionError
    from greg.cognition.cortex import reason
    params = {"problem_id": f"natops/{instance['instance_id']}/compiled",
              "compile": {"geometry": {"consequence_class": "read_only"}, "data": split_network(instance)}}
    in_bounds = within_genome_bounds(instance)
    try:
        r = reason(params, registry=registry())
    except (CognitionError, ValueError, TypeError) as exc:
        return {"cut": None, "via_reason": True, "state": "REQUEST_REJECTED", "translation_failure": "input_request",
                "missing": [str(exc)[:200]], "subprocesses": 0, "in_bounds": in_bounds}
    sel = r.get("selected_receipt") if isinstance(r.get("selected_receipt"), dict) else {}
    state = sel.get("abstention_state", r.get("outcome_state"))
    out = {"via_reason": True, "state": state, "selected": r.get("method_or_composition_selected"),
           "compiler_outcome": r.get("state"), "subprocesses": 2 if sel else 0, "in_bounds": in_bounds,
           "genome_version": (sel.get("proof_artifact") or {}).get("version") if sel else None,
           "verifier": (sel.get("evaluator_result") or {}).get("verdict"), "translation_failure": None}
    if sel and state in ("NONE", "REFUTED"):
        cut = back_translate(sel.get("output"))
        if cut is None:
            out["translation_failure"] = "output"
        out["cut"] = cut
        out["refuted"] = state == "REFUTED"
    else:
        out["cut"] = None
        if not in_bounds:
            out["translation_failure"] = "input_bounds"
    return out


@_timed
def practitioner(instance):
    import networkx as nx
    g = nx.DiGraph(instance["edges"])
    return {"cut": sorted(nx.minimum_node_cut(g, instance["source"], instance["target"])), "via_reason": False,
            "subprocesses": 0}


ARMS = {"degree_greedy": degree_greedy, "betweenness_greedy": betweenness_greedy, "flow_maxflow": flow_maxflow,
        "composition": composition, "compiled": compiled, "practitioner": practitioner}
