"""Acceptance B.G2: recorded Mind-versus-baseline results are recomputed from their own retained rows.

Mission B: "Compare against a competent simpler baseline." The recorded comparisons were checked only for freeze
hashes and row shape, so an edited verdict or summary would have passed. Here the verdict of the cross-geometry
held-out run and the per-family composition lift are recomputed by the same code that produced them, from the
rows retained beside them, and must equal what was recorded; an edited copy is caught.

Genome admission (docs/evidence/greg-genome-admission) retains only aggregates, not the per-seed rows its rule
reads, so its statuses cannot be recomputed from the record; that is acceptance gap B.G9.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from cortex.evaluation import crossgeo_loss
from cortex.evaluation.composition_lift import run as composition_lift

ROOT = Path(__file__).resolve().parents[2]
CROSSGEO = ROOT / "tests" / "evidence" / "greg-crossgeo-v0.3" / "results.json"
LIFT = ROOT / "docs" / "evidence" / "greg-composition-lift" / "2026-10-07" / "results.json"


def crossgeo_verdict(d: dict) -> dict:
    return crossgeo_loss.verdict(d["heldout"]["arms"], d["heldout"]["rows"], d["adversarial"]["rows"], d["planning"])


def assert_same(recomputed, recorded):
    if isinstance(recorded, dict):
        assert set(recomputed) == set(recorded)
        for key in recorded:
            assert_same(recomputed[key], recorded[key])
    elif isinstance(recorded, list):
        assert len(recomputed) == len(recorded)
        for a, b in zip(recomputed, recorded):
            assert_same(a, b)
    elif isinstance(recorded, float):
        assert recomputed == pytest.approx(recorded, rel=1e-9)
    else:
        assert recomputed == recorded


def test_the_crossgeo_verdict_recomputes_from_its_retained_rows():
    d = json.loads(CROSSGEO.read_text())
    recomputed = crossgeo_verdict(d)
    assert_same(recomputed, d["verdict"])
    assert recomputed["strongest_run_baseline"] == "static_router" and recomputed["not_run"] == ["always_llm", "tool_llm"]


def test_the_composition_lift_summary_recomputes_from_its_retained_rows():
    d = json.loads(LIFT.read_text())
    assert_same(composition_lift.summarize(d["heldout"]), d["summary"])


def test_an_edited_record_no_longer_matches_its_recomputation():
    d = json.loads(CROSSGEO.read_text())
    edited = copy.deepcopy(d["verdict"])
    edited["gain"]["gain"] *= 2                               # an inflated gain in the record
    with pytest.raises(AssertionError):
        assert_same(crossgeo_verdict(d), edited)
    lift = json.loads(LIFT.read_text())
    tampered = copy.deepcopy(lift["heldout"])
    flipped = next((arm for row in tampered for arm in row["arms"].values() if arm["result"] == "correct"), None)
    assert flipped is not None
    flipped["result"] = "wrong"                               # one retained outcome changed
    with pytest.raises(AssertionError):
        assert_same(composition_lift.summarize(tampered), lift["summary"])
