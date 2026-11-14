"""Feasibility pilot on #189's disclosed pilot seeds 0-5 only (never a stress or holdout seed)."""
import sys, json, statistics, importlib.util, time
sys.path.insert(0, '.')
s = importlib.util.spec_from_file_location('exp', 'tests/evidence/antifragility-2026-10-15/experiment.py')
e = importlib.util.module_from_spec(s); s.loader.exec_module(e)
from greg.cognition.cortex import reason, registry_view
from greg.cognition.genomes import library
reg = registry_view(None)
for cid in ("cognition.swarm", "cognition.blackbox"):
    reg.set_state(cid, "ATTACHED")
ms = library.executables()["blackbox_multistart_lbfgsb"]
out = {}
for st in ("LOW", "HIGH"):
    for f in e.FUNCTIONS:
        row = {"swarm": [], "multistart": []}
        for seed in range(0, 6):
            it = e.instance(f, st, seed); req = e.request(it)
            r = reason({"problem_id": f"p-{st}-{f}-{seed}", "compile": {"geometry": {"geometry": "optimization"}, "data": req}},
                       registry=reg, journal=None)
            row["swarm"].append((r.get("result") or {}).get("fitness"))
            d = len(req["shift"])
            data = {"objective": f, "dimension": d, "lower": -5.12, "upper": 5.12, "shift": req["shift"],
                    "evaluations": req["budget"], "seed": seed}
            t = time.monotonic(); o = ms.solve(data, {"latency_s": 30.0, "compute": 10**6}); o = (o.get("output") or {}); row.setdefault("ms_s", []).append(round(time.monotonic()-t, 3))
            row["multistart"].append(o.get("value") if isinstance(o, dict) else None)
        tau = e.TOLERANCE[f]
        out[f"{st}/{f}"] = {"swarm_pass": sum(v is not None and v <= tau for v in row["swarm"]),
                            "ms_pass": sum(v is not None and v <= tau for v in row["multistart"]),
                            "swarm_med": statistics.median(row["swarm"]), "ms_med": statistics.median(row["multistart"]),
                            "ms_med_s": statistics.median(row["ms_s"])}
print(json.dumps(out, indent=1))
