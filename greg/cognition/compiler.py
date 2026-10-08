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
STATUS_RANK = {"DEFAULT_FOR_GEOMETRY": 0, "NICHE_CAPABILITY": 1, "UNEVALUATED": 2, "EXPERIMENTAL": 3,
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


OPERATORS = (
    Operator("consequence_raises_requirements", ("consequence_class in external_contact|financial|irreversible",),
             "adds independent-verification, fresh-evidence and Gate requirements; never changes the method family",
             ("consequence_class",), ("requirements",), ("consequence class is declared honestly",),
             ("under-declared consequence",), ("read-only questions",), "decision_analysis", "none", "none",
             "tests/unit/test_greg_competency_compiler.py (rule test; no effect benchmark)",
             lambda g, r: g.consequence_class in HIGH_CONSEQUENCE, _requirements_raise),
    Operator("reversibility", ("reversibility == irreversible",), "requires a founder decision or a reversible stage",
             ("reversibility",), ("requirements",), ("reversibility is declared",), ("misdeclared reversibility",),
             (), "decision_analysis", "none", "none", "rule test only",
             lambda g, r: g.reversibility == "irreversible" or g.consequence_class == "irreversible", _reversibility),
    Operator("anti_ruin", ("stochastic and consequence financial",), "adds a tail-bound requirement; prefers the "
             "robust estimate->optimise composition", ("deterministic_or_stochastic", "consequence_class"),
             ("requirements", "prefer"), ("ruin is the dominant loss",), ("over-conservatism",),
             ("deterministic problems",), "decision_analysis", "none", "none",
             "P6 F1 (robust composition vs point optimiser: 14 of 16 point plans claimed coverage they lacked)",
             lambda g, r: g.deterministic_or_stochastic == "stochastic" and g.consequence_class == "financial",
             _anti_ruin),
    Operator("bottleneck", ("graph_structure",), "routes to min-cut control-point analysis first",
             ("graph_structure",), ("prefer",), ("the graph is the system",), ("multi-commodity flows",), (),
             "optimality_certificate", "one max-flow", "milliseconds", "flow_maxflow admission",
             lambda g, r: bool(g.graph_structure), _bottleneck),
    Operator("value_of_information", ("decision under uncertainty with a test option",),
             "prices the next test before acting", ("uncertainty_structure",), ("prefer",),
             ("a test can change the decision",), ("no actionable test",), (), "decision_analysis",
             "three stages", "sub-second", "P6 v2 F4",
             lambda g, r: g.uncertainty_structure in ("beta", "posterior") and g.decision_type == "act_or_test",
             _value_of_information),
    Operator("premortem", ("any consequential decision",), "records the strongest failure story as dissent",
             (), ("dissent",), (), ("ritualised dissent",), ("trivial arithmetic",), "decision_analysis", "none",
             "none", "rule test only",
             lambda g, r: g.consequence_class not in (None, "read_only"), _premortem),
)


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
            if family in genomes:
                need = genomes[family].genome.required_inputs
                status = evidence["genomes"].get(family, {}).get("status", "UNEVALUATED")
                standalone = genomes[family].genome.standalone_decision
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
            rows.append({"method": f"cognition.{family}", "operation": op, "kind": "operation", "status": status,
                         "epistemic_classes": list(classes), "rejected": reason})
    recipe = route(data)
    if recipe:
        verdict = evidence["recipes"].get(recipe, {})
        reason = None
        if verdict.get("lift") is False and verdict.get("prefer"):
            reason = f"frozen VPL verdict: no lift over {verdict['prefer']}; the cheaper constituent is preferred"
        rows.append({"method": f"composition:{recipe}", "operation": recipe, "kind": "composition",
                     "status": "VPL_LIFT" if verdict.get("lift") else verdict.get("status", "UNEVALUATED"),
                     "stages": list(RECIPES[recipe]["stages"]), "rejected": reason})
    return rows


def _rank(row: dict, prefer: list, competence: dict) -> tuple:
    status = 0 if row["status"] == "VPL_LIFT" else STATUS_RANK.get(row["status"], 5)
    preferred = 0 if (row["operation"] in prefer or row["method"] in prefer) else 1
    settled = -competence.get(row["method"], 0.5)
    return (preferred, status, settled, 0 if row["kind"] == "operation" else 1, row["method"])


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
    plan = {"requirements": [], "prefer": [], "notes": [], "dissent": []}
    receipt = {"schema": SCHEMA, "problem_id": pid, "inputs_digest": digest(params), "geometry": g.known(),
               "subgeometry": g.subgeometry, "consequence_class": g.consequence_class or "read_only",
               "methods_considered": [], "methods_rejected": [], "method_or_composition_selected": None,
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
        return finish("HUMAN_JUDGMENT_REQUIRED", human_packet(g, body))
    # 2. operators transform the representation (recorded, never silent)
    for op in OPERATORS:
        if op.applies(g, body):
            op.apply(g, body, plan)
            receipt["transformations"].append({"operator_id": op.operator_id, "transformation": op.transformation,
                                               "evidence_type": op.evidence_type, "benchmark": op.benchmark})
    # 3. candidates by native geometry and inputs; frozen negative evidence excludes
    rows = candidates(data, g, evidence)
    receipt["methods_considered"] = [r["method"] for r in rows]
    receipt["methods_rejected"] = [{"method": r["method"], "why": r["rejected"]} for r in rows if r["rejected"]]
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
        return finish("CAPABILITY_DEFICIT")
    competence = _settled_competence(journal, g.geometry)
    eligible.sort(key=lambda r: _rank(r, plan["prefer"], competence))
    chosen = eligible[0]
    receipt["method_or_composition_selected"] = chosen["method"]
    receipt["selection_level"] = ("preferred_by_operator" if chosen["operation"] in plan["prefer"]
                                  or chosen["method"] in plan["prefer"] else "admission_status")
    receipt["conditional_competence_basis"] = {m: round(v, 4) for m, v in competence.items()} or \
        "no settled outcomes in this journal; admission evidence and cost decide"
    if body.get("execute") is False:
        return finish("PLANNED")
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
    return finish("ANSWERED", inner["output"])
