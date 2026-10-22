"""Matched baseline for selection.budgeted: the certified optimum vs "trim the uncapped plan".

Heuristic (what a person does without the construction): take the best uncapped portfolio, then
repeatedly drop the cost whose removal (with everything that needs it) keeps the most profit, until the
plan fits the budget. Run: PYTHONPATH=. python docs/evidence/greg-budgeted-selection/2026-10-21/baseline.py
"""
import json
import random

from greg import recombine


def best_closure(items, value, needs):
    best, best_set = 0, set()
    items = list(items)
    for mask in range(1 << len(items)):
        S = {items[k] for k in range(len(items)) if mask >> k & 1}
        if recombine._down(S, needs) == S and sum(value[i] for i in S) > best:
            best, best_set = sum(value[i] for i in S), S
    return best_set


def trim(p):
    value, needs = dict(map(tuple, p["items"])), recombine._needs(p)
    S = best_closure(value, value, needs)
    while recombine._spend(value, S) > p["budget"]:
        options = []
        for c in [i for i in S if value[i] < 0]:
            T = {i for i in S if c not in recombine._down([i], needs)}
            options.append((sum(value[i] for i in T), sorted(T)))
        S = set(max(options)[1])
    return sum(value[i] for i in S)


def shared_costs(rng):
    m, o = rng.randint(2, 4), rng.randint(3, 6)
    items = [{"id": f"C{j}", "value": -rng.randint(2, 10)} for j in range(m)] + \
            [{"id": f"O{j}", "value": rng.randint(2, 9)} for j in range(o)]
    req = [[f"O{j}", f"C{c}"] for j in range(o) for c in rng.sample(range(m), rng.randint(1, min(2, m)))]
    total = sum(-i["value"] for i in items if i["value"] < 0)
    return {"items": items, "requires": req, "budget": rng.randint(0, total)}


def measure(seed=1021, n=2000):
    rng = random.Random(seed)
    miss = gap = total = binding = 0
    for _ in range(n):
        p = recombine.normalize_budgeted(shared_costs(rng))
        best, h = recombine.budgeted_brute_force(p), trim(p)
        assert h <= best
        value = dict(map(tuple, p["items"]))
        binding += recombine._spend(value, best_closure(value, value, recombine._needs(p))) > p["budget"]
        total += best
        if h < best:
            miss, gap = miss + 1, gap + best - h
    return {"family": "shared fixed costs under a cap: 2-4 costs of 2-10, 3-6 offers of 2-9 each needing 1-2 of "
                      "them, budget uniform from 0 to the total cost", "seed": seed, "instances": n,
            "cap_binding": binding, "heuristic_suboptimal": miss, "share": round(miss / n, 4),
            "profit_left_by_heuristic": gap, "optimal_profit_total": total,
            "share_of_profit_lost": round(gap / total, 4) if total else None}


if __name__ == "__main__":
    print(json.dumps(measure(), indent=2))
