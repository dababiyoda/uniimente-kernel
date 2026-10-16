"""Layer 4: MICA/CDPE local field repair on UNSEEN damage, against a static route and an adaptive central replanner.

TARGET_FORM_001 (``developmental/``) tests one fixed, deterministic 20 % removal. The reserved organ
``cortex.developmental.mica_field`` names its falsifier as "MICA/CDPE beats strong centralized adaptive
baseline on unseen failures". This runner composes the same lab components (``MICAField``,
``simulate_transport``; TARGET_FORM_001 itself is unchanged) on damage the lab never saw:

* seeds 1-40; removal fraction 0.10 / 0.20 / 0.30 / 0.40 by seed % 4; cells removed uniformly at random
  (seeded) among all cells except source and sink; every edge of the original route blocked;
* arms per seed, as in the lab: ``distributed`` (local target-field propagation then local gradient route),
  ``static_central`` (the original route), ``adaptive_central`` (global shortest path on the damaged field);
* metrics: packets delivered in 40 ticks, first-delivery tick, planning operations.

Verdict (frozen): ADVANTAGE if distributed delivers more than adaptive_central on more seeds than the
reverse with one-sided sign test p < 0.05; PARITY if delivered counts tie on every seed where either
delivers; otherwise NO_MATERIAL_ADVANTAGE. Planning-operation ratios are reported, not judged. The
structural point is stated in advance: the local field is a distributed shortest-path (distance-vector)
computation, so parity on delivered throughput is the expected outcome; any claimed benefit must come
from somewhere else (no central coordinator), which this runner does not measure.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

MANIFEST = HERE / "freeze-v1.json"
SEEDS = range(1, 41)
FRACTIONS = (0.10, 0.20, 0.30, 0.40)
TICKS = 40
FROZEN_CODE = ["cortex/evaluation/developmental_sweep/run.py", "developmental/mica.py", "developmental/cdpe.py",
               "developmental/contracts.py"]


def trial(seed: int) -> dict:
    from developmental.cdpe import simulate_transport
    from developmental.mica import MICAField
    base = MICAField()
    base_ops, _ = base.propagate_target_field()
    original = base.local_route()
    fraction = FRACTIONS[seed % len(FRACTIONS)]
    pool = sorted(c for c in base.cells if c not in (base.source_id, base.sink_id))
    removal = random.Random(seed).sample(pool, round(len(base.cells) * fraction))
    damaged = base.clone()
    damaged.block_route(original)
    damaged.remove_cells(removal)
    out = {"seed": seed, "fraction": fraction, "removed": len(removal)}
    dist = damaged.clone()
    ops, _ = dist.propagate_target_field()
    route = dist.local_route()
    arms = {"distributed": (dist, route, ops), "static_central": (damaged.clone(), original, base_ops)}
    adaptive = damaged.clone()
    a_route, a_ops = adaptive.global_shortest_path()
    arms["adaptive_central"] = (adaptive, a_route, a_ops)
    for name, (field, path, planning) in arms.items():
        m = simulate_transport(field, path, ticks=TICKS, mode=name, planning_operations=planning,
                               central_coordinator_required=name != "distributed")
        out[name] = {"delivered": m.delivered, "first_delivery_tick": m.first_delivery_tick,
                     "planning_operations": m.planning_operations, "route_length": len(path),
                     "false_activations": field.false_activations,
                     "exact_restoration_attempts": field.exact_restoration_attempts}
    return out


def sign_test(wins, losses):
    n = wins + losses
    return 1.0 if n == 0 else sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def summarize(rows) -> dict:
    wins = sum(1 for r in rows if r["distributed"]["delivered"] > r["adaptive_central"]["delivered"])
    losses = sum(1 for r in rows if r["distributed"]["delivered"] < r["adaptive_central"]["delivered"])
    active = [r for r in rows if r["distributed"]["delivered"] or r["adaptive_central"]["delivered"]]
    if wins > losses and sign_test(wins, losses) < 0.05:
        verdict = "ADVANTAGE"
    elif wins == losses == 0 and active:
        verdict = "PARITY"
    else:
        verdict = "NO_MATERIAL_ADVANTAGE"
    by_fraction = {}
    for f in FRACTIONS:
        fr = [r for r in rows if r["fraction"] == f]
        by_fraction[str(f)] = {arm: {"delivered_total": sum(r[arm]["delivered"] for r in fr),
                                     "seeds_with_delivery": sum(1 for r in fr if r[arm]["delivered"])}
                               for arm in ("distributed", "static_central", "adaptive_central")}
    ratios = [r["distributed"]["planning_operations"] / r["adaptive_central"]["planning_operations"]
              for r in rows if r["adaptive_central"]["planning_operations"]]
    return {"distributed_vs_adaptive": {"wins": wins, "losses": losses, "ties": len(rows) - wins - losses,
                                        "sign_test_p_one_sided": round(sign_test(wins, losses), 6)},
            "verdict": verdict, "by_fraction": by_fraction,
            "planning_ops_ratio_median": round(statistics.median(ratios), 3) if ratios else None,
            "false_activations": sum(r[a]["false_activations"] for r in rows
                                     for a in ("distributed", "static_central", "adaptive_central")),
            "exact_restoration_attempts": sum(r[a]["exact_restoration_attempts"] for r in rows
                                              for a in ("distributed", "static_central", "adaptive_central"))}


def inputs():
    return {"code": {p: "sha256:" + hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in FROZEN_CODE},
            "seeds": [SEEDS.start, SEEDS.stop - 1], "fractions": list(FRACTIONS), "ticks": TICKS}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if args.freeze:
        if MANIFEST.exists():
            raise SystemExit("refusing to overwrite an existing freeze; create a new version")
        MANIFEST.write_text(json.dumps({"frozen_at": datetime.now(timezone.utc).isoformat(), "inputs": inputs()},
                                       indent=2) + "\n")
        return
    if json.loads(MANIFEST.read_text())["inputs"] != inputs():
        raise SystemExit("FROZEN_INPUT_CHANGED: results cannot be reported")
    rows = [trial(seed) for seed in SEEDS]
    report = {"schema": "greg-developmental-sweep/1", "manifest_sha256": "sha256:" + hashlib.sha256(
        MANIFEST.read_bytes()).hexdigest(), "finished_at": datetime.now(timezone.utc).isoformat(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "trials": rows, "summary": summarize(rows)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report["summary"], indent=1))


if __name__ == "__main__":
    main()
