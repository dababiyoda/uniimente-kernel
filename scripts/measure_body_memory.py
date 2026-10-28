"""Measure what a running GREG body keeps in memory as its history grows.

One holding mission (infinite closure, 60 s cadence) on a real body, ticked with a
simulated clock, the scenario of FINDING-LEDGER-APPEND-COST-2026-10-14. At each
checkpoint it reports retained ledger records, resident set size, Python heap held
(tracemalloc) and where the heap growth lives, by source file.

    python scripts/measure_body_memory.py --ticks 2400 --every 600 [--out result.json]

The body runs in a temporary directory with a test key; nothing leaves the machine.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import resource
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from greg.body import Body  # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy  # noqa: E402


def rss_kb() -> int:
    with open("/proc/self/statm") as fh:
        return int(fh.read().split()[1]) * (os.sysconf("SC_PAGE_SIZE") // 1024)


def heap_by_file(snapshot, root: Path, top: int = 8) -> list:
    rows = []
    for stat in snapshot.statistics("filename")[:top]:
        name = stat.traceback[0].filename
        try:
            name = str(Path(name).resolve().relative_to(root))
        except ValueError:
            name = Path(name).name
        rows.append({"file": name, "kb": round(stat.size / 1024, 1), "blocks": stat.count})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticks", type=int, default=2400)
    ap.add_argument("--every", type=int, default=600)
    ap.add_argument("--out")
    ap.add_argument("--no-trace", action="store_true", help="RSS only (tracemalloc slows the body)")
    ap.add_argument("--resident", type=int, help="override the ledger's resident window (records)")
    ap.add_argument("--trim", action="store_true",
                    help="return free heap pages to the OS (glibc malloc_trim) before each RSS reading")
    args = ap.parse_args(argv)
    if args.resident is not None:
        import provenance.ledger as ledger_module
        ledger_module.RESIDENT_RECORDS = args.resident

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        home, key, body_id, _ = make_body(tmp)
        ws = workspace(home, "m:hold")
        drop(home, signed(key, body_id, "MISSION", mission(
            "m:hold", checks=[note_check("n", ws / "n.txt", "kept")],
            strategies=[write_strategy("w", "n.txt", "kept", ["n"])], capabilities=["fs.read", "fs.write"],
            closure={"kind": "infinite", "cadence_seconds": 60})))
        clock = Clock()
        if not args.no_trace:
            tracemalloc.start(1)
        points = []
        with Body(home, clock=clock) as body:
            ledger = body.journal.ledger
            started = time.perf_counter()
            for i in range(1, args.ticks + 1):
                body.tick()
                clock.advance(61)
                if i % args.every == 0:
                    gc.collect()
                    if args.trim:
                        import ctypes
                        ctypes.CDLL("libc.so.6").malloc_trim(0)
                    point = {"ticks": i, "records": len(ledger.records), "rss_kb": rss_kb(),
                             "ledger_bytes_on_disk": os.path.getsize(ledger.path),
                             "seconds": round(time.perf_counter() - started, 1)}
                    if not args.no_trace:
                        snap = tracemalloc.take_snapshot()
                        point["heap_kb"] = round(sum(s.size for s in snap.statistics("filename")) / 1024, 1)
                        point["heap_by_file"] = heap_by_file(snap, ROOT)
                    points.append(point)
                    print(json.dumps({k: v for k, v in point.items() if k != "heap_by_file"}), flush=True)
        first, last = points[0], points[-1]
        dr = last["records"] - first["records"]
        result = {
            "scenario": "one holding mission, infinite closure, 60 s cadence, simulated clock",
            "resident_records": getattr(sys.modules.get("provenance.ledger"), "RESIDENT_RECORDS", None),
            "python": sys.version.split()[0], "ticks": args.ticks, "points": points,
            "rss_bytes_per_record": round((last["rss_kb"] - first["rss_kb"]) * 1024 / dr, 1) if dr else None,
            "disk_bytes_per_record": round((last["ledger_bytes_on_disk"] - first["ledger_bytes_on_disk"]) / dr, 1)
            if dr else None,
            "max_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        }
        if not args.no_trace:
            result["heap_bytes_per_record"] = round((last["heap_kb"] - first["heap_kb"]) * 1024 / dr, 1) if dr else None
        print(json.dumps({k: v for k, v in result.items() if k != "points"}, indent=1))
        if args.out:
            Path(args.out).write_text(json.dumps(result, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
