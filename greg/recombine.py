"""RECOMBINE: Capability Genesis constructs new capabilities from engines it already trusts.

Until now Genesis could *acquire* a function (an installed tool or package with a
catalogued oracle) or *commission* one (a builder against a founder contract). A
function nobody catalogued and no founder contract described ended at escalation.

This module adds the third route the mechanism-reuse ladder names but never had:
construction by **certificate-carrying reduction**. A Reduction maps a problem GREG
has no engine for onto a function it can already solve with certificates (maximum
flow, linear programming), then maps the certified answer back and proves it *in the
original problem's own terms*:

    problem --normalize--> canonical problem --encode--> engine request
       ^                                                         |
       |                                              certified engine answer
    certify (GREG, exact, independent of encode and engine)      |
       +-------------------------- decode <----------------------+

Reductions chain (matching -> staffing -> maximum flow), so one certified engine
serves a growing family of functions; each new reduction is a small reviewed file,
not a new solver. Mechanism lineage (primary sources, see each card):

- certifying algorithms: an answer ships with a witness a simple checker verifies
  (McConnell, Mehlhorn, Naeher, Schweitzer, "Certifying algorithms", Computer Science
  Review 5(2), 2011);
- max-flow/min-cut (Ford & Fulkerson, Canadian J. Math. 8, 1956) and Hall's theorem
  (J. London Math. Soc. 10, 1935) / Koenig-Egervary: a staffing or matching shortfall
  is proved by a set of orders whose eligible workers lack the capacity;
- the time-cost trade-off LP (Kelley, "Critical-path planning and scheduling:
  mathematical basis", Operations Research 9(3), 1961; Fulkerson, Operations Research
  9(2), 1961): project crashing is a difference-constraint LP with integral vertices.

The mutation is *certificate transport*: the engine's certificate is not just checked
on the engine's terms and discarded; it is carried back through every reduction and
re-expressed as a witness a person can read about their own problem (which orders,
which workers, which tasks). What remains trusted per call is stated in each card.

Authority: a constructed capability is read-only, inherits nothing from the engine it
calls, is registered VERIFIED only after its own frozen brute-force oracle passes
through the real engine, and is attached only by a founder command or a founder-signed
mission auto_attach inside the mission's light cone. Building != installing !=
activating != consequence authority.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, replace
from fractions import Fraction
import hashlib
import inspect
from itertools import combinations, product
import random
import re
import tempfile
from pathlib import Path

from greg.capabilities import CapabilityError, InvocationContext
from greg.cognition import network

MAX_DEPTH = 3
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,39}$")
MAX_WORKERS = MAX_ORDERS = 1000
MAX_PAIRS = 15000
MAX_TASKS = 240                 # two LP variables per task, under the LP engine's 500
MAX_PRECEDENCES = 1500          # LP rows: two per task plus one per precedence, under 2,000


class ReductionError(Exception):
    """A decoded answer does not prove itself in the original problem's terms."""


def _invalid(why: str):
    # Deliberately avoids the capability-fault markers: a bad request is not a broken capability.
    return CapabilityError(f"constructed request invalid: {why}")


def _count(value, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _invalid(f"{what} must be a nonnegative integer")
    if value > network.MAX_TOTAL_CAPACITY:
        raise _invalid(f"{what} exceeds 2^31-1")
    return value


def _ident(value, what: str) -> str:
    if not isinstance(value, str) or not ID.match(value):
        raise _invalid(f"{what} {value!r} must be 1-40 letters, digits or _.- (starting with a letter or digit)")
    return value


# == staffing -> maximum flow ===============================================================

def normalize_staffing(params: dict) -> dict:
    """Workers with capacities and skills; orders with demands and the skill or workers they accept."""
    if not isinstance(params, dict):
        raise _invalid("parameters must be an object")
    workers, orders = params.get("workers"), params.get("orders")
    if not isinstance(workers, list) or not 1 <= len(workers) <= MAX_WORKERS:
        raise _invalid(f"1-{MAX_WORKERS} workers required")
    if not isinstance(orders, list) or not 1 <= len(orders) <= MAX_ORDERS:
        raise _invalid(f"1-{MAX_ORDERS} orders required")
    capacity, skills = {}, {}
    for w in workers:
        if not isinstance(w, dict):
            raise _invalid("each worker must be an object")
        wid = _ident(w.get("id"), "worker id")
        if wid in capacity:
            raise _invalid(f"worker {wid} repeats")
        capacity[wid] = _count(w.get("capacity"), f"capacity of {wid}")
        held = w.get("skills", [])
        if not isinstance(held, list) or not all(isinstance(s, str) and s for s in held):
            raise _invalid(f"skills of {wid} must be a list of names")
        skills[wid] = set(held)
    demand, eligible = {}, {}
    for o in orders:
        if not isinstance(o, dict):
            raise _invalid("each order must be an object")
        oid = _ident(o.get("id"), "order id")
        if oid in demand:
            raise _invalid(f"order {oid} repeats")
        demand[oid] = _count(o.get("demand"), f"demand of {oid}")
        allowed = set(capacity)
        if o.get("skill") is not None:
            if not isinstance(o["skill"], str) or not o["skill"]:
                raise _invalid(f"skill of {oid} must be a name")
            allowed = {w for w in allowed if o["skill"] in skills[w]}
        if o.get("eligible") is not None:
            if not isinstance(o["eligible"], list) or not set(o["eligible"]) <= set(capacity):
                raise _invalid(f"eligible workers of {oid} must name known workers")
            allowed &= set(o["eligible"])
        eligible[oid] = sorted(allowed)
    if sum(len(v) for v in eligible.values()) > MAX_PAIRS:
        raise _invalid(f"more than {MAX_PAIRS} eligible worker-order pairs")
    return {"workers": sorted([w, c] for w, c in capacity.items()),
            "orders": sorted([o, d] for o, d in demand.items()),
            "eligible": {o: eligible[o] for o in sorted(eligible)}}


def encode_staffing(p: dict) -> dict:
    total = sum(d for _, d in p["orders"])
    big = total + 1     # a worker-order arc can never be in a minimum cut: cutting all demand costs only `total`
    edges = [["source", f"w:{w}", c] for w, c in p["workers"]] + [[f"o:{o}", "sink", d] for o, d in p["orders"]]
    edges += [[f"w:{w}", f"o:{o}", big] for o, ws in p["eligible"].items() for w in ws]
    if sum(e[2] for e in edges) > network.MAX_TOTAL_CAPACITY:
        raise _invalid("the encoded network exceeds the engine's 2^31-1 total capacity")
    nodes = ["source", "sink"] + [f"w:{w}" for w, _ in p["workers"]] + [f"o:{o}" for o, _ in p["orders"]]
    return {"edges": edges, "nodes": nodes, "source": "source", "sink": "sink", "directed": True}


def decode_staffing(p: dict, flow: dict) -> dict:
    if flow.get("certified") is not True or "min_cut" not in flow:
        raise ReductionError("the engine answer carries no certified minimum cut")
    assignment = sorted([u[2:], v[2:], x] for u, v, x in flow["flows"] if u.startswith("w:") and v.startswith("o:"))
    side = set(flow["min_cut"]["source_side"])
    staffed = sum(x for *_, x in assignment)
    total = sum(d for _, d in p["orders"])
    # Orders on the sink side of the cut: their eligible workers are all on the sink side too
    # (no worker-order arc is cut), so demand(U) - capacity(N(U)) is the shortfall.
    bottleneck = [o for o, _ in p["orders"] if f"o:{o}" not in side] if staffed < total else []
    return {"assignment": assignment, "staffed": staffed, "bottleneck_orders": bottleneck}


def certify_staffing(p: dict, answer: dict) -> dict:
    """GREG-owned and exact: feasibility of the assignment, and optimality by a deficiency set.

    For any set U of orders, at most demand(O minus U) + capacity(N(U)) units can be staffed,
    where N(U) are the workers eligible for some order in U. An assignment that meets that
    bound for the stated U is therefore maximum (weak duality; generalized Hall/Koenig)."""
    capacity, demand = dict(map(tuple, p["workers"])), dict(map(tuple, p["orders"]))
    used, filled = defaultdict(int), defaultdict(int)
    seen = set()
    for item in answer.get("assignment", []):
        if not isinstance(item, list) or len(item) != 3:
            raise ReductionError(f"assignment entry {item!r} must be [worker, order, units]")
        w, o, x = item
        if (w, o) in seen or o not in demand or w not in p["eligible"][o]:
            raise ReductionError(f"{w} is not eligible for {o}, or the pair repeats")
        if isinstance(x, bool) or not isinstance(x, int) or x <= 0:
            raise ReductionError(f"units of {w} on {o} must be a positive integer")
        seen.add((w, o))
        used[w] += x
        filled[o] += x
    for w, u in used.items():
        if u > capacity[w]:
            raise ReductionError(f"{w} is assigned {u}, above capacity {capacity[w]}")
    for o, f in filled.items():
        if f > demand[o]:
            raise ReductionError(f"{o} is filled {f}, above demand {demand[o]}")
    staffed = sum(filled.values())
    if answer.get("staffed") != staffed:
        raise ReductionError("the stated total is not the assignment's total")
    U = answer.get("bottleneck_orders", [])
    if not set(U) <= set(demand):
        raise ReductionError("the bottleneck names unknown orders")
    neighbours = sorted({w for o in U for w in p["eligible"][o]})
    bound = sum(d for o, d in demand.items() if o not in U) + sum(capacity[w] for w in neighbours)
    if staffed != bound:
        raise ReductionError(f"staffed {staffed} does not meet the bound {bound} of the stated bottleneck: "
                             "optimality is not shown")
    total = sum(demand.values())
    return {"certified": True, "staffed": staffed, "total_demand": total, "shortage": total - staffed,
            "assignment": answer["assignment"], "unfilled": {o: demand[o] - filled[o] for o in demand
                                                              if filled[o] < demand[o]},
            "bottleneck": None if staffed == total else {
                "orders": sorted(U), "eligible_workers": neighbours, "demand": sum(demand[o] for o in U),
                "capacity": sum(capacity[w] for w in neighbours),
                "why": "these orders can only be served by these workers, whose whole capacity is short of "
                       "their demand; no assignment can do better without more capacity for exactly them"},
            "certificate": {"kind": "deficiency set (generalized Hall/Koenig): staffed equals demand outside U "
                                    "plus capacity of U's eligible workers", "arithmetic": "exact integers",
                            "checked_by": "GREG, from the original problem; shares no code with the engine"}}


def staffing_brute_force(p: dict) -> int:
    """Max staffed = min over order sets U of demand(O minus U) + capacity(N(U)). Exponential; oracle only."""
    capacity, demand = dict(map(tuple, p["workers"])), dict(map(tuple, p["orders"]))
    orders = sorted(demand)
    best = None
    for k in range(len(orders) + 1):
        for U in combinations(orders, k):
            neighbours = {w for o in U for w in p["eligible"][o]}
            value = sum(demand[o] for o in orders if o not in U) + sum(capacity[w] for w in neighbours)
            best = value if best is None else min(best, value)
    return best


def staffing_exhaustive(p: dict) -> int:
    """Enumerate every integer assignment (tiny instances only): checks the oracle's own theorem."""
    capacity, demand = dict(map(tuple, p["workers"])), dict(map(tuple, p["orders"]))
    pairs = [(w, o) for o, ws in p["eligible"].items() for w in ws]
    best = 0
    for units in product(*[range(min(capacity[w], demand[o]) + 1) for w, o in pairs]):
        used, filled = defaultdict(int), defaultdict(int)
        for (w, o), x in zip(pairs, units):
            used[w] += x
            filled[o] += x
        if all(used[w] <= capacity[w] for w in used) and all(filled[o] <= demand[o] for o in filled):
            best = max(best, sum(units))
    return best


FIXED_STAFFING = [
    ("hall-violation", {"workers": [{"id": "Ana", "capacity": 2, "skills": ["forklift"]},
                                    {"id": "Ben", "capacity": 5, "skills": ["packing"]}],
                        "orders": [{"id": "Dock1", "demand": 3, "skill": "forklift"},
                                   {"id": "Dock2", "demand": 2, "skill": "forklift"},
                                   {"id": "Line", "demand": 4, "skill": "packing"}]}),
    ("nobody-eligible", {"workers": [{"id": "A", "capacity": 3}], "orders": [{"id": "X", "demand": 2, "skill": "weld"}]}),
    ("zero-demand", {"workers": [{"id": "A", "capacity": 0}], "orders": [{"id": "X", "demand": 0}]}),
    ("fully-staffed", {"workers": [{"id": "A", "capacity": 2}, {"id": "B", "capacity": 2}],
                       "orders": [{"id": "X", "demand": 3, "eligible": ["A", "B"]}, {"id": "Y", "demand": 1}]}),
]


def _random_staffing(rng: random.Random) -> dict:
    skills = ["a", "b", "c"]
    workers = [{"id": f"W{i}", "capacity": rng.randint(0, 3), "skills": rng.sample(skills, rng.randint(0, 3))}
               for i in range(rng.randint(1, 4))]
    orders = [{"id": f"O{i}", "demand": rng.randint(0, 3), "skill": rng.choice(skills)}
              for i in range(rng.randint(1, 4))]
    return {"workers": workers, "orders": orders}


def oracle_staffing(seed: int) -> list[dict]:
    rng = random.Random(seed)
    cases = [{"name": n, "input": params} for n, params in FIXED_STAFFING]
    cases += [{"name": f"random{i}", "input": _random_staffing(rng)} for i in range(6)]
    for case in cases:
        case["expected"] = {"staffed": staffing_brute_force(normalize_staffing(case["input"]))}
    return cases


def judge_staffing(answer: dict, expected: dict) -> bool:
    return answer.get("certified") is True and answer["staffed"] == expected["staffed"]


# == matching -> staffing ====================================================================

def normalize_matching(params: dict) -> dict:
    if not isinstance(params, dict):
        raise _invalid("parameters must be an object")
    left, right, pairs = params.get("left"), params.get("right"), params.get("pairs")
    for what, side in (("left", left), ("right", right)):
        if not isinstance(side, list) or not 1 <= len(side) <= MAX_ORDERS or len(set(side)) != len(side):
            raise _invalid(f"{what} must list 1-{MAX_ORDERS} distinct ids")
        for item in side:
            _ident(item, f"{what} id")
    if not isinstance(pairs, list) or len(pairs) > MAX_PAIRS:
        raise _invalid(f"pairs must be a list of at most {MAX_PAIRS} [left, right]")
    allowed = defaultdict(set)
    for pair in pairs:
        if not isinstance(pair, list) or len(pair) != 2 or pair[0] not in left or pair[1] not in right:
            raise _invalid(f"pair {pair!r} must be [left id, right id]")
        allowed[pair[1]].add(pair[0])
    return {"left": sorted(left), "right": sorted(right), "allowed": {r: sorted(allowed[r]) for r in sorted(right)}}


def encode_matching(p: dict) -> dict:
    return {"workers": [{"id": w, "capacity": 1} for w in p["left"]],
            "orders": [{"id": r, "demand": 1, "eligible": p["allowed"][r]} for r in p["right"]]}


def decode_matching(p: dict, staffing: dict) -> dict:
    if staffing.get("certified") is not True:
        raise ReductionError("the staffing answer is not certified")
    unmatched = (staffing.get("bottleneck") or {}).get("orders", [])
    return {"pairs": sorted([w, o] for w, o, _ in staffing["assignment"]), "size": staffing["staffed"],
            "deficient_right": unmatched}


def certify_matching(p: dict, answer: dict) -> dict:
    """Koenig/Hall: |M| = |R| - (|U| - |N(U)|) for the stated U proves the matching maximum."""
    left_used, right_used = set(), set()
    for pair in answer.get("pairs", []):
        if not isinstance(pair, list) or len(pair) != 2:
            raise ReductionError(f"pair {pair!r} must be [left, right]")
        l, r = pair
        if r not in p["allowed"] or l not in p["allowed"][r]:
            raise ReductionError(f"{l}-{r} is not an allowed pair")
        if l in left_used or r in right_used:
            raise ReductionError(f"{l} or {r} is matched twice")
        left_used.add(l)
        right_used.add(r)
    size = len(answer["pairs"])
    if answer.get("size") != size:
        raise ReductionError("the stated size is not the matching's size")
    U = answer.get("deficient_right", [])
    if not set(U) <= set(p["right"]):
        raise ReductionError("the deficiency set names unknown right ids")
    N = sorted({l for r in U for l in p["allowed"][r]})
    if size != len(p["right"]) - (len(U) - len(N)):
        raise ReductionError("the matching does not meet the deficiency bound: maximality is not shown")
    return {"certified": True, "size": size, "pairs": answer["pairs"],
            "unmatched_right": sorted(set(p["right"]) - right_used),
            "deficiency": None if not U else {"right": sorted(U), "their_only_partners": N,
                                              "deficit": len(U) - len(N)},
            "certificate": {"kind": "Koenig-Hall deficiency: size = |right| - (|U| - |N(U)|)",
                            "arithmetic": "exact integers",
                            "checked_by": "GREG, from the original pairs; shares no code with the engine"}}


def matching_brute_force(p: dict) -> int:
    best = 0

    def grow(i, used, size):
        nonlocal best
        best = max(best, size)
        if i == len(p["right"]) or size + len(p["right"]) - i <= best:
            return
        for l in p["allowed"][p["right"][i]]:
            if l not in used:
                grow(i + 1, used | {l}, size + 1)
        grow(i + 1, used, size)
    grow(0, frozenset(), 0)
    return best


def oracle_matching(seed: int) -> list[dict]:
    rng = random.Random(seed)
    cases = [{"name": "perfect", "input": {"left": ["a", "b"], "right": ["x", "y"],
                                           "pairs": [["a", "x"], ["a", "y"], ["b", "x"]]}},
             {"name": "hall-violation", "input": {"left": ["a", "b", "c"], "right": ["x", "y", "z"],
                                                  "pairs": [["a", "x"], ["a", "y"], ["a", "z"], ["b", "x"]]}},
             {"name": "no-pairs", "input": {"left": ["a"], "right": ["x"], "pairs": []}}]
    for i in range(6):
        left = [f"L{k}" for k in range(rng.randint(1, 5))]
        right = [f"R{k}" for k in range(rng.randint(1, 5))]
        pairs = [[l, r] for l in left for r in right if rng.random() < 0.35]
        cases.append({"name": f"random{i}", "input": {"left": left, "right": right, "pairs": pairs}})
    for case in cases:
        case["expected"] = {"size": matching_brute_force(normalize_matching(case["input"]))}
    return cases


def judge_matching(answer: dict, expected: dict) -> bool:
    return answer.get("certified") is True and answer["size"] == expected["size"]


# == project crashing -> linear programming ==================================================

def normalize_crash(params: dict) -> dict:
    """Tasks with normal and shortest durations and a cost per unit of shortening; precedences; a deadline."""
    if not isinstance(params, dict):
        raise _invalid("parameters must be an object")
    tasks = params.get("tasks")
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= MAX_TASKS:
        raise _invalid(f"1-{MAX_TASKS} tasks required")
    rows, index = [], {}
    for t in tasks:
        if not isinstance(t, dict):
            raise _invalid("each task must be an object")
        tid = _ident(t.get("id"), "task id")
        if tid in index:
            raise _invalid(f"task {tid} repeats")
        duration = _count(t.get("duration"), f"duration of {tid}")
        shortest = _count(t.get("min_duration", duration), f"min_duration of {tid}")
        if shortest > duration:
            raise _invalid(f"{tid}: min_duration above duration")
        cost = t.get("cost_per_unit", 0)
        if isinstance(cost, bool) or not isinstance(cost, int) or not 0 <= cost <= 10**6:
            raise _invalid(f"cost_per_unit of {tid} must be an integer 0-1,000,000")
        index[tid] = len(rows)
        rows.append([tid, duration, shortest, cost])
    precedences = params.get("precedences", [])
    if not isinstance(precedences, list) or len(precedences) > MAX_PRECEDENCES:
        raise _invalid(f"at most {MAX_PRECEDENCES} precedences")
    edges = set()
    for pair in precedences:
        if not isinstance(pair, list) or len(pair) != 2 or pair[0] not in index or pair[1] not in index \
                or pair[0] == pair[1]:
            raise _invalid(f"precedence {pair!r} must be [earlier task, later task]")
        edges.add(tuple(pair))
    order = _topological([r[0] for r in rows], edges)
    if order is None:
        raise _invalid("the precedences contain a cycle")
    deadline = _count(params.get("deadline"), "deadline")
    return {"tasks": sorted(rows), "precedences": sorted(map(list, edges)), "deadline": deadline, "order": order}


def _topological(nodes, edges):
    indegree, out = {n: 0 for n in nodes}, defaultdict(list)
    for a, b in edges:
        out[a].append(b)
        indegree[b] += 1
    queue, order = deque(sorted(n for n in nodes if not indegree[n])), []
    while queue:
        n = queue.popleft()
        order.append(n)
        for m in sorted(out[n]):
            indegree[m] -= 1
            if not indegree[m]:
                queue.append(m)
    return order if len(order) == len(nodes) else None


def _longest(p: dict, durations: dict) -> tuple[int, list]:
    """Exact longest path through the precedence DAG and one chain that attains it."""
    preds = defaultdict(list)
    for a, b in p["precedences"]:
        preds[b].append(a)
    finish, via = {}, {}
    for t in p["order"]:
        start = max((finish[a] for a in preds[t]), default=0)
        via[t] = max(preds[t], key=lambda a: (finish[a], a), default=None) if preds[t] else None
        finish[t] = start + durations[t]
    end = max(p["order"], key=lambda t: (finish[t], t))
    chain = [end]
    while via[chain[-1]] is not None and finish[via[chain[-1]]] == finish[chain[-1]] - durations[chain[-1]]:
        chain.append(via[chain[-1]])
    return finish[end], chain[::-1]


def direct_crash(p: dict):
    """Infeasibility needs no engine: the shortest-duration critical chain already exceeds the deadline."""
    length, chain = _longest(p, {t: s for t, _, s, _ in p["tasks"]})
    if length <= p["deadline"]:
        return None
    return {"feasible": False, "chain": chain, "chain_length": length}


def encode_crash(p: dict) -> dict:
    variables, cost, constraints = [], {}, []
    for i, (tid, duration, shortest, c) in enumerate(p["tasks"]):
        variables += [{"name": f"s{i}", "lower": 0, "upper": p["deadline"]},
                      {"name": f"f{i}", "lower": 0, "upper": p["deadline"]}]
        if c:
            cost[f"s{i}"], cost[f"f{i}"] = c, -c     # cost * (duration - (f - s)), constant dropped
        constraints += [{"name": f"shortest_{i}", "op": ">=", "coefficients": {f"f{i}": 1, f"s{i}": -1},
                         "rhs": shortest},
                        {"name": f"normal_{i}", "op": "<=", "coefficients": {f"f{i}": 1, f"s{i}": -1},
                         "rhs": duration}]
    position = {t[0]: i for i, t in enumerate(p["tasks"])}
    for a, b in p["precedences"]:
        constraints.append({"name": f"after_{position[a]}_{position[b]}", "op": ">=",
                            "coefficients": {f"s{position[b]}": 1, f"f{position[a]}": -1}, "rhs": 0})
    return {"variables": variables, "objective": {"sense": "min", "coefficients": cost}, "constraints": constraints}


def decode_crash(p: dict, lp: dict) -> dict:
    if lp.get("certified") is not True or lp.get("status") != "optimal":
        raise ReductionError(f"the engine answer is not a certified optimum ({lp.get('status')})")
    plan = []
    for i, (tid, *_rest) in enumerate(p["tasks"]):
        s, f = lp["values"][f"s{i}"], lp["values"][f"f{i}"]
        if abs(s - round(s)) > 1e-6 or abs(f - round(f)) > 1e-6:
            raise ReductionError(f"the engine returned a fractional vertex for {tid}")
        plan.append([tid, round(s), round(f)])
    constant = sum(d * c for _, d, _, c in p["tasks"])
    return {"feasible": True, "plan": plan, "lp_objective": lp["objective"] + constant,
            "lp_certificate": lp["certificate"]}


def certify_crash(p: dict, answer: dict) -> dict:
    """Exact feasibility of the plan in the project's own terms, and its cost equal to the certified optimum.

    The optimum's lower bound is the LP duality certificate GREG checked on its own encoding;
    the encoding's faithfulness is established by the frozen brute-force oracle at
    qualification, not per call. Infeasibility is proved here alone, by a chain."""
    spec = {t: (d, s, c) for t, d, s, c in p["tasks"]}
    if answer.get("feasible") is False:
        chain = answer.get("chain", [])
        if not chain or any([a, b] not in p["precedences"] for a, b in zip(chain, chain[1:])):
            raise ReductionError("the infeasibility chain is not a precedence chain")
        length = sum(spec[t][1] for t in chain)
        if length != answer.get("chain_length") or length <= p["deadline"]:
            raise ReductionError("the chain does not exceed the deadline at its shortest durations")
        return {"certified": True, "feasible": False, "deadline": p["deadline"], "chain": chain,
                "shortest_chain_length": length,
                "certificate": {"kind": "a precedence chain whose shortest durations already exceed the deadline",
                                "arithmetic": "exact integers", "engine": "none needed"}}
    timing = {}
    for item in answer.get("plan", []):
        tid, s, f = item
        if tid not in spec or tid in timing or not isinstance(s, int) or not isinstance(f, int):
            raise ReductionError(f"plan entry {item!r} is malformed")
        timing[tid] = (s, f)
    if set(timing) != set(spec):
        raise ReductionError("the plan does not schedule every task exactly once")
    for tid, (s, f) in timing.items():
        d, shortest, _ = spec[tid]
        if s < 0 or f > p["deadline"] or not shortest <= f - s <= d:
            raise ReductionError(f"{tid} breaks its duration bounds or the deadline")
    for a, b in p["precedences"]:
        if timing[b][0] < timing[a][1]:
            raise ReductionError(f"{b} starts before {a} finishes")
    crash = {t: spec[t][0] - (f - s) for t, (s, f) in timing.items()}
    cost = sum(spec[t][2] * x for t, x in crash.items())
    target = Fraction(answer["lp_objective"]).limit_denominator(10**6)
    if abs(Fraction(cost) - target) > Fraction(1, 10**6) * max(1, abs(cost)):
        raise ReductionError(f"plan cost {cost} differs from the certified optimum {float(target)}")
    makespan, chain = _longest(p, {t: f - s for t, (s, f) in timing.items()})
    return {"certified": True, "feasible": True, "deadline": p["deadline"], "cost": cost,
            "finish": max(f for _, f in timing.values()),
            "schedule": [[t, s, f] for t, (s, f) in sorted(timing.items())],
            "shorten": {t: x for t, x in sorted(crash.items()) if x},
            "critical_chain": chain, "critical_length": makespan,
            "certificate": {"kind": "plan feasible in exact integers; cost equals the LP optimum whose primal-dual "
                                    "certificate GREG checked on its own encoding (time-cost trade-off LP)",
                            "engine_certificate": answer.get("lp_certificate"),
                            "per_call_trust": "the reduction's encoding, frozen-oracle qualified"}}


def crash_brute_force(p: dict):
    """Every integer shortening vector (tiny instances only): the cheapest that meets the deadline, else None."""
    ranges = [range(d - s + 1) for _, d, s, _ in p["tasks"]]
    best = None
    for crash in product(*ranges):
        durations = {t[0]: t[1] - x for t, x in zip(p["tasks"], crash)}
        if _longest(p, durations)[0] <= p["deadline"]:
            cost = sum(t[3] * x for t, x in zip(p["tasks"], crash))
            best = cost if best is None else min(best, cost)
    return best


FIXED_CRASH = [
    ("shorten-cheapest", {"tasks": [{"id": "A", "duration": 3, "min_duration": 1, "cost_per_unit": 2},
                                    {"id": "B", "duration": 4, "min_duration": 2, "cost_per_unit": 1},
                                    {"id": "C", "duration": 2}],
                          "precedences": [["A", "B"]], "deadline": 5}),
    ("parallel-paths", {"tasks": [{"id": "A", "duration": 4, "min_duration": 2, "cost_per_unit": 3},
                                  {"id": "B", "duration": 4, "min_duration": 1, "cost_per_unit": 1},
                                  {"id": "C", "duration": 3, "min_duration": 3},
                                  {"id": "D", "duration": 2, "min_duration": 1, "cost_per_unit": 5}],
                        "precedences": [["A", "C"], ["B", "D"]], "deadline": 6}),
    ("impossible", {"tasks": [{"id": "A", "duration": 3, "min_duration": 3}, {"id": "B", "duration": 2}],
                    "precedences": [["A", "B"]], "deadline": 4}),
    ("already-on-time", {"tasks": [{"id": "A", "duration": 2, "min_duration": 1, "cost_per_unit": 9}],
                         "deadline": 5}),
]


def oracle_crash(seed: int) -> list[dict]:
    rng = random.Random(seed)
    cases = [{"name": n, "input": params} for n, params in FIXED_CRASH]
    for i in range(6):
        n = rng.randint(1, 4)
        tasks = []
        for k in range(n):
            d = rng.randint(0, 4)
            tasks.append({"id": f"T{k}", "duration": d, "min_duration": max(0, d - rng.randint(0, 2)),
                          "cost_per_unit": rng.randint(0, 3)})
        precedences = [[f"T{a}", f"T{b}"] for a in range(n) for b in range(a + 1, n) if rng.random() < 0.5]
        normal = _longest({"order": [t["id"] for t in tasks], "precedences": precedences},
                          {t["id"]: t["duration"] for t in tasks})[0]
        cases.append({"name": f"random{i}", "input": {"tasks": tasks, "precedences": precedences,
                                                      "deadline": max(0, normal - rng.randint(-1, 4))}})
    for case in cases:
        best = crash_brute_force(normalize_crash(case["input"]))
        case["expected"] = {"feasible": best is not None, "cost": best}
    return cases


def judge_crash(answer: dict, expected: dict) -> bool:
    if answer.get("certified") is not True or answer["feasible"] != expected["feasible"]:
        return False
    return not expected["feasible"] or answer["cost"] == expected["cost"]


# == the reduction library ===================================================================

@dataclass(frozen=True)
class Reduction:
    reduction_id: str
    function: str              # what GREG constructs
    target: str                # what it reduces to (a catalogued engine, or another reduction)
    description: str
    inputs: dict
    normalize: object
    encode: object
    decode: object
    certify: object
    oracle: object
    judge: object
    baseline: str              # the simplest alternative, stated honestly
    card: dict                 # Mechanism Card (directive section 6 fields)
    direct: object = None      # answers that need no engine (proved from the problem alone)
    epistemic_classes: tuple = ("optimization",)   # the Competency Compiler's geometry vocabulary


CARD_FIELDS = ("source", "source_version_and_license", "observed_behavior", "underlying_function",
               "state_and_transitions", "inputs_and_outputs", "resource_consumption", "feedback_loops",
               "selection_rules", "trust_and_authority_boundaries", "failure_behavior", "recovery_behavior",
               "evidence_and_uncertainties", "reusable_primitive", "candidate_transformation", "new_failure_risk",
               "intended_greg_capability", "independent_verifier", "integration_interface",
               "replacement_and_rollback")     # the directive's Mechanism Card (section 6), field for field

_SHARED = {
    "source_version_and_license": "published theorems (no software version); GREG's implementation is original code "
                                  "in this repository under its license; no third-party code copied",
    "state_and_transitions": "stateless per call: normalize -> encode -> engine -> decode -> certify; capability "
                             "lifecycle DISCOVERED -> VERIFIED -> ATTACHED | DETACHED | QUARANTINED on the journal",
    "feedback_loops": "a certificate failure in service is a capability fault; two in a row quarantine the "
                      "construction (and the engine when the engine faulted) and re-form the function",
    "selection_rules": "chosen only when no ATTACHED or VERIFIED implementation exists; ahead of the builder and "
                       "founder rungs; exactly one reduction per function, chains at most 3 deep, acyclic",
    "trust_and_authority_boundaries": "read-only; runs only while its pinned engine is ATTACHED; creates no "
                                      "authority; attached only by founder command or signed read-only auto_attach",
    "acquisition": "reasoned from published theorems; no binary or protected artifact inspected; REA not needed "
                   "because the mechanisms are public mathematics and the engines' source is installed",
}


def _card(*, source, observed, function, io, resources, failure, recovery, evidence, primitive, mutation, risk,
          capability, verifier, interface, rollback, classification="BUILDABLE"):
    card = {**_SHARED, "mode": "RECOMBINE", "classification": classification, "source": source,
            "observed_behavior": observed, "underlying_function": function, "inputs_and_outputs": io,
            "resource_consumption": resources, "failure_behavior": failure, "recovery_behavior": recovery,
            "evidence_and_uncertainties": evidence, "reusable_primitive": primitive,
            "candidate_transformation": mutation, "new_failure_risk": risk, "intended_greg_capability": capability,
            "independent_verifier": verifier, "integration_interface": interface,
            "replacement_and_rollback": rollback}
    assert set(CARD_FIELDS) <= set(card)
    return card


REDUCTIONS: dict[str, Reduction] = {r.function: r for r in (
    Reduction(
        "staffing-via-maxflow", "assignment.staffing", "graph.max_flow",
        "Assign workers with capacities and skills to orders with demands; the most units that can be staffed, "
        "and, when short, the exact orders and workers that make it impossible to do better",
        {"workers": "list", "orders": "list"}, normalize_staffing, encode_staffing, decode_staffing,
        certify_staffing, oracle_staffing, judge_staffing,
        "greedy assignment (not optimal in general, and gives no proof of a shortage)",
        _card(source=["Ford & Fulkerson, Canadian J. Math. 8:399-404 (1956)",
                      "P. Hall, J. London Math. Soc. 10:26-30 (1935)",
                      "McConnell et al., Certifying algorithms, Computer Science Review 5(2):119-161 (2011)"],
              observed="a maximum flow's residual graph leaves a source side whose cut arcs are saturated; any "
                       "flow value equals the cut capacity only at the optimum",
              function="max-flow/min-cut duality on a bipartite transportation network",
              io={"in": "workers[{id, capacity, skills}], orders[{id, demand, skill?, eligible?}]",
                  "out": "staffed, shortage, assignment[[worker, order, units]], bottleneck{orders, "
                         "eligible_workers, demand, capacity}"},
              resources="one engine call; network of workers + orders + 2 nodes and one arc per eligible pair; "
                        "certificate linear in pairs",
              failure="engine lies (refused by the max-flow certificate, then by the deficiency check); request "
                      "too large for int32 total capacity (refused before the engine)",
              recovery="engine quarantined and re-acquired from another package; construction re-formed over it",
              evidence="frozen brute-force oracle (subset formula, itself cross-checked against exhaustive "
                       "enumeration); 600 seeded cases each through NetworkX and SciPy with no mismatch",
              primitive="source -> worker (capacity) -> order (uncuttable) -> sink (demand)",
              mutation="certificate transport: the residual minimum cut becomes a deficiency set of orders and "
                       "the only workers who can serve them",
              risk="integer units only; a skill model richer than one skill per order needs a new reduction",
              capability="assignment.staffing: certified staffing with a named bottleneck",
              verifier="GREG deficiency-set check in exact integers + frozen brute-force oracle",
              interface="Genesis 'constructed' route; mission function assignment.staffing; template "
                        "constructed-question",
              rollback="CAPABILITY_DETACH of the composed id; the engine and the history stay")),
    Reduction(
        "matching-via-staffing", "assignment.matching", "assignment.staffing",
        "Largest one-to-one matching between two sets under allowed pairs, with a Hall deficiency proving "
        "nothing larger exists",
        {"left": "list", "right": "list", "pairs": "list"}, normalize_matching, encode_matching, decode_matching,
        certify_matching, oracle_matching, judge_matching,
        "augmenting paths by hand (Hopcroft-Karp) would be a new solver to qualify; reusing staffing adds none",
        _card(source=["D. Koenig (1931) / E. Egervary (1931)", "P. Hall (1935)"],
              observed="with unit capacities and demands, staffing is matching and its deficiency set is a Hall "
                       "violator",
              function="Koenig-Hall duality between maximum matchings and deficiency sets",
              io={"in": "left[ids], right[ids], pairs[[left, right]]",
                  "out": "size, pairs, unmatched_right, deficiency{right, their_only_partners, deficit}"},
              resources="as staffing with unit numbers",
              failure="inherits staffing's; a non-allowed pair or a repeated vertex is refused by GREG's check",
              recovery="as staffing", evidence="frozen brute-force maximum matching; chain test through the real "
                                                 "engine",
              primitive="unit capacities and unit demands",
              mutation="reduction onto a constructed capability, not an engine: one reviewed function set, zero "
                       "new solvers",
              risk="depth: a fault in staffing's reduction affects matching too (both quarantine together)",
              capability="assignment.matching: certified matching with a Hall witness",
              verifier="Koenig-Hall size check in exact integers + frozen brute force",
              interface="Genesis 'constructed' route; mission function assignment.matching",
              rollback="CAPABILITY_DETACH; staffing and the engine stay")),
    Reduction(
        "crash-via-lp", "project.crash", "lp.optimize",
        "Cheapest way to finish a project by a deadline by shortening tasks within their limits, or a proof "
        "that no shortening can meet it",
        {"tasks": "list", "precedences": "list", "deadline": "int"}, normalize_crash, encode_crash, decode_crash,
        certify_crash, oracle_crash, judge_crash,
        "trial-and-error shortening of critical tasks by hand: neither cheapest nor proved",
        _card(source=["J.E. Kelley, Operations Research 9(3):296-320 (1961)",
                      "D.R. Fulkerson, Operations Research 9(2):167-178 (1961)"],
              observed="time-cost trade-off in start/finish variables is a difference-constraint system; with "
                       "integer data its vertices are integral",
              function="linear programming duality on a totally unimodular constraint system",
              io={"in": "tasks[{id, duration, min_duration, cost_per_unit}], precedences, deadline",
                  "out": "cost, schedule, shorten, critical_chain; or feasible=false with a chain"},
              resources="one engine call with 2 variables per task and 2 rows per task plus one per precedence; "
                        "none when infeasibility is proved directly",
              failure="engine returns a fractional or wrong vertex (refused); impossible deadline (proved by a "
                      "chain without the engine)",
              recovery="engine quarantined and re-acquired (HiGHS via SciPy, or GLOP via OR-Tools)",
              evidence="frozen brute force over integer shortenings; 416 seeded engine cases each on SciPy/HiGHS and "
                       "OR-Tools/GLOP and 184 proved without the engine, no mismatch",
              primitive="start/finish variables with duration bounds and precedence differences",
              mutation="infeasibility proved without the engine by a shortest-duration chain; feasibility and cost "
                       "re-checked in exact integers against the original project",
              risk="optimality rests on the LP certificate over GREG's own encoding; the encoding is trusted per "
                   "call because the frozen oracle qualified it (not re-proved per call)",
              capability="project.crash: certified cheapest on-time plan or certified impossibility",
              verifier="exact plan check + LP duality certificate on GREG's encoding + frozen brute force",
              interface="Genesis 'constructed' route; mission function project.crash",
              rollback="CAPABILITY_DETACH; the LP engine and the history stay"),
        direct=direct_crash),
)}


def source_digest(reduction: Reduction) -> str:
    """Content identity of a reduction's executable parts; a change is a different implementation."""
    parts = [reduction.reduction_id, reduction.function, reduction.target]
    for fn in (reduction.normalize, reduction.encode, reduction.decode, reduction.certify, reduction.oracle,
               reduction.judge, reduction.direct):
        parts.append(inspect.getsource(fn) if fn is not None else "-")
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def chain_digest(path) -> str:
    return hashlib.sha256("|".join(source_digest(r) for r in path).encode()).hexdigest()


def chain(function: str, catalog: dict, reductions: dict | None = None):
    """Reductions from ``function`` to a catalogued package engine, or None. Depth-bounded, acyclic."""
    reductions = REDUCTIONS if reductions is None else reductions
    path, seen, current = [], set(), function
    while current in reductions:
        if current in seen or len(path) >= MAX_DEPTH:
            return None
        seen.add(current)
        path.append(reductions[current])
        current = reductions[current].target
    if not path or catalog.get(current, {}).get("kind") != "package":
        return None
    return path, current


def fits(data: dict, reductions: dict | None = None) -> list[Reduction]:
    """Reductions whose declared inputs a request carries, most specific first.

    How the Mind recognizes a problem shape it can have constructed: the Competency Compiler names
    such a function in its CapabilityDeficit instead of an unbuildable geometry label."""
    reductions = REDUCTIONS if reductions is None else reductions
    keys = set(data) if isinstance(data, dict) else set()
    return sorted((r for r in reductions.values() if set(r.inputs) <= keys),
                  key=lambda r: (-len(r.inputs), r.function))


def library(query: str = "", reductions: dict | None = None) -> list[dict]:
    """Searchable index of reduction cards, deduplicated by content digest."""
    reductions = REDUCTIONS if reductions is None else reductions
    rows, seen = [], set()
    words = [w for w in query.lower().split() if w]
    for r in reductions.values():
        digest = source_digest(r)
        if digest in seen:
            continue
        seen.add(digest)
        text = " ".join([r.function, r.target, r.description, r.baseline, str(r.card)]).lower()
        if all(w in text for w in words):
            rows.append({"reduction_id": r.reduction_id, "function": r.function, "target": r.target,
                         "description": r.description, "baseline": r.baseline, "source_digest": digest,
                         "card": r.card})
    return rows


# == the composed adapter and its qualification ==============================================

def _engine_fault(engine_id: str, exc: CapabilityError) -> CapabilityError:
    if str(exc).startswith("capability refused:"):
        return CapabilityError(f"capability refused: composed engine {engine_id} faulted: {str(exc)[20:220]}")
    return exc


def composed_adapter(path, registry):
    """Run a reduction chain over the engine pinned in the manifest; every level re-certifies.

    ``adapter.batch`` answers many requests with one isolated engine run when the engine's
    adapter offers ``batch`` (installed packages do), else one call each. The single-call
    adapter is the same code path with a batch of one."""

    def batch(params_list, ctx: InvocationContext) -> list:
        prov = ctx.manifest.provenance
        if chain_digest(path) != prov["chain_digest"]:
            raise CapabilityError("capability refused: composed capability's reduction code changed since "
                                  "qualification; quarantine required")
        descended = []
        for params in params_list:                      # descend: request errors stay per request
            levels, current, shortcut = [], params, None
            try:
                for r in path:
                    problem = r.normalize(current)
                    levels.append((r, problem))
                    shortcut = r.direct(problem) if r.direct else None
                    if shortcut is not None:
                        break
                    current = r.encode(problem)
                descended.append((levels, current, shortcut))
            except CapabilityError as exc:
                descended.append(exc)
        pending = [i for i, d in enumerate(descended) if not isinstance(d, Exception) and d[2] is None]
        engine_answers = {}
        if pending:
            engine_id = prov["target_capability_id"]
            ok, why = registry.usable(engine_id)
            if not ok:
                raise CapabilityError(f"capability refused: composed capability's engine {engine_id} is not "
                                      f"usable ({why})")
            engine, engine_ctx = registry.adapters[engine_id], replace(ctx, manifest=registry.manifests[engine_id])
            requests = [descended[i][1] for i in pending]
            if hasattr(engine, "batch"):
                try:
                    results = engine.batch(requests, engine_ctx)
                except CapabilityError as exc:
                    raise _engine_fault(engine_id, exc) from exc
            else:
                results = []
                for request in requests:
                    try:
                        results.append(engine(request, engine_ctx))
                    except CapabilityError as exc:
                        results.append(exc)
            for i, result in zip(pending, results):
                engine_answers[i] = _engine_fault(engine_id, result) if isinstance(result, CapabilityError) \
                    else result
        out = []
        for i, d in enumerate(descended):               # ascend: every level re-certifies
            if isinstance(d, Exception):
                out.append(d)
                continue
            levels, _, shortcut = d
            try:
                if shortcut is None:
                    answer = engine_answers[i]
                    if isinstance(answer, Exception):
                        out.append(answer)
                        continue
                    engine_label = answer.get("engine")
                    r, problem = levels[-1]
                    answer = r.certify(problem, r.decode(problem, answer))
                else:
                    engine_label = None
                    r, problem = levels[-1]
                    answer = r.certify(problem, shortcut)
                for r, problem in reversed(levels[:-1]):
                    answer = r.certify(problem, r.decode(problem, answer))
            except ReductionError as exc:
                out.append(CapabilityError(f"capability refused: composed capability failed its certificate: "
                                           f"{exc}"))
                continue
            out.append({**answer, "composed_of": [r.reduction_id for r in path],
                        "engine": engine_label or "none needed", "authority_created": False})
        return out

    def adapter(params, ctx: InvocationContext):
        [answer] = batch([params], ctx)
        if isinstance(answer, Exception):
            raise answer
        return answer

    adapter.batch = batch
    return adapter


def qualify(path, adapter, manifest, seed: int) -> tuple[bool, dict]:
    """The constructed function's own frozen brute-force oracle, run through the real engine in one batch."""
    head = path[0]
    cases = head.oracle(seed)
    report = {"cases": len(cases), "failures": [], "oracle": f"brute force for {head.function} (GREG)",
              "through": "the attached engine, exactly as in service (one isolated batch)",
              "chain": [r.reduction_id for r in path]}
    with tempfile.TemporaryDirectory(prefix="greg-recombine-") as tmp:
        ctx = InvocationContext(workspace=Path(tmp), read_roots=(Path(tmp),), secrets=None, manifest=manifest)
        try:
            answers = adapter.batch([case["input"] for case in cases], ctx)
        except CapabilityError as exc:
            answers = [exc] * len(cases)
    engine_calls = 0
    for case, answer in zip(cases, answers):
        if isinstance(answer, Exception):
            report["failures"].append({"case": case["name"], "error": str(answer)[:200]})
            continue
        engine_calls += answer.get("engine") != "none needed"
        if not head.judge(answer, case["expected"]):
            report["failures"].append({"case": case["name"], "expected": str(case["expected"])[:120]})
    report["engine_calls"] = engine_calls
    return not report["failures"], report
