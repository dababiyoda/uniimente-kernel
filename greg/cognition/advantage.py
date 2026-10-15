"""Lawful Asymmetric Advantage Compiler: generate interventions at evidenced control points, never rank by fiat.

Founder directive 2026-10-07: build an intervention *generator*, not only a ranker; translate "systemic
dominance" as superior lawful capability, "deterrence" as lawful accountability, and keep victim
protection and minimal collateral harm; classify buildability; backcast frontier goals.

Mechanism (mental models compiled to typed operators):

    evidenced control map (egregore/leverage schema) -> bottlenecks on an evidenced path to the outcome
    -> each typed OPERATOR whose node kinds match -> lawful-means gate -> buildability from GREG's real
    capability registry and genome library -> candidate with backcast, next experiment, rollback,
    counterargument and collateral -> UNESTIMATED until evidence supplies effect, confidence and harm
    -> ``to_interventions`` hands estimated candidates to the existing ranker
       (``egregore.leverage.propose_institutional_leverage``); this module never invents magnitudes.

Structural priority (shown, not used as an outcome estimate): bottleneck severity from the evidenced map,
then the number of Spider-Web control points strengthened, compounding, reversibility, buildability.
Building the compiler authorizes nothing: every candidate keeps its consequence class and the founder
grant it would need.

Track B convergence (2026-10-15): the canonical intervention generator is #158's Lawful Leverage Foundry
(``foundry.lawful_leverage``), which hard-filters, estimates and hands survivors to the ranker; candidates from
``compile_map`` stay UNESTIMATED and the ranker drops them. Every operator here now has a canonical Foundry
mechanism (``FOUNDRY_MECHANISM``): five had an equivalent and seven were ported into the Foundry library
(``lawful_leverage.PORTED_FROM``), the accountability operator as four legal channels. ``compile_map`` is a
historical, read-only structural view (``greg cognition advantage``): it generates nothing the Foundry lacks
and its operator table is pinned. The destinations below remain the live buildability view of the Backcast GPS
horizons.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from greg.cognition.contracts import CognitionError

CONTROL_POINTS = ("eligibility", "routing", "proof", "settlement", "reliability", "capability_formation",
                  "compounding")
NODE_KINDS = ("actor", "rule", "incentive", "idea", "resource", "process", "outcome")
MECHANISMS = ("direct", "rule", "incentive", "frame", "doctrine", "coordination")
BUILDABILITY = ("BUILDABLE_NOW", "EXPERIMENTAL_NOW", "FRONTIER_RESEARCH", "SCIENCE_FICTION_DESCENDANT")
LAWFUL_MEANS = ("build_software", "publish_verified_record", "offer_voluntary_service", "contract_with_consent",
                "comply_verifiably", "truthful_advocacy", "voluntary_coordination", "open_standard", "price_offer",
                "lawful_report")
PROHIBITED_MEANS = ("coercion", "deception", "bribery", "unauthorized_access", "covert_surveillance", "collusion",
                    "predatory_exclusion", "exploiting_vulnerable_people", "harassment", "impersonation",
                    "resisting_shutdown", "control_over_people")
MATURITY = {"present": 0, "commodity": 0, "experimental": 1, "frontier": 2, "science_fiction": 3}
CONSEQUENCE = {"build_software": "internal_write", "publish_verified_record": "external_contact",
               "offer_voluntary_service": "external_contact", "contract_with_consent": "financial",
               "comply_verifiably": "internal_write", "truthful_advocacy": "external_contact",
               "voluntary_coordination": "external_contact", "open_standard": "external_contact",
               "price_offer": "financial", "lawful_report": "external_contact"}
RANK = ("read_only", "internal_write", "external_contact", "financial", "irreversible")


@dataclass(frozen=True)
class Operator:
    id: str
    model: str                       # the mental model this operator compiles
    kinds: tuple[str, ...]
    control_points: tuple[str, ...]
    mechanism: str
    means: tuple[str, ...]
    capabilities: tuple[tuple[str, str], ...]     # (capability id, maturity if GREG lacks it)
    compounding: bool
    reversible: bool
    outcome: str
    measure: str
    experiment: str
    rollback: str
    counterargument: str
    collateral: str


def _op(id, model, kinds, cps, mechanism, means, caps, compounding, reversible, outcome, measure, experiment,
        rollback, counter, collateral):
    return Operator(id, model, kinds, cps, mechanism, means, caps, compounding, reversible, outcome, measure,
                    experiment, rollback, counter, collateral)


OPERATORS = (
    _op("proof_substrate", "trust bottleneck -> make the outcome provable", ("process", "outcome", "actor"),
        ("proof", "eligibility", "compounding"), "coordination",
        ("build_software", "publish_verified_record", "contract_with_consent"),
        (("cognition.evidence", "present"), ("artifact.store", "present"), ("worker.appraise", "present")),
        True, True, "{label}: outcomes carry receipts a counterparty can check without trusting the claimant",
        "share of {label} transactions accepted on a verified receipt",
        "issue receipts for 10 consenting {label} transactions; measure counterparty acceptance and dispute time",
        "stop issuing receipts; issued records stay with their owners",
        "counterparties may not value receipts they did not ask for",
        "participants whose records become visible: consent, minimisation and correction rights"),
    _op("eligibility_packet", "pre-qualification removes manual vetting", ("actor", "rule"),
        ("eligibility", "routing"), "rule", ("build_software", "comply_verifiably", "offer_voluntary_service"),
        (("cognition.evidence", "present"), ("cognition.formal", "present"), ("fs.write", "present")),
        True, True, "{label}: participants arrive pre-qualified against the rule, checkably",
        "vetting time and rejection rate for {label} before vs after",
        "compile the {label} rule into a checkable model; pre-qualify 10 consenting applicants; compare vetting time",
        "withdraw packets; applicants keep their own documents",
        "the gatekeeper may refuse third-party qualification",
        "applicants wrongly excluded by an encoding error: human review of every refusal"),
    _op("settlement_on_proof", "pay on verified outcome, not on promise", ("resource", "process"),
        ("settlement", "proof"), "incentive", ("contract_with_consent", "build_software"),
        (("cognition.evidence", "present"), ("payments.escrow", "commodity")), True, False,
        "{label}: payment releases when the verified outcome occurs",
        "days from outcome to settlement and dispute rate for {label}",
        "one consenting pair settles one {label} transaction through a regulated escrow provider",
        "return escrowed funds under the provider's terms",
        "regulatory licensing for money transmission; use a licensed provider",
        "payers and payees: funds held by a licensed third party, never by GREG"),
    _op("default_pathway", "become the route the workflow already takes", ("process", "actor"),
        ("routing", "compounding"), "coordination", ("build_software", "offer_voluntary_service", "open_standard"),
        (("browser.session", "present"), ("cognition.formal", "present")), True, True,
        "{label}: the existing workflow routes through the offering without a behaviour change",
        "share of {label} flow that passes through the integration",
        "integrate with one incumbent tool used for {label}; measure adoption without a sales call",
        "remove the integration; the incumbent flow is unchanged",
        "platform terms may forbid the integration", "incumbent users: no lock-in; export always available"),
    _op("counter_position", "a model the incumbent cannot copy without harming itself", ("actor", "incentive"),
        ("compounding",), "doctrine", ("offer_voluntary_service", "price_offer", "truthful_advocacy"),
        (("venture.assess", "present"), ("cognition.game", "present")), True, True,
        "{label}: an offer whose copying would cannibalise the incumbent's own revenue",
        "incumbent response time and share of {label} customers switching",
        "price one offer against {label}'s incumbent; record whether it can match without self-harm",
        "withdraw the offer", "the incumbent may cross-subsidise to match",
        "incumbent employees and customers: compete on value, never on disparagement"),
    _op("constraint_to_advantage", "turn a binding rule into a verified qualification", ("rule",),
        ("eligibility", "proof"), "rule", ("comply_verifiably", "publish_verified_record"),
        (("cognition.formal", "present"), ("cognition.evidence", "present")), True, True,
        "{label}: verified compliance becomes the qualification others lack",
        "time to qualify and share of competitors qualified under {label}",
        "encode {label}; verify one compliant process; ask one buyer whether it changes selection",
        "stop publishing the compliance record", "the rule may change or be weakly enforced",
        "regulated parties: compliance help offered, never weaponised complaints"),
    _op("aggregate_fragmented", "pool fragmented supply into one coordinated rail", ("actor", "resource"),
        ("routing", "compounding", "settlement"), "coordination", ("voluntary_coordination", "contract_with_consent"),
        (("cognition.crowd", "present"), ("cognition.optimization", "present")), True, True,
        "{label}: fragmented participants transact through one coordinated pool",
        "matched volume and unit cost for {label}",
        "pool 5 consenting {label} participants for one matched transaction; compare unit cost",
        "dissolve the pool; participants keep their relationships",
        "antitrust: coordinate supply, never prices among competitors",
        "small participants: voluntary entry and exit, transparent allocation"),
    _op("remove_single_point", "redundancy where one failure stops the outcome", ("process", "resource", "actor"),
        ("reliability",), "direct", ("build_software", "contract_with_consent"),
        (("cognition.graph", "present"), ("worker.commission", "present")), False, True,
        "{label}: the outcome survives the failure of {label}",
        "outcome availability when {label} fails (drill)",
        "map alternatives to {label}; run one failure drill", "remove the redundant path",
        "redundancy costs money that may exceed the expected loss", "none beyond cost"),
    _op("data_flywheel", "every transaction improves the next", ("process", "outcome"),
        ("compounding", "capability_formation", "routing"), "coordination", ("build_software", "contract_with_consent"),
        (("cognition.settle", "present"), ("memory.precedents", "present")), True, True,
        "{label}: settled outcomes route the next {label} transaction better",
        "routing accuracy on held-out {label} transactions after N settlements",
        "settle 20 {label} outcomes; compare learned vs static routing on fresh ones (P4-style)",
        "freeze routing at the static policy", "the data may not predict (P4 v1/v2 were inconclusive)",
        "data subjects: purpose-limited, consented use only"),
    _op("accountable_transparency", "lawful deterrence: make misconduct costly by verified records",
        ("actor", "incentive", "outcome"), ("proof", "reliability"), "frame",
        ("publish_verified_record", "lawful_report", "truthful_advocacy"),
        (("cognition.cortex.deterrence.accountability", "present"), ("cognition.evidence", "present")), True, True,
        "{label}: misconduct carries a verified, proportionate record and a lawful report path",
        "incidence of the harmful conduct at {label} after records exist",
        "with consenting victims, document one {label} incident to evidentiary standard; file through the lawful channel",
        "withdraw publication of unadjudicated claims", "naming before adjudication risks defamation",
        "victims first: consent, safety and anonymity; accused: accuracy, right of reply"),
    _op("regenerative_incentive", "participants become more capable inside the rail", ("actor", "incentive"),
        ("compounding", "eligibility", "capability_formation"), "incentive", ("offer_voluntary_service", "price_offer"),
        (("venture.assess", "present"), ("cognition.probabilistic", "present")), True, True,
        "{label}: each transaction raises the participant's own eligibility and capability",
        "participant eligibility and retention at {label} after 3 cycles",
        "offer one capability-building benefit tied to verified completion at {label}; measure retention",
        "end the benefit with notice", "benefits may attract opportunists rather than builders",
        "participants: no dependency traps, portable records, exit without penalty"),
    _op("remove_step", "via negativa: delete a step instead of adding one", ("process", "rule"),
        ("routing", "reliability"), "direct", ("build_software", "comply_verifiably"),
        (("cognition.formal", "present"),), False, True,
        "{label}: the outcome occurs without the step", "cycle time and error rate without {label}",
        "run one {label} cycle without the step under a formal check that obligations still hold",
        "restore the step", "the step may encode a hidden obligation", "none if the formal check holds"),
)


# Each operator's canonical mechanism in the Foundry library (tested both ways in test_greg_mind_convergence.py).
FOUNDRY_MECHANISM = {"proof_substrate": ("proof.verifiable_receipts",),
                     "eligibility_packet": ("eligibility.published_standard",),
                     "settlement_on_proof": ("settlement.milestone_escrow",),
                     "default_pathway": ("defaults.incumbent_integration",),
                     "counter_position": ("incentives.counter_position",),
                     "constraint_to_advantage": ("standards.verified_compliance",),
                     "aggregate_fragmented": ("coordination.consented_pool",),
                     "remove_single_point": ("dependency.second_source",),
                     "data_flywheel": ("routing.evidence_triage",),
                     # split by legal channel: each has its own lawful basis, access, evidence and authorization
                     "accountable_transparency": ("proof.evidence_preservation", "proof.confidential_review",
                                                  "proof.authority_submission", "proof.public_publication"),
                     "regenerative_incentive": ("incentives.regenerative_benefit",),
                     "remove_step": ("workflow.remove_step",)}
# The operator table is historical (Track B): it no longer evolves here. Extend the Foundry library instead; a
# test pins this digest so an edit to OPERATORS cannot quietly create a second, independently evolving generator.


def lawful(operator: Operator) -> list[str]:
    problems = []
    for means in operator.means:
        if any(word in means for word in PROHIBITED_MEANS):
            problems.append(f"unlawful means: {means}")
        elif means not in LAWFUL_MEANS:
            problems.append(f"means outside the lawful vocabulary: {means}")
    if operator.mechanism not in MECHANISMS or set(operator.control_points) - set(CONTROL_POINTS):
        problems.append("mechanism or control point outside the closed vocabulary")
    if set(operator.kinds) - set(NODE_KINDS):
        problems.append("node kind outside the closed vocabulary")
    return problems


def _present() -> dict:
    from greg.capabilities import BUILTINS
    from .genome_library import inventory
    admission = {e.genome_id: e.admission for e in inventory()}
    return {cid: admission.get(cid, "PRESENT") for cid in BUILTINS}


def buildability(capabilities, present=None) -> tuple[str, list[dict]]:
    present = _present() if present is None else present
    worst, steps = 0, []
    for cid, maturity in capabilities:
        if maturity not in MATURITY:
            raise CognitionError(f"unknown maturity {maturity!r}")
        if cid in present:
            level = 1 if present[cid] in ("EXPERIMENTAL", "REJECTED") else 0
            steps.append({"capability": cid, "state": f"in GREG ({present[cid].lower()})",
                          "step": "founder attach if not attached" if level == 0 else "admit by native benchmark"})
        else:
            level = MATURITY[maturity]
            steps.append({"capability": cid, "state": f"absent; {maturity}",
                          "step": {"commodity": "acquire via Capability Genesis (provider or open source)",
                                   "present": "acquire via Capability Genesis (provider or open source)",
                                   "experimental": "build and benchmark against the simplest baseline",
                                   "frontier": "research program with a falsifiable milestone",
                                   "science_fiction": "keep the destination; compile its effect; build the "
                                                      "strongest real approximation"}[maturity]})
        worst = max(worst, level)
    return BUILDABILITY[worst], steps


def compile_map(leverage_map: dict, request: dict, *, operators=OPERATORS) -> dict:
    """Generate lawful candidate interventions at the evidenced bottlenecks of a control map."""
    from egregore.leverage import _paths_to
    nodes = {n["id"]: n for n in leverage_map["nodes"]}
    links = {l["id"]: l for l in leverage_map["links"]}
    for l in links.values():
        if l["source"] not in nodes or l["target"] not in nodes:
            raise CognitionError("link endpoint outside the map")
    if request["outcome_node"] not in nodes:
        raise CognitionError("outcome node outside the map")
    reach = _paths_to(request["outcome_node"], links, request.get("max_hops", 6))
    bottlenecks = sorted(({"node": nid, "severity": round(nodes[nid]["gap"] * w, 9), "path": list(p)}
                          for nid, (w, p) in reach.items() if nodes[nid]["gap"] > 0),
                         key=lambda b: (-b["severity"], b["node"]))
    present, candidates, refused = _present(), [], []
    for op in operators:
        problems = lawful(op)
        if problems:
            refused.append({"operator": op.id, "reasons": problems})
            continue
        for b in bottlenecks:
            node = nodes[b["node"]]
            if node["kind"] not in op.kinds:
                continue
            label = node["label"]
            level, steps = buildability(op.capabilities, present)
            consequence = max((CONSEQUENCE[m] for m in op.means), key=RANK.index)
            candidates.append({
                "id": f"{op.id}@{b['node']}", "operator": op.id, "mental_model": op.model, "node": b["node"],
                "canonical_foundry_mechanisms": list(FOUNDRY_MECHANISM[op.id]),
                "label": label, "control_points": list(op.control_points), "mechanism": op.mechanism,
                "means": list(op.means), "lawful": True, "buildability": level, "backcast": steps,
                "consequence_class": consequence,
                "authority_required": "none beyond development" if consequence in ("read_only", "internal_write")
                else f"founder grant for {consequence} before any external step",
                "structural_priority": [b["severity"], len(op.control_points), op.compounding, op.reversible,
                                        -BUILDABILITY.index(level)],
                "estimate_status": "UNESTIMATED: effect, confidence and harm need evidence before ranking",
                "expected_outcome": op.outcome.format(label=label), "success_measure": op.measure.format(label=label),
                "next_experiment": op.experiment.format(label=label), "rollback": op.rollback,
                "counterargument": op.counterargument, "collateral": op.collateral,
                "evidence_refs": list(node["evidence_refs"]), "bottleneck_path": b["path"]})
    candidates.sort(key=lambda c: (-c["structural_priority"][0], -c["structural_priority"][1],
                                   not c["structural_priority"][2], not c["structural_priority"][3],
                                   -c["structural_priority"][4], c["id"]))
    return {"schema": "greg-advantage-compiler/0.1", "objective": request["objective"],
            "bottlenecks": bottlenecks, "candidates": candidates, "refused_operators": refused,
            "baseline": "do nothing (always kept by the ranker)",
            "canonical_generator": "foundry.lawful_leverage: the same operators, hard-filtered and estimated",
            "historical_view": "superseded generator kept read-only; use `greg gravity` (the Foundry) to act",
            "authority_created": False}


def to_interventions(candidates: list[dict], estimates: dict) -> list[dict]:
    """Merge evidence-backed estimates into the existing leverage schema; unestimated candidates are dropped."""
    required = ("effect", "confidence", "harm", "cost_usd", "effort_hours", "delay_days", "evidence_refs", "action")
    out = []
    for c in candidates:
        e = estimates.get(c["id"])
        if e is None:
            continue
        missing = [k for k in required if k not in e]
        if missing or not e["evidence_refs"]:
            raise CognitionError(f"{c['id']}: estimates need {', '.join(missing) or 'evidence_refs'}")
        row = {"id": c["id"], "node": c["node"], "mechanism": c["mechanism"], "effect": e["effect"],
               "confidence": e["confidence"], "harm": e["harm"], "cost_usd": e["cost_usd"],
               "effort_hours": e["effort_hours"], "delay_days": e["delay_days"], "action": e["action"],
               "expected_outcome": c["expected_outcome"], "success_measure": c["success_measure"],
               "rollback": c["rollback"], "counterargument": c["counterargument"], "evidence_refs": e["evidence_refs"]}
        if c["mechanism"] in ("frame", "doctrine"):
            if "narrative" not in e:
                raise CognitionError(f"{c['id']}: frame and doctrine routes need an evidence-linked narrative")
            row["narrative"] = e["narrative"]
        out.append(row)
    return out


# ------------------------------------------------------------------ founder destinations, compiled and backcast
@dataclass(frozen=True)
class Destination:
    expression: str
    literal: str                     # buildability of the literal wording
    effect: str                      # the compiled, falsifiable effect
    capabilities: tuple[tuple[str, str], ...]
    falsifier: str
    horizon: str                     # its horizon on the one Backcast GPS (greg/path.json)


# The Founder Effect Compiler's six examples. Each is placed on greg/path.json (``horizon``): this table is a live
# buildability view of those horizons from the genome inventory, not a second Backcast GPS.
DESTINATIONS = (
    Destination("Become omniscient about my businesses", "SCIENCE_FICTION_DESCENDANT",
                "minimise decision-relevant unknowns with authorized data, freshness and stated uncertainty",
                (("brief.freshness", "present"), ("memory.precedents", "present"), ("cognition.evidence", "present"),
                 ("connectors.business_data", "commodity")),
                "a founder decision made with a material fact GREG had authorized access to but did not surface",
                "decision_relevant_knowledge"),
    Destination("Make UNIIMENTE immortal", "SCIENCE_FICTION_DESCENDANT",
                "intent and capability survive component failure: durable ledger, backups, replaceable models, succession",
                (("artifact.store", "present"), ("cognition.cortex", "present"), ("backup.offsite", "commodity"),
                 ("succession.legal", "commodity")),
                "a restore drill loses founder intent, ledger history or the ability to swap the model", "continuity"),
    Destination("Heal yourself", "BUILDABLE_NOW",
                "detect lost function, localise it, repair or replace it, verify restoration, resume work",
                (("worker.appraise", "present"), ("repo.integration_audit", "present"), ("worker.commission", "present")),
                "an injected fault is not detected, or the mission does not resume after repair", "capability_genesis"),
    Destination("Grow a new organ", "BUILDABLE_NOW",
                "a recurring deficit becomes a bounded subsystem with contracts, tests, lifecycle and shutdown",
                (("cognition.compose", "present"), ("foundry.apply", "present")),
                "a formed capability is used once and never again, or bypasses founder attach", "persistent_organs"),
    Destination("Give UNIIMENTE an immune system", "BUILDABLE_NOW",
                "detect, contain, recover from and learn from attacks and failures without autoimmune refusal",
                (("cognition.robust_pattern", "present"), ("cognition.protection", "present"),
                 ("intrusion.detection", "commodity")),
                "a replayed incident is missed, or legitimate novelty is quarantined", "immune_function"),
    Destination("Watch over and protect me in the physical world", "SCIENCE_FICTION_DESCENDANT",
                "lawful situational awareness from public and consented data with early warning and escalation",
                (("http.get", "present"), ("feeds.public_safety", "commodity"), ("location.consented", "commodity"),
                 ("perception.ubiquitous", "science_fiction")),
                "a public, available warning relevant to the founder's consented location is not surfaced",
                "situational_awareness"),
)


def backcast(destination: Destination) -> dict:
    present = _present()
    real = tuple(c for c in destination.capabilities if c[1] != "science_fiction")
    level, steps = buildability(real, present)
    _, full = buildability(destination.capabilities, present)
    return {"expression": destination.expression, "horizon": destination.horizon, "literal": destination.literal,
            "effect": destination.effect,
            "compiled_effect_buildability": level, "backcast": full, "falsifier": destination.falsifier,
            "kept_on_horizon": [s["capability"] for s in full if "science_fiction" in s["state"]]}


def export() -> dict:
    return {"operators": [asdict(o) for o in OPERATORS], "destinations": [backcast(d) for d in DESTINATIONS]}
