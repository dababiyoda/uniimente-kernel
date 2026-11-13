"""Ground truth for a dependency-control-point instance, computed independently of every evaluated arm.

Two exact methods, sharing no code with any arm (no NetworkX, nothing from ``greg/cognition``):

1. ``menger_k``: the maximum number of internally vertex-disjoint S->T paths, by unit-capacity augmenting paths
   on the node-split graph (written here from scratch). By Menger's theorem it equals the minimum S-T vertex cut.
   The residual reachability after the last augmentation yields a cut whose size is checked to equal k.
2. ``ilp_k``: an integer program solved by HiGHS (``scipy.optimize.milp``): binary x_v for every intermediate v,
   reachability r in [0, 1] with r_S = 1, r_T = 0 and r_v >= r_u - x_v for every edge u -> v (x_S = x_T = 0);
   minimise sum x_v.

``truth(instance)`` returns k only when both agree and the certificate cut separates S from T; otherwise it
raises, and the instance is reported as TRUTH_DISAGREEMENT (declared exclusion, never silently dropped).

``score(instance, k, cut)`` is the one scoring function every arm uses: CORRECT iff ``cut`` is a set of
intermediate modules whose removal leaves T unreachable from S AND its size equals k; an answered cut that fails
either test is WRONG (a false answer); no cut is ABSTAIN.
"""
from __future__ import annotations

from collections import deque


class TruthError(Exception):
    pass


def _adj(edges):
    adj = {}
    for u, v in edges:
        adj.setdefault(u, []).append(v)
        adj.setdefault(v, [])
    return adj


def separates(edges, s, t, removed) -> bool:
    """True when t is unreachable from s once the modules in ``removed`` are deleted."""
    removed = set(removed)
    if s in removed or t in removed:
        return False
    adj = _adj(edges)
    seen, q = {s}, deque([s])
    while q:
        for v in adj.get(q.popleft(), ()):
            if v not in seen and v not in removed:
                seen.add(v)
                q.append(v)
    return t not in seen


def menger_k(edges, s, t):
    """(k, certificate cut) by unit-capacity augmenting paths on the node-split graph."""
    adj = _adj(edges)
    if t in adj.get(s, ()):
        raise TruthError("direct edge S->T: no vertex cut exists")
    nodes = sorted(adj)
    # node v -> (v, 0) in-copy and (v, 1) out-copy; split arc capacity 1 (inf for s and t); original arcs inf
    big = len(nodes) + 1
    cap = {}

    def arc(a, b, c):
        cap[(a, b)] = cap.get((a, b), 0) + c
        cap.setdefault((b, a), 0)

    for v in nodes:
        arc((v, 0), (v, 1), big if v in (s, t) else 1)
    for u in nodes:
        for v in adj[u]:
            arc((u, 1), (v, 0), big)
    nbr = {}
    for a, b in cap:
        nbr.setdefault(a, []).append(b)
    src, snk = (s, 1), (t, 0)
    k = 0
    while True:
        parent, q = {src: None}, deque([src])
        while q and snk not in parent:
            a = q.popleft()
            for b in nbr.get(a, ()):
                if b not in parent and cap[(a, b)] > 0:
                    parent[b] = a
                    q.append(b)
        if snk not in parent:
            break
        b = snk
        while parent[b] is not None:
            a = parent[b]
            cap[(a, b)] -= 1
            cap[(b, a)] += 1
            b = a
        k += 1
        if k > len(nodes):
            raise TruthError("flow exceeds node count")
    reach, q = {src}, deque([src])
    while q:
        a = q.popleft()
        for b in nbr.get(a, ()):
            if b not in reach and cap[(a, b)] > 0:
                reach.add(b)
                q.append(b)
    cut = sorted(v for v in nodes if v not in (s, t) and (v, 0) in reach and (v, 1) not in reach)
    if len(cut) != k or not separates(edges, s, t, cut):
        raise TruthError("Menger certificate inconsistent")
    return k, cut


def ilp_k(edges, s, t):
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    adj = _adj(edges)
    nodes = sorted(adj)
    mids = [v for v in nodes if v not in (s, t)]
    xi = {v: i for i, v in enumerate(mids)}
    ri = {v: len(mids) + i for i, v in enumerate(nodes)}
    n = len(mids) + len(nodes)
    rows, lo, hi = [], [], []
    for u in nodes:
        for v in adj[u]:
            row = np.zeros(n)            # r_v - r_u + x_v >= 0
            row[ri[v]] += 1
            row[ri[u]] -= 1
            if v in xi:
                row[xi[v]] += 1
            rows.append(row)
            lo.append(0)
            hi.append(np.inf)
    c = np.zeros(n)
    c[:len(mids)] = 1
    lb, ub = np.zeros(n), np.ones(n)
    lb[ri[s]] = 1
    ub[ri[t]] = 0
    integrality = np.zeros(n)
    integrality[:len(mids)] = 1
    res = milp(c, constraints=[LinearConstraint(np.array(rows), lo, hi)] if rows else [],
               bounds=Bounds(lb, ub), integrality=integrality, options={"mip_rel_gap": 0})
    if not res.success:
        raise TruthError(f"ILP failed: {res.message}")
    cut = sorted(v for v in mids if res.x[xi[v]] > 0.5)
    k = int(round(res.fun))
    if len(cut) != k or not separates(edges, s, t, cut):
        raise TruthError("ILP solution inconsistent")
    return k, cut


def truth(instance) -> dict:
    edges, s, t = instance["edges"], instance["source"], instance["target"]
    k1, cut1 = menger_k(edges, s, t)
    k2, cut2 = ilp_k(edges, s, t)
    if k1 != k2:
        raise TruthError(f"truth methods disagree: menger {k1} vs ILP {k2}")
    return {"k": k1, "menger_cut": cut1, "ilp_cut": cut2}


def score(instance, k, cut) -> str:
    if cut is None:
        return "ABSTAIN"
    s, t = instance["source"], instance["target"]
    if (not isinstance(cut, (list, tuple)) or len(set(cut)) != len(cut)
            or any(not isinstance(v, str) for v in cut)):
        return "WRONG"
    nodes = {n for e in instance["edges"] for n in e}
    if not set(cut) <= nodes - {s, t}:
        return "WRONG"
    return "CORRECT" if separates(instance["edges"], s, t, cut) and len(cut) == k else "WRONG"
