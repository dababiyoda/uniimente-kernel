"""Does a real solver worker exit non-zero on malformed input (its own bug, not the host)? cwd = tree. Runs worker.py directly."""
import json, subprocess, sys, itertools
sys.path.insert(0, ".")
from greg.cognition.solvers import SOLVERS
from greg.cognition.contracts import canonical
geometry = {"latency_limit": 5, "compute_limit": 100000}
payloads = [("list", []), ("nested_int", {"items": [1, 2], "workers": [3], "orders": [4], "edges": [5], "nodes": [6], "samples": [7], "series": [8], "values": 9, "bounds": 3, "data": 1, "matrix": [1], "constraints": [1], "variables": [1], "jobs": [1], "tasks": [1], "arms": [1], "observations": [1], "graph": 1, "function": 1, "votes": [1], "claims": [1], "evidence": [1]}),
            ("str", "x"), ("none", None), ("deep", {"a": [[[[[[[[1]]]]]]]] * 3})]
hits = []
fams = sorted(SOLVERS)[: int(sys.argv[1]) if len(sys.argv) > 1 else 30]
for fam in fams:
    for label, data in payloads:
        req = canonical({"data": data, "geometry": geometry})
        try:
            p = subprocess.run([sys.executable, "-I", "greg/cognition/worker.py", fam], input=req.encode(), capture_output=True, timeout=30)
        except subprocess.TimeoutExpired:
            hits.append((fam, label, "timeout", "")); continue
        if p.returncode:
            hits.append((fam, label, p.returncode, p.stderr.decode()[-160:].replace("\n", " | ")))
print("families tried:", len(fams), "payloads each:", len(payloads), "non-zero exits:", len(hits))
for h in hits[:25]: print("  ", h)
