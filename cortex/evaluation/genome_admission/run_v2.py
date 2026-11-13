"""IntelligenceGenome admission v2: native benchmarks for the Layer 1/2/4 repertoire (greg/cognition/repertoire.py).

Same frozen status rule as v1 (``run.status``); fresh seeds 2001-2040; every parameter below is declared
before the run and none was tuned on benchmark data. Per family:

* ``robust_pattern`` (median/MAD modified z, 3.5). Native geometry: a univariate series with injected
  outliers; v1's generator, with Student-t(3) bulk noise on even seeds (heavy tails). Baseline: Tukey IQR
  fences. Competitor: Rosner's generalized ESD (alpha .05, up to 25 % outliers), the strongest classical
  test for this geometry. Metric 1 - F1. Reference only: the old population z-score (threshold 3).
* ``crowd`` (Dawid-Skene). Native geometry: 40-120 items, 2-4 classes, 5-9 observers, each an expert
  (accuracy U(.8,.95)), average (U(1/k+.1, 1/k+.3)) or spammer (uniform labels) with probabilities .3/.5/.2,
  each labelling every item with probability U(.4, 1). Metric: item error rate. Baseline: majority vote.
  Competitor: one-step agreement-weighted vote (accuracy estimated from agreement with the majority,
  Nitzan-Paroush log-odds weights) - acquirable without ground truth. Reference only (not in the rule):
  the oracle vote weighted by the true accuracies, which no deployed method can know.
* ``swarm`` (PSO, 20 particles, constriction) and ``blackbox`` (DE, population 10). Native geometry:
  a menu objective (sphere, rastrigin, ackley, rosenbrock, griewank), 2-8 dimensions, bounds [-5, 5],
  optimum shifted U(-2, 2), 2000 evaluations. Metric: best fitness found. Baseline: uniform random search.
  Competitor: swarm vs DE (what GREG already has); blackbox vs multistart L-BFGS-B (finite-difference
  gradients; every evaluation counted against the same budget).
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

from cortex.evaluation.genome_admission import run as V1  # noqa: E402
from greg.cognition.repertoire import objective  # noqa: E402
from greg.cognition.solvers import SOLVERS  # noqa: E402

SEEDS = range(2001, 2041)
GEOMETRY = {"compute_limit": 100000, "latency_limit": 10.0}
MANIFEST = HERE / "freeze-v2.json"
FROZEN_CODE = ["cortex/evaluation/genome_admission/run_v2.py", "cortex/evaluation/genome_admission/run.py",
               "greg/cognition/repertoire.py", "greg/cognition/solvers.py"]
BUDGET = 2000


def call(family, data):
    started = time.perf_counter()
    out = SOLVERS[family](data, GEOMETRY)
    return out, time.perf_counter() - started


def f1(found, truth):
    found = set(found)
    tp = len(found & truth)
    return 0.0 if tp == 0 else 2 * tp / (len(found) + len(truth))


def generalized_esd(values, alpha=0.05, max_fraction=0.25):
    from scipy.stats import t as student
    n, work, removed = len(values), list(enumerate(values)), []
    count = 0
    for i in range(1, int(max_fraction * n) + 1):
        mean = statistics.fmean(v for _, v in work)
        sd = statistics.stdev(v for _, v in work)
        if sd == 0:
            break
        j, (index, value) = max(enumerate(work), key=lambda e: abs(e[1][1] - mean))
        r = abs(value - mean) / sd
        p = 1 - alpha / (2 * (n - i + 1))
        tq = student.ppf(p, n - i - 1)
        lam = (n - i) * tq / math.sqrt((n - i - 1 + tq ** 2) * (n - i + 1))
        removed.append(index)
        del work[j]
        if r > lam:
            count = i
    return removed[:count]


def bench_robust_pattern(seed):
    r = random.Random(seed)
    n, rate = 60, r.choice((.02, .05, .1, .15, .2))
    if seed % 2 == 0:
        values = [r.gauss(0, 1) / math.sqrt(sum(r.gauss(0, 1) ** 2 for _ in range(3)) / 3) for _ in range(n)]
    else:
        values = [r.gauss(0, 1) for _ in range(n)]
    truth = set(r.sample(range(n), max(1, round(rate * n))))
    for i in truth:
        values[i] += r.choice((-1, 1)) * r.uniform(6, 10)
    out, sec = call("robust_pattern", {"observations": values})
    q = sorted(values)
    q1, q3 = q[n // 4], q[3 * n // 4]
    iqr = [i for i, v in enumerate(values) if v < q1 - 1.5 * (q3 - q1) or v > q3 + 1.5 * (q3 - q1)]
    old, _ = call("pattern", {"observations": values, "threshold": 3})
    return {"candidate": 1 - f1(out["output"]["anomalies"], truth), "baseline": 1 - f1(iqr, truth),
            "competitor": 1 - f1(generalized_esd(values), truth),
            "reference": 1 - f1(old["output"]["anomalies"], truth), "seconds": sec,
            "names": ("median/MAD modified z 3.5", "Tukey IQR fences", "generalized ESD (Rosner)",
                      "population z-score 3 (v1 family)")}


def _weighted(votes, weights, k):
    score = [0.0] * k
    for observer, label in votes.items():
        score[label] += weights.get(observer, 0.0)
    return max(range(k), key=lambda c: (score[c], -c))


def bench_crowd(seed):
    r = random.Random(seed)
    k, n, m = r.choice((2, 3, 4)), r.randint(40, 120), r.randint(5, 9)
    prior = [r.random() + .2 for _ in range(k)]
    truth = [r.choices(range(k), prior)[0] for _ in range(n)]
    kinds = [r.choices(("expert", "average", "spammer"), (.3, .5, .2))[0] for _ in range(m)]
    acc = [r.uniform(.8, .95) if t == "expert" else r.uniform(1 / k + .1, 1 / k + .3) if t == "average" else 1 / k
           for t in kinds]
    cover = [r.uniform(.4, 1) for _ in range(m)]
    votes = [dict() for _ in range(n)]
    for i in range(n):
        for j in range(m):
            if r.random() < cover[j]:
                if kinds[j] == "spammer":
                    votes[i][j] = r.randrange(k)
                else:
                    votes[i][j] = truth[i] if r.random() < acc[j] else r.choice([c for c in range(k) if c != truth[i]])
        if not votes[i]:
            j = r.randrange(m)
            votes[i][j] = truth[i] if r.random() < acc[j] else r.randrange(k)
    classes = [f"c{c}" for c in range(k)]
    data = {"classes": classes, "labels": [{"item_id": f"i{i}", "observer_id": f"o{j}", "independence_group": f"o{j}",
                                            "label": classes[label]} for i in range(n) for j, label in votes[i].items()]}
    out, sec = call("crowd", data)
    ds = [classes.index(out["output"]["labels"][f"i{i}"]) for i in range(n)]
    majority = [_weighted(v, {j: 1.0 for j in range(m)}, k) for v in votes]
    agree = {j: (sum(1 for i in range(n) if j in votes[i] and votes[i][j] == majority[i]) + 1) /
                (sum(1 for i in range(n) if j in votes[i]) + 2) for j in range(m)}
    def logodds(a):
        a = min(max(a, 1e-3), 1 - 1e-3)
        return max(0.0, math.log((k - 1) * a / (1 - a)))
    one_step = [_weighted(v, {j: logodds(agree[j]) for j in range(m)}, k) for v in votes]
    oracle = [_weighted(v, {j: logodds(acc[j]) for j in range(m)}, k) for v in votes]
    def error(labels):
        return sum(1 for a, b in zip(labels, truth) if a != b) / n
    return {"candidate": error(ds), "baseline": error(majority), "competitor": error(one_step),
            "reference": error(oracle), "seconds": sec,
            "names": ("Dawid-Skene EM", "majority vote", "one-step agreement-weighted vote",
                      "oracle true-accuracy weighted vote (not deployable)")}


def _problem(seed):
    r = random.Random(seed)
    dim = r.randint(2, 8)
    return {"function": r.choice(("sphere", "rastrigin", "ackley", "rosenbrock", "griewank")),
            "shift": [r.uniform(-2, 2) for _ in range(dim)], "bounds": [[-5, 5]] * dim, "budget": BUDGET,
            "seed": seed}


def random_search(data):
    f, bounds, budget = objective(data)
    r = random.Random(data["seed"] + 7)
    return min(f([r.uniform(lo, hi) for lo, hi in bounds]) for _ in range(budget))


def multistart_lbfgsb(data):
    from scipy.optimize import minimize
    f, bounds, budget = objective(data)
    r = random.Random(data["seed"] + 11)
    state = {"used": 0, "best": math.inf}

    class Spent(Exception):
        pass

    def counted(x):
        if state["used"] >= budget:
            raise Spent
        state["used"] += 1
        y = f(list(x))
        state["best"] = min(state["best"], y)
        return y
    while state["used"] < budget:
        try:
            minimize(counted, [r.uniform(lo, hi) for lo, hi in bounds], method="L-BFGS-B", bounds=bounds)
        except Spent:
            break
    return state["best"]


def bench_swarm(seed):
    data = _problem(seed)
    out, sec = call("swarm", data)
    de, _ = call("blackbox", data)
    return {"candidate": out["output"]["fitness"], "baseline": random_search(data),
            "competitor": de["output"]["fitness"], "reference": None, "seconds": sec,
            "names": ("particle swarm", "random search", "differential evolution (GREG blackbox)", None)}


def bench_blackbox(seed):
    data = _problem(seed)
    out, sec = call("blackbox", data)
    return {"candidate": out["output"]["fitness"], "baseline": random_search(data),
            "competitor": multistart_lbfgsb(data), "reference": None, "seconds": sec,
            "names": ("differential evolution", "random search", "multistart L-BFGS-B", None)}


BENCHMARKS = {"robust_pattern": bench_robust_pattern, "crowd": bench_crowd, "swarm": bench_swarm,
              "blackbox": bench_blackbox}


def inputs():
    return {"code": {p: "sha256:" + hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in FROZEN_CODE},
            "seeds": [SEEDS.start, SEEDS.stop - 1], "families": sorted(BENCHMARKS), "budget": BUDGET}


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
        status = V1.status([{k: v for k, v in r.items() if k in ("candidate", "baseline", "competitor")} for r in rows])
        reference = None
        if names[3]:
            w = sum(1 for r in rows if r["candidate"] < r["reference"] - 1e-9)
            l = sum(1 for r in rows if r["reference"] < r["candidate"] - 1e-9)
            reference = {"name": names[3], "wins": w, "losses": l, "mean": round(statistics.fmean(
                r["reference"] for r in rows), 6)}
        families[family] = {"candidate": names[0], "baseline": names[1], "competitor": names[2], "n": len(rows),
                            **status, "reference_not_in_rule": reference,
                            "mean_metric": {k: round(statistics.fmean(r[k] for r in rows), 6)
                                            for k in ("candidate", "baseline", "competitor")},
                            "median_metric": {k: round(statistics.median(r[k] for r in rows), 6)
                                              for k in ("candidate", "baseline", "competitor")},
                            "median_seconds": round(statistics.median(r["seconds"] for r in rows), 5),
                            "per_item": [{k: (round(v, 9) if isinstance(v, float) else v) for k, v in r.items()
                                          if k != "names"} for r in rows]}
    report = {"schema": "greg-genome-admission/2", "manifest_sha256": "sha256:" + hashlib.sha256(
        MANIFEST.read_bytes()).hexdigest(), "finished_at": datetime.now(timezone.utc).isoformat(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "families": families}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({f: (v["status"], v["vs_baseline"], v.get("vs_competitor"), v["reference_not_in_rule"])
                      for f, v in families.items()}, indent=1))


if __name__ == "__main__":
    main()
