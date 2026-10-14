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

SCHEMA = "greg-competency-compilation/0.2"   # 0.2: selected_receipt (the executed method's own receipt)
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_INDEX = ROOT / "docs" / "evidence" / "greg-mind-evidence-index.json"
HIGH_CONSEQUENCE = ("external_contact", "financial", "irreversible")
HUMAN_CLASSES = ("normative", "legal", "institutional_acceptance")
HUMAN_ROLES = ("founder", "operator", "domain_expert", "affected_participant", "auditor", "customer",
               "professional", "regulator")
STATUS_RANK = {"DEFAULT_FOR_GEOMETRY": 0, "NICHE_CAPABILITY": 1, "UNEVALUATED": 2, "EXPERIMENTAL": 3, "NO_LIFT": 8,
               "COMPOSITION_ONLY": 9, "SUPERSEDED": 9, "REJECTED": 9, "FRONTIER_HORIZON": 9}
EXCLUDED = ("SUPERSEDED", "REJECTED", "FRONTIER_HORIZON", "COMPOSITION_ONLY")
# Statuses that are not positive evidence: they persist through a version bump until a re-admission replaces
# them (a version change never turns a negative or inconclusive result into UNEVALUATED).
NOT_POSITIVE = EXCLUDED + ("EXPERIMENTAL",)
HIGH_CONSEQUENCE = ("external_contact", "financial", "irreversible")
# The order in which Capability Genesis searches a cognition deficit (greg.genesis.COGNITION_SEARCH).
GENESIS_SEARCH = ("attached", "verified_detached", "genome_library", "installed_package", "builder", "founder")
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
        _prefer("cognition.game", "cognition.game_minimax", "cognition.game_lp_dual", "minimax"), "candidate_set"),
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
        _prefer("cognition.control", "cognition.basal_pid", "cognition.pid_simopt", "cognition.control_mpc",
                "cognition.basal_kalman"),
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


def candidates(data: dict, g: CompetencyGeometry, evidence: dict, *, parts: bool = True) -> list[dict]:
    from .catalog import FAMILIES
    from .composition import RECIPES, route
    from .genomes import library
    rows, keys = [], set(data)
    unfit = []          # catalogued methods whose inputs the request does not all carry (the relaxation rule)
    genomes = library.executables()
    # a superseded genome's competitor promoted into a registered genome of its own (same geometry and inputs)
    promoted = {old: new for old, new in library.promotions().items() if new in FAMILIES}
    for family, (_, ops, classes, _, _) in FAMILIES.items():
        for op in ops:
            stale = None
            outputs = None
            if family in genomes:
                need = genomes[family].genome.required_inputs
                outputs = sorted(genomes[family].genome.output_contract)
                record = evidence["genomes"].get(family, {})
                status = record.get("status", "UNEVALUATED")
                standalone = genomes[family].genome.standalone_decision
                measured, current = record.get("version"), genomes[family].genome.version
                if measured and measured != current and status not in NOT_POSITIVE:
                    # positive evidence binds the version measured; negative evidence persists until a
                    # re-admission replaces it
                    stale = f"{status} was measured at version {measured}; version {current} needs re-admission"
                    status = "UNEVALUATED"
            else:
                need = NATIVE_INPUTS.get(op)
                status = "UNEVALUATED"
                standalone = True
            if need is None:
                continue
            if not set(need) <= keys:
                unfit.append({"method": f"cognition.{family}", "inputs": sorted(need), "outputs": outputs,
                              "epistemic_classes": list(classes)})
                continue
            reason = None
            if g.geometry and g.geometry not in classes:
                reason = f"native geometry {classes} does not include {g.geometry}"
            elif not standalone:
                reason = "composition stage only (no standalone decision)"
            elif status in EXCLUDED:
                reason = f"frozen admission status {status}"
            row = {"method": f"cognition.{family}", "operation": op, "kind": "operation", "status": status,
                   "epistemic_classes": list(classes), "rejected": reason, "inputs": sorted(need), "outputs": outputs,
                   **({"stale_evidence": stale} if stale else {})}
            if family in genomes and not stale and evidence["genomes"].get(family, {}).get("median_seconds") is not None:
                row["median_seconds"] = evidence["genomes"][family]["median_seconds"]   # held-out, this version
            if family in genomes and not stale:
                # subregion verdicts bind the version they were measured at, like the status they refine
                measured = _subregion_evidence(genomes[family], data, evidence["genomes"].get(family, {}))
                if measured:
                    row["subregion"] = measured
            if family in genomes and status == "SUPERSEDED":
                item = genomes[family]
                row["superseded_by"] = {"mechanism": item.genome.competitor,
                                        "deployable": bool(getattr(item, "competitor_deployable", True)),
                                        "evidence": evidence["genomes"].get(family, {}).get("evidence")}
                if family in promoted:
                    # the mechanism is already a registered genome: its own row and record govern it, and
                    # attaching it is the founder's decision (never a Genesis acquisition)
                    row["superseded_by"]["promoted_as"] = f"cognition.{promoted[family]}"
            if family in genomes and genomes[family].promotes in FAMILIES:
                row["promotes"] = f"cognition.{genomes[family].promotes}"
            rows.append(row)
    _reject_relaxations(rows, unfit, keys, g.geometry)
    rows += _organ_rows(data, g, evidence)
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
        lacking = _stage_lacks(data, recipe, g, evidence)
        if lacking:
            # the stage that reads the part would abstain on it: the recipe is not a fit. When the part carries
            # inputs only this recipe (or a fuller method) reads, it asks the recipe's question and the request
            # ends asking for what it lacks, never in an attach ask, Genesis or a stage abstention; otherwise the
            # part asks a simpler question that the methods it fully supplies answer
            row["rejected"] = (f"its {lacking['stage']} stage ({lacking['stage_method']}) reads part "
                               f"{lacking['part']!r}, which lacks {lacking['missing_inputs']}")
            if lacking["carried"]:
                row["rejected"] += f" (the part carries {lacking['carried']}, which no method it fully supplies reads)"
                row["missing_inputs"] = [{"method": row["method"], "part": lacking["part"],
                                          "missing_inputs": lacking["missing_inputs"]}]
        rows.append(row)
        if parts:
            rows += _part_rows(data, recipe, g, evidence)
    return rows


def _part_rows(data: dict, recipe: str, g: CompetencyGeometry, evidence: dict) -> list[dict]:
    """A composition request whose one typed part is the whole question (``{"capacity_network": {...}}``, the shape
    graph_then_allocate reads) asks that question of every method whose native inputs the part carries: the flat
    network is exactly what flow_expansion_mcf answers alone. Those operation rows are offered beside the recipe,
    each marked with the part it reads; ranking, the relaxation rule and attachment decide as for any row. A
    recipe of several parts is a joint question no single part answers, so it offers none."""
    from .composition import RECIPES
    required = RECIPES[recipe]["requires"]
    if len(required) != 1 or set(data) - {required[0], *PART_FLAGS} or not isinstance(data[required[0]], dict):
        return []
    part = required[0]
    return [{**row, "part": part} for row in candidates(_part_data(data, part), g, evidence, parts=False)
            if row["kind"] == "operation"]


PART_FLAGS = ("formalization_complete",)        # request-level flags a part-addressed method reads with its part


def _stage_lacks(data: dict, recipe: str, g: CompetencyGeometry, evidence: dict) -> dict | None:
    """For a recipe of one part, the inputs its first stage needs that the part does not carry, else None.

    The first stage of a one-part recipe reads the part whole (graph_then_allocate compiles
    ``capacity_network`` with compile_capacity_expansion), so the part must carry that operation's native inputs;
    without them the stage abstains and the composition cannot answer. ``carried`` lists the stage inputs the part
    does carry that no method whose native inputs the part fully supplies reads (budget and unit_cost beside a
    max-flow network): then the part asks this recipe's question with information missing, as the relaxation
    rule decides for a flat request. A part that carries none (a plain max-flow network) asks a simpler question.
    A recipe of several parts feeds its stages from several places and is not judged here."""
    from .catalog import FAMILIES
    from .composition import RECIPES
    from .genomes import library
    spec = RECIPES[recipe]
    if len(spec["requires"]) != 1 or not spec.get("operations") or not isinstance(data.get(spec["requires"][0]), dict):
        return None
    part, operation = spec["requires"][0], spec["operations"][0]
    genomes = library.executables()
    for family, (_, ops, *_rest) in FAMILIES.items():
        if operation in ops:
            need = set(genomes[family].genome.required_inputs if family in genomes else NATIVE_INPUTS.get(operation)
                       or ())
            missing = sorted(need - set(data[part]))
            if not missing:
                return None
            served = {i for r in candidates(_part_data(data, part), g, evidence, parts=False)
                      if r["kind"] == "operation" for i in r["inputs"]}
            return {"part": part, "stage": spec["stages"][0], "stage_method": f"cognition.{family}",
                    "missing_inputs": missing, "carried": sorted((need & set(data[part])) - served)}
    return None


def _part_data(data: dict, part: str) -> dict:
    """What a part-addressed method reads: the part, with the request-level flags (``formalization_complete``)."""
    return {**data[part], **{k: data[k] for k in PART_FLAGS if k in data}}


def _same_decision(row: dict, fuller: dict) -> bool:
    """True when ``row`` produces every output the fuller method does: it decides the same question with less
    side information (hysteresis vs the Bayesian regime filter, which also reads a dwell prior) and competes."""
    return row["outputs"] is not None and fuller["outputs"] is not None and set(fuller["outputs"]) <= set(row["outputs"])


def _missing_information(rows: list[dict]) -> list[dict]:
    """What the request lacks, once per (method, part, inputs): the fuller methods a relaxation was rejected for
    (``missing_for_fuller``) and the recipes whose reading stage the part cannot feed (``missing_inputs``). An
    entry from a part-addressed row names that part."""
    out = []
    for r in rows:
        for m in r.get("missing_for_fuller", []) + r.get("missing_inputs", []):
            entry = {**m, **({"part": r["part"]} if r.get("part") else {})}
            if entry not in out:
                out.append(entry)
    return out


def _lacks(missing: list[dict]) -> str:
    """'[inputs] (in part p) for [methods]', once per distinct set of missing inputs and part."""
    grouped = {}
    for m in missing:
        grouped.setdefault((tuple(m["missing_inputs"]), m.get("part") or ""), set()).add(m["method"])
    return "; ".join(f"{list(inputs)}{f' in part {part!r}' if part else ''} for {sorted(methods)}"
                     for (inputs, part), methods in sorted(grouped.items()))


def _reject_relaxations(rows: list[dict], unfit: list[dict], keys: set, geometry: str | None) -> None:
    """A method that reads a strict subset of the inputs another catalogued method consumes, while the request
    carries some of those further inputs, and that does not produce that method's decision, answers a relaxed
    question: max_flow ignores the budget, prices and increment limit of a capacity-expansion request and
    returns no increments; a feasibility check ignores an objective. It is rejected with that reason rather
    than allowed to answer a question that was not asked.

    The fuller method decides even when it is itself unusable (withheld, or excluded by its admission status):
    the request then ends in an honest deficit or attach ask, never in an answer to the relaxation. It decides
    too when the request carries only part of its inputs (budget and prices without max_increment): the
    rejection names what the request lacks for it, and the request ends asking for that information. A fuller
    method whose native geometry the declared geometry excludes does not decide: a request declared
    constraint_feasibility asks the feasibility question even when its model also carries an objective. A
    method producing the same decision from less side information is not a relaxation; it competes on
    evidence. Families without a declared output contract (native cortex families) are compared on inputs
    alone."""
    def fuller_than(row, other):
        return (other is not row and set(row["inputs"]) < set(other["inputs"]) and not _same_decision(row, other)
                and not (geometry and geometry not in other["epistemic_classes"]))
    for row in rows:
        if row["rejected"]:
            continue
        mine = set(row["inputs"])
        fuller = [r for r in rows if fuller_than(row, r)]
        # catalogued methods the request supplies in part: it carries some of their further inputs, not all
        partial = [r for r in unfit if fuller_than(row, r) and (set(r["inputs"]) - mine) & keys]
        if fuller or partial:
            ignored = sorted((set().union(*(set(r["inputs"]) for r in fuller + partial)) & keys) - mine)
            row["rejected"] = (f"answers a relaxation: ignores declared inputs {ignored} that "
                               f"{sorted(r['method'] for r in fuller + partial)} consume")
            if partial:
                row["missing_for_fuller"] = [{"method": r["method"], "missing_inputs": sorted(set(r["inputs"]) - keys)}
                                             for r in sorted(partial, key=lambda r: r["method"])]
                row["rejected"] += "; the request lacks " + _lacks(row["missing_for_fuller"])


def _organ_rows(data: dict, g: CompetencyGeometry, evidence: dict) -> list[dict]:
    """Cortex organs (Z3, CP-SAT, Fermi, evidence/causal, semantic, deterrence, schedule extraction) for payload
    parts they serve, named by the cortex's own deterministic route policy and run through the canonical problem
    path. Their status comes from the evidence index's ``organs`` section when it has one, else UNEVALUATED."""
    from cortex.routing import _route_parts      # the cortex's route policy, reused rather than re-implemented
    from .bridge import _CLASS, ORGANS
    rows = []
    for key, cls in _route_parts(data):
        cid = ORGANS.get(key)
        if cid is None:
            continue
        klass = _CLASS.get(cls, cls)
        status = (evidence.get("organs") or {}).get(cid, {}).get("status", "UNEVALUATED")
        reason = (f"native geometry {klass} does not include {g.geometry}" if g.geometry and g.geometry != klass
                  else f"frozen status {status}" if status in EXCLUDED else None)
        rows.append({"method": cid, "operation": "problem", "kind": "problem", "status": status, "organ": key,
                     "epistemic_classes": [klass], "rejected": reason})
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


def _rank(row: dict, prefer: list, competence: dict) -> tuple:
    status = 0 if row["status"] == "VPL_LIFT" else STATUS_RANK.get(row["status"], 5)
    preferred = 0 if (row["operation"] in prefer or row["method"] in prefer) else 1
    settled = -competence.get(row["method"], 0.5)
    region = SUBREGION_RANK.get((row.get("subregion") or {}).get("verdict"), 1)
    latency = row.get("median_seconds")
    # Frozen negative evidence outranks an operator's preference: evidence over heuristics. Within one status,
    # the measured subregion verdict orders fits before settled competence, then measured held-out latency
    # (unmeasured last), then operations before compositions and organs.
    return (1 if row.get("demoted") else 0, preferred, status, region, settled,
            latency if latency is not None else float("inf"), 0 if row["kind"] == "operation" else 1, row["method"])


NEGATION = {"<=": ">", ">=": "<", "<": ">=", ">": "<=", "==": "!=", "!=": "=="}


def invert_claim(claim: dict) -> dict:
    """Inversion as an executable representation change: 'these constraints imply this property' holds exactly
    when 'constraints AND NOT property' is unsatisfiable, so the claim becomes a formal feasibility instance.
    The negation is exact over the reals (strict comparisons), never an epsilon approximation."""
    if (set(claim) - {"variables", "constraints", "property"} or not isinstance(claim.get("property"), dict)
            or not isinstance(claim.get("constraints"), list)):
        raise CognitionError("a claim takes variables, constraints and one linear property")
    prop = claim["property"]
    if (set(prop) != {"coefficients", "op", "rhs"} or not isinstance(prop["op"], str) or prop["op"] not in NEGATION
            or not isinstance(prop["coefficients"], dict) or isinstance(prop["rhs"], bool)
            or not isinstance(prop["rhs"], (int, float, str))):
        raise CognitionError("the property is one linear comparison {coefficients, op, rhs}")
    if not all(isinstance(c, dict) for c in claim["constraints"]):
        raise CognitionError("every constraint is a linear comparison mapping")
    return {"variables": claim["variables"],
            "constraints": list(claim["constraints"]) + [{**prop, "op": NEGATION[prop["op"]]}]}


def premises(claim: dict) -> dict:
    """The claim's constraints alone: if they are unsatisfiable, every property 'holds' vacuously."""
    return {"variables": claim["variables"], "constraints": list(claim["constraints"])}


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


def _operation_usable(registry, operation: str) -> bool:
    """Some attached, available capability on the registry declares this cognitive operation."""
    for cid, manifest in getattr(registry, "manifests", {}).items():
        profile = getattr(manifest, "cognitive_profile", None) or {}
        if operation in (profile.get("operations") or ()):
            try:
                if registry.usable(cid)[0]:
                    return True
            except Exception:
                continue
    return False


def _usable(registry, row: dict) -> tuple[bool, str]:
    """Whether the row can run now: an operation's capability must be attached; a composition needs an
    attached capability for every operation stage it declares (problem-path stages are routed on the canonical
    path and checked there)."""
    if row["kind"] == "problem":
        from .bridge import ROUTER
        for cid in (ROUTER, row["method"]):
            try:
                ok, why = registry.usable(cid) if cid in registry.manifests else (False, "not registered")
            except Exception as exc:
                ok, why = False, f"registry: {type(exc).__name__}"
            if not ok:
                return False, f"{cid}: {why}"
        return True, "organ attached behind the attached cortex router"
    if row["kind"] != "operation":
        from .composition import RECIPES
        missing = [op for op in RECIPES[row["operation"]].get("operations", ()) if not _operation_usable(registry, op)]
        if missing:
            return False, f"composition stages without an attached capability: {missing}"
        return True, "composition: every declared operation stage has an attached capability"
    try:
        ok, why = registry.usable(row["method"])
    except Exception as exc:
        return False, f"registry: {type(exc).__name__}"
    return bool(ok), str(why)


def _state(registry, method: str) -> str | None:
    try:
        return registry.state.get(method)
    except Exception:
        return None


def _formed(registry, data: dict, g: CompetencyGeometry, body: dict, high: bool, receipt: dict):
    """Directive section 24, after the founder's attach: a mechanism Capability Genesis formed for a residual
    geometry (an installed open-source engine qualified on GREG's frozen oracle; ``greg.genesis``) serves it.

    Reached only when no catalogued method fits or can run. The founder's attach is the only way such a mechanism
    becomes usable; every answer is accepted only on GREG's own certificate, which shares no code with the engine.
    A refusal (input outside competence, a changed package, a failed certificate) is recorded and the deficit
    stands. Returns ``(state, result)`` or None."""
    try:
        from greg import genesis
        formed = genesis.formed_cognition(registry, data, g.geometry)
    except Exception as exc:          # a registry object without the views Genesis reads: recorded, not fatal
        receipt["dissent"].append(f"formed mechanisms not consulted: {type(exc).__name__}: {exc}"[:300])
        return None
    for manifest, adapter in formed:
        cid, spec = manifest.capability_id, genesis.CATALOG[manifest.function]
        receipt["methods_considered"].append(cid)
        receipt["method_or_composition_selected"], receipt["selection_level"] = cid, "formed_by_capability_genesis"
        if high and data.get("formalization_complete") is not True:
            receipt["abstentions"].append("FORMALIZATION_INCOMPLETE: complete formal model plus independently "
                                          "verified world assumptions")
            return "FORMALIZATION_INCOMPLETE", None
        if body.get("execute") is False:
            return "PLANNED", None
        try:
            answer = genesis.run_formed(manifest, adapter, data)
        except Exception as exc:
            receipt["abstentions"].append(f"{cid} refused: {exc}"[:300])
            receipt["method_or_composition_selected"] = receipt["selection_level"] = None
            continue
        receipt.update(proof_artifacts=[{"type": "genesis_mechanism_certificate",
                                         "evidence_type": spec["evidence_type"]}],
                       verification_method=f"GREG-owned certificate sharing no code with {answer.get('engine')}: "
                                           f"{answer['certificate']['kind']}",
                       confidence_type=spec["evidence_type"],
                       uncertainty="exact for the declared inputs; whether they describe the world is not verified")
        receipt["resource_use"]["stages"] = 1
        if receipt.get("withheld_best_fit"):
            receipt["withheld_best_fit"]["served_by"] = cid
        return ("WORLD_UNVERIFIED" if high else "ANSWERED"), answer
    return None


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
    if best.get("promotes"):
        # the frozen evidence that made this mechanism worth promoting, labelled for what it measured
        former = evidence.get("genomes", {}).get(best["promotes"].removeprefix("cognition."), {})
        measured["promotes"] = {k: v for k, v in {
            "superseded_method": best["promotes"], "superseded_status": former.get("status"),
            "supersession_evidence": former.get("evidence"),
            "scope": "that evidence measured this mechanism as the superseded genome's competitor arm, not this "
                     "genome's code; this genome's own status is admission_status"}.items() if v is not None}
    served = fallback["method"] if fallback else "no attached method"
    measured["registered"] = [{"capability_id": best["method"], "state": "VERIFIED"}]
    # one ask per method and measured version, however many requests need it (never one per request)
    packet = asks.resource_request(
        request_id=f"attach-{digest({'method': best['method'], 'version': record.get('version')})[7:23]}",
        kind="CAPABILITY_ATTACH",
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
    violations = asks.screen(packet, quoted=(pid,))      # the caller's problem id is data, not GREG's wording
    if violations:
        raise CognitionError(f"the attach ask failed the ask screen: {violations}")
    return packet


def _judgment_ask(pid: str, request_id: str, scope: str, packet: dict, journal) -> dict:
    """Record the question as a founder ask through greg.asks (the one path for decision.requested), once, when
    a canonical journal is present; otherwise return it prepared. Recording asks; it decides and grants nothing."""
    from datetime import datetime, timezone
    from greg import asks
    from .human import judgment_ask
    return _record_once(journal, judgment_ask(pid, request_id, scope, packet, datetime.now(timezone.utc).isoformat()),
                        quoted=(pid,))


def _record_once(journal, message: dict, *, quoted=()) -> dict:
    """Record one founder ask through greg.asks (the one path for decision.requested) when a canonical journal is
    present, at most once per request id; otherwise return it prepared. Asking decides and grants nothing."""
    from greg import asks
    rid = message["request_id"]
    existing = None if journal is None else next(
        (e.payload for e in journal.replay("decision.requested") if e.payload.get("request_id") == rid), None)
    if existing is not None:
        return {"request_id": rid, "kind": existing.get("kind"), "state": "RECORDED",
                "scope_digest": existing.get("scope_digest")}
    if journal is None or not callable(getattr(journal, "record", None)):
        asks.validate(message)
        return {**message, "state": "PREPARED_NOT_RECORDED",
                "record_with": "greg.asks.record on the body (the one path for decision.requested)"}
    shown = asks.record(journal, message, quoted=quoted)
    return {"request_id": rid, "kind": shown["kind"], "state": "RECORDED", "scope_digest": shown["scope_digest"]}


SETTLED_MIN_N = 10              # settled outcomes before live evidence may inhibit a method


def _settled_counts(journal) -> dict:
    """Settled (count, correct) per method from the canonical journal, summed over versions and geometries."""
    if journal is None:
        return {}
    from .settlement import competence
    out = {}
    for (method, _version, _geometry), record in competence(journal).items():
        n, k = out.get(method, (0, 0))
        out[method] = (n + record.get("count", 0), k + record.get("correct", 0))
    return {m: v for m, v in out.items() if v[0]}


def _settled_competence(journal, geometry_class) -> dict:
    """Mean settled correctness per method (Laplace), from the canonical journal (existing settlement)."""
    return {m: (k + 1) / (n + 2) for m, (n, k) in _settled_counts(journal).items()}


def _settled_inhibition(n: int, k: int) -> str | None:
    """Live negative evidence: with at least SETTLED_MIN_N settled outcomes, a method whose 95% Wilson upper bound
    on correctness is below one half is demoted (ranked after every other fit, never deleted)."""
    if n < SETTLED_MIN_N:
        return None
    from .settlement import _wilson
    upper = _wilson(k, n)[1]
    return (f"settled outcomes on this body: {k} of {n} correct (95% upper bound {upper:.3f} < 0.5)"
            if upper < 0.5 else None)


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
               "subgeometry": g.subgeometry, "consequence_class": g.consequence_class or "undeclared",
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
               "outcome_link": None, "later_appraisal": None, "state": None, "capability_deficit": None,
               "selected_receipt": None}

    def finish(state, result=None):
        receipt["state"], receipt["result"] = state, result
        receipt["requirements"] = list(dict.fromkeys(plan["requirements"]))
        receipt["dissent"] = list(dict.fromkeys(receipt["dissent"] + plan["dissent"]))
        receipt["latency_s"] = round(time.monotonic() - started, 4)
        receipt["receipt_id"] = digest({k: v for k, v in receipt.items() if k != "receipt_id"})
        return receipt

    from .contracts import ConsequenceVector
    try:
        vector = ConsequenceVector(**consequence)
    except TypeError as exc:
        raise CognitionError("compile.consequence takes ConsequenceVector fields (harm levels 0-1, lawful, "
                             "consent, exposure_details)") from exc
    # 1. constitutional pre-filter: hard eligibility before any optimisation
    if vector.prohibited:
        receipt["abstentions"].append("law, consent and rights constraints are eligibility gates; upside cannot compensate")
        return finish("PROHIBITED")
    if g.human_judgment_required or g.legal_content or g.rights_impact or g.geometry in HUMAN_CLASSES:
        receipt["method_or_composition_selected"] = "human:qualified_judgment"
        receipt["selection_level"] = "constitutional_route"
        # the question's identity: what the founder's signed answer must be bound to (judgments excluded,
        # so views arriving later address the same question)
        scope = digest({"problem_id": pid, "geometry": body.get("geometry", {}), "data": data,
                        "consequence": consequence})
        request_id = f"judgment-{scope[7:23]}"
        packet = {**human_packet(g, body), "request_id": request_id, "scope_digest": scope}
        judgments = (body.get("human") or {}).get("judgments")
        # the return path: typed judgments are evidence; only the founder's signed answer to THIS request decides
        from .human import adjudicate
        adjudicated = adjudicate(judgments, journal, request_id=request_id, scope_digest=scope)
        if judgments is not None or adjudicated["decision"] is not None:
            receipt["human_judgments"] = adjudicated
        for j in adjudicated["judgments"]:
            if j["verdict"] != (adjudicated["decision"] or {}).get("verdict"):
                receipt["dissent"].append(f"{j['role']} {j['participant_ref']} ({j['competence_domain']}): "
                                          f"{j['verdict']}: {j['rationale'][:200]}")
        receipt["dissent"] += adjudicated["provenance_conflicts"]
        if adjudicated["decision"] is None:
            ask = _judgment_ask(pid, request_id, scope, packet, journal)
            return finish("HUMAN_JUDGMENT_REQUIRED", {**packet, "judgments_received": len(adjudicated["judgments"]),
                                                       "awaiting": "the founder's signed answer to " + request_id,
                                                       "founder_ask": ask})
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
    rows = candidates(data, g, evidence)
    # the geometry the inputs themselves imply (methods whose native inputs they carry), against the declaration
    from dataclasses import replace
    implied = sorted({c for r in candidates(data, replace(g, geometry=None), evidence)
                      for c in r.get("epistemic_classes", [])})
    receipt["derived_geometry"] = {"declared": g.geometry, "fits_by_inputs": implied,
                                   "agrees": not g.geometry or not implied or g.geometry in implied}
    if not receipt["derived_geometry"]["agrees"]:
        receipt["dissent"].append(f"declared geometry {g.geometry!r} but the inputs fit methods of {implied}: the "
                                  f"declaration excludes them (check the declaration before trusting a deficit)")
    receipt["methods_considered"] = [r["method"] for r in rows]
    receipt["methods_rejected"] = [{"method": r["method"], "why": r["rejected"]} for r in rows if r["rejected"]]
    receipt["methods_demoted"] = [{"method": r["method"], "why": r["demoted"]} for r in rows if r.get("demoted")]
    eligible = [r for r in rows if not r["rejected"]]
    superseding = [{"mechanism": r["superseded_by"]["mechanism"], "supersedes": r["method"],
                    "evidence": r["superseded_by"]["evidence"],
                    "route": "greg.genesis (Capability Genesis) under the enclosing mission's authority",
                    "authority": "none: a candidate to acquire, never an attached method"}
                   for r in rows if r.get("superseded_by", {}).get("deployable")
                   and not r["superseded_by"].get("promoted_as")]
    high = g.consequence_class in HIGH_CONSEQUENCE or vector.high
    if not eligible:
        formed = _formed(registry, data, g, body, high, receipt)
        if formed is not None:
            return finish(*formed)
        missing = _missing_information(rows)
        if missing:
            # the method that answers the question asked exists; the request lacks some of its inputs. That is
            # missing information, not a capability deficit: Capability Genesis is not asked to build it again
            receipt["missing_information"] = missing
            receipt["abstentions"].append("missing information: the request lacks " + _lacks(missing))
            return finish("ABSTAIN")
        if superseding:
            # the method that fits was superseded on frozen held-out evidence by a deployable mechanism: name it
            receipt["acquisition_candidates"] = superseding
        receipt["capability_deficit"] = {
            "function": f"cognition.{g.geometry or 'unknown'}:{g.subgeometry or 'unspecified'}",
            "purpose": g.objective or g.epistemic_question or "cognitive request",
            "required_inputs": sorted(data), "geometry": g.known(),
            "verification": {"failed": ("every catalogued method that reads these inputs is ineligible here "
                                        "(unserviceable lists why)" if rows else
                                        f"the request's shape (keys {sorted(data)}) matches no catalogued method's "
                                        f"native inputs"),
                             "unserviceable": receipt["methods_rejected"] or "no method declares these inputs",
                             "verified": True},
            "search_order": list(GENESIS_SEARCH),
            "route": "greg.genesis (Capability Genesis) under the enclosing mission's authority"}
        return finish("CAPABILITY_DEFICIT")
    competence = _settled_competence(journal, g.geometry)
    settled = _settled_counts(journal)
    for r in eligible:
        inhibited = _settled_inhibition(*settled.get(r["method"], (0, 0)))
        if inhibited and not r.get("demoted"):
            r["demoted"] = inhibited                    # live negative evidence changes routing
    receipt["methods_demoted"] = [{"method": r["method"], "why": r["demoted"]} for r in rows if r.get("demoted")]
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
                                                      else {}),
                                        **({"promotes": best["promotes"]} if best.get("promotes") else {})}
        state = _state(registry, best["method"])
        if best["kind"] == "composition" or state != "VERIFIED":
            # only a verified, withheld capability is attachable by the founder's attach command; a quarantined,
            # detached or attached-but-unavailable one is not asked about here
            receipt["founder_attach_ask"] = {"state": "NOT_PREPARED",
                                             "why": f"{best['method']} is {best['usable_why']}; only a VERIFIED "
                                                    f"capability can be attached"}
        else:
            try:
                receipt["founder_attach_ask"] = _record_once(
                    journal, attach_ask(pid, best, runnable[0] if runnable else None, evidence), quoted=(pid,))
            except Exception as exc:      # the optional ask never aborts routing; its failure is recorded
                receipt["founder_attach_ask"] = {"state": "NOT_PREPARED", "why": f"{type(exc).__name__}: {exc}"[:300]}
    if not runnable:
        formed = _formed(registry, data, g, body, high, receipt)
        if formed is not None:
            return finish(*formed)
        receipt["capability_deficit"] = {
            "function": f"cognition.{g.geometry or 'unknown'}:{g.subgeometry or 'unspecified'}",
            "purpose": g.objective or g.epistemic_question or "cognitive request",
            "required_inputs": sorted(data), "geometry": g.known(),
            "verification": {"failed": "every fitting method is registered but not attached",
                             "unserviceable": [{"method": r["method"], "why": r["usable_why"]} for r in eligible],
                             "verified": True},
            "search_order": list(GENESIS_SEARCH),
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
    # 4. execute through the same canonical reason. High consequence raises the proof requirement on this path
    # exactly as on the direct canonical path (FORMALIZATION_INCOMPLETE for formal/optimisation methods).
    high = g.consequence_class in HIGH_CONSEQUENCE or vector.high
    extra = {"consequences": consequence} if consequence else {}
    if chosen["kind"] == "problem":
        from cortex.routing import FORMAL_ENGINES
        if high and chosen["organ"] in FORMAL_ENGINES and data.get("formalization_complete") is not True:
            receipt["abstentions"].append("FORMALIZATION_INCOMPLETE: complete formal model plus independently "
                                          "verified world assumptions")
            return finish("FORMALIZATION_INCOMPLETE")
        inner = reason({"problem_id": pid, "problem": {"question": g.objective or g.epistemic_question or pid,
                                                       "payload": data}},
                       registry=registry, journal=journal, model_config=model_config)
        receipt["intermediate_receipts"] = [inner["receipt_id"]]
        receipt["selected_receipt"] = inner
        receipt["proof_artifacts"] = [{"type": inner.get("proof_type"),
                                       "evidence_type": (inner.get("proof_artifact") or {}).get("evidence_type")}]
        receipt["verification_method"] = (inner.get("evaluator_result") or {}).get("independence") or \
            "cortex adversarial verifier"
        receipt["confidence_type"] = receipt["proof_artifacts"][0]["evidence_type"] or inner.get("proof_type")
        receipt["uncertainty"] = inner.get("uncertainty")
        receipt["resource_use"]["stages"] = 1
        if not _has_answer(inner):
            receipt["abstentions"].append(f"{inner['abstention_state']}: {inner.get('missing_information')}")
            return finish(inner["abstention_state"])
        return finish("WORLD_UNVERIFIED" if high or inner["abstention_state"] == "WORLD_UNVERIFIED" else "ANSWERED",
                      inner["output"])
    if chosen["kind"] == "composition":
        from .composition import RECIPES
        if high and "optimize" in RECIPES[chosen["operation"]]["stages"] and data.get("formalization_complete") is not True:
            receipt["abstentions"].append("FORMALIZATION_INCOMPLETE: complete formal model plus independently "
                                          "verified world assumptions")
            return finish("FORMALIZATION_INCOMPLETE")
        inner = reason({"problem_id": pid, "chain": {"question": g.objective or "compiled", "payload": data}},
                       registry=registry, journal=journal, model_config=model_config)
        receipt["intermediate_receipts"] = [s["receipt_id"] for s in inner["stages"]]
        receipt["dissent"] += [f"stage {s['stage']} ({s['method']}): {s['counterargument']}"[:400]
                               for s in inner["stages"] if s.get("counterargument")]
        receipt["translation_checks"] = inner["bindings"] + inner["translation_failures"]
        receipt["resource_use"]["stages"] = len(inner["stages"])
        receipt["verification_method"] = "per-stage independent verifier; cross-intelligence checks where declared"
        receipt["confidence_type"] = "composition of typed stage evidence"
        if inner["state"] != "ANSWERED":
            receipt["abstentions"].append(f"{inner['state']}: {inner['reason']}")
            return finish(inner["state"])
        return finish("ANSWERED", inner["answer"])
    geometry_hint = {"latency_limit": min(30.0, float(g.latency_budget or 20.0)),
                     **({"consequence_class": g.consequence_class} if g.consequence_class else {})}
    if chosen.get("part"):
        receipt["payload_part"] = chosen["part"]          # the method reads this part of the request: the question
        data = _part_data(data, chosen["part"])
    inner = reason({"problem_id": pid, "operation": chosen["operation"], "data": data, "geometry": geometry_hint,
                    **extra}, registry=registry, journal=journal, model_config=model_config)
    receipt["intermediate_receipts"] = [inner["receipt_id"]]
    # the executed method's own receipt, whole: settlement credits that method through this compilation
    # (greg.cognition.settlement), and the compile receipt is the link back from the outcome
    receipt["selected_receipt"] = inner
    receipt["proof_artifacts"] = [{"type": inner["proof_type"],
                                   "evidence_type": (inner.get("proof_artifact") or {}).get("evidence_type")}]
    receipt["verification_method"] = (inner.get("evaluator_result") or {}).get("independence")
    receipt["confidence_type"] = receipt["proof_artifacts"][0]["evidence_type"] or inner["proof_type"]
    receipt["uncertainty"] = inner.get("uncertainty")
    receipt["dissent"].append(inner.get("strongest_counterargument", ""))
    receipt["resource_use"]["stages"] = 1
    conditional = inner["abstention_state"] == "WORLD_UNVERIFIED" and _has_answer(inner)
    if inner["abstention_state"] != "NONE":
        receipt["abstentions"].append(f"{inner['abstention_state']}: {inner['missing_information']}")
        if not conditional:
            return finish(inner["abstention_state"])
    # a high-consequence answer is a conditional result (WORLD_UNVERIFIED), never ANSWERED: the answer is kept,
    # evaluated (sensitivity, premises) and labelled; world assumptions and consequence authority stay separate
    done = "WORLD_UNVERIFIED" if conditional else "ANSWERED"
    if inverted is not None:
        verdict = claim_verdict(inner["output"])
        if verdict["claim"] == "HOLDS_WITHIN_MODEL":
            verdict = _premises_check(pid, chosen["operation"], body["data"]["claim"], geometry_hint, verdict,
                                      registry, journal, model_config, receipt, extra)
        return finish(done, verdict)
    if "sensitivity" in plan["evaluate"]:
        receipt["sensitivity"] = _sensitivity_runs(pid, chosen["operation"], data, inner["output"], geometry_hint,
                                                   registry, journal, model_config, receipt, extra)
    return finish(done, inner["output"])


def _has_answer(inner: dict) -> bool:
    """An answer the path may use: NONE, or the conditional WORLD_UNVERIFIED a high-consequence geometry gets.
    A refuted or timed-out receipt keeps its output for audit, never for use."""
    return inner["abstention_state"] in ("NONE", "WORLD_UNVERIFIED") and isinstance(inner.get("output"), dict)


def _premises_check(pid, operation, claim, hint, verdict, registry, journal, model_config, receipt, extra) -> dict:
    """An UNSAT negation proves the claim only if the constraints are satisfiable on their own; otherwise every
    property 'holds' vacuously and the claim is PREMISES_INCONSISTENT."""
    from .cortex import reason
    if not claim["constraints"]:
        return {**verdict, "premises": "SATISFIABLE (no constraints)"}
    check = reason({"problem_id": f"{pid}/premises"[:96], "operation": operation, "data": premises(claim),
                    "geometry": hint, **extra}, registry=registry, journal=journal, model_config=model_config)
    receipt["intermediate_receipts"].append(check["receipt_id"])
    status = check["output"].get("solver_status") if _has_answer(check) else None
    if status == "UNSAT":
        return {"claim": "PREMISES_INCONSISTENT",
                "basis": "the constraints alone are unsatisfiable, so the property holds only vacuously"}
    if status == "SAT":
        return {**verdict, "premises": "SATISFIABLE"}
    return {**verdict, "premises": f"UNDECIDED ({status or check['abstention_state']}): the claim may hold vacuously"}


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


def _sensitivity_runs(pid, operation, data, baseline, hint, registry, journal, model_config, receipt, extra) -> dict:
    """Perturb each numeric top-level input by +10% (at most four) and re-run the same method on the one path."""
    from .cortex import reason
    keys = [k for k in sorted(data) if _numbers(data[k])][:4]
    base = _numbers(baseline)
    rows = {}
    for key in keys:
        varied = {**data, key: _scaled(data[key], 1.1)}
        out = reason({"problem_id": f"{pid}/sens/{key}"[:128], "operation": operation, "data": varied,
                      "geometry": hint, **extra}, registry=registry, journal=journal, model_config=model_config)
        receipt["intermediate_receipts"].append(out["receipt_id"])
        if not _has_answer(out):
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
