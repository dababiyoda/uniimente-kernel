"""#40 Game theory and mechanism design: rules under which truthful, useful behavior pays.

Two mechanisms, each with a best-response check a designer can rerun:

* Proper scoring (Brier) for provider forecasts: a provider paid by the Brier
  score maximizes expected pay by reporting its true belief. ``best_report``
  searches the report grid and returns the argmax.
* Sealed-bid second-price (Vickrey) procurement for capability providers: the
  lowest bid wins and is paid the second-lowest bid, so bidding true cost is a
  dominant strategy. ``bid_gain`` compares truthful bidding against every
  deviation over a grid of rival bids.

Mechanisms are simulated and checked; none moves money.
"""
from __future__ import annotations


def brier_payment(report: float, outcome: int, scale: float = 100.0) -> float:
    return scale * (1 - (report - outcome) ** 2)


def expected_pay(report: float, belief: float) -> float:
    return belief * brier_payment(report, 1) + (1 - belief) * brier_payment(report, 0)


def best_report(belief: float, grid: int = 100) -> float:
    return max((i / grid for i in range(grid + 1)), key=lambda r: (expected_pay(r, belief), -abs(r - belief)))


def vickrey_procurement(bids: dict) -> dict:
    ranked = sorted(bids.items(), key=lambda kv: (kv[1], kv[0]))
    winner, _ = ranked[0]
    price = ranked[1][1] if len(ranked) > 1 else ranked[0][1]
    return {"winner": winner, "paid": price}


def utility(provider: str, cost: float, bids: dict) -> float:
    result = vickrey_procurement(bids)
    return (result["paid"] - cost) if result["winner"] == provider else 0.0


def bid_gain(cost: float, rival_bids: list[float], deviations: list[float]) -> float:
    """Largest gain any deviation achieves over truthful bidding across rival scenarios (<= 0 means truthful is dominant)."""
    worst = float("-inf")
    for rival in rival_bids:
        truthful = utility("me", cost, {"me": cost, "rival": rival})
        for bid in deviations:
            worst = max(worst, utility("me", cost, {"me": bid, "rival": rival}) - truthful)
    return worst


QUERY_OPS = {"best_report": lambda a, r: {"report": best_report(float(a["belief"]))},
             "procure": lambda a, r: vickrey_procurement(a["bids"])}
APPLY_OPS: dict = {}


def exercise(root) -> dict:
    beliefs = [0.1, 0.35, 0.5, 0.72, 0.9]
    grid = [x * 5.0 for x in range(1, 41)]
    return {"brier_truthful": all(abs(best_report(b) - b) < 1e-9 for b in beliefs),
            "vickrey_max_deviation_gain": bid_gain(60.0, grid, grid),
            "procurement": vickrey_procurement({"a": 120, "b": 90, "c": 150}),
            "first_price_would_reward_shading": utility("me", 60, {"me": 95, "rival": 100}) > 0}
