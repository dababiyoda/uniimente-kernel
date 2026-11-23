"""LOCAL-REAL: the same code benchmarked under BUSY extra busy-loop processes, then with none, then verified. Only
the host changed, so the right verdict is not VERIFIED. Usage: python -B contention_pair.py OUT_DIR [BUSY] > verdict.json"""
import json
import multiprocessing
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from greg import compute  # noqa: E402


def spin(stop):
    while not stop.is_set():
        pass


if __name__ == "__main__":
    out_dir, busy = Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 4
    out_dir.mkdir(parents=True, exist_ok=True)
    stop = multiprocessing.Event()
    loops = [multiprocessing.Process(target=spin, args=(stop,)) for _ in range(busy)]
    for p in loops:
        p.start()
    time.sleep(1)
    before = compute.benchmark()
    stop.set()
    for p in loops:
        p.join()
    time.sleep(1)
    after = compute.benchmark()
    (out_dir / "contended-before.json").write_text(json.dumps(before, indent=1))
    (out_dir / "contention-removed-after.json").write_text(json.dumps(after, indent=1))
    verdict = compute.verify_improvement(before, after)
    verdict["busy_loops_during_before"] = busy
    print(json.dumps(verdict, indent=1))
