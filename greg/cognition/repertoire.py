"""Layer 1 and Layer 2 mechanisms admitted only through native benchmarks (founder directive 2026-10-07).

* ``robust_anomalies`` (Layer 1): median/MAD modified z-score (Iglewicz and Hoaglin 1993). The genome
  admission run of 2026-10-14 REJECTED the population z-score on contaminated series and named this
  method as the acquisition target (z-score lost 1/24 to it).
* ``crowd_label`` (Layer 2, collective): Dawid-Skene expectation-maximisation (Dawid and Skene 1979). Many
  observers label many items; the method learns each observer's confusion matrix from agreement alone, so
  reliable observers count more and noise or spam counts less, without ground truth. Correlated observers
  (one ``independence_group``) count as one voter: their per-item plurality.
* ``swarm_minimize`` (Layer 2, swarm): particle swarm optimisation with Clerc-Kennedy constriction on a
  declared black-box objective, under a hard evaluation budget.
* ``evolve_blackbox`` (Layer 4, evolutionary search): SciPy differential evolution on the same declared
  objective and budget. The admission run REJECTED DE on a quadratic, whose minimum is closed-form; this
  is DE on its native geometry (multimodal, derivative-free).

Objectives are chosen from a fixed menu (``OBJECTIVES``) with a declared shift; no input becomes code.
Every parameter here was fixed before any admission run; none was tuned on benchmark data.
"""
from __future__ import annotations

import math
import random
import statistics

from .contracts import CognitionError, integer, number


def _result(output, proof, status="ANSWER"):
    return {"output": output, "proof": proof, "status": status, "formal_validity": "NOT_APPLICABLE",
            "missing_information": [], "empirical_validity": "WORLD_UNVERIFIED"}


# ------------------------------------------------------------------ Layer 1: robust anomalies
def modified_z(values):
    median = statistics.median(values)
    deviations = [abs(v - median) for v in values]
    mad = statistics.median(deviations)
    if mad > 0:
        return [0.6745 * (v - median) / mad for v in values], median, mad, "median/MAD"
    mean_ad = statistics.fmean(deviations)
    if mean_ad > 0:                      # more than half the values equal the median
        return [(v - median) / (1.253314 * mean_ad) for v in values], median, mad, "median/mean-absolute-deviation"
    return [0.0] * len(values), median, mad, "constant series"


def robust_anomalies(data, geometry):
    values = [number(x) for x in data["observations"]]
    if not 3 <= len(values) <= 100000:
        raise CognitionError("between 3 and 100000 observations required")
    threshold = number(data.get("threshold", 3.5), low=0, high=20)
    scores, median, mad, scale = modified_z(values)
    out = {"anomalies": [i for i, z in enumerate(scores) if abs(z) > threshold], "median": median, "mad": mad}
    return _result(out, {"observations": values, "model": {"method": "modified z-score", "scale": scale,
                                                           "threshold": threshold}, "scores": scores,
                         "limits": "assumes a unimodal bulk; more than half contaminated defeats any median method"})


# ------------------------------------------------------------------ Layer 2: Dawid-Skene crowd labelling
def _voters(data, classes):
    seen, group_of, tallies = set(), {}, {}
    for row in data["labels"]:
        item, observer = str(row["item_id"]), str(row["observer_id"])
        group, label = str(row["independence_group"]), row["label"]
        if label not in classes:
            raise CognitionError("label outside the declared classes")
        if (item, observer) in seen:
            raise CognitionError("an observer may label an item once")
        if group_of.setdefault(observer, group) != group:
            raise CognitionError("an observer belongs to one independence group")
        seen.add((item, observer))
        tallies.setdefault((item, group), {}).setdefault(label, 0)
        tallies[(item, group)][label] += 1
    votes, ties = {}, []
    for (item, group), counts in sorted(tallies.items()):
        top = max(counts.values())
        winners = [c for c in classes if counts.get(c) == top]
        if len(winners) == 1:
            votes.setdefault(item, {})[group] = classes.index(winners[0])
        else:
            ties.append({"item_id": item, "group": group, "tied": winners})
    return votes, ties, sorted(set(group_of.values()))


def crowd_label(data, geometry):
    classes = list(data["classes"])
    if not 2 <= len(classes) <= 20 or len(set(map(str, classes))) != len(classes):
        raise CognitionError("between 2 and 20 distinct classes required")
    if not 1 <= len(data["labels"]) <= 50000:
        raise CognitionError("between 1 and 50000 labels required")
    iterations = integer(data.get("max_iterations", 50), low=1, high=500)
    smoothing = number(data.get("smoothing", 1.0), low=0.01, high=100)
    minimum = number(data.get("min_posterior", 0.0), low=0, high=1)
    votes, ties, groups = _voters(data, classes)
    if len(groups) < 3:
        raise CognitionError("at least three independent groups required")
    k, items = len(classes), sorted(votes)
    pairs = sum(len(v) for v in votes.values())
    if pairs * k > geometry["compute_limit"]:            # one EM sweep; sweeps are capped by max_iterations
        raise CognitionError("crowd-labelling operation budget exceeded")
    # Initialise with the soft majority, then alternate M and E steps (log space, exact likelihood).
    post = {i: [sum(1 for g in votes[i].values() if g == c) / len(votes[i]) for c in range(k)] for i in items}
    trace, previous = [], None
    for _ in range(iterations):
        prior = [(sum(post[i][c] for i in items) + smoothing) / (len(items) + k * smoothing) for c in range(k)]
        counts = {g: [[smoothing] * k for _ in range(k)] for g in groups}
        for i in items:
            for g, label in votes[i].items():
                for c in range(k):
                    counts[g][c][label] += post[i][c]
        confusion = {g: [[x / sum(row) for x in row] for row in rows] for g, rows in counts.items()}
        likelihood = 0.0
        for i in items:
            logs = [math.log(prior[c]) + sum(math.log(confusion[g][c][label]) for g, label in votes[i].items())
                    for c in range(k)]
            top = max(logs)
            total = sum(math.exp(x - top) for x in logs)
            post[i] = [math.exp(x - top) / total for x in logs]
            likelihood += top + math.log(total)
        # Smoothing is a Dirichlet prior, so EM ascends the log-posterior (MAP objective), not the raw likelihood.
        objective = likelihood + smoothing * (sum(math.log(p) for p in prior) + sum(
            math.log(x) for rows in confusion.values() for row in rows for x in row))
        trace.append({"log_likelihood": round(likelihood, 9), "map_objective": round(objective, 9)})
        if previous is not None and abs(objective - previous) < 1e-7:
            break
        previous = objective
    labels, abstained = {}, []
    for i in items:
        best = max(range(k), key=lambda c: (post[i][c], -c))
        if post[i][best] >= minimum:
            labels[i] = classes[best]
        else:
            labels[i] = None
            abstained.append(i)
    reliability = {g: round(sum(prior[c] * confusion[g][c][c] for c in range(k)), 6) for g in groups}
    majority = {i: classes[max(range(k), key=lambda c: (sum(1 for x in votes[i].values() if x == c), -c))]
                for i in items}
    out = {"labels": labels, "posteriors": {i: [round(p, 9) for p in post[i]] for i in items},
           "observer_reliability": reliability, "iterations": len(trace), "abstained": abstained}
    return _result(out, {"participants": groups, "independence": "one vote per independence group per item",
                         "dissent": [{"item_id": i, "majority": majority[i], "dawid_skene": labels[i]}
                                     for i in items if labels[i] != majority[i]] + ties,
                         "trace": {"em": trace, "classes": classes, "smoothing": smoothing},
                         # the fitted model, so the verifier can recompute the E-step from the raw votes
                         "model": {"prior": prior, "confusion": confusion},
                         "baseline_status": "admitted only by the frozen native benchmark against majority vote"})


# ------------------------------------------------------------------ declared black-box objectives
def _sphere(x):
    return sum(v * v for v in x)


def _rastrigin(x):
    return 10 * len(x) + sum(v * v - 10 * math.cos(2 * math.pi * v) for v in x)


def _ackley(x):
    n = len(x)
    return (-20 * math.exp(-0.2 * math.sqrt(sum(v * v for v in x) / n))
            - math.exp(sum(math.cos(2 * math.pi * v) for v in x) / n) + 20 + math.e)


def _rosenbrock(x):
    y = [v + 1 for v in x]               # shifted so the minimum sits at the declared shift
    return sum(100 * (y[i + 1] - y[i] ** 2) ** 2 + (1 - y[i]) ** 2 for i in range(len(y) - 1))


def _griewank(x):
    return 1 + sum(v * v for v in x) / 4000 - math.prod(math.cos(v / math.sqrt(i + 1)) for i, v in enumerate(x))


OBJECTIVES = {"sphere": _sphere, "rastrigin": _rastrigin, "ackley": _ackley, "rosenbrock": _rosenbrock,
              "griewank": _griewank}


def objective(data):
    name = data["function"]
    if name not in OBJECTIVES:
        raise CognitionError("objective must be one of " + ", ".join(sorted(OBJECTIVES)))
    shift = [number(v) for v in data["shift"]]
    bounds = [(number(lo), number(hi)) for lo, hi in data["bounds"]]
    if not 1 <= len(shift) <= 32 or len(bounds) != len(shift) or any(lo >= hi for lo, hi in bounds):
        raise CognitionError("matching shift and ordered bounds required (1-32 dimensions)")
    if any(not lo <= s <= hi for s, (lo, hi) in zip(shift, bounds)):
        raise CognitionError("the declared optimum must lie inside the bounds")
    budget = integer(data["budget"], low=10, high=200000)
    function = OBJECTIVES[name]
    return (lambda x: function([a - b for a, b in zip(x, shift)])), bounds, budget


def _search_result(best, value, used, budget, trace, method, data):
    return _result({"candidate": best, "fitness": value, "evaluations": used},
                   {"participants": method, "independence": "one seeded search", "dissent": [],
                    "trace": trace[-50:], "baseline_status": "admitted only by the frozen native benchmark",
                    "evaluator": {"function": data["function"], "budget": budget}})


def swarm_minimize(data, geometry):
    f, bounds, budget = objective(data)
    if budget > geometry["compute_limit"]:
        raise CognitionError("swarm evaluation budget exceeded")
    rng = random.Random(integer(data["seed"], high=2147483647))
    size = integer(data.get("particles", 20), low=4, high=200)
    w, c1, c2 = 0.7298, 1.49618, 1.49618          # Clerc-Kennedy constriction
    span = [hi - lo for lo, hi in bounds]
    pos = [[rng.uniform(lo, hi) for lo, hi in bounds] for _ in range(size)]
    vel = [[rng.uniform(-s, s) * 0.5 for s in span] for _ in range(size)]
    fit, used = [], 0
    for p in pos:
        if used >= budget:
            break
        fit.append(f(p))
        used += 1
    pos, vel = pos[:len(fit)], vel[:len(fit)]
    personal = [list(p) for p in pos]
    gi = min(range(len(fit)), key=fit.__getitem__)
    best, value, trace = list(pos[gi]), fit[gi], []
    while used < budget:
        for j in range(len(pos)):
            if used >= budget:
                break
            for d, (lo, hi) in enumerate(bounds):
                vel[j][d] = w * vel[j][d] + c1 * rng.random() * (personal[j][d] - pos[j][d]) \
                    + c2 * rng.random() * (best[d] - pos[j][d])
                vel[j][d] = max(-span[d], min(span[d], vel[j][d]))
                pos[j][d] = max(lo, min(hi, pos[j][d] + vel[j][d]))
            y = f(pos[j])
            used += 1
            if y < fit[j]:
                fit[j], personal[j] = y, list(pos[j])
                if y < value:
                    best, value = list(pos[j]), y
                    trace.append({"evaluation": used, "fitness": value})
    return _search_result(best, value, used, budget, trace, "particle swarm (global best, constriction)", data)


def evolve_blackbox(data, geometry):
    from scipy.optimize import differential_evolution
    f, bounds, budget = objective(data)
    if budget > geometry["compute_limit"]:
        raise CognitionError("evolutionary evaluation budget exceeded")
    population = integer(data.get("population", 10), low=4, high=50)
    per_generation = population * len(bounds)
    if budget < 2 * per_generation:
        raise CognitionError("budget below two generations")
    used, best, trace = 0, [None, math.inf], []

    def counted(x):
        nonlocal used
        used += 1
        y = f(list(x))
        if y < best[1]:
            best[0], best[1] = [float(v) for v in x], y
            trace.append({"evaluation": used, "fitness": y})
        return y

    differential_evolution(counted, bounds, maxiter=budget // per_generation - 1, popsize=population,
                           seed=integer(data["seed"], high=2147483647), polish=False, tol=0, atol=0,
                           workers=1, updating="immediate")
    return _search_result(best[0], best[1], used, budget, trace, "differential evolution (rand/1/bin)", data)


REPERTOIRE = {"robust_pattern": robust_anomalies, "crowd": crowd_label, "swarm": swarm_minimize,
              "blackbox": evolve_blackbox}
