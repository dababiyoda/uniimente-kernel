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
from functools import lru_cache
import json
from pathlib import Path
import time

from .contracts import CognitionError, canonical, digest, strict_data

SCHEMA = "greg-competency-compilation/0.2"   # 0.2: selected_receipt (the executed method's own receipt)
# The confidence label of an answer from a construction whose problem-level certificate GREG checked.
CERTIFIED = "certified: exact problem-level certificate"
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_INDEX = ROOT / "docs" / "evidence" / "greg-mind-evidence-index.json"
# The thinking budget's clock (directive section 12); a module attribute so tests can drive it deterministically.
CLOCK = time.monotonic
DEFAULT_BUDGET_S = 20.0
HIGH_CONSEQUENCE = ("external_contact", "financial", "irreversible")
HUMAN_CLASSES = ("normative", "legal", "institutional_acceptance")
HUMAN_ROLES = ("founder", "operator", "domain_expert", "affected_participant", "auditor", "customer",
               "professional", "regulator")
STATUS_RANK = {"DEFAULT_FOR_GEOMETRY": 0, "NICHE_CAPABILITY": 1, "UNEVALUATED": 2, "CONSTRUCTED_VERIFIED": 2,
               "EXPERIMENTAL": 3, "NO_LIFT": 8,
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
    # PR #155 repertoire, where the input signature names the question unambiguously. robust_anomalies is not
    # listed: it reads ("observations",) like anomalies and quorum, and all three are one epistemic class, so
    # an observations-only request cannot say which question it asks (it stays reachable by its operation).
    "crowd_label": ("classes", "labels"), "swarm_minimize": ("function", "shift", "bounds", "budget", "seed"),
    "evolve_blackbox": ("function", "shift", "bounds", "budget", "seed"),
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
    """Frozen results that change routing: genome and operation-family admission statuses, recipe lift
    verdicts, P4 demotion."""
    path = path or EVIDENCE_INDEX
    if not path.exists():
        return {"genomes": {}, "recipes": {}, "routing": {}, "operations": {}}
    return json.loads(path.read_text())


def function_digest(text: str, name: str) -> str | None:
    """sha256 of a module-level function's source lines, decorators included, with trailing whitespace
    stripped; None when the module defines no such function. Source text, not an AST dump, so the digest does
    not change with the Python version."""
    import ast
    import hashlib
    for node in ast.parse(text).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            lines = text.splitlines()[start - 1:node.end_lineno]
            return "sha256:" + hashlib.sha256("\n".join(line.rstrip() for line in lines).encode()).hexdigest()
    return None


@lru_cache(maxsize=None)
def solver_code(family: str) -> dict | None:
    """The operation family's solver as it is now: repository path, function name and source digest."""
    import inspect
    from .solvers import SOLVERS
    fn = SOLVERS.get(family)
    if fn is None:
        return None
    from .code_binding import closure
    path = Path(inspect.getsourcefile(fn)).resolve()
    rel = path.relative_to(ROOT).as_posix()
    bound = closure(rel, fn.__name__)
    return {"path": rel, "function": fn.__name__, "sha256": function_digest(path.read_text(), fn.__name__),
            "closure_sha256": bound["sha256"] if bound else None, "closure_members": bound["members"] if bound else {},
            "closure_unresolved": bound["unresolved"] if bound else []}


def operation_status(family: str, record: dict) -> tuple[str, str | None]:
    """(routing status, stale reason) for an operation family's frozen verdict (PR #155 lineage).

    Like a genome's version rule: positive evidence binds the executable code measured, the static dependency
    closure of the solver function at the run's source commit (greg.cognition.code_binding: the function, the
    repository helpers, classes and module constants it reaches). Any changed member routes the family as
    UNEVALUATED until re-admitted; negative and inconclusive evidence persists with its original scope. A
    positive verdict bound only to the entry function, or not bound at all, is treated as stale."""
    status = record.get("status", "UNEVALUATED")
    if status in NOT_POSITIVE or status == "UNEVALUATED":
        return status, None
    if "competitor" in record and not record.get("competitor"):
        # a DEFAULT measured only against a baseline, with no competitor, is not an admission under the rule the
        # genomes follow (review of #179, H4): it routes as UNEVALUATED until a re-admission names a competitor
        return "UNEVALUATED", (f"{status} was measured against a baseline only (no competitor in its frozen run); "
                               "needs re-admission against a competitor")
    code, now = record.get("code") or {}, solver_code(family) or {}
    measured = code.get("closure_sha256")
    if measured is not None and (code.get("path"), code.get("function")) != (now.get("path"), now.get("function")):
        # the family now dispatches to another function than the one its run called (review of #179, B1)
        return "UNEVALUATED", (f"{status} was measured on {code.get('path')}::{code.get('function')}; the family now "
                               f"dispatches to {now.get('path')}::{now.get('function')}; needs re-admission")
    dispatched = code.get("dispatched") or {}
    if dispatched.get("runtime_disagrees"):
        seen = dispatched["runtime_disagrees"]
        return "UNEVALUATED", (f"{status}: the run recorded {seen.get('path')}::{seen.get('function')} at runtime, "
                               f"not the statically bound {dispatched.get('path')}::{dispatched.get('function')}; "
                               "nothing is bound; needs re-admission")
    unbound = [*([f"{dispatched['unresolved_updates']} non-literal update(s) of the dispatch table at the run's "
                  "commit, and the run recorded no runtime dispatch that confirms it"]
                 if dispatched.get("unresolved_updates") and not dispatched.get("verified_at_runtime") else []),
               *(code.get("closure_unresolved") or []), *(now.get("closure_unresolved") or [])]
    if measured is not None and unbound:
        # code the static closure cannot follow binds nothing positive (round-2 review of #179, N4)
        return "UNEVALUATED", f"{status} cannot be bound to its code: {'; '.join(unbound)}; needs re-admission"
    if measured is None:
        return "UNEVALUATED", (f"{status} is bound to the solver's entry function only "
                               f"({code.get('sha256') or 'not recorded'}), not its dependency closure; "
                               "needs re-admission")
    if measured != now.get("closure_sha256"):
        then, current = code.get("closure_members") or {}, now.get("closure_members") or {}
        # a member whose own code changed, apart from one the closure now reaches that it did not (unchanged code
        # newly called by a changed member), apart from one it no longer reaches
        changed = sorted(k for k in set(then) & set(current) if then[k] != current[k])
        added, removed = sorted(set(current) - set(then)), sorted(set(then) - set(current))
        return "UNEVALUATED", (f"{status} was measured on solver closure {measured}; changed since: "
                               f"{', '.join(changed) or 'none'}"
                               + (f"; added to the closure since: {', '.join(added)}" if added else "")
                               + (f"; no longer in the closure: {', '.join(removed)}" if removed else "")
                               + ("" if changed or added or removed else " (members not recorded)")
                               + "; needs re-admission")
    return status, None


RECIPE_BOUNDARY = frozenset({"greg/cognition/cortex.py::reason", "greg/cognition/bridge.py::reason_cortex"})


def recipe_code(recipe: str, read=None) -> dict | None:
    """The executable a recipe verdict measured: the dependency closure of the function that runs the recipe
    (its operation-recipe function, or ``run`` for a template recipe) plus the digest of its RECIPES entry."""
    import hashlib
    import json as _json
    from . import code_binding
    from .composition import RECIPES
    read = read or code_binding.working_tree
    # the function OPERATION_RECIPES bound the recipe to in that tree, never today's (round-2 review, N5 / B1)
    then = code_binding.dispatch("greg/cognition/composition.py", "OPERATION_RECIPES", recipe, read)
    function = "run" if then is None else then.get("function")     # no operation recipe then: the template runner
    if function is None:
        return None
    # the stages run through cortex.reason, whose solvers carry their own bindings: hash it, do not follow it
    bound = code_binding.closure((then or {}).get("path") or "greg/cognition/composition.py", function, read,
                                 stop=RECIPE_BOUNDARY)
    if bound is None:
        return None
    entry = "sha256:" + hashlib.sha256(_json.dumps(RECIPES.get(recipe), sort_keys=True).encode()).hexdigest()
    return {"function": bound["entry"], "closure_sha256": bound["sha256"], "closure_members": bound["members"],
            "closure_unresolved": bound["unresolved"], "dispatched": then, "recipe_entry_sha256": entry,
            "stage_closures": _stage_closures(recipe, read)}


def _stage_closures(recipe: str, read) -> dict:
    """Each genome that can serve one of the recipe's stage operations -> its solve closure digest in that tree
    (None when absent). The recipe's own closure stops at cortex.reason, so a behaviour change in a stage solver
    must still stale the recipe's verdict (round-3 review of #179, finding 1)."""
    import inspect
    from . import code_binding
    from .composition import RECIPES
    from .genomes import library
    from .catalog import FAMILIES
    entry = RECIPES.get(recipe) or {}
    operations = set(entry.get("operations") or ())
    out = {}
    for family, item in sorted(library.executables().items()):
        if getattr(item.genome, "operation", None) not in operations:
            continue
        path = Path(inspect.getsourcefile(item.solve)).resolve().relative_to(ROOT).as_posix()
        bound = code_binding.closure(path, item.solve.__name__, read)
        out[family] = None if bound is None else bound["sha256"]
    # operation families served through SOLVERS, resolved at that tree (round-4 review of #179, finding A)
    genomes = library.executables()
    for family, spec in sorted(FAMILIES.items()):
        if family not in genomes and operations & set(spec[1]):       # genome families are bound above
            then = code_binding.dispatch("greg/cognition/solvers.py", "SOLVERS", family, read)
            bound = (code_binding.closure(then["path"], then["function"], read)
                     if then and then.get("path") and then.get("function") else None)
            out[f"solvers:{family}"] = None if bound is None else bound["sha256"]
    if any(not k.startswith("solvers:") for k in out):
        # genome stages run through the runtime adapter, not the bound solve (round-5 review of #179, N4)
        for path, name in (("greg/cognition/solvers.py", "_genome_solver"), ("greg/cognition/genomes/library.py", "run")):
            bound = code_binding.closure(path, name, read)
            out[f"adapter:{name}"] = None if bound is None else _digest_members(bound["members"], ADAPTER_REGISTRY)
    if out:
        # every statement that can rebind a SOLVERS key, the forms dispatch() cannot resolve included (N4)
        out["dispatch:SOLVERS"] = code_binding.table_statements("greg/cognition/solvers.py", "SOLVERS", read)
    # problem-path stages served by cortex organs (template recipes); an unmapped class binds None (fails closed)
    for klass in entry.get("stage_classes") or ():
        for path, name in STAGE_ORGANS.get(klass, ((None, None),)):
            bound = code_binding.closure(path, name, read) if path else None
            out[f"organ:{klass}:{name}"] = None if bound is None else bound["sha256"]
    if entry.get("stage_classes"):
        # the route policy that picks a stage's organ, and every organ the cortex router can instantiate, derived
        # from cortex.routing rather than a hand copy: an edit to any of them stales a template recipe (N4)
        for path, name in [("cortex/routing.py", "_route_parts"), *_router_organs()]:
            bound = code_binding.closure(path, name, read)
            out[f"route:{name}"] = None if bound is None else bound["sha256"]
    return out


# The genome registry tuple decides only which genome serves a family. Each stage family is bound by its own solve
# closure above, so a registry change that reached a stage would stale the recipe there; adding unrelated genome
# modules must not (merge of #158 fa0d92a0 added two modules and staled every genome-stage recipe through it).
ADAPTER_REGISTRY = frozenset({"greg/cognition/genomes/library.py::MODULES"})


def _digest_members(members: dict, exclude: frozenset) -> str:
    import hashlib
    import json as _json
    kept = {k: v for k, v in members.items() if k not in exclude}
    return "sha256:" + hashlib.sha256(_json.dumps(kept, sort_keys=True).encode()).hexdigest()


def _router_organs() -> list[tuple[str, str]]:
    """(path, class) of every organ class cortex.routing imports, today."""
    import inspect
    import cortex.routing as routing
    out = set()
    for name, obj in vars(routing).items():
        if isinstance(obj, type) and name.endswith("Organ") and obj.__module__.startswith("cortex.organs"):
            out.add((Path(inspect.getsourcefile(obj)).resolve().relative_to(ROOT).as_posix(), obj.__name__))
    return sorted(out)


# The cortex organs that can serve a template recipe's problem-path stage class (cortex.routing's organ set).
STAGE_ORGANS = {"estimate": (("cortex/organs/estimation.py", "EstimationOrgan"),),
                "causal": (("cortex/organs/evidence_causal.py", "EvidenceCausalOrgan"),),
                "optimization": (("cortex/organs/cpsat.py", "CpSatOrgan"), ("cortex/organs/formal.py", "FormalOrgan"))}


@lru_cache(maxsize=None)
def _recipe_code_now(recipe: str) -> str | None:
    now = recipe_code(recipe)
    return None if now is None else (now["closure_sha256"] + "|" + now["recipe_entry_sha256"] + "|" +
                                     _json_stages(now.get("stage_closures")))


def _json_stages(stages) -> str:
    import json as _json
    return _json.dumps(stages or {}, sort_keys=True)


def recipe_stale(recipe: str, verdict: dict) -> str | None:
    """Why a recipe's positive verdict no longer binds its code, or None (review of #179, H5)."""
    if "code" not in verdict:
        return None            # a hand-built index without bindings (unit-test fixtures); the builder always writes it
    code = verdict.get("code") or {}
    if not code.get("closure_sha256"):
        return "the recipe code it measured is not recorded (absent from git at the run's source commit); " \
               "needs re-measurement"
    unbound = [*code.get("closure_unresolved", []),
               *([f"{code['dispatched']['unresolved_updates']} non-literal update(s) of OPERATION_RECIPES"]
                 if (code.get("dispatched") or {}).get("unresolved_updates") else [])]
    if unbound:
        return f"the recipe code it measured cannot be bound: {'; '.join(unbound)}; needs re-measurement"
    if code["closure_sha256"] + "|" + code.get("recipe_entry_sha256", "") + "|" + _json_stages(
            code.get("stage_closures")) != _recipe_code_now(recipe):
        return f"measured on recipe code {code['closure_sha256']}; the recipe code has changed; needs re-measurement"
    return None


@lru_cache(maxsize=None)
def genome_code(family: str) -> dict | None:
    """The genome's solve function as it is now: its static dependency closure (greg.cognition.code_binding)."""
    import inspect
    from . import code_binding
    from .genomes import library
    item = library.executables().get(family)
    if item is None:
        return None
    path = Path(inspect.getsourcefile(item.solve)).resolve().relative_to(ROOT).as_posix()
    return code_binding.closure(path, item.solve.__name__)


def genome_code_drift(family: str, record: dict) -> list[str]:
    """Closure members of the genome's solver that changed since its admission run measured them. Reported on
    every surface; only a changed default configuration (or version) gates routing, because a re-admission at the
    current code is the owner's scheduled admission v3."""
    then = (record.get("code") or {}).get("closure_members")
    now = (genome_code(family) or {}).get("members")
    if not then or not now:
        return []
    return sorted(k for k in set(then) | set(now) if then.get(k) != now.get(k))


def family_status(family: str, evidence: dict) -> dict:
    """The one admission status of a catalog family, read from the one evidence index. The compiler, Capability
    Genesis, the genome inventory and ``mind_status`` all call this (review of #179, H2/M16).

    Returns ``status`` (what routing uses: a stale or structural label routes as UNEVALUATED; negative evidence
    persists), ``raw`` (the label the frozen run recorded, or None), ``stale`` (why a positive verdict no longer
    binds, or None), ``evidence`` (the frozen file) and ``kind`` (genome, operation or none)."""
    from .genomes import library
    genomes = library.executables()
    if family in genomes:
        record = (evidence.get("genomes") or {}).get(family) or {}
        raw = record.get("status")
        status, stale = raw or "UNEVALUATED", None
        measured, current = record.get("version"), genomes[family].genome.version
        drift = genome_code_drift(family, record)
        if measured and measured != current and status not in NOT_POSITIVE:
            # positive evidence binds the version measured; negative evidence persists until a re-admission
            stale = f"{status} was measured at version {measured}; version {current} needs re-admission"
            status = "UNEVALUATED"
        elif status not in NOT_POSITIVE and status != "UNEVALUATED" and \
                any(member.rsplit("::", 1)[1].endswith("DEFAULT_CONFIG") for member in drift):
            # a changed default configuration is a different method at the same version (review of #179, M15)
            stale = (f"{status} was measured with a different default configuration "
                     f"({', '.join(m for m in drift if m.endswith('DEFAULT_CONFIG'))}); needs re-admission")
            status = "UNEVALUATED"
        return {"status": status, "raw": raw, "stale": stale, "evidence": record.get("evidence"),
                "kind": "genome", "code_drift": drift}
    record = (evidence.get("operations") or {}).get(family) or {}
    # PR #155 lineage: a frozen held-out verdict for an operation family routes like a genome's, bound to the
    # solver code closure it measured; a structural label (alias, not run) is indexed as UNEVALUATED
    status, stale = operation_status(family, record)
    return {"status": status, "raw": record.get("raw_status"), "stale": stale, "evidence": record.get("evidence"),
            "kind": "operation" if record else "none"}


def candidates(data: dict, g: CompetencyGeometry, evidence: dict, *, parts: bool = True) -> list[dict]:
    from .composition import RECIPES, route
    keys = set(data)
    rows, unfit, pending = _family_rows(keys, g, evidence, data)
    rows += _organ_rows(data, g, evidence)
    _reject_relaxations(rows, unfit, keys, g.geometry)
    _settle_promotions(pending, rows)
    recipe = route(data)
    if recipe:
        verdict = evidence["recipes"].get(recipe, {})
        classes = recipe_classes(recipe)
        row = {"method": f"composition:{recipe}", "operation": recipe, "kind": "composition",
               "status": "VPL_LIFT" if verdict.get("lift") else verdict.get("status", "UNEVALUATED"),
               "stages": list(RECIPES[recipe]["stages"]), "epistemic_classes": classes, "rejected": None,
               # practitioner arms the same frozen run tied or lost to (review of #179, L11): reported, since the
               # lift is over GREG's best constituent, not over these
               **{k: verdict[k] for k in ("tied_by", "loses_to") if verdict.get(k)}}
        stale = recipe_stale(recipe, verdict)
        if stale and verdict.get("lift"):
            # a lift binds the recipe code it measured (review of #179, H5); no lift persists like any negative
            row["status"], row["stale_evidence"] = "UNEVALUATED", stale
        if g.geometry and g.geometry not in classes:
            # the declaration is honoured for a recipe exactly as for an operation or an organ
            row["rejected"] = f"native geometry of its stages {tuple(classes)} does not include {g.geometry}"
        if verdict.get("lift") is False:
            # Demoted, not deleted: a recipe without verified lift ranks after every other method that fits,
            # because the simpler constituent wins ties; it stays the route when nothing else fits (P6 F5:
            # 8.5% cheaper, not significant, and its comparison arm is not an invocable method).
            row["status"] = "NO_LIFT"
            row["demoted"] = (f"frozen VPL verdict ({verdict.get('evidence', 'evidence index')}): no lift over "
                              f"{verdict.get('prefer') or 'its best constituent'}; ranked after every other fit")
        lacking = None if row["rejected"] else _stage_lacks(data, recipe, g, evidence)
        if lacking:
            # the stage that reads the part would abstain on it: the recipe is not a fit. When the part carries
            # inputs only this recipe (or a fuller method) reads, and no other method reads more of it, it asks the
            # recipe's question and the request ends asking for what it lacks, never in an attach ask, Genesis or a
            # stage abstention; otherwise the part asks another method's question
            row["rejected"] = (f"its {lacking['stage']} stage ({lacking['stage_method']}) reads part "
                               f"{lacking['part']!r}, which lacks {lacking['missing_inputs']}")
            if lacking["more"]:
                row["rejected"] += f" ({lacking['more']} read more of the part)"
            elif lacking["carried"]:
                row["rejected"] += f" (the part carries {lacking['carried']}, which no method it fully supplies reads)"
                row["missing_inputs"] = [{"method": row["method"], "part": lacking["part"],
                                          "missing_inputs": lacking["missing_inputs"]}]
        rows.append(row)
        if not row["rejected"]:
            _reject_recipe_relaxations(row, recipe, rows, keys, evidence)
        if parts:
            rows += _part_rows(data, g, evidence)
        # a single genome admitted DEFAULT against this recipe's twin, at its current version, that fits this request
        # (a row no rule rejected, flat or in the part): equal quality at no more than 1.25x the recipe's latency on
        # this geometry. The recipe's lift was measured over a repertoire without it. Decided after the stage rule and
        # the part rows: a genome with no row here answers another question, and a rejected recipe is not demoted.
        # Demoted, not deleted, the recipe still serves while the genome is withheld. It is no fallback for an input
        # the attached genome refuses: parallel edges end in the genome's abstention
        fits = {r["method"] for r in rows if not r["rejected"]}
        matched = [m for m in _matched_by_single_genome(recipe, evidence) if m["method"] in fits]
        if matched and not row["rejected"]:
            row["matched_by"] = matched
            row["demoted"] = "; ".join(filter(None, [row.get("demoted"), _matched_reason(matched)]))
    else:
        rows += _derived_rows(data, rows)
    return rows


def _reject_recipe_relaxations(row: dict, recipe: str, rows: list[dict], keys: set, evidence: dict) -> None:
    """The fixed recipe's twin of the derived-chain rule below. A single method or organ reading a strict subset of
    the inputs a routed recipe consumes answers a relaxation of the recipe's question and is rejected; a genome
    admitted DEFAULT against the recipe's twin decides the same question and still competes. Without this rule an
    unevaluated recipe tied an unevaluated organ on status and lost on the method name: on the converged tree the
    Fermi organ answered F1's estimate-then-optimize requests, ignored ``formal_template`` and abstained
    (development check of the converged recipe-lift re-measurement, 2026-10-21)."""
    from .composition import RECIPES
    consumed = set(RECIPES[recipe]["requires"]) & keys
    twins = {m["method"] for m in _matched_by_single_genome(recipe, evidence)}
    for other in rows:
        if (other is row or other["kind"] == "composition" or other["rejected"] or other.get("part")
                or other["method"] in twins):
            continue
        if set(other.get("inputs") or ()) < consumed:
            other["rejected"] = (f"answers a relaxation: ignores declared inputs "
                                 f"{sorted(consumed - set(other['inputs']))} that {row['method']} consumes")


def _derived_rows(data: dict, rows: list[dict]) -> list[dict]:
    """PR #155's dataflow derivation, reachable from the one Layer-5 entry (review of #179, M7): only when no
    fixed recipe routes and the derived chain consumes every input of every recipe that matched (M8). A single
    method reading a strict subset of the chain's inputs answers a relaxation of it and is rejected."""
    from .composition import RECIPES, derive, derived_inputs, matching
    derived = derive(data)
    consumed = derived_inputs(data)
    if not derived or not all(set(RECIPES[m]["requires"]) <= consumed for m in matching(data)):
        return []
    row = {"method": "composition:derived:" + "+".join(derived), "operation": "derived", "kind": "composition",
           "status": "UNEVALUATED", "stages": list(derived), "epistemic_classes": [], "rejected": None,
           "inputs": sorted(consumed), "outputs": None,
           "evidence_note": "NICHE_CAPABILITY in PR #155's P6 v3 (lift over the best single intelligence, not over "
                            "the best fixed recipe), measured before run() and derive() changed (review M8): needs "
                            "re-measurement"}
    for other in rows:
        if other["kind"] != "composition" and not other["rejected"] and set(other.get("inputs") or ()) < consumed:
            other["rejected"] = (f"answers a relaxation: ignores declared inputs "
                                 f"{sorted(consumed - set(other['inputs']))} that {row['method']} consumes")
    return [row]


def family_rows(keys, g: CompetencyGeometry, evidence: dict, data: dict | None = None) -> list[dict]:
    """One row per catalogued or genome family operation whose native inputs are all among ``keys``, with the
    compiler's own verdict in ``rejected``: native geometry, composition stage, frozen admission status, or a
    relaxation of a fuller catalogued method. Capability Genesis reads these same rows for a cognition deficit, so it
    names exactly the families this compiler would route to once attached. ``data`` (the request's values) only
    places a row in its measured subregion; no verdict depends on it. Cortex organs, which are routed on the
    request's values, are not among these rows (candidates adds them before the relaxation rule)."""
    keys = set(keys)
    rows, unfit, pending = _family_rows(keys, g, evidence, data)
    _reject_relaxations(rows, unfit, keys, g.geometry)
    _settle_promotions(pending, rows)
    return rows


def _family_rows(keys: set, g: CompetencyGeometry, evidence: dict, data: dict | None):
    """The family rows before the relaxation rule, the catalogued methods whose inputs ``keys`` do not all carry
    (``unfit``, which the relaxation rule reads), and the superseded rows whose promoted genome is settled after it."""
    from .catalog import FAMILIES
    from .genomes import library
    rows = []
    unfit = []          # catalogued methods whose inputs the request does not all carry (the relaxation rule)
    genomes = library.executables()
    # a superseded genome's competitor promoted into a registered genome of its own (same geometry and inputs)
    promoted = {old: new for old, new in library.promotions().items() if new in FAMILIES}
    pending = []                          # (superseded row, its promoted genome's method), settled after rejection
    for family, (_, ops, classes, _, _) in FAMILIES.items():
        for op in ops:
            stale = None
            outputs = None
            admission = family_status(family, evidence)
            status, stale = admission["status"], admission["stale"]
            record = evidence["genomes"].get(family, {}) if family in genomes else {}
            measured = current = None
            other_version = False             # the family's evidence was measured at another version of its code
            if family in genomes:
                need = genomes[family].genome.required_inputs
                outputs = sorted(genomes[family].genome.output_contract)
                standalone = genomes[family].genome.standalone_decision
                measured, current = record.get("version"), genomes[family].genome.version
                other_version = bool(measured) and measured != current
            else:
                need = NATIVE_INPUTS.get(op)
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
                reason = f"frozen admission status {status}" + (
                    f", measured at version {measured} (it persists until a re-admission at {current})"
                    if other_version else "")
            row = {"method": f"cognition.{family}", "operation": op, "kind": "operation", "status": status,
                   "epistemic_classes": list(classes), "rejected": reason, "inputs": sorted(need), "outputs": outputs,
                   **({"stale_evidence": stale} if stale else {}),
                   # solver code that changed since the admission run measured it (reported, not gating)
                   **({"code_drift": admission["code_drift"]} if admission.get("code_drift") else {})}
            # Held-out measurements (median latency, subregion verdicts) bind the version they were measured at.
            # Measured at another version, they never rank, order fits or name acquisitions, whatever the status:
            # a negative status persists, but the latency and verdicts it came with describe other code. They
            # are reported under ``stale_measurements``, labelled with the version measured.
            if family in genomes and not other_version and record.get("median_seconds") is not None:
                row["median_seconds"] = record["median_seconds"]          # held-out, measured at this version
            if family in genomes and not other_version and data is not None:
                placed = _subregion_evidence(genomes[family], data, record)
                if placed:
                    row["subregion"] = placed
            if other_version:
                row["stale_measurements"] = _stale_measurements(genomes[family], record, data)
            if family in genomes and status == "SUPERSEDED":
                item = genomes[family]
                row["superseded_by"] = {"mechanism": item.genome.competitor,
                                        "deployable": bool(getattr(item, "competitor_deployable", True)),
                                        "evidence": evidence["genomes"].get(family, {}).get("evidence")}
                if family in promoted:
                    pending.append((row, f"cognition.{promoted[family]}"))
            if family not in genomes and status == "SUPERSEDED":
                # an operation family superseded by its frozen run's competitor: name it as the acquisition
                # candidate (review of #179, M1)
                operation = (evidence.get("operations") or {}).get(family) or {}
                if operation.get("competitor"):
                    row["superseded_by"] = {"mechanism": operation["competitor"], "deployable": True,
                                            "evidence": operation.get("evidence")}
            if family in genomes and genomes[family].promotes in FAMILIES:
                row["promotes"] = f"cognition.{genomes[family].promotes}"
            rows.append(row)
    return rows, unfit, pending


def _settle_promotions(pending: list, rows: list[dict]) -> None:
    """After the relaxation rule: a superseded row whose competitor is a registered genome names it."""
    why = {r["method"]: r["rejected"] for r in rows}
    for row, method in pending:
        if method in why and not why[method]:
            # the mechanism is already a registered genome that can answer this request: its own row and record
            # govern it, and attaching it is the founder's decision (never a Genesis acquisition)
            row["superseded_by"]["promoted_as"] = method
        elif method in why:
            # its promoted genome cannot answer this request (its own frozen status, a relaxation): the superseding
            # mechanism stays an acquisition candidate, and the reason is kept. A declared geometry that excludes the
            # promoted genome excludes this row too (promotion keeps the class), and run names no candidate for it
            row["superseded_by"]["promoted_rejected"] = {"method": method, "why": why[method]}


def _matched_reason(matched: list[dict], inhibited=frozenset()) -> str:
    """Why a recipe is demoted by the single genomes that matched its twin. The recipe ranks after each matched genome
    that is not demoted. One that settled outcomes on this body demote (``inhibited``) is a demoted fit too, so the
    recipe need not rank after it: the demoted fits are ordered among themselves by the other rank keys."""
    def them(methods):
        return "it" if len(methods) == 1 else "them"
    text = (f"admitted single genome {', '.join(m['method'] for m in matched)} matched this recipe's twin "
            f"({', '.join(m['evidence'] for m in matched)}); the single method is canonical for this geometry")
    ahead = [m["method"] for m in matched if m["method"] not in inhibited]
    demoted = [m["method"] for m in matched if m["method"] in inhibited]
    if not demoted:
        return text + f" and the recipe ranks after {them(ahead)}"
    if ahead:
        text += f" and the recipe ranks after {', '.join(ahead)}"
    return text + (f", but settled outcomes on this body demote {', '.join(demoted)} too, so the recipe is ordered "
                   f"with {them(demoted)} among the demoted fits by the other rank keys")


def _matched_by_single_genome(recipe: str, evidence: dict) -> list[dict]:
    """Genomes whose admission competitor is ``recipe``'s twin and whose frozen status at their current version is
    DEFAULT_FOR_GEOMETRY (a stale or any other status matches nothing)."""
    from .genomes import library
    out = []
    for family, item in sorted(library.executables().items()):
        record = evidence["genomes"].get(family, {})
        if (getattr(item, "competitor_recipe", None) == recipe and record.get("status") == "DEFAULT_FOR_GEOMETRY"
                and record.get("version") == item.genome.version):
            out.append({"method": f"cognition.{family}", "version": item.genome.version,
                        "evidence": record.get("evidence") or "evidence index"})
    return out


def _part_rows(data: dict, g: CompetencyGeometry, evidence: dict) -> list[dict]:
    """A composition request whose one typed part is the whole question (``{"capacity_network": {...}}``, the shape
    graph_then_allocate reads) asks that question of every method whose native inputs the part carries: the flat
    network is exactly what flow_expansion_mcf answers alone. Those operation rows are offered beside the recipe,
    each marked with the part it reads; ranking, the relaxation rule and attachment decide as for any row. A
    recipe of several parts is a joint question no single part answers, so it offers none."""
    part = _one_part(data)
    if part is None:
        return []
    return [{**row, "part": part} for row in candidates(_part_data(data, part), g, evidence, parts=False)
            if row["kind"] == "operation"]


PART_FLAGS = ("formalization_complete",)        # request-level flags a part-addressed method reads with its part


def _one_part(data: dict) -> str | None:
    """The part, when the request is a recipe of one typed part and nothing else (``{"capacity_network": {...}}``,
    plus request-level flags): that part is the whole question. Otherwise None."""
    from .composition import RECIPES, route
    recipe = route(data)
    required = RECIPES[recipe]["requires"] if recipe else ()
    if len(required) != 1 or set(data) - {required[0], *PART_FLAGS} or not isinstance(data[required[0]], dict):
        return None
    return required[0]


def recipe_classes(recipe: str) -> list[str]:
    """A recipe's native geometry: the epistemic classes of its stages. An operation stage has the classes of the
    catalogued family that declares the operation; a problem-path stage (a cortex organ) has the class its recipe
    declares in ``stage_classes``. As for a family of several classes, a declaration excludes the recipe only when
    no stage is native to it; a recipe whose stages declare no class is excluded by every declaration."""
    from .catalog import FAMILIES
    from .composition import RECIPES
    spec = RECIPES[recipe]
    classes = set(spec.get("stage_classes", ()))
    for operation in spec.get("operations", ()):
        classes |= {c for _, ops, family_classes, _, _ in FAMILIES.values() if operation in ops
                    for c in family_classes}
    return sorted(classes)


def _method_inputs() -> list[dict]:
    """Every catalogued mechanism that declares the inputs it reads: method, operation, inputs, outputs and native
    classes. An operation reads the native inputs candidates() fits on (a family without a declared output
    contract has outputs None); a composition recipe reads its typed parts and has its stages' classes."""
    from .catalog import FAMILIES
    from .composition import RECIPES
    from .genomes import library
    genomes, out = library.executables(), []
    for family, (_, ops, classes, _, _) in FAMILIES.items():
        for op in ops:
            if family in genomes:
                need, outputs = genomes[family].genome.required_inputs, sorted(genomes[family].genome.output_contract)
            else:
                need, outputs = NATIVE_INPUTS.get(op), None
            if need is not None:
                out.append({"method": f"cognition.{family}", "operation": op, "inputs": sorted(need),
                            "outputs": outputs, "epistemic_classes": list(classes)})
    for recipe, spec in RECIPES.items():
        out.append({"method": f"composition:{recipe}", "operation": recipe, "inputs": sorted(spec["requires"]),
                    "outputs": None, "epistemic_classes": recipe_classes(recipe)})
    return out


def _served(rows: list[dict], g: CompetencyGeometry) -> set:
    """The inputs read by the mechanisms the request fully supplies and whose native geometry the declaration
    admits: operations and cortex organs, whatever else (frozen status, a relaxation) rejected them. Such a
    mechanism poses the question those inputs ask. One the declaration excludes poses none: variables and
    constraints declared optimization are the optimization question without its objective, not the feasibility
    question. Part-addressed rows are another request's (the part's) and are not counted."""
    return {i for r in rows if not r.get("part") and not (g.geometry and g.geometry not in r["epistemic_classes"])
            for i in r.get("inputs", ())}


def _readers(keys: set) -> list[dict]:
    """Every catalogued method and recipe that reads some of ``keys``, with what it reads and what it lacks."""
    return [{**m, "reads": sorted(set(m["inputs"]) & keys), "missing_inputs": sorted(set(m["inputs"]) - keys)}
            for m in _method_inputs() if set(m["inputs"]) & keys]


def _read_more(m: dict, readers: list[dict]) -> list[str]:
    """The methods and recipes that read more of the request than ``m`` does without producing its decision, among
    those whose question the request could be (it carries at least as many of their inputs as they lack). The
    request is then their question, not ``m``'s, whatever their status or the declaration."""
    return sorted({o["method"] for o in readers if len(o["reads"]) > len(m["reads"])
                   and len(o["reads"]) >= len(o["missing_inputs"]) and not _same_decision(m, o)})


def _partially_supplied(data: dict, rows: list[dict], g: CompetencyGeometry, part: str | None = None) -> list[dict]:
    """Catalogued mechanisms (operations and recipes) that read some of what ``data`` carries and need inputs it
    lacks; ``rows`` are the candidates for ``data``. ``why`` is None when the request asks that mechanism's
    question, so that what it lacks is missing information rather than a capability deficit; otherwise it says
    why the mechanism is not the question asked.

    The analogue of a one-part recipe's 'carried' rule (_stage_lacks) for a request that no mechanism it fully
    supplies can answer. A mechanism is the question asked when
      - the declaration does not exclude its native geometry;
      - the request carries an input it reads that no mechanism the request fully supplies reads (_served;
        otherwise that mechanism poses the question, and the relaxation rule decides between the two);
      - the request carries at least as many of its inputs as it lacks: one key shared with a larger method does
        not make the request that method's question (a cost table with a budget is not a capacity expansion
        missing five inputs). A part named for a recipe (``{"capacity_network": {...}}``) names it already, so the
        recipe's own stage rule needs no such count; and
      - no other catalogued method or recipe that the request supplies in full, or in part carrying at least as
        many of its inputs as it lacks (whatever its status or the declaration), reads more of the request's
        inputs without producing its decision (_read_more): the request is that mechanism's question (max_flow is
        not asked for the sink beside the expansion methods when the request also carries a budget; a PID tracking
        problem declared prediction is not a simulation missing its step probability). A mechanism producing the
        same decision from less side information competes and is asked as well (hysteresis beside the Bayesian
        regime filter, which also reads a dwell prior). Keys no mechanism requires (optional inputs) decide
        nothing.
    Request-level flags (``formalization_complete``) are not inputs."""
    served = _served(rows, g)
    readers = _readers(set(data) - set(PART_FLAGS))
    out = []
    for m in readers:
        if not m["missing_inputs"]:
            continue
        more = _read_more(m, readers)
        why = (f"native geometry {tuple(m['epistemic_classes'])} does not include {g.geometry}"
               if g.geometry and g.geometry not in m["epistemic_classes"]
               else "every input it reads here is read by a mechanism the request fully supplies"
               if not set(m["reads"]) - served
               else "the request carries fewer of its inputs than it lacks"
               if len(m["reads"]) < len(m["missing_inputs"])
               else f"{more} read more of the request" if more else None)
        out.append({**m, "why": why, **({"part": part} if part else {})})
    out.sort(key=lambda m: (m["method"], m["operation"]))
    return out


def _stage_lacks(data: dict, recipe: str, g: CompetencyGeometry, evidence: dict) -> dict | None:
    """For a recipe of one part, the inputs its first stage needs that the part does not carry, else None.

    The first stage of a one-part recipe reads the part whole (graph_then_allocate compiles
    ``capacity_network`` with compile_capacity_expansion), so the part must carry that operation's native inputs;
    without them the stage abstains and the composition cannot answer. ``carried`` lists the stage inputs the part
    does carry that no mechanism the part fully supplies (and the declaration admits) reads (budget and unit_cost
    beside a max-flow network; _served): then the part asks this recipe's question with information missing, as
    the relaxation rule decides for a flat request. A part that carries none (a plain max-flow network) asks a
    simpler question, and so does a part another method reads more of (``more``, _read_more, as for a flat
    request): a causal graph sent as a capacity network is the causal question, not a capacity expansion missing
    five inputs, whatever the declaration. A recipe of several parts feeds its stages from several places and is
    not judged here."""
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
            served = _served(candidates(_part_data(data, part), g, evidence, parts=False), g)
            stage = {"reads": sorted(need & set(data[part])),
                     "outputs": sorted(genomes[family].genome.output_contract) if family in genomes else None}
            return {"part": part, "stage": spec["stages"][0], "stage_method": f"cognition.{family}",
                    "missing_inputs": missing, "carried": sorted(set(stage["reads"]) - served),
                    "more": _read_more(stage, _readers(set(data[part]) - set(PART_FLAGS)))}
    return None


def _part_data(data: dict, part: str) -> dict:
    """What a part-addressed method reads: the part, with the request-level flags (``formalization_complete``)."""
    return {**data[part], **{k: data[k] for k in PART_FLAGS if k in data}}


def _same_decision(row: dict, fuller: dict) -> bool:
    """True when ``row`` produces every output the fuller method does: it decides the same question with less
    side information (hysteresis vs the Bayesian regime filter, which also reads a dwell prior) and competes."""
    return row["outputs"] is not None and fuller["outputs"] is not None and set(fuller["outputs"]) <= set(row["outputs"])


def _missing_information(rows: list[dict], partial: list[dict] = ()) -> list[dict]:
    """What the request lacks, once per (method, part, inputs): the fuller methods a relaxation was rejected for
    (``missing_for_fuller``), the recipes whose reading stage the part cannot feed (``missing_inputs``), and the
    partially supplied methods and recipes whose question the request asks (``partial``, from
    _partially_supplied). An entry from a part-addressed row names that part."""
    entries = [{**m, **({"part": r["part"]} if r.get("part") else {})}
               for r in rows for m in r.get("missing_for_fuller", []) + r.get("missing_inputs", [])]
    entries += [{"method": p["method"], "missing_inputs": p["missing_inputs"],
                 **({"part": p["part"]} if p.get("part") else {})} for p in partial if p["why"] is None]
    out = []
    for entry in entries:
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
    alone, and so are cortex organs, which read the payload parts they are routed on: the semantic organ reads
    ``sources`` and answers no grid repair, so it does not serve a develop_repair request (it served one whenever
    develop_repair was withheld, and a request lacking one of its inputs was answered instead of asking)."""
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
    path. Their status comes from the evidence index's ``organs`` section when it has one, else UNEVALUATED; like a
    genome's, positive organ evidence binds the version it was measured at (CORTEX_ENTRIES) and negative evidence
    persists until a re-admission replaces it. ``inputs`` are the payload parts an organ reads, by the same policy:
    those without which it is not routed."""
    from cortex.routing import _route_parts      # the cortex's route policy, reused rather than re-implemented
    from .bridge import _CLASS, ORGANS
    from .catalog import CORTEX_ENTRIES
    routed = _route_parts(data)
    if not routed:
        return []
    without = {k: {key for key, _ in _route_parts({x: v for x, v in data.items() if x != k})} for k in data}
    rows = []
    for key, cls in routed:
        cid = ORGANS.get(key)
        if cid is None:
            continue
        klass = _CLASS.get(cls, cls)
        status, stale = organ_status(cid, evidence)
        reason = (f"native geometry {klass} does not include {g.geometry}" if g.geometry and g.geometry != klass
                  else f"frozen status {status}" if status in EXCLUDED else None)
        rows.append({"method": cid, "operation": "problem", "kind": "problem", "status": status, "organ": key,
                     "epistemic_classes": [klass], "inputs": sorted(k for k in data if key not in without[k]),
                     "outputs": None, "rejected": reason, **({"stale_evidence": stale} if stale else {})})
    return rows


def organ_status(cid: str, evidence: dict) -> tuple[str, str | None]:
    """(routing status, stale reason) of a cortex organ, from the evidence index's ``organs`` section: UNEVALUATED
    without a row; positive evidence binds the version measured (CORTEX_ENTRIES), negative evidence persists. The
    compiler and the genome inventory both read it (round-2 review of #179, N2)."""
    from .catalog import CORTEX_ENTRIES
    record = (evidence.get("organs") or {}).get(cid, {})
    status = record.get("status", "UNEVALUATED")
    measured, current = record.get("version"), CORTEX_ENTRIES.get(cid, (None,))[0]
    if measured and current and measured != current and status not in NOT_POSITIVE:
        return "UNEVALUATED", f"{status} was measured at version {measured}; version {current} needs re-admission"
    return status, None


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


def _run_constructed(chosen: dict, data: dict, pid: str, registry, receipt: dict, finish, *, high: bool = False,
                     budget=None, evaluate=()):
    """Invoke an attached, read-only construction; its problem-level certificate is the evidence.

    A construction is optimisation-class (``recombine.Reduction.epistemic_classes``), so it meets the same rules
    as every other compile route: under high consequence it needs a complete formal model and returns a
    conditional result (WORLD_UNVERIFIED), never ANSWERED; its call is a required step on the decision's thinking
    budget (refused below the minimum step, measured, any overrun disclosed); and the sensitivity operator, when
    it applies, re-runs the construction itself on perturbed inputs."""
    from greg.capabilities import CapabilityError
    manifest = registry.manifests[chosen["method"]]
    if manifest.consequence_class != "read_only" or not manifest.provider.startswith("composed:"):
        receipt["abstentions"].append("ABSTAIN: only a read-only construction may answer inside cognition")
        return finish("ABSTAIN")
    if high and data.get("formalization_complete") is not True:
        receipt["abstentions"].append("FORMALIZATION_INCOMPLETE: complete formal model plus independently "
                                      "verified world assumptions")
        return finish("FORMALIZATION_INCOMPLETE")
    request = {key: data[key] for key in chosen["inputs"]}
    adapter = registry.adapters[manifest.capability_id]
    step = f"constructed:{manifest.capability_id}"
    allotted = budget.allot(step, required=True) if budget is not None else None
    if budget is not None and allotted is None:
        receipt["abstentions"].append(budget.stops()[-1]["reason"])
        return finish("ABSTAIN")
    try:
        out = _call_construction(adapter, manifest, request, pid)
    except CapabilityError as exc:
        if str(exc).startswith("capability refused:"):
            # the mission's two-strike repair re-forms a construction that faults in service
            receipt["capability_fault"] = {"capability_id": manifest.capability_id, "detail": str(exc)[:300],
                                           "failure_class": getattr(exc, "failure_class", None)}
        receipt["abstentions"].append(f"ABSTAIN: {str(exc)[:300]}")
        return finish("ABSTAIN")
    finally:
        if budget is not None:
            _close_step(budget, step, allotted, receipt, f"{manifest.capability_id}")
    receipt["resource_use"]["stages"] = 1
    receipt["proof_artifacts"] = [{"type": "certificate", "evidence_type": (out.get("certificate") or {}).get("kind")}]
    receipt["verification_method"] = (out.get("certificate") or {}).get("checked_by") or \
        "GREG problem-level certificate, independent of the engine"
    receipt["dissent"].append(f"trust per call: {manifest.provenance.get('baseline', 'see the construction card')}")
    if out.get("certified") is not True:
        receipt["abstentions"].append("ABSTAIN: the construction returned no certificate")
        return finish("ABSTAIN")
    # Set only once the certificate is in hand: a predicate on this label then implies an answer
    # that carries a problem-level certificate, never an abstention that merely tried.
    receipt["confidence_type"] = CERTIFIED
    if high:
        receipt["uncertainty"] = "exact for the declared inputs; whether they describe the world is not verified"
    if "sensitivity" in evaluate and budget is not None:
        def rerun(key, varied, limit):
            try:
                again = _call_construction(adapter, manifest, {k: varied[k] for k in chosen["inputs"]}, pid)
            except CapabilityError as exc:
                return {"abstention_state": f"ABSTAIN: {str(exc)[:120]}"}
            return {"abstention_state": "NONE" if again.get("certified") is True else "NO_CERTIFICATE",
                    "output": again}
        receipt["sensitivity"] = _perturbation_runs(request, out, budget, receipt, rerun)
    return finish("WORLD_UNVERIFIED" if high else "ANSWERED", out)


def _call_construction(adapter, manifest, request: dict, pid: str) -> dict:
    import tempfile
    from greg.capabilities import InvocationContext
    with tempfile.TemporaryDirectory(prefix="greg-constructed-") as tmp:
        ctx = InvocationContext(workspace=Path(tmp), read_roots=(), secrets=None, manifest=manifest,
                                target=f"cognition:{pid}")
        return adapter(request, ctx)


def _close_step(budget, step: str, allotted, receipt: dict, who: str) -> None:
    """Record a required step's measured spend and disclose an overrun (the call itself is not interruptible)."""
    budget.done(step)
    used = budget.ledger[-1]["spent_s"]
    if allotted is not None and used > allotted:
        receipt["dissent"].append(f"{who} overran the thinking budget: {used:.3g}s spent of {allotted:.3g}s "
                                  "allotted; the construction's engine, not the budget, bounds its call")


def _stale_measurements(item, record: dict, data: dict | None) -> dict:
    """A genome's frozen held-out evidence measured at another version of its code, labelled with that version.

    Reported in rows, receipts and attach asks, and never used to rank, order fits or name acquisitions: the median
    latency and subregion verdicts describe the code that was measured. Its status is handled by the status rule
    (positive evidence counts as UNEVALUATED; negative evidence persists until a re-admission replaces it)."""
    measured, current, status = record.get("version"), item.genome.version, record.get("status")
    persists = status in NOT_POSITIVE
    region = _subregion_evidence(item, data, record) if data is not None else None
    return {k: v for k, v in {
        "version_measured": measured, "version_current": current, "status": status,
        "evidence": record.get("evidence"), "median_seconds": record.get("median_seconds"), "subregion": region,
        "stale_evidence": (f"measured at version {measured}, not the current {current}: reported, never used to rank, "
                           f"order fits or name acquisitions; "
                           + (f"the {status} status persists until a re-admission at {current} replaces it"
                              if persists else f"the {status} status counts as UNEVALUATED until a re-admission"))
    }.items() if v is not None}


def _rank(row: dict, prefer: list, competence: dict) -> tuple:
    status = 0 if row["status"] == "VPL_LIFT" else STATUS_RANK.get(row["status"], 5)
    preferred = 0 if (row["operation"] in prefer or row["method"] in prefer) else 1
    settled = -competence.get(row["method"], 0.5)
    region = SUBREGION_RANK.get((row.get("subregion") or {}).get("verdict"), 1)
    latency = row.get("median_seconds")
    # Frozen negative evidence outranks an operator's preference: evidence over heuristics. Within one status,
    # the measured subregion verdict orders fits before settled competence, then measured held-out latency
    # (unmeasured last), then operations before compositions and organs. Both measurements count only at the
    # version they were measured at (_family_rows reports another version's under stale_measurements).
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
    path and checked there). A construction (``kind == "constructed"``) runs exactly when its own capability is
    usable: constructed_candidates admits only an attached, read-only one, and this re-checks it, never widens."""
    if row["kind"] == "constructed":
        try:
            ok, why = registry.usable(row["method"])
        except Exception as exc:
            return False, f"registry: {type(exc).__name__}"
        return bool(ok), str(why)
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
        if row["operation"] == "derived":
            # derived stages run on the canonical problem path behind the cortex router, checked there
            from .bridge import ROUTER
            ok, why = registry.usable(ROUTER) if ROUTER in registry.manifests else (False, "not registered")
            return (True, "derived composition: stages run on the canonical path") if ok else (False, f"{ROUTER}: {why}")
        missing = [op for op in RECIPES[row["operation"]].get("operations", ()) if not _operation_usable(registry, op)]
        if missing:
            return False, f"composition stages without an attached capability: {missing}"
        return True, "composition: every declared operation stage has an attached capability"
    try:
        ok, why = registry.usable(row["method"])
    except Exception as exc:
        return False, f"registry: {type(exc).__name__}"
    return bool(ok), str(why)


FIT_KINDS = ("operation", "problem", "composition")


def fitting(rows: list[dict]) -> list[dict]:
    """The rows that fit a request, as a capability deficit records them: what ``runnable`` needs to apply this
    compiler's own test to them later, without the request's values (an organ's or a recipe's fit depends on them)."""
    return [{"method": r["method"], "kind": r["kind"], "operation": r["operation"]} for r in rows]


def runnable(registry, rows) -> str | None:
    """The first of ``rows`` (recorded by ``fitting``) that can run now by this compiler's own test (``_usable``):
    the method a request whose eligible rows these are would be routed to if compiled now, else None. A deficit's
    need is served exactly when this names one."""
    for row in rows:
        try:
            if _usable(registry, row)[0]:
                return row["method"]
        except Exception:           # a row this compiler cannot test (an unknown recipe) is not runnable
            continue
    return None


def _state(registry, method: str) -> str | None:
    try:
        return registry.state.get(method)
    except Exception:
        return None


def _formed(registry, data: dict, g: CompetencyGeometry, body: dict, high: bool, receipt: dict, budget, *, pid: str,
            vector, journal=None):
    """Directive section 24, after the founder's attach: a mechanism Capability Genesis formed for a residual
    geometry (an installed open-source engine qualified on GREG's frozen oracle; ``greg.genesis``) serves it.

    Reached only when no catalogued method fits or can run. The founder's attach is the only way such a mechanism
    becomes usable; every answer is accepted only on GREG's own certificate, which shares no code with the engine.
    A refusal (input outside competence, a changed package, a failed certificate) is recorded and the deficit
    stands. An answer carries the mechanism's own receipt (``selected_receipt``), which settlement credits by
    capability id and pinned package version; a mechanism whose settled outcomes on this body are significantly
    poor is demoted after every other formed mechanism, as a catalogued method is. Returns ``(state, result)`` or
    None.

    Each call is a required step on the decision's thinking budget: refused below the minimum step, measured, and
    any overrun reported. The engine's own wall limit is set by the Genesis runner (``mechanisms.run``: its CPU
    limit plus 20 s per call), not by the remaining budget, so an overrun is disclosed rather than prevented."""
    try:
        from greg import genesis
        formed = genesis.formed_cognition(registry, data, g.geometry)
    except Exception as exc:          # a registry object without the views Genesis reads: recorded, not fatal
        receipt["dissent"].append(f"formed mechanisms not consulted: {type(exc).__name__}: {exc}"[:300])
        return None
    settled = _settled_counts(journal) if formed else {}
    inhibited = {m.capability_id: _settled_inhibition(*settled.get(m.capability_id, (0, 0))) for m, _ in formed}
    receipt["methods_demoted"] += [{"method": cid, "why": why} for cid, why in inhibited.items() if why]
    formed.sort(key=lambda pair: bool(inhibited[pair[0].capability_id]))      # stable: demoted, never deleted
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
        step = f"formed:{cid}"
        limit = budget.allot(step, required=True)
        if limit is None:
            receipt["abstentions"].append(budget.stops()[-1]["reason"])
            receipt["method_or_composition_selected"] = receipt["selection_level"] = None
            return "ABSTAIN", None
        started = time.monotonic()
        try:
            answer = genesis.run_formed(manifest, adapter, data)
        except Exception as exc:
            receipt["abstentions"].append(f"{cid} refused: {exc}"[:300])
            receipt["method_or_composition_selected"] = receipt["selection_level"] = None
            receipt.setdefault("formed_tried", []).append([cid, manifest.digest()])   # ran, no certified answer
            continue
        finally:
            budget.done(step)
            spent = budget.ledger[-1]["spent_s"]
            if spent > limit:
                receipt["dissent"].append(f"{cid} overran the thinking budget: {spent:.3g}s spent of {limit:.3g}s "
                                          "allotted; the Genesis runner, not the budget, bounds its engine")
        inner = _formed_receipt(pid, manifest, spec, g, vector, data, answer, time.monotonic() - started, high,
                                [m.capability_id for m, _ in formed])
        if inhibited[cid]:
            receipt["dissent"].append(f"{cid}: {inhibited[cid]}")
        # the compile receipt carries the evidence the formed mechanism was chosen on, not only its own receipt
        # (whole-machine trace gap, #158, 2026-10-21): settled outcomes per formed mechanism considered, and the
        # mechanism receipt's strongest counterargument as dissent
        receipt["conditional_competence_basis"] = {
            m.capability_id: ({"settled": settled[m.capability_id][0], "correct": settled[m.capability_id][1],
                               "laplace": round((settled[m.capability_id][1] + 1) / (settled[m.capability_id][0] + 2),
                                                4)}
                              if m.capability_id in settled else "no settled outcomes in this journal")
            for m, _ in formed}
        receipt["dissent"].append(inner["strongest_counterargument"])
        receipt.update(proof_artifacts=[{"type": "genesis_mechanism_certificate",
                                         "evidence_type": spec["evidence_type"]}],
                       verification_method=f"GREG-owned certificate sharing no code with {answer.get('engine')}: "
                                           f"{answer['certificate']['kind']}",
                       confidence_type=spec["evidence_type"], intermediate_receipts=[inner["receipt_id"]],
                       selected_receipt=inner,
                       uncertainty="exact for the declared inputs; whether they describe the world is not verified")
        receipt["resource_use"]["stages"] = 1
        if receipt.get("withheld_best_fit"):
            receipt["withheld_best_fit"]["served_by"] = cid
        return ("WORLD_UNVERIFIED" if high else "ANSWERED"), answer
    return None


def _formed_tried(registry, receipt: dict) -> list:
    """The formed mechanisms this compile ran and got no certified answer from, as ``[capability_id, digest]``
    (recorded by ``_formed`` as each one refused).

    Capability Genesis records them on the deficit's search pass; a mechanism is excluded from serving the need
    only if this compile tried it, never because it became usable later (an attach during a host outage's
    back-off, for one) and never because it was merely considered."""
    return [list(pair) for pair in receipt.get("formed_tried", [])]


def _formed_receipt(pid: str, manifest, spec: dict, g: CompetencyGeometry, vector, data: dict, answer: dict,
                    latency: float, high: bool, considered: list) -> dict:
    """The formed mechanism's own CognitiveReceipt. Its method is the capability id and its version the package
    version pinned on the Mechanism Card (settlement checks both against Genesis's registration, never against
    BUILTINS). Its evaluator is GREG's certificate, which the adapter checked before this answer existed."""
    from cortex.outcomes import classify_greg
    from .contracts import CognitiveReceipt, ProblemGeometry
    klass = g.geometry or spec["signature"]["classes"][0]
    geometry = ProblemGeometry(epistemic_class=klass, consequence_class=g.consequence_class or "read_only",
                               optimization_question=klass == "optimization")
    signature = spec["signature"]
    read = {k: data[k] for k in (*signature["required"], *signature["optional"]) if k in data}
    state = "WORLD_UNVERIFIED" if high else "NONE"
    engine = str(answer.get("engine"))
    return CognitiveReceipt(
        problem_id=pid, geometry=asdict(geometry), consequence_class=geometry.consequence_class,
        consequence_vector=asdict(vector), method=manifest.capability_id,
        method_version=str(manifest.provenance.get("version")), epistemic_class=klass,
        input_digest=digest({"problem_id": pid, "mechanism": manifest.capability_id, "data": read}),
        evidence_refs=[], assumptions=["Input and model validity are not established by computation"],
        excluded_variables=[], output=answer, uncertainty={"conditional_on_input": True, "world_confidence": None},
        proof_type=None, proof_artifact=None, alternative_methods_considered=[{"method": c} for c in considered],
        method_selection_reason="founder-attached mechanism Capability Genesis formed for this residual geometry; no "
                                "catalogued method fits or can run",
        strongest_counterargument="the declared inputs may not describe the world; the engine is untrusted and its "
                                  "answer stands only on GREG's certificate",
        falsification_condition="GREG's certificate fails on recomputation, or an observed outcome contradicts this "
                                "receipt",
        abstention_state=state,
        missing_information=["empirical conditions and legitimate consequence authority require separate "
                             "verification"] if high else [],
        compute_cost={"engine": engine, "model_calls": 0, "energy": "unmeasured"}, money_cost=0.0,
        latency=max(0.0, latency), evaluator="GREG-owned certificate (greg.genesis)",
        evaluator_result={"verdict": "STRUCTURALLY_VERIFIED", "certificate": answer["certificate"]["kind"],
                          "independence": f"GREG-owned certificate sharing no code with {engine}"},
        reason_code="WORLD_UNVERIFIED" if high else None,
        outcome_state="CONDITIONAL_RESULT" if high else "ANSWERED_WITHIN_SCOPE",
        contribution_attribution=[{"method": manifest.capability_id, "role": "calculation",
                                   "uncertainty": "not causal credit"}],
        causal_credit=[{"method": manifest.capability_id, "role": "solver"},
                       {"method": "greg.genesis certificate", "role": "falsifier"}],
        outcome=classify_greg(state, has_output=True)).to_dict()


def attach_ask(pid: str, best: dict, fallback: dict | None, evidence: dict) -> dict:
    """A founder ask to attach a withheld capability, on the one asks contract and its screen. Prepared here and
    returned for the body to record through greg.asks; attaching stays the founder's decision."""
    from datetime import datetime, timezone
    from greg import asks
    family = best["method"].removeprefix("cognition.")
    record = evidence.get("genomes", {}).get(family, {})
    operation = (evidence.get("operations") or {}).get(family) or {}
    from .genome_library import NOTES
    # an operation family's ask cites its own frozen evidence, raw label, history, code binding and recorded
    # caveats, like a genome's (review of #179, M1)
    measured = {k: v for k, v in {"admission_status": best["status"],
                                  "admission_evidence": record.get("evidence") or operation.get("evidence"),
                                  "measured_version": record.get("version"),
                                  "raw_status": operation.get("raw_status"),
                                  "admission_history": operation.get("history"),
                                  "measured_code_closure": (operation.get("code") or {}).get("closure_sha256"),
                                  "caveat": NOTES.get(family),
                                  "code_changed_since_admission": best.get("code_drift"),
                                  "subregion": best.get("subregion"), "current_state": best["usable_why"],
                                  "stale_measurements": best.get("stale_measurements")}.items()
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


SETTLED_ALPHA = 0.05            # family-wise, Holm over the challengers tested against the evidence-ranked first fit


def _settled_preference(eligible: list[dict], settled: dict) -> dict | None:
    """Retained settled outcomes alone can change the choice between two eligible fits (whole-machine trace gap,
    #158, 2026-10-21). The evidence-ranked first fit A is compared with every other undemoted fit B that, like A,
    has at least SETTLED_MIN_N settled outcomes on this body; B is preferred when a one-sided Fisher exact test
    says B's correct rate exceeds A's at Holm-adjusted p < SETTLED_ALPHA. The threshold is the inhibition rule's
    and is not lowered here. Without enough outcomes on both sides nothing moves and frozen evidence decides.

    Stated limitation: outcomes are pooled over a method's versions and geometries, as the inhibition rule pools
    them (``_settled_counts``). Reorders ``eligible`` in place; returns the test record, or None."""
    if len(eligible) < 2:
        return None
    first = eligible[0]
    n_a, k_a = settled.get(first["method"], (0, 0))
    if n_a < SETTLED_MIN_N:
        return None
    from scipy.stats import fisher_exact
    tests = []
    for row in eligible[1:]:
        n_b, k_b = settled.get(row["method"], (0, 0))
        if row.get("demoted") or n_b < SETTLED_MIN_N:
            continue
        p = float(fisher_exact([[k_b, n_b - k_b], [k_a, n_a - k_a]], alternative="greater")[1])
        tests.append({"method": row["method"], "settled": [k_b, n_b], "p_one_sided": p})
    if not tests:
        return None
    m, adjusted, running = len(tests), {}, 0.0
    for i, t in enumerate(sorted(tests, key=lambda t: t["p_one_sided"])):
        running = max(running, min(1.0, (m - i) * t["p_one_sided"]))
        adjusted[t["method"]] = running
    for t in tests:
        t["p_holm"] = round(adjusted[t["method"]], 6)
        t["p_one_sided"] = round(t["p_one_sided"], 6)
    winners = [t for t in tests if adjusted[t["method"]] < SETTLED_ALPHA]
    record = {"against": first["method"], "against_settled": [k_a, n_a], "min_n": SETTLED_MIN_N,
              "alpha": SETTLED_ALPHA, "test": "one-sided Fisher exact, Holm over the challengers", "tests": tests,
              "preferred": None}
    if winners:
        win = min(winners, key=lambda t: (t["p_holm"], t["method"]))
        row = next(r for r in eligible if r["method"] == win["method"])
        row["settled_preferred"] = {
            **win, "why": (f"settled outcomes on this body prefer {row['method']} ({win['settled'][0]} of "
                           f"{win['settled'][1]} correct) over the evidence-ranked {first['method']} ({k_a} of "
                           f"{n_a}); one-sided Fisher exact, Holm-adjusted p = {win['p_holm']}")}
        eligible.remove(row)
        eligible.insert(0, row)
        record["preferred"] = row["method"]
    return record


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


def run(params, *, registry, journal=None, model_config=None, caller_window=None, shared_deadline=None,
        shared_compute_limit=None) -> dict:
    from .cortex import _cpu_delta, _cpu_seconds, reason
    started = time.monotonic()
    pid, body = validate(params)
    g = CompetencyGeometry.parse(body.get("geometry", {}))
    from .budget import Controller
    # One thinking budget for the whole decision: the answer, the premises check and every sensitivity re-run
    # draw on the declared latency_budget. It used to be a per-run limit, so one request could spend it six times.
    # Inside a canonical dispatch the caller's grant window bounds the whole decision and reaches every inner run.
    budget = Controller(float(g.latency_budget) if g.latency_budget else DEFAULT_BUDGET_S,
                        declared=bool(g.latency_budget), clock=CLOCK, caller_window=caller_window,
                        shared_deadline=shared_deadline, shared_compute_limit=shared_compute_limit)
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
        receipt["resource_use"]["budget"] = budget.summary()
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
    rows = candidates(data, g, evidence) + constructed_candidates(data, g, registry)
    # the geometry the inputs themselves imply (methods whose native inputs they carry), against the declaration
    from dataclasses import replace
    implied = sorted({c for r in candidates(data, replace(g, geometry=None), evidence)
                      + constructed_candidates(data, replace(g, geometry=None), registry)
                      for c in r.get("epistemic_classes", [])})
    receipt["derived_geometry"] = {"declared": g.geometry, "fits_by_inputs": implied,
                                   "agrees": not g.geometry or not implied or g.geometry in implied}
    if not receipt["derived_geometry"]["agrees"]:
        receipt["dissent"].append(f"declared geometry {g.geometry!r} but the inputs fit methods of {implied}: the "
                                  f"declaration excludes them (check the declaration before trusting a deficit or a "
                                  f"request for missing inputs)")
    receipt["methods_considered"] = [r["method"] for r in rows]
    receipt["methods_rejected"] = [{"method": r["method"], "why": r["rejected"]} for r in rows if r["rejected"]]
    receipt["methods_demoted"] = [{"method": r["method"], "why": r["demoted"]} for r in rows if r.get("demoted")]
    eligible = [r for r in rows if not r["rejected"]]
    # a superseded row the declaration excludes names nothing: promotion keeps the epistemic class, so the
    # superseding mechanism (promoted or not) has the geometry the declaration excludes
    superseding = [{"mechanism": r["superseded_by"]["mechanism"], "supersedes": r["method"],
                    "evidence": r["superseded_by"]["evidence"],
                    "route": "greg.genesis (Capability Genesis) under the enclosing mission's authority",
                    "authority": "none: a candidate to acquire, never an attached method",
                    **({"promoted_genome_rejected": r["superseded_by"]["promoted_rejected"]}
                       if r["superseded_by"].get("promoted_rejected") else {})}
                   for r in rows if r.get("superseded_by", {}).get("deployable")
                   and not r["superseded_by"].get("promoted_as")
                   and not (g.geometry and g.geometry not in r["epistemic_classes"])]
    high = g.consequence_class in HIGH_CONSEQUENCE or vector.high
    if not eligible:
        formed = _formed(registry, data, g, body, high, receipt, budget, pid=pid, vector=vector, journal=journal)
        if formed is not None:
            return finish(*formed)
        # catalogued methods and recipes the request supplies in part, flat and (in a one-part recipe's shape) in
        # its part
        part = _one_part(data)
        partial = _partially_supplied(data, rows, g) + (
            _partially_supplied(_part_data(data, part), candidates(_part_data(data, part), g, evidence, parts=False),
                                g, part) if part else [])
        missing = _missing_information(rows, partial)
        if missing:
            # the method that answers the question asked exists; the request lacks some of its inputs. That is
            # missing information, not a capability deficit: Capability Genesis is not asked to build it again
            receipt["missing_information"] = missing
            receipt["abstentions"].append("missing information: the request lacks " + _lacks(missing))
            return finish("ABSTAIN")
        if superseding:
            # the method that fits was superseded on frozen held-out evidence by a deployable mechanism: name it
            receipt["acquisition_candidates"] = superseding
        # every catalogued method or recipe that reads any of the request's inputs is accounted for, with why it
        # cannot serve
        readers = [{"method": p["method"], **({"part": p["part"]} if p.get("part") else {}),
                    "why": f"reads {p['reads']} and lacks {p['missing_inputs']}: {p['why']}"} for p in partial]
        receipt["capability_deficit"] = {
            "function": f"cognition.{g.geometry or 'unknown'}:{g.subgeometry or 'unspecified'}",
            "purpose": g.objective or g.epistemic_question or "cognitive request",
            "required_inputs": sorted(data), "geometry": g.known(),
            "verification": {"failed": ("every catalogued method that reads these inputs is ineligible here "
                                        "(unserviceable lists why)" if rows else
                                        f"the request's shape (keys {sorted(data)}) matches no catalogued method's "
                                        f"native inputs" + ("; the methods that read some of them are not the "
                                                            "question asked (unserviceable lists why)" if readers
                                                            else ", and no catalogued method or recipe reads any of "
                                                                 "them")),
                             "unserviceable": (receipt["methods_rejected"] + readers
                                               or "no catalogued method or recipe reads any of these inputs"),
                             "verified": True},
            "fitting": [],                          # nothing fits: only a formed mechanism can serve it
            "tried": _formed_tried(registry, receipt),   # formed mechanisms this compile ran with no answer
            "search_order": list(GENESIS_SEARCH),
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
    settled = _settled_counts(journal)
    for r in eligible:
        inhibited = _settled_inhibition(*settled.get(r["method"], (0, 0)))
        if inhibited and not r.get("demoted"):
            r["demoted"] = inhibited                    # live negative evidence changes routing
            r["settled_inhibition"] = True
    by_outcomes = {r["method"] for r in eligible if r.get("settled_inhibition")}
    for r in eligible:
        if r.get("matched_by") and by_outcomes & {m["method"] for m in r["matched_by"]}:
            # a matched genome is a demoted fit too: the recipe need not rank after it. candidates composed the
            # reason from this same list after any earlier one (a lift verdict), and a demoted row is not rewritten
            r["demoted"] = r["demoted"].replace(_matched_reason(r["matched_by"]),
                                                _matched_reason(r["matched_by"], by_outcomes))
    receipt["methods_demoted"] = [{"method": r["method"], "why": r["demoted"]} for r in rows if r.get("demoted")]
    eligible.sort(key=lambda r: _rank(r, plan["prefer"], competence))
    preference = _settled_preference(eligible, settled)
    if preference:
        receipt["settled_preference"] = preference
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
                                        **({"stale_measurements": best["stale_measurements"]}
                                           if best.get("stale_measurements") else {}),
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
        formed = _formed(registry, data, g, body, high, receipt, budget, pid=pid, vector=vector, journal=journal)
        if formed is not None:
            return finish(*formed)
        receipt["capability_deficit"] = {
            "function": f"cognition.{g.geometry or 'unknown'}:{g.subgeometry or 'unspecified'}",
            "purpose": g.objective or g.epistemic_question or "cognitive request",
            "required_inputs": sorted(data), "geometry": g.known(),
            "verification": {"failed": "every fitting method is registered but not attached",
                             "unserviceable": [{"method": r["method"], "why": r["usable_why"]} for r in eligible],
                             "verified": True},
            "fitting": fitting(eligible),           # the need is served once one can run (``runnable``)
            "tried": _formed_tried(registry, receipt),   # formed mechanisms this compile ran with no answer
            "search_order": list(GENESIS_SEARCH),
            "route": "founder attach of the prepared ask, or greg.genesis under the enclosing mission's authority"}
        return finish("CAPABILITY_DEFICIT")
    chosen = runnable[0]
    receipt["method_or_composition_selected"] = chosen["method"]
    receipt["selection_level"] = (_demoted_level(chosen, best) if chosen.get("demoted")
                                  else "preferred_by_settled_outcomes" if chosen.get("settled_preferred")
                                  else "preferred_by_operator" if chosen["operation"] in plan["prefer"]
                                  or chosen["method"] in plan["prefer"] else "admission_status")
    if chosen.get("settled_preferred"):
        receipt["dissent"].append(chosen["settled_preferred"]["why"])
    if chosen.get("demoted"):
        receipt["dissent"].append(chosen["demoted"])
    if chosen.get("stale_evidence"):
        receipt["selection_level"] = "unevaluated_at_current_version"
        receipt["dissent"].append(f"stale admission evidence: {chosen['stale_evidence']}")
    if chosen.get("stale_measurements"):
        # held-out evidence of another version of this method's code, labelled with that version (never ranked)
        receipt["stale_measurements"] = chosen["stale_measurements"]
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
    # 4. execute through the same canonical reason. High consequence raises the proof requirement on every route
    # exactly as on the direct canonical path (FORMALIZATION_INCOMPLETE for formal/optimisation methods); a
    # construction is optimisation-class, and its call draws on the same thinking budget.
    if chosen["kind"] == "constructed":
        return _run_constructed(chosen, data, pid, registry, receipt, finish, high=high, budget=budget,
                                evaluate=plan["evaluate"])
    extra = {"consequences": consequence} if consequence else {}
    if chosen["kind"] == "problem":
        from cortex.routing import FORMAL_ENGINES
        if high and chosen["organ"] in FORMAL_ENGINES and data.get("formalization_complete") is not True:
            receipt["abstentions"].append("FORMALIZATION_INCOMPLETE: complete formal model plus independently "
                                          "verified world assumptions")
            return finish("FORMALIZATION_INCOMPLETE")
        limit = budget.allot("answer", required=True)
        if limit is None:
            receipt["abstentions"].append(budget.stops()[-1]["reason"])
            return finish("ABSTAIN")
        payload = data
        if budget.bounded:
            resources = data.get("resources") or {}
            payload = {**data, "resources": {**resources, "max_latency_s": min(
                float(resources.get("max_latency_s", 30.0)), limit)}}
        inner = reason({"problem_id": pid, "problem": {"question": g.objective or g.epistemic_question or pid,
                                                       "payload": payload}},
                       registry=registry, journal=journal, model_config=model_config, **budget.inner)
        budget.done("answer")
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
        if high and "optimize" in chosen["stages"] and data.get("formalization_complete") is not True:
            receipt["abstentions"].append("FORMALIZATION_INCOMPLETE: complete formal model plus independently "
                                          "verified world assumptions")
            return finish("FORMALIZATION_INCOMPLETE")
        limit = budget.allot("answer", required=True)
        if limit is None:
            receipt["abstentions"].append(budget.stops()[-1]["reason"])
            return finish("ABSTAIN")
        chain = {"question": g.objective or "compiled", "payload": data,
                 **({"max_latency_s": limit} if budget.bounded else {})}
        inner = reason({"problem_id": pid, "chain": chain}, registry=registry, journal=journal,
                       model_config=model_config, **budget.inner)
        budget.done("answer")
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
    limit = budget.allot("answer", required=True)
    if limit is None:
        receipt["abstentions"].append(budget.stops()[-1]["reason"])
        return finish("ABSTAIN")
    geometry_hint = {"latency_limit": limit,
                     **({"consequence_class": g.consequence_class} if g.consequence_class else {})}
    if chosen.get("part"):
        receipt["payload_part"] = chosen["part"]          # the method reads this part of the request: the question
        data = _part_data(data, chosen["part"])
    cpu_started = _cpu_seconds()
    inner = reason({"problem_id": pid, "operation": chosen["operation"], "data": data, "geometry": geometry_hint,
                    **extra}, registry=registry, journal=journal, model_config=model_config, **budget.inner)
    budget.done("answer", cpu_seconds=_cpu_delta(cpu_started))
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
                                      registry, journal, model_config, receipt, extra, budget)
        return finish(done, verdict)
    if "sensitivity" in plan["evaluate"]:
        receipt["sensitivity"] = _sensitivity_runs(pid, chosen["operation"], data, inner["output"], geometry_hint,
                                                   registry, journal, model_config, receipt, extra, budget)
    return finish(done, inner["output"])


def _demoted_level(chosen: dict, best: dict) -> str:
    """Why a demoted fit serves. A demoted row ranks after every fit that is not, so either a better-ranked fit cannot
    run (the receipt names it in ``withheld_best_fit``) or every fit is demoted and this one ranks first, labelled by
    what demoted it: no verified lift, settled outcomes on this body, or else best of the demoted fits (a recipe
    matched by a single genome that settled outcomes on this body demote too)."""
    if chosen is not best:
        return "serves_while_best_fit_withheld"
    if chosen["status"] == "NO_LIFT":
        return "only_fit_despite_no_lift"
    if chosen.get("settled_inhibition"):
        return "demoted_by_settled_outcomes"
    return "best_of_demoted_fits"


def _has_answer(inner: dict) -> bool:
    """An answer the path may use: NONE, or the conditional WORLD_UNVERIFIED a high-consequence geometry gets.
    A refuted or timed-out receipt keeps its output for audit, never for use."""
    return inner["abstention_state"] in ("NONE", "WORLD_UNVERIFIED") and isinstance(inner.get("output"), dict)


def _premises_check(pid, operation, claim, hint, verdict, registry, journal, model_config, receipt, extra,
                    budget) -> dict:
    """An UNSAT negation proves the claim only if the constraints are satisfiable on their own; otherwise every
    property 'holds' vacuously and the claim is PREMISES_INCONSISTENT. The check is required evidence, so the
    thinking budget never prices it away; without room for it the verdict stays undecided."""
    from .cortex import _cpu_delta, _cpu_seconds, reason
    if not claim["constraints"]:
        return {**verdict, "premises": "SATISFIABLE (no constraints)"}
    limit = budget.allot("premises", required=True)
    if limit is None:
        return {**verdict, "premises": f"UNDECIDED ({budget.stops()[-1]['reason']}): the claim may hold vacuously"}
    cpu_started = _cpu_seconds()
    check = reason({"problem_id": f"{pid}/premises"[:96], "operation": operation, "data": premises(claim),
                    "geometry": {**hint, "latency_limit": limit}, **extra}, registry=registry, journal=journal,
                   model_config=model_config, **budget.inner)
    budget.done("premises", cpu_seconds=_cpu_delta(cpu_started))
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


def _sensitivity_runs(pid, operation, data, baseline, hint, registry, journal, model_config, receipt, extra,
                      budget) -> dict:
    """Perturb each numeric top-level input by +10% (at most four) and re-run the same method on the one path.

    Each re-run is optional cognition: the thinking budget starts it only when the slowest measured run fits in
    what remains. An input it cannot afford is reported as untested, never as robust."""
    from .cortex import reason

    def rerun(key, varied, limit):
        out = reason({"problem_id": f"{pid}/sens/{key}"[:128], "operation": operation, "data": varied,
                      "geometry": {**hint, "latency_limit": limit}, **extra}, registry=registry, journal=journal,
                     model_config=model_config, **budget.inner)
        receipt["intermediate_receipts"].append(out["receipt_id"])
        return out

    return _perturbation_runs(data, baseline, budget, receipt, rerun)


def _perturbation_runs(data, baseline, budget, receipt, rerun) -> dict:
    """The sensitivity operator's measurement, shared by every route that answers: ``rerun(key, varied, limit)``
    re-answers the request with one input perturbed and returns a receipt-shaped dict."""
    from .cortex import _cpu_delta, _cpu_seconds
    keys = [k for k in sorted(data) if _numbers(data[k])][:4]
    base = _numbers(baseline)
    rows, not_run = {}, {}
    for key in keys:
        limit = budget.allot(f"sensitivity:{key}", required=False)
        if limit is None:
            not_run[key] = budget.stops()[-1]["reason"]
            continue
        varied = {**data, key: _scaled(data[key], 1.1)}
        cpu_started = _cpu_seconds()
        out = rerun(key, varied, limit)
        budget.done(f"sensitivity:{key}", cpu_seconds=_cpu_delta(cpu_started))
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
    if not_run:
        receipt["dissent"].append(f"sensitivity: {', '.join(not_run)} not tested within the thinking budget; "
                                  "the answer's robustness to them is unknown")
    receipt["resource_use"]["stages"] += len(rows)
    return {"perturbation": "+10% on each numeric top-level input (at most four)", "inputs": rows,
            "fragile_inputs": fragile, "not_run": not_run}
