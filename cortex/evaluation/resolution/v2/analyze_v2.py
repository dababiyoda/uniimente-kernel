"""Abstention-to-resolution routing, run v2: the v1 decision rule unchanged, checked against v2's freeze.

    python analyze_v2.py --suite SUITE --run ARM=FILE [...] --out FILE

H1 reads each row's ``harm``, which the v2 harness scores by the pre-registered text (D2). ``harm_any_detached`` is
reported per arm, descriptive only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze as A  # noqa: E402  (the frozen v1 decision rule)

FREEZE = A.FREEZE.parent / "v2" / "freeze.json"
ROOT = Path(__file__).resolve().parents[4]
_ANALYZE = A.analyze


def freeze_mismatches(freeze: Path = FREEZE) -> list:
    """v2's frozen files whose bytes changed since its freeze; a run that reports with any is INCONCLUSIVE."""
    import hashlib
    bad = []
    for rel, want in json.loads(freeze.read_text())["files"].items():
        path = ROOT / rel
        got = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if got != want:
            bad.append(rel)
    return bad


def analyze(suite: dict, runs: dict) -> dict:
    out = _ANALYZE(suite, runs)
    out["harm_any_detached"] = {arm: sorted(r["item_id"] for r in run["rows"] if r.get("harm_any_detached"))
                                for arm, run in runs.items()}
    return out


A.analyze = analyze
A.freeze_mismatches = freeze_mismatches

if __name__ == "__main__":
    raise SystemExit(A.main())
