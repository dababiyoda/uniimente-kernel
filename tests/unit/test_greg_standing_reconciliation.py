"""Proof-carrying standing reconciliation: the selected invention of docs/opus-maximus/INVENTION_LEDGER.md.

An interrupted dispatch is never retried blindly; the founder states whether it executed. A founder-signed
mission may carry ``standing_reconciliation: {"consequence_inert": true}``. Then, and only when the retained facts
prove the interrupted run could not have left a consequence (the script worker: no network, no credentials, no paid
route, writes only inside a private clone discarded before any retry; no completed evidence; at most two such
settlements per action), the engine records the proof and retries once. Anything else still asks the founder, and
the question says which conditions failed.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from greg import planner, routing, templates, workers
from greg import worker_isolation as isolation
from greg.body import Body, Layout
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.unit.test_greg_interface import GOOD, FakeModel, inventory
from tests.unit.test_greg_script_worker import SCRIPT
from tests.unit.test_greg_workers import make_repo

MANDATE = {"consequence_inert": True}


def _envelope():
    try:
        isolation._backend(require_bubblewrap=True)
    except isolation.WorkerIsolationError as exc:
        pytest.skip(f"the script worker needs the real envelope: {exc}")


@pytest.fixture(autouse=True)
def _no_host_ca_override(monkeypatch):
    for name in isolation._CERT_ENV:      # a host CA outside the supported roots refuses the envelope
        monkeypatch.delenv(name, raising=False)


def _strategy(provider="script", order="one-sub"):
    return {"action_id": "commission-worker", "capability": "worker.commission",
            "params": {"provider": provider, "order": order}, "cost_usd": 0.01}


def _proof(tmp_path, *, spec=None, strategy=None, capability="worker.commission", consequence="internal_write",
           prior=0, providers=None):
    return workers.inert_interruption_proof(
        spec={"standing_reconciliation": MANDATE} if spec is None else spec, strategy=strategy or _strategy(),
        capability_id=capability, consequence_class=consequence, mission_workspace=tmp_path, prior=prior,
        providers=providers)


# -- the pure proof ---------------------------------------------------------------------------------------------

def test_the_proof_holds_only_for_the_inert_script_worker_under_a_signed_mandate(tmp_path):
    proof = _proof(tmp_path)
    assert proof["holds"] and all(proof["predicates"].values())
    assert proof["evidence"]["provider_class"] == "ScriptWorker"
    assert proof["evidence"]["provider_guarantees"]["network"].startswith("network namespace closed")
    assert proof["evidence"]["workers_code_sha256"]


@pytest.mark.parametrize("change,unmet", [
    ({"spec": {}}, "founder_mandate"),
    ({"spec": {"standing_reconciliation": {"consequence_inert": "yes"}}}, "founder_mandate"),
    ({"capability": "fs.write"}, "worker_commission"),
    ({"consequence": "external_effect"}, "internal_consequence_only"),
    ({"strategy": _strategy(provider="codex")}, "provider_consequence_inert"),
    ({"strategy": _strategy(provider="claude-code")}, "provider_consequence_inert"),
    ({"strategy": _strategy(provider="nobody")}, "provider_consequence_inert"),
    ({"strategy": _strategy(order="../escape")}, "no_completed_evidence"),
    ({"prior": 2}, "within_limit"),
])
def test_each_condition_alone_withholds_the_settlement(tmp_path, change, unmet):
    proof = _proof(tmp_path, **change)
    assert not proof["holds"]
    assert [k for k, ok in proof["predicates"].items() if not ok] == [unmet]


@pytest.mark.parametrize("status,holds", [("COMPLETED", False), ("NO_CHANGE", False), ("FAILED", False),
                                          ("UNCERTAIN", True)])
def test_completed_evidence_means_it_executed_and_is_never_settled_as_not_executed(tmp_path, status, holds):
    root = tmp_path / "work-orders" / "one-sub"
    root.mkdir(parents=True)
    (root / "evidence.json").write_text(json.dumps({"status": status}))
    assert _proof(tmp_path)["holds"] is holds


def test_an_instance_attribute_cannot_make_a_provider_inert(tmp_path):
    impostor = workers.CliAgentWorker("impostor", ["true"], reviewed=True)
    impostor.CONSEQUENCE_INERT = True                   # the class, not the object, carries the guarantee
    proof = _proof(tmp_path, strategy=_strategy(provider="impostor"), providers={"impostor": impostor})
    assert not proof["predicates"]["provider_consequence_inert"]


def test_a_standing_reconciliation_counts_as_a_reconciliation_not_a_receipted_outcome():
    record = {"route": "standing_reconciliation", "receipt": None, "status": "RECONCILED_NOT_EXECUTED"}
    assert routing.founder_reconciled(record)
    assert not routing.founder_reconciled({**record, "receipt": "sha256:x"})


def test_a_model_drafted_proposal_never_carries_a_standing_mandate():
    draft = {**json.loads(json.dumps(GOOD)), "standing_reconciliation": MANDATE}
    ctx = planner.PlannerContext(read_roots=(), capabilities=inventory(), repositories={}, today="2026-09-26")
    proposal = planner.propose("Tell me if my kernel checkout gets dirty", ctx,
                               transport=FakeModel([json.dumps(draft)]))
    assert proposal["status"] == "PROPOSED", proposal
    assert "standing_reconciliation" not in proposal["spec"]


# -- on the mission path ----------------------------------------------------------------------------------------

def _crash_first(body, n=1):
    """The first ``n`` dispatches of worker.commission die mid-effect: the Gate keeps a claim and no receipt."""
    real, calls = body.registry.adapters["worker.commission"], []

    def adapter(params, ctx):
        calls.append(params)
        if len(calls) <= n:
            raise RuntimeError("power lost mid-effect")
        return real(params, ctx)
    body.registry.adapters["worker.commission"] = adapter
    return calls


def _run(tmp_path, *, mandate=True, provider="script", crashes=1, ticks=10):
    data = tmp_path / "data"
    data.mkdir()
    repo = make_repo(data)
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data])
    spec = templates.code_change(repo=str(repo), objective="add sub() with a founder-signed script", order="one-sub",
                                 provider=provider, allowed_paths=["pkg/*", "tests/*"], budget_usd=0.01,
                                 script=SCRIPT if provider == "script" else None,
                                 workspace_root=Layout(home).workspace)
    if mandate:
        spec["standing_reconciliation"] = dict(MANDATE)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        calls = _crash_first(body, crashes)
        for _ in range(ticks):
            body.tick()
            clock.advance(60)
        acts = [e.payload for e in body.journal.replay("mission.action")
                if e.payload["action_id"] == "commission-worker"]
        asks = [r for r in body.engine.book.open_requests() if r["kind"] == "RECONCILIATION"]
        m = body.engine.book.missions[spec["mission_id"]]
        achieved = bool(body.journal.replay("mission.achieved"))
        digest = m.command_digest
    return acts, asks, calls, achieved, digest, m


def test_with_the_mandate_an_inert_interruption_is_settled_with_its_proof_and_run_once(tmp_path):
    _envelope()
    acts, asks, calls, achieved, digest, m = _run(tmp_path)
    assert [a["status"] for a in acts] == ["UNCERTAIN", "RECONCILED_NOT_EXECUTED", "DONE"], acts
    assert not asks, "no founder question for a provably inert interruption"
    settled = acts[1]
    assert settled["route"] == "standing_reconciliation" and settled["receipt"] is None
    assert settled["mandate"] == digest and settled["proof"]["holds"]
    assert settled["attempt"] == acts[0]["attempt"] and acts[2]["attempt"] == acts[0]["attempt"] + 1
    assert len(calls) == 2, "the interrupted dispatch plus exactly one retry"
    assert m.spent_usd == pytest.approx(acts[2]["cost_usd"]), "the interrupted attempt's held cap was released"
    assert achieved


def test_without_the_mandate_the_founder_is_still_asked_and_nothing_reruns(tmp_path):
    _envelope()
    acts, asks, calls, _, _, _ = _run(tmp_path, mandate=False)
    assert [a["status"] for a in acts] == ["UNCERTAIN"]
    assert len(asks) == 1 and "standing mandate" not in asks[0]["why_now"]
    assert len(calls) == 1


def test_with_the_mandate_a_provider_that_could_reach_the_world_is_still_asked_and_told_why(tmp_path, monkeypatch):
    monkeypatch.setitem(workers.PROVIDERS, "local-cli", workers.CliAgentWorker("local-cli", ["true"], reviewed=True))
    acts, asks, calls, _, _, _ = _run(tmp_path, provider="local-cli")
    assert [a["status"] for a in acts] == ["UNCERTAIN"]
    assert len(asks) == 1 and "provider_consequence_inert" in asks[0]["why_now"]
    assert len(calls) == 1


def test_an_action_that_keeps_crashing_is_settled_twice_then_handed_to_the_founder(tmp_path):
    _envelope()
    acts, asks, calls, achieved, _, _ = _run(tmp_path, crashes=3, ticks=12)
    assert [a["status"] for a in acts] == ["UNCERTAIN", "RECONCILED_NOT_EXECUTED"] * 2 + ["UNCERTAIN"]
    assert len(asks) == 1 and "within_limit" in asks[0]["why_now"]
    assert len(calls) == 3 and not achieved
