"""P6 v5: track_then_staff (a Layer 1 basal tracker -> Erlang C) and the natural F8 family's integrity.

Development dates only (2015-01-29..02-28); no held-out item (2015-03-01..06-30) is generated and no arm runs on a
held-out date. Genome families start registered-and-withheld (VERIFIED); the canonical-path tests attach them in an
in-memory registry view exactly as the frozen evaluation does. Nothing here changes a body or creates authority.
"""
import copy
import csv
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
from statistics import NormalDist
import zipfile

import pytest

pytest.importorskip("scipy")
pytest.importorskip("numpy")

from cortex.evaluation.composition_lift import run_v5 as R  # noqa: E402
from cortex.evaluation.composition_lift.vpl_metrics import validate_preregistration  # noqa: E402
from cortex.evaluation.data import build_uber_nyc_2015 as B  # noqa: E402
from greg.cognition.composition import (RECIPES, CognitionError, route, staffing_quantile,  # noqa: E402
                                        track_measurements, tracked_multiplier)
from greg.cognition.cortex import reason, registry_view  # noqa: E402
from greg.cognition.genomes.basal import kalman_solve  # noqa: E402
from greg.cognition.genomes.solvers_b import erlang_solve, erlang_truth  # noqa: E402


def attached():
    registry = registry_view()
    for cid in R.EVAL_ATTACH:
        registry.set_state(cid, "ATTACHED")
    return registry


@pytest.fixture(scope="module")
def calibration():
    return R.calibrate()


@pytest.fixture(scope="module")
def dev(calibration):
    return R.items("dev", calibration)


def find(dev, stream, day, block):
    return next(i for i in dev if i["stream"] == stream and i["date"] == day and i["block"] == block)


def chain(payload, pid="t", **kw):
    return {"problem_id": pid, "chain": {"question": "q", "payload": payload, **kw}}


def synthetic(observed=None, plan=None, block=16, penalty=10.0, tracker=None):
    plan = plan or [100.0] * 48
    if observed is None:
        noise = [0.05, -0.12, 0.08, 0.15, -0.04, 0.1, -0.09, 0.02, 0.11, -0.13, 0.06, 0.0, -0.07, 0.12, 0.03]
        observed = [round(110 * (1 + e)) for e in noise]
    return {"observed_today": observed, "standing_plan": {"blocks": plan, "decision_block": block},
            "staffing": {**R.STAFFING, "shortage_penalty": penalty},
            "tracker": tracker if tracker is not None else {"q": 1e-5, "r": 0.01,
                                                            "prior": {"mean": [1.0, 0.0], "var": [0.04, 1e-5]}}}


# ------------------------------------------------------------------ the committed data and its build
def test_the_committed_extract_records_its_sources_and_has_six_disjoint_streams():
    data = R.uber()
    assert data["source"]["trips"]["sha256"] == B.TRIPS_SHA256 and data["source"]["zones"]["sha256"] == B.ZONES_SHA256
    assert "FiveThirtyEight" in data["licence"] and "TLC" in data["licence"] and "evaluation use only" in data["licence"]
    assert data["dates"][0] == "2015-01-01" and data["dates"][-1] == "2015-06-30" and len(data["dates"]) == 181
    assert list(data["counts"]) == sorted(R.STREAM_IDS) and set(data["counts"]) == set(B.STREAMS)
    assert all(len(days) == 181 and all(len(d) == 48 for d in days) for days in data["counts"].values())
    assert data["rows_kept"] + sum(data["rows_left_out"].values()) == data["rows"] == 14_270_479
    assert sum(sum(map(sum, days)) for days in data["counts"].values()) == data["rows_kept"]


def _synthetic_sources(tmp_path):
    zones = "LocationID,Borough,Zone\r1,EWR,Newark Airport\r4,Manhattan,Alphabet City\r14,Brooklyn,Bay Ridge\r" \
            "3,Bronx,Allerton/Pelham Gardens\r7,Queens,Astoria\r132,Queens,JFK Airport\r138,Queens,LaGuardia Airport\r" \
            "5,Staten Island,Arden Heights\r264,Unknown,NV\r"
    zpath = tmp_path / "zones.csv"
    zpath.write_bytes(zones.encode())
    rows = [B.HEADER, ["B1", "2015-01-01 00:00:00", "B1", "4"], ["B1", "2015-01-01 00:29:59", "B1", "4"],
            ["B1", "2015-01-01 00:30:00", "B1", "132"], ["B1", "2015-06-30 23:59:00", "B1", "7"],
            ["B1", "2015-03-05 08:10:00", "B1", "138"], ["B1", "2015-03-05 08:10:00", "B1", "5"],
            ["B1", "2015-03-05 08:10:00", "B1", "1"], ["B1", "2015-07-01 00:00:00", "B1", "4"]]
    text = io.StringIO()
    csv.writer(text, lineterminator="\n").writerows(rows)
    tpath = tmp_path / "trips.zip"
    with zipfile.ZipFile(tpath, "w") as zf:
        zf.writestr(B.MEMBER, text.getvalue())
        zf.writestr("__MACOSX/._" + B.MEMBER, "resource fork")
    return tpath, zpath


def test_the_build_is_deterministic_skips_resource_forks_and_accounts_for_every_row(tmp_path, monkeypatch):
    trips, zones = _synthetic_sources(tmp_path)
    monkeypatch.setattr(B, "TRIPS_SHA256", hashlib.sha256(trips.read_bytes()).hexdigest())
    monkeypatch.setattr(B, "ZONES_SHA256", hashlib.sha256(zones.read_bytes()).hexdigest())
    first, second = B.build(trips, zones), B.build(trips, zones)
    assert B.write(first, tmp_path / "a.json.gz") == B.write(second, tmp_path / "b.json.gz")
    assert (tmp_path / "a.json.gz").read_bytes() == (tmp_path / "b.json.gz").read_bytes()
    assert first["rows"] == 8 and first["rows_kept"] == 5
    assert first["rows_left_out"] == {"outside_streams": 2, "unknown_location_id": 0, "outside_dates": 1}
    c = first["counts"]
    assert c["Manhattan"][0][0] == 2 and c["JFK Airport"][0][1] == 1                  # 00:29:59 is block 0
    assert c["Queens (excluding JFK and LaGuardia)"][180][47] == 1 and c["LaGuardia Airport"][63][16] == 1
    assert sum(map(sum, c["Queens (excluding JFK and LaGuardia)"])) == 1               # airports are not Queens
    assert json.loads(gzip.decompress((tmp_path / "a.json.gz").read_bytes())) == first


def test_the_build_refuses_any_source_whose_digest_differs(tmp_path):
    trips, zones = _synthetic_sources(tmp_path)
    with pytest.raises(SystemExit, match="sha256"):
        B.build(trips, zones)


@pytest.mark.skipif(not (os.environ.get("F8_UBER_ZIP") and os.environ.get("F8_ZONES_CSV")),
                    reason="set F8_UBER_ZIP and F8_ZONES_CSV to the downloaded sources to rebuild the extract")
def test_the_committed_extract_rebuilds_byte_for_byte_from_the_recorded_sources(tmp_path):
    data = B.build(Path(os.environ["F8_UBER_ZIP"]), Path(os.environ["F8_ZONES_CSV"]))
    assert B.write(data, tmp_path / "x.json.gz") == hashlib.sha256(R.DATA.read_bytes()).hexdigest()


# ------------------------------------------------------------------ the recipe: translation and abstentions
def test_the_tracker_geometry_routes_only_to_its_recipe_and_no_recipe_shadows_another():
    payload = synthetic()
    assert route(payload) == "track_then_staff"
    f6_like = {"arrival_histories": [], "staffing": payload["staffing"]}
    assert route(f6_like) == "forecast_then_staff"
    assert route({**payload, **f6_like}) is None                       # ambiguous: no composition at all
    for a in RECIPES:
        for b in RECIPES:
            if a != b:
                assert not set(RECIPES[a]["requires"]) <= set(RECIPES[b]["requires"]), (a, b)


def test_the_translation_is_the_q_star_multiplier_times_the_plan_and_the_erlang_answer_at_that_rate():
    payload = synthetic(block=20, penalty=30.0)
    payload["standing_plan"]["blocks"][20] = 240.0
    r = reason(chain(payload), registry=attached())
    assert r["state"] == "ANSWERED" and r["authority_created"] is False
    assert [s["stage"] for s in r["stages"]] == ["track", "staff"]
    assert all(s["verifier"] == "STRUCTURALLY_VERIFIED" for s in r["stages"])
    data, usable, planned = track_measurements(payload)
    assert usable == 15 and planned == 240.0
    out = kalman_solve(data, {})["output"]
    level = staffing_quantile(payload["staffing"])
    m = out["positions"][-1] + NormalDist().inv_cdf(level) * math.sqrt(out["final_position_variance"] + 0.01)
    assert r["answer"]["quantile_level"] == level == pytest.approx(1 - 1 / 30, abs=1e-6)
    assert r["answer"]["multiplier"] == pytest.approx(tracked_multiplier(out, 0.01, level)) == pytest.approx(m)
    assert r["answer"]["arrival_rate"] == pytest.approx(240.0 * m / 1800)
    assert r["answer"]["agents"] == erlang_truth({"arrival_rate": r["answer"]["arrival_rate"],
                                                  "mean_service_time": 1200.0, "target_wait": 120.0,
                                                  "max_wait_probability": 0.2})
    assert [b["slot"] for b in r["bindings"]] == ["staffing costs -> critical fractile",
                                                  f"kalman position, variance -> q{level:g} multiplier",
                                                  "multiplier x plan[20] -> arrival_rate"]


def test_fewer_than_three_usable_measurements_abstain_before_any_stage_runs():
    plan = [100.0] * 48
    for j in range(13):
        plan[j] = 10.0                                    # below half the day's mean plan: no measurement
    r = reason(chain(synthetic(plan=plan)), registry=attached())
    assert r["state"] == "STAGE_ABSTAINED" and r["stages"] == [] and "2 usable measurements" in r["reason"]


def test_a_rejected_noise_model_and_an_undeclared_one_abstain_through_the_tracker_stage():
    flat = synthetic(observed=[110] * 15)                  # innovations far smaller than declared: NIS rejects
    r = reason(chain(flat), registry=attached())
    assert r["state"] == "STAGE_ABSTAINED" and [s["stage"] for s in r["stages"]] == ["track"]
    undeclared = synthetic(tracker={"prior": {"mean": [1.0, 0.0], "var": [0.04, 1e-5]}})
    r = reason(chain(undeclared), registry=attached())
    assert r["state"] == "STAGE_ABSTAINED" and r["answer"] is None


def test_a_zero_plan_for_the_decision_block_is_a_translation_failure_not_a_guess():
    payload = synthetic()
    payload["standing_plan"]["blocks"][16] = 0.0
    r = reason(chain(payload), registry=attached())
    assert r["state"] == "TRANSLATION_FAILED" and r["translation_failures"] and r["answer"] is None
    assert [s["stage"] for s in r["stages"]] == ["track"]


def test_malformed_payloads_are_refused():
    for mutate in (lambda p: p["standing_plan"].update(decision_block=14),           # an observed block
                   lambda p: p["standing_plan"].update(decision_block=48),
                   lambda p: p["standing_plan"].update(extra=1),
                   lambda p: p["staffing"].update(overtime=2),
                   lambda p: p["tracker"].update(gain=0.5),
                   lambda p: p["observed_today"].__setitem__(0, -1)):
        payload = synthetic()
        mutate(payload)
        with pytest.raises(CognitionError):
            reason(chain(payload), registry=attached())


def test_a_withheld_tracker_makes_the_chain_abstain():
    registry = registry_view()
    registry.set_state("cognition.queue_erlang", "ATTACHED")             # the basal tracker stays withheld
    r = reason(chain(synthetic()), registry=registry)
    assert r["state"] == "STAGE_ABSTAINED" and r["answer"] is None


def test_the_in_process_erlang_staffing_agrees_with_the_genome_on_the_rates_f8_meets():
    for arrivals in (3, 17, 40.5, 211, 958.25, 1413, 2875.5, 6000):
        data = {"arrival_rate": arrivals / 1800, "mean_service_time": 1200.0, "target_wait": 120.0,
                "max_wait_probability": 0.2}
        assert erlang_solve(data, {})["output"]["agents"] == erlang_truth(data) == R.requirement(arrivals)


# ------------------------------------------------------------------ the F8 family: partition, leakage, calibration
def test_the_partition_is_fixed_by_date_and_the_heldout_count_is_declared():
    hist, dev, held = R.dates("history"), R.dates("dev"), R.dates("heldout")
    assert (hist[0], hist[-1], dev[0], dev[-1], held[0], held[-1]) == (
        "2015-01-01", "2015-01-28", "2015-01-29", "2015-02-28", "2015-03-01", "2015-06-30")
    assert hist + dev + held == R.uber()["dates"]
    assert len(held) * len(R.streams()) * len(R.DECISION_BLOCKS) == 2196
    assert R.date_index(dev[0]) == 7 * R.PLAN_WEEKS                       # every development day has four weeks


def test_the_payload_never_holds_the_scored_block_or_any_later_count(dev, calibration, monkeypatch):
    for item in (find(dev, "Manhattan", "2015-02-10", 16), find(dev, "JFK Airport", "2015-02-27", 36)):
        i, k = item["date_index"], item["block"]
        counts = R.uber()["counts"][item["stream"]][i]
        assert item["payload"]["observed_today"] == counts[:k - 1] and len(item["payload"]["observed_today"]) == k - 1
        assert item["truth"]["actual"] == counts[k]
        plan = R.standing_plan(item["stream"], i)
        assert item["payload"]["standing_plan"]["blocks"] == plan
        # perturb the in-progress block, the scored block, every later block and every later day: payload unchanged
        perturbed = copy.deepcopy(R.uber())
        stream = perturbed["counts"][item["stream"]]
        stream[i][k - 1:] = [n * 3 + 7 for n in stream[i][k - 1:]]
        for later in range(i + 1, len(stream)):
            stream[later] = [n + 11 for n in stream[later]]
        monkeypatch.setattr(R, "uber", lambda: perturbed)
        again = R.f8(item["stream"], item["date"], k, calibration)
        assert again["payload"] == item["payload"] and again["truth"]["actual"] != item["truth"]["actual"]
        monkeypatch.undo()


def test_the_standing_plan_is_the_mean_of_the_four_previous_same_weekdays():
    i = R.date_index("2015-02-12")                                           # a Thursday
    counts = R.uber()["counts"]["Brooklyn"]
    expected = [sum(counts[i - 7 * w][b] for w in (1, 2, 3, 4)) / 4 for b in range(48)]
    assert R.standing_plan("Brooklyn", i) == expected
    with pytest.raises(ValueError):
        R.standing_plan("Brooklyn", 27)


def test_calibration_reads_development_days_only_and_optimises_the_genomes_own_model(calibration, monkeypatch):
    import numpy as np
    perturbed = copy.deepcopy(R.uber())
    first_heldout = R.date_index("2015-03-01")
    for days in perturbed["counts"].values():
        for i in range(first_heldout, len(days)):
            days[i] = [n * 5 + 3 for n in days[i]]
    monkeypatch.setattr(R, "uber", lambda: perturbed)
    assert R.calibrate() == calibration                                        # held-out days change nothing
    monkeypatch.undo()
    for stream, fit in calibration.items():
        assert fit["kalman"]["at_grid_edge"] == [] and 0 < fit["ewma"]["alpha"] <= 1 and fit["ewma"]["sigma"] > 0
    # the likelihood recursion is the genome's: its final state on a series equals kalman_track's own output
    fit = calibration["Brooklyn"]["kalman"]
    checked = 0
    for zs in R._ratio_days("Brooklyn")[:5]:
        _, x, p11 = R.kalman_loglik_grid([zs], np.array([fit["q"]]), np.array([fit["r"]]),
                                         np.array([fit["prior_var"]]), final_state=True)
        out = kalman_solve({"dt": 1.0, "measurements": zs, **R.tracker(fit)}, {})
        if out["status"] != "ANSWER":                    # the genome's NIS test may refuse a day; skip that day
            continue
        assert out["output"]["positions"][-1] == pytest.approx(float(x[0]), rel=1e-12)
        assert out["output"]["final_position_variance"] == pytest.approx(float(p11[0]), rel=1e-12)
        checked += 1
    assert checked >= 3


def test_scoring_costs_decisions_and_the_fallback_and_counts_malformed_plans(dev):
    item = find(dev, "Brooklyn", "2015-02-03", 26)
    req, penalty = item["truth"]["required"], item["truth"]["shortage_penalty"]
    assert R.f8_cost(item, {"agents": req}) == (item["truth"]["hindsight_cost"], "decided", req)
    assert R.f8_cost(item, {"agents": req - 3})[0] == req - 3 + 3 * penalty
    fallback = item["fallback"]["agents"]
    expected = fallback + penalty * max(0, req - fallback)
    assert R.f8_cost(item, None) == (expected, "fallback", fallback)
    assert R.f8_cost(item, {"agents": 2.5}) == (expected, "wrong", fallback)
    assert R.f8_cost(item, {"agents": -1})[1] == "wrong"
    assert fallback == R.requirement(item["payload"]["standing_plan"]["blocks"][26])


def test_the_practitioner_arms_run_in_process_on_development_items(dev):
    item = find(dev, "Manhattan", "2015-02-17", 36)
    rows = {arm: R.run_arm(item, arm, "track_then_staff") for arm in R.IN_PROCESS}
    assert all(row["result"] == "decided" and row["stages"] == 0 for row in rows.values())
    assert rows["standing_plan_then_staff"]["agents"] == item["fallback"]["agents"]
    assert rows["ewma_ratio_quantile_then_staff"]["agents"] >= rows["ewma_ratio_then_staff"]["agents"]  # q* >= 2/3


# ------------------------------------------------------------------ one development item end to end
def test_one_development_item_runs_end_to_end_through_the_canonical_path(dev):
    item = find(dev, "Brooklyn", "2015-02-03", 26)
    answer, seconds, r = R.chain(item)
    assert r["state"] == "ANSWERED" and r["recipe"] == "track_then_staff" and r["routed_by"] == "geometry"
    assert r["authority_created"] is False and r["execution_authority"] == "none"
    assert [s["stage"] for s in r["stages"]] == ["track", "staff"]
    assert {s["method"] for s in r["stages"]} == {"cognition.basal_kalman", "cognition.queue_erlang"}
    assert all(s["verifier"] == "STRUCTURALLY_VERIFIED" for s in r["stages"])
    assert R.f8_cost(item, answer)[1] == "decided" and seconds < R.CHAIN_BUDGET_S
    compiled, _, receipt = R.compiled(item)
    assert receipt["state"] == "ANSWERED" and receipt["method_or_composition_selected"] == "composition:track_then_staff"
    assert compiled == answer
    static = R.run_arm(item, "static_composition", "track_then_staff")
    assert static["answer"] == answer and static["stages"] == 2


# ------------------------------------------------------------------ pre-registration and the build guard
def test_the_preregistration_is_complete_and_names_the_committed_data():
    doc = json.loads(R.PREREG.read_text())
    assert validate_preregistration(doc) == []
    assert doc["family_id"] == "F8" and doc["natural"] is True and doc["n_heldout"] == 2196
    assert doc["data_provenance"]["sha256"] == hashlib.sha256(R.DATA.read_bytes()).hexdigest()
    assert B.TRIPS_SHA256 in json.dumps(doc["data_provenance"]) and B.ZONES_SHA256 in json.dumps(doc["data_provenance"])
    assert "evaluation use only" in doc["data_provenance"]["licence"]
    assert doc["latency_rule"]["kind"] == "multiplier" and doc["latency_rule"]["value"] == R.LATENCY_MULTIPLIER
    assert doc["static_arm"] == {**doc["static_arm"], "chosen_on": "development", "must_decide": True}
    assert doc["compiled_arm"]["entry"] == "compile" and doc["alpha"] == 0.05
    assert any("69-41" in d for d in doc["disclosures"])
    assert {p["arm"] for p in doc["predictions"]} >= {"best_constituent", "ewma_ratio_quantile_then_staff"}


def test_the_suite_build_refuses_without_a_complete_preregistration(monkeypatch, tmp_path):
    bad = tmp_path / "prereg.json"
    bad.write_text(json.dumps({"family_id": "F8"}))
    monkeypatch.setattr(R, "PREREG", bad)
    monkeypatch.setattr(R, "SUITE", tmp_path / "suite.json")
    monkeypatch.setattr("sys.argv", ["run_v5.py", "--build"])
    with pytest.raises(SystemExit, match="pre-registration is incomplete"):
        R.main()
    assert not (tmp_path / "suite.json").exists()


def test_the_freeze_hashes_the_data_the_prereg_and_every_module_the_run_can_execute():
    closure = set(R.code_closure())
    for path in ("greg/cognition/composition.py", "greg/cognition/genomes/basal.py", "greg/cognition/genomes/solvers_b.py",
                 "greg/cognition/compiler.py", "greg/cognition/worker.py", "cortex/evaluation/composition_lift/run.py",
                 "cortex/evaluation/composition_lift/vpl_metrics.py", "cortex/evaluation/data/uber_nyc_2015_halfhour.json.gz",
                 "cortex/evaluation/composition_lift/prereg-v5.json", "docs/evidence/greg-mind-evidence-index.json"):
        assert path in closure
    assert all((R.ROOT / p).is_file() and "__pycache__" not in p for p in closure)
