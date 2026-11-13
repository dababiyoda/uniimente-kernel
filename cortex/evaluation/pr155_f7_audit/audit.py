"""Independent audit of PR #158's F7 verdict (P6 v4) against its parametric min-cost-flow reference.

Founder decision 2026-10-14 (Track B, INTENT-20261014-MIND-LINEAGE-CONVERGENCE): "independently audit PR #158's
F7 result against its parametric min-cost-flow reference". F7's truth (``expansion_truth``), its scorer
(``expansion_value``) and its practitioner reference (``parametric_min_cost_flow``) share one algorithm family:
NetworkX min-cost flow plus bisection, and an Edmonds-Karp written in the same module. An error there would
make every F7 comparison wrong at once, so the audit re-derives everything without that code:

1. Instances. The 200 held-out items are rebuilt from the bundled SNDlib data with this file's own
   implementation of the declared rules (module sizing at 80% utilisation, free capacity, K <= 4 shortest
   loop-free paths by km capped at 32 arcs, price = 1 + round(km / 100), at most 20 units per arc, budget =
   20 x the cheapest admissible path). No function of ``run_v4.py`` or ``greg.cognition.genomes.flow`` is
   imported. Identity: every arm's recorded plan in results-v4.json must name exactly the rebuilt arcs, and
   the rebuilt no-lease throughput and path count must equal the recorded ones.
2. Optimum. Each instance is solved as a mixed-integer program by HiGHS (``scipy.optimize.milp``; a
   different solver family from network simplex and from the composition's CP-SAT): maximise throughput F
   with arc flow <= free capacity + leased units, integer leased units in [0, 20], conservation, and total
   lease price <= budget, at a relative gap of 0.
3. Rescoring. Every arm's recorded plan is re-scored with ``scipy.sparse.csgraph.maximum_flow`` on
   capacity + increments, with its own budget and bounds check: optimal, suboptimal, wrong or no_decision.

Verdict (frozen in ``freeze.json`` before the first run):

* CONFIRMED  every item is rebuilt and identity-checked, the independent optimum equals the recorded truth
             on every item, and every arm's recorded outcome and throughput reproduce on every item;
* REFUTED    any item where the recorded truth differs from the independent optimum, or any arm whose
             recorded outcome or throughput does not reproduce (listed item by item);
* INCOMPLETE an item cannot be rebuilt or identity-checked, or a MILP does not reach proven optimality.

Scope: the audit tests the optimisation claims on F7's declared model. It does not make F7's truth a
realised outcome (it stays a computed optimum), and it does not re-run any GREG arm.

Run (refuses if any frozen input changed):
    python cortex/evaluation/pr155_f7_audit/audit.py
"""
from __future__ import annotations

from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FREEZE = HERE / "freeze.json"
DATA = "cortex/evaluation/data/sndlib_networks.json.gz"
RESULTS = "docs/evidence/greg-composition-lift/2026-10-14-v4/results-v4.json"
OUT = ROOT / "docs/evidence/pr155-f7-audit/2026-10-14/results.json"
INPUTS = ("cortex/evaluation/pr155_f7_audit/audit.py", DATA, RESULTS)
# The declared F7 decision layer (run_v4.py docstring), re-implemented here.
MODULE, UTILISATION, MAX_PATHS, MIN_PATHS, MAX_ARCS = 10, 0.8, 4, 2, 32
MAX_INCREMENT, BUDGET_UNITS, PAIRS = 20, 20, 10


class AuditError(RuntimeError):
    pass


def sha256(rel: str) -> str:
    return "sha256:" + hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def check_freeze() -> dict:
    if not FREEZE.exists():
        raise AuditError("NOT_FROZEN: commit freeze.json before the first run")
    frozen = json.loads(FREEZE.read_text())
    changed = [rel for rel in INPUTS if frozen["inputs"].get(rel) != sha256(rel)]
    if changed:
        raise AuditError(f"FROZEN_INPUT_CHANGED: {changed}")
    return frozen


# ------------------------------------------------------------------ instances (own implementation)
def networks() -> dict:
    with gzip.open(ROOT / DATA, "rt", encoding="utf-8") as fh:
        return json.load(fh)["networks"]


def heldout(names) -> list[str]:
    ordered = sorted(names)
    return [n for i, n in enumerate(ordered) if i % 5 != 0]


def free_capacity(load: float) -> int:
    modules = max(1, math.ceil(load / (UTILISATION * MODULE)))
    return int(math.floor(modules * MODULE - load))


def admissible_arcs(net: dict, s: str, t: str):
    import networkx as nx
    g = nx.Graph()
    for u, v, km, _, _ in net["links"]:
        g.add_edge(u, v, km=km)
    for k in range(MAX_PATHS, MIN_PATHS - 1, -1):
        paths = []
        for p in nx.shortest_simple_paths(g, s, t, weight="km"):
            paths.append(p)
            if len(paths) == k:
                break
        arcs = sorted({(p[i], p[i + 1]) for p in paths for i in range(len(p) - 1)})
        if len(arcs) <= MAX_ARCS:
            return arcs, k
    return None


def cheapest_path(arcs, price, s, t) -> int:
    """Bellman-Ford on the admissible arcs (prices are positive integers)."""
    best = {s: 0}
    for _ in range(len(arcs) + 1):
        changed = False
        for u, v in arcs:
            if u in best and best[u] + price[(u, v)] < best.get(v, math.inf):
                best[v] = best[u] + price[(u, v)]
                changed = True
        if not changed:
            break
    return best[t]


def instance(net: dict, pair: int) -> dict | None:
    s, t, demand = net["top_demands"][pair]
    found = admissible_arcs(net, s, t)
    if found is None:
        return None
    arcs, k = found
    load, km = {}, {}
    for u, v, length, uv, vu in net["links"]:
        load[(u, v)], load[(v, u)] = uv, vu
        km[(u, v)] = km[(v, u)] = length
    price = {a: 1 + round(km[a] / 100) for a in arcs}
    return {"arcs": arcs, "paths": k, "source": s, "sink": t, "demand": demand,
            "capacity": {a: free_capacity(load[a]) for a in arcs}, "price": price,
            "budget": BUDGET_UNITS * cheapest_path(arcs, price, s, t)}


# ------------------------------------------------------------------ independent solvers
def max_flow(inst: dict, increments: dict) -> int:
    import numpy as np
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import maximum_flow
    nodes = sorted({n for a in inst["arcs"] for n in a})
    at = {n: i for i, n in enumerate(nodes)}
    rows = [at[u] for u, _ in inst["arcs"]]
    cols = [at[v] for _, v in inst["arcs"]]
    caps = [inst["capacity"][a] + increments.get(a, 0) for a in inst["arcs"]]
    graph = csr_matrix((np.array(caps, dtype=np.int32), (rows, cols)), shape=(len(nodes), len(nodes)))
    return int(maximum_flow(graph, at[inst["source"]], at[inst["sink"]]).flow_value)


def optimum(inst: dict) -> dict:
    """max F: f_a <= c_a + x_a, integer 0 <= x_a <= 20, conservation, sum price_a x_a <= budget (HiGHS)."""
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    arcs, m = inst["arcs"], len(inst["arcs"])
    nodes = sorted({n for a in arcs for n in a})
    n = 2 * m + 1                                   # f (m), x (m), F
    c = np.zeros(n)
    c[-1] = -1.0
    rows, lo, hi = [], [], []
    for i, a in enumerate(arcs):                    # f_a - x_a <= c_a
        row = np.zeros(n)
        row[i], row[m + i] = 1.0, -1.0
        rows.append(row), lo.append(-np.inf), hi.append(inst["capacity"][a])
    for node in nodes:                              # out - in - F[s] + F[t] = 0
        row = np.zeros(n)
        for i, (u, v) in enumerate(arcs):
            row[i] += (u == node) - (v == node)
        row[-1] = -1.0 if node == inst["source"] else 1.0 if node == inst["sink"] else 0.0
        rows.append(row), lo.append(0.0), hi.append(0.0)
    row = np.zeros(n)                               # lease budget
    row[m:2 * m] = [inst["price"][a] for a in arcs]
    rows.append(row), lo.append(-np.inf), hi.append(inst["budget"])
    upper = [inst["capacity"][a] + MAX_INCREMENT for a in arcs] + [MAX_INCREMENT] * m + [np.inf]
    result = milp(c, constraints=LinearConstraint(np.array(rows), lo, hi), bounds=Bounds([0.0] * n, upper),
                  integrality=np.array([0] * m + [1] * m + [0]), options={"mip_rel_gap": 0.0, "disp": False})
    if result.status != 0:
        return {"optimal": False, "message": result.message}
    value = -result.fun
    increments = {a: int(round(result.x[m + i])) for i, a in enumerate(arcs)}
    return {"optimal": True, "value": int(round(value)), "integral": abs(value - round(value)) < 1e-6,
            "mip_gap": getattr(result, "mip_gap", None),
            # the MILP's own plan re-checked by the independent max-flow and budget
            "plan_value": max_flow(inst, increments),
            "plan_spent": sum(inst["price"][a] * x for a, x in increments.items())}


def rescore(inst: dict, answer, truth: int) -> tuple[str, int | None]:
    if not isinstance(answer, dict) or not isinstance(answer.get("increments"), dict):
        return "no_decision", None
    keys = {f"{u}->{v}": (u, v) for u, v in inst["arcs"]}
    try:
        inc = {keys[k]: int(x) for k, x in answer["increments"].items()}
    except (KeyError, TypeError, ValueError):
        return "wrong", None
    spent = sum(inst["price"][a] * x for a, x in inc.items())
    if spent > inst["budget"] or any(not 0 <= x <= MAX_INCREMENT for x in inc.values()):
        return "wrong", None
    value = max_flow(inst, inc)
    if answer.get("flow_value") is not None and answer["flow_value"] != value:
        return "wrong", value
    return ("optimal" if value == truth else "suboptimal"), value


# ------------------------------------------------------------------ audit
def audit() -> dict:
    frozen = check_freeze()
    recorded = json.loads((ROOT / RESULTS).read_text())
    rows = {r["item_id"]: r for r in recorded["heldout"]}
    nets = networks()
    items, problems, incomplete = [], [], []
    counts, recomputed = {}, {}
    for name in heldout(nets):
        for pair in range(PAIRS):
            item_id = f"F7-{name}-{pair}"
            inst = instance(nets[name], pair)
            row = rows.get(item_id)
            if inst is None or row is None:
                incomplete.append(f"{item_id}: {'out of scope' if inst is None else 'not in results-v4'}")
                continue
            arc_keys = {f"{u}->{v}" for u, v in inst["arcs"]}
            identity = {"arcs_match_every_recorded_plan": all(
                set(arm["answer"]["increments"]) == arc_keys for arm in row["arms"].values()
                if isinstance(arm.get("answer"), dict) and isinstance(arm["answer"].get("increments"), dict)),
                "paths": inst["paths"] == row["truth"]["paths"], "arc_count": len(inst["arcs"]) == row["truth"]["arcs"],
                "no_lease_throughput": max_flow(inst, {}) == row["truth"]["without_lease"]}
            if not all(identity.values()):
                incomplete.append(f"{item_id}: identity {identity}")
                continue
            best = optimum(inst)
            if not best["optimal"] or not best["integral"]:
                incomplete.append(f"{item_id}: MILP {best}")
                continue
            if (best["plan_value"], best["plan_spent"] <= inst["budget"]) != (best["value"], True):
                problems.append(f"{item_id}: the MILP's plan re-checks to {best['plan_value']} (claimed {best['value']})")
            truth_ok = best["value"] == row["truth"]["optimum"]
            if not truth_ok:
                problems.append(f"{item_id}: recorded truth {row['truth']['optimum']} != independent optimum "
                                f"{best['value']}")
            arms = {}
            for arm, rec in row["arms"].items():
                outcome, value = rescore(inst, rec.get("answer"), best["value"])
                arms[arm] = {"outcome": outcome, "throughput": value,
                             "reproduces": (outcome, value) == (rec["result"], rec["throughput"])}
                counts.setdefault(arm, {}).setdefault(rec["result"], 0)
                counts[arm][rec["result"]] += 1
                recomputed.setdefault(arm, {}).setdefault(outcome, 0)
                recomputed[arm][outcome] += 1
                if not arms[arm]["reproduces"]:
                    problems.append(f"{item_id} {arm}: recorded {rec['result']}/{rec['throughput']}, "
                                    f"independent {outcome}/{value}")
            items.append({"item_id": item_id, "independent_optimum": best["value"],
                          "recorded_truth": row["truth"]["optimum"], "truth_agrees": truth_ok,
                          "budget": inst["budget"], "arcs": len(inst["arcs"]), "arms": arms})
    verdict = "INCOMPLETE" if incomplete else "REFUTED" if problems else "CONFIRMED"
    summary_recorded = {arm: {k: v for k, v in o.items() if v} for arm, o in
                        recorded["summary"]["F7"]["outcomes"].items()}
    return {"schema": "pr155-f7-audit/1", "verdict": verdict, "rule": frozen["rule"],
            "items_audited": len(items), "truth_agreement": sum(i["truth_agrees"] for i in items),
            "outcomes_recorded_per_item": counts, "outcomes_independent": recomputed,
            "outcomes_recorded_summary": summary_recorded,
            "summary_reproduces": all(recomputed.get(arm, {}) == summary_recorded.get(arm, {})
                                      for arm in summary_recorded),
            "problems": problems, "incomplete": incomplete, "items": items,
            "freeze": {"frozen_at": frozen["frozen_at"], "inputs": frozen["inputs"]},
            "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                            text=True).stdout.strip(),
            "python": platform.python_version(), "finished_at": datetime.now(timezone.utc).isoformat()}


def main() -> None:
    if OUT.exists():
        raise AuditError(f"{OUT} exists: frozen evidence is never overwritten")
    report = audit()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: report[k] for k in ("verdict", "items_audited", "truth_agreement", "summary_reproduces",
                                             "outcomes_independent", "problems", "incomplete")}, indent=1))


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    main()
