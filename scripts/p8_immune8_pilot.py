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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", choices=("gate-audit",))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    pilot = P7.Pilot(workers=WORKERS)
    try:
        result = gate_audit(pilot=pilot)
    finally:
        pilot.close()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps({"out": str(args.out), "evaluations": result["evaluations"], "seconds": result["seconds"]}))


if __name__ == "__main__":
    main()
