"""Cross-organ mission harness: appraisal negative controls (CI) and the
full three-process run (only when sibling organ checkouts are configured)."""
from __future__ import annotations

import copy
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("cross_organ_mission", ROOT / "scripts/cross_organ_mission.py")
mission = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mission)

PACKET = {"id": "p-1", "risk_flags": ["finance_education_only"]}
ASSESSMENT = {
    "opportunity_packet_id": "p-1", "go_no_go": "needs_more_evidence", "opportunity_score": 0.62,
    "market_alignment": 0.7, "risk_level": "medium", "legal_readiness": "review_required",
    "requires_human_approval": True, "validation_plan": ["step"], "reasons": ["r"],
    "expected_roi": "modeled 2.1x over 18 months; unknown until validation — no revenue promises",
    "cases": [{"case": "bull"}, {"case": "bear"}, {"case": "do_nothing"}],
}


def test_honest_assessment_is_internally_appraised():
    result = mission.appraise(PACKET, ASSESSMENT, copy.deepcopy(ASSESSMENT))
    assert result["verdict"] == "internally_appraised"
    assert "not external acceptance" in result["tier"]


@pytest.mark.parametrize("field,value", [
    ("go_no_go", "go"), ("opportunity_score", 0.99), ("risk_level", "low"), ("reasons", ["other"]),
])
def test_irreproducible_assessment_fails(field, value):
    rederived = {**ASSESSMENT, field: value}
    result = mission.appraise(PACKET, ASSESSMENT, rederived)
    assert result["verdict"] == "appraisal_failed"
    assert result["reproduced"][field] is False


@pytest.mark.parametrize("mutate,invariant", [
    (lambda a: a.update(requires_human_approval=False), "human_approval_required"),
    (lambda a: a.update(cases=[{"case": "bull"}]), "committee_has_bull_bear_do_nothing"),
    (lambda a: a.update(legal_readiness="standard"), "finance_flag_forces_review"),
    (lambda a: a.update(expected_roi="guaranteed 10x"), "no_revenue_promise"),
    (lambda a: a.update(opportunity_packet_id="p-2"), "assessment_answers_this_packet"),
])
def test_reproducible_but_invalid_assessment_fails(mutate, invariant):
    """Two runs agreeing on a wrong answer must not pass appraisal."""
    bad = copy.deepcopy(ASSESSMENT)
    mutate(bad)
    result = mission.appraise(PACKET, bad, copy.deepcopy(bad))
    assert result["verdict"] == "appraisal_failed"
    assert result["invariants"][invariant] is False


ENV = ("UNIIMENTE_DALEOBANKS_DIR", "UNIIMENTE_DALEOBANKS_PYTHON",
       "UNIIMENTE_WEALTHMACHINE_DIR", "UNIIMENTE_WEALTHMACHINE_PYTHON")


@pytest.mark.skipif(not all(os.getenv(v) for v in ENV), reason="sibling organ checkouts not configured")
def test_full_three_process_mission(tmp_path):
    proc = subprocess.run([sys.executable, str(ROOT / "scripts/cross_organ_mission.py"),
                           "--daleobanks", os.environ[ENV[0]], "--daleobanks-python", os.environ[ENV[1]],
                           "--wealthmachine", os.environ[ENV[2]], "--wealthmachine-python", os.environ[ENV[3]],
                           "--out", str(tmp_path)], capture_output=True, text=True, timeout=900)
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    assert "RESULT: PASS" in proc.stdout
