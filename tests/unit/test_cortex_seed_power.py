"""The recorded power analysis (`tests/evidence/cortex-seed-v0.1.6/power-analysis.json`) reads the frozen
held-out result faithfully, its sample sizes satisfy their own definitions, and it changes no frozen rule.
The full recomputation (`python scripts/analysis/cortex_seed_power.py --check`) takes about half a minute;
these checks recompute the parts each claim rests on."""
from __future__ import annotations

import importlib.util
import json
import random
from pathlib import Path

import pytest

from cortex.evaluation import scoring as S

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/evidence/cortex-seed-v0.1.6"
_spec = importlib.util.spec_from_file_location("cortex_seed_power", ROOT / "scripts/analysis/cortex_seed_power.py")
P = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P)
REC = json.loads((EVIDENCE / "power-analysis.json").read_text(encoding="utf-8"))
HELD = json.loads((EVIDENCE / "heldout-results.json").read_text(encoding="utf-8"))
BASELINES = S.THRESHOLDS["declared_baselines"]


def _stays(power_at, n):
    return all(power_at(m) >= P.TARGET_POWER for m in range(n, n + 26))


def test_it_changes_no_frozen_rule_and_cites_the_frozen_run():
    assert REC["changes_frozen_rule"] is False
    assert REC["freeze_manifest_sha256"] == HELD["freeze_manifest_sha256"]
    assert REC["frozen_rule"]["min_quality_gain_lower_bound"] == S.THRESHOLDS["min_quality_gain_lower_bound"]
    assert REC["frozen_rule"]["bootstrap_B"] == S.BOOTSTRAP_B
    assert sorted(REC["baselines"]) == sorted(BASELINES)


@pytest.mark.parametrize("name", BASELINES)
def test_observed_inputs_reproduce_from_the_frozen_result(name):
    obs = REC["baselines"][name]["observed"]
    routed = {i["item_id"]: i for i in HELD["arms"]["routed_seed"]["items"]}
    base = {i["item_id"]: i for i in HELD["arms"][name]["items"]}
    wins = sum(routed[k]["score"] - base[k]["score"] for k in routed)
    assert obs["n"] == len(routed) == 42 and obs["routed_only_wins"] == wins
    assert obs["frozen_lower_bound"] == HELD["arms"][name]["paired_gain_vs_routed"]["ci95"][0]
    harmful = sum(1 for k in routed if base[k]["critical"] or base[k]["unsupported_certainty"])
    assert REC["baselines"][name]["endpoints"]["harmful_failure"]["baseline_only"] == harmful
    assert not any(i["critical"] or i["unsupported_certainty"] for i in routed.values())


@pytest.mark.parametrize("name", BASELINES)
def test_the_binomial_limit_agrees_with_the_frozen_bootstrap_on_the_observed_data(name):
    obs = REC["baselines"][name]["observed"]
    assert abs(P.lower_bound(obs["n"], obs["routed_only_wins"]) - obs["frozen_lower_bound"]) <= 1 / obs["n"]


@pytest.mark.parametrize("name", BASELINES)
def test_quality_sample_size_meets_its_definition(name):
    q = REC["baselines"][name]["quality_gain"]
    p, thr, n = REC["baselines"][name]["observed"]["mean_gain"], S.THRESHOLDS["min_quality_gain_lower_bound"], q["items_for_80pct_power"]
    power = lambda m: P.quality_power(m, p, thr)  # noqa: E731
    assert _stays(power, n)
    assert not _stays(power, n - (1 if n <= 400 else 5))
    assert abs(power(42) - q["power_at_observed_n"]) < 1e-12 and q["power_at_observed_n"] < 0.2


def test_the_frozen_bootstrap_boundary_is_the_recorded_one():
    chk = REC["baselines"]["always_llm"]["quality_gain"]["frozen_bootstrap_check"]
    n, k = chk["n"], chk["frozen_wins_needed"]
    for wins, clears in ((k - 1, False), (k, True)):
        lo, _ = S._bootstrap_mean([1.0] * wins + [0.0] * (n - wins), random.Random(S.BOOTSTRAP_SEED + 1))
        assert (lo > S.THRESHOLDS["min_quality_gain_lower_bound"]) is clears
        assert lo == chk["by_wins"][str(wins)]["frozen_lower_bounds"]["wins_first"]


@pytest.mark.parametrize("name", BASELINES)
@pytest.mark.parametrize("endpoint", ["harmful_failure", "critical_error"])
def test_mcnemar_sample_sizes_meet_their_definition(name, endpoint):
    e = REC["baselines"][name]["endpoints"][endpoint]
    assert e["observed_exact_one_sided_p"] == pytest.approx(0.5 ** e["baseline_only"])
    for pr, row in e["by_routed_failure_rate"].items():
        n = row["items_for_80pct_power"]
        power = lambda m: P.mcnemar_power(m, e["observed_rate_baseline"], float(pr))  # noqa: E731
        assert _stays(power, n) and not _stays(power, n - (1 if n <= 400 else 5))
