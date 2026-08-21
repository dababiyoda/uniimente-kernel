"""Execute the real cross-repository Route B counterfactual.

Canonical CI supplies pinned DALEOBANKS and WealthMachineIntelligence
checkouts. The ordinary kernel suite skips this one test when those explicit
inputs are absent, then the same CI job runs it separately after both pinned
checkouts are present. A skip is not reported as Route B evidence.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


KERNEL_ROOT = Path(__file__).resolve().parents[2]


def _external_checkout(variable: str, marker: str) -> Path:
    value = os.environ.get(variable)
    if not value:
        pytest.skip(f"{variable} absent; dedicated Route B CI step must supply it")
    path = Path(value).resolve()
    if not (path / marker).is_file():
        pytest.fail(f"{variable} does not contain pinned source marker {marker}: {path}")
    return path


def test_real_daleobanks_to_wmi_route_is_causally_controlled() -> None:
    daleobanks = _external_checkout(
        "TRACK_A_DALEOBANKS_DIR", "services/idea_refinery.py"
    )
    wealthmachine = _external_checkout(
        "TRACK_A_WMI_DIR", "src/services/opportunity_intake.py"
    )
    probe = KERNEL_ROOT / "runtime/probes/route_b_counterfactual.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(probe),
            "--kernel", str(KERNEL_ROOT),
            "--daleobanks", str(daleobanks),
            "--wealthmachine", str(wealthmachine),
        ],
        cwd=KERNEL_ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert completed.returncode == 0, (
        f"Route B probe failed\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
    )

    report = json.loads(completed.stdout.strip().splitlines()[-1])
    assert report["classification"] == "SANDBOX_EXECUTION_CONSEQUENCE_INERT"
    assert report["closure_count_delta"] == 0
    assert report["external_effects"] == 0
    assert report["network"] == "DENIED"
    assert report["source_revisions_verified"] is True
    assert report["route"]["schema_path"] == (
        "contracts/wire-opportunity-packet.schema.json"
    )
    assert report["route"]["consequence_class"] == "INERT"
    assert report["scope_guards"]["non_inert_binding_refused"] is True
    assert report["states"]["A_HEALTHY"]["assessment"] is True
    assert report["states"]["B_EDGE_DISABLED"]["assessment"] is False
    assert report["states"]["C_LOCAL_MOCK_BYPASS"]["lookalike_assessment_exists"] is True
    assert report["states"]["C_LOCAL_MOCK_BYPASS"]["accepted_by_router"] is False
    assert report["states"]["D_EDGE_RESTORED"]["causal_receipt"] is True
    assert report["states"]["D_EDGE_RESTORED"]["requires_human_approval"] is True
    assert report["same_binding_after_restore"] is True
