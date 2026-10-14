"""Rebuild ``bank_calls_halfhour.json.gz`` from its public source (P6 v3 natural family F6).

Source: ``bank_calls`` from the fpp3 R package (Hyndman & Athanasopoulos, *Forecasting: Principles and
Practice*, 3rd ed.), "call volume for a large North American commercial bank", 5-minute counts on 164
weekdays from 2003-03-03 to 2003-10-24, 07:00-21:00. The fpp3 package is GPL-3; the counts are factual
observations redistributed for teaching and research. This script reads the CSV mirror in the Rdatasets
collection, checks its sha256, and keeps only what the family needs: per day, 28 half-hour totals
(07:00-21:00; the single 21:00-21:05 interval is dropped).

Usage (network needed once; the output is committed, so evaluation never downloads):

    python -I cortex/evaluation/data/build_bank_calls.py /path/to/bank_calls.csv
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys

SOURCE_URL = "https://raw.githubusercontent.com/vincentarelbundock/Rdatasets/master/csv/fpp3/bank_calls.csv"
SOURCE_SHA256 = "6e430180c3fa8a284e38b8367e9a7d6dae4921ca1b184cbaba7aae9b07a8f9a5"
OUT = Path(__file__).resolve().parent / "bank_calls_halfhour.json.gz"
INTERVALS_PER_DAY, BLOCK = 169, 6


def build(csv_path: Path) -> dict:
    raw = csv_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SOURCE_SHA256:
        raise SystemExit(f"source sha256 {digest} differs from the recorded {SOURCE_SHA256}")
    days: dict[str, list[tuple[str, int]]] = {}
    for row in csv.DictReader(raw.decode("utf-8").splitlines()):
        stamp = row["DateTime"]
        days.setdefault(stamp[:10], []).append((stamp[11:16], int(row["Calls"])))
    out = []
    for date, rows in days.items():
        if len(rows) != INTERVALS_PER_DAY or rows[0][0] != "07:00" or rows[-1][0] != "21:00":
            raise SystemExit(f"{date}: unexpected interval layout")
        counts = [c for _, c in rows[:-1]]                       # drop 21:00-21:05
        out.append({"date": date, "blocks": [sum(counts[i:i + BLOCK]) for i in range(0, len(counts), BLOCK)]})
    return {"source": SOURCE_URL, "source_sha256": SOURCE_SHA256,
            "description": "half-hour call arrival counts, 28 blocks 07:00-21:00, one row per weekday",
            "licence": "fpp3 R package (GPL-3); factual counts redistributed for research",
            "block_starts": [f"{7 + i // 2:02d}:{30 * (i % 2):02d}" for i in range(28)], "days": out}


if __name__ == "__main__":
    data = build(Path(sys.argv[1]))
    with gzip.GzipFile(OUT, "wb", mtime=0) as fh:                 # mtime 0: byte-reproducible
        fh.write(json.dumps(data, separators=(",", ":")).encode())
    print(json.dumps({"days": len(data["days"]), "out": str(OUT)}))
