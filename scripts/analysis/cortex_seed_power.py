"""What evidence would decide the Seed Cortex 0.1.6 gain question (planning analysis, not a rule change).

Reads the frozen held-out result and computes, exactly, how many held-out items a *new* frozen version
would need before the unchanged exit rule could establish the routed seed's gain over each declared
baseline, if the next suite resembled this one (plug-in assumption). It also computes the same for a
harmful-failure endpoint (critical error or unsupported certainty) under an exact one-sided McNemar test.

Nothing here edits the frozen rule, the suites or any result. A different primary endpoint could only
apply to a future, separately frozen version and is a founder decision.

    python scripts/analysis/cortex_seed_power.py            # writes the JSON next to the held-out result
    python scripts/analysis/cortex_seed_power.py --check    # recomputes and compares with the recorded JSON
"""
from __future__ import annotations

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
N_MAX = 6000
# _bootstrap_mean returns the sorted bootstrap means at index int(0.025 * B): the (int(0.025 * B) + 1)-th order
# statistic. For a 0/1 paired difference the bootstrap mean is Binomial(n, k/n) / n, so the frozen lower bound is
# approximately that binomial's quantile at this level (exactly so as B grows).
LOWER_Q = (int(0.025 * S.BOOTSTRAP_B) + 1) / S.BOOTSTRAP_B


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
    """P(Binomial(n, p) >= k)."""
    return min(1.0, sum(pmf(n, j, p) for j in range(max(k, 0), n + 1)))


def lower_bound(n: int, k: int) -> float:
    """Large-B limit of the frozen paired-gain lower bound when k of n paired differences are 1 and the rest 0."""
    p, acc = k / n, 0.0
    for m in range(n + 1):
        acc += pmf(n, m, p)
        if acc >= LOWER_Q:
            return m / n
    return 1.0


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


def first_n(power_at, start: int = 10) -> int | None:
    """Smallest n whose power reaches TARGET_POWER and stays there for the next 25 n (discreteness guard)."""
    n = start
    while n <= N_MAX:
        if power_at(n) >= TARGET_POWER and all(power_at(m) >= TARGET_POWER for m in range(n + 1, n + 26)):
            return n
        n += 1 if n < 400 else 5
    return None


def _placements(n: int, k: int) -> dict[str, list[float]]:
    shuffled = [1.0] * k + [0.0] * (n - k)
    random.Random(S.BOOTSTRAP_SEED).shuffle(shuffled)
    return {"wins_first": [1.0] * k + [0.0] * (n - k), "wins_last": [0.0] * (n - k) + [1.0] * k,
            "wins_shuffled": shuffled}


def frozen_boundary(n: int, k_limit: int, threshold: float) -> dict:
    """The frozen _bootstrap_mean (B, seed and RNG stream exactly as paired_gain uses them) around the binomial
    boundary. Its Monte Carlo quantile depends on where the wins sit in item order, so three placements are tried;
    the frozen boundary is the fewest wins that clear the threshold in every placement."""
    rows, needed = {}, None
    for k in range(k_limit - 1, k_limit + 4):
        lows = {name: S._bootstrap_mean(v, random.Random(S.BOOTSTRAP_SEED + 1))[0]
                for name, v in _placements(n, k).items()}
        rows[str(k)] = {"frozen_lower_bounds": lows, "clears_in_every_placement": all(x > threshold for x in lows.values())}
        if needed is None and rows[str(k)]["clears_in_every_placement"]:
            needed = k
    return {"n": n, "binomial_limit_wins_needed": k_limit, "frozen_wins_needed": needed, "by_wins": rows}


def mcnemar_power(n: int, pb: float, pr: float) -> float:
    """Power of the exact one-sided McNemar test (baseline-only failures in excess) at ALPHA, independent arms."""
    q_b, q_r = pb * (1 - pr), pr * (1 - pb)
    q = q_b + q_r
    if q == 0:
        return 0.0
    total = 0.0
    for d in range(1, n + 1):
        pd = pmf(n, d, q)
        if pd < 1e-15 and d > n * q:
            break
        crit = next((b for b in range(d + 1) if sf(d, b, 0.5) <= ALPHA), None)
        if crit is not None:
            total += pd * sf(d, crit, q_b / q)
    return total


def mcnemar_p(b: int, c: int) -> float:
    """Exact one-sided McNemar p-value: b baseline-only failures, c routed-only failures."""
    return sf(b + c, b, 0.5) if b + c else 1.0


def analyse() -> dict:
    held = json.loads((EVIDENCE / "heldout-results.json").read_text(encoding="utf-8"))
    arms = held["arms"]
    routed = {i["item_id"]: i for i in arms["routed_seed"]["items"]}
    n_obs = len(routed)
    harmful = lambda i: bool(i.get("critical") or i.get("unsupported_certainty"))  # noqa: E731
    threshold = S.THRESHOLDS["min_quality_gain_lower_bound"]
    replies_per_item = 1 + len(A.COMMITTEE_ROLES)
    out = {
        "schema": "cortex-seed-power/0.1",
        "source": "tests/evidence/cortex-seed-v0.1.6/heldout-results.json",
        "freeze_manifest_sha256": held["freeze_manifest_sha256"],
        "changes_frozen_rule": False,
        "purpose": "how many held-out items a future frozen version needs before its exit decision can go either way",
        "assumptions": [
            "plug-in: the next suite's per-item failure rates equal this suite's observed rates",
            "paired differences are 0/1 as observed (the routed seed failed no item); a routed failure lowers power",
            "quality: the frozen bootstrap lower bound is replaced by its large-B binomial limit and spot-checked "
            "against the frozen _bootstrap_mean below",
            "harmful failure = critical or unsupported certainty; exact one-sided McNemar at alpha 0.05, arms "
            "treated as independent per item",
        ],
        "frozen_rule": {"min_quality_gain_lower_bound": threshold, "bootstrap_B": S.BOOTSTRAP_B,
                        "lower_quantile_level": LOWER_Q, "target_power": TARGET_POWER},
        "baselines": {},
    }
    for name in S.THRESHOLDS["declared_baselines"]:
        base = {i["item_id"]: i for i in arms[name]["items"]}
        diffs = [routed[k]["score"] - base[k]["score"] for k in sorted(routed)]
        if any(d not in (0.0, 1.0) for d in diffs):
            raise SystemExit(f"{name}: non-binary paired differences; the binomial limit does not apply")
        wins = int(sum(diffs))
        p = wins / n_obs
        n80 = first_n(lambda n: quality_power(n, p, threshold))
        frozen_check = frozen_boundary(n80, k_star(n80, threshold), threshold) if n80 is not None else None
        if frozen_check is not None and frozen_check["frozen_wins_needed"] is not None:
            frozen_check["power_with_frozen_boundary"] = sf(n80, frozen_check["frozen_wins_needed"], p)
        crit_b = sum(1 for k in routed if base[k].get("critical") and not routed[k].get("critical"))
        crit_r = sum(1 for k in routed if routed[k].get("critical") and not base[k].get("critical"))
        harm_b = sum(1 for k in routed if harmful(base[k]) and not harmful(routed[k]))
        harm_r = sum(1 for k in routed if harmful(routed[k]) and not harmful(base[k]))
        endpoints = {}
        for label, b, c in (("harmful_failure", harm_b, harm_r), ("critical_error", crit_b, crit_r)):
            pb = b / n_obs
            sens = {}
            for pr in (0.0, 0.01):
                n_needed = first_n(lambda n: mcnemar_power(n, pb, pr))
                sens[str(pr)] = {"items_for_80pct_power": n_needed,
                                 "baseline_replies_needed": None if n_needed is None else n_needed * replies_per_item}
            endpoints[label] = {"baseline_only": b, "routed_only": c, "observed_rate_baseline": pb,
                                "observed_exact_one_sided_p": mcnemar_p(b, c),
                                "power_at_observed_n": mcnemar_power(n_obs, pb, 0.0), "by_routed_failure_rate": sens}
        out["baselines"][name] = {
            "observed": {"n": n_obs, "routed_only_wins": wins, "mean_gain": p,
                         "frozen_lower_bound": arms[name]["paired_gain_vs_routed"]["ci95"][0],
                         "binomial_limit_lower_bound": lower_bound(n_obs, wins),
                         "baseline_quality": arms[name]["summary"]["mean_quality"]},
            "quality_gain": {
                "attainable": p > threshold,
                "headroom_over_threshold": p - threshold,
                "power_at_observed_n": quality_power(n_obs, p, threshold),
                "items_for_80pct_power": n80,
                "baseline_replies_needed": None if n80 is None else n80 * replies_per_item,
                "wins_needed_at_that_n": None if n80 is None else k_star(n80, threshold),
                "frozen_bootstrap_check": frozen_check,
            },
            "endpoints": endpoints,
        }
    q = {k: v["quality_gain"]["items_for_80pct_power"] for k, v in out["baselines"].items()}
    h = {k: v["endpoints"]["harmful_failure"]["by_routed_failure_rate"]["0.0"]["items_for_80pct_power"]
         for k, v in out["baselines"].items()}
    fz = {k: (v["quality_gain"]["frozen_bootstrap_check"] or {}).get("power_with_frozen_boundary")
          for k, v in out["baselines"].items()}
    out["binding"] = {
        "quality_gain_items": max(q.values()) if None not in q.values() else None,
        "quality_gain_power_there_with_frozen_boundary": fz[max(q, key=lambda k: q[k] or 0)],
        "harmful_failure_items": max(h.values()) if None not in h.values() else None,
        "reading": ("the frozen quality rule needs a lower bound above 0.05 while the committee leaves 0.071 of "
                    "headroom, so under the plug-in rates it needs a suite more than an order of magnitude larger "
                    "than 42 items; the harmful-failure endpoint the seed was built to reduce needs far fewer. "
                    "Neither number is a result; both assume the next suite resembles this one."),
    }
    return out


def _differences(recorded, fresh, path="$"):
    """Exact for structure, integers, strings and booleans; floats to 1e-9 relative (libm may differ in the last bit)."""
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
    print(json.dumps({k: v["quality_gain"] | {"harm": v["endpoints"]["harmful_failure"]}
                      for k, v in result["baselines"].items()}, indent=1))
    print(json.dumps(result["binding"], indent=1))


if __name__ == "__main__":
    main()
