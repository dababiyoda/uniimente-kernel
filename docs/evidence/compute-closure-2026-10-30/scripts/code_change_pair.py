"""LOCAL-REAL positive control: a real code change on the same host. The before run carries a slower scratch-ledger
step (DELAY seconds of extra wait per replicate, as slower code would); the after run is the shipped code. Only the
code changed, so the right verdict is VERIFIED unless the host's contention moved between the runs. ATTEMPTS pairs
are run and every verdict is kept. Usage: python -B code_change_pair.py [ATTEMPTS] [DELAY] > code-change-pairs.json"""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from greg import compute  # noqa: E402

attempts = int(sys.argv[1]) if len(sys.argv) > 1 else 3
delay = float(sys.argv[2]) if len(sys.argv) > 2 else 0.15
shipped = compute._scratch_ledger


def slower(seed, records):
    shipped(seed, records)
    time.sleep(delay)


results = []
for _ in range(attempts):
    compute._scratch_ledger = slower
    before = compute.benchmark()
    compute._scratch_ledger = shipped
    after = compute.benchmark()
    v = compute.verify_improvement(before, after)
    results.append({k: v.get(k) for k in ("verdict", "reason", "p_value", "relative_effect", "noise_floor",
                                          "median_before", "median_after")} | {"contention": v["contention"]})
print(json.dumps({"delay_removed_seconds": delay, "attempts": results,
                  "verified": sum(r["verdict"] == "VERIFIED" for r in results)}, indent=1))
