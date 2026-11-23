"""Stage A runner (pre-registered in docs/evidence/symbiosoup-stage-a/2026-11-22/PREREGISTRATION.md).

PYTHONPATH=. python -m developmental.symbiosoup.stage_a --seeds 0 1 2 --out <dir>
Appends one JSON line per finished seed to <dir>/runs.jsonl and a progress line per checkpoint to
<dir>/progress-<seed>.jsonl."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .soup import Soup


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", required=True)
    ap.add_argument("--programs", type=int, default=128 * 1024)
    ap.add_argument("--epochs", type=int, default=16000)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for seed in args.seeds:
        started = time.monotonic()
        progress = out / f"progress-{seed}.jsonl"

        def note(point, progress=progress):
            with progress.open("a") as f:
                f.write(json.dumps(point) + "\n")
        result = Soup(seed=seed, programs=args.programs).run(args.epochs, threshold=1.0, after=2, on_point=note)
        result["wall_seconds"] = round(time.monotonic() - started, 1)
        result["sensitivity_threshold_3"] = next((p["epoch"] for p in result["points"]
                                                  if p["higher_entropy"] >= 3.0), None)
        with (out / "runs.jsonl").open("a") as f:
            f.write(json.dumps({k: v for k, v in result.items() if k != "points"}) + "\n")


if __name__ == "__main__":
    main()
