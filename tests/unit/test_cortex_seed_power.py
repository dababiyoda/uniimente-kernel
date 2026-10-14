"""The recorded power analysis (`tests/evidence/cortex-seed-v0.1.6/power-analysis.json`) reads the frozen
held-out result faithfully, its sample sizes satisfy their own definitions, its exact joint power agrees with
brute-force enumeration, its frozen-bootstrap replay agrees with the frozen code, and it changes no frozen rule.
CI job 6 also recomputes the whole file (`python scripts/analysis/cortex_seed_power.py --check`, about 25 s)."""
from __future__ import annotations

import importlib.util
import itertools
import json
import math
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
THR = S.THRESHOLDS["min_quality_gain_lower_bound"]
REPLIES = REC["frozen_rule"]["replies_per_item"]


def _items(arm):
    return {i["item_id"]: i for i in HELD["arms"][arm]["items"]}


def _minimal(power, n, full_stay=True):
    """n is the smallest size whose power reaches 0.8 and stays there for 25 more sizes."""
    if full_stay:
        assert all(power(m) >= P.TARGET_POWER for m in range(n, n + P.STAY + 1))
    else:
        assert power(n) >= P.TARGET_POWER
    assert power(n - 1) < P.TARGET_POWER


# ------------------------------------------------------------------ provenance
def test_it_changes_no_frozen_rule_and_cites_the_frozen_run():
    assert REC["changes_frozen_rule"] is False
    assert REC["freeze_manifest_sha256"] == HELD["freeze_manifest_sha256"]
    fr = REC["frozen_rule"]
    assert fr["min_quality_gain_lower_bound"] == THR and fr["bootstrap_B"] == S.BOOTSTRAP_B
    assert fr["declared_baselines"] == BASELINES == sorted(REC["baselines"])
    assert fr["lower_quantile_level"] == P.LOWER_Q and fr["target_power"] == P.TARGET_POWER
    assert REPLIES == 1 + len(P.A.COMMITTEE_ROLES) == 4


@pytest.mark.parametrize("name", BASELINES)
def test_observed_inputs_reproduce_from_the_frozen_result(name):
    obs, routed, base = REC["baselines"][name]["observed"], _items("routed_seed"), _items(name)
    assert obs["n"] == len(routed) == 42
    assert obs["routed_only_wins"] == sum(routed[k]["score"] - base[k]["score"] for k in routed)
    assert obs["frozen_lower_bound"] == HELD["arms"][name]["paired_gain_vs_routed"]["ci95"][0]
    assert obs["baseline_quality"] == HELD["arms"][name]["summary"]["mean_quality"]
    ends = REC["baselines"][name]["endpoints"]
    assert ends["harmful_failure"]["baseline_only"] == sum(1 for i in base.values() if i["critical"] or i["unsupported_certainty"])
    assert ends["critical_error"]["baseline_only"] == sum(1 for i in base.values() if i["critical"])
    assert not any(i["critical"] or i["unsupported_certainty"] for i in routed.values())


@pytest.mark.parametrize("endpoint,fails", [
    ("quality_gain", lambda i: i["score"] == 0.0),
    ("harmful_failure", lambda i: i["critical"] or i["unsupported_certainty"]),
    ("critical_error", lambda i: i["critical"]),
])
def test_the_overlap_of_the_two_baselines_failures_is_the_observed_one(endpoint, fails):
    a, c = (_items(n) for n in BASELINES)
    pat = REC["joint"][endpoint]["pattern"]
    assert pat["both"] == sum(1 for k in a if fails(a[k]) and fails(c[k]))
    assert pat["always_llm_only"] == sum(1 for k in a if fails(a[k]) and not fails(c[k]))
    assert pat["llm_committee_only"] == sum(1 for k in a if fails(c[k]) and not fails(a[k]))
    assert pat["rates"] == [pat["both"] / 42, pat["always_llm_only"] / 42, pat["llm_committee_only"] / 42]


# ------------------------------------------------------------------ the frozen bootstrap
@pytest.mark.parametrize("name", BASELINES)
def test_the_binomial_limit_agrees_with_the_frozen_bootstrap_on_the_observed_data(name):
    obs = REC["baselines"][name]["observed"]
    assert P.lower_bound(obs["n"], obs["routed_only_wins"]) == obs["frozen_lower_bound"] == obs["binomial_limit_lower_bound"]
    assert obs["mean_gain"] == obs["routed_only_wins"] / obs["n"]


def test_the_column_replay_is_the_frozen_bootstrap_exactly():
    rng = random.Random(7)
    for n in (42, 57):
        cols = P._frozen_columns(n)
        for k in (0, 3, 9):
            wins = rng.sample(range(n), k)
            values = [1.0 if i in wins else 0.0 for i in range(n)]
            frozen, _ = S._bootstrap_mean(values, random.Random(S.BOOTSTRAP_SEED + 1))
            assert P.frozen_lower_bound(cols, wins) == frozen


def test_the_frozen_crosscheck_reproduces_and_stays_near_the_binomial_limit():
    rec = REC["baselines"]["always_llm"]["quality_gain"]["frozen_crosscheck"]
    p = REC["baselines"]["always_llm"]["observed"]["mean_gain"]
    assert P.frozen_crosscheck(rec["n"], p, THR) == rec
    for name in BASELINES:
        chk = REC["baselines"][name]["quality_gain"]["frozen_crosscheck"]
        p = REC["baselines"][name]["observed"]["mean_gain"]
        rates = {int(k): v for k, v in chk["clear_rate_by_wins"].items()}
        assert chk["edges_settled"] and rates[min(rates)] == 0.0 and rates[max(rates)] == 1.0
        assert chk["binomial_limit_wins_needed"] == P.k_star(chk["n"], THR) == min(rates) + 2
        assert chk["binomial_limit_power"] == P.sf(chk["n"], chk["binomial_limit_wins_needed"], p)
        assert chk["placements_per_win_count"] == P.PLACEMENTS
        assert chk["frozen_rule_power"] == pytest.approx(
            math.fsum(P.pmf(chk["n"], k, p) * r for k, r in rates.items()) + P.sf(chk["n"], max(rates) + 1, p))
        assert abs(chk["frozen_rule_power"] - chk["binomial_limit_power"]) < 0.02


# ------------------------------------------------------------------ per-baseline sizes
@pytest.mark.parametrize("name", BASELINES)
def test_quality_sample_size_meets_its_definition(name):
    q, p = REC["baselines"][name]["quality_gain"], REC["baselines"][name]["observed"]["mean_gain"]
    power = lambda m: P.quality_power(m, p, THR)  # noqa: E731
    _minimal(power, q["items_for_80pct_power"])
    assert q["power_at_observed_n"] == power(42) and q["power_at_observed_n"] < 0.2
    assert q["attainable"] is (p > THR)
    assert q["wins_needed_at_that_n"] == P.k_star(q["items_for_80pct_power"], THR)
    assert q["baseline_replies_needed"] == q["items_for_80pct_power"] * REPLIES
    assert q["frozen_crosscheck"]["n"] == q["items_for_80pct_power"]


def _mcnemar_direct(n, pb, pr):
    """Independent formula: condition on the number of discordant items, then on who failed."""
    qb, qr = pb * (1 - pr), pr * (1 - pb)
    q = qb + qr
    total = 0.0
    for d in range(1, n + 1):
        w = P.pmf(n, d, q)
        if d > n * q and w < 1e-18:
            break
        b_min = next((b for b in range(d + 1) if P.sf(d, b, 0.5) <= P.ALPHA), None)
        if b_min is not None:
            total += w * P.sf(d, b_min, qb / q)
    return total


@pytest.mark.parametrize("name", BASELINES)
@pytest.mark.parametrize("endpoint", ["harmful_failure", "critical_error"])
def test_mcnemar_sizes_meet_their_definition(name, endpoint):
    e = REC["baselines"][name]["endpoints"][endpoint]
    assert e["observed_exact_one_sided_p"] == pytest.approx(0.5 ** e["baseline_only"])
    assert e["power_at_observed_n"] == pytest.approx(_mcnemar_direct(42, e["observed_rate_baseline"], 0.0), abs=1e-12)
    for pr, row in e["by_routed_failure_rate"].items():
        n = row["items_for_80pct_power"]
        power = lambda m, pr=float(pr): P.mcnemar_power(m, e["observed_rate_baseline"], pr)  # noqa: E731
        _minimal(power, n, full_stay=n < 400)
        assert power(n) == pytest.approx(_mcnemar_direct(n, e["observed_rate_baseline"], float(pr)), abs=1e-10)
        assert row["baseline_replies_needed"] == n * REPLIES


# ------------------------------------------------------------------ both baselines at once
def _joint_brute(n, q_both, q_a, q_c, r, t_a, t_c):
    """Full multinomial enumeration over the eight per-item outcomes (two baseline flags x routed flag)."""
    q_n = 1 - q_both - q_a - q_c
    outcomes = [((1, 1), q_both), ((1, 0), q_a), ((0, 1), q_c), ((0, 0), q_n)]
    cells = [(fa, fc, fr, q * (r if fr else 1 - r)) for (fa, fc), q in outcomes for fr in (0, 1)]
    total = 0.0
    for counts in itertools.product(range(n + 1), repeat=len(cells) - 1):
        last = n - sum(counts)
        if last < 0:
            continue
        counts = counts + (last,)
        prob = math.factorial(n)
        for (fa, fc, fr, p), k in zip(cells, counts):
            prob = prob / math.factorial(k) * p ** k
        ba = sum(k for (fa, fc, fr, _), k in zip(cells, counts) if fa and not fr)
        ca = sum(k for (fa, fc, fr, _), k in zip(cells, counts) if fr and not fa)
        bc = sum(k for (fa, fc, fr, _), k in zip(cells, counts) if fc and not fr)
        cc = sum(k for (fa, fc, fr, _), k in zip(cells, counts) if fr and not fc)
        if ba >= t_a(ca) and bc >= t_c(cc):
            total += prob
    return total


@pytest.mark.parametrize("args", [(6, 0.2, 0.1, 0.1, 0.1), (7, 0.15, 0.1, 0.0, 0.2), (6, 0.0, 0.3, 0.0, 0.05)])
def test_exact_joint_power_matches_brute_force_enumeration(args):
    n, qb, qa, qc, r = args
    t = lambda c: max(1, P.mcnemar_threshold(c) - 3)  # noqa: E731  (lower thresholds so small n is informative)
    assert P.joint_power(n, qb, qa, qc, r, t, t) == pytest.approx(_joint_brute(n, qb, qa, qc, r, t, t), abs=1e-12)


def test_joint_quality_size_meets_its_definition_and_is_binding():
    j = REC["joint"]["quality_gain"]
    rates = j["pattern"]["rates"]
    power = lambda m: P.joint_power(m, *rates, 0.0, lambda _: P.k_star(m, THR), lambda _: P.k_star(m, THR))  # noqa: E731
    _minimal(power, j["items_for_80pct_power"])
    assert j["power_at_observed_n"] == pytest.approx(power(42), abs=1e-12)
    assert j["items_for_80pct_power"] >= max(REC["baselines"][n]["quality_gain"]["items_for_80pct_power"] for n in BASELINES)
    assert j["baseline_replies_needed"] == j["items_for_80pct_power"] * REPLIES
    assert REC["binding"]["quality_gain_items"] == j["items_for_80pct_power"]


@pytest.mark.parametrize("endpoint", ["harmful_failure", "critical_error"])
def test_joint_mcnemar_sizes_meet_their_definition(endpoint):
    j = REC["joint"][endpoint]
    rates = j["pattern"]["rates"]
    t = P.mcnemar_threshold
    assert j["power_at_observed_n"] == pytest.approx(P.joint_power(42, *rates, 0.0, t, t), abs=1e-12)
    for pr, row in j["by_routed_failure_rate"].items():
        n = row["items_for_80pct_power"]
        power = lambda m, pr=float(pr): P.joint_power(m, *rates, pr, t, t)  # noqa: E731
        _minimal(power, n, full_stay=float(pr) == 0.0 and n < 400)
        single = max(REC["baselines"][b]["endpoints"][endpoint]["by_routed_failure_rate"][pr]["items_for_80pct_power"]
                     for b in BASELINES)
        assert n >= single
        assert row["power_at_largest_single_baseline_size"] == pytest.approx(power(single), abs=1e-12)
        assert row["baseline_replies_needed"] == n * REPLIES
    hf = REC["joint"]["harmful_failure"]["by_routed_failure_rate"]
    assert REC["binding"]["harmful_failure_items"] == hf["0.0"]["items_for_80pct_power"]
    assert REC["binding"]["harmful_failure_items_if_routed_fails_1pct"] == hf["0.01"]["items_for_80pct_power"]
