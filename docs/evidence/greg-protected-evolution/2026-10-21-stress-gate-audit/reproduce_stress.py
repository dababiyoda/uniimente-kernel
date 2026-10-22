"""Reproduce one recorded P8 cycle's STRESS-SET per-item losses from its TRAIN items only, at its source commit.

Run with the source commit's checkout as cwd/argv[1]. Never builds or scores a held-out item: train items are built
from the train seeds (or, for forecasting, the first half of the commit's shuffled pool) by the commit's own
generators, the train seal is recomputed with the commit's SealedEvaluator and compared with the record, then the
incumbent and recorded candidate configurations run in-process on the commit's stress derivation (JSON round-trip
both ways, as the sandbox did; the sandbox's caught exceptions become a missing output, as the sandbox did), and the
commit's sealed evaluator scores them.
usage: reproduce_stress.py CHECKOUT RECORD.json OUT.json
"""
import json
import random
import sys
import time
from pathlib import Path

checkout, record_path, out_path = Path(sys.argv[1]).resolve(), Path(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, str(checkout))
from greg.cognition import evolution as E  # noqa: E402  (the source commit's code)
from greg.cognition.genomes.contract import GenomeError  # noqa: E402

record = json.loads(record_path.read_text())
target = record["target"]
regenerated = []

if target == "forecast_quantile":
    from greg.cognition.genomes import admission, forecasting
    pool = forecasting.admission_series()
    # fe222f4's forecasting_split(808), TRAIN half only
    used = {forecasting.instance(s)[0]["series_id"] for s in (*admission.DEV_SEEDS, *admission.HELDOUT_SEEDS)}
    free = sorted((s for s in pool if s["id"] not in used), key=lambda s: int(s["id"][1:]))
    random.Random(808).shuffle(free)
    half = len(free) // 2
    train = {s["id"]: {"data": {"history": s["train"], "horizon": 13, "levels": list(forecasting.LEVELS),
                                "series_id": s["id"]}, "truth": {"actual": s["test"]}} for s in free[:half]}
    regenerated = sorted(train)
    score, stress_fn, method = forecasting.score, E._stress, forecasting.solve_with
elif target == "immune_detect":
    from greg.cognition.genomes import collective
    seeds = E.IMMUNE_TRAIN_SEEDS
    train = {}
    for s in seeds:
        data, truth = collective.immune_instance(s)
        train[f"s{s}"] = {"data": data, "truth": truth}
    regenerated = list(seeds)
    score, stress_fn, method = collective.immune_score, E._immune_stress, collective.immune_solve_with
elif target == "constraint_release":
    from greg.cognition.genomes import developmental
    seeds = E.CR_SPLITS[E.CR_CURRENT_SPLIT][0] if hasattr(E, "CR_SPLITS") else E.CR_TRAIN_SEEDS
    train = {}
    for s in seeds:
        data, truth = developmental.constraint_release_instance(s)
        train[f"s{s}"] = {"data": data, "truth": truth}
    regenerated = list(seeds)
    score, stress_fn, method = (developmental.constraint_release_score, E._cr_stress,
                                developmental.constraint_release_solve_with)
else:
    raise SystemExit(f"unknown target {target}")

seal = E.SealedEvaluator(train, score).seal
seal_ok = seal == record["evaluator_seals"]["train"]
print(target, "train items", len(train), "train seal matches record:", seal_ok, flush=True)
if not seal_ok:
    raise SystemExit("train seal mismatch: the reproduced train items are not the recorded ones")

stress = E.SealedEvaluator(stress_fn(train), score)
problems = json.loads(json.dumps(stress.problems()))


def run(config):
    config = json.loads(json.dumps(config))
    outputs = {}
    for p in problems:
        try:
            out = method(config, p["data"])
            outputs[p["id"]] = {"output": out["output"], "certificate": out["certificate"]}
        except (GenomeError, ValueError, ZeroDivisionError, OverflowError) as exc:
            outputs[p["id"]] = {"error": f"{type(exc).__name__}: {str(exc)[:160]}"}
    return json.loads(json.dumps(outputs))


result = {"target": target, "record": str(record_path), "source_commit": record["source_commit"],
          "train_seal": seal, "train_seal_matches_record": seal_ok, "regenerated_train": regenerated,
          "heldout_built": False, "losses": {}, "errors": {}, "categories": {}}
for role, config in (("incumbent", record["incumbent"]["config"]), ("candidate", record["candidate"]["config"])):
    t = time.time()
    outs = run(config)
    losses = stress.losses(outs)
    result["losses"][role] = {k: v for k, v in losses.items()}
    result["errors"][role] = sorted(k for k, v in outs.items() if "error" in v)
    result["categories"][role] = {k: score(stress._items[k]["data"], stress._items[k]["truth"],
                                           (outs.get(k) or {}).get("output"))["category"] for k in stress._items}
    print(role, f"{time.time() - t:.0f}s", flush=True)
out_path.write_text(json.dumps(result, indent=1))
