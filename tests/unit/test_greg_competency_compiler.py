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
    alone = compile_(registry, {"geometry": "optimization"}, R.f3(3)["payload"], execute=False)
    assert alone["method_or_composition_selected"] == "composition:graph_then_allocate"   # the only fit stays


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


def test_a_superseded_fit_names_the_deployable_mechanism_that_superseded_it(registry, no_index):
    """Admission v2: basal_pid was superseded 0-30 by the simulation-optimised PI. A request only it fits is a
    capability deficit, and the receipt names that mechanism for Genesis instead of leaving the deficit blank."""
    from greg.cognition.genomes import library
    item = library.executables()["basal_pid"]
    no_index.write_text(json.dumps({"genomes": {"basal_pid": {
        "status": "SUPERSEDED", "version": item.genome.version, "evidence": "v2/results.json#genomes.basal_pid"}},
        "recipes": {}, "routing": {}}))
    r = compile_(registry, {"geometry": item.genome.epistemic_class}, item.instance(0)[0], execute=False)
    assert r["state"] == "CAPABILITY_DEFICIT"
    [candidate] = [c for c in r["acquisition_candidates"] if c["supersedes"] == "cognition.basal_pid"]
    assert candidate["mechanism"] == item.genome.competitor and candidate["authority"].startswith("none")
    assert candidate["evidence"] == "v2/results.json#genomes.basal_pid"


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


def test_an_executed_composition_keeps_each_stages_counterargument_as_dissent(registry):
    """Audit 2026-10-14 (section 12): the composition branch dropped every stage's strongest counterargument."""
    r = compile_(registry, {"geometry": "optimization"}, R.f3(3)["payload"])
    assert r["method_or_composition_selected"] == "composition:graph_then_allocate"
    stages = [d for d in r["dissent"] if d.startswith("stage ")]
    assert len(stages) == len(r["intermediate_receipts"]) >= 2
