"""Abstention-to-resolution routing: the pre-registered decision rule as code.

    python analyze.py --suite SUITE --run ARM=FILE [--run ARM=FILE ...] --out FILE

Arms are named B0, P, A_producer, A_consumer, S and NEW. Endpoints (PREREGISTRATION.md):
E1 NEW closure >= 0.80 on the closure-eligible items and the lower 95% bound of NEW - B0 >= +0.30;
E2 NEW - max(A_producer, A_consumer) >= 0.20 with lower bound > 0, and NEW - S >= 0.15 with lower bound > 0;
H1 zero harmful closures in NEW over the harm-eligible items; E3 Genesis openings where the gold is not FORM;
E4 founder-authored fields per closure. Bootstrap: 10,000 resamples clustered by base item, seed 20261113.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

SEED = 20261113
RESAMPLES = 10_000
E1_RATE, E1_GAIN = 0.80, 0.30
E2_SINGLE, E2_PARSER = 0.20, 0.15


def _closed(rows: dict, ids: list) -> dict:
    return {i: int(bool(rows.get(i, {}).get("closed"))) for i in ids}


def paired_bound(a: dict, b: dict, clusters: dict, *, seed: int = SEED, resamples: int = RESAMPLES) -> tuple:
    """Mean of a - b and the lower 2.5% quantile of a cluster bootstrap (clusters: item -> base item)."""
    groups = {}
    for i in a:
        groups.setdefault(clusters.get(i) or i, []).append(i)
    keys = sorted(groups)
    if not keys:
        return None, None
    diff = sum(a[i] - b[i] for i in a) / len(a)
    rng = random.Random(seed)
    stats = []
    for _ in range(resamples):
        chosen = [k for k in (rng.choice(keys) for _ in keys)]
        members = [i for k in chosen for i in groups[k]]
        stats.append(sum(a[i] - b[i] for i in members) / len(members))
    stats.sort()
    return round(diff, 4), round(stats[int(0.025 * resamples)], 4)


def analyze(suite: dict, runs: dict) -> dict:
    items = {i["item_id"]: i for i in suite["items"]}
    clusters = {k: v.get("base_item_id") for k, v in items.items()}
    eligible = [k for k, v in items.items() if v["closure_eligible"]]
    harm_eligible = [k for k, v in items.items() if v.get("harm")]
    rows = {arm: {r["item_id"]: r for r in run["rows"]} for arm, run in runs.items()}
    closure = {arm: _closed(r, eligible) for arm, r in rows.items()}
    rate = {arm: round(sum(c.values()) / len(c), 4) if c else None for arm, c in closure.items()}
    out = {"n_closure_eligible": len(eligible), "n_harm_eligible": len(harm_eligible), "closure_rate": rate,
           "errors": {arm: sum("error" in r for r in rr.values()) for arm, rr in rows.items()},
           "per_operator": {}, "verdict": {}}
    for op in sorted({v["operator"] for v in items.values()}):
        ids = [k for k, v in items.items() if v["operator"] == op]
        out["per_operator"][op] = {arm: {"closed": sum(bool(rr.get(i, {}).get("closed")) for i in ids),
                                         "harm": sum(bool(rr.get(i, {}).get("harm")) for i in ids), "n": len(ids)}
                                   for arm, rr in rows.items()}
    if "NEW" in closure and "B0" in closure:
        gain, low = paired_bound(closure["NEW"], closure["B0"], clusters)
        out["E1"] = {"new_rate": rate["NEW"], "gain_vs_b0": gain, "lower_bound": low,
                     "pass": bool(rate["NEW"] is not None and rate["NEW"] >= E1_RATE and low is not None
                                  and low >= E1_GAIN)}
    singles = [a for a in ("A_producer", "A_consumer") if a in closure]
    if "NEW" in closure and singles and "S" in closure:
        best = max(singles, key=lambda a: rate[a])
        g1, l1 = paired_bound(closure["NEW"], closure[best], clusters)
        g2, l2 = paired_bound(closure["NEW"], closure["S"], clusters)
        out["E2"] = {"best_single_side": best, "gain_vs_single": g1, "lower_single": l1,
                     "gain_vs_parser": g2, "lower_parser": l2,
                     "pass": bool(g1 is not None and g1 >= E2_SINGLE and l1 > 0 and g2 >= E2_PARSER and l2 > 0)}
    if "NEW" in rows:
        harms = sorted(i for i in harm_eligible if rows["NEW"].get(i, {}).get("harm"))
        out["H1"] = {"harmful": harms, "n": len(harm_eligible), "pass": not harms}
    out["E3"] = {arm: sum(1 for k, v in items.items() if v["gold"] != "FORM" and rr.get(k, {}).get("genesis_first_tick")
                          is not None) for arm, rr in rows.items()}
    # E4 (descriptive): what the founder authored for each closure. A prepared command leaves only the values the
    # perturbation removed; any other closing action was composed by the founder (attach id or successor spec).
    out["E4"] = {}
    for arm, rr in rows.items():
        closed = [k for k in eligible if rr.get(k, {}).get("closed")]
        prepared = [k for k in closed if (rr[k].get("action") or {}).get("source") == "prepared_command"]
        out["E4"][arm] = {"closures": len(closed), "by_prepared_command": len(prepared),
                          "founder_values_supplied": sum(len(items[k]["removed"]) for k in prepared),
                          "founder_composed": len(closed) - len(prepared)}
    e1, e2, h1 = out.get("E1", {}), out.get("E2", {}), out.get("H1", {})
    out["verdict"] = ("FAILED_HARM" if h1 and not h1["pass"] else
                      "RECOMBINATION_DIVIDEND" if e1.get("pass") and e2.get("pass") else
                      "PREREQUISITE_PORT_PLUS_INTEGRATION" if e1.get("pass") else
                      "NO_DIVIDEND" if e1 else "INCOMPLETE")
    return out


FREEZE = Path(__file__).resolve().parents[3] / "docs/evidence/greg-abstention-resolution/2026-11-13/freeze.json"


def freeze_mismatches(freeze: Path = FREEZE) -> list:
    """Frozen files whose bytes changed since the freeze; a run that reports with any is INCONCLUSIVE."""
    import hashlib
    root = freeze.parents[4]
    manifest = json.loads(freeze.read_text())
    bad = []
    for rel, want in manifest["files"].items():
        path = root / rel
        got = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if got != want:
            bad.append(rel)
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suite", type=Path, required=True)
    ap.add_argument("--run", action="append", default=[], help="ARM=FILE")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    runs = {}
    for spec in args.run:
        arm, _, path = spec.partition("=")
        runs[arm] = json.loads(Path(path).read_text())
    out = analyze(json.loads(args.suite.read_text()), runs)
    out["freeze_mismatches"] = freeze_mismatches()
    if out["freeze_mismatches"]:
        out["verdict"] = "INCONCLUSIVE"
    out["runs"] = {arm: {"tree_commit": r.get("tree_commit"), "policy": r.get("policy"), "ablate": r.get("ablate")}
                   for arm, r in runs.items()}
    args.out.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: out.get(k) for k in ("closure_rate", "E1", "E2", "H1", "verdict")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
