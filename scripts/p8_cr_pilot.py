"""Design pilot for P8 cycle 5 on the constraint-release target, on REVIEW seeds only (3000-3999).

Cycle 4 (2026-10-15) searched 39 configurations of ``develop_constraint_release``'s search policy, kept a candidate
that was 23.7% better on train and lost 26-37 on held-out, while random restart (the target's baseline) beat the
incumbent on 53% of train items. Its search tried ``p_restart`` only at 0.064, 0.156 and 0.339. This pilot asks,
before any cycle-5 split is drawn, whether a restart-heavy region of the closed space beats the incumbent on two
independent halves of review seeds, and whether a search that starts from a declared cover of the space would select
it under the unchanged rule. It is design knowledge, disclosed in the cycle-5 pre-registration; it is not evidence
for the cycle and it decides nothing.

Every loss is computed as the cycle computes it: ``SealedEvaluator.losses`` over ``constraint_release_score`` on the
output of ``constraint_release_solve_with`` (the sandbox's method) or of ``constraint_release_random_restart`` (the
target's baseline), run in this process. Stress items come from the cycle's own ``_cr_stress``. A simulated cycle
runs the cycle's own ``search`` and decision constants. The guard refuses any seed outside the review range (and the
development seeds 0-9, which only the unit test uses), so no P8-reserved or admission instance is ever generated.

    PYTHONPATH=. taskset -c 1 python scripts/p8_cr_pilot.py grid --out grid.json
    PYTHONPATH=. taskset -c 1 python scripts/p8_cr_pilot.py simulate --settings S --pool 3200-3499 --out sim.json
    PYTHONPATH=. taskset -c 1 python scripts/p8_cr_pilot.py region --configs C --pool 3200-3499 --out region.json
    PYTHONPATH=. python scripts/p8_cr_pilot.py summarise --dir pilot --out pilot/summary.json
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from greg.cognition import evolution as E                      # noqa: E402
from greg.cognition.genomes import admission, developmental as D   # noqa: E402

REVIEW_SEEDS = range(3000, 4000)
DEV_SEEDS = range(0, 10)
PILOT_TRAIN = tuple(range(3000, 3060))
PILOT_TEST = tuple(range(3060, 3120))
CYCLE_4_RECORD = ROOT / "docs/evidence/greg-protected-evolution/2026-10-15-cr-4/cycle-cr-4.json"


class PilotError(ValueError):
    pass


def guard(seeds) -> tuple:
    """The seeds, or PilotError: only review seeds (and development seeds, for tests), never a P8-reserved,
    admission or spent seed."""
    seeds = tuple(seeds)
    forbidden = set(admission.P8_RESERVED) | set(admission.HELDOUT_SEEDS) | admission.spent_seeds()
    bad = sorted(s for s in seeds if type(s) is not int or s in forbidden
                 or not (s in REVIEW_SEEDS or s in DEV_SEEDS))
    if bad:
        raise PilotError(f"the pilot uses review seeds 3000-3999 only (development 0-9 in tests); refused {bad[:10]}")
    return seeds


def items(seeds) -> dict:
    out = {}
    for s in guard(seeds):
        data, truth = D.constraint_release_instance(s)
        out[f"r{s}"] = {"data": data, "truth": truth, "category": D.constraint_release_subregion(data)}
    return out


class Pilot:
    """In-process evaluation with the cycle's own loss; memoised per (configuration, item)."""

    def __init__(self):
        self.target = E.cr_target()
        self.cache: dict = {}
        self.evaluations = 0

    def _output(self, config, data):
        if config == "random_restart":
            return {"output": D.constraint_release_random_restart(data)}
        try:
            out = D.constraint_release_solve_with(config, data)
            return {"output": out["output"], "certificate": out["certificate"]}
        except Exception as exc:                      # as the sandbox records it: an error is no answer
            return {"error": f"{type(exc).__name__}: {str(exc)[:160]}"}

    def losses(self, config, its: dict) -> dict:
        key = "random_restart" if config == "random_restart" else E.config_id(self.target.validate(config))
        missing = {k: v for k, v in its.items() if (key, k, _fingerprint(v)) not in self.cache}
        if missing:
            outputs = {k: self._output(config, v["data"]) for k, v in missing.items()}
            self.evaluations += len(missing)
            for k, loss in E.SealedEvaluator(missing, D.constraint_release_score).losses(outputs).items():
                self.cache[(key, k, _fingerprint(missing[k]))] = loss
        return {k: self.cache[(key, k, _fingerprint(v))] for k, v in its.items()}


def _fingerprint(item) -> str:
    """Stress items share ids with their source item but differ in data: memoise by the data's digest."""
    return E.digest(item["data"])


def paired(a: dict, b: dict) -> dict:
    """a against b on the same items, as the cycle counts them: lower loss wins (1e-12 tolerance)."""
    wins = sum(1 for k in a if a[k] < b[k] - 1e-12)
    losses = sum(1 for k in a if b[k] < a[k] - 1e-12)
    return {"wins": wins, "losses": losses, "ties": len(a) - wins - losses,
            "sign_test_p_one_sided": round(E.sign_test(wins, losses), 6)}


def mean(values) -> float:
    return round(statistics.fmean(values), 6)


def resampled_decision(candidate: dict, incumbent: dict, n: int, *, draws: int = 2000, seed: int = 0) -> dict:
    """How often the rule's held-out step would RETAIN on ``n`` items drawn with replacement from a pool: the
    one-sided sign test gives p < ALPHA and the candidate's mean loss is lower (and the same at ALPHA / 3)."""
    import random
    keys = sorted(candidate)
    rng = random.Random(f"p8-cr-pilot-resample:{seed}:{n}")
    retain = retain_3 = 0
    for _ in range(draws):
        sample = [keys[rng.randrange(len(keys))] for _ in range(n)]
        wins = sum(1 for k in sample if candidate[k] < incumbent[k] - 1e-12)
        losses = sum(1 for k in sample if incumbent[k] < candidate[k] - 1e-12)
        lower = sum(candidate[k] for k in sample) < sum(incumbent[k] for k in sample)
        p = E.sign_test(wins, losses)
        retain += p < E.ALPHA and lower
        retain_3 += p < E.ALPHA / 3 and lower
    return {"n": n, "draws": draws, "retain_rate": round(retain / draws, 4),
            "retain_rate_at_alpha_over_3": round(retain_3 / draws, 4)}


def on_pool(pilot, config, pool: dict, reference: dict, sizes=(90, 180)) -> dict:
    """A configuration against the incumbent on a fresh pool: paired counts, means, the rule's resampled decision."""
    ls = pilot.losses(config, pool)
    out = {"mean_loss": mean(ls.values()), "incumbent_mean_loss": mean(reference.values()),
           "vs_incumbent": paired(ls, reference)}
    out["resampled"] = [resampled_decision(ls, reference, n) for n in sizes]
    return out


def grid_configs() -> list[dict]:
    """The pilot grid: p_restart x (mu, offspring) x tournament with the other floats at the incumbent, then the
    other three probabilities at their bounds for three p_restart levels."""
    inc = dict(D.CR_DEFAULT_CONFIG)
    out = []
    for p, (mu, lam), t in itertools.product((0.0, 0.25, 0.5, 0.75, 0.9, 1.0),
                                             ((2, 2), (4, 4), (8, 8), (2, 8), (8, 2)), (1, 2, 3)):
        out.append({**inc, "p_restart": p, "mu": mu, "offspring": lam, "tournament": t})
    for p, (rec, extra, extra_rec) in itertools.product((0.0, 0.5, 0.9), ((0.0, 0.0, 0.0), (0.9, 0.9, 0.9),
                                                                          (0.9, 0.0, 0.0), (0.0, 0.9, 0.9))):
        out.append({**inc, "p_restart": p, "p_recombine": rec, "p_extra_mutation": extra,
                    "p_extra_mutation_recombined": extra_rec})
    target = E.cr_target()
    seen, unique = set(), []
    for c in out:
        c = target.validate(c)
        if E.config_id(c) not in seen:
            seen.add(E.config_id(c))
            unique.append(c)
    return unique


def cycle_4_configs() -> list[dict]:
    """The configurations cycle 4 evaluated, read from its frozen record (no instance of its split is generated)."""
    if not CYCLE_4_RECORD.is_file():
        return []
    record = json.loads(CYCLE_4_RECORD.read_text())
    return [{"id": step["id"], "config": step["config"], "cycle_4_train_mean_loss": step["train_mean_loss"]}
            for step in record["search"]["lineage"]]


def grid(train_seeds=PILOT_TRAIN, test_seeds=PILOT_TEST, *, configs=None, stress=True, cycle4=True) -> dict:
    started = time.time()
    train_seeds, test_seeds = guard(train_seeds), guard(test_seeds)          # both, before any instance exists
    pilot = Pilot()
    halves = {"pilot_train": items(train_seeds), "pilot_test": items(test_seeds)}
    stress_items = E._cr_stress(halves["pilot_train"]) if stress else {}
    inc = dict(D.CR_DEFAULT_CONFIG)
    rows = []
    reference = {h: pilot.losses(inc, its) for h, its in halves.items()}
    restart = {h: pilot.losses("random_restart", its) for h, its in halves.items()}
    configs = grid_configs() if configs is None else configs
    entries = [{"config": c, "source": "grid"} for c in configs]
    if cycle4:
        known = {E.config_id(e["config"]) for e in entries}
        for step in cycle_4_configs():
            if step["id"] in known:
                next(e for e in entries if E.config_id(e["config"]) == step["id"])["cycle_4_train_mean_loss"] = \
                    step["cycle_4_train_mean_loss"]
                continue
            entries.append({"config": step["config"], "source": "cycle-4 lineage",
                            "cycle_4_train_mean_loss": step["cycle_4_train_mean_loss"]})
    for entry in entries:
        config = entry["config"]
        row = {"id": E.config_id(config), "config": config, "source": entry["source"]}
        if "cycle_4_train_mean_loss" in entry:
            row["cycle_4_train_mean_loss"] = entry["cycle_4_train_mean_loss"]
        for half, its in halves.items():
            ls = pilot.losses(config, its)
            row[half] = {"mean_loss": mean(ls.values()), "vs_incumbent": paired(ls, reference[half]),
                         "vs_random_restart": paired(ls, restart[half])}
        if stress_items:
            ls = pilot.losses(config, stress_items)
            inc_s = pilot.losses(inc, stress_items)
            row["stress"] = {kind: {"mean_loss": mean(v for k, v in ls.items() if k.startswith(kind + ":")),
                                    "incumbent": mean(v for k, v in inc_s.items() if k.startswith(kind + ":"))}
                             for kind in ("lean", "fewval")}
            row["stress"]["passes_gate"] = not any(E.worsened(v["incumbent"], v["mean_loss"])
                                                   for v in row["stress"].values() if isinstance(v, dict))
        rows.append(row)
    summary = {h: {"incumbent_mean_loss": mean(reference[h].values()),
                   "random_restart_mean_loss": mean(restart[h].values()),
                   "random_restart_vs_incumbent": paired(restart[h], reference[h]),
                   "incumbent_failure_rate_vs_random_restart": round(
                       sum(1 for k in reference[h] if reference[h][k] > restart[h][k]) / len(reference[h]), 4)}
               for h in halves}
    return {"schema": "greg-p8-cr-pilot-grid/1", "seeds": {"pilot_train": [min(train_seeds), max(train_seeds)],
                                                           "pilot_test": [min(test_seeds), max(test_seeds)]},
            "incumbent": {"id": E.config_id(inc), "config": inc}, "summary": summary, "rows": rows,
            "evaluations": pilot.evaluations, "seconds": round(time.time() - started, 1)}


def simulate(train_seeds=PILOT_TRAIN, test_seeds=PILOT_TEST, *, settings: list[dict], pool_seeds=()) -> dict:
    """Simulated cycles: each runs the cycle's own ``search`` on pilot-train, applies the unchanged rule's train,
    adversarial and held-out steps with pilot-test as the one look, and reports the decision it would reach. The
    verification step is the target's own verifier on every stress output."""
    started = time.time()
    train_seeds, test_seeds, pool_seeds = guard(train_seeds), guard(test_seeds), guard(pool_seeds)
    if set(pool_seeds) & (set(train_seeds) | set(test_seeds)):
        raise PilotError("the look pool must be fresh: disjoint from the simulated train and test seeds")
    pilot = Pilot()
    train, test, pool = items(train_seeds), items(test_seeds), items(pool_seeds)
    target = pilot.target
    inc = target.incumbent
    stress = E._cr_stress(train)
    baseline_train = pilot.losses("random_restart", train)
    runs = []
    for s in settings:
        setting = E.search_setting(target, s["search"], seed=s["seed"], lhs=s.get("lhs", 0))
        inc_train = pilot.losses(inc, train)
        found = E.run_search(target, lambda config: pilot.losses(config, train), generations=s["generations"],
                             population=s["population"], seed=s["seed"],
                             incumbent_loss=round(statistics.fmean(inc_train.values()), 6),
                             initial=setting.get("initial", ()))
        out = {"settings": s, "declared_initial": len(setting.get("initial", ())), "evaluated": found["evaluated"],
               "incumbent_failure_rate": round(sum(1 for k in train if inc_train[k] > baseline_train[k]) / len(train),
                                               4),
               "incumbent_train_mean_loss": mean(inc_train.values()),
               "candidate": {"id": found["candidate"]["id"], "config": found["candidate"]["config"],
                             "train_mean_loss": round(found["candidate"]["train_mean_loss"], 6)}}
        best = found["candidate"]["config"]
        gain = E.relative_gain(round(statistics.fmean(inc_train.values()), 6), found["candidate"]["train_mean_loss"])
        out["candidate"]["p_restart"] = best["p_restart"]
        out["top_train"] = [{"id": st["id"], "ops": st["ops"], "p_restart": st["config"]["p_restart"],
                             "train_mean_loss": st["train_mean_loss"]}
                            for st in sorted(found["lineage"], key=lambda st: (st["train_mean_loss"], st["id"]))[:5]]
        out["train_gain"] = round(gain, 4)
        stages = {"triggered": out["incumbent_failure_rate"] >= E.FAILURE_RATE_TRIGGER,
                  "advances": found["candidate"]["id"] != E.config_id(inc) and gain > E.TRAIN_GAIN_MIN}
        inc_s, cand_s = pilot.losses(inc, stress), pilot.losses(best, stress)
        verified = all(all(D.constraint_release_verify(stress[k]["data"], o["output"], o["certificate"]).values())
                       for k, o in ((k, pilot._output(best, stress[k]["data"])) for k in stress)
                       if o.get("output") is not None)
        adversarial = {kind: {"incumbent": mean(v for k, v in inc_s.items() if k.startswith(kind + ":")),
                              "candidate": mean(v for k, v in cand_s.items() if k.startswith(kind + ":"))}
                       for kind in ("lean", "fewval")}
        stages["adversarial_passes"] = verified and not any(E.worsened(v["incumbent"], v["candidate"])
                                                            for v in adversarial.values())
        out["adversarial"] = {**adversarial, "all_outputs_verified": verified}
        inc_t, cand_t = pilot.losses(inc, test), pilot.losses(best, test)
        look = paired(cand_t, inc_t)
        look.update(incumbent_mean_loss=mean(inc_t.values()), candidate_mean_loss=mean(cand_t.values()))
        stages["heldout_passes"] = look["sign_test_p_one_sided"] < E.ALPHA and \
            statistics.fmean(cand_t.values()) < statistics.fmean(inc_t.values())
        stages["heldout_passes_bonferroni_3"] = look["sign_test_p_one_sided"] < E.ALPHA / 3 and \
            statistics.fmean(cand_t.values()) < statistics.fmean(inc_t.values())
        out["pilot_test_look"] = look
        if pool:
            out["pool"] = on_pool(pilot, best, pool, pilot.losses(inc, pool))
        out["stages"] = stages
        out["would_decide"] = ("NO_RECURRING_FAILURE" if not stages["triggered"] else "RETAIN" if all(
            stages[k] for k in ("advances", "adversarial_passes", "heldout_passes")) else "REJECT")
        runs.append(out)
    return {"schema": "greg-p8-cr-pilot-simulate/1",
            "seeds": {"pilot_train": [min(train_seeds), max(train_seeds)],
                      "pilot_test": [min(test_seeds), max(test_seeds)],
                      "pool": [min(pool_seeds), max(pool_seeds)] if pool_seeds else None},
            "runs": runs, "evaluations": pilot.evaluations, "seconds": round(time.time() - started, 1)}


def region(pool_seeds, configs: list[dict]) -> dict:
    """Fixed configurations (and random restart) against the incumbent on a fresh pool, with per-item losses."""
    started = time.time()
    pool_seeds = guard(pool_seeds)
    pilot = Pilot()
    pool = items(pool_seeds)
    reference = pilot.losses(dict(D.CR_DEFAULT_CONFIG), pool)
    rows = [{"id": "random_restart", "config": "random_restart",
             **on_pool(pilot, "random_restart", pool, reference),
             "losses": pilot.losses("random_restart", pool)}]
    for entry in configs:
        config = pilot.target.validate(entry["config"])
        rows.append({"id": E.config_id(config), "config": config, "why": entry.get("why"),
                     **on_pool(pilot, config, pool, reference), "losses": pilot.losses(config, pool)})
    return {"schema": "greg-p8-cr-pilot-region/1", "seeds": {"pool": [min(pool_seeds), max(pool_seeds)]},
            "incumbent": {"config": dict(D.CR_DEFAULT_CONFIG), "losses": reference}, "rows": rows,
            "evaluations": pilot.evaluations, "seconds": round(time.time() - started, 1)}


def spearman(xs, ys) -> float:
    """Spearman's rank correlation with average ranks for ties."""
    def ranks(values):
        order = sorted(range(len(values)), key=lambda i: values[i])
        out, i = [0.0] * len(values), 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            for k in range(i, j + 1):
                out[order[k]] = (i + j) / 2
            i = j + 1
        return out
    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    return cov / (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5


def summarise(directory: Path) -> dict:
    """Every derived number the pre-registration states, computed from the pilot's own files."""
    directory = Path(directory)
    grid_ = json.loads((directory / "grid.json").read_text())
    s, rows = grid_["summary"], grid_["rows"]

    def passes(row, half):
        return (row[half]["vs_incumbent"]["sign_test_p_one_sided"] < E.ALPHA
                and row[half]["mean_loss"] < s[half]["incumbent_mean_loss"])
    levels = {}
    for row in rows:
        if row["source"] != "grid":
            continue
        levels.setdefault(row["config"]["p_restart"], []).append(row)
    by_level = [{"p_restart": p, "n": len(rs),
                 **{f"{h}_mean_loss": round(statistics.fmean(r[h]["mean_loss"] for r in rs), 5)
                    for h in ("pilot_train", "pilot_test")},
                 **{f"{h}_wins_losses": [round(statistics.fmean(r[h]["vs_incumbent"][k] for r in rs), 1)
                                         for k in ("wins", "losses")] for h in ("pilot_train", "pilot_test")},
                 "sign_both": sum(1 for r in rs if all(r[h]["vs_incumbent"]["sign_test_p_one_sided"] < E.ALPHA
                                                       for h in ("pilot_train", "pilot_test"))),
                 "lower_mean_both": sum(1 for r in rs if all(r[h]["mean_loss"] < s[h]["incumbent_mean_loss"]
                                                             for h in ("pilot_train", "pilot_test"))),
                 "stress_gate": sum(1 for r in rs if r["stress"]["passes_gate"])}
                for p, rs in sorted(levels.items())]
    both = [r for r in rows if passes(r, "pilot_train") and passes(r, "pilot_test")]
    out = {"grid": {"summary": s, "configurations": len(rows),
                    "by_p_restart": by_level,
                    "pass_both_halves": [{"id": r["id"], "p_restart": r["config"]["p_restart"],
                                          "stress_gate": r["stress"]["passes_gate"]} for r in both],
                    "spearman_train_test_mean_loss": round(spearman(
                        [r["pilot_train"]["mean_loss"] for r in rows], [r["pilot_test"]["mean_loss"] for r in rows]), 3),
                    "cycle_4_candidate": next(({k: r[k] for k in ("pilot_train", "pilot_test", "stress")}
                                               for r in rows if r["id"] == "cfg-afdb92cb42e7"), None)}}
    region_ = json.loads((directory / "region.json").read_text())
    nine = {r["id"] for r in both}
    out["region"] = {"seeds": region_["seeds"], "rows": [
        {"id": r["id"], "why": r.get("why"), "passed_both_halves": r["id"] in nine, "mean_loss": r["mean_loss"],
         "incumbent_mean_loss": r["incumbent_mean_loss"], "vs_incumbent": r["vs_incumbent"],
         "resampled": r["resampled"]} for r in region_["rows"]]}
    sims = []
    for path in sorted(directory.glob("simulate-*-T*.json")):
        if path.name.endswith("settings.json"):
            continue
        d = json.loads(path.read_text())
        for run in d["runs"]:
            st = run["settings"]
            sims.append({"file": path.name, "train": d["seeds"]["pilot_train"], "search": st["search"],
                         "lhs": st.get("lhs"), "generations": st["generations"], "seed": st["seed"],
                         "evaluated": run["evaluated"], "failure_rate": run["incumbent_failure_rate"],
                         "candidate": run["candidate"]["id"], "p_restart": run["candidate"]["config"]["p_restart"],
                         "stages": run["stages"], "pool": run["pool"]})
    policies = {}
    for sim in sims:
        policies.setdefault(f"{sim['search']} lhs={sim['lhs']} generations={sim['generations']} "
                            f"seed={sim['seed']}", []).append(sim)
    out["simulated"] = {"runs": sims, "by_policy": {
        k: {"runs": len(v), **{f"mean_retain_rate_n{size}": round(statistics.fmean(
            x["pool"]["resampled"][i]["retain_rate"] for x in v), 3) for i, size in enumerate((90, 180))},
            **{f"mean_retain_rate_n{size}_at_alpha_over_3": round(statistics.fmean(
                x["pool"]["resampled"][i]["retain_rate_at_alpha_over_3"] for x in v), 3)
               for i, size in enumerate((90, 180))}} for k, v in policies.items()},
        "failure_rates": sorted({x["failure_rate"] for x in sims})}
    return out


def _range(text: str) -> tuple:
    lo, hi = (int(v) for v in text.split("-"))
    return tuple(range(lo, hi + 1))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", choices=("grid", "simulate", "region", "summarise"))
    ap.add_argument("--train", type=_range, default=PILOT_TRAIN, help="review seeds, e.g. 3000-3059")
    ap.add_argument("--test", type=_range, default=PILOT_TEST, help="review seeds, e.g. 3060-3119")
    ap.add_argument("--settings", type=Path, help="simulate: a JSON list of cycle settings")
    ap.add_argument("--pool", type=_range, default=(), help="simulate, region: a fresh look pool, e.g. 3200-3499")
    ap.add_argument("--configs", type=Path, help="region: a JSON list of {config, why}")
    ap.add_argument("--dir", type=Path, help="summarise: the pilot directory")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    if args.mode == "summarise":
        args.out.write_text(json.dumps(summarise(args.dir), indent=1) + "\n")
        print(json.dumps({"out": str(args.out)}))
        return
    if args.mode == "grid":
        result = grid(args.train, args.test)
    elif args.mode == "region":
        result = region(args.pool, json.loads(args.configs.read_text()))
    else:
        result = simulate(args.train, args.test, settings=json.loads(args.settings.read_text()),
                          pool_seeds=args.pool)
    args.out.write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps({"out": str(args.out), "evaluations": result["evaluations"], "seconds": result["seconds"]}))


if __name__ == "__main__":
    main()
