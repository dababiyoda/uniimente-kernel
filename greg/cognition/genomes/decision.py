"""Layer 3 decision analysis: preposterior analysis that turns a posterior into value-of-information inputs.

``decision_preposterior`` (operation ``preposterior_scenarios``): for a go/no-go decision whose payoff is
linear in an unknown success rate theta (launch value = N * V * theta - K, abandon = 0) with a Beta(a, b)
posterior, and an optional pilot of n trials, enumerate every pilot outcome k = 0..n with its exact
beta-binomial predictive probability and the best decision value after observing k. The output is exactly
the typed input of the existing ``value_of_information`` family (posterior_scenarios, prior_best_value,
cost). It decides nothing alone (COMPOSITION_ONLY): with ``beta_update`` before it and
``value_of_information`` after it, it is the ``bayes_then_voi`` composition (next-best test selection).
"""
from __future__ import annotations

from fractions import Fraction
import math
import random

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int, finite

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT")


def _inputs(data):
    a = finite(data.get("alpha"), low=1e-6, high=1e6, name="alpha")
    b = finite(data.get("beta"), low=1e-6, high=1e6, name="beta")
    n = bounded_int(data.get("pilot_size"), low=1, high=400, name="pilot_size")
    customers = finite(data.get("customers"), low=0, high=1e9, name="customers")
    value = finite(data.get("value_per_success"), low=0, high=1e6, name="value_per_success")
    fixed = finite(data.get("fixed_cost"), low=0, high=1e12, name="fixed_cost")
    cost = finite(data.get("pilot_cost"), low=0, high=1e12, name="pilot_cost")
    return a, b, n, customers, value, fixed, cost


def _log_beta(x, y):
    return math.lgamma(x) + math.lgamma(y) - math.lgamma(x + y)


def preposterior(data):
    a, b, n, customers, value, fixed, cost = _inputs(data)
    gain = customers * value
    scenarios = []
    for k in range(n + 1):
        logp = (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
                + _log_beta(a + k, b + n - k) - _log_beta(a, b))
        mean = (a + k) / (a + b + n)
        scenarios.append({"probability": math.exp(logp), "best_value": max(0.0, gain * mean - fixed)})
    total = sum(s["probability"] for s in scenarios)
    for s in scenarios:
        s["probability"] /= total                      # remove floating drift; exact sum is 1
    return {"posterior_scenarios": scenarios, "prior_best_value": max(0.0, gain * a / (a + b) - fixed),
            "cost": cost, "act_now": "launch" if gain * a / (a + b) - fixed > 0 else "abandon"}


def solve(data, budget):
    out = preposterior(data)
    return answer(out, {"predictive": "beta-binomial, exact log-gamma evaluation", "outcomes": len(out["posterior_scenarios"]),
                        "decision_model": "launch value N*V*theta - K versus abandon 0"})


def verify(data, output, certificate):
    """Independent recomputation in exact rational arithmetic for integer posteriors (else float recursion)."""
    a, b, n, customers, value, fixed, cost = _inputs(data)
    probs = []
    if float(a).is_integer() and float(b).is_integer() and n <= 200:
        a_i, b_i = int(a), int(b)
        def beta_int(x, y):
            return Fraction(math.factorial(x - 1) * math.factorial(y - 1), math.factorial(x + y - 1))
        probs = [float(math.comb(n, k) * beta_int(a_i + k, b_i + n - k) / beta_int(a_i, b_i)) for k in range(n + 1)]
    else:
        p = 1.0
        for i in range(n):                              # P(k=0) by product, then the ratio recursion
            p *= (b + i) / (a + b + i)
        for k in range(n + 1):
            probs.append(p)
            p *= (n - k) / (k + 1) * (a + k) / (b + n - k - 1) if k < n else 1
    got = [s["probability"] for s in output["posterior_scenarios"]]
    gain = customers * value
    best = [max(0.0, gain * (a + k) / (a + b + n) - fixed) for k in range(n + 1)]
    return {"probabilities_recomputed": len(got) == n + 1 and all(math.isclose(x, y, rel_tol=1e-6, abs_tol=1e-12)
                                                                  for x, y in zip(got, probs)),
            "best_values_recomputed": all(math.isclose(s["best_value"], v, rel_tol=1e-9, abs_tol=1e-9)
                                          for s, v in zip(output["posterior_scenarios"], best)),
            "prior_value": math.isclose(output["prior_best_value"], max(0.0, gain * a / (a + b) - fixed),
                                        rel_tol=1e-9, abs_tol=1e-9),
            "cost_passed_through": output["cost"] == cost}


def instance(seed):
    r = random.Random(seed)
    return ({"alpha": 1 + r.randint(0, 20), "beta": 1 + r.randint(0, 60), "pilot_size": r.randint(10, 80),
             "customers": 1000, "value_per_success": 20, "fixed_cost": r.randint(1000, 6000),
             "pilot_cost": r.randint(50, 800)}, {})


def score(data, truth, output):
    if not isinstance(output, dict) or "posterior_scenarios" not in output:
        return {"quality": 0.0, "category": "abstain"}
    ok = all(verify(data, output, {}).values())
    return {"quality": 1.0 if ok else -1.0, "category": "correct" if ok else "wrong"}


INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.decision.preposterior", version="1.0.0", family="decision_preposterior",
            layer=3, operation="preposterior_scenarios", epistemic_class="strategic",
            subgeometry="go/no-go with a Beta posterior and an optional binomial pilot",
            native_representation="Beta(a, b) posterior + linear payoff + pilot size and cost",
            required_inputs=("alpha", "beta", "pilot_size", "customers", "value_per_success", "fixed_cost",
                             "pilot_cost"),
            output_contract={"posterior_scenarios": "[{probability, best_value}]", "prior_best_value": "float",
                             "cost": "float", "act_now": "launch|abandon"},
            algorithm_or_runtime="exact beta-binomial predictive enumeration (log-gamma)", parameters={},
            memory_model="stateless", learning_rule="none", composition_inputs=("posterior",),
            composition_outputs=("posterior_scenarios", "prior_best_value", "cost"),
            evidence_type="decision_analysis",
            verification_method="exact rational beta-binomial recomputation (float ratio recursion otherwise)",
            confidence_semantics="exact under the stated Beta posterior and linear payoff; the posterior itself "
                                 "is an assumption",
            resource_profile="O(pilot_size)", latency_profile="microseconds",
            known_strengths=("exact preposterior analysis",),
            known_failure_modes=("payoff nonlinearity is not modelled", "assumes exchangeable pilot trials"),
            counterindications=("non-binary outcomes", "pilots that change the population"),
            abstention_conditions=("invalid posterior or pilot",),
            benchmark_suite="structural recomputation on generated posteriors",
            baseline="none (no standalone decision)", competitor="none (no standalone decision)",
            source_provenance="Raiffa & Schlaifer (1961) preposterior analysis", buildability="BUILDABLE_NOW",
            lineage=LINEAGE, standalone_decision=False),
        solve=solve, verify=verify, instance=instance, score=score, baseline=lambda d: None,
        competitor=lambda d: None),
]
