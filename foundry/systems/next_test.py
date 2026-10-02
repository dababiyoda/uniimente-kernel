"""#19 Recommender systems: the Next-Best-Test Router and the Narrative Next-Depth Router.

Next-Best-Test: each open hypothesis carries a Beta belief about whether it is
true and a decision it gates. A candidate test observes one hypothesis with a
known accuracy at a known cost. Its value is the expected reduction in the
probability of making the wrong decision (value of information), divided by
cost. Tests on beliefs that cannot change the decision are worth zero, however
cheap.

Next-Depth: given a person's path through owned content and observed
transitions (who went from A to B and whether they then deepened the
relationship), rank the next item by evidenced deepening rate, lower-bounded so
a single lucky transition does not dominate.
"""
from __future__ import annotations

import math


def _p_wrong(p_true: float, threshold: float) -> float:
    # Normalized false-positive loss = threshold, false-negative loss = 1-threshold.
    # Their sum is 1, so the specified decision threshold is the Bayes boundary.
    return (1 - p_true) * threshold if p_true >= threshold else p_true * (1 - threshold)


def value_of_information(alpha: float, beta: float, accuracy: float, threshold: float = 0.5) -> float:
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in (alpha, beta, accuracy, threshold)):
        raise ValueError("belief, accuracy and threshold must be finite numeric inputs")
    if alpha <= 0 or beta <= 0 or not 0 <= accuracy <= 1 or not 0 < threshold < 1:
        raise ValueError("positive Beta parameters, probability accuracy and interior threshold required")
    p = alpha / (alpha + beta)
    before = _p_wrong(p, threshold)
    p_pos = p * accuracy + (1 - p) * (1 - accuracy)
    post_pos = p * accuracy / p_pos if p_pos else p
    post_neg = p * (1 - accuracy) / (1 - p_pos) if p_pos < 1 else p
    after = p_pos * _p_wrong(post_pos, threshold) + (1 - p_pos) * _p_wrong(post_neg, threshold)
    return max(0.0, before - after)


def next_best_test(hypotheses: dict, tests: list[dict]) -> list[dict]:
    """hypotheses: {id: {alpha, beta, stakes, threshold?}}; tests: [{id, hypothesis, accuracy, cost}]."""
    ranked = []
    for t in tests:
        h = hypotheses[t["hypothesis"]]
        if (type(t["cost"]) not in (int, float) or not math.isfinite(t["cost"]) or t["cost"] <= 0
                or type(h.get("stakes", 1.0)) not in (int, float)
                or not math.isfinite(h.get("stakes", 1.0)) or h.get("stakes", 1.0) < 0):
            raise ValueError("test cost must be positive; stakes must be finite and nonnegative")
        voi = value_of_information(h["alpha"], h["beta"], t["accuracy"], h.get("threshold", 0.5)) * h.get("stakes", 1.0)
        ranked.append({"test": t["id"], "hypothesis": t["hypothesis"], "value": round(voi, 4),
                       "value_per_cost": round(voi / t["cost"], 6)})
    return sorted(ranked, key=lambda r: (-r["value_per_cost"], r["test"]))


def next_depth(current: str, transitions: list[dict], *, z: float = 1.2816) -> list[dict]:
    """transitions: [{from, to, deepened: bool}] -> candidates from ``current`` by lower-bounded deepening rate."""
    stats: dict[str, list] = {}
    for t in transitions:
        if t["from"] == current:
            stats.setdefault(t["to"], [0, 0])
            stats[t["to"]][0] += 1 if t["deepened"] else 0
            stats[t["to"]][1] += 1
    out = []
    for item, (wins, n) in stats.items():
        p = (wins + 1) / (n + 2)
        lower = max(0.0, p - z * math.sqrt(p * (1 - p) / (n + 3)))
        out.append({"next": item, "deepening_rate": round(wins / n, 3), "observations": n, "lower_bound": round(lower, 4)})
    return sorted(out, key=lambda r: (-r["lower_bound"], r["next"]))


QUERY_OPS = {"next_best_test": lambda a, r: {"ranked": next_best_test(a["hypotheses"], a["tests"])},
             "next_depth": lambda a, r: {"ranked": next_depth(a["current"], a["transitions"])}}
APPLY_OPS: dict = {}


def exercise(root) -> dict:
    hypotheses = {"buyer_pays": {"alpha": 2, "beta": 2, "stakes": 10000},          # uncertain, high stakes
                  "format_pdf_ok": {"alpha": 40, "beta": 2, "stakes": 500},          # already near-certain
                  "budget_owner_exists": {"alpha": 3, "beta": 3, "stakes": 8000}}
    tests = [{"id": "5 buyer interviews", "hypothesis": "buyer_pays", "accuracy": 0.8, "cost": 500},
             {"id": "paid pilot offer", "hypothesis": "buyer_pays", "accuracy": 0.95, "cost": 2000},
             {"id": "survey on file format", "hypothesis": "format_pdf_ok", "accuracy": 0.9, "cost": 50},
             {"id": "ask finance lead", "hypothesis": "budget_owner_exists", "accuracy": 0.85, "cost": 300}]
    ranked = next_best_test(hypotheses, tests)
    transitions = ([{"from": "intro", "to": "case-study", "deepened": True}] * 14 + [{"from": "intro", "to": "case-study", "deepened": False}] * 6
                   + [{"from": "intro", "to": "viral-clip", "deepened": True}]
                   + [{"from": "intro", "to": "pricing", "deepened": False}] * 5)
    depth = next_depth("intro", transitions)
    return {"test_order": [r["test"] for r in ranked],
            "near_certain_belief_worth_little": ranked[-1]["test"] == "survey on file format",
            "depth_order": [d["next"] for d in depth],
            "one_lucky_transition_not_first": depth[0]["next"] == "case-study"}
