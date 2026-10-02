"""Native PR132 tests retained for extracted mechanisms, not 55-system acceptance.

Source: da3d4ac8643ecf6791ffadcac064f8bb1cc6269d
Original path: tests/unit/test_foundry_systems.py.
"""

import pytest

from foundry.systems import graph, model_check, reputation, search, next_test, mechanism, dsl, proofs



def test_model_checker_verifies_the_boundary_and_returns_the_shortest_counterexample():
    assert model_check.check(model_check.APPROVAL_BOUNDARY)["holds"] is True
    bad = model_check.check(model_check.buggy_approval_boundary())
    assert bad["holds"] is False and bad["trace"] == ["raise_request", "execute_on_pending"]
    assert bad["violated"] == "never_executed_without_approval"
    with pytest.raises(model_check.ModelError):
        model_check.check({"variables": {"x": [0]}, "initial": {"x": 0}, "transitions": [{"name": "t", "set": {"y": 1}}]})
    bounded = model_check.check({"variables": {"n": list(range(50))}, "initial": {"n": 0},
                                 "transitions": [{"name": f"to{i}", "set": {"n": i}} for i in range(50)]}, max_states=10)
    assert bounded["holds"] is None, "hitting the state bound is reported, never read as a proof"



def test_graph_refuses_non_causal_edges_and_explains_capital(tmp_path):
    result = graph.exercise(tmp_path)
    assert result["why_capital_reaches_signal"] and result["bad_edge_refused"]
    assert result["shared_capabilities"][0]["node"] == "cap:proof-verifier"
    g = graph.Graph()
    with pytest.raises(graph.GraphError):
        g.add("x", "Rumor")
    g.add("a", "Action")
    with pytest.raises(graph.GraphError):
        g.link("a", "produced", "missing")



def test_reputation_ignores_unevidenced_claims_and_ranks_by_lower_bound(tmp_path):
    result = reputation.exercise(tmp_path)
    assert result["steady_beats_lucky"] and result["recovery_beats_unrecovered"]
    assert result["stale_is_insufficient"] and result["sybil_ignored"]



def test_search_returns_worked_and_failed_precedents_side_by_side(tmp_path):
    result = search.exercise(tmp_path)
    assert (result["closest_worked"], result["closest_failed"]) == ("freight-pilot-worked", "freight-pilot-failed")
    assert result["unmeasured"] == ["freight-unmeasured"] and result["clinic_case_excluded"]
    assert search.search([{"id": "a", "text": "unrelated"}], "freight") == []



def test_next_best_test_ignores_near_certain_beliefs_and_prefers_information_per_cost():
    assert next_test.value_of_information(99, 1, 0.9) < 0.01
    result = next_test.exercise(None)
    assert result["near_certain_belief_worth_little"] and result["one_lucky_transition_not_first"]



def test_mechanisms_make_truth_the_best_response():
    result = mechanism.exercise(None)
    assert result["brier_truthful"] and result["vickrey_max_deviation_gain"] <= 0
    assert result["procurement"] == {"winner": "b", "paid": 120}



def test_dsl_runs_narrow_rules_and_rejects_code():
    result = dsl.exercise(None)
    assert result["price"] == 392.0 and result["budget"] == 800 and all(result["refused"].values())
    for src in ("2 ** 10 ** 10", "[x for x in range(9)]", "units[0]", "open('/etc/passwd')"):
        with pytest.raises(dsl.RuleError):
            dsl.parse("pricing", src)



def test_proofs_bind_membership_to_a_trusted_root_only(tmp_path):
    result = proofs.exercise(tmp_path)
    assert result["all_members_prove"] and result["tampered_sibling_fails"] and result["non_member_refused"]
    assert result["forged_proof_self_consistent"], "negative evidence: a forger's proof is internally consistent"
    assert result["forged_rejected_by_trusted_root"] and result["signed_root_substitution_detected"]


