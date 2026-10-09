"""Layer 1 basal intelligences: narrow, cheap, inspectable feedback, estimation and switching rules.

Each intelligence here is a classical engineering mechanism with a few-line state update, a native
benchmark whose truth comes from the generator itself (or an exhaustive grid over it), a simple baseline
and the strongest reasonable competing rule. The names describe the computation, nothing more; none of
these rules is a model of life, cognition or general intelligence, and none creates authority: they are
read-only computations over the data handed to them.

``basal_pid`` (operation ``pid_track``): SIMC PI tuning (Skogestad 2003, tau_c = theta) of a declared
    first-order-plus-dead-time plant, simulated in closed loop on the declared scenario (setpoint schedule,
    input load step, seeded measurement noise, actuator limits, conditional-integration anti-windup).
``basal_kalman`` (operation ``kalman_track``): 1-D constant-velocity Kalman filter with known discrete
    white-noise-acceleration and measurement variances; refuses (abstains) when its own innovation test
    rejects the declared noise model.
``basal_hysteresis`` (operation ``hysteresis_switch``): Schmitt trigger (hysteresis band) with a
    confirmation count, both chosen in closed form from the declared Gaussian noise and dwell model.
``basal_bandit`` (operation ``bandit_allocate``): Thompson sampling with Beta(1, 1) priors on a Bernoulli
    reward tape.
``basal_breaker`` (operation ``circuit_break``): closed / open / half-open circuit breaker whose trip
    count is a binomial-tail test of the declared background failure rate and whose cooldown balances the
    declared outage-call and unavailability costs.

Scoring convention shared by all five: ``score(data, truth, None)`` (abstention) is the quality of the
system's safe fallback when the method declines (manual hold, raw sensor, never switch, round-robin,
always call). A "wrong" answer is never scored above one unit below that fallback, so a false answer can
never look better than abstaining.
"""
from __future__ import annotations

from collections import deque
import hashlib
import math
import random

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int, finite

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT")


def _dict(data):
    if not isinstance(data, dict):
        raise GenomeError("data must be an object")
    return data


def _wrong(raw_quality, fallback_quality):
    """A false answer scores at most one unit below abstaining."""
    return {"quality": float(min(raw_quality, fallback_quality - 1.0)), "category": "wrong"}


def _q(x):
    """Upper Gaussian tail Q(x) = P(N(0,1) > x)."""
    return 0.5 * math.erfc(x / math.sqrt(2.0))


# ======================================================================== basal_pid
PID_EFFORT_WEIGHT = 0.05   # cost = IAE + weight * |K| * dt * total variation of u   (both in y*time units)
PID_SAT_FRACTION = 0.2     # one contiguous run at the same actuator limit longer than this = persistent saturation
PID_DIVERGE = 10.0         # |r - y| above this multiple of the scenario span = divergence
PID_SETTLE_BAND = 0.05     # settling band, fraction of the setpoint step


def _pid_inputs(data):
    _dict(data)
    gain = finite(data.get("gain"), low=-1e6, high=1e6, name="gain")
    if abs(gain) < 1e-9:
        raise GenomeError("gain must be nonzero")
    tau = finite(data.get("tau"), low=1e-6, high=1e6, name="tau")
    theta = finite(data.get("theta"), low=0.0, high=1e6, name="theta")
    dt = finite(data.get("dt"), low=1e-6, high=1e6, name="dt")
    steps = bounded_int(data.get("steps"), low=10, high=10_000, name="steps")
    delay = int(round(theta / dt))
    if delay > 2000:
        raise GenomeError("dead time above 2000 samples")
    raw = data.get("setpoints")
    if not isinstance(raw, list) or not 1 <= len(raw) <= 50:
        raise GenomeError("setpoints: 1-50 [time, value] pairs required")
    schedule = []
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise GenomeError("setpoint entries are [time, value]")
        schedule.append((finite(item[0], low=0.0, high=1e12, name="setpoint time"),
                         finite(item[1], name="setpoint value")))
    if schedule[0][0] != 0.0 or any(b[0] <= a[0] for a, b in zip(schedule, schedule[1:])):
        raise GenomeError("setpoint times start at 0 and strictly increase")
    load = data.get("load", {"time": 0.0, "magnitude": 0.0})
    if not isinstance(load, dict):
        raise GenomeError("load is {time, magnitude}")
    load_time = finite(load.get("time", 0.0), low=0.0, high=1e12, name="load time")
    load_mag = finite(load.get("magnitude", 0.0), name="load magnitude")
    noise = finite(data.get("noise_sd", 0.0), low=0.0, high=1e9, name="noise_sd")
    u_min = finite(data.get("u_min"), name="u_min")
    u_max = finite(data.get("u_max"), name="u_max")
    if not u_min < u_max:
        raise GenomeError("u_min < u_max required")
    u0 = finite(data.get("u0"), name="u0")
    if not u_min <= u0 <= u_max:
        raise GenomeError("u0 within actuator limits required")
    seed = bounded_int(data.get("seed", 0), low=0, high=2**31 - 1, name="seed")
    tau_c = data.get("tau_c")
    if tau_c is not None:
        tau_c = finite(tau_c, low=1e-9, high=1e9, name="tau_c")
    return {"gain": gain, "tau": tau, "theta": theta, "dt": dt, "steps": steps, "delay": delay,
            "schedule": schedule, "load_time": load_time, "load": load_mag, "noise_sd": noise,
            "u_min": u_min, "u_max": u_max, "u0": u0, "seed": seed, "tau_c": tau_c}


def _pid_controller(out):
    """Validate a controller specification (the output contract shared by every arm)."""
    if not isinstance(out, dict) or out.get("law") not in ("pid", "on_off"):
        raise GenomeError("controller law is pid or on_off")
    if out["law"] == "on_off":
        return {"law": "on_off", "band": finite(out.get("band"), low=0.0, high=1e12, name="band")}
    kc = finite(out.get("kc"), low=-1e9, high=1e9, name="kc")
    ti = finite(out.get("ti"), low=1e-9, high=1e12, name="ti")
    td = finite(out.get("td", 0.0), low=0.0, high=1e12, name="td")
    tf = finite(out.get("tf", 0.0), low=0.0, high=1e12, name="tf")
    b = finite(out.get("b", 1.0), low=0.0, high=1.0, name="b")
    if td > 0 and tf <= 0:
        raise GenomeError("a derivative term needs a filter time tf > 0")
    return {"law": "pid", "kc": kc, "ti": ti, "td": td, "tf": tf, "b": b}


def _pid_loop(p, ctrl):
    """Solver-side closed-loop simulation (index arithmetic for the dead time)."""
    K, dt, n, d = p["gain"], p["dt"], p["steps"], p["delay"]
    a = math.exp(-dt / p["tau"])
    bp = K * (1.0 - a)
    rng = random.Random(p["seed"])
    noise = [rng.gauss(0.0, p["noise_sd"]) for _ in range(n)]
    schedule, umin, umax, u0 = p["schedule"], p["u_min"], p["u_max"], p["u0"]
    y = K * u0
    j = 0
    us, ys, rs = [], [], []
    if ctrl["law"] == "pid":
        kc, ti, td, tf, b = ctrl["kc"], ctrl["ti"], ctrl["td"], ctrl["tf"], ctrl["b"]
        ki = kc * dt / ti
        alpha = tf / (tf + dt) if td > 0 else 0.0
        beta = kc * td / (tf + dt) if td > 0 else 0.0
        integ = u0 - kc * (b * schedule[0][1] - y)
        deriv, ym_prev = 0.0, y
    else:
        on = u0 >= 0.5 * (umin + umax)
        sign = 1.0 if K > 0 else -1.0
    for k in range(n):
        t = k * dt
        while j + 1 < len(schedule) and schedule[j + 1][0] <= t:
            j += 1
        r = schedule[j][1]
        w = p["load"] if t >= p["load_time"] else 0.0
        ym = y + noise[k]
        if ctrl["law"] == "pid":
            e = r - ym
            if td > 0:
                deriv = alpha * deriv - beta * (ym - ym_prev)
            v = kc * (b * r - ym) + integ + deriv
            u = min(umax, max(umin, v))
            step = ki * e
            if not ((v > umax and step > 0) or (v < umin and step < 0)):
                integ += step
            ym_prev = ym
        else:
            e = sign * (r - ym)
            if e > ctrl["band"]:
                on = True
            elif e < -ctrl["band"]:
                on = False
            u = umax if on else umin
        us.append(u)
        ys.append(y)
        rs.append(r)
        applied = us[k - d] if k >= d else u0
        y = a * y + bp * (applied + w)
    return ys, us, rs


def _pid_metrics(p, ys, us, rs):
    dt, umin, umax, u0 = p["dt"], p["u_min"], p["u_max"], p["u0"]
    iae = sum(abs(r - y) for r, y in zip(rs, ys)) * dt
    tv = abs(us[0] - u0) + sum(abs(b - a) for a, b in zip(us, us[1:]))
    run, longest, last = 0, 0, None
    for u in us:
        lim = "max" if u >= umax else "min" if u <= umin else None
        run = run + 1 if lim is not None and lim == last else (1 if lim is not None else 0)
        last = lim
        longest = max(longest, run)
    return {"iae": iae, "effort_tv": tv, "cost": iae + PID_EFFORT_WEIGHT * abs(p["gain"]) * dt * tv,
            "max_abs_error": max(abs(r - y) for r, y in zip(rs, ys)), "longest_limit_run": longest}


def _pid_span(p):
    y0 = p["gain"] * p["u0"]
    return max(max(abs(r - y0) for _, r in p["schedule"]), abs(p["gain"] * p["load"]), 10 * p["noise_sd"], 1e-6)


def _pid_steps_summary(p, ys):
    """Overshoot and settling time of each setpoint step (true output, segment until the next event)."""
    dt, n, sched = p["dt"], p["steps"], p["schedule"]
    events = sorted({t for t, _ in sched[1:]} | ({p["load_time"]} if p["load"] != 0 and p["load_time"] > 0 else set()))
    overshoot, settling = [], []
    for (t0, r_prev), (t1, r1) in zip(sched, sched[1:]):
        k1 = math.ceil(t1 / dt - 1e-12)
        later = [t for t in events if t > t1]
        k2 = min(n, math.ceil(later[0] / dt - 1e-12)) if later else n
        step = r1 - r_prev
        if k1 >= n or k2 <= k1 or step == 0:
            overshoot.append(None)
            settling.append(None)
            continue
        seg = ys[k1:k2]
        sgn = 1.0 if step > 0 else -1.0
        overshoot.append(round(max(0.0, max((y - r1) * sgn for y in seg)) / abs(step), 6))
        band = PID_SETTLE_BAND * abs(step)
        last_out = max((i for i, y in enumerate(seg) if abs(y - r1) > band), default=-1)
        settling.append(None if last_out == len(seg) - 1 else round((last_out + 1) * dt, 6))
    return overshoot, settling


def _pid_char_poly(kc, ti, td, tf, dt, a, bp, d):
    """Closed-loop characteristic polynomial in q = z^-1 (increasing powers), linear region."""
    def mul(x, y):
        out = [0.0] * (len(x) + len(y) - 1)
        for i, xi in enumerate(x):
            for j, yj in enumerate(y):
                out[i + j] += xi * yj
        return out

    def add(x, y):
        n = max(len(x), len(y))
        return [(x[i] if i < len(x) else 0.0) + (y[i] if i < len(y) else 0.0) for i in range(n)]

    ki = kc * dt / ti
    alpha = tf / (tf + dt) if td > 0 else 0.0
    beta = kc * td / (tf + dt) if td > 0 else 0.0
    one_q, one_aq, one_alq = [1.0, -1.0], [1.0, -a], [1.0, -alpha]
    den = mul(mul(one_q, one_alq), one_aq)
    ctrl = add(add([kc * c for c in mul(one_q, one_alq)], [0.0] + [ki * c for c in one_alq]),
               [beta * c for c in mul(one_q, one_q)])
    loop = [0.0] * (d + 1) + [bp * c for c in ctrl]
    return add(den, loop)


def _pid_spectral_radius_poly(p, ctrl):
    import numpy as np
    a = math.exp(-p["dt"] / p["tau"])
    coeffs = _pid_char_poly(ctrl["kc"], ctrl["ti"], ctrl["td"], ctrl["tf"], p["dt"], a,
                            p["gain"] * (1 - a), p["delay"])
    roots = np.roots(np.array(coeffs, dtype=float))   # coefficients of increasing q = decreasing z
    return float(max(abs(roots))) if len(roots) else 0.0


def simc_pi(p):
    """SIMC PI (Skogestad 2003): Kc = tau / (K (tau_c + theta)), Ti = min(tau, 4 (tau_c + theta))."""
    tc = p["tau_c"] if p["tau_c"] is not None else p["theta"]
    kc = p["tau"] / (p["gain"] * (tc + p["theta"]))
    ti = min(p["tau"], 4.0 * (tc + p["theta"]))
    return {"law": "pid", "kc": kc, "ti": ti, "td": 0.0, "tf": 0.0, "b": 1.0}, tc


def pid_solve(data, budget):
    p = _pid_inputs(data)
    if p["theta"] < p["dt"] and p["tau_c"] is None:
        return answer(None, {"reason": "dead time below one sample"}, status="ABSTAIN",
                      missing=["dead time below one sample: SIMC tau_c = theta is undefined; declare tau_c"])
    if p["theta"] > 10.0 * p["tau"]:
        return answer(None, {"theta_over_tau": p["theta"] / p["tau"]}, status="ABSTAIN",
                      missing=["dead-time dominated beyond theta/tau = 10: a dead-time compensator is required"])
    loads = {0.0, p["load"]}
    needed = [r / p["gain"] - w for _, r in p["schedule"] for w in loads]
    margin = 0.02 * (p["u_max"] - p["u_min"])
    if any(not p["u_min"] + margin <= u <= p["u_max"] - margin for u in needed):
        return answer(None, {"required_inputs": [round(u, 6) for u in needed]}, status="ABSTAIN",
                      missing=["a setpoint is unreachable within the actuator limits"])
    ctrl, tc = simc_pi(p)
    ys, us, rs = _pid_loop(p, ctrl)
    m = _pid_metrics(p, ys, us, rs)
    overshoot, settling = _pid_steps_summary(p, ys)
    rho = _pid_spectral_radius_poly(p, ctrl)
    out = {k: (round(v, 12) if isinstance(v, float) else v) for k, v in ctrl.items()}
    out["rule"] = "SIMC PI, tau_c = theta" if p["tau_c"] is None else "SIMC PI, declared tau_c"
    cert = {"seed": p["seed"], "iae": m["iae"], "effort_tv": m["effort_tv"], "cost": m["cost"],
            "effort_weight": PID_EFFORT_WEIGHT, "overshoot": overshoot, "settling_time": settling,
            "max_abs_error": m["max_abs_error"], "longest_limit_run": m["longest_limit_run"],
            "closed_loop_spectral_radius": rho, "tau_c": tc, "delay_samples": p["delay"],
            "discretisation": "exact ZOH first-order lag, dead time rounded to whole samples",
            "anti_windup": "conditional integration (clamping)",
            "limits": "linear stability from the declared model only; plant-model mismatch is not covered"}
    return answer(out, cert)


def _pid_judge(p, ctrl):
    """Independent closed-loop replay (deque dead time); used by verify and score, never by solve."""
    K, dt, n = p["gain"], p["dt"], p["steps"]
    lag = math.exp(-dt / p["tau"])
    rng = random.Random(p["seed"])
    eps = [rng.gauss(0.0, p["noise_sd"]) for _ in range(n)]
    pipe = deque([p["u0"]] * p["delay"])
    lo, hi, u_prev = p["u_min"], p["u_max"], p["u0"]
    x = K * p["u0"]
    sched = list(p["schedule"])
    trace_y, trace_u, trace_r = [], [], []
    law = ctrl["law"]
    if law == "pid":
        g, ti, td, tf, wt = ctrl["kc"], ctrl["ti"], ctrl["td"], ctrl["tf"], ctrl["b"]
        filt_a = tf / (tf + dt) if td > 0 else 0.0
        filt_b = g * td / (tf + dt) if td > 0 else 0.0
        acc = p["u0"] - g * (wt * sched[0][1] - x)
        dstate, prev_meas = 0.0, x
    relay = p["u0"] >= 0.5 * (lo + hi)
    for k in range(n):
        now = k * dt
        ref = [v for t, v in sched if t <= now][-1]
        dist = p["load"] if now >= p["load_time"] else 0.0
        meas = x + eps[k]
        if law == "pid":
            err = ref - meas
            if td > 0:
                dstate = filt_a * dstate - filt_b * (meas - prev_meas)
            raw = g * (wt * ref - meas) + acc + dstate
            act = hi if raw > hi else lo if raw < lo else raw
            inc = g * dt / ti * err
            windup = (raw > hi and inc > 0) or (raw < lo and inc < 0)
            if not windup:
                acc += inc
            prev_meas = meas
        elif law == "on_off":
            err = (ref - meas) * (1.0 if K > 0 else -1.0)
            relay = True if err > ctrl["band"] else False if err < -ctrl["band"] else relay
            act = hi if relay else lo
        else:                                          # "hold": manual mode at the initial input
            act = p["u0"]
        trace_y.append(x)
        trace_u.append(act)
        trace_r.append(ref)
        pipe.append(act)
        x = lag * x + K * (1.0 - lag) * (pipe.popleft() + dist)
        u_prev = act
    iae = dt * sum(abs(r - y) for r, y in zip(trace_r, trace_y))
    tv = abs(trace_u[0] - p["u0"]) + sum(abs(trace_u[i] - trace_u[i - 1]) for i in range(1, n))
    longest, run = 0, 0
    for i, u in enumerate(trace_u):
        at = u >= hi or u <= lo
        same = i > 0 and at and trace_u[i - 1] == u
        run = run + 1 if same else (1 if at else 0)
        longest = max(longest, run)
    del u_prev
    return {"iae": iae, "effort_tv": tv, "cost": iae + PID_EFFORT_WEIGHT * abs(K) * dt * tv,
            "max_abs_error": max(abs(r - y) for r, y in zip(trace_r, trace_y)), "longest_limit_run": longest,
            "y": trace_y}


def _pid_eig_radius(p, ctrl):
    """Spectral radius from closed-loop state-space eigenvalues (independent of the polynomial route)."""
    import numpy as np
    dt, d = p["dt"], p["delay"]
    a = math.exp(-dt / p["tau"])
    bp = p["gain"] * (1 - a)
    kc, ki = ctrl["kc"], ctrl["kc"] * dt / ctrl["ti"]
    al = ctrl["tf"] / (ctrl["tf"] + dt) if ctrl["td"] > 0 else 0.0
    be = ctrl["kc"] * ctrl["td"] / (ctrl["tf"] + dt) if ctrl["td"] > 0 else 0.0
    # state: [y_k, y_{k-1}, I_k, D_{k-1}, u_{k-1}, ..., u_{k-d}]
    n = 4 + d
    u_row = np.zeros(n)
    u_row[0], u_row[1], u_row[2], u_row[3] = -kc - be, be, 1.0, al
    A = np.zeros((n, n))
    if d == 0:
        A[0] = bp * u_row
        A[0, 0] += a
    else:
        A[0, 0] = a
        A[0, 4 + d - 1] = bp
    A[1, 0] = 1.0
    A[2, 0], A[2, 2] = -ki, 1.0
    A[3, 0], A[3, 1], A[3, 3] = -be, be, al
    if d >= 1:
        A[4] = u_row
        for i in range(1, d):
            A[4 + i, 4 + i - 1] = 1.0
    return float(max(abs(np.linalg.eigvals(A))))


def pid_verify(data, output, certificate):
    p = _pid_inputs(data)
    ctrl = _pid_controller(output)
    sim = _pid_judge(p, ctrl)
    checks = {"iae_recomputed": math.isclose(sim["iae"], certificate.get("iae", math.nan), rel_tol=1e-6, abs_tol=1e-9),
              "effort_recomputed": math.isclose(sim["effort_tv"], certificate.get("effort_tv", math.nan),
                                                rel_tol=1e-6, abs_tol=1e-9),
              "cost_recomputed": math.isclose(sim["cost"], certificate.get("cost", math.nan), rel_tol=1e-6, abs_tol=1e-9),
              "seed_bound": certificate.get("seed") == p["seed"],
              "no_divergence": sim["max_abs_error"] <= PID_DIVERGE * _pid_span(p),
              "no_persistent_saturation": sim["longest_limit_run"] <= PID_SAT_FRACTION * p["steps"]}
    if ctrl["law"] == "pid":
        rho = _pid_eig_radius(p, ctrl)
        checks["linear_loop_stable"] = rho < 1.0
        checks["spectral_radius_recomputed"] = abs(rho - certificate.get("closed_loop_spectral_radius", math.nan)) <= 1e-5
    # overshoot of every step, recomputed from the replayed trace
    sched, dt, n, ys = p["schedule"], p["dt"], p["steps"], sim["y"]
    claimed = certificate.get("overshoot", [])
    ok = len(claimed) == len(sched) - 1
    for i, ((_, r0), (t1, r1)) in enumerate(zip(sched, sched[1:])):
        if not ok:
            break
        k1 = math.ceil(t1 / dt - 1e-12)
        stops = [t for t, _ in sched[i + 2:]] + ([p["load_time"]] if p["load"] != 0 and p["load_time"] > t1 else [])
        k2 = min([n] + [math.ceil(t / dt - 1e-12) for t in stops])
        if k1 >= n or k2 <= k1 or r1 == r0:
            ok = claimed[i] is None
            continue
        worst = max((y - r1) * (1 if r1 > r0 else -1) for y in ys[k1:k2])
        ok = isinstance(claimed[i], (int, float)) and abs(max(0.0, worst) / abs(r1 - r0) - claimed[i]) <= 1e-5
    checks["overshoot_recomputed"] = ok
    return checks


def pid_instance(seed):
    r = random.Random(seed)
    gain = r.uniform(0.5, 3.0)
    tau = r.uniform(2.0, 20.0)
    theta = tau * math.exp(r.uniform(math.log(0.05), math.log(2.0)))
    dt = (tau + theta) / 20.0
    theta = max(1, round(theta / dt)) * dt
    steps = 800
    horizon = steps * dt
    u0 = 1.0
    y0 = gain * u0
    s1 = r.uniform(0.5, 1.5)
    s2 = s1 - r.uniform(0.3, 1.0)
    load = r.choice((-1.0, 1.0)) * r.uniform(0.3, 0.8)
    data = {"gain": gain, "tau": tau, "theta": theta, "dt": dt, "steps": steps,
            "setpoints": [[0.0, y0], [0.05 * horizon, y0 + gain * s1], [0.35 * horizon, y0 + gain * s2]],
            "load": {"time": 0.65 * horizon, "magnitude": load}, "noise_sd": gain * r.uniform(0.002, 0.02),
            "u_min": -0.5, "u_max": 3.5, "u0": u0, "seed": r.randint(0, 2**31 - 1)}
    p = _pid_inputs(data)
    # Truth: exhaustive PI grid (rule-free scale) evaluated by the independent replay; normaliser only.
    kscale, tscale = tau / (gain * theta), tau + theta
    best = None
    for i in range(14):
        for j in range(10):
            ctrl = {"law": "pid", "kc": kscale * 2 ** (-4 + 5 * i / 13), "ti": tscale * 2 ** (-3 + 4 * j / 9),
                    "td": 0.0, "tf": 0.0, "b": 1.0}
            sim = _pid_judge(p, ctrl)
            if sim["max_abs_error"] > PID_DIVERGE * _pid_span(p) or sim["longest_limit_run"] > PID_SAT_FRACTION * steps:
                continue
            if _pid_eig_radius(p, ctrl) >= 1.0:
                continue
            if best is None or sim["cost"] < best[0]:
                best = (sim["cost"], ctrl["kc"], ctrl["ti"])
    hold = _pid_judge(p, {"law": "hold"})["cost"]
    ref = best[0] if best else hold
    return data, {"reference_cost": ref, "reference_gains": {"kc": best[1], "ti": best[2]} if best else None,
                  "hold_cost": hold}


def pid_score(data, truth, output):
    p = _pid_inputs(data)
    ref = truth["reference_cost"]
    fallback = -truth["hold_cost"] / ref
    if output is None:
        return {"quality": fallback, "category": "abstain"}
    try:
        ctrl = _pid_controller(output)
    except GenomeError:
        return _wrong(-1e6, fallback)
    sim = _pid_judge(p, ctrl)
    quality = -sim["cost"] / ref
    unstable = ctrl["law"] == "pid" and _pid_eig_radius(p, ctrl) >= 1.0
    if (unstable or sim["max_abs_error"] > PID_DIVERGE * _pid_span(p)
            or sim["longest_limit_run"] > PID_SAT_FRACTION * p["steps"]):
        return _wrong(quality, fallback)
    return {"quality": quality, "category": "correct"}


def pid_on_off(data):
    """Baseline: relay with a small hysteresis band (twice the noise sd)."""
    p = _pid_inputs(data)
    return {"law": "on_off", "band": max(2.0 * p["noise_sd"], 1e-3 * _pid_span(p))}


def pid_amigo(data):
    """Competitor: AMIGO PI (Astrom & Hagglund 2004), robust (Ms ~ 1.4) near-optimal load-rejection PI."""
    p = _pid_inputs(data)
    K, T, L = p["gain"], p["tau"], p["theta"]
    if L <= 0:
        return None
    kc = (0.15 + (0.35 - L * T / (L + T) ** 2) * T / L) / K
    ti = 0.35 * L + 13.0 * L * T * T / (T * T + 12.0 * L * T + 7.0 * L * L)
    return {"law": "pid", "kc": kc, "ti": ti, "td": 0.0, "tf": 0.0, "b": 1.0}


def pid_ziegler_nichols(data):
    """Alternative competitor (evaluated on dev, not selected): Ziegler-Nichols open-loop PI."""
    p = _pid_inputs(data)
    if p["theta"] <= 0:
        return None
    return {"law": "pid", "kc": 0.9 * p["tau"] / (p["gain"] * p["theta"]), "ti": 3.33 * p["theta"],
            "td": 0.0, "tf": 0.0, "b": 1.0}


def pid_subregion(data):
    ratio = data["theta"] / data["tau"]
    return "lag_dominant" if ratio < 0.3 else "balanced" if ratio <= 1.0 else "delay_dominant"


# ======================================================================== basal_kalman
KF_DIFFUSE_VEL_VAR = 1e6
KF_NIS_Z = 5.0           # two-sided innovation test at about 1e-6 per tail (Wilson-Hilferty)
KF_WRONG_RMSE = 3.0      # RMSE above 3 measurement sds is a gross estimation failure


def _kf_inputs(data):
    _dict(data)
    dt = finite(data.get("dt"), low=1e-6, high=1e6, name="dt")
    zs = data.get("measurements")
    if not isinstance(zs, list) or not 3 <= len(zs) <= 1000:
        raise GenomeError("measurements: 3-1000 entries (number or null)")
    zs = [None if z is None else finite(z, name="measurement") for z in zs]
    if all(z is None for z in zs):
        raise GenomeError("at least one measurement required")
    q = data.get("q")
    r = data.get("r")
    q = None if q is None else finite(q, low=0.0, high=1e12, name="q")
    r = None if r is None else finite(r, low=1e-12, high=1e12, name="r")
    prior = data.get("prior")
    if prior is not None:
        if not isinstance(prior, dict) or not isinstance(prior.get("mean"), list) or not isinstance(prior.get("var"), list) \
                or len(prior["mean"]) != 2 or len(prior["var"]) != 2:
            raise GenomeError("prior is {mean: [x, v], var: [px, pv]}")
        prior = ([finite(v, name="prior mean") for v in prior["mean"]],
                 [finite(v, low=1e-12, high=1e12, name="prior var") for v in prior["var"]])
    return dt, zs, q, r, prior


def _nis_bounds(n):
    if n == 0:
        return 0.0, 0.0
    c = 2.0 / (9.0 * n)
    lo = n * max(0.0, 1 - c - KF_NIS_Z * math.sqrt(c)) ** 3
    hi = n * (1 - c + KF_NIS_Z * math.sqrt(c)) ** 3
    return lo, hi


def _kf_scalar(dt, zs, q, r, prior):
    q11, q12, q22 = q * dt ** 4 / 4.0, q * dt ** 3 / 2.0, q * dt * dt
    if prior is not None:
        x, v = prior[0]
        p11, p12, p22 = prior[1][0], 0.0, prior[1][1]
        start = 0
    else:
        x, v, p11, p12, p22, start = zs[0], 0.0, r, 0.0, KF_DIFFUSE_VEL_VAR, 1
    est, nis, updates = [x] if start else [], 0.0, 0
    for k in range(start, len(zs)):
        if k > 0:
            x += dt * v
            p11, p12, p22 = p11 + 2 * dt * p12 + dt * dt * p22 + q11, p12 + dt * p22 + q12, p22 + q22
        z = zs[k]
        if z is not None:
            s = p11 + r
            k1, k2 = p11 / s, p12 / s
            innov = z - x
            x += k1 * innov
            v += k2 * innov
            p11, p12, p22 = (1 - k1) * p11, (1 - k1) * p12, p22 - k2 * p12
            nis += innov * innov / s
            updates += 1
        est.append(x)
    return est, v, p11, nis, updates, (k1, k2) if updates else (None, None)


def kalman_solve(data, budget):
    dt, zs, q, r, prior = _kf_inputs(data)
    missing = [name for name, val in (("process noise q", q), ("measurement noise r", r)) if val is None]
    if missing:
        return answer(None, {"reason": "noise statistics not declared"}, status="ABSTAIN",
                      missing=[f"{m} must be declared (known-noise Kalman filter)" for m in missing])
    if prior is None and zs[0] is None:
        return answer(None, {"reason": "no prior and no first measurement"}, status="ABSTAIN",
                      missing=["a prior {mean, var} or a first measurement is required to initialise"])
    est, v, p11, nis, updates, gain = _kf_scalar(dt, zs, q, r, prior)
    lo, hi = _nis_bounds(updates)
    cert = {"model": "1-D constant velocity, discrete white-noise acceleration", "q": q, "r": r,
            "initialisation": "declared prior" if prior is not None else "first measurement, diffuse velocity",
            "updates": updates, "nis_sum": nis, "nis_bounds": [lo, hi], "final_gain": list(gain)}
    if not lo <= nis <= hi:
        return answer(None, cert, status="ABSTAIN",
                      missing=["declared noise model rejected by the innovation (NIS) test"])
    return answer({"positions": est, "final_velocity": v, "final_position_variance": p11}, cert)


def kalman_verify(data, output, certificate):
    """Matrix (Joseph-form) recursion in numpy plus the innovation consistency test."""
    import numpy as np
    dt, zs, q, r, prior = _kf_inputs(data)
    F = np.array([[1.0, dt], [0.0, 1.0]])
    G = np.array([[dt * dt / 2.0], [dt]])
    Q = q * (G @ G.T)
    H = np.array([[1.0, 0.0]])
    if prior is not None:
        x = np.array([[prior[0][0]], [prior[0][1]]])
        P = np.diag(prior[1])
        first = 0
        est = []
    else:
        x = np.array([[zs[0]], [0.0]])
        P = np.diag([r, KF_DIFFUSE_VEL_VAR])
        first = 1
        est = [float(x[0, 0])]
    nis, m = 0.0, 0
    eye = np.eye(2)
    for k in range(first, len(zs)):
        if k > 0:
            x = F @ x
            P = F @ P @ F.T + Q
        if zs[k] is not None:
            S = float((H @ P @ H.T)[0, 0]) + r
            Kg = P @ H.T / S
            nu = zs[k] - float((H @ x)[0, 0])
            x = x + Kg * nu
            J = eye - Kg @ H
            P = J @ P @ J.T + r * (Kg @ Kg.T)
            nis += nu * nu / S
            m += 1
        est.append(float(x[0, 0]))
    got = output.get("positions") if isinstance(output, dict) else None
    scale = 1.0 + max(abs(e) for e in est)
    lo, hi = _nis_bounds(m)
    same = isinstance(got, list) and len(got) == len(est) and all(
        isinstance(g, (int, float)) and math.isfinite(g) and abs(g - e) <= 1e-6 * scale for g, e in zip(got, est))
    return {"estimates_recomputed": same,
            "final_variance_recomputed": math.isclose(output.get("final_position_variance", math.nan), float(P[0, 0]),
                                                      rel_tol=1e-6, abs_tol=1e-12),
            "innovation_consistent": lo <= nis <= hi,
            "nis_recomputed": math.isclose(certificate.get("nis_sum", math.nan), nis, rel_tol=1e-6, abs_tol=1e-9)}


def kalman_instance(seed):
    rnd = random.Random(seed)
    n = rnd.randint(100, 400)
    dt = rnd.uniform(0.1, 1.0)
    sa = math.exp(rnd.uniform(math.log(0.01), math.log(1.0)))
    sm = math.exp(rnd.uniform(math.log(0.1), math.log(5.0)))
    dropout = rnd.choice((0.0, 0.1))
    px, pv = 25.0, 4.0
    x, v = rnd.gauss(0.0, math.sqrt(px)), rnd.gauss(0.0, math.sqrt(pv))
    truth, zs = [], []
    for k in range(n):
        if k > 0:
            acc = rnd.gauss(0.0, sa)
            x, v = x + dt * v + 0.5 * dt * dt * acc, v + dt * acc
        truth.append(x)
        z = x + rnd.gauss(0.0, sm)
        zs.append(None if k > 0 and rnd.random() < dropout else z)
    return ({"dt": dt, "measurements": zs, "q": sa * sa, "r": sm * sm,
             "prior": {"mean": [0.0, 0.0], "var": [px, pv]}}, {"positions": truth, "dropout": dropout})


def _kf_hold(data):
    dt, zs, q, r, prior = _kf_inputs(data)
    last = prior[0][0] if prior is not None else next(z for z in zs if z is not None)
    out = []
    for z in zs:
        last = z if z is not None else last
        out.append(last)
    return out


def kalman_score(data, truth, output):
    r = data["r"]
    def rmse(est):
        return math.sqrt(sum((e - t) ** 2 for e, t in zip(est, truth["positions"])) / len(truth["positions"]))
    fallback = -rmse(_kf_hold(data)) / math.sqrt(r)
    if output is None:
        return {"quality": fallback, "category": "abstain"}
    est = output.get("positions") if isinstance(output, dict) else None
    if not isinstance(est, list) or len(est) != len(truth["positions"]) or not all(
            isinstance(e, (int, float)) and math.isfinite(e) for e in est):
        return _wrong(-1e6, fallback)
    err = rmse(est) / math.sqrt(r)
    if err > KF_WRONG_RMSE:
        return _wrong(-err, fallback)
    return {"quality": -err, "category": "correct"}


def kalman_last_measurement(data):
    """Baseline: the raw last measurement (held through dropouts)."""
    return {"positions": _kf_hold(data)}


def _ewma(zs, alpha, start):
    out, s = [], start
    for z in zs:
        if z is not None:
            s = alpha * z + (1 - alpha) * s
        out.append(s)
    return out


def kalman_ewma(data):
    """Competitor: EWMA whose alpha minimises one-step-ahead measurement prediction error on the first 20%."""
    dt, zs, q, r, prior = _kf_inputs(data)
    first = next(z for z in zs if z is not None)
    head = zs[:max(3, len(zs) // 5)]
    best = None
    for i in range(1, 51):
        alpha = i / 50.0
        s, sse = first, 0.0
        for z in head:
            if z is None:
                continue
            sse += (z - s) ** 2
            s = alpha * z + (1 - alpha) * s
        if best is None or sse < best[0]:
            best = (sse, alpha)
    return {"positions": _ewma(zs, best[1], first), "alpha": best[1]}


def kalman_alpha_beta(data):
    """Competitor: alpha-beta (Holt level + trend) filter; alpha and beta minimise one-step-ahead measurement
    prediction error on the first 20% (grid 0.05-1.0 x 0-1.0). Stronger than the level-only EWMA."""
    dt, zs, q, r, prior = _kf_inputs(data)
    first = next(z for z in zs if z is not None)
    head = zs[:max(3, len(zs) // 5)]

    def run(a, b, seq):
        lvl, tr, out, sse = first, 0.0, [], 0.0
        for z in seq:
            pred = lvl + tr
            if z is None:
                lvl = pred
            else:
                sse += (z - pred) ** 2
                new = a * z + (1 - a) * pred
                tr = b * (new - lvl) + (1 - b) * tr
                lvl = new
            out.append(lvl)
        return out, sse

    best = min((run(a / 20, b / 20, head)[1], a / 20, b / 20) for a in range(1, 21) for b in range(0, 21))
    return {"positions": run(best[1], best[2], zs)[0], "alpha": best[1], "beta": best[2]}


def kalman_subregion(data):
    return "dropouts" if any(z is None for z in data["measurements"]) else "complete"


# ======================================================================== basal_hysteresis
HY_W_FALSE = 5.0     # cost of one false switch, in samples of detection delay
HY_W_MISS = 50.0     # cost of a missed change; detection delay is capped here
HY_MAX_CONFIRM = 12


def _hy_inputs(data):
    _dict(data)
    sig = data.get("signal")
    if not isinstance(sig, list) or not 20 <= len(sig) <= 4000:
        raise GenomeError("signal: 20-4000 samples")
    sig = [finite(x, name="signal sample") for x in sig]
    levels = data.get("levels")
    if not isinstance(levels, list) or len(levels) != 2:
        raise GenomeError("levels: [low, high]")
    lo, hi = finite(levels[0], name="low level"), finite(levels[1], name="high level")
    if not hi > lo:
        raise GenomeError("high level must exceed low level")
    thr = finite(data.get("threshold", 0.5 * (lo + hi)), name="threshold")
    if not lo < thr < hi:
        raise GenomeError("threshold must lie between the levels")
    sigma = data.get("noise_sd")
    sigma = None if sigma is None else finite(sigma, low=1e-12, high=1e12, name="noise_sd")
    dwell = finite(data.get("mean_dwell", 100.0), low=1.0, high=1e7, name="mean_dwell")
    s0 = data.get("initial_state", 0)
    if s0 not in (0, 1) or isinstance(s0, bool):
        raise GenomeError("initial_state is 0 or 1")
    return sig, lo, hi, thr, sigma, dwell, s0


def _runs_delay(p, m):
    """Expected trials until m consecutive successes (probability p), minus one = delay in samples."""
    if p >= 1.0 - 1e-15:
        return m - 1.0
    if p <= 1e-300:
        return math.inf
    pm = p ** m
    if pm <= 1e-300:
        return math.inf
    return (1.0 - pm) / ((1.0 - p) * pm) - 1.0


def schmitt_design(lo, hi, thr, sigma, dwell):
    """Closed-form choice of hysteresis h and confirmation m under i.i.d. Gaussian noise."""
    d_lo, d_hi = thr - lo, hi - thr
    best = None
    for i in range(0, 41):
        h = i * min(d_lo, d_hi) / 40.0 * 1.5
        for m in range(1, HY_MAX_CONFIRM + 1):
            cost = 0.0
            for d_from, d_to in ((d_lo, d_hi), (d_hi, d_lo)):          # low->high and high->low changes
                p_det = _q((h - d_to) / sigma)
                p_false = _q((d_from + h) / sigma)
                delay = min(_runs_delay(p_det, m), HY_W_MISS)
                false_rate = (1.0 - p_false) * p_false ** m                # run initiations per sample
                cost += 0.5 * (delay + HY_W_FALSE * 2.0 * dwell * false_rate)
            if best is None or cost < best[0] - 1e-12:
                best = (cost, h, m)
    return best


def _schmitt_run(sig, upper, lower, m, s0):
    s, cnt, out, switches = s0, 0, [], []
    for k, x in enumerate(sig):
        beyond = x > upper if s == 0 else x < lower
        cnt = cnt + 1 if beyond else 0
        if cnt >= m:
            s, cnt = 1 - s, 0
            switches.append(k)
        out.append(s)
    return "".join("1" if b else "0" for b in out), switches


def hysteresis_solve(data, budget):
    sig, lo, hi, thr, sigma, dwell, s0 = _hy_inputs(data)
    if sigma is None:
        return answer(None, {"reason": "noise level not declared"}, status="ABSTAIN",
                      missing=["noise_sd must be declared to size the hysteresis band"])
    cost, h, m = schmitt_design(lo, hi, thr, sigma, dwell)
    if cost >= HY_W_MISS:
        return answer(None, {"expected_cost_per_change": cost}, status="ABSTAIN",
                      missing=["noise too large relative to the level separation for a memoryless switch: "
                               "filter or average first"])
    states, switches = _schmitt_run(sig, thr + h, thr - h, m, s0)
    return answer({"states": states, "switch_count": len(switches)},
                  {"upper": thr + h, "lower": thr - h, "hysteresis": h, "confirm": m,
                   "expected_cost_per_change": cost, "switch_indices": switches[:1000],
                   "weights": {"false_switch": HY_W_FALSE, "miss": HY_W_MISS},
                   "model": "i.i.d. Gaussian noise, geometric dwell; closed-form run-length design"})


def hysteresis_verify(data, output, certificate):
    """Replay: every recorded switch must be justified by m consecutive samples beyond the band, and no
    unrecorded switch may have been due."""
    sig, lo, hi, thr, sigma, dwell, s0 = _hy_inputs(data)
    states = output.get("states") if isinstance(output, dict) else None
    up, down, m = certificate.get("upper"), certificate.get("lower"), certificate.get("confirm")
    shape = (isinstance(states, str) and len(states) == len(sig) and set(states) <= {"0", "1"}
             and isinstance(m, int) and m >= 1 and isinstance(up, float) and isinstance(down, float))
    if not shape:
        return {"shape": False}
    justified, prev, streak = True, s0, 0
    for k, ch in enumerate(states):
        cur = int(ch)
        outside = sig[k] > up if prev == 0 else sig[k] < down
        streak = streak + 1 if outside else 0
        should_switch = streak >= m
        if (cur != prev) != should_switch:
            justified = False
            break
        if should_switch:
            streak = 0
        prev = cur
    return {"shape": True, "band_centered": abs((up + down) / 2 - thr) <= 1e-9 * (1 + abs(thr)) and up >= down,
            "switches_justified": justified,
            "switch_count": output.get("switch_count") == sum(1 for a, b in zip(str(s0) + states, states) if a != b)}


def _hy_signal(rnd, lo, hi, sigma, dwell, n, s0):
    truth, sig, s = [], [], s0
    while len(truth) < n:
        length = 20 + int(rnd.expovariate(1.0 / max(1.0, dwell - 20)))
        truth.extend([s] * length)
        s = 1 - s
    truth = truth[:n]
    sig = [(hi if t else lo) + rnd.gauss(0.0, sigma) for t in truth]
    return sig, truth


def hysteresis_instance(seed):
    rnd = random.Random(seed)
    lo = rnd.uniform(-1.0, 1.0)
    delta = rnd.uniform(0.5, 2.0)
    sigma = delta * math.exp(rnd.uniform(math.log(0.05), math.log(0.6)))
    dwell = rnd.randint(60, 200)
    s0 = rnd.randint(0, 1)
    sig, truth = _hy_signal(rnd, lo, lo + delta, sigma, dwell, 1500, s0)
    return ({"signal": sig, "levels": [lo, lo + delta], "threshold": lo + delta / 2, "noise_sd": sigma,
             "mean_dwell": float(dwell), "initial_state": s0},
            {"states": "".join(map(str, truth)),
             "changes": [k for k in range(1, len(truth)) if truth[k] != truth[k - 1]]})


def _hy_cost(states, truth_states, changes, s0):
    n = len(truth_states)
    detected = [k for k in range(n) if states[k] != (states[k - 1] if k else str(s0))]
    matched, total = set(), 0.0
    bounds = changes + [n]
    for j, c in enumerate(changes):
        target = truth_states[c]
        if (states[c - 1] if c else str(s0)) == target:
            continue                               # already in the new regime (an earlier switch, counted false)
        hit = next((k for k in detected if c <= k < bounds[j + 1] and states[k] == target), None)
        if hit is None:
            total += HY_W_MISS
        else:
            matched.add(hit)
            total += min(hit - c, HY_W_MISS)
    false = len(detected) - len(matched)
    disagreement = sum(1 for a, b in zip(states, truth_states) if a != b) / n
    return total + HY_W_FALSE * false, false, disagreement


def hysteresis_score(data, truth, output):
    changes = truth["changes"]
    n_changes = max(1, len(changes))
    s0 = data["initial_state"]
    hold = str(s0) * len(truth["states"])
    fallback = -_hy_cost(hold, truth["states"], changes, s0)[0] / n_changes
    if output is None:
        return {"quality": fallback, "category": "abstain"}
    states = output.get("states") if isinstance(output, dict) else None
    if not isinstance(states, str) or len(states) != len(truth["states"]) or not set(states) <= {"0", "1"}:
        return _wrong(-1e6, fallback)
    cost, false, disagreement = _hy_cost(states, truth["states"], changes, s0)
    quality = -cost / n_changes
    if false > len(changes) or disagreement > 0.25:
        return _wrong(quality, fallback)
    return {"quality": quality, "category": "correct"}


def hysteresis_single_threshold(data):
    """Baseline: one threshold, no hysteresis."""
    sig, lo, hi, thr, sigma, dwell, s0 = _hy_inputs(data)
    states = "".join("1" if x > thr else "0" for x in sig)
    return {"states": states}


def _median_states(sig, w, thr):
    out = []
    for k in range(len(sig)):
        win = sorted(sig[max(0, k - w + 1):k + 1])
        n = len(win)
        med = win[n // 2] if n % 2 else 0.5 * (win[n // 2 - 1] + win[n // 2])
        out.append("1" if med > thr else "0")
    return "".join(out)


def hysteresis_median(data):
    """Competitor: causal moving median + single threshold, window tuned by simulation of the declared model."""
    sig, lo, hi, thr, sigma, dwell, s0 = _hy_inputs(data)
    if sigma is None:
        return {"states": _median_states(sig, 9, thr), "window": 9}
    rnd = random.Random(7919)
    syn, truth = _hy_signal(rnd, lo, hi, sigma, dwell, 1500, 0)
    tstates = "".join(map(str, truth))
    changes = [k for k in range(1, len(truth)) if truth[k] != truth[k - 1]]
    best = None
    for w in range(1, 42, 2):
        c = _hy_cost(_median_states(syn, w, thr), tstates, changes, 0)[0]
        if best is None or c < best[0]:
            best = (c, w)
    return {"states": _median_states(sig, best[1], thr), "window": best[1]}


def hysteresis_subregion(data):
    return "low_noise" if data["noise_sd"] / (data["levels"][1] - data["levels"][0]) < 0.2 else "high_noise"


# ======================================================================== basal_bandit
BANDIT_WRONG_GAP = 0.1   # concentrating most pulls on an arm this far below the best is a false conclusion


def _bandit_inputs(data):
    _dict(data)
    tape = data.get("outcomes")
    if not isinstance(tape, list) or not 2 <= len(tape) <= 50:
        raise GenomeError("outcomes: 2-50 arm reward tapes")
    horizon = bounded_int(data.get("horizon"), low=1, high=1000, name="horizon")
    binary = True
    clean = []
    for arm in tape:
        if not isinstance(arm, list) or len(arm) != horizon:
            raise GenomeError("each arm tape holds exactly `horizon` rewards")
        vals = [finite(x, low=0.0, high=1.0, name="reward") for x in arm]
        binary = binary and all(x in (0.0, 1.0) for x in vals)
        clean.append([int(x) for x in vals] if binary else vals)
    seed = bounded_int(data.get("seed", 0), low=0, high=2**31 - 1, name="seed")
    stationary = data.get("stationary", True)
    if not isinstance(stationary, bool):
        raise GenomeError("stationary is a boolean")
    return clean, horizon, seed, binary, stationary


def _thompson(tape, horizon, seed):
    rng = random.Random(seed)
    k = len(tape)
    wins, losses, seq = [0] * k, [0] * k, []
    for _ in range(horizon):
        draws = [rng.betavariate(1 + wins[a], 1 + losses[a]) for a in range(k)]
        arm = max(range(k), key=lambda a: (draws[a], -a))
        x = tape[arm][wins[arm] + losses[arm]]
        wins[arm] += x
        losses[arm] += 1 - x
        seq.append(arm)
    return seq, wins, losses


def bandit_solve(data, budget):
    tape, horizon, seed, binary, stationary = _bandit_inputs(data)
    if not binary:
        return answer(None, {"reason": "non-binary rewards"}, status="ABSTAIN",
                      missing=["rewards are not Bernoulli: a bounded-reward or Gaussian bandit is required"])
    if not stationary:
        return answer(None, {"reason": "declared non-stationary"}, status="ABSTAIN",
                      missing=["arm means declared non-stationary: discounted or sliding-window sampling required"])
    seq, wins, losses = _thompson(tape, horizon, seed)
    counts = [wins[a] + losses[a] for a in range(len(tape))]
    means = [(1 + wins[a]) / (2 + counts[a]) for a in range(len(tape))]
    best = max(range(len(tape)), key=lambda a: (means[a], -a))
    return answer({"sequence": seq, "counts": counts, "total_reward": sum(wins), "recommended_arm": best},
                  {"seed": seed, "prior": [1, 1], "sampler": "random.Random(seed).betavariate, arms in index order",
                   "tie_break": "lowest index", "reward_model": "per-arm reward tape (i-th pull of arm a = tape[a][i])",
                   "posterior": [[1 + wins[a], 1 + losses[a]] for a in range(len(tape))],
                   "trace_digest": hashlib.sha256(",".join(map(str, seq)).encode()).hexdigest()})


def bandit_verify(data, output, certificate):
    """Independent replay of the declared sampler plus reward / count / posterior recomputation."""
    tape, horizon, seed, binary, stationary = _bandit_inputs(data)
    seq = output.get("sequence") if isinstance(output, dict) else None
    k = len(tape)
    if not isinstance(seq, list) or len(seq) != horizon or not all(isinstance(a, int) and 0 <= a < k for a in seq):
        return {"sequence_shape": False}
    pulls, reward = [0] * k, 0
    succ = [0] * k
    for a in seq:
        x = tape[a][pulls[a]]
        pulls[a] += 1
        succ[a] += x
        reward += x
    rng = random.Random(certificate.get("seed", -1))
    alpha, beta = [1] * k, [1] * k
    replay = []
    for _ in range(horizon):
        theta = [rng.betavariate(alpha[i], beta[i]) for i in range(k)]
        top = max(theta)
        pick = theta.index(top)
        replay.append(pick)
        got = tape[pick][alpha[pick] + beta[pick] - 2]
        alpha[pick] += got
        beta[pick] += 1 - got
    post_mean = [(1 + succ[a]) / (2 + pulls[a]) for a in range(k)]
    return {"sequence_shape": True, "counts_match": output.get("counts") == pulls,
            "reward_recomputed": output.get("total_reward") == reward,
            "seed_bound": certificate.get("seed") == seed,
            "sampler_replayed": replay == seq,
            "recommendation_is_posterior_argmax": output.get("recommended_arm") == post_mean.index(max(post_mean))}


def bandit_instance(seed):
    rnd = random.Random(seed)
    k = rnd.randint(2, 10)
    horizon = rnd.randint(400, 1000)
    means = [rnd.uniform(0.05, 0.95) for _ in range(k)]
    tape = [[1 if rnd.random() < mu else 0 for _ in range(horizon)] for mu in means]
    return {"outcomes": tape, "horizon": horizon, "seed": rnd.randint(0, 2**31 - 1)}, {"means": means}


def _regret(counts, means):
    top = max(means)
    return sum(n * (top - mu) for n, mu in zip(counts, means))


def bandit_score(data, truth, output):
    means = truth["means"]
    k, horizon = len(means), data["horizon"]
    robin = [horizon // k + (1 if a < horizon % k else 0) for a in range(k)]
    fallback = -_regret(robin, means)
    if output is None:
        return {"quality": fallback, "category": "abstain"}
    seq = output.get("sequence") if isinstance(output, dict) else None
    if not isinstance(seq, list) or len(seq) != horizon or not all(isinstance(a, int) and 0 <= a < k for a in seq):
        return _wrong(-1e6, fallback)
    counts = [seq.count(a) for a in range(k)]
    quality = -_regret(counts, means)
    most = max(range(k), key=lambda a: counts[a])
    if max(means) - means[most] >= BANDIT_WRONG_GAP:
        return _wrong(quality, fallback)
    return {"quality": quality, "category": "correct"}


def _empirical_policy(data, choose):
    tape, horizon, seed, binary, stationary = _bandit_inputs(data)
    k = len(tape)
    pulls, total, seq = [0] * k, [0.0] * k, []
    rng = random.Random(seed)
    for t in range(horizon):
        arm = t if t < k else choose(t, pulls, total, rng)
        x = tape[arm][pulls[arm]]
        pulls[arm] += 1
        total[arm] += x
        seq.append(arm)
    return {"sequence": seq, "counts": pulls}


def bandit_epsilon_greedy(data):
    """Baseline: each arm once, then epsilon-greedy with epsilon = 0.1."""
    def choose(t, pulls, total, rng):
        if rng.random() < 0.1:
            return rng.randrange(len(pulls))
        means = [total[a] / pulls[a] for a in range(len(pulls))]
        return means.index(max(means))
    return _empirical_policy(data, choose)


def bandit_ucb1(data):
    """Competitor: UCB1 (Auer, Cesa-Bianchi & Fischer 2002)."""
    def choose(t, pulls, total, rng):
        idx = [total[a] / pulls[a] + math.sqrt(2.0 * math.log(t) / pulls[a]) for a in range(len(pulls))]
        return idx.index(max(idx))
    return _empirical_policy(data, choose)


def _bernoulli_kl(p, q):
    p, q = min(max(p, 1e-12), 1 - 1e-12), min(max(q, 1e-12), 1 - 1e-12)
    return p * math.log(p / q) + (1 - p) * math.log((1 - p) / (1 - q))


def bandit_klucb(data):
    """Competitor: KL-UCB (Garivier & Cappe 2011), exploration log(t), index by 25-step bisection."""
    def choose(t, pulls, total, rng):
        bound, best, pick = math.log(t), -1.0, 0
        for a in range(len(pulls)):
            mu = total[a] / pulls[a]
            lo, hi = mu, 1.0
            for _ in range(25):
                mid = 0.5 * (lo + hi)
                if pulls[a] * _bernoulli_kl(mu, mid) <= bound:
                    lo = mid
                else:
                    hi = mid
            if lo > best + 1e-15:
                best, pick = lo, a
        return pick
    return _empirical_policy(data, choose)


def bandit_subregion(data):
    return "few_arms" if len(data["outcomes"]) <= 4 else "many_arms"


# ======================================================================== basal_breaker
CB_OUTAGE_CALL = 2.0       # cost of one call into an outage (timeout, load on a failing dependency)
CB_UNAVAILABLE = 0.5       # extra cost of refusing a request while the dependency is healthy
CB_WINDOW = 10             # trip test window (last W calls while closed)
CB_ALPHA = 1e-3            # trip when the window's failure count is this improbable under background failure
CB_WRONG_UNAVAILABLE = 0.25  # refusing more than this share of healthy-period requests = denial of service


def _cb_inputs(data):
    _dict(data)
    outcomes = data.get("outcomes")
    if not isinstance(outcomes, str) or not 10 <= len(outcomes) <= 20_000 or not set(outcomes) <= {"0", "1"}:
        raise GenomeError("outcomes: string of 10-20000 call results ('1' success, '0' failure)")
    p = data.get("background_failure")
    p = None if p is None else finite(p, low=0.0, high=1.0, name="background_failure")
    mean_outage = data.get("mean_outage")
    mean_outage = None if mean_outage is None else finite(mean_outage, low=1.0, high=1e7, name="mean_outage")
    costs = data.get("costs", {"outage_call": CB_OUTAGE_CALL, "unavailable": CB_UNAVAILABLE})
    if not isinstance(costs, dict):
        raise GenomeError("costs is {outage_call, unavailable}")
    c_out = finite(costs.get("outage_call", CB_OUTAGE_CALL), low=0.0, high=1e6, name="outage_call cost")
    c_un = finite(costs.get("unavailable", CB_UNAVAILABLE), low=0.0, high=1e6, name="unavailable cost")
    seed = bounded_int(data.get("seed", 0), low=0, high=2**31 - 1, name="seed")
    return outcomes, p, mean_outage, c_out, c_un, seed


def _binom_tail(n, f, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(f, n + 1))


def breaker_parameters(p, mean_outage, c_out, c_un):
    trip = next((f for f in range(1, CB_WINDOW + 1) if _binom_tail(CB_WINDOW, f, p) <= CB_ALPHA), CB_WINDOW)
    cooldown = int(min(500, max(1, round(math.sqrt(2.0 * c_out * mean_outage / (1.0 + c_un))))))
    return trip, cooldown


def _breaker_run(outcomes, trip, cooldown):
    state, window, reopen = "CLOSED", deque(maxlen=CB_WINDOW), 0
    decisions, transitions = [], []
    for t, res in enumerate(outcomes):
        if state == "OPEN" and t >= reopen:
            state = "HALF_OPEN"
            transitions.append([t, "OPEN", "HALF_OPEN"])
        if state == "OPEN":
            decisions.append("0")
            continue
        decisions.append("1")
        ok = res == "1"
        if state == "HALF_OPEN":
            if ok:
                state = "CLOSED"
                window.clear()
                transitions.append([t, "HALF_OPEN", "CLOSED"])
            else:
                state, reopen = "OPEN", t + 1 + cooldown
                transitions.append([t, "HALF_OPEN", "OPEN"])
            continue
        window.append(0 if ok else 1)
        if sum(window) >= trip:
            state, reopen = "OPEN", t + 1 + cooldown
            window.clear()
            transitions.append([t, "CLOSED", "OPEN"])
    return "".join(decisions), transitions


def breaker_solve(data, budget):
    outcomes, p, mean_outage, c_out, c_un, seed = _cb_inputs(data)
    missing = [m for m, v in (("background_failure", p), ("mean_outage", mean_outage)) if v is None]
    if missing:
        return answer(None, {"reason": "dependency profile not declared"}, status="ABSTAIN",
                      missing=[f"{m} must be declared to set the trip test and cooldown" for m in missing])
    if p >= 0.5:
        return answer(None, {"background_failure": p}, status="ABSTAIN",
                      missing=["background failure >= 0.5: a failure-rate trip cannot separate outages from normal "
                               "operation"])
    trip, cooldown = breaker_parameters(p, mean_outage, c_out, c_un)
    decisions, transitions = _breaker_run(outcomes, trip, cooldown)
    calls = decisions.count("1")
    return answer({"decisions": decisions, "calls": calls,
                   "params": {"window": CB_WINDOW, "trip_failures": trip, "cooldown": cooldown}},
                  {"transitions": transitions[:1000], "transition_count": len(transitions),
                   "trip_rule": f"open when >= {trip} of the last {CB_WINDOW} calls failed "
                                f"(binomial tail <= {CB_ALPHA} at p = {p:.4g})",
                   "cooldown_rule": "sqrt(2 * outage_call_cost * mean_outage / (1 + unavailable_cost))",
                   "half_open": "one probe call; success closes, failure re-opens",
                   "successes_observed": sum(1 for d, o in zip(decisions, outcomes) if d == "1" and o == "1")})


def breaker_verify(data, output, certificate):
    """Replay the FSM tick by tick from the decisions and the outcomes of *called* ticks only."""
    outcomes, p, mean_outage, c_out, c_un, seed = _cb_inputs(data)
    decisions = output.get("decisions") if isinstance(output, dict) else None
    params = output.get("params") if isinstance(output, dict) else None
    if not isinstance(decisions, str) or len(decisions) != len(outcomes) or not set(decisions) <= {"0", "1"} \
            or not isinstance(params, dict):
        return {"shape": False}
    trip, cool, win = params.get("trip_failures"), params.get("cooldown"), params.get("window")
    # declared-threshold check, recomputed from the binomial pmf by recursion
    pmf = [(1 - p) ** CB_WINDOW]
    for i in range(CB_WINDOW):
        pmf.append(pmf[-1] * (CB_WINDOW - i) / (i + 1) * (p / (1 - p)) if p < 1 else 0.0)
    tails = [sum(pmf[f:]) for f in range(CB_WINDOW + 1)]
    want_trip = next((f for f in range(1, CB_WINDOW + 1) if tails[f] <= CB_ALPHA * (1 + 1e-9)), CB_WINDOW)
    want_cool = int(min(500, max(1, round((2.0 * c_out * mean_outage / (1.0 + c_un)) ** 0.5))))
    mode, fails, opened_at, log, consistent = "closed", [], None, [], True
    for t, d in enumerate(decisions):
        if mode == "open" and t - opened_at > cool:
            mode = "half"
            log.append([t, "OPEN", "HALF_OPEN"])
        allowed = mode != "open"
        if (d == "1") != allowed:
            consistent = False
            break
        if d == "0":
            continue
        failed = outcomes[t] == "0"
        if mode == "half":
            if failed:
                mode, opened_at = "open", t
                log.append([t, "HALF_OPEN", "OPEN"])
            else:
                mode, fails = "closed", []
                log.append([t, "HALF_OPEN", "CLOSED"])
            continue
        fails = (fails + [1 if failed else 0])[-win:] if isinstance(win, int) and win > 0 else []
        if isinstance(trip, int) and sum(fails) >= trip:
            mode, opened_at, fails = "open", t, []
            log.append([t, "CLOSED", "OPEN"])
    return {"shape": True, "declared_thresholds": trip == want_trip and cool == want_cool and win == CB_WINDOW,
            "decisions_follow_fsm": consistent,
            "transitions_replayed": consistent and log[:1000] == certificate.get("transitions")
            and len(log) == certificate.get("transition_count"),
            "call_count": output.get("calls") == decisions.count("1")}


def breaker_instance(seed):
    rnd = random.Random(seed)
    n = 3000
    p = rnd.uniform(0.01, 0.08)
    mean_outage = rnd.uniform(10.0, 120.0)
    mean_up = rnd.uniform(150.0, 500.0)
    fail_out = rnd.uniform(0.85, 1.0)
    mask, up = [], True
    while len(mask) < n:
        length = max(3, int(rnd.expovariate(1.0 / (mean_up if up else mean_outage))))
        mask.extend([0 if up else 1] * length)
        up = not up
    mask = mask[:n]
    outcomes = "".join("0" if rnd.random() < (fail_out if m else p) else "1" for m in mask)
    return ({"outcomes": outcomes, "background_failure": p, "mean_outage": mean_outage,
             "costs": {"outage_call": CB_OUTAGE_CALL, "unavailable": CB_UNAVAILABLE}, "seed": rnd.randint(0, 2**31 - 1)},
            {"outage": "".join(map(str, mask))})


def _cb_value(decisions, outcomes, outage):
    up = outage.count("0")
    succ = sum(1 for d, o in zip(decisions, outcomes) if d == "1" and o == "1")
    out_calls = sum(1 for d, m in zip(decisions, outage) if d == "1" and m == "1")
    refused_up = sum(1 for d, m in zip(decisions, outage) if d == "0" and m == "0")
    return (succ - CB_OUTAGE_CALL * out_calls - CB_UNAVAILABLE * refused_up) / max(1, up), refused_up / max(1, up)


def breaker_score(data, truth, output):
    outcomes, outage = data["outcomes"], truth["outage"]
    fallback = _cb_value("1" * len(outcomes), outcomes, outage)[0]
    if output is None:
        return {"quality": fallback, "category": "abstain"}
    d = output.get("decisions") if isinstance(output, dict) else None
    if not isinstance(d, str) or len(d) != len(outcomes) or not set(d) <= {"0", "1"}:
        return _wrong(-1e6, fallback)
    quality, refused = _cb_value(d, outcomes, outage)
    if refused > CB_WRONG_UNAVAILABLE:
        return _wrong(quality, fallback)
    return {"quality": quality, "category": "correct"}


def breaker_always_retry(data):
    """Baseline: call every request immediately."""
    outcomes = _cb_inputs(data)[0]
    return {"decisions": "1" * len(outcomes)}


def breaker_backoff(data):
    """Competitor: exponential backoff with full jitter (base 1 tick, cap = twice the cost-balanced probe
    interval, so its saturated mean wait equals the breaker's cooldown)."""
    outcomes, p, mean_outage, c_out, c_un, seed = _cb_inputs(data)
    cap = 2.0 * breaker_parameters(p if p is not None else 0.05, mean_outage or 30.0, c_out, c_un)[1]
    rng = random.Random(seed)
    attempt, ready, out = 0, 0, []
    for t, res in enumerate(outcomes):
        if t < ready:
            out.append("0")
            continue
        out.append("1")
        if res == "1":
            attempt = 0
        else:
            attempt += 1
            ready = t + 1 + int(rng.uniform(0.0, min(cap, 2.0 ** attempt)))
    return {"decisions": "".join(out)}


def breaker_subregion(data):
    return "short_outages" if data["mean_outage"] < 40 else "long_outages"


# ======================================================================== genomes
def _genome(**kw):
    return IntelligenceGenome(layer=1, buildability="BUILDABLE_NOW", lineage=LINEAGE, version="1.0.0", **kw)


INTELLIGENCES = [
    Executable(
        genome=_genome(
            intelligence_id="basal.control.simc_pi", family="basal_pid", operation="pid_track",
            epistemic_class="physical",
            subgeometry="setpoint tracking and load rejection of a declared first-order-plus-dead-time plant",
            source_provenance="Skogestad (2003) SIMC rules; Astrom & Hagglund (2004) AMIGO; Ziegler & Nichols (1942)",
            native_representation="FOPDT model (K, tau, theta) + sample time + setpoint schedule + load step + "
                                  "noise sd + actuator limits + seed",
            required_inputs=("gain", "tau", "theta", "dt", "steps", "setpoints", "u_min", "u_max", "u0"),
            output_contract={"law": "pid", "kc": "float", "ti": "float", "td": "float", "tf": "float",
                             "b": "float", "rule": "str"},
            algorithm_or_runtime="SIMC PI (tau_c = theta) + exact-ZOH closed-loop simulation with conditional-"
                                 "integration anti-windup and seeded measurement noise",
            parameters={"tau_c": "theta unless declared", "effort_weight": PID_EFFORT_WEIGHT,
                        "persistent_saturation_fraction": PID_SAT_FRACTION},
            memory_model="stateless per call (controller state lives only inside the simulation)",
            learning_rule="none; competence settles per geometry from receipts",
            composition_inputs=("plant_model", "setpoints"), composition_outputs=("controller_gains",),
            evidence_type="control_trace",
            verification_method="independent deque-based closed-loop replay of the returned gains (IAE, effort, "
                                "overshoot) and state-space eigenvalue stability check",
            confidence_semantics="performance is a simulation of the declared model and seed; real plants differ "
                                 "by model error",
            resource_profile="O(steps) pure Python per simulation; numpy roots for the stability margin",
            latency_profile="milliseconds",
            known_strengths=("one-parameter robust tuning", "smooth actuator use under measurement noise",
                             "closed-form, auditable gains"),
            known_failure_modes=("gains are only as good as the FOPDT model", "PI only: no derivative action",
                                 "tau_c = theta trades some load-rejection speed for robustness"),
            counterindications=("integrating or unstable plants", "theta/tau > 10 (dead-time compensator needed)",
                                "strongly nonlinear plants"),
            abstention_conditions=("dead time below one sample without a declared tau_c", "theta/tau > 10",
                                   "a setpoint unreachable within the actuator limits"),
            benchmark_suite="seeded FOPDT plants, theta/tau 0.05-2, two setpoint steps + input load step + noise; "
                            "score -(IAE + effort)/grid-optimal PI cost; dev seeds 0-9, held-out 1000-1029",
            baseline="on-off relay with a hysteresis band of twice the noise sd",
            competitor="AMIGO PI (Astrom & Hagglund 2004); Ziegler-Nichols open-loop PI also run on dev"),
        solve=pid_solve, verify=pid_verify, instance=pid_instance, score=pid_score, baseline=pid_on_off,
        competitor=pid_amigo, subregion=pid_subregion, tolerance=1e-9,
        notes={"alternative_competitor": "pid_ziegler_nichols and Cohen-Coon PI were run on dev seeds: both go "
                                         "wrong (persistent saturation / instability) on lag-dominant one-sample-"
                                         "delay plants, so AMIGO is the declared strongest reasonable competitor"}),
    Executable(
        genome=_genome(
            intelligence_id="basal.estimate.kalman_cv", family="basal_kalman", operation="kalman_track",
            epistemic_class="physical", subgeometry="1-D position tracking with known Gaussian noise",
            source_provenance="Kalman (1960); Bar-Shalom, Li & Kirubarajan (2001) DWNA model and NIS test; "
                              "Holt (1957) / alpha-beta filter",
            native_representation="regularly sampled noisy positions (null = dropout) + q + r (+ prior)",
            required_inputs=("dt", "measurements", "q", "r"),
            output_contract={"positions": "[float]", "final_velocity": "float", "final_position_variance": "float"},
            algorithm_or_runtime="scalar-form constant-velocity Kalman recursion; chi-square innovation test",
            parameters={"nis_z": KF_NIS_Z, "diffuse_velocity_variance": KF_DIFFUSE_VEL_VAR},
            memory_model="two-state mean and 2x2 covariance", learning_rule="none (noise statistics are declared)",
            composition_inputs=("measurements", "noise_model"), composition_outputs=("positions", "velocity"),
            evidence_type="statistical_estimate",
            verification_method="independent numpy Joseph-form matrix recursion and normalised innovation squared "
                                "consistency bounds",
            confidence_semantics="minimum-mean-square-error under the declared linear-Gaussian model; the NIS test "
                                 "is the model check",
            resource_profile="O(n) scalar arithmetic", latency_profile="sub-millisecond to a few milliseconds",
            known_strengths=("optimal under the declared model", "bridges dropouts by prediction",
                             "self-checks its noise model"),
            known_failure_modes=("manoeuvres outside the white-acceleration model", "mis-declared noise (abstains)",
                                 "non-Gaussian outliers"),
            counterindications=("unknown noise statistics", "nonlinear dynamics or measurements", "heavy-tailed noise"),
            abstention_conditions=("q or r not declared", "no prior and no first measurement",
                                   "innovation test rejects the declared noise model"),
            benchmark_suite="seeded DWNA tracks, 100-400 samples, sd ratios over two decades, half with 10% "
                            "dropouts; score -RMSE / measurement sd; dev 0-9, held-out 1000-1029",
            baseline="raw last measurement (held through dropouts)",
            competitor="alpha-beta (Holt level + trend) filter with alpha, beta minimising one-step prediction "
                       "error on the first 20%"),
        solve=kalman_solve, verify=kalman_verify, instance=kalman_instance, score=kalman_score,
        baseline=kalman_last_measurement, competitor=kalman_alpha_beta, subregion=kalman_subregion, tolerance=1e-9,
        notes={"alternative_competitor": "kalman_ewma (level-only EWMA, alpha on the first 20%): the assigned "
                                         "competitor; weaker on dev (alpha collapses to 1 on most tracks), so the "
                                         "alpha-beta filter is the declared strongest reasonable competitor"}),
    Executable(
        genome=_genome(
            intelligence_id="basal.switch.schmitt_confirm", family="basal_hysteresis", operation="hysteresis_switch",
            epistemic_class="physical", subgeometry="two-regime detection in a noisy scalar signal",
            source_provenance="Schmitt (1938) trigger; run-length (debounce) confirmation; Gaussian tail design",
            native_representation="sampled signal + two declared levels + threshold + noise sd + mean dwell",
            required_inputs=("signal", "levels", "noise_sd"),
            output_contract={"states": "string of 0/1 per sample", "switch_count": "int"},
            algorithm_or_runtime="Schmitt band +/- h with m-sample confirmation; (h, m) minimise a closed-form "
                                 "expected cost under i.i.d. Gaussian noise",
            parameters={"false_switch_weight": HY_W_FALSE, "miss_weight": HY_W_MISS, "max_confirm": HY_MAX_CONFIRM},
            memory_model="one bit of state + one run counter", learning_rule="none",
            composition_inputs=("signal",), composition_outputs=("regime_states",),
            evidence_type="heuristic_trace",
            verification_method="replay: every switch justified by m consecutive samples beyond the band and no "
                                "due switch omitted",
            confidence_semantics="design is optimal only for the declared Gaussian i.i.d. model; the trace is an "
                                 "audit, not a proof of correct regimes",
            resource_profile="O(n) comparisons; design grid of 41 x 12 closed forms",
            latency_profile="sub-millisecond",
            known_strengths=("near-zero delay at low noise", "inspectable two-number design", "O(1) memory"),
            known_failure_modes=("correlated or heavy-tailed noise breaks the design formulas",
                                 "high noise: memoryless switching is dominated by filtering"),
            counterindications=("noise sd comparable to the level separation", "drifting levels"),
            abstention_conditions=("noise sd not declared", "expected cost per change >= the miss cost"),
            benchmark_suite="seeded two-level regime signals, noise/separation 0.05-0.6, dwell 60-200; score "
                            "-(capped delay + 5 x false switches + 50 x misses) per change; dev 0-9, held-out 1000-1029",
            baseline="single threshold at the midpoint",
            competitor="causal moving median (window tuned by simulating the declared model) + single threshold"),
        solve=hysteresis_solve, verify=hysteresis_verify, instance=hysteresis_instance, score=hysteresis_score,
        baseline=hysteresis_single_threshold, competitor=hysteresis_median, subregion=hysteresis_subregion,
        tolerance=1e-9),
    Executable(
        genome=_genome(
            intelligence_id="basal.allocate.thompson_bernoulli", family="basal_bandit", operation="bandit_allocate",
            epistemic_class="strategic", subgeometry="stationary Bernoulli multi-armed bandit, finite horizon",
            source_provenance="Thompson (1933); Agrawal & Goyal (2012) regret analysis; Garivier & Cappe (2011) "
                              "KL-UCB; Auer et al. (2002) UCB1",
            native_representation="K per-arm reward tapes (i-th pull of arm a reveals tape[a][i]) + horizon + seed",
            required_inputs=("outcomes", "horizon", "seed"),
            output_contract={"sequence": "[arm]", "counts": "[int]", "total_reward": "int", "recommended_arm": "int"},
            algorithm_or_runtime="Thompson sampling, Beta(1, 1) priors, seeded random.Random betavariate",
            parameters={"prior": [1, 1]}, memory_model="K Beta posteriors",
            learning_rule="conjugate Beta-Bernoulli update per pull",
            composition_inputs=("arms",), composition_outputs=("allocation", "posterior"),
            evidence_type="simulation",
            verification_method="independent replay of the declared sampler and recomputation of counts, reward "
                                "and the posterior-mean recommendation",
            confidence_semantics="randomised policy; regret is an outcome of one seeded run, not a bound",
            resource_profile="O(horizon x K) Beta draws", latency_profile="milliseconds",
            known_strengths=("asymptotically optimal regret for Bernoulli arms", "no tuning constant"),
            known_failure_modes=("non-stationary arms", "one run's regret has high variance at small horizons"),
            counterindications=("non-binary rewards", "drifting arm means", "adversarial rewards"),
            abstention_conditions=("rewards not in {0, 1}", "declared non-stationary"),
            benchmark_suite="seeded Bernoulli bandits, K 2-10, horizon 400-1000, means U(0.05, 0.95); score "
                            "-pseudo-regret; dev 0-9, held-out 1000-1029",
            baseline="epsilon-greedy (epsilon 0.1) after one pull per arm",
            competitor="KL-UCB (Garivier & Cappe 2011)"),
        solve=bandit_solve, verify=bandit_verify, instance=bandit_instance, score=bandit_score,
        baseline=bandit_epsilon_greedy, competitor=bandit_klucb, subregion=bandit_subregion, tolerance=1e-9,
        notes={"alternative_competitor": "bandit_ucb1: the assigned competitor; weaker than the epsilon-greedy "
                                         "baseline on dev (over-explores at these horizons), so KL-UCB is the "
                                         "declared strongest reasonable competitor"}),
    Executable(
        genome=_genome(
            intelligence_id="basal.protect.circuit_breaker", family="basal_breaker", operation="circuit_break",
            epistemic_class="strategic", subgeometry="protecting calls to a dependency with intermittent outages",
            source_provenance="Nygard (2007) circuit-breaker pattern; binomial tail trip test; AWS full-jitter "
                              "backoff (Brooker 2015)",
            native_representation="per-request call-result tape + declared background failure + mean outage + costs",
            required_inputs=("outcomes", "background_failure", "mean_outage"),
            output_contract={"decisions": "string of 1 (call) / 0 (fail fast) per request", "calls": "int",
                             "params": "{window, trip_failures, cooldown}"},
            algorithm_or_runtime="closed/open/half-open FSM; trip at the smallest window failure count with "
                                 "binomial tail <= 1e-3; cooldown sqrt(2 c_out L / (1 + c_unavail))",
            parameters={"window": CB_WINDOW, "alpha": CB_ALPHA, "outage_call_cost": CB_OUTAGE_CALL,
                        "unavailable_cost": CB_UNAVAILABLE},
            memory_model="FSM state + last W call results", learning_rule="none",
            composition_inputs=("call_results",), composition_outputs=("call_decisions",),
            evidence_type="heuristic_trace",
            verification_method="tick-by-tick FSM replay against the declared thresholds, using only results of "
                                "called ticks (non-anticipation)",
            confidence_semantics="value is measured on the supplied tape; parameters are optimal only for the "
                                 "declared rates",
            resource_profile="O(requests)", latency_profile="sub-millisecond",
            known_strengths=("stops hammering a failing dependency within a few calls", "ignores isolated failures",
                             "auditable transitions"),
            known_failure_modes=("brownouts can close the breaker on a lucky probe",
                                 "fixed cooldown is mis-sized when outage lengths differ from the declaration"),
            counterindications=("background failure >= 0.5", "dependencies whose failures are per-request, not "
                                "per-period"),
            abstention_conditions=("background failure or mean outage not declared", "background failure >= 0.5"),
            benchmark_suite="seeded up/outage alternations (mean outage 10-120, background failure 1-8%, outage "
                            "failure 85-100%), 3000 requests; score (successes - 2 x outage calls - 0.5 x healthy "
                            "refusals) / healthy ticks; dev 0-9, held-out 1000-1029",
            baseline="always call immediately",
            competitor="exponential backoff with full jitter (cap = twice the cost-balanced probe interval)"),
        solve=breaker_solve, verify=breaker_verify, instance=breaker_instance, score=breaker_score,
        baseline=breaker_always_retry, competitor=breaker_backoff, subregion=breaker_subregion, tolerance=1e-9),
]
