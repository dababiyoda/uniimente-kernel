"""Forecast calibration from realized values bound to retained forecast receipts (directive section 5)."""
from types import SimpleNamespace

import pytest

from greg.cognition import settlement
from greg.cognition.cortex import reason, registry_view
from greg.cognition.genomes import forecasting as F


class Ledger:
    def __init__(self):
        self.records = {}

    def add(self, cognitive):
        h = f"sha256:{len(self.records):064x}"
        self.records[h] = SimpleNamespace(record_type="receipt", payload={"result": {"output": cognitive}})
        return h

    def find(self, h):
        return self.records.get(h)


class Journal:
    def __init__(self):
        self.ledger, self.events = Ledger(), []

    def record(self, kind, payload, key=None, sensitivity=None):
        self.events.append(SimpleNamespace(type="greg." + kind, payload=payload))

    def replay(self, prefix=""):
        return [e for e in self.events if e.type.startswith("greg." + prefix)]


def forecast(seed):
    """A real M4 development series forecast through the canonical cognition path; its true continuation."""
    data, truth = F.instance(seed)
    registry = registry_view()
    registry.set_state("cognition.forecast_quantile", "ATTACHED")             # evaluation-only, in memory
    r = reason({"problem_id": f"cal-{seed}", "operation": "forecast_distribution", "data": data,
                "geometry": {"latency_limit": 20}}, registry=registry)
    assert r["abstention_state"] == "NONE"
    return r, truth["actual"]


def test_realized_values_bind_to_receipts_and_yield_per_level_coverage():
    j = Journal()
    for seed in range(4):                                                     # development seeds only
        receipt, actual = forecast(seed)
        settlement.record_realization(j, receipt=j.ledger.add(receipt), realized=actual, source="external_record")
    out = settlement.outcome_calibration(j)
    assert out["n"] == 4 and out["authority_created"] is False
    levels = {row["level"]: row for row in out["levels"]}
    assert set(levels) == set(F.LEVELS)
    assert all(row["receipts"] == 4 and row["all_steps"]["n"] == 4 * 13 for row in levels.values())
    assert levels[0.95]["all_steps"]["coverage"] >= levels[0.05]["all_steps"]["coverage"]   # monotone in level
    # the verdict uses one step per receipt: four receipts are too few to test calibration
    assert {row["state"] for row in levels.values()} == {"INSUFFICIENT_EVIDENCE"}
    assert out["verdict"] == "INSUFFICIENT_EVIDENCE"


def test_a_realization_must_bind_a_valid_forecast_receipt_with_one_value_per_step():
    j = Journal()
    receipt, actual = forecast(0)
    h = j.ledger.add(receipt)
    with pytest.raises(ValueError, match="13 finite numbers"):
        settlement.record_realization(j, receipt=h, realized=actual[:-1], source="external_record")
    with pytest.raises(ValueError, match="source"):
        settlement.record_realization(j, receipt=h, realized=actual, source="rumour")
    forged = {**receipt, "output": {**receipt["output"], "point": [0.0] * 13}}  # receipt_id no longer holds
    with pytest.raises(ValueError, match="valid forecast receipt"):
        settlement.record_realization(j, receipt=j.ledger.add(forged), realized=actual, source="external_record")
    with pytest.raises(ValueError):
        settlement.record_realization(j, receipt="sha256:missing", realized=actual, source="external_record")


def test_too_few_realizations_are_insufficient_and_a_passing_predicate_is_not_one():
    j = Journal()
    assert settlement.outcome_calibration(j)["verdict"] == "unmeasured"
    receipt, actual = forecast(1)
    settlement.record_realization(j, receipt=j.ledger.add(receipt), realized=actual, source="sensor_observation")
    assert settlement.outcome_calibration(j)["verdict"] == "INSUFFICIENT_EVIDENCE"   # 1 receipt < 20


def test_copies_of_one_forecast_count_once_and_twenty_distinct_forecasts_give_a_verdict():
    j = Journal()
    receipt, actual = forecast(2)
    for _ in range(5):                                                        # five ledger copies of one forecast
        settlement.record_realization(j, receipt=j.ledger.add(dict(receipt)), realized=actual,
                                      source="external_record")
    assert settlement.outcome_calibration(j)["n"] == 1
    j = Journal()
    registry = registry_view()
    registry.set_state("cognition.forecast_quantile", "ATTACHED")
    for seed in range(10):                                                    # development series only
        data, truth = F.instance(seed)
        for origin, realized in ((data["history"], truth["actual"]),          # two rolling origins per series
                                 (data["history"][:-13], data["history"][-13:])):
            r = reason({"problem_id": f"roll-{seed}-{len(origin)}", "operation": "forecast_distribution",
                        "data": {**data, "history": origin}, "geometry": {"latency_limit": 20}}, registry=registry)
            settlement.record_realization(j, receipt=j.ledger.add(r), realized=realized, source="external_record")
    out = settlement.outcome_calibration(j)
    assert out["n"] == 20 and all(row["receipts"] == 20 for row in out["levels"])
    assert out["verdict"] in ("CALIBRATED", "MISCALIBRATED")
