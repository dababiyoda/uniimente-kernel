"""P6 v2: close or falsify the cognitive-composition gate (founder directive 2026-10-07, step A).

v1 measured VPL = 1 of 2 on two families constructed around the composition module (F1 lift p=0.00012;
F2 4 wins / 0 losses, p=0.0625). v2 pre-registers three more held-out families:

* F2b ``identify_then_optimize`` at higher power: the v1 generator with fresh seeds 25-72 (48 items).
* X1 ``crossgeo composition``: the 48 held-out items of the frozen cross-geometry suite
  (``cortex/evaluation/suites/crossgeo-heldout-v0.3.json``) whose family is ``composition``.
* X2 ``crossgeo schedule_words``: the 57 held-out items of the same suite whose family is
  ``schedule_words`` (a scheduling request in words; extraction -> formal model -> solver).

X1 and X2 were written by the agent that built the cortex router, for the cross-geometry evaluation, and
frozen before this composition module existed (``freeze-crossgeo-v0.3.json``). They are independently
derived from this experiment; they are **not** a natural task distribution (no founder-used missions exist
yet). The strongest single intelligence one would want for X2 - a language model reading the words - is
NOT_RUN: no founder-selected local model is configured in this container.

Arms. Constituents are produced by withholding organs through the cortex registry (the same mechanism a
founder detach uses): X1 ``estimate_only`` (only the Fermi organ) and ``formal_only`` (only Z3 + CP-SAT);
X2 ``extraction_only`` (formal engines withheld) and ``formal_only`` (extractor withheld); F2b
``identify_alone`` and ``optimize_on_association`` as in v1. ``routed`` is the full cortex (X1, X2) or the
geometry-routed composition (F2b). Scoring: X1/X2 by the suite's own gold (``crossgeo_loss.answer_correct``),
F2b as v1. correct / wrong (a decisive answer that fails gold) / no decision (abstention or no answer).

Verdict (frozen, v1's rule): a family counts toward VPL when routed decides more held-out items correctly
than the best constituent, adds no wrong answer, the one-sided exact sign test over discordant items gives
p < 0.05, and the routed median latency is inside 60 s.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from cortex.evaluation.composition_lift import run as V1  # noqa: E402

CROSSGEO = ROOT / "cortex/evaluation/suites/crossgeo-heldout-v0.3.json"
MANIFEST = HERE / "freeze-v2.json"
F2B_SEEDS = range(25, 73)
FROZEN_CODE = ["cortex/evaluation/composition_lift/run_v2.py", "cortex/evaluation/composition_lift/run.py",
               "greg/cognition/composition.py", "greg/cognition/cortex.py", "greg/cognition/bridge.py",
               "cortex/routing.py", "cortex/genome.py", "cortex/organs/estimation.py", "cortex/organs/formal.py",
               "cortex/organs/cpsat.py", "cortex/organs/schedule_extraction.py",
               "cortex/organs/evidence_causal.py", "cortex/evaluation/crossgeo_loss.py",
               "cortex/evaluation/suites/crossgeo-heldout-v0.3.json", "cortex/evaluation/freeze-crossgeo-v0.3.json"]
FERMI = "cortex.estimation.fermi@0.1.0"
Z3, CPSAT = "cortex.formal.z3@0.2.0", "cortex.optimization.cpsat@0.2.0"
EXTRACT = "cortex.extraction.schedule@0.1.0"
CONSTITUENTS = {"F2b": ("identify_alone", "optimize_on_association"), "X1": ("estimate_only", "formal_only"),
                "X2": ("extraction_only", "formal_only")}
WITHHOLD = {("X1", "estimate_only"): "keep", ("X1", "formal_only"): "keep",
            ("X2", "extraction_only"): (Z3, CPSAT), ("X2", "formal_only"): (EXTRACT,)}
KEEP = {("X1", "estimate_only"): {FERMI}, ("X1", "formal_only"): {Z3, CPSAT}}


def crossgeo(family):
    items = json.loads(CROSSGEO.read_text())["items"]
    return [i for i in items if family in i["families"]]


def _cortex_run(problem, withhold=()):
    from cortex.genome import seed_registry
    from cortex.routing import Cortex
    registry = seed_registry()
    for key in withhold:
        registry.withhold(key, "evaluation: constituent arm (founder-detach mechanism)")
    started = time.perf_counter()
    receipt = Cortex(registry, clock=lambda: "2026-10-14T00:00:00Z").run(problem)
    return receipt, time.perf_counter() - started


def score_gold(gold, receipt) -> str:
    from cortex.evaluation.crossgeo_loss import answer_correct
    answer = (receipt.get("output") or {}).get("answer")
    if receipt["disposition"]["kind"] in ("abstain", "handoff", "bounded_test") or answer is None:
        return "no_decision"
    return "correct" if answer_correct(gold["answer"], answer) else "wrong"


def run_crossgeo(item, family, arm):
    from cortex.genome import seed_registry
    keys = seed_registry().keys()
    if arm == "routed":
        withhold = ()
    elif (family, arm) in KEEP:
        withhold = [k for k in keys if k not in KEEP[(family, arm)] and k.split("@")[0].startswith("cortex.")
                    and k not in ("cortex.verifier.adversarial@0.1.0",)]
    else:
        withhold = WITHHOLD[(family, arm)]
    receipt, seconds = _cortex_run(item["problem"], withhold)
    return {"result": score_gold(item["gold"], receipt), "seconds": round(seconds, 3),
            "state": receipt["output"]["state"], "selected": receipt["route"]["selected"]}


def run_f2b(item, arm):
    out = V1.run_arm(item, "routed_composition" if arm == "routed" else arm)
    return {k: out[k] for k in ("result", "seconds", "state")}


def summarize(rows) -> dict:
    out, vpl = {}, 0
    for family, constituents in CONSTITUENTS.items():
        fr = [r for r in rows if r["family"] == family]
        arms = list(constituents) + ["routed"]
        counts = {a: {k: sum(1 for r in fr if r["arms"][a]["result"] == k) for k in ("correct", "wrong", "suboptimal",
                                                                                   "no_decision")} for a in arms}
        best = max(constituents, key=lambda a: (counts[a]["correct"], -counts[a]["wrong"]))
        wins = sum(1 for r in fr if r["arms"]["routed"]["result"] == "correct" and r["arms"][best]["result"] != "correct")
        losses = sum(1 for r in fr if r["arms"][best]["result"] == "correct" and r["arms"]["routed"]["result"] != "correct")
        p = V1.sign_test(wins, losses)
        median = statistics.median(r["arms"]["routed"]["seconds"] for r in fr)
        lift = (counts["routed"]["correct"] > counts[best]["correct"] and counts["routed"]["wrong"] <= counts[best]["wrong"]
                and p < 0.05 and median <= V1.CHAIN_BUDGET_S)
        vpl += int(lift)
        out[family] = {"n": len(fr), "counts": counts, "best_constituent": best, "routed_wins": wins,
                       "routed_losses": losses, "sign_test_p_one_sided": round(p, 6),
                       "median_seconds": {a: round(statistics.median(r["arms"][a]["seconds"] for r in fr), 3)
                                          for a in arms}, "lift": lift}
    out["VPL_v2"] = {"families_with_lift": vpl, "families": len(CONSTITUENTS), "rule": V1.VERDICT_RULE}
    return out


def inputs() -> dict:
    return {"code": {p: V1._sha(ROOT / p) for p in FROZEN_CODE}, "f2b_seeds": [F2B_SEEDS.start, F2B_SEEDS.stop - 1],
            "crossgeo_families": ["composition", "schedule_words"], "verdict_rule": V1.VERDICT_RULE,
            "constituents": {k: list(v) for k, v in CONSTITUENTS.items()}}


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
    rows = []
    for seed in F2B_SEEDS:
        item = V1.f2(seed)
        row = {"item_id": f"F2b-{seed}", "family": "F2b", "arms": {}}
        for arm in CONSTITUENTS["F2b"] + ("routed",):
            row["arms"][arm] = run_f2b(item, arm)
        rows.append(row)
    for family, name in (("X1", "composition"), ("X2", "schedule_words")):
        for item in crossgeo(name):
            row = {"item_id": item["item_id"], "family": family, "arms": {}}
            for arm in CONSTITUENTS[family] + ("routed",):
                row["arms"][arm] = run_crossgeo(item, family, arm)
            rows.append(row)
    report = {"schema": "greg-composition-lift-results/2", "manifest_sha256": V1._sha(MANIFEST),
              "finished_at": datetime.now(timezone.utc).isoformat(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "platform": platform.platform(), "python": sys.version.split()[0], "heldout": rows,
              "summary": summarize(rows),
              "limits": ["X1/X2 were authored by the router-building agent, frozen before this module; not natural tasks",
                         "the strongest single intelligence for X2 (a local language model) is NOT_RUN: none configured",
                         "constituent arms withhold organs through the registry; organ code is unchanged"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report["summary"], indent=1))


if __name__ == "__main__":
    main()
