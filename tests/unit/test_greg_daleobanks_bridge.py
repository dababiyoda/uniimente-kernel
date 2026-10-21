"""DALEOBANKS work surface: GREG runs DALEOBANKS's own checks and publishing gate in DALEOBANKS's interpreter.

Runs against the pinned organ when UNIIMENTE_DALEOBANKS_ROOT/UNIIMENTE_DALEOBANKS_PYTHON name it (as CI does), else
a DALEOBANKS checkout with an installed interpreter beside this repository (``../DALEOBANKS/.venv``); skipped when
neither exists. No platform credentials or LIVE arming are ever supplied here.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from greg import daleobanks_bridge as bridge
from greg.capabilities import BUILTINS, InvocationContext, SecretBroker

DALEOBANKS = Path(os.environ.get("UNIIMENTE_DALEOBANKS_ROOT") or Path(__file__).resolve().parents[3] / "DALEOBANKS")
PYTHON = Path(os.environ.get("UNIIMENTE_DALEOBANKS_PYTHON") or DALEOBANKS / ".venv/bin/python")
pytestmark = pytest.mark.skipif(not PYTHON.exists(), reason="no DALEOBANKS checkout with an installed interpreter")


def ctx(tmp_path, capability):
    return InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path, DALEOBANKS),
                             secrets=SecretBroker(tmp_path / "s.json"), manifest=BUILTINS[capability][0],
                             mission_id="m:test", grant_id="grant-test")


def files(tmp_path, draft: str):
    (tmp_path / "source.txt").write_text("z3-solver 5.1.0.0 released; previous 5.0.0.0.\n")
    (tmp_path / "draft.txt").write_text(draft)
    return {"daleobanks_root": str(DALEOBANKS), "python": str(PYTHON), "draft": str(tmp_path / "draft.txt"),
            "source": str(tmp_path / "source.txt")}


def test_verified_draft_and_publish_request_is_truthfully_blocked_by_daleobanks(tmp_path):
    params = files(tmp_path, "z3-solver 5.1.0.0 is on PyPI, after 5.0.0.0.")
    verdict = bridge.verify(params, ctx(tmp_path, "daleobanks.verify"))
    assert verdict["verdict"] == "VERIFIED", verdict["findings"]
    out = bridge.publish(params, ctx(tmp_path, "daleobanks.publish"))
    assert out["status"] == "BLOCKED_BY_DALEOBANKS" and out["published"] == {}
    assert out["kill_switch_armed"] is False and all(r["dry_run"] for r in out["dry_run"].values())
    assert out["publish_gated"] == []                       # disarmed: the kill switch decided, no grant was asked
    assert out["daleobanks_ledger"]["chain_ok"] is True
    # The outcome sensor projects this mission's canonical publish receipt; the organ file only confirms it.
    from dataclasses import replace
    from events.spine import EventSpine
    from greg.journal import Journal
    from provenance.ledger import EvidenceLedger
    journal = Journal(EventSpine(EvidenceLedger("sha256:" + "6" * 64)), actor="spiffe://uniimente.internal/greg/test")
    receipt = journal.ledger.append("receipt", {"result": {"result_class": "positive", "output": out}}).hash
    journal.record("mission.action", {"mission_id": "m:test", "action_id": "publish", "status": "DONE",
                                      "capability": "daleobanks.publish", "receipt": receipt}, key=["publish"])
    outcome = bridge.publish_status({}, replace(ctx(tmp_path, "daleobanks.outcome"), journal=journal))
    assert outcome["requested"] and outcome["outcome"] == "BLOCKED_DRY_RUN" and outcome["organ_consistent"]


def test_figures_absent_from_the_source_are_rejected(tmp_path):
    params = files(tmp_path, "z3-solver 6.0 is out and 90% faster.")
    verdict = bridge.verify(params, ctx(tmp_path, "daleobanks.verify"))
    assert verdict["verdict"] == "REJECTED" and any("not found in the source" in f for f in verdict["findings"])


def test_live_arming_is_never_forwarded_by_greg(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE", "true")                      # even if the body's environment says LIVE...
    params = files(tmp_path, "z3-solver 5.1.0.0 is on PyPI.")
    out = bridge.publish(params, ctx(tmp_path, "daleobanks.publish"))
    assert out["kill_switch_armed"] is False and out["published"] == {}   # ...GREG never arms DALEOBANKS


def test_the_real_organ_runs_inside_the_confined_namespace_and_reaches_nothing_while_disarmed(tmp_path):
    """#26: on a confined body DALEOBANKS's own interpreter runs in a network namespace behind the relay. Its checks
    and its disarmed publishing gate work unchanged there; anything it tried to reach would be journaled."""
    from foundry.systems.segmentation import Journal, Relay
    from greg.worker_isolation import WorkerIsolationError, _backend
    try:
        _backend(require_bubblewrap=True)
    except WorkerIsolationError as exc:
        pytest.skip(f"no bubblewrap network namespaces here: {exc}")
    journal = Journal(tmp_path / "egress-journal.jsonl")
    relay = Relay({}, journal)
    params = files(tmp_path, "z3-solver 5.1.0.0 is on PyPI, after 5.0.0.0.")

    def confined(capability):
        return InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path, DALEOBANKS),
                                 secrets=SecretBroker(tmp_path / "s.json"), manifest=BUILTINS[capability][0],
                                 mission_id="m:test", grant_id="grant-test", egress=relay)
    assert bridge.verify(params, confined("daleobanks.verify"))["verdict"] == "VERIFIED"
    out = bridge.publish(params, confined("daleobanks.publish"))
    assert out["status"] == "BLOCKED_BY_DALEOBANKS" and out["published"] == {}
    assert out["daleobanks_ledger"]["chain_ok"] is True
    assert journal.read() == []                         # the disarmed organ asked the relay for nothing


# -- Next-wave item 4: the organ's own gate reason, and the DALEOBANKS grant the founder signed ------------------


def _armed_interpreter(tmp_path) -> str:
    """The founder arms DALEOBANKS (its own LIVE switch) through the interpreter the signed mission names. GREG's
    bridge never sets or forwards LIVE; this shim stands for the founder's own DALEOBANKS environment."""
    shim = tmp_path / "armed-daleobanks" / "python"
    shim.parent.mkdir()
    shim.write_text(f"#!/bin/sh\nLIVE=true exec {PYTHON} \"$@\"\n")
    shim.chmod(0o755)
    return str(shim)


def test_an_armed_daleobanks_without_its_grant_is_reported_with_its_own_gate_reason(tmp_path):
    """Armed and under its rate limit, DALEOBANKS still needs a grant a human approved there for this exact draft.
    Without one its publish authority refuses before any platform call and ledgers why; GREG reports that reason,
    not a guess (before: "rate governor or credentials")."""
    params = {**files(tmp_path, "z3-solver 5.1.0.0 is on PyPI."), "python": _armed_interpreter(tmp_path)}
    out = bridge.publish(params, ctx(tmp_path, "daleobanks.publish"))
    assert out["kill_switch_armed"] is True and out["published"] == {}
    assert out["status"] == "BLOCKED_BY_DALEOBANKS" and out["platforms"]
    if not (DALEOBANKS / "services/publish_authority.py").exists():
        # An organ older than DALEOBANKS's publish authority has no grant gate; the report must say so, not invent one.
        assert out["publish_gated"] == [] and "no gate recorded a refusal" in out["why"]
        return
    assert [g["reason"] for g in out["publish_gated"]] == ["no_capability_grant"] * len(out["platforms"])
    assert "no_capability_grant" in out["why"] and "daleobanks_grant" in out["why"]
    assert all(r["dry_run"] for r in out["dry_run"].values())
    assert out["daleobanks_ledger"]["chain_ok"] is True


class _Organ:
    """Stands in for DALEOBANKS's interpreter: records the request GREG sent and answers as the organ would."""

    def __init__(self, answer):
        self.answer, self.requests = answer, []

    def __call__(self, argv, input, **kwargs):
        import json
        import subprocess
        self.requests.append(json.loads(input))
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(self.answer), stderr="")


def _stub(tmp_path, monkeypatch, answer):
    organ = _Organ(answer)
    monkeypatch.setattr(bridge.subprocess, "run", organ)
    root = tmp_path / "organ"
    (root / ".venv" / "bin").mkdir(parents=True)
    python = root / ".venv" / "bin" / "python"
    python.write_text("#!/bin/sh\n")
    python.chmod(0o755)
    (tmp_path / "draft.txt").write_text("text")
    context = InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path,),
                                secrets=SecretBroker(tmp_path / "s.json"), manifest=BUILTINS["daleobanks.publish"][0],
                                mission_id="m:test", grant_id="grant-test")
    return organ, {"daleobanks_root": str(root), "draft": str(tmp_path / "draft.txt")}, context


ARMED = {"kill_switch_armed": True, "platforms": ["x"], "results": {"x": {"post_id": "dry-1", "dry_run": True}},
         "ethics": {}, "critic": {}}


def test_the_founder_signed_daleobanks_grant_is_forwarded_exactly_and_never_minted(tmp_path, monkeypatch):
    organ, params, context = _stub(tmp_path, monkeypatch, {**ARMED, "publish_gated": [
        {"platform": "x", "reason": "content_outside_approved_intent", "capability_grant_id": "cg_7"}]})
    out = bridge.publish({**params, "daleobanks_grant": "cg_7", "draft_id": "draft-42"}, context)
    [request] = organ.requests
    assert request["daleobanks_grant"] == "cg_7" and request["draft_id"] == "draft-42"
    assert "LIVE" not in str(request)
    assert out["status"] == "BLOCKED_BY_DALEOBANKS" and "content_outside_approved_intent" in out["why"]
    assert "no DALEOBANKS grant reached" not in out["why"]          # a grant did reach it; its reason is the truth
    organ.requests.clear()
    bridge.publish(params, context)                                   # nothing signed: nothing forwarded
    assert "daleobanks_grant" not in organ.requests[0] and "draft_id" not in organ.requests[0]


@pytest.mark.parametrize("extra", [{"daleobanks_grant": "cg_7"}, {"draft_id": "d"},
                                   {"daleobanks_grant": "cg 7; rm", "draft_id": "d"},
                                   {"daleobanks_grant": 7, "draft_id": "d"}])
def test_a_half_or_malformed_daleobanks_grant_reference_is_refused_before_daleobanks_runs(tmp_path, monkeypatch,
                                                                                          extra):
    from greg.capabilities import CapabilityError
    organ, params, context = _stub(tmp_path, monkeypatch, ARMED)
    with pytest.raises(CapabilityError, match="go together"):
        bridge.publish({**params, **extra}, context)
    assert organ.requests == []


def test_armed_with_no_gate_recorded_says_credentials_not_the_rate_governor(tmp_path, monkeypatch):
    _, params, context = _stub(tmp_path, monkeypatch, {**ARMED, "publish_gated": []})
    out = bridge.publish(params, context)
    assert out["status"] == "BLOCKED_BY_DALEOBANKS" and "no gate recorded a refusal" in out["why"]
    assert "rate governor" not in out["why"]
