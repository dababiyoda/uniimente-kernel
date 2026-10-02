"""Native simulation qualifications do not establish real-world forecasts."""
from copy import deepcopy
import pytest

from greg.capabilities import CapabilityError
from foundry.systems import emulator, scenarios
from tests.unit.test_foundry_bridge_boundaries import invoke


def strategy(**changes):
    return {"platform_share": {}, "regulatory_exposure": 0, "runway_months": 24,
            "founder_hours_per_week": 0, "single_provider_share": 0,
            "outcome_differentiation": 1, **changes}


def test_uncertain_completion_is_reconciled_before_retrying_in_emulator(tmp_path):
    args = {"script": ["timeout", "partial_write", "ok"], "key": "invoice", "amount": 900,
            "honours_idempotency": True}
    out = invoke(tmp_path, 20, "compare", args)["result"]
    assert out["unsafe_retry"]["truth"]["charges"] == 2
    assert out["bounded_reconciliation"]["truth"]["charges"] == 1
    assert out["bounded_reconciliation"]["calls"] == 2
    assert out["bounded_reconciliation"]["state"] == "SIMULATED_RECONCILED_FROM_PROVIDER_LOG"
    assert not out["money_moved"] and not out["live_provider_qualified"]
    assert out == invoke(tmp_path, 20, "compare", args)["result"]
    assert not (tmp_path / "workspace").exists()


def test_dishonest_provider_cannot_be_covered_by_universal_exactly_once_claim(tmp_path):
    out = invoke(tmp_path, 20, "compare", {"script": ["duplicate_delivery"], "key": "k", "amount": 1,
                                          "honours_idempotency": False})["result"]
    assert out["bounded_reconciliation"]["truth"]["charges"] == 2
    assert out["bounded_reconciliation"]["state"] == "SIMULATED_DUPLICATE_EFFECT_REQUIRES_REPAIR"


def test_no_response_stops_at_resource_ceiling(tmp_path):
    out = invoke(tmp_path, 20, "compare", {"script": ["timeout"] * 10, "key": "k", "amount": 1,
                                          "honours_idempotency": True, "attempts": 2})["result"]
    assert out["bounded_reconciliation"]["calls"] == 2
    assert out["bounded_reconciliation"]["state"] == "BUDGET_EXHAUSTED"
    assert out["bounded_reconciliation"]["truth"]["charges"] == 0


@pytest.mark.parametrize("mutation", [{"script": ["undocumented"]}, {"amount": True}, {"amount": -1},
                                       {"attempts": 100000}, {"honours_idempotency": "yes"}])
def test_invalid_fault_or_budget_inputs_refuse(tmp_path, mutation):
    with pytest.raises(CapabilityError):
        invoke(tmp_path, 20, "compare", {"script": ["ok"], "key": "k", "amount": 1,
                                         "honours_idempotency": True, **mutation})


def test_declared_simulation_has_ground_truth_boundary_and_rename_invariance(tmp_path):
    out = invoke(tmp_path, 22, "tribunal", {"strategies": {"independent": strategy()}, "runs": 64})["result"]
    assert all(cell["survival"] == 1 and cell["revenue_retained"] == 1 for cell in out["table"]["independent"].values())
    assert out["evidence_kind"] == "simulation" and out["world_validity"] == "WORLD_UNVERIFIED"
    exposed = strategy(platform_share={"platform": .8}, runway_months=6, founder_hours_per_week=20,
                       single_provider_share=.9, outcome_differentiation=.2)
    a = scenarios.tribunal({"A": exposed}, runs=64, seed=2)
    b = scenarios.tribunal({"B": exposed}, runs=64, seed=2)
    assert a["table"]["A"] == b["table"]["B"]
    assert a["table"]["A"]["platform_loss"]["revenue_retained"] < .5


@pytest.mark.parametrize("changes", [{"platform_share": {"a": .8, "b": .8}}, {"runway_months": -1},
                                      {"founder_hours_per_week": 200}, {"single_provider_share": 2}])
def test_simulation_assumptions_are_explicit_and_bounded(tmp_path, changes):
    with pytest.raises(CapabilityError):
        invoke(tmp_path, 22, "tribunal", {"strategies": {"candidate": strategy(**changes)}})
    with pytest.raises(CapabilityError):
        invoke(tmp_path, 22, "tribunal", {"strategies": {"candidate": {"runway_months": 5}}})


def test_simulation_work_is_capped_before_enumeration(tmp_path):
    with pytest.raises(CapabilityError):
        invoke(tmp_path, 22, "tribunal", {"strategies": {"candidate": strategy()}, "runs": 100000})
