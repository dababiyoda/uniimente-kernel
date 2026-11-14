"""Design pilot for P8 cycle 7 on a second target, the negative-selection detector (``immune_detect``), on immune
REVIEW seeds 3100-3999 only.

P8's exit condition is repeated held-out gains. Cycle 6 kept a constraint-release proposal; a second target is needed.
``forecast_quantile`` has no unused data: its pool of 241 M4 weekly series is fully drawn by the development seeds,
the admission freezes and cycle 1's split (``evolution.used_instance_keys``), and its cycle-1 held-out split is spent.
``immune_detect`` is the remaining declared target. Cycle 2 (2026-10-09) triggered on it (40% of 40 train items) and
stopped at the scarce-sample stress gate, so its held-out split 8000-8059 was never looked at.

Questions, answered before any cycle-7 split is drawn:

1. Does the trigger fire on fresh review train sets?
2. Is there headroom in the closed space ``collective.IMMUNE_CONFIG_SPACE`` that survives the cycle's stress sets
   (``_immune_stress``: 80 self samples; a five-fold tighter false-alarm budget) and holds on a fresh pool?
3. How often would a cycle run with the cycle's own search, loss, gates and rule RETAIN, and at which split sizes?

Declared before any pilot instance was generated (none is added after looking):

- **Seeds.** Review seeds 3100-3999 only, through ``guard`` (development seeds 0-9 only in unit tests). Immune review
  seeds 3000-3059 were drawn by the native-regime builder measurement (``65b9acc``) and the unit tests, so this pilot
  starts at 3100. No P8-reserved (7000-8599, and 8600-9199 once reserved), admission or spent seed is generated.
- **Train sets** ``TRAIN_SETS``: three disjoint sets of 120 items; each is also simulated on its first 60 items.
- **Look pool** ``POOL``: 3460-3999 (540 items), disjoint from every train set; the held-out step is resampled from it
  (``RESAMPLE_SIZES``), as the cycle-5/6 pilots did.
- **Region** ``region_configs``: the incumbent's axis cover (what ``cover/1`` declares), cycle 2's REJECTED candidate
  and cycle 2's five next-best configurations, each measured on the pool and on the first train set's stress items.
- **Simulated cycles** ``SIMULATIONS``: ``cover/1`` (lhs 0) and ``mutate-incumbent/1``, generations 5, population 8,
  search seed 20261007, on each 120-item train set, and ``cover/1`` on each 60-item subset (9 runs).
- **Decision rules for the pre-registration** (``choose``):
  - VIABLE iff the trigger fires on at least 2 of the 3 train sets AND the best mean P(RETAIN) at alpha 0.05 over the
    declared (policy, train size, held-out size) choices is at least ``VIABLE_MIN`` (0.30);
  - the choice is the (policy, train size, held-out size) with the highest mean P(RETAIN) at the programme-wide
    threshold alpha/7 (the seventh P8 cycle); ties go to cover/1, then 120 train items, then the smaller held-out size.
  Otherwise the pilot reports NOT_VIABLE with its numbers: a second target is not manufactured.

Every loss is computed as the cycle computes it: ``SealedEvaluator.losses`` over ``collective.immune_score`` on the
output of ``collective.immune_solve_with`` (the sandbox's method) or of ``collective.immune_zscore`` (the target's
baseline), run in this process (several worker processes, each running the same function on whole items). An
exception is an abstention, as the sandbox records it. Each stress ANSWER is checked by ``collective.immune_verify``.
It is design knowledge, disclosed in the cycle-7 pre-registration; it is not evidence for the cycle and decides
nothing about adoption.

    PYTHONPATH=. python scripts/p8_immune_pilot.py region --out pilot/region.json
    PYTHONPATH=. python scripts/p8_immune_pilot.py simulate --out pilot/simulate.json
    PYTHONPATH=. python scripts/p8_immune_pilot.py summarise --dir pilot --out pilot/summary.json
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import math
import os
from pathlib import Path
import random
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from greg.cognition import evolution as E                      # noqa: E402
from greg.cognition.genomes import admission, collective as C  # noqa: E402

REVIEW_SEEDS = range(3100, 4000)
DEV_SEEDS = range(0, 10)
# reserved for P8 once the cycle-7 design is committed (admission.P8_RESERVED); refused here either way
P8_EXTENSION = range(8600, 9200)
TRAIN_SETS = {"T1": tuple(range(3100, 3220)), "T2": tuple(range(3220, 3340)), "T3": tuple(range(3340, 3460))}
POOL = tuple(range(3460, 4000))
RESAMPLE_SIZES = (120, 180, 240, 360, 480)
SEARCH_SEED = 20261007
SIMULATIONS = ([{"train": t, "size": 120, "search": "cover/1", "lhs": 0} for t in TRAIN_SETS]
               + [{"train": t, "size": 120, "search": "mutate-incumbent/1"} for t in TRAIN_SETS]
               + [{"train": t, "size": 60, "search": "cover/1", "lhs": 0} for t in TRAIN_SETS])
GENERATIONS, POPULATION = 5, 8
VIABLE_MIN = 0.30
# Reading-only thresholds: the seventh P8 cycle overall and the second pre-registered cycle on this target.
THRESHOLDS = {"alpha": E.ALPHA, "target_2": E.ALPHA / 2, "programme_7": E.ALPHA / 7}
CYCLE_2_RECORD = ROOT / "docs/evidence/greg-protected-evolution/2026-10-09/cycle-immune-2.json"
WORKERS = max(1, min(3, (os.cpu_count() or 1) - 1))


class PilotError(ValueError):
    pass


def guard(seeds) -> tuple:
    """The seeds, or PilotError: immune review seeds 3100-3999 only (development seeds 0-9 for tests), never a
    P8-reserved, admission or spent seed."""
    seeds = tuple(seeds)
    forbidden = (set(admission.P8_RESERVED) | set(P8_EXTENSION) | set(admission.HELDOUT_SEEDS)
                 | admission.spent_seeds())
    bad = sorted((s for s in seeds if type(s) is not int or s in forbidden
                  or not (s in REVIEW_SEEDS or s in DEV_SEEDS)), key=repr)
    if bad:
        raise PilotError(f"the immune pilot uses review seeds 3100-3999 only (development 0-9 in tests); "
                         f"refused {bad[:10]}")
    return seeds


def items(seeds) -> dict:
    out = {}
    for s in guard(seeds):
        data, truth = C.immune_gaussian_instance(s)
        out[f"r{s}"] = {"data": data, "truth": truth, "category": C.immune_dimension_band(data)}
    return out


def _output(config, data) -> dict:
    """The sandbox's method in this process; an exception is no answer, as the sandbox records it."""
    if config == "zscore":
        return {"output": C.immune_zscore(data)}
    try:
        out = C.immune_solve_with(config, data)
        return {"output": out["output"], "certificate": out["certificate"]}
    except Exception as exc:                              # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {str(exc)[:160]}"}


def _job(args):
    config, data = args
    return _output(config, data)


class Pilot:
    """In-process evaluation with the cycle's own loss; memoised per (configuration, item data)."""

    def __init__(self, workers: int = WORKERS):
        self.target = E.immune_target()
        self.cache: dict = {}
        self.outputs: dict = {}
        self.evaluations = 0
        self.workers = workers
        self._pool = None

    def close(self):
        if self._pool is not None:
            self._pool.shutdown()
            self._pool = None

    def _key(self, config):
        return "zscore" if config == "zscore" else E.config_id(self.target.validate(config))

    def run(self, config, its: dict) -> dict:
        key = self._key(config)
        missing = {k: v for k, v in its.items() if (key, _fingerprint(v)) not in self.outputs}
        if missing:
            jobs = [(config, v["data"]) for v in missing.values()]
            if self.workers > 1 and len(jobs) > 4:
                if self._pool is None:
                    self._pool = ProcessPoolExecutor(self.workers)
                results = list(self._pool.map(_job, jobs, chunksize=4))
            else:
                results = [_job(j) for j in jobs]
            self.evaluations += len(missing)
            for (k, v), out in zip(missing.items(), results):
                self.outputs[(key, _fingerprint(v))] = out
        return {k: self.outputs[(key, _fingerprint(v))] for k, v in its.items()}

    def losses(self, config, its: dict) -> dict:
        key = self._key(config)
        outputs = self.run(config, its)
        todo = {k: v for k, v in its.items() if (key, _fingerprint(v)) not in self.cache}
        if todo:
            for k, loss in E.SealedEvaluator(todo, C.immune_score).losses(outputs).items():
                self.cache[(key, _fingerprint(todo[k]))] = loss
        return {k: self.cache[(key, _fingerprint(v))] for k, v in its.items()}

    def verified(self, config, its: dict) -> bool:
        return E.outputs_verified(C.immune_verify, its, self.run(config, its))


def _fingerprint(item) -> str:
    """Stress items share ids with their source item but differ in data: memoise by the data's digest."""
    return E.digest(item["data"])


def paired(a: dict, b: dict) -> dict:
    """a against b on the same items, as the cycle counts them: lower loss wins (1e-12 tolerance)."""
    wins = sum(1 for k in a if a[k] < b[k] - 1e-12)
    losses = sum(1 for k in a if b[k] < a[k] - 1e-12)
    return {"wins": wins, "losses": losses, "ties": len(a) - wins - losses,
            "sign_test_p_one_sided": round(E.sign_test(wins, losses), 6)}


def describe(ls: dict) -> dict:
    """Mean loss as the rule reads it (infinite when any answer is wrong), the number of wrong answers, and the mean
    over the remaining items (a reading aid only: the rule never drops a wrong answer)."""
    finite = [v for v in ls.values() if math.isfinite(v)]
    return {"mean_loss": round(statistics.fmean(ls.values()), 6), "wrong": len(ls) - len(finite),
            "abstain": sum(1 for v in finite if v == 0), "n": len(ls),
            "mean_loss_without_wrong": round(statistics.fmean(finite), 6) if finite else None}


def resampled(candidate: dict, incumbent: dict, n: int, *, draws: int = 2000, seed: int = 0) -> dict:
    """How often the rule's held-out step would RETAIN on ``n`` items drawn with replacement from a pool: the
    one-sided sign test gives p below each threshold and the candidate's mean loss is lower (an infinite mean, any
    wrong answer, is never lower than another infinite mean)."""
    keys = sorted(candidate)
    rng = random.Random(f"p8-immune-pilot-resample:{seed}:{n}")
    counts = {name: 0 for name in THRESHOLDS}
    for _ in range(draws):
        sample = [keys[rng.randrange(len(keys))] for _ in range(n)]
        wins = sum(1 for k in sample if candidate[k] < incumbent[k] - 1e-12)
        losses = sum(1 for k in sample if incumbent[k] < candidate[k] - 1e-12)
        lower = statistics.fmean(candidate[k] for k in sample) < statistics.fmean(incumbent[k] for k in sample)
        p = E.sign_test(wins, losses)
        for name, alpha in THRESHOLDS.items():
            counts[name] += p < alpha and lower
    return {"n": n, "draws": draws, **{f"retain_rate_{name}": round(c / draws, 4) for name, c in counts.items()}}


def on_pool(pilot, config, pool: dict, reference: dict) -> dict:
    ls = pilot.losses(config, pool)
    return {**describe(ls), "vs_incumbent": paired(ls, reference),
            "resampled": [resampled(ls, reference, n) for n in RESAMPLE_SIZES]}


def stress_report(pilot, config, stress: dict) -> dict:
    inc = pilot.target.incumbent
    ls, inc_s = pilot.losses(config, stress), pilot.losses(inc, stress)
    out = {}
    for kind in ("scarce", "strict"):
        mine = {k: v for k, v in ls.items() if k.startswith(kind + ":")}
        theirs = {k: v for k, v in inc_s.items() if k.startswith(kind + ":")}
        out[kind] = {"candidate": describe(mine), "incumbent": describe(theirs)}
    out["all_outputs_verified"] = pilot.verified(config, stress)
    out["passes_gate"] = out["all_outputs_verified"] and not any(
        E.worsened(out[k]["incumbent"]["mean_loss"], out[k]["candidate"]["mean_loss"]) for k in ("scarce", "strict"))
    return out


def cycle_2_configs() -> list[dict]:
    """Cycle 2's REJECTED candidate and its five next-best configurations, read from its frozen record (no instance
    of its split is generated)."""
    if not CYCLE_2_RECORD.is_file():
        return []
    record = json.loads(CYCLE_2_RECORD.read_text())
    ranked = sorted(record["search"]["lineage"], key=lambda s: (s["train_mean_loss"], s["id"]))
    return [{"config": s["config"], "why": f"cycle 2 lineage rank {i + 1} (train mean {s['train_mean_loss']})"}
            for i, s in enumerate(ranked[:6])]


def region_configs() -> list[dict]:
    """The incumbent's axis cover (cover/1's declared configurations with lhs 0) and cycle 2's six best."""
    target = E.immune_target()
    cover = E.search_setting(target, "cover/1", seed=SEARCH_SEED, lhs=0)["initial"]
    out, seen = [], {E.config_id(target.incumbent)}
    for entry in [{"config": c, "why": "axis cover"} for c in cover] + cycle_2_configs():
        cid = E.config_id(target.validate(entry["config"]))
        if cid not in seen:
            seen.add(cid)
            out.append(entry)
    return out


def region(pool_seeds=POOL, stress_seeds=TRAIN_SETS["T1"], configs=None, *, pilot=None) -> dict:
    started = time.time()
    pool_seeds, stress_seeds = guard(pool_seeds), guard(stress_seeds)       # both, before any instance exists
    if set(pool_seeds) & set(stress_seeds):
        raise PilotError("the region's pool and stress train set must be disjoint")
    pilot = pilot or Pilot()
    pool, train = items(pool_seeds), items(stress_seeds)
    stress = E._immune_stress(train)
    inc = pilot.target.incumbent
    reference = pilot.losses(inc, pool)
    base = pilot.losses("zscore", pool)
    inc_train, base_train = pilot.losses(inc, train), pilot.losses("zscore", train)
    rows = []
    for entry in (region_configs() if configs is None else configs):
        config = pilot.target.validate(entry["config"])
        rows.append({"id": E.config_id(config), "config": config, "why": entry.get("why"),
                     "pool": on_pool(pilot, config, pool, reference),
                     "train": {**describe(pilot.losses(config, train)),
                               "vs_incumbent": paired(pilot.losses(config, train), inc_train)},
                     "stress": stress_report(pilot, config, stress)})
    return {"schema": "greg-p8-immune-pilot-region/1",
            "seeds": {"pool": [min(pool_seeds), max(pool_seeds)], "train": [min(stress_seeds), max(stress_seeds)]},
            "incumbent": {"id": E.config_id(inc), "config": inc, "pool": describe(reference),
                          "train": describe(inc_train), "stress": stress_report(pilot, inc, stress)},
            "zscore": {"pool": {**describe(base), "vs_incumbent": paired(base, reference)},
                       "incumbent_failure_rate_pool": round(sum(reference[k] > base[k] for k in pool) / len(pool), 4),
                       "incumbent_failure_rate_train": round(
                           sum(inc_train[k] > base_train[k] for k in train) / len(train), 4)},
            "rows": rows, "evaluations": pilot.evaluations, "seconds": round(time.time() - started, 1)}


def simulate_one(pilot, train: dict, pool: dict, setting: dict) -> dict:
    """One simulated cycle with the cycle's own search, train-gain gate and adversarial gate; the held-out step is
    resampled from the pool."""
    target = pilot.target
    inc = target.incumbent
    declared = E.search_setting(target, setting["search"], seed=SEARCH_SEED, lhs=setting.get("lhs", 0))
    inc_train, base_train = pilot.losses(inc, train), pilot.losses("zscore", train)
    inc_mean = round(statistics.fmean(inc_train.values()), 6)
    found = E.run_search(target, lambda config: pilot.losses(config, train), generations=GENERATIONS,
                         population=POPULATION, seed=SEARCH_SEED, incumbent_loss=inc_mean,
                         initial=declared.get("initial", ()))
    best = found["candidate"]["config"]
    gain = E.relative_gain(inc_mean, found["candidate"]["train_mean_loss"])
    rate = sum(1 for k in train if inc_train[k] > base_train[k]) / len(train)
    stages = {"triggered": rate >= E.FAILURE_RATE_TRIGGER,
              "advances": found["candidate"]["id"] != E.config_id(inc) and gain > E.TRAIN_GAIN_MIN}
    stress = stress_report(pilot, best, E._immune_stress(train)) if stages["advances"] else None
    stages["adversarial_passes"] = bool(stress and stress["passes_gate"])
    out = {"settings": setting, "evaluated": found["evaluated"], "incumbent_failure_rate": round(rate, 4),
           "incumbent_train": describe(inc_train),
           "candidate": {"id": found["candidate"]["id"], "config": best,
                         "train_mean_loss": round(found["candidate"]["train_mean_loss"], 6)},
           "train_gain": gain if math.isinf(gain) else round(gain, 4),
           "candidate_train": describe(pilot.losses(best, train)),
           "top_train": [{"id": s["id"], "ops": s["ops"], "config": s["config"], "train_mean_loss": s["train_mean_loss"]}
                         for s in sorted(found["lineage"], key=lambda s: (s["train_mean_loss"], s["id"]))[:5]],
           "stress": stress, "stages": stages,
           "pool": on_pool(pilot, best, pool, pilot.losses(inc, pool))}
    passes = all(stages.values())
    out["resampled_retain"] = [{"n": r["n"], **{k: (v if passes else 0.0) for k, v in r.items()
                                                if k.startswith("retain_rate")}} for r in out["pool"]["resampled"]]
    out["would_reach_heldout"] = passes
    return out


def simulate(simulations=SIMULATIONS, *, train_sets=None, pool_seeds=POOL, pilot=None) -> dict:
    started = time.time()
    train_sets = TRAIN_SETS if train_sets is None else train_sets
    all_train = {s for seeds in train_sets.values() for s in seeds}
    guard(sorted(all_train)), guard(pool_seeds)
    if set(pool_seeds) & all_train:
        raise PilotError("the look pool must be fresh: disjoint from every simulated train set")
    pilot = pilot or Pilot()
    pool = items(pool_seeds)
    runs = []
    for setting in simulations:
        train = items(train_sets[setting["train"]][:setting["size"]])
        runs.append(simulate_one(pilot, train, pool, setting))
        print(json.dumps({"done": setting, "decision_stages": runs[-1]["stages"],
                          "seconds": round(time.time() - started)}), flush=True)
    return {"schema": "greg-p8-immune-pilot-simulate/1",
            "seeds": {"train": {k: [min(v), max(v)] for k, v in train_sets.items()},
                      "pool": [min(pool_seeds), max(pool_seeds)]},
            "search_seed": SEARCH_SEED, "generations": GENERATIONS, "population": POPULATION,
            "runs": runs, "evaluations": pilot.evaluations, "seconds": round(time.time() - started, 1)}


def choose(sim: dict) -> dict:
    """The declared decision rules, applied to the simulated cycles."""
    triggered = {}
    for run in sim["runs"]:
        if run["settings"]["size"] == max(r["settings"]["size"] for r in sim["runs"]):
            triggered[run["settings"]["train"]] = run["stages"]["triggered"]
    cells = {}
    for run in sim["runs"]:
        s = run["settings"]
        for r in run["resampled_retain"]:
            cells.setdefault((s["search"], s["size"], r["n"]), []).append(r)
    table = [{"search": k[0], "train_size": k[1], "heldout_size": k[2], "runs": len(v),
              **{f"mean_{name}": round(statistics.fmean(r[name] for r in v), 4)
                 for name in v[0] if name.startswith("retain_rate")}} for k, v in sorted(cells.items())]
    best_005 = max((row["mean_retain_rate_alpha"] for row in table), default=0.0)
    viable = sum(triggered.values()) >= 2 and best_005 >= VIABLE_MIN
    order = sorted(table, key=lambda row: (-row["mean_retain_rate_programme_7"], row["search"] != "cover/1",
                                           -row["train_size"], row["heldout_size"]))
    return {"triggered_by_train_set": triggered, "best_mean_retain_alpha": best_005, "viable_min": VIABLE_MIN,
            "verdict": "VIABLE" if viable else "NOT_VIABLE", "table": table,
            "choice": ({k: order[0][k] for k in ("search", "train_size", "heldout_size")} if viable else None)}


def summarise(directory: Path) -> dict:
    directory = Path(directory)
    out = {}
    if (directory / "region.json").is_file():
        reg = json.loads((directory / "region.json").read_text())
        out["region"] = {"seeds": reg["seeds"], "incumbent": reg["incumbent"], "zscore": reg["zscore"], "rows": [
            {"id": r["id"], "why": r["why"], "config": r["config"],
             **{k: r["pool"][k] for k in ("mean_loss", "wrong", "abstain", "mean_loss_without_wrong", "vs_incumbent")},
             "resampled": r["pool"]["resampled"], "train": r["train"],
             "stress_passes_gate": r["stress"]["passes_gate"],
             "stress": {k: {"candidate_wrong": r["stress"][k]["candidate"]["wrong"],
                            "candidate_mean": r["stress"][k]["candidate"]["mean_loss"],
                            "incumbent_mean": r["stress"][k]["incumbent"]["mean_loss"]} for k in ("scarce", "strict")}}
            for r in reg["rows"]]}
    if (directory / "simulate.json").is_file():
        sim = json.loads((directory / "simulate.json").read_text())
        out["simulated"] = {"runs": [{"settings": r["settings"], "evaluated": r["evaluated"],
                                      "failure_rate": r["incumbent_failure_rate"], "incumbent_train": r["incumbent_train"],
                                      "candidate": r["candidate"], "candidate_train": r["candidate_train"],
                                      "train_gain": r["train_gain"], "stages": r["stages"],
                                      "stress": None if r["stress"] is None else {
                                          k: r["stress"][k] for k in ("scarce", "strict", "passes_gate")},
                                      "pool": {k: r["pool"][k] for k in ("mean_loss", "wrong", "abstain",
                                                                          "mean_loss_without_wrong", "vs_incumbent")},
                                      "resampled_if_reached": r["pool"]["resampled"]} for r in sim["runs"]],
                            "decision": choose(sim)}
    return out


def _range(text: str) -> tuple:
    lo, hi = (int(v) for v in text.split("-"))
    return tuple(range(lo, hi + 1))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", choices=("region", "simulate", "summarise"))
    ap.add_argument("--dir", type=Path, help="summarise: the pilot directory")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    if args.mode == "summarise":
        args.out.write_text(json.dumps(summarise(args.dir), indent=1) + "\n")
        print(json.dumps({"out": str(args.out)}))
        return
    pilot = Pilot()
    try:
        result = region(pilot=pilot) if args.mode == "region" else simulate(pilot=pilot)
    finally:
        pilot.close()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps({"out": str(args.out), "evaluations": result["evaluations"], "seconds": result["seconds"]}))


if __name__ == "__main__":
    main()
