"""organ.exchange / organ.status: the signed organ exchange as governed mission capabilities.

The refusal tests need no organ checkout. The live exchange runs real DALEOBANKS and
WealthMachineIntelligence code in their own interpreters and is skipped unless all four of
UNIIMENTE_DALEOBANKS_ROOT, UNIIMENTE_DALEOBANKS_PYTHON, UNIIMENTE_WEALTHMACHINE_ROOT and
UNIIMENTE_WEALTHMACHINE_PYTHON name them (CI: the one-machine workflow sets them).
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest

from adapters import bridge_transport as bt
from events.spine import EventSpine
from greg import organ_bridge, organs
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext
from greg.journal import Journal
from provenance.ledger import EvidenceLedger

ORGAN_ENV = ("UNIIMENTE_DALEOBANKS_ROOT", "UNIIMENTE_DALEOBANKS_PYTHON", "UNIIMENTE_WEALTHMACHINE_ROOT",
             "UNIIMENTE_WEALTHMACHINE_PYTHON")
SEED = ("Financial independence is not selfish. It is protection from systems that profit from dependency. "
        "Maybe a budgeting checklist or workshop could help people start.")


def live_organs():
    if not all(os.environ.get(k) for k in ORGAN_ENV):
        why = "organ checkouts not configured (" + ", ".join(ORGAN_ENV) + ")"
        if os.environ.get("UNIIMENTE_REQUIRE_ORGANS") == "1":   # the CI gate: a skip would be a silent pass
            pytest.fail(why)
        pytest.skip(why)
    return {"daleobanks_root": os.environ["UNIIMENTE_DALEOBANKS_ROOT"],
            "daleobanks_python": os.environ["UNIIMENTE_DALEOBANKS_PYTHON"],
            "wealthmachine_root": os.environ["UNIIMENTE_WEALTHMACHINE_ROOT"],
            "wealthmachine_python": os.environ["UNIIMENTE_WEALTHMACHINE_PYTHON"]}


def organ_roots(params: dict) -> tuple:
    """Read roots covering the organ checkouts and their interpreters' directories."""
    return tuple(Path(params[k]).resolve() for k in ("daleobanks_root", "wealthmachine_root")) + \
        tuple(Path(params[k]).parent for k in ("daleobanks_python", "wealthmachine_python"))


@pytest.fixture
def journal(tmp_path):
    return Journal(EventSpine(EvidenceLedger("sha256:" + "1" * 64, path=str(tmp_path / "l.jsonl"))),
                   actor="spiffe://uniimente.internal/test/organs")


def ctx(tmp_path, journal, *, roots=(), mission_id="m:organ-test", capability="organ.exchange"):
    manifest, _ = BUILTINS[capability]
    return InvocationContext(workspace=tmp_path / "w", read_roots=tuple(Path(r) for r in roots), secrets=None,
                             manifest=manifest, journal=journal, mission_id=mission_id)


def fake_checkouts(tmp_path):
    dale, wmi = tmp_path / "dale", tmp_path / "wmi"
    (dale / "services").mkdir(parents=True)
    (dale / "services" / "idea_refinery.py").write_text("")
    (wmi / "src" / "services").mkdir(parents=True)
    (wmi / "src" / "services" / "opportunity_intake.py").write_text("")
    return {"daleobanks_root": str(dale), "wealthmachine_root": str(wmi),
            "daleobanks_python": "/usr/bin/python3", "wealthmachine_python": "/usr/bin/python3", "seed": SEED}


def test_manifests_are_registered_and_bounded():
    exchange, _ = BUILTINS["organ.exchange"]
    status, _ = BUILTINS["organ.status"]
    assert exchange.consequence_class == "internal_write" and exchange.target_prefix == "organ:"
    assert exchange.network == "none" and exchange.filesystem == "workspace-write"
    assert status.consequence_class == "read_only" and status.retry_safe


@pytest.mark.parametrize("change, why", [
    ({"seed": ""}, "seed"), ({"seed": "x" * 2001}, "seed"),
    ({"daleobanks_root": "/etc"}, "outside permitted roots"),
    ({"daleobanks_python": "python3"}, "absolute"),
])
def test_exchange_refuses_out_of_scope_or_malformed_requests(tmp_path, journal, change, why):
    params = fake_checkouts(tmp_path)
    with pytest.raises(CapabilityError, match=why):
        organs.exchange({**params, **change}, ctx(tmp_path, journal, roots=(tmp_path, Path("/usr/bin"))))


def test_interpreter_outside_read_roots_is_refused(tmp_path, journal):
    with pytest.raises(CapabilityError, match="outside permitted roots"):
        organs.exchange(fake_checkouts(tmp_path), ctx(tmp_path, journal, roots=(tmp_path,)))


def test_exchange_belongs_to_one_mission(tmp_path, journal):
    with pytest.raises(CapabilityError, match="one mission"):
        organs.exchange(fake_checkouts(tmp_path), ctx(tmp_path, journal, roots=(tmp_path,), mission_id=""))


def test_trace_is_stable_per_mission_and_seed():
    assert organs.trace_for("m:a", "s") == organs.trace_for("m:a", "s") != organs.trace_for("m:b", "s")


def test_status_reports_nothing_before_any_exchange(tmp_path, journal):
    out = organs.status({}, ctx(tmp_path, journal, capability="organ.status"))
    assert out == {"organs_observed": [], "messages": 0, "transport_verified": False, "trace_ids": [],
                   "verdict": None, "appraisals": 0, "bound_to_receipts": [], "founder_reconciled": False,
                   "unbound_facts_ignored": 0}


def register(journal, mission_id):
    journal.record("mission.registered", {"mission_id": mission_id, "spec": {"strategies": [
        {"action_id": "organs", "capability": "organ.exchange"}]}}, key=[mission_id, "registered"])


def finish(journal, mission_id, output=None, *, status="DONE", reconciled=False):
    """What the engine records after the Gate: a DONE action and its receipt (or a founder reconciliation)."""
    receipt = None if reconciled else journal.ledger.append("receipt", {"result": {"output": output}}).hash
    journal.record("mission.action", {"mission_id": mission_id, "action_id": "organs", "status": status,
                                      "receipt": receipt, "route": "founder_reconciliation" if reconciled else None},
                   key=[mission_id, "organs", status, receipt or "reconciled"])


def bridge_message(journal, mission_id, body=b'{"id": "p1"}'):
    headers = bt.build_headers(body, identity="daleobanks", schema_version="1.1", idempotency_key="p1",
                               trace_id="trace-" + mission_id)
    return organ_bridge.record_exchange(journal, mission_id=mission_id, headers=headers, body=body,
                                        nonce_cache=bt.NonceCache(), expected_sender="daleobanks",
                                        expected_operation="opportunity.evaluate")


def test_status_reads_only_this_missions_facts(tmp_path, journal, monkeypatch):
    monkeypatch.setenv(bt.SIGNING_KEY_ENV, "k" * 64)
    register(journal, "m:other")
    seen = bridge_message(journal, "m:other")
    finish(journal, "m:other", {"packet_sha256": seen["content_sha256"], "assessment_sha256": "a" * 64})
    mine = organs.status({}, ctx(tmp_path, journal, capability="organ.status"))
    theirs = organs.status({}, ctx(tmp_path, journal, capability="organ.status", mission_id="m:other"))
    assert mine["messages"] == 0 and theirs["messages"] == 1 and theirs["transport_verified"] is True


def test_facts_from_an_exchange_that_never_completed_do_not_count(tmp_path, journal, monkeypatch):
    """Attack (review finding): the body dies after the adapter recorded organ facts and a REPRODUCED
    appraisal but before the Gate's receipt; the founder reconciles the dispatch as not executed.
    Those facts must not satisfy organ.status or the sandbox metric."""
    monkeypatch.setenv(bt.SIGNING_KEY_ENV, "k" * 64)
    mid = "m:organ-test"
    register(journal, mid)
    seen = bridge_message(journal, mid)
    judged = {"trace_id": "t", "packet_sha256": seen["content_sha256"], "assessment_sha256": "a" * 64,
              "redo_sha256": "r" * 64}
    organ_bridge.record_appraisal(journal, mission_id=mid, appraiser="kernel-organ-appraiser",
                                  reproduced={"go_no_go": True}, invariants={"x": True}, exchange=judged)
    finish(journal, mid, status="RECONCILED_NOT_EXECUTED", reconciled=True)
    out = organs.status({}, ctx(tmp_path, journal, capability="organ.status"))
    assert out["verdict"] is None and out["messages"] == 0 and out["unbound_facts_ignored"] == 2
    finish(journal, mid, {"packet_sha256": seen["content_sha256"], "assessment_sha256": "a" * 64})
    out = organs.status({}, ctx(tmp_path, journal, capability="organ.status"))
    assert out["verdict"] == "REPRODUCED" and out["messages"] == 1 and len(out["bound_to_receipts"]) == 1


def test_a_founder_reconciled_executed_dispatch_vouches_for_its_facts(tmp_path, journal, monkeypatch):
    monkeypatch.setenv(bt.SIGNING_KEY_ENV, "k" * 64)
    mid = "m:organ-test"
    register(journal, mid)
    bridge_message(journal, mid)
    finish(journal, mid, reconciled=True)          # the founder said it executed: the founder's authority
    out = organs.status({}, ctx(tmp_path, journal, capability="organ.status"))
    assert out["messages"] == 1 and out["founder_reconciled"] is True


def test_appraisals_of_different_exchanges_never_collapse(journal):
    """A REFUTED, a REPRODUCED and a differing REFUTED are three facts, each naming its exchange."""
    mid = "m:organ-test"
    verdicts = []
    for i, ok in enumerate((False, True, False)):
        judged = {"trace_id": "t", "packet_sha256": f"{i}" * 64, "assessment_sha256": "a" * 64,
                  "redo_sha256": "r" * 64}
        verdicts.append(organ_bridge.record_appraisal(journal, mission_id=mid, appraiser="k",
                                                      reproduced={"go_no_go": ok}, invariants={}, exchange=judged))
    recorded = [e.payload for e in journal.replay("organ.appraised")]
    assert [r["verdict"] for r in recorded] == ["REFUTED", "REPRODUCED", "REFUTED"]
    assert all(r["exchange"]["packet_sha256"] for r in recorded)


def git_checkouts(tmp_path):
    """fake_checkouts committed to git, so the exchange can snapshot each organ's HEAD."""
    params = fake_checkouts(tmp_path)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "GIT_CONFIG_NOSYSTEM": "1"}
    for root in (params["daleobanks_root"], params["wealthmachine_root"]):
        for cmd in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "c"]):
            subprocess.run(["git", "-C", root, *cmd], check=True, capture_output=True, env=env)
    return params


def message(trace, identity="daleobanks"):
    return {"body": '{"id": "p1"}', "headers": {bt.H_TRACE: trace, "X-Schema-Version": "1.1", "identity": identity}}


def test_an_organ_that_rewrites_the_other_organs_code_is_refused(tmp_path, journal, monkeypatch):
    """Attack (review finding): organ processes share the body's UID and filesystem, so the DALEOBANKS
    stage rewrites WealthMachine's code and both WealthMachine runs would execute it, making
    REPRODUCED meaningless. Expected: the WealthMachine snapshot digest no longer matches; refused
    before WealthMachine runs and before anything is recorded."""
    params = git_checkouts(tmp_path)
    calls = []

    def stage(python, cwd, code, *args, stdin=None, env, timeout):
        calls.append(cwd.name)
        (cwd.parent / "wealthmachine" / "src" / "services" / "opportunity_intake.py").write_text("FORGED = 1\n")
        return message(organs.trace_for("m:organ-test", SEED))

    monkeypatch.setattr(organs, "_stage", stage)
    with pytest.raises(CapabilityError, match="snapshot changed while DALEOBANKS ran"):
        organs.exchange(params, ctx(tmp_path, journal, roots=(tmp_path, Path("/usr/bin"))))
    assert calls == ["daleobanks"] and journal.replay("organ.") == []
    assert (Path(params["wealthmachine_root"]) / "src/services/opportunity_intake.py").read_text() == ""


def test_an_organ_that_signs_another_trace_is_refused_before_recording(tmp_path, journal, monkeypatch):
    params = git_checkouts(tmp_path)
    monkeypatch.setattr(organs, "_stage", lambda *a, **k: message("trace-elsewhere"))
    with pytest.raises(CapabilityError, match="not the assigned"):
        organs.exchange(params, ctx(tmp_path, journal, roots=(tmp_path, Path("/usr/bin"))))
    assert journal.replay("organ.") == []


def test_the_snapshot_runs_head_and_reports_uncommitted_edits(tmp_path):
    params = git_checkouts(tmp_path)
    wmi = Path(params["wealthmachine_root"])
    (wmi / "src/services/opportunity_intake.py").write_text("UNCOMMITTED = 1\n")
    snap = organs._snapshot(wmi, tmp_path / "snap")
    assert snap["uncommitted_changes_ignored"] is True
    assert (snap["path"] / "src/services/opportunity_intake.py").read_text() == ""
    assert snap["head"] == organs._head(wmi)


def test_live_exchange_runs_real_organ_code_and_reproduces(tmp_path, journal):
    params = live_organs()
    out = organs.exchange({**params, "seed": SEED}, ctx(tmp_path, journal, roots=organ_roots(params)))
    assert out["appraisal_verdict"] == "REPRODUCED" and out["transport_verified"] is True
    assert out["assessment"]["requires_human_approval"] is True
    assert out["sender_identity_isolated"] is False          # pinned organs share one key: stated, not hidden
    assert out["external_effects"] is None and out["authority_created"] is False
    status = organs.status({}, ctx(tmp_path, journal, capability="organ.status"))
    assert status["verdict"] is None and status["unbound_facts_ignored"] == 3   # no receipt vouches yet
    register(journal, "m:organ-test")
    finish(journal, "m:organ-test", out)
    status = organs.status({}, ctx(tmp_path, journal, capability="organ.status"))
    assert status["organs_observed"] == ["daleobanks", "wealthmachine"] and status["verdict"] == "REPRODUCED"
    assert journal.replay("mission.observed") == [] and journal.replay("mission.appraised") == []
    for organ in ("daleobanks", "wealthmachine"):          # the code that ran is the code recorded
        assert out["organ_code"][organ]["head"] == out["organ_heads"][organ]
        assert len(out["organ_code"][organ]["tree_sha256"]) == 64
    for root in ("daleobanks_root", "wealthmachine_root"):    # the organ checkouts are never written
        import subprocess
        dirty = subprocess.run(["git", "-C", params[root], "status", "--porcelain"], capture_output=True,
                               text=True).stdout
        assert dirty == ""


def test_a_seed_with_no_opportunity_is_a_truthful_refusal(tmp_path, journal):
    params = live_organs()
    with pytest.raises(CapabilityError, match="no opportunity"):
        organs.exchange({**params, "seed": "The weather was pleasant today."},
                        ctx(tmp_path, journal, roots=organ_roots(params)))
    assert journal.replay("organ.observed") == []
