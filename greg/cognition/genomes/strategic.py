"""Layer 3 intelligences, pack C: strategic and temporal formal methods.

Three executables on GREG's one cognition path (``greg.cognition.cortex.reason`` -> isolated worker ->
independent verifier -> CognitiveReceipt), directive section 5 and section 31 item 2. Each is an ordinary,
well-understood method; the genome records where it is natively competent, what it is compared against and
how its output is checked.

* ``bimatrix_nash`` (``bimatrix_nash_equilibrium``): every Nash equilibrium with equal-size supports of a
  general-sum two-player game by support enumeration in exact rational arithmetic, returning the one with
  the highest total payoff, plus a welfare-maximal correlated equilibrium from one SciPy HiGHS linear
  program. The maximal-welfare claim is made only when an exact test shows the game nondegenerate. Verified
  by an epsilon-Nash check written independently, an exact re-check of the rational certificate, an
  independent mixed-integer program over all equilibria for the welfare claim (an exact vertex enumeration
  decides any disagreement), the correlated equilibrium's incentive constraints and an LP dual certificate
  for its welfare, checked in exact rationals.
* ``mechanism_check`` (``mechanism_ic_ir_check``): dominant-strategy incentive compatibility and ex-post
  individual rationality of a declared direct mechanism (allocation and payment tables over a finite type
  space), by exhaustive enumeration in exact rational arithmetic. It reports the largest profitable
  misreport (agent, true type, reported type, others' profile, gain) and the worst participation shortfall,
  or that both properties hold. Verified by an independent re-enumeration organised differently (true
  profile first, dictionary-keyed) and a direct replay of each witness.
* ``verify_liveness`` (``model_check_liveness``): "every weakly fair run eventually reaches the goal" for a
  finite transition system in the typed guarded-command language of ``verify_modelcheck``. Counterexamples
  are lassos (or deadlocks) found from a reachable strongly connected component that avoids the goal and is
  weakly fair (iterative Tarjan). Verified by step-by-step lasso replay with an independent interpreter, or,
  for HOLDS, by independent code for the same fair-SCC criterion: a NumPy-explored region, SciPy's compiled
  strong components and a vectorised fairness filter. The benchmark truth adds an Emerson-Lei greatest
  fixpoint (no SCC decomposition), which must agree.

The liveness checker imports the parser, type checker, magnitude bounds, closure compiler, interpreter and
vectorised evaluator of ``solvers_c`` without editing that admitted module. Everything is read-only
computation: no files, network, subprocesses or environment access, and no output of any method here creates
authority.
"""
from __future__ import annotations

from collections import deque
from fractions import Fraction
import hashlib
from itertools import combinations, product
import math
import random
import re
import time
import warnings

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int, finite
from .solvers_c import _mc_compiled, _mc_digest, _mc_eval, _mc_step, _mc_system, _mc_vec, _mc_z3

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "directive section 5 and section 31 item 2: Layer 3 pack C (strategic and temporal formal methods)",
           "greg/cognition/genomes/solvers_c.py (guarded-command language of verify_modelcheck, reused unedited)")


def _common(**kw):
    return dict(buildability="BUILDABLE_NOW", memory_model="stateless",
                learning_rule="none (competence settles per geometry through GREG outcomes)", lineage=LINEAGE, **kw)


def _abstain(reason, **certificate):
    return answer(None, {"reason": reason, **certificate}, status="ABSTAIN", missing=[reason])


def _unknown(reason, **certificate):
    return answer(None, {"reason": reason, **certificate}, status="UNKNOWN", missing=[reason])


def _obj(data):
    if not isinstance(data, dict):
        raise GenomeError("data must be an object")
    return data


def _is_num(x):
    try:
        return type(x) in (int, float) and math.isfinite(x)
    except OverflowError:                       # an integer beyond the float range is not a usable number
        return False


def _is_int(x):
    return type(x) is int


# =================================================================== 1. bimatrix Nash equilibria
NASH_MAX_ACTIONS, NASH_MAX_ABS = 8, 1e6
NASH_MAX_PAIRS = 1000                    # equal-size support pairs C(m + n, m) - 1; a 6 x 6 game has 923
NASH_EPS = 1e-9                          # epsilon-Nash tolerance, relative to the payoff scale
NASH_WELFARE_TOL = 1e-6                  # MILP welfare comparison tolerance, relative to the payoff scale
NASH_CE_TOL = 1e-7                       # correlated incentive and dual-optimality tolerance, relative to the scale
NASH_MILP_TOL = 1e-9                     # HiGHS feasibility and integrality tolerance in the welfare MILP
NASH_EXACT_CHARS = 4000                  # longest exact rational string the verifier parses
CE_REPAIR_ROUNDS = 4                     # active-set rounds of the exact dual repair (each drops one multiplier)
NASH_IBR_CHECKPOINTS, NASH_POLISH = (100, 400, 1500, 4000), 0.02
SELECTIONS = ("max_welfare_nash", "nash")
_RATIONAL = re.compile(r"-?[0-9]+(/[0-9]+)?")


def _bimatrix(data):
    _obj(data)
    a, b = data.get("row_payoffs"), data.get("column_payoffs")
    if (not isinstance(a, list) or not 1 <= len(a) <= NASH_MAX_ACTIONS or not isinstance(a[0], list)
            or not 1 <= len(a[0]) <= NASH_MAX_ACTIONS):
        raise GenomeError(f"row_payoffs: an m x n matrix with 1 <= m, n <= {NASH_MAX_ACTIONS}")
    m, n = len(a), len(a[0])
    for name, mat in (("row_payoffs", a), ("column_payoffs", b)):
        if not isinstance(mat, list) or len(mat) != m or any(not isinstance(r, list) or len(r) != n for r in mat):
            raise GenomeError(f"{name}: rectangular, the shape of row_payoffs")
    a = [[finite(x, low=-NASH_MAX_ABS, high=NASH_MAX_ABS, name="row payoff") for x in r] for r in a]
    b = [[finite(x, low=-NASH_MAX_ABS, high=NASH_MAX_ABS, name="column payoff") for x in r] for r in b]
    return a, b


def _scale(a, b):
    """The payoff magnitude every normalisation and tolerance is relative to: the largest absolute payoff (1 only
    when every payoff is zero). There is no floor at 1, so a game stated in small units keeps relative tolerances."""
    return max(abs(v) for mat in (a, b) for r in mat for v in r) or 1.0


def _rational_solve(rows, rhs):
    """Exact Gauss-Jordan elimination over Fractions; None when the square system is singular."""
    size = len(rows)
    t = [list(r) + [v] for r, v in zip(rows, rhs)]
    for c in range(size):
        p = next((i for i in range(c, size) if t[i][c] != 0), None)
        if p is None:
            return None
        t[c], t[p] = t[p], t[c]
        inv = 1 / t[c][c]
        pivot = [v * inv for v in t[c]]
        t[c] = pivot
        for i in range(size):
            f = t[i][c]
            if i != c and f != 0:
                t[i] = [v - f * w for v, w in zip(t[i], pivot)]
    return [t[i][size] for i in range(size)]


def _support_equilibria(A, B, deadline):
    """Every equilibrium whose supports have equal size, and an exact degeneracy test. None if the latency
    budget runs out.

    For supports I (rows) and J (columns) of size k: y on J makes every row of I indifferent at value u, x on I
    makes every column of J indifferent at value v (two (k+1)-square systems); kept when x, y are strictly
    positive on their supports and no pure strategy outside a support pays more. Complete for nondegenerate
    games (every equilibrium there has equal support sizes). Each system whose solution is nonnegative and
    unbeaten is a point of a best-response polytope, and every vertex of those polytopes arises this way, so
    ``degenerate`` is exact: some such point has a zero weight on its support or more pure best responses than
    its support size, which is the definition of a degenerate game (von Stengel 2002, section 2.6).
    """
    m, n = len(A), len(A[0])
    one, zero = Fraction(1), Fraction(0)
    found, pairs, degenerate = [], 0, False
    for k in range(1, min(m, n) + 1):
        tail = [one] * k + [zero]
        rhs = [zero] * k + [one]
        for I in combinations(range(m), k):
            for J in combinations(range(n), k):
                pairs += 1
                if pairs % 64 == 0 and time.perf_counter() > deadline:
                    return None
                ys = _rational_solve([[A[i][j] for j in J] + [-one] for i in I] + [tail], rhs)
                xs = _rational_solve([[B[i][j] for i in I] + [-one] for j in J] + [tail], rhs)
                row = col = None
                if ys is not None and min(ys[:k]) >= 0:
                    row = [sum(A[i][j] * q for j, q in zip(J, ys)) for i in range(m)]
                    if max(row) > ys[k]:
                        row = None
                    elif min(ys[:k]) == 0 or row.count(ys[k]) > k:
                        degenerate = True
                if xs is not None and min(xs[:k]) >= 0:
                    col = [sum(B[i][j] * p for i, p in zip(I, xs)) for j in range(n)]
                    if max(col) > xs[k]:
                        col = None
                    elif min(xs[:k]) == 0 or col.count(xs[k]) > k:
                        degenerate = True
                if row is None or col is None or min(ys[:k]) == 0 or min(xs[:k]) == 0:
                    continue
                x, y = [zero] * m, [zero] * n
                for i, p in zip(I, xs):
                    x[i] = p
                for j, q in zip(J, ys):
                    y[j] = q
                found.append({"x": x, "y": y, "u": ys[k], "v": xs[k], "I": I, "J": J})
    return found, pairs, degenerate


def _correlated(a, b):
    """Welfare-maximal correlated equilibrium: one HiGHS LP over the joint distribution p.

    max sum p (A + B) s.t. sum_j p_ij (A_ij - A_kj) >= 0 for every row pair, sum_i p_ij (B_ij - B_il) >= 0
    for every column pair, sum p = 1, p >= 0. Payoffs are divided by their scale first. Returns (output,
    dual certificate): multipliers alpha, beta >= 0 from the LP marginals (zero on the diagonal, where no
    constraint exists) and the smallest bound mu with mu - (G' alpha)_ij >= (A + B)_ij in every cell, computed
    exactly from the stated float multipliers and rounded up, so weak duality caps every correlated
    equilibrium's welfare at mu (checked by the verifier with its own exact arithmetic). When HiGHS's float
    multipliers are too coarse for that bound to meet the plan's welfare (near-degenerate incentive constraints
    need multipliers of 1e14 and more), an exact active-set solve repairs them; if the bound still misses, the
    correlated plan is withheld (output None) rather than claimed optimal without a certificate.
    """
    import numpy as np
    from scipy.optimize import linprog
    S = _scale(a, b)
    A, B = np.array(a, dtype=float) / S, np.array(b, dtype=float) / S
    m, n = A.shape
    G = []
    for i in range(m):
        for k in range(m):
            if k != i:
                g = np.zeros((m, n))
                g[i, :] = A[i, :] - A[k, :]
                G.append(g.ravel())
    for j in range(n):
        for l in range(n):
            if l != j:
                g = np.zeros((m, n))
                g[:, j] = B[:, j] - B[:, l]
                G.append(g.ravel())
    w = (A + B).ravel()
    extra = {"A_ub": -np.array(G), "b_ub": np.zeros(len(G))} if G else {}
    res = linprog(-w, A_eq=np.ones((1, m * n)), b_eq=[1.0], bounds=[(0, None)] * (m * n), method="highs",
                  options={"primal_feasibility_tolerance": 1e-10, "dual_feasibility_tolerance": 1e-10}, **extra)
    if res.status != 0:
        return None, {"reason": f"correlated-equilibrium LP: {res.message}"}
    p = np.clip(res.x, 0.0, None)
    p = p / p.sum()
    lam = np.clip(-np.asarray(res.ineqlin.marginals, dtype=float), 0.0, None) if G else np.zeros(0)
    alpha, beta, z = [[0.0] * m for _ in range(m)], [[0.0] * n for _ in range(n)], 0
    for i in range(m):
        for k in range(m):
            if k != i:
                alpha[i][k] = float(lam[z])
                z += 1
    for j in range(n):
        for l in range(n):
            if l != j:
                beta[j][l] = float(lam[z])
                z += 1
    dist = [[float(p[i * n + j]) for j in range(n)] for i in range(m)]
    welfare = math.fsum(dist[i][j] * (a[i][j] + b[i][j]) for i in range(m) for j in range(n))
    fa, fb = [[Fraction(v) for v in r] for r in a], [[Fraction(v) for v in r] for r in b]
    exact_welfare = sum(Fraction(dist[i][j]) * (fa[i][j] + fb[i][j]) for i in range(m) for j in range(n))
    slack = Fraction(NASH_CE_TOL) * Fraction(S)
    mu = _ce_cells(fa, fb, alpha, beta)
    if max(mu.values()) > exact_welfare + slack / 10:
        repaired = _ce_exact_dual(fa, fb, alpha, beta, exact_welfare)
        if repaired is not None:
            mu2 = _ce_cells(fa, fb, *repaired)
            if max(mu2.values()) < max(mu.values()):
                (alpha, beta), mu = repaired, mu2
    top = max(mu.values())
    if top > exact_welfare + slack:
        return None, {"reason": "correlated equilibrium withheld: the LP's dual multipliers do not certify its "
                                "welfare exactly (near-degenerate incentive constraints)"}
    bound = float(top)
    if Fraction(bound) < top:                               # round up: the stated bound stays a valid cap
        bound = math.nextafter(bound, math.inf)
    return ({"distribution": dist, "welfare": welfare, "objective": "max_welfare"},
            {"row_multipliers": alpha, "column_multipliers": beta, "bound": bound})


def _ce_cells(fa, fb, alpha, beta):
    """Exact dual value of every cell: (A + B)_ij + sum_k alpha_ik (A_ij - A_kj) + sum_l beta_jl (B_ij - B_il)
    for the stated multipliers; any bound at or above their maximum is a valid cap (weak duality)."""
    m, n = len(fa), len(fa[0])
    return {(i, j): fa[i][j] + fb[i][j]
            + sum(Fraction(alpha[i][k]) * (fa[i][j] - fa[k][j]) for k in range(m) if k != i and alpha[i][k])
            + sum(Fraction(beta[j][l]) * (fb[i][j] - fb[i][l]) for l in range(n) if l != j and beta[j][l])
            for i in range(m) for j in range(n)}


def _ce_exact_dual(fa, fb, alpha, beta, welfare):
    """Exact repair of the LP's float dual by complementary slackness: the unknowns are the bound and the
    multipliers HiGHS made positive; the equations are the cells whose float dual value lies nearest the plan's
    welfare (tight cells), taken in that order while independent; unknowns left without an equation keep
    their float value. A negative multiplier leaves the active set and the solve repeats. Returns float
    multipliers (alpha, beta), rounded from the exact solution, or None."""
    m, n = len(fa), len(fa[0])
    active = [("a", i, k) for i in range(m) for k in range(m) if k != i and alpha[i][k] > 0] + \
             [("b", j, l) for j in range(n) for l in range(n) if l != j and beta[j][l] > 0]

    def coeff(g, i, j):
        kind, p, q = g
        if kind == "a":
            return fa[i][j] - fa[q][j] if i == p else Fraction(0)
        return fb[i][j] - fb[i][q] if j == p else Fraction(0)
    cells = _ce_cells(fa, fb, alpha, beta)
    order = sorted(cells, key=lambda c: (abs(cells[c] - welfare), c))
    for _ in range(min(len(active), CE_REPAIR_ROUNDS) + 1):
        d = len(active) + 1                              # unknowns: the bound, then the active multipliers
        basis = []                                       # (pivot, row, rhs), fully reduced
        for i, j in order:
            row = [Fraction(1)] + [-coeff(g, i, j) for g in active]
            rhs = fa[i][j] + fb[i][j]
            for piv, brow, brhs in basis:
                f = row[piv]
                if f:
                    row = [x - f * y for x, y in zip(row, brow)]
                    rhs -= f * brhs
            piv = next((c for c in range(d) if row[c]), None)
            if piv is None:
                continue
            inv = 1 / row[piv]
            row, rhs = [x * inv for x in row], rhs * inv
            reduced = []
            for bp, brow, brhs in basis:
                f = brow[piv]
                reduced.append((bp, [x - f * y for x, y in zip(brow, row)], brhs - f * rhs) if f else (bp, brow, brhs))
            basis = reduced + [(piv, row, rhs)]
            if len(basis) == d:
                break
        pivots = {bp for bp, _, _ in basis}             # the bound always pivots: every row has it with 1
        z = [Fraction(0)] * d
        for c in range(1, d):
            if c not in pivots:                          # no tight cell pins it: keep the LP's value
                kind, p, q = active[c - 1]
                z[c] = Fraction(alpha[p][q] if kind == "a" else beta[p][q])
        for bp, brow, brhs in basis:
            z[bp] = brhs - sum(brow[c] * z[c] for c in range(d) if c not in pivots)
        lam = z[1:]
        worst = min(range(len(lam)), key=lambda t: lam[t], default=None)
        if worst is not None and lam[worst] < 0:
            del active[worst]
            continue
        if any(abs(val) > 1e300 for val in lam):
            return None
        new_alpha, new_beta = [[0.0] * m for _ in range(m)], [[0.0] * n for _ in range(n)]
        for (kind, p, q), val in zip(active, lam):
            (new_alpha if kind == "a" else new_beta)[p][q] = float(val)
        return new_alpha, new_beta
    return None


def nash_solve(data, budget):
    a, b = _bimatrix(data)
    m, n = len(a), len(a[0])
    pairs = math.comb(m + n, m) - 1
    if pairs > NASH_MAX_PAIRS:
        return _abstain(f"support enumeration needs {pairs} support pairs (> {NASH_MAX_PAIRS}); it is exponential "
                        "in the number of actions", rows=m, cols=n)
    A = [[Fraction(v) for v in r] for r in a]
    B = [[Fraction(v) for v in r] for r in b]
    deadline = time.perf_counter() + max(0.5, float((budget or {}).get("latency_s", 5.0)))
    enumerated = _support_equilibria(A, B, deadline)
    if enumerated is None:
        return _unknown("latency budget exhausted during support enumeration")
    found, examined, degenerate = enumerated
    if not found:
        return _unknown("degenerate game: no equilibrium with equal-size supports (equilibria may form a "
                        "continuum)", support_pairs=examined)
    complete = not degenerate and len(found) % 2 == 1    # a nondegenerate game has an odd number of equilibria
    best = max(found, key=lambda e: e["u"] + e["v"])    # the first maximum in enumeration order
    ce, dual = _correlated(a, b)
    out = {"row_strategy": [float(p) for p in best["x"]], "column_strategy": [float(q) for q in best["y"]],
           "row_payoff": float(best["u"]), "column_payoff": float(best["v"]),
           "welfare": float(best["u"] + best["v"]), "selection": "max_welfare_nash" if complete else "nash",
           "correlated": ce}
    cert = {"method": "support enumeration over every equal-size support pair, exact rational arithmetic; "
                      "highest-welfare equilibrium selected; correlated equilibrium by one HiGHS LP",
            "support_pairs": examined, "equilibria_found": len(found),
            "degeneracy_symptoms": {"extra_pure_best_responses": degenerate,
                                    "even_equilibrium_count": len(found) % 2 == 0},
            "welfare_claim": "maximal over all equilibria" if complete else "none: degeneracy symptoms seen, so "
                             "equal-size support enumeration may have missed equilibria",
            "row_support": list(best["I"]), "column_support": list(best["J"]),
            "equilibrium_welfares": sorted(float(e["u"] + e["v"]) for e in found)[-50:],
            "exact": {"row_strategy": [str(p) for p in best["x"]], "column_strategy": [str(q) for q in best["y"]],
                      "row_payoff": str(best["u"]), "column_payoff": str(best["v"])},
            "correlated_dual": dual}
    return answer(out, cert)


def _nash_values(a, b, output):
    """(x, y, row values A y, column values x B, u, v) by plain float arithmetic, or None if malformed (an entry
    outside [-1, 2] is no probability and could overflow the sums)."""
    m, n = len(a), len(a[0])
    if not isinstance(output, dict):
        return None
    x, y = output.get("row_strategy"), output.get("column_strategy")
    if (not isinstance(x, list) or len(x) != m or not all(_is_num(p) and -1.0 <= p <= 2.0 for p in x)
            or not isinstance(y, list) or len(y) != n or not all(_is_num(q) and -1.0 <= q <= 2.0 for q in y)):
        return None
    row = [math.fsum(a[i][j] * y[j] for j in range(n)) for i in range(m)]
    col = [math.fsum(b[i][j] * x[i] for i in range(m)) for j in range(n)]
    u = math.fsum(x[i] * row[i] for i in range(m))
    v = math.fsum(col[j] * y[j] for j in range(n))
    return x, y, row, col, u, v


def _nash_equilibrium(a, b, output):
    """Independent epsilon-Nash check: (u, v) when both strategies are distributions, each player's expected
    payoff is within epsilon of its best pure response and the claimed payoffs and welfare match; else None."""
    got = _nash_values(a, b, output)
    if got is None:
        return None
    x, y, row, col, u, v = got
    eps = NASH_EPS * _scale(a, b)
    claimed = [output.get(k) for k in ("row_payoff", "column_payoff", "welfare")]
    if (min(x) < -1e-12 or min(y) < -1e-12 or abs(math.fsum(x) - 1.0) > 1e-9 or abs(math.fsum(y) - 1.0) > 1e-9
            or max(row) - u > eps or max(col) - v > eps or not all(_is_num(c) for c in claimed)
            or abs(claimed[0] - u) > eps or abs(claimed[1] - v) > eps or abs(claimed[2] - u - v) > 2 * eps):
        return None
    return u, v


def _nash_milp(a, b, sense="max"):
    """Evaluation side only (``verify`` and the benchmark truth; never ``solve``): the highest (or lowest)
    total payoff over ALL Nash equilibria, by the mixed-integer formulation of Sandholm, Gilpin and Conitzer
    (2005) solved by SciPy HiGHS: regrets r_i = u - (A y)_i >= 0, s_j = v - (x B)_j >= 0, binary b_i with
    x_i <= 1 - b_i and r_i <= M b_i (a played strategy has zero regret). Each player's payoffs are mapped
    affinely onto [0, 1] (the equilibria are unchanged and the objective keeps each player's true weight), and
    HiGHS runs with feasibility and integrality tolerances of 1e-9, so a regret above about 1e-9 of a player's
    payoff range is never read as zero. Returns (welfare, x, y) with the optimal profile, or None if HiGHS does
    not finish."""
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    A0, B0 = np.array(a, dtype=float), np.array(b, dtype=float)
    lo_a, lo_b = float(A0.min()), float(B0.min())
    ra, rb = float(A0.max()) - lo_a, float(B0.max()) - lo_b
    A = (A0 - lo_a) / ra if ra > 0 else np.zeros_like(A0)
    B = (B0 - lo_b) / rb if rb > 0 else np.zeros_like(B0)
    R = max(ra, rb) or 1.0
    m, n = A.shape
    ma, mb = 1.0, 1.0
    iu, iv = m + n, m + n + 1
    ir, js, ibx, iby = m + n + 2, 2 * m + n + 2, 2 * m + 2 * n + 2, 3 * m + 2 * n + 2
    size = 3 * m + 3 * n + 2
    rows, lo, hi = [], [], []

    def add(entries, low, high):
        row = np.zeros(size)
        for k, c in entries:
            row[k] += c
        rows.append(row)
        lo.append(low)
        hi.append(high)
    add([(i, 1.0) for i in range(m)], 1.0, 1.0)
    add([(m + j, 1.0) for j in range(n)], 1.0, 1.0)
    for i in range(m):
        add([(iu, 1.0), (ir + i, -1.0)] + [(m + j, -A[i, j]) for j in range(n)], 0.0, 0.0)
        add([(i, 1.0), (ibx + i, 1.0)], -np.inf, 1.0)
        add([(ir + i, 1.0), (ibx + i, -ma)], -np.inf, 0.0)
    for j in range(n):
        add([(iv, 1.0), (js + j, -1.0)] + [(i, -B[i, j]) for i in range(m)], 0.0, 0.0)
        add([(m + j, 1.0), (iby + j, 1.0)], -np.inf, 1.0)
        add([(js + j, 1.0), (iby + j, -mb)], -np.inf, 0.0)
    c = np.zeros(size)
    sign = -1.0 if sense == "max" else 1.0
    c[iu], c[iv] = sign * ra / R, sign * rb / R
    lb = [0.0] * (m + n + 2) + [0.0] * (2 * m + 2 * n)
    ub = [1.0] * (m + n + 2) + [ma] * m + [mb] * n + [1.0] * (m + n)
    with warnings.catch_warnings():                          # SciPy warns that HiGHS options pass through verbatim
        warnings.simplefilter("ignore")
        res = milp(c, constraints=LinearConstraint(np.array(rows), lo, hi),
                   integrality=[0] * (2 * m + 2 * n + 2) + [1] * (m + n), bounds=Bounds(lb, ub),
                   options={"mip_rel_gap": 0.0, "time_limit": 20.0, "mip_feasibility_tolerance": NASH_MILP_TOL,
                            "primal_feasibility_tolerance": NASH_MILP_TOL})
    if res.status != 0 or res.x is None:
        return None
    welfare = sign * res.fun * R + lo_a + lo_b
    return welfare, [float(t) for t in res.x[:m]], [float(t) for t in res.x[m:m + n]]


def _exact_rational(s):
    """A rational exactly as the solver writes it ("p" or "p/q"); anything else (floats, exponents, infinities,
    other types, overlong strings) raises ValueError, so a malformed certificate is refuted, never parsed."""
    if not isinstance(s, str) or len(s) > NASH_EXACT_CHARS or not _RATIONAL.fullmatch(s):
        raise ValueError("not an exact rational string")
    return Fraction(s)


def _exact_certificate(a, b, output, exact):
    """The certificate's rationals form an exact equilibrium, and the output floats are their roundings."""
    m, n = len(a), len(a[0])
    try:
        rows, cols = exact["row_strategy"], exact["column_strategy"]
        if not isinstance(rows, list) or not isinstance(cols, list):
            return False
        x = [_exact_rational(s) for s in rows]
        y = [_exact_rational(s) for s in cols]
        u, v = _exact_rational(exact["row_payoff"]), _exact_rational(exact["column_payoff"])
    except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError):
        return False
    if len(x) != m or len(y) != n or min(x) < 0 or min(y) < 0 or sum(x) != 1 or sum(y) != 1:
        return False
    A = [[Fraction(v_) for v_ in r] for r in a]
    B = [[Fraction(v_) for v_ in r] for r in b]
    row = [sum(A[i][j] * y[j] for j in range(n)) for i in range(m)]
    col = [sum(B[i][j] * x[i] for i in range(m)) for j in range(n)]
    if max(row) != u or max(col) != v or sum(x[i] * row[i] for i in range(m)) != u \
            or sum(col[j] * y[j] for j in range(n)) != v:
        return False

    def near(f, g):                                    # relative: no floor, so small units are held to it too
        return _is_num(g) and abs(float(f) - g) <= 1e-12 * max(abs(g), abs(float(f)))
    return (all(near(p, q) for p, q in zip(x, output["row_strategy"]))
            and all(near(p, q) for p, q in zip(y, output["column_strategy"]))
            and near(u, output["row_payoff"]) and near(v, output["column_payoff"]))


def _bareiss_solve(M, rhs):
    """Square integer system M z = rhs by fraction-free (Bareiss) elimination and exact back substitution;
    None when M is singular. The verifier's own exact linear algebra (the solver uses Fraction Gauss-Jordan)."""
    k = len(M)
    t = [list(r) + [v] for r, v in zip(M, rhs)]
    prev = 1
    for c in range(k):
        p = next((i for i in range(c, k) if t[i][c] != 0), None)
        if p is None:
            return None
        t[c], t[p] = t[p], t[c]
        for i in range(c + 1, k):
            t[i] = [(t[c][c] * t[i][j] - t[i][c] * t[c][j]) // prev for j in range(k + 1)]
        prev = t[c][c]
    z = [Fraction(0)] * k
    for i in reversed(range(k)):
        z[i] = (t[i][k] - sum(t[i][j] * z[j] for j in range(i + 1, k))) / Fraction(t[i][i])
    return z


def _polytope_vertices(C, labels_var, labels_con):
    """Every vertex but the origin of {z >= 0, C z <= 1} (C a positive integer matrix, q x p), exactly: for each
    k, every k tight constraints over every k-variable support, solved by Bareiss and kept when feasible.
    Returns {vertex: (label bitmask, sum z)}: a zero coordinate carries its variable's label, a tight row its
    constraint's label."""
    q, p = len(C), len(C[0])
    out = {}
    for k in range(1, min(p, q) + 1):
        for S in combinations(range(p), k):
            for T in combinations(range(q), k):
                z = _bareiss_solve([[C[t][s] for s in S] for t in T], [1] * k)
                if z is None or min(z) < 0:
                    continue
                full = [Fraction(0)] * p
                for s, val in zip(S, z):
                    full[s] = val
                key = tuple(full)
                if key in out:
                    continue
                load = [sum(C[t][s] * full[s] for s in range(p)) for t in range(q)]
                if max(load) > 1:
                    continue
                mask = 0
                for s in range(p):
                    if full[s] == 0:
                        mask |= 1 << labels_var[s]
                for t in range(q):
                    if load[t] == 1:
                        mask |= 1 << labels_con[t]
                out[key] = (mask, sum(full))
    return out


def _nash_extreme_welfare(a, b):
    """Evaluation side only: the highest total payoff over ALL Nash equilibria, exactly, or None past
    NASH_MAX_PAIRS + 1 bases per polytope. Payoffs are scaled to integers and shifted positive; the vertices of
    the best-response polytopes P = {x >= 0, B'^T x <= 1} and Q = {y >= 0, A' y <= 1} are enumerated exactly
    and every completely labelled pair is an extreme equilibrium (the criterion of lrsNash: Avis, Rosenberg,
    Savani and von Stengel 2010). The equilibrium set is a finite union of polytopes whose vertices are extreme
    equilibria, and on each one a player's payoff is linear in the other's strategy, so the maximum over the
    extreme equilibria is the maximum over all of them, degenerate games included. Independent of the
    solver's equal-size support enumeration and of the MILP."""
    m, n = len(a), len(a[0])
    if math.comb(m + n, m) > NASH_MAX_PAIRS + 1:
        return None
    fa, fb = [[Fraction(v) for v in r] for r in a], [[Fraction(v) for v in r] for r in b]
    den = math.lcm(*(f.denominator for mat in (fa, fb) for r in mat for f in r))
    ia = [[int(f * den) for f in r] for r in fa]
    ib = [[int(f * den) for f in r] for r in fb]
    shift_a = 1 - min(min(r) for r in ia)
    shift_b = 1 - min(min(r) for r in ib)
    P = _polytope_vertices([[ib[i][j] + shift_b for i in range(m)] for j in range(n)],
                           list(range(m)), [m + j for j in range(n)])
    Q = _polytope_vertices([[ia[i][j] + shift_a for j in range(n)] for i in range(m)],
                           [m + j for j in range(n)], list(range(m)))
    full = (1 << (m + n)) - 1
    best = None
    for lx, sx in P.values():
        need = full & ~lx
        for ly, sy in Q.values():
            if ly & need == need:
                w = 1 / sy + 1 / sx                          # payoffs in the shifted integer units
                if best is None or w > best:
                    best = w
    if best is None:
        return None
    return (best - shift_a - shift_b) / den


def _welfare_maximality(a, b, welfare):
    """The claim that ``welfare`` (a verified equilibrium's) is maximal over all equilibria. The MILP confirms
    it when the two agree within the tolerance; its optimum is an upper bound, so agreement is sound. When they
    disagree the MILP may have read a near-equilibrium as an equilibrium, or missed one, so the exact vertex
    enumeration decides; beyond its size the MILP's refutation stands only if its own optimal profile is an
    equilibrium of the original game, and otherwise the check is reported infeasible."""
    tol = NASH_WELFARE_TOL * _scale(a, b)
    milp = _nash_milp(a, b, "max")
    if milp is not None and abs(milp[0] - welfare) <= tol:
        return {"welfare_maximal_over_all_equilibria_by_independent_milp": True}
    exact = _nash_extreme_welfare(a, b)
    if exact is not None:
        return {"welfare_maximal_over_all_equilibria_by_exact_vertex_enumeration": welfare >= float(exact) - tol}
    if milp is not None and milp[0] > welfare + tol:
        x, y = [max(t, 0.0) for t in milp[1]], [max(t, 0.0) for t in milp[2]]
        sx, sy = math.fsum(x), math.fsum(y)
        if sx > 0 and sy > 0:
            profile = {"row_strategy": [t / sx for t in x], "column_strategy": [t / sy for t in y]}
            got = _nash_values(a, b, profile)
            if got is not None:
                u, v = got[4], got[5]
                eps = NASH_EPS * _scale(a, b)
                if max(got[2]) - u <= eps and max(got[3]) - v <= eps and u + v > welfare + tol:
                    return {"welfare_maximal_over_all_equilibria_by_independent_milp": False}
    return {"welfare_maximality_check_feasible": False}


def _correlated_dual_certified(a, b, dist, dual, S):
    """Exact weak duality for the correlated LP: multipliers alpha (rows) and beta (columns), finite and
    nonnegative, zero on the diagonal (no constraint exists there), and a bound with
    bound - sum_k alpha_ik (a_ij - a_kj) - sum_l beta_jl (b_ij - b_il) >= a_ij + b_ij in every cell, evaluated in
    exact rationals of the stated floats. Then every correlated equilibrium's welfare is at most the bound,
    whatever the multipliers' size, and the plan is certified when its own welfare is within NASH_CE_TOL of
    the scale of that bound."""
    m, n = len(a), len(a[0])
    if not isinstance(dual, dict):
        return False
    alpha, beta, bound = dual.get("row_multipliers"), dual.get("column_multipliers"), dual.get("bound")

    def square(mat, size):
        return (isinstance(mat, list) and len(mat) == size
                and all(isinstance(r, list) and len(r) == size and all(_is_num(t) and t >= 0 for t in r)
                        for r in mat)
                and all(mat[i][i] == 0 for i in range(size)))
    if not (square(alpha, m) and square(beta, n) and _is_num(bound)):
        return False
    A, B = [[Fraction(v) for v in r] for r in a], [[Fraction(v) for v in r] for r in b]
    al = [[Fraction(t) for t in r] for r in alpha]
    be = [[Fraction(t) for t in r] for r in beta]
    top = Fraction(bound)
    feasible = all(top - sum(al[i][k] * (A[i][j] - A[k][j]) for k in range(m) if k != i)
                   - sum(be[j][l] * (B[i][j] - B[i][l]) for l in range(n) if l != j) >= A[i][j] + B[i][j]
                   for i in range(m) for j in range(n))
    welfare = sum(Fraction(dist[i][j]) * (A[i][j] + B[i][j]) for i in range(m) for j in range(n))
    return feasible and welfare >= top - Fraction(NASH_CE_TOL) * Fraction(S)


def _correlated_checks(a, b, ce, dual):
    m, n = len(a), len(a[0])
    S = _scale(a, b)
    dist = ce.get("distribution") if isinstance(ce, dict) else None
    if (not isinstance(dist, list) or len(dist) != m
            or any(not isinstance(r, list) or len(r) != n or not all(_is_num(p) and -1.0 <= p <= 2.0 for p in r)
                   for r in dist)):
        return {"correlated_well_formed": False}
    flat = [p for r in dist for p in r]
    valid = min(flat) >= -1e-12 and abs(math.fsum(flat) - 1.0) <= 1e-9
    tol = NASH_CE_TOL * S
    row_ic = all(math.fsum(dist[i][j] * (a[i][j] - a[k][j]) for j in range(n)) >= -tol
                 for i in range(m) for k in range(m) if k != i)
    col_ic = all(math.fsum(dist[i][j] * (b[i][j] - b[i][l]) for i in range(m)) >= -tol
                 for j in range(n) for l in range(n) if l != j)
    welfare = math.fsum(dist[i][j] * (a[i][j] + b[i][j]) for i in range(m) for j in range(n))
    claimed = ce.get("welfare")
    return {"correlated_well_formed": True, "correlated_is_a_distribution": valid,
            "correlated_incentive_constraints_hold": row_ic and col_ic,
            "correlated_welfare_recomputed": _is_num(claimed) and abs(claimed - welfare) <= 1e-9 * S,
            "correlated_objective_declared": ce.get("objective") == "max_welfare",
            "correlated_welfare_optimal_by_dual_certificate": _correlated_dual_certified(a, b, dist, dual, S)}


def nash_verify(data, output, certificate):
    a, b = _bimatrix(data)
    S = _scale(a, b)
    got = _nash_values(a, b, output)
    if got is None:
        return {"strategies_well_formed": False}
    x, y, row, col, u, v = got
    eps = NASH_EPS * S
    claimed = [output.get(k) for k in ("row_payoff", "column_payoff", "welfare")]
    selection = output.get("selection")
    checks = {"strategies_well_formed": True,
              "valid_distributions": min(x) >= -1e-12 and min(y) >= -1e-12 and abs(math.fsum(x) - 1.0) <= 1e-9
              and abs(math.fsum(y) - 1.0) <= 1e-9,
              "row_payoff_equals_best_pure_response": max(row) - u <= eps,
              "column_payoff_equals_best_pure_response": max(col) - v <= eps,
              "payoffs_recomputed": _is_num(claimed[0]) and _is_num(claimed[1]) and abs(claimed[0] - u) <= eps
              and abs(claimed[1] - v) <= eps,
              "welfare_recomputed": _is_num(claimed[2]) and abs(claimed[2] - u - v) <= 2 * eps,
              "selection_declared": selection in SELECTIONS}
    if selection == "max_welfare_nash":
        checks.update(_welfare_maximality(a, b, claimed[2]) if _is_num(claimed[2])
                      else {"welfare_maximality_check_feasible": False})
    cert = certificate if isinstance(certificate, dict) else {}
    checks["exact_certificate_is_an_exact_equilibrium"] = (
        isinstance(cert.get("exact"), dict) and _exact_certificate(a, b, output, cert["exact"]))
    ce = output.get("correlated")
    if ce is not None:
        checks.update(_correlated_checks(a, b, ce, cert.get("correlated_dual")))
        if checks.get("correlated_well_formed") and _is_num(ce.get("welfare")) and _is_num(claimed[2]):
            # every Nash equilibrium is a correlated equilibrium
            checks["correlated_welfare_at_least_nash_welfare"] = ce["welfare"] >= claimed[2] - NASH_CE_TOL * S
    return checks


def _pure_equilibria(a, b):
    m, n = len(a), len(a[0])
    return [(i, j) for i in range(m) for j in range(n)
            if a[i][j] >= max(a[k][j] for k in range(m)) and b[i][j] >= max(b[i][l] for l in range(n))]


def _profile_output(a, b, x, y, method):
    """A float profile in the output contract if it is an epsilon-Nash equilibrium, else None."""
    m, n = len(a), len(a[0])
    out = {"row_strategy": [float(p) for p in x], "column_strategy": [float(q) for q in y], "selection": "nash",
           "correlated": None, "method": method}
    u = math.fsum(out["row_strategy"][i] * a[i][j] * out["column_strategy"][j] for i in range(m) for j in range(n))
    v = math.fsum(out["row_strategy"][i] * b[i][j] * out["column_strategy"][j] for i in range(m) for j in range(n))
    out.update(row_payoff=u, column_payoff=v, welfare=u + v)
    return out if _nash_equilibrium(a, b, out) is not None else None


def nash_pure_search(data):
    """Baseline: search the pure profiles only; the highest-welfare pure equilibrium, or no decision (None)
    when the game has none (matching pennies, Shapley-type cycles, many random games)."""
    a, b = _bimatrix(data)
    pure = _pure_equilibria(a, b)
    if not pure:
        return None
    i, j = max(pure, key=lambda ij: a[ij[0]][ij[1]] + b[ij[0]][ij[1]])
    x, y = [0.0] * len(a), [0.0] * len(a[0])
    x[i], y[j] = 1.0, 1.0
    return {"row_strategy": x, "column_strategy": y, "row_payoff": a[i][j], "column_payoff": b[i][j],
            "welfare": a[i][j] + b[i][j], "selection": "nash", "correlated": None,
            "method": "pure-profile search, highest welfare"}


def _nashpy():
    try:
        import nashpy
    except ImportError:
        return None
    return nashpy


def _lemke_howson(nashpy, a, b):
    import numpy as np
    game = nashpy.Game(np.array(a, dtype=float), np.array(b, dtype=float))
    for label in range(len(a) + len(a[0])):
        try:
            x, y = game.lemke_howson(initial_dropped_label=label)
        except Exception:                       # a third-party pivoting failure is a missed label, not a crash
            continue
        if all(math.isfinite(float(p)) for p in [*x, *y]):
            out = _profile_output(a, b, list(x), list(y), f"lemke_howson (nashpy), dropped label {label}")
            if out is not None:
                return out
    return None


def _polish(a, b, x, y):
    """Snap a learning-dynamics profile to an exact equilibrium on the support it visits (indifference
    solved in floats); the pure profile of its modes is tried too. None when neither is an equilibrium."""
    import numpy as np
    A, B = np.array(a, dtype=float), np.array(b, dtype=float)
    m, n = A.shape
    I = [i for i in range(m) if x[i] > NASH_POLISH]
    J = [j for j in range(n) if y[j] > NASH_POLISH]
    if len(I) == len(J) and I:
        k = len(I)
        try:
            ys = np.linalg.solve(np.vstack([np.column_stack([A[np.ix_(I, J)], -np.ones(k)]),
                                            np.r_[np.ones(k), 0.0]]), np.r_[np.zeros(k), 1.0])
            xs = np.linalg.solve(np.vstack([np.column_stack([B[np.ix_(I, J)].T, -np.ones(k)]),
                                            np.r_[np.ones(k), 0.0]]), np.r_[np.zeros(k), 1.0])
        except np.linalg.LinAlgError:
            ys = xs = None
        if ys is not None and min(ys[:k]) > 0 and min(xs[:k]) > 0:
            px, py = np.zeros(m), np.zeros(n)
            px[I], py[J] = xs[:k], ys[:k]
            out = _profile_output(a, b, (px / px.sum()).tolist(), (py / py.sum()).tolist(),
                                  "damped best response, support polish")
            if out is not None:
                return out
    px, py = np.zeros(m), np.zeros(n)
    px[int(np.argmax(x))], py[int(np.argmax(y))] = 1.0, 1.0
    return _profile_output(a, b, px.tolist(), py.tolist(), "damped best response, pure mode")


def _damped_best_response(a, b):
    """Iterated best response with damping 1/(t + 2) (fictitious-play averaging), checkpoints at 100, 400, 1500
    and 4000 rounds, each followed by a support polish. Converges in zero-sum, 2 x n and potential games; it
    can cycle forever (Shapley's game), so no equilibrium at the last checkpoint is no decision."""
    import numpy as np
    A, B = np.array(a, dtype=float), np.array(b, dtype=float)
    m, n = A.shape
    x, y = np.full(m, 1.0 / m), np.full(n, 1.0 / n)
    t = 0
    for stop in NASH_IBR_CHECKPOINTS:
        while t < stop:
            step = 1.0 / (t + 2)
            bx, by = np.zeros(m), np.zeros(n)
            bx[int(np.argmax(A @ y))] = 1.0
            by[int(np.argmax(x @ B))] = 1.0
            x, y = (1 - step) * x + step * bx, (1 - step) * y + step * by
            t += 1
        out = _polish(a, b, x, y)
        if out is not None:
            return out
    return None


def nash_competitor(data):
    """Competitor: Lemke-Howson complementary pivoting (nashpy, every initially dropped label) when nashpy is
    installed; otherwise damped iterated best response with a support polish. nashpy is not a declared
    dependency and was absent when this genome was built, so the damped dynamics are what normally runs."""
    a, b = _bimatrix(data)
    nashpy = _nashpy()
    return _lemke_howson(nashpy, a, b) if nashpy is not None else _damped_best_response(a, b)


def _nash_truth(a, b):
    """Independent reference for the benchmark: NumPy float support enumeration over every equal-size pair
    with a nondegeneracy screen (no zero weight on a support, no extra best response within 1e-7 of the
    scale, an odd equilibrium count), cross-checked against the HiGHS MILP maximum and minimum equilibrium
    welfare. None when the screen or the cross-check fails (the generator then redraws)."""
    import numpy as np
    A, B = np.array(a, dtype=float), np.array(b, dtype=float)
    m, n = A.shape
    S = _scale(a, b)
    welfare, pure = [], 0
    for k in range(1, min(m, n) + 1):
        for I in combinations(range(m), k):
            for J in combinations(range(n), k):
                rhs = np.r_[np.zeros(k), 1.0]
                try:
                    ys = np.linalg.solve(np.vstack([np.column_stack([A[np.ix_(I, J)], -np.ones(k)]),
                                                    np.r_[np.ones(k), 0.0]]), rhs)
                    xs = np.linalg.solve(np.vstack([np.column_stack([B[np.ix_(I, J)].T, -np.ones(k)]),
                                                    np.r_[np.ones(k), 0.0]]), rhs)
                except np.linalg.LinAlgError:
                    continue
                if min(ys[:k]) < -1e-9 or min(xs[:k]) < -1e-9:
                    continue
                y, x = np.zeros(n), np.zeros(m)
                y[list(J)], x[list(I)] = ys[:k], xs[:k]
                row, col = A @ y, x @ B
                if row.max() > ys[k] + 1e-9 * S or col.max() > xs[k] + 1e-9 * S:
                    continue
                if min(ys[:k].min(), xs[:k].min()) < 1e-9:
                    return None                                     # an equilibrium on the support boundary
                if (np.abs(row - ys[k]) <= 1e-7 * S).sum() > k or (np.abs(col - xs[k]) <= 1e-7 * S).sum() > k:
                    return None                                     # an extra best response: degenerate
                welfare.append(float(ys[k] + xs[k]))
                pure += k == 1
    if not welfare or len(welfare) % 2 == 0:
        return None
    hi, lo = _nash_milp(a, b, "max"), _nash_milp(a, b, "min")
    if hi is None or lo is None or abs(hi[0] - max(welfare)) > NASH_WELFARE_TOL * S \
            or abs(lo[0] - min(welfare)) > NASH_WELFARE_TOL * S:
        return None
    return {"max_welfare": max(welfare), "min_welfare": min(welfare), "equilibria": len(welfare),
            "pure_equilibria": pure, "basis": "NumPy support enumeration with a nondegeneracy screen, "
                                              "cross-checked by HiGHS MILP maximum and minimum welfare"}


def _nash_random(r, low, high):
    m, n = r.randint(low, high), r.randint(low, high)
    return ([[r.randint(-20, 20) for _ in range(n)] for _ in range(m)],
            [[r.randint(-20, 20) for _ in range(n)] for _ in range(m)], f"random:{m}x{n}")


def _nash_coordination(r):
    k = r.randint(3, 5)
    da, db = r.sample(range(6, 30), k), r.sample(range(6, 30), k)
    a = [[da[i] if i == j else r.randint(-3, 3) for j in range(k)] for i in range(k)]
    b = [[db[i] if i == j else r.randint(-3, 3) for j in range(k)] for i in range(k)]
    return a, b, f"coordination:{k}x{k}"


def _nash_no_pure(r):
    if r.random() < 0.4:                                     # Shapley's cyclic game, scaled and perturbed
        base_a, base_b = [[0, 1, 0], [0, 0, 1], [1, 0, 0]], [[0, 0, 1], [1, 0, 0], [0, 1, 0]]
        a = [[10 * v + r.randint(-2, 2) for v in row] for row in base_a]
        b = [[10 * v + r.randint(-2, 2) for v in row] for row in base_b]
        if not _pure_equilibria(a, b):
            return a, b, "no_pure:shapley"
    for _ in range(500):
        a, b, label = _nash_random(r, 2, 4)
        if not _pure_equilibria(a, b):
            return a, b, "no_pure:" + label.split(":")[1]
    raise GenomeError("no-pure generator exhausted its draws")


def _nash_chicken(r):
    k = r.choice([2, 3])
    a = [[r.randint(-12, -4) if i == j else r.randint(2, 12) for j in range(k)] for i in range(k)]
    b = [[a[j][i] + r.randint(-2, 2) for j in range(k)] for i in range(k)]
    return a, b, f"anti_coordination:{k}x{k}"


def nash_instance(seed):
    r = random.Random(3_300_000 + seed)
    kind = ("random", "coordination", "no_pure", "anti_coordination", "large")[seed % 5]
    for _ in range(300):
        if kind == "random":
            a, b, label = _nash_random(r, 2, 4)
        elif kind == "coordination":
            a, b, label = _nash_coordination(r)
        elif kind == "no_pure":
            a, b, label = _nash_no_pure(r)
        elif kind == "anti_coordination":
            a, b, label = _nash_chicken(r)
        else:
            a, b, label = _nash_random(r, 5, 6)
        truth = _nash_truth(a, b)
        if truth is not None:
            return ({"row_payoffs": a, "column_payoffs": b, "name": label, "seed": 33_000 + seed},
                    {**truth, "kind": kind})
    raise GenomeError("no nondegenerate game drawn for this seed")


def nash_subregion(data):
    count = len(_pure_equilibria(data["row_payoffs"], data["column_payoffs"]))
    return "no_pure" if count == 0 else "one_pure" if count == 1 else "multi_pure"


def nash_score(data, truth, output):
    """A verified equilibrium scores 0.5 + 0.5 x its welfare's position between the worst and best equilibrium
    welfare (1.0 when all equilibria tie); not an equilibrium, or a false claim of maximal welfare, is wrong."""
    if output is None:
        return {"quality": 0.0, "category": "abstain"}
    a, b = _bimatrix(data)
    eq = _nash_equilibrium(a, b, output)
    if eq is None or output.get("selection") not in SELECTIONS:
        return {"quality": -1.0, "category": "wrong"}
    S = _scale(a, b)
    w, hi, lo = eq[0] + eq[1], truth["max_welfare"], truth["min_welfare"]
    if output["selection"] == "max_welfare_nash" and w < hi - NASH_WELFARE_TOL * S:
        return {"quality": -1.0, "category": "wrong"}
    rel = 1.0 if hi - lo <= NASH_WELFARE_TOL * S else min(1.0, max(0.0, (w - lo) / (hi - lo)))
    return {"quality": 0.5 + 0.5 * rel, "category": "correct"}


# =================================================================== 2. direct-mechanism DSIC and IR check
MECH_MAX_AGENTS, MECH_MAX_TYPES, MECH_MAX_OUTCOMES, MECH_MAX_PROFILES = 4, 10, 64, 4096
MECH_MAX_DEVIATIONS, MECH_MAX_ABS, MECH_SAMPLES = 100_000, 1e6, 64
MECH_REL_TOL = 1e-12                     # a claimed magnitude against the float of its exact value, relative
MECH_VERDICTS = ("HOLDS", "VIOLATION")


def _mech(data):
    _obj(data)
    outcomes = data.get("outcomes")
    if (not isinstance(outcomes, list) or not 1 <= len(outcomes) <= MECH_MAX_OUTCOMES
            or not all(isinstance(o, str) and 1 <= len(o) <= 64 for o in outcomes)
            or len(set(outcomes)) != len(outcomes)):
        raise GenomeError(f"outcomes: 1-{MECH_MAX_OUTCOMES} unique labels")
    agents = data.get("agents")
    if not isinstance(agents, list) or not 1 <= len(agents) <= MECH_MAX_AGENTS:
        raise GenomeError(f"agents: a list of 1-{MECH_MAX_AGENTS} agents")
    values = []
    for ag in agents:
        v = ag.get("values") if isinstance(ag, dict) else None
        if (not isinstance(v, list) or not 1 <= len(v) <= MECH_MAX_TYPES
                or any(not isinstance(row, list) or len(row) != len(outcomes) for row in v)):
            raise GenomeError(f"each agent: values[type][outcome] for 1-{MECH_MAX_TYPES} types and every outcome")
        values.append([[finite(x, low=-MECH_MAX_ABS, high=MECH_MAX_ABS, name="value") for x in row] for row in v])
    n, k = len(values), [len(v) for v in values]
    profiles = math.prod(k)
    if profiles > MECH_MAX_PROFILES:
        raise GenomeError(f"more than {MECH_MAX_PROFILES} type profiles")
    alloc, pay = data.get("allocation"), data.get("payments")
    if not isinstance(alloc, list) or len(alloc) != profiles:
        raise GenomeError("allocation: one outcome index per type profile (lexicographic order)")
    alloc = [bounded_int(o, low=0, high=len(outcomes) - 1, name="allocation") for o in alloc]
    if not isinstance(pay, list) or len(pay) != profiles or any(not isinstance(p, list) or len(p) != n for p in pay):
        raise GenomeError("payments: one payment per agent per type profile (lexicographic order)")
    pay = [[finite(x, low=-MECH_MAX_ABS, high=MECH_MAX_ABS, name="payment") for x in p] for p in pay]
    outside = data.get("outside_option", [0.0] * n)
    if not isinstance(outside, list) or len(outside) != n:
        raise GenomeError("outside_option: one value per agent")
    outside = [finite(x, low=-MECH_MAX_ABS, high=MECH_MAX_ABS, name="outside option") for x in outside]
    # the float arms' tolerance unit: the largest magnitude stated (1 only when all are zero), never floored at 1
    scale = max(abs(x) for x in [v for agent in values for row in agent for v in row]
                + [p for row in pay for p in row] + outside) or 1.0
    return {"n": n, "k": k, "values": values, "alloc": alloc, "pay": pay, "outside": outside, "scale": scale}


def _deviations(k):
    return sum(math.prod(k) * (k[i] - 1) for i in range(len(k)))


def mech_solve(data, budget):
    M = _mech(data)
    if data.get("randomized"):
        return _abstain("randomized mechanisms need expected utilities over lotteries; only deterministic "
                        "allocation and payment tables are in competence")
    n, k = M["n"], M["k"]
    if _deviations(k) > MECH_MAX_DEVIATIONS:
        return _abstain(f"{_deviations(k)} unilateral misreports exceed {MECH_MAX_DEVIATIONS}", type_counts=k)
    V = [[[Fraction(x) for x in row] for row in agent] for agent in M["values"]]
    P = [[Fraction(x) for x in row] for row in M["pay"]]
    out_opt = [Fraction(x) for x in M["outside"]]
    alloc = M["alloc"]
    mult = [math.prod(k[i + 1:]) for i in range(n)]
    best, positive = None, 0
    for i in range(n):
        others = [j for j in range(n) if j != i]
        for t in range(k[i]):
            for rest in product(*[range(k[j]) for j in others]):
                base = sum(s * mult[j] for j, s in zip(others, rest))
                truthful = base + t * mult[i]
                u0 = V[i][t][alloc[truthful]] - P[truthful][i]
                for r in range(k[i]):
                    if r == t:
                        continue
                    lie = base + r * mult[i]
                    g = V[i][t][alloc[lie]] - P[lie][i] - u0
                    positive += g > 0
                    if best is None or g > best[0]:          # strict: keeps the lexicographically first maximum
                        best = (g, i, t, rest, r)
    worst, short = None, 0
    for i in range(n):
        for idx, prof in enumerate(product(*[range(x) for x in k])):
            s = V[i][prof[i]][alloc[idx]] - P[idx][i] - out_opt[i]
            short += s < 0
            if worst is None or s < worst[0]:
                worst = (s, i, prof)
    top = best[0] if best else Fraction(0)
    dsic_holds, ir_holds = top <= 0, worst[0] >= 0
    dsic = {"holds": dsic_holds, "max_gain": float(top), "witness": None}
    if not dsic_holds:
        _, i, t, rest, r = best
        dsic["witness"] = {"agent": i, "true_type": t, "reported_type": r, "others": list(rest), "gain": float(top)}
    ir = {"holds": ir_holds, "min_slack": float(worst[0]), "witness": None}
    if not ir_holds:
        ir["witness"] = {"agent": worst[1], "profile": list(worst[2]), "slack": float(worst[0])}
    out = {"verdict": "HOLDS" if dsic_holds and ir_holds else "VIOLATION", "dsic": dsic, "ir": ir}
    return answer(out, {"method": "exhaustive enumeration of every unilateral misreport and every type profile in "
                                  "exact rational arithmetic; witnesses are the lexicographically first extremes "
                                  "in (agent, true type, others, report) and (agent, profile) order",
                        "misreports_checked": _deviations(k), "profiles": math.prod(k), "type_counts": k,
                        "profitable_misreports": positive, "participation_shortfalls": short,
                        "properties": {"DSIC": "dominant-strategy incentive compatibility (weak: a zero-gain "
                                               "misreport is not a violation)",
                                       "IR": "ex-post individual rationality against each agent's outside option"}})


def _mech_shape(M, output):
    """The output's claims as plain values, or None if malformed (never raises)."""
    n, k = M["n"], M["k"]
    if not isinstance(output, dict) or output.get("verdict") not in MECH_VERDICTS:
        return None
    dsic, ir = output.get("dsic"), output.get("ir")
    if not isinstance(dsic, dict) or not isinstance(ir, dict):
        return None
    if type(dsic.get("holds")) is not bool or not _is_num(dsic.get("max_gain")) \
            or type(ir.get("holds")) is not bool or not _is_num(ir.get("min_slack")):
        return None
    w, z = dsic.get("witness"), ir.get("witness")
    if w is not None:
        if (not isinstance(w, dict) or not all(_is_int(w.get(f)) for f in ("agent", "true_type", "reported_type"))
                or not 0 <= w["agent"] < n or not isinstance(w.get("others"), list) or len(w["others"]) != n - 1
                or not _is_num(w.get("gain"))):
            return None
        i = w["agent"]
        others = [j for j in range(n) if j != i]
        if (not 0 <= w["true_type"] < k[i] or not 0 <= w["reported_type"] < k[i]
                or not all(_is_int(s) and 0 <= s < k[j] for j, s in zip(others, w["others"]))):
            return None
    if z is not None:
        if (not isinstance(z, dict) or not _is_int(z.get("agent")) or not 0 <= z["agent"] < n
                or not isinstance(z.get("profile"), list) or len(z["profile"]) != n
                or not all(_is_int(s) and 0 <= s < k[j] for j, s in enumerate(z["profile"]))
                or not _is_num(z.get("slack"))):
            return None
    return dsic, ir, w, z


def _mech_index(k, prof):
    idx = 0
    for size, t in zip(k, prof):
        idx = idx * size + t
    return idx


def _replay_gain(M, w):
    """Direct replay of one misreport with exact arithmetic: (true profile, reported profile) -> gain."""
    i, k = w["agent"], M["k"]
    truth = list(w["others"][:i]) + [w["true_type"]] + list(w["others"][i:])
    lie = truth[:i] + [w["reported_type"]] + truth[i + 1:]
    vt = M["values"][i][w["true_type"]]
    a, b = _mech_index(k, truth), _mech_index(k, lie)
    return (Fraction(vt[M["alloc"][b]]) - Fraction(M["pay"][b][i])) - (Fraction(vt[M["alloc"][a]])
                                                                      - Fraction(M["pay"][a][i]))


def _replay_slack(M, z):
    i = z["agent"]
    idx = _mech_index(M["k"], z["profile"])
    return (Fraction(M["values"][i][z["profile"][i]][M["alloc"][idx]]) - Fraction(M["pay"][idx][i])
            - Fraction(M["outside"][i]))


def _mech_close(claimed, exact):
    """A claimed float against the float of the verifier's exact value, relative to that value's own magnitude
    (no floor at 1: a mechanism stated in small units is held to the same relative precision)."""
    target = float(exact)
    return abs(claimed - target) <= MECH_REL_TOL * abs(target)


def mech_verify(data, output, certificate):
    M = _mech(data)
    shape = _mech_shape(M, output)
    if shape is None:
        return {"output_well_formed": False}
    dsic, ir, w, z = shape
    n, k = M["n"], M["k"]
    if _deviations(k) > MECH_MAX_DEVIATIONS:
        return {"output_well_formed": True, "independent_enumeration_feasible": False}
    # independent re-enumeration, organised by true profile and keyed by tuples (the solver indexes by radix)
    profiles = list(product(*[range(x) for x in k]))
    outcome = dict(zip(profiles, M["alloc"]))
    paid = dict(zip(profiles, M["pay"]))
    value = [[[Fraction(x) for x in row] for row in agent] for agent in M["values"]]
    charge = {p: [Fraction(x) for x in paid[p]] for p in profiles}
    gains = {}
    for prof in profiles:
        for i in range(n):
            t = prof[i]
            honest = value[i][t][outcome[prof]] - charge[prof][i]
            for r in range(k[i]):
                if r != t:
                    lie = prof[:i] + (r,) + prof[i + 1:]
                    gains[(i, t, prof[:i] + prof[i + 1:], r)] = value[i][t][outcome[lie]] - charge[lie][i] - honest
    top = max(gains.values(), default=Fraction(0))
    first = min((key for key, g in gains.items() if g == top), default=None) if top > 0 else None
    slacks = {(i, prof): value[i][prof[i]][outcome[prof]] - charge[prof][i] - Fraction(M["outside"][i])
              for i in range(n) for prof in profiles}
    low = min(slacks.values())
    worst = min(key for key, s in slacks.items() if s == low) if low < 0 else None
    cert = certificate if isinstance(certificate, dict) else {}
    checks = {"output_well_formed": True,
              "verdict_matches_the_properties": output["verdict"] == ("HOLDS" if dsic["holds"] and ir["holds"]
                                                                      else "VIOLATION"),
              "dsic_max_gain_recomputed": _mech_close(dsic["max_gain"], top),
              "dsic_holds_recomputed": dsic["holds"] is (top <= 0),
              "dsic_witness_is_the_first_maximal_misreport":
                  (w is None) if first is None else
                  (w is not None and (w["agent"], w["true_type"], tuple(w["others"]), w["reported_type"]) == first),
              "ir_min_slack_recomputed": _mech_close(ir["min_slack"], low),
              "ir_holds_recomputed": ir["holds"] is (low >= 0),
              "ir_witness_is_the_first_worst_profile":
                  (z is None) if worst is None else
                  (z is not None and (z["agent"], tuple(z["profile"])) == worst),
              "certificate_counts_recomputed":
                  cert.get("profitable_misreports") == sum(1 for g in gains.values() if g > 0)
                  and cert.get("participation_shortfalls") == sum(1 for s in slacks.values() if s < 0)}
    if w is not None:
        g = _replay_gain(M, w)
        checks["dsic_witness_gain_replayed"] = g > 0 and _mech_close(w["gain"], g)
    if z is not None:
        s = _replay_slack(M, z)
        checks["ir_witness_slack_replayed"] = s < 0 and _mech_close(z["slack"], s)
    return checks


def _mech_tensors(M):
    """NumPy utility tensors over exact rationals (object arrays of Fractions): U[i] has the reported-profile
    axes then the agent's true type."""
    import numpy as np
    n, k = M["n"], M["k"]
    alloc = np.array(M["alloc"], dtype=int).reshape(k)
    pay = np.array([[Fraction(x) for x in row] for row in M["pay"]], dtype=object).reshape(k + [n])
    tensors = []
    for i in range(n):
        val = np.array([[Fraction(x) for x in row] for row in M["values"][i]], dtype=object)  # (types, outcomes)
        tensors.append(np.moveaxis(val[:, alloc], 0, -1) - pay[..., i][..., None])
    return tensors


def _mech_truth(M):
    """Benchmark truth by NumPy tensor arithmetic over exact rationals (a third method, organised by array axes):
    the holds flags and the counts of each kind of violation are exact, as the solver's and the verifier's
    semantics are; the largest misreport gain and the smallest participation slack are the floats of their
    exact values."""
    import numpy as np
    n, k = M["n"], M["k"]
    top, count, slack_min, short = None, 0, None, 0
    for i, U in enumerate(_mech_tensors(M)):
        Ui = np.moveaxis(U, i, -2)                                  # (... others ..., report, true type)
        honest = np.diagonal(Ui, axis1=-2, axis2=-1)                # (... others ..., true type)
        if k[i] > 1:
            gain = Ui - honest[..., None, :]
            off = gain[~np.broadcast_to(np.eye(k[i], dtype=bool), gain.shape)]   # every misreport, no truth
            best = max(off)
            top = best if top is None or best > top else top
            count += sum(1 for g in off if g > 0)
        slack = (honest - Fraction(M["outside"][i])).ravel()
        low = min(slack)
        slack_min = low if slack_min is None or low < slack_min else slack_min
        short += sum(1 for x in slack if x < 0)
    top = Fraction(0) if top is None else top
    return {"dsic_max_gain": float(top), "dsic_holds": top <= 0, "profitable_misreports": count,
            "ir_min_slack": float(slack_min), "ir_holds": slack_min >= 0, "participation_shortfalls": short}


def _float_gain(M, w):
    i, k = w["agent"], M["k"]
    truth = w["others"][:i] + [w["true_type"]] + w["others"][i:]
    lie = truth[:i] + [w["reported_type"]] + truth[i + 1:]
    vt = M["values"][i][w["true_type"]]
    a, b = _mech_index(k, truth), _mech_index(k, lie)
    return (vt[M["alloc"][b]] - M["pay"][b][i]) - (vt[M["alloc"][a]] - M["pay"][a][i])


def mech_score(data, truth, output):
    """Both property claims must match the truth; a violated property's witness must replay as a genuine
    violation. Quality 1.0 when both hold, else 0.5 + 0.5 x the mean share of the largest violation found."""
    if output is None:
        return {"quality": 0.0, "category": "abstain"}
    M = _mech(data)
    shape = _mech_shape(M, output)
    wrong = {"quality": -1.0, "category": "wrong"}
    if shape is None:
        return wrong
    dsic, ir, w, z = shape
    if dsic["holds"] != truth["dsic_holds"] or ir["holds"] != truth["ir_holds"]:
        return wrong
    if output["verdict"] != ("HOLDS" if dsic["holds"] and ir["holds"] else "VIOLATION"):
        return wrong
    credits = []                                    # witnesses replay exactly, as the truth is exact
    if not truth["dsic_holds"]:
        g = _replay_gain(M, w) if w is not None else Fraction(0)
        if g <= 0:
            return wrong
        credits.append(min(1.0, float(g) / truth["dsic_max_gain"]))
    if not truth["ir_holds"]:
        s = _replay_slack(M, z) if z is not None else Fraction(0)
        if s >= 0:
            return wrong
        credits.append(min(1.0, float(s) / truth["ir_min_slack"]))
    return {"quality": 1.0 if not credits else 0.5 + 0.5 * sum(credits) / len(credits), "category": "correct"}


def _mech_output(dsic_gain, dsic_witness, ir_slack, ir_witness, tol, method):
    dsic_holds, ir_holds = dsic_gain <= tol, ir_slack >= -tol
    return {"verdict": "HOLDS" if dsic_holds and ir_holds else "VIOLATION",
            "dsic": {"holds": dsic_holds, "max_gain": dsic_gain, "witness": None if dsic_holds else dsic_witness},
            "ir": {"holds": ir_holds, "min_slack": ir_slack, "witness": None if ir_holds else ir_witness},
            "method": method}


def mech_sampled(data):
    """Baseline: random sampled misreports and profiles (64 of each, seeded); nothing found is reported as
    HOLDS, so rare violations are missed."""
    M = _mech(data)
    n, k = M["n"], M["k"]
    r = random.Random(bounded_int(data.get("seed", 0), low=0, high=10 ** 9, name="seed") * 7919 + 17)
    liars = [i for i in range(n) if k[i] > 1]
    best, best_w = -math.inf, None
    for _ in range(MECH_SAMPLES if liars else 0):
        i = r.choice(liars)
        rest = [r.randrange(k[j]) for j in range(n) if j != i]
        t = r.randrange(k[i])
        rep = r.choice([x for x in range(k[i]) if x != t])
        w = {"agent": i, "true_type": t, "reported_type": rep, "others": rest}
        g = _float_gain(M, w)
        if g > best:
            best, best_w = g, {**w, "gain": g}
    worst, worst_z = math.inf, None
    for _ in range(MECH_SAMPLES):
        i = r.randrange(n)
        prof = [r.randrange(x) for x in k]
        idx = _mech_index(k, prof)
        s = M["values"][i][prof[i]][M["alloc"][idx]] - M["pay"][idx][i] - M["outside"][i]
        if s < worst:
            worst, worst_z = s, {"agent": i, "profile": prof, "slack": s}
    return _mech_output(best if liars else 0.0, best_w, worst, worst_z, 1e-9 * M["scale"],
                        f"random sampling: {MECH_SAMPLES} misreports and {MECH_SAMPLES} profiles")


def mech_milp(data):
    """Competitor: one HiGHS MILP per agent for the maximum regret - one-hot true type, report and others'
    profile, with a selector pi(t, r, q) <= each one-hot (sum pi = 1) - and one LP over the profile simplex for
    the smallest participation slack."""
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, linprog, milp
    from scipy.sparse import coo_matrix
    M = _mech(data)
    n, k = M["n"], M["k"]
    if _deviations(k) > MECH_MAX_DEVIATIONS:
        return None
    best, best_w = 0.0 if all(x == 1 for x in k) else -math.inf, None
    for i in range(n):
        K = k[i]
        if K < 2:
            continue
        others = [j for j in range(n) if j != i]
        rests = list(product(*[range(k[j]) for j in others]))
        triples = [(t, r, q) for t in range(K) for r in range(K) if r != t for q in range(len(rests))]
        g = np.array([_float_gain(M, {"agent": i, "true_type": t, "reported_type": r, "others": list(rests[q])})
                      for t, r, q in triples])
        nt, Q = len(triples), len(rests)
        oy, oz, ow = nt, nt + K, nt + 2 * K
        size = nt + 2 * K + Q
        rr, cc, vv, lo, hi = [], [], [], [], []

        def row(entries, low, high):
            for col, val in entries:
                rr.append(len(lo))
                cc.append(col)
                vv.append(val)
            lo.append(low)
            hi.append(high)
        row([(z, 1.0) for z in range(nt)], 1.0, 1.0)
        row([(oy + t, 1.0) for t in range(K)], 1.0, 1.0)
        row([(oz + t, 1.0) for t in range(K)], 1.0, 1.0)
        row([(ow + q, 1.0) for q in range(Q)], 1.0, 1.0)
        for t in range(K):
            row([(oy + t, 1.0), (oz + t, 1.0)], -np.inf, 1.0)
        for z, (t, r, q) in enumerate(triples):
            row([(z, 1.0), (oy + t, -1.0)], -np.inf, 0.0)
            row([(z, 1.0), (oz + r, -1.0)], -np.inf, 0.0)
            row([(z, 1.0), (ow + q, -1.0)], -np.inf, 0.0)
        A = coo_matrix((vv, (rr, cc)), shape=(len(lo), size)).tocsr()
        res = milp(np.r_[-g, np.zeros(2 * K + Q)], constraints=LinearConstraint(A, lo, hi),
                   integrality=np.r_[np.zeros(nt), np.ones(2 * K + Q)], bounds=Bounds(0.0, 1.0),
                   options={"time_limit": 10.0, "mip_rel_gap": 0.0})
        if res.status != 0:
            return None
        z = int(np.argmax(res.x[:nt]))
        t, r, q = triples[z]
        if g[z] > best:
            best, best_w = float(g[z]), {"agent": i, "true_type": t, "reported_type": r, "others": list(rests[q]),
                                         "gain": float(g[z])}
    pairs = [(i, prof) for i in range(n) for prof in product(*[range(x) for x in k])]
    slack = np.array([M["values"][i][prof[i]][M["alloc"][_mech_index(k, prof)]]
                      - M["pay"][_mech_index(k, prof)][i] - M["outside"][i] for i, prof in pairs])
    res = linprog(slack, A_eq=np.ones((1, len(pairs))), b_eq=[1.0], bounds=[(0, None)] * len(pairs),
                  method="highs")
    if res.status != 0:
        return None
    z = int(np.argmax(res.x))
    worst_z = {"agent": pairs[z][0], "profile": list(pairs[z][1]), "slack": float(slack[z])}
    return _mech_output(best, best_w, float(slack[z]), worst_z, 1e-9 * M["scale"],
                        "HiGHS MILP for maximum regret per agent; LP for minimum participation slack")


def _mech_tables(k, rule):
    alloc, pay = [], []
    for prof in product(*[range(x) for x in k]):
        o, p = rule(prof)
        alloc.append(o)
        pay.append(p)
    return alloc, pay


def _mech_auction(r, kind):
    rare = kind in ("second_price_bug", "rare_fee")             # planted on one corner of a wider type space
    n = 3 if rare else r.choice([2, 3])
    k = [r.randint(4, 6) if rare else r.randint(3, 5) for _ in range(n)]
    levels = [sorted(r.sample(range(1, 16), x)) for x in k]
    reserve = r.choice([0, 0, r.randint(2, 6)])
    fee = r.randint(1, 3)
    outcomes = ["none"] + [f"agent{i}" for i in range(n)]
    agents = [{"values": [[lv if o == i + 1 else 0 for o in range(n + 1)] for lv in levels[i]]} for i in range(n)]

    def rule(prof):
        bids = [levels[i][t] for i, t in enumerate(prof)]
        pay = [0] * n
        if kind == "rare_fee" and all(t == 0 for t in prof):     # a participation fee charged on one profile
            pay = [fee] * n
        top = max(bids)
        if top < reserve:
            return 0, pay
        w = bids.index(top)                                        # ties go to the lowest index
        second = max([x for j, x in enumerate(bids) if j != w] + [reserve])
        if kind == "first_price" or (kind == "second_price_bug" and prof[w] == k[w] - 1
                                     and all(t == 0 for j, t in enumerate(prof) if j != w)):
            pay[w] += bids[w]                                      # pay-your-bid (planted on one corner for the bug)
        else:
            pay[w] += second
        return w + 1, pay
    alloc, pay = _mech_tables(k, rule)
    expected = {"second_price": (True, True)}.get(kind)
    return {"agents": agents, "outcomes": outcomes, "allocation": alloc, "payments": pay}, expected, \
        f"{kind}:n={n},reserve={reserve}"


def _mech_project(r):
    n = r.choice([2, 3])
    k = [r.randint(3, 5) for _ in range(n)]
    levels = [sorted(r.sample(range(0, 13), x)) for x in k]
    share = r.randint(3, 8)
    variant = r.choice(["clarke", "proportional"])
    agents = [{"values": [[0, lv] for lv in levels[i]]} for i in range(n)]

    def rule(prof):
        theta = [levels[i][t] for i, t in enumerate(prof)]
        if variant == "proportional":                              # pay a share proportional to the report
            total = sum(theta)
            build = total >= share * n
            return int(build), [round(share * n * x / total, 4) if build else 0 for x in theta]
        w = [x - share for x in theta]
        build = sum(w) >= 0
        pay = []
        for i in range(n):
            rest = sum(w) - w[i]
            pivot = max(rest, 0) - (rest if build else 0)           # Clarke tax: the externality on the others
            pay.append((share if build else 0) + pivot)
        return int(build), pay
    alloc, pay = _mech_tables(k, rule)
    expected = (True, None) if variant == "clarke" else None
    return {"agents": agents, "outcomes": ["no", "build"], "allocation": alloc, "payments": pay}, expected, \
        f"public_project:{variant},n={n}"


def _mech_random(r):
    n = r.choice([2, 3])
    k = [r.randint(2, 4) for _ in range(n)]
    nout = r.randint(2, 4)
    agents = [{"values": [[r.randint(0, 10) for _ in range(nout)] for _ in range(x)]} for x in k]
    alloc, pay = _mech_tables(k, lambda prof: (r.randrange(nout), [r.randint(-2, 8) for _ in range(n)]))
    return {"agents": agents, "outcomes": [f"o{j}" for j in range(nout)], "allocation": alloc, "payments": pay}, \
        None, f"random_mechanism:n={n}"


def mech_instance(seed):
    r = random.Random(4_400_000 + seed)
    kind = ("second_price", "first_price", "second_price_bug", "public_project", "fee_or_random")[seed % 5]
    if kind == "public_project":
        data, expected, label = _mech_project(r)
    elif kind == "fee_or_random":
        data, expected, label = _mech_auction(r, "rare_fee") if (seed // 5) % 2 == 0 else _mech_random(r)
    else:
        data, expected, label = _mech_auction(r, kind)
    data = {**data, "name": label, "seed": 44_000 + seed}
    truth = _mech_truth(_mech(data))
    if expected is not None and (truth["dsic_holds"] != expected[0]
                                 or (expected[1] is not None and truth["ir_holds"] != expected[1])):
        raise GenomeError("mechanism generator disagrees with its independent NumPy enumeration")
    return data, {**truth, "kind": label.split(":")[0]}


def mech_subregion(data):
    return data.get("name", "mechanism").split(":")[0]


# =================================================================== 3. liveness under weak fairness
LV_NATIVE_STATES, LV_MAX_TRACE = 20_000, 1000
LV_BMC_DEPTH, LV_Z3_SECONDS = 10, 4.0
LV_COUNTEREXAMPLES = ("lasso", "deadlock")


def _live(data):
    _obj(data)
    system = data.get("system")
    if not isinstance(system, dict):
        raise GenomeError("system: {variables, commands}; goal: a boolean expression")
    if "goal" not in data:
        raise GenomeError("goal: a boolean expression over the variables")
    try:
        sysm = _mc_system({"system": {"variables": system.get("variables"), "commands": system.get("commands"),
                                      "invariant": data["goal"]}})
    except GenomeError as exc:
        raise GenomeError(str(exc).replace("invariant", "goal")) from None
    names = [c[0] for c in sysm["commands"]]
    fair = data.get("fair", names)
    if (not isinstance(fair, list) or not all(isinstance(f, str) for f in fair) or len(set(fair)) != len(fair)
            or any(f not in names for f in fair)):
        raise GenomeError("fair: a list of distinct command names (default: every command is weakly fair)")
    return sysm, tuple(sorted(names.index(f) for f in fair))


def _live_scope(data):
    if data.get("property", "liveness") != "liveness":
        return "only 'every fair run eventually reaches the goal' is in competence (no general LTL)"
    if data.get("fairness", "weak") != "weak":
        return "only weak fairness is in competence (strong fairness needs Streett refinement of the SCCs)"
    return None


def _trace_digest(seq):
    h = hashlib.sha256()
    for s in seq:
        h.update((",".join(map(str, s)) + ";").encode())
    return "sha256:" + h.hexdigest()


def _tarjan(adj):
    """Iterative Tarjan: strongly connected components of a graph given as successor lists."""
    size = len(adj)
    index, low, on = [-1] * size, [0] * size, [False] * size
    stack, comps, counter = [], [], 0
    for root in range(size):
        if index[root] != -1:
            continue
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on[root] = True
        work = [(root, 0)]
        while work:
            v, pos = work[-1]
            if pos < len(adj[v]):
                work[-1] = (v, pos + 1)
                w = adj[v][pos]
                if index[w] == -1:
                    index[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    on[w] = True
                    work.append((w, 0))
                elif on[w]:
                    low[v] = min(low[v], index[w])
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[v])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop()
                    on[w] = False
                    comp.append(w)
                    if w == v:
                        break
                comps.append(comp)
    return comps


def _walk(edges, inside, src, accept):
    """BFS inside a node set from src to the first node satisfying accept: [(command, node), ...] or None."""
    if accept(src):
        return []
    prev, queue = {src: None}, deque([src])
    while queue:
        v = queue.popleft()
        for c, w in edges[v]:
            if w in inside and w not in prev:
                prev[w] = (v, c)
                if accept(w):
                    path = []
                    while prev[w] is not None:
                        u, cmd = prev[w]
                        path.append((cmd, w))
                        w = u
                    return path[::-1]
                queue.append(w)
    return None


def _fair_cycle(edges, enabled, comp, entry, fair):
    """A closed walk from entry inside one SCC that, for each fair command, visits a state where it is disabled
    or takes it: weakly fair by construction."""
    inside, steps, cur = set(comp), [], entry
    for a in fair:
        disabled = {v for v in comp if not enabled[v] >> a & 1}
        if disabled:
            path = _walk(edges, inside, cur, lambda v: v in disabled)
            steps += path
            cur = path[-1][1] if path else cur
        else:
            path = _walk(edges, inside, cur, lambda v: any(c == a and w in inside for c, w in edges[v]))
            steps += path
            cur = path[-1][1] if path else cur
            w = next(w for c, w in edges[cur] if c == a and w in inside)
            steps.append((a, w))
            cur = w
    if not steps:
        c, w = next((c, w) for c, w in edges[entry] if w in inside)
        steps.append((c, w))
        cur = w
    return steps + _walk(edges, inside, cur, lambda v: v == entry)


def live_solve(data, budget):
    sysm, fair = _live(data)
    scope = _live_scope(data)
    if scope:
        return _abstain(scope)
    cmds, goal = _mc_compiled(sysm)
    lo, hi = sysm["lo"], sysm["hi"]
    deadline = time.perf_counter() + max(0.5, float((budget or {}).get("latency_s", 5.0)))
    index, states, parent, enabled, edges = {}, [], [], [], []
    for s0 in product(*sysm["inits"]):
        if s0 not in index and not goal(s0):
            index[s0] = len(states)
            states.append(s0)
            parent.append(None)
    head = 0
    while head < len(states):                       # breadth first: node ids are in nondecreasing depth
        s = states[head]
        mask, out = 0, []
        for ci, t in _mc_step(cmds, lo, hi, s):
            mask |= 1 << ci
            if goal(t):
                continue
            if t not in index:
                index[t] = len(states)
                states.append(t)
                parent.append((head, ci))
            out.append((ci, index[t]))
        enabled.append(mask)
        edges.append(out)
        head += 1
        if len(states) > LV_NATIVE_STATES:
            return _abstain(f"the goal-avoiding region exceeds {LV_NATIVE_STATES} states (state explosion)",
                            states_explored=len(states))
        if head % 256 == 0 and time.perf_counter() > deadline:
            return _unknown("latency budget exhausted", states_explored=len(states))
    comps = _tarjan([sorted({w for _, w in out}) for out in edges])
    region = {"region_states": len(states), "sccs": len(comps)}
    dead = next((v for v in range(len(states)) if enabled[v] == 0), None)
    fair_comp = None
    for comp in comps:
        inside = set(comp)
        if len(comp) == 1 and not any(w == comp[0] for _, w in edges[comp[0]]):
            continue                                                 # trivial: no cycle
        if all(any(not enabled[v] >> a & 1 for v in comp)
               or any(c == a and w in inside for v in comp for c, w in edges[v]) for a in fair):
            if fair_comp is None or min(comp) < min(fair_comp):
                fair_comp = comp
    if dead is None and fair_comp is None:
        return answer({"verdict": "HOLDS", "region_states": len(states)},
                      {"method": "breadth-first region of goal-avoiding states, iterative Tarjan SCCs, weak-fairness "
                                 "filter: no reachable deadlock and no weakly fair goal-avoiding SCC",
                       **region, "region_digest": _mc_digest(states),
                       "fair_commands": [cmds[a][0] for a in fair], "state_order": sysm["names"]})
    use_dead = dead is not None and (fair_comp is None or dead <= min(fair_comp))
    loop = dead if use_dead else min(fair_comp)
    stem, v = [], loop
    while parent[v] is not None:
        u, c = parent[v]
        stem.append((c, v))
        v = u
    stem.reverse()
    root = v
    cycle = [] if use_dead else _fair_cycle(edges, enabled, fair_comp, loop, fair)
    if len(stem) + len(cycle) > LV_MAX_TRACE:
        return _unknown(f"counterexample longer than {LV_MAX_TRACE} steps", **region)
    seq = [states[root]] + [states[w] for _, w in stem] + [states[w] for _, w in cycle]
    out = {"verdict": "VIOLATED", "counterexample": "deadlock" if use_dead else "lasso",
           "initial": list(states[root]), "stem": [cmds[c][0] for c, _ in stem],
           "cycle": [cmds[c][0] for c, _ in cycle], "loop_state": list(states[loop]),
           "trace_digest": _trace_digest(seq)}
    return answer(out, {"method": "breadth-first region, iterative Tarjan SCCs, weak-fairness filter; shortest "
                                  "stem to the earliest deadlock or weakly fair SCC, then a covering closed walk",
                        **region, "fair_commands": [cmds[a][0] for a in fair], "state_order": sysm["names"]})


def _live_enabled(sysm, cmd, state):
    """The verifier's own semantics (recursive interpreter): the successor of state under cmd, or None."""
    env = dict(zip(sysm["names"], state))
    if not _mc_eval(cmd[1], env):
        return None
    nxt = list(state)
    for i, e in cmd[2]:
        v = _mc_eval(e, env)
        if not sysm["lo"][i] <= v <= sysm["hi"][i]:
            return None
        nxt[i] = v
    return tuple(nxt)


def _live_replay(sysm, fair, output):
    """Replay a counterexample step by step from an initial state; check goal avoidance and weak fairness."""
    n = len(sysm["names"])
    initial, loop = output.get("initial"), output.get("loop_state")
    stem, cycle, kind = output.get("stem"), output.get("cycle"), output.get("counterexample")
    if (not isinstance(initial, list) or len(initial) != n or not all(_is_int(x) for x in initial)
            or not isinstance(loop, list) or len(loop) != n or not all(_is_int(x) for x in loop)
            or not isinstance(stem, list) or not isinstance(cycle, list) or kind not in LV_COUNTEREXAMPLES
            or len(stem) + len(cycle) > LV_MAX_TRACE or not all(isinstance(c, str) for c in stem + cycle)):
        return {"counterexample_well_formed": False}
    by_name = {c[0]: c for c in sysm["commands"]}

    def avoid(s):
        return not _mc_eval(sysm["invariant"], dict(zip(sysm["names"], s)))
    s = tuple(initial)
    seq, replays = [s], all(x in init for x, init in zip(initial, sysm["inits"]))
    for name in stem:
        t = _live_enabled(sysm, by_name[name], s) if name in by_name else None
        if t is None:
            replays = False
            break
        s = t
        seq.append(s)
    at_loop = replays and list(s) == loop
    visited = [s]
    taken = set()
    if at_loop and kind == "lasso":
        for name in cycle:
            t = _live_enabled(sysm, by_name[name], s) if name in by_name else None
            if t is None:
                replays = False
                break
            taken.add(name)
            s = t
            seq.append(s)
            visited.append(s)
    checks = {"counterexample_well_formed": True, "starts_in_an_initial_state": seq[0] == tuple(initial)
              and all(x in init for x, init in zip(initial, sysm["inits"])),
              "trace_replays": replays, "stem_ends_at_the_loop_state": at_loop,
              "every_state_avoids_the_goal": all(avoid(x) for x in seq)}
    if kind == "deadlock":
        checks["deadlock_has_no_enabled_command"] = (
            at_loop and not cycle and all(_live_enabled(sysm, c, s) is None for c in sysm["commands"]))
    else:
        cyc = visited[:-1]
        checks["cycle_returns_to_the_loop_state"] = replays and bool(cycle) and list(s) == loop
        checks["cycle_is_weakly_fair"] = replays and bool(cycle) and all(
            sysm["commands"][a][0] in taken
            or any(_live_enabled(sysm, sysm["commands"][a], x) is None for x in cyc) for a in fair)
    digest = "sha256:" + hashlib.sha256("".join(",".join(str(v) for v in x) + ";" for x in seq).encode()).hexdigest()
    checks["trace_digest_matches_the_replay"] = output.get("trace_digest") == digest
    return checks


def _live_region(sysm, cap):
    """The verifier's own exploration of the goal-avoiding region: NumPy level-synchronous over arrays of states
    with the vectorised semantics of ``_mc_vec`` (the solver uses compiled closures one state at a time). States
    are numbered in sorted-code order (radix codes, or byte keys when the declared ranges overflow int64);
    returns the states, enabled[state, command] and the edge arrays (src, command, dst) between region states,
    or None beyond the cap."""
    import numpy as np
    names, lo, hi, cmds = sysm["names"], sysm["lo"], sysm["hi"], sysm["commands"]
    radix = [h - l + 1 for l, h in zip(lo, hi)]
    lo_a = np.array(lo, dtype=np.int64)
    if math.prod(radix) < 2 ** 62:
        mult = np.array([math.prod(radix[i + 1:]) for i in range(len(radix))], dtype=np.int64)

        def encode(arr):
            return ((arr - lo_a) * mult).sum(axis=1)
    else:
        # declared ranges too wide for one int64 code (the reachable region may still be tiny): each state's
        # offsets as big-endian uint32 bytes, one opaque key per state; byte order is the radix codes' order
        key = np.dtype((np.void, 4 * len(names)))

        def encode(arr):
            return np.ascontiguousarray((arr - lo_a).astype(">u4")).view(key).reshape(-1)

    def columns(arr):
        return {name: arr[:, i] for i, name in enumerate(names)}

    def goal(arr):
        return _mc_vec(sysm["invariant"], columns(arr), len(arr))
    init = np.array(list(product(*sysm["inits"])), dtype=np.int64).reshape(-1, len(names))
    init = init[~goal(init)]
    seen, first = np.unique(encode(init), return_index=True)
    frontier = init[first]
    rows, row_codes, row_enabled, e_src, e_cmd, e_dst = [], [], [], [], [], []
    while len(frontier):
        size, cols, codes = len(frontier), columns(frontier), encode(frontier)
        en = np.zeros((size, len(cmds)), dtype=bool)
        found = []
        for c, (_, guard, ups) in enumerate(cmds):
            g = np.flatnonzero(_mc_vec(guard, cols, size))
            if not len(g):
                continue
            sub = {k: v[g] for k, v in cols.items()}
            nxt, ok = frontier[g].copy(), np.ones(len(g), dtype=bool)
            for i, e in ups:
                val = _mc_vec(e, sub, len(g))
                ok &= (val >= lo[i]) & (val <= hi[i])
                nxt[:, i] = val
            g, nxt = g[ok], nxt[ok]
            en[g, c] = True
            keep = ~goal(nxt)
            g, nxt = g[keep], nxt[keep]
            e_src.append(codes[g])
            e_cmd.append(np.full(len(g), c, dtype=np.int64))
            e_dst.append(encode(nxt))
            found.append(nxt)
        rows.append(frontier)
        row_codes.append(codes)
        row_enabled.append(en)
        if not found:
            break
        found = np.concatenate(found)
        codes, first = np.unique(encode(found), return_index=True)
        fresh = ~np.isin(codes, seen)
        frontier = found[first[fresh]]
        seen = np.union1d(seen, codes[fresh])
        if len(seen) > cap:
            return None
    order = np.argsort(np.concatenate(row_codes)) if row_codes else np.zeros(0, dtype=np.int64)
    empty = np.zeros(0, dtype=np.int64)
    return {"count": len(seen),
            "states": np.concatenate(rows)[order] if rows else np.zeros((0, len(names)), dtype=np.int64),
            "enabled": np.concatenate(row_enabled)[order] if rows else np.zeros((0, len(cmds)), dtype=bool),
            "src": np.searchsorted(seen, np.concatenate(e_src)) if e_src else empty,
            "cmd": np.concatenate(e_cmd) if e_cmd else empty,
            "dst": np.searchsorted(seen, np.concatenate(e_dst)) if e_dst else empty}


def _live_fair_scc(region, fair):
    """The verifier's fair-SCC test, independent code from the solver's: SciPy's compiled strong components
    (Pearce's algorithm) over the edge arrays and a vectorised weak-fairness filter. True when some cyclic
    component has, for every fair command, a state where it is disabled or an internal edge that takes it."""
    import numpy as np
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    count, src, cmd, dst = region["count"], region["src"], region["cmd"], region["dst"]
    if count == 0 or len(src) == 0:
        return False
    graph = coo_matrix((np.ones(len(src)), (src, dst)), shape=(count, count)).tocsr()
    k, label = connected_components(graph, directed=True, connection="strong")
    inner = label[src] == label[dst]
    cyclic = np.bincount(label, minlength=k) > 1
    cyclic[label[src[inner & (src == dst)]]] = True                  # a self-loop makes a singleton cyclic
    for a in fair:
        disabled, taken = np.zeros(k, dtype=bool), np.zeros(k, dtype=bool)
        disabled[label[~region["enabled"][:, a]]] = True
        taken[label[src[inner & (cmd == a)]]] = True
        cyclic &= disabled | taken
    return bool(cyclic.any())


def _live_fixpoint(region, fair):
    """A third method with no SCC decomposition, for the benchmark truth: the greatest fixpoint
    Z = nu Z. (intersection over fair a of E[Z U T_a(Z)]), where T_a(Z) holds the states of Z that have a disabled
    and a successor in Z, or an a-edge into Z (with no fair commands, Z = nu Z. Z and EX Z). Z is exactly the set
    of states with a weakly fair infinite goal-avoiding run. Iterations can grow with the length of progress
    chains (quadratic worst case), so the verifier uses the SCC test and this runs on benchmark-sized regions."""
    count = region["count"]
    succ, pred = [[] for _ in range(count)], [[] for _ in range(count)]
    for v, c, w in zip(region["src"].tolist(), region["cmd"].tolist(), region["dst"].tolist()):
        succ[v].append((c, w))
        pred[w].append(v)
    enabled = region["enabled"].tolist()
    Z = [True] * count
    while True:
        has = [Z[v] and any(Z[w] for _, w in succ[v]) for v in range(count)]
        new = has[:]
        for a in fair:
            reach = [Z[v] and ((not enabled[v][a] and has[v]) or any(c == a and Z[w] for c, w in succ[v]))
                     for v in range(count)]
            queue = [v for v in range(count) if reach[v]]
            while queue:
                v = queue.pop()
                for u in pred[v]:
                    if Z[u] and not reach[u]:
                        reach[u] = True
                        queue.append(u)
            new = [p and q for p, q in zip(new, reach)]
        if new == Z:
            return any(Z)
        Z = new


def _live_deadlock(region):
    return bool(region["count"]) and bool((~region["enabled"].any(axis=1)).any())


def live_verify(data, output, certificate):
    sysm, fair = _live(data)
    if _live_scope(data):
        # a lasso that is weakly fair need not be strongly fair, and HOLDS here says nothing about another
        # property: no answer to an out-of-competence request is confirmed
        return {"request_in_scope": False}
    verdict = output.get("verdict") if isinstance(output, dict) else None
    if verdict == "VIOLATED":
        return _live_replay(sysm, fair, output)
    if verdict == "HOLDS":
        if not _is_int(output.get("region_states")):
            return {"region_count_well_formed": False}
        region = _live_region(sysm, 2 * LV_NATIVE_STATES)
        if region is None:
            return {"independent_recount_feasible": False}
        cert = certificate if isinstance(certificate, dict) else {}
        return {"independent_recount_feasible": True,
                "region_count_matches": region["count"] == output["region_states"],
                "region_digest_matches": _mc_digest(map(tuple, region["states"].tolist())) == cert.get("region_digest"),
                "no_reachable_deadlock": not _live_deadlock(region),
                "no_weakly_fair_goal_avoiding_component": not _live_fair_scc(region, fair)}
    return {"verdict_is_holds_or_violated": False}


def live_score(data, truth, output):
    if output is None:
        return {"quality": 0.0, "category": "abstain"}
    if _live_scope(data):                    # the truth is weak-fairness liveness; another request has none here
        return {"quality": -1.0, "category": "wrong"}
    verdict = output.get("verdict") if isinstance(output, dict) else None
    if verdict == "HOLDS":
        ok = truth["holds"]
    elif verdict == "VIOLATED":
        sysm, fair = _live(data)
        ok = all(_live_replay(sysm, fair, output).values())       # a replayed fair lasso is a proof
    else:
        return {"quality": -1.0, "category": "wrong"}
    return {"quality": 1.0, "category": "correct"} if ok else {"quality": -1.0, "category": "wrong"}


def live_bmc(data):
    """Baseline: Z3 bounded model checking to depth 10 for a goal-avoiding lasso that is weakly fair on its loop
    (or a goal-avoiding deadlock), one 4 s total budget. No counterexample within the bound is reported as
    HOLDS, so longer lassos are missed; out of budget abstains."""
    import z3
    sysm, fair = _live(data)
    if _live_scope(data):
        return None
    names, index, lo, hi = sysm["names"], sysm["index"], sysm["lo"], sysm["hi"]
    nv, cmds = len(names), sysm["commands"]
    ctx = z3.Context()
    deadline = time.perf_counter() + LV_Z3_SECONDS

    def timed_check(solver):
        left = deadline - time.perf_counter()
        if left <= 0.01:
            return z3.unknown
        solver.set("timeout", max(1, int(left * 1000)))
        return solver.check()

    def state(k):
        return [z3.Int(f"x{k}_{i}", ctx) for i in range(nv)]

    def ranges(xs):
        return z3.And([z3.And(x >= l, x <= h) for x, l, h in zip(xs, lo, hi)])

    def enabled(c, xs):
        _, guard, ups = cmds[c]
        return z3.And(_mc_z3(guard, xs, index, ctx),
                      *[z3.And(e >= lo[i], e <= hi[i]) for i, e in ((i, _mc_z3(e, xs, index, ctx)) for i, e in ups)])

    def step(c, xs, ys):
        upd = dict(cmds[c][2])
        return z3.And(enabled(c, xs), *[ys[i] == (_mc_z3(upd[i], xs, index, ctx) if i in upd else xs[i])
                                        for i in range(nv)])

    def goal(xs):
        return _mc_z3(sysm["invariant"], xs, index, ctx)
    solver = z3.Solver(ctx=ctx)
    solver.set("random_seed", 0)
    X, acts = [state(0)], []
    solver.add(ranges(X[0]), *[z3.Or([X[0][i] == v for v in sysm["inits"][i]]) for i in range(nv)],
               z3.Not(goal(X[0])))
    for k in range(LV_BMC_DEPTH + 1):
        dead = z3.And([z3.Not(enabled(c, X[k])) for c in range(len(cmds))])
        loops = [z3.And(*[X[k][i] == X[l][i] for i in range(nv)],
                        *[z3.Or([z3.Or(z3.Not(enabled(a, X[j])), acts[j] == a) for j in range(l, k)]) for a in fair])
                 for l in range(k)]
        solver.push()
        solver.add(z3.Or(dead, *loops))
        verdict = timed_check(solver)
        if verdict == z3.sat:
            model = solver.model()
            seq = [tuple(model.eval(x, model_completion=True).as_long() for x in xs) for xs in X]
            moves = [cmds[model.eval(a, model_completion=True).as_long()][0] for a in acts]
            is_dead = z3.is_true(model.eval(dead, model_completion=True))
            l = k if is_dead else next(l for l in range(k) if z3.is_true(model.eval(loops[l], model_completion=True)))
            solver.pop()
            return {"verdict": "VIOLATED", "counterexample": "deadlock" if is_dead else "lasso",
                    "initial": list(seq[0]), "stem": moves[:l], "cycle": moves[l:], "loop_state": list(seq[l]),
                    "trace_digest": _trace_digest(seq), "method": f"BMC counterexample at depth {k}"}
        solver.pop()
        if verdict != z3.unsat:
            return None                                            # out of budget: abstain
        if k == LV_BMC_DEPTH:
            break
        acts.append(z3.Int(f"a{k}", ctx))
        X.append(state(k + 1))
        solver.add(acts[k] >= 0, acts[k] < len(cmds), ranges(X[k + 1]), z3.Not(goal(X[k + 1])),
                   z3.Or([z3.And(acts[k] == c, step(c, X[k], X[k + 1])) for c in range(len(cmds))]))
    return {"verdict": "HOLDS", "method": f"no counterexample within depth {LV_BMC_DEPTH} (bounded, not a proof)"}


def _live_graph(data):
    """Explicit goal-avoiding region as a NetworkX digraph (closure semantics), or None beyond the cap."""
    import networkx as nx
    sysm, fair = _live(data)
    cmds, goal = _mc_compiled(sysm)
    lo, hi = sysm["lo"], sysm["hi"]
    G, labels, enabled = nx.DiGraph(), {}, {}
    inits = [s for s in product(*sysm["inits"]) if not goal(s)]
    queue = deque(dict.fromkeys(inits))
    G.add_nodes_from(queue)
    while queue:
        s = queue.popleft()
        enabled[s] = 0
        for ci, t in _mc_step(cmds, lo, hi, s):
            enabled[s] |= 1 << ci
            if goal(t):
                continue
            if t not in G:
                G.add_node(t)
                queue.append(t)
            G.add_edge(s, t)
            labels.setdefault((s, t), set()).add(ci)
        if G.number_of_nodes() > LV_NATIVE_STATES:
            return None
    return sysm, fair, cmds, G, labels, enabled, list(dict.fromkeys(inits))


def live_networkx(data):
    """Competitor: NetworkX strongly_connected_components on the explicit goal-avoiding region with a
    straightforward weak-fairness filter; stem and cycle from NetworkX shortest paths."""
    import networkx as nx
    if _live_scope(data):
        return None
    built = _live_graph(data)
    if built is None:
        return None
    sysm, fair, cmds, G, labels, enabled, inits = built
    H = G.copy()
    H.add_edges_from(("__start__", s) for s in inits)

    def name_path(path):
        return [cmds[min(labels[(u, v)])][0] for u, v in zip(path, path[1:])]
    dead = [s for s in G if enabled[s] == 0]
    target, cycle_nodes, cycle_names = None, None, []
    if dead:
        target = min(dead)
    else:
        for comp in nx.strongly_connected_components(G):
            sub = G.subgraph(comp)
            if len(comp) == 1 and not sub.has_edge(next(iter(comp)), next(iter(comp))):
                continue
            if all(any(not enabled[v] >> a & 1 for v in comp) or any(a in labels[e] for e in sub.edges)
                   for a in fair):
                target = min(comp)
                cur, cycle_nodes = target, [target]
                for a in fair:
                    disabled = sorted(v for v in comp if not enabled[v] >> a & 1)
                    if disabled:
                        path = nx.shortest_path(sub, cur, disabled[0])
                        cycle_names += name_path(path)
                        cycle_nodes += path[1:]
                        cur = path[-1]
                    else:
                        u, w = min(e for e in sub.edges if a in labels[e])
                        path = nx.shortest_path(sub, cur, u)
                        cycle_names += name_path(path) + [cmds[a][0]]
                        cycle_nodes += path[1:] + [w]
                        cur = w
                if not cycle_names:
                    w = min(sub.successors(target))
                    cycle_names, cycle_nodes, cur = name_path([target, w]), [target, w], w
                back = nx.shortest_path(sub, cur, target)
                cycle_names += name_path(back)
                cycle_nodes += back[1:]
                break
    if target is None:
        return {"verdict": "HOLDS", "region_states": G.number_of_nodes(),
                "method": "NetworkX SCCs: no deadlock and no weakly fair goal-avoiding SCC"}
    stem_nodes = nx.shortest_path(H, "__start__", target)[1:]
    seq = stem_nodes + (cycle_nodes[1:] if cycle_nodes else [])
    return {"verdict": "VIOLATED", "counterexample": "lasso" if cycle_nodes else "deadlock",
            "initial": list(stem_nodes[0]), "stem": name_path(stem_nodes), "cycle": cycle_names,
            "loop_state": list(target), "trace_digest": _trace_digest(seq),
            "method": "NetworkX SCCs with a weak-fairness filter"}


def _lv_var(name, low, high, init=0):
    return {"name": name, "min": low, "max": high, "init": init}


def _lv_tick(var, top):
    return {"name": f"tick_{var}", "guard": True, "update": {var: ["mod", ["+", var, 1], top + 1]}}


def _lv_peterson(r):
    variant = r.choice(["correct", "correct", "p0_unfair", "wrong_turn"])
    m1, m2 = r.randint(3, 7), r.randint(3, 7)
    variables = [_lv_var("pc0", 0, 3), _lv_var("pc1", 0, 3), _lv_var("f0", 0, 1), _lv_var("f1", 0, 1),
                 _lv_var("turn", 0, 1, [0, 1]), _lv_var("c1", 0, m1), _lv_var("c2", 0, m2)]
    commands = []
    for i, j in ((0, 1), (1, 0)):
        pc, f, fj = f"pc{i}", f"f{i}", f"f{j}"
        wait_turn = i if variant != "wrong_turn" else j
        commands += [
            {"name": f"p{i}_flag", "guard": ["==", pc, 0], "update": {f: 1, pc: 1}},
            {"name": f"p{i}_yield", "guard": ["==", pc, 1], "update": {"turn": j, pc: 2}},
            {"name": f"p{i}_enter", "guard": ["and", ["==", pc, 2], ["or", ["==", fj, 0], ["==", "turn", wait_turn]]],
             "update": {pc: 3}},
            {"name": f"p{i}_exit", "guard": ["==", pc, 3], "update": {f: 0, pc: 0}}]
    commands += [_lv_tick("c1", m1), _lv_tick("c2", m2)]
    fair = [c["name"] for c in commands if not (variant == "p0_unfair" and c["name"].startswith("p0_"))]
    return {"variables": variables, "commands": commands}, ["==", "pc0", 3], fair, f"peterson_starvation:{variant}"


def _lv_counter(r):
    top, ticks = r.randint(12, 30), r.randint(2, 5)
    back = r.randint(top // 2, top - 2)
    variant = r.choice(["reset", "reset", "stutter", "inc_unfair"])
    commands = [{"name": "inc", "guard": ["<", "x", top], "update": {"x": ["+", "x", 1]}}, _lv_tick("t", ticks)]
    if variant == "reset":
        commands.append({"name": "reset", "guard": ["==", "x", back], "update": {"x": 0}})
    fair = [c["name"] for c in commands if not (variant == "inc_unfair" and c["name"] == "inc")]
    return ({"variables": [_lv_var("x", 0, top), _lv_var("t", 0, ticks)], "commands": commands},
            ["==", "x", top], fair, f"counter_reset:{variant},N={top}")


def _lv_livelock(r):
    variant = r.choice(["polite", "priority_weak", "priority_wait"])
    ticks = r.randint(2, 6)
    variables = [_lv_var("pc0", 0, 3), _lv_var("pc1", 0, 3), _lv_var("f0", 0, 1), _lv_var("f1", 0, 1),
                 _lv_var("t", 0, ticks)]
    commands = []
    for i, j in ((0, 1), (1, 0)):
        pc, f, fj, fi = f"pc{i}", f"f{i}", f"f{j}", f"f{i}"
        commands += [{"name": f"p{i}_try", "guard": ["==", pc, 0], "update": {f: 1, pc: 1}},
                     {"name": f"p{i}_enter", "guard": ["and", ["==", pc, 1], ["==", fj, 0]], "update": {pc: 3}},
                     {"name": f"p{i}_exit", "guard": ["==", pc, 3], "update": {f: 0, pc: 0}}]
        if variant == "polite" or i == 1:
            commands.append({"name": f"p{i}_back_off", "guard": ["and", ["==", pc, 1], ["==", fj, 1]],
                             "update": {fi: 0, pc: 2}})
            retry = ["==", pc, 2] if variant != "priority_wait" else ["and", ["==", pc, 2], ["==", fj, 0]]
            commands.append({"name": f"p{i}_retry", "guard": retry, "update": {pc: 0}})
    commands.append(_lv_tick("t", ticks))
    return ({"variables": variables, "commands": commands}, ["or", ["==", "pc0", 3], ["==", "pc1", 3]],
            [c["name"] for c in commands], f"livelock:{variant}")


def _lv_random(r):
    size, actions, ticks = r.randint(10, 22), r.randint(2, 4), r.randint(1, 3)
    goal_states = r.sample(range(1, size), r.randint(1, 3))
    commands = []
    for a in range(actions):
        domain = [s for s in range(size) if r.random() < 0.6]
        if not domain:
            continue
        update = r.randrange(size)
        for s in domain:
            update = ["ite", ["==", "s", s], r.randrange(size), update]
        commands.append({"name": f"act{a}", "guard": ["or", *[["==", "s", s] for s in domain]],
                         "update": {"s": update}})
    commands.append(_lv_tick("t", ticks))
    fair = [c["name"] for c in commands if c["name"].startswith("tick") or r.random() < 0.7]
    goal = ["or", *[["==", "s", g] for g in goal_states]]
    return ({"variables": [_lv_var("s", 0, size - 1), _lv_var("t", 0, ticks)], "commands": commands}, goal, fair,
            f"random_lts:S={size}")


def _lv_round_robin(r):
    k, bug, ticks = r.randint(3, 5), r.random() < 0.5, r.randint(1, 3)
    variables = [_lv_var("p", 0, k - 1), _lv_var("done0", 0, 1), _lv_var("t", 0, ticks)] + \
        [_lv_var(f"req{i}", 0, 1) for i in range(k)]
    nxt = ["mod", ["+", "p", 1], k]
    commands = []
    for i in range(k):
        commands.append({"name": f"request{i}", "guard": ["==", f"req{i}", 0], "update": {f"req{i}": 1}})
        serve = {f"req{i}": 0, "p": nxt, **({"done0": 1} if i == 0 else {})}
        commands.append({"name": f"serve{i}", "guard": ["and", ["==", "p", i], ["==", f"req{i}", 1]], "update": serve})
    waiting = ["or", *[["and", ["==", "p", i], ["==", f"req{i}", 1]] for i in range(k)]]
    commands.append({"name": "advance", "guard": True if bug else ["not", waiting], "update": {"p": nxt}})
    commands.append(_lv_tick("t", ticks))
    return ({"variables": variables, "commands": commands}, ["==", "done0", 1], [c["name"] for c in commands],
            f"round_robin:{'skips_requests' if bug else 'waits'},k={k}")


def _live_truth(data):
    """Benchmark truth by three methods that share no code with the solver and must agree (a disagreement
    raises): the Emerson-Lei fixpoint (no SCCs) and the verifier's SciPy SCC test, both on the verifier's NumPy
    region, and the competitor's NetworkX SCC filter on its own exploration."""
    sysm, fair = _live(data)
    region = _live_region(sysm, LV_NATIVE_STATES)
    nxr = live_networkx(data)
    if region is None or nxr is None:
        raise GenomeError("liveness generator produced a region beyond the native cap")
    dead = _live_deadlock(region)
    holds = not dead and not _live_fixpoint(region, fair)
    if holds != (not dead and not _live_fair_scc(region, fair)) or holds != (nxr["verdict"] == "HOLDS"):
        raise GenomeError("liveness generator: the fixpoint, the SciPy SCC test and NetworkX disagree")
    return {"holds": holds, "region_states": region["count"]}


def live_instance(seed):
    r = random.Random(5_500_000 + seed)
    gen = (_lv_peterson, _lv_counter, _lv_livelock, _lv_random, _lv_round_robin)[seed % 5]
    system, goal, fair, label = gen(r)
    data = {"system": system, "goal": goal, "fair": fair, "property": "liveness", "fairness": "weak",
            "name": label, "seed": 55_000 + seed}
    return data, {**_live_truth(data), "kind": label.split(":")[0]}


def live_subregion(data):
    return data.get("name", "system").split(":")[0]


# =================================================================== genomes
INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.game.bimatrix_support_enumeration", version="1.0.0", family="bimatrix_nash",
            layer=3, operation="bimatrix_nash_equilibrium", epistemic_class="strategic",
            subgeometry="general-sum two-player normal-form games, up to 8 actions each and 1000 support pairs",
            source_provenance="Nash (1951); support enumeration (von Stengel 2002, Handbook of Game Theory ch. 45); "
                              "correlated equilibrium (Aumann 1974) as a linear program; equilibrium-welfare MILP "
                              "(Sandholm, Gilpin, Conitzer 2005) on the verifier side",
            native_representation="row and column payoff matrices",
            required_inputs=("row_payoffs", "column_payoffs"),
            output_contract={"row_strategy": "[float]", "column_strategy": "[float]", "row_payoff": "float",
                             "column_payoff": "float", "welfare": "float", "selection": "max_welfare_nash | nash",
                             "correlated": "{distribution, welfare, objective} | null"},
            algorithm_or_runtime="exact rational Gauss-Jordan on every equal-size support pair; highest-welfare "
                                 "equilibrium; one HiGHS LP for the welfare-maximal correlated equilibrium",
            parameters={"max_actions": NASH_MAX_ACTIONS, "max_support_pairs": NASH_MAX_PAIRS, "epsilon": NASH_EPS},
            composition_inputs=("payoff model",), composition_outputs=("equilibrium profile", "correlated plan"),
            evidence_type="exact_calculation",
            verification_method="independent epsilon-Nash check (distributions; each payoff equals the best pure "
                                "response within 1e-9 of the scale); exact re-check of the rational certificate; "
                                "an independent HiGHS MILP over ALL equilibria for the maximal-welfare claim, with "
                                "an exact vertex enumeration of every extreme equilibrium deciding when the two "
                                "disagree; the correlated equilibrium's incentive constraints and an LP dual "
                                "certificate whose weak duality is checked in exact rationals",
            confidence_semantics="the equilibrium is exact for the declared payoffs; the maximal-welfare claim is "
                                 "made only when an exact test finds the game nondegenerate and is confirmed to "
                                 "1e-6 of the scale; the correlated equilibrium meets its incentive constraints to "
                                 "1e-7 of the scale (floats) and its welfare is within 1e-7 of the scale of a bound "
                                 "proven exactly by its LP dual, or the plan is withheld; every tolerance is "
                                 "relative to the largest payoff, with no floor; nothing here predicts what real "
                                 "players will do",
            resource_profile="C(m + n, m) - 1 support pairs, each two (k+1)-square rational solves",
            latency_profile="milliseconds at 4 x 4; about 0.2 s at 6 x 6",
            known_strengths=("finds every equilibrium of a nondegenerate game, so it can select the welfare-best",
                             "exact rational arithmetic: no tolerance on the equilibrium itself",
                             "answers games without a pure equilibrium, where pure search has no decision"),
            known_failure_modes=("exponential in the number of actions (abstains past 1000 support pairs)",
                                 "degenerate games: equal-size supports can miss equilibria; then the welfare "
                                 "claim is withheld, and a missed better equilibrium is caught by the verifier",
                                 "near-degenerate incentive constraints can leave the correlated plan without an "
                                 "exact dual certificate; it is then withheld",
                                 "equilibrium selection by total payoff is one normative choice among several"),
            counterindications=("large games (use Lemke-Howson or an MILP)", "games with more than two players",
                                "settings where players do not play equilibrium (behavioural data first)"),
            abstention_conditions=("more than 1000 support pairs",
                                   "no equal-size equilibrium found (degenerate continuum) -> UNKNOWN",
                                   "latency budget exhausted -> UNKNOWN"),
            benchmark_suite="random general-sum 2-4 actions, coordination games with many equilibria, games "
                            "without pure equilibria (incl. perturbed Shapley), anti-coordination, 5-6 action "
                            "random games; nondegenerate by screen; truth by NumPy enumeration cross-checked by "
                            "HiGHS MILP; seeds 0-9 dev / held out by the harness",
            baseline="pure-profile search (highest-welfare pure equilibrium); no decision without one",
            competitor="Lemke-Howson (nashpy) when installed, else damped iterated best response (fictitious-play "
                       "averaging, 4000 rounds) with a support polish; it may not converge (no decision then)",
            dependency="scipy", **_common()),
        solve=nash_solve, verify=nash_verify, instance=nash_instance, score=nash_score, baseline=nash_pure_search,
        competitor=nash_competitor, subregion=nash_subregion, tolerance=1e-9,
        notes={"competitor": "nashpy is not a declared dependency; where it is absent the damped dynamics run, a "
                             "weaker arm than Lemke-Howson"}),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.mechanism.dsic_ir_exhaustive", version="1.0.0", family="mechanism_check", layer=3,
            operation="mechanism_ic_ir_check", epistemic_class="strategic",
            subgeometry="deterministic direct mechanisms over finite type spaces (up to 4 agents, 4096 profiles)",
            source_provenance="dominant-strategy incentive compatibility and ex-post individual rationality "
                              "(Hurwicz 1972; Myerson 1981; Nisan et al. 2007, ch. 9)",
            native_representation="agents' values[type][outcome], allocation and payment tables by type profile",
            required_inputs=("agents", "outcomes", "allocation", "payments"),
            output_contract={"verdict": "HOLDS | VIOLATION",
                             "dsic": "{holds, max_gain, witness: {agent, true_type, reported_type, others, gain}}",
                             "ir": "{holds, min_slack, witness: {agent, profile, slack}}"},
            algorithm_or_runtime="exhaustive enumeration of every unilateral misreport and every profile, exact "
                                 "rationals; lexicographically first extreme witnesses",
            parameters={"max_misreports": MECH_MAX_DEVIATIONS, "max_profiles": MECH_MAX_PROFILES},
            composition_inputs=("mechanism tables", "valuation model"),
            composition_outputs=("verdict", "profitable misreport", "participation shortfall"),
            evidence_type="exhaustive_check",
            verification_method="independent re-enumeration organised by true profile with tuple-keyed tables "
                                "(maximum gain, minimum slack, counts and the canonical witnesses) plus a direct "
                                "exact replay of each witness; each claimed magnitude must match the float of its "
                                "exact value to 1e-12 of that value",
            confidence_semantics="exact for the declared tables and valuations; says nothing about valuations the "
                                 "model omits, collusion or randomized play",
            resource_profile="n x profiles x (types - 1) exact gains", latency_profile="milliseconds",
            known_strengths=("never misses a violation inside the declared type space",
                             "reports the most profitable misreport, the decision-relevant one",
                             "separates incentive failures from participation failures"),
            known_failure_modes=("exponential in the number of agents (abstains past 100,000 misreports)",
                                 "only as faithful as the declared valuation tables",
                                 "checks dominant-strategy truthfulness, not Bayesian incentive compatibility"),
            counterindications=("continuous or very large type spaces (needs analytic or sampled checks)",
                                "randomized mechanisms", "group or collusive deviations"),
            abstention_conditions=("more than 100,000 unilateral misreports", "randomized mechanism declared"),
            benchmark_suite="second-price with reserves (holds), first-price (common violations), second-price with "
                            "a planted pay-your-bid corner and a one-profile participation fee (rare violations), "
                            "Clarke-pivot and proportional cost-sharing public projects, random tables; truth by "
                            "NumPy re-enumeration over exact rationals; seeds 0-9 dev / held out by the harness",
            baseline="64 random sampled misreports and 64 random profiles; nothing found is reported as HOLDS",
            competitor="HiGHS MILP per agent for the maximum regret (one-hot true type, report and others' profile "
                       "with a linking selector) and an LP for the minimum participation slack",
            **_common()),
        solve=mech_solve, verify=mech_verify, instance=mech_instance, score=mech_score, baseline=mech_sampled,
        competitor=mech_milp, subregion=mech_subregion, tolerance=1e-9),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.verification.fair_scc_liveness", version="1.0.0", family="verify_liveness",
            layer=3, operation="model_check_liveness", epistemic_class="deductive",
            subgeometry="finite guarded-command transition systems; 'eventually goal' under weak fairness",
            source_provenance="explicit-state liveness checking by fair strongly connected components (Lichtenstein "
                              "and Pnueli 1985; Tarjan 1972); SciPy strong components (Pearce) on the verifier "
                              "side; an Emerson-Lei fixpoint (1986) in the benchmark truth",
            native_representation="typed JSON guarded commands (the verify_modelcheck language), a goal expression "
                                  "and the weakly fair commands",
            required_inputs=("system", "goal"),
            output_contract={"verdict": "HOLDS | VIOLATED", "region_states": "int (HOLDS)",
                             "counterexample": "lasso | deadlock (VIOLATED)",
                             "initial/stem/cycle/loop_state/trace_digest": "the counterexample run (VIOLATED)"},
            algorithm_or_runtime="breadth-first goal-avoiding region, iterative Tarjan SCCs, weak-fairness filter, "
                                 "shortest stem and a covering closed walk",
            parameters={"max_states": LV_NATIVE_STATES, "max_trace": LV_MAX_TRACE},
            composition_inputs=("transition system", "goal", "fairness"), composition_outputs=("verdict", "lasso"),
            evidence_type="exhaustive_check",
            verification_method="VIOLATED: step-by-step lasso replay by an independent interpreter (initial state, "
                                "goal avoidance, return to the loop state, weak fairness, trace digest); HOLDS: the "
                                "same fair-SCC criterion recomputed by independent code (NumPy-explored region, region "
                                "count and digest, SciPy compiled strong components, vectorised fairness filter); no "
                                "answer to a request outside weak-fairness liveness is confirmed",
            confidence_semantics="exact for the declared model and fairness within the state cap; weak fairness "
                                 "only; says nothing about code the model abstracts",
            resource_profile="time and memory linear in the goal-avoiding region (<= 20,000 states)",
            latency_profile="solve: milliseconds to about 0.2 s at the cap; HOLDS verification up to about 3 s there",
            known_strengths=("decides fair liveness exactly when the region fits",
                             "finds long lassos that bounded model checking misses",
                             "counterexamples are replayable runs, deadlocks included"),
            known_failure_modes=("state explosion: abstains beyond 20,000 goal-avoiding states",
                                 "weak fairness only: progress that needs strong fairness is reported VIOLATED, "
                                 "correctly for the declared fairness but perhaps not what was meant",
                                 "only as faithful as the model of the real system"),
            counterindications=("strong fairness or general LTL properties",
                                "very wide state spaces (use symbolic or bounded methods)"),
            abstention_conditions=("property other than liveness", "fairness other than weak",
                                   "more than 20,000 goal-avoiding states",
                                   "counterexample longer than 1000 steps -> UNKNOWN",
                                   "latency budget exhausted -> UNKNOWN"),
            benchmark_suite="Peterson starvation freedom (correct, unfair scheduling of one process, wrong turn "
                            "test), counters with resets (long lassos), polite and prioritised livelocks, random "
                            "labelled transition systems, round-robin schedulers that wait or skip; truth by the "
                            "Emerson-Lei fixpoint, the verifier's SciPy SCC test and NetworkX SCCs agreeing; seeds "
                            "0-9 dev / held out by the harness",
            baseline="Z3 bounded model checking to depth 10 for a weakly fair goal-avoiding lasso or deadlock, one "
                     "4 s total budget; nothing found is reported HOLDS",
            competitor="NetworkX strongly_connected_components on the explicit region with a straightforward "
                       "weak-fairness filter and NetworkX shortest paths",
            dependency="scipy", **_common()),
        solve=live_solve, verify=live_verify, instance=live_instance, score=live_score, baseline=live_bmc,
        competitor=live_networkx, subregion=live_subregion, tolerance=1e-9),
]
