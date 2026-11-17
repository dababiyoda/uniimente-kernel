"""Layer 2 collective intelligence, batch B: ecology bidding as a priced task market (Bertsekas auction).

The 2026-10-21 coverage record (``docs/collaboration/MIND-COVERAGE-2026-10-21.md``) lists ecological intelligence
as INTEGRATED with "methods do not bid; no ecology executor", and section 31 condition 1 names "ecology bidding" as a
family with no executor. Effect, not metaphor: the effect sought is that scarce capacity (workers, solvers, method
slots) goes to the tasks that value it most, through local bids and emergent prices rather than a central planner.
The mechanism is the auction algorithm (Bertsekas 1979): each unassigned task bids for the agent slot with the best
net value (value minus price), raising its price by the bid increment; prices are the market's state and an epsilon
complementary-slackness condition makes the final allocation exactly optimal for integer values.

* ``collective_auction`` (``capacitated_task_allocation``): allocate tasks to agents with capacities, maximising
  total integer value; a task may stay unallocated (value 0). Verified by feasibility and value arithmetic and by an
  independent dual bound computed from the certified prices: any prices give an upper bound on the optimum (weak
  duality), and the allocation is proved optimal when it comes within less than one unit of that bound.

Everything is read-only computation: no files, network, subprocesses or environment access, and no output of any
method here creates authority. Development seeds 0-9 and this lane's declared review range 9400-9439 only.
"""
from __future__ import annotations

import heapq
import math
import random

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "INTENT-20261021-MIND-MAXIMUM-CONTINUATION section 4 (restore the full five-layer scope)",
           "docs/collaboration/MIND-COVERAGE-2026-10-21.md (Layer 2: no ecology-bidding executor)")
AU_MAX_TASKS, AU_MAX_AGENTS, AU_MAX_VALUE, AU_MAX_SLOTS = 400, 60, 100_000, 2000
AU_NATIVE_TASKS = 250
AU_SCALE = 4                     # epsilon-scaling factor


def _input(data):
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    values, caps = data.get("task_agent_values"), data.get("agent_capacities")
    if not isinstance(values, list) or not 1 <= len(values) <= AU_MAX_TASKS:
        raise GenomeError(f"task_agent_values: 1-{AU_MAX_TASKS} rows (one per task)")
    if not isinstance(caps, list) or not 1 <= len(caps) <= AU_MAX_AGENTS:
        raise GenomeError(f"agent_capacities: 1-{AU_MAX_AGENTS} positive integers")
    caps = [bounded_int(c, low=1, high=AU_MAX_SLOTS, name="agent capacity") for c in caps]
    k = len(caps)
    rows = []
    for row in values:
        if not isinstance(row, list) or len(row) != k:
            raise GenomeError("each task row holds one integer value per agent")
        rows.append([bounded_int(v, low=0, high=AU_MAX_VALUE, name="value") for v in row])
    if sum(caps) > AU_MAX_SLOTS:
        raise GenomeError(f"total capacity above {AU_MAX_SLOTS} slots")
    return rows, caps


def _allocation_output(rows, alloc):
    return {"allocation": alloc, "total_value": sum(rows[i][j] for i, j in enumerate(alloc) if j >= 0)}


def _auction(rows, caps):
    """Forward auction with epsilon scaling on the square problem: persons are the m tasks plus one dummy per agent
    slot; objects are the agent slots plus m null slots (value 0 for every task, the 'stay unallocated' option).
    Dummies value everything at 0. All objects end assigned, so epsilon-CS gives total >= OPT - n eps, and the final
    eps < 1 / n makes the allocation optimal for integer values. Groups of identical objects (one agent's slots, the
    null slots) are kept as price heaps, so a bid scans groups, not slots."""
    m, k = len(rows), len(caps)
    groups = list(caps) + [m]                                    # group k: the null slots
    n = sum(groups)
    heaps = [[(0.0, g, s) for s in range(size)] for g, size in enumerate(groups)]
    owner = {}                                                   # (group, slot) -> person
    vmax = max([max(r) for r in rows] + [1])
    eps = max(1.0, vmax / AU_SCALE)
    final = 1.0 / (n + 1)

    def value(person, g):
        return rows[person][g] if person < m and g < k else 0

    while True:
        owner.clear()
        held = [None] * n                                        # person -> (group, slot)
        free = list(range(n))
        while free:
            person = free.pop()
            first = [value(person, g) - heaps[g][0][0] for g in range(len(groups))]
            best_g = max(range(len(groups)), key=lambda g: (first[g], -g))
            best = first[best_g]
            second = max([first[g] for g in range(len(groups)) if g != best_g]
                         + [value(person, best_g) - _second(heaps[best_g])])
            price, g, slot = heapq.heappop(heaps[best_g])
            heapq.heappush(heaps[best_g], (price + best - second + eps, g, slot))
            prev = owner.get((g, slot))
            if prev is not None:
                held[prev] = None
                free.append(prev)
            owner[(g, slot)] = person
            held[person] = (g, slot)
        if eps < final:
            break
        eps = max(final / 2, eps / AU_SCALE)
    alloc = [held[i][0] if held[i][0] < k else -1 for i in range(m)]
    prices = [[0.0] * size for size in groups]
    for h in heaps:
        for price, g, slot in h:
            prices[g][slot] = price
    return alloc, prices[:k], prices[k], n - m


def _second(h):
    """The second-lowest price in a group heap (a single-slot group has none: +inf, so it never wins second place)."""
    if len(h) < 2:
        return math.inf
    return min(h[1][0], h[2][0]) if len(h) > 2 else h[1][0]


def auction_solve(data, budget):
    rows, caps = _input(data)
    if len(rows) > AU_NATIVE_TASKS:
        return answer(None, {"reason": "beyond the native size"}, status="ABSTAIN",
                      missing=[f"more than {AU_NATIVE_TASKS} tasks"])
    alloc, slot_prices, null_prices, dummies = _auction(rows, caps)
    return answer(_allocation_output(rows, alloc),
                  {"method": "forward auction with epsilon scaling (Bertsekas) on the square slot problem",
                   "slot_prices": slot_prices, "null_prices": null_prices, "dummy_persons": dummies})


def dual_bound(rows, caps, slot_prices, null_prices, dummies):
    """Weak duality for the square slot problem (any prices): sum of all object prices + for each task the best net
    value over agents (cheapest slot) and the cheapest null slot + for each dummy person the best net value (minus
    the cheapest price of any object). Returns None when the certificate is malformed."""
    m, k = len(rows), len(caps)

    def ok(p):
        return type(p) in (int, float) and math.isfinite(p)
    if (not isinstance(slot_prices, list) or len(slot_prices) != k or not isinstance(null_prices, list)
            or len(null_prices) != m or dummies != sum(caps)
            or not all(isinstance(ps, list) and len(ps) == c and all(ok(p) for p in ps)
                       for ps, c in zip(slot_prices, caps)) or not all(ok(p) for p in null_prices)):
        return None
    cheapest = [min(ps) for ps in slot_prices]
    null_min = min(null_prices) if null_prices else math.inf
    total = math.fsum(math.fsum(ps) for ps in slot_prices) + math.fsum(null_prices)
    for row in rows:
        total += max([row[j] - cheapest[j] for j in range(k)] + [-null_min])
    total += dummies * -min(cheapest + [null_min])
    return total


def _shape(output, m, k):
    return (isinstance(output, dict) and set(output) == {"allocation", "total_value"}
            and isinstance(output["allocation"], list) and len(output["allocation"]) == m
            and all(type(j) is int and -1 <= j < k for j in output["allocation"])
            and type(output["total_value"]) is int)


def auction_verify(data, output, certificate):
    rows, caps = _input(data)
    m, k = len(rows), len(caps)
    if not _shape(output, m, k):
        return {"output_shape": False}
    alloc = output["allocation"]
    load = [0] * k
    for j in alloc:
        if j >= 0:
            load[j] += 1
    value = sum(rows[i][j] for i, j in enumerate(alloc) if j >= 0)
    cert = certificate if isinstance(certificate, dict) else {}
    bound = dual_bound(rows, caps, cert.get("slot_prices"), cert.get("null_prices"), cert.get("dummy_persons"))
    return {"output_shape": True, "capacities_respected": all(a <= c for a, c in zip(load, caps)),
            "value_recomputed": output["total_value"] == value,
            "dual_bound_certificate_well_formed": bound is not None,
            "optimal_by_dual_bound": bound is not None and value > bound - 1.0 + 1e-9}


def lp_optimum(rows, caps):
    """Evaluation side only: the transportation LP (task <= 1, agent <= capacity) by SciPy HiGHS; the constraint
    matrix is totally unimodular, so the LP optimum is the integer optimum."""
    import numpy as np
    from scipy.optimize import linprog
    from scipy.sparse import lil_matrix
    m, k = len(rows), len(caps)
    a = lil_matrix((m + k, m * k))
    for i in range(m):
        for j in range(k):
            a[i, i * k + j] = 1.0
            a[m + j, i * k + j] = 1.0
    res = linprog(-np.asarray(rows, dtype=float).ravel(), A_ub=a.tocsr(), b_ub=np.array([1.0] * m + caps, dtype=float),
                  bounds=(0, 1), method="highs")
    if not res.success:
        raise GenomeError("LP optimum not found")
    return int(round(-res.fun))


def auction_instance(seed):
    r = random.Random(f"genome:collective_auction:{seed}")
    kind = ("skill_matched", "scarce", "sparse_competence", "uniform_random")[seed % 4]
    m, k = r.randint(30, 150), r.randint(3, 15)
    ratio = r.uniform(0.3, 0.7) if kind == "scarce" else r.uniform(0.6, 1.5)
    caps = [1] * k
    for _ in range(max(0, int(m * ratio) - k)):
        caps[r.randrange(k)] += 1
    skill = [r.uniform(0.2, 1.0) for _ in range(k)]
    rows = []
    for _ in range(m):
        size = r.uniform(10, 100)
        if kind == "uniform_random":
            row = [r.randint(0, 1000) for _ in range(k)]
        else:
            row = [max(0, int(size * skill[j] * r.uniform(0.6, 1.4) * 10)) for j in range(k)]
            if kind == "sparse_competence":
                row = [v if r.random() < 0.3 else 0 for v in row]
        rows.append(row)
    data = {"task_agent_values": rows, "agent_capacities": caps}
    return data, {"optimum": lp_optimum(rows, caps), "kind": kind}


def auction_subregion(data):
    rows, caps = _input(data)
    scarce = sum(caps) < len(rows)
    sparse = sum(v == 0 for row in rows for v in row) * 2 > len(rows) * len(caps)
    return ("scarce" if scarce else "ample") + ("_sparse" if sparse else "_dense")


def auction_score(data, truth, output):
    rows, caps = _input(data)
    if output is None:
        return {"quality": 0.0, "category": "abstain"}
    if not _shape(output, len(rows), len(caps)):
        return {"quality": -1.0, "category": "wrong"}
    load = [0] * len(caps)
    for j in output["allocation"]:
        if j >= 0:
            load[j] += 1
    value = sum(rows[i][j] for i, j in enumerate(output["allocation"]) if j >= 0)
    if any(a > c for a, c in zip(load, caps)) or value != output["total_value"]:
        return {"quality": -1.0, "category": "wrong"}
    q = value / truth["optimum"] if truth["optimum"] else 1.0
    return {"quality": q, "category": "correct" if value == truth["optimum"] else "wrong"}


def auction_greedy(data):
    """Baseline: greedy by value (highest task-agent value first while the task is free and the agent has room)."""
    rows, caps = _input(data)
    room = list(caps)
    alloc = [-1] * len(rows)
    pairs = sorted(((v, i, j) for i, row in enumerate(rows) for j, v in enumerate(row) if v > 0),
                   key=lambda x: (-x[0], x[1], x[2]))
    for v, i, j in pairs:
        if alloc[i] < 0 and room[j] > 0:
            alloc[i] = j
            room[j] -= 1
    return _allocation_output(rows, alloc)


def auction_central_lsa(data):
    """Competitor: the central planner, SciPy linear_sum_assignment (Jonker-Volgenant) on the expanded task x
    (agent slots + null slots) value matrix, maximising."""
    import numpy as np
    from scipy.optimize import linear_sum_assignment
    rows, caps = _input(data)
    m = len(rows)
    owner = [j for j, c in enumerate(caps) for _ in range(c)] + [-1] * m
    v = np.asarray(rows, dtype=float)
    mat = np.hstack([v[:, [j for j in owner if j >= 0]], np.zeros((m, m))])
    ri, ci = linear_sum_assignment(mat, maximize=True)
    alloc = [-1] * m
    for i, c in zip(ri, ci):
        alloc[int(i)] = owner[int(c)]
    alloc = [j if j >= 0 and rows[i][j] > 0 else -1 for i, j in enumerate(alloc)]
    return _allocation_output(rows, alloc)


INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="collective.market.task_auction", version="1.0.0", family="collective_auction", layer=2,
            operation="capacitated_task_allocation", epistemic_class="optimization",
            subgeometry="allocation of tasks to capacitated agents (workers, solvers, method slots) with integer "
                        "task-agent values; a task may stay unallocated",
            source_provenance="Bertsekas (1979, 1988) auction algorithm with epsilon scaling; Bertsekas and "
                              "Castanon (1992) asymmetric assignment by square augmentation",
            native_representation="task x agent integer value matrix and agent capacities",
            required_inputs=("task_agent_values", "agent_capacities"),
            output_contract={"allocation": "[agent index or -1] per task", "total_value": "int"},
            algorithm_or_runtime="forward auction with epsilon scaling (factor 4, final eps < 1/n) on the square "
                                 "problem of tasks + one dummy per slot against slots + one null slot per task; "
                                 "identical slots kept as price heaps",
            parameters={"scaling_factor": AU_SCALE, "native_tasks": AU_NATIVE_TASKS},
            memory_model="the price of every slot (the market state) and the current holder of each",
            learning_rule="none across instances; within one, prices rise by each bid's increment",
            composition_inputs=("task values per worker or method (e.g. from competence evidence)", "capacities"),
            composition_outputs=("allocation", "total value", "clearing prices (marginal value of each slot)"),
            evidence_type="optimality_certificate",
            verification_method="capacities and the total value recomputed from the allocation; an independent "
                                "weak-duality bound computed from the certified slot and null prices (sum of prices + "
                                "each task's best net value + each dummy's) must exceed the value by less than one, "
                                "which for integer values proves optimality",
            confidence_semantics="the exact maximum total value for the supplied integer values and capacities, "
                                 "proved by a dual bound anyone can recompute",
            resource_profile="pseudo-polynomial: O(n log(n V)) phases x bids; n = tasks + slots <= a few hundred",
            latency_profile="tens to hundreds of milliseconds in pure Python at benchmark size",
            known_strengths=("exact with a checkable price certificate",
                             "the prices are marginal values of capacity: a slot's price says what one more unit "
                             "of that agent is worth", "bids are local: each task only reads prices"),
            known_failure_modes=("pure Python: slower than a compiled central assignment solver",
                                 "price wars on near-tied values cost many bids before scaling closes them",
                                 "values are the caller's: miscalibrated competence gives a confident wrong "
                                 "allocation", "integer values only (the optimality proof needs them)"),
            counterindications=("tasks needing several agents or agents with setup costs (a MILP)",
                                "fractional or real-valued values (scale to integers first)",
                                "more than 250 tasks without a time budget"),
            abstention_conditions=(f"more than {AU_NATIVE_TASKS} tasks",),
            benchmark_suite="skill-matched values (task size x agent skill x noise), scarce capacity (30-70% of "
                            "tasks), sparse competence (70% zero values) and uniform random values; 30-150 tasks, "
                            "3-15 agents; truth by the transportation LP in SciPy HiGHS (totally unimodular, so "
                            "integral); seeds 0-9 dev, held-out seeds fixed by the admission freeze",
            baseline="greedy by value",
            competitor="central planner: SciPy linear_sum_assignment (Jonker-Volgenant) on the expanded slot matrix",
            dependency=None, buildability="BUILDABLE_NOW", lineage=LINEAGE),
        solve=auction_solve, verify=auction_verify, instance=auction_instance, score=auction_score,
        baseline=auction_greedy, competitor=auction_central_lsa, subregion=auction_subregion, tolerance=1e-12),
]
