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
    with pytest.raises(ValueError, match="unrefuted forecast receipt"):
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


def test_re_running_one_forecast_never_manufactures_a_sample():
    """Review finding 4: each re-run mints a new receipt id (latency is in the receipt), so one forecast re-run
    twenty times gave n = 20 and a verdict."""
    j = Journal()
    data, truth = F.instance(0)                                               # development seed
    registry = registry_view()
    registry.set_state("cognition.forecast_quantile", "ATTACHED")
    ids = set()
    for _ in range(20):
        r = reason({"problem_id": "daily-forecast", "operation": "forecast_distribution", "data": data,
                    "geometry": {"latency_limit": 20}}, registry=registry)
        ids.add(r["receipt_id"])
        settlement.record_realization(j, receipt=j.ledger.add(r), realized=truth["actual"], source="external_record")
    out = settlement.outcome_calibration(j)
    assert len(ids) > 1 and out["n"] == 1 and out["verdict"] == "INSUFFICIENT_EVIDENCE"


def test_conflicting_realizations_of_one_forecast_are_reported_not_resolved():
    j = Journal()
    receipt, actual = forecast(2)
    settlement.record_realization(j, receipt=j.ledger.add(dict(receipt)), realized=actual, source="external_record")
    settlement.record_realization(j, receipt=j.ledger.add(dict(receipt)), realized=[v + 1 for v in actual],
                                  source="founder_reported")
    out = settlement.outcome_calibration(j)
    assert out["n"] == 0 and len(out["conflicts"]) == 1


def test_a_refuted_forecast_is_never_bound_or_scored():
    """Review finding 4: a REFUTED receipt keeps its output for audit and was bound and counted."""
    from greg.cognition.contracts import digest
    receipt, actual = forecast(3)
    refuted = {k: v for k, v in receipt.items() if k != "receipt_id"}
    refuted["abstention_state"] = "REFUTED"
    refuted["receipt_id"] = digest(refuted)                                   # a genuinely valid REFUTED receipt
    assert settlement._valid_receipt(refuted)
    j = Journal()
    with pytest.raises(ValueError, match="unrefuted"):
        settlement.record_realization(j, receipt=j.ledger.add(refuted), realized=actual, source="external_record")


def test_a_calibrated_forecaster_is_rarely_called_miscalibrated_across_its_levels():
    """Review finding 5: seven uncorrected 95% tests called a perfectly calibrated forecaster MISCALIBRATED
    about a quarter of the time. With the Bonferroni correction the family error stays near alpha."""
    import random
    from statistics import NormalDist
    rnd = random.Random(3000)
    levels = (0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95)
    m, alpha, trials, false = len(levels), 0.05, 4000, 0
    z = NormalDist().inv_cdf(1 - alpha / (2 * m))
    for _ in range(trials):
        u = [rnd.random() for _ in range(40)]                                 # PIT values of a calibrated forecaster
        if any(not (lambda lo_hi: lo_hi[0] <= q <= lo_hi[1])(settlement._wilson(sum(x <= q for x in u), 40, z))
               for q in levels):
            false += 1
    assert false / trials < 0.08


def test_on_the_body_a_signed_realization_binds_and_the_awaiting_list_empties(tmp_path):
    """Review finding 15: calibration was reachable only from tests. A forecast receipt retained on the body
    ledger is listed as awaiting a realization; the founder's signed REALIZATION binds it (with its command
    digest) and calibration reads it; a malformed one is rejected and recorded."""
    from greg.body import Body
    from tests.greg_fixtures import drop, make_body, signed
    receipt, actual = forecast(0)
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as b:
        record = b.journal.ledger.append("receipt", {"result": {"output": receipt}})
        [waiting] = settlement.awaiting_realization(b.journal)
        assert waiting["receipt"] == record.hash and waiting["horizon"] == 13
    drop(home, signed(key, body_id, "REALIZATION", {"receipt": record.hash, "realized": actual,
                                                    "source": "external_record", "note": "M4 test continuation"}))
    drop(home, signed(key, body_id, "REALIZATION", {"receipt": record.hash, "realized": actual[:3],
                                                    "source": "external_record"}), name="short.json")
    with Body(home) as b:
        b.tick()
        [bound] = [e.payload for e in b.journal.replay("cognition.realization")]
        assert bound["command_digest"] and bound["source"] == "external_record"
        assert settlement.awaiting_realization(b.journal) == []
        assert settlement.outcome_calibration(b.journal)["n"] == 1
        assert any(e.payload["file"] == "short.json" for e in b.journal.replay("command.rejected"))
