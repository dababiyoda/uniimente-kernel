"""IntelligenceGenome admission: native benchmarks for every executable operation-contract family.

Founder directive 2026-10-07, section 15: "native problem family -> simple baseline -> candidate method ->
strongest reasonable competing method -> held-out evaluation -> cost/latency normalization ->
falsification -> retain / niche-specialize / reject". The library gets stronger partly by killing useless
complexity.

Each benchmark generates items with ground truth (seeds 1001-1040, never used for tuning; every parameter
below is declared before the run) and calls the family's real solver (``greg.cognition.solvers.SOLVERS``,
the same code the bounded worker runs). Per item it scores the candidate, the simple baseline and, where
one exists, the strongest reasonable competitor; "better" is strictly better by the family's metric.

Status rule (frozen):
* REJECTED            the baseline is better on more items than the candidate, one-sided sign test p < 0.05;
* SUPERSEDED          the candidate beats the baseline (p < 0.05) but the competitor beats the candidate
                      (p < 0.05): acquire the competitor (Capability Genesis);
* DEFAULT_FOR_GEOMETRY the candidate beats the baseline (p < 0.05) and no competitor beats it (p < 0.05);
* EXPERIMENTAL        otherwise (no demonstrated difference).
Families that cannot be benchmarked here carry a structural status with the reason (ROUTE_ONLY,
NOT_RUN, ALIAS, SUPERSEDED_BY_CANONICAL_ORGAN, NOT_BENCHMARKED).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from greg.cognition.solvers import SOLVERS  # noqa: E402

SEEDS = range(1001, 1041)
GEOMETRY = {"compute_limit": 200000, "latency_limit": 10.0}
MANIFEST = HERE / "freeze-v1.json"
FROZEN_CODE = ["cortex/evaluation/genome_admission/run.py", "greg/cognition/solvers.py"]


def sign_test(wins, losses):
    n = wins + losses
    return 1.0 if n == 0 else sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def call(family, data):
    started = time.perf_counter()
    out = SOLVERS[family](data, GEOMETRY)
    return out, time.perf_counter() - started


# ------------------------------------------------------------------ benchmarks (lower metric = better unless noted)
def bench_probabilistic(seed):
    """Predict the next Bernoulli outcome from 1-8 observations. Metric: expected log loss under the true p."""
    r = random.Random(seed)
    p = r.betavariate(2, 2)
    n = r.randint(1, 8)
    s = sum(r.random() < p for _ in range(n))
    def loss(q):
        q = min(max(q, 1e-6), 1 - 1e-6)
        return -(p * math.log(q) + (1 - p) * math.log(1 - q))
    out, sec = call("probabilistic", {"alpha": 1, "beta": 1, "successes": s, "failures": n - s})
    return {"candidate": loss(out["output"]["mean"]), "baseline": loss(min(max(s / n, 0.02), 0.98)),
            "competitor": loss((s + 0.5) / (n + 1)), "seconds": sec,
            "names": ("Beta(1,1) posterior mean", "clipped MLE", "Jeffreys posterior mean")}


def bench_control(seed):
    """Hold a first-order plant at a set point. Metric: integrated absolute error over 120 steps."""
    r = random.Random(seed)
    a, b, target, umax, dt = r.uniform(.2, 1.0), r.uniform(.5, 2.0), r.uniform(1, 5), 10.0, .1
    noise = [r.gauss(0, .05) for _ in range(120)]
    def run(policy):
        x, state, iae = 0.0, {}, 0.0
        for t in range(120):
            u, state = policy(x, state)
            x += dt * (-a * x + b * u) + noise[t]
            iae += abs(target - x) * dt
        return iae
    def pid(x, state):
        out, _ = call("control", {"observed": x, "target": target, "dt": dt, "kp": 2.0, "ki": 1.0, "kd": 0.0,
                                  "correction_limit": umax, "state": state})
        return out["output"]["correction"], out["output"]["state"]
    def bang(x, state):
        return (umax if x < target else -umax), state
    def p_only(x, state):
        return max(-umax, min(umax, 2.0 * (target - x))), state
    started = time.perf_counter()
    cand = run(pid)
    return {"candidate": cand, "baseline": run(bang), "competitor": run(p_only),
            "seconds": time.perf_counter() - started, "names": ("PID kp=2 ki=1", "bang-bang", "P-only kp=2")}


def bench_micro(seed):
    """Thermostat: keep temperature near a set point without chattering the heater.
    Metric: heater switches, with a comfort constraint (an arm that leaves the comfort band for more than
    5% longer than the baseline is scored as worse)."""
    r = random.Random(seed)
    c, band, loss_rate, heat = r.uniform(18, 22), .3, r.uniform(.05, .15), r.uniform(.3, .6)
    noise = [r.gauss(0, .08) for _ in range(300)]
    def run(rule):
        x, on, switches, outside = c, False, 0, 0
        for t in range(300):
            new = rule(x, on)
            switches += new != on
            on = new
            x += (heat if on else 0) - loss_rate * (x - (c - 6)) / 6 + noise[t]
            outside += abs(x - c) > 2 * band
        return switches, outside / 300
    def micro(x, on):
        out, _ = call("micro", {"observed": x, "low": c - band, "high": c + band})
        state = out["output"]["state"]
        return True if state == "stimulate" else False if state == "inhibit" else on
    def reflex(x, on):
        return x < c
    def score(arm, base):
        return arm[0] + (1000 if arm[1] > base[1] + .05 else 0)
    base = run(reflex)
    started = time.perf_counter()
    cand = run(micro)
    return {"candidate": score(cand, base), "baseline": score(base, base), "competitor": None,
            "seconds": time.perf_counter() - started, "names": ("set-point band (micro)", "single-threshold reflex", None)}


def bench_pattern(seed):
    """Find injected outliers in a contaminated series. Metric: 1 - F1."""
    r = random.Random(seed)
    n, rate = 60, r.choice((.02, .05, .1, .15, .2))
    values = [r.gauss(0, 1) for _ in range(n)]
    truth = set(r.sample(range(n), max(1, round(rate * n))))
    for i in truth:
        values[i] += r.choice((-1, 1)) * r.uniform(6, 10)
    def f1(found):
        found = set(found)
        tp = len(found & truth)
        return 0.0 if tp == 0 else 2 * tp / (len(found) + len(truth))
    out, sec = call("pattern", {"observations": values, "threshold": 3})
    q = sorted(values)
    q1, q3 = q[n // 4], q[3 * n // 4]
    iqr = [i for i, v in enumerate(values) if v < q1 - 1.5 * (q3 - q1) or v > q3 + 1.5 * (q3 - q1)]
    med = statistics.median(values)
    mad = statistics.median(abs(v - med) for v in values) or 1e-9
    robust = [i for i, v in enumerate(values) if abs(v - med) / (1.4826 * mad) >= 3.5]
    return {"candidate": 1 - f1(out["output"]["anomalies"]), "baseline": 1 - f1(iqr), "competitor": 1 - f1(robust),
            "seconds": sec, "names": ("z-score threshold 3", "Tukey IQR fences", "median/MAD robust z 3.5")}


def bench_collective(seed):
    """Aggregate seven independent noisy binary judgments. Metric: -1 wrong, 0 no decision, +1 correct
    (lower metric = better is used, so the value is negated)."""
    r = random.Random(seed)
    truth = r.choice(("yes", "no"))
    acc = [r.uniform(.55, .75) for _ in range(7)]
    votes = [truth if r.random() < a else ("no" if truth == "yes" else "yes") for a in acc]
    out, sec = call("collective", {"observations": [{"observer_id": f"o{i}", "independence_group": f"g{i}",
                                                     "weight": 1, "choice": v} for i, v in enumerate(votes)],
                                   "minimum_independent": 3, "threshold": .7})
    def utility(choice):
        return 0 if choice is None else (1 if choice == truth else -1)
    majority = max(("yes", "no"), key=votes.count)
    best = votes[max(range(7), key=lambda i: acc[i])]
    return {"candidate": -utility(out["output"]["choice"]), "baseline": -utility(best),
            "competitor": -utility(majority), "seconds": sec,
            "names": ("quorum (threshold .7, abstains below)", "most accurate single observer", "simple majority")}


def bench_evolutionary(seed):
    """Minimise a declared quadratic. Metric: distance of the returned point's fitness from the true minimum."""
    r = random.Random(seed)
    dim = r.randint(2, 6)
    center = [r.uniform(-5, 5) for _ in range(dim)]
    out, sec = call("evolutionary", {"center": center, "bounds": [[-10, 10]] * dim, "generations": 10,
                                     "population": 8, "seed": seed})
    return {"candidate": out["output"]["fitness"], "baseline": 0.0, "competitor": None, "seconds": sec,
            "names": ("differential evolution", "analytic minimum (the declared centre)", None)}


def bench_simulation(seed):
    """Expected successes over a number of Bernoulli steps. Metric: absolute error of the mean."""
    r = random.Random(seed)
    p, steps = r.uniform(.05, .95), r.randint(5, 50)
    out, sec = call("simulation", {"seed": seed, "samples": 200, "steps": steps, "step_probability": p})
    return {"candidate": abs(out["output"]["mean"] - steps * p), "baseline": 0.0, "competitor": None,
            "seconds": sec, "names": ("Monte Carlo (200 samples)", "analytic steps x p", None)}


def bench_sequential(seed):
    """Finite-horizon MDP. Metric: negative expected return from state s0 under the true model."""
    r = random.Random(seed)
    states, actions, horizon = [f"s{i}" for i in range(5)], ["a", "b", "c"], 10
    transitions, rewards = {}, {}
    for s in states:
        transitions[s], rewards[s] = {}, {}
        for a in actions:
            w = [r.random() for _ in states]
            total = sum(w)
            transitions[s][a] = {t: x / total for t, x in zip(states, w)}
            rewards[s][a] = round(r.uniform(-1, 1), 3)
    out, sec = call("sequential", {"transitions": transitions, "rewards": rewards, "horizon": horizon})
    def greedy_value():
        values = dict.fromkeys(states, 0.0)
        for _ in range(horizon):
            values = {s: rewards[s][max(actions, key=lambda a: rewards[s][a])] + sum(
                p * values[t] for t, p in transitions[s][max(actions, key=lambda a: rewards[s][a])].items())
                for s in states}
        return values["s0"]
    return {"candidate": -out["output"]["values"]["s0"], "baseline": -greedy_value(), "competitor": None,
            "seconds": sec, "names": ("backward induction", "greedy one-step policy", None)}


def bench_information(seed):
    """Buy information or act now. Metric: negative expected net value of the decision."""
    r = random.Random(seed)
    k = r.randint(2, 4)
    w = [r.random() for _ in range(k)]
    probs = [x / sum(w) for x in w]
    probs[-1] = 1 - sum(probs[:-1])
    best = [round(r.uniform(0, 100), 2) for _ in range(k)]
    prior = round(max(sum(p * b for p, b in zip(probs, best)) - r.uniform(0, 30), 0), 2)
    cost = round(r.uniform(0, 25), 2)
    out, sec = call("information", {"posterior_scenarios": [{"probability": p, "best_value": b}
                                                            for p, b in zip(probs, best)],
                                    "prior_best_value": prior, "cost": cost})
    informed = sum(p * b for p, b in zip(probs, best)) - cost
    value = lambda acquire: informed if acquire else prior  # noqa: E731
    return {"candidate": -value(out["output"]["acquire"]), "baseline": -value(False), "competitor": -value(True),
            "seconds": sec, "names": ("value-of-information rule", "never acquire", "always acquire")}


def bench_game(seed):
    """Two-player zero-sum matrix game. Metric: negative guaranteed value of the row strategy."""
    r = random.Random(seed)
    m, n = r.randint(2, 6), r.randint(2, 6)
    a = [[round(r.uniform(-5, 5), 2) for _ in range(n)] for _ in range(m)]
    out, sec = call("game", {"payoffs": a})
    def guarantee(x):
        return min(sum(x[i] * a[i][j] for i in range(m)) for j in range(n))
    uniform = [1 / m] * m
    pure = max(range(m), key=lambda i: min(a[i]))
    return {"candidate": -guarantee(out["output"]["mixed_strategy"]), "baseline": -guarantee(uniform),
            "competitor": -min(a[pure]), "seconds": sec, "names": ("minimax LP", "uniform mix", "pure maximin")}


def bench_graph(seed):
    """Weighted shortest path. Metric: path cost (unreachable = infinite, scored as worse)."""
    r = random.Random(seed)
    nodes = [f"n{i}" for i in range(12)]
    edges = [[u, v, round(r.uniform(1, 20), 2)] for u in nodes for v in nodes if u != v and r.random() < .2]
    out, sec = call("graph", {"edges": edges, "start": "n0", "goal": "n11"})
    from collections import deque
    adj = {}
    for u, v, w in edges:
        adj.setdefault(u, []).append((v, w))
    prev, seen, queue = {}, {"n0"}, deque(["n0"])
    while queue:
        u = queue.popleft()
        for v, _ in adj.get(u, []):
            if v not in seen:
                seen.add(v)
                prev[v] = u
                queue.append(v)
    def cost_of(path):
        if not path:
            return math.inf
        weights = {(u, v): min(w for a, b, w in edges if (a, b) == (u, v)) for u, v in zip(path, path[1:])}
        return sum(weights.values())
    bfs = []
    if "n11" in seen:
        node = "n11"
        while node != "n0":
            bfs.append(node)
            node = prev[node]
        bfs = ["n0"] + bfs[::-1]
    cand = out["output"]["cost"] if out["output"]["reachable"] else math.inf
    return {"candidate": cand, "baseline": cost_of(bfs), "competitor": None, "seconds": sec,
            "names": ("Dijkstra (networkx)", "fewest-hops BFS path", None)}


def bench_exact(seed):
    """Rational arithmetic. Metric: 0 if the result equals the exact rational value, else 1."""
    from fractions import Fraction
    r = random.Random(seed)
    terms = [(r.randint(1, 9), r.randint(2, 30)) for _ in range(r.randint(3, 6))]
    expr = " + ".join(f"{a}/{b}" for a, b in terms)
    truth = sum(Fraction(a, b) for a, b in terms)
    out, sec = call("exact", {"expression": expr})
    float_value = eval(expr)  # noqa: S307 - generated numeric literals only
    return {"candidate": 0 if Fraction(out["output"]["exact"]) == truth else 1,
            "baseline": 0 if Fraction(float_value) == truth else 1, "competitor": None, "seconds": sec,
            "names": ("exact rational arithmetic", "binary floating point", None)}


BENCHMARKS = {"probabilistic": bench_probabilistic, "control": bench_control, "micro": bench_micro,
              "pattern": bench_pattern, "collective": bench_collective, "evolutionary": bench_evolutionary,
              "simulation": bench_simulation, "sequential": bench_sequential, "information": bench_information,
              "game": bench_game, "graph": bench_graph, "exact": bench_exact}
STRUCTURAL = {
    "search": ("ALIAS", "same solver as graph (SOLVERS['search'] is graph)"),
    "estimation": ("SUPERSEDED_BY_CANONICAL_ORGAN", "cortex.estimation.fermi (P6 F1 evidence) is canonical"),
    "formal": ("SUPERSEDED_BY_CANONICAL_ORGAN", "cortex.formal.z3 behind the 0.2.1 route policy (P4 evidence)"),
    "optimization": ("SUPERSEDED_BY_CANONICAL_ORGAN", "cortex.optimization.cpsat behind the 0.2.1 route policy"),
    "causal": ("NOT_BENCHMARKED", "randomized two-arm estimate equals the naive difference by construction; the "
                                  "observational case belongs to cortex.evidence_causal (P6 F2 evidence)"),
    "semantic": ("NOT_RUN", "no founder-selected local model in this container"),
    "human": ("ROUTE_ONLY", "records a panel and returns HUMAN_REVIEW_REQUIRED; not machine-benchmarkable"),
    "evidence": ("NOT_BENCHMARKED", "evidence binding; no native ground-truth suite yet"),
    "protection": ("NOT_BENCHMARKED", "victim-protection review; no native ground-truth suite yet"),
}


def status(rows):
    def compare(a, b):
        wins = sum(1 for r in rows if r[a] is not None and r[b] is not None and r[a] < r[b] - 1e-9)
        losses = sum(1 for r in rows if r[a] is not None and r[b] is not None and r[b] < r[a] - 1e-9)
        return wins, losses
    w, l = compare("candidate", "baseline")
    out = {"vs_baseline": {"wins": w, "losses": l, "p_better": round(sign_test(w, l), 6),
                           "p_worse": round(sign_test(l, w), 6)}}
    has_comp = any(r["competitor"] is not None for r in rows)
    if has_comp:
        cw, cl = compare("candidate", "competitor")
        out["vs_competitor"] = {"wins": cw, "losses": cl, "p_better": round(sign_test(cw, cl), 6),
                                "p_worse": round(sign_test(cl, cw), 6)}
    if sign_test(l, w) < .05:
        verdict = "REJECTED"
    elif sign_test(w, l) < .05:
        verdict = "SUPERSEDED" if has_comp and out["vs_competitor"]["p_worse"] < .05 else "DEFAULT_FOR_GEOMETRY"
    else:
        verdict = "EXPERIMENTAL"
    out["status"] = verdict
    return out


def inputs():
    return {"code": {p: "sha256:" + hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in FROZEN_CODE},
            "seeds": [SEEDS.start, SEEDS.stop - 1], "families": sorted(BENCHMARKS),
            "structural": {k: v[0] for k, v in STRUCTURAL.items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if args.freeze:
        if MANIFEST.exists():
            raise SystemExit("refusing to overwrite an existing freeze; create a new version")
        MANIFEST.write_text(json.dumps({"frozen_at": datetime.now(timezone.utc).isoformat(), "inputs": inputs()},
                                       indent=2) + "\n")
        return
    if json.loads(MANIFEST.read_text())["inputs"] != inputs():
        raise SystemExit("FROZEN_INPUT_CHANGED: results cannot be reported")
    families = {}
    for family, bench in BENCHMARKS.items():
        rows = [bench(seed) for seed in SEEDS]
        names = rows[0]["names"]
        clean = [{k: (None if v is not None and isinstance(v, float) and math.isinf(v) and False else v)
                  for k, v in r.items() if k != "names"} for r in rows]
        families[family] = {"candidate": names[0], "baseline": names[1], "competitor": names[2], "n": len(rows),
                            **status(clean),
                            "mean_metric": {k: (round(statistics.fmean(r[k] for r in rows if r[k] is not None
                                                                          and math.isfinite(r[k])), 6)
                                                if any(r[k] is not None for r in rows) else None)
                                            for k in ("candidate", "baseline", "competitor")},
                            "median_seconds": round(statistics.median(r["seconds"] for r in rows), 5)}
    for family, (verdict, why) in STRUCTURAL.items():
        families[family] = {"status": verdict, "reason": why}
    report = {"schema": "greg-genome-admission/1", "manifest_sha256": "sha256:" + hashlib.sha256(
        MANIFEST.read_bytes()).hexdigest(), "finished_at": datetime.now(timezone.utc).isoformat(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "families": families}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({f: (v["status"], v.get("vs_baseline"), v.get("vs_competitor")) for f, v in families.items()},
                     indent=1))


if __name__ == "__main__":
    main()
