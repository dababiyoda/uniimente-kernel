"""#47 Business compiler: validated evidence in; buyer, offer, pricing, workflow, economics and kill rules out.

Evidence records carry an id, a kind, the fields they can support and whether
they were verified. Each kind may support only certain fields (an interview can
evidence the problem and buyer, not the price; a payment or signed quote can
evidence price; a cost measurement can evidence marginal cost; a legal review
can evidence restrictions). The compiler:

  - uses verified evidence only, and cites evidence ids for every field;
  - refuses any required field no admissible evidence supports (named);
  - refuses conflicting evidence for a field instead of picking a winner;
  - derives price from the lowest evidenced willingness to pay, economics from
    measured cost, and the kill rule from the observed conversion rate;
  - emits source documents compiled by #1 (business genome validated by
    business/genome.py, a #2 pricing policy, a #15 delivery workflow and an
    experiment), so the output is executable, not a memo.
"""
from __future__ import annotations

import math

from foundry.systems import compiler

ADMISSIBLE = {
    "interview": {"problem", "buyer", "retention"},
    "payment": {"price_usd", "buyer", "offer", "conversion"},
    "signed_quote": {"price_usd", "offer", "buyer"},
    "cost_measurement": {"marginal_cost_usd", "fulfillment"},
    "channel_test": {"distribution", "conversion_rate"},
    "legal_review": {"legal_restrictions"},
    "outcome_measurement": {"regenerative_effect"},
    "capability_check": {"required_capabilities"},
}
REQUIRED = ("problem", "buyer", "offer", "price_usd", "marginal_cost_usd", "fulfillment", "distribution",
            "conversion", "conversion_rate", "retention", "legal_restrictions", "regenerative_effect",
            "required_capabilities")
NUMERIC = {"price_usd", "marginal_cost_usd", "conversion_rate"}
OFFERS_PER_TEST = 20


class BusinessCompileError(ValueError):
    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = problems


def _collect(evidence: list[dict]) -> tuple[dict, list[str]]:
    support: dict[str, list[tuple[str, object]]] = {}
    problems = []
    for e in evidence:
        if not e.get("verified"):
            continue
        allowed = ADMISSIBLE.get(e["kind"], set())
        for field, value in e.get("claims", {}).items():
            if field not in allowed:
                problems.append(f"evidence {e['id']} ({e['kind']}) is not admissible for {field}")
                continue
            support.setdefault(field, []).append((e["id"], value))
    return support, problems


def _resolve(field, rows, problems):
    if field == "price_usd":
        return min(float(v) for _, v in rows)            # the price every evidenced buyer accepted
    if field == "marginal_cost_usd":
        return max(float(v) for _, v in rows)            # the worst measured cost
    if field == "conversion_rate":
        return min(float(v) for _, v in rows)            # the most pessimistic channel test
    if field in ("legal_restrictions", "required_capabilities"):
        out = []
        for _, v in rows:
            for item in v:
                if item not in out:
                    out.append(item)
        return out
    values = {str(v) for _, v in rows}
    if len(values) > 1:
        problems.append(f"conflicting evidence for {field}: " + "; ".join(f"{i}={v!r}" for i, v in rows))
        return None
    return rows[0][1]


def compile_business(name: str, evidence: list[dict]) -> dict:
    support, problems = _collect(evidence)
    fields, cited = {}, {}
    for f in REQUIRED:
        rows = support.get(f)
        if not rows:
            problems.append(f"no verified admissible evidence for {f}")
            continue
        fields[f] = _resolve(f, rows, problems)
        cited[f] = sorted(i for i, _ in rows)
    if problems:
        raise BusinessCompileError(problems)
    expected_wins = fields["conversion_rate"] * OFFERS_PER_TEST
    kill_threshold = max(1, math.floor(expected_wins / 2))
    genome = {
        "kind": "business", "name": name, "problem": fields["problem"], "buyer": fields["buyer"],
        "offer": fields["offer"], "price_usd": fields["price_usd"], "distribution": fields["distribution"],
        "conversion": fields["conversion"], "fulfillment": fields["fulfillment"], "retention": fields["retention"],
        "marginal_cost_usd": fields["marginal_cost_usd"],
        "demand_evidence_refs": sorted(set(cited["price_usd"]) | set(cited["buyer"])),
        "required_capabilities": fields["required_capabilities"], "required_workflows": [],
        "legal_restrictions": fields["legal_restrictions"], "regenerative_effect": fields["regenerative_effect"],
        "kill_condition": f"fewer than {kill_threshold} paid of {OFFERS_PER_TEST} offers in 90 days",
        "falsification_test": f"{OFFERS_PER_TEST} offers at ${fields['price_usd']:g}; expect about {expected_wins:.1f} paid",
    }
    import yaml
    sources = {
        "business": yaml.safe_dump(genome, sort_keys=True),
        "pricing": yaml.safe_dump({"kind": "policy", "id": f"{name}-pricing", "language": "pricing", "rules": {
            "quote": f"max({fields['price_usd']:g} * units, cost_per_unit * units * 1.2)"}}, sort_keys=True),
        "delivery": yaml.safe_dump({"kind": "workflow", "id": f"{name}-delivery", "steps": [
            {"name": "record_evidence", "system": 36, "op": "put", "args": {"text": f"{name} delivery evidence"},
             "write": True},
            {"name": "verify", "system": 36, "op": "verify"}]}, sort_keys=True),
        "experiment": yaml.safe_dump({"kind": "experiment", "id": f"{name}-falsify",
                                      "hypothesis": f"{fields['buyer']} buys {fields['offer']} at ${fields['price_usd']:g}",
                                      "metric": "custom:paid_offers", "falsifier": genome["kill_condition"],
                                      "stop_rule": f"{OFFERS_PER_TEST} offers or 90 days", "budget_usd": 0},
                                     sort_keys=True),
    }
    try:
        compiled = {k: compiler.compile_source(v, f"{name}/{k}.yaml") for k, v in sources.items()}
    except compiler.CompileError as exc:   # the genome owner refused what the evidence implies
        raise BusinessCompileError(exc.problems) from None
    unit_margin = fields["price_usd"] - fields["marginal_cost_usd"]
    return {"name": name, "citations": cited, "economics": {
                "unit_margin_usd": round(unit_margin, 2), "margin_pct": round(unit_margin / fields["price_usd"], 4),
                "expected_paid_per_test": round(expected_wins, 2),
                "expected_margin_per_test_usd": round(unit_margin * expected_wins, 2)},
            "kill_rule": genome["kill_condition"], "compiled": {k: v["hash"] for k, v in compiled.items()},
            "sources": sources}


QUERY_OPS = {"compile": lambda a, r: {k: v for k, v in compile_business(a["name"], a["evidence"]).items()
                                      if k != "sources" or a.get("include_sources")}}
APPLY_OPS: dict = {}


EVIDENCE = [
    {"id": "int-1", "kind": "interview", "verified": True,
     "claims": {"problem": "suppliers cannot prove delivery", "buyer": "procurement lead", "retention": "monthly re-audit"}},
    {"id": "int-2", "kind": "interview", "verified": True, "claims": {"problem": "suppliers cannot prove delivery"}},
    {"id": "pay-1", "kind": "payment", "verified": True,
     "claims": {"price_usd": 900, "offer": "verified delivery audit", "buyer": "procurement lead",
                "conversion": "audit call"}},
    {"id": "quote-1", "kind": "signed_quote", "verified": True, "claims": {"price_usd": 1200, "offer": "verified delivery audit"}},
    {"id": "cost-1", "kind": "cost_measurement", "verified": True,
     "claims": {"marginal_cost_usd": 140, "fulfillment": "GREG evidence pack"}},
    {"id": "chan-1", "kind": "channel_test", "verified": True, "claims": {"distribution": "owned newsletter",
                                                                          "conversion_rate": 0.15}},
    {"id": "legal-1", "kind": "legal_review", "verified": True, "claims": {"legal_restrictions": ["no payment custody"]}},
    {"id": "out-1", "kind": "outcome_measurement", "verified": True,
     "claims": {"regenerative_effect": "audited suppliers were paid 11 days sooner"}},
    {"id": "cap-1", "kind": "capability_check", "verified": True, "claims": {"required_capabilities": [["evidence-pack", "1.0"]]}},
    {"id": "hearsay", "kind": "interview", "verified": False, "claims": {"buyer": "CFO"}},
]


def exercise(root) -> dict:
    ok = compile_business("proof-rail-audit", EVIDENCE)
    refusals = {}
    def refused(label, evidence):
        try:
            compile_business("x", evidence)
            refusals[label] = None
        except BusinessCompileError as exc:
            refusals[label] = exc.problems
    refused("no_price_evidence", [e for e in EVIDENCE if e["id"] not in ("pay-1", "quote-1")])
    refused("interview_claims_price", EVIDENCE + [{"id": "int-3", "kind": "interview", "verified": True,
                                                   "claims": {"price_usd": 5000}}])
    refused("conflicting_buyer", EVIDENCE + [{"id": "pay-2", "kind": "payment", "verified": True,
                                              "claims": {"buyer": "CFO", "price_usd": 950}}])
    refused("unverified_only_cost", [e for e in EVIDENCE if e["id"] != "cost-1"]
            + [{"id": "cost-x", "kind": "cost_measurement", "verified": False, "claims": {"marginal_cost_usd": 1}}])
    refused("unprofitable", [dict(e, claims={**e["claims"], "marginal_cost_usd": 950}) if e["id"] == "cost-1" else e
                             for e in EVIDENCE])
    return {"economics": ok["economics"], "kill_rule": ok["kill_rule"], "citations": ok["citations"],
            "compiled_objects": sorted(ok["compiled"]), "refusals": refusals}
