"""immune-8: the successor design pilot to immune-7 (P8 on ``immune_detect``), authorized by the founder directive of
2026-10-21 (docs/intent/sources/MIND-MAXIMUM-CONTINUATION-2026-10-21-source.md, sections 1-2).

Lineage: immune-7 (docs/evidence/greg-protected-evolution/2026-10-21-immune-7) judged the target NOT_VIABLE under
its declared rule and is preserved unchanged. This module is built in steps, each committed before the next, so that
every declaration precedes the observation it governs:

- ``gate-audit`` (step A): re-applies the repaired stress gate (``evolution.stress_worsened``, fixed in 32246ee) to
  immune-7's own simulated cycles and region rows, through the merged gate (``stress_summary`` and
  ``stress_worsened`` on item-level losses, 09555108). It regenerates only immune-7's already-exposed review train items
  (3100-3459) and generates no new data.

    PYTHONPATH=. taskset -c 2,3 python scripts/p8_immune8_pilot.py gate-audit \
        --out docs/evidence/greg-protected-evolution/2026-10-21-immune-8/gate-audit.json

- ``region``, ``simulate`` and ``summarise`` (steps C-D): the immune-8 pilot proper, on review seeds 4000-4999 only
  (step B's exposure audit), in the declared narrower space ``evolution.immune_search_space("immune-8/alarm-cap/1")``,
  with the merged gate. Every rule is declared below the step-C marker and in DESIGN.md, committed before any of
  its instances was generated.

    D=docs/evidence/greg-protected-evolution/2026-10-21-immune-8/pilot
    PYTHONPATH=. taskset -c 2,3 python scripts/p8_immune8_pilot.py region --out $D/region.json
    PYTHONPATH=. taskset -c 2,3 python scripts/p8_immune8_pilot.py simulate --out $D/simulate.json
    PYTHONPATH=. python scripts/p8_immune8_pilot.py summarise --dir $D --out $D/summary.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from greg.cognition import evolution as E                      # noqa: E402
from greg.cognition.genomes import collective as C             # noqa: E402

_SPEC7 = importlib.util.spec_from_file_location("p8_immune_pilot", ROOT / "scripts" / "p8_immune_pilot.py")
P7 = importlib.util.module_from_spec(_SPEC7)
sys.modules.setdefault("p8_immune_pilot", P7)            # worker processes unpickle its job by name
_SPEC7.loader.exec_module(P7)

IMMUNE_7 = ROOT / "docs/evidence/greg-protected-evolution/2026-10-21-immune-7"
WORKERS = 2                                    # cores 2-3 (taskset): core 0 and core 1 belong to other lanes


class PilotError(ValueError):
    pass


# ------------------------------------------------------------------ the cycle's adversarial gate, as cycle() runs it
# The gate implementation is the merged one (independent stress-gate audit, 09555108): ``evolution.stress_summary``
# on item-level losses (grouped by exact kind, paired by key, malformed values marked) and
# ``evolution.stress_worsened`` on its per-kind record, with ``evolution.outputs_verified`` - the same three calls
# ``evolution.cycle`` makes in its step 5. No replica of the gate exists in this module.
def gate(pilot, config, stress: dict) -> dict:
    """The cycle's step-5 verdict with the merged gate (``stress_summary`` + ``stress_worsened`` on item-level
    losses), and, for comparison only, the pre-32246ee verdict, which compared the two means with ``worsened``
    alone (a malformed set, which has no means, fails both)."""
    inc_s, cand_s = pilot.losses(pilot.target.incumbent, stress), pilot.losses(config, stress)
    adversarial = E.stress_summary(inc_s, cand_s)          # item-level losses, paired by key
    verified = pilot.verified(config, stress)
    fixed = verified and not any(E.stress_worsened(v) for v in adversarial.values())
    before = verified and not any(v.get("malformed") or E.worsened(v["incumbent"], v["candidate"])
                                  for v in adversarial.values())
    return {"adversarial": adversarial, "all_outputs_verified": verified, "passes_fixed_gate": fixed,
            "passes_pre_32246ee_gate": before}


# ------------------------------------------------------------------ step A: immune-7 under the repaired gate
def _immune7_items(seeds) -> dict:
    """immune-7's own review train items (3100-3459), already generated and looked at by immune-7; nothing new."""
    seeds = tuple(seeds)
    if not set(seeds) <= set(range(3100, 3460)) and not set(seeds) <= set(range(0, 10)):
        raise PilotError(f"the gate audit regenerates only immune-7's exposed train items 3100-3459; refused "
                         f"{sorted(set(seeds) - set(range(3100, 3460)))[:10]}")
    return P7.items(seeds)


def gate_audit(directory: Path = IMMUNE_7 / "pilot", *, pilot=None, train_sets=None) -> dict:
    started = time.time()
    sim = json.loads((directory / "simulate.json").read_text())
    reg = json.loads((directory / "region.json").read_text())
    train_sets = P7.TRAIN_SETS if train_sets is None else train_sets
    pilot = pilot or P7.Pilot(workers=WORKERS)
    runs = []
    for run in sim["runs"]:
        s = run["settings"]
        row = {"settings": s, "candidate": run["candidate"]["id"], "stages_recorded": run["stages"]}
        if run["stages"]["advances"]:
            train = _immune7_items(train_sets[s["train"]][:s["size"]])
            g = gate(pilot, run["candidate"]["config"], E._immune_stress(train))
            row.update(g)
            row["recorded_gate_reproduced"] = g["passes_pre_32246ee_gate"] == run["stages"]["adversarial_passes"]
        row["reaches_heldout_fixed"] = bool(run["stages"]["triggered"] and run["stages"]["advances"]
                                            and row.get("passes_fixed_gate", False))
        row["resampled_retain_fixed"] = [{k: (v if row["reaches_heldout_fixed"] or k == "n" else 0.0)
                                          for k, v in r.items() if k == "n" or k.startswith("retain_rate")}
                                         for r in run["pool"]["resampled"]]
        runs.append(row)
    corrected = P7.choose({"runs": [{"settings": r["settings"],
                                     "stages": {**r["stages_recorded"],
                                                "adversarial_passes": r.get("passes_fixed_gate", False)},
                                     "resampled_retain": r["resampled_retain_fixed"]} for r in runs]})
    t1 = _immune7_items(train_sets["T1"])
    stress = E._immune_stress(t1)
    rows = []
    for r in reg["rows"]:
        g = gate(pilot, r["config"], stress)
        rows.append({"id": r["id"], "why": r["why"], "config": r["config"],
                     "pool_wrong": r["pool"]["wrong"], "pool_vs_incumbent": r["pool"]["vs_incumbent"],
                     "pool_resampled_without_gate": r["pool"]["resampled"],
                     "recorded_passes_gate": r["stress"]["passes_gate"], **g})
    return {"schema": "greg-p8-immune8-gate-audit/1",
            "question": "do immune-7's conclusions depend on the stress-gate defect fixed in 32246ee?",
            "data": "immune-7's own review train items 3100-3459 (already exposed); no new instance",
            "simulated_cycles": runs,
            "recorded_decision": {k: P7.choose(sim)[k] for k in ("verdict", "best_mean_retain_alpha")},
            "corrected_decision": corrected,
            "region_rows_on_T1_stress": rows,
            "evaluations": pilot.evaluations, "seconds": round(time.time() - started, 1)}


# ====================================================================== step C: the immune-8 pilot declaration
# Everything below was declared and committed before any instance of the review seeds 4000-4999 was generated
# (DESIGN.md in the evidence directory states the same rules in prose; a test checks the two agree).
SPACE = "immune-8/alarm-cap/1"             # evolution.IMMUNE_SEARCH_SPACES: alarm_fraction in [0.4, 0.75]
REVIEW_SEEDS = range(4000, 5000)            # exposure audit (step B): never generated by any immune generator
DEV_SEEDS = range(0, 10)
TRAIN_SETS = {"T1": tuple(range(4000, 4120)), "T2": tuple(range(4120, 4240)), "T3": tuple(range(4240, 4360))}
POOL = tuple(range(4360, 5000))             # 640 look items, disjoint from every train set
RESAMPLE_SIZES = (120, 240, 360, 480)       # held-out sizes reported; the choice rule takes the LARGEST viable one
DRAWS = 2000
SEARCH_SEED = 20261022                      # pilot only; a recorded cycle takes a fresh seed
GENERATIONS, POPULATION = 5, 8
POLICIES = ({"search": "mutate-incumbent/1"}, {"search": "cover/1", "lhs": 0})
SIMULATIONS = tuple({"train": t, "size": 120, **p} for p in POLICIES for t in TRAIN_SETS)
VIABLE_MIN = 0.30
THRESHOLDS = P7.THRESHOLDS                  # 0.05 (the rule), 0.05/2 (this target), 0.05/7 (the programme)
LIMITS = {"region": {"seconds": 3600, "evaluations": 15_000},
          "simulate": {"seconds": 3 * 3600, "evaluations": 50_000}}
BASELINES = {"zscore": "C.immune_zscore (the rule's trigger baseline)",
             "hotelling": "C.immune_prediction_region (exact Gaussian prediction ellipsoid; the admission competitor "
                          "on this regime)",
             "knn5": "C.immune_knn_conformal (5-NN split-conformal detector)"}
# Fixed configurations INFORMED BY PRIOR OBSERVATIONS (immune-7's region rows, measured on review seeds 3460-3999, and
# cycle 2's lineage). They are comparators only: no frozen search would select them, and they are not candidates.
INFORMED = (
    {"label": "informed:whitening-full", "inside_space": True,
     "config": {**C.IMMUNE_DEFAULT_CONFIG, "whitening": "full"}},
    {"label": "informed:full-scale1-u0.511 (cycle-2 rank 4)", "inside_space": True,
     "config": {**C.IMMUNE_DEFAULT_CONFIG, "whitening": "full", "scale_set": [1.0], "uniform_share": 0.511}},
    {"label": "informed:full-scale1-u0.492", "inside_space": True,
     "config": {**C.IMMUNE_DEFAULT_CONFIG, "whitening": "full", "scale_set": [1.0], "uniform_share": 0.492}},
    {"label": "informed:full-scale1-u0.511-a0.789 (cycle-2 rank 3)", "inside_space": False,
     "config": {**C.IMMUNE_DEFAULT_CONFIG, "whitening": "full", "scale_set": [1.0], "uniform_share": 0.511,
                "alarm_fraction": 0.789}},
    {"label": "informed:cycle-2 REJECTED candidate (a0.866)", "inside_space": False,
     "config": {**C.IMMUNE_DEFAULT_CONFIG, "whitening": "full", "scale_set": [1.0], "uniform_share": 0.492,
                "alarm_fraction": 0.866}},
)


class LimitExceeded(RuntimeError):
    pass


def forbidden_seeds() -> set:
    """Every seed the exposure audit found drawn, reserved or declared off-limits (step B)."""
    from greg.cognition.genomes import admission
    out = set(admission.P8_RESERVED) | set(admission.HELDOUT_SEEDS) | admission.spent_seeds()
    out |= set(range(1000, 1030)) | set(range(1100, 1130)) | set(range(1200, 1400)) | set(range(5001, 5041))
    out |= set(range(3000, 4000))           # native-regime tests/builder (3000-3059) and immune-7 (3100-3999)
    return out


def guard(seeds) -> tuple:
    """The seeds, or PilotError: immune-8 review seeds 4000-4999 only (development seeds 0-9 in tests)."""
    seeds = tuple(seeds)
    forbidden = forbidden_seeds()
    bad = sorted((s for s in seeds if type(s) is not int or s in forbidden
                  or not (s in REVIEW_SEEDS or s in DEV_SEEDS)), key=repr)
    if bad:
        raise PilotError(f"the immune-8 pilot uses review seeds 4000-4999 only (development 0-9 in tests); "
                         f"refused {bad[:10]}")
    return seeds


def items(seeds) -> dict:
    out = {}
    for s in guard(seeds):
        data, truth = C.immune_gaussian_instance(s)
        out[f"r{s}"] = {"data": data, "truth": truth, "category": C.immune_dimension_band(data)}
    return out


def narrow_target():
    return E.immune_target(SPACE)


def _baseline_output(name, data):
    fn = {"zscore": C.immune_zscore, "hotelling": C.immune_prediction_region, "knn5": C.immune_knn_conformal}[name]
    try:
        return {"output": fn(data)}
    except Exception as exc:                              # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {str(exc)[:160]}"}


class Pilot(P7.Pilot):
    """immune-7's in-process evaluator (the cycle's loss, memoised per configuration and item data) with the extra
    baselines, under declared resource limits."""

    def __init__(self, workers: int = WORKERS, limits: dict | None = None):
        super().__init__(workers=workers)
        self.limits = limits
        self.started = time.time()

    def check_limits(self):
        if self.limits and (self.evaluations > self.limits["evaluations"]
                            or time.time() - self.started > self.limits["seconds"]):
            raise LimitExceeded(f"declared limit exceeded: {self.evaluations} evaluations, "
                                f"{round(time.time() - self.started)} s, limits {self.limits}")

    def baseline(self, name, its: dict) -> dict:
        key = f"baseline:{name}"
        missing = {k: v for k, v in its.items() if (key, P7._fingerprint(v)) not in self.outputs}
        for v in missing.values():
            self.outputs[(key, P7._fingerprint(v))] = _baseline_output(name, v["data"])
        outputs = {k: self.outputs[(key, P7._fingerprint(v))] for k, v in its.items()}
        return E.SealedEvaluator(its, C.immune_score).losses(outputs)


def clopper_pearson_upper(wrong: int, n: int, level: float = 0.95) -> float:
    """One-sided exact upper confidence bound on a binomial rate (``wrong`` of ``n``). With 0 wrong it is
    1 - (1 - level)^(1/n): zero observed errors bound the rate, they never show it is zero."""
    from scipy.stats import beta
    return 1.0 if wrong >= n else float(beta.ppf(level, wrong + 1, n - wrong))


def errors(ls: dict) -> dict:
    wrong = sum(1 for v in ls.values() if math.isinf(v))
    return {"wrong": wrong, "n": len(ls), "rate": round(wrong / len(ls), 6),
            "upper_95": round(clopper_pearson_upper(wrong, len(ls)), 6)}


def on_pool(pilot, ls: dict, reference: dict, baselines: dict) -> dict:
    return {**P7.describe(ls), "errors": errors(ls), "vs_incumbent": P7.paired(ls, reference),
            "vs_baselines": {name: P7.paired(ls, b) for name, b in baselines.items()},
            "resampled": [P7.resampled(ls, reference, n, draws=DRAWS, seed=8) for n in RESAMPLE_SIZES]}


def region(*, pilot=None) -> dict:
    """The incumbent, the baselines and the informed fixed configurations on the pool, and the repaired stress gate
    of each informed configuration on every train set's stress items."""
    started = time.time()
    guard(POOL), guard(sorted(s for seeds in TRAIN_SETS.values() for s in seeds))
    pilot = pilot or Pilot(limits=LIMITS["region"])
    pool = items(POOL)
    inc = pilot.target.incumbent
    reference = pilot.losses(inc, pool)
    baselines = {name: pilot.baseline(name, pool) for name in BASELINES}
    trains = {t: items(seeds) for t, seeds in TRAIN_SETS.items()}
    stresses = {t: E._immune_stress(tr) for t, tr in trains.items()}
    out = {"schema": "greg-p8-immune8-region/1", "space": SPACE,
           "seeds": {"pool": [min(POOL), max(POOL)], "train": {t: [min(s), max(s)] for t, s in TRAIN_SETS.items()}},
           "incumbent": {"id": E.config_id(inc), "pool": {**P7.describe(reference), "errors": errors(reference),
                                                          "vs_baselines": {n: P7.paired(reference, b)
                                                                           for n, b in baselines.items()}},
                         "stress": {}},
           "baselines": {name: {"what": BASELINES[name], **P7.describe(b), "errors": errors(b),
                                "vs_incumbent": P7.paired(b, reference)} for name, b in baselines.items()},
           "trigger": {}, "rows": []}
    for t, tr in trains.items():
        inc_t, z_t = pilot.losses(inc, tr), pilot.baseline("zscore", tr)
        out["trigger"][t] = round(sum(inc_t[k] > z_t[k] for k in tr) / len(tr), 4)
        inc_s = pilot.losses(inc, stresses[t])
        out["incumbent"]["stress"][t] = {kind: errors({k: v for k, v in inc_s.items() if k.startswith(kind + ":")})
                                         for kind in ("scarce", "strict")}
    for entry in INFORMED:
        pilot.check_limits()
        config = pilot.target.validate(entry["config"])
        if entry["inside_space"] != _inside(config):
            raise PilotError(f"{entry['label']}: declared inside_space is wrong")
        ls = pilot.losses(config, pool)
        row = {"label": entry["label"], "informed_by_prior_observations": True, "inside_space": entry["inside_space"],
               "id": E.config_id(config), "config": config, "pool": on_pool(pilot, ls, reference, baselines),
               "gate": {t: gate(pilot, config, stresses[t]) for t in TRAIN_SETS}}
        passes = [row["gate"][t]["passes_fixed_gate"] for t in TRAIN_SETS]
        row["fixed_protocol_retain"] = [{"n": r["n"], **{k: round(v * sum(passes) / len(passes), 4)
                                                         for k, v in r.items() if k.startswith("retain_rate")}}
                                        for r in row["pool"]["resampled"]]
        out["rows"].append(row)
    out.update(evaluations=pilot.evaluations, seconds=round(time.time() - started, 1))
    return out


def _inside(config) -> bool:
    try:
        narrow_target().validate(config)
        return True
    except E.EvolutionError:
        return False


def simulate_one(pilot, train: dict, pool: dict, setting: dict, reference: dict, baselines: dict) -> dict:
    """One simulated cycle: the cycle's own trigger, search (in the declared narrower space), train-gain gate and
    repaired adversarial gate; the held-out step is resampled from the pool."""
    target = narrow_target()
    inc = target.incumbent
    declared = E.search_setting(target, setting["search"], seed=SEARCH_SEED, lhs=setting.get("lhs", 0))
    inc_train, base_train = pilot.losses(inc, train), pilot.baseline("zscore", train)
    inc_mean = round(statistics.fmean(inc_train.values()), 6)

    def evaluate(config):
        pilot.check_limits()
        return pilot.losses(config, train)
    found = E.run_search(target, evaluate, generations=GENERATIONS, population=POPULATION, seed=SEARCH_SEED,
                         incumbent_loss=inc_mean, initial=declared.get("initial", ()))
    best = found["candidate"]["config"]
    gain = E.relative_gain(inc_mean, found["candidate"]["train_mean_loss"])
    rate = sum(1 for k in train if inc_train[k] > base_train[k]) / len(train)
    stages = {"triggered": rate >= E.FAILURE_RATE_TRIGGER,
              "advances": found["candidate"]["id"] != E.config_id(inc) and gain > E.TRAIN_GAIN_MIN}
    g = gate(pilot, best, E._immune_stress(train)) if stages["advances"] else None
    stages["adversarial_passes"] = bool(g and g["passes_fixed_gate"])
    ls = pilot.losses(best, pool)
    out = {"settings": setting, "evaluated": found["evaluated"], "incumbent_failure_rate": round(rate, 4),
           "incumbent_train": {**P7.describe(inc_train), "errors": errors(inc_train)},
           "candidate": {"id": found["candidate"]["id"], "config": best,
                         "train_mean_loss": round(found["candidate"]["train_mean_loss"], 6)},
           "train_gain": gain if math.isinf(gain) else round(gain, 4),
           "candidate_train": {**P7.describe(pilot.losses(best, train)), "errors": errors(pilot.losses(best, train))},
           "top_train": [{"id": s["id"], "ops": s["ops"], "config": s["config"], "train_mean_loss": s["train_mean_loss"]}
                         for s in sorted(found["lineage"], key=lambda s: (s["train_mean_loss"], s["id"]))[:5]],
           "gate": g, "stages": stages, "pool": on_pool(pilot, ls, reference, baselines)}
    passes = all(stages.values())
    out["resampled_retain"] = [{"n": r["n"], **{k: (v if passes else 0.0) for k, v in r.items()
                                                if k.startswith("retain_rate")}} for r in out["pool"]["resampled"]]
    out["would_reach_heldout"] = passes
    return out


def simulate(simulations=SIMULATIONS, *, pilot=None) -> dict:
    started = time.time()
    guard(POOL), guard(sorted(s for seeds in TRAIN_SETS.values() for s in seeds))
    pilot = pilot or Pilot(limits=LIMITS["simulate"])
    pool = items(POOL)
    reference = pilot.losses(pilot.target.incumbent, pool)
    baselines = {name: pilot.baseline(name, pool) for name in BASELINES}
    runs, stopped = [], None
    for setting in simulations:
        try:
            pilot.check_limits()
            runs.append(simulate_one(pilot, items(TRAIN_SETS[setting["train"]][:setting["size"]]), pool, setting,
                                     reference, baselines))
        except LimitExceeded as exc:
            stopped = str(exc)
            break
        print(json.dumps({"done": setting, "stages": runs[-1]["stages"], "seconds": round(time.time() - started)}),
              flush=True)
    return {"schema": "greg-p8-immune8-simulate/1", "space": SPACE,
            "seeds": {"train": {k: [min(v), max(v)] for k, v in TRAIN_SETS.items()}, "pool": [min(POOL), max(POOL)]},
            "search_seed": SEARCH_SEED, "generations": GENERATIONS, "population": POPULATION,
            "complete": stopped is None and len(runs) == len(simulations), "stopped": stopped,
            "runs": runs, "evaluations": pilot.evaluations, "seconds": round(time.time() - started, 1)}


def choose(sim: dict) -> dict:
    """The declared decision rule.

    - INCOMPLETE (a declared limit stopped the pilot) is NOT_VIABLE: an incomplete pilot never qualifies.
    - VIABLE iff the trigger fires on at least 2 of the 3 train sets AND some (policy, held-out size n) cell has a mean
      simulated P(RETAIN) at alpha 0.05, under the unchanged rule and the repaired stress gate, of at least 0.30.
    - The held-out size is the LARGEST n with such a cell (a smaller n is never chosen to hide rare errors); the
      policy is the one with the highest mean P(RETAIN) at the programme-wide 0.05/7 at that n, ties to
      mutate-incumbent/1."""
    triggered = {r["settings"]["train"]: r["stages"]["triggered"] for r in sim["runs"]}
    cells = {}
    for run in sim["runs"]:
        for r in run["resampled_retain"]:
            cells.setdefault((run["settings"]["search"], r["n"]), []).append(r)
    table = [{"search": k[0], "heldout_size": k[1], "runs": len(v),
              **{f"mean_{name}": round(statistics.fmean(r[name] for r in v), 4)
                 for name in v[0] if name.startswith("retain_rate")}} for k, v in sorted(cells.items())]
    best = max((row["mean_retain_rate_alpha"] for row in table), default=0.0)
    viable_cells = [row for row in table if row["mean_retain_rate_alpha"] >= VIABLE_MIN]
    complete = sim.get("complete", True) and len(sim["runs"]) == len(SIMULATIONS)
    viable = complete and sum(triggered.values()) >= 2 and bool(viable_cells)
    choice = None
    if viable:
        n = max(row["heldout_size"] for row in viable_cells)
        at_n = sorted((row for row in viable_cells if row["heldout_size"] == n),
                      key=lambda row: (-row["mean_retain_rate_programme_7"], row["search"] != "mutate-incumbent/1"))
        choice = {"search": at_n[0]["search"], "train_size": 120, "heldout_size": n,
                  "zero_violation_upper_95_at_n": round(clopper_pearson_upper(0, n), 6)}
    return {"complete": complete, "triggered_by_train_set": triggered, "best_mean_retain_alpha": best,
            "viable_min": VIABLE_MIN, "verdict": "VIABLE" if viable else "NOT_VIABLE", "table": table,
            "choice": choice}


def summarise(directory: Path) -> dict:
    directory = Path(directory)
    out = {}
    if (directory / "region.json").is_file():
        out["region"] = json.loads((directory / "region.json").read_text())
    if (directory / "simulate.json").is_file():
        out["decision"] = choose(json.loads((directory / "simulate.json").read_text()))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", choices=("gate-audit", "region", "simulate", "summarise"))
    ap.add_argument("--dir", type=Path, help="summarise: the pilot directory")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    if args.mode == "summarise":
        args.out.write_text(json.dumps(summarise(args.dir), indent=1) + "\n")
        print(json.dumps({"out": str(args.out)}))
        return
    pilot = Pilot(limits=LIMITS.get(args.mode))
    try:
        result = {"gate-audit": gate_audit, "region": region, "simulate": simulate}[args.mode](pilot=pilot)
    finally:
        pilot.close()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps({"out": str(args.out), "evaluations": result["evaluations"], "seconds": result["seconds"]}))


if __name__ == "__main__":
    main()
