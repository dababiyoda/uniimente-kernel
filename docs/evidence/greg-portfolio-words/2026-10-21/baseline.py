"""Matched baseline for selection.closure: the certified optimum vs a standalone greedy rule.

Greedy rule (what a person does without the construction): repeatedly take any profitable item whose
still-unmet prerequisites it pays for on its own. Run: python docs/evidence/greg-portfolio-words/2026-10-21/baseline.py
"""
import json
import random

from greg import recombine


def closure(item, req):
    out, stack = {item}, [item]
    while stack:
        x = stack.pop()
        for a, b in req:
            if a == x and b not in out:
                out.add(b)
                stack.append(b)
    return out


def greedy(p):
    val = dict((i, v) for i, v in p["items"])
    req = [tuple(r) for r in p["requires"]]
    taken, changed = set(), True
    while changed:
        changed = False
        for i, v in sorted(val.items(), key=lambda kv: -kv[1]):
            if v <= 0 or i in taken:
                continue
            need = closure(i, req) - taken
            if sum(val[x] for x in need) > 0:
                taken |= need
                changed = True
    return sum(val[x] for x in taken)


def shared_costs(rng):
    m, o = rng.randint(1, 3), rng.randint(2, 5)
    items = [{"id": f"C{j}", "value": -rng.randint(2, 10)} for j in range(m)] + \
            [{"id": f"O{j}", "value": rng.randint(1, 8)} for j in range(o)]
    req = [[f"O{j}", f"C{c}"] for j in range(o) for c in rng.sample(range(m), rng.randint(1, m))]
    return {"items": items, "requires": req}


def measure(name, make, seed, n=2000):
    rng = random.Random(seed)
    miss = gap = total = 0
    for _ in range(n):
        p = recombine.normalize_selection(make(rng))
        best, g = recombine.selection_brute_force(p), greedy(p)
        assert g <= best
        total += best
        if g < best:
            miss, gap = miss + 1, gap + best - g
    return {"family": name, "seed": seed, "instances": n, "greedy_suboptimal": miss, "share": round(miss / n, 4),
            "profit_left_by_greedy": gap, "optimal_profit_total": total,
            "share_of_profit_lost": round(gap / total, 4) if total else None}


if __name__ == "__main__":
    print(json.dumps([measure("uniform random (the selection oracle's generator)", recombine._random_selection,
                              20261021),
                      measure("shared fixed costs: 1-3 costs of 2-10, 2-5 offers of 1-8 each needing 1-3 of them",
                              shared_costs, 1021)], indent=2))
