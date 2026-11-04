"""Robust control (L3), local signal-level sensing (L1) and local error correction (L1).

The 2026-10-21 coverage record (``docs/collaboration/MIND-COVERAGE-2026-10-21.md``) lists "robust control",
"local sensing" and "local error correction" as ABSENT. Effect, not metaphor: each genome below names an effect
and claims nothing biological or physical beyond it.

* ``control_robust_tube`` (``robust_tube_mpc``): a discrete-time linear plant with a bounded additive disturbance
  (a box), box state and input constraints and a short horizon. The answer is a tube MPC policy
  ``u_t = v_t + K (x_t - z_t)``: a nominal plan (z, v) solved by a HiGHS LP on constraints tightened by the exact
  finite-horizon reach of the error ``e_{t+1} = (A + B K) e_t + w_t``, plus an ancillary feedback K from the
  discrete LQR (SciPy DARE). Every constraint and the stage cost are convex in the disturbance sequence, so their
  worst case over the box is attained at a vertex sequence: the verifier simulates every vertex sequence step by
  step, and the score recomputes the exact worst case by superposition over the same vertices. The cost is a
  weighted L1 cost, so the competitor's min-max problem is an LP. GREG has no plant: this is control of a declared
  model, and competence here is simulated.
* ``basal_cusum_detect`` (``detect_mean_shift``): signal-level sensing. GREG has no physical sensors; the genome
  watches a supplied numeric stream for a shift in its mean and raises one alarm. The method is Page's two-sided
  CUSUM with reference value k = delta / (2 sigma) and a threshold h set by Siegmund's approximation for the
  declared in-control average run length ARL0. The verifier recomputes the statistic by a different formula
  (cumulative sum minus its running minimum) and re-solves nothing: it checks h against the ARL0 equation directly.
* ``basal_hamming_correct`` (``correct_bit_errors``): local error correction of a stream of Hamming or extended
  Hamming (SECDED) codewords by syndrome decoding; SECDED double errors are flagged, never guessed. The verifier
  re-encodes every decoded block bit by bit and recomputes syndromes and parity on its own.

Everything is read-only computation: no files, network, subprocesses or environment access, and no output of any
method here creates authority. Development seeds 0-9 only.
"""
from __future__ import annotations

import itertools
import math
import random

from .contract import Executable, GenomeError, IntelligenceGenome, answer

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "INTENT-20261021-MIND-MAXIMUM-CONTINUATION section 4 (restore the full five-layer scope)")


def _num(v):
    return type(v) in (int, float) and math.isfinite(v)


# =================================================================== robust control: tube MPC
RT_MAX_N, RT_MAX_M, RT_MAX_HORIZON = 4, 2, 8
RT_MAX_VERTEX_BITS = 12          # at most 2^12 disturbance vertex sequences are enumerated (verify and score)
RT_TOL = 1e-7


def _matrix(value, rows, cols, name):
    if (not isinstance(value, list) or len(value) != rows
            or not all(isinstance(r, list) and len(r) == cols and all(_num(x) for x in r) for r in value)):
        raise GenomeError(f"{name}: a {rows} x {cols} list of finite numbers")
    return [[float(x) for x in r] for r in value]


def _vector(value, size, name, *, positive=False, nonneg=False):
    if not isinstance(value, list) or len(value) != size or not all(_num(x) for x in value):
        raise GenomeError(f"{name}: a list of {size} finite numbers")
    if positive and not all(x > 0 for x in value):
        raise GenomeError(f"{name}: every entry > 0")
    if nonneg and not all(x >= 0 for x in value):
        raise GenomeError(f"{name}: every entry >= 0")
    return [float(x) for x in value]


def _rt(data):
    """Parse a robust-control request (plain Python lists; no NumPy)."""
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    A = data.get("A")
    n = len(A) if isinstance(A, list) else 0
    if not 1 <= n <= RT_MAX_N:
        raise GenomeError(f"A: square, 1-{RT_MAX_N} states")
    A = _matrix(A, n, n, "A")
    B = data.get("B")
    m = len(B[0]) if isinstance(B, list) and B and isinstance(B[0], list) else 0
    if not 1 <= m <= RT_MAX_M:
        raise GenomeError(f"B: n x m with 1-{RT_MAX_M} inputs")
    B = _matrix(B, n, m, "B")
    x0 = _vector(data.get("x0"), n, "x0")
    xmax = _vector(data.get("x_max"), n, "x_max", positive=True)
    umax = _vector(data.get("u_max"), m, "u_max", positive=True)
    wmax = _vector(data.get("w_max"), n, "w_max", nonneg=True)
    N = data.get("horizon")
    if type(N) is not int or not 1 <= N <= RT_MAX_HORIZON:
        raise GenomeError(f"horizon: integer 1-{RT_MAX_HORIZON}")
    w = data.get("weights")
    if not isinstance(w, dict) or set(w) != {"q", "r"} or not all(_num(w[k]) and w[k] > 0 for k in w):
        raise GenomeError("weights: {q > 0, r > 0} (cost q |x|_1 + r |u|_1 per step)")
    if any(abs(a) > b for a, b in zip(x0, xmax)):
        raise GenomeError("x0 must satisfy the state bounds")
    return {"A": A, "B": B, "x0": x0, "xmax": xmax, "umax": umax, "wmax": wmax, "N": N, "q": float(w["q"]),
            "r": float(w["r"]), "n": n, "m": m}


def _rt_prediction(p):
    """Nominal prediction z_t = c_t + G_t v (t = 0..N) for z_{t+1} = A z_t + B v_t, z_0 = x0."""
    import numpy as np
    A, B, N, n, m = np.array(p["A"]), np.array(p["B"]), p["N"], p["n"], p["m"]
    c = np.zeros((N + 1, n))
    G = np.zeros((N + 1, n, N * m))
    c[0] = p["x0"]
    for t in range(N):
        c[t + 1] = A @ c[t]
        G[t + 1] = A @ G[t]
        G[t + 1][:, t * m:(t + 1) * m] += B
    return c, G


def _rt_nominal_lp(p, alpha, beta):
    """min q sum_t |z_t|_1 + r sum_t |v_t|_1 s.t. |z_t| <= x_max - alpha_t (t = 1..N), |v_t| <= u_max - beta_t.
    Returns (v [N x m], z [(N+1) x n], cost) or None when infeasible."""
    import numpy as np
    from scipy.optimize import linprog
    N, n, m = p["N"], p["n"], p["m"]
    c, G = _rt_prediction(p)
    xb = np.array(p["xmax"])[None, :] - alpha                        # (N+1) x n, row 0 unused
    ub = np.array(p["umax"])[None, :] - beta                         # N x m
    if (xb[1:] < 0).any() or (ub < 0).any():
        return None
    nv, nsx = N * m, N * n
    size = nv + nsx + nv                                             # v, |z| slacks, |v| slacks
    rows, rhs = [], []
    for t in range(1, N + 1):
        for i in range(n):
            g = np.zeros(size)
            g[:nv] = G[t][i]
            s = np.zeros(size)
            s[nv + (t - 1) * n + i] = 1.0
            rows += [g - s, -g - s, g, -g]
            rhs += [-c[t][i], c[t][i], xb[t][i] - c[t][i], xb[t][i] + c[t][i]]
    for j in range(nv):
        e = np.zeros(size)
        e[j] = 1.0
        s = np.zeros(size)
        s[nv + nsx + j] = 1.0
        rows += [e - s, -e - s]
        rhs += [0.0, 0.0]
    cost = np.concatenate([np.zeros(nv), np.full(nsx, p["q"]), np.full(nv, p["r"])])
    bounds = [(-float(ub[j // m][j % m]), float(ub[j // m][j % m])) for j in range(nv)] + [(0, None)] * (nsx + nv)
    res = linprog(cost, A_ub=np.array(rows), b_ub=np.array(rhs), bounds=bounds, method="highs")
    if res.status != 0:
        return None
    v = res.x[:nv].reshape(N, m)
    z = c + np.einsum("tij,j->ti", G, res.x[:nv])
    return v, z, float(res.fun)


def _rt_lqr(p):
    import numpy as np
    from scipy.linalg import solve_discrete_are
    A, B = np.array(p["A"]), np.array(p["B"])
    Q, R = p["q"] * np.eye(p["n"]), p["r"] * np.eye(p["m"])
    P = solve_discrete_are(A, B, Q, R)
    return -np.linalg.solve(R + B.T @ P @ B, B.T @ P @ A)


def _rt_policy(K, v, z):
    return {"K": [[float(x) for x in row] for row in K], "nominal_inputs": [[float(x) for x in row] for row in v],
            "nominal_states": [[float(x) for x in row] for row in z]}


def tube_solve(data, budget):
    import numpy as np
    p = _rt(data)
    if p["n"] * p["N"] > RT_MAX_VERTEX_BITS:
        return answer(None, {"reason": "too many disturbance vertex sequences to verify"}, status="ABSTAIN",
                      missing=[f"n x horizon above {RT_MAX_VERTEX_BITS}: worst-case satisfaction could not be "
                               f"checked exhaustively"])
    try:
        K = _rt_lqr(p)
    except (np.linalg.LinAlgError, ValueError) as exc:
        return answer(None, {"reason": f"no stabilising LQR gain: {type(exc).__name__}"}, status="ABSTAIN",
                      missing=["the discrete Riccati equation has no stabilising solution (not stabilisable)"])
    A, B, N, n, m = np.array(p["A"]), np.array(p["B"]), p["N"], p["n"], p["m"]
    Phi = A + B @ K
    wmax = np.array(p["wmax"])
    alpha, beta = np.zeros((N + 1, n)), np.zeros((N, m))
    power = np.eye(n)                                           # Phi^(t-1)
    for t in range(1, N + 1):
        alpha[t] = alpha[t - 1] + np.abs(power) @ wmax          # exact support of e_t = sum_k Phi^k w_(t-1-k)
        if t < N:
            beta[t] = beta[t - 1] + np.abs(K @ power) @ wmax    # exact support of K e_t
        power = Phi @ power
    plan = _rt_nominal_lp(p, alpha, beta)
    if plan is None:
        return answer(None, {"reason": "tightened nominal problem infeasible",
                             "tightening_state": alpha[1:].tolist(), "tightening_input": beta.tolist()},
                      status="ABSTAIN", missing=["no nominal plan satisfies the constraints tightened by the "
                                                 "disturbance reach of the LQR error dynamics"])
    v, z, nominal = plan
    # |x_t| <= |z_t| + alpha_t and |u_t| <= |v_t| + beta_t, so the worst-case cost is at most this bound
    bound = nominal + p["q"] * float(alpha[1:].sum()) + p["r"] * float(beta.sum())
    cert = {"rule": "tube MPC: LQR ancillary gain, finite-horizon exact error-reach tightening, nominal L1 LP (HiGHS)",
            "tightening_state": alpha[1:].tolist(), "tightening_input": beta.tolist(),
            "closed_loop_spectral_radius": float(max(abs(np.linalg.eigvals(Phi)))),
            "nominal_cost": nominal, "worst_case_cost_bound": bound}
    return answer(_rt_policy(K, v, z), cert)


def _rt_output(p, output):
    """Parse a policy output into floats, or None when malformed."""
    if not isinstance(output, dict) or set(output) != {"K", "nominal_inputs", "nominal_states"}:
        return None
    try:
        K = _matrix(output["K"], p["m"], p["n"], "K")
        v = _matrix(output["nominal_inputs"], p["N"], p["m"], "nominal_inputs")
        z = _matrix(output["nominal_states"], p["N"] + 1, p["n"], "nominal_states")
    except GenomeError:
        return None
    return K, v, z


def tube_verify(data, output, certificate):
    """Independent step-by-step closed-loop simulation over every disturbance vertex sequence (itertools order)."""
    p = _rt(data)
    parsed = _rt_output(p, output)
    if parsed is None:
        return {"output_shape": False}
    K, v, z = parsed
    A, B, N, n, m = p["A"], p["B"], p["N"], p["n"], p["m"]
    if n * N > RT_MAX_VERTEX_BITS:
        return {"output_shape": True, "vertex_enumeration_within_cap": False}
    starts = all(abs(a - b) <= RT_TOL * (1 + abs(b)) for a, b in zip(z[0], p["x0"]))
    consistent = True
    for t in range(N):
        for i in range(n):
            nxt = sum(A[i][j] * z[t][j] for j in range(n)) + sum(B[i][j] * v[t][j] for j in range(m))
            consistent &= abs(nxt - z[t + 1][i]) <= RT_TOL * (1 + abs(nxt))
    import numpy as np
    An, Bn, Kn = np.array(A), np.array(B), np.array(K)
    signs = np.array(list(itertools.product((-1.0, 1.0), repeat=n * N)))          # S x (N n)
    W = signs * np.tile(np.array(p["wmax"]), N)[None, :]
    X = np.tile(np.array(p["x0"]), (len(W), 1))
    xmax, umax = np.array(p["xmax"]), np.array(p["umax"])
    inputs_ok, states_ok, cost = True, True, np.zeros(len(W))
    for t in range(N):
        U = np.array(v[t])[None, :] + (X - np.array(z[t])[None, :]) @ Kn.T
        inputs_ok &= bool(np.all(np.abs(U) <= umax * (1 + RT_TOL) + RT_TOL))
        X = X @ An.T + U @ Bn.T + W[:, t * n:(t + 1) * n]
        states_ok &= bool(np.all(np.abs(X) <= xmax * (1 + RT_TOL) + RT_TOL))
        cost += p["r"] * np.abs(U).sum(axis=1) + p["q"] * np.abs(X).sum(axis=1)
    bound = certificate.get("worst_case_cost_bound") if isinstance(certificate, dict) else None
    return {"output_shape": True, "vertex_enumeration_within_cap": True, "nominal_starts_at_x0": starts,
            "nominal_follows_the_model": bool(consistent), "input_bounds_hold_on_every_vertex_sequence": inputs_ok,
            "state_bounds_hold_on_every_vertex_sequence": states_ok,
            "worst_case_cost_within_certified_bound": _num(bound) and float(cost.max()) <= bound * (1 + 1e-9) + 1e-9}


def _rt_worst_case(p, output):
    """Exact worst case over the disturbance box by superposition: the closed loop is affine in the disturbance
    sequence and |.| is convex, so the maxima of the constraint excess and of the cost are at vertex sequences.
    Returns (violation normalised by the bounds, worst-case cost) or None for a malformed policy."""
    import numpy as np
    parsed = _rt_output(p, output)
    if parsed is None:
        return None
    K, v, z = (np.array(a) for a in parsed)
    A, B, N, n, m = np.array(p["A"]), np.array(p["B"]), p["N"], p["n"], p["m"]
    Phi = A + B @ K
    xbar, ubar = np.zeros((N + 1, n)), np.zeros((N, m))      # zero-disturbance closed loop
    xbar[0] = p["x0"]
    for t in range(N):
        ubar[t] = v[t] + K @ (xbar[t] - z[t])
        xbar[t + 1] = A @ xbar[t] + B @ ubar[t]
    Mx = np.zeros((N, n, N * n))                             # x_(t+1) response to w_j
    Mu = np.zeros((N, m, N * n))                             # u_t response to w_j
    for t in range(1, N + 1):
        for j in range(t):
            block = np.linalg.matrix_power(Phi, t - 1 - j)
            Mx[t - 1][:, j * n:(j + 1) * n] = block
            if t < N:
                Mu[t][:, j * n:(j + 1) * n] = K @ block
    count = 1 << (N * n)
    bits = (np.arange(count)[:, None] >> np.arange(N * n)[None, :]) & 1
    Wv = (2.0 * bits - 1.0) * np.tile(np.array(p["wmax"]), N)[None, :]
    X = xbar[1:][None, :, :] + np.einsum("tij,sj->sti", Mx, Wv)
    U = ubar[None, :, :] + np.einsum("tij,sj->sti", Mu, Wv)
    xmax, umax = np.array(p["xmax"]), np.array(p["umax"])
    violation = max(float(np.max((np.abs(X) - xmax) / xmax)), float(np.max((np.abs(U) - umax) / umax)), 0.0)
    cost = p["q"] * np.abs(X).sum(axis=(1, 2)) + p["r"] * np.abs(U).sum(axis=(1, 2))
    return violation, float(cost.max())


def tube_score(data, truth, output):
    """Zero violations first, then cost. Quality: a violating policy -1 - min(violation, 1) (wrong); abstaining 0;
    a robustly safe policy 1 - worst-case cost / (2 * scale), in [0.5, 1], where scale = N (q sum x_max + r sum
    u_max) bounds any safe policy's cost."""
    p = _rt(data)
    if output is None:
        return {"quality": 0.0, "category": "abstain"}
    wc = _rt_worst_case(p, output)
    if wc is None:
        return {"quality": -2.0, "category": "wrong"}
    violation, cost = wc
    if violation > 1e-6:
        return {"quality": -1.0 - min(violation, 1.0), "category": "wrong"}
    scale = p["N"] * (p["q"] * sum(p["xmax"]) + p["r"] * sum(p["umax"]))
    return {"quality": 1.0 - cost / (2.0 * scale), "category": "correct"}


def tube_nominal(data):
    """Baseline: certainty-equivalent nominal MPC, constraints not tightened, applied open loop (K = 0)."""
    import numpy as np
    p = _rt(data)
    plan = _rt_nominal_lp(p, np.zeros((p["N"] + 1, p["n"])), np.zeros((p["N"], p["m"])))
    if plan is None:
        return None
    v, z, _ = plan
    return _rt_policy(np.zeros((p["m"], p["n"])), v, z)


def tube_minmax_open_loop(data):
    """Competitor: min-max open-loop MPC by a vertex-scenario LP (SciPy HiGHS). One input sequence u must keep every
    vertex disturbance sequence inside the bounds and minimises the worst scenario's L1 cost (an epigraph variable
    over all scenarios). Exact over open-loop policies because constraints and cost are convex in w."""
    import numpy as np
    from scipy.optimize import linprog
    from scipy.sparse import csr_matrix, hstack, identity, kron, vstack
    p = _rt(data)
    N, n, m = p["N"], p["n"], p["m"]
    if n * N > RT_MAX_VERTEX_BITS:
        return None
    A = np.array(p["A"])
    c, G = _rt_prediction(p)
    c, G = c[1:].reshape(N * n), G[1:].reshape(N * n, N * m)
    D = np.zeros((N * n, N * n))                                     # x_(t+1) response to w_j: A^(t-j)
    for t in range(N):
        for j in range(t + 1):
            D[t * n:(t + 1) * n, j * n:(j + 1) * n] = np.linalg.matrix_power(A, t - j)
    signs = np.array(list(itertools.product((-1.0, 1.0), repeat=n * N)))
    W = signs * np.tile(np.array(p["wmax"]), N)[None, :]
    S, nx, nu = len(W), N * n, N * m
    offset = (c[None, :] + W @ D.T).reshape(S * nx)                  # free response of every scenario
    # variables: u (nu), |u| slacks (nu), tau (1), per-scenario |x| slacks a (S * nx), with 0 <= a <= x_max
    Gs = kron(csr_matrix(np.ones((S, 1))), csr_matrix(G), format="csr")
    Ia = identity(S * nx, format="csr")
    zero_u = csr_matrix((S * nx, nu))
    zero_t = csr_matrix((S * nx, 1))
    upper = hstack([Gs, zero_u, zero_t, -Ia])                        #  G u - a <= -offset
    lower = hstack([-Gs, zero_u, zero_t, -Ia])                       # -G u - a <=  offset
    epi_a = kron(identity(S), csr_matrix(np.full((1, nx), p["q"])))
    epi = hstack([csr_matrix((S, nu)), csr_matrix(np.full((S, nu), p["r"])), csr_matrix(-np.ones((S, 1))), epi_a])
    Iu = identity(nu, format="csr")
    absu = vstack([hstack([Iu, -Iu, csr_matrix((nu, 1)), csr_matrix((nu, S * nx))]),
                   hstack([-Iu, -Iu, csr_matrix((nu, 1)), csr_matrix((nu, S * nx))])])
    A_ub = vstack([upper, lower, epi, absu]).tocsc()
    b_ub = np.concatenate([-offset, offset, np.zeros(S), np.zeros(2 * nu)])
    cost = np.zeros(2 * nu + 1 + S * nx)
    cost[2 * nu] = 1.0
    umax = np.tile(np.array(p["umax"]), N)
    xmax = np.tile(np.array(p["xmax"]), N * S)
    bounds = ([(-u, u) for u in umax] + [(0, None)] * nu + [(None, None)] + [(0, x) for x in xmax])
    res = linprog(cost, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")
    if res.status != 0:
        return None
    u = res.x[:nu].reshape(N, m)
    cfull, Gfull = _rt_prediction(p)
    z = cfull + np.einsum("tij,j->ti", Gfull, res.x[:nu])
    return _rt_policy(np.zeros((m, n)), u, z)


def _rt_controllable(A, B):
    import numpy as np
    A, B = np.array(A), np.array(B)
    blocks, M = [], B
    for _ in range(len(A)):
        blocks.append(M)
        M = A @ M
    return np.linalg.matrix_rank(np.hstack(blocks)) == len(A)


def tube_instance(seed):
    import numpy as np
    r = random.Random(f"genome:control_robust_tube:{seed}")
    while True:
        kind = r.choice(("double_integrator", "unstable", "stable_oscillator", "third_order"))
        if kind == "double_integrator":
            dt = r.uniform(0.2, 0.6)
            A = [[1.0, dt], [0.0, 1.0]]
            B = [[0.5 * dt * dt], [dt]]
        elif kind == "unstable":
            lam = [r.uniform(1.02, 1.2), r.uniform(0.4, 0.95)]
            th = r.uniform(0, math.pi)
            V = np.array([[math.cos(th), -math.sin(th) * r.uniform(0.3, 1.0)], [math.sin(th), math.cos(th)]])
            A = (V @ np.diag(lam) @ np.linalg.inv(V)).tolist()
            B = [[r.uniform(-1, 1)], [r.uniform(0.3, 1.0)]]
        elif kind == "stable_oscillator":
            rho, th = r.uniform(0.85, 0.99), r.uniform(0.2, 1.0)
            A = [[rho * math.cos(th), -rho * math.sin(th)], [rho * math.sin(th), rho * math.cos(th)]]
            B = [[r.uniform(-0.5, 0.5)], [r.uniform(0.4, 1.0)]]
        else:
            dt = r.uniform(0.2, 0.5)
            A = [[1.0, dt, 0.0], [0.0, 1.0, dt], [0.0, 0.0, r.uniform(0.5, 1.0)]]
            B = [[0.0], [0.0], [dt]]
        n = len(A)
        A = [[round(x, 6) for x in row] for row in A]
        B = [[round(x, 6) for x in row] for row in B]
        if _rt_controllable(A, B):
            break
    N = r.choice((3, 4, 5)) if n == 2 else r.choice((3, 4))
    xmax = [round(r.uniform(1.0, 3.0), 4) for _ in range(n)]
    x0 = [round(r.uniform(0.3, 0.9) * b * r.choice((-1, 1)), 4) for b in xmax]
    umax = [round(r.uniform(0.5, 2.0), 4)]
    wmax = [round(r.uniform(0.01, 0.08) * b, 4) for b in xmax]
    data = {"A": A, "B": B, "x0": x0, "x_max": xmax, "u_max": umax, "w_max": wmax, "horizon": N,
            "weights": {"q": 1.0, "r": round(r.uniform(0.05, 1.0), 4)}}
    return data, {"plant": kind, "vertex_sequences": 1 << (n * N),
                  "truth_method": "exact worst case over every disturbance vertex sequence (score)"}


def tube_subregion(data):
    import numpy as np
    rho = float(max(abs(np.linalg.eigvals(np.array(data["A"])))))
    regime = "unstable" if rho > 1.0 + 1e-9 else ("marginal" if rho > 0.999 else "stable")
    load = max(w / x for w, x in zip(data["w_max"], data["x_max"]))
    return f"{regime}_{'heavy' if load > 0.05 else 'light'}_disturbance"


# =================================================================== signal-level sensing: two-sided CUSUM
CU_MAX_LEN = 20000
FALSE_ALARM_LOSS = 200.0         # declared loss of an alarm before the change (or with no change), in samples
MISS_LOSS = 100.0                # declared extra loss of a missed change, beyond the samples it ran undetected
SIEGMUND_OFFSET = 1.166          # Siegmund's overshoot correction for Gaussian CUSUM


def _cu(data):
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    stream = data.get("stream")
    if not isinstance(stream, list) or not 2 <= len(stream) <= CU_MAX_LEN or not all(_num(x) for x in stream):
        raise GenomeError(f"stream: 2-{CU_MAX_LEN} finite numbers")
    mu0, sigma, delta, arl0 = (data.get(k) for k in ("mu0", "sigma", "delta", "arl0"))
    if not _num(mu0) or not _num(sigma) or sigma <= 0 or not _num(delta) or delta <= 0:
        raise GenomeError("mu0 finite; sigma > 0; delta > 0 (declared post-change shift magnitude)")
    if not _num(arl0) or not 20 <= arl0 <= 1e7:
        raise GenomeError("arl0: declared in-control average run length, 20-1e7 samples")
    return [float(x) for x in stream], float(mu0), float(sigma), float(delta), float(arl0)


def _siegmund_two_sided_arl(h, k):
    """In-control ARL of the two-sided CUSUM (two symmetric one-sided charts): Siegmund's approximation of each
    one-sided ARL with drift -k and boundary h + 1.166, halved."""
    b = h + SIEGMUND_OFFSET
    one = (math.exp(2 * k * b) - 2 * k * b - 1) / (2 * k * k)
    return one / 2.0


def _cusum_threshold(k, arl0):
    lo, hi = 0.0, 1.0
    while _siegmund_two_sided_arl(hi, k) < arl0:
        hi *= 2.0
        if hi > 1e4:
            raise GenomeError("threshold out of range")
    for _ in range(200):
        mid = (lo + hi) / 2
        if _siegmund_two_sided_arl(mid, k) < arl0:
            lo = mid
        else:
            hi = mid
    return hi


def cusum_solve(data, budget):
    stream, mu0, sigma, delta, arl0 = _cu(data)
    k = delta / (2 * sigma)
    h = _cusum_threshold(k, arl0)
    up = down = 0.0
    alarm, direction, stat = None, None, None
    for t, x in enumerate(stream):
        z = (x - mu0) / sigma
        up = max(0.0, up + z - k)
        down = max(0.0, down - z - k)
        if up > h or down > h:
            alarm, direction, stat = t, ("up" if up > h else "down"), max(up, down)
            break
    cert = {"rule": "two-sided Page CUSUM, reference k = delta / (2 sigma), threshold h from Siegmund's ARL0 "
                    "approximation", "k": k, "h": h, "statistic_at_alarm": stat,
            "declared_arl0": arl0, "samples_read": (alarm + 1) if alarm is not None else len(stream)}
    return answer({"alarm": alarm, "direction": direction}, cert)


def cusum_verify(data, output, certificate):
    """Recompute both statistics as cumulative sum minus running minimum (NumPy) and check the threshold against the
    ARL0 equation directly."""
    import numpy as np
    stream, mu0, sigma, delta, arl0 = _cu(data)
    if (not isinstance(output, dict) or set(output) != {"alarm", "direction"}
            or not (output["alarm"] is None or (type(output["alarm"]) is int and 0 <= output["alarm"] < len(stream)))
            or output["direction"] not in ((None,) if output["alarm"] is None else ("up", "down"))):
        return {"output_shape": False}
    if not isinstance(certificate, dict) or not _num(certificate.get("k")) or not _num(certificate.get("h")):
        return {"output_shape": True, "certificate_well_formed": False}
    k, h = float(certificate["k"]), float(certificate["h"])
    k_ok = abs(k * 2 * sigma - delta) <= 1e-9 * max(1.0, delta)
    b = h + SIEGMUND_OFFSET
    arl = (math.expm1(2 * k * b) - 2 * k * b) / (4 * k * k) if k > 0 else float("inf")
    h_ok = h > 0 and abs(arl / arl0 - 1.0) <= 1e-6
    z = (np.asarray(stream) - mu0) / sigma
    alarm_true, dir_true = None, None
    for sign, name in ((1.0, "up"), (-1.0, "down")):
        C = np.concatenate([[0.0], np.cumsum(sign * z - k)])
        S = C[1:] - np.minimum.accumulate(C)[1:]
        hits = np.flatnonzero(S > h)
        if hits.size and (alarm_true is None or hits[0] < alarm_true):
            alarm_true, dir_true = int(hits[0]), name
    return {"output_shape": True, "certificate_well_formed": True, "reference_value_matches_delta": k_ok,
            "threshold_meets_declared_arl0": h_ok, "alarm_is_the_first_crossing": output["alarm"] == alarm_true,
            "direction_matches_the_crossing_chart": output["direction"] == dir_true}


def _cu_loss(T, tau, alarm):
    if tau is None:
        return (0.0, "correct") if alarm is None else (FALSE_ALARM_LOSS, "wrong")
    if alarm is None:
        return float(T - tau) + MISS_LOSS, "wrong"
    if alarm < tau:
        return FALSE_ALARM_LOSS, "wrong"
    return float(alarm - tau), "correct"


def cusum_score(data, truth, output):
    """Declared loss (samples): detection delay alarm - tau; a false alarm (before tau, or with no change) 200; a miss
    (T - tau) + 100; no change and no alarm 0. Quality = -loss. Abstaining claims nothing: it carries the no-alarm
    loss with category abstain."""
    stream = data["stream"]
    tau = truth["change_point"]
    if output is None:
        loss, _ = _cu_loss(len(stream), tau, None)
        return {"quality": -loss, "category": "abstain"}
    alarm = output.get("alarm") if isinstance(output, dict) else "malformed"
    if not (alarm is None or (type(alarm) is int and 0 <= alarm < len(stream))):
        return {"quality": -(len(stream) + FALSE_ALARM_LOSS + MISS_LOSS), "category": "wrong"}
    loss, category = _cu_loss(len(stream), tau, alarm)
    return {"quality": -loss, "category": category}


def _normal_quantile(p):
    """Inverse standard normal CDF by bisection on erfc (stdlib only)."""
    lo, hi = -40.0, 40.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if 0.5 * math.erfc(-mid / math.sqrt(2)) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def cusum_window_ztest(data):
    """Baseline: non-overlapping windows of w samples; alarm at the end of the first window whose mean differs from
    mu0 by more than z sigma / sqrt(w), with the per-window false-alarm probability w / ARL0 (so the in-control ARL
    is exactly ARL0) and w the smallest window giving the declared shift a noncentrality of z + 1."""
    stream, mu0, sigma, delta, arl0 = _cu(data)
    w = 1
    for _ in range(50):
        z = _normal_quantile(1 - min(0.5, w / arl0) / 2)
        nxt = max(1, math.ceil(((z + 1.0) * sigma / delta) ** 2))
        if nxt == w:
            break
        w = nxt
    z = _normal_quantile(1 - min(0.5, w / arl0) / 2)
    for end in range(w, len(stream) + 1, w):
        mean = sum(stream[end - w:end]) / w
        if abs(mean - mu0) * math.sqrt(w) / sigma > z:
            return {"alarm": end - 1, "direction": "up" if mean > mu0 else "down"}
    return {"alarm": None, "direction": None}


def cusum_shiryaev_roberts(data):
    """Competitor: two-sided Shiryaev-Roberts (one chart per shift sign, log domain), each chart's threshold
    A = 2 ARL0 nu, with nu = exp(-0.583 delta / sigma) Siegmund's overshoot factor (Pollak 1987: E_inf T ~ A / nu)."""
    stream, mu0, sigma, delta, arl0 = _cu(data)
    mu = delta / sigma
    log_a = math.log(2 * arl0 * math.exp(-0.583 * mu))
    log_up = log_down = -math.inf
    for t, x in enumerate(stream):
        z = (x - mu0) / sigma
        log_up = (math.log1p(math.exp(log_up)) if log_up < 30 else log_up + math.log1p(math.exp(-log_up))) \
            + mu * z - mu * mu / 2
        log_down = (math.log1p(math.exp(log_down)) if log_down < 30 else log_down + math.log1p(math.exp(-log_down))) \
            - mu * z - mu * mu / 2
        if log_up > log_a or log_down > log_a:
            return {"alarm": t, "direction": "up" if log_up > log_a else "down"}
    return {"alarm": None, "direction": None}


def cusum_instance(seed):
    r = random.Random(f"genome:basal_cusum_detect:{seed}")
    T = r.randrange(200, 801)
    # merge review 2026-10-22 (before the v8 freeze): ARL0 200-1000 was shorter than the 200-800-sample streams, so
    # every detector false-alarmed on most instances and the benchmark could not separate them. The declared
    # in-control run length is now long relative to the pre-change segment (at most 640 samples).
    arl0 = r.choice((5000.0, 10000.0, 20000.0))
    sigma = round(r.uniform(0.5, 3.0), 4)
    mu0 = round(r.uniform(-5.0, 5.0), 4)
    delta = round(sigma * r.choice((0.5, 0.75, 1.0, 1.5, 2.0)), 6)
    change = r.random() < 0.75
    tau = r.randrange(T // 5, (4 * T) // 5) if change else None
    shift = delta * r.choice((0.5, 1.0, 1.0, 2.0)) * r.choice((-1, 1)) if change else 0.0
    noise = r.choice(("gaussian", "gaussian", "student_t5"))
    stream = []
    for t in range(T):
        if noise == "gaussian":
            e = r.gauss(0.0, 1.0)
        else:                                              # Student t, 5 dof, scaled to unit variance
            chi = sum(r.gauss(0.0, 1.0) ** 2 for _ in range(5))
            e = r.gauss(0.0, 1.0) / math.sqrt(chi / 5) / math.sqrt(5 / 3)
        stream.append(round(mu0 + sigma * e + (shift if change and t >= tau else 0.0), 6))
    data = {"stream": stream, "mu0": mu0, "sigma": sigma, "delta": delta, "arl0": arl0}
    return data, {"change_point": tau, "shift": shift, "noise": noise}


def cusum_subregion(data):
    mag = data["delta"] / data["sigma"]
    return f"{'small' if mag < 0.9 else 'large'}_declared_shift_arl{int(data['arl0'])}"


# =================================================================== local error correction: Hamming / SECDED
CODES = {"hamming_7_4": (3, False), "hamming_15_11": (4, False), "secded_8_4": (3, True), "secded_16_11": (4, True)}
HC_MAX_BLOCKS = 4096
BAYES_MAX_DATA_BITS = 11


def _hc(data):
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    code = data.get("code")
    if code not in CODES:
        raise GenomeError(f"code: one of {sorted(CODES)}")
    r, extended = CODES[code]
    n = (1 << r) - 1 + (1 if extended else 0)
    words = data.get("codewords")
    if (not isinstance(words, list) or not 1 <= len(words) <= HC_MAX_BLOCKS
            or not all(isinstance(w, str) and len(w) == n and not set(w) - {"0", "1"} for w in words)):
        raise GenomeError(f"codewords: 1-{HC_MAX_BLOCKS} strings of {n} bits")
    p = data.get("flip_probability")
    if not _num(p) or not 0 < p < 0.5:
        raise GenomeError("flip_probability: declared channel flip probability in (0, 0.5)")
    return code, r, extended, words, float(p)


def _data_positions(r):
    """Hamming positions 1..2^r - 1 that carry data (not powers of two), in order."""
    return [j for j in range(1, 1 << r) if j & (j - 1)]


def hamming_solve(data, budget):
    import numpy as np
    code, r, extended, words, _ = _hc(data)
    n = (1 << r) - 1
    R = np.array([[int(c) for c in w] for w in words], dtype=np.int64)
    ham = R[:, 1:] if extended else R                         # Hamming positions 1..n at columns 0..n-1
    H = (np.arange(1, n + 1)[None, :] >> np.arange(r)[:, None]) & 1      # r x n: column j = binary(j + 1)
    syn = ((ham @ H.T) % 2) @ (1 << np.arange(r))
    parity = R.sum(axis=1) % 2 if extended else None
    fixed = R.copy()
    status = []
    for b in range(len(words)):
        s = int(syn[b])
        if extended:
            if parity[b] == 0 and s == 0:
                status.append("ok")
            elif parity[b] == 1:
                fixed[b, s] ^= 1                              # s = 0: the overall parity bit itself (column 0)
                status.append("corrected")
            else:
                status.append("uncorrectable")
        elif s == 0:
            status.append("ok")
        else:
            fixed[b, s - 1] ^= 1
            status.append("corrected")
    cols = [j if extended else j - 1 for j in _data_positions(r)]
    decoded = ["".join(str(int(x)) for x in fixed[b, cols]) if status[b] != "uncorrectable" else None
               for b in range(len(words))]
    cert = {"rule": "syndrome decoding" + ("; overall parity separates single from double errors" if extended else ""),
            "syndromes": [int(s) for s in syn],
            "overall_parity": [int(x) for x in parity] if extended else None}
    return answer({"decoded": decoded, "status": status}, cert)


def _reencode(bits, r, extended):
    """Independent bit-by-bit encoder: data bits fill non-power-of-two positions; parity at 2^i is the XOR of the
    data positions whose index has bit i set; the extended code prepends the XOR of every bit."""
    n = (1 << r) - 1
    word = [0] * (n + 1)                                       # 1-based
    it = iter(bits)
    for j in range(1, n + 1):
        if j & (j - 1):
            word[j] = next(it)
    for i in range(r):
        pos = 1 << i
        acc = 0
        for j in range(1, n + 1):
            if j != pos and j & pos:
                acc ^= word[j]
        word[pos] = acc
    body = word[1:]
    return ([sum(body) % 2] + body) if extended else body


def _check_bits(received, r, extended):
    """Independent syndrome (as a list of r check bits) and overall parity of a received word."""
    body = received[1:] if extended else received
    checks = []
    for i in range(r):
        acc = 0
        for j, bit in enumerate(body, start=1):
            if j >> i & 1:
                acc ^= bit
        checks.append(acc)
    return checks, (sum(received) % 2 if extended else None)


def hamming_verify(data, output, certificate):
    code, r, extended, words, _ = _hc(data)
    k = len(_data_positions(r))
    if (not isinstance(output, dict) or set(output) != {"decoded", "status"}
            or not isinstance(output["decoded"], list) or not isinstance(output["status"], list)
            or len(output["decoded"]) != len(words) or len(output["status"]) != len(words)):
        return {"output_shape": False}
    shapes = reencode = flags = consistent = True
    for word, dec, st in zip(words, output["decoded"], output["status"]):
        received = [int(c) for c in word]
        if st == "uncorrectable":
            consistent &= dec is None
            checks, parity = _check_bits(received, r, extended)
            # distance >= 2 from every codeword: SECDED only, even overall parity and a nonzero syndrome
            flags &= extended and parity == 0 and any(checks)
            continue
        if st not in ("ok", "corrected") or not isinstance(dec, str) or len(dec) != k or set(dec) - {"0", "1"}:
            shapes = False
            continue
        enc = _reencode([int(c) for c in dec], r, extended)
        distance = sum(a != b for a, b in zip(enc, received))
        reencode &= distance == (0 if st == "ok" else 1)
    return {"output_shape": shapes, "every_decoded_block_reencodes_within_its_claimed_distance": reencode,
            "every_flag_is_a_detected_double_error": flags, "flagged_blocks_carry_no_data": consistent}


def hamming_score(data, truth, output):
    """Per block: the original data 1; a flagged block 0; a silent miscorrection (wrong data, unflagged) -1, so a silent
    miscorrection costs two units more than a flag. Quality is the mean; the instance is wrong when any block is a
    silent miscorrection. Abstaining (nothing decoded) is quality 0, category abstain."""
    original = truth["data"]
    if output is None:
        return {"quality": 0.0, "category": "abstain"}
    decoded = output.get("decoded") if isinstance(output, dict) else None
    if not isinstance(decoded, list) or len(decoded) != len(original):
        return {"quality": -1.0, "category": "wrong"}
    values = [1 if d == o else (0 if d is None else -1) for d, o in zip(decoded, original)]
    return {"quality": sum(values) / len(values), "category": "wrong" if -1 in values else "correct"}


def hamming_raw(data):
    """Baseline: no correction; the data positions of each received word are read as they are."""
    code, r, extended, words, _ = _hc(data)
    cols = [j if extended else j - 1 for j in _data_positions(r)]
    return {"decoded": ["".join(w[c] for c in cols) for w in words], "status": ["ok"] * len(words)}


def hamming_bayes(data):
    """Competitor: the exhaustive Bayes decoder under the declared loss and flip probability. Every one of the 2^k
    codewords is scored by its likelihood p^d (1-p)^(n-d) (uniform prior); the MAP codeword is decoded when its
    posterior exceeds 1/2 (decoding then has positive expected score against flagging, 2P - 1 > 0), else the block is
    flagged. For independent flips at the declared p no decoder has a better expected score."""
    import numpy as np
    code, r, extended, words, p = _hc(data)
    k = len(_data_positions(r))
    if k > BAYES_MAX_DATA_BITS:
        return None
    msgs = (np.arange(1 << k)[:, None] >> np.arange(k - 1, -1, -1)[None, :]) & 1
    book = np.array([_reencode(list(m), r, extended) for m in msgs], dtype=np.int64)       # 2^k x n
    R = np.array([[int(c) for c in w] for w in words], dtype=np.int64)
    dist = (R[:, None, :] != book[None, :, :]).sum(axis=2)                                   # blocks x 2^k
    logl = dist * math.log(p) + (book.shape[1] - dist) * math.log1p(-p)
    best = logl.argmax(axis=1)
    post = 1.0 / np.exp(logl - logl.max(axis=1, keepdims=True)).sum(axis=1)
    decoded, status = [], []
    for b in range(len(words)):
        if post[b] > 0.5:
            decoded.append("".join(str(int(x)) for x in msgs[best[b]]))
            status.append("ok" if dist[b, best[b]] == 0 else "corrected")
        else:
            decoded.append(None)
            status.append("uncorrectable")
    return {"decoded": decoded, "status": status}


def hamming_instance(seed):
    r_ = random.Random(f"genome:basal_hamming_correct:{seed}")
    code = r_.choice(sorted(CODES))
    r, extended = CODES[code]
    k = len(_data_positions(r))
    blocks = r_.randrange(16, 97)
    p = round(r_.uniform(0.005, 0.15), 5)
    model = r_.choice(("iid", "iid", "burst"))
    original, words, flips = [], [], []
    for _ in range(blocks):
        bits = [r_.randrange(2) for _ in range(k)]
        enc = _reencode(bits, r, extended)
        if model == "iid":
            pos = [j for j in range(len(enc)) if r_.random() < p]
        else:                                                  # occasional bursts at the same mean flip rate
            length = r_.randrange(2, 4)
            pos = sorted(set(range(start := r_.randrange(len(enc)), min(len(enc), start + length))))
            pos = pos if r_.random() < p * len(enc) / length else []
        for j in pos:
            enc[j] ^= 1
        original.append("".join(map(str, bits)))
        words.append("".join(map(str, enc)))
        flips.append(pos)
    data = {"code": code, "codewords": words, "flip_probability": p}
    return data, {"data": original, "flips": flips, "error_model": model}


def hamming_subregion(data):
    return f"{data['code']}_{'noisy' if data['flip_probability'] > 0.05 else 'clean'}"


# =================================================================== genomes
INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.control.tube_mpc_lqr", version="1.0.0", family="control_robust_tube", layer=3,
            operation="robust_tube_mpc", epistemic_class="physical",
            subgeometry="discrete-time linear plant, box-bounded additive disturbance, box state and input "
                        "constraints, short horizon; robust constraint satisfaction then worst-case L1 cost",
            source_provenance="tube MPC (Mayne, Seron and Rakovic 2005; Chisci, Rossiter and Zappa 2001 constraint "
                              "tightening); discrete LQR ancillary gain (SciPy solve_discrete_are); HiGHS LP",
            native_representation="A, B, x0, box bounds x_max, u_max, disturbance box w_max, horizon N, L1 weights",
            required_inputs=("A", "B", "x0", "x_max", "u_max", "w_max", "horizon", "weights"),
            output_contract={"K": "ancillary gain m x n", "nominal_inputs": "v_t (N x m)",
                             "nominal_states": "z_t (N+1 x n)", "policy": "u_t = v_t + K (x_t - z_t)"},
            algorithm_or_runtime="DARE gain K; exact finite-horizon support of the error reach set of A + B K gives "
                                 "per-step tightening; one nominal L1 LP (HiGHS) on the tightened constraints",
            parameters={"max_states": RT_MAX_N, "max_inputs": RT_MAX_M, "max_horizon": RT_MAX_HORIZON,
                        "max_vertex_bits": RT_MAX_VERTEX_BITS},
            memory_model="none across requests", learning_rule="none",
            composition_inputs=("linear plant model", "disturbance bound", "constraints"),
            composition_outputs=("affine feedback policy over the horizon", "certified worst-case cost bound"),
            evidence_type="feasibility_witness",
            verification_method="independent step-by-step closed-loop simulation over every disturbance vertex "
                                "sequence (itertools enumeration): nominal consistency, input and state bounds on "
                                "every vertex, worst-case cost within the certified bound",
            confidence_semantics="exact for the declared linear model and disturbance box over the horizon: no "
                                 "admissible disturbance sequence violates a constraint; says nothing beyond the "
                                 "horizon (no terminal invariant set) or about model mismatch",
            resource_profile="one small LP (3N(n + m) variables); verification enumerates 2^(nN) <= 4096 sequences",
            latency_profile="milliseconds",
            known_strengths=("robust constraint satisfaction by construction (exact tightening), with a "
                             "certificate a simulation can check",
                             "feedback shrinks the error reach on unstable plants, so it stays feasible where an "
                             "open-loop robust plan cannot",
                             "one LP regardless of the number of disturbance vertices"),
            known_failure_modes=("optimises the nominal cost, not the worst-case cost: the open-loop min-max "
                                 "competitor optimises the score's own objective and can be cheaper on stable "
                                 "plants with light disturbance",
                                 "a fixed LQR gain is not optimised for the tightening; a poor K over-tightens and "
                                 "the nominal problem becomes infeasible (abstains)",
                                 "finite horizon only: no recursive feasibility or terminal invariant set is claimed",
                                 "the benchmark plants are seeded models; GREG controls no real plant"),
            counterindications=("nonlinear or uncertain plant matrices (parametric uncertainty)",
                                "stochastic disturbances where a chance constraint is the right specification",
                                "long horizons with wide state (vertex verification is exponential)"),
            abstention_conditions=("no stabilising Riccati solution", "the tightened nominal problem is infeasible",
                                   "n x horizon above 12 (worst case not exhaustively checkable)"),
            benchmark_suite="seeded double integrators, unstable and stable-oscillator 2-state plants and a "
                            "3-state chain, horizon 3-5, disturbance 1-8% of the state bounds; quality: violations "
                            "first (wrong), then worst-case L1 cost over every vertex sequence by superposition; "
                            "seeds 0-9 dev, held-out seeds fixed by the admission freeze",
            baseline="certainty-equivalent nominal MPC (same LP, constraints not tightened), applied open loop",
            competitor="min-max open-loop MPC: one vertex-scenario LP (SciPy HiGHS) keeps every vertex sequence "
                       "feasible and minimises the worst scenario's L1 cost",
            dependency="scipy", buildability="BUILDABLE_NOW", lineage=LINEAGE + (
                "docs/collaboration/MIND-COVERAGE-2026-10-21.md (robust control ABSENT)",)),
        solve=tube_solve, verify=tube_verify, instance=tube_instance, score=tube_score, baseline=tube_nominal,
        competitor=tube_minmax_open_loop, subregion=tube_subregion, tolerance=1e-6),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="basal.sensing.cusum_two_sided", version="1.0.0", family="basal_cusum_detect", layer=1,
            operation="detect_mean_shift", epistemic_class="estimate",
            subgeometry="online detection of a mean shift in a supplied numeric stream with known in-control mean "
                        "and spread; signal-level sensing only (GREG has no physical sensors)",
            source_provenance="Page (1954) cumulative sum; Lorden (1971) minimax optimality; Siegmund (1985) ARL "
                              "approximation with the 1.166 overshoot correction",
            native_representation="stream of numbers, in-control mean mu0 and sd sigma, declared shift magnitude "
                                  "delta, declared in-control ARL0",
            required_inputs=("stream", "mu0", "sigma", "delta", "arl0"),
            output_contract={"alarm": "index of the first alarm, or null", "direction": "up | down | null"},
            algorithm_or_runtime="two one-sided CUSUM recursions S = max(0, S +/- z - k), k = delta / (2 sigma); "
                                 "alarm when either exceeds h, with h solved by bisection from Siegmund's ARL0 "
                                 "approximation",
            parameters={"max_length": CU_MAX_LEN, "false_alarm_loss": FALSE_ALARM_LOSS, "miss_loss": MISS_LOSS},
            memory_model="two running sums; constant memory", learning_rule="none (in-control parameters declared)",
            composition_inputs=("a signal stream", "its in-control model"),
            composition_outputs=("alarm time", "shift direction"),
            evidence_type="statistical_estimate",
            verification_method="independent NumPy recomputation of both statistics as cumulative sum minus running "
                                "minimum; the threshold is checked against the ARL0 equation in closed form; the "
                                "alarm must be the first crossing and the direction its chart",
            confidence_semantics="the alarm is a statistical decision: under the in-control model false alarms "
                                 "occur at about one per ARL0 samples (Siegmund's approximation, not exact)",
            resource_profile="O(T) time, O(1) memory", latency_profile="sub-millisecond to a few milliseconds",
            known_strengths=("minimax-optimal detection delay for the declared shift at a given false-alarm rate "
                             "(Lorden)", "constant memory and purely local updates", "detects both directions"),
            known_failure_modes=("the threshold comes from an approximation for Gaussian data; heavy-tailed noise "
                                 "raises the false-alarm rate above the declared ARL0",
                                 "a shift much smaller than the declared delta is detected slowly or missed",
                                 "Shiryaev-Roberts has near-identical delay; the two differ by a few samples either "
                                 "way, so a decisive lift over it is not expected",
                                 "signal-level only: GREG has no physical sensors and reads only supplied streams"),
            counterindications=("unknown in-control mean or variance (needs self-starting estimation)",
                                "autocorrelated streams", "variance changes rather than mean shifts"),
            abstention_conditions=("none beyond invalid input: no alarm is itself an answer",),
            benchmark_suite="seeded streams of 200-800 samples, declared ARL0 200/500/1000, change in 75% of streams "
                            "at a uniform point, actual shift 0.5-2x the declared delta in either direction, "
                            "Gaussian or Student-t5 noise; declared loss (delay; false alarm 200; miss T - tau + "
                            "100); seeds 0-9 dev, held-out seeds fixed by the admission freeze",
            baseline="fixed-window z-test on non-overlapping windows sized for the declared shift, per-window "
                     "false-alarm probability w / ARL0",
            competitor="two-sided Shiryaev-Roberts with Pollak's ARL0 threshold A = 2 ARL0 exp(-0.583 delta / sigma) "
                       "per chart",
            dependency=None, buildability="BUILDABLE_NOW", lineage=LINEAGE + (
                "docs/collaboration/MIND-COVERAGE-2026-10-21.md (local sensing ABSENT)",)),
        solve=cusum_solve, verify=cusum_verify, instance=cusum_instance, score=cusum_score,
        baseline=cusum_window_ztest, competitor=cusum_shiryaev_roberts, subregion=cusum_subregion, tolerance=1e-9),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="basal.repair.hamming_syndrome", version="1.0.0", family="basal_hamming_correct",
            layer=1, operation="correct_bit_errors", epistemic_class="arithmetic",
            subgeometry="block codes over a binary channel: Hamming(7,4), Hamming(15,11), extended Hamming SECDED "
                        "(8,4) and (16,11)",
            source_provenance="Hamming (1950) error detecting and error correcting codes; extended Hamming "
                              "single-error-correct double-error-detect (SECDED)",
            native_representation="code name, received codewords as bit strings, declared flip probability",
            required_inputs=("code", "codewords", "flip_probability"),
            output_contract={"decoded": "[data bits or null]", "status": "[ok | corrected | uncorrectable]"},
            algorithm_or_runtime="syndrome = H r mod 2 (NumPy) names the flipped position; SECDED overall parity "
                                 "separates single (correct) from double (flag) errors",
            parameters={"max_blocks": HC_MAX_BLOCKS},
            memory_model="none", learning_rule="none",
            composition_inputs=("a stream of received codewords",),
            composition_outputs=("corrected data", "detected-uncorrectable flags"),
            evidence_type="exact_calculation",
            verification_method="independent bit-by-bit re-encoding of every decoded block (distance 0 for ok, 1 for "
                                "corrected) and independent check-bit and parity recomputation for every flag (a "
                                "flag must be a detected double error)",
            confidence_semantics="every decoded block is the unique codeword within distance 1 of what was received; "
                                 "three or more flips (two for plain Hamming) can still decode silently to wrong data",
            resource_profile="O(blocks x n x r)", latency_profile="sub-millisecond to milliseconds",
            known_strengths=("corrects every single flip per block exactly",
                             "SECDED flags every double flip instead of guessing",
                             "cost independent of the number of codewords (no codebook search)"),
            known_failure_modes=("plain Hamming silently miscorrects every double flip (it cannot detect them)",
                                 "three flips in a SECDED block decode silently to wrong data",
                                 "ignores the declared flip probability: at high p on (15,11) the Bayes decoder "
                                 "flags blocks where a single-error correction is more likely wrong than right",
                                 "on independent flips at the declared p the exhaustive Bayes competitor is optimal "
                                 "in expectation; outside that regime the two decide identically, so the candidate "
                                 "can at best tie it on quality and win on cost"),
            counterindications=("burst channels without interleaving", "codes other than the declared four",
                                "soft-decision (analog) channel outputs"),
            abstention_conditions=("none beyond invalid input: a double error is a flag, not an abstention",),
            benchmark_suite="seeded blocks of random data in one of four codes, 16-96 blocks, flip probability "
                            "0.005-0.15, independent flips or occasional 2-3 bit bursts at the same mean rate; per "
                            "block +1 correct, 0 flagged, -1 silent miscorrection; seeds 0-9 dev, held-out seeds "
                            "fixed by the admission freeze",
            baseline="no correction: the data positions are read as received",
            competitor="exhaustive Bayes decoder under the declared loss: posterior over all 2^k codewords at the "
                       "declared flip probability, decode the MAP codeword when its posterior exceeds 1/2, else "
                       "flag (triple modular redundancy at matched redundancy is infeasible: it needs rate 1/3 and "
                       "its own transmission; plain maximum-likelihood table decoding guesses on SECDED double "
                       "errors and is weaker under this loss)",
            dependency=None, buildability="BUILDABLE_NOW", lineage=LINEAGE + (
                "docs/collaboration/MIND-COVERAGE-2026-10-21.md (local error correction ABSENT)",)),
        solve=hamming_solve, verify=hamming_verify, instance=hamming_instance, score=hamming_score,
        baseline=hamming_raw, competitor=hamming_bayes, subregion=hamming_subregion, tolerance=1e-9),
]
