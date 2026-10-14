"""The recorded power analysis (`tests/evidence/cortex-seed-v0.1.6/power-analysis.json`) reads the frozen
held-out result faithfully, its sample sizes satisfy their own definitions, its exact joint power agrees with
brute-force enumeration, every recorded frozen-bootstrap replay recomputes exactly, the report quotes its numbers
faithfully, and it changes no frozen rule. Prose fields are not checked here; CI job 6 recomputes the whole file
(`python scripts/analysis/cortex_seed_power.py --check`)."""
from __future__ import annotations

import importlib.util
import itertools
import json
import math
import random
import re
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
    assert REC["schema"] == "cortex-seed-power/0.3" and REC["source"] == "tests/evidence/cortex-seed-v0.1.6/heldout-results.json"
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
    assert all(e["routed_only"] == 0 for e in ends.values())


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


@pytest.mark.parametrize("name", BASELINES)
def test_every_recorded_frozen_replay_recomputes_exactly(name):
    q = REC["baselines"][name]["quality_gain"]
    p = REC["baselines"][name]["observed"]["mean_gain"]
    n80 = q["items_for_80pct_power"]
    steps = [n for n in range(n80 + 1, n80 + P.STAY + 1) if P.k_star(n, THR) > P.k_star(n - 1, THR)]
    assert [c["n"] for c in q["frozen_crosscheck_at_steps"]] == steps
    for chk in [q["frozen_crosscheck"]] + q["frozen_crosscheck_at_steps"]:
        assert P.frozen_crosscheck(chk["n"], p, THR) == chk
        rates = {int(k): v for k, v in chk["clear_rate_by_wins"].items()}
        assert chk["edges_settled"] and rates[min(rates)] == 0.0 and rates[max(rates)] == 1.0
        assert abs(chk["frozen_rule_power"] - chk["binomial_limit_power"]) < 0.02


def test_the_packed_replay_equals_the_plain_replay():
    rng = random.Random(11)
    for n in (42, 130):
        cols = P._frozen_columns(n)
        packed = P._packed(cols)
        for k in (1, 5, 17):
            wins = rng.sample(range(n), k)
            assert P._lower_from_packed(packed, wins, n) == P.frozen_lower_bound(cols, wins)


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


# ------------------------------------------------------------------ robustness (second post-run review)
def test_the_binomial_pmf_does_not_underflow_for_large_counts():
    for m, p in ((1500, 0.4), (3000, 0.35), (6000, 0.2)):
        pmfs = P._pmf_list(m, p)
        # lgamma near m carries ~1e-12 absolute error, which the mode anchor passes on to every term
        assert math.fsum(pmfs) == pytest.approx(1.0, abs=1e-9)
        for t in (int(m * p) - 40, int(m * p), int(m * p) + 40):
            assert P._tail(m, p, t) == pytest.approx(P.sf(m, t, p), abs=1e-9)
    assert P.joint_power(1500, 0.4, 0.0, 0.0, 0.0, lambda c: 30, lambda c: 30) == pytest.approx(1.0, abs=1e-9)
    assert P.joint_power(1500, 0.0, 0.4, 0.0, 0.0, lambda c: 620, lambda c: 0) == pytest.approx(P.sf(1500, 620, 0.4), abs=1e-9)


def test_certain_failure_does_not_crash():
    assert P._pmf_list(5, 1.0) == (0.0, 0.0, 0.0, 0.0, 0.0, 1.0)
    assert P.joint_power(5, 1.0, 0.0, 0.0, 0.0, lambda c: 3, lambda c: 3) == 1.0


def test_an_unattainable_baseline_is_recorded_not_crashed():
    q = P.quality_section(2 / 42, THR, REPLIES, 42)
    assert q["attainable"] is False and q["items_for_80pct_power"] is None
    assert q["baseline_replies_needed"] is None and q["frozen_crosscheck"] is None and q["frozen_crosscheck_at_steps"] == []
    assert P.mcnemar_size(0.0, 0.0, REPLIES) == {"items_for_80pct_power": None, "baseline_replies_needed": None}


# ------------------------------------------------------------------ the report quotes these numbers
def _section(path, marker):
    text = (ROOT / path).read_text(encoding="utf-8")
    return " ".join(text.split(marker, 1)[1].split())


def test_the_report_quotes_the_recorded_numbers():
    sec = _section("docs/cortex/SEED_EXPERIMENT_REPORT.md", "## 0.1.6 — the decisive test")
    b, j, bind = REC["baselines"], REC["joint"], REC["binding"]
    a, c = (b[n] for n in BASELINES)
    pct = lambda x: f"{round(100 * x)}%"  # noqa: E731
    assert (f"the frozen rule had {pct(a['quality_gain']['power_at_observed_n'])} power to establish the gain over "
            f"`always_llm`, {pct(c['quality_gain']['power_at_observed_n'])} over `llm_committee`, and "
            f"{pct(j['quality_gain']['power_at_observed_n'])} over both at once") in sec
    q = j["quality_gain"]
    assert (f"| quality gain, frozen rule unchanged (binomial-limit sizes) | {a['quality_gain']['items_for_80pct_power']:,} items | "
            f"{c['quality_gain']['items_for_80pct_power']:,} items | **{q['items_for_80pct_power']:,} items** | "
            f"{q['baseline_replies_needed']:,} |") in sec
    rows = [("harmful failure (critical or unsupported certainty), exact one-sided McNemar, alpha 0.05", "harmful_failure", "0.0"),
            ("the same, if the seed itself failed harmfully on 1% of items", "harmful_failure", "0.01"),
            ("critical error only", "critical_error", "0.0")]
    for label, e, pr in rows:
        sizes = [x["endpoints"][e]["by_routed_failure_rate"][pr]["items_for_80pct_power"] for x in (a, c)]
        jr = j[e]["by_routed_failure_rate"][pr]
        assert (f"| {label} | {sizes[0]:,} | {sizes[1]:,} | **{jr['items_for_80pct_power']:,}** | "
                f"{jr['baseline_replies_needed']:,} |") in sec, label
    fa, fc = a["quality_gain"]["frozen_crosscheck"], c["quality_gain"]["frozen_crosscheck"]
    k = fc["binomial_limit_wins_needed"]
    assert (f"its power is {fa['frozen_rule_power']:.3f} at {fa['n']:,} items and {fc['frozen_rule_power']:.3f} at "
            f"{fc['n']:,}, where {k} wins clear in {100 * fc['clear_rate_by_wins'][str(k)]:.1f}% of item orders") in sec
    step = c["quality_gain"]["frozen_crosscheck_at_steps"][0]
    assert (f"At {step['n']:,} items, where the wins needed step from {step['binomial_limit_wins_needed'] - 1} to "
            f"{step['binomial_limit_wins_needed']}, it is {step['frozen_rule_power']:.4f} against "
            f"{step['binomial_limit_power']:.3f} at the limit") in sec
    hf = j["harmful_failure"]["by_routed_failure_rate"]["0.0"]
    assert f"the chance of clearing both is {hf['power_at_largest_single_baseline_size']:.2f}" in sec
    assert f"hence {bind['harmful_failure_items']}" in sec
    assert (f"at least {bind['harmful_failure_items']} items ({bind['harmful_failure_items_if_routed_fails_1pct']} if the "
            f"seed itself may fail harmfully on 1% of items)") in sec
    assert f"{bind['quality_gain_items']:,} at the binomial limit" in sec


def test_the_adr_and_intent_record_quote_the_same_sizes():
    bind = REC["binding"]
    adr = _section("docs/decisions/ADR-20261013-polyintelligence-seed-genome-convergence.md", "Addendum, 2026-10-14")
    intent = json.loads((ROOT / "docs/intent/INTENT-20261013-polyintelligence-seed-genome-v0.1.json").read_text(encoding="utf-8"))
    for text in (adr, intent["next_review_trigger"]):
        assert f"{bind['quality_gain_items']:,} at the binomial limit" in text
        assert f"{bind['harmful_failure_items']} items" in text
        assert re.search(rf"\b{bind['harmful_failure_items_if_routed_fails_1pct']} if the seed itself fail", text)
