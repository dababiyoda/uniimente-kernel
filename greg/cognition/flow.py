"""Least-cost delivery from stated supplies to stated demands, from open-source engines, proved by GREG.

One function Capability Genesis can form from installed packages (greg/mechanisms.py):

    flow.min_cost   send every supply to every demand over capacitated arcs at the least total cost

The engines (NetworkX's network simplex, OR-Tools' SimpleMinCostFlow) are untrusted. GREG checks every
answer itself, in exact integers, sharing no code with either:

a delivery plan: every arc carries a whole amount within its capacity and every site ships exactly its
    supply (or receives exactly its demand). It costs the least possible exactly when its residual graph
    has no negative cycle; Bellman-Ford from a virtual root finds any such cycle, and when none exists its
    distances are site prices that prove the total.
"no delivery plan exists": GREG runs its own maximum flow from all supplies to all demands. If it
    carries every unit, the engine's claim is false. Otherwise the sites it can still reach form a set
    whose net supply exceeds the capacity of the arcs leaving it (Gale's condition fails), and GREG names
    that set and both numbers.

Competence: at most 1,000 sites and 5,000 arcs; whole-number supplies and capacities up to 2^31-1 in
total; costs up to 1e9 in size with at most six decimal places (scaled once to exact integers, since
OR-Tools takes integers). Supplies must balance demands. Arcs from a site to itself move nothing and are
refused. The frozen oracle (brute force over every whole-number flow) is GREG's and never shown to an engine.
"""
from __future__ import annotations

from collections import defaultdict, deque
from fractions import Fraction
import itertools
import math
import random
import re

from greg.capabilities import CapabilityError

MAX_NODES, MAX_ARCS, MAX_TOTAL = 1000, 5000, 2**31 - 1
MAX_COST, MAX_SCALE = 10**9, 10**6
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.:-]{0,63}$")


class CertificateError(Exception):
    """The engine's claim does not prove itself."""


def _invalid(why: str):
    # Wording deliberately avoids the capability-fault markers: a bad request is not a broken engine.
    return CapabilityError(f"delivery request invalid: {why}")


def _whole(value, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or (isinstance(value, float)
                                                                          and not value.is_integer()):
        raise _invalid(f"{what} {value!r} must be a whole number")
    return int(value)


def normalize_min_cost(params: dict) -> dict:
    if not isinstance(params, dict):
        raise _invalid("parameters must be an object")
    arcs, supplies = params.get("arcs"), params.get("supplies") or {}
    if not isinstance(arcs, list) or not arcs or len(arcs) > MAX_ARCS:
        raise _invalid(f"arcs must be a list of 1-{MAX_ARCS} [from, to, capacity, cost]")
    if not isinstance(supplies, dict):
        raise _invalid("supplies must map a site to a whole number (negative for a demand)")
    out, nodes, scale, costs = [], set(supplies), 1, []
    for a in arcs:
        if not isinstance(a, (list, tuple)) or len(a) != 4:
            raise _invalid(f"arc {a!r} must be [from, to, capacity, cost]")
        u, v, cap, cost = a
        if u == v:
            raise _invalid(f"arc {u} -> {v} goes nowhere")
        cap = _whole(cap, "capacity")
        if cap < 0:
            raise _invalid("capacities must be nonnegative")
        if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) \
                or abs(cost) > MAX_COST:
            raise _invalid(f"cost {cost!r} must be a finite number up to 1e9 in size")
        exact = Fraction(str(cost)) if isinstance(cost, float) else Fraction(cost)
        if MAX_SCALE % exact.denominator:
            raise _invalid(f"cost {cost!r} has more than six decimal places")
        scale = scale * exact.denominator // math.gcd(scale, exact.denominator)
        nodes.update((u, v))
        out.append([u, v, cap])
        costs.append(exact)
    for n in nodes:
        if not isinstance(n, str) or not NAME.match(n):
            raise _invalid(f"site name {n!r} must be 1-64 letters, digits, spaces or _.:-")
    if len(nodes) > MAX_NODES:
        raise _invalid(f"more than {MAX_NODES} sites")
    b = {n: _whole(supplies.get(n, 0), "supply") for n in sorted(nodes)}
    if sum(b.values()):
        raise _invalid(f"supplies total {sum(x for x in b.values() if x > 0)} but demands total "
                       f"{-sum(x for x in b.values() if x < 0)}; they must balance")
    if sum(x for x in b.values() if x > 0) > MAX_TOTAL or sum(c for _, _, c in out) > MAX_TOTAL:
        raise _invalid("total supply or capacity exceeds 2^31-1")
    return {"nodes": sorted(nodes), "supplies": b,
            "arcs": [[u, v, c, int(k * scale)] for (u, v, c), k in zip(out, costs)], "scale": scale}


# -- engine runners: fixed GREG code executed in the candidate's isolated interpreter --------

RUNNERS = {
    "networkx.min_cost": r'''
def solve(req):
    nx = MODULE
    g = nx.MultiDiGraph()
    for n, b in req["supplies"].items():
        g.add_node(n, demand=-b)
    for i, (u, v, cap, cost) in enumerate(req["arcs"]):
        g.add_edge(u, v, key=i, capacity=cap, weight=cost)
    try:
        _, flow = nx.network_simplex(g)
    except nx.NetworkXUnfeasible:
        return {"status": "infeasible"}
    return {"status": "optimal", "flows": [flow[u][v][i] for i, (u, v, _, _) in enumerate(req["arcs"])]}
''',
    "ortools.min_cost": r'''
def solve(req):
    solver = MODULE.SimpleMinCostFlow()
    index = {n: i for i, n in enumerate(req["nodes"])}
    for u, v, cap, cost in req["arcs"]:
        solver.add_arc_with_capacity_and_unit_cost(index[u], index[v], cap, cost)
    for n, b in req["supplies"].items():
        solver.set_node_supply(index[n], b)
    status = solver.solve()
    if status == solver.INFEASIBLE:
        return {"status": "infeasible"}
    if status != solver.OPTIMAL:
        raise RuntimeError(f"OR-Tools status {status}")
    return {"status": "optimal", "flows": [int(solver.flow(i)) for i in range(len(req["arcs"]))]}
''',
}


# -- certificate (GREG-owned; exact) ----------------------------------------------------------

def _plain(value: Fraction):
    return int(value) if value.denominator == 1 else float(value)


def _prices(req, flows) -> dict | None:
    """Bellman-Ford over the residual graph from a virtual root; None when a negative cycle exists."""
    index = {n: i for i, n in enumerate(req["nodes"])}
    residual = []
    for (u, v, cap, cost), f in zip(req["arcs"], flows):
        if f < cap:
            residual.append((index[u], index[v], cost))
        if f > 0:
            residual.append((index[v], index[u], -cost))
    dist = [0] * len(index)
    for _ in range(len(dist) + 1):
        changed = False
        for a, b, w in residual:
            if dist[a] + w < dist[b]:
                dist[b] = dist[a] + w
                changed = True
        if not changed:
            return {n: dist[i] for n, i in index.items()}
    return None


def _max_flow_cut(req) -> tuple[int, set]:
    """GREG's own augmenting-path flow from all supplies to all demands; the value and the reachable sites."""
    source, sink = ("s",), ("t",)
    residual = defaultdict(lambda: defaultdict(int))
    for u, v, cap, _ in req["arcs"]:
        residual[u][v] += cap
    for n, b in req["supplies"].items():
        if b > 0:
            residual[source][n] += b
        elif b < 0:
            residual[n][sink] += -b
    value = 0
    while True:
        parent, queue = {source: None}, deque([source])
        while queue and sink not in parent:
            x = queue.popleft()
            for y, c in residual[x].items():
                if c > 0 and y not in parent:
                    parent[y] = x
                    queue.append(y)
        if sink not in parent:
            return value, {n for n in parent if n not in (source, sink)}
        push, y = math.inf, sink
        while parent[y] is not None:
            push, y = min(push, residual[parent[y]][y]), parent[y]
        y = sink
        while parent[y] is not None:
            residual[parent[y]][y] -= push
            residual[y][parent[y]] += push
            y = parent[y]
        value += push


def certify_min_cost(req: dict, claim) -> dict:
    if not isinstance(claim, dict) or claim.get("status") not in ("optimal", "infeasible"):
        raise CertificateError("the claim must say optimal (with arc flows) or infeasible")
    total_supply = sum(b for b in req["supplies"].values() if b > 0)
    if claim["status"] == "infeasible":
        value, side = _max_flow_cut(req)
        if value == total_supply:
            raise CertificateError("the engine said no delivery plan exists, but one does")
        net = sum(req["supplies"][n] for n in side)
        leaving = sum(cap for u, v, cap, _ in req["arcs"] if u in side and v not in side)
        if not net > leaving:
            raise CertificateError("GREG could not prove that no delivery plan exists")
        return {"certified": True, "status": "infeasible", "sites": sorted(side), "net_supply": net,
                "capacity_leaving": leaving, "most_deliverable": value, "engine_said": "infeasible",
                "certificate": {"kind": "Gale's condition fails: these sites hold more net supply than the arcs "
                                        "leaving them can carry", "arithmetic": "exact integers"}}
    flows = claim.get("flows")
    if not isinstance(flows, list) or len(flows) != len(req["arcs"]):
        raise CertificateError("the claim must give one flow per arc")
    balance = defaultdict(int)
    for (u, v, cap, _), f in zip(req["arcs"], flows):
        if isinstance(f, bool) or not isinstance(f, int) or not 0 <= f <= cap:
            raise CertificateError(f"flow {f!r} on {u} -> {v} is not a whole amount within capacity {cap}")
        balance[u] += f
        balance[v] -= f
    for n, b in req["supplies"].items():
        if balance[n] != b:
            raise CertificateError(f"{n} ships {balance[n]} but its supply is {b}")
    prices = _prices(req, flows)
    if prices is None:
        raise CertificateError("a cheaper rerouting exists; the plan does not cost the least")
    scale = req["scale"]
    total = Fraction(sum(f * cost for (_, _, _, cost), f in zip(req["arcs"], flows)), scale)
    return {"certified": True, "status": "optimal", "total_cost": _plain(total),
            "shipments": [[u, v, f, _plain(Fraction(cost, scale))] for (u, v, _, cost), f in zip(req["arcs"], flows)
                          if f],
            "certificate": {"kind": "no cheaper rerouting: the residual graph has no negative cycle (Bellman-Ford)",
                            "arcs_checked": len(req["arcs"]), "arithmetic": "exact integers",
                            "site_prices": {n: _plain(Fraction(p, scale)) for n, p in prices.items()}}}


# -- frozen oracle, judge, probe, local baseline ----------------------------------------------

def brute_force(req: dict) -> dict:
    """Every whole-number flow within capacity; oracle-sized networks only."""
    ranges = [range(cap + 1) for _, _, cap, _ in req["arcs"]]
    if math.prod(len(r) for r in ranges) > 60000:
        raise ValueError("brute-force flow is for oracle-sized networks only")
    best = None
    for flows in itertools.product(*ranges):
        balance = defaultdict(int)
        for (u, v, _, _), f in zip(req["arcs"], flows):
            balance[u] += f
            balance[v] -= f
        if all(balance[n] == b for n, b in req["supplies"].items()):
            cost = sum(f * c for (_, _, _, c), f in zip(req["arcs"], flows))
            best = cost if best is None else min(best, cost)
    if best is None:
        return {"status": "infeasible", "total_cost": None}
    return {"status": "optimal", "total_cost": _plain(Fraction(best, req["scale"]))}


FIXED_MIN_COST = [
    ("transport", {"arcs": [["w1", "s1", 3, 4], ["w1", "s2", 3, 6], ["w2", "s1", 3, 5], ["w2", "s2", 3, 3]],
                   "supplies": {"w1": 3, "w2": 2, "s1": -2, "s2": -3}}),
    ("parallel", {"arcs": [["a", "b", 1, 3], ["a", "b", 3, 4]], "supplies": {"a": 2, "b": -2}}),
    ("through-hub", {"arcs": [["a", "h", 2, 1], ["h", "b", 2, 1], ["a", "b", 2, 5]], "supplies": {"a": 3, "b": -3}}),
    ("negative-cycle-is-used", {"arcs": [["a", "b", 2, -2], ["b", "a", 1, 1], ["a", "c", 2, 0]],
                                "supplies": {"a": 0, "b": 0, "c": 0}}),
    ("cut-too-small", {"arcs": [["a", "b", 1, 1], ["c", "b", 3, 1]], "supplies": {"a": 2, "c": 1, "b": -3}}),
    ("demand-unreached", {"arcs": [["a", "b", 3, 1]], "supplies": {"a": 2, "b": -1, "z": -1}}),
    ("decimals", {"arcs": [["a", "b", 2, 0.5], ["a", "c", 2, 1.25], ["c", "b", 2, -0.5]],
                  "supplies": {"a": 2, "b": -2}}),
    ("nothing-to-ship", {"arcs": [["a", "b", 3, 4]], "supplies": {}}),
]


def oracle_min_cost(seed: int) -> list[dict]:
    rng = random.Random(seed)
    cases = [{"name": name, "input": params} for name, params in FIXED_MIN_COST]
    for index in range(8):
        names = [f"s{i}" for i in range(rng.randint(2, 5))]
        arcs = []
        for _ in range(rng.randint(1, 6)):
            u, v = rng.sample(names, 2)
            arcs.append([u, v, rng.randint(0, 3), rng.randint(-3, 9)])
        supplies = {n: 0 for n in names}
        for _ in range(rng.randint(0, 3)):
            a, b = rng.sample(names, 2)
            supplies[a] += 1
            supplies[b] -= 1
        cases.append({"name": f"random{index}", "input": {"arcs": arcs, "supplies": supplies}})
    for case in cases:
        case["expected"] = brute_force(normalize_min_cost(case["input"]))
    return cases


def judge_min_cost(answer: dict, expected: dict) -> bool:
    return answer["status"] == expected["status"] and answer.get("total_cost") == expected["total_cost"]


def size(req: dict) -> dict:
    return {"nodes": len(req["nodes"]), "arcs": len(req["arcs"]),
            "units": sum(b for b in req["supplies"].values() if b > 0)}


def probe_min_cost(seed: int) -> dict:
    rng = random.Random(seed ^ 0x7F7F)
    names = [f"n{i}" for i in range(300)]
    arcs = [[names[i], names[i + 1], 1000, rng.randint(1, 50)] for i in range(299)]      # a feasible backbone
    arcs += [[names[i + 1], names[i], 1000, rng.randint(1, 50)] for i in range(299)]
    while len(arcs) < 3000:
        u, v = rng.sample(names, 2)
        arcs.append([u, v, rng.randint(1, 20), rng.randint(1, 100)])
    supplies = {n: 0 for n in names}
    for _ in range(40):
        a, b = rng.sample(names, 2)
        supplies[a] += 1
        supplies[b] -= 1
    return {"arcs": arcs, "supplies": supplies}


def local_successive_shortest_paths(req: dict) -> dict:
    """Successive shortest paths with queue-based Bellman-Ford, in plain Python."""
    index = {n: i for i, n in enumerate(req["nodes"])}
    graph = defaultdict(list)                       # node -> [to, capacity, cost, reverse index]
    for u, v, cap, cost in req["arcs"]:
        a, b = index[u], index[v]
        graph[a].append([b, cap, cost, len(graph[b])])
        graph[b].append([a, 0, -cost, len(graph[a]) - 1])
    source, sink = len(index), len(index) + 1
    for n, s in req["supplies"].items():
        if s > 0:
            graph[source].append([index[n], s, 0, len(graph[index[n]])])
            graph[index[n]].append([source, 0, 0, len(graph[source]) - 1])
        elif s < 0:
            graph[index[n]].append([sink, -s, 0, len(graph[sink])])
            graph[sink].append([index[n], 0, 0, len(graph[index[n]]) - 1])
    total = 0
    while True:
        dist, parent, queue, queued = {source: 0}, {}, deque([source]), {source}
        while queue:
            x = queue.popleft()
            queued.discard(x)
            for k, (y, cap, cost, _) in enumerate(graph[x]):
                if cap > 0 and dist[x] + cost < dist.get(y, math.inf):
                    dist[y], parent[y] = dist[x] + cost, (x, k)
                    if y not in queued:
                        queued.add(y)
                        queue.append(y)
        if sink not in dist:
            return {"total_cost": _plain(Fraction(total, req["scale"]))}
        push, y = math.inf, sink
        while y != source:
            x, k = parent[y]
            push, y = min(push, graph[x][k][1]), x
        y = sink
        while y != source:
            x, k = parent[y]
            graph[x][k][1] -= push
            graph[y][graph[x][k][3]][1] += push
            y = x
        total += push * dist[sink]
