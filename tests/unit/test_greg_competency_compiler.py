"""Layer 5 Competency Compiler on the canonical cognition entry (directive sections 8-12)."""
import json

import pytest

pytest.importorskip("ortools")
pytest.importorskip("networkx")

from cortex.evaluation.composition_lift import run_v2 as R  # noqa: E402
from greg.cognition import compiler  # noqa: E402
from greg.cognition.cortex import reason, registry_view  # noqa: E402
from greg.cognition.genomes.flow import maxflow_instance  # noqa: E402

RECEIPT_FIELDS = {"problem_id", "geometry", "subgeometry", "consequence_class", "methods_considered",
                  "methods_rejected", "method_or_composition_selected", "selection_level",
                  "conditional_competence_basis", "inputs_digest", "assumptions", "evidence_refs", "transformations",
                  "intermediate_receipts", "proof_artifacts", "uncertainty", "abstentions", "dissent", "cost",
                  "latency_s", "resource_use", "translation_checks", "verification_method", "result",
                  "confidence_type", "authority_state", "outcome_link", "later_appraisal"}


@pytest.fixture
def registry():
    r = registry_view()
    for cid in R.EVAL_ATTACH:
        r.set_state(cid, "ATTACHED")
    return r


@pytest.fixture(autouse=True)
def no_index(tmp_path, monkeypatch):
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")
    return tmp_path / "index.json"


def compile_(registry, geometry, data, **extra):
    return reason({"problem_id": "p", "compile": {"geometry": geometry, "data": data, **extra}}, registry=registry)


def test_receipt_carries_every_directive_field_and_creates_no_authority(registry):
    r = compile_(registry, {"geometry": "optimization", "graph_structure": True}, maxflow_instance(3)[0])
    assert RECEIPT_FIELDS <= set(r) and r["authority_created"] is False
    assert r["authority_state"] == "EXISTING_KERNEL_GATE_REQUIRED"
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == "cognition.flow_maxflow"
    assert r["confidence_type"] == "optimality_certificate" and r["intermediate_receipts"]


def test_legal_or_value_questions_route_to_qualified_human_judgment_without_a_vote(registry):
    for geometry in ({"geometry": "legal"}, {"geometry": "normative"}, {"human_judgment_required": True},
                     {"geometry": "optimization", "rights_impact": True}):
        r = compile_(registry, geometry, maxflow_instance(3)[0])
        assert r["state"] == "HUMAN_JUDGMENT_REQUIRED" and not r["intermediate_receipts"]
        packet = r["result"]
        assert "majority" in packet["decision_authority"] and "refuse" in packet["refusal_rights"]


def test_prohibited_harm_is_refused_before_optimisation(registry):
    for consequence in ({"rights": 0.1}, {"lawful": False}, {"consent": False}):
        r = compile_(registry, {"geometry": "optimization"}, maxflow_instance(3)[0], consequence=consequence)
        assert r["state"] == "PROHIBITED" and not r["methods_considered"]


def test_high_consequence_raises_requirements_and_does_not_route_to_a_formal_organ(registry):
    data = {"factors": [{"name": "a", "low": 1, "central": 2, "high": 3}]}
    r = compile_(registry, {"geometry": "estimate", "consequence_class": "financial"}, data)
    assert r["method_or_composition_selected"] == "cognition.estimation"
    assert any("Kernel Gate" in q for q in r["requirements"])
    assert any(t["operator_id"] == "consequence_raises_requirements" for t in r["transformations"])


def test_a_geometry_no_method_serves_becomes_a_genesis_ready_deficit(registry):
    r = compile_(registry, {"geometry": "optimization", "subgeometry": "protein folding"}, {"sequence": "ACDE"})
    deficit = r["capability_deficit"]
    assert r["state"] == "CAPABILITY_DEFICIT" and deficit["verification"]["verified"] is True
    assert deficit["search_order"][0] == "attached" and "genesis" in deficit["route"]


def test_frozen_negative_evidence_changes_routing(registry, no_index):
    data = maxflow_instance(3)[0]
    assert compile_(registry, {"geometry": "optimization"}, data)["method_or_composition_selected"] == \
        "cognition.flow_maxflow"
    no_index.write_text(json.dumps({"genomes": {"flow_maxflow": {"status": "REJECTED"}}, "recipes": {},
                                    "routing": {}}))
    r = compile_(registry, {"geometry": "optimization"}, data)
    assert r["state"] == "CAPABILITY_DEFICIT"
    assert {"method": "cognition.flow_maxflow", "why": "frozen admission status REJECTED"} in r["methods_rejected"]


def test_a_composition_without_verified_lift_yields_to_any_other_fit(registry, no_index):
    no_index.write_text(json.dumps({"genomes": {}, "routing": {},
                                    "recipes": {"graph_then_allocate": {"lift": False,
                                                                        "prefer": "flow_reinforce_greedy"}}}))
    both = {**R.f3(3)["payload"], **maxflow_instance(3)[0]}      # a recipe and an operation both fit
    r = compile_(registry, {"geometry": "optimization", "graph_structure": True}, both, execute=False)
    assert any(x["method"] == "composition:graph_then_allocate" and "no lift" in x["why"]
               for x in r["methods_demoted"])
    assert r["method_or_composition_selected"] == "cognition.flow_maxflow"
    # the recipe's one-part request is also asked of the operations its part fits: the constituent the frozen
    # verdict prefers serves it, reading that part
    alone = compile_(registry, {"geometry": "optimization"}, R.f3(3)["payload"], execute=False)
    assert alone["method_or_composition_selected"] == "cognition.flow_reinforce_greedy"
    registry.set_state("cognition.flow_reinforce_greedy", "VERIFIED")             # withheld: no operation can run
    only = compile_(registry, {"geometry": "optimization"}, R.f3(3)["payload"], execute=False)
    assert only["method_or_composition_selected"] == "composition:graph_then_allocate"   # the only runnable fit stays


def test_a_demoted_composition_stays_the_route_when_nothing_else_fits(registry, no_index):
    no_index.write_text(json.dumps({"genomes": {}, "routing": {},
                                    "recipes": {"forecast_then_allocate": {"lift": False, "prefer": "optimize_alone",
                                                                           "evidence": "results-v2.json#F5"}}}))
    r = compile_(registry, {"geometry": "optimization"}, R.f5(0)["payload"], execute=False)
    assert r["method_or_composition_selected"] == "composition:forecast_then_allocate"
    assert r["selection_level"] == "only_fit_despite_no_lift"
    assert any("no lift over optimize_alone" in d for d in r["dissent"])


def test_plan_only_records_operator_transformations(registry):
    r = compile_(registry, {"geometry": "optimization", "graph_structure": True, "consequence_class": "irreversible"},
                 R.f3(3)["payload"], execute=False)
    assert r["state"] == "PLANNED" and not r["intermediate_receipts"]
    ops = {t["operator_id"] for t in r["transformations"]}
    assert {"bottleneck", "reversibility", "consequence_raises_requirements", "premortem"} <= ops


def test_unknown_geometry_fields_are_refused_and_unknowns_stay_unknown(registry):
    with pytest.raises(Exception):
        compile_(registry, {"geometry": "optimization", "omniscience": True}, {})
    g = compiler.CompetencyGeometry.parse({"geometry": "prediction"})
    assert g.known() == {"geometry": "prediction"} and g.forecast_horizon is None


def test_every_directive_mental_model_is_an_operator_or_names_its_mechanism():
    ids = {op.operator_id for op in compiler.OPERATORS}
    assert len(compiler.DIRECTIVE_MODELS) == 33
    for model, target in compiler.DIRECTIVE_MODELS.items():
        assert target in ids or target in compiler.OPERATOR_HOMES, model
    for op in compiler.OPERATORS:
        assert op.effect_kind in ("representation", "candidate_set", "evidence_request", "evaluation")
        assert all([op.operator_id, op.problem_signatures, op.transformation, op.evidence_type, op.cost,
                    op.latency, op.benchmark]), op.operator_id


def test_sensitivity_analysis_actually_reruns_the_method(registry):
    r = compile_(registry, {"geometry": "optimization", "graph_structure": True, "consequence_class": "financial",
                            "deterministic_or_stochastic": "stochastic"}, maxflow_instance(3)[0])
    # a financial geometry gets the canonical path's conditional result, never ANSWERED (review finding 7: the
    # compiled path used to drop the consequence class); the answer is kept and still evaluated
    assert r["state"] == "WORLD_UNVERIFIED" and isinstance(r["result"], dict)
    sens = r["sensitivity"]
    assert sens["inputs"] and len(r["intermediate_receipts"]) == 1 + len(sens["inputs"])
    for v in sens["inputs"].values():
        assert v["state"] != "ANSWERED" or isinstance(v["answer_changed"], bool)
    assert any(t["operator_id"] == "sensitivity_analysis" and t["effect_kind"] == "evaluation"
               for t in r["transformations"])


def test_strategic_geometry_recruits_game_theory_and_records_it(registry):
    r = compile_(registry, {"geometry": "optimization", "multi_actor": True, "adversarial_pressure": 0.5,
                            "consequence_class": "internal_write"}, maxflow_instance(3)[0], execute=False)
    ops = {t["operator_id"] for t in r["transformations"]}
    assert {"game_theory", "inversion", "premortem"} <= ops


def test_positive_admission_evidence_binds_the_version_it_measured(registry, no_index):
    # a status measured on another version of the code is not inherited: the method ranks as UNEVALUATED
    # and the receipt says so; negative evidence persists until a re-admission replaces it
    from greg.cognition.genomes import library
    data = maxflow_instance(3)[0]
    current = library.genome("flow_maxflow").version
    no_index.write_text(json.dumps({"genomes": {"flow_maxflow": {"status": "DEFAULT_FOR_GEOMETRY",
                                                                 "version": current}}, "recipes": {}, "routing": {}}))
    fresh = compile_(registry, {"geometry": "optimization"}, data, execute=False)
    assert fresh["selection_level"] == "admission_status"
    no_index.write_text(json.dumps({"genomes": {"flow_maxflow": {"status": "DEFAULT_FOR_GEOMETRY",
                                                                 "version": "0.0.1"}}, "recipes": {}, "routing": {}}))
    stale = compile_(registry, {"geometry": "optimization"}, data, execute=False)
    assert stale["method_or_composition_selected"] == "cognition.flow_maxflow"
    assert stale["selection_level"] == "unevaluated_at_current_version"
    assert any("measured at version 0.0.1" in d for d in stale["dissent"])
    no_index.write_text(json.dumps({"genomes": {"flow_maxflow": {"status": "REJECTED", "version": "0.0.1"}},
                                    "recipes": {}, "routing": {}}))
    assert compile_(registry, {"geometry": "optimization"}, data)["state"] == "CAPABILITY_DEFICIT"


def test_measured_subregion_evidence_reaches_the_receipt_and_names_an_acquisition(registry, no_index):
    # develop_repair on frozen held-out instances: dominated 0-15 by the centralized replanner with a
    # reliable controller, favoured 12-3 with an unreliable one. The receipt carries the verdict for the
    # request's own subregion; a dominated route names the competitor for Capability Genesis (no authority).
    from greg.cognition.genomes import library
    item = library.executables()["develop_repair"]
    table = {"reliable_controller": {"n": 15, "wins": 0, "losses": 15, "ties": 0, "p_better": 1.0, "p_worse": 3.1e-05},
             "unreliable_controller": {"n": 15, "wins": 12, "losses": 3, "ties": 0, "p_better": 0.017578,
                                       "p_worse": 0.996307}}
    no_index.write_text(json.dumps({"genomes": {"develop_repair": {
        "status": "NICHE_CAPABILITY", "version": item.genome.version, "evidence": "results.json#develop_repair",
        "competitor": item.genome.competitor, "subregions_vs_competitor": table}}, "recipes": {}, "routing": {}}))
    geometry = {"geometry": item.genome.epistemic_class}
    registry.set_state("cognition.develop_repair", "ATTACHED")       # evaluation-only, in memory
    dominated = compile_(registry, geometry, item.instance(0)[0], execute=False)
    assert dominated["subregion_evidence"]["name"] == "reliable_controller"
    assert dominated["subregion_evidence"]["verdict"] == "DOMINATED"
    assert any("lost 15-0" in d for d in dominated["dissent"])
    assert dominated["acquisition_candidates"][0]["mechanism"] == item.genome.competitor
    assert dominated["acquisition_candidates"][0]["authority"].startswith("none")
    favoured = compile_(registry, geometry, item.instance(1)[0], execute=False)
    assert favoured["subregion_evidence"]["verdict"] == "FAVOURED" and "acquisition_candidates" not in favoured


def test_stale_subregion_evidence_never_steers_and_stale_negative_evidence_persists(registry, no_index):
    """Review finding 10: a version bump left old subregion verdicts ordering fits, adding dissent and naming
    acquisitions, and promoted a stale EXPERIMENTAL status to UNEVALUATED (ranked higher)."""
    from greg.cognition.genomes import library
    item = library.executables()["develop_repair"]
    table = {"reliable_controller": {"n": 15, "wins": 0, "losses": 15, "ties": 0, "p_better": 1.0, "p_worse": 3.1e-05}}
    no_index.write_text(json.dumps({"genomes": {"develop_repair": {
        "status": "NICHE_CAPABILITY", "version": "0.0.1", "evidence": "results.json#develop_repair",
        "competitor": item.genome.competitor, "subregions_vs_competitor": table}}, "recipes": {}, "routing": {}}))
    registry.set_state("cognition.develop_repair", "ATTACHED")
    r = compile_(registry, {"geometry": item.genome.epistemic_class}, item.instance(0)[0], execute=False)
    assert r["selection_level"] == "unevaluated_at_current_version"
    assert "subregion_evidence" not in r and "acquisition_candidates" not in r
    assert not any("lost 15-0" in d for d in r["dissent"])
    rows = compiler.candidates(item.instance(0)[0], compiler.CompetencyGeometry.parse(
        {"geometry": item.genome.epistemic_class}), {"genomes": {"develop_repair": {
            "status": "EXPERIMENTAL", "version": "0.0.1"}}, "recipes": {}, "routing": {}})
    assert {r["status"] for r in rows if r["method"] == "cognition.develop_repair"} == {"EXPERIMENTAL"}


def test_a_superseded_fit_names_the_deployable_mechanism_that_superseded_it(registry, no_index, monkeypatch):
    """Admission v2: basal_pid was superseded 0-30 by the simulation-optimised PI. Where that mechanism is not a
    registered genome, a request only basal_pid fits is a capability deficit, and the receipt names the mechanism
    for Genesis instead of leaving the deficit blank."""
    from greg.cognition import catalog
    from greg.cognition.genomes import library
    item = library.executables()["basal_pid"]
    monkeypatch.delitem(catalog.FAMILIES, library.promotions()["basal_pid"])     # its promotion not registered
    no_index.write_text(json.dumps({"genomes": {"basal_pid": {
        "status": "SUPERSEDED", "version": item.genome.version, "evidence": "v2/results.json#genomes.basal_pid"}},
        "recipes": {}, "routing": {}}))
    r = compile_(registry, {"geometry": item.genome.epistemic_class}, item.instance(0)[0], execute=False)
    assert r["state"] == "CAPABILITY_DEFICIT"
    [candidate] = [c for c in r["acquisition_candidates"] if c["supersedes"] == "cognition.basal_pid"]
    assert candidate["mechanism"] == item.genome.competitor and candidate["authority"].startswith("none")
    assert candidate["evidence"] == "v2/results.json#genomes.basal_pid"


def test_a_promoted_competitor_is_asked_for_by_attach_not_acquired_by_genesis(registry, no_index):
    """Once the superseding mechanism is a registered genome (greg/cognition/genomes/competitors.py), the same
    request fits it: the deficit is only that it is withheld, the founder's attach ask carries the frozen
    supersession evidence labelled for what it measured, and nothing is proposed for Genesis acquisition."""
    from greg import asks
    from greg.cognition.genomes import library
    item = library.executables()["basal_pid"]
    no_index.write_text(json.dumps({"genomes": {"basal_pid": {
        "status": "SUPERSEDED", "version": item.genome.version, "evidence": "v2/results.json#genomes.basal_pid"}},
        "recipes": {}, "routing": {}}))
    r = compile_(registry, {"geometry": item.genome.epistemic_class}, item.instance(0)[0], execute=False)
    assert r["state"] == "CAPABILITY_DEFICIT" and "acquisition_candidates" not in r
    assert {"method": "cognition.basal_pid", "why": "frozen admission status SUPERSEDED"} in r["methods_rejected"]
    assert r["withheld_best_fit"]["method"] == "cognition.pid_simopt"
    assert r["withheld_best_fit"]["promotes"] == "cognition.basal_pid"
    rows = compiler.candidates(item.instance(0)[0], compiler.CompetencyGeometry.parse(
        {"geometry": item.genome.epistemic_class}), json.loads(no_index.read_text()))
    [old] = [x for x in rows if x["method"] == "cognition.basal_pid"]
    assert old["superseded_by"]["promoted_as"] == "cognition.pid_simopt"
    ask = r["founder_attach_ask"]
    assert ask["kind"] == "CAPABILITY_ATTACH" and ask["authority_requested"]["attach"] == "cognition.pid_simopt"
    assert ask["evidence"]["admission_status"] == "UNEVALUATED"
    assert ask["evidence"]["promotes"]["supersession_evidence"] == "v2/results.json#genomes.basal_pid"
    assert ask["evidence"]["promotes"]["superseded_status"] == "SUPERSEDED" and asks.screen(ask) == []
    registry.set_state("cognition.pid_simopt", "ATTACHED")            # evaluation-only founder pin, in memory
    planned = compile_(registry, {"geometry": item.genome.epistemic_class}, item.instance(0)[0], execute=False)
    assert planned["state"] == "PLANNED" and planned["method_or_composition_selected"] == "cognition.pid_simopt"


def test_an_oracle_competitor_is_never_proposed_for_acquisition(registry, no_index):
    from greg.cognition.genomes import library
    item = library.executables()["collective_market"]
    data = item.instance(0)[0]
    name = item.subregion(data)
    no_index.write_text(json.dumps({"genomes": {"collective_market": {
        "status": "DEFAULT_FOR_GEOMETRY", "version": item.genome.version, "competitor": item.genome.competitor,
        "subregions_vs_competitor": {name: {"n": 10, "wins": 0, "losses": 10, "ties": 0, "p_better": 1.0,
                                            "p_worse": 0.001}}}}, "recipes": {}, "routing": {}}))
    registry.set_state("cognition.collective_market", "ATTACHED")
    r = compile_(registry, {"geometry": item.genome.epistemic_class}, data, execute=False)
    assert r["subregion_evidence"]["verdict"] == "DOMINATED" and "acquisition_candidates" not in r


def test_a_withheld_best_fit_prepares_one_screened_founder_attach_ask(registry, no_index):
    # the best fit by frozen evidence is registered but withheld: the compiler says so, prepares an attach ask
    # on the one asks contract (never recorded or acted on here) and serves nothing it cannot run
    from greg import asks
    from greg.cognition.genomes import library
    item = library.executables()["develop_repair"]
    no_index.write_text(json.dumps({"genomes": {"develop_repair": {
        "status": "NICHE_CAPABILITY", "version": item.genome.version, "evidence": "results.json#develop_repair"}},
        "recipes": {}, "routing": {}}))
    r = compile_(registry, {"geometry": item.genome.epistemic_class}, item.instance(1)[0], execute=False)
    assert r["state"] == "CAPABILITY_DEFICIT"
    assert r["withheld_best_fit"]["method"] == "cognition.develop_repair"
    assert r["withheld_best_fit"]["state"].startswith("state VERIFIED") and r["withheld_best_fit"]["served_by"] is None
    ask = r["founder_attach_ask"]
    assert ask["state"] == "PREPARED_NOT_RECORDED" and ask["resource"] == "capability"
    assert ask["authority_requested"] == {"attach": "cognition.develop_repair", "spend": "none",
                                          "consequence_class": "read_only"}
    assert ask["evidence"]["admission_status"] == "NICHE_CAPABILITY"
    assert any(o["cost"] == "none" for o in ask["options"])                   # refusing is a costed choice
    asks.validate({k: v for k, v in ask.items() if k not in ("state", "record_with")})
    assert asks.screen(ask) == []


def test_a_composition_with_a_withheld_stage_never_displaces_an_attached_operation(registry, no_index):
    """Review finding 12: graph -> allocate ranked first on its lift and was 'usable' although its compile stage
    was withheld, so the attached max-flow genome never served."""
    both = {**R.f3(3)["payload"], **maxflow_instance(3)[0]}
    no_index.write_text(json.dumps({"genomes": {"flow_maxflow": {"status": "NICHE_CAPABILITY"}},
                                    "recipes": {"graph_then_allocate": {"lift": True, "status": "VPL_LIFT"}},
                                    "routing": {}}))
    geometry = {"geometry": "optimization"}           # no graph_structure operator: the recipe's lift ranks it first
    registry.set_state("cognition.flow_capacity_plan", "VERIFIED")             # a stage withheld
    r = compile_(registry, geometry, both, execute=False)
    assert r["state"] == "PLANNED" and r["method_or_composition_selected"] == "cognition.flow_maxflow"
    assert "compile_capacity_expansion" in r["withheld_best_fit"]["state"]
    assert r["founder_attach_ask"]["state"] == "NOT_PREPARED"                 # a recipe is not attachable
    registry.set_state("cognition.flow_capacity_plan", "ATTACHED")
    served = compile_(registry, geometry, both, execute=False)
    assert served["method_or_composition_selected"] == "composition:graph_then_allocate"


def test_a_withheld_best_fit_is_asked_for_on_the_attach_contract(registry, no_index):
    from greg import asks
    from greg.console import _attachable
    both = {**R.f3(3)["payload"], **maxflow_instance(3)[0]}
    no_index.write_text(json.dumps({"genomes": {"flow_maxflow": {"status": "DEFAULT_FOR_GEOMETRY"}},
                                    "recipes": {}, "routing": {}}))
    geometry = {"geometry": "optimization", "graph_structure": True}
    attached = compile_(registry, geometry, both, execute=False)
    assert attached["method_or_composition_selected"] == "cognition.flow_maxflow"
    assert "withheld_best_fit" not in attached and "founder_attach_ask" not in attached
    registry.set_state("cognition.flow_maxflow", "VERIFIED")                   # withhold the best fit
    r = compile_(registry, geometry, both, execute=False)
    # the recipe's cross-check stage is the withheld max-flow genome itself, so nothing usable remains
    assert r["state"] == "CAPABILITY_DEFICIT"
    assert r["withheld_best_fit"] == {"method": "cognition.flow_maxflow", "state": "state VERIFIED",
                                      "status": "DEFAULT_FOR_GEOMETRY", "served_by": None}
    ask = r["founder_attach_ask"]
    assert ask["kind"] == "CAPABILITY_ATTACH" and ask["authority_requested"]["attach"] == "cognition.flow_maxflow"
    assert ask["evidence"]["registered"] == [{"capability_id": "cognition.flow_maxflow", "state": "VERIFIED"}]
    assert [c["capability_id"] for c in _attachable(ask)] == ["cognition.flow_maxflow"]   # the Attach button exists
    assert asks.surface(ask)["answer_effect"].startswith("Approve or Reject only records")


@pytest.mark.parametrize("state", ["QUARANTINED", "DETACHED"])
def test_no_attach_ask_for_a_capability_the_founder_cannot_attach(registry, no_index, state):
    """Review finding 11: quarantined and detached capabilities were asked about as if attachable."""
    no_index.write_text(json.dumps({"genomes": {"flow_maxflow": {"status": "DEFAULT_FOR_GEOMETRY"}},
                                    "recipes": {}, "routing": {}}))
    registry.set_state("cognition.flow_maxflow", state)
    r = compile_(registry, {"geometry": "optimization", "graph_structure": True}, maxflow_instance(3)[0],
                 execute=False)
    assert r["state"] == "CAPABILITY_DEFICIT" and r["founder_attach_ask"]["state"] == "NOT_PREPARED"


def test_an_urgent_sounding_problem_id_never_aborts_routing(registry, no_index):
    """Review finding 2: 'deadline' in the caller's problem id failed the ask screen and crashed the compile."""
    from greg import asks
    no_index.write_text(json.dumps({"genomes": {"flow_maxflow": {"status": "DEFAULT_FOR_GEOMETRY"}},
                                    "recipes": {}, "routing": {}}))
    registry.set_state("cognition.flow_maxflow", "VERIFIED")
    r = reason({"problem_id": "deadline-urgent-allocation-7", "compile": {
        "geometry": {"geometry": "optimization", "graph_structure": True}, "data": maxflow_instance(3)[0],
        "execute": False}}, registry=registry)
    assert r["state"] == "CAPABILITY_DEFICIT"
    assert r["founder_attach_ask"]["kind"] == "CAPABILITY_ATTACH"
    assert asks.screen(r["founder_attach_ask"], quoted=("deadline-urgent-allocation-7",)) == []


def test_a_formal_model_reaches_the_cortex_formal_organ_through_the_canonical_problem_path(registry):
    """Audit 2026-10-14: no compile request could reach the Z3 / CP-SAT, Fermi or causal organs; a formal model
    produced zero candidates. The cortex's own route policy now names the organ."""
    from cortex.examples import STAFFING
    r = compile_(registry, {"geometry": "optimization"}, STAFFING["payload"])
    assert r["method_or_composition_selected"] == "cognition.cortex.formal.z3"
    assert r["state"] in ("ANSWERED", "WORLD_UNVERIFIED") and r["intermediate_receipts"]
    assert r["consequence_class"] == "undeclared"               # never asserted read_only when nobody declared it
    high = compile_(registry, {"geometry": "optimization", "consequence_class": "financial"}, STAFFING["payload"])
    assert high["state"] == "FORMALIZATION_INCOMPLETE"


def test_the_consequence_vector_is_parsed_strictly_and_raises_the_proof_requirement(registry):
    from greg.cognition.contracts import CognitionError
    data = maxflow_instance(3)[0]
    assert compile_(registry, {"geometry": "optimization"}, data, consequence={"discrimination": 0.2})["state"] == \
        "PROHIBITED"
    harmed = compile_(registry, {"geometry": "optimization"}, data, consequence={"financial": 0.8})
    assert harmed["state"] == "WORLD_UNVERIFIED" and isinstance(harmed["result"], dict)
    with pytest.raises(CognitionError, match="ConsequenceVector"):
        compile_(registry, {"geometry": "optimization"}, data, consequence={"high": True})


def test_measured_held_out_latency_breaks_ties_within_one_status():
    fast = {"method": "cognition.a", "operation": "x", "kind": "operation", "status": "DEFAULT_FOR_GEOMETRY",
            "median_seconds": 0.001}
    slow = {**fast, "method": "cognition.b", "median_seconds": 0.5}
    unmeasured = {k: v for k, v in {**fast, "method": "cognition.c"}.items() if k != "median_seconds"}
    ranked = sorted([unmeasured, slow, fast], key=lambda r: compiler._rank(r, [], {}))
    assert [r["method"] for r in ranked] == ["cognition.a", "cognition.b", "cognition.c"]
    niche = {**fast, "method": "cognition.d", "status": "NICHE_CAPABILITY", "median_seconds": 0.0001}
    assert sorted([niche, slow], key=lambda r: compiler._rank(r, [], {}))[0]["method"] == "cognition.b"


def test_on_the_body_a_withheld_best_fit_is_asked_for_once_per_method_and_the_founder_can_attach_it(tmp_path,
                                                                                                    no_index):
    """Audit 2026-10-14: the compiler prepared attach asks that nothing recorded. With a canonical journal it
    records one CAPABILITY_ATTACH ask per method and measured version, however many requests need it."""
    from greg.body import Body
    from greg.console import _attachable
    from tests.greg_fixtures import make_body
    no_index.write_text(json.dumps({"genomes": {"flow_maxflow": {"status": "DEFAULT_FOR_GEOMETRY", "version": "x"}},
                                    "recipes": {}, "routing": {}}))
    home, _, _, _ = make_body(tmp_path)
    with Body(home) as b:
        registry = registry_view(b.journal)
        assert registry.state["cognition.flow_maxflow"] == "VERIFIED"           # withheld on a fresh body
        for pid in ("first", "second"):
            r = reason({"problem_id": pid, "compile": {"geometry": {"geometry": "optimization"},
                                                       "data": maxflow_instance(3)[0], "execute": False}},
                       registry=registry, journal=b.journal)
            assert r["founder_attach_ask"]["state"] == "RECORDED"
        requested = [e.payload for e in b.journal.replay("decision.requested")]
    assert len(requested) == 1 and requested[0]["kind"] == "CAPABILITY_ATTACH"
    assert [c["capability_id"] for c in _attachable(requested[0])] == ["cognition.flow_maxflow"]


def test_settled_failures_on_the_body_demote_a_method_and_a_few_do_not(registry, no_index, monkeypatch):
    """Section 31 item 13: live negative evidence changes routing. Ten or more settled outcomes whose 95% upper
    bound on correctness is below one half demote the method (ranked after every other fit, never deleted)."""
    both = {**R.f3(3)["payload"], **maxflow_instance(3)[0]}
    no_index.write_text(json.dumps({"genomes": {"flow_maxflow": {"status": "DEFAULT_FOR_GEOMETRY"}},
                                    "recipes": {}, "routing": {}}))
    geometry = {"geometry": "optimization"}
    monkeypatch.setattr(compiler, "_settled_counts", lambda journal: {"cognition.flow_maxflow": (12, 2)})
    r = compile_(registry, geometry, both, execute=False)
    assert r["method_or_composition_selected"] == "composition:graph_then_allocate"
    assert any("2 of 12 correct" in d["why"] for d in r["methods_demoted"])
    monkeypatch.setattr(compiler, "_settled_counts", lambda journal: {"cognition.flow_maxflow": (6, 0)})
    assert compile_(registry, geometry, both, execute=False)["method_or_composition_selected"] == \
        "cognition.flow_maxflow"                                     # too few outcomes to inhibit
    assert compiler._settled_inhibition(12, 8) is None


def test_an_executed_composition_keeps_each_stages_counterargument_as_dissent(registry, no_index):
    """Audit 2026-10-14 (section 12): the composition branch dropped every stage's strongest counterargument."""
    no_index.write_text(json.dumps({"genomes": {"flow_reinforce_greedy": {"status": "SUPERSEDED"}}, "routing": {},
                                    "recipes": {"graph_then_allocate": {"lift": True, "status": "VPL_LIFT"}}}))
    r = compile_(registry, {"geometry": "optimization"}, R.f3(3)["payload"])
    assert r["method_or_composition_selected"] == "composition:graph_then_allocate"
    stages = [d for d in r["dissent"] if d.startswith("stage ")]
    assert len(stages) == len(r["intermediate_receipts"]) >= 2


def test_the_geometry_the_inputs_imply_is_recorded_and_a_contradicting_declaration_is_dissent(registry):
    """Audit 2026-10-14 (section 31 item 3a): geometry was only ever declared, never derived from the data."""
    agree = compile_(registry, {"geometry": "optimization"}, maxflow_instance(3)[0], execute=False)
    assert agree["derived_geometry"]["agrees"] is True and "optimization" in agree["derived_geometry"]["fits_by_inputs"]
    wrong = compile_(registry, {"geometry": "causal"}, maxflow_instance(3)[0], execute=False)
    assert wrong["derived_geometry"]["agrees"] is False and wrong["state"] == "CAPABILITY_DEFICIT"
    assert any("declared geometry 'causal'" in d for d in wrong["dissent"])


def test_a_method_that_answers_a_relaxation_is_rejected_not_allowed_to_answer():
    """A capacity-expansion request (budget, prices, increment limit) was answered by max_flow, which ignores all
    three and returns no plan. A strict-input-subset method that does not produce the fuller method's decision is
    rejected; one producing the same decision from less side information still competes."""
    from greg.cognition.genomes import library
    mcf = library.executables()["flow_expansion_mcf"]
    data, truth = mcf.instance(3)
    attached = registry_view()
    for cid in ("cognition.flow_expansion_mcf", "cognition.flow_maxflow"):
        attached.set_state(cid, "ATTACHED")
    r = reason({"problem_id": "relax", "compile": {"geometry": {"consequence_class": "read_only"}, "data": data}},
               registry=attached)
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == "cognition.flow_expansion_mcf"
    assert r["result"]["flow_value"] == truth["optimum"]
    why = {m["method"]: m["why"] for m in r["methods_rejected"]}
    assert "answers a relaxation" in why["cognition.flow_maxflow"] and "budget" in why["cognition.flow_maxflow"]
    only_maxflow = registry_view()
    only_maxflow.set_state("cognition.flow_maxflow", "ATTACHED")                    # the fuller method withheld
    r = reason({"problem_id": "relax2", "compile": {"geometry": {"consequence_class": "read_only"}, "data": data}},
               registry=only_maxflow)
    assert r["method_or_composition_selected"] != "cognition.flow_maxflow" and r["state"] != "ANSWERED"
    signal = library.executables()["basal_bayes_filter"].instance(0)[0]
    rows = compiler.candidates(signal, compiler.CompetencyGeometry.parse({}), compiler.evidence_index())
    eligible = {row["method"] for row in rows if not row["rejected"]}
    assert {"cognition.basal_hysteresis", "cognition.basal_bayes_filter"} <= eligible   # same decision: they compete
    formal = {"variables": {"x": [0, 5]}, "constraints": [], "objective": {"coefficients": {"x": 1}, "sense": "max"}}
    rows = compiler.candidates(formal, compiler.CompetencyGeometry.parse({}), compiler.evidence_index())
    assert "answers a relaxation" in next(row["rejected"] for row in rows if row["method"] == "cognition.formal")


def test_a_tracker_staffing_request_compiles_to_the_basal_tracker_recipe():
    """Regression (P6 v5): {observed_today, standing_plan, staffing} is the track_then_staff geometry. No single
    genome reads those inputs, so the compiler must reach the composition (basal Kalman tracker -> Erlang C), plan
    it without running it, then run it through the same canonical path when execution is asked for."""
    attached = registry_view()
    for cid in ("cognition.basal_kalman", "cognition.queue_erlang"):
        attached.set_state(cid, "ATTACHED")
    noise = [0.05, -0.12, 0.08, 0.15, -0.04, 0.1, -0.09, 0.02, 0.11, -0.13, 0.06, 0.0, -0.07, 0.12, 0.03]
    data = {"observed_today": [round(110 * (1 + e)) for e in noise],
            "standing_plan": {"blocks": [100.0] * 48, "decision_block": 16},
            "staffing": {"block_seconds": 1800.0, "mean_service_time": 1200.0, "target_wait": 120.0,
                         "max_wait_probability": 0.2, "agent_cost": 1.0, "shortage_penalty": 10.0},
            "tracker": {"q": 1e-5, "r": 0.01, "prior": {"mean": [1.0, 0.0], "var": [0.04, 1e-5]}}}
    planned = compile_(attached, {"consequence_class": "read_only"}, data, execute=False)
    assert planned["state"] == "PLANNED" and planned["method_or_composition_selected"] == "composition:track_then_staff"
    assert not planned["intermediate_receipts"]
    r = compile_(attached, {"consequence_class": "read_only"}, data)
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == "composition:track_then_staff"
    assert len(r["intermediate_receipts"]) == 2 and type(r["result"]["agents"]) is int
    assert r["authority_created"] is False


def test_a_declared_feasibility_question_is_not_a_relaxation_of_an_optimisation_it_excludes():
    """Review 2026-10-14: a request declared constraint_feasibility (or deductive) whose model also carries an
    objective ended in CAPABILITY_DEFICIT: formal was rejected as a relaxation of optimisation methods that the
    declared geometry itself excludes, and Genesis was asked for a capability that exists and is attached."""
    data = {"variables": {"x": [0, 5], "y": [0, 5]},
            "constraints": [{"coefficients": {"x": 1, "y": 1}, "op": "<=", "rhs": 4}],
            "objective": {"coefficients": {"x": 1}, "sense": "max"}}
    for declared in ("constraint_feasibility", "deductive"):
        r = reason({"problem_id": "feas", "compile": {"geometry": {"geometry": declared,
                                                                  "consequence_class": "read_only"}, "data": data}},
                   registry=registry_view())
        assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == "cognition.formal", declared
        assert r["capability_deficit"] is None
        assert not any(m["method"] == "cognition.formal" for m in r["methods_rejected"])
    undeclared = compiler.candidates(data, compiler.CompetencyGeometry.parse({}), compiler.evidence_index())
    assert "answers a relaxation" in next(row["rejected"] for row in undeclared if row["method"] == "cognition.formal")


def test_a_request_that_omits_one_input_of_the_fuller_method_is_not_answered_by_the_relaxation():
    """Review 2026-10-14: a capacity-expansion request with budget and prices but no max_increment was ANSWERED by
    max_flow, which ignores both and returns no plan. The fuller method decides although the request supplies only
    part of its inputs; the request ends asking for the missing input, not in a capability deficit."""
    from greg.cognition.genomes import library
    data, _ = library.executables()["flow_expansion_mcf"].instance(3)
    partial = {k: v for k, v in data.items() if k != "max_increment"}
    attached = registry_view()
    for cid in ("cognition.flow_expansion_mcf", "cognition.flow_maxflow"):
        attached.set_state(cid, "ATTACHED")
    r = reason({"problem_id": "partial", "compile": {"geometry": {"consequence_class": "read_only"},
                                                     "data": partial}}, registry=attached)
    assert r["state"] == "ABSTAIN" and r["result"] is None and r["capability_deficit"] is None
    assert r["method_or_composition_selected"] is None and not r["intermediate_receipts"]
    why = {m["method"]: m["why"] for m in r["methods_rejected"]}
    assert "answers a relaxation" in why["cognition.flow_maxflow"]
    assert "budget" in why["cognition.flow_maxflow"] and "unit_cost" in why["cognition.flow_maxflow"]
    assert {"method": "cognition.flow_expansion_mcf", "missing_inputs": ["max_increment"]} in r["missing_information"]
    assert any("max_increment" in a for a in r["abstentions"])
    plain = {k: data[k] for k in ("edges", "source", "sink")}          # a max-flow question asks nothing more
    r = reason({"problem_id": "plain", "compile": {"geometry": {"consequence_class": "read_only"}, "data": plain}},
               registry=attached)
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == "cognition.flow_maxflow"


def test_a_one_part_composition_request_that_omits_an_input_asks_for_it(no_index):
    """Review 2026-10-14 (round 2): the capacity-expansion request without max_increment ends ABSTAIN asking for it
    when flat, but in the graph_then_allocate shape ({capacity_network: {...}}) it ended in a CAPABILITY_DEFICIT
    routed to an attach ask or Genesis (mcf attached, the recipe's stages withheld), or in STAGE_ABSTAINED once the
    stages were attached. The recipe's compile stage reads the part and needs max_increment: the composition is
    not a fit for a part that lacks its stage's inputs, and the request asks for what it lacks, whatever is
    attached and whatever the evidence index ranks first."""
    from greg.cognition.genomes import library
    data, _ = library.executables()["flow_expansion_mcf"].instance(3)
    partial = {"capacity_network": {k: v for k, v in data.items() if k != "max_increment"}}
    only_mcf = registry_view()
    only_mcf.set_state("cognition.flow_expansion_mcf", "ATTACHED")
    stages = registry_view()
    for cid in ("cognition.flow_expansion_mcf", "cognition.flow_capacity_plan", "cognition.optimization",
                "cognition.flow_maxflow"):
        stages.set_state(cid, "ATTACHED")
    lifted = json.dumps({"genomes": {}, "routing": {},
                         "recipes": {"graph_then_allocate": {"lift": True, "status": "VPL_LIFT"}}})
    for index in (None, lifted):
        if index:
            no_index.write_text(index)
        for name, registry in (("mcf only", only_mcf), ("stages attached", stages)):
            r = reason({"problem_id": "partial-shape", "compile": {"geometry": {"consequence_class": "read_only"},
                                                                   "data": partial}}, registry=registry)
            where = (name, bool(index))
            assert r["state"] == "ABSTAIN" and r["capability_deficit"] is None and r["result"] is None, where
            assert r["method_or_composition_selected"] is None and not r["intermediate_receipts"], where
            assert {"method": "composition:graph_then_allocate", "part": "capacity_network",
                    "missing_inputs": ["max_increment"]} in r["missing_information"], where
            assert {"method": "cognition.flow_expansion_mcf", "part": "capacity_network",
                    "missing_inputs": ["max_increment"]} in r["missing_information"], where
            why = {m["method"]: m["why"] for m in r["methods_rejected"]}
            assert "max_increment" in why["composition:graph_then_allocate"], where
            assert any("max_increment" in a for a in r["abstentions"]), where
    # a part that carries every input of the compile stage keeps the recipe a fit, and a lifted recipe ranks first
    full = reason({"problem_id": "full-shape", "compile": {"geometry": {"consequence_class": "read_only"},
                                                           "data": {"capacity_network": data}, "execute": False}},
                  registry=stages)
    assert full["method_or_composition_selected"] == "composition:graph_then_allocate"
    assert not any(m["method"] == "composition:graph_then_allocate" for m in full["methods_rejected"])
    # a plain max-flow part asks the max-flow question: answered by max_flow, the recipe is not a fit for it
    plain = {"capacity_network": {k: data[k] for k in ("edges", "source", "sink")}}
    r = reason({"problem_id": "plain-shape", "compile": {"geometry": {"consequence_class": "read_only"},
                                                         "data": plain}}, registry=stages)
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == "cognition.flow_maxflow"
    assert r["payload_part"] == "capacity_network"
    assert "missing_information" not in r
    # it asks nothing of the recipe: with max_flow excluded by the declaration, shaped ends like flat, in a deficit
    for d in (plain, plain["capacity_network"]):
        r = reason({"problem_id": "plain-arith", "compile": {"geometry": {"geometry": "arithmetic",
                                                                          "consequence_class": "read_only"},
                                                             "data": d}}, registry=stages)
        assert r["state"] == "CAPABILITY_DEFICIT" and "missing_information" not in r, sorted(d)


def test_a_one_part_composition_request_reaches_the_single_method_that_answers_its_part(no_index):
    """Review 2026-10-14: a request in the graph_then_allocate shape ({capacity_network: {...}}) never reached
    flow_expansion_mcf; with mcf attached and the recipe's stages withheld it ended in a deficit saying no method
    fit. The part is offered to the methods whose native inputs it carries; a lifted recipe still ranks first."""
    from greg.cognition.genomes import library
    data, truth = library.executables()["flow_expansion_mcf"].instance(3)
    shaped = {"capacity_network": data}
    only_mcf = registry_view()
    only_mcf.set_state("cognition.flow_expansion_mcf", "ATTACHED")
    r = reason({"problem_id": "shape", "compile": {"geometry": {"consequence_class": "read_only"}, "data": shaped}},
               registry=only_mcf)
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == "cognition.flow_expansion_mcf"
    assert r["payload_part"] == "capacity_network" and r["result"]["flow_value"] == truth["optimum"]
    assert r["selected_receipt"]["method"] == "cognition.flow_expansion_mcf"
    rejected = {m["method"]: m["why"] for m in r["methods_rejected"]}
    assert "answers a relaxation" in rejected["cognition.flow_maxflow"]        # the rule holds inside the part
    nothing = reason({"problem_id": "shape", "compile": {"geometry": {"consequence_class": "read_only"},
                                                         "data": shaped}}, registry=registry_view())
    assert nothing["state"] == "CAPABILITY_DEFICIT"
    assert "registered but not attached" in nothing["capability_deficit"]["verification"]["failed"]
    unknown = reason({"problem_id": "odd", "compile": {"geometry": {}, "data": {"mystery_field": 1}}},
                     registry=registry_view())
    assert "matches no catalogued method's native inputs" in unknown["capability_deficit"]["verification"]["failed"]
    no_index.write_text(json.dumps({"genomes": {}, "routing": {},
                                    "recipes": {"graph_then_allocate": {"lift": True, "status": "VPL_LIFT"}}}))
    for cid in ("cognition.flow_capacity_plan", "cognition.optimization", "cognition.flow_maxflow"):
        only_mcf.set_state(cid, "ATTACHED")
    lifted = reason({"problem_id": "shape", "compile": {"geometry": {"consequence_class": "read_only"},
                                                        "data": shaped, "execute": False}}, registry=only_mcf)
    assert lifted["method_or_composition_selected"] == "composition:graph_then_allocate"   # measured lift ranks first


def test_a_flat_request_that_lacks_an_input_no_fitting_method_reads_asks_for_it(no_index):
    """Review 2026-10-14 (round 3): a flat capacity-expansion request without sink, source or edges ended in a
    CAPABILITY_DEFICIT routed to Genesis whose verification said 'no method declares these inputs', although
    flow_expansion_mcf (attached) reads every key it carries; the same request in the {capacity_network} shape
    asked for the missing input. Missing information came only from a fitting relaxation, so when nothing fit a
    near-complete request became a Genesis deficit. A request that carries at least as many of a catalogued
    method's inputs as it lacks, including one no mechanism it fully supplies reads, asks that method's question;
    a key shared with a much larger method does not, and a deficit names every mechanism that reads its inputs."""
    from greg.cognition.genomes import library
    data, _ = library.executables()["flow_expansion_mcf"].instance(3)
    mcf = registry_view()
    mcf.set_state("cognition.flow_expansion_mcf", "ATTACHED")

    def compile_on(registry, d, geometry=None):
        return reason({"problem_id": "lacks", "compile": {"geometry": {"consequence_class": "read_only",
                                                                       **(geometry or {})}, "data": d}},
                      registry=registry)

    expansion = ("cognition.flow_capacity_plan", "cognition.flow_expansion_mcf", "cognition.flow_reinforce_greedy")
    for gone in (("sink",), ("source",), ("edges",), ("sink", "source"), ("edges", "sink", "source")):
        flat = {k: v for k, v in data.items() if k not in gone}
        for shape, d in (("flat", flat), ("shaped", {"capacity_network": flat})):
            r = compile_on(mcf, d)
            where = (shape, gone)
            assert r["state"] == "ABSTAIN" and r["capability_deficit"] is None and r["result"] is None, where
            part = {"part": "capacity_network"} if shape == "shaped" else {}
            for method in expansion:
                assert {"method": method, "missing_inputs": sorted(gone), **part} in r["missing_information"], where
            # max_flow reads a strict subset of what the expansion methods read of the request: not the question
            assert not any(m["method"] == "cognition.flow_maxflow" for m in r["missing_information"]), where
            assert any(gone[0] in a for a in r["abstentions"]), where
    # a fitting max_flow rejected by frozen evidence still reads only part of the request: the budget and prices
    # it carries make it the expansion question, missing max_increment (it ended in a deficit)
    no_index.write_text(json.dumps({"genomes": {"flow_maxflow": {"status": "REJECTED"}}, "recipes": {},
                                    "routing": {}}))
    r = compile_on(mcf, {k: data[k] for k in ("edges", "source", "sink", "budget", "unit_cost")})
    assert r["state"] == "ABSTAIN"
    assert {"method": "cognition.flow_expansion_mcf", "missing_inputs": ["max_increment"]} in r["missing_information"]
    r = compile_on(mcf, {k: data[k] for k in ("edges", "source", "sink")})     # the max-flow question: a deficit
    assert r["state"] == "CAPABILITY_DEFICIT" and "missing_information" not in r
    no_index.unlink()
    # max_flow reads the network the expansion methods read, and the request also carries a budget: they are asked
    r = compile_on(mcf, {k: data[k] for k in ("edges", "source", "budget")})
    assert r["state"] == "ABSTAIN"
    assert {m["method"] for m in r["missing_information"]} == set(expansion)
    # a method producing the same decision from less side information competes: both are asked for what they lack
    r = compile_on(mcf, {"signal": [0.1, 0.9, 1.1], "levels": [0.0, 1.0], "mean_dwell": 5})
    assert r["missing_information"] == [{"method": "cognition.basal_bayes_filter", "missing_inputs": ["noise_sd"]},
                                        {"method": "cognition.basal_hysteresis", "missing_inputs": ["noise_sd"]}]
    # one key shared with larger methods is not their question: a deficit that names every reader and why
    r = compile_on(mcf, {"costs": [[4, 1], [2, 3]], "budget": 5})
    assert r["state"] == "CAPABILITY_DEFICIT" and "missing_information" not in r
    verification = r["capability_deficit"]["verification"]
    readers = {u["method"]: u["why"] for u in verification["unserviceable"]}
    assert set(expansion) | {"cognition.develop_constraint_release"} <= set(readers)
    assert "reads ['budget']" in readers["cognition.flow_expansion_mcf"]
    assert "fewer of its inputs than it lacks" in readers["cognition.flow_expansion_mcf"]
    assert "not the question asked" in verification["failed"]
    # a few keys of a request another mechanism reads far more of are not this method's question: a PID tracking
    # problem declared prediction is not a simulation missing its step probability (simulation reads two of its
    # twelve keys, the PID controllers nine), whatever the declaration says of the controllers
    pid, _ = library.executables()["basal_pid"].instance(0)
    r = compile_on(mcf, pid, {"geometry": "prediction"})
    assert r["state"] == "CAPABILITY_DEFICIT" and "missing_information" not in r
    readers = {u["method"]: u["why"] for u in r["capability_deficit"]["verification"]["unserviceable"]}
    assert "'cognition.basal_pid'" in readers["cognition.simulation"]
    assert "read more of the request" in readers["cognition.simulation"]
    # keys no mechanism requires (optional inputs) decide nothing: a hysteresis request without its levels asks
    # hysteresis for them, beside the Bayesian filter that produces the same decision (its own optional
    # initial_state and threshold, and the filter's dwell prior, kept it from being asked)
    hysteresis, _ = library.executables()["basal_hysteresis"].instance(0)
    r = compile_on(mcf, {k: v for k, v in hysteresis.items() if k != "levels"})
    assert r["state"] == "ABSTAIN"
    assert r["missing_information"] == [{"method": "cognition.basal_bayes_filter", "missing_inputs": ["levels"]},
                                        {"method": "cognition.basal_hysteresis", "missing_inputs": ["levels"]}]
    # nor do keys no mechanism requires, however many
    r = compile_on(mcf, {k: v for k, v in data.items() if k != "sink"} | {"note": "pilot", "owner": "ops",
                                                                           "region": "north", "tier": 2})
    assert {"method": "cognition.flow_expansion_mcf", "missing_inputs": ["sink"]} in r["missing_information"]
    # only a mechanism whose question the request could be reads 'more': two grid keys of a twelve-input repair
    # problem leave a treatment-effect request its question; most of the repair problem's inputs make it that one
    grid = {"width": 4, "height": 3}
    r = compile_on(mcf, {"treated": [1.0, 2.0], **grid})
    assert r["missing_information"] == [{"method": "cognition.causal", "missing_inputs": ["control"]}]
    repair = {**grid, "sources": [[0, 0]], "sinks": [[2, 3]], "removed": [], "blocked": [], "events": [], "steps": 3}
    r = compile_on(mcf, {"treated": [1.0, 2.0], **repair})
    assert r["missing_information"] == [{"method": "cognition.develop_repair", "missing_inputs": ["message_loss",
                                                                                                  "seed"]}]
    # a request-level flag and a key no mechanism requires change nothing
    r = compile_on(mcf, {"treated": [1.0, 2.0], "note": "pilot", "formalization_complete": True})
    assert r["missing_information"] == [{"method": "cognition.causal", "missing_inputs": ["control"]}]
    # a declaration that excludes the reader keeps the deficit, and says so
    r = compile_on(mcf, {k: v for k, v in data.items() if k != "sink"}, {"geometry": "arithmetic"})
    assert r["state"] == "CAPABILITY_DEFICIT" and "missing_information" not in r
    readers = {u["method"]: u["why"] for u in r["capability_deficit"]["verification"]["unserviceable"]}
    assert "does not include arithmetic" in readers["cognition.flow_expansion_mcf"]
    # 'no method reads these inputs' only when none does
    r = compile_on(mcf, {"mystery_field": 1})
    assert r["capability_deficit"]["verification"]["unserviceable"] == \
        "no catalogued method or recipe reads any of these inputs"


def test_every_catalogued_mechanism_a_request_supplies_in_part_is_asked_or_accounted_for(no_index):
    """Review 2026-10-14 (round 3), the rest of the same class: what the request lacks is judged against every
    catalogued mechanism that reads its keys, not only operations. A request carrying one typed part of a
    two-part recipe asks for the other part (it ended in a deficit claiming no method reads its inputs); a
    mechanism the request fully supplies poses the question its keys ask, whatever its frozen status, and so does
    a cortex organ (Fermi reads estimation_model); a mechanism the declaration excludes poses none: variables and
    constraints declared optimization are the optimization question without its objective (they ended in a
    deficit because the excluded feasibility method was counted as posing the question); and a one-part recipe's
    part is judged as a flat request is."""
    from greg.cognition.genomes import library
    registry = registry_view()

    def compile_on(d, geometry=None):
        return reason({"problem_id": "mechanisms", "compile": {"geometry": {"consequence_class": "read_only",
                                                                            **(geometry or {})}, "data": d,
                                                               "execute": False}}, registry=registry)

    r = compile_on({"formal_template": {"variables": {"x": [0, 4]}}})
    assert r["state"] == "ABSTAIN" and r["capability_deficit"] is None
    assert r["missing_information"] == [
        {"method": "composition:estimate_then_optimize", "missing_inputs": ["estimation_model"]},
        {"method": "composition:identify_then_optimize", "missing_inputs": ["causal_studies"]}]
    r = compile_on({"newsvendor": {"products": [], "capacity": 3}})
    assert r["missing_information"] == [{"method": "composition:forecast_then_allocate",
                                         "missing_inputs": ["demand_histories"]}]
    # a declaration that excludes the recipe's stages keeps the deficit, and names the recipe as a reader
    r = compile_on({"newsvendor": {"products": [], "capacity": 3}}, {"geometry": "causal"})
    assert r["state"] == "CAPABILITY_DEFICIT" and "missing_information" not in r
    readers = {u["method"]: u["why"] for u in r["capability_deficit"]["verification"]["unserviceable"]}
    assert "does not include causal" in readers["composition:forecast_then_allocate"]
    # the declaration decides which fully supplied mechanism poses the question
    model = {"variables": {"x": [0, 4]}, "constraints": [{"expr": "x >= 1"}]}
    r = compile_on(model, {"geometry": "optimization"})
    assert r["state"] == "ABSTAIN"
    assert {"method": "cognition.optimization", "missing_inputs": ["objective"]} in r["missing_information"]
    assert any("check the declaration before trusting a deficit or a request for missing inputs" in d
               for d in r["dissent"])
    r = compile_on(model, {"geometry": "constraint_feasibility"})
    assert r["method_or_composition_selected"] == "cognition.formal" and "missing_information" not in r
    # an organ the request fully supplies poses the estimation question even when frozen evidence rejects it
    no_index.write_text(json.dumps({"genomes": {}, "recipes": {}, "routing": {},
                                    "organs": {"cognition.cortex.estimation.fermi": {"status": "REJECTED"}}}))
    estimate = {"estimation_model": {"factors": {}}}
    r = compile_on(estimate)
    assert r["state"] == "CAPABILITY_DEFICIT" and "missing_information" not in r
    readers = {u["method"]: u["why"] for u in r["capability_deficit"]["verification"]["unserviceable"]}
    assert "read by a mechanism the request fully supplies" in readers["composition:estimate_then_optimize"]
    assert "frozen status REJECTED" in readers["cognition.cortex.estimation.fermi"]
    r = compile_on(estimate, {"geometry": "optimization"})       # declared optimization: the composite question
    assert r["missing_information"] == [{"method": "composition:estimate_then_optimize",
                                         "missing_inputs": ["formal_template"]}]
    no_index.unlink()
    # in a one-part recipe's shape the part's question is decided as a flat request's: a causal graph sent as a
    # capacity network is the causal question (its method reads six of its keys, the recipe's compile stage one),
    # so declared optimization it ends in the deficit the flat graph ends in, and without its outcome it asks the
    # causal method for the outcome, not the recipe for five capacity inputs (both of which it did)
    dag, _ = library.executables()["causal_backdoor"].instance(0)
    for d in (dag, {"capacity_network": dag}):
        r = compile_on(d, {"geometry": "optimization"})
        assert r["state"] == "CAPABILITY_DEFICIT" and "missing_information" not in r, sorted(d)
    why = {m["method"]: m["why"] for m in r["methods_rejected"]}
    assert "'cognition.causal_backdoor'" in why["composition:graph_then_allocate"]
    assert "read more of the part" in why["composition:graph_then_allocate"]
    r = compile_on({"capacity_network": dag})                   # undeclared: the causal question, never the recipe's
    assert "missing_information" not in r
    no_outcome = {k: v for k, v in dag.items() if k != "outcome"}
    for d, part in ((no_outcome, {}), ({"capacity_network": no_outcome}, {"part": "capacity_network"})):
        r = compile_on(d)
        assert r["missing_information"] == [{"method": "cognition.causal_backdoor", "missing_inputs": ["outcome"],
                                             **part}], sorted(d)


def test_a_composition_is_checked_against_the_declared_geometry_like_every_other_method(no_index):
    """Review 2026-10-14 (round 3): composition rows were never checked against the declared geometry. A
    capacity-expansion request declared 'arithmetic' ended in a deficit when flat (every flow method is
    optimization), but in the {capacity_network} shape it was ANSWERED by graph_then_allocate, whose stages are
    all optimization, and without max_increment it asked for an input of the composition the declaration
    excludes. A recipe carries its stages' native classes and is rejected when none includes the declaration."""
    from greg.cognition.composition import RECIPES
    from greg.cognition.genomes import library
    data, _ = library.executables()["flow_expansion_mcf"].instance(3)
    partial = {k: v for k, v in data.items() if k != "max_increment"}
    registry = registry_view()
    for cid in list(R.EVAL_ATTACH) + ["cognition.flow_expansion_mcf"]:
        registry.set_state(cid, "ATTACHED")

    def compile_on(d, geometry):
        return reason({"problem_id": "declared", "compile": {"geometry": {"consequence_class": "read_only",
                                                                          **geometry}, "data": d}},
                      registry=registry)

    for label, d in (("full", data), ("no max_increment", partial)):
        for shape, payload in (("flat", d), ("shaped", {"capacity_network": d})):
            r = compile_on(payload, {"geometry": "arithmetic"})
            where = (label, shape)
            assert r["state"] == "CAPABILITY_DEFICIT" and r["result"] is None, where
            assert "missing_information" not in r and not r["intermediate_receipts"], where
            if shape == "shaped":
                why = {m["method"]: m["why"] for m in r["methods_rejected"]}
                assert "does not include arithmetic" in why["composition:graph_then_allocate"], where
    # a declaration native to its stages keeps the recipe a fit (and a lifted recipe ranks first)
    no_index.write_text(json.dumps({"genomes": {}, "routing": {},
                                    "recipes": {"graph_then_allocate": {"lift": True, "status": "VPL_LIFT"}}}))
    r = compile_on({"capacity_network": data}, {"geometry": "optimization"})
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == "composition:graph_then_allocate"
    # every recipe declares its stages' classes; the declaration is checked against them
    assert all(compiler.recipe_classes(name) for name in RECIPES)
    assert compiler.recipe_classes("graph_then_allocate") == ["optimization"]
    assert compiler.recipe_classes("estimate_then_optimize") == ["estimate", "optimization"]
    for recipe, payload, native, foreign in (
            ("forecast_then_staff", {"arrival_histories": {}, "staffing": {}}, "prediction", "optimization"),
            ("estimate_then_optimize", {"estimation_model": {}, "formal_template": {}}, "estimate", "causal")):
        for declared, rejected in ((native, False), (foreign, True)):
            rows = compiler.candidates(payload, compiler.CompetencyGeometry.parse({"geometry": declared}),
                                       compiler.evidence_index())
            row = next(r for r in rows if r["method"] == f"composition:{recipe}")
            assert bool(row["rejected"]) is rejected, (recipe, declared, row["rejected"])


def test_a_cortex_organ_reading_one_part_of_a_genome_request_does_not_answer_it():
    """Review 2026-10-14 (round 3), the same class in the organ path: organ rows were added after the relaxation
    rule ran, so the semantic organ (routed on ``sources``) served a develop_repair request whenever develop_repair
    was withheld, and a develop_repair request lacking one input was answered by it instead of asking for the
    input; in the {capacity_network} shape the same requests ended in the attach route and asked. An organ that
    reads a strict subset of a catalogued method's inputs, while the request carries the rest, is a relaxation."""
    from greg.cognition.genomes import library
    data, _ = library.executables()["develop_repair"].instance(0)
    registry = registry_view()                                  # develop_repair registered, not attached

    def compile_on(d, geometry=None):
        return reason({"problem_id": "organ", "compile": {"geometry": {"consequence_class": "read_only",
                                                                       **(geometry or {})}, "data": d,
                                                          "execute": False}}, registry=registry)

    partial = {k: v for k, v in data.items() if k != "blocked"}
    for shape, full, lacking in (("flat", data, partial),
                                 ("shaped", {"capacity_network": data}, {"capacity_network": partial})):
        r = compile_on(full)
        assert r["state"] == "CAPABILITY_DEFICIT" and r["method_or_composition_selected"] is None, shape
        assert r["withheld_best_fit"]["method"] == "cognition.develop_repair", shape
        assert r["capability_deficit"]["route"].startswith("founder attach of the prepared ask"), shape
        r = compile_on(lacking)
        assert r["state"] == "ABSTAIN", shape
        assert [(m["method"], m["missing_inputs"]) for m in r["missing_information"]] == \
            [("cognition.develop_repair", ["blocked"])], shape
    why = {m["method"]: m["why"] for m in compile_on(data)["methods_rejected"]}
    assert "answers a relaxation" in why["cognition.cortex.semantic"]
    assert "['cognition.develop_repair']" in why["cognition.cortex.semantic"]
    # a declaration that excludes the fuller method leaves the organ its question; an organ alone is untouched
    assert compile_on(data, {"geometry": "semantic"})["method_or_composition_selected"] == "cognition.cortex.semantic"
    assert compile_on({"sources": data["sources"]})["method_or_composition_selected"] == "cognition.cortex.semantic"


def _f7_index(no_index):
    """Admission v3's verdicts for the F7 shape: the recipe's VPL lift, and flow_expansion_mcf DEFAULT against its
    twin at the genome's current version."""
    from greg.cognition.genomes import library
    no_index.write_text(json.dumps({
        "routing": {}, "recipes": {"graph_then_allocate": {"lift": True, "status": "VPL_LIFT"}},
        "genomes": {"flow_expansion_mcf": {"status": "DEFAULT_FOR_GEOMETRY",
                                           "version": library.executables()["flow_expansion_mcf"].genome.version,
                                           "evidence": "docs/evidence/greg-genome-admission/x/results.json"}}}))


def _everything_attached():
    registry = registry_view()
    for cid in list(registry.manifests):
        registry.set_state(cid, "ATTACHED")
    return registry


def _f7_run(registry):
    def run(request, **extra):
        return reason({"problem_id": "f7-shape", "compile": {"geometry": {}, "data": request, **extra}},
                      registry=registry)
    return run


def test_a_recipe_is_demoted_only_for_a_matched_genome_that_fits_this_request(no_index):
    """Independent review 2026-10-15 (F2): the single-genome match was decided without asking whether the genome fits
    this request. A capacity network sent beside any other key fits no single genome (it is not a one-part request),
    yet the recipe was demoted after every other fit and another question was answered ("expression": "2 + 2" was
    ANSWERED 4; "sources" went to the semantic organ, which abstained)."""
    from greg.cognition.genomes import library
    _f7_index(no_index)
    data, truth = library.executables()["flow_expansion_mcf"].instance(3)            # development seed
    run = _f7_run(_everything_attached())
    for extra in ({"expression": "2 + 2"}, {"sources": [{"id": "s1", "text": "capacity report"}]}):
        r = run({"capacity_network": data, **extra}, execute=False)
        assert r["method_or_composition_selected"] == "composition:graph_then_allocate", extra
        assert "composition:graph_then_allocate" not in {d["method"] for d in r["methods_demoted"]}
    answered = run({"capacity_network": data, "expression": "2 + 2"})
    assert answered["state"] == "ANSWERED" and answered["result"]["flow_value"] == truth["optimum"]
    plain = run({"capacity_network": data}, execute=False)          # the one-part request: the genome answers its part
    assert plain["method_or_composition_selected"] == "cognition.flow_expansion_mcf"
    assert any(d["method"] == "composition:graph_then_allocate" and "matched this recipe's twin" in d["why"]
               for d in plain["methods_demoted"])


def test_a_recipe_the_stage_rule_rejects_is_not_listed_as_demoted(no_index):
    """Independent review 2026-10-15 (F5): the match was decided before the stage rule, so a part that is no capacity
    network listed the recipe both as rejected (its compile stage lacks the inputs) and as demoted by the match."""
    from greg.cognition.genomes import library
    _f7_index(no_index)
    other, _ = library.executables()["assignment_lsa"].instance(2)                   # development seed; no network
    r = _f7_run(_everything_attached())({"capacity_network": other}, execute=False)
    assert "composition:graph_then_allocate" in {d["method"] for d in r["methods_rejected"]}
    assert "composition:graph_then_allocate" not in {d["method"] for d in r["methods_demoted"]}


@pytest.mark.parametrize("lift", [True, False])
def test_a_recipe_serving_while_its_matched_genome_is_withheld_says_so(no_index, lift):
    """Independent review 2026-10-15 (F4): every demoted fit that served was labelled only_fit_despite_no_lift. A
    recipe serving while the genome that matched it is withheld is not the only fit, whether its own lift verdict is
    verified or not (the fix verification's label-order mutation survived the lift case alone)."""
    from greg.cognition.genomes import library
    _f7_index(no_index)
    if not lift:
        index = json.loads(no_index.read_text())
        index["recipes"]["graph_then_allocate"] = {"lift": False, "status": "NO_LIFT"}
        no_index.write_text(json.dumps(index))
    data, _ = library.executables()["flow_expansion_mcf"].instance(3)                # development seed
    stages = registry_view()
    for cid in ("cognition.flow_capacity_plan", "cognition.optimization", "cognition.flow_maxflow"):
        stages.set_state(cid, "ATTACHED")
    r = _f7_run(stages)({"capacity_network": data}, execute=False)
    assert r["method_or_composition_selected"] == "composition:graph_then_allocate"
    assert r["withheld_best_fit"]["method"] == "cognition.flow_expansion_mcf"
    assert r["selection_level"] == "serves_while_best_fit_withheld"


def test_a_fit_demoted_by_its_settled_outcomes_is_labelled_so(registry, no_index, monkeypatch):
    """Independent review 2026-10-15 (F4): a method demoted by its settled outcomes on this body, serving because
    nothing else fits, was labelled only_fit_despite_no_lift although no lift verdict applies to it."""
    monkeypatch.setattr(compiler, "_settled_counts", lambda journal: {"cognition.flow_maxflow": (12, 2)})
    r = compile_(registry, {"geometry": "optimization"}, maxflow_instance(3)[0], execute=False)
    assert r["method_or_composition_selected"] == "cognition.flow_maxflow"          # demoted, and the only fit
    assert any("2 of 12 correct" in d["why"] for d in r["methods_demoted"])
    assert r["selection_level"] == "demoted_by_settled_outcomes"


def _f7_index_also(no_index, recipe=None, **statuses):
    """``_f7_index`` with the recipe's lift verdict replaced by ``recipe`` and the shape's other genomes given these
    admission statuses at their current versions."""
    from greg.cognition.genomes import library
    _f7_index(no_index)
    index = json.loads(no_index.read_text())
    for family, status in statuses.items():
        index["genomes"][family] = {"status": status, "version": library.executables()[family].genome.version,
                                    "evidence": f"docs/evidence/greg-genome-admission/x/results.json#{family}"}
    if recipe:
        index["recipes"]["graph_then_allocate"] = recipe
    no_index.write_text(json.dumps(index))


@pytest.mark.parametrize("genome", ["attached", "withheld"])
def test_a_recipe_whose_matched_genome_its_settled_outcomes_demote_does_not_claim_to_rank_after_it(no_index,
                                                                                                    monkeypatch,
                                                                                                    genome):
    """Fix verification 2026-10-15: when the genome that matched a recipe's twin is itself demoted by its settled
    outcomes on this body, both are demoted fits and the recipe may rank first (best_of_demoted_fits, a label no
    test reached), yet the recipe's demotion reason, repeated in dissent, said the recipe ranks after the genome.
    Attached or withheld, the demoted genome ranks after the recipe, so the recipe serves as the best demoted fit."""
    from greg.cognition.genomes import library
    _f7_index_also(no_index, flow_reinforce_greedy="SUPERSEDED")      # admission v3's verdict on the other genome
    data, _ = library.executables()["flow_expansion_mcf"].instance(3)                # development seed
    if genome == "attached":
        registry = _everything_attached()
    else:
        registry = registry_view()
        for cid in ("cognition.flow_capacity_plan", "cognition.optimization", "cognition.flow_maxflow"):
            registry.set_state(cid, "ATTACHED")
    run = _f7_run(registry)
    control = run({"capacity_network": data}, execute=False)          # no settled outcomes: the genome ranks first
    assert (control["method_or_composition_selected"] == "cognition.flow_expansion_mcf" if genome == "attached"
            else control["withheld_best_fit"]["method"] == "cognition.flow_expansion_mcf")
    assert {d["method"]: d["why"] for d in control["methods_demoted"]}["composition:graph_then_allocate"].endswith(
        "the single method is canonical for this geometry and the recipe ranks after it")
    monkeypatch.setattr(compiler, "_settled_counts", lambda journal: {"cognition.flow_expansion_mcf": (12, 2)})
    r = run({"capacity_network": data}, execute=False)
    assert r["method_or_composition_selected"] == "composition:graph_then_allocate" and "withheld_best_fit" not in r
    assert r["selection_level"] == "best_of_demoted_fits"
    demoted = {d["method"]: d["why"] for d in r["methods_demoted"]}
    assert "2 of 12 correct" in demoted["cognition.flow_expansion_mcf"]
    why = demoted["composition:graph_then_allocate"]
    assert "matched this recipe's twin" in why and "ranks after" not in why
    assert why.endswith("the single method is canonical for this geometry, but settled outcomes on this body demote "
                        "cognition.flow_expansion_mcf too, so the recipe is ordered with it among the demoted fits by "
                        "the other rank keys") and why in r["dissent"]


@pytest.mark.parametrize("case", ["after a no-lift verdict", "beside a matched genome ahead", "both demoted"])
def test_the_matched_reason_is_qualified_inside_the_recipes_whole_demotion_reason(no_index, monkeypatch, case):
    """Fix verification 2026-10-15: the qualified reason replaces the matched one inside the recipe's composed
    demotion reason. A NO_LIFT verdict before it is kept; a second matched genome that is not demoted still ranks
    before the recipe, and the reason says so; two demoted matched genomes are named as such (the
    flow_reinforce_greedy DEFAULT verdict is hypothetical: admission v3 found it SUPERSEDED)."""
    from greg.cognition.genomes import library
    if case == "after a no-lift verdict":
        _f7_index_also(no_index, recipe={"lift": False, "status": "NO_LIFT"}, flow_reinforce_greedy="SUPERSEDED")
    else:
        _f7_index_also(no_index, flow_reinforce_greedy="DEFAULT_FOR_GEOMETRY")
    settled = {"cognition.flow_expansion_mcf": (12, 2)}
    if case == "both demoted":
        settled["cognition.flow_reinforce_greedy"] = (12, 2)
    monkeypatch.setattr(compiler, "_settled_counts", lambda journal: settled)
    data, _ = library.executables()["flow_expansion_mcf"].instance(3)                # development seed
    r = _f7_run(_everything_attached())({"capacity_network": data}, execute=False)
    why = {d["method"]: d["why"] for d in r["methods_demoted"]}["composition:graph_then_allocate"]
    assert why.count("matched this recipe's twin") == 1 and "ranks after it" not in why
    if case == "after a no-lift verdict":                    # the lift verdict ranks the recipe after the genome
        assert why.startswith("frozen VPL verdict (evidence index): no lift over its best constituent; ranked after "
                              "every other fit; admitted single genome cognition.flow_expansion_mcf matched")
        assert why.endswith(", but settled outcomes on this body demote cognition.flow_expansion_mcf too, so the "
                            "recipe is ordered with it among the demoted fits by the other rank keys")
        assert r["method_or_composition_selected"] == "cognition.flow_expansion_mcf"
        assert r["selection_level"] == "demoted_by_settled_outcomes"
    elif case == "beside a matched genome ahead":
        assert why.endswith("the single method is canonical for this geometry and the recipe ranks after "
                            "cognition.flow_reinforce_greedy, but settled outcomes on this body demote "
                            "cognition.flow_expansion_mcf too, so the recipe is ordered with it among the demoted fits "
                            "by the other rank keys")
        assert r["method_or_composition_selected"] == "cognition.flow_reinforce_greedy"
        assert r["selection_level"] == "admission_status"
    else:
        assert why.endswith("the single method is canonical for this geometry, but settled outcomes on this body "
                            "demote cognition.flow_expansion_mcf, cognition.flow_reinforce_greedy too, so the recipe is "
                            "ordered with them among the demoted fits by the other rank keys")
        assert r["method_or_composition_selected"] == "composition:graph_then_allocate"
        assert r["selection_level"] == "best_of_demoted_fits" and why in r["dissent"]


@pytest.mark.parametrize("promotion", ["registered", "not registered"])
def test_no_acquisition_candidate_is_named_for_a_geometry_the_declaration_excludes(registry, no_index, monkeypatch,
                                                                                   promotion):
    """Independent review 2026-10-15 (F6): a basal_pid request declared deductive named the simulation-optimised PI
    tuner (physical) for Genesis to acquire, although the declaration excludes it: promotion keeps the epistemic
    class. The same held where the superseding mechanism is not a registered genome."""
    from greg.cognition import catalog
    from greg.cognition.genomes import library
    item = library.executables()["basal_pid"]
    no_index.write_text(json.dumps({"genomes": {"basal_pid": {
        "status": "SUPERSEDED", "version": item.genome.version, "evidence": "v2/results.json#genomes.basal_pid"}},
        "recipes": {}, "routing": {}}))
    if promotion == "not registered":
        monkeypatch.delitem(catalog.FAMILIES, library.promotions()["basal_pid"])
    data = item.instance(2)[0]                                                        # development seed
    r = compile_(registry, {"geometry": "deductive"}, data, execute=False)
    assert r["state"] == "CAPABILITY_DEFICIT" and "acquisition_candidates" not in r
    if promotion == "not registered":                       # the native declaration still names the mechanism
        native = compile_(registry, {"geometry": item.genome.epistemic_class}, data, execute=False)
        assert "cognition.basal_pid" in [c["supersedes"] for c in native["acquisition_candidates"]]


def test_an_admitted_single_genome_that_matched_a_recipes_twin_outranks_the_recipe(no_index):
    """Review of #179 (M10, L11) and admission v3: flow_expansion_mcf was admitted DEFAULT against the
    graph_then_allocate twin (equal quality on 30 of 30 at about a seventh of the latency). The recipe's VPL_LIFT
    was measured over a repertoire without it, yet a request in the recipe's own shape still ranked the recipe
    first. The matched recipe is demoted, not deleted: it serves while the genome is withheld (with one prepared
    attach ask), and a stale or lower verdict matches nothing."""
    from greg.cognition.genomes import library
    item = library.executables()["flow_expansion_mcf"]
    data, truth = item.instance(3)                                                   # development seed
    shaped = {"capacity_network": data}

    def index(status="DEFAULT_FOR_GEOMETRY", version=item.genome.version):
        no_index.write_text(json.dumps({
            "routing": {}, "recipes": {"graph_then_allocate": {"lift": True, "status": "VPL_LIFT"}},
            "genomes": {"flow_expansion_mcf": {"status": status, "version": version,
                                               "evidence": "docs/evidence/greg-genome-admission/x/results.json"}}}))

    stages = registry_view()
    for cid in ("cognition.flow_capacity_plan", "cognition.optimization", "cognition.flow_maxflow"):
        stages.set_state(cid, "ATTACHED")
    both = registry_view()
    for cid in ("cognition.flow_capacity_plan", "cognition.optimization", "cognition.flow_maxflow",
                "cognition.flow_expansion_mcf"):
        both.set_state(cid, "ATTACHED")

    def run(registry, **extra):
        return reason({"problem_id": "f7-shape", "compile": {"geometry": {"consequence_class": "read_only"},
                                                             "data": shaped, **extra}}, registry=registry)
    index()
    r = run(both)
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == "cognition.flow_expansion_mcf"
    assert r["result"]["flow_value"] == truth["optimum"]
    demoted = {d["method"]: d["why"] for d in r["methods_demoted"]}
    assert "matched this recipe's twin" in demoted["composition:graph_then_allocate"]
    # an operator preference for the recipe never outranks the genome that matched it (it did before the demotion)
    rows = [row for row in compiler.candidates(shaped, compiler.CompetencyGeometry.parse({}), compiler.evidence_index())
            if not row["rejected"]]
    ranked = sorted(rows, key=lambda row: compiler._rank(row, ["graph_then_allocate"], {}))
    assert ranked[0]["method"] == "cognition.flow_expansion_mcf"
    served = run(stages, execute=False)                       # the genome withheld: the recipe still serves
    assert served["method_or_composition_selected"] == "composition:graph_then_allocate"
    assert served["withheld_best_fit"]["method"] == "cognition.flow_expansion_mcf"
    for status, version in (("NICHE_CAPABILITY", item.genome.version), ("DEFAULT_FOR_GEOMETRY", "0.0.0-old")):
        index(status, version)                                # a lower or stale verdict matches nothing
        assert run(both, execute=False)["method_or_composition_selected"] == "composition:graph_then_allocate"


def test_an_optimal_claim_must_meet_its_own_proven_bound_and_a_composition_carries_its_certificate(registry, no_index):
    """Review of #179 (M6): the optimisation verifier checked feasibility only. A feasible but suboptimal plan
    written into the proof with the solver status OPTIMAL verified, although its own proof bound (58) exceeded its
    objective (55), and the composition's answer dropped the solver status. An OPTIMAL claim must now meet its
    proven bound and the proof must be the output's; the composition reports how strong its certificate is."""
    import copy
    from greg.cognition.catalog import FAMILIES
    from greg.cognition.solvers import SOLVERS
    from greg.cognition.verification import verify
    data = {"variables": {"x": [0, 5], "y": [0, 5]},
            "constraints": [{"coefficients": {"x": 1, "y": 1}, "op": "<=", "rhs": 4}],
            "objective": {"coefficients": {"x": 1, "y": 1}, "sense": "max"}}
    honest = SOLVERS["optimization"](data, {"latency_limit": 10})
    proof_class = FAMILIES["optimization"][3]
    assert honest["output"]["solver_status"] == "OPTIMAL" and all(verify("optimization", data, honest, proof_class)
                                                                   ["checks"].values())
    forged = copy.deepcopy(honest)
    forged["output"].update(solution={"x": 1, "y": 2}, objective_value=3.0)       # feasible, one short of optimum
    forged["proof"]["solution"] = {"x": 1, "y": 2}
    checks = verify("optimization", data, forged, proof_class)["checks"]
    assert checks["constraint_substitution"] and checks["objective_substitution"]  # feasibility alone passes
    assert checks["optimal_objective_meets_its_bound"] is False
    mismatched = copy.deepcopy(honest)
    mismatched["output"].update(solution={"x": 1, "y": 2}, objective_value=3.0)   # the proof is another solution's
    assert verify("optimization", data, mismatched, proof_class)["checks"]["proof_matches_output"] is False
    no_index.write_text(json.dumps({"genomes": {"flow_reinforce_greedy": {"status": "SUPERSEDED"}}, "routing": {},
                                    "recipes": {"graph_then_allocate": {"lift": True, "status": "VPL_LIFT"}}}))
    r = compile_(registry, {"geometry": "optimization"}, R.f3(3)["payload"])
    assert r["method_or_composition_selected"] == "composition:graph_then_allocate"
    assert r["result"]["solver_status"] == "OPTIMAL" and r["result"]["optimality"] == "proven"
    assert r["result"]["optimality_gap"] == 0
