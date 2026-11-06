"""P6 converged v1: re-measure the recipe lifts on the converged Mind (founder directive 2026-10-21, section 6).

Why: every recipe verdict in the evidence index was measured on one lineage's freeze commit, and the converged tree
binds recipe code completely (its own closure plus every stage genome, operation family and organ), so all seven
recipe verdicts route UNEVALUATED. The directive says "Bind verification to the actual integrated code. Do not
transfer old benchmark claims onto changed implementations." This runner measures the synthetic families again on
this tree, on fresh held-out seeds, against the strongest single intelligence available - not only the
lineage constituents.

Reused unchanged (imported, not copied): the generators, payloads, truths, constituent arms and scoring of v1 (F1
``estimate_then_optimize``) and v2 (F2R ``identify_then_optimize``, F3 ``graph_then_allocate``, F4
``bayes_then_voi``), and v1's sign test. The natural families (F5 M4, F6 bank calls, F7 SNDlib, F8 Uber) are not
re-measured here: their held-out data were already looked at, so any re-run on them is diagnostic only and could
not support a generalization claim.

Declared changes from v1/v2, before any held-out run:
* seeds: fresh held-out ranges (F1 6501-6540, F2R 6601-6664, F3 6701-6740, F4 6801-6840), outside every range any
  suite in this repository has generated and outside the reservations #158 holds (3000-3999, 7000 and up);
* ``static_composition`` is each family's own recipe (declared), not v2's single development-selected recipe;
* arms added, run through ``greg.cognition.cortex.reason`` with the same evaluation-only registry view:
  - ``exact_single`` on F3: ``flow_expansion_mcf`` (operation ``expand_capacity_mcf``), the admitted
    DEFAULT_FOR_GEOMETRY genome for budgeted capacity expansion (#158 admission v3); no other family has an
    admitted single genome that answers its whole question, which is stated rather than invented;
  - ``compiled``: the same request through the Competency Compiler (``{"compile": {...}}``), the canonical Layer
    5 entry; reported with its state and stage count, never in the rule.

Development check before the freeze (dev seeds 1-2 of each family, never a held-out seed; disclosed in the
pre-registration): every arm executed. The compiled arm abstained on F1 because the Fermi organ, UNEVALUATED like the
now-unbound recipe, won the tie on its method name and ignored ``formal_template``. That compiler defect was fixed
before the freeze (``compiler._reject_recipe_relaxations``), so the frozen bindings include the fix.

Rule (frozen here; v1's binary rule against the strongest single): a family counts toward converged VPL when
routed composition decides more held-out items correctly than the best single arm (the best of the lineage
constituents and ``exact_single``, chosen on held-out results), adds no wrong answer over it, the one-sided exact
sign test over discordant items gives p < 0.05, and routed median latency is within the 60 s chain budget. The
lineage rule (constituents only) is reported beside it for comparability with v1/v2. Reported, never in the rule:
false answers, abstentions (no_decision), translation and composition failures, suboptimal answers, median and p95
latency, stages, and the compiled arm.

Procedure (pre-registered in ``prereg-converged-v1.json``): commit this runner and the pre-registration; in a clean
tree ``--freeze`` writes ``freeze-converged-v1.json`` (file digests, the four recipes' complete code bindings, seeds,
rule); commit it; run once, from a clean detached worktree at the freeze commit, under ``python -I``. The run
refuses a dirty tree or any changed input.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
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
from cortex.evaluation.composition_lift import run_v2 as V2  # noqa: E402

MANIFEST = HERE / "freeze-converged-v1.json"
PREREG = HERE / "prereg-converged-v1.json"
CHAIN_BUDGET_S = 60.0
SEEDS = {"F1": range(6501, 6541), "F2R": range(6601, 6665), "F3": range(6701, 6741), "F4": range(6801, 6841)}
RECIPE = {"F1": "estimate_then_optimize", "F2R": "identify_then_optimize", "F3": "graph_then_allocate",
          "F4": "bayes_then_voi"}
CONSTITUENTS = {"F1": V1.CONSTITUENTS["F1"], **{f: V2.CONSTITUENTS[f] for f in ("F2R", "F3", "F4")}}
SINGLES = {"F3": ("exact_single",)}
EVAL_ATTACH = tuple(V2.EVAL_ATTACH) + ("cognition.flow_expansion_mcf",)
FROZEN_FILES = ["cortex/evaluation/composition_lift/run_converged_v1.py",
                "cortex/evaluation/composition_lift/prereg-converged-v1.json",
                "cortex/evaluation/composition_lift/run.py", "cortex/evaluation/composition_lift/run_v2.py",
                *[p for p in V2.FROZEN_CODE if not p.startswith("cortex/evaluation/composition_lift/")
                  and not p.endswith(".gz")],
                "greg/cognition/compiler.py", "greg/cognition/genomes/flow.py"]
RULE = ("converged rule: routed correct > best single correct (best of lineage constituents and exact_single, "
        "chosen on held-out results), routed wrong <= best single wrong, one-sided exact sign test p < 0.05 over "
        "discordant items, routed median latency <= 60 s. Lineage rule (constituents only) reported beside it.")
RESULTS = ("correct", "wrong", "suboptimal", "no_decision")


def generate(family: str, seed: int) -> dict:
    if family == "F1":
        return {**V1.f1(seed), "family": "F1"}
    return {"F2R": V2.f2r, "F3": V2.f3, "F4": V2.f4}[family](seed)


def _attach_registry():
    V2.EVAL_ATTACH = EVAL_ATTACH                       # evaluation-only founder pin, in memory, before first use
    V2._REGISTRY = None
    return V2.registry()


def _compiled(item) -> tuple[dict | None, float, dict]:
    started = time.perf_counter()
    r = V2.reason({"problem_id": item["item_id"] + "/compiled",
                   "compile": {"geometry": {"consequence_class": "read_only"}, "data": item["payload"]}})
    answer = r.get("result") if r.get("state") == "ANSWERED" else None
    return answer, time.perf_counter() - started, r


def score(item, answer) -> str:
    family = item["family"]
    if family == "F1":
        return V1.score(item, answer)
    if family == "F2R":
        return V1.score({**item, "family": "F2"}, answer)
    if family == "F3":
        return V2.f3_score(item, answer)
    return V2.f4_score(item, answer)


def run_arm(item, arm) -> dict:
    family = item["family"]
    if arm == "exact_single":
        started = time.perf_counter()
        out = V2.op(item["item_id"] + "/exact", "expand_capacity_mcf", item["payload"]["capacity_network"])
        answer = {"increments": out["increments"]} if out and isinstance(out.get("increments"), dict) else None
        return {"result": score(item, answer), "seconds": round(time.perf_counter() - started, 3),
                "state": "single genome", "stages": 1}
    if arm == "compiled":
        answer, seconds, r = _compiled(item)
        return {"result": score(item, answer), "seconds": round(seconds, 3), "state": r.get("state"),
                "stages": (r.get("resource_use") or {}).get("stages"),
                "method": (r.get("selected") or {}).get("method") if isinstance(r.get("selected"), dict) else None}
    if family == "F1":
        out = V1.run_arm(item, arm, RECIPE["F1"])
        return {"result": out["result"], "seconds": out["seconds"], "state": out["state"], "stages": None}
    row = V2.run_arm(item, arm, RECIPE[family])
    return {k: row[k] for k in ("result", "seconds", "state", "stages") if k in row}


def arms_for(family) -> list[str]:
    return [*CONSTITUENTS[family], *SINGLES.get(family, ()), "static_composition", "routed_composition",
            "compiled"]


def _verdict(fr: list[dict], singles: tuple[str, ...]) -> dict:
    counts = {a: {k: sum(1 for r in fr if r["arms"][a]["result"] == k) for k in RESULTS} for a in fr[0]["arms"]}
    best = max(singles, key=lambda a: (counts[a]["correct"], -counts[a]["wrong"]))
    wins = sum(1 for r in fr if r["arms"]["routed_composition"]["result"] == "correct"
               and r["arms"][best]["result"] != "correct")
    losses = sum(1 for r in fr if r["arms"][best]["result"] == "correct"
                 and r["arms"]["routed_composition"]["result"] != "correct")
    p = V1.sign_test(wins, losses)
    median = statistics.median(r["arms"]["routed_composition"]["seconds"] for r in fr)
    lift = (counts["routed_composition"]["correct"] > counts[best]["correct"]
            and counts["routed_composition"]["wrong"] <= counts[best]["wrong"] and p < 0.05
            and median <= CHAIN_BUDGET_S)
    return {"best_single": best, "routed_wins": wins, "routed_losses": losses,
            "sign_test_p_one_sided": p, "lift": lift}


def summarize(rows: list[dict]) -> dict:
    out = {}
    for family in SEEDS:
        fr = [r for r in rows if r["family"] == family]
        if not fr:
            continue
        arms = list(fr[0]["arms"])
        converged = _verdict(fr, tuple(CONSTITUENTS[family]) + SINGLES.get(family, ()))
        lineage = _verdict(fr, tuple(CONSTITUENTS[family]))
        seconds = {a: sorted(r["arms"][a]["seconds"] for r in fr) for a in arms}
        routed_states = [r["arms"]["routed_composition"]["state"] for r in fr]
        out[family] = {
            "recipe": RECIPE[family], "n": len(fr),
            "counts": {a: {k: sum(1 for r in fr if r["arms"][a]["result"] == k) for k in RESULTS} for a in arms},
            "median_seconds": {a: round(statistics.median(v), 3) for a, v in seconds.items()},
            "p95_seconds": {a: round(v[min(len(v) - 1, math.ceil(0.95 * len(v)) - 1)], 3) for a, v in seconds.items()},
            "translation_failure_rate": routed_states.count("TRANSLATION_FAILED") / len(fr),
            "composition_failure_rate": sum(s != "ANSWERED" for s in routed_states) / len(fr),
            # the index reads these keys: the converged verdict decides; best_constituent names the best single
            "lift": converged["lift"], "best_constituent": converged["best_single"],
            "routed_wins": converged["routed_wins"], "routed_losses": converged["routed_losses"],
            "sign_test_p_one_sided": round(converged["sign_test_p_one_sided"], 12),
            "lineage_rule": {**lineage, "sign_test_p_one_sided": round(lineage["sign_test_p_one_sided"], 12)},
            "exact_singles": list(SINGLES.get(family, ())),
            "tied_by": [a for a in SINGLES.get(family, ()) if fr and
                        sum(r["arms"][a]["result"] == "correct" for r in fr) ==
                        sum(r["arms"]["routed_composition"]["result"] == "correct" for r in fr)],
        }
    lifted = [f for f in out if out[f]["lift"]]
    return {**out, "VPL_converged": {"families_with_lift": len(lifted), "lifted": lifted, "families": len(out),
                                     "rule": RULE}}


def bindings() -> dict:
    from greg.cognition.compiler import recipe_code
    out = {}
    for family, recipe in RECIPE.items():
        code = recipe_code(recipe)
        out[recipe] = None if code is None else {
            "function": code["function"], "closure_sha256": code["closure_sha256"],
            "stage_closures": code["stage_closures"], "recipe_entry_sha256": code["recipe_entry_sha256"],
            "closure_unresolved": code["closure_unresolved"]}
    return out


def inputs() -> dict:
    return {"files": {p: "sha256:" + hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in FROZEN_FILES},
            "recipe_bindings": bindings(), "seeds": {f: [s.start, s.stop - 1] for f, s in SEEDS.items()},
            "eval_attach": list(EVAL_ATTACH), "rule": RULE}


def dirty() -> list[str]:
    out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def measure(seeds: dict | None = None, log=None) -> dict:
    _attach_registry()
    rows = []
    for family, family_seeds in (seeds or SEEDS).items():
        for seed in family_seeds:
            item = generate(family, seed)
            arms = {arm: run_arm(item, arm) for arm in arms_for(family)}
            rows.append({"item_id": item["item_id"], "family": family, "seed": seed, "arms": arms})
            if log:
                log(f"{item['item_id']} " + " ".join(f"{a}={v['result']}" for a, v in arms.items()))
    return {"heldout": rows, "summary": summarize(rows)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if dirty():
        raise SystemExit("DIRTY_TREE: commit or discard tracked changes first\n" + "\n".join(dirty()))
    if args.freeze:
        if MANIFEST.exists():
            raise SystemExit("refusing to overwrite an existing freeze; create a new version")
        MANIFEST.write_text(json.dumps({"frozen_at": datetime.now(timezone.utc).isoformat(), "inputs": inputs()},
                                       indent=2) + "\n")
        return
    if not MANIFEST.exists():
        raise SystemExit("NOT_FROZEN: run --freeze and commit the manifest first")
    if json.loads(MANIFEST.read_text())["inputs"] != inputs():
        raise SystemExit("FROZEN_INPUT_CHANGED: results cannot be reported")
    started = datetime.now(timezone.utc).isoformat()
    measured = measure(log=lambda line: print(line, flush=True))
    report = {"schema": "greg-composition-lift-converged/1",
              "manifest_sha256": "sha256:" + hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
              "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "environment": {"python": platform.python_version()}, "recipe_bindings": bindings(), **measured}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({f: {k: v for k, v in s.items() if k in ("lift", "best_constituent", "routed_wins",
                                                              "routed_losses", "sign_test_p_one_sided")}
                      for f, s in report["summary"].items() if f in SEEDS}, indent=1))


if __name__ == "__main__":
    main()
