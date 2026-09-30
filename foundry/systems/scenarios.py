"""#22 Simulation engine: the Counterfactual Tribunal for strategies under crisis.

A strategy declares its dependencies: share of revenue through each platform,
regulatory exposure, months of capital runway, founder hours it needs, and its
largest single provider. Scenarios are shocks: platform loss, regulation,
competitor attack, capital scarcity, founder absence, provider outage. Each
(strategy, scenario) pair is simulated over many seeded runs with shock
severity sampled from its declared range; the tribunal reports survival
probability and revenue retained, and writes a playbook per scenario: the
strategy that survives best and the mitigations implied by what broke.

The Kernel's twins/tribunal.py (main vs twin over a frozen corpus) keeps its
dominance geometry: a strategy is recommended over another only if it is no
worse in every scenario and better in at least one.
"""
from __future__ import annotations

import random

SCENARIOS = {
    "platform_loss": {"platform": "largest", "severity": (0.7, 1.0)},
    "regulation": {"regulatory": True, "severity": (0.3, 0.8)},
    "competitor_attack": {"price_cut": True, "severity": (0.1, 0.4)},
    "capital_scarcity": {"runway_cut": True, "severity": (0.4, 0.8)},
    "founder_absence": {"founder_months": True, "severity": (1, 4)},
    "provider_outage": {"provider": True, "severity": (0.5, 1.0)},
}
MITIGATIONS = {
    "platform": "move revenue to owned channels (#31/#32/#33) before the platform moves",
    "regulatory": "pre-build compliance evidence (#6/#43) and a compliant variant",
    "price": "compete on verified outcomes (#41), not price",
    "runway": "raise reserves in the treasury waterfall (#55) and cut burn triggers",
    "founder": "delegate with narrow grants (#8) and documented runbooks (#14/#15)",
    "provider": "add a second provider behind the router (#25) and an emulator test (#20)",
}


def _simulate(strategy: dict, scenario: dict, rng: random.Random) -> tuple[bool, float, str | None]:
    low, high = scenario["severity"]
    s = rng.uniform(low, high)
    revenue, runway, broke = 1.0, strategy["runway_months"], None
    if "platform" in scenario:
        share = max(strategy.get("platform_share", {}).values() or [0])
        revenue -= share * s
        broke = "platform" if share * s > 0.3 else broke
    if scenario.get("regulatory"):
        revenue -= strategy.get("regulatory_exposure", 0) * s
        broke = "regulatory" if strategy.get("regulatory_exposure", 0) * s > 0.3 else broke
    if scenario.get("price_cut"):
        revenue -= s * (1 - strategy.get("outcome_differentiation", 0))
        broke = "price" if s * (1 - strategy.get("outcome_differentiation", 0)) > 0.2 else broke
    if scenario.get("runway_cut"):
        runway *= (1 - s)
        broke = "runway" if runway < 3 else broke
    if scenario.get("founder_months"):
        dependency = strategy.get("founder_hours_per_week", 0) / 40
        revenue -= dependency * s / 4
        broke = "founder" if dependency * s / 4 > 0.25 else broke
    if scenario.get("provider"):
        revenue -= strategy.get("single_provider_share", 0) * s
        broke = "provider" if strategy.get("single_provider_share", 0) * s > 0.3 else broke
    revenue = max(0.0, revenue)
    survived = revenue * strategy["runway_months"] >= 3 and runway >= 2
    return survived, revenue, broke


def tribunal(strategies: dict, *, runs: int = 400, seed: int = 7) -> dict:
    table: dict = {}
    for name, strategy in sorted(strategies.items()):
        for scenario, shock in SCENARIOS.items():
            rng = random.Random(f"{seed}:{name}:{scenario}")
            outcomes = [_simulate(strategy, shock, rng) for _ in range(runs)]
            broke = [b for _, _, b in outcomes if b]
            table.setdefault(name, {})[scenario] = {
                "survival": round(sum(s for s, _, _ in outcomes) / runs, 3),
                "revenue_retained": round(sum(r for _, r, _ in outcomes) / runs, 3),
                "main_failure": max(set(broke), key=broke.count) if broke else None}
    playbook = {}
    for scenario in SCENARIOS:
        best = max(sorted(strategies), key=lambda n: (table[n][scenario]["survival"], table[n][scenario]["revenue_retained"]))
        failures = sorted({table[n][scenario]["main_failure"] for n in strategies if table[n][scenario]["main_failure"]})
        playbook[scenario] = {"most_resilient": best, "mitigations": [MITIGATIONS[f] for f in failures]}

    def dominates(a, b):
        pairs = [(table[a][s]["survival"], table[b][s]["survival"]) for s in SCENARIOS]
        return all(x >= y for x, y in pairs) and any(x > y for x, y in pairs)
    dominance = sorted([a, b] for a in strategies for b in strategies if a != b and dominates(a, b))
    return {"table": table, "playbook": playbook, "dominance": dominance}


QUERY_OPS = {"tribunal": lambda a, r: tribunal(a["strategies"], runs=int(a.get("runs", 400)), seed=int(a.get("seed", 7)))}
APPLY_OPS: dict = {}


def exercise(root) -> dict:
    strategies = {
        "rented_audience": {"platform_share": {"tiktok": 0.8}, "regulatory_exposure": 0.1, "runway_months": 6,
                            "founder_hours_per_week": 30, "single_provider_share": 0.6, "outcome_differentiation": 0.1},
        "owned_proof_rail": {"platform_share": {"linkedin": 0.2}, "regulatory_exposure": 0.2, "runway_months": 12,
                             "founder_hours_per_week": 8, "single_provider_share": 0.2, "outcome_differentiation": 0.7},
    }
    first, second = tribunal(strategies), tribunal(strategies)
    return {"deterministic": first == second, "dominance": first["dominance"],
            "platform_loss": {n: first["table"][n]["platform_loss"] for n in strategies},
            "playbook_platform_loss": first["playbook"]["platform_loss"],
            "scenarios_covered": sorted(SCENARIOS)}
