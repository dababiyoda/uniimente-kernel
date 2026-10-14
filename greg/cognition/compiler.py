"""Layer 5 Competency Compiler: geometry -> the smallest competent intelligence or composition -> typed evidence.

Founder directive 2026-10-07, sections 8-12. One more request shape on GREG's one cognition entry
(``cognition.reason``: ``{"problem_id", "compile": {...}}``); it chooses among the methods the existing
catalog, the executable IntelligenceGenome library and the composition recipes already provide, runs the
choice through the same ``reason`` (isolated worker, independent verifier, receipt), and returns a
compilation receipt. It owns no solver, registry, ledger, authority or event plane.

    observe request -> characterise geometry (unknowns stay unknown) -> constitutional pre-filter
      (PROHIBITED; THIS REQUIRES QUALIFIED HUMAN JUDGMENT) -> consequence raises requirements (never
      routes the world to SMT) -> mental-model operators transform the representation -> candidate
      methods by native geometry and inputs -> exclude what frozen negative evidence rejected ->
      rank (admission status, settled conditional competence, cost, latency) -> execute through
      reason -> receipt with every directive field -> CAPABILITY_DEFICIT for Genesis when nothing fits

Epistemic routing (which method can reason about this) stays separate from authority routing (what may
become real): every receipt carries ``authority_state: EXISTING_KERNEL_GATE_REQUIRED`` and
``authority_created: false``; high solver confidence, a formal proof or a VPL gain never authorises.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
import json
from pathlib import Path
import time

from .contracts import CognitionError, canonical, digest, strict_data

SCHEMA = "greg-competency-compilation/0.1"
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_INDEX = ROOT / "docs" / "evidence" / "greg-mind-evidence-index.json"
HIGH_CONSEQUENCE = ("external_contact", "financial", "irreversible")
HUMAN_CLASSES = ("normative", "legal", "institutional_acceptance")
HUMAN_ROLES = ("founder", "operator", "domain_expert", "affected_participant", "auditor", "customer",
               "professional", "regulator")
STATUS_RANK = {"DEFAULT_FOR_GEOMETRY": 0, "NICHE_CAPABILITY": 1, "UNEVALUATED": 2, "CONSTRUCTED_VERIFIED": 2,
               "EXPERIMENTAL": 3, "NO_LIFT": 8,
               "COMPOSITION_ONLY": 9, "SUPERSEDED": 9, "REJECTED": 9, "FRONTIER_HORIZON": 9}
EXCLUDED = ("SUPERSEDED", "REJECTED", "FRONTIER_HORIZON", "COMPOSITION_ONLY")
# Inputs that identify an existing (pre-genome) family's native geometry.
NATIVE_INPUTS = {
    "estimate": ("factors",), "constraints": ("variables", "constraints"),
    "optimize": ("variables", "constraints", "objective"), "shortest_path": ("edges", "start", "goal"),
    "beta_update": ("alpha", "beta", "successes", "failures"), "treatment_effect": ("treated", "control"),
    "pid": ("observed", "target", "correction_limit"), "value_of_information": ("posterior_scenarios",
                                                                                "prior_best_value", "cost"),
    "simulate": ("seed", "samples", "steps", "step_probability"), "minimax": ("payoffs",),
    "anomalies": ("observations",), "mdp": ("transitions", "rewards", "horizon"),
    "quorum": ("observations",), "calculate": ("expression",), "setpoint": ("observed", "low", "high"),
}


@dataclass(frozen=True)
class CompetencyGeometry:
    """Directive section 9. Every field optional; ``None`` means unknown and is never coerced."""
    domain: str | None = None
    objective: str | None = None
    decision_type: str | None = None
    epistemic_question: str | None = None
    geometry: str | None = None                 # an epistemic class
    subgeometry: str | None = None
    known_variables: tuple | None = None
    unknown_variables: tuple | None = None
    constraint_types: tuple | None = None
    objective_type: str | None = None
    state_space_size: int | None = None
    continuous_or_discrete: str | None = None
    deterministic_or_stochastic: str | None = None
    static_or_dynamic: str | None = None
    causal_question: bool | None = None
    forecast_horizon: int | None = None
    data_volume: int | None = None
    data_quality: float | None = None
    uncertainty_structure: str | None = None
    constraint_density: float | None = None
    graph_structure: bool | None = None
    adversarial_pressure: float | None = None
    multi_actor: bool | None = None
    resource_limits: dict | None = None
    latency_budget: float | None = None
    compute_budget: int | None = None
    evidence_requirement: str | None = None
    consequence_class: str | None = None
    reversibility: str | None = None
    human_judgment_required: bool | None = None
    authority_required: bool | None = None
    legal_content: bool | None = None
    rights_impact: bool | None = None

    @classmethod
    def parse(cls, raw) -> "CompetencyGeometry":
        if not isinstance(raw, dict) or set(raw) - {f.name for f in fields(cls)}:
            raise CognitionError("unknown geometry fields")
        strict_data(raw)
        values = {k: tuple(v) if isinstance(v, list) else v for k, v in raw.items()}
        g = cls(**values)
        if g.consequence_class not in (None, "read_only", "internal_write", *HIGH_CONSEQUENCE):
            raise CognitionError("unknown consequence class")
        if g.reversibility not in (None, "reversible", "partially_reversible", "irreversible", "unknown"):
            raise CognitionError("invalid reversibility")
        return g

    def known(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


# ------------------------------------------------------------------ mental-model operators (section 6)
@dataclass(frozen=True)
class Operator:
    operator_id: str
    problem_signatures: tuple
    transformation: str
    required_inputs: tuple
    outputs: tuple
    assumptions: tuple
    failure_modes: tuple
    counterindications: tuple
    evidence_type: str
    cost: str
    latency: str
    benchmark: str
    applies: object = field(compare=False, repr=False, default=None)
    apply: object = field(compare=False, repr=False, default=None)
    # What the operator changes: representation, candidate_set, evidence_request, or evaluation.
    effect_kind: str = "representation"


def _requirements_raise(g, req, plan):
    plan["requirements"] += ["independent verification by a second method or evidence source",
                             "fresh external evidence for every world assumption",
                             "legitimate authority through the existing Kernel Gate before any effect"]
    plan["notes"].append("high consequence raised proof, evidence and authority requirements; it did not select "
                         "a formal organ")


def _reversibility(g, req, plan):
    plan["requirements"].append("explicit founder decision for an irreversible consequence; prefer a reversible "
                                "staged alternative or abstain")


def _anti_ruin(g, req, plan):
    plan["requirements"].append("tail bound: report the worst-case/high quantile and refuse plans whose ruin "
                                "probability is unbounded")
    plan["prefer"].append("composition:estimate_then_optimize")


def _bottleneck(g, req, plan):
    plan["prefer"].insert(0, "max_flow")
    plan["notes"].append("control-point analysis first: the minimum cut names the binding constraints")


def _value_of_information(g, req, plan):
    plan["prefer"].append("composition:bayes_then_voi")
    plan["notes"].append("uncertainty is decision-relevant: price the next test before acting")


def _premortem(g, req, plan):
    plan["dissent"].append("premortem: the encoded model may omit a binding condition; a world assumption may be "
                           "false; adversarial actors may respond")


def _prefer(*methods):
    def apply(g, req, plan):
        plan["prefer"].extend(m for m in methods if m not in plan["prefer"])
    return apply


def _require(text):
    def apply(g, req, plan):
        plan["requirements"].append(text)
    return apply


def _sensitivity(g, req, plan):
    plan["evaluate"].append("sensitivity")
    plan["notes"].append("sensitivity: the chosen method re-runs with each numeric input perturbed; an answer that "
                         "moves is reported as fragile")


def _inversion(g, req, plan):
    plan["requirements"].append("inversion: state the observable conditions under which this answer would be wrong")
    plan["dissent"].append("inversion: what would have to be true for the opposite conclusion?")


def _reference_class(g, req, plan):
    plan["requirements"].append("reference class: anchor on a base rate from comparable cases before case-specific "
                                "adjustment")
    plan["prefer"].extend(["cognition.probabilistic", "cognition.bayes_interval"])


def _op(operator_id, signatures, transformation, inputs, outputs, assumptions, failures, counter, evidence, cost,
        latency, benchmark, applies, apply, effect_kind):
    return Operator(operator_id, signatures, transformation, inputs, outputs, assumptions, failures, counter, evidence,
                    cost, latency, benchmark, applies, apply, effect_kind)


def _high(g):
    return g.consequence_class in HIGH_CONSEQUENCE


OPERATORS = (
    Operator("consequence_raises_requirements", ("consequence_class in external_contact|financial|irreversible",),
             "adds independent-verification, fresh-evidence and Gate requirements; never changes the method family",
             ("consequence_class",), ("requirements",), ("consequence class is declared honestly",),
             ("under-declared consequence",), ("read-only questions",), "decision_analysis", "none", "none",
             "tests/unit/test_greg_competency_compiler.py (rule test; no effect benchmark)",
             lambda g, r: g.consequence_class in HIGH_CONSEQUENCE, _requirements_raise, "evidence_request"),
    Operator("reversibility", ("reversibility == irreversible",), "requires a founder decision or a reversible stage",
             ("reversibility",), ("requirements",), ("reversibility is declared",), ("misdeclared reversibility",),
             (), "decision_analysis", "none", "none", "rule test only",
             lambda g, r: g.reversibility == "irreversible" or g.consequence_class == "irreversible", _reversibility,
             "evidence_request"),
    Operator("anti_ruin", ("stochastic and consequence financial",), "adds a tail-bound requirement; prefers the "
             "robust estimate->optimise composition", ("deterministic_or_stochastic", "consequence_class"),
             ("requirements", "prefer"), ("ruin is the dominant loss",), ("over-conservatism",),
             ("deterministic problems",), "decision_analysis", "none", "none",
             "P6 F1 (robust composition vs point optimiser: 14 of 16 point plans claimed coverage they lacked)",
             lambda g, r: g.deterministic_or_stochastic == "stochastic" and g.consequence_class == "financial",
             _anti_ruin, "candidate_set"),
    Operator("bottleneck", ("graph_structure",), "routes to min-cut control-point analysis first",
             ("graph_structure",), ("prefer",), ("the graph is the system",), ("multi-commodity flows",), (),
             "optimality_certificate", "one max-flow", "milliseconds", "flow_maxflow admission",
             lambda g, r: bool(g.graph_structure), _bottleneck, "candidate_set"),
    Operator("value_of_information", ("decision under uncertainty with a test option",),
             "prices the next test before acting", ("uncertainty_structure",), ("prefer",),
             ("a test can change the decision",), ("no actionable test",), (), "decision_analysis",
             "three stages", "sub-second", "P6 v2 F4",
             lambda g, r: g.uncertainty_structure in ("beta", "posterior") and g.decision_type == "act_or_test",
             _value_of_information, "candidate_set"),
    Operator("premortem", ("any consequential decision",), "records the strongest failure story as dissent",
             (), ("dissent",), (), ("ritualised dissent",), ("trivial arithmetic",), "decision_analysis", "none",
             "none", "rule test only",
             lambda g, r: g.consequence_class not in (None, "read_only"), _premortem, "evaluation"),
    _op("sensitivity_analysis", ("high consequence with stochastic or uncertain inputs",),
        "re-runs the chosen method with each numeric input perturbed by 10% and reports whether the answer moves",
        ("numeric inputs",), ("sensitivity",), ("10% is a material perturbation for the inputs",),
        ("misses interactions between inputs", "perturbing an integer domain can make it infeasible"),
        ("exact arithmetic", "read-only questions"), "sensitivity_trace", "up to four extra isolated runs",
        "up to four method latencies", "tests/unit/test_greg_competency_compiler.py (executes; no effect benchmark)",
        lambda g, r: _high(g) and (g.deterministic_or_stochastic == "stochastic" or g.uncertainty_structure is not None),
        _sensitivity, "evaluation"),
    _op("inversion", ("any consequential conclusion",), "asks what would make the conclusion false",
        (), ("requirements", "dissent"), (), ("ritual inversion",), ("read-only arithmetic",), "decision_analysis",
        "none", "none", "rule test only", lambda g, r: g.consequence_class not in (None, "read_only"),
        _inversion, "evidence_request"),
    _op("reference_class", ("small or low-quality case data",),
        "anchors on a base rate before case-specific adjustment; prefers Bayesian families", ("data_volume or data_quality",),
        ("requirements", "prefer"), ("a comparable reference class exists",), ("the wrong reference class",),
        ("plentiful clean data",), "posterior", "none", "none", "rule test only",
        lambda g, r: (g.data_volume is not None and g.data_volume < 30) or (g.data_quality is not None
                                                                             and g.data_quality < 0.5),
        _reference_class, "candidate_set"),
    _op("game_theory", ("several actors with opposed interests",),
        "routes strategic interaction to equilibrium methods before single-agent optimisation",
        ("multi_actor", "adversarial_pressure"), ("prefer",), ("payoffs can be stated",),
        ("misread incentives", "unmodelled actors"), ("cooperative single-owner problems",), "game_model",
        "one LP", "sub-second", "game_minimax admission",
        lambda g, r: bool(g.multi_actor) and (g.adversarial_pressure or 0) > 0,
        _prefer("cognition.game", "cognition.game_minimax", "minimax"), "candidate_set"),
    _op("mechanism_design", ("allocation among actors with private information",),
        "prefers incentive-compatible allocation (truthful rules) over guessing reported values",
        ("multi_actor", "objective_type"), ("prefer",), ("actors may misreport",), ("collusion outside the model",),
        ("a single decision-maker",), "decision_analysis", "one auction", "sub-second", "mech_vcg admission",
        lambda g, r: bool(g.multi_actor) and g.objective_type in ("allocation", "welfare"),
        _prefer("cognition.mech_vcg", "cognition.collective_market"), "candidate_set"),
    _op("feedback_loops", ("dynamic system with a target",),
        "routes regulation problems to closed-loop control and estimation before open-loop plans",
        ("static_or_dynamic",), ("prefer",), ("the dynamics are approximately stationary",),
        ("model mismatch", "actuator limits"), ("one-shot decisions",), "control_trace", "one simulation",
        "milliseconds", "basal_pid and control_mpc admission",
        lambda g, r: g.static_or_dynamic == "dynamic",
        _prefer("cognition.control", "cognition.basal_pid", "cognition.control_mpc", "cognition.basal_kalman"),
        "candidate_set"),
    _op("falsification", ("a claim that will inform action",),
        "requires a stated falsifier and a verifier independent of the solver", (), ("requirements",),
        ("a falsifier can be observed",), ("unfalsifiable framing",), (), "decision_analysis", "none", "none",
        "every genome verify() refutes corrupted outputs (admission tests)",
        lambda g, r: g.evidence_requirement in ("high", "external"),
        _require("falsification: name the observation that would refute this answer; the verifier must not share "
                 "the solver's code path"), "evidence_request"),
    _op("second_order_effects", ("decisions touching other actors or rights",),
        "requires the downstream effects on affected participants to be stated before acting",
        ("multi_actor",), ("requirements",), ("affected participants can be named",), ("unknown unknowns",),
        ("purely internal computation",), "decision_analysis", "none", "none", "rule test only",
        lambda g, r: bool(g.multi_actor) and g.consequence_class not in (None, "read_only"),
        _require("second-order effects and regenerative impact: state who else is affected, how, and whether "
                 "participants are better off"), "evidence_request"),
    _op("pareto_analysis", ("several objectives that cannot be traded at a declared rate",),
        "keeps the non-dominated set instead of collapsing objectives into one scalar", ("objective_type",),
        ("requirements",), ("objectives are independent",), ("too many objectives make everything non-dominated",),
        ("one declared objective",), "decision_analysis", "none", "none",
        "foundry.lawful_leverage frontier tests",
        lambda g, r: g.objective_type == "multi",
        _require("pareto analysis: return the non-dominated alternatives with each objective, not a single scalar"),
        "evaluation"),
)

# Directive section 6, every listed model -> the operator that executes it, or the mechanism that carries it.
DIRECTIVE_MODELS = {
    "first principles": "first_principles", "inversion": "inversion", "reference classes": "reference_class",
    "Bayesian updating": "bayesian_updating", "Fermi decomposition": "fermi_decomposition",
    "sensitivity analysis": "sensitivity_analysis", "expected value": "expected_value",
    "value of information": "value_of_information", "opportunity cost": "opportunity_cost",
    "optionality": "optionality", "reversibility": "reversibility", "anti-ruin boundaries": "anti_ruin",
    "premortem": "premortem", "counterfactuals": "counterfactuals", "steelmanning": "steelmanning",
    "falsification": "falsification", "constraint analysis": "constraint_analysis",
    "bottleneck analysis": "bottleneck", "systems thinking": "systems_thinking",
    "second-order effects": "second_order_effects", "feedback loops": "feedback_loops",
    "game theory": "game_theory", "mechanism design": "mechanism_design",
    "control-point analysis": "control_point_analysis", "dependency analysis": "dependency_analysis",
    "backcasting": "backcasting", "weakest-link reasoning": "weakest_link_reasoning",
    "marginal analysis": "marginal_analysis", "Pareto analysis": "pareto_analysis",
    "power-law reasoning": "power_law_reasoning", "portfolio/concentration reasoning": "portfolio_concentration",
    "asymmetry analysis": "asymmetry_analysis", "regenerative-impact analysis": "regenerative_impact_analysis",
}

# Directive section 6 models already carried by a mechanism elsewhere on the one path (not duplicated here):
OPERATOR_HOMES = {
    "first_principles": "CompetencyGeometry: the problem is restated as typed fields before any method is chosen",
    "bayesian_updating": "cognition.probabilistic (beta_update) and the forecasting/decision genomes",
    "fermi_decomposition": "cognition.cortex.estimation.fermi",
    "expected_value": "foundry.lawful_leverage Monte Carlo means and the information family",
    "opportunity_cost": "foundry.lawful_leverage direct-labour and do-nothing baselines",
    "optionality": "foundry.lawful_leverage defer-to-trigger and staged variants (option_value)",
    "counterfactuals": "do-nothing and direct-labour arms in every Foundry comparison; ablation arms in P6",
    "steelmanning": "every Foundry candidate and genome carries its strongest counterargument",
    "constraint_analysis": "the constraints and optimization families; Foundry hard eligibility gates",
    "control_point_analysis": "bottleneck operator (max_flow) and the Foundry control-point rule",
    "dependency_analysis": "foundry dependency surface and the dependency_capture harm dimension",
    "backcasting": "greg.path Backcast GPS and frontier_backcasts",
    "weakest_link_reasoning": "Foundry path_support (every link must be real) and min-cut",
    "marginal_analysis": "Foundry staged pilots and value of information",
    "systems_thinking": "egregore.leverage strongest-path propagation over the institutional map",
    "power_law_reasoning": "anti_ruin tail requirement; only where tails are measured",
    "portfolio_concentration": "dependency_capture harm ceiling and multi-candidate Pareto frontier",
    "asymmetry_analysis": "Foundry benefit and cost/harm vectors; control point only when it dominates",
    "regenerative_impact_analysis": "second_order_effects operator; participant_benefit in the Foundry vector",
}



# ------------------------------------------------------------------ evidence-driven routing
def evidence_index(path: Path | None = None) -> dict:
    """Frozen results that change routing: genome admission statuses, recipe lift verdicts, P4 demotion."""
    path = path or EVIDENCE_INDEX
    if not path.exists():
        return {"genomes": {}, "recipes": {}, "routing": {}}
    return json.loads(path.read_text())


def candidates(data: dict, g: CompetencyGeometry, evidence: dict) -> list[dict]:
    from .catalog import FAMILIES
    from .composition import RECIPES, route
    from .genomes import library
    rows, keys = [], set(data)
    genomes = library.executables()
    for family, (_, ops, classes, _, _) in FAMILIES.items():
        for op in ops:
            stale = None
            if family in genomes:
                need = genomes[family].genome.required_inputs
                record = evidence["genomes"].get(family, {})
                status = record.get("status", "UNEVALUATED")
                standalone = genomes[family].genome.standalone_decision
                measured, current = record.get("version"), genomes[family].genome.version
                if measured and measured != current and status not in EXCLUDED:
                    # positive evidence binds the version measured; negative evidence persists until a
                    # re-admission replaces it
                    stale = f"{status} was measured at version {measured}; version {current} needs re-admission"
                    status = "UNEVALUATED"
            else:
                need = NATIVE_INPUTS.get(op)
                status = "UNEVALUATED"
                standalone = True
            if need is None or not set(need) <= keys:
                continue
            reason = None
            if g.geometry and g.geometry not in classes:
                reason = f"native geometry {classes} does not include {g.geometry}"
            elif not standalone:
                reason = "composition stage only (no standalone decision)"
            elif status in EXCLUDED:
                reason = f"frozen admission status {status}"
            row = {"method": f"cognition.{family}", "operation": op, "kind": "operation", "status": status,
                   "epistemic_classes": list(classes), "rejected": reason,
                   **({"stale_evidence": stale} if stale else {})}
            if family in genomes:
                measured = _subregion_evidence(genomes[family], data, evidence["genomes"].get(family, {}))
                if measured:
                    row["subregion"] = measured
            rows.append(row)
    recipe = route(data)
    if recipe:
        verdict = evidence["recipes"].get(recipe, {})
        row = {"method": f"composition:{recipe}", "operation": recipe, "kind": "composition",
               "status": "VPL_LIFT" if verdict.get("lift") else verdict.get("status", "UNEVALUATED"),
               "stages": list(RECIPES[recipe]["stages"]), "rejected": None}
        if verdict.get("lift") is False:
            # Demoted, not deleted: a recipe without verified lift ranks after every other method that fits,
            # because the simpler constituent wins ties; it stays the route when nothing else fits (P6 F5:
            # 8.5% cheaper, not significant, and its comparison arm is not an invocable method).
            row["status"] = "NO_LIFT"
            row["demoted"] = (f"frozen VPL verdict ({verdict.get('evidence', 'evidence index')}): no lift over "
                              f"{verdict.get('prefer') or 'its best constituent'}; ranked after every other fit")
        rows.append(row)
    return rows


SUBREGION_RANK = {"FAVOURED": 0, "NEUTRAL": 1, "DOMINATED": 2}


def _subregion_evidence(item, data: dict, record: dict) -> dict | None:
    """This request's native subregion and the frozen held-out verdict there against the genome's competitor.

    FAVOURED / DOMINATED need a one-sided exact sign test p < 0.05 within the subregion; anything else is
    NEUTRAL. Measured evidence, reported and used to order fits; it is never a status and never authority."""
    table = record.get("subregions_vs_competitor") or {}
    if item.subregion is None or not table:
        return None
    try:
        name = item.subregion(data)
    except Exception:            # an input the subregion function cannot place is simply unplaced
        return None
    measured = table.get(name)
    if measured is None:
        return {"name": name, "verdict": "UNMEASURED"}
    verdict = ("FAVOURED" if measured["p_better"] < 0.05 else "DOMINATED" if measured["p_worse"] < 0.05
               else "NEUTRAL")
    return {"name": name, "verdict": verdict, "vs_competitor": measured, "competitor": record.get("competitor"),
            "competitor_deployable": item.competitor_deployable, "evidence": record.get("evidence")}


def constructed_candidates(data: dict, g: CompetencyGeometry, registry) -> list[dict]:
    """Capabilities Capability Genesis constructed (greg.recombine) that fit this request's inputs.

    An ATTACHED construction is a candidate like any admitted method; a fitting reduction with no
    attached construction is rejected as *constructible*, so the deficit names a function Genesis
    can actually form instead of an unbuildable geometry label. Attachment stays a founder act."""
    from greg import recombine
    rows = []
    for reduction in recombine.fits(data):
        attached = [m.capability_id for m in getattr(registry, "by_function", lambda f: [])(reduction.function)
                    if m.provider.startswith("composed:") and m.consequence_class == "read_only"
                    and registry.usable(m.capability_id)[0]]
        row = {"method": attached[0] if attached else f"constructible:{reduction.function}",
               "operation": reduction.function, "kind": "constructed", "inputs": list(reduction.inputs),
               "epistemic_classes": list(reduction.epistemic_classes),
               "status": "CONSTRUCTED_VERIFIED" if attached else "UNEVALUATED", "rejected": None}
        if g.geometry and g.geometry not in reduction.epistemic_classes:
            row["rejected"] = f"native geometry {list(reduction.epistemic_classes)} does not include {g.geometry}"
        elif not attached:
            row["rejected"] = "constructible: no attached construction yet (Capability Genesis can form it)"
            row["constructible"] = True
        rows.append(row)
    return rows


def _run_constructed(chosen: dict, data: dict, pid: str, registry, receipt: dict, finish):
    """Invoke an attached, read-only construction; its problem-level certificate is the evidence."""
    import tempfile
    from greg.capabilities import CapabilityError, InvocationContext
    manifest = registry.manifests[chosen["method"]]
    if manifest.consequence_class != "read_only" or not manifest.provider.startswith("composed:"):
        receipt["abstentions"].append("ABSTAIN: only a read-only construction may answer inside cognition")
        return finish("ABSTAIN")
    request = {key: data[key] for key in chosen["inputs"]}
    with tempfile.TemporaryDirectory(prefix="greg-constructed-") as tmp:
        ctx = InvocationContext(workspace=Path(tmp), read_roots=(), secrets=None, manifest=manifest,
                                target=f"cognition:{pid}")
        try:
            out = registry.adapters[manifest.capability_id](request, ctx)
        except CapabilityError as exc:
            if str(exc).startswith("capability refused:"):
                # the mission's two-strike repair re-forms a construction that faults in service
                receipt["capability_fault"] = {"capability_id": manifest.capability_id, "detail": str(exc)[:300]}
            receipt["abstentions"].append(f"ABSTAIN: {str(exc)[:300]}")
            return finish("ABSTAIN")
    receipt["resource_use"]["stages"] = 1
    receipt["proof_artifacts"] = [{"type": "certificate", "evidence_type": (out.get("certificate") or {}).get("kind")}]
    receipt["verification_method"] = (out.get("certificate") or {}).get("checked_by") or \
        "GREG problem-level certificate, independent of the engine"
    receipt["confidence_type"] = "certified: exact problem-level certificate"
    receipt["dissent"].append(f"trust per call: {manifest.provenance.get('baseline', 'see the construction card')}")
    if out.get("certified") is not True:
        receipt["abstentions"].append("ABSTAIN: the construction returned no certificate")
        return finish("ABSTAIN")
    return finish("ANSWERED", out)


def _rank(row: dict, prefer: list, competence: dict) -> tuple:
    status = 0 if row["status"] == "VPL_LIFT" else STATUS_RANK.get(row["status"], 5)
    preferred = 0 if (row["operation"] in prefer or row["method"] in prefer) else 1
    settled = -competence.get(row["method"], 0.5)
    region = SUBREGION_RANK.get((row.get("subregion") or {}).get("verdict"), 1)
    # Frozen negative evidence outranks an operator's preference: evidence over heuristics. Within one status,
    # the measured subregion verdict orders fits before settled competence.
    return (1 if row.get("demoted") else 0, preferred, status, region, settled,
            0 if row["kind"] == "operation" else 1, row["method"])


NEGATION = {"<=": ">", ">=": "<", "<": ">=", ">": "<=", "==": "!=", "!=": "=="}


def invert_claim(claim: dict) -> dict:
    """Inversion as an executable representation change: 'these constraints imply this property' holds exactly
    when 'constraints AND NOT property' is unsatisfiable, so the claim becomes a formal feasibility instance.
    The negation is exact over the reals (strict comparisons), never an epsilon approximation."""
    if (set(claim) - {"variables", "constraints", "property"} or not isinstance(claim.get("property"), dict)
            or not isinstance(claim.get("constraints"), list)):
        raise CognitionError("a claim takes variables, constraints and one linear property")
    prop = claim["property"]
    if set(prop) != {"coefficients", "op", "rhs"} or prop["op"] not in NEGATION:
        raise CognitionError("the property is one linear comparison {coefficients, op, rhs}")
    return {"variables": claim["variables"],
            "constraints": list(claim["constraints"]) + [{**prop, "op": NEGATION[prop["op"]]}]}


def claim_verdict(output: dict) -> dict:
    """SAT: a counterexample to the claim (the verifier re-substituted it exactly). UNSAT: the property holds
    for every assignment the encoded constraints allow (a solver report, conditional on the model)."""
    status = output.get("solver_status")
    if status == "SAT":
        return {"claim": "REFUTED", "counterexample": output["solution"],
                "basis": "an assignment satisfying every constraint and violating the property"}
    if status == "UNSAT":
        return {"claim": "HOLDS_WITHIN_MODEL",
                "basis": "constraints AND NOT property is unsatisfiable (solver report; conditional on the model)"}
    return {"claim": "UNDECIDED", "basis": f"solver status {status}"}


def _usable(registry, row: dict) -> tuple[bool, str]:
    """Whether the row can run now: an operation's capability must be attached; a composition's stages are
    checked stage by stage on the canonical path."""
    if row["kind"] != "operation":
        return True, "composition: stages checked on the canonical path"
    try:
        ok, why = registry.usable(row["method"])
    except Exception as exc:
        return False, f"registry: {type(exc).__name__}"
    return bool(ok), str(why)


def attach_ask(pid: str, best: dict, fallback: dict | None, evidence: dict) -> dict:
    """A founder ask to attach a withheld capability, on the one asks contract and its screen. Prepared here and
    returned for the body to record through greg.asks; attaching stays the founder's decision."""
    from datetime import datetime, timezone
    from greg import asks
    family = best["method"].removeprefix("cognition.")
    record = evidence.get("genomes", {}).get(family, {})
    measured = {k: v for k, v in {"admission_status": best["status"], "admission_evidence": record.get("evidence"),
                                  "measured_version": record.get("version"),
                                  "subregion": best.get("subregion"), "current_state": best["usable_why"]}.items()
                if v is not None}
    served = fallback["method"] if fallback else "no attached method"
    packet = asks.resource_request(
        request_id=f"attach-{digest({'pid': pid, 'method': best['method']})[7:23]}", kind="RESOURCE",
        resource="capability",
        why_now=f"the best-fitting method for request {pid} by frozen evidence, {best['method']}, is registered "
                f"but not attached",
        recommendation=f"review the admission evidence and attach {best['method']} if it is sufficient",
        evidence=measured,
        options=[{"option": f"attach {best['method']}", "cost": "one founder-signed attach decision; no money",
                  "expected_effect": f"requests of this geometry route to {best['method']}"},
                 {"option": "keep it withheld", "cost": "none",
                  "expected_effect": f"requests of this geometry are served by {served}"}],
        expected_effect=f"routes this geometry to {best['method']} instead of {served}",
        uncertainty="held-out admission evidence on generated or reserved instances; outcomes on GREG's own "
                    "missions are not yet measured",
        authority_requested={"attach": best["method"], "spend": "none", "consequence_class": "read_only"},
        consequence_of_no_response=f"requests of this geometry are served by {served}; nothing else changes",
        created_at=datetime.now(timezone.utc).isoformat())
    asks.validate(packet)
    violations = asks.screen(packet)
    if violations:
        raise CognitionError(f"the attach ask failed the ask screen: {violations}")
    return {**packet, "state": "PREPARED_NOT_RECORDED",
            "record_with": "greg.asks.record on the body (the one path for decision.requested)"}


def _settled_competence(journal, geometry_class) -> dict:
    """Mean settled correctness per method from the canonical journal (existing settlement), if any."""
    if journal is None:
        return {}
    from .settlement import competence
    out = {}
    for (method, _version, _geometry), record in competence(journal).items():
        n = record.get("count", 0)
        if n:
            out[method] = (record.get("correct", 0) + 1) / (n + 2)
    return out


# ------------------------------------------------------------------ compile + run
def validate(params) -> tuple[str, dict]:
    if not isinstance(params, dict) or set(params) - {"problem_id", "compile"}:
        raise CognitionError("a compilation request takes problem_id and compile")
    body = params.get("compile")
    if not isinstance(body, dict) or set(body) - {"geometry", "data", "consequence", "evidence_refs", "execute",
                                                  "human", "assumptions"}:
        raise CognitionError("compile takes geometry, data, consequence, evidence_refs, assumptions, human, execute")
    strict_data(body)
    if len(canonical(params).encode()) > 4 * 1024 * 1024:
        raise CognitionError("compilation request exceeds 4 MiB")
    pid = params.get("problem_id")
    if not isinstance(pid, str) or not 1 <= len(pid) <= 96:
        raise CognitionError("bounded problem identity required")
    if not isinstance(body.get("data"), dict):
        raise CognitionError("compile.data is a bounded mapping")
    return pid, body


def human_packet(g: CompetencyGeometry, body: dict) -> dict:
    """THIS REQUIRES QUALIFIED HUMAN JUDGMENT: a typed request, never a vote."""
    human = body.get("human") or {}
    roles = [r for r in human.get("roles", ["founder", "domain_expert", "affected_participant"]) if r in HUMAN_ROLES]
    return {"state": "HUMAN_JUDGMENT_REQUIRED", "roles": roles,
            "competence_domain": human.get("competence_domain", g.domain or "unspecified"),
            "decision_authority": "the role the Constitution names for this decision; never a majority of opinions",
            "disagreement": "every view and its rationale is preserved; no aggregation into a vote",
            "refusal_rights": "any participant may refuse; refusal is recorded, never overridden by cognition",
            "provenance_required": ["identity", "expertise basis", "conflicts of interest"],
            "machine_role": "prepare evidence and alternatives only"}


def run(params, *, registry, journal=None, model_config=None) -> dict:
    from .cortex import reason
    started = time.monotonic()
    pid, body = validate(params)
    g = CompetencyGeometry.parse(body.get("geometry", {}))
    data = body["data"]
    consequence = body.get("consequence") or {}
    evidence = evidence_index()
    plan = {"requirements": [], "prefer": [], "notes": [], "dissent": [], "evaluate": []}
    receipt = {"schema": SCHEMA, "problem_id": pid, "inputs_digest": digest(params), "geometry": g.known(),
               "subgeometry": g.subgeometry, "consequence_class": g.consequence_class or "read_only",
               "methods_considered": [], "methods_rejected": [], "methods_demoted": [],
               "method_or_composition_selected": None,
               "selection_level": None, "conditional_competence_basis": None,
               "assumptions": list(body.get("assumptions", [])) + ["the declared geometry is honest"],
               "evidence_refs": list(body.get("evidence_refs", [])), "transformations": [],
               "intermediate_receipts": [], "proof_artifacts": [], "uncertainty": None, "abstentions": [],
               "dissent": [], "cost": {"money_usd": 0.0, "model_calls": 0}, "latency_s": None,
               "resource_use": {"stages": 0}, "translation_checks": [], "verification_method": None,
               "result": None, "confidence_type": None, "requirements": [],
               "authority_state": "EXISTING_KERNEL_GATE_REQUIRED", "authority_created": False,
               "outcome_link": None, "later_appraisal": None, "state": None, "capability_deficit": None}

    def finish(state, result=None):
        receipt["state"], receipt["result"] = state, result
        receipt["requirements"] = list(dict.fromkeys(plan["requirements"]))
        receipt["dissent"] = list(dict.fromkeys(receipt["dissent"] + plan["dissent"]))
        receipt["latency_s"] = round(time.monotonic() - started, 4)
        receipt["receipt_id"] = digest({k: v for k, v in receipt.items() if k != "receipt_id"})
        return receipt

    # 1. constitutional pre-filter: hard eligibility before any optimisation
    if consequence.get("lawful") is False or consequence.get("consent") is False or (consequence.get("rights") or 0) > 0:
        receipt["abstentions"].append("law, consent and rights constraints are eligibility gates; upside cannot compensate")
        return finish("PROHIBITED")
    if g.human_judgment_required or g.legal_content or g.rights_impact or g.geometry in HUMAN_CLASSES:
        receipt["method_or_composition_selected"] = "human:qualified_judgment"
        receipt["selection_level"] = "constitutional_route"
        packet = human_packet(g, body)
        judgments = (body.get("human") or {}).get("judgments")
        if judgments is None:
            return finish("HUMAN_JUDGMENT_REQUIRED", packet)
        # the return path: typed judgments are evidence; only the founder's signed answer decides
        from .human import adjudicate
        adjudicated = adjudicate(judgments, journal)
        receipt["human_judgments"] = adjudicated
        for j in adjudicated["judgments"]:
            if j["verdict"] != (adjudicated["decision"] or {}).get("verdict"):
                receipt["dissent"].append(f"{j['role']} {j['participant_ref']} ({j['competence_domain']}): "
                                          f"{j['verdict']}: {j['rationale'][:200]}")
        receipt["dissent"] += adjudicated["provenance_conflicts"]
        if adjudicated["decision"] is None:
            return finish("HUMAN_JUDGMENT_REQUIRED", {**packet, "judgments_received": len(adjudicated["judgments"]),
                                                       "awaiting": "the founder's signed answer"})
        return finish("HUMAN_JUDGMENT_RECORDED", {"decision": adjudicated["decision"],
                                                  "acts": "nothing: a recorded human decision still reaches the "
                                                          "world only through the Gate"})
    # 2. operators transform the representation (recorded, never silent)
    for op in OPERATORS:
        if op.applies(g, body):
            op.apply(g, body, plan)
            receipt["transformations"].append({"operator_id": op.operator_id, "transformation": op.transformation,
                                               "effect_kind": op.effect_kind, "evidence_type": op.evidence_type,
                                               "benchmark": op.benchmark})
    # 2b. representation operators rewrite the problem itself, so a different intelligence can solve it
    inverted = None
    if isinstance(data.get("claim"), dict):
        inverted = invert_claim(data["claim"])
        receipt["transformations"].append({
            "operator_id": "inversion", "effect_kind": "representation",
            "transformation": "claim 'constraints imply property' -> satisfiability of constraints AND NOT property",
            "input_digest": digest(data["claim"]), "output_digest": digest(inverted),
            "evidence_type": "exact_negation", "benchmark": "tests/unit/test_greg_inversion_operator.py"})
        data = inverted
    # 3. candidates by native geometry and inputs; frozen negative evidence excludes
    rows = candidates(data, g, evidence) + constructed_candidates(data, g, registry)
    receipt["methods_considered"] = [r["method"] for r in rows]
    receipt["methods_rejected"] = [{"method": r["method"], "why": r["rejected"]} for r in rows if r["rejected"]]
    receipt["methods_demoted"] = [{"method": r["method"], "why": r["demoted"]} for r in rows if r.get("demoted")]
    eligible = [r for r in rows if not r["rejected"]]
    if not eligible:
        receipt["capability_deficit"] = {
            "function": f"cognition.{g.geometry or 'unknown'}:{g.subgeometry or 'unspecified'}",
            "purpose": g.objective or g.epistemic_question or "cognitive request",
            "required_inputs": sorted(data), "geometry": g.known(),
            "verification": {"failed": "no catalogued, admitted, attached-or-attachable method fits this geometry",
                             "unserviceable": receipt["methods_rejected"] or "no method declares these inputs",
                             "verified": True},
            "search_order": ["attached", "verified_detached", "installed_software", "builder", "founder"],
            "route": "greg.genesis (Capability Genesis) under the enclosing mission's authority"}
        buildable = [r for r in rows if r.get("constructible")]
        if buildable:
            # The Mind names the missing function in a form Capability Genesis can construct.
            from greg import recombine
            from greg.genesis import CATALOG
            found = recombine.chain(buildable[0]["operation"], CATALOG)
            if found is not None:
                path, engine = found
                receipt["capability_deficit"].update({
                    "function": buildable[0]["operation"], "required_inputs": buildable[0]["inputs"],
                    "constructible": {"chain": [r.reduction_id for r in path], "engine": engine,
                                      "alternatives": [r["operation"] for r in buildable[1:]]},
                    "search_order": ["attached", "verified_detached", "constructed", "builder", "founder"]})
        return finish("CAPABILITY_DEFICIT")
    competence = _settled_competence(journal, g.geometry)
    eligible.sort(key=lambda r: _rank(r, plan["prefer"], competence))
    for r in eligible:
        r["usable"], r["usable_why"] = _usable(registry, r)
    best = eligible[0]
    runnable = [r for r in eligible if r["usable"]]
    if not best["usable"]:
        # the best fit by evidence is registered but withheld: say so, route to the best usable fit, and
        # prepare (never record or act on) one founder ask to attach it, with its admission evidence
        receipt["withheld_best_fit"] = {"method": best["method"], "state": best["usable_why"],
                                        "status": best["status"], "served_by": runnable[0]["method"] if runnable
                                        else None, **({"subregion": best["subregion"]} if best.get("subregion")
                                                      else {})}
        receipt["founder_attach_ask"] = attach_ask(pid, best, runnable[0] if runnable else None, evidence)
    if not runnable:
        receipt["capability_deficit"] = {
            "function": f"cognition.{g.geometry or 'unknown'}:{g.subgeometry or 'unspecified'}",
            "purpose": g.objective or g.epistemic_question or "cognitive request",
            "required_inputs": sorted(data), "geometry": g.known(),
            "verification": {"failed": "every fitting method is registered but not attached",
                             "unserviceable": [{"method": r["method"], "why": r["usable_why"]} for r in eligible],
                             "verified": True},
            "search_order": ["attached", "verified_detached", "installed_software", "builder", "founder"],
            "route": "founder attach of the prepared ask, or greg.genesis under the enclosing mission's authority"}
        return finish("CAPABILITY_DEFICIT")
    chosen = runnable[0]
    receipt["method_or_composition_selected"] = chosen["method"]
    receipt["selection_level"] = ("only_fit_despite_no_lift" if chosen.get("demoted")
                                  else "preferred_by_operator" if chosen["operation"] in plan["prefer"]
                                  or chosen["method"] in plan["prefer"] else "admission_status")
    if chosen.get("demoted"):
        receipt["dissent"].append(chosen["demoted"])
    if chosen.get("stale_evidence"):
        receipt["selection_level"] = "unevaluated_at_current_version"
        receipt["dissent"].append(f"stale admission evidence: {chosen['stale_evidence']}")
    region = chosen.get("subregion")
    if region:
        receipt["subregion_evidence"] = region
        if region["verdict"] == "DOMINATED":
            m = region["vs_competitor"]
            receipt["dissent"].append(
                f"in subregion {region['name']} this method lost {m['losses']}-{m['wins']} to its competitor on "
                f"frozen held-out instances (p = {m['p_worse']}): {region['competitor']}")
            if region["competitor_deployable"]:
                # measured insufficiency of the repertoire here: a named mechanism for Capability Genesis
                receipt["acquisition_candidates"] = [{
                    "mechanism": region["competitor"], "subregion": region["name"], "evidence": region["evidence"],
                    "route": "greg.genesis (Capability Genesis) under the enclosing mission's authority",
                    "authority": "none: a candidate to acquire, never an attached method"}]
    receipt["conditional_competence_basis"] = {m: round(v, 4) for m, v in competence.items()} or \
        "no settled outcomes in this journal; admission evidence and cost decide"
    if body.get("execute") is False:
        return finish("PLANNED")
    if chosen["kind"] == "constructed":
        return _run_constructed(chosen, data, pid, registry, receipt, finish)
    # 4. execute through the same canonical reason
    if chosen["kind"] == "composition":
        inner = reason({"problem_id": pid, "chain": {"question": g.objective or "compiled", "payload": data}},
                       registry=registry, journal=journal, model_config=model_config)
        receipt["intermediate_receipts"] = [s["receipt_id"] for s in inner["stages"]]
        receipt["translation_checks"] = inner["bindings"] + inner["translation_failures"]
        receipt["resource_use"]["stages"] = len(inner["stages"])
        receipt["verification_method"] = "per-stage independent verifier; cross-intelligence checks where declared"
        receipt["confidence_type"] = "composition of typed stage evidence"
        if inner["state"] != "ANSWERED":
            receipt["abstentions"].append(f"{inner['state']}: {inner['reason']}")
            return finish(inner["state"])
        return finish("ANSWERED", inner["answer"])
    geometry_hint = {"latency_limit": min(30.0, float(g.latency_budget or 20.0))}
    inner = reason({"problem_id": pid, "operation": chosen["operation"], "data": data, "geometry": geometry_hint},
                   registry=registry, journal=journal, model_config=model_config)
    receipt["intermediate_receipts"] = [inner["receipt_id"]]
    receipt["proof_artifacts"] = [{"type": inner["proof_type"],
                                   "evidence_type": (inner.get("proof_artifact") or {}).get("evidence_type")}]
    receipt["verification_method"] = (inner.get("evaluator_result") or {}).get("independence")
    receipt["confidence_type"] = receipt["proof_artifacts"][0]["evidence_type"] or inner["proof_type"]
    receipt["uncertainty"] = inner.get("uncertainty")
    receipt["dissent"].append(inner.get("strongest_counterargument", ""))
    receipt["resource_use"]["stages"] = 1
    if inner["abstention_state"] != "NONE":
        receipt["abstentions"].append(f"{inner['abstention_state']}: {inner['missing_information']}")
        return finish(inner["abstention_state"])
    if inverted is not None:
        return finish("ANSWERED", claim_verdict(inner["output"]))
    if "sensitivity" in plan["evaluate"]:
        receipt["sensitivity"] = _sensitivity_runs(pid, chosen["operation"], data, inner["output"], geometry_hint,
                                                   registry, journal, model_config, receipt)
    return finish("ANSWERED", inner["output"])


def _numbers(value):
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, dict):
        return [x for k in sorted(value) for x in _numbers(value[k])]
    if isinstance(value, list):
        return [x for v in value for x in _numbers(v)]
    return []


def _scaled(value, factor):
    if isinstance(value, bool) or not isinstance(value, (int, float, dict, list)):
        return value
    if isinstance(value, int):
        return int(round(value * factor)) if abs(value) > 1 else value
    if isinstance(value, float):
        return value * factor
    if isinstance(value, dict):
        return {k: _scaled(v, factor) for k, v in value.items()}
    return [_scaled(v, factor) for v in value]


def _sensitivity_runs(pid, operation, data, baseline, hint, registry, journal, model_config, receipt) -> dict:
    """Perturb each numeric top-level input by +10% (at most four) and re-run the same method on the one path."""
    from .cortex import reason
    keys = [k for k in sorted(data) if _numbers(data[k])][:4]
    base = _numbers(baseline)
    rows = {}
    for key in keys:
        varied = {**data, key: _scaled(data[key], 1.1)}
        out = reason({"problem_id": f"{pid}/sens/{key}"[:128], "operation": operation, "data": varied,
                      "geometry": hint}, registry=registry, journal=journal, model_config=model_config)
        receipt["intermediate_receipts"].append(out["receipt_id"])
        if out["abstention_state"] != "NONE":
            rows[key] = {"state": out["abstention_state"]}
            continue
        now = _numbers(out["output"])
        moved = canonical(out["output"]) != canonical(baseline)
        change = (max((abs(a - b) / max(1e-9, abs(b)) for a, b in zip(now, base)), default=0.0)
                  if len(now) == len(base) else None)
        rows[key] = {"state": "ANSWERED", "answer_changed": moved, "max_relative_change": change}
    fragile = [k for k, v in rows.items() if v.get("answer_changed")]
    if fragile:
        receipt["dissent"].append(f"sensitivity: the answer moves when {', '.join(fragile)} change by 10%")
    receipt["resource_use"]["stages"] += len(rows)
    return {"perturbation": "+10% on each numeric top-level input (at most four)", "inputs": rows,
            "fragile_inputs": fragile}
