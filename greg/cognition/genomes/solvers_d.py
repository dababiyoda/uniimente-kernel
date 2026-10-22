"""Layer 3 solver intelligences, batch D: weighted MaxSAT, bin packing, measurement reconciliation (convex QP),
modularity community detection and multistart L-BFGS-B.

The 2026-10-21 coverage record (``docs/collaboration/MIND-COVERAGE-2026-10-21.md``) lists SAT, packing, convex
optimisation and community / topology analysis as ABSENT from Layer 3; #179 named multistart L-BFGS-B as the
acquisition target that beat differential evolution. Each executable here is an installed, mature engine on
GREG's one cognition path (``greg.cognition.cortex.reason`` -> isolated worker -> independent verifier ->
CognitiveReceipt), chosen for GREG's operating needs: reconciling conflicting claims (MaxSAT), sizing a pool of
workers or containers (bin packing), reconciling inconsistent numeric estimates against known balances (QP),
decomposing a dependency graph into modules (community detection) and tuning a declared continuous objective
(multistart L-BFGS-B). No verifier calls the engine its solver uses.

* ``maxsat_cpsat`` (``weighted_maxsat``): weighted partial MaxSAT by OR-Tools CP-SAT. Verified by recomputing the
  violated clauses of the returned assignment and by Z3 proving that no assignment satisfying the hard clauses
  violates less weight (or that the hard clauses are unsatisfiable).
* ``binpack_cpsat`` (``bin_packing_min_bins``): one-dimensional bin packing by OR-Tools CP-SAT (assignment model,
  first-fit-decreasing upper bound, decreasing-size symmetry breaking). Verified by partition and load arithmetic
  and by an independent Martello-Toth L2 lower bound; when that bound does not close, by SciPy HiGHS proving one
  bin fewer infeasible.
* ``reconcile_qp`` (``reconcile_measurements``): weighted least-squares reconciliation of measurements against
  linear balances with non-negativity (a convex QP), by a primal active-set method on exact KKT face solves
  started from a LP-feasible point. Verified by a KKT certificate: primal feasibility, non-negative bound
  multipliers, complementarity and stationarity recomputed in NumPy; convexity makes KKT sufficient.
* ``community_louvain`` (``detect_communities``): modularity communities by NetworkX Louvain (best of five seeded
  restarts) polished by node-level local moves. Verified by an independent modularity recomputation, partition
  checks and a single-node-move local-optimality check written here.
* ``blackbox_multistart_lbfgsb`` (``continuous_minimize``): multistart SciPy L-BFGS-B under a strict function
  evaluation budget on a declared objective. Verified by an independent vectorised re-evaluation of the objective
  at the returned point, the box and the budget; global optimality is never claimed.

Everything is read-only computation: no files, network, subprocesses or environment access, and no output of
any method here creates authority. Development seeds 0-9 and the lane's declared review range 9300-9399 only.
"""
from __future__ import annotations

import hashlib
import json
import math
import random

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int, finite

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "INTENT-20261021-MIND-MAXIMUM-CONTINUATION section 4 (restore the full five-layer scope)",
           "docs/collaboration/MIND-COVERAGE-2026-10-21.md (Layer 3 ABSENT families)")
NAME_MAX = 64


def _common(**kw):
    return dict(buildability="BUILDABLE_NOW", memory_model="stateless",
                learning_rule="none (competence settles per geometry through GREG outcomes)", lineage=LINEAGE, **kw)


def _abstain(reason, **certificate):
    return answer(None, {"reason": reason, **certificate}, status="ABSTAIN", missing=[reason])


def _unknown(reason, **certificate):
    return answer(None, {"reason": reason, **certificate}, status="UNKNOWN", missing=[reason])


def _mapping(data):
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    return data


def _cert(certificate):
    return certificate if isinstance(certificate, dict) else {}


def _seconds(budget, cap=10.0):
    try:
        return max(0.5, min(cap, float((budget or {}).get("latency_s", cap))))
    except (TypeError, ValueError):
        return cap


def _digest(value) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# =================================================================== 1. weighted partial MaxSAT
MS_MAX_VARS, MS_MAX_CLAUSES, MS_NATIVE_VARS, MS_NATIVE_CLAUSES = 2000, 20000, 200, 3000
MS_MAX_WEIGHT, MS_MAX_WIDTH = 1_000_000, 50
MS_VERIFY_MS = 20000


def _maxsat(data):
    """(variables, clauses as tuples of non-zero ints, weights: int or None for hard)."""
    data = _mapping(data)
    n = bounded_int(data.get("num_vars"), low=1, high=MS_MAX_VARS, name="num_vars")
    clauses, weights = data.get("clauses"), data.get("clause_weights")
    if (not isinstance(clauses, list) or not isinstance(weights, list) or len(clauses) != len(weights)
            or not 1 <= len(clauses) <= MS_MAX_CLAUSES):
        raise GenomeError(f"clauses and clause_weights: equal-length lists of 1-{MS_MAX_CLAUSES}")
    out_c, out_w = [], []
    for c, w in zip(clauses, weights):
        if (not isinstance(c, list) or not 1 <= len(c) <= MS_MAX_WIDTH
                or not all(type(x) is int and 1 <= abs(x) <= n for x in c) or len(set(c)) != len(c)):
            raise GenomeError("clause: a list of distinct literals +-1..num_vars")
        if w is not None:
            w = bounded_int(w, low=1, high=MS_MAX_WEIGHT, name="clause weight (null for a hard clause)")
        out_c.append(tuple(c))
        out_w.append(w)
    return n, out_c, out_w


def _sat(clause, assignment):
    return any((lit > 0) == bool(assignment[abs(lit) - 1]) for lit in clause)


def _maxsat_output(clauses, weights, assignment):
    violated = [i for i, (c, w) in enumerate(zip(clauses, weights)) if w is not None and not _sat(c, assignment)]
    return {"feasible": True, "assignment": [int(v) for v in assignment], "violated": violated,
            "violated_weight": sum(weights[i] for i in violated)}


INFEASIBLE = {"feasible": False, "assignment": None, "violated": None, "violated_weight": None}


def maxsat_solve(data, budget):
    from ortools.sat.python import cp_model
    n, clauses, weights = _maxsat(data)
    if n > MS_NATIVE_VARS or len(clauses) > MS_NATIVE_CLAUSES:
        return _abstain(f"more than {MS_NATIVE_VARS} variables or {MS_NATIVE_CLAUSES} clauses exceeds the bounded "
                        "independently verifiable size", variables=n, clauses=len(clauses))
    model = cp_model.CpModel()
    x = [model.new_bool_var(f"x{i}") for i in range(n)]

    def lit(v):
        return x[v - 1] if v > 0 else x[-v - 1].Not()
    objective = []
    for i, (c, w) in enumerate(zip(clauses, weights)):
        if w is None:
            model.add_bool_or([lit(v) for v in c])
        else:
            relax = model.new_bool_var(f"r{i}")
            model.add_bool_or([lit(v) for v in c] + [relax])
            objective.append(w * relax)
    if objective:
        model.minimize(sum(objective))
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.max_time_in_seconds = _seconds(budget)
    status = solver.solve(model)
    cert = {"method": "OR-Tools CP-SAT weighted partial MaxSAT (one relaxation literal per soft clause)",
            "variables": n, "hard": sum(w is None for w in weights), "soft": sum(w is not None for w in weights)}
    if status == cp_model.INFEASIBLE:
        return answer(dict(INFEASIBLE), {**cert, "solver_status": "INFEASIBLE"})
    if status != cp_model.OPTIMAL:
        return _unknown("CP-SAT did not prove optimality within the time limit", **cert)
    out = _maxsat_output(clauses, weights, [int(solver.boolean_value(v)) for v in x])
    return answer(out, {**cert, "solver_status": "OPTIMAL", "witness": _digest(out["assignment"])})


def _z3_better_exists(n, clauses, weights, bound):
    """Z3 (a different engine from CP-SAT): 'sat' if some assignment satisfies every hard clause and violates soft
    weight strictly below ``bound`` (None: only the hard clauses), 'unsat' if none does, 'unknown' on timeout."""
    import z3
    ctx = z3.Context()
    xs = [z3.Bool(f"x{i}", ctx) for i in range(n)]

    def clause(c):
        return z3.Or([xs[v - 1] if v > 0 else z3.Not(xs[-v - 1]) for v in c])
    s = z3.Solver(ctx=ctx)
    s.set("timeout", MS_VERIFY_MS)
    soft = []
    for c, w in zip(clauses, weights):
        if w is None:
            s.add(clause(c))
        else:
            soft.append((clause(c), w))
    if bound is not None:
        if not soft:
            return "unsat" if bound <= 0 else "sat"
        s.add(z3.PbLe([(z3.Not(e), w) for e, w in soft], bound - 1))
    return str(s.check())


def maxsat_verify(data, output, certificate):
    n, clauses, weights = _maxsat(data)
    if not isinstance(output, dict) or set(output) != {"feasible", "assignment", "violated", "violated_weight"} \
            or type(output["feasible"]) is not bool:
        return {"output_shape": False}
    certificate = _cert(certificate)
    if not output["feasible"]:
        if any(output[k] is not None for k in ("assignment", "violated", "violated_weight")):
            return {"output_shape": False}
        return {"output_shape": True, "hard_clauses_unsatisfiable_by_z3":
                _z3_better_exists(n, clauses, weights, None) == "unsat"}
    a, viol, cost = output["assignment"], output["violated"], output["violated_weight"]
    shape = (isinstance(a, list) and len(a) == n and all(type(v) is int and v in (0, 1) for v in a)
             and isinstance(viol, list) and all(type(i) is int for i in viol) and type(cost) is int)
    if not shape:
        return {"output_shape": False}
    recomputed = [i for i, (c, w) in enumerate(zip(clauses, weights)) if w is not None and not _sat(c, a)]
    checks = {"output_shape": True,
              "hard_clauses_satisfied": all(_sat(c, a) for c, w in zip(clauses, weights) if w is None),
              "violated_clauses_recomputed": viol == recomputed,
              "violated_weight_recomputed": cost == sum(weights[i] for i in recomputed),
              "witness_is_the_certified_assignment": certificate.get("witness") == _digest(a)}
    if not all(checks.values()):
        checks["no_better_assignment_by_z3"] = False      # an inconsistent answer is not sent to the prover
        return checks
    checks["no_better_assignment_by_z3"] = _z3_better_exists(n, clauses, weights, cost) == "unsat"
    return checks


def maxsat_optimum(n, clauses, weights):
    """Evaluation side only: the exact optimum by SciPy HiGHS (a third engine), or None when the hard clauses are
    unsatisfiable."""
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    soft = [i for i, w in enumerate(weights) if w is not None]
    col = {i: n + k for k, i in enumerate(soft)}
    size = n + len(soft)
    c = np.zeros(size)
    for i in soft:
        c[col[i]] = weights[i]
    rows, low = [], []
    for i, clause in enumerate(clauses):
        row = np.zeros(size)
        negatives = 0
        for v in clause:
            if v > 0:
                row[v - 1] += 1
            else:
                row[-v - 1] -= 1
                negatives += 1
        if i in col:
            row[col[i]] = 1
        rows.append(row)
        low.append(1 - negatives)
    res = milp(c, constraints=[LinearConstraint(np.array(rows), np.array(low), np.inf)],
               bounds=Bounds(0, 1), integrality=np.ones(size), options={"time_limit": 60})
    if res.status == 2:
        return None
    if not res.success:
        raise GenomeError("reference MILP did not finish")
    return int(round(res.fun))


def maxsat_instance(seed):
    r = random.Random(f"genome:maxsat_cpsat:{seed}")
    kind = ("claims_rules", "random_3sat", "planted_hard", "mixed_width")[seed % 4]
    clauses, weights = [], []
    if kind == "claims_rules":
        # propositions with a hidden true world; reliable and unreliable sources assert each; hard rules
        # (implications consistent with the world) tie propositions together
        n = r.randint(30, 60)
        world = [r.random() < 0.5 for _ in range(n)]
        rules, target = 0, r.randint(n, 2 * n)
        while rules < target:                   # implication rules true in the hidden world
            a, b = r.sample(range(1, n + 1), 2)
            c = [a if r.random() < 0.5 else -a, b if r.random() < 0.5 else -b]
            if _sat(c, world):
                clauses.append(c)
                weights.append(None)
                rules += 1
        sources = [r.uniform(0.55, 0.95) for _ in range(r.randint(4, 8))]
        for v in range(n):
            for s in r.sample(range(len(sources)), r.randint(1, 3)):
                truthful = r.random() < sources[s]
                clauses.append([(v + 1) if world[v] == truthful else -(v + 1)])
                weights.append(max(1, round(100 * math.log(sources[s] / (1 - sources[s])))))
    elif kind == "random_3sat":
        n = r.randint(30, 50)
        for _ in range(int(n * r.uniform(4.5, 6.0))):
            vs = r.sample(range(1, n + 1), 3)
            clauses.append([v if r.random() < 0.5 else -v for v in vs])
            weights.append(r.randint(1, 20))
    elif kind == "planted_hard":
        n = r.randint(30, 50)
        world = [r.random() < 0.5 for _ in range(n)]
        while len(clauses) < 3 * n:
            vs = r.sample(range(1, n + 1), 3)
            c = [v if r.random() < 0.5 else -v for v in vs]
            if _sat(c, world):
                clauses.append(c)
                weights.append(None)
        for _ in range(4 * n):
            vs = r.sample(range(1, n + 1), 2)
            clauses.append([v if r.random() < 0.5 else -v for v in vs])
            weights.append(r.randint(1, 50))
    else:
        n = r.randint(25, 45)
        groups = [r.sample(range(1, n + 1), r.randint(3, 5)) for _ in range(n // 6)]
        for g in groups:                                     # at most one of each group (pairwise hard)
            for i in range(len(g)):
                for j in range(i + 1, len(g)):
                    clauses.append([-g[i], -g[j]])
                    weights.append(None)
        for _ in range(4 * n):
            vs = r.sample(range(1, n + 1), r.randint(1, 4))
            clauses.append([v if r.random() < 0.5 else -v for v in vs])
            weights.append(r.randint(1, 30))
    # every hard clause above is satisfied by a planted world or by all-false (groups) except claims_rules,
    # whose rules are built true in its world
    data = {"num_vars": n, "clauses": clauses, "clause_weights": weights}
    n, cl, w = _maxsat(data)
    return data, {"optimum": maxsat_optimum(n, cl, w), "total_soft": sum(x for x in w if x is not None)}


def maxsat_subregion(data):
    n, clauses, weights = _maxsat(data)
    hard = sum(w is None for w in weights)
    if sum(1 for c, w in zip(clauses, weights) if w is not None and len(c) == 1) * 2 >= len(clauses) - hard:
        return "unit_claims"
    return "hard_and_soft" if hard else "soft_only"


def maxsat_score(data, truth, output):
    if not isinstance(output, dict) or "feasible" not in output:
        return {"quality": -1.0, "category": "abstain"}
    n, clauses, weights = _maxsat(data)
    if truth["optimum"] is None:
        ok = output.get("feasible") is False
        return {"quality": 0.0 if ok else -2.0, "category": "correct" if ok else "wrong"}
    a = output.get("assignment")
    if (output.get("feasible") is not True or not isinstance(a, list) or len(a) != n
            or not all(v in (0, 1) and type(v) is int for v in a)
            or not all(_sat(c, a) for c, w in zip(clauses, weights) if w is None)):
        return {"quality": -2.0, "category": "wrong"}
    cost = sum(w for c, w in zip(clauses, weights) if w is not None and not _sat(c, a))
    if output.get("violated_weight") != cost:
        return {"quality": -2.0, "category": "wrong"}            # a false claim about its own assignment
    gap = (cost - truth["optimum"]) / max(1, truth["total_soft"])
    return {"quality": -gap, "category": "correct" if cost == truth["optimum"] else "wrong"}


def maxsat_greedy(data):
    """Baseline: polarity by weighted occurrence, then single-variable flips while they lower the cost (hard
    clauses weigh more than every soft clause together); abstains when a hard clause stays violated."""
    n, clauses, weights = _maxsat(data)
    big = sum(w for w in weights if w is not None) + 1
    cw = [big if w is None else w for w in weights]
    pos, neg = [0] * n, [0] * n
    occurs = [[] for _ in range(n)]
    for i, c in enumerate(clauses):
        for v in c:
            (pos if v > 0 else neg)[abs(v) - 1] += cw[i]
            occurs[abs(v) - 1].append(i)
    a = [1 if pos[v] >= neg[v] else 0 for v in range(n)]
    for _ in range(100):
        improved = False
        for v in range(n):
            before = sum(cw[i] for i in occurs[v] if not _sat(clauses[i], a))
            a[v] ^= 1
            after = sum(cw[i] for i in occurs[v] if not _sat(clauses[i], a))
            if after < before:
                improved = True
            else:
                a[v] ^= 1
        if not improved:
            break
    if not all(_sat(c, a) for c, w in zip(clauses, weights) if w is None):
        return None
    return _maxsat_output(clauses, weights, a)


def maxsat_z3_optimize(data):
    """Competitor: Z3's MaxSAT engine (Optimize with soft constraints, MaxRes core-guided)."""
    import z3
    n, clauses, weights = _maxsat(data)
    ctx = z3.Context()
    xs = [z3.Bool(f"x{i}", ctx) for i in range(n)]
    o = z3.Optimize(ctx=ctx)
    o.set("timeout", 10000)
    for c, w in zip(clauses, weights):
        e = z3.Or([xs[v - 1] if v > 0 else z3.Not(xs[-v - 1]) for v in c])
        if w is None:
            o.add(e)
        else:
            o.add_soft(e, w)
    result = o.check()
    if result == z3.unsat:
        return dict(INFEASIBLE)
    if result != z3.sat:
        return None
    m = o.model()
    return _maxsat_output(clauses, weights, [int(z3.is_true(m.eval(x, model_completion=True))) for x in xs])


# =================================================================== 2. one-dimensional bin packing
BP_MAX_ITEMS, BP_NATIVE_ITEMS, BP_MAX_CAPACITY = 2000, 150, 1_000_000
BP_VERIFY_SECONDS = 20.0


def _packing_input(data):
    data = _mapping(data)
    cap = bounded_int(data.get("bin_capacity"), low=1, high=BP_MAX_CAPACITY, name="bin_capacity")
    sizes = data.get("item_sizes")
    if not isinstance(sizes, list) or not 1 <= len(sizes) <= BP_MAX_ITEMS:
        raise GenomeError(f"item_sizes: 1-{BP_MAX_ITEMS} integers in [1, bin_capacity]")
    return [bounded_int(s, low=1, high=cap, name="item size") for s in sizes], cap


def _ffd(sizes, cap):
    """First-fit decreasing: list of bins, each a list of item indices."""
    bins, loads = [], []
    for i in sorted(range(len(sizes)), key=lambda i: (-sizes[i], i)):
        for b, load in enumerate(loads):
            if load + sizes[i] <= cap:
                bins[b].append(i)
                loads[b] += sizes[i]
                break
        else:
            bins.append([i])
            loads.append(sizes[i])
    return bins


def _canonical_packing(bins):
    packing = sorted(sorted(b) for b in bins if b)
    return {"bins": len(packing), "packing": packing}


def _fits_in(sizes, cap, k, seconds, hint):
    """CP-SAT feasibility of a packing into exactly ``k`` bins: (status name, bins as item lists or None). Loads are
    bounded below by the volume left for the other bins; the item count per bin is bounded by how many of the
    smallest items fit (a redundant cardinality cut that decides triplet-like instances)."""
    from ortools.sat.python import cp_model
    n = len(sizes)
    order = sorted(range(n), key=lambda i: (-sizes[i], i))
    total = sum(sizes)
    smallest, most = sorted(sizes), 0
    while most < n and sum(smallest[:most + 1]) <= cap:
        most += 1
    model = cp_model.CpModel()
    x = {}
    for rank, i in enumerate(order):                   # the rank-th largest item goes to a bin <= rank
        for b in range(min(k, rank + 1)):
            x[i, b] = model.new_bool_var(f"x{i}_{b}")
        model.add_exactly_one(x[i, b] for b in range(min(k, rank + 1)))
    for b in range(k):
        members = [i for i in range(n) if (i, b) in x]
        load = model.new_int_var(max(0, total - (k - 1) * cap), cap, f"load{b}")
        model.add(load == sum(sizes[i] * x[i, b] for i in members))
        model.add(sum(x[i, b] for i in members) <= most)
        model.add(sum(x[i, b] for i in members) >= max(1, n - (k - 1) * most))
    for b, items in enumerate(hint[:k]):
        for i in items:
            if (i, b) in x:
                model.add_hint(x[i, b], 1)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.max_time_in_seconds = seconds
    status = solver.solve(model)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return "FEASIBLE", [[i for i in range(n) if (i, b) in x and solver.boolean_value(x[i, b])] for b in range(k)]
    return ("INFEASIBLE" if status == cp_model.INFEASIBLE else "UNKNOWN"), None


def binpack_solve(data, budget):
    import time
    sizes, cap = _packing_input(data)
    n = len(sizes)
    if n > BP_NATIVE_ITEMS:
        return _abstain(f"more than {BP_NATIVE_ITEMS} items exceeds the bounded independently verifiable size",
                        items=n)
    first_fit = _ffd(sizes, cap)
    volume = -(-sum(sizes) // cap)
    cert = {"method": "first-fit decreasing; else OR-Tools CP-SAT feasibility in k bins for k = volume bound upward "
                      "(assignment model, load bounds, cardinality cut, FFD hint)", "items": n,
            "upper_bound_ffd": len(first_fit), "volume_bound": volume}
    if len(first_fit) == volume:
        return answer(_canonical_packing(first_fit), {**cert, "solver_status": "FFD_MEETS_VOLUME_BOUND"})
    deadline = time.monotonic() + _seconds(budget)
    refuted = []
    for k in range(volume, len(first_fit)):
        left = deadline - time.monotonic()
        if left <= 0.05:
            break
        status, bins = _fits_in(sizes, cap, k, left, first_fit)
        if status == "FEASIBLE":
            return answer(_canonical_packing(bins), {**cert, "solver_status": "OPTIMAL",
                                                     "proven_infeasible_bin_counts": refuted})
        if status == "UNKNOWN":
            break
        refuted.append(k)
    else:
        return answer(_canonical_packing(first_fit), {**cert, "solver_status": "OPTIMAL",
                                                      "proven_infeasible_bin_counts": refuted})
    return _unknown("CP-SAT did not decide a bin count within the time limit", **cert,
                    proven_infeasible_bin_counts=refuted)


def martello_toth_l2(sizes, cap):
    """Independent lower bound (verifier side; no code shared with the solver): Martello and Toth's L2."""
    total = sum(sizes)
    best = -(-total // cap)
    half = cap / 2
    thresholds = {0} | {s for s in sizes if s <= half}
    for k in thresholds:
        big = [s for s in sizes if s > cap - k]
        medium = [s for s in sizes if cap - k >= s > half]
        small = [s for s in sizes if half >= s >= k]
        free = len(medium) * cap - sum(medium)
        extra = max(0, -(-(sum(small) - free) // cap))
        best = max(best, len(big) + len(medium) + extra)
    return best


def _highs_fits(sizes, cap, bins):
    """True if HiGHS finds a packing in ``bins`` bins, False if it proves none, None if undecided."""
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    n = len(sizes)
    if bins <= 0:
        return False
    order = sorted(range(n), key=lambda i: -sizes[i])
    cols = [(i, b) for rank, i in enumerate(order) for b in range(min(bins, rank + 1))]
    idx = {k: j for j, k in enumerate(cols)}
    rows, lo, hi = [], [], []
    for i in range(n):
        row = np.zeros(len(cols))
        for b in range(bins):
            if (i, b) in idx:
                row[idx[i, b]] = 1
        rows.append(row)
        lo.append(1)
        hi.append(1)
    for b in range(bins):
        row = np.zeros(len(cols))
        for i in range(n):
            if (i, b) in idx:
                row[idx[i, b]] = sizes[i]
        rows.append(row)
        lo.append(-np.inf)
        hi.append(cap)
    res = milp(np.zeros(len(cols)), constraints=[LinearConstraint(np.array(rows), lo, hi)], bounds=Bounds(0, 1),
               integrality=np.ones(len(cols)), options={"time_limit": BP_VERIFY_SECONDS})
    if res.status == 2:
        return False
    if res.status == 0:
        return True
    return None


def binpack_verify(data, output, certificate):
    sizes, cap = _packing_input(data)
    n = len(sizes)
    if not isinstance(output, dict) or set(output) != {"bins", "packing"} or type(output["bins"]) is not int \
            or not isinstance(output["packing"], list) \
            or not all(isinstance(b, list) and b and all(type(i) is int for i in b) for b in output["packing"]):
        return {"output_shape": False}
    packing = output["packing"]
    flat = [i for b in packing for i in b]
    checks = {"output_shape": True,
              "every_item_packed_exactly_once": sorted(flat) == list(range(n)),
              "canonical_order": packing == sorted(sorted(b) for b in packing),
              "bin_count_matches": output["bins"] == len(packing),
              "loads_within_capacity": all(0 <= i < n for i in flat)
              and all(sum(sizes[i] for i in b) <= cap for b in packing)}
    if not all(checks.values()):
        checks["no_packing_in_fewer_bins"] = False
        return checks
    bound = martello_toth_l2(sizes, cap)
    if bound >= len(packing):
        checks["no_packing_in_fewer_bins"] = bound == len(packing)
        checks["closed_by"] = True                         # the L2 bound alone proves optimality
    else:
        checks["no_packing_in_fewer_bins"] = _highs_fits(sizes, cap, len(packing) - 1) is False
    return checks


def binpack_instance(seed):
    """Planted packings with a known optimum: every bin is filled to capacity, or the planted slack totals less
    than one bin, so the volume bound equals the planted bin count."""
    r = random.Random(f"genome:binpack_cpsat:{seed}")
    kind = ("perfect_cut", "triplets", "slack_planted", "big_and_small")[seed % 4]
    cap = r.choice((100, 120, 150))
    k = r.randint(8, 18)
    sizes = []
    slack_left = cap - 1
    for _ in range(k):
        if kind == "triplets":
            while True:
                a = r.randint(cap // 4 + 1, cap // 2 - 1)
                b = r.randint(cap // 4 + 1, cap // 2 - 1)
                c = cap - a - b
                if cap // 4 < c < cap // 2:
                    break
            pieces = [a, b, c]
        else:
            fill = cap
            if kind == "slack_planted" and slack_left > 0:
                s = r.randint(0, min(slack_left, cap // 10))
                slack_left -= s
                fill = cap - s
            pieces = []
            if kind == "big_and_small":
                big = r.randint(cap // 2 + 1, int(cap * 0.8))
                pieces.append(big)
                fill -= big
            parts = r.randint(1, 4) if kind == "big_and_small" else r.randint(2, 5)
            cuts = sorted(r.sample(range(1, fill), min(parts - 1, fill - 1))) if fill > 1 else []
            bounds = [0] + cuts + [fill]
            pieces += [bounds[j + 1] - bounds[j] for j in range(len(bounds) - 1) if bounds[j + 1] > bounds[j]]
        sizes += pieces
    r.shuffle(sizes)
    assert -(-sum(sizes) // cap) == k
    return {"item_sizes": sizes, "bin_capacity": cap}, {"optimum": k, "kind": kind}


def binpack_subregion(data):
    sizes, cap = _packing_input(data)
    if sum(1 for s in sizes if s > cap / 2) * 4 >= len(sizes):
        return "large_items"
    return "triplet_like" if all(cap / 4 < s < cap / 2 for s in sizes) else "mixed"


def binpack_score(data, truth, output):
    if not isinstance(output, dict) or not isinstance(output.get("packing"), list):
        return {"quality": 0.0, "category": "abstain"}
    sizes, cap = _packing_input(data)
    packing = output["packing"]
    flat = [i for b in packing if isinstance(b, list) for i in b]
    if (not all(isinstance(b, list) and b for b in packing) or sorted(flat) != list(range(len(sizes)))
            or any(sum(sizes[i] for i in b) > cap for b in packing) or output.get("bins") != len(packing)):
        return {"quality": -1.0, "category": "wrong"}
    q = truth["optimum"] / len(packing)
    return {"quality": q, "category": "correct" if len(packing) == truth["optimum"] else "wrong"}


def binpack_ffd(data):
    """Baseline: first-fit decreasing (11/9 OPT + 6/9 worst case)."""
    sizes, cap = _packing_input(data)
    return _canonical_packing(_ffd(sizes, cap))


def binpack_highs(data):
    """Competitor: SciPy HiGHS branch-and-cut on the same assignment model, minimising bins used, 10 s limit
    (returns its incumbent when the limit is hit)."""
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    sizes, cap = _packing_input(data)
    n = len(sizes)
    ub = len(_ffd(sizes, cap))
    smallest, most = sorted(sizes), 0
    while most < n and sum(smallest[:most + 1]) <= cap:
        most += 1
    order = sorted(range(n), key=lambda i: (-sizes[i], i))
    cols = [(i, b) for rank, i in enumerate(order) for b in range(min(ub, rank + 1))]
    idx = {key: j for j, key in enumerate(cols)}
    total = len(cols) + ub
    c = np.zeros(total)
    c[len(cols):] = 1
    rows, lo, hi = [], [], []
    for i in range(n):
        row = np.zeros(total)
        for b in range(ub):
            if (i, b) in idx:
                row[idx[i, b]] = 1
        rows.append(row)
        lo.append(1)
        hi.append(1)
    for b in range(ub):
        row = np.zeros(total)
        for i in range(n):
            if (i, b) in idx:
                row[idx[i, b]] = sizes[i]
        row[len(cols) + b] = -cap
        rows.append(row)
        lo.append(-np.inf)
        hi.append(0)
        count = np.zeros(total)                               # the same cardinality cut the candidate uses
        count[:len(cols)] = (row[:len(cols)] > 0).astype(float)
        count[len(cols) + b] = -most
        rows.append(count)
        lo.append(-np.inf)
        hi.append(0)
    res = milp(c, constraints=[LinearConstraint(np.array(rows), lo, hi)], bounds=Bounds(0, 1),
               integrality=np.ones(total), options={"time_limit": 10.0})
    if res.x is None:
        return None
    bins = [[i for i in range(n) if (i, b) in idx and res.x[idx[i, b]] > 0.5] for b in range(ub)]
    return _canonical_packing(bins)


# =================================================================== 3. measurement reconciliation (convex QP)
QP_MAX_VARS, QP_MAX_ROWS, QP_EXACT_TRUTH_VARS = 500, 500, 12
QP_FEAS_TOL, QP_KKT_TOL = 1e-7, 1e-6


def _qp_input(data):
    import numpy as np
    data = _mapping(data)
    m, sd = data.get("measured_values"), data.get("std_devs")
    a, b = data.get("balance_matrix"), data.get("balance_rhs")
    if not isinstance(m, list) or not 1 <= len(m) <= QP_MAX_VARS or not isinstance(sd, list) or len(sd) != len(m):
        raise GenomeError(f"measured_values and std_devs: equal-length lists of 1-{QP_MAX_VARS} numbers")
    if (not isinstance(a, list) or not 1 <= len(a) <= QP_MAX_ROWS or not isinstance(b, list) or len(b) != len(a)
            or not all(isinstance(row, list) and len(row) == len(m) for row in a)):
        raise GenomeError("balance_matrix: rows of len(measured_values) coefficients; balance_rhs: one per row")
    mv = np.array([finite(v, low=-1e9, high=1e9, name="measured value") for v in m])
    sv = np.array([finite(v, low=1e-9, high=1e9, name="std dev") for v in sd])
    av = np.array([[finite(v, low=-1e6, high=1e6, name="coefficient") for v in row] for row in a])
    bv = np.array([finite(v, low=-1e12, high=1e12, name="rhs") for v in b])
    return mv, sv, av, bv


def _qp_objective(x, m, s):
    return float(sum(((xi - mi) / si) ** 2 for xi, mi, si in zip(x, m, s)))


def _face(m, s, a, b, free):
    """Exact solve of min sum((x-m)/s)^2 s.t. A x = b, x_i = 0 off ``free``: (x, lambda) or None if the face is
    infeasible. x_F = m_F + (1/2) S_F^2 A_F^T lambda, with A_F S_F^2 A_F^T lambda = 2 (b - A_F m_F)."""
    import numpy as np
    n = len(m)
    f = np.array(sorted(free), dtype=int)
    x = np.zeros(n)
    if len(f) == 0:
        return (x, np.zeros(len(b))) if np.allclose(b, 0, atol=QP_FEAS_TOL * (1 + np.abs(b).max())) else None
    af, s2 = a[:, f], s[f] ** 2
    lhs = (af * s2) @ af.T
    rhs = 2 * (b - af @ m[f])
    lam = np.linalg.lstsq(lhs, rhs, rcond=None)[0]
    x[f] = m[f] + 0.5 * s2 * (af.T @ lam)
    scale = 1 + np.abs(b).max() + np.abs(a).max() * np.abs(x).max()
    if np.abs(a @ x - b).max() > QP_FEAS_TOL * scale:
        return None
    return x, lam


def _kkt_multipliers(x, lam, m, s, a):
    return 2 * (x - m) / s ** 2 - a.T @ lam


def reconcile_solve(data, budget):
    import numpy as np
    from scipy.optimize import linprog
    m, s, a, b = _qp_input(data)
    n = len(m)
    start = linprog(np.zeros(n), A_eq=a, b_eq=b, bounds=[(0, None)] * n, method="highs")
    if start.status == 2:
        return answer({"feasible": False, "estimates": None, "objective": None},
                      {"method": "HiGHS LP phase one: no non-negative point satisfies the balances",
                       "solver_status": "INFEASIBLE"})
    if start.status != 0:
        return _unknown("LP phase one did not finish")
    x = np.maximum(start.x, 0.0)
    scale = 1 + np.abs(x).max() + np.abs(m).max()
    work = {i for i in range(n) if x[i] <= 1e-12 * scale}       # bounds held at zero
    for i in work:
        x[i] = 0.0
    for iteration in range(20 * n + 20):
        face = _face(m, s, a, b, set(range(n)) - work)
        if face is None:
            return _unknown("face solve lost feasibility (degenerate balances)")
        target, lam = face
        step = target - x
        if np.abs(step).max() > 1e-12 * scale:
            alpha, block = 1.0, None
            for i in set(range(n)) - work:
                if step[i] < 0 and -x[i] / step[i] < alpha:
                    alpha, block = -x[i] / step[i], i
            x = x + alpha * step
            if block is not None:
                work.add(block)
                x[block] = 0.0
            continue
        x = target
        mu = _kkt_multipliers(x, lam, m, s, a)
        candidates = [i for i in work if mu[i] < -QP_KKT_TOL * (1 + np.abs(mu).max())]
        if not candidates:
            mu[sorted(set(range(n)) - work)] = 0.0
            x = np.maximum(x, 0.0)
            out = {"feasible": True, "estimates": [float(v) for v in x], "objective": _qp_objective(x, m, s)}
            return answer(out, {"method": "primal active-set on exact KKT face solves from a HiGHS LP-feasible "
                                          "start", "iterations": iteration + 1,
                                "balance_multipliers": [float(v) for v in lam],
                                "bound_multipliers": [float(v) for v in mu], "active_bounds": sorted(work)})
        work.discard(min(candidates, key=lambda i: mu[i]))
    return _unknown("active-set iteration limit reached")


def _scales(x, m, s, a, b):
    import numpy as np
    feas = 1 + np.abs(b).max() + np.abs(a).max() * np.abs(x).max()
    grad = 1 + np.abs(2 * (x - m) / s ** 2).max()
    return feas, grad


def reconcile_verify(data, output, certificate):
    import numpy as np
    m, s, a, b = _qp_input(data)
    n = len(m)
    if not isinstance(output, dict) or set(output) != {"feasible", "estimates", "objective"} \
            or type(output["feasible"]) is not bool:
        return {"output_shape": False}
    certificate = _cert(certificate)
    if not output["feasible"]:
        if output["estimates"] is not None or output["objective"] is not None:
            return {"output_shape": False}
        # Farkas: infeasibility of {A x = b, x >= 0} is shown by y with A^T y >= 0 and b^T y < 0; found here by an
        # independent LP (variables y bounded to [-1, 1])
        from scipy.optimize import linprog
        res = linprog(b, A_ub=-a.T, b_ub=np.zeros(n), bounds=[(-1, 1)] * len(b), method="highs")
        return {"output_shape": True, "farkas_certificate_found": bool(
            res.status == 0 and res.fun < -1e-9 and (a.T @ res.x).min() >= -1e-9)}
    x, obj = output["estimates"], output["objective"]
    lam, mu = certificate.get("balance_multipliers"), certificate.get("bound_multipliers")
    num = (int, float)
    if (not isinstance(x, list) or len(x) != n or not all(type(v) in num and math.isfinite(v) for v in x)
            or type(obj) not in num or not math.isfinite(obj)):
        return {"output_shape": False}
    if (not isinstance(lam, list) or len(lam) != len(b) or not isinstance(mu, list) or len(mu) != n
            or not all(type(v) in num and math.isfinite(v) for v in lam + mu)):
        return {"output_shape": True, "kkt_certificate_present": False}
    x, lam, mu = np.array(x, dtype=float), np.array(lam, dtype=float), np.array(mu, dtype=float)
    feas, grad = _scales(x, m, s, a, b)
    residual = 2.0 * (x - m) / (s * s) - a.T @ lam - mu
    return {"output_shape": True, "kkt_certificate_present": True,
            "balances_hold": bool(np.abs(a @ x - b).max() <= QP_FEAS_TOL * feas),
            "non_negative": bool(x.min() >= -QP_FEAS_TOL * feas),
            "bound_multipliers_non_negative": bool(mu.min() >= -QP_KKT_TOL * grad),
            "complementarity": bool(np.abs(mu * x).max() <= QP_KKT_TOL * grad * (1 + np.abs(x).max())),
            "stationarity": bool(np.abs(residual).max() <= QP_KKT_TOL * grad),
            "objective_recomputed": abs(float(np.sum(((x - m) / s) ** 2)) - obj) <= 1e-9 * (1 + abs(obj))}


def reconcile_exhaustive(m, s, a, b):
    """Evaluation side only (n <= 12): the optimum by enumerating every set of zero bounds. Each face's exact
    solution, when non-negative and feasible, is a feasible point; the optimum lies on its own face, so the least
    objective over feasible face solutions is the optimum. Independent of the solver's active-set path."""
    import itertools
    import numpy as np
    n = len(m)
    best = None
    for k in range(n + 1):
        for zeros in itertools.combinations(range(n), k):
            free = [i for i in range(n) if i not in zeros]
            x = np.zeros(n)
            if free:
                af, s2 = a[:, free], s[free] ** 2
                lam = np.linalg.pinv((af * s2) @ af.T) @ (2 * (b - af @ m[free]))
                x[free] = m[free] + 0.5 * s2 * (af.T @ lam)
            feas = 1 + np.abs(b).max() + np.abs(a).max() * np.abs(x).max()
            if x.min() < -1e-9 * feas or np.abs(a @ x - b).max() > 1e-7 * feas:
                continue
            value = float(np.sum(((np.maximum(x, 0) - m) / s) ** 2))
            if best is None or value < best:
                best = value
    return best


def reconcile_instance(seed):
    """Balanced flow networks, hierarchical totals and budget splits with noisy (sometimes grossly wrong) measured
    values; small true values put the non-negativity bounds in play."""
    import numpy as np
    r = random.Random(f"genome:reconcile_qp:{seed}")
    kind = ("flow_network", "hierarchy_totals", "budget_split", "gross_error")[seed % 4]
    if kind in ("flow_network", "gross_error"):
        units = r.randint(3, 5)
        streams, flow = [], []                                # (from, to); -1 is the environment
        index = {}

        def stream(f, t):
            if (f, t) not in index:
                index[f, t] = len(streams)
                streams.append((f, t))
                flow.append(0.0)
            return index[f, t]
        for _ in range(r.randint(3, 5)):                      # true flows: a sum of environment-to-environment paths
            path = [-1] + r.sample(range(units), r.randint(1, units)) + [-1]
            amount = r.choice((r.uniform(0.0, 3.0), r.uniform(5, 100)))
            for f, t in zip(path, path[1:]):
                if len(streams) < 12 or (f, t) in index:
                    flow[stream(f, t)] += amount
        for _ in range(r.randint(1, 3)):                      # idle streams: true flow zero
            f, t = r.sample(range(-1, units), 2)
            if len(streams) < 12:
                stream(f, t)
        n = len(streams)
        a = np.zeros((units, n))
        for j, (f, t) in enumerate(streams):
            if f >= 0:
                a[f, j] -= 1
            if t >= 0:
                a[t, j] += 1
        true = np.array(flow)
        if np.abs(a @ true).max() > 1e-9:                     # a path cut short by the stream cap: rebalance it away
            # fall back to one path through every unit plus an idle recycle stream
            path = [-1] + list(range(units)) + [-1]
            streams = [(f, t) for f, t in zip(path, path[1:])] + [(units - 1, 0)]
            n = len(streams)
            a = np.zeros((units, n))
            for j, (f, t) in enumerate(streams):
                if f >= 0:
                    a[f, j] -= 1
                if t >= 0:
                    a[t, j] += 1
            true = np.array([r.uniform(5, 100)] * (units + 1) + [0.0])
        b = np.zeros(units)
    elif kind == "hierarchy_totals":
        groups = r.randint(2, 3)
        sizes = [r.randint(2, 3) for _ in range(groups)]
        n = 1 + groups + sum(sizes)
        true = np.zeros(n)
        a = np.zeros((1 + groups, n))
        col = 1 + groups
        for g, size in enumerate(sizes):
            leaves = [r.choice((0.0, r.uniform(0, 2), r.uniform(10, 200))) for _ in range(size)]
            true[col:col + size] = leaves
            true[1 + g] = sum(leaves)
            a[1 + g, 1 + g] = -1
            a[1 + g, col:col + size] = 1
            col += size
        true[0] = true[1:1 + groups].sum()
        a[0, 0] = -1
        a[0, 1:1 + groups] = 1
        b = np.zeros(1 + groups)
    else:
        n = r.randint(6, 12)
        true = np.array([r.choice((0.0, r.uniform(0, 3), r.uniform(5, 80))) for _ in range(n)])
        a = np.ones((1, n))
        b = np.array([float(true.sum())])
        if r.random() < 0.5:                                  # a second known sub-budget
            k = r.randint(2, n - 2)
            row = np.zeros(n)
            row[:k] = 1
            a = np.vstack([a, row])
            b = np.append(b, true[:k].sum())
    s = np.array([max(0.5, 0.05 * v + r.uniform(0.2, 2.0)) for v in true])
    meas = true + np.array([r.gauss(0, sd) for sd in s])
    if kind == "gross_error":
        j = r.randrange(n)
        meas[j] += r.choice((-1, 1)) * r.uniform(5, 10) * s[j]
    data = {"measured_values": [round(float(v), 6) for v in meas], "std_devs": [round(float(v), 6) for v in s],
            "balance_matrix": [[float(v) for v in row] for row in a], "balance_rhs": [round(float(v), 6) for v in b]}
    m, s, a, b = _qp_input(data)
    return data, {"optimum": reconcile_exhaustive(m, s, a, b), "true_values": [float(v) for v in true]}


def reconcile_subregion(data):
    m, s, a, b = _qp_input(data)
    if len(b) <= 2 and (a[0] == 1).all():
        return "budget_split"
    return "balanced_network" if (b == 0).all() else "other_balances"


def reconcile_score(data, truth, output):
    import numpy as np
    if not isinstance(output, dict) or not isinstance(output.get("estimates"), list):
        return {"quality": 0.0, "category": "abstain"}
    m, s, a, b = _qp_input(data)
    try:
        x = np.array(output["estimates"], dtype=float)
    except (TypeError, ValueError):
        return {"quality": -1.0, "category": "wrong"}
    if x.shape != m.shape or not np.isfinite(x).all() or truth["optimum"] is None:
        return {"quality": -1.0, "category": "wrong"}
    feas = 1 + np.abs(b).max() + np.abs(a).max() * np.abs(x).max()
    if np.abs(a @ x - b).max() > 1e-6 * feas or x.min() < -1e-6 * feas:
        return {"quality": -1.0, "category": "wrong"}         # violates the balances or a bound
    value = float(np.sum(((x - m) / s) ** 2))
    claimed = output.get("objective")
    if type(claimed) in (int, float) and abs(claimed - value) > 1e-6 * (1 + abs(value)):
        return {"quality": -1.0, "category": "wrong"}
    q = (truth["optimum"] + 1e-9) / (value + 1e-9)
    return {"quality": min(q, 1.0), "category": "correct" if value <= truth["optimum"] * (1 + 1e-6) + 1e-9
            else "wrong"}


def reconcile_projection_clip(data):
    """Baseline: the textbook closed form (weighted projection of the measurements onto the balances, ignoring the
    bounds), with negative estimates clipped to zero as practitioners do; clipping breaks the balances."""
    import numpy as np
    m, s, a, b = _qp_input(data)
    s2 = s ** 2
    lam = np.linalg.pinv((a * s2) @ a.T) @ (2 * (b - a @ m))
    x = np.maximum(m + 0.5 * s2 * (a.T @ lam), 0.0)
    return {"feasible": True, "estimates": [float(v) for v in x], "objective": _qp_objective(x, m, s)}


def reconcile_slsqp(data):
    """Competitor: SciPy SLSQP on the same QP (analytic gradient, ftol 1e-12, 1000 iterations) from the clipped
    measurements; the general-purpose practitioner route."""
    import numpy as np
    from scipy.optimize import minimize
    m, s, a, b = _qp_input(data)
    w = 1 / s ** 2
    res = minimize(lambda x: float(np.sum(w * (x - m) ** 2)), np.maximum(m, 0), jac=lambda x: 2 * w * (x - m),
                   method="SLSQP", bounds=[(0, None)] * len(m),
                   constraints=[{"type": "eq", "fun": lambda x: a @ x - b, "jac": lambda x: a}],
                   options={"ftol": 1e-12, "maxiter": 1000})
    if not res.success:
        return None
    x = np.maximum(res.x, 0.0)
    return {"feasible": True, "estimates": [float(v) for v in x], "objective": _qp_objective(x, m, s)}


# =================================================================== 4. modularity community detection
CD_MAX_NODES, CD_MAX_EDGES, CD_NATIVE_NODES, CD_NATIVE_EDGES = 5000, 50000, 2000, 20000
CD_RESTARTS = 5
CD_MOVE_TOL = 1e-12


def _network(data):
    """(sorted node names, {(u, v): weight} with u < v)."""
    edges = _mapping(data).get("network_edges")
    if not isinstance(edges, list) or not 1 <= len(edges) <= CD_MAX_EDGES:
        raise GenomeError(f"network_edges: 1-{CD_MAX_EDGES} [u, v, weight] triples")
    out = {}
    for e in edges:
        if not isinstance(e, list) or len(e) != 3:
            raise GenomeError("edge: [u, v, weight]")
        u, v, w = e
        if not all(isinstance(x, str) and 0 < len(x) <= NAME_MAX for x in (u, v)) or u == v:
            raise GenomeError("edge ends: distinct node names of 1-64 characters")
        w = finite(w, low=1e-9, high=1e9, name="edge weight")
        key = (u, v) if u < v else (v, u)
        if key in out:
            raise GenomeError(f"duplicate edge {key}")
        out[key] = w
    nodes = sorted({x for k in out for x in k})
    if len(nodes) > CD_MAX_NODES:
        raise GenomeError(f"at most {CD_MAX_NODES} nodes")
    return nodes, out


def _modularity(nodes, edges, communities):
    """Independent recomputation: Q = sum_c [L_c / m - (D_c / 2m)^2]."""
    where = {v: k for k, c in enumerate(communities) for v in c}
    m = sum(edges.values())
    inside = [0.0] * len(communities)
    degree = [0.0] * len(communities)
    for (u, v), w in edges.items():
        degree[where[u]] += w
        degree[where[v]] += w
        if where[u] == where[v]:
            inside[where[u]] += w
    return sum(inside[k] / m - (degree[k] / (2 * m)) ** 2 for k in range(len(communities)))


def _canonical_communities(groups):
    return sorted(sorted(g) for g in groups if g)


def _local_moves(nodes, edges, groups):
    """Solver-side polish: move single nodes while a move raises modularity."""
    adj = {v: {} for v in nodes}
    for (u, v), w in edges.items():
        adj[u][v] = w
        adj[v][u] = w
    k = {v: sum(adj[v].values()) for v in nodes}
    m = sum(edges.values())
    label = {v: i for i, g in enumerate(groups) for v in g}
    tot = {}
    for v in nodes:
        tot[label[v]] = tot.get(label[v], 0.0) + k[v]
    size = {}
    for v in nodes:
        size[label[v]] = size.get(label[v], 0) + 1
    fresh = len(groups)
    moves = 0
    for _ in range(100):
        changed = False
        for v in nodes:
            a = label[v]
            links = {}
            for u, w in adj[v].items():
                links[label[u]] = links.get(label[u], 0.0) + w
            k_va = links.get(a, 0.0)
            options = [(c, k_vc) for c, k_vc in links.items() if c != a]
            if size[a] > 1:
                options.append((None, 0.0))
            best, gain = a, 1e-13
            for c, k_vc in options:
                d_c = 0.0 if c is None else tot[c]
                delta = (k_vc - k_va) / m - k[v] * (d_c - tot[a] + k[v]) / (2 * m * m)
                if delta > gain:
                    best, gain = c, delta
            if best != a:
                if best is None:
                    best, fresh = fresh, fresh + 1
                tot[a] -= k[v]
                size[a] -= 1
                tot[best] = tot.get(best, 0.0) + k[v]
                size[best] = size.get(best, 0) + 1
                label[v] = best
                changed = True
                moves += 1
        if not changed:
            break
    out = {}
    for v in nodes:
        out.setdefault(label[v], []).append(v)
    return list(out.values()), moves


def community_solve(data, budget):
    import networkx as nx
    nodes, edges = _network(data)
    if len(nodes) > CD_NATIVE_NODES or len(edges) > CD_NATIVE_EDGES:
        return _abstain(f"more than {CD_NATIVE_NODES} nodes or {CD_NATIVE_EDGES} edges", nodes=len(nodes))
    g = nx.Graph()
    g.add_weighted_edges_from((u, v, w) for (u, v), w in edges.items())
    best, best_q, best_seed = None, -math.inf, None
    for seed in range(CD_RESTARTS):
        groups = nx.community.louvain_communities(g, weight="weight", resolution=1.0, seed=seed)
        q = nx.community.modularity(g, groups, weight="weight")
        if q > best_q + 1e-15:
            best, best_q, best_seed = groups, q, seed
    groups, moves = _local_moves(nodes, edges, [sorted(c) for c in best])
    communities = _canonical_communities(groups)
    return answer({"communities": communities, "modularity": _modularity(nodes, edges, communities)},
                  {"method": f"networkx Louvain, best of {CD_RESTARTS} seeded restarts, polished by node moves",
                   "best_seed": best_seed, "polish_moves": moves, "nodes": len(nodes), "edges": len(edges)})


def _best_single_move(nodes, edges, communities):
    """Verifier side, written apart from the solver's polish: the largest modularity change of moving one node to
    a neighbouring community or to a new singleton community."""
    where = {v: k for k, c in enumerate(communities) for v in c}
    m = sum(edges.values())
    deg = dict.fromkeys(nodes, 0.0)
    nbr = {v: [] for v in nodes}
    for (u, v), w in edges.items():
        deg[u] += w
        deg[v] += w
        nbr[u].append((v, w))
        nbr[v].append((u, w))
    total = [0.0] * len(communities)
    for v in nodes:
        total[where[v]] += deg[v]
    best = 0.0
    for v in nodes:
        home = where[v]
        to = {}
        for u, w in nbr[v]:
            to[where[u]] = to.get(where[u], 0.0) + w
        own = to.get(home, 0.0)
        for target, weight in list(to.items()) + [(-1, 0.0)]:
            if target == home or (target == -1 and len(communities[home]) == 1):
                continue
            dtarget = 0.0 if target == -1 else total[target]
            gain = (weight - own) / m - deg[v] * (dtarget - (total[home] - deg[v])) / (2 * m * m)
            best = max(best, gain)
    return best


def community_verify(data, output, certificate):
    nodes, edges = _network(data)
    if not isinstance(output, dict) or set(output) != {"communities", "modularity"} \
            or type(output["modularity"]) not in (int, float) or not isinstance(output["communities"], list) \
            or not all(isinstance(c, list) and c and all(isinstance(v, str) for v in c)
                       for c in output["communities"]):
        return {"output_shape": False}
    comms = output["communities"]
    flat = [v for c in comms for v in c]
    checks = {"output_shape": True, "partition_of_the_nodes": sorted(flat) == nodes and len(set(flat)) == len(flat),
              "canonical_order": comms == sorted(sorted(c) for c in comms)}
    if not all(checks.values()):
        checks.update(modularity_recomputed=False, no_improving_single_node_move=False)
        return checks
    checks["modularity_recomputed"] = abs(_modularity(nodes, edges, comms) - output["modularity"]) <= 1e-9
    checks["no_improving_single_node_move"] = _best_single_move(nodes, edges, comms) <= CD_MOVE_TOL
    return checks


def community_instance(seed):
    """Planted-partition graphs (stochastic block models) with balanced or skewed blocks, weights and mixing."""
    r = random.Random(f"genome:community_louvain:{seed}")
    kind = ("sbm_balanced", "sbm_skewed", "weighted", "hierarchical")[seed % 4]
    blocks = r.randint(4, 10)
    if kind == "sbm_skewed":
        sizes = [max(5, int(r.paretovariate(1.5) * 8)) for _ in range(blocks)]
        sizes = [min(s, 60) for s in sizes]
    else:
        sizes = [r.randint(10, 30) for _ in range(blocks)]
    mixing = r.uniform(0.1, 0.45)
    avg_degree = r.uniform(6, 12)
    names, block_of = [], []
    for b, size in enumerate(sizes):
        for i in range(size):
            names.append(f"m{b:02d}_{i:02d}")
            block_of.append(b)
    n = len(names)
    edges = {}
    for i in range(n):
        for j in range(i + 1, n):
            same = block_of[i] == block_of[j]
            if kind == "hierarchical":
                near = block_of[i] // 2 == block_of[j] // 2
                p = (avg_degree * (1 - mixing) / sizes[block_of[i]] if same else
                     avg_degree * mixing * (0.8 if near else 0.2) / max(1, n - sizes[block_of[i]]) * 2)
            else:
                p = (avg_degree * (1 - mixing) / sizes[block_of[i]] if same
                     else avg_degree * mixing / max(1, n - sizes[block_of[i]]))
            if r.random() < p:
                w = round(r.uniform(1, 5), 3) if kind == "weighted" else 1
                edges[(names[i], names[j])] = w
    data = {"network_edges": [[u, v, w] for (u, v), w in edges.items()]}
    nodes, e = _network(data)
    planted = {}
    for name, b in zip(names, block_of):
        if name in set(nodes):
            planted.setdefault(b, []).append(name)
    planted = _canonical_communities(planted.values())
    return data, {"planted": planted, "planted_modularity": _modularity(nodes, e, planted)}


def community_subregion(data):
    nodes, edges = _network(data)
    weighted = any(w != 1 for w in edges.values())
    return ("weighted" if weighted else "unweighted") + ("_sparse" if 2 * len(edges) < 8 * len(nodes) else "_dense")


def community_score(data, truth, output):
    if not isinstance(output, dict) or not isinstance(output.get("communities"), list):
        return {"quality": -1.0, "category": "abstain"}
    nodes, edges = _network(data)
    comms = output["communities"]
    flat = [v for c in comms if isinstance(c, list) for v in c]
    if sorted(flat) != nodes or any(not isinstance(c, list) or not c for c in comms):
        return {"quality": -2.0, "category": "wrong"}
    q = _modularity(nodes, edges, comms)
    claimed = output.get("modularity")
    if type(claimed) not in (int, float) or abs(claimed - q) > 1e-6:
        return {"quality": -2.0, "category": "wrong"}            # a false modularity claim
    return {"quality": q, "category": "correct"}


def _partition_output(nodes, edges, groups):
    communities = _canonical_communities([list(g) for g in groups])
    return {"communities": communities, "modularity": _modularity(nodes, edges, communities)}


def community_label_propagation(data):
    """Baseline: NetworkX semi-synchronous label propagation (deterministic, no modularity objective)."""
    import networkx as nx
    nodes, edges = _network(data)
    g = nx.Graph()
    g.add_weighted_edges_from((u, v, w) for (u, v), w in edges.items())
    return _partition_output(nodes, edges, nx.community.label_propagation_communities(g))


def community_greedy_modularity(data):
    """Competitor: Clauset-Newman-Moore greedy modularity agglomeration (networkx.greedy_modularity_communities)."""
    import networkx as nx
    nodes, edges = _network(data)
    g = nx.Graph()
    g.add_weighted_edges_from((u, v, w) for (u, v), w in edges.items())
    return _partition_output(nodes, edges, nx.community.greedy_modularity_communities(g, weight="weight"))


# =================================================================== 5. multistart L-BFGS-B
BB_OBJECTIVES = ("sphere", "rastrigin", "ackley", "rosenbrock", "griewank", "styblinski_tang")
BB_MAX_DIM, BB_MAX_EVALS = 30, 200_000
ST_MIN = -39.16616570377142                     # Styblinski-Tang minimum per coordinate (at z = -2.903534)


def _bb_input(data):
    data = _mapping(data)
    name = data.get("objective")
    if name not in BB_OBJECTIVES:
        raise GenomeError(f"objective: one of {BB_OBJECTIVES} (declared objectives only; no code is accepted)")
    d = bounded_int(data.get("dimension"), low=1, high=BB_MAX_DIM, name="dimension")
    lo = finite(data.get("lower"), low=-1e6, high=1e6, name="lower")
    hi = finite(data.get("upper"), low=-1e6, high=1e6, name="upper")
    if not lo < hi:
        raise GenomeError("lower < upper required")
    shift = data.get("shift")
    if not isinstance(shift, list) or len(shift) != d:
        raise GenomeError("shift: one number per dimension")
    shift = [finite(v, low=lo, high=hi, name="shift") for v in shift]
    budget = bounded_int(data.get("evaluations"), low=10, high=BB_MAX_EVALS, name="evaluations")
    seed = bounded_int(data.get("seed"), low=0, high=2**31 - 1, name="seed")
    return name, d, lo, hi, shift, budget, seed


def _bb_value(name, z):
    """Solver side, scalar Python: the declared objective of z = x - shift (minimum 0 at z = 0, except
    Styblinski-Tang, whose minimum is d * ST_MIN at z_i = -2.903534)."""
    if name == "sphere":
        return sum(v * v for v in z)
    if name == "rastrigin":
        return 10 * len(z) + sum(v * v - 10 * math.cos(2 * math.pi * v) for v in z)
    if name == "ackley":
        n = len(z)
        return (-20 * math.exp(-0.2 * math.sqrt(sum(v * v for v in z) / n))
                - math.exp(sum(math.cos(2 * math.pi * v) for v in z) / n) + 20 + math.e)
    if name == "rosenbrock":
        y = [v + 1 for v in z]
        return sum(100 * (y[i + 1] - y[i] ** 2) ** 2 + (1 - y[i]) ** 2 for i in range(len(y) - 1)) if len(y) > 1 \
            else (1 - y[0]) ** 2
    if name == "griewank":
        return 1 + sum(v * v for v in z) / 4000 - math.prod(math.cos(v / math.sqrt(i + 1)) for i, v in enumerate(z))
    return sum(v ** 4 - 16 * v * v + 5 * v for v in z) / 2


def _bb_minimum(name, d):
    return d * ST_MIN if name == "styblinski_tang" else 0.0


class _Exhausted(Exception):
    pass


def _counted(name, shift, budget):
    state = {"used": 0, "best": None, "value": math.inf}

    def f(x):
        if state["used"] >= budget:
            raise _Exhausted
        state["used"] += 1
        v = _bb_value(name, [float(a) - b for a, b in zip(x, shift)])
        if v < state["value"]:
            state["best"], state["value"] = [float(a) for a in x], v
        return v
    return f, state


def bb_multistart_solve(data, budget_spec):
    import numpy as np
    from scipy.optimize import minimize
    name, d, lo, hi, shift, budget, seed = _bb_input(data)
    f, state = _counted(name, shift, budget)
    rng = random.Random(seed)
    starts = 0
    per_start = max(20 * (d + 1), budget // 10)
    try:
        while state["used"] < budget:
            x0 = np.array([rng.uniform(lo, hi) for _ in range(d)])
            starts += 1
            minimize(f, x0, method="L-BFGS-B", bounds=[(lo, hi)] * d,
                     options={"maxfun": min(per_start, budget - state["used"]), "ftol": 1e-15, "gtol": 1e-12})
    except _Exhausted:
        pass
    if state["best"] is None:
        return _unknown("no evaluation within the budget")
    return answer({"x": state["best"], "value": state["value"]},
                  {"method": "multistart SciPy L-BFGS-B (finite-difference gradients) from uniform starts",
                   "evaluations_used": state["used"], "evaluation_budget": budget, "starts": starts,
                   "per_start_limit": per_start, "global_optimality": "not claimed"})


def _bb_value_vectorised(name, z):
    """Verifier side, NumPy and written apart from the solver's scalar code."""
    import numpy as np
    z = np.asarray(z, dtype=float)
    if name == "sphere":
        return float(np.dot(z, z))
    if name == "rastrigin":
        return float(10 * z.size + np.sum(z ** 2 - 10 * np.cos(2 * np.pi * z)))
    if name == "ackley":
        return float(-20 * np.exp(-0.2 * np.sqrt(np.mean(z ** 2))) - np.exp(np.mean(np.cos(2 * np.pi * z)))
                     + 20 + np.e)
    if name == "rosenbrock":
        y = z + 1
        if y.size == 1:
            return float((1 - y[0]) ** 2)
        return float(np.sum(100 * (y[1:] - y[:-1] ** 2) ** 2 + (1 - y[:-1]) ** 2))
    if name == "griewank":
        return float(1 + np.sum(z ** 2) / 4000 - np.prod(np.cos(z / np.sqrt(np.arange(1, z.size + 1)))))
    return float(0.5 * np.sum(z ** 4 - 16 * z ** 2 + 5 * z))


def bb_verify(data, output, certificate):
    name, d, lo, hi, shift, budget, seed = _bb_input(data)
    if (not isinstance(output, dict) or set(output) != {"x", "value"} or not isinstance(output["x"], list)
            or len(output["x"]) != d or not all(type(v) in (int, float) and math.isfinite(v) for v in output["x"])
            or type(output["value"]) not in (int, float) or not math.isfinite(output["value"])):
        return {"output_shape": False}
    certificate = _cert(certificate)
    used = certificate.get("evaluations_used")
    z = [a - b for a, b in zip(output["x"], shift)]
    value = _bb_value_vectorised(name, z)
    return {"output_shape": True, "inside_the_box": all(lo <= v <= hi for v in output["x"]),
            "value_recomputed": abs(value - output["value"]) <= 1e-9 * (1 + abs(value)),
            "within_the_evaluation_budget": type(used) is int and 1 <= used <= budget,
            "not_below_the_declared_minimum": output["value"] >= _bb_minimum(name, d) - 1e-9 * (1 + abs(value))}


def bb_instance(seed):
    r = random.Random(f"genome:blackbox_multistart_lbfgsb:{seed}")
    name = BB_OBJECTIVES[seed % len(BB_OBJECTIVES)]
    d = r.choice((2, 3, 5, 8, 10))
    lo, hi = {"sphere": (-5.0, 5.0), "rastrigin": (-5.12, 5.12), "ackley": (-32.768, 32.768),
              "rosenbrock": (-5.0, 10.0), "griewank": (-600.0, 600.0), "styblinski_tang": (-5.0, 5.0)}[name]
    if name == "styblinski_tang":
        shift = [round(r.uniform(-1.5, 1.5), 4) for _ in range(d)]     # keeps the minimiser inside the box
    else:
        width = hi - lo
        shift = [round(r.uniform(lo + 0.2 * width, hi - 0.2 * width), 4) for _ in range(d)]
    data = {"objective": name, "dimension": d, "lower": lo, "upper": hi, "shift": shift,
            "evaluations": 1000 * d, "seed": r.randrange(2**31)}
    return data, {"minimum": _bb_minimum(name, d)}


def bb_subregion(data):
    name = _bb_input(data)[0]
    return "unimodal" if name in ("sphere", "rosenbrock") else "multimodal"


def bb_score(data, truth, output):
    if not isinstance(output, dict) or not isinstance(output.get("x"), list):
        return {"quality": -10.0, "category": "abstain"}
    name, d, lo, hi, shift, budget, seed = _bb_input(data)
    x = output["x"]
    if (len(x) != d or not all(type(v) in (int, float) and math.isfinite(v) and lo <= v <= hi for v in x)
            or type(output.get("value")) not in (int, float)):
        return {"quality": -11.0, "category": "wrong"}
    value = _bb_value_vectorised(name, [a - b for a, b in zip(x, shift)])
    if abs(value - output["value"]) > 1e-6 * (1 + abs(value)):
        return {"quality": -11.0, "category": "wrong"}            # a false value claim
    gap = max(0.0, value - truth["minimum"])
    return {"quality": -min(9.9, math.log10(1 + gap / 1e-6) / 2), "category": "correct"}


def _bb_one_start(data):
    import numpy as np
    from scipy.optimize import minimize
    name, d, lo, hi, shift, budget, seed = _bb_input(data)
    f, state = _counted(name, shift, budget)
    try:
        minimize(f, np.full(d, (lo + hi) / 2), method="L-BFGS-B", bounds=[(lo, hi)] * d,
                 options={"maxfun": budget, "ftol": 1e-15, "gtol": 1e-12})
    except _Exhausted:
        pass
    return {"x": state["best"], "value": state["value"]} if state["best"] is not None else None


def bb_single_start(data):
    """Baseline: one L-BFGS-B start from the centre of the box with the whole budget."""
    return _bb_one_start(data)


def bb_differential_evolution(data):
    """Competitor: SciPy differential evolution (rand/1/bin, population 10 per dimension, no polish) under the same
    evaluation budget - #179's ``blackbox`` family's mechanism."""
    from scipy.optimize import differential_evolution
    name, d, lo, hi, shift, budget, seed = _bb_input(data)
    f, state = _counted(name, shift, budget)
    per_generation = 10 * d
    try:
        differential_evolution(f, [(lo, hi)] * d, maxiter=max(1, budget // per_generation - 1), popsize=10,
                               seed=seed, polish=False, tol=0, atol=0, workers=1, updating="immediate")
    except _Exhausted:
        pass
    return {"x": state["best"], "value": state["value"]} if state["best"] is not None else None


# =================================================================== registration
_DEV = "development seeds 0-9 only (admission --dev; not admission evidence): "

INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.sat.weighted_maxsat", version="1.0.0", family="maxsat_cpsat", layer=3,
            operation="weighted_maxsat", epistemic_class="constraint_feasibility",
            subgeometry="weighted partial MaxSAT over Boolean propositions: hard clauses must hold, soft clauses "
                        "carry violation weights (claim reconciliation, rule-consistent belief selection)",
            source_provenance="Cook (1971); MaxSAT as a 0/1 program; OR-Tools CP-SAT (Apache-2.0); Z3 (MIT) for "
                              "the independent check",
            native_representation="DIMACS-style integer literals: clauses with null weight (hard) or a positive "
                                  "integer weight (soft)",
            required_inputs=("num_vars", "clauses", "clause_weights"),
            output_contract={"feasible": "bool", "assignment": "[0|1 per variable] or null",
                             "violated": "[soft clause index] or null", "violated_weight": "int or null"},
            algorithm_or_runtime="OR-Tools CP-SAT (one worker, fixed seed) with one relaxation literal per soft "
                                 "clause, minimising violated weight",
            parameters={"native_vars": MS_NATIVE_VARS, "native_clauses": MS_NATIVE_CLAUSES},
            composition_inputs=("claims with source reliabilities as weights", "rules as hard clauses"),
            composition_outputs=("consistent assignment", "violated (rejected) claims", "violated weight"),
            evidence_type="optimality_certificate",
            verification_method="the violated clauses and their weight recomputed from the returned assignment; "
                                "every hard clause checked; Z3 (a different engine) must prove that no assignment "
                                "satisfying the hard clauses violates less weight (pseudo-Boolean bound), or that the "
                                "hard clauses are unsatisfiable when infeasibility is claimed; the assignment must "
                                "be the one the certificate's witness digest names",
            confidence_semantics="exact optimum of the supplied clauses, proven by an independent solver's UNSAT "
                                 "answer (a solver verdict, not a checkable proof object)",
            resource_profile="NP-hard; CP-SAT and Z3 times grow exponentially in the worst case; <= 200 variables "
                             "and 3000 clauses native",
            latency_profile="milliseconds to a second at benchmark size; the Z3 check dominates",
            known_strengths=("exact with an independent second-engine proof",
                             "hard rules and weighted evidence in one model: the rejected claims are named",
                             "proves infeasibility of contradictory hard rules instead of failing silently"),
            known_failure_modes=("weights are the caller's: miscalibrated source reliabilities give a confident "
                                 "wrong reconciliation",
                                 "the optimality check trusts Z3's UNSAT verdict; no DRAT/VeriPB proof is checked",
                                 "with ties one of several optimal assignments is returned",
                                 "exponential worst case: hard random instances near the phase transition can time "
                                 "out (UNKNOWN)"),
            counterindications=("continuous or numeric claims (use reconcile_qp)",
                                "probabilistic beliefs needing posteriors rather than one consistent world (use a "
                                "Bayesian model)",
                                "very large instances (> 200 variables) without a time budget"),
            abstention_conditions=(f"more than {MS_NATIVE_VARS} variables or {MS_NATIVE_CLAUSES} clauses",
                                   "UNKNOWN when CP-SAT does not prove optimality within the latency budget"),
            benchmark_suite="claims-and-rules reconciliation (sources of known reliability, implication rules true "
                            "in a hidden world), over-constrained random 3-SAT, planted-satisfiable hard 3-SAT with "
                            "weighted soft 2-clauses, and mixed-width soft clauses with at-most-one hard groups; "
                            "25-60 variables; truth by SciPy HiGHS on the 0/1 program (a third engine); seeds 0-9 "
                            "dev, held-out seeds fixed by the admission freeze",
            baseline="weighted-polarity assignment improved by single-variable flips (abstains when a hard clause "
                     "stays violated)",
            competitor="Z3 Optimize (MaxRes core-guided MaxSAT) with soft constraints", dependency="ortools",
            **_common()),
        solve=maxsat_solve, verify=maxsat_verify, instance=maxsat_instance, score=maxsat_score,
        baseline=maxsat_greedy, competitor=maxsat_z3_optimize, subregion=maxsat_subregion, tolerance=1e-12),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.or.bin_packing", version="1.0.0", family="binpack_cpsat", layer=3,
            operation="bin_packing_min_bins", epistemic_class="optimization",
            subgeometry="one-dimensional bin packing: integer item sizes into the fewest bins of one capacity",
            source_provenance="Martello and Toth (1990) L2 bound; Johnson (1973) first-fit decreasing; OR-Tools "
                              "CP-SAT (Apache-2.0); SciPy HiGHS (MIT) for the independent check",
            native_representation="item sizes and one bin capacity (integers)",
            required_inputs=("item_sizes", "bin_capacity"),
            output_contract={"bins": "int", "packing": "[[item index]] canonical (sorted bins, sorted by first)"},
            algorithm_or_runtime="first-fit decreasing; when it misses the volume bound, OR-Tools CP-SAT on the "
                                 "assignment model with decreasing-size symmetry breaking and the FFD upper bound",
            parameters={"native_items": BP_NATIVE_ITEMS},
            composition_inputs=("job or file sizes", "worker or container capacity"),
            composition_outputs=("minimum number of bins", "packing"),
            evidence_type="optimality_certificate",
            verification_method="every item packed exactly once, loads within capacity and canonical order by "
                                "arithmetic; optimality by an independent Martello-Toth L2 lower bound written in the "
                                "verifier, and when L2 is below the bin count by SciPy HiGHS proving the instance "
                                "does not fit in one bin fewer",
            confidence_semantics="exact minimum number of bins for the supplied sizes, certified by a lower bound or "
                                 "by a second engine's infeasibility verdict",
            resource_profile="NP-hard; assignment model O(items x bins) Booleans; <= 150 items native",
            latency_profile="microseconds when FFD meets the volume bound; up to seconds otherwise",
            known_strengths=("exact with a checkable lower-bound certificate on most instances",
                             "first-fit decreasing answers at once when it meets the volume bound"),
            known_failure_modes=("one dimension only: memory and CPU together need vector packing",
                                 "sizes are the caller's point estimates",
                                 "instances whose optimum exceeds L2 rely on HiGHS's infeasibility verdict and can "
                                 "time out (the check then fails)",
                                 "the assignment model is symmetric; large hard instances can time out (UNKNOWN)"),
            counterindications=("multi-dimensional or conflicting items (vector packing / graph colouring)",
                                "makespan on a fixed number of machines (a scheduling problem)",
                                "more than 150 items without a time budget"),
            abstention_conditions=(f"more than {BP_NATIVE_ITEMS} items",
                                   "UNKNOWN when CP-SAT does not prove the minimum within the latency budget"),
            benchmark_suite="planted perfect cuts, Falkenauer-style triplets, planted bins with total slack under one "
                            "bin, and one large item plus small pieces per bin; 8-18 planted bins of capacity 100, "
                            "150 or 1000 (optimum known by construction: the volume bound equals the planted count); "
                            "seeds 0-9 dev, held-out seeds fixed by the admission freeze",
            baseline="first-fit decreasing",
            competitor="SciPy HiGHS branch-and-cut on the assignment model with the same symmetry breaking and "
                       "cardinality cut (bins-used objective, 10 s limit)",
            dependency="ortools", **_common()),
        solve=binpack_solve, verify=binpack_verify, instance=binpack_instance, score=binpack_score,
        baseline=binpack_ffd, competitor=binpack_highs, subregion=binpack_subregion, tolerance=1e-12),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.convex.measurement_reconciliation", version="1.0.0", family="reconcile_qp",
            layer=3, operation="reconcile_measurements", epistemic_class="estimate",
            subgeometry="weighted least-squares reconciliation of measured values against linear balances with "
                        "non-negativity (a strictly convex QP): data reconciliation of flows, totals and budgets",
            source_provenance="Kuehn and Davidson (1961) data reconciliation; Nocedal and Wright (2006) primal "
                              "active-set QP; SciPy HiGHS LP for the feasible start",
            native_representation="measured values with standard deviations, balance matrix and right-hand side",
            required_inputs=("measured_values", "std_devs", "balance_matrix", "balance_rhs"),
            output_contract={"feasible": "bool", "estimates": "[float] or null", "objective": "float or null"},
            algorithm_or_runtime="HiGHS LP phase one, then a primal active-set method whose steps are exact KKT face "
                                 "solves (NumPy least squares); infeasibility reported when phase one finds no point",
            parameters={"feasibility_tolerance": QP_FEAS_TOL, "kkt_tolerance": QP_KKT_TOL},
            composition_inputs=("inconsistent estimates from several sources", "known identities between them"),
            composition_outputs=("reconciled estimates", "chi-square objective", "balance multipliers"),
            evidence_type="optimality_certificate",
            verification_method="KKT certificate recomputed in NumPy: balances hold, estimates non-negative, bound "
                                "multipliers non-negative, complementarity and stationarity of the weighted objective "
                                "within stated relative tolerances, objective recomputed; the problem is strictly "
                                "convex so KKT is sufficient; claimed infeasibility needs a Farkas vector found by an "
                                "independent LP",
            confidence_semantics="the optimum to the stated tolerances under the caller's error model (independent "
                                 "Gaussian errors with the given standard deviations); not a statement that the "
                                 "reconciled values are true",
            resource_profile="O(iterations x (rows^2 n + rows^3)); <= 500 values",
            latency_profile="milliseconds at benchmark size",
            known_strengths=("exact optimum with a checkable certificate (multipliers)",
                             "respects non-negativity where the textbook closed form goes negative",
                             "the objective is a chi-square statistic: large values flag gross errors"),
            known_failure_modes=("assumes independent errors with known standard deviations",
                                 "a gross measurement error is spread over its balance rather than isolated",
                                 "degenerate (dependent) balances can stall the active set (UNKNOWN)"),
            counterindications=("correlated errors (needs a full covariance)", "nonlinear balances (energy, "
                                "component balances with concentrations)", "gross-error identification as the "
                                "goal (needs a test such as the measurement test)"),
            abstention_conditions=("UNKNOWN when the active-set iteration limit is reached or a face solve loses "
                                   "feasibility",),
            benchmark_suite="process flow networks, two-level hierarchical totals and budget splits with 6-12 values, "
                            "noisy measurements, small true values that activate bounds and one gross error in a "
                            "quarter of instances; truth by exhaustive enumeration of every set of zero bounds "
                            "(independent of the active-set path); seeds 0-9 dev, held-out seeds fixed by the "
                            "admission freeze",
            baseline="the textbook closed form (weighted projection onto the balances) with negatives clipped to zero",
            competitor="SciPy SLSQP on the same QP (analytic gradient, ftol 1e-12)", dependency="scipy",
            **_common()),
        solve=reconcile_solve, verify=reconcile_verify, instance=reconcile_instance, score=reconcile_score,
        baseline=reconcile_projection_clip, competitor=reconcile_slsqp, subregion=reconcile_subregion,
        tolerance=1e-6),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.graph.modularity_communities", version="1.0.0", family="community_louvain",
            layer=3, operation="detect_communities", epistemic_class="optimization",
            subgeometry="modularity community detection on undirected weighted graphs (module structure of "
                        "dependency or collaboration networks)",
            source_provenance="Newman and Girvan (2004) modularity; Blondel et al. (2008) Louvain as in "
                              "networkx.community.louvain_communities (BSD-3)",
            native_representation="undirected weighted edge list [u, v, weight] with string node names",
            required_inputs=("network_edges",),
            output_contract={"communities": "[[node]] canonical", "modularity": "float"},
            algorithm_or_runtime=f"networkx Louvain, best of {CD_RESTARTS} seeded restarts, then node-level local "
                                 "moves until none raises modularity",
            parameters={"restarts": CD_RESTARTS, "resolution": 1.0, "native_nodes": CD_NATIVE_NODES},
            composition_inputs=("dependency or interaction graph",),
            composition_outputs=("modules", "modularity"),
            evidence_type="heuristic_trace",
            verification_method="partition of the node set and canonical order checked; modularity recomputed by an "
                                "independent formula; no single-node move (to a neighbouring community or a new one) "
                                "may raise modularity, computed by verifier code apart from the solver's polish",
            confidence_semantics="a valid, single-move locally optimal partition with exactly the stated modularity; "
                                 "not the maximum modularity (NP-hard), and modularity is not ground truth",
            resource_profile="near-linear per Louvain pass; <= 2000 nodes native",
            latency_profile="tens of milliseconds at benchmark size",
            known_strengths=("fast and widely validated", "the local-move polish removes Louvain's misplaced nodes",
                             "checkable claim: every number is recomputed"),
            known_failure_modes=("modularity resolution limit: small modules merge in large graphs",
                                 "degenerate optimum landscape: different seeds give different partitions",
                                 "a high modularity does not mean the modules are meaningful"),
            counterindications=("directed dependency analysis where direction matters (use a DAG method)",
                                "overlapping communities", "graphs with fewer than ~20 nodes (eyeball it)"),
            abstention_conditions=(f"more than {CD_NATIVE_NODES} nodes or {CD_NATIVE_EDGES} edges",),
            benchmark_suite="stochastic block models (balanced, Pareto-skewed, weighted, two-level hierarchical) with "
                            "4-10 planted blocks, mixing 0.1-0.45 and mean degree 6-12; quality is the recomputed "
                            "modularity, the planted partition's modularity is reported; seeds 0-9 dev, held-out "
                            "seeds fixed by the admission freeze",
            baseline="networkx semi-synchronous label propagation",
            competitor="Clauset-Newman-Moore greedy modularity (networkx.greedy_modularity_communities)",
            dependency="networkx", **_common()),
        solve=community_solve, verify=community_verify, instance=community_instance, score=community_score,
        baseline=community_label_propagation, competitor=community_greedy_modularity, subregion=community_subregion,
        tolerance=1e-9),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.continuous.multistart_lbfgsb", version="1.0.0",
            family="blackbox_multistart_lbfgsb", layer=3, operation="continuous_minimize",
            epistemic_class="optimization",
            subgeometry="bound-constrained minimisation of a declared smooth or rugged continuous objective under a "
                        "function-evaluation budget",
            source_provenance="Byrd, Lu, Nocedal and Zhu (1995) L-BFGS-B as in scipy.optimize (BSD-3); multistart "
                              "global optimisation; #179's acquisition target (beat DE 26-8, p = 0.0015, post hoc)",
            native_representation="a declared objective name, dimension, box, shift, evaluation budget and seed",
            required_inputs=("objective", "dimension", "lower", "upper", "shift", "evaluations", "seed"),
            output_contract={"x": "[float]", "value": "float"},
            algorithm_or_runtime="uniform random starts, each a SciPy L-BFGS-B run (finite-difference gradients) "
                                 "capped at a tenth of the budget; best point kept; stops exactly at the budget",
            parameters={"per_start": "max(20 (d + 1), budget / 10)", "max_dimension": BB_MAX_DIM},
            composition_inputs=("declared objective",), composition_outputs=("best point", "value"),
            evidence_type="heuristic_trace",
            verification_method="the objective re-evaluated at the returned point by an independent vectorised "
                                "implementation; the point inside the box; evaluations within the budget; the value "
                                "not below the declared minimum",
            confidence_semantics="the returned point has exactly the stated value; no claim of global optimality",
            resource_profile="exactly the declared evaluation budget plus L-BFGS-B overhead",
            latency_profile="tens to hundreds of milliseconds at benchmark size",
            known_strengths=("exploits smoothness: fast local convergence on smooth basins",
                             "restarts recover from local minima on moderately multimodal landscapes"),
            known_failure_modes=("finite-difference gradients mislead on noisy or discontinuous objectives",
                                 "highly multimodal landscapes in many dimensions (Rastrigin d >= 8) defeat a "
                                 "budgeted multistart", "no global optimality guarantee"),
            counterindications=("noisy or discontinuous objectives (use a derivative-free method)",
                                "integer or categorical decisions (use CP-SAT or MILP)",
                                "objectives with known structure (use the exact solver for that structure)"),
            abstention_conditions=("UNKNOWN when no evaluation fits the budget",),
            benchmark_suite="shifted sphere, Rastrigin, Ackley, Rosenbrock, Griewank and Styblinski-Tang in 2-10 "
                            "dimensions with 1000 evaluations per dimension; quality is the log gap to the known "
                            "minimum; seeds 0-9 dev, held-out seeds fixed by the admission freeze",
            baseline="one L-BFGS-B start from the centre of the box with the whole budget",
            competitor="SciPy differential evolution (rand/1/bin, popsize 10, no polish) at the same budget, #179's "
                       "blackbox mechanism", dependency="scipy", **_common()),
        solve=bb_multistart_solve, verify=bb_verify, instance=bb_instance, score=bb_score,
        baseline=bb_single_start, competitor=bb_differential_evolution, subregion=bb_subregion, tolerance=0.05),
]
