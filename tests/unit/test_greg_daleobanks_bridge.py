"""DALEOBANKS work surface: GREG runs DALEOBANKS's own checks and publishing gate in DALEOBANKS's interpreter.

Skipped when no DALEOBANKS checkout with an installed interpreter sits beside this repository
(``../DALEOBANKS/.venv``). No platform credentials or LIVE arming are ever supplied here.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from greg import daleobanks_bridge as bridge
from greg.capabilities import BUILTINS, InvocationContext, SecretBroker

DALEOBANKS = Path(__file__).resolve().parents[3] / "DALEOBANKS"
pytestmark = pytest.mark.skipif(not (DALEOBANKS / ".venv/bin/python").exists(),
                                reason="DALEOBANKS checkout with .venv not present beside the Kernel")


def ctx(tmp_path, capability):
    return InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path, DALEOBANKS),
                             secrets=SecretBroker(tmp_path / "s.json"), manifest=BUILTINS[capability][0],
                             mission_id="m:test", grant_id="grant-test")


def files(tmp_path, draft: str):
    (tmp_path / "source.txt").write_text("z3-solver 5.1.0.0 released; previous 5.0.0.0.\n")
    (tmp_path / "draft.txt").write_text(draft)
    return {"daleobanks_root": str(DALEOBANKS), "draft": str(tmp_path / "draft.txt"),
            "source": str(tmp_path / "source.txt")}


def test_verified_draft_and_publish_request_is_truthfully_blocked_by_daleobanks(tmp_path):
    params = files(tmp_path, "z3-solver 5.1.0.0 is on PyPI, after 5.0.0.0.")
    verdict = bridge.verify(params, ctx(tmp_path, "daleobanks.verify"))
    assert verdict["verdict"] == "VERIFIED", verdict["findings"]
    out = bridge.publish(params, ctx(tmp_path, "daleobanks.publish"))
    assert out["status"] == "BLOCKED_BY_DALEOBANKS" and out["published"] == {}
    assert out["kill_switch_armed"] is False and all(r["dry_run"] for r in out["dry_run"].values())
    assert out["daleobanks_ledger"]["chain_ok"] is True
    outcome = bridge.publish_status({}, ctx(tmp_path, "daleobanks.outcome"))
    assert outcome["requested"] and outcome["outcome"] == "BLOCKED_DRY_RUN"


def test_figures_absent_from_the_source_are_rejected(tmp_path):
    params = files(tmp_path, "z3-solver 6.0 is out and 90% faster.")
    verdict = bridge.verify(params, ctx(tmp_path, "daleobanks.verify"))
    assert verdict["verdict"] == "REJECTED" and any("not found in the source" in f for f in verdict["findings"])


def test_live_arming_is_never_forwarded_by_greg(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE", "true")                      # even if the body's environment says LIVE...
    params = files(tmp_path, "z3-solver 5.1.0.0 is on PyPI.")
    out = bridge.publish(params, ctx(tmp_path, "daleobanks.publish"))
    assert out["kill_switch_armed"] is False and out["published"] == {}   # ...GREG never arms DALEOBANKS
