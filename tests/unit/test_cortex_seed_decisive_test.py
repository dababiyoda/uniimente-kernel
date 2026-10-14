"""The decisive-test counts cited by docs/cortex/SEED_EXPERIMENT_REPORT.md are recomputed from the frozen routed
arm and the reported run (`tests/evidence/cortex-seed-v0.1.6/decisive-test-counts.json`). Route selection and the
finality jurisdiction are structural, so this runs the same with or without Z3."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("cortex_seed_decisive_test",
                                               ROOT / "scripts/analysis/cortex_seed_decisive_test.py")
D = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(D)
REC = json.loads(D.OUT.read_text(encoding="utf-8"))
REPORT = (ROOT / "docs/cortex/SEED_EXPERIMENT_REPORT.md").read_text(encoding="utf-8")


def test_the_recorded_counts_reproduce():
    assert D.analyse() == REC


def test_the_counts_the_report_states():
    assert REC["items"] == 42 and REC["geometry_labels"] == 12
    assert len(REC["route_sets"]) == 7 and sum(REC["route_sets"].values()) == 42
    assert REC["no_organ"] == {"items": 8, "dispositions": {"abstain": 1, "handoff": 5, "recommend": 2},
                               "recommended": ["H-G01", "H-G05"]}
    assert REC["dispositions"] == {"abstain": 11, "bounded_test": 4, "handoff": 8, "recommend": 19}
    assert REC["correct_withholdings"] == 23 and REC["overcautious"] == 0
    assert REC["abstentions_with_capability_deficit"] == ["H-S03"]
    section = REPORT.split("## 0.1.6 — the decisive test", 1)[1]
    assert "decisive-test-counts.json" in section
    for jurisdiction, n in REC["decided_by"].items():
        assert f"{jurisdiction.replace('_', ' ')} {n}" in section, jurisdiction
