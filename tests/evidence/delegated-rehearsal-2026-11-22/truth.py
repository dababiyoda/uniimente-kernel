"""Independent truth for the delegated rehearsal: exact arithmetic, no GREG code imported.

Net monthly economics: jobs x (price - variable cost) - fixed cost is increasing in jobs and price and decreasing in
both costs, so its interval over the declared ranges has exact corners. The launch decision: Beta(1,1) prior updated
on E9, launch value = accounts x margin x theta - fixed cost, abandon = 0, and a pilot of n contacts priced by exact
beta-binomial preposterior analysis (the same textbook computation, written separately here).
"""
from fractions import Fraction
import json
import math
from pathlib import Path

PACK = json.loads((Path(__file__).parent / "evidence_tampa.json").read_text())
E = {e["id"]: e for e in PACK["evidence"]}


def net_monthly():
    jobs, price, var, fixed = E["E5"], E["E1"], E["E6"], E["E7"]
    corner = lambda j, p, v, f: j * (p - v) - f
    return {"low": corner(jobs["low"], price["low"], var["high"], fixed["high"]),
            "central": corner(jobs["central"], price["central"], var["central"], fixed["central"]),
            "high": corner(jobs["high"], price["high"], var["low"], fixed["low"])}


def _log_beta(x, y):
    return math.lgamma(x) + math.lgamma(y) - math.lgamma(x + y)


def decision(accounts):
    m = E["E11"]
    a, b = 1 + E["E9"]["successes"], 1 + E["E9"]["failures"]
    gain, fixed = Fraction(accounts * m["annual_gross_margin_per_account"]), Fraction(m["launch_fixed_cost"])
    now = gain * Fraction(a, a + b) - fixed
    best_now = max(Fraction(0), now)
    n, cost = m["pilot"]["pilot_size"], m["pilot"]["pilot_cost"]
    ev = 0.0
    for k in range(n + 1):
        p = math.exp(math.log(math.comb(n, k)) + _log_beta(a + k, b + n - k) - _log_beta(a, b))
        ev += p * max(0.0, float(gain * Fraction(a + k, a + b + n) - fixed))
    ev -= cost
    act = "launch" if now > 0 else "abandon"
    best = "pilot" if ev > float(best_now) + 1e-6 else act
    return {"accounts": accounts, "posterior_mean": a / (a + b), "value_now": float(now), "value_with_pilot": ev,
            "net_value_of_pilot": ev - float(best_now), "optimal": best}


if __name__ == "__main__":
    print(json.dumps({"net_monthly_usd": net_monthly(), "before_correction": decision(E["E11"]["reachable_accounts"]),
                      "after_correction": decision(PACK["correction_midway"]["changes"]["E11.reachable_accounts"])},
                     indent=2))
