"""Lawful deterrence assessment (founder /goal "maximize ... deterrence"; review pass 2, B36).

Mechanism, not metaphor: the expected-value condition of Becker (1968). Misconduct
"pays" for a risk-neutral actor when

    gain - p_detect * p_sanction * sanction - attempt_cost > 0

The organ samples the declared parameter ranges, reports how often misconduct pays,
and evaluates *lawful* interventions by how far they lower that probability, per
unit of cost. It does not predict any person's behavior.

Hard boundaries:

* Interventions come from a closed lawful vocabulary. Coercive or rights-violating
  kinds (threats, retaliation, intimidation, extortion, deception, doxxing,
  unconsented surveillance, vigilantism, harassment, coercion) are refused, never
  ranked. Unknown kinds are malformed input.
* An intervention whose declared harm hits a hard dimension (rights, physical,
  discrimination at high, or anything critical) is refused.
* Interventions that reach another party (reporting to an authority, contractual
  remedies, public transparency, restitution claims) are marked external; the
  router hands those off to legitimate human or institutional authority.
* Each intervention is labelled by the lever it moves. Evidence (Nagin 2013)
  supports certainty of apprehension far more consistently than severity; a
  severity-only gain is flagged, not trusted.
"""
from __future__ import annotations

import random
import time
from typing import Any, Mapping

from ..contracts import ConsequenceVector, CortexError, Expenditure, OrganResult

ORGAN_ID = "cortex.deterrence.accountability@0.1.0"
VERSION = "0.1.0"
PARAMETERS = ("gain_usd", "p_detect", "p_sanction", "sanction_usd", "attempt_cost_usd")
REQUIRED = ("gain_usd", "p_detect", "p_sanction", "sanction_usd")
PROBABILITIES = ("p_detect", "p_sanction")
LAWFUL_KINDS = {
    # internal: changes the organisation's own controls
    "detection": "internal", "evidence_preservation": "internal", "access_control": "internal",
    "process_change": "internal", "independent_audit": "internal", "victim_support": "internal",
    # external: reaches another party; always handed off
    "report_to_authority": "external", "contractual_remedy": "external", "transparency": "external",
    "restitution": "external",
}
PROHIBITED_KINDS = ("threat", "retaliation", "intimidation", "extortion", "deception", "doxxing",
                    "unconsented_surveillance", "vigilantism", "harassment", "coercion")
LEVERS = {"p_detect": "certainty", "p_sanction": "certainty", "sanction_usd": "severity",
          "gain_usd": "opportunity", "attempt_cost_usd": "opportunity"}
SAMPLES = 20000
TRUTH_NOTE = ("A risk-neutral expected-value model of incentives (Becker 1968), not a prediction of any "
              "person's behavior. People are not risk-neutral; deterrence evidence supports certainty of "
              "apprehension far more consistently than severity (Nagin 2013).")


class DeterrenceError(ValueError):
    pass


def _range(name: str, spec: Any) -> tuple[float, float]:
    if not isinstance(spec, Mapping) or "low" not in spec or "high" not in spec:
        raise DeterrenceError(f"{name} needs a low/high range")
    lo, hi = float(spec["low"]), float(spec["high"])
    if lo > hi:
        raise DeterrenceError(f"{name}: low exceeds high")
    if name in PROBABILITIES and not (0.0 <= lo <= hi <= 1.0):
        raise DeterrenceError(f"{name} must lie in [0, 1]")
    if name not in PROBABILITIES and lo < 0:
        raise DeterrenceError(f"{name} must be non-negative")
    return lo, hi


def _apply(value: float, name: str, effect: Mapping[str, Any]) -> float:
    if "set" in effect:
        out = float(effect["set"])
    elif "multiply" in effect:
        out = value * float(effect["multiply"])
    elif "add" in effect:
        out = value + float(effect["add"])
    else:
        raise DeterrenceError(f"effect on {name} needs set, multiply or add")
    return min(1.0, max(0.0, out)) if name in PROBABILITIES else max(0.0, out)


class DeterrenceOrgan:
    organ_id = ORGAN_ID
    version = VERSION

    def run(self, problem, geometry, budget) -> OrganResult:
        started = time.perf_counter()
        spec = problem.payload.get("deterrence_model")
        if not isinstance(spec, Mapping):
            return self._fail("INSUFFICIENT_EVIDENCE", "no deterrence model supplied", started)
        try:
            ranges, interventions, refused = self._parse(spec)
        except (DeterrenceError, CortexError, TypeError, ValueError) as exc:
            return self._fail("MALFORMED_INPUT", f"model rejected: {exc}", started)
        seed = int(spec.get("seed", 7))
        rng = random.Random(seed)
        draws = [{n: rng.uniform(*ranges[n]) for n in ranges} for _ in range(SAMPLES)]

        def pays(rows):
            values = sorted(r["gain_usd"] - r["p_detect"] * r["p_sanction"] * r["sanction_usd"]
                            - r.get("attempt_cost_usd", 0.0) for r in rows)
            positive = sum(v > 0 for v in values) / len(values)
            return positive, {"low": values[int(0.05 * len(values))], "median": values[len(values) // 2],
                              "high": values[int(0.95 * len(values)) - 1]}

        base_rate, base_payoff = pays(draws)
        ranked = []
        for iv in interventions:
            after_rows = [{n: (_apply(v, n, iv["effects"][n]) if n in iv["effects"] else v) for n, v in row.items()}
                          for row in draws]
            rate, payoff = pays(after_rows)
            reduction = base_rate - rate
            levers = sorted({LEVERS[n] for n in iv["effects"]})
            ranked.append({"id": iv["id"], "kind": iv["kind"], "reach": LAWFUL_KINDS[iv["kind"]],
                           "levers": levers, "pays_probability_after": round(rate, 4),
                           "reduction": round(reduction, 4), "expected_payoff_after": payoff,
                           "cost_usd": iv["cost_usd"],
                           "reduction_per_1k_usd": round(reduction / iv["cost_usd"] * 1000, 4)
                           if iv["cost_usd"] > 0 else None,
                           "severity_only": levers == ["severity"]})
        ranked.sort(key=lambda r: (-r["reduction"], r["cost_usd"], r["id"]))
        best = ranked[0] if ranked else None
        proof = {
            "proof_class": "deterrence_assessment",
            "model": "risk-neutral expected value: gain - p_detect * p_sanction * sanction - attempt_cost (Becker 1968)",
            "actor_role": str(spec.get("actor_role", "unspecified role")),
            "behavior": str(spec.get("behavior", "unspecified")),
            "parameters": {n: {"low": lo, "high": hi, "dist": "uniform"} for n, (lo, hi) in ranges.items()},
            "samples": SAMPLES, "seed": seed,
            "baseline": {"misconduct_pays_probability": round(base_rate, 4), "expected_payoff": base_payoff},
            "interventions": ranked, "refused": refused,
            "assumptions": ["actor is risk-neutral", "parameter ranges are declared by the requester",
                            "parameters are independent and uniform within their ranges",
                            "an intervention changes only the parameters it names"],
            "limitations": ["no behavioral response beyond the declared effects", "no displacement to other misconduct",
                            "severity effects are weakly supported by evidence; certainty effects are stronger"],
            "truth_note": TRUTH_NOTE,
        }
        answer = {"misconduct_pays_probability": round(base_rate, 4),
                  "best_intervention": None if best is None else
                  {k: best[k] for k in ("id", "kind", "reach", "levers", "pays_probability_after", "reduction")},
                  "external_action_required": bool(best and best["reach"] == "external"),
                  "refused": [r["id"] for r in refused]}
        notes = tuple(f"refused {r['id']}: {r['why']}" for r in refused)
        return OrganResult(
            organ_id=ORGAN_ID, organ_version=VERSION, state="OK", answer=answer, proof=proof,
            assumptions=tuple(proof["assumptions"]),
            uncertainty=f"misconduct pays in {base_rate:.1%} of sampled parameter combinations (risk-neutral model)",
            expenditure=Expenditure(seconds=time.perf_counter() - started),
            dependencies=("python-stdlib",), origin="deterministic", notes=notes)

    @staticmethod
    def _parse(spec):
        params = spec.get("parameters")
        if not isinstance(params, Mapping):
            raise DeterrenceError("parameters must be an object")
        unknown = set(params) - set(PARAMETERS)
        if unknown:
            raise DeterrenceError(f"unknown parameters {sorted(unknown)}")
        missing = [p for p in REQUIRED if p not in params]
        if missing:
            raise DeterrenceError(f"missing parameters {missing}")
        ranges = {n: _range(n, params[n]) for n in PARAMETERS if n in params}
        interventions, refused, seen = [], [], set()
        for iv in spec.get("interventions", []):
            iid, kind = iv.get("id"), iv.get("kind")
            if not isinstance(iid, str) or not iid or iid in seen:
                raise DeterrenceError(f"bad or duplicate intervention id {iid!r}")
            seen.add(iid)
            if kind in PROHIBITED_KINDS:
                refused.append({"id": iid, "kind": kind, "why": "coercive or rights-violating; never ranked"})
                continue
            if kind not in LAWFUL_KINDS:
                raise DeterrenceError(f"{iid}: unknown intervention kind {kind!r}")
            hard = ConsequenceVector.from_partial(iv.get("harm") or {}).hard_violations()
            if hard:
                refused.append({"id": iid, "kind": kind, "why": f"hard harm {list(hard)}"})
                continue
            effects = iv.get("effects") or {}
            if not effects or set(effects) - set(ranges):
                raise DeterrenceError(f"{iid}: effects must name declared parameters")
            for name, effect in effects.items():
                _apply(1.0, name, effect)          # validates the effect shape
            cost = float(iv.get("cost_usd", 0.0))
            if cost < 0:
                raise DeterrenceError(f"{iid}: negative cost")
            interventions.append({"id": iid, "kind": kind, "effects": dict(effects), "cost_usd": cost})
        return ranges, interventions, refused

    def _fail(self, state: str, why: str, started: float) -> OrganResult:
        return OrganResult(organ_id=ORGAN_ID, organ_version=VERSION, state=state, answer=None,
                           proof={"proof_class": "deterrence_assessment", "failure": why},
                           uncertainty="not assessed",
                           expenditure=Expenditure(seconds=time.perf_counter() - started),
                           dependencies=("python-stdlib",), notes=(why,))
