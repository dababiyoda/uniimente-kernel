"""Lawful Leverage Foundry (directive 2026-10-07, sections 17-20): generation upstream of the existing ranker.

Every test attacks a claim the module makes: hard constraints precede optimisation, harm stays a vector,
control points are never assumed to beat direct labour, the output is accepted unchanged by the existing
institutional-leverage ranker and ask contract, and nothing creates authority.
"""
from copy import deepcopy
from dataclasses import replace

import pytest

from egregore import SignalEnvelope, propose_institutional_leverage
from foundry import lawful_leverage as L
from greg import asks

H = "sha256:" + "b" * 64


def node(i, gap=0.0, kind="process"):
    return dict(id=i, kind=kind, label=i, gap=gap, evidence_refs=[H])


def link(i, s, t, strength=0.9, confidence=0.9):
    return dict(id=i, source=s, target=t, mechanism="coordination", strength=strength, confidence=confidence,
                evidence_refs=[H])


def consent(mechanism, *parties):
    return dict(mechanism=mechanism, covers=list(parties), evidence_refs=[H])


def problem(**changes):
    p = dict(
        problem_id="claims-1", objective="cut time-to-settlement for verified repair claims",
        as_of="2026-10-08T12:00:00Z", outcome_node="settled",
        institutional_map=dict(
            nodes=[node("proof_gap", 0.2), node("eligibility_check", 0.8), node("payer_rules", 0.1, "rule"),
                   node("handoff", 0.3), node("settled", 0.0, "outcome"), node("supplier", 0.1, "resource")],
            links=[link("proof-elig", "proof_gap", "eligibility_check", 0.9, 0.8),
                   link("rules-elig", "payer_rules", "eligibility_check", 0.7, 0.6),
                   link("elig-handoff", "eligibility_check", "handoff", 0.9, 0.95),
                   link("handoff-settled", "handoff", "settled", 0.9, 0.95),
                   link("supplier-handoff", "supplier", "handoff", 0.4, 0.7)],
            interventions=[]),
        surfaces=[
            dict(surface="proof", node="proof_gap", state="receipts are PDFs re-checked by hand", evidence_refs=[H],
                 third_parties=["payers"], consent=consent("payer opt-in pilot agreement", "payers")),
            dict(surface="eligibility", node="eligibility_check", state="each claim checked case by case",
                 evidence_refs=[H], third_parties=["claimants"],
                 consent=consent("published standard with an appeal path", "claimants")),
            dict(surface="workflow", node="eligibility_check", state="no checklist", evidence_refs=[H]),
            dict(surface="capability", node="eligibility_check", state="manual data entry", evidence_refs=[H]),
            dict(surface="settlement", node="handoff", state="net-60 invoices", evidence_refs=[H],
                 third_parties=["payers"]),
            dict(surface="information", node="payer_rules", state="rule changes found late", evidence_refs=[H]),
            dict(surface="dependency", node="supplier", state="one parts supplier", evidence_refs=[H]),
        ],
        direct_labor=dict(description="contract reviewer clears the eligibility queue each week", effect=0.35,
                          confidence=0.8, cost_usd_per_cycle=600, effort_hours_per_cycle=2,
                          consequence_class="financial", evidence_refs=[H]),
        evidence={"proof.verifiable_receipts": dict(successes=7, trials=10, refs=[H])},
        constraints=dict(budget_usd=8000, founder_attention_hours=10, held_authority=["read_only", "internal_write"],
                         value_per_unit_gap_usd=2000),
        samples=1500, seed=7)
    p.update(changes)
    return p


def favourable():
    """Strong evidence on a near-certain upstream link, weak direct labour: a control point should win."""
    p = problem()
    p["institutional_map"]["links"][0] = link("proof-elig", "proof_gap", "eligibility_check", 0.95, 0.98)
    p["evidence"] = {"proof.verifiable_receipts": dict(successes=17, trials=20, refs=[H])}
    p["direct_labor"]["effect"] = 0.15
    return p


def rows(report):
    return {r["candidate_id"]: r for r in report["candidates"]}


def test_library_is_lawful_complete_and_inspectable():
    assert {m.surface for m in L.LIBRARY} == set(L.SURFACES) and len(L.SURFACES) == 16
    for m in L.LIBRARY:
        assert not m.flags and m.falsifier and m.rollback and m.counterargument
        assert set(m.assets) <= set(L.ASSETS) and m.assets
        assert m.consequence_class in L.CONSEQUENCE and m.reversibility in L.REVERSIBILITY
        assert set(dict(m.harm)) <= set(L.HARM)
    card = L.mechanism_card()
    assert len(card) == len(L.LIBRARY) and all(isinstance(c["harm"], dict) for c in card)


def test_prohibited_mechanisms_are_rejected_whatever_their_upside():
    p = L.validate(problem())
    base = L.BY_ID["proof.verifiable_receipts"]
    reach = {"proof_gap": (0.9, ("proof-elig",))}
    for flag in L.PROHIBITED:
        bad = replace(base, flags=(flag,), effect_prior=0.99)
        reasons = L.eligibility(bad, p["surfaces"][0], p, reach)
        assert f"REJECTED_PROHIBITED_MECHANISM:{flag}" in reasons
    # an unreviewed flag is not silently allowed either
    assert "REJECTED_UNREVIEWED_FLAG:novel" in L.eligibility(replace(base, flags=("novel",)), p["surfaces"][0], p,
                                                             reach)


def test_consent_harm_vector_consequence_and_path_are_gates_before_estimation():
    p = problem()
    p["constraints"]["harm_ceiling"] = {"participant_burden": 0.0}
    p["constraints"]["prohibited_consequence_classes"] = ["financial"]
    r = rows(L.compile(p))
    # consent: payers are affected by escrow with no consent path; the consented variant is not rejected for it
    assert "REJECTED_NO_CONSENT_PATH" in r["settlement.milestone_escrow"]["reasons"]
    assert "settlement.milestone_escrow:consented" not in r      # consent is never self-asserted by a variant
    # harm stays a vector: the named dimension is reported, the others are not collapsed into it
    assert "REJECTED_HARM:participant_burden" in r["eligibility.published_standard"]["reasons"]
    assert r["eligibility.published_standard"]["harm_vector"]["third_party"] == pytest.approx(0.05)
    # consequence class, including a deferred one
    assert "REJECTED_CONSEQUENCE_CLASS:financial" in r["direct_labor"]["reasons"]
    # no evidenced path to the bottleneck (the supplier sits downstream of it)
    assert "INELIGIBLE_NO_EVIDENCED_PATH_TO_BOTTLENECK" in r["dependency.second_source"]["reasons"]
    for row in r.values():
        if row["reasons"]:
            assert row["eligibility"] == "REJECTED" and "estimate" not in row and not row["pareto_frontier"]


def test_control_points_are_not_assumed_to_beat_direct_labour():
    p = problem()
    p["constraints"].pop("value_per_unit_gap_usd")
    report = L.compile(p)
    assert report["selected"] == "direct_labor"
    assert report["selection_rule"] == "no control point demonstrated dominance over repeated direct labour"
    verdicts = {r["vs_direct_labor"]["verdict"] for r in report["candidates"]
                if r.get("vs_direct_labor") and r["eligibility"] == "ELIGIBLE"}
    assert "DOMINATES" not in verdicts
    # the alternatives are value trade-offs for the founder, not silently discarded
    assert report["value_tradeoffs_for_founder"]


def dominating():
    """Strong evidence and a declared hourly rate: total spend makes capital and effort commensurable."""
    p = favourable()
    p["constraints"].pop("value_per_unit_gap_usd")
    p["constraints"]["value_per_effort_hour_usd"] = 50
    return p


def test_a_control_point_wins_only_where_joint_samples_show_dominance():
    report = L.compile(dominating())
    chosen = rows(report)[report["selected"]]
    assert chosen["kind"] != "direct_labor" and chosen["vs_direct_labor"]["verdict"] == "DOMINATES"
    assert chosen["vs_direct_labor"]["p_better_informative"] >= L.PROBABLE and chosen["defensible"]
    assert report["selection_rule"] == "control point dominates repeated direct labour on joint samples"


def test_without_a_direct_labour_baseline_the_rule_says_so():
    p = favourable()
    p.pop("direct_labor")
    report = L.compile(p)
    assert report["selection_rule"].startswith("no direct-labour baseline declared")
    assert all(r["vs_direct_labor"] in (None, {"verdict": "NO_DIRECT_LABOR_BASELINE_DECLARED"})
               for r in report["candidates"] if r["eligibility"] == "ELIGIBLE")


def test_nothing_defensible_means_retain_the_current_state():
    p = problem()
    p.pop("direct_labor")
    for e in p["institutional_map"]["links"]:
        e["confidence"] = 0.3
    report = L.compile(p)
    assert report["selected"] == "do_nothing" and report["decision_brief"] is None
    assert report["selection_rule"] == "no defensible route: retain the current state"


def test_frontier_is_exactly_the_undominated_estimated_set():
    report = L.compile(problem())
    est = [r for r in report["candidates"] if r["eligibility"] == "ELIGIBLE"]
    for r in est:
        dominated = any(L.dominates(o, r) for o in est if o is not r)
        assert r["pareto_frontier"] is (not dominated)


def test_recombination_assumes_no_synergy():
    report = rows(L.compile(problem()))
    combo = report["proof.verifiable_receipts+eligibility.published_standard"]
    a, b = report["proof.verifiable_receipts"], report["eligibility.published_standard"]
    assert combo["lineage"][-1] == "recombine:proof+eligibility"
    assert combo["estimate"]["mean"] <= a["estimate"]["mean"] + b["estimate"]["mean"] + 1e-9
    pa, pb = a["harm_vector"], b["harm_vector"]
    assert combo["harm_vector"]["privacy"] == pytest.approx(1 - (1 - pa["privacy"]) * (1 - pb["privacy"]))
    assert combo["harm_vector"]["participant_burden"] == pytest.approx(
        pa["participant_burden"] + pb["participant_burden"])


def test_deterministic_for_a_seed_and_sensitive_to_it():
    one, two = L.compile(problem()), L.compile(problem())
    assert one["receipt_id"] == two["receipt_id"]
    other = L.compile(problem(seed=8))
    assert other["receipt_id"] != one["receipt_id"]
    assert [r["candidate_id"] for r in other["candidates"]] == [r["candidate_id"] for r in one["candidates"]]


def test_emitted_interventions_are_accepted_unchanged_by_the_existing_ranker():
    p = favourable()
    report = L.compile(p)
    assert report["interventions"] and len(report["interventions"]) <= L.MAX_CANDIDATES
    model = {**p["institutional_map"], "interventions": report["interventions"]}
    signal = SignalEnvelope.build(source="test:foundry", source_event_id="f-1", observed_at="2026-10-08T11:00:00Z",
                                  payload={"institutional_map": model}, evidence_refs=[H])
    ctx = {"institutional_leverage": {"objective": p["objective"], "outcome_node": "settled",
                                      "as_of": p["as_of"], "max_evidence_age_seconds": 86400, "budget_usd": 8000}}
    proposals = propose_institutional_leverage((signal,), ctx)
    assert proposals and all(x.execution_authority == "none" for x in proposals)
    assert {x.payload["institutional_leverage"]["route"]["intervention_id"] for x in proposals} <= \
        {i["id"] for i in report["interventions"]}


def test_decision_brief_satisfies_the_one_ask_contract_and_its_screen():
    report = L.compile(problem())
    brief = report["decision_brief"]
    assert brief is not None                       # hiring is financial, and trade-offs exist
    packet = asks.resource_request(**brief)
    asks.validate(packet)
    assert asks.screen(packet) == []
    assert any(o["cost"].lower().startswith("none") for o in packet["options"])
    assert "spend" in packet["authority_requested"]


def test_brief_is_absent_when_the_route_is_inside_held_authority_and_undisputed():
    p = favourable()
    p["constraints"]["held_authority"] = ["read_only", "internal_write", "external_contact", "financial"]
    report = L.compile(p)
    chosen = rows(report)[report["selected"]]
    assert chosen["authority"]["state"] == "WITHIN_HELD_AUTHORITY_GATE_REQUIRED"
    assert (report["decision_brief"] is None) == (not report["value_tradeoffs_for_founder"])


def test_value_of_information_is_only_routed_when_a_separate_test_exists():
    report = L.compile(favourable())
    voi = report["value_of_information"]
    assert voi.get("evpi_usd", 0) >= -1e-9
    if report["selected"].endswith(":staged"):
        assert voi["state"] == "MONETISED_NO_TEST" and "cognition_request" not in voi
    else:
        assert voi["state"] == "MONETISED" and voi["test"] == report["selected"] + ":staged"
        assert voi["rival"].split(":")[0] != report["selected"].split(":")[0]
        assert abs(sum(s["probability"] for s in voi["cognition_request"]["posterior_scenarios"]) - 1) < 1e-9


def test_over_the_contract_ceiling_nothing_is_dropped_silently():
    p = problem()
    nodes = {"proof": "proof_gap", "eligibility": "eligibility_check", "workflow": "eligibility_check",
             "capability": "eligibility_check", "information": "payer_rules"}
    p["surfaces"] = [dict(surface=s, node=nodes.get(s, "eligibility_check"), state="declared", evidence_refs=[H],
                          consent=consent("opt-in agreement", "participants")) for s in L.SURFACES]
    report = L.compile(p)
    total = report["generated"]["library"] + report["generated"]["mutated"] + report["generated"]["recombined"] + 1
    assert total > L.MAX_CANDIDATES
    assert len(report["generated"]["not_evaluated_over_ceiling"]) == total - L.MAX_CANDIDATES
    assert len([r for r in report["candidates"] if r["candidate_id"] != "do_nothing"]) == L.MAX_CANDIDATES


@pytest.mark.parametrize("mutate,needle", [
    (lambda p: p["constraints"].__setitem__("legal_operator", "UNIIMENTE"), "legal operator"),
    (lambda p: p.__setitem__("mechanism_overrides", {"made.up": {"cost_usd": 1}}), "unknown mechanism"),
    (lambda p: p["evidence"].__setitem__("proof", {"successes": 3, "trials": 2, "refs": [H]}), "exceed"),
    (lambda p: p["surfaces"][0].__setitem__("node", "nowhere"), "absent from the map"),
    (lambda p: p.__setitem__("surfaces", p["surfaces"] + [deepcopy(p["surfaces"][0])]), "declared twice"),
    (lambda p: p.__setitem__("samples", 5), "lawful-leverage problem"),
])
def test_malformed_or_unlawful_problems_are_refused(mutate, needle):
    p = problem()
    mutate(p)
    with pytest.raises(L.LeverageRefused, match=needle):
        L.compile(p)


def test_no_authority_is_created_and_nothing_executes():
    report = L.compile(favourable())
    assert report["authority_created"] is False and report["executes"] is False
    assert report["estimate_status"] == "input_estimates_not_verified_outcomes"
    assert all(step["consequence_class"] in ("read_only", "internal_write") for step in report["preparable"])


# ---------------------------------------------------------------- regressions from the 2026-10-08 adversarial review
def test_a_surface_that_names_third_parties_needs_consent_covering_every_one():
    p = problem()
    p["surfaces"][5]["third_parties"] = ["claimants whose public posts are read"]      # information surface
    r = rows(L.compile(p))
    assert "REJECTED_NO_CONSENT_PATH" in r["information.public_signal_monitor"]["reasons"]
    p["surfaces"][5]["consent"] = consent("posting terms", "someone else")
    r = rows(L.compile(p))
    assert any(x.startswith("REJECTED_CONSENT_DOES_NOT_COVER") for x in r["information.public_signal_monitor"]["reasons"])


def test_a_combination_cannot_launder_a_component_gate():
    p = favourable()
    p["constraints"]["prohibited_consequence_classes"] = ["external_contact"]
    r = rows(L.compile(p))
    combo = r["proof.verifiable_receipts+eligibility.published_standard"]
    assert combo["eligibility"] == "REJECTED"
    assert "proof.verifiable_receipts:REJECTED_CONSEQUENCE_CLASS:external_contact" in combo["reasons"]


def test_scope_variants_scale_the_sampled_effect_even_with_strong_evidence():
    r = rows(L.compile(favourable()))
    full, staged = r["proof.verifiable_receipts"]["estimate"], r["proof.verifiable_receipts:staged"]["estimate"]
    assert 0.35 < staged["mean"] / full["mean"] < 0.65                 # halved, not erased by evidence
    assert 0.35 < full["pessimistic_mean"] / full["mean"] < 0.65      # the halved-effect check is live


def test_dominance_ignores_samples_where_nothing_could_close():
    r = rows(L.compile(favourable()))
    v = r["proof.verifiable_receipts"]["vs_direct_labor"]
    assert 0 < v["informative_samples"] < 1500                        # outcome-path failures are excluded


def test_an_indefensible_baseline_never_flips_the_choice_to_doing_nothing():
    p = favourable()
    p["constraints"].pop("value_per_unit_gap_usd")
    p["direct_labor"].update(effect=0.02, effort_hours_per_cycle=1)
    report = L.compile(p)
    assert report["selected"] != "do_nothing"
    assert report["selection_rule"].startswith("the declared direct-labour baseline is not defensible")


def test_a_pareto_dominated_baseline_is_never_selected():
    p = problem()
    p["constraints"].pop("value_per_unit_gap_usd")
    p["surfaces"] = [dict(surface="routing", node="eligibility_check", state="manual triage", evidence_refs=[H])]
    p["mechanism_overrides"] = {"routing.evidence_triage": {"effort_hours": 0, "maintenance_hours_per_cycle": 0,
                                                            "founder_attention_hours": 0, "delay_days": 0}}
    p["evidence"] = {"routing.evidence_triage": dict(successes=60, trials=100, refs=[H])}
    report = L.compile(p)
    r = rows(report)
    if L.dominates(r["routing.evidence_triage"], r["direct_labor"]):
        assert report["selected"] != "direct_labor"
    assert r[report["selected"]]["pareto_frontier"]


def test_negative_monetised_value_is_never_defensible():
    r = rows(L.compile(problem()))                                     # $2000 per unit of gap declared
    d = r["direct_labor"]
    assert d["monetised_mean_usd"] < 0 and "NEGATIVE_MONETISED_VALUE" in d["falsification_flags"]
    assert not d["defensible"]


def test_harm_ceilings_can_be_tightened_never_loosened():
    p = problem()
    p["constraints"]["harm_ceiling"] = {"privacy": 0.9, "tail": 0.05}
    c = L.ceilings(L.validate(p))
    assert c["privacy"] == L.DEFAULT_CEILING["privacy"] and c["tail"] == 0.05


@pytest.mark.parametrize("name", [" UNIIMENTE", "UNIIMENTE LLC", "uniimente\u200b", "GREG", "the egregore", ""])
def test_the_institution_is_never_its_own_legal_operator(name):
    p = problem()
    p["constraints"]["legal_operator"] = name
    with pytest.raises(L.LeverageRefused):
        L.compile(p)


def test_combinations_show_every_component_capability_to_the_gate():
    report = L.compile(favourable())
    combo = next(i for i in report["interventions"] if "+" in i["id"])
    parts = combo["action"]["payload"]["lawful_leverage"]["components"]
    assert len(parts) == 2 and combo["action"]["requested_capability"] == \
        "composite:" + "+".join(c["requested_capability"] for c in parts)


def test_deferred_routes_name_the_missing_class_and_carry_it_to_the_gate():
    report = L.compile(favourable())
    trigger = next(r for r in report["candidates"] if r["candidate_id"].endswith(":on_trigger")
                   and r["eligibility"] == "ELIGIBLE")
    brief = L.decision_brief({**report, "selected": trigger["candidate_id"], "value_tradeoffs_for_founder": []})
    assert trigger["authority"]["deferred_consequence_class"] in brief["why_now"]
    record = next((i for i in report["interventions"] if i["id"] == trigger["candidate_id"]), None)
    if record is not None:
        assert record["action"]["payload"]["lawful_leverage"]["deferred_consequence_class"] == \
            trigger["authority"]["deferred_consequence_class"]


def test_irreversible_direct_labour_is_labelled_irreversible():
    p = problem()
    p["direct_labor"]["consequence_class"] = "irreversible"
    assert rows(L.compile(p))["direct_labor"]["reversibility"] == "irreversible"


def test_problem_text_never_enters_gregs_own_prose():
    p = problem()
    p["direct_labor"]["description"] = "reviewer clears the queue before the payer deadline, urgently"
    brief = L.compile(p)["decision_brief"]
    packet = asks.resource_request(**brief)
    assert asks.screen(packet) == []
    for field in ("why_now", "recommendation", "expected_effect", "uncertainty"):
        assert "deadline" not in packet[field] and "eligibility_check" not in packet[field]
