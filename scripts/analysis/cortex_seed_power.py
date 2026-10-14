"""What evidence would decide the Seed Cortex 0.1.6 gain question (planning analysis, not a rule change).

Reads the frozen held-out result and computes how many held-out items a *new* frozen version would need before
the unchanged exit rule could establish the routed seed's gain, if the next suite resembled this one (plug-in
assumption). The frozen rule must clear *each* declared baseline (cortex/evaluation/scoring.py THRESHOLDS), so the
deciding sizes are joint: both baselines at once, with the per-item overlap of their failures taken from the run.
The same is computed for a harmful-failure endpoint (critical error or unsupported certainty) and a critical-error
endpoint under an exact one-sided McNemar test per baseline.

Nothing here edits the frozen rule, the suites or any result. A different primary endpoint could only apply to a
future, separately frozen version and is a founder decision.

    python scripts/analysis/cortex_seed_power.py            # writes power-analysis.json next to the held-out result
    python scripts/analysis/cortex_seed_power.py --check    # recomputes and compares with the recorded JSON
"""
from __future__ import annotations

import functools
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from cortex.evaluation import arms as A  # noqa: E402
from cortex.evaluation import scoring as S  # noqa: E402

EVIDENCE = ROOT / "tests/evidence/cortex-seed-v0.1.6"
OUT = EVIDENCE / "power-analysis.json"
TARGET_POWER = 0.8
ALPHA = 0.05
STAY = 25          # a size counts only if power stays at or above target for the next STAY sizes (discreteness)
N_MAX = 6000
ROUTED_FAILURE_RATES = (0.0, 0.01)
PLACEMENTS = 400   # random item orders per win count in the frozen-bootstrap cross-check
PLACEMENT_SEED = 20261014
# _bootstrap_mean returns the sorted bootstrap means at index int(0.025 * B): the (int(0.025 * B) + 1)-th order
# statistic. For a 0/1 paired difference each resample's count of wins is Binomial(n, k/n), so as B grows the frozen
# lower bound tends to that binomial's quantile; LOWER_Q is the level of the order statistic the frozen code reads.
# The B = 2000 Monte Carlo noise is measured below (frozen_crosscheck), not assumed away.
LOWER_Q = (int(0.025 * S.BOOTSTRAP_B) + 1) / S.BOOTSTRAP_B


# ---------------------------------------------------------------- binomial primitives (correctly rounded sums)
def _logpmf(n: int, k: int, p: float) -> float:
    if p <= 0.0:
        return 0.0 if k == 0 else -math.inf
    if p >= 1.0:
        return 0.0 if k == n else -math.inf
    return (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
            + k * math.log(p) + (n - k) * math.log1p(-p))


def pmf(n: int, k: int, p: float) -> float:
    return math.exp(_logpmf(n, k, p))


def sf(n: int, k: int, p: float) -> float:
    """P(Binomial(n, p) >= k). math.fsum keeps the result identical across Python versions (3.12 changed sum())."""
    return min(1.0, math.fsum(pmf(n, j, p) for j in range(max(k, 0), n + 1)))


@functools.lru_cache(maxsize=None)
def _pmf_list(m: int, p: float) -> tuple[float, ...]:
    """Binomial(m, p) pmf from 0 until the remaining mass is negligible (recurrence, no cancellation)."""
    if m <= 0 or p <= 0.0:
        return (1.0,)
    out = [math.exp(m * math.log1p(-p))]
    ratio = p / (1.0 - p)
    k = 0
    while k < m and (k <= m * p or out[-1] > 1e-18):
        out.append(out[-1] * (m - k) / (k + 1) * ratio)
        k += 1
    return tuple(out)


@functools.lru_cache(maxsize=None)
def _tail(m: int, p: float, t: int) -> float:
    """P(Binomial(m, p) >= t)."""
    if t <= 0:
        return 1.0
    pmfs = _pmf_list(m, p)
    return max(0.0, 1.0 - math.fsum(pmfs[:t])) if t < len(pmfs) else 0.0


# ---------------------------------------------------------------- the frozen quality rule (one baseline)
def lower_bound(n: int, k: int) -> float:
    """Large-B limit of the frozen paired-gain lower bound when k of n paired differences are 1 and the rest 0."""
    p, acc = k / n, 0.0
    for m in range(n + 1):
        acc += pmf(n, m, p)
        if acc >= LOWER_Q:
            return m / n
    return 1.0


@functools.lru_cache(maxsize=None)
def k_star(n: int, threshold: float) -> int | None:
    """Fewest routed-only wins out of n for which the lower bound clears the threshold."""
    lo, hi = math.floor(threshold * n), n
    if lower_bound(n, hi) <= threshold:
        return None
    while lo < hi:  # lower_bound is non-decreasing in k
        mid = (lo + hi) // 2
        if lower_bound(n, mid) > threshold:
            hi = mid
        else:
            lo = mid + 1
    return lo


def quality_power(n: int, p: float, threshold: float) -> float:
    k = k_star(n, threshold)
    return 0.0 if k is None else sf(n, k, p)


# ---------------------------------------------------------------- exact one-sided McNemar (one baseline)
@functools.lru_cache(maxsize=None)
def mcnemar_threshold(c: int) -> int:
    """Fewest baseline-only failures b that reject at ALPHA when the routed seed alone failed c items."""
    b = 0
    while sf(b + c, b, 0.5) > ALPHA:
        b += 1
    return b


def mcnemar_p(b: int, c: int) -> float:
    """Exact one-sided McNemar p-value: b baseline-only failures, c routed-only failures."""
    return sf(b + c, b, 0.5) if b + c else 1.0


def mcnemar_power(n: int, pb: float, pr: float) -> float:
    """Power against one baseline: per item the baseline fails with pb and the routed seed with pr, independently."""
    return joint_power(n, 0.0, pb, 0.0, pr, mcnemar_threshold, lambda c: 0)


# ---------------------------------------------------------------- both baselines at once, exact
def joint_power(n: int, q_both: float, q_a: float, q_c: float, r: float, t_a, t_c) -> float:
    """P(the test clears against baseline A AND baseline C) over n items.

    Per item the baselines fail together with q_both, A alone with q_a, C alone with q_c (the overlap observed in the
    frozen run), and the routed seed fails independently with r. Against a baseline, b counts items it failed and the
    routed seed did not, c the reverse; the test clears when b >= t(c). Exact: nested conditional binomials over the
    six counts that matter, with negligible tails cut at 1e-18."""
    q_n = 1.0 - q_both - q_a - q_c
    px1, px2, px3 = q_both * (1 - r), q_a * (1 - r), q_c * (1 - r)
    py1, py2, py3 = q_n * r, q_a * r, q_c * r          # routed fails: neither / A also / C also
    total = []
    for y2, w2 in enumerate(_pmf_list(n, py2)):
        rest2 = 1.0 - py2
        for y3, w3 in enumerate(_pmf_list(n - y2, py3 / rest2 if rest2 > 0 else 0.0)):
            rest3 = rest2 - py3
            for y1, w1 in enumerate(_pmf_list(n - y2 - y3, py1 / rest3 if rest3 > 0 else 0.0)):
                wy = w2 * w3 * w1
                if wy < 1e-18:
                    continue
                m = n - y1 - y2 - y3
                rest = rest3 - py1
                need_a, need_c = t_a(y1 + y3), t_c(y1 + y2)
                s = []
                for x1, v1 in enumerate(_pmf_list(m, px1 / rest if rest > 0 else 0.0)):
                    rest_1 = rest - px1
                    p2 = px2 / rest_1 if rest_1 > 0 else 0.0
                    if px3 == 0.0:      # C never fails alone: its test depends on x1 only, A's on the tail of x2
                        if x1 >= need_c:
                            s.append(v1 * _tail(m - x1, p2, need_a - x1))
                        continue
                    for x2, v2 in enumerate(_pmf_list(m - x1, p2)):
                        if x1 + x2 < need_a:
                            continue
                        rest_2 = rest_1 - px2
                        p3 = px3 / rest_2 if rest_2 > 0 else 0.0
                        s.append(v1 * v2 * _tail(m - x1 - x2, p3, need_c - x1))
                total.append(wy * math.fsum(s))
    return min(1.0, math.fsum(total))


def first_n(power_at, start: int = 10) -> int | None:
    """Smallest n >= start whose power reaches TARGET_POWER and stays there for the next STAY sizes."""
    power_at = functools.lru_cache(maxsize=None)(power_at)
    n = start
    while n <= N_MAX:
        if all(power_at(m) >= TARGET_POWER for m in range(n, n + STAY + 1)):
            return n
        n += 1
    return None


# ---------------------------------------------------------------- the frozen bootstrap itself, by item order
def _frozen_columns(n: int) -> list[list[int]]:
    """How often each item index is drawn in each of the B resamples, replaying the exact RNG stream that
    scoring.paired_gain gives _bootstrap_mean (the stream depends on n only, never on the values)."""
    rng = random.Random(S.BOOTSTRAP_SEED + 1)
    cols = [[0] * S.BOOTSTRAP_B for _ in range(n)]
    for b in range(S.BOOTSTRAP_B):
        for _ in range(n):
            cols[rng.randrange(n)][b] += 1
    return cols


def frozen_lower_bound(cols: list[list[int]], wins: list[int]) -> float:
    """The frozen _bootstrap_mean lower bound for a 0/1 vector whose 1s sit at the indices in `wins`."""
    n = len(cols)
    counts = sorted(map(sum, zip(*(cols[i] for i in wins)))) if wins else [0] * S.BOOTSTRAP_B
    return counts[int(0.025 * S.BOOTSTRAP_B)] / n


def frozen_crosscheck(n: int, p: float, threshold: float) -> dict:
    """At size n, the share of random item orders in which k wins clear the frozen rule, for k around the
    binomial-limit boundary, and the frozen rule's power that follows (pmf-weighted)."""
    cols = _frozen_columns(n)
    rng = random.Random(PLACEMENT_SEED + n)
    ks = k_star(n, threshold)
    rates = {}
    for k in range(ks - 2, ks + 3):
        clear = sum(frozen_lower_bound(cols, rng.sample(range(n), k)) > threshold for _ in range(PLACEMENTS))
        rates[k] = clear / PLACEMENTS
    lo, hi = min(rates), max(rates)
    power = math.fsum(pmf(n, k, p) * r for k, r in rates.items()) + sf(n, hi + 1, p)
    return {"n": n, "binomial_limit_wins_needed": ks, "placements_per_win_count": PLACEMENTS,
            "clear_rate_by_wins": {str(k): r for k, r in rates.items()},
            "edges_settled": rates[lo] == 0.0 and rates[hi] == 1.0,
            "frozen_rule_power": power, "binomial_limit_power": sf(n, ks, p)}


# ---------------------------------------------------------------- the analysis
def _pattern(routed, base_a, base_c, fails) -> dict:
    keys = sorted(routed)
    both = sum(1 for k in keys if fails(base_a[k]) and fails(base_c[k]))
    only_a = sum(1 for k in keys if fails(base_a[k]) and not fails(base_c[k]))
    only_c = sum(1 for k in keys if fails(base_c[k]) and not fails(base_a[k]))
    n = len(keys)
    return {"both": both, "always_llm_only": only_a, "llm_committee_only": only_c,
            "rates": [both / n, only_a / n, only_c / n]}


def analyse() -> dict:
    held = json.loads((EVIDENCE / "heldout-results.json").read_text(encoding="utf-8"))
    arms = held["arms"]
    names = S.THRESHOLDS["declared_baselines"]
    if names != ["always_llm", "llm_committee"]:
        raise SystemExit("the analysis is written for the two declared baselines always_llm and llm_committee")
    routed = {i["item_id"]: i for i in arms["routed_seed"]["items"]}
    base = {name: {i["item_id"]: i for i in arms[name]["items"]} for name in names}
    n_obs = len(routed)
    if any(routed[k]["critical"] or routed[k]["unsupported_certainty"] or routed[k]["score"] != 1.0 for k in routed):
        raise SystemExit("the routed seed failed an item; the 0/1 plug-in below does not apply")
    threshold = S.THRESHOLDS["min_quality_gain_lower_bound"]
    replies_per_item = 1 + len(A.COMMITTEE_ROLES)
    harmful = lambda i: bool(i["critical"] or i["unsupported_certainty"])  # noqa: E731
    endpoints = {"harmful_failure": harmful, "critical_error": lambda i: bool(i["critical"])}
    out = {
        "schema": "cortex-seed-power/0.2",
        "source": "tests/evidence/cortex-seed-v0.1.6/heldout-results.json",
        "freeze_manifest_sha256": held["freeze_manifest_sha256"],
        "changes_frozen_rule": False,
        "purpose": "how many held-out items a future frozen version needs before its exit decision can go either way",
        "assumptions": [
            "plug-in: the next suite's per-item failure rates, and the overlap between the two baselines' failures, "
            "equal this suite's",
            "the routed seed failed no item here; the quality analysis keeps that (0/1 paired differences); the McNemar "
            "endpoints also show a routed harmful-failure rate of 1%",
            "quality: the frozen bootstrap lower bound is taken at its large-B binomial limit; frozen_crosscheck replays "
            "the frozen bootstrap itself over random item orders at the deciding sizes",
            "McNemar: exact one-sided test at alpha 0.05 against each baseline; the routed seed's failures are "
            "independent of the baselines'",
            "every size is the smallest n whose power reaches 0.8 and stays there for the next 25 sizes, scanned one "
            "item at a time",
        ],
        "frozen_rule": {"min_quality_gain_lower_bound": threshold, "bootstrap_B": S.BOOTSTRAP_B,
                        "lower_quantile_level": LOWER_Q, "target_power": TARGET_POWER,
                        "declared_baselines": names, "replies_per_item": replies_per_item},
        "baselines": {},
        "joint": {},
    }
    # ---- per baseline
    for name in names:
        wins = sum(1 for k in routed if routed[k]["score"] - base[name][k]["score"] == 1.0)
        if any(routed[k]["score"] - base[name][k]["score"] not in (0.0, 1.0) for k in routed):
            raise SystemExit(f"{name}: non-binary paired differences; the binomial limit does not apply")
        p = wins / n_obs
        n80 = first_n(lambda n, p=p: quality_power(n, p, threshold))
        row = {
            "observed": {"n": n_obs, "routed_only_wins": wins, "mean_gain": p,
                         "frozen_lower_bound": arms[name]["paired_gain_vs_routed"]["ci95"][0],
                         "binomial_limit_lower_bound": lower_bound(n_obs, wins),
                         "baseline_quality": arms[name]["summary"]["mean_quality"]},
            "quality_gain": {"attainable": p > threshold, "power_at_observed_n": quality_power(n_obs, p, threshold),
                             "items_for_80pct_power": n80, "wins_needed_at_that_n": k_star(n80, threshold),
                             "baseline_replies_needed": n80 * replies_per_item,
                             "frozen_crosscheck": frozen_crosscheck(n80, p, threshold)},
            "endpoints": {},
        }
        for label, fails in endpoints.items():
            b = sum(1 for k in routed if fails(base[name][k]))
            pb = b / n_obs
            by_rate = {}
            for pr in ROUTED_FAILURE_RATES:
                n_needed = first_n(lambda n, pb=pb, pr=pr: mcnemar_power(n, pb, pr))
                by_rate[str(pr)] = {"items_for_80pct_power": n_needed,
                                    "baseline_replies_needed": n_needed * replies_per_item}
            row["endpoints"][label] = {"baseline_only": b, "routed_only": 0, "observed_rate_baseline": pb,
                                       "observed_exact_one_sided_p": mcnemar_p(b, 0),
                                       "power_at_observed_n": mcnemar_power(n_obs, pb, 0.0),
                                       "by_routed_failure_rate": by_rate}
        out["baselines"][name] = row
    # ---- both baselines at once (what the frozen rule requires)
    a, c = names
    qual = _pattern(routed, base[a], base[c], lambda i: i["score"] == 0.0)
    start = max(out["baselines"][x]["quality_gain"]["items_for_80pct_power"] for x in names)

    def q_joint(n):
        return joint_power(n, *qual["rates"], 0.0, lambda _: k_star(n, threshold), lambda _: k_star(n, threshold))
    nq = first_n(q_joint, start)
    out["joint"]["quality_gain"] = {"pattern": qual, "power_at_observed_n": q_joint(n_obs),
                                    "items_for_80pct_power": nq, "baseline_replies_needed": nq * replies_per_item}
    for label, fails in endpoints.items():
        pat = _pattern(routed, base[a], base[c], fails)
        by_rate = {}
        for pr in ROUTED_FAILURE_RATES:
            start = max(out["baselines"][x]["endpoints"][label]["by_routed_failure_rate"][str(pr)]["items_for_80pct_power"]
                        for x in names)
            n_needed = first_n(lambda n, pr=pr: joint_power(n, *pat["rates"], pr, mcnemar_threshold, mcnemar_threshold),
                               start)
            by_rate[str(pr)] = {"items_for_80pct_power": n_needed, "baseline_replies_needed": n_needed * replies_per_item,
                                "power_at_largest_single_baseline_size": joint_power(
                                    start, *pat["rates"], pr, mcnemar_threshold, mcnemar_threshold)}
        out["joint"][label] = {"pattern": pat,
                               "power_at_observed_n": joint_power(n_obs, *pat["rates"], 0.0, mcnemar_threshold,
                                                                  mcnemar_threshold),
                               "by_routed_failure_rate": by_rate}
    out["binding"] = {
        "quality_gain_items": out["joint"]["quality_gain"]["items_for_80pct_power"],
        "harmful_failure_items": out["joint"]["harmful_failure"]["by_routed_failure_rate"]["0.0"]["items_for_80pct_power"],
        "harmful_failure_items_if_routed_fails_1pct":
            out["joint"]["harmful_failure"]["by_routed_failure_rate"]["0.01"]["items_for_80pct_power"],
        "reading": ("the frozen rule must clear both baselines; under the plug-in rates the quality rule needs a suite "
                    "more than an order of magnitude larger than 42 items, while the harmful-failure endpoint the seed "
                    "was built to reduce needs about a tenth of that. Neither number is a result; both assume the next "
                    "suite resembles this one."),
    }
    return out


def _differences(recorded, fresh, path="$"):
    """Exact for structure, integers, strings and booleans; floats to 1e-9 relative."""
    if isinstance(recorded, dict) and isinstance(fresh, dict):
        if recorded.keys() != fresh.keys():
            yield f"{path}: keys differ"
            return
        for k in recorded:
            yield from _differences(recorded[k], fresh[k], f"{path}.{k}")
    elif isinstance(recorded, list) and isinstance(fresh, list):
        if len(recorded) != len(fresh):
            yield f"{path}: lengths differ"
            return
        for i, (a, b) in enumerate(zip(recorded, fresh)):
            yield from _differences(a, b, f"{path}[{i}]")
    elif isinstance(recorded, float) and isinstance(fresh, float):
        if not math.isclose(recorded, fresh, rel_tol=1e-9, abs_tol=1e-12):
            yield f"{path}: {recorded} != {fresh}"
    elif type(recorded) is not type(fresh) or recorded != fresh:
        yield f"{path}: {recorded!r} != {fresh!r}"


def main() -> None:
    result = analyse()
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        diffs = list(_differences(json.loads(OUT.read_text(encoding="utf-8")), json.loads(text)))
        if diffs:
            raise SystemExit("power-analysis.json does not match a fresh computation: " + "; ".join(diffs[:10]))
        print("power-analysis.json reproduces")
        return
    OUT.write_text(text, encoding="utf-8")
    summary = {name: {"quality": {k: v for k, v in row["quality_gain"].items() if k != "frozen_crosscheck"},
                      "crosscheck": row["quality_gain"]["frozen_crosscheck"],
                      "endpoints": row["endpoints"]} for name, row in result["baselines"].items()}
    print(json.dumps(summary, indent=1))
    print(json.dumps(result["joint"], indent=1))
    print(json.dumps(result["binding"], indent=1))


if __name__ == "__main__":
    main()
