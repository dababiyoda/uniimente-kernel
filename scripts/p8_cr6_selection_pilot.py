"""Design pilot for P8 cycle 6 on the constraint-release target: candidate SELECTION rules, on review seeds 3500-3999.

Cycle 5 (2026-10-16) searched with cover/1 and reached the restart anchor (``p_restart`` 1.0) at a train mean loss
within 0.5% of the best; ten evaluated configurations tied it. The frozen selection, the lowest train mean loss,
picked an operator variant (``offspring`` 6) that failed the lean stress set, so the held-out gate was never reached.
Cycle 5's pilot had already found that train mean loss does not rank configurations (Spearman -0.18 between halves).

This pilot asks, before any cycle-6 split is drawn, which rule for choosing the cycle's ONE candidate from a search
lineage most often yields a candidate that passes the unchanged train-gain and stress gates and then wins the unchanged
held-out step. The search is unchanged: each simulated cycle runs the cycle's own ``run_search`` (cover/1, ``lhs`` 0,
generations 5, population 8; its later generations are bred from the best train MEANS whatever the final selection),
so every rule is applied to the SAME lineage and the comparison between rules is paired. Every rule is declared in
``RULES`` below before any pilot instance was generated; none was added after looking.

Every loss is the cycle's loss (``SealedEvaluator.losses`` over ``constraint_release_score``) on the output of
``constraint_release_solve_with``, the sandbox's method, run in this process; stress items come from ``_cr_stress``;
every stress ANSWER is checked by the target's verifier, as the cycle checks the candidate's. The held-out step is
resampled from a fresh pool disjoint from every train set. The guard accepts review seeds 3500-3999 only (and the
development seeds 0-9, for tests): cycle 5's pilot used 3000-3119 and 3200-3499.

    PYTHONPATH=. taskset -c 2 python scripts/p8_cr6_selection_pilot.py lineages --train 3500-3559 \
        --seeds 101,102,103 --pool 3740-3999 --out T1.json
    PYTHONPATH=. python scripts/p8_cr6_selection_pilot.py summarise --dir DIR --out DIR/summary.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import p8_cr_pilot as P                                         # noqa: E402
from greg.cognition import evolution as E                      # noqa: E402
from greg.cognition.genomes import developmental as D          # noqa: E402

PILOT_SEEDS = range(3500, 4000)
SEARCH = {"search": "cover/1", "lhs": 0, "generations": 5, "population": 8}
# Reading-only thresholds of cycle 6: the fourth attempt on this target and the sixth P8 cycle overall.
THRESHOLDS = {"alpha": E.ALPHA, "target_4": E.ALPHA / 4, "programme_6": E.ALPHA / 6}
RESTART_HEAVY = 0.75
TRIM = 0.1


def guard(seeds) -> tuple:
    """Review seeds 3500-3999 only (development seeds 0-9 in tests), then the cycle-5 pilot's own guard."""
    seeds = tuple(seeds)
    bad = sorted(s for s in seeds if type(s) is not int or not (s in PILOT_SEEDS or s in P.DEV_SEEDS))
    if bad:
        raise P.PilotError(f"the cycle-6 pilot uses review seeds 3500-3999 only (development 0-9 in tests); "
                           f"refused {bad[:10]}")
    return P.guard(seeds)


def trimmed_mean(values, fraction: float = TRIM) -> float:
    values = sorted(values)
    k = int(len(values) * fraction)
    return statistics.fmean(values[k:len(values) - k] if len(values) > 2 * k else values)


class Pilot(P.Pilot):
    """The cycle-5 pilot's evaluator, which also records whether every stress ANSWER verifies."""

    def __init__(self):
        super().__init__()
        self.verified: dict = {}

    def stress(self, config, stress_items: dict) -> dict:
        """Lean and few-validation means and the verification of every answer, as the cycle's adversarial gate.
        Each output is computed once: verified, then scored by the sealed evaluator and memoised."""
        key = E.config_id(self.target.validate(config))
        missing = {k: v for k, v in stress_items.items() if (key, k, P._fingerprint(v)) not in self.cache}
        if missing:
            outputs = {k: self._output(config, v["data"]) for k, v in missing.items()}
            self.evaluations += len(missing)
            ok = all(all(D.constraint_release_verify(missing[k]["data"], o["output"], o["certificate"]).values())
                     for k, o in outputs.items() if o.get("output") is not None)
            self.verified[key] = self.verified.get(key, True) and ok
            for k, loss in E.SealedEvaluator(missing, D.constraint_release_score).losses(outputs).items():
                self.cache[(key, k, P._fingerprint(missing[k]))] = loss
        losses = self.losses(config, stress_items)
        return {kind: P.mean(v for k, v in losses.items() if k.startswith(kind + ":")) for kind in ("lean", "fewval")} \
            | {"verified": self.verified[key]}


def profile(config, train_losses: dict, inc_train: dict, inc_mean_rounded: float, stress: dict,
            inc_stress: dict) -> dict:
    """Everything a selection rule may read about one evaluated configuration: train data only."""
    values = list(train_losses.values())
    vs = P.paired(train_losses, inc_train)
    mean = statistics.fmean(values)
    passes = stress["verified"] and not any(E.worsened(inc_stress[k], stress[k]) for k in ("lean", "fewval"))
    return {"id": E.config_id(config), "p_restart": config["p_restart"], "mean": mean,
            "median": statistics.median(values), "trimmed": trimmed_mean(values), "wins": vs["wins"],
            "losses": vs["losses"], "sign_p": E.sign_test(vs["wins"], vs["losses"]),
            "gain": E.relative_gain(inc_mean_rounded, mean), "stress": stress, "stress_passes": passes}


def _eligible(rows, incumbent_id):
    """Configurations the unchanged train gate would let advance: not the incumbent, train mean gain > 1%."""
    return [r for r in rows if r["id"] != incumbent_id and r["gain"] > E.TRAIN_GAIN_MIN]


def _pick(rows, key, incumbent_id, *, eligible=True, stress=False, fallback=None):
    pool = _eligible(rows, incumbent_id) if eligible else list(rows)
    if stress:
        pool = [r for r in pool if r["stress_passes"]]
    if not pool:
        return fallback(rows, incumbent_id) if fallback else None
    return min(pool, key=key)


def _mean_pick(rows, incumbent_id):
    return min(rows, key=lambda r: (r["mean"], r["id"]))


# Declared before any pilot instance was generated. Each maps a lineage's profiles to one candidate.
RULES = {
    "mean/1": (_mean_pick, "the lowest train mean loss, ties by id (cycles 1-5)"),
    "median/1": (lambda rows, inc: min(rows, key=lambda r: (r["median"], r["mean"], r["id"])),
                 "the lowest train median loss, ties by mean then id"),
    "trimmed/1": (lambda rows, inc: min(rows, key=lambda r: (r["trimmed"], r["mean"], r["id"])),
                  "the lowest 10%-trimmed train mean loss, ties by mean then id"),
    "signtest/1": (lambda rows, inc: _pick(rows, lambda r: (r["sign_p"], r["mean"], r["id"]), inc,
                                           fallback=_mean_pick),
                   "among configurations whose train mean beats the incumbent's by > 1%, the smallest one-sided "
                   "sign-test p against the incumbent on train items, ties by mean then id; none -> mean/1"),
    "netwins/1": (lambda rows, inc: _pick(rows, lambda r: (-(r["wins"] - r["losses"]), r["mean"], r["id"]), inc,
                                          fallback=_mean_pick),
                  "among configurations whose train mean beats the incumbent's by > 1%, the most train wins minus "
                  "losses against the incumbent, ties by mean then id; none -> mean/1"),
    "stress-mean/1": (lambda rows, inc: _pick(rows, lambda r: (r["mean"], r["id"]), inc, stress=True,
                                              fallback=_mean_pick),
                      "among configurations that pass the train gain AND both train-derived stress sets (every "
                      "answer verified), the lowest train mean; none -> mean/1"),
    "stress-signtest/1": (lambda rows, inc: _pick(rows, lambda r: (r["sign_p"], r["mean"], r["id"]), inc,
                                                  stress=True, fallback=_mean_pick),
                          "as signtest/1 among configurations that also pass both train-derived stress sets; "
                          "none -> mean/1"),
}


def resampled(candidate: dict, incumbent: dict, n: int, *, draws: int = 2000, seed: int = 0) -> dict:
    """How often the rule's held-out step would RETAIN on n items drawn with replacement from the pool: one-sided
    sign test p below each threshold and a lower mean loss."""
    keys = sorted(candidate)
    rng = random.Random(f"p8-cr6-pilot-resample:{seed}:{n}")
    hits = dict.fromkeys(THRESHOLDS, 0)
    for _ in range(draws):
        sample = [keys[rng.randrange(len(keys))] for _ in range(n)]
        wins = sum(1 for k in sample if candidate[k] < incumbent[k] - 1e-12)
        losses = sum(1 for k in sample if incumbent[k] < candidate[k] - 1e-12)
        if sum(candidate[k] for k in sample) < sum(incumbent[k] for k in sample):
            p = E.sign_test(wins, losses)
            for name, threshold in THRESHOLDS.items():
                hits[name] += p < threshold
    return {"n": n, "draws": draws, **{f"retain_rate_{name}": round(hits[name] / draws, 4) for name in THRESHOLDS}}


def lineages(train_seeds, search_seeds, pool_seeds, *, settings=None, sizes=(180, 240), draws=2000) -> dict:
    """For each search seed: run the cycle's search on the train set, profile every evaluated configuration on train
    and on the train-derived stress sets, apply every rule, and measure each rule's candidate on the fresh pool."""
    started = time.time()
    train_seeds, pool_seeds = guard(train_seeds), guard(pool_seeds)
    if set(train_seeds) & set(pool_seeds):
        raise P.PilotError("the pool must be fresh: disjoint from the train set")
    settings = {**SEARCH, **(settings or {})}
    pilot = Pilot()
    target = pilot.target
    inc = target.incumbent
    inc_id = E.config_id(inc)
    train, pool = P.items(train_seeds), P.items(pool_seeds)
    stress_items = E._cr_stress(train)
    inc_train = pilot.losses(inc, train)
    inc_mean_rounded = round(statistics.fmean(inc_train.values()), 6)
    baseline = pilot.losses("random_restart", train)
    inc_stress = pilot.stress(inc, stress_items)
    inc_pool = pilot.losses(inc, pool)
    pooled: dict = {}

    def on_pool(config):
        cid = E.config_id(config)
        if cid not in pooled:
            ls = pilot.losses(config, pool)
            pooled[cid] = {"mean_loss": P.mean(ls.values()), "vs_incumbent": P.paired(ls, inc_pool),
                           "resampled": [resampled(ls, inc_pool, n, draws=draws) for n in sizes]}
        return pooled[cid]

    runs = []
    for seed in search_seeds:
        setting = E.search_setting(target, settings["search"], seed=seed, lhs=settings["lhs"])
        found = E.run_search(target, lambda config: pilot.losses(config, train), generations=settings["generations"],
                             population=settings["population"], seed=seed, incumbent_loss=inc_mean_rounded,
                             initial=setting.get("initial", ()))
        rows = []
        for step in found["lineage"]:
            config = step["config"]
            rows.append({**profile(config, pilot.losses(config, train), inc_train, inc_mean_rounded,
                                   pilot.stress(config, stress_items), inc_stress), "config": config})
        rows[0]["mean"] = inc_mean_rounded              # as the search scores the incumbent
        assert rows[0]["id"] == inc_id and _mean_pick(rows, inc_id)["id"] == found["candidate"]["id"], \
            "mean/1 must be the search's own pick"
        picks = {}
        for name, (rule, _) in RULES.items():
            row = rule(rows, inc_id)
            advances = row["id"] != inc_id and row["gain"] > E.TRAIN_GAIN_MIN
            picks[name] = {"id": row["id"], "p_restart": row["p_restart"], "train_mean": round(row["mean"], 6),
                           "train_gain": round(row["gain"], 4), "train_wins_losses": [row["wins"], row["losses"]],
                           "train_sign_p": round(row["sign_p"], 6), "advances": advances,
                           "stress": row["stress"], "stress_passes": row["stress_passes"],
                           "pool": on_pool(row["config"]) if advances else None}
        runs.append({"search_seed": seed, "evaluated": found["evaluated"],
                     "search_candidate": found["candidate"]["id"],
                     "incumbent_failure_rate": round(sum(1 for k in train if inc_train[k] > baseline[k]) / len(train),
                                                     4),
                     "lineage_stress_passes": sum(r["stress_passes"] for r in rows),
                     "lineage_restart_heavy": sum(r["p_restart"] >= RESTART_HEAVY for r in rows),
                     "lineage": [{k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.items()
                                  if k != "config"} for r in rows],
                     "picks": picks})
    return {"schema": "greg-p8-cr6-selection-pilot/1", "settings": settings, "rules": {k: v[1] for k, v in
                                                                                      RULES.items()},
            "seeds": {"train": [min(train_seeds), max(train_seeds)], "pool": [min(pool_seeds), max(pool_seeds)],
                      "search": list(search_seeds)},
            "incumbent": {"id": inc_id, "train_mean": inc_mean_rounded, "stress": inc_stress,
                          "pool_mean": P.mean(inc_pool.values())},
            "runs": runs, "evaluations": pilot.evaluations, "seconds": round(time.time() - started, 1)}


def _rate(pick, i, threshold) -> float:
    """A simulated cycle's P(RETAIN): 0 when the unchanged rule stops before the held-out step (the candidate does
    not advance or fails the stress gate), else the resampled held-out rate on the fresh pool."""
    if not (pick["advances"] and pick["stress_passes"]) or not pick["pool"]:
        return 0.0
    return pick["pool"]["resampled"][i][f"retain_rate_{threshold}"]


def summarise(paths) -> dict:
    """Per rule over every simulated cycle: how often it advances, passes the stress gate, picks a restart-heavy
    configuration, and its mean P(RETAIN) (0 for a cycle stopped before the held-out step) at each threshold."""
    files = [json.loads(Path(p).read_text()) for p in paths]
    cycles = [(f["seeds"]["train"], run) for f in files for run in f["runs"]]
    sizes = [r["n"] for r in next(run["picks"][k]["pool"] for _, run in cycles for k in run["picks"]
                                  if run["picks"][k]["pool"])["resampled"]]
    out = {"files": [str(p) for p in paths], "cycles": len(cycles),
           "train_sets": sorted({tuple(t) for t, _ in cycles}), "rules": {}}
    for name in files[0]["rules"]:
        picks = [run["picks"][name] for _, run in cycles]
        row = {"advances": sum(p["advances"] for p in picks), "stress_passes": sum(
            p["advances"] and p["stress_passes"] for p in picks),
            "restart_heavy": sum(p["p_restart"] >= RESTART_HEAVY for p in picks),
            "same_as_mean_rule": sum(p["id"] == run["picks"]["mean/1"]["id"] for p, (_, run) in zip(picks, cycles))}
        for i, n in enumerate(sizes):
            for t in THRESHOLDS:
                rates = [_rate(p, i, t) for p in picks]
                row[f"p_retain_n{n}_{t}"] = round(statistics.fmean(rates), 3)
        row["per_cycle_n180_alpha"] = [_rate(p, 0, "alpha") for p in picks]
        row["ungated_n180_alpha"] = round(statistics.fmean(
            p["pool"]["resampled"][0]["retain_rate_alpha"] if p["pool"] else 0.0 for p in picks), 3)
        by_set = {}
        for p, (t, _) in zip(picks, cycles):
            by_set.setdefault(f"{t[0]}-{t[1]}", []).append(_rate(p, 0, "alpha"))
        row["by_train_set_n180_alpha"] = {k: round(statistics.fmean(v), 3) for k, v in by_set.items()}
        out["rules"][name] = row
    return out


def _range(text: str) -> tuple:
    lo, hi = (int(v) for v in text.split("-"))
    return tuple(range(lo, hi + 1))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", choices=("lineages", "summarise"))
    ap.add_argument("--train", type=_range, help="review seeds, e.g. 3500-3559")
    ap.add_argument("--pool", type=_range, help="a fresh look pool, e.g. 3740-3999")
    ap.add_argument("--seeds", default="101,102,103", help="search seeds, comma-separated")
    ap.add_argument("--files", nargs="*", type=Path, help="summarise: lineage files")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    if args.mode == "summarise":
        args.out.write_text(json.dumps(summarise(args.files), indent=1) + "\n")
        print(json.dumps({"out": str(args.out)}))
        return
    if not args.train or not args.pool:
        raise SystemExit("lineages needs --train and --pool")
    result = lineages(args.train, [int(s) for s in args.seeds.split(",")], args.pool)
    args.out.write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps({"out": str(args.out), "evaluations": result["evaluations"], "seconds": result["seconds"]}))


if __name__ == "__main__":
    main()
