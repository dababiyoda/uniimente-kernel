"""Layer 3 intelligences, strategic pack B: repeated games, Nash bargaining and credible commitment.

The 2026-10-21 coverage record (``docs/collaboration/MIND-COVERAGE-2026-10-21.md``) lists repeated games,
bargaining models and credible commitment analysis as ABSENT. Three executables on GREG's one cognition path
(``greg.cognition.cortex.reason`` -> isolated worker -> independent verifier -> CognitiveReceipt), each an
ordinary, well-understood method with a stated, checkable objective:

* ``game_repeated_sustain`` (``repeated_game_sustainability``): for a two-player stage game repeated forever with a
  common discount factor, the smallest discount delta* at which a declared pure target profile is a subgame-perfect
  equilibrium path under Friedman's (1971) grim trigger: any unilateral deviation is punished by reverting forever
  to one stage Nash equilibrium (pure or mixed), the one that makes delta* smallest. By the one-shot deviation
  principle the condition is exact and closed-form, player by player: delta >= (d - v) / (d - e), with v the
  target payoff, d the best one-shot deviation payoff and e the punishment payoff. The genome is therefore an
  exact calculation, not a search; what it adds is the exact stage-equilibrium set (support enumeration in rational
  arithmetic, reused from ``strategic``), the minimisation over punishments and an exact certificate. Verified by
  an independent Z3 enumeration of every support pair that hosts a stage equilibrium (unequal supports included)
  and an exact recomputation of delta*.
* ``game_nash_bargaining`` (``nash_bargaining_solution``): the Nash (1950) bargaining solution of a two- or three-
  player problem whose feasible set is the convex hull of declared payoff vectors, relative to a disagreement
  point: the unique feasible point maximising the product of gains. Solved by a log-barrier interior-point method
  over convex weights of the vertices, then polished by Newton's method on the affine hull of the active face.
  Certificate: the convex weights and the supporting hyperplane with normal proportional to 1 / (u - d) (the KKT
  condition of the concave log-product). Verified independently: feasibility and Pareto efficiency by SciPy HiGHS
  linear programs, the tangency condition, and that no vertex lies beyond the supporting hyperplane.
* ``game_stackelberg_commit`` (``stackelberg_commitment``): the optimal mixed strategy for a leader who commits
  before a best-responding follower (strong Stackelberg equilibrium: the follower breaks ties in the leader's
  favour), by Conitzer and Sandholm's (2006) multiple linear programs, one per follower action, solved exactly by a
  rational two-phase simplex (Bland's rule). The certificate holds, for every follower action, a dual-feasible
  point of that action's LP whose bound does not exceed the claimed leader value; the verifier checks each in exact
  rationals, plus the follower's best response and the leader value.

Everything is read-only computation: no files, network, subprocesses or environment access, and no output of any
method here creates authority. A game model is the declared payoff model; nothing here predicts what real players
will do. Development seeds 0-9 only.
"""
from __future__ import annotations

from fractions import Fraction
from itertools import combinations
import math
import random
import time

from .contract import Executable, GenomeError, IntelligenceGenome, answer, finite

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "INTENT-20261021-MIND-MAXIMUM-CONTINUATION section 4 (restore the full five-layer scope)",
           "docs/collaboration/MIND-COVERAGE-2026-10-21.md (repeated games, bargaining models, credible commitment "
           "analysis ABSENT)")
EXACT_CHARS = 4000                      # longest exact rational string a verifier parses


def _common(**kw):
    return dict(buildability="BUILDABLE_NOW", memory_model="stateless", epistemic_class="strategic", layer=3,
                learning_rule="none (competence settles per geometry through GREG outcomes)", lineage=LINEAGE, **kw)


def _abstain(reason, **certificate):
    return answer(None, {"reason": reason, **certificate}, status="ABSTAIN", missing=[reason])


def _unknown(reason, **certificate):
    return answer(None, {"reason": reason, **certificate}, status="UNKNOWN", missing=[reason])


def _obj(data):
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    return data


def _matrix(data, key, rows=None, cols=None, *, max_actions, max_abs=1e6):
    mat = data.get(key)
    if (not isinstance(mat, list) or not 1 <= len(mat) <= max_actions or not isinstance(mat[0], list)
            or not 1 <= len(mat[0]) <= max_actions):
        raise GenomeError(f"{key}: an m x n matrix with 1 <= m, n <= {max_actions}")
    m, n = (len(mat), len(mat[0])) if rows is None else (rows, cols)
    if len(mat) != m or any(not isinstance(r, list) or len(r) != n for r in mat):
        raise GenomeError(f"{key}: rectangular{'' if rows is None else ', the shape of the first matrix'}")
    return [[finite(x, low=-max_abs, high=max_abs, name=key) for x in r] for r in mat]


def _q(x):
    """Exact rational of a float payoff (a binary fraction); integers stay small."""
    return Fraction(x)


def _fs(q):
    return f"{q.numerator}/{q.denominator}" if q.denominator != 1 else str(q.numerator)


def _parse(s):
    """An exact rational from a certificate string, or None (refuses long or malformed strings)."""
    if not isinstance(s, str) or not 0 < len(s) <= EXACT_CHARS:
        return None
    try:
        num, _, den = s.partition("/")
        if not num.lstrip("-").isdigit() or (den and not den.isdigit()):
            return None
        q = Fraction(int(num), int(den) if den else 1)
    except (ValueError, ZeroDivisionError):
        return None
    return q


def _is_num(x):
    return type(x) in (int, float) and math.isfinite(x)


# =================================================================== 1. repeated games: grim-trigger sustainability
REP_MAX_ACTIONS = 6
REP_HORIZON = 5000                       # competitor's finite horizon
REP_TOL = 1e-6                           # scoring tolerance on delta*


def _rep(data):
    _obj(data)
    a = _matrix(data, "row_payoffs", max_actions=REP_MAX_ACTIONS)
    b = _matrix(data, "column_payoffs", len(a), len(a[0]), max_actions=REP_MAX_ACTIONS)
    t = data.get("target_profile")
    if (not isinstance(t, list) or len(t) != 2 or not all(type(x) is int for x in t)
            or not 0 <= t[0] < len(a) or not 0 <= t[1] < len(a[0])):
        raise GenomeError("target_profile: [row action, column action], 0-based indices")
    delta = finite(data.get("discount"), low=0.0, high=1.0, name="discount")
    if not 0.0 < delta < 1.0:
        raise GenomeError("discount: strictly between 0 and 1")
    return a, b, (t[0], t[1]), delta


def _rep_threshold(v, d, e):
    """Smallest delta in [0, 1) with (1 - delta) d + delta e <= v, or None when no delta < 1 works."""
    if d <= v:
        return Fraction(0)
    if v <= e:
        return None
    return (d - v) / (d - e)


def rep_solve(data, budget):
    from .strategic import _support_equilibria
    a, b, (ti, tj), delta = _rep(data)
    A = [[_q(x) for x in r] for r in a]
    B = [[_q(x) for x in r] for r in b]
    deadline = time.perf_counter() + max(0.05, float(budget.get("latency_s", 5.0)) * 0.8)
    found = _support_equilibria(A, B, deadline)
    if found is None:
        return _unknown("latency budget exhausted enumerating stage equilibria")
    eqs, pairs, degenerate = found
    if degenerate:
        return _abstain("degenerate stage game: equal-support enumeration may miss stage equilibria, so the "
                        "minimum over punishments is not certain", support_pairs=pairs)
    if not eqs:
        return _unknown("no stage equilibrium found")
    v = (A[ti][tj], B[ti][tj])
    dev = (max(A[k][tj] for k in range(len(A))), max(B[ti][k] for k in range(len(B[0]))))
    listed, best = [], None
    for idx, eq in enumerate(eqs):
        pay = (eq["u"], eq["v"])
        parts = [_rep_threshold(v[p], dev[p], pay[p]) for p in (0, 1)]
        thr = None if None in parts else max(parts)
        listed.append({"row_strategy": [_fs(x) for x in eq["x"]], "column_strategy": [_fs(y) for y in eq["y"]],
                       "payoff": [_fs(pay[0]), _fs(pay[1])], "threshold": None if thr is None else _fs(thr)})
        if thr is not None and (best is None or thr < best[0]):
            best = (thr, idx)
    q_delta = Fraction(delta)
    star = None if best is None else best[0]
    sustain = star is not None and q_delta >= star
    pun = None if best is None else {k: listed[best[1]][k] for k in ("row_strategy", "column_strategy", "payoff")}
    out = {"delta_star": None if star is None else float(star), "delta_star_exact": None if star is None else _fs(star),
           "sustainable": sustain, "target_payoff": [_fs(v[0]), _fs(v[1])],
           "deviation_payoff": [_fs(dev[0]), _fs(dev[1])], "punishment": pun,
           "enforceable_payoff": [_fs(v[0]), _fs(v[1])] if sustain else None}
    return answer(out, {"method": "Friedman grim trigger: exact closed-form threshold per player over every stage "
                                  "Nash equilibrium (exact rational support enumeration), minimised over punishments",
                        "stage_equilibria": listed, "support_pairs": pairs, "degenerate": False,
                        "semantics": "subgame-perfect by the one-shot deviation principle; punishment is reversion "
                                     "to one stage Nash equilibrium forever; strong inequality not required"})


def _z3_equilibria(A, B):
    """Independent (verifier and truth): every support pair hosting a stage Nash equilibrium, by Z3 over linear
    real arithmetic, one equilibrium per support pair, plus whether any is non-isolated or has unequal supports
    (then the game is treated as degenerate). Exact rationals throughout."""
    import z3
    m, n = len(A), len(A[0])
    x = [z3.Real(f"x{i}") for i in range(m)]
    y = [z3.Real(f"y{j}") for j in range(n)]
    s = [z3.Bool(f"s{i}") for i in range(m)]
    t = [z3.Bool(f"t{j}") for j in range(n)]
    u, w = z3.Real("u"), z3.Real("w")
    solver = z3.Solver()
    solver.add(z3.Sum(x) == 1, z3.Sum(y) == 1)
    for i in range(m):
        pay = z3.Sum([z3.RealVal(A[i][j]) * y[j] for j in range(n)])
        solver.add(x[i] >= 0, s[i] == (x[i] > 0), pay <= u, z3.Implies(s[i], pay == u))
    for j in range(n):
        pay = z3.Sum([z3.RealVal(B[i][j]) * x[i] for i in range(m)])
        solver.add(y[j] >= 0, t[j] == (y[j] > 0), pay <= w, z3.Implies(t[j], pay == w))

    def val(model, var):
        return Fraction(model.eval(var, model_completion=True).as_fraction())
    found, irregular = [], False
    while solver.check() == z3.sat:
        mod = solver.model()
        xs, ys = [val(mod, v) for v in x], [val(mod, v) for v in y]
        sup_s = [z3.is_true(mod.eval(v, model_completion=True)) for v in s]
        sup_t = [z3.is_true(mod.eval(v, model_completion=True)) for v in t]
        found.append({"x": xs, "y": ys, "u": val(mod, u), "v": val(mod, w)})
        if sum(sup_s) != sum(sup_t):
            irregular = True
        same = [s[i] == sup_s[i] for i in range(m)] + [t[j] == sup_t[j] for j in range(n)]
        solver.push()
        solver.add(*same, z3.Or([x[i] != z3.RealVal(xs[i]) for i in range(m)]
                                + [y[j] != z3.RealVal(ys[j]) for j in range(n)]))
        if solver.check() == z3.sat:
            irregular = True
        solver.pop()
        solver.add(z3.Not(z3.And(same)))
    return found, irregular


def rep_reference(a, b, target):
    """Independent exact delta* (verifier and truth): Z3 stage equilibria, then 1 - (v - e) / (d - e) per player."""
    A = [[Fraction(x) for x in r] for r in a]
    B = [[Fraction(x) for x in r] for r in b]
    ti, tj = target
    eqs, irregular = _z3_equilibria(A, B)
    v = [A[ti][tj], B[ti][tj]]
    d = [max(r[tj] for r in A), max(B[ti])]
    best = None
    for eq in eqs:
        need = []
        for p, e in enumerate((eq["u"], eq["v"])):
            if d[p] - v[p] <= 0:
                need.append(Fraction(0))
            elif v[p] - e <= 0:
                need = None
                break
            else:
                need.append(1 - (v[p] - e) / (d[p] - e))
        if need is not None and (best is None or max(need) < best):
            best = max(need)
    return {"delta_star": best, "irregular": irregular, "equilibria": eqs, "target_payoff": v, "deviation": d}


def _rep_shape(out):
    keys = {"delta_star", "delta_star_exact", "sustainable", "target_payoff", "deviation_payoff", "punishment",
            "enforceable_payoff"}
    return isinstance(out, dict) and set(out) == keys and isinstance(out["sustainable"], bool)


def rep_verify(data, output, certificate):
    a, b, target, delta = _rep(data)
    if not _rep_shape(output):
        return {"output_shape": False}
    checks = {"output_shape": True}
    ref = rep_reference(a, b, target)
    checks["stage_game_regular"] = not ref["irregular"]
    tp = [_parse(x) for x in output["target_payoff"]] if isinstance(output["target_payoff"], list) else [None]
    dp = [_parse(x) for x in output["deviation_payoff"]] if isinstance(output["deviation_payoff"], list) else [None]
    checks["target_payoff_exact"] = tp == ref["target_payoff"]
    checks["deviation_payoff_exact"] = dp == ref["deviation"]
    star = ref["delta_star"]
    claimed = output["delta_star_exact"]
    if star is None:
        checks["delta_star_minimal"] = claimed is None and output["delta_star"] is None and output["punishment"] is None
        checks["sustainable_verdict"] = output["sustainable"] is False and output["enforceable_payoff"] is None
        return checks
    q = _parse(claimed)
    checks["delta_star_minimal"] = q == star and _is_num(output["delta_star"]) and abs(output["delta_star"] -
                                                                                     float(star)) <= 1e-12
    # the claimed punishment must be a stage Nash equilibrium (exact) whose own threshold is the claimed delta*
    pun = output["punishment"]
    ok = isinstance(pun, dict) and set(pun) == {"row_strategy", "column_strategy", "payoff"}
    if ok:
        xs = [_parse(s) for s in pun["row_strategy"]] if isinstance(pun["row_strategy"], list) else [None]
        ys = [_parse(s) for s in pun["column_strategy"]] if isinstance(pun["column_strategy"], list) else [None]
        ok = (None not in xs and None not in ys and len(xs) == len(a) and len(ys) == len(a[0])
              and min(xs) >= 0 and min(ys) >= 0 and sum(xs) == 1 and sum(ys) == 1)
    if ok:
        A = [[Fraction(x) for x in r] for r in a]
        B = [[Fraction(x) for x in r] for r in b]
        rows = [sum(A[i][j] * ys[j] for j in range(len(ys))) for i in range(len(xs))]
        cols = [sum(B[i][j] * xs[i] for i in range(len(xs))) for j in range(len(ys))]
        e = (sum(p * r for p, r in zip(xs, rows)), sum(q_ * c for q_, c in zip(ys, cols)))
        ok = (e[0] == max(rows) and e[1] == max(cols)
              and [_parse(s) for s in pun["payoff"]] == list(e) if isinstance(pun["payoff"], list) else False)
        if ok:
            need = []
            for p in (0, 1):
                v, d = ref["target_payoff"][p], ref["deviation"][p]
                need.append(Fraction(0) if d <= v else (None if v <= e[p] else 1 - (v - e[p]) / (d - e[p])))
            ok = None not in need and max(need) == q
    checks["punishment_is_stage_nash_at_threshold"] = bool(ok)
    sustain = Fraction(delta) >= star
    checks["sustainable_verdict"] = output["sustainable"] is sustain and (
        output["enforceable_payoff"] == output["target_payoff"] if sustain else output["enforceable_payoff"] is None)
    return checks


def _rep_pure_nash(a, b):
    m, n = len(a), len(a[0])
    return [(i, j) for i in range(m) for j in range(n)
            if a[i][j] >= max(a[k][j] for k in range(m)) and b[i][j] >= max(b[i][k] for k in range(n))]


def rep_baseline(data):
    """Baseline: a one-shot deviation check at the given discount only, punishing by the first pure stage Nash
    equilibrium (row-major); no delta*. No decision when the stage game has no pure equilibrium."""
    a, b, (ti, tj), delta = _rep(data)
    pure = _rep_pure_nash(a, b)
    if not pure:
        return None
    pi, pj = pure[0]
    ok = True
    for p, (v, d, e) in enumerate(((a[ti][tj], max(r[tj] for r in a), a[pi][pj]),
                                   (b[ti][tj], max(b[ti]), b[pi][pj]))):
        if (1 - delta) * d + delta * e > v + 1e-12:
            ok = False
    return {"sustainable": ok}


def rep_competitor(data):
    """Competitor: brute-force simulation. For every stage equilibrium (support enumeration from ``strategic``) the
    conforming and best-deviating payoff streams are summed over a 5000-period horizon, and delta* is found by
    bisection (40 halvings) on the simulated incentive condition; the given discount is checked the same way."""
    from .strategic import _support_equilibria
    a, b, (ti, tj), delta = _rep(data)
    found = _support_equilibria([[_q(x) for x in r] for r in a], [[_q(x) for x in r] for r in b],
                                time.perf_counter() + 5.0)
    if found is None or not found[0]:
        return None
    v = (a[ti][tj], b[ti][tj])
    d = (max(r[tj] for r in a), max(b[ti]))

    def holds(dl, e):
        for p in (0, 1):
            conform = deviate = 0.0
            weight = 1.0
            for t in range(REP_HORIZON):
                conform += weight * v[p]
                deviate += weight * (d[p] if t == 0 else e[p])
                weight *= dl
            if deviate > conform + 1e-12 * max(1.0, abs(conform)):
                return False
        return True
    best = None
    for eq in found[0]:
        e = (float(eq["u"]), float(eq["v"]))
        if holds(0.0, e):
            star = 0.0
        elif not holds(1 - 1e-9, e):
            continue
        else:
            lo, hi = 0.0, 1 - 1e-9
            for _ in range(40):
                mid = (lo + hi) / 2
                lo, hi = (lo, mid) if holds(mid, e) else (mid, hi)
            star = hi
        if best is None or star < best[0]:
            best = (star, e)
    if best is None:
        return {"delta_star": None, "sustainable": False}
    return {"delta_star": best[0], "sustainable": holds(delta, best[1])}


def _rep_pd(r):
    s, p = r.randint(-5, 2), r.randint(3, 6)
    rr = p + r.randint(2, 8)
    t = rr + r.randint(1, 10)
    while 2 * rr <= t + s:
        t -= 1
    a = [[rr, s], [t, p]]
    return a, [list(x) for x in zip(*a)], [0, 0]


def _rep_cournot(r):
    k = r.randint(3, 5)
    alpha, c1, c2 = r.randint(18, 30), r.randint(1, 4), r.randint(1, 4)
    a = [[q1 * (alpha - 2 * (q1 + q2) - c1) for q2 in range(k)] for q1 in range(k)]
    b = [[q2 * (alpha - 2 * (q1 + q2) - c2) for q2 in range(k)] for q1 in range(k)]
    best = max(((i, j) for i in range(k) for j in range(k)), key=lambda p: (a[p[0]][p[1]] + b[p[0]][p[1]], -p[0]))
    return a, b, list(best)


def _rep_random(r, m, n):
    a = [[r.randint(0, 99) for _ in range(n)] for _ in range(m)]
    b = [[r.randint(0, 99) for _ in range(n)] for _ in range(m)]
    best = max(((i, j) for i in range(m) for j in range(n)), key=lambda p: (a[p[0]][p[1]] + b[p[0]][p[1]], -p[0]))
    return a, b, list(best)


REP_KINDS = ("prisoners_dilemma", "cournot", "random", "no_pure_nash")


def rep_instance(seed):
    r = random.Random(f"genome:game_repeated_sustain:{seed}")
    kind = REP_KINDS[seed % 4]
    for _ in range(200):
        if kind == "prisoners_dilemma":
            a, b, target = _rep_pd(r)
        elif kind == "cournot":
            a, b, target = _rep_cournot(r)
        else:
            a, b, target = _rep_random(r, r.randint(3, 5), r.randint(3, 5))
            if kind == "no_pure_nash" and _rep_pure_nash(a, b):
                continue
        ref = rep_reference(a, b, target)
        if not ref["irregular"]:
            break
    else:
        raise GenomeError("no regular instance drawn")
    delta = round(r.uniform(0.05, 0.99), 4)
    data = {"row_payoffs": a, "column_payoffs": b, "target_profile": target, "discount": delta}
    star = ref["delta_star"]
    return data, {"kind": kind, "delta_star": None if star is None else _fs(star),
                  "sustainable": star is not None and Fraction(delta) >= star}


def rep_subregion(data):
    a, b, (ti, tj), _ = _rep(data)
    if (ti, tj) in _rep_pure_nash(a, b):
        return "target_is_stage_nash"
    return "pure_punishment_available" if _rep_pure_nash(a, b) else "mixed_punishment_only"


def rep_score(data, truth, output):
    if output is None:
        return {"quality": -0.5, "category": "abstain"}
    if not isinstance(output, dict) or not isinstance(output.get("sustainable"), bool):
        return {"quality": -1.0, "category": "wrong"}
    if output["sustainable"] != truth["sustainable"]:
        return {"quality": 0.0, "category": "wrong"}
    if "delta_star" not in output:
        return {"quality": 0.5, "category": "abstain"}           # a verdict at the given discount only
    true_star, claim = truth["delta_star"], output["delta_star"]
    if true_star is None:
        good = claim is None
    else:
        good = _is_num(claim) and abs(claim - float(Fraction(true_star))) <= REP_TOL
    return {"quality": 1.0, "category": "correct"} if good else {"quality": 0.5, "category": "wrong"}


# =================================================================== 2. Nash bargaining solution
NB_MAX_VERTICES, NB_MAX_ABS = 24, 1e6
NB_TOL = 1e-9                             # verifier tolerances, relative to the payoff scale
NB_SCORE_TOL = 1e-6                       # a point within 1e-6 of the scale of the truth is correct


def _nb(data):
    _obj(data)
    verts, d = data.get("vertices"), data.get("disagreement")
    if not isinstance(d, list) or len(d) not in (2, 3):
        raise GenomeError("disagreement: a payoff vector for 2 or 3 players")
    n = len(d)
    if not isinstance(verts, list) or not 1 <= len(verts) <= NB_MAX_VERTICES:
        raise GenomeError(f"vertices: 1-{NB_MAX_VERTICES} payoff vectors")
    if any(not isinstance(v, list) or len(v) != n for v in verts):
        raise GenomeError("every vertex has one payoff per player")
    V = [[finite(x, low=-NB_MAX_ABS, high=NB_MAX_ABS, name="vertex payoff") for x in v] for v in verts]
    d = [finite(x, low=-NB_MAX_ABS, high=NB_MAX_ABS, name="disagreement payoff") for x in d]
    return V, d


def _nb_scale(V, d):
    return max([abs(x) for v in V for x in v] + [abs(x) for x in d] + [1.0])


def _nb_interior(G):
    """Convex weights whose point gives every player a positive gain, by the max-min-gain LP (HiGHS), or None when
    no feasible point strictly improves on the disagreement point for everyone."""
    import numpy as np
    from scipy.optimize import linprog
    k, n = G.shape
    c = np.concatenate([np.zeros(k), [-1.0]])
    A_ub = np.hstack([-G.T, np.ones((n, 1))])
    A_eq = np.concatenate([np.ones(k), [0.0]])[None, :]
    res = linprog(c, A_ub=A_ub, b_ub=np.zeros(n), A_eq=A_eq, b_eq=[1.0],
                  bounds=[(0, None)] * k + [(None, 1.0)], method="highs")
    if res.status != 0 or -res.fun <= 1e-12:
        return None
    w = np.clip(res.x[:k], 0, None)
    w = w / w.sum()
    return w if (G.T @ w > 0).all() else None


NB_STAGE_GAP = 1e-6                       # barrier gap at which face identification and polishing start


def _nb_barrier(G, start):
    """Log-barrier interior point over convex weights w of the vertex gains G (k x n): maximise sum log(G^T w).
    A generator: yields (w, gap) after each centring stage, the barrier parameter growing x8 per stage until the
    duality gap k / t is below 1e-13. ``start`` is a weight vector with positive gains."""
    import numpy as np
    k, n = G.shape
    eps = 0.5
    while True:
        w = (1 - eps) * start + eps / k
        if (G.T @ w > 0).all():
            break
        eps /= 2
    ones = np.ones(k)
    t = 1.0
    for _ in range(60):
        for _ in range(100):
            g = G.T @ w
            grad = -t * (G @ (1 / g)) - 1 / w
            H = t * ((G / g ** 2) @ G.T)
            H[np.diag_indices(k)] += 1 / w ** 2
            # equality-constrained Newton step (1^T step = 0) by elimination
            hg, h1 = np.linalg.solve(H, np.column_stack([-grad, ones])).T
            step = hg - h1 * (ones @ hg) / (ones @ h1)
            dec = float(-grad @ step)
            if dec / 2 < 1e-12:
                break
            s = 1.0
            phi = -t * np.sum(np.log(g)) - np.sum(np.log(w))
            while True:
                w2 = w + s * step
                g2 = G.T @ w2
                if (w2 > 0).all() and (g2 > 0).all():
                    phi2 = -t * np.sum(np.log(g2)) - np.sum(np.log(w2))
                    if phi2 <= phi - 0.25 * s * dec or s < 1e-14:
                        break
                s /= 2
            w = w2
        yield w, k / t
        if k / t < 1e-13:
            return
        t *= 8


def _nb_polish(G, w):
    """Newton on the affine hull of the active vertices; returns (gains, weights) or None if it leaves the face."""
    import numpy as np
    from scipy.optimize import nnls
    k, n = G.shape
    active = [i for i in range(k) if w[i] > 1e-6 * w.max()]
    P = G[active]
    base = P[0]
    D = (P[1:] - base).T if len(active) > 1 else np.zeros((n, 0))
    if D.shape[1]:
        U, S, _ = np.linalg.svd(D, full_matrices=False)
        B = U[:, S > 1e-10 * max(1.0, S.max())]
    else:
        B = np.zeros((n, 0))
    u = G.T @ w
    if B.shape[1] == 0:
        u = base.copy()
    else:
        s = B.T @ (u - base)
        for _ in range(60):
            x = base + B @ s
            if (x <= 0).any():
                return None
            grad = B.T @ (1 / x)
            H = -(B.T * (1 / x ** 2)) @ B
            step = np.linalg.solve(H, -grad)
            lam = 1.0
            while (base + B @ (s + lam * step) <= 0).any():
                lam /= 2
            s = s + lam * step
            if np.abs(lam * step).max() <= 1e-16 * max(1.0, np.abs(s).max()):
                break
        u = base + B @ s
    if (u <= 0).any():
        return None
    coef, resid = nnls(np.vstack([P.T, np.ones(len(active))]), np.concatenate([u, [1.0]]))
    if resid > 1e-10 * max(1.0, np.abs(G).max()):
        return None
    full = np.zeros(k)
    full[active] = coef
    return u, full


def nb_solve(data, budget):
    import numpy as np
    V, d = _nb(data)
    n = len(d)
    Va, da = np.array(V, dtype=float), np.array(d, dtype=float)
    scale = _nb_scale(V, d)
    G = (Va - da) / scale
    pos = [i for i in range(len(V)) if (G[i] > 0).all()]
    if pos:                               # a vertex that improves on disagreement for everyone is a valid start
        start = np.zeros(len(V))
        start[max(pos, key=lambda i: float(np.sum(np.log(G[i]))))] = 1.0
    else:                                 # otherwise the max-min-gain LP finds an interior start
        start = _nb_interior(G)
    if start is None:
        raise GenomeError("no feasible point gives every player strictly more than the disagreement point")
    method = "log-barrier interior point (gap 1e-13), no polished face certified"
    for w, gap in _nb_barrier(G, start):
        u = G.T @ w
        if gap > NB_STAGE_GAP:
            continue
        polished = _nb_polish(G, w)
        if polished is not None:
            pu, pw = polished
            # first-order optimality: no vertex lies beyond the hyperplane with normal 1 / gains (1/pu . pu = n)
            if float(np.max(G @ (1 / pu))) <= n * (1 + 1e-12):
                u, w = pu, pw
                method = f"log-barrier interior point to gap {gap:.1e}, Newton-polished on the active face"
                break
    normal = 1 / u
    normal = normal / normal.sum()
    point = (u * scale + da).tolist()
    gains = (u * scale).tolist()
    excess = float(np.max(G @ normal - normal @ u)) * scale
    out = {"point": point, "gains": gains, "nash_product": float(np.prod(u * scale)),
           "supporting_weights": normal.tolist(), "support_value": float(normal @ (u * scale + da))}
    weights = [[i, float(x)] for i, x in enumerate(w) if x > 1e-12]
    return answer(out, {"method": method, "convex_weights": weights, "max_vertex_excess": excess,
                        "players": n, "semantics": "maximises the product of gains over the convex hull of the "
                                                   "vertices intersected with gains > 0 (no free disposal)"})


def _nb_hull_residual(V, u):
    """Independent LP (HiGHS): the least L1 distance from u to the convex hull of V."""
    import numpy as np
    from scipy.optimize import linprog
    k, n = len(V), len(u)
    Va = np.array(V, dtype=float).T
    # variables: w (k), r+ (n), r- (n); Va w + r+ - r- = u; sum w = 1
    c = np.concatenate([np.zeros(k), np.ones(2 * n)])
    A_eq = np.vstack([np.hstack([Va, np.eye(n), -np.eye(n)]), np.concatenate([np.ones(k), np.zeros(2 * n)])])
    res = linprog(c, A_eq=A_eq, b_eq=np.concatenate([u, [1.0]]), bounds=(0, None), method="highs")
    return float(res.fun) if res.status == 0 else math.inf


def _nb_pareto_slack(V, u):
    """Independent LP (HiGHS): the largest total improvement s >= 0 with u + s in the hull."""
    import numpy as np
    from scipy.optimize import linprog
    k, n = len(V), len(u)
    Va = np.array(V, dtype=float).T
    c = np.concatenate([np.zeros(k), -np.ones(n)])
    A_eq = np.vstack([np.hstack([Va, -np.eye(n)]), np.concatenate([np.ones(k), np.zeros(n)])])
    res = linprog(c, A_eq=A_eq, b_eq=np.concatenate([u, [1.0]]), bounds=(0, None), method="highs")
    return float(-res.fun) if res.status == 0 else -math.inf


def nb_verify(data, output, certificate):
    import numpy as np
    V, d = _nb(data)
    n = len(d)
    keys = {"point", "gains", "nash_product", "supporting_weights", "support_value"}
    if (not isinstance(output, dict) or set(output) != keys or not all(
            isinstance(output[k], list) and len(output[k]) == n and all(_is_num(x) for x in output[k])
            for k in ("point", "gains", "supporting_weights"))
            or not _is_num(output["nash_product"]) or not _is_num(output["support_value"])):
        return {"output_shape": False}
    scale = _nb_scale(V, d)
    tol = NB_TOL * scale
    u, da = np.array(output["point"], dtype=float), np.array(d, dtype=float)
    gains = u - da
    lam = np.array(output["supporting_weights"], dtype=float)
    Va = np.array(V, dtype=float)
    checks = {"output_shape": True}
    checks["gains_consistent"] = bool(np.all(np.abs(gains - np.array(output["gains"])) <= tol))
    checks["individually_rational"] = bool(np.all(gains > tol))
    checks["feasible_in_hull"] = _nb_hull_residual(V, u) <= tol * n
    checks["product_consistent"] = bool(gains.min() > 0) and math.isclose(
        float(np.exp(np.sum(np.log(np.maximum(gains, 1e-300))))), output["nash_product"], rel_tol=1e-8)
    # KKT for max sum log(gain) over a convex set: the gradient 1 / gain supports the set at u
    pos = bool(np.all(lam > 0)) and abs(float(lam.sum()) - 1.0) <= 1e-9
    checks["weights_tangent"] = pos and bool(gains.min() > 0) and float(
        np.ptp(lam * gains) / max(np.abs(lam * gains).max(), 1e-300)) <= 1e-7
    checks["support_value_consistent"] = abs(float(lam @ u) - output["support_value"]) <= tol
    checks["no_vertex_beyond_supporting_hyperplane"] = pos and float(np.max(Va @ lam) - lam @ u) <= tol
    checks["pareto_efficient"] = _nb_pareto_slack(V, u) <= tol * n
    return checks


# ---- exact truth: enumerate the simplices spanned by vertex subsets (independent of the solver)
def _nb_exact_solve(rows, rhs):
    """Exact solution of a consistent (possibly overdetermined) rational system, or None if inconsistent or not
    unique."""
    t = [list(r) + [b] for r, b in zip(rows, rhs)]
    cols = len(rows[0])
    r = 0
    piv = []
    for c in range(cols):
        p = next((i for i in range(r, len(t)) if t[i][c] != 0), None)
        if p is None:
            return None
        t[r], t[p] = t[p], t[r]
        t[r] = [v / t[r][c] for v in t[r]]
        for i in range(len(t)):
            if i != r and t[i][c] != 0:
                f = t[i][c]
                t[i] = [a - f * b for a, b in zip(t[i], t[r])]
        piv.append(c)
        r += 1
    if any(row[cols] != 0 for row in t[r:]):
        return None
    return [t[i][cols] for i in range(cols)]


def nb_reference(V, d):
    """Exact Nash bargaining point: the best feasible stationary point over every simplex of 1..n vertices (the
    optimum lies in the relative interior of some such simplex and is stationary on its affine hull). Rational
    for facets and vertices; one quadratic root (SymPy, exact) on edges of a three-player problem."""
    import sympy
    n = len(d)
    Q = [[Fraction(x) for x in v] for v in V]
    D = [Fraction(x) for x in d]
    best = None

    def consider(point_exact, value):
        nonlocal best
        if best is None or value > best[1]:
            best = (point_exact, value)
    for v in Q:
        g = [v[i] - D[i] for i in range(n)]
        if all(x > 0 for x in g):
            consider([sympy.Rational(x.numerator, x.denominator) for x in v], sympy.Rational(math.prod(g)))
    for size in range(2, n + 1):
        for S in combinations(range(len(Q)), size):
            P = [Q[i] for i in S]
            if size == n:                      # a hyperplane: x_i = c' / (n a_i)
                if n == 2:
                    a = [P[1][1] - P[0][1], P[0][0] - P[1][0]]
                else:
                    e1 = [P[1][i] - P[0][i] for i in range(3)]
                    e2 = [P[2][i] - P[0][i] for i in range(3)]
                    a = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]]
                if all(x == 0 for x in a) or any(x == 0 for x in a):
                    continue
                c = sum(a[i] * (P[0][i] - D[i]) for i in range(n))
                g = [c / (n * a[i]) for i in range(n)]
                if not all(x > 0 for x in g):
                    continue
                u = [D[i] + g[i] for i in range(n)]
                lam = _nb_exact_solve([[P[k][i] for k in range(size)] for i in range(n)] + [[Fraction(1)] * size],
                                      u + [Fraction(1)])
                if lam is None or min(lam) < 0:
                    continue
                consider([sympy.Rational(x.numerator, x.denominator) for x in u], sympy.Rational(math.prod(g)))
            else:                              # an edge of a three-player problem: maximise a cubic in t on [0, 1]
                t = sympy.Symbol("t")
                g = [sympy.Rational(P[0][i] - D[i]) + sympy.Rational(P[1][i] - P[0][i]) * t for i in range(n)]
                if all(sympy.Rational(P[1][i] - P[0][i]) == 0 for i in range(n)):
                    continue
                f = sympy.expand(math.prod(g))
                for root in sympy.real_roots(sympy.Poly(sympy.diff(f, t), t)):
                    if not 0 <= root <= 1:
                        continue
                    gs = [sympy.nsimplify(x.subs(t, root)) for x in g]
                    if not all(sympy.N(x, 50) > 0 for x in gs):
                        continue
                    u = [sympy.Rational(D[i]) + gs[i] for i in range(n)]
                    consider(u, sympy.simplify(f.subs(t, root)))
    point, value = best
    return {"point": [float(sympy.N(x, 30)) for x in point], "product": float(sympy.N(value, 30))}


def nb_baseline(data):
    """Baseline: the vertex with the largest product of gains (no decision when no vertex improves on the
    disagreement point for every player)."""
    V, d = _nb(data)
    n = len(d)
    pos = [v for v in V if all(v[i] > d[i] for i in range(n))]
    if not pos:
        return None
    best = max(pos, key=lambda v: math.prod(v[i] - d[i] for i in range(n)))
    g = [best[i] - d[i] for i in range(n)]
    return {"point": list(best), "gains": g, "nash_product": math.prod(g)}


def nb_competitor(data):
    """Competitor: SciPy SLSQP maximising the log-product over convex weights of the vertices."""
    import numpy as np
    from scipy.optimize import minimize
    V, d = _nb(data)
    Va, da = np.array(V, dtype=float), np.array(d, dtype=float)
    scale = _nb_scale(V, d)
    G = (Va - da) / scale
    k = len(V)
    pos = [i for i in range(k) if (G[i] > 0).all()]
    if pos:                                  # start between the best vertex and the centroid
        best = max(pos, key=lambda i: float(np.sum(np.log(G[i]))))
        w0 = np.full(k, 0.5 / k)
        w0[best] += 0.5
        if not (G.T @ w0 > 0).all():
            w0 = np.zeros(k)
            w0[best] = 1.0
    else:                                    # no vertex improves on disagreement for everyone: a max-min start
        w0 = _nb_interior(G)
        if w0 is None:
            return None

    def f(w):
        g = G.T @ w
        return -float(np.sum(np.log(np.maximum(g, 1e-300))))

    def jac(w):
        g = np.maximum(G.T @ w, 1e-300)
        return -(G @ (1 / g))
    res = minimize(f, w0, jac=jac, method="SLSQP", bounds=[(0, 1)] * k,
                   constraints=[{"type": "eq", "fun": lambda w: np.sum(w) - 1, "jac": lambda w: np.ones(k)}],
                   options={"ftol": 1e-15, "maxiter": 1000})
    w = np.clip(res.x, 0, None)
    w = w / w.sum()
    u = G.T @ w
    if (u <= 0).any():
        return None
    g = (u * scale).tolist()
    return {"point": (u * scale + da).tolist(), "gains": g, "nash_product": math.prod(g)}


def _nb_frontier(r, n, count):
    """Integer points on a concave superellipse frontier sum (u_i / R_i)^p = 1 (p in [1.3, 3]), plus the origin:
    a utility-possibility frontier sampled at ``count`` random directions."""
    p = r.uniform(1.3, 3.0)
    radii = [r.randint(200, 1000) for _ in range(n)]
    pts = {tuple([0] * n)}
    for _ in range(count):
        x = [r.random() + 0.02 for _ in range(n)]
        s = sum(v ** p for v in x) ** (1 / p)
        pts.add(tuple(round(radii[i] * x[i] / s) for i in range(n)))
    return [list(q) for q in sorted(pts)]


def _nb_random(r, n):
    return [[r.randint(0, 100) for _ in range(n)] for _ in range(r.randint(n + 2, 10 if n == 3 else 12))]


def _nb_frontier2(r):
    return _nb_frontier(r, 2, r.randint(5, 14))


def _nb_frontier3(r):
    return _nb_frontier(r, 3, r.randint(5, 9))


NB_KINDS = ("random_2", "frontier_2", "random_3", "frontier_3")


def nb_instance(seed):
    r = random.Random(f"genome:game_nash_bargaining:{seed}")
    kind = NB_KINDS[seed % 4]
    while True:
        V = {"random_2": lambda: _nb_random(r, 2), "frontier_2": lambda: _nb_frontier2(r),
             "random_3": lambda: _nb_random(r, 3), "frontier_3": lambda: _nb_frontier3(r)}[kind]()
        n = len(V[0])
        lo = [min(v[i] for v in V) for i in range(n)]
        hi = [max(v[i] for v in V) for i in range(n)]
        d = [lo[i] + r.randint(0, max(0, (hi[i] - lo[i]) // 3)) for i in range(n)]
        if any(all(v[i] > d[i] for i in range(n)) for v in V):
            break
    data = {"vertices": V, "disagreement": d}
    return data, {"kind": kind, **nb_reference(V, d)}


def nb_subregion(data):
    V, d = _nb(data)
    return f"{len(d)}_players"


def nb_score(data, truth, output):
    if output is None:
        return {"quality": -0.5, "category": "abstain"}
    V, d = _nb(data)
    n = len(d)
    if (not isinstance(output, dict) or not isinstance(output.get("point"), list) or len(output["point"]) != n
            or not all(_is_num(x) for x in output["point"])):
        return {"quality": -1.0, "category": "wrong"}
    scale = _nb_scale(V, d)
    u = output["point"]
    gains = [u[i] - d[i] for i in range(n)]
    if min(gains) <= 0 or _nb_hull_residual(V, u) > 1e-7 * scale:
        return {"quality": -1.0, "category": "wrong"}
    if max(abs(u[i] - truth["point"][i]) for i in range(n)) <= NB_SCORE_TOL * scale:
        return {"quality": 1.0, "category": "correct"}
    return {"quality": min(1.0, math.prod(gains) / truth["product"]), "category": "wrong"}


# =================================================================== 3. credible commitment: Stackelberg leader
SC_MAX_ACTIONS, SC_MAX_ABS = 8, 1e6
SC_TOL = 1e-9                              # scoring tolerance on best responses and values, relative to the scale


def _sc(data):
    _obj(data)
    a = _matrix(data, "leader_payoffs", max_actions=SC_MAX_ACTIONS, max_abs=SC_MAX_ABS)
    b = _matrix(data, "follower_payoffs", len(a), len(a[0]), max_actions=SC_MAX_ACTIONS, max_abs=SC_MAX_ABS)
    return a, b


def _simplex(c, A_ub, b_ub, A_eq, b_eq, deadline):
    """Exact two-phase simplex (Bland's rule) over Fractions: maximise c.x s.t. A_ub x <= b_ub, A_eq x = b_eq,
    x >= 0. Returns ("optimal", x, value), ("infeasible", None, None), ("unbounded", None, None) or None on
    timeout."""
    nv = len(c)
    rows, kinds = [], []
    for r, b in zip(A_ub, b_ub):
        rows.append((list(r), b, "le"))
    for r, b in zip(A_eq, b_eq):
        rows.append((list(r), b, "eq"))
    m = len(rows)
    n_slack = sum(1 for _, _, k in rows if k == "le")
    total = nv + n_slack + m                      # originals, slacks, artificials (one per row, some unused)
    T, basis, art = [], [], []
    si = nv
    for idx, (r, b, k) in enumerate(rows):
        line = [Fraction(0)] * (total + 1)
        for j, v in enumerate(r):
            line[j] = Fraction(v)
        if k == "le":
            line[si] = Fraction(1)
            slack_col = si
            si += 1
        line[total] = Fraction(b)
        if line[total] < 0:
            line = [-v for v in line]
        if k == "le" and line[slack_col] == 1:
            basis.append(slack_col)
        else:
            col = nv + n_slack + idx
            line[col] = Fraction(1)
            basis.append(col)
            art.append(col)
        T.append(line)
        kinds.append(k)
    art_set = set(art)

    def pivot(r, col):
        p = T[r][col]
        T[r] = [v / p for v in T[r]]
        for i in range(m):
            if i != r and T[i][col] != 0:
                f = T[i][col]
                T[i] = [a - f * b for a, b in zip(T[i], T[r])]
        basis[r] = col

    def run(obj, allowed):
        while True:
            if time.perf_counter() > deadline:
                return None
            red = [obj[j] - sum(obj[basis[i]] * T[i][j] for i in range(m)) for j in range(total)]
            enter = next((j for j in range(total) if j in allowed and red[j] > 0), None)
            if enter is None:
                return "optimal"
            ratios = [(T[i][total] / T[i][enter], basis[i], i) for i in range(m) if T[i][enter] > 0]
            if not ratios:
                return "unbounded"
            pivot(min(ratios)[2], enter)
    if art:
        obj1 = [Fraction(0)] * total
        for col in art:
            obj1[col] = Fraction(-1)
        status = run(obj1, set(range(total)))
        if status is None:
            return None
        if sum(T[i][total] for i in range(m) if basis[i] in art_set) > 0:
            return ("infeasible", None, None)
        for i in range(m):                       # drive zero-level artificials out of the basis
            if basis[i] in art_set:
                col = next((j for j in range(nv + n_slack) if T[i][j] != 0), None)
                if col is not None:
                    pivot(i, col)
    allowed = set(range(nv + n_slack))
    obj2 = [Fraction(v) for v in c] + [Fraction(0)] * (total - nv)
    status = run(obj2, allowed)
    if status is None:
        return None
    if status == "unbounded":
        return ("unbounded", None, None)
    x = [Fraction(0)] * nv
    for i in range(m):
        if basis[i] < nv:
            x[basis[i]] = T[i][total]
    return ("optimal", x, sum(Fraction(ci) * xi for ci, xi in zip(c, x)))


def sc_solve(data, budget):
    a, b = _sc(data)
    A = [[_q(x) for x in r] for r in a]
    B = [[_q(x) for x in r] for r in b]
    m, n = len(A), len(A[0])
    deadline = time.perf_counter() + max(0.05, float(budget.get("latency_s", 5.0)) * 0.8)
    low = min(min(r) for r in A)
    duals = []
    for j in range(n):
        others = [k for k in range(n) if k != j]
        # dual of LP_j with z = low + z': min z' s.t. sum_k mu_k (B[i][k] - B[i][j]) + z' >= A[i][j] - low
        c = [Fraction(0)] * len(others) + [Fraction(-1)]
        A_ub = [[-(B[i][k] - B[i][j]) for k in others] + [Fraction(-1)] for i in range(m)]
        b_ub = [-(A[i][j] - low) for i in range(m)]
        res = _simplex(c, A_ub, b_ub, [], [], deadline)
        if res is None:
            return _unknown("latency budget exhausted in the dual linear programs")
        if res[0] != "optimal":
            return _unknown(f"dual LP for follower action {j} {res[0]} (unexpected)")
        mu = {k: res[1][idx] for idx, k in enumerate(others)}
        duals.append({"mu": [_fs(mu.get(k, Fraction(0))) for k in range(n)], "z": low + res[1][-1]})
    order = sorted(range(n), key=lambda j: (-duals[j]["z"], j))
    for j in order:
        others = [k for k in range(n) if k != j]
        res = _simplex([A[i][j] for i in range(m)], [[B[i][k] - B[i][j] for i in range(m)] for k in others],
                       [Fraction(0)] * len(others), [[Fraction(1)] * m], [Fraction(1)], deadline)
        if res is None:
            return _unknown("latency budget exhausted in the primal linear programs")
        if res[0] == "infeasible":
            continue
        if res[0] != "optimal" or res[2] != duals[j]["z"]:
            return _unknown("primal and dual values disagree (unexpected)")
        x, value = res[1], res[2]
        fol = sum(B[i][j] * x[i] for i in range(m))
        out = {"leader_strategy": [float(v) for v in x], "leader_strategy_exact": [_fs(v) for v in x],
               "follower_response": j, "leader_value": float(value), "leader_value_exact": _fs(value),
               "follower_value": float(fol)}
        return answer(out, {"method": "Conitzer-Sandholm multiple LPs, exact rational two-phase simplex (Bland)",
                            "dual_bounds": [{"mu": dl["mu"], "z": _fs(dl["z"])} for dl in duals],
                            "tie_breaking": "strong Stackelberg: the follower breaks ties in the leader's favour",
                            "semantics": "for every follower action k, (mu_k, z_k) is dual feasible for the LP "
                                         "'best leader value among commitments to which k is a best response', so "
                                         "z_k bounds it; every z_k is at most the leader value"})
    return _unknown("no follower action is a best response to any commitment (unexpected)")


def sc_verify(data, output, certificate):
    a, b = _sc(data)
    m, n = len(a), len(a[0])
    keys = {"leader_strategy", "leader_strategy_exact", "follower_response", "leader_value", "leader_value_exact",
            "follower_value"}
    if not isinstance(output, dict) or set(output) != keys:
        return {"output_shape": False}
    xs = [_parse(s) for s in output["leader_strategy_exact"]] if isinstance(output["leader_strategy_exact"],
                                                                            list) else [None]
    val = _parse(output["leader_value_exact"])
    j = output["follower_response"]
    shape = (len(xs) == m and None not in xs and val is not None and type(j) is int and 0 <= j < n
             and isinstance(output["leader_strategy"], list) and len(output["leader_strategy"]) == m
             and all(_is_num(v) for v in output["leader_strategy"]) and _is_num(output["leader_value"])
             and _is_num(output["follower_value"]))
    if not shape:
        return {"output_shape": True, "commitment_is_distribution": False, "follower_best_responds": False,
                "leader_value_exact": False, "dual_bounds_certify_optimality": False}
    A = [[Fraction(x) for x in r] for r in a]
    B = [[Fraction(x) for x in r] for r in b]
    fol = [sum(B[i][k] * xs[i] for i in range(m)) for k in range(n)]
    lead = sum(A[i][j] * xs[i] for i in range(m))
    checks = {"output_shape": True,
              "commitment_is_distribution": min(xs) >= 0 and sum(xs) == 1,
              "floats_match_exact": all(abs(f - float(q)) <= 1e-12 for f, q in zip(output["leader_strategy"], xs))
              and abs(output["leader_value"] - float(val)) <= 1e-12 * max(1.0, abs(float(val)))
              and abs(output["follower_value"] - float(fol[j])) <= 1e-12 * max(1.0, abs(float(fol[j]))),
              "follower_best_responds": fol[j] == max(fol),
              "leader_value_exact": lead == val}
    # optimality: a dual-feasible bound z_k <= value for every follower action k, checked exactly
    bounds = certificate.get("dual_bounds") if isinstance(certificate, dict) else None
    ok = isinstance(bounds, list) and len(bounds) == n
    if ok:
        for k, entry in enumerate(bounds):
            if not isinstance(entry, dict) or not isinstance(entry.get("mu"), list) or len(entry["mu"]) != n:
                ok = False
                break
            mu = [_parse(s) for s in entry["mu"]]
            z = _parse(entry.get("z"))
            if None in mu or z is None or min(mu) < 0 or mu[k] != 0 or z > val:
                ok = False
                break
            if any(sum(mu[q] * (B[i][q] - B[i][k]) for q in range(n)) + z < A[i][k] for i in range(m)):
                ok = False
                break
    checks["dual_bounds_certify_optimality"] = bool(ok)
    return checks


def sc_reference(a, b):
    """Independent truth: Conitzer-Sandholm in floating point with SciPy HiGHS (one LP per follower action)."""
    import numpy as np
    from scipy.optimize import linprog
    A, B = np.array(a, dtype=float), np.array(b, dtype=float)
    m, n = A.shape
    best = None
    for j in range(n):
        A_ub = np.array([B[:, k] - B[:, j] for k in range(n) if k != j]).reshape(-1, m)
        res = linprog(-A[:, j], A_ub=A_ub if len(A_ub) else None, b_ub=np.zeros(len(A_ub)) if len(A_ub) else None,
                      A_eq=np.ones((1, m)), b_eq=[1.0], bounds=(0, None), method="highs")
        if res.status == 0 and (best is None or -res.fun > best[0] + 1e-12):
            best = (-res.fun, j, res.x.tolist())
    return {"leader_value": best[0], "follower_response": best[1], "leader_strategy": best[2]}


def _sc_scale(a, b):
    return max([abs(x) for r in a for x in r] + [abs(x) for r in b for x in r] + [1.0])


def _sc_output(A, B, x, method):
    """A commitment x (Fractions) -> output with the follower's leader-favourable best response."""
    m, n = len(A), len(A[0])
    fol = [sum(B[i][k] * x[i] for i in range(m)) for k in range(n)]
    best = max(fol)
    j = max((k for k in range(n) if fol[k] == best), key=lambda k: (sum(A[i][k] * x[i] for i in range(m)), -k))
    val = sum(A[i][j] * x[i] for i in range(m))
    return {"leader_strategy": [float(v) for v in x], "leader_strategy_exact": [_fs(v) for v in x],
            "follower_response": j, "leader_value": float(val), "leader_value_exact": _fs(val),
            "follower_value": float(fol[j])}


def sc_baseline(data):
    """Baseline: the leader's best pure commitment (the follower breaks ties in the leader's favour)."""
    a, b = _sc(data)
    A = [[_q(x) for x in r] for r in a]
    B = [[_q(x) for x in r] for r in b]
    m = len(A)
    outs = [_sc_output(A, B, [Fraction(int(i == r)) for i in range(m)], "pure") for r in range(m)]
    return max(outs, key=lambda o: Fraction(o["leader_value_exact"]))


def sc_competitor(data):
    """Competitor: commit to the leader's best simultaneous-move Nash strategy (exact support enumeration from
    ``strategic``); the follower then best responds with leader-favourable ties. Its value is at least that Nash
    payoff, and the commitment value gap is the candidate's value minus it."""
    from .strategic import _support_equilibria
    a, b = _sc(data)
    A = [[_q(x) for x in r] for r in a]
    B = [[_q(x) for x in r] for r in b]
    found = _support_equilibria(A, B, time.perf_counter() + 5.0)
    if found is None or not found[0]:
        return None
    eq = max(found[0], key=lambda e: e["u"])
    return _sc_output(A, B, eq["x"], "nash")


def _sc_security(r):
    t = r.randint(3, 6)
    reward = [r.randint(1, 10) for _ in range(t)]
    penalty = [-r.randint(1, 10) for _ in range(t)]
    gain = [r.randint(1, 10) for _ in range(t)]
    loss = [-r.randint(1, 10) for _ in range(t)]
    a = [[reward[j] if i == j else penalty[j] for j in range(t)] for i in range(t)]
    b = [[loss[j] if i == j else gain[j] for j in range(t)] for i in range(t)]
    return a, b


def _sc_random(r, low, high):
    m, n = r.randint(low, high), r.randint(low, high)
    return ([[r.randint(-10, 10) for _ in range(n)] for _ in range(m)],
            [[r.randint(-10, 10) for _ in range(n)] for _ in range(m)])


def _sc_inspection(r):
    """Graded inspection: the inspector picks an intensity k of L (cost per level), the inspectee a violation level
    v of V; a violation is caught with probability k / L (payoffs scaled by L to stay integral)."""
    big_l, big_v = r.randint(2, 5), r.randint(1, 4)
    cost, harm, gain, fine = r.randint(1, 6), r.randint(2, 8), r.randint(1, 6), r.randint(2, 12)
    a = [[-cost * k * big_l - harm * v * (big_l - k) for v in range(big_v + 1)] for k in range(big_l + 1)]
    b = [[gain * v * (big_l - k) - fine * v * k for v in range(big_v + 1)] for k in range(big_l + 1)]
    return a, b


SC_KINDS = (("security", _sc_security), ("random_large", lambda r: _sc_random(r, 4, 8)),
            ("inspection", _sc_inspection), ("random_small", lambda r: _sc_random(r, 2, 3)))


def sc_instance(seed):
    r = random.Random(f"genome:game_stackelberg_commit:{seed}")
    kind, make = SC_KINDS[seed % 4]
    a, b = make(r)
    data = {"leader_payoffs": a, "follower_payoffs": b}
    return data, {"kind": kind, **sc_reference(a, b)}


def sc_subregion(data):
    a, b = _sc(data)
    pure = Fraction(sc_baseline(data)["leader_value_exact"])
    return "mixed_commitment_gain" if sc_reference(a, b)["leader_value"] > float(pure) + SC_TOL * _sc_scale(a, b) \
        else "pure_commitment_optimal"


def sc_score(data, truth, output):
    if output is None:
        return {"quality": -0.5, "category": "abstain"}
    a, b = _sc(data)
    m, n = len(a), len(a[0])
    if (not isinstance(output, dict) or not isinstance(output.get("leader_strategy"), list)
            or len(output["leader_strategy"]) != m or not all(_is_num(v) for v in output["leader_strategy"])
            or type(output.get("follower_response")) is not int or not 0 <= output["follower_response"] < n
            or not _is_num(output.get("leader_value"))):
        return {"quality": -1.0, "category": "wrong"}
    scale = _sc_scale(a, b)
    x, j = output["leader_strategy"], output["follower_response"]
    if min(x) < -1e-12 or abs(sum(x) - 1) > 1e-9:
        return {"quality": -1.0, "category": "wrong"}
    fol = [sum(b[i][k] * x[i] for i in range(m)) for k in range(n)]
    value = sum(a[i][j] * x[i] for i in range(m))
    if fol[j] < max(fol) - SC_TOL * scale or abs(value - output["leader_value"]) > SC_TOL * scale:
        return {"quality": -1.0, "category": "wrong"}
    top, low = truth["leader_value"], min(min(r) for r in a)
    if value >= top - SC_TOL * scale:
        return {"quality": 1.0, "category": "correct"}
    return {"quality": max(0.0, (value - low) / (top - low)) if top > low else 0.0, "category": "wrong"}


# =================================================================== genomes
INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.game.repeated_grim_trigger", version="1.0.0", family="game_repeated_sustain",
            operation="repeated_game_sustainability",
            subgeometry="infinitely repeated two-player stage games (up to 6 x 6 actions) with a common discount: the "
                        "least discount at which a pure target profile is a subgame-perfect path under Nash-reversion "
                        "grim trigger, and whether the given discount sustains it",
            source_provenance="Friedman (1971) Nash-reversion trigger strategies; one-shot deviation principle "
                              "(Blackwell 1965; Fudenberg and Tirole 1991, section 4.2); stage equilibria by support "
                              "enumeration (von Stengel 2002) reused from strategic.py; Z3 (MIT) on the verifier side",
            native_representation="row and column stage payoff matrices, a pure target profile and a discount factor",
            required_inputs=("row_payoffs", "column_payoffs", "target_profile", "discount"),
            output_contract={"delta_star": "float | null (null: no stage-Nash punishment sustains it)",
                             "delta_star_exact": "rational string | null", "sustainable": "bool at the given discount",
                             "target_payoff": "[rational] stage payoff of the target",
                             "deviation_payoff": "[rational] best one-shot deviation payoffs",
                             "punishment": "{row_strategy, column_strategy, payoff} the stage Nash reverted to | null",
                             "enforceable_payoff": "[rational] the average payoff the equilibrium enforces | null"},
            algorithm_or_runtime="exact rational support enumeration of the stage equilibria; per punishment and "
                                 "player the closed-form threshold (d - v) / (d - e); the minimum over punishments",
            parameters={"max_actions": REP_MAX_ACTIONS},
            composition_inputs=("payoff model", "discount factor"),
            composition_outputs=("critical discount", "sustainability verdict", "punishment profile"),
            evidence_type="exact_calculation",
            verification_method="an independent Z3 enumeration (linear real arithmetic) of every support pair that "
                                "hosts a stage equilibrium, unequal supports included, with a uniqueness check per "
                                "support; delta* recomputed exactly as 1 - (v - e) / (d - e); the claimed punishment "
                                "re-checked as an exact stage equilibrium whose threshold equals delta*",
            confidence_semantics="exact for the declared payoffs and the declared strategy class (unilateral "
                                 "deviations, reversion to one stage Nash equilibrium); a lower delta* may exist "
                                 "with harsher punishments (minmax with carrot-and-stick, Abreu 1988), which this "
                                 "genome does not search; nothing here predicts what real players will do",
            resource_profile="C(m + n, m) - 1 support pairs, each two rational solves; then O(equilibria)",
            latency_profile="milliseconds at 2 x 2 to 4 x 4; tens of milliseconds at 5 x 5",
            known_strengths=("exact rational delta*, not a bisection estimate",
                             "uses mixed stage equilibria as punishments where no pure one exists",
                             "an exact certificate: the stage equilibria, their thresholds and the chosen punishment"),
            known_failure_modes=("given the punishment the formula is analytic and exact: the genome's value over a "
                                 "careful hand calculation is only the equilibrium enumeration and the bookkeeping",
                                 "degenerate stage games: equal-support enumeration may miss equilibria, so it "
                                 "abstains", "Nash reversion is not the harshest credible punishment: optimal "
                                 "penal codes (Abreu 1988) can sustain cooperation at lower discounts",
                                 "only pure target profiles; no correlated or alternating target paths",
                                 "the simulation competitor matches it to 1e-6 except where the horizon truncation "
                                 "matters (discounts near 1)"),
            counterindications=("more than two players", "imperfect monitoring (noisy observation of actions)",
                                "finitely repeated games (backward induction applies)", "stage games above 6 x 6"),
            abstention_conditions=("degenerate stage game -> ABSTAIN", "latency budget exhausted -> UNKNOWN"),
            benchmark_suite="prisoner's dilemmas, discrete Cournot duopolies (collusive target), random 3-5 action "
                            "games (welfare-best target) and random games without a pure equilibrium; regular by an "
                            "independent Z3 screen; truth by Z3 enumeration and exact recomputation; quality: half for "
                            "the verdict at the given discount, half for delta* within 1e-6; seeds 0-9 dev, held-out "
                            "seeds fixed by the admission freeze",
            baseline="one-shot deviation check at the given discount only, punishing by the first pure stage "
                     "equilibrium; no delta*",
            competitor="brute-force simulation: discounted payoff streams over a 5000-period horizon and 40-step "
                       "bisection on the discount, over the same stage-equilibrium punishments",
            dependency="z3-solver", **_common()),
        solve=rep_solve, verify=rep_verify, instance=rep_instance, score=rep_score, baseline=rep_baseline,
        competitor=rep_competitor, subregion=rep_subregion, tolerance=1e-9),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.game.nash_bargaining", version="1.0.0", family="game_nash_bargaining",
            operation="nash_bargaining_solution",
            subgeometry="two- and three-player bargaining over the convex hull of declared payoff vectors (up to 24) "
                        "relative to a disagreement point",
            source_provenance="Nash (1950) bargaining solution; KKT conditions of the concave log-product (Boyd and "
                              "Vandenberghe 2004, chapter 5); log-barrier interior point (ibid., chapter 11); SciPy "
                              "(BSD-3) HiGHS on the verifier side and SLSQP as the competitor",
            native_representation="a list of payoff vectors spanning the feasible set, and the disagreement point",
            required_inputs=("vertices", "disagreement"),
            output_contract={"point": "[float] the agreed payoffs", "gains": "[float] over the disagreement point",
                             "nash_product": "float", "supporting_weights": "[float] normal of the supporting "
                                                                            "hyperplane, sums to 1",
                             "support_value": "float, weights . point"},
            algorithm_or_runtime="log-barrier Newton over convex vertex weights (barrier parameter x8 until the gap "
                                 "is below 1e-13), then Newton on the affine hull of the active face",
            parameters={"max_vertices": NB_MAX_VERTICES, "players": "2 or 3", "verifier_tolerance": NB_TOL},
            composition_inputs=("payoff possibility set", "outside options"),
            composition_outputs=("agreement point", "implied weights of the players"),
            evidence_type="optimality_certificate",
            verification_method="independent HiGHS LPs: the point lies in the hull (L1 residual) and no feasible "
                                "point improves every player (Pareto slack 0); the supporting weights are "
                                "proportional to 1 / gain (tangency) and no vertex lies beyond their hyperplane",
            confidence_semantics="the KKT certificate holds to 1e-9 of the payoff scale in floating point; the point "
                                 "is the axiomatic Nash solution of the declared model, not a prediction of what "
                                 "negotiators will agree",
            resource_profile="O(k^3) per Newton step over k vertex weights; tens of steps",
            latency_profile="milliseconds",
            known_strengths=("a checkable optimality certificate (supporting hyperplane) with every answer",
                             "Newton polishing reaches the face's stationary point to rounding"),
            known_failure_modes=("SLSQP reaches the same point on well-conditioned problems and was about 5x faster "
                                 "on the development seeds (1.4 ms against 6.9 ms median): the genome's only "
                                 "advantage is the certificate, which the admission rule does not score, so it is "
                                 "expected to be SUPERSEDED",
                                 "floating point: an exact rational solution is not returned",
                                 "assumes no free disposal: the feasible set is the hull itself",
                                 "the Nash solution is one axiomatic choice; Kalai-Smorodinsky or egalitarian "
                                 "solutions answer other fairness questions"),
            counterindications=("non-convex feasible sets", "more than three players (not supported in this version)",
                                "no point strictly better than disagreement for every player"),
            abstention_conditions=("no feasible point gives every player more than the disagreement point -> input "
                                   "refused",),
            benchmark_suite="random 2- and 3-player hulls of 4-12 integer payoff vectors, and sampled concave "
                            "frontiers; truth by exact enumeration of every vertex simplex's stationary point "
                            "(rationals; SymPy roots on 3-player edges); correct within 1e-6 of the scale, otherwise "
                            "quality is the Nash-product ratio; seeds 0-9 dev, held-out seeds fixed by the admission "
                            "freeze",
            baseline="the vertex with the largest Nash product",
            competitor="SciPy SLSQP on the log-product over convex vertex weights (ftol 1e-15)",
            dependency="scipy", **_common()),
        solve=nb_solve, verify=nb_verify, instance=nb_instance, score=nb_score, baseline=nb_baseline,
        competitor=nb_competitor, subregion=nb_subregion, tolerance=1e-9),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.game.stackelberg_multiple_lps", version="1.0.0", family="game_stackelberg_commit",
            operation="stackelberg_commitment",
            subgeometry="two-player normal-form games (up to 8 x 8) where the leader commits to a mixed strategy and "
                        "the follower best responds (strong Stackelberg equilibrium)",
            source_provenance="von Stackelberg (1934); von Stengel and Zamir (2010) commitment value; Conitzer and "
                              "Sandholm (2006) multiple LPs; exact rational simplex with Bland's rule (Bland 1977); "
                              "SciPy HiGHS (MIT) as the independent truth",
            native_representation="leader and follower payoff matrices (leader chooses rows)",
            required_inputs=("leader_payoffs", "follower_payoffs"),
            output_contract={"leader_strategy": "[float] committed mixed strategy",
                             "leader_strategy_exact": "[rational string]", "follower_response": "int column",
                             "leader_value": "float", "leader_value_exact": "rational string",
                             "follower_value": "float"},
            algorithm_or_runtime="for each follower action the dual of its LP, then the primal of the best, by an "
                                 "exact two-phase rational simplex",
            parameters={"max_actions": SC_MAX_ACTIONS},
            composition_inputs=("payoff model with a first mover",),
            composition_outputs=("optimal commitment", "induced response", "value of commitment"),
            evidence_type="optimality_certificate",
            verification_method="exact rationals: the commitment is a distribution, the follower's response is a best "
                                "response, the leader value is recomputed, and for every follower action a "
                                "dual-feasible point bounds the best commitment inducing it by at most the value",
            confidence_semantics="exact for the declared payoffs under strong-Stackelberg tie-breaking; a follower "
                                 "who breaks ties against the leader can lower the value (weak Stackelberg); "
                                 "commitment must be credible and observable for the model to apply",
            resource_profile="n + 1 exact LPs with m or n variables",
            latency_profile="milliseconds to tens of milliseconds at 8 x 8 with integer payoffs",
            known_strengths=("exact rational optimum with a complete dual certificate",
                             "never below the leader's best Nash payoff or best pure commitment"),
            known_failure_modes=("the declared competitor (commit to the best Nash strategy) answers a weaker "
                                 "question: commitment value is never below it (von Stengel and Zamir 2010), so a win "
                                 "against it is expected by theory; the strongest deployable competitor would be one "
                                 "MILP (DOBSS) or the HiGHS multiple LPs, which tie on quality",
                                 "rational arithmetic slows on large or float payoffs (denominator growth)",
                                 "strong-Stackelberg tie-breaking is optimistic: a commitment exactly at a "
                                 "follower indifference point is fragile"),
            counterindications=("multiple followers or Bayesian follower types (use DOBSS)",
                                "games above 8 x 8", "settings where commitment is not observable"),
            abstention_conditions=("latency budget exhausted -> UNKNOWN",),
            benchmark_suite="security games (cover a target, attacker picks one), random 2-8 action games, inspection "
                            "games and coordination games, integer payoffs; truth by SciPy HiGHS multiple LPs; "
                            "correct within 1e-9 of the scale, otherwise quality is the leader value's share of the "
                            "range from the worst payoff; seeds 0-9 dev, held-out seeds fixed by the admission freeze",
            baseline="the leader's best pure commitment",
            competitor="commit to the leader's best simultaneous-move Nash strategy (exact support enumeration); the "
                       "commitment value gap is reported against it",
            dependency=None, **_common()),
        solve=sc_solve, verify=sc_verify, instance=sc_instance, score=sc_score, baseline=sc_baseline,
        competitor=sc_competitor, subregion=sc_subregion, tolerance=1e-9,
        notes={"competitor": "specified by the lane brief; it answers the simultaneous-move question, so the "
                             "candidate is expected to weakly dominate it. HiGHS multiple LPs (the truth method) is "
                             "the stronger deployable competitor and would tie on quality"}),
]
