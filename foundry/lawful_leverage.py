"""Lawful Leverage Foundry: the upstream search the institutional-leverage ranker lacked.

Founder directive 2026-10-07, sections 17-20. ``egregore.leverage`` ranks interventions it is
handed; a system that only ranks supplied interventions cannot claim to search for the strongest
lawful one. This module generates them, then hands survivors to that same ranker:

    objective -> active bottleneck (the ranker's own path math) -> evidenced control surfaces
      -> generate lawful mechanisms from a reviewed library -> mutate (staged pilot, defer to a
      trigger, consented scope) -> recombine complementary surfaces -> HARD FILTER (prohibited
      mechanisms, consent, consequence classes, harm ceilings, budget, founder attention, evidenced
      path; eligibility gates, never weights) -> estimate (seeded Monte Carlo with common random
      numbers over link reality and Beta effect posteriors) and falsify (path support, prior-only
      evidence, adversarial sensitivity, declared falsifier) -> compare (Pareto frontier over a
      benefit vector and a cost/harm vector; a control point is preferred only where the evidence
      shows it dominates repeated direct labour) -> value of the next test -> emit
      institutional-leverage interventions, the minimum founder decision brief (turned into an ask
      only by ``greg.asks`` on GREG's side), preparable steps and the asset production line.

Nothing here executes, publishes, contacts, spends, or grants or widens authority. Every estimate
is an input estimate, not a verified outcome. ``authority_created`` is always false; the existing
Gate remains the only path to consequence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import math
from pathlib import Path
import random

from jsonschema import Draft202012Validator, FormatChecker

from egregore import leverage as ranker
from egregore.contracts import ContractError, canonical_copy, digest

VERSION = "lawful-leverage/0.1"
ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "contracts/lawful-leverage.schema.json").read_text())

SURFACES = ("proof", "eligibility", "permission", "incentives", "routing", "defaults", "coordination", "standards",
            "reputation", "dependency", "settlement", "capital", "information", "timing", "capability", "workflow")
ASSETS = ("knowledge", "evidence", "relationship", "reputation", "software", "workflow", "sop", "automation",
          "permission", "distribution", "data_rights", "capability", "contract", "customer_trust", "capital",
          "ownership", "optionality", "verified_precedent", "recovery_procedure")
HARM = ("third_party", "privacy", "dependency_capture", "tail", "participant_burden")
DEFAULT_CEILING = {"third_party": 0.2, "privacy": 0.1, "dependency_capture": 0.4, "tail": 0.2,
                   "participant_burden": 0.4}
# Never eligible, whatever the upside: law, rights, consent and authority are gates, not weights.
PROHIBITED = ("deception", "coercion", "unauthorized_access", "nonconsensual_surveillance", "control_over_people",
              "exploits_vulnerable_people", "collusion", "bribery", "intimidation", "retaliation",
              "regulatory_evasion", "fabricated_evidence", "shutdown_resistance", "authority_expansion")
CONSEQUENCE = ("read_only", "internal_write", "external_contact", "financial", "irreversible")
REVERSIBILITY = {"reversible": 0.0, "partially_reversible": 0.5, "irreversible": 1.0}
COMPLEMENTS = (("proof", "eligibility"), ("proof", "settlement"), ("proof", "reputation"), ("standards", "defaults"),
               ("information", "timing"), ("workflow", "capability"), ("incentives", "settlement"),
               ("routing", "information"), ("coordination", "standards"), ("dependency", "capability"),
               ("permission", "eligibility"), ("capital", "settlement"))
MAX_CANDIDATES = 64           # the institutional-leverage contract's intervention ceiling
PROBABLE = 0.8                # "defensible" and "dominates" both mean at least 80% of joint samples


class LeverageRefused(ContractError):
    """The Foundry refuses a malformed problem, a non-human legal operator or an unlawful request."""


@dataclass(frozen=True)
class Mechanism:
    """One lawful intervention template. Priors are deliberately weak and uncalibrated: evidence updates them."""
    mechanism_id: str
    surface: str
    leverage_mechanism: str          # the institutional-leverage enum (direct/rule/incentive/coordination)
    title: str
    action_class: str
    consequence_class: str
    effect_prior: float
    prior_strength: float
    persistence: float               # share of the effect retained each further cycle
    cost_usd: float
    effort_hours: float
    maintenance_hours_per_cycle: float
    delay_days: float
    founder_attention_hours: float
    reversibility: str
    harm: tuple                      # ((dimension, value), ...)
    third_parties_affected: bool
    assets: tuple
    compounding: float
    reuse: float
    option_value: float
    protective_effect: float
    participant_benefit: float
    falsifier: str
    rollback: str
    counterargument: str
    flags: tuple = ()
    deferred_consequence_class: str | None = None
    lineage: tuple = ()
    kind: str = "generated"
    components: tuple = ()
    trigger_probability: float = 1.0
    consented: bool = False

    def harm_vector(self) -> dict:
        base = dict.fromkeys(HARM, 0.0)
        base.update(dict(self.harm))
        return base


def _m(mid, surface, mech, title, action, consequence, effect, persistence, cost, effort, maintain, delay, attention,
       reversibility, harm, third, assets, compounding, reuse, option, protective, benefit, falsifier, rollback,
       counter):
    return Mechanism(mid, surface, mech, title, action, consequence, effect, 4.0, persistence, cost, effort, maintain,
                     delay, attention, reversibility, tuple(sorted(harm.items())), third, tuple(assets), compounding,
                     reuse, option, protective, benefit, falsifier, rollback, counter)


# The reviewed library: one lawful mechanism per control surface. Every number is a weak prior for a
# template, not market data; problem evidence and mechanism_overrides replace them where known.
LIBRARY = (
    _m("proof.verifiable_receipts", "proof", "rule", "issue verifiable outcome receipts counterparties can check",
       "artifact.prepare", "external_contact", 0.35, 0.95, 400, 24, 1, 7, 2, "reversible",
       {"privacy": 0.05, "participant_burden": 0.05}, True,
       ("evidence", "verified_precedent", "reputation", "software"), 0.8, 0.8, 0.4, 0.5, 0.6,
       "share of transactions that clear without manual re-verification rises at the bottleneck",
       "stop issuing receipts; prior verification path is unchanged",
       "counterparties may not trust or read the receipts"),
    _m("eligibility.published_standard", "eligibility", "rule",
       "pre-qualify participants against a published, appealable standard", "artifact.prepare", "external_contact",
       0.3, 0.9, 300, 30, 2, 14, 3, "reversible", {"participant_burden": 0.15, "third_party": 0.05}, True,
       ("sop", "permission", "knowledge", "customer_trust"), 0.7, 0.7, 0.3, 0.4, 0.5,
       "per-transaction eligibility checks fall while acceptance quality holds",
       "withdraw the standard; per-case review resumes", "a standard can exclude legitimate participants"),
    _m("permission.standing_grant", "permission", "rule",
       "request a bounded, revocable standing permission from the party that controls the gate", "request.prepare",
       "external_contact", 0.4, 0.95, 0, 6, 0.5, 21, 2, "reversible", {"dependency_capture": 0.2}, False,
       ("permission", "relationship"), 0.6, 0.5, 0.5, 0.3, 0.3,
       "approvals per transaction fall to zero inside the granted scope",
       "the grantor revokes; per-instance approval resumes", "the gatekeeper may refuse or attach conditions"),
    _m("incentives.outcome_pricing", "incentives", "incentive",
       "price on the verified outcome so counterparties share the target", "offer.prepare", "financial", 0.3, 0.85,
       200, 16, 2, 30, 4, "partially_reversible", {"tail": 0.1, "participant_burden": 0.05}, True,
       ("contract", "customer_trust", "capital"), 0.6, 0.6, 0.3, 0.3, 0.6,
       "share of engagements reaching the verified outcome rises; disputes do not",
       "revert to the prior price for new engagements; honour signed ones", "outcome measurement disputes"),
    _m("routing.evidence_triage", "routing", "coordination",
       "route incoming work to the handler with the best settled outcome record", "workflow.prepare",
       "internal_write", 0.25, 0.9, 0, 20, 1, 7, 1, "reversible", {}, False,
       ("workflow", "automation", "knowledge"), 0.7, 0.8, 0.2, 0.2, 0.3,
       "first-pass resolution rate at the bottleneck rises", "restore the previous routing table",
       "outcome records may be too thin to route on"),
    _m("defaults.opt_in_template", "defaults", "rule",
       "publish an opt-in default template participants may adopt or ignore", "artifact.prepare", "external_contact",
       0.25, 0.9, 150, 12, 0.5, 14, 2, "reversible", {"participant_burden": 0.05}, True,
       ("sop", "distribution", "knowledge"), 0.6, 0.8, 0.3, 0.2, 0.5,
       "share of new transactions using the template rises without complaints",
       "withdraw the template; nothing depends on it", "defaults help only if adoption is voluntary and real"),
    _m("coordination.shared_cadence", "coordination", "coordination",
       "convene the actors on a shared cadence and handoff protocol", "meeting.prepare", "external_contact", 0.25,
       0.8, 0, 10, 2, 7, 4, "reversible", {"participant_burden": 0.1}, True,
       ("relationship", "workflow", "sop"), 0.5, 0.5, 0.3, 0.2, 0.4,
       "handoff latency between the actors falls", "stop the cadence", "meetings can become the bottleneck"),
    _m("standards.open_spec", "standards", "rule",
       "publish an open interoperability specification others may implement", "artifact.prepare",
       "external_contact", 0.3, 0.97, 500, 40, 2, 30, 6, "partially_reversible", {"tail": 0.05}, False,
       ("knowledge", "reputation", "distribution", "verified_precedent"), 0.9, 0.9, 0.6, 0.3, 0.6,
       "independent implementers adopt the spec and integration time falls",
       "mark the spec superseded; existing implementers keep it", "nobody adopts it; competitors fork it"),
    _m("reputation.consented_case_studies", "reputation", "incentive",
       "publish verified case studies only with each subject's written consent", "artifact.prepare",
       "external_contact", 0.2, 0.85, 100, 12, 0.5, 14, 2, "partially_reversible", {"privacy": 0.05}, True,
       ("reputation", "customer_trust", "verified_precedent"), 0.6, 0.6, 0.3, 0.2, 0.4,
       "qualified inbound requests citing the case studies rise", "unpublish on request",
       "case studies persuade weakly without third-party verification"),
    _m("dependency.second_source", "dependency", "direct",
       "qualify a second supplier for the single point of dependency", "procurement.prepare", "financial", 0.3,
       0.95, 600, 20, 1, 30, 3, "reversible", {}, False,
       ("relationship", "recovery_procedure", "optionality"), 0.5, 0.6, 0.7, 0.8, 0.3,
       "the bottleneck keeps operating through a primary-supplier outage drill",
       "release the second source", "two suppliers cost more to manage"),
    _m("settlement.milestone_escrow", "settlement", "incentive",
       "settle against verified milestones through a neutral escrow or holdback", "contract.prepare", "financial",
       0.3, 0.9, 250, 10, 1, 21, 3, "partially_reversible", {"participant_burden": 0.05, "tail": 0.05}, True,
       ("contract", "customer_trust", "recovery_procedure"), 0.6, 0.7, 0.3, 0.7, 0.6,
       "unpaid or disputed deliveries at the bottleneck fall",
       "release escrow per the signed terms", "escrow adds friction for honest counterparties"),
    _m("capital.prepay_discount", "capital", "incentive",
       "offer an optional prepayment discount to fund working capital", "offer.prepare", "financial", 0.2, 0.7,
       100, 6, 0.5, 14, 2, "partially_reversible", {"tail": 0.1}, True, ("capital", "customer_trust"), 0.5, 0.5,
       0.4, 0.2, 0.4, "cash conversion cycle shortens without churn", "end the offer for new orders",
       "discounts can signal distress or erode margin"),
    _m("information.public_signal_monitor", "information", "coordination",
       "monitor lawful public sources for earlier detection of changes at the bottleneck", "monitor.prepare",
       "read_only", 0.15, 0.9, 0, 10, 1, 3, 1, "reversible", {}, False,
       ("knowledge", "optionality", "data_rights"), 0.7, 0.8, 0.8, 0.5, 0.2,
       "lead time between a relevant change and GREG's detection grows",
       "stop monitoring", "public signals may be too sparse or late to matter"),
    _m("timing.prepared_offer", "timing", "coordination",
       "prepare an offer in advance and release it only when a declared trigger occurs", "offer.prepare",
       "external_contact", 0.3, 0.85, 50, 8, 0.5, 2, 2, "reversible", {}, True,
       ("optionality", "knowledge"), 0.5, 0.6, 0.9, 0.3, 0.4,
       "time from trigger to offer falls to under a day when the trigger occurs",
       "discard the prepared offer", "the trigger may never occur"),
    _m("capability.internal_tool", "capability", "direct",
       "build a bounded internal tool removing a recurring manual step", "build.prepare", "internal_write", 0.35,
       0.95, 0, 40, 2, 14, 2, "reversible", {"dependency_capture": 0.05}, False,
       ("software", "automation", "capability"), 0.8, 0.8, 0.4, 0.3, 0.3,
       "manual hours per transaction at the bottleneck fall", "switch the tool off; the manual path remains",
       "the tool may automate the wrong step"),
    _m("workflow.sop_checklist", "workflow", "rule",
       "codify the recurring process into an SOP and a checklist with a recovery path", "artifact.prepare",
       "internal_write", 0.2, 0.9, 0, 12, 0.5, 5, 1, "reversible", {}, False,
       ("sop", "workflow", "recovery_procedure", "knowledge"), 0.7, 0.9, 0.2, 0.4, 0.3,
       "error and rework rates at the bottleneck fall", "retire the SOP",
       "an SOP no one follows changes nothing"),
)
BY_ID = {m.mechanism_id: m for m in LIBRARY}
assert len(BY_ID) == len(LIBRARY) and {m.surface for m in LIBRARY} == set(SURFACES)


# ------------------------------------------------------------------ input
def validate(problem: dict) -> dict:
    problem = canonical_copy(problem)
    errors = sorted(Draft202012Validator(SCHEMA, format_checker=FormatChecker()).iter_errors(problem),
                    key=lambda e: list(e.path))
    if errors:
        raise LeverageRefused(f"lawful-leverage problem: {errors[0].message} at {list(errors[0].path)}")
    if str(problem["constraints"].get("legal_operator", "alfonso_lopez")).upper() == "UNIIMENTE":
        raise LeverageRefused("UNIIMENTE is never the legal operator")
    model = ranker._validate("map", problem["institutional_map"])
    nodes = {n["id"]: n for n in model["nodes"]}
    if problem["outcome_node"] not in nodes:
        raise LeverageRefused("outcome node is not on the institutional map")
    for edge in model["links"]:
        if edge["source"] not in nodes or edge["target"] not in nodes:
            raise LeverageRefused(f"dangling link {edge['id']}")
    seen = set()
    for s in problem["surfaces"]:
        if s["node"] not in nodes:
            raise LeverageRefused(f"surface {s['surface']} names node {s['node']} absent from the map")
        if s["surface"] in seen:
            raise LeverageRefused(f"surface {s['surface']} declared twice")
        seen.add(s["surface"])
    for key in problem.get("mechanism_overrides", {}):
        if key not in BY_ID:
            raise LeverageRefused(f"override for unknown mechanism {key}")
    for key, ev in problem.get("evidence", {}).items():
        if key not in BY_ID and key not in SURFACES and key != "direct_labor":
            raise LeverageRefused(f"evidence for unknown mechanism or surface {key}")
        if ev["successes"] > ev["trials"]:
            raise LeverageRefused(f"evidence {key}: successes exceed trials")
    return {**problem, "institutional_map": model}


# ------------------------------------------------------------------ generate / mutate / recombine
def _instantiate(problem: dict) -> list[tuple[Mechanism, dict]]:
    """Library mechanisms on evidenced surfaces only: no surface evidence, no candidate."""
    overrides = problem.get("mechanism_overrides", {})
    out = []
    for s in problem["surfaces"]:
        for m in LIBRARY:
            if m.surface != s["surface"]:
                continue
            o = {k: v for k, v in overrides.get(m.mechanism_id, {}).items() if k != "target"}
            out.append((replace(m, **o, lineage=("library",)), s))
    return out


def _mutate(base: list[tuple[Mechanism, dict]], trigger_p: float) -> list[tuple[Mechanism, dict]]:
    out = []
    for m, s in base:
        out.append((replace(m, mechanism_id=m.mechanism_id + ":staged", effect_prior=m.effect_prior * 0.5,
                            cost_usd=m.cost_usd * 0.3, effort_hours=m.effort_hours * 0.4,
                            delay_days=m.delay_days * 0.5, reversibility="reversible",
                            harm=tuple((k, v * 0.5) for k, v in m.harm), assets=tuple(sorted({*m.assets, "evidence"})),
                            option_value=min(1.0, m.option_value + 0.2), lineage=m.lineage + ("mutate:staged_pilot",)),
                    s))
        if m.consequence_class in ("external_contact", "financial"):
            out.append((replace(m, mechanism_id=m.mechanism_id + ":on_trigger", consequence_class="internal_write",
                                deferred_consequence_class=m.consequence_class, trigger_probability=trigger_p,
                                option_value=min(1.0, m.option_value + 0.3),
                                lineage=m.lineage + ("mutate:defer_to_trigger",)), s))
        if m.third_parties_affected and not m.consented:
            out.append((replace(m, mechanism_id=m.mechanism_id + ":consented", effect_prior=m.effect_prior * 0.7,
                                harm=tuple((k, 0.0 if k == "third_party" else v) for k, v in m.harm), consented=True,
                                lineage=m.lineage + ("mutate:consented_scope",)), s))
    return out


def _recombine(base: list[tuple[Mechanism, dict]]) -> list[tuple[Mechanism, dict, Mechanism, dict]]:
    by_surface = {m.surface: (m, s) for m, s in base}
    return [(*by_surface[a], *by_surface[b]) for a, b in COMPLEMENTS if a in by_surface and b in by_surface]


# ------------------------------------------------------------------ hard filter (eligibility before optimisation)
def eligibility(m: Mechanism, surface: dict | None, problem: dict, reach: dict) -> list[str]:
    c = problem["constraints"]
    ceiling = {**DEFAULT_CEILING, **c.get("harm_ceiling", {})}
    reasons = [f"REJECTED_PROHIBITED_MECHANISM:{f}" for f in m.flags if f in PROHIBITED]
    unknown = [f for f in m.flags if f not in PROHIBITED]
    reasons += [f"REJECTED_UNREVIEWED_FLAG:{f}" for f in unknown]
    banned = set(c.get("prohibited_consequence_classes", []))
    for cls in {m.consequence_class, m.deferred_consequence_class} - {None}:
        if cls in banned:
            reasons.append(f"REJECTED_CONSEQUENCE_CLASS:{cls}")
    if m.third_parties_affected and not m.consented and not (surface or {}).get("consent_mechanism"):
        reasons.append("REJECTED_NO_CONSENT_PATH")
    for dim, value in m.harm_vector().items():
        if value > ceiling[dim]:
            reasons.append(f"REJECTED_HARM:{dim}")
    if m.cost_usd > c["budget_usd"]:
        reasons.append("REJECTED_BUDGET")
    if m.founder_attention_hours > c["founder_attention_hours"]:
        reasons.append("REJECTED_FOUNDER_ATTENTION")
    nodes = [comp["node"] for comp in m.components] or [(surface or {}).get("node")]
    if any(n not in reach for n in nodes):
        reasons.append("INELIGIBLE_NO_EVIDENCED_PATH_TO_BOTTLENECK")
    return reasons


# ------------------------------------------------------------------ estimate and falsify
def _posterior(m: Mechanism, problem: dict) -> tuple[float, float, int]:
    ev = problem.get("evidence", {})
    record = ev.get(m.mechanism_id.split(":")[0]) or ev.get(m.surface) or {"successes": 0, "trials": 0}
    mean = min(0.99, max(0.01, m.effect_prior))
    a = mean * m.prior_strength + record["successes"]
    b = (1 - mean) * m.prior_strength + record["trials"] - record["successes"]
    return a, b, record["trials"]


def _closure_factor(persistence: float, delay_cycles: int, horizon: int) -> float:
    active = max(0, horizon - delay_cycles)
    return sum(persistence ** t for t in range(active))


class _World:
    """Common random numbers: one realisation of every link per sample, shared by all candidates."""

    def __init__(self, links: dict, samples: int, seed: int):
        rng = random.Random(f"{seed}:links")
        ids = sorted(links)
        self.real = [{lid: rng.random() < links[lid]["confidence"] for lid in ids} for _ in range(samples)]
        self.links = links

    def weight(self, s: int, path) -> float:
        w = 1.0
        for lid in path:
            if not self.real[s][lid]:
                return 0.0
            w *= self.links[lid]["strength"]
        return w

    def support(self, path) -> float:
        return sum(all(r[lid] for lid in path) for r in self.real) / len(self.real)


def _quantile(xs: list, q: float) -> float:
    ys = sorted(xs)
    return ys[min(len(ys) - 1, max(0, int(q * (len(ys) - 1) + 0.5)))]


def _simulate(m: Mechanism, problem: dict, world: _World, ctx: dict, effect_scale: float = 1.0) -> list[float]:
    """Cumulative outcome-level gap closure over the horizon, one value per joint sample."""
    n, horizon = ctx["samples"], ctx["horizon"]
    rng = random.Random(f"{ctx['seed']}:{m.mechanism_id}:{effect_scale}")
    parts = m.components or ({"node": ctx["surface_node"][m.mechanism_id], "mechanism": m},)
    posts = []
    for comp in parts:
        mech = comp["mechanism"]
        a, b, _ = _posterior(replace(mech, effect_prior=mech.effect_prior * effect_scale), problem)
        posts.append((a, b, ctx["reach"][comp["node"]][1]))
    delay = int(math.ceil(m.delay_days / ctx["cycle_days"]))
    if m.kind == "direct_labor":
        factor = float(horizon)                   # paid every cycle; no persistence after it stops
    else:
        factor = _closure_factor(m.persistence, delay, horizon)
    out = []
    for s in range(n):
        severity = ctx["gap"] * world.weight(s, ctx["outcome_path"])
        miss = 1.0
        for a, b, path in posts:
            miss *= 1.0 - rng.betavariate(a, b) * world.weight(s, path)
        realised = 1.0 if rng.random() < m.trigger_probability else 0.0
        out.append((1.0 - miss) * severity * factor * realised)
    return out


def _summary(xs: list[float]) -> dict:
    return {"mean": sum(xs) / len(xs), "p05": _quantile(xs, 0.05), "p50": _quantile(xs, 0.5),
            "p95": _quantile(xs, 0.95)}


def _costs(m: Mechanism, horizon: int) -> dict:
    return {"capital_usd": m.cost_usd, "effort_hours": m.effort_hours + m.maintenance_hours_per_cycle * horizon,
            "founder_attention_hours": m.founder_attention_hours, "delay_days": m.delay_days,
            "irreversibility": REVERSIBILITY[m.reversibility]}


def _authority(m: Mechanism, held: set) -> dict:
    now_ok = m.consequence_class in held and m.consequence_class != "irreversible"
    later = m.deferred_consequence_class
    state = ("WITHIN_HELD_AUTHORITY_GATE_REQUIRED" if now_ok and (later is None or later in held)
             else "PREPARABLE_NOW_FOUNDER_DECISION_AT_TRIGGER" if now_ok
             else "FOUNDER_DECISION_REQUIRED")
    burden = {"WITHIN_HELD_AUTHORITY_GATE_REQUIRED": 0.0, "PREPARABLE_NOW_FOUNDER_DECISION_AT_TRIGGER": 0.5,
              "FOUNDER_DECISION_REQUIRED": 1.0}[state]
    return {"state": state, "consequence_class": m.consequence_class, "deferred_consequence_class": later,
            "authority_burden": burden}


# ------------------------------------------------------------------ compare
BENEFIT_KEYS = ("p_meaningful", "mean_closure", "compounding", "reuse", "option_value", "protective_effect",
                "participant_benefit")
COST_KEYS = ("capital_usd", "effort_hours", "founder_attention_hours", "delay_days", "irreversibility",
             "authority_burden", "dependency_capture", *[f"harm_{d}" for d in HARM if d != "dependency_capture"])


def _vectors(row: dict) -> tuple[tuple, tuple]:
    benefit = tuple(row["benefit"][k] for k in BENEFIT_KEYS)
    cost = tuple(row["cost"][k] for k in COST_KEYS)
    return benefit, cost


def dominates(a: dict, b: dict) -> bool:
    ab, ac = _vectors(a)
    bb, bc = _vectors(b)
    no_worse = all(x >= y for x, y in zip(ab, bb)) and all(x <= y for x, y in zip(ac, bc))
    return no_worse and (ab != bb or ac != bc)


def frontier(rows: list[dict]) -> list[str]:
    return [r["candidate_id"] for r in rows if not any(dominates(o, r) for o in rows if o is not r)]


def _p_greater(xs: list[float], ys: list[float]) -> float:
    return sum(x >= y for x, y in zip(xs, ys)) / len(xs)


# ------------------------------------------------------------------ compile
def compile(problem: dict) -> dict:  # noqa: A001 - the Foundry's public verb
    p = validate(problem)
    model = p["institutional_map"]
    nodes = {n["id"]: n for n in model["nodes"]}
    links = {e["id"]: e for e in model["links"]}
    horizon, samples, seed = p.get("horizon_cycles", 12), p.get("samples", 4000), p.get("seed", 20261008)
    cycle_days = p.get("cycle_days", 7)
    # 1. the active bottleneck, by the ranker's own path math (one owner of routing arithmetic)
    to_outcome = ranker._paths_to(p["outcome_node"], links, 6)
    gaps = sorted(((nodes[n]["gap"] * w, n) for n, (w, _) in to_outcome.items() if nodes[n]["gap"] > 0),
                  key=lambda t: (-t[0], t[1]))
    if not gaps:
        raise LeverageRefused("no evidenced bottleneck reaches the outcome; retain current state")
    severity_expected, bottleneck = gaps[0]
    outcome_path = to_outcome[bottleneck][1]
    reach = ranker._paths_to(bottleneck, links, max(1, 6 - len(outcome_path)))
    ctx = {"samples": samples, "horizon": horizon, "seed": seed, "cycle_days": cycle_days, "reach": reach,
           "gap": nodes[bottleneck]["gap"], "outcome_path": outcome_path, "surface_node": {}}
    world = _World(links, samples, seed)
    # 2. generate, mutate, recombine
    base = _instantiate(p)
    mutated = _mutate(base, p.get("trigger_probability", 0.5))
    combos: list[tuple[Mechanism, dict]] = []
    for m1, s1, m2, s2 in _recombine(base):
        merged_harm = {d: max(m1.harm_vector()[d], m2.harm_vector()[d]) for d in HARM}
        worst = max((m1, m2), key=lambda m: REVERSIBILITY[m.reversibility])
        combo = replace(
            m1, mechanism_id=f"{m1.mechanism_id}+{m2.mechanism_id}", surface=f"{m1.surface}+{m2.surface}",
            leverage_mechanism="coordination", title=f"{m1.title}; and {m2.title}",
            consequence_class=max((m1.consequence_class, m2.consequence_class), key=CONSEQUENCE.index),
            cost_usd=m1.cost_usd + m2.cost_usd, effort_hours=m1.effort_hours + m2.effort_hours,
            maintenance_hours_per_cycle=m1.maintenance_hours_per_cycle + m2.maintenance_hours_per_cycle,
            delay_days=max(m1.delay_days, m2.delay_days),
            founder_attention_hours=m1.founder_attention_hours + m2.founder_attention_hours,
            persistence=min(m1.persistence, m2.persistence), reversibility=worst.reversibility,
            harm=tuple(sorted(merged_harm.items())),
            third_parties_affected=m1.third_parties_affected or m2.third_parties_affected,
            assets=tuple(sorted({*m1.assets, *m2.assets})),
            **{k: max(getattr(m1, k), getattr(m2, k)) for k in
               ("compounding", "reuse", "option_value", "protective_effect", "participant_benefit")},
            falsifier=f"{m1.falsifier}; and {m2.falsifier}", rollback=f"{m1.rollback}; {m2.rollback}",
            counterargument=f"{m1.counterargument}; {m2.counterargument}; synergy is not assumed (independent "
                            "channels only)", lineage=("library", f"recombine:{m1.surface}+{m2.surface}"),
            kind="recombined",
            components=({"node": s1["node"], "mechanism": m1, "surface": s1}, {"node": s2["node"], "mechanism": m2,
                                                                              "surface": s2}))
        ok = all(s.get("consent_mechanism") for m, s in ((m1, s1), (m2, s2))
                 if m.third_parties_affected and not m.consented)
        combos.append((combo, {"consent_mechanism": "each affected component's consent path" if ok else None}))
    direct = None
    if "direct_labor" in p:
        d = p["direct_labor"]
        direct = Mechanism("direct_labor", "direct", "direct", d["description"], "work.perform",
                           d.get("consequence_class", "internal_write"),
                           d["effect"], 2 + 18 * d["confidence"], 0.0, d["cost_usd_per_cycle"] * horizon,
                           d["effort_hours_per_cycle"] * horizon, 0.0, 0.0, 0.0, "reversible", (), False,
                           ("knowledge",), 0.1, 0.1, 0.0, 0.0, 0.2,
                           "per-cycle gap at the bottleneck falls while the labour is paid",
                           "stop the labour; the gap returns", "repeated labour does not compound",
                           lineage=("problem.direct_labor",), kind="direct_labor")
    # Priority when the contract ceiling binds: library, direct labour, recombinations, then mutations.
    # Nothing is dropped silently: the report lists every candidate not evaluated.
    pool = base + ([(direct, {"node": bottleneck})] if direct else []) + combos + mutated
    dropped = [m.mechanism_id for m, _ in pool[MAX_CANDIDATES:]]
    pool = pool[:MAX_CANDIDATES]
    # 3. hard filter, then estimate only what is eligible
    held = set(p["constraints"]["held_authority"])
    rows, sims = [], {}
    for m, surface in pool:
        node = surface.get("node") if surface else None
        if not m.components:
            ctx["surface_node"][m.mechanism_id] = node
        reasons = eligibility(m, surface, p, reach)
        if m.components:
            node = max(m.components, key=lambda c: (reach.get(c["node"], (0.0,))[0], c["node"]))["node"]
        row = {"candidate_id": m.mechanism_id, "kind": m.kind, "surface": m.surface, "title": m.title,
               "lineage": list(m.lineage), "node": node,
               "eligibility": "ELIGIBLE" if not reasons else "REJECTED", "reasons": reasons,
               "harm_vector": m.harm_vector(), "reversibility": m.reversibility,
               "authority": _authority(m, held), "assets": list(m.assets)}
        if not reasons:
            xs = _simulate(m, p, world, ctx)
            sims[m.mechanism_id] = xs
            stats = _summary(xs)
            paths = [reach[c["node"]][1] for c in m.components] or [reach[node][1]]
            support = world.support(tuple(sorted({lid for path in paths for lid in path} | set(outcome_path))))
            evidence_trials = sum(_posterior(c["mechanism"], p)[2] for c in m.components) if m.components \
                else _posterior(m, p)[2]
            threshold = 0.05 * severity_expected * horizon
            pess = _simulate(m, p, world, ctx, effect_scale=0.5)
            pessimistic = {**_summary(pess), "p_meaningful": sum(x >= threshold for x in pess) / len(pess)}
            if m.components:
                miss = 1.0
                for c in m.components:
                    a, b, _ = _posterior(c["mechanism"], p)
                    miss *= 1.0 - a / (a + b) * reach[c["node"]][0]
                at_node = min(1.0, (1.0 - miss) / max(1e-9, reach[node][0]))
            else:
                a, b, _ = _posterior(m, p)
                at_node = a / (a + b)
            k = _posterior(m.components[0]["mechanism"] if m.components else m, p)
            evidence_weight = (k[0] + k[1]) / (k[0] + k[1] + 10.0)
            row.update(
                estimate={**stats, "p_meaningful": sum(x >= threshold for x in xs) / len(xs),
                          "meaningful_threshold": threshold, "path_support": support,
                          "evidence_trials": evidence_trials,
                          "evidence_basis": ("OBSERVED_OUTCOMES" if evidence_trials else
                                             "DECLARED_ESTIMATE" if m.kind == "direct_labor" else "PRIOR_ONLY"),
                          "pessimistic_mean": pessimistic["mean"],
                          "pessimistic_p_meaningful": pessimistic["p_meaningful"],
                          "effect_at_node": at_node * m.trigger_probability, "evidence_weight": evidence_weight},
                benefit={"p_meaningful": sum(x >= threshold for x in xs) / len(xs), "mean_closure": stats["mean"],
                         **{k: getattr(m, k) for k in BENEFIT_KEYS[2:]}},
                cost={**_costs(m, horizon), "authority_burden": row["authority"]["authority_burden"],
                      "dependency_capture": m.harm_vector()["dependency_capture"],
                      **{f"harm_{d}": v for d, v in m.harm_vector().items() if d != "dependency_capture"}},
                falsifier=m.falsifier, rollback=m.rollback, counterargument=m.counterargument)
        rows.append(row)
    # do-nothing is always a real, costed option
    zero = {"p_meaningful": 0.0, "mean_closure": 0.0, **dict.fromkeys(BENEFIT_KEYS[2:], 0.0)}
    rows.append({"candidate_id": "do_nothing", "kind": "baseline", "surface": None, "title": "retain the current state",
                 "lineage": ["baseline"], "node": bottleneck, "eligibility": "ELIGIBLE", "reasons": [],
                 "harm_vector": dict.fromkeys(HARM, 0.0), "reversibility": "reversible",
                 "authority": {"state": "NO_AUTHORITY_NEEDED", "consequence_class": "read_only",
                               "deferred_consequence_class": None, "authority_burden": 0.0},
                 "assets": [], "estimate": {"mean": 0.0, "p05": 0.0, "p50": 0.0, "p95": 0.0, "p_meaningful": 0.0,
                                            "meaningful_threshold": 0.05 * severity_expected * horizon,
                                            "path_support": 1.0, "evidence_trials": 0, "evidence_basis": "BASELINE",
                                            "pessimistic_mean": 0.0, "pessimistic_p_meaningful": 0.0,
                                            "effect_at_node": 0.0, "evidence_weight": 0.0},
                 "benefit": zero, "cost": dict.fromkeys(COST_KEYS, 0.0), "falsifier": "the gap stays where it is",
                 "rollback": "nothing to roll back", "counterargument": "the bottleneck persists"})
    sims["do_nothing"] = [0.0] * samples
    # 4. falsification flags, the control-point rule and the Pareto frontier
    estimated = [r for r in rows if r["eligibility"] == "ELIGIBLE"]
    dsims = sims.get("direct_labor")
    drow = next((r for r in estimated if r["candidate_id"] == "direct_labor"), None)
    for r in estimated:
        e = r["estimate"]
        flags = []
        if e["path_support"] < 0.5:
            flags.append("PATH_UNSUPPORTED")
        if e["evidence_basis"] == "PRIOR_ONLY":
            flags.append("PRIOR_ONLY_ESTIMATE")
        if r["kind"] != "baseline" and e["pessimistic_p_meaningful"] < PROBABLE <= e["p_meaningful"]:
            flags.append("ASSUMPTION_SENSITIVE")
        r["falsification_flags"] = flags
        r["defensible"] = (r["kind"] != "baseline" and e["p_meaningful"] >= PROBABLE and e["path_support"] >= 0.5
                           and bool(r["falsifier"]) and bool(r["rollback"]))
        if r["kind"] in ("baseline", "direct_labor"):
            r["vs_direct_labor"] = None
        elif dsims is None:
            r["vs_direct_labor"] = {"verdict": "NO_DIRECT_LABOR_BASELINE_DECLARED"}
        else:
            p_better = _p_greater(sims[r["candidate_id"]], dsims)
            cheaper = (r["cost"]["capital_usd"] <= drow["cost"]["capital_usd"]
                       and r["cost"]["effort_hours"] <= drow["cost"]["effort_hours"]) if drow else False
            verdict = ("DOMINATES" if p_better >= PROBABLE and cheaper
                       else "BEATS_ON_OUTCOME_ONLY" if p_better >= PROBABLE
                       else "NOT_DEMONSTRATED")
            r["vs_direct_labor"] = {"verdict": verdict, "p_outcome_at_least_direct": p_better, "cheaper": cheaper}
    front = set(frontier(estimated))
    for r in rows:
        r["pareto_frontier"] = r["candidate_id"] in front
    # 5. select: control points only where they dominate repeated direct labour; never by assumption
    budget, attention = max(1.0, p["constraints"]["budget_usd"]), max(1.0, p["constraints"]["founder_attention_hours"])

    def efficiency(r):
        c = r["cost"]
        burden = (1 + c["capital_usd"] / budget + c["founder_attention_hours"] / attention
                  + c["delay_days"] / (cycle_days * horizon) + c["effort_hours"] / (40.0 * horizon))
        return r["estimate"]["mean"] / burden

    pool_ok = [r for r in estimated if r["defensible"] and r["pareto_frontier"]]
    control = [r for r in pool_ok if r["kind"] != "direct_labor"
               and (r["vs_direct_labor"] or {}).get("verdict") in ("DOMINATES", "NO_DIRECT_LABOR_BASELINE_DECLARED")]
    order = sorted(control, key=lambda r: (-efficiency(r), r["candidate_id"]))
    if order:
        chosen, rule = order[0], ("control point dominates repeated direct labour on joint samples"
                                  if dsims is not None else "no direct-labour baseline declared; defensible "
                                  "control point over doing nothing")
    elif drow is not None and drow.get("defensible"):
        chosen, rule = drow, "no control point demonstrated dominance over repeated direct labour"
    else:
        chosen, rule = next(r for r in rows if r["candidate_id"] == "do_nothing"), \
            "no defensible route: retain the current state"
    # Without demonstrated dominance the remaining defensible frontier routes are value trade-offs (more
    # outcome for more cost, or less cash for more effort): the founder's judgment, never a hidden scalar.
    tradeoffs = sorted((r for r in pool_ok if r is not chosen and not dominates(chosen, r)
                        and r["candidate_id"] != "direct_labor"),
                       key=lambda r: (-r["estimate"]["mean"], r["candidate_id"]))
    def family(cid):                     # a route and its staged / deferred / consented variants are one family
        return cid.split(":")[0]

    rivals = sorted((r for r in pool_ok + ([drow] if drow is not None and drow.get("defensible") else [])
                     if family(r["candidate_id"]) != family(chosen["candidate_id"])),
                    key=lambda r: (-efficiency(r), r["candidate_id"]))
    runner = rivals[0] if rivals else None
    # 6. value of the next test (EVPI between the chosen route and its strongest rival)
    voi = _voi(chosen, runner, sims, p, rows)
    report = {
        "schema": VERSION, "problem_id": p["problem_id"], "objective": p["objective"], "as_of": p["as_of"],
        "inputs_digest": digest(problem), "seed": seed, "samples": samples, "horizon_cycles": horizon,
        "cycle_days": cycle_days,
        "bottleneck": {"node": bottleneck, "gap": nodes[bottleneck]["gap"], "expected_severity": severity_expected,
                       "outcome_path": list(outcome_path),
                       "rule": "egregore.leverage path math: gap x strongest evidenced path weight to the outcome"},
        "generated": {"library": len(base), "mutated": len(mutated), "recombined": len(combos),
                      "supplied_direct_labor": bool(direct), "ceiling": MAX_CANDIDATES,
                      "not_evaluated_over_ceiling": dropped},
        "candidates": rows, "selected": chosen["candidate_id"], "selection_rule": rule,
        "runner_up": runner["candidate_id"] if runner else None,
        "value_tradeoffs_for_founder": [r["candidate_id"] for r in tradeoffs],
        "value_of_information": voi,
        "control_point_rule": "a control point is preferred only where at least 80% of joint samples show it closes "
                              "at least as much gap as repeated direct labour at no greater capital or effort; "
                              "otherwise direct labour (or doing nothing) stays the recommendation",
        "estimate_status": "input_estimates_not_verified_outcomes",
        "authority_created": False, "executes": False,
    }
    report["interventions"] = interventions(report, p)
    report["asset_line"] = asset_line(chosen)
    report["preparable"] = preparable(report)
    report["decision_brief"] = decision_brief(report)
    report["receipt_id"] = digest({k: v for k, v in report.items() if k != "receipt_id"})
    return report


def _voi(chosen: dict, runner: dict | None, sims: dict, p: dict, rows: list[dict]) -> dict:
    if runner is None or chosen["candidate_id"] == "do_nothing":
        return {"state": "NO_RIVAL", "evpi_closure": 0.0}
    value = p["constraints"].get("value_per_unit_gap_usd")
    xa, xb = sims[chosen["candidate_id"]], sims[runner["candidate_id"]]
    if value is None:
        evpi = sum(max(a, b) for a, b in zip(xa, xb)) / len(xa) - max(sum(xa), sum(xb)) / len(xa)
        return {"state": "NOT_MONETISED", "evpi_closure": evpi, "rival": runner["candidate_id"],
                "note": "no value_per_unit_gap_usd declared; information value is in gap units only"}
    na = [a * value - chosen["cost"]["capital_usd"] for a in xa]
    nb = [b * value - runner["cost"]["capital_usd"] for b in xb]
    pairs = sorted(zip(na, nb), key=lambda t: t[0] - t[1])
    buckets = 20
    size = len(pairs) // buckets
    scenarios = []
    for i in range(buckets):
        chunk = pairs[i * size:(i + 1) * size] if i < buckets - 1 else pairs[i * size:]
        scenarios.append({"probability": len(chunk) / len(pairs),
                          "best_value": max(sum(a for a, _ in chunk) / len(chunk), sum(b for _, b in chunk) / len(chunk))})
    prior = max(sum(na) / len(na), sum(nb) / len(nb))
    staged = next((r for r in rows if r["candidate_id"] == chosen["candidate_id"] + ":staged"
                   and r["eligibility"] == "ELIGIBLE"), None)
    gross = sum(s["probability"] * s["best_value"] for s in scenarios) - prior
    best = chosen["candidate_id"] if sum(na) >= sum(nb) else runner["candidate_id"]
    common = {"rival": runner["candidate_id"], "evpi_usd_banded": gross, "monetised_prior_best": best,
              "monetised_means_usd": {chosen["candidate_id"]: sum(na) / len(na),
                                      runner["candidate_id"]: sum(nb) / len(nb)}}
    if staged is None:
        why = ("the selected route is itself a staged pilot: acting is the test" if chosen["candidate_id"]
               .endswith(":staged") else "no eligible staged pilot exists for the selected route")
        return {"state": "MONETISED_NO_TEST", **common, "test": None, "test_may_pay": False, "note": why}
    test_cost = staged["cost"]["capital_usd"]
    return {"state": "MONETISED", **common, "test": staged["candidate_id"], "test_cost_usd": test_cost,
            "test_may_pay": gross > test_cost,
            "cognition_request": {"posterior_scenarios": scenarios, "prior_best_value": prior, "cost": test_cost},
            "note": "upper bound: the value of learning which of 20 equal-probability outcome bands holds. Below the "
                    "test cost it rules the staged pilot out; above it the pilot may pay, never must. The canonical "
                    "cognition value_of_information family re-derives the same quantity independently"}


# ------------------------------------------------------------------ outputs
def interventions(report: dict, p: dict) -> list[dict]:
    """Frontier candidates as institutional-leverage records the existing ranker accepts unchanged."""
    overrides = p.get("mechanism_overrides", {})
    surfaces = {s["surface"]: s for s in p["surfaces"]}
    out = []
    for r in report["candidates"]:
        if r["candidate_id"] == "do_nothing" or r["eligibility"] != "ELIGIBLE" or not r["pareto_frontier"]:
            continue
        base_id = r["candidate_id"].split("+")[0].split(":")[0]
        m = BY_ID.get(base_id)
        refs = set()
        for part in str(r["surface"]).split("+"):
            refs |= set(surfaces.get(part, {}).get("evidence_refs", []))
        if r["kind"] == "direct_labor":
            refs |= set(p["direct_labor"]["evidence_refs"])
            action = {"action_class": "work.perform", "requested_capability": "work.perform",
                      "target": f"bottleneck:{report['bottleneck']['node']}",
                      "consequence_class": r["authority"]["consequence_class"]}
            mech = "direct"
        else:
            target = overrides.get(base_id, {}).get("target", f"proposal:{r['surface']}:{r['node']}")
            action = {"action_class": m.action_class, "requested_capability": m.action_class, "target": target,
                      "consequence_class": r["authority"]["consequence_class"]}
            mech = "coordination" if r["kind"] == "recombined" else m.leverage_mechanism
        for key, ev in p.get("evidence", {}).items():
            if key in (base_id, r["surface"]):
                refs |= set(ev["refs"])
        record = {
            "id": r["candidate_id"], "node": r["node"], "mechanism": mech,
            "effect": round(min(1.0, r["estimate"]["effect_at_node"]), 6),
            "confidence": round(r["estimate"]["evidence_weight"], 6),
            "harm": round(max(r["harm_vector"].values()), 6),
            "cost_usd": r["cost"]["capital_usd"], "effort_hours": r["cost"]["effort_hours"],
            "delay_days": r["cost"]["delay_days"],
            "action": {**action, "payload": {"lawful_leverage": {
                "problem_id": report["problem_id"], "harm_vector": r["harm_vector"], "assets": r["assets"],
                "authority_state": r["authority"]["state"], "estimate": {k: r["estimate"][k] for k in
                                                                       ("mean", "p05", "p95", "p_meaningful")},
                "falsification_flags": r.get("falsification_flags", [])}}},
            "expected_outcome": r["title"], "success_measure": r["falsifier"], "rollback": r["rollback"],
            "counterargument": r["counterargument"], "evidence_refs": sorted(refs)[:32],
        }
        out.append(ranker._validate("intervention", record))
    return out


def asset_line(chosen: dict) -> dict:
    """Section 20: every closed cycle should leave a durable asset; say which, and which are still pending."""
    planned = sorted(set(chosen.get("assets", [])) & set(ASSETS))
    return {"route": chosen["candidate_id"], "planned_assets": planned,
            "pending_until_verified": ["verified_precedent", "evidence"],
            "loop": "advantage -> asset -> capability -> better sensing -> better routing -> stronger intervention "
                    "-> verified result -> stronger asset",
            "state": "PLANNED_NOT_REALISED" if planned else "NO_DURABLE_ASSET"}


def preparable(report: dict) -> list[dict]:
    """What GREG may prepare under authority it already holds: measurement and drafts, never the effect."""
    steps = [{"step": "measure the falsifier baseline at the bottleneck", "consequence_class": "read_only",
              "for": report["selected"]}]
    for r in report["candidates"]:
        if r["candidate_id"] == report["selected"] and r["authority"]["state"] != "NO_AUTHORITY_NEEDED":
            steps.append({"step": f"prepare, do not send: {r['title']}", "consequence_class": "internal_write",
                          "for": r["candidate_id"]})
    return steps


def decision_brief(report: dict) -> dict | None:
    """The minimum founder decision as the keyword arguments of ``greg.asks.resource_request``.

    Facts, costed options (one costs nothing), uncertainty and the authority asked for; no pressure.
    The Foundry never records an ask: GREG's side validates, screens and (on the body) records it.
    """
    chosen = next(r for r in report["candidates"] if r["candidate_id"] == report["selected"])
    held = chosen["authority"]["state"] in ("WITHIN_HELD_AUTHORITY_GATE_REQUIRED", "NO_AUTHORITY_NEEDED")
    if held and not report["value_tradeoffs_for_founder"]:
        return None
    by_id = {r["candidate_id"]: r for r in report["candidates"] if r["eligibility"] == "ELIGIBLE"}
    alts = [cid for cid in [report["selected"], report.get("runner_up"), *report["value_tradeoffs_for_founder"][:3],
                            "direct_labor"] if cid and cid in by_id and cid != "do_nothing"]
    options = []
    for cid in dict.fromkeys(alts):
        r = by_id[cid]
        options.append({"option": f"{cid}: {r['title']}",
                        "cost": f"${r['cost']['capital_usd']:.0f} capital, {r['cost']['effort_hours']:.0f} effort hours,"
                                f" {r['cost']['founder_attention_hours']:.1f} founder hours",
                        "expected_effect": f"cumulative gap closure {r['estimate']['p05']:.3f} to "
                                           f"{r['estimate']['p95']:.3f} (p05 to p95), mean {r['estimate']['mean']:.3f}, "
                                           f"probability of a meaningful closure {r['estimate']['p_meaningful']:.2f}"})
    options.append({"option": "do_nothing: retain the current state",
                    "cost": f"none; the bottleneck {report['bottleneck']['node']} stays at gap "
                            f"{report['bottleneck']['gap']:.2f}",
                    "expected_effect": "no change at the bottleneck"})
    e = chosen["estimate"]
    return dict(
        request_id=f"leverage-{report['problem_id']}"[:96], kind="leverage_route", resource="mandate",
        why_now=(f"{report['bottleneck']['node']} is the largest evidenced gap reaching the outcome; " +
                 (f"the selected route needs consequence class {chosen['authority']['consequence_class']}, which "
                  f"this objective does not hold" if not held else
                  f"no route dominates the others, so choosing among {len(report['value_tradeoffs_for_founder'])} "
                  f"trade-offs is a value judgment")),
        recommendation=f"{chosen['candidate_id']}: {chosen['title']} ({report['selection_rule']})",
        evidence={"bottleneck": report["bottleneck"], "estimate": e, "harm_vector": chosen["harm_vector"],
                  "vs_direct_labor": chosen.get("vs_direct_labor"), "falsification_flags":
                  chosen.get("falsification_flags", []), "value_of_information": {
                      k: v for k, v in report["value_of_information"].items() if k != "cognition_request"}},
        options=options,
        expected_effect=f"mean cumulative gap closure {e['mean']:.3f} over {report['horizon_cycles']} cycles; "
                        f"probability of a meaningful closure {e['p_meaningful']:.2f}",
        uncertainty=f"estimates rest on {e['evidence_trials']} observed trials "
                    f"({e['evidence_basis']}); path support {e['path_support']:.2f}; with effects halved the "
                    f"probability of a meaningful closure is {e['pessimistic_p_meaningful']:.2f}",
        authority_requested={"consequence_class": chosen["authority"]["consequence_class"],
                             "deferred_consequence_class": chosen["authority"]["deferred_consequence_class"],
                             "spend": (f"up to ${chosen['cost']['capital_usd']:.0f} for this route only"
                                       if chosen["cost"]["capital_usd"] else "none"),
                             "scope": f"objective {report['objective']}; through the existing Gate only"},
        consequence_of_no_response="nothing executes; preparable steps stay prepared and unsent; the question "
                                   "returns only if the bottleneck or the evidence changes",
        created_at=report["as_of"], falsifier=chosen["falsifier"], rollback=chosen["rollback"])


def mechanism_card() -> list[dict]:
    """The reviewed library as data (for review, tests and the founder): no hidden templates."""
    return [{**asdict(m), "harm": dict(m.harm)} for m in LIBRARY]
