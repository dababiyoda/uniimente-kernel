"""F7 spend at equal throughput (review of #179, M11): a diagnostic on development items only.

The frozen F7 scorer measures throughput alone. This probe asks a question the freeze did not: when the
composition and parametric min-cost flow (PMCF) reach the same throughput, does the composition lease more than
it needs? PMCF's min-cost flow at the reached volume is the cheapest plan for that volume, so any excess is spend
that carries no extra flow. Held-out items are never read. The result is diagnostic, not a generalisation claim;
admission v3 and the F7 re-measurement should pre-register spend at equal throughput as a declared secondary
measure.

    python -m cortex.evaluation.pr155_f7_spend_diagnostic.probe OUT.json
"""
import json
import subprocess
import sys
from importlib.metadata import version

from cortex.evaluation.composition_lift import run_v4 as V
from greg.cognition.genomes.flow import expansion_value


def main(out: str) -> dict:
    dev, _ = V.partition()
    items = [it for n in dev for p in range(len(V.sndlib()["networks"][n]["top_demands"])) if (it := V.f7(n, p))]
    assert all(it["network"] in dev for it in items)
    rows = []
    for it in items:
        net = it["payload"]["capacity_network"]
        ans, _, _ = V.chain(it, "graph_then_allocate")
        pm = V.parametric_min_cost_flow(net)

        def spend(inc):
            return sum(u * net["unit_cost"][k] for k, u in inc.items())
        rows.append({"item": it["item_id"],
                     "composition_throughput": expansion_value(net, ans["increments"])[0] if ans else None,
                     "pmcf_throughput": expansion_value(net, pm["increments"])[0],
                     "composition_spend": spend(ans["increments"]) if ans else None,
                     "pmcf_spend": spend(pm["increments"]), "budget": net["budget"],
                     "same_plan": bool(ans) and {k: v for k, v in ans["increments"].items() if v}
                     == {k: v for k, v in pm["increments"].items() if v}})
    equal = [r for r in rows if r["composition_throughput"] == r["pmcf_throughput"]]
    excess = [(r["composition_spend"] - r["pmcf_spend"]) / r["budget"] for r in equal
              if r["composition_spend"] > r["pmcf_spend"]]
    summary = {"partition": "dev", "items": len(rows), "equal_throughput": len(equal),
               "composition_spends_more": len(excess),
               "pmcf_spends_more": sum(r["pmcf_spend"] > r["composition_spend"] for r in equal),
               "same_plan": sum(r["same_plan"] for r in rows),
               "excess_share_of_budget_mean": round(sum(excess) / len(excess), 4) if excess else 0.0,
               "excess_share_of_budget_max": round(max(excess), 4) if excess else 0.0}
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout.strip())
    record = {"summary": summary, "rows": rows, "source_commit": head, "working_tree_dirty": dirty,
              "versions": {p: version(p) for p in ("networkx", "ortools", "scipy", "numpy")},
              "python": sys.version.split()[0]}
    with open(out, "w") as fh:
        json.dump(record, fh, indent=1)
        fh.write("\n")
    return summary


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1]), indent=1))
