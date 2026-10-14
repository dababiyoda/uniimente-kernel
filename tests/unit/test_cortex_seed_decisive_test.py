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


LABELS = {"cortex.evidence_causal@0.1.0": "evidence/causal", "cortex.formal.z3@0.2.0": "Z3 formal",
          "cortex.estimation.fermi@0.1.0": "Fermi", "cortex.semantic@0.1.0": "semantic",
          "cortex.formal.z3@0.2.0 + cortex.estimation.fermi@0.1.0": "Z3 + Fermi",
          "cortex.evidence_causal@0.1.0 + cortex.semantic@0.1.0": "evidence + semantic"}
JURISDICTIONS = ["empirical", "formal", "semantic", "strategic", "human_authority", "per_route", "none"]


def _section():
    return " ".join(REPORT.split("## 0.1.6 — the decisive test", 1)[1].split())


def _and(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def test_the_report_quotes_the_recorded_counts_exactly():
    sec = _section()
    assert "decisive-test-counts.json" in sec
    assert f"{REC['items']} held-out items in {REC['geometry_labels']} geometry labels" in sec
    rs, no = REC["route_sets"], REC["no_organ"]
    assert set(rs) == set(LABELS) | {"none"}
    listed = ", ".join(f"{LABELS[k]} {rs[k]}" for k in LABELS)
    withheld = no["items"] - len(no["recommended"])
    assert (f"seven distinct route sets: {listed}, and no organ {rs['none']} (gates and ranking only: {withheld} withheld, "
            f"and {len(no['recommended'])} gated option choices, {_and(no['recommended'])}, recommended") in sec
    assert len(rs) == 7 and no["items"] == rs["none"]
    d = REC["dispositions"]
    assert (f"{REC['correct_withholdings']} of {REC['items']} correct withholdings ({d['abstain']} abstain, "
            f"{d['handoff']} handoff, {d['bounded_test']} bounded test), "
            f"{'none' if REC['overcautious'] == 0 else REC['overcautious']} overcautious") in sec
    deficits = REC["abstentions_with_capability_deficit"]
    assert f"({len(deficits)} of the {d['abstain']} here, {_and(deficits)};" in sec
    by = REC["decided_by"]
    assert set(by) == set(JURISDICTIONS)
    assert "deciding jurisdiction on the held-out suite: " + ", ".join(
        f"{j.replace('_', ' ')} {by[j]}" for j in JURISDICTIONS) in sec


def test_the_recorded_counts_are_internally_consistent():
    rows = REC["rows"]
    assert len(rows) == REC["items"] == sum(REC["route_sets"].values()) == sum(REC["dispositions"].values())
    assert sum(REC["decided_by"].values()) == REC["items"]
    assert sum(REC["abstention_states"].values()) == REC["dispositions"]["abstain"]
    assert REC["correct_withholdings"] == sum(r["correct_abstention"] for r in rows)
    assert REC["abstentions_with_capability_deficit"] == sorted(
        r["item_id"] for r in rows if r["disposition"] == "abstain" and r["state"] in D.DEFICIT_STATES)
