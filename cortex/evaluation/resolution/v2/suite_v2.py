"""Abstention-to-resolution routing, run v2: the candidate generator.

The v1 generator (``../suite.py``) unchanged, with a new seed, and with every base item v1's suite used excluded as
well as the development items, so v2's held-out items are new to the dividend's author's measurements.

    python suite_v2.py --out candidates.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import suite as S  # noqa: E402  (the frozen v1 generator)

SEED = 20261114
V1_SUITE = S.ROOT / "docs/evidence/greg-abstention-resolution/2026-11-13/suite.json"


def used_in_v1() -> set:
    return {i["base_item_id"] for i in json.loads(V1_SUITE.read_text())["items"] if i.get("base_item_id")}


def candidates() -> list:
    v1 = used_in_v1()
    development = S._excluded
    S._excluded = lambda item_id: development(item_id) or item_id in v1
    try:
        return S.candidates(seed=SEED)
    finally:
        S._excluded = development


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    items = candidates()
    args.out.write_text(json.dumps({"schema": "greg-resolution-candidates/1", "seed": SEED, "source": S.SOURCE,
                                    "excludes": "development items and every v1 suite base item",
                                    "items": items, "digest": S.digest(items)}, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"candidates": len(items), "digest": S.digest(items)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
