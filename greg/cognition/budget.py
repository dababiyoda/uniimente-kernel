"""Decision-aware cognitive expenditure (directive §12).

Before an optional step (another calculation, a model call, a simulation, a lookup, a
founder interruption) the controller asks one question: could the step's result change
the decision enough to pay for everything it costs? It answers with exact expected value
of sample information over a declared decision:

    EVSI = E_signal[ max_a E[U(a, s) | signal] ] - max_a E[U(a, s)]

computed in rational arithmetic, so 0 <= EVSI <= EVPI holds exactly and is checked.
Cost counts money, seconds and founder minutes at the founder-owned conversion rates the
decision declares; a zero token fee is not free. Entropy reduction alone earns nothing:
a step whose every possible result leaves the best action unchanged has EVSI = 0.

Verdicts: RUN, SKIP (with the stopping reason), WAIT (the decisive information is free
and arrives before the deadline), or UNCERTAIN when declared alternative priors put the
EVSI range across the cost line. Mandatory checks — verification, permission, legitimacy
— are refused here: they are not optional costs to optimize away.
"""
from __future__ import annotations

from datetime import datetime
from fractions import Fraction

from .contracts import CognitionError, number

MANDATORY_KINDS = ("verification", "permission_check", "legitimacy_gate", "eligibility")
STEP_KINDS = ("calculation", "model_call", "simulation", "lookup", "founder_interruption")


def _q(value, name):
    if isinstance(value, bool):
        raise CognitionError(f"{name} must be a number")
    if isinstance(value, str):
        try:
            return Fraction(value)
        except (ValueError, ZeroDivisionError) as exc:
            raise CognitionError(f"{name} is not an exact number") from exc
    return Fraction(str(number(value)))


def _prior(states, override=None):
    prior = {s["id"]: _q((override or {}).get(s["id"], s.get("prior")), f"prior of {s['id']}") for s in states}
    if any(p < 0 for p in prior.values()) or sum(prior.values()) != 1:
        raise CognitionError("state probabilities must be non-negative and sum to exactly one")
    return prior


def _parse(decision):
    states, actions = decision.get("states"), decision.get("actions")
    if not isinstance(states, list) or not 2 <= len(states) <= 64:
        raise CognitionError("two to 64 states required")
    if not isinstance(actions, list) or not 1 <= len(actions) <= 64:
        raise CognitionError("one to 64 actions required")
    ids = [s["id"] for s in states]
    if len(set(ids)) != len(ids):
        raise CognitionError("duplicate state ids")
    payoffs = {}
    for action in actions:
        row = action.get("payoffs", {})
        if set(row) != set(ids):
            raise CognitionError(f"action {action.get('id')} needs a payoff for every state")
        payoffs[action["id"]] = {s: _q(v, f"payoff {action['id']}/{s}") for s, v in row.items()}
    return ids, payoffs


def _best(payoffs, belief):
    values = {a: sum(belief[s] * u for s, u in row.items()) for a, row in payoffs.items()}
    top = max(values.values())
    return top, sorted(a for a, v in values.items() if v == top), values


def evsi(decision, likelihoods, prior=None):
    ids, payoffs = _parse(decision)
    prior = prior or _prior(decision["states"])
    signals = sorted({sig for row in likelihoods.values() for sig in row})
    for s in ids:
        row = {sig: _q(likelihoods.get(s, {}).get(sig, 0), f"likelihood {s}/{sig}") for sig in signals}
        if any(p < 0 for p in row.values()) or sum(row.values()) != 1:
            raise CognitionError(f"signal likelihoods for state {s} must sum to exactly one")
    now_value, now_actions, _ = _best(payoffs, prior)
    with_info, policy = Fraction(0), {}
    for sig in signals:
        joint = {s: prior[s] * _q(likelihoods.get(s, {}).get(sig, 0), "likelihood") for s in ids}
        mass = sum(joint.values())
        if mass == 0:
            continue
        posterior = {s: joint[s] / mass for s in ids}
        value, actions, _ = _best(payoffs, posterior)
        with_info += mass * value
        policy[sig] = actions
    perfect = sum(prior[s] * max(row[s] for row in payoffs.values()) for s in ids) - now_value
    gain = with_info - now_value
    if not 0 <= gain <= perfect:
        raise ArithmeticError("value-of-information bound violated; refusing the result")
    changes = any(set(a) != set(now_actions) for a in policy.values())
    return {"evsi": gain, "evpi": perfect, "decide_now": now_actions, "policy": policy, "changes_decision": changes}


def step_cost(step, rates):
    cost = step.get("cost", {})
    usd = _q(cost.get("usd", 0), "usd")
    if usd != 0:
        raise CognitionError("cognition never purchases; a paid step needs a founder-approved route, not this controller")
    seconds, minutes = _q(cost.get("seconds", 0), "seconds"), _q(cost.get("founder_minutes", 0), "founder_minutes")
    if seconds < 0 or minutes < 0:
        raise CognitionError("costs are non-negative")
    if (seconds and "per_second" not in rates) or (minutes and "per_founder_minute" not in rates):
        raise CognitionError("time and founder attention need founder-owned conversion rates")
    return (seconds * _q(rates.get("per_second", 0), "per_second") +
            minutes * _q(rates.get("per_founder_minute", 0), "per_founder_minute"))


def decide(decision, step, *, now=None):
    """Verdict for one optional step, with the numbers and the stopping reason."""
    kind = step.get("kind")
    if kind in MANDATORY_KINDS:
        raise CognitionError(f"{kind} is mandatory; it is never skipped to save cost")
    if kind not in STEP_KINDS:
        raise CognitionError(f"unknown optional step kind {kind!r}")
    rates = decision.get("rates", {})
    if rates and not decision.get("rates_owner"):
        raise CognitionError("conversion rates must name their founder-owned policy")
    cost = step_cost(step, rates)
    priors = [None] + list(decision.get("alternative_priors", []))
    runs = [evsi(decision, step["likelihoods"], _prior(decision["states"], p) if p else None) for p in priors]
    low, high = min(r["evsi"] for r in runs), max(r["evsi"] for r in runs)
    main = runs[0]
    record = {"step": step.get("id"), "kind": kind, "evsi": str(main["evsi"]), "evsi_range": [str(low), str(high)],
              "evpi": str(main["evpi"]), "cost": str(cost), "decide_now": main["decide_now"],
              "policy_if_run": {k: v for k, v in main["policy"].items()}, "changes_decision": main["changes_decision"]}
    available_at = step.get("available_at")
    deadline = decision.get("deadline")
    if available_at and deadline:
        now = now or datetime.now().astimezone()
        due = datetime.fromisoformat(available_at.replace("Z", "+00:00"))
        if due > now and cost == 0 and high > 0 and due <= datetime.fromisoformat(deadline.replace("Z", "+00:00")):
            return {**record, "verdict": "WAIT",
                    "stopping_reason": "the decisive information is free and arrives before the deadline"}
    if high == 0:
        return {**record, "verdict": "SKIP", "stopping_reason": "no possible result changes the best action"}
    if low > cost:
        return _escalation({**record, "verdict": "RUN", "stopping_reason": None}, decision, kind, low, high, cost)
    if high <= cost:
        return {**record, "verdict": "SKIP",
                "stopping_reason": "the step cannot change the decision enough to justify its total cost"}
    return _escalation({**record, "verdict": "UNCERTAIN",
                        "stopping_reason": "alternative priors put the value of the step on both sides of its cost"},
                       decision, kind, low, high, cost)


def _escalation(verdict, decision, kind, low, high, cost):
    """A founder interruption states the exact decision, options, costs, uncertainty and authority."""
    if kind == "founder_interruption" and verdict["verdict"] in ("RUN", "UNCERTAIN"):
        verdict["escalation"] = {"decision": decision.get("question"),
                                 "options": sorted({a for acts in verdict["policy_if_run"].values() for a in acts}),
                                 "cost": verdict["cost"], "uncertainty": [str(low), str(high)],
                                 "authority_needed": decision.get("authority_needed", "founder judgment"),
                                 "if_waiting": decision.get("cost_of_waiting", "not declared"),
                                 "urgency": "none manufactured; the founder may decline"}
    return verdict
