"""organ.exchange / organ.status: the signed organ exchange as governed mission capabilities.

The refusal tests need no organ checkout. The live exchange runs real DALEOBANKS and
WealthMachineIntelligence code in their own interpreters and is skipped unless all four of
UNIIMENTE_DALEOBANKS_ROOT, UNIIMENTE_DALEOBANKS_PYTHON, UNIIMENTE_WEALTHMACHINE_ROOT and
UNIIMENTE_WEALTHMACHINE_PYTHON name them (CI: the one-machine workflow sets them).
"""
from __future__ import annotations

import os
from pathlib import Path

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
                   "verdict": None, "appraisals": 0}


def test_status_reads_only_this_missions_facts(tmp_path, journal, monkeypatch):
    monkeypatch.setenv(bt.SIGNING_KEY_ENV, "k" * 64)
    body = b'{"id": "p1"}'
    headers = bt.build_headers(body, identity="daleobanks", schema_version="1.1", idempotency_key="p1",
                               trace_id="trace-x")
    organ_bridge.record_exchange(journal, mission_id="m:other", headers=headers, body=body,
                                 nonce_cache=bt.NonceCache(), expected_sender="daleobanks",
                                 expected_operation="opportunity.evaluate")
    mine = organs.status({}, ctx(tmp_path, journal, capability="organ.status"))
    theirs = organs.status({}, ctx(tmp_path, journal, capability="organ.status", mission_id="m:other"))
    assert mine["messages"] == 0 and theirs["messages"] == 1 and theirs["transport_verified"] is True


def test_live_exchange_runs_real_organ_code_and_reproduces(tmp_path, journal):
    params = live_organs()
    out = organs.exchange({**params, "seed": SEED}, ctx(tmp_path, journal, roots=organ_roots(params)))
    assert out["appraisal_verdict"] == "REPRODUCED" and out["transport_verified"] is True
    assert out["assessment"]["requires_human_approval"] is True
    assert out["sender_identity_isolated"] is False          # pinned organs share one key: stated, not hidden
    assert out["external_effects"] is None and out["authority_created"] is False
    status = organs.status({}, ctx(tmp_path, journal, capability="organ.status"))
    assert status["organs_observed"] == ["daleobanks", "wealthmachine"] and status["verdict"] == "REPRODUCED"
    assert journal.replay("mission.observed") == [] and journal.replay("mission.appraised") == []
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
