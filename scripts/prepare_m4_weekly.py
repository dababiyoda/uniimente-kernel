"""Reproducibly derive cortex/evaluation/data/m4_weekly.json.gz from the public M4 competition files.

Sources (fetched once, hashes pinned below; the derived file records them):
  https://raw.githubusercontent.com/Mcompetitions/M4-methods/master/Dataset/Train/Weekly-train.csv
  https://raw.githubusercontent.com/Mcompetitions/M4-methods/master/Dataset/Test/Weekly-test.csv
  https://raw.githubusercontent.com/Mcompetitions/M4-methods/master/Dataset/M4-info.csv
Usage: python scripts/prepare_m4_weekly.py <dir-with-the-three-csvs>
"""
import csv
import gzip
import hashlib
import json
import sys
from pathlib import Path

PINNED = {"Weekly-train.csv": "d478d3f6ed673e6ed3c2cb0fbed5425f72eedd51318ebebeb0b5ecfcefc37714",
          "Weekly-test.csv": "3b2bc4be8e636e802260dcd843ca3c5da40536a1fbe1ecb3229a97dae4f44688"}
OUT = Path(__file__).resolve().parents[1] / "cortex" / "evaluation" / "data" / "m4_weekly.json.gz"


def main(src: Path):
    hashes = {}
    for name, expected in PINNED.items():
        digest = hashlib.sha256((src / name).read_bytes()).hexdigest()
        if digest != expected:
            raise SystemExit(f"{name}: sha256 {digest} != pinned {expected}")
        hashes[name] = "sha256:" + digest
    info = {r["M4id"]: r["category"] for r in csv.DictReader(open(src / "M4-info.csv")) if r["SP"] == "Weekly"}
    def rows(name):
        reader = csv.reader(open(src / name))
        next(reader)
        return {r[0]: [float(v) for v in r[1:] if v.strip()] for r in reader}
    train, test = rows("Weekly-train.csv"), rows("Weekly-test.csv")
    series = [{"id": k, "category": info[k], "train": train[k], "test": test[k]} for k in sorted(train, key=lambda x: int(x[1:]))]
    payload = {"schema": "m4-weekly/1", "source": "M4 competition (Makridakis, Spiliotis, Assimakopoulos 2018/2020), "
               "github.com/Mcompetitions/M4-methods Dataset/", "source_hashes": hashes,
               "license_note": "no license file in the source repository; used here only as an independent "
                               "benchmark with attribution", "horizon": 13, "series": series}
    with gzip.open(OUT, "wt", encoding="utf-8", compresslevel=9) as fh:
        json.dump(payload, fh, separators=(",", ":"))
    print(OUT, len(series))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
