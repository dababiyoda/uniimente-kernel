"""Acceptance and hostile controls for the first Infinite Goal Chase brick.

All functions and founder interactions are synthetic. Subprocess exits are real;
external outcomes, actual founder attention and production identity are not.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from itertools import permutations
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

import pytest

from capabilities.genome import GenomeRegistry
from egregore.contracts import canonical_copy, digest, ContractError, IntegrityConflict
from egregore.goal_chase import CommunicationRouter, ROOT
from egregore.goal_chase_demo import DEMO_KEY, T0
from egregore.goal_chase_sandbox import (
    SyntheticFounder, open_sandbox, goal, action, observation, decision,
)


@pytest.fixture
def host(tmp_path):
    founder = SyntheticFounder(DEMO_KEY)
    time = [T0]
    @contextmanager
    def opened(**kw):
        with open_sandbox(tmp_path / "events.jsonl", founder=founder,
                          clock=lambda: time[0], **kw) as chase:
            yield chase
    return opened, founder, time


def start(chase, founder, *, spec=None, obs=None):
    spec = spec or goal(now=T0)
    chase.register(founder.sign("GOAL", spec, now=T0))
    chase.observe(obs or observation(spec["goal_id"], now=T0))
    chase.tick("begin")


def gate_executions(chase):
    return [r for r in chase.spine.ledger.by_type("event")
            if r.payload.get("type") == "action.executing"]


def assert_trace(chase, gid="sandbox:GOAL-001"):
    state = chase.goals[gid]
    assert state["status"] == "ACHIEVED"
    assert len(state["reconciled"]) == len(state["spec"]["actions"])
    events = [e for e in chase.events if e.payload["goal_id"] == gid]
    ancestry = chase.memory.ancestry(events[-1].event_id)
    assert len(ancestry) == len(events)
    assert ancestry[-1]["type"] == "goal.registered"
    assert {"goal.observed", "goal.action_selected", "goal.authority_resolved",
            "goal.action_started", "goal.candidate_evaluated", "goal.reconciled"} <= {e["type"] for e in ancestry}
    ledger = chase.spine.ledger
    for action in state["spec"]["actions"]:
        aid = action["action_id"]
        reconciled = state["reconciled"][aid]
        receipt = ledger.find(reconciled["receipt_hash"])
        outcome = ledger.find(reconciled["outcome_hash"])
        assert receipt.record_type == "receipt" and outcome.record_type == "outcome"
        assert outcome.payload["action_ref"] == receipt.payload["action_id"]
        assert receipt.payload["result"]["simulation"] is True
        assert receipt.payload["result"]["external_effects"] == 0
        assert receipt.payload["result"]["scope_digest"] == digest(action)
        witness = next(r for r in ledger.by_type("witness")
                       if r.payload["witness_id"] == receipt.payload["witness_id"])
        assert witness.payload["target"] == action["target"]
        assert witness.payload["capability"] == action["capability"]
        if state["started"][aid]["decision_ref"]:
            rid = state["started"][aid]["decision_ref"]
            approved = chase.decisions[rid]
            assert approved["body"]["answer"] == "APPROVE"
            assert approved["body"]["scope"]["action"] == action
            decision_event = next(e for e in events if e.type == "goal.decision_received")
            started = next(e for e in events if e.type == "goal.action_started" and e.payload["data"]["action_id"] == aid)
            assert events.index(decision_event) < events.index(started)
    cps = [r for r in ledger.by_type("workflow") if r.payload["workflow_id"] == "goal-chase:" + gid]
    assert cps[-1].payload["status"] == "completed"
    assert cps[-1].payload["cursor"] == len(state["spec"]["actions"])
    assert ledger.verify_chain()[0]


def test_path_a_internal_work_closes_without_founder(host):
    opened, founder, _ = host
    with opened() as chase:
        start(chase, founder, spec=goal(now=T0, actions=[action()]))
        assert_trace(chase)
        assert not chase.requests and not chase.router.messages
        assert len(gate_executions(chase)) == 1
        artifact = chase.goals["sandbox:GOAL-001"]["reconciled"]["sandbox:research"]["artifact"]
        assert artifact["rejected_source_ids"] == ["sandbox:stale-source"]


def test_path_b_persistent_boundary_approval_resume_and_duplicate(host):
    opened, founder, time = host
    with opened() as chase:
        start(chase, founder)
        assert len(gate_executions(chase)) == 1  # only research, never the reserved action
        assert len(chase.requests) == len(chase.router.messages) == 1
        before = chase.snapshot()
        request = chase.pending_messages()[0]
        assert request["what_has_already_been_done"] == ["sandbox:research"]
        assert request["budget_requested_cents"] == 43000
    time[0] += timedelta(minutes=5)
    with opened() as chase:
        assert chase.snapshot() == before
        chase.tick("quiet-after-restart")
        assert len(chase.requests) == 1 and not chase.router.messages
        env = founder.sign("DECISION", decision(request), now=time[0])
        chase.decide(env)
        chase.decide(env)
        chase.tick("resume")
        assert_trace(chase)
        assert len(gate_executions(chase)) == 2
        assert chase.metrics()["sandbox_intervention_minutes_per_verified_outcome"] == 2
        assert chase.metrics()["founder_intervention_minutes_per_verified_outcome"] is None
        assert chase.metrics()["time_waiting_on_founder_seconds"] == 300
        chase.tick("resume")
        chase.tick("quiet-completed")
        assert len(gate_executions(chase)) == 2


def test_path_c_capability_deficit_is_durable_and_not_an_escalation(host):
    opened, founder, _ = host
    with opened() as chase:
        start(chase, founder, spec=goal(now=T0, actions=[action(capability="not.implemented")]))
        assert not gate_executions(chase) and not chase.requests
        deficit = chase.snapshot()["sandbox:GOAL-001"]["deficits"][0]
        assert deficit["state"] == "NEEDED" and deficit["execution_authority"] == "none"
        assert deficit["search_order"] == ["FIND", "RECOMPOSE", "SPECIALIZE", "MUTATE", "INVENT"]
    with opened() as chase:
        chase.tick("quiet-deficit")
        assert len(chase.snapshot()["sandbox:GOAL-001"]["deficits"]) == 1
        assert chase.metrics()["sandbox_verified_outcomes"] == 0


def test_path_d_quiet_wait_emits_no_message_or_task(host):
    opened, founder, _ = host
    with opened() as chase:
        start(chase, founder, obs=observation(now=T0, usable=False))
        for i in range(5):
            chase.tick(f"quiet-{i}")
        assert chase.goals["sandbox:GOAL-001"]["status"] == "WAITING"
        assert not chase.requests and not gate_executions(chase)
        assert len(chase.ticks) == 6


@pytest.mark.parametrize("mutation", ["forged", "expired", "different_goal", "budget", "target", "capability", "max_uses", "model", "conditional", "modified", "future"])
def test_hostile_decisions_fail_before_reserved_execution(host, mutation):
    opened, founder, _ = host
    with opened() as chase:
        start(chase, founder)
        request = chase.pending_messages()[0]
        body = decision(request)
        now, expiry = T0, T0 + timedelta(minutes=20)
        if mutation == "different_goal": body["goal_id"] = "sandbox:other"
        if mutation == "budget": body["scope"]["action"]["cost_cents"] += 1
        if mutation == "target": body["scope"]["action"]["target"] = "sandbox:other"
        if mutation == "capability": body["scope"]["action"]["capability"] = "other.capability"
        if mutation == "max_uses": body["scope"]["max_uses"] = 2
        if mutation == "conditional": body["conditions"] = ["Only if an unknown condition holds"]
        if mutation == "modified": body["requested_modification"] = "widen budget"
        if mutation == "expired": now, expiry = T0 - timedelta(hours=1), T0 - timedelta(minutes=1)
        if mutation == "future": now = T0 + timedelta(minutes=1)
        env = founder.sign("DECISION", body, now=now, expires_at=expiry)
        if mutation == "forged": env["signature"] = "0" * 64
        if mutation == "model": env["founder_identity"] = "model:claims-alfonso-approved"
        with pytest.raises(Exception): chase.decide(env)
        chase.tick("after-attack")
        assert len(gate_executions(chase)) == 1
        assert not chase.decisions
        assert any(e.type == "goal.input_rejected" for e in chase.events)


def test_rejection_survives_restart_new_facts_and_repeated_ticks(host):
    opened, founder, time = host
    with opened() as chase:
        start(chase, founder)
        message = chase.pending_messages()[0]
        chase.decide(founder.sign("DECISION", decision(message, answer="REJECT"), now=T0))
    with opened() as chase:
        for i in range(4): chase.tick("denied-" + str(i))
        obs = observation(now=T0, oid="sandbox:new-facts")
        obs["payload"]["records"][0]["cost_cents"] = 42000
        chase.observe(obs)
        chase.tick("denied-new-facts")
        with pytest.raises(ContractError):
            chase.decide(founder.sign("DECISION", decision(message), now=T0))
        assert len(chase.requests) == 1 and len(gate_executions(chase)) == 1
        assert not chase.pending_messages()


@pytest.mark.parametrize("kind", ["MODEL_OUTPUT", "PREDICTION", "EXTERNAL_EVIDENCE", "VERIFIED_OUTCOME", "FOUNDER_STATEMENT"])
def test_reality_types_never_promote_to_sandbox_evidence(host, kind):
    opened, founder, _ = host
    with opened() as chase:
        chase.register(founder.sign("GOAL", goal(now=T0), now=T0))
        obs = observation(now=T0)
        obs["kind"] = kind
        with pytest.raises(ContractError): chase.observe(obs)
        chase.tick("no-accepted-evidence")
        assert not gate_executions(chase)
        assert chase.snapshot()["sandbox:GOAL-001"]["state"] == "NEEDS_EVIDENCE"


def test_stale_observation_and_expired_accepted_approval_block(host):
    opened, founder, time = host
    with opened() as chase:
        start(chase, founder)
        message = chase.pending_messages()[0]
        chase.decide(founder.sign("DECISION", decision(message), now=T0, expires_at=T0 + timedelta(seconds=20)))
        time[0] += timedelta(seconds=21)
        chase.tick("expired-accepted-decision")
        assert len(gate_executions(chase)) == 1
        time[0] += timedelta(hours=2)
        chase.tick("stale-source")
        assert len(gate_executions(chase)) == 1 and len(chase.requests) == 1


def test_fresh_material_observation_invalidates_old_approval(host):
    opened, founder, time = host
    with opened() as chase:
        start(chase, founder)
        old = chase.pending_messages()[0]
        time[0] += timedelta(seconds=1)
        chase.observe(observation(now=time[0], oid="sandbox:new"))
        with pytest.raises(ContractError):
            chase.decide(founder.sign("DECISION", decision(old), now=time[0]))
        chase.tick("material-change")
        assert len(chase.requests) == 2
        assert len(chase.pending_messages()) == 1
        assert len(gate_executions(chase)) == 1


@pytest.mark.parametrize("state", ["SUPERSEDED", "PROHIBITED", "ABANDONED_BY_FOUNDER", "DEFERRED"])
def test_founder_lifecycle_stops_pending_action(host, state):
    opened, founder, _ = host
    with opened() as chase:
        start(chase, founder)
        message = chase.pending_messages()[0]
        chase.lifecycle(founder.sign("LIFECYCLE", {"goal_id": message["goal_id"], "state": state, "reason": "explicit founder stop"}, now=T0))
        with pytest.raises(ContractError): chase.decide(founder.sign("DECISION", decision(message), now=T0))
        chase.tick("stopped")
        assert len(gate_executions(chase)) == 1 and not chase.pending_messages()


def test_conflicting_authenticated_founder_intent_is_preserved_and_blocks(host):
    opened, founder, _ = host
    with opened() as chase:
        start(chase, founder)
        conflicting = goal(now=T0)
        conflicting["statement"] = "A conflicting instruction without a supersession decision"
        with pytest.raises(IntegrityConflict): chase.register(founder.sign("GOAL", conflicting, now=T0))
        chase.tick("conflicted")
        assert len(gate_executions(chase)) == 1
        assert chase.goals["sandbox:GOAL-001"]["conflicted"]


def test_duplicate_observation_trigger_and_escalation_spam_suppressed(host):
    opened, founder, _ = host
    with opened() as chase:
        start(chase, founder)
        before = len(chase.events)
        chase.observe(observation(now=T0))
        chase.tick("begin")
        assert len(chase.events) == before
        for i in range(8): chase.tick("spam-" + str(i))
        assert len(chase.requests) == len(chase.deliveries) == len(gate_executions(chase)) == 1
        assert chase.metrics()["duplicate_suppressed"] == 8


@pytest.mark.parametrize("channel", ["sms", "voice", "email", "push", "https://provider.invalid"])
def test_external_channels_never_construct_or_call(channel):
    with pytest.raises(ContractError): CommunicationRouter(channel)
    with pytest.raises(ContractError): CommunicationRouter(external_effects=True)


def test_communication_unavailable_recovers_from_spine_without_duplicate(host):
    opened, founder, _ = host
    router = CommunicationRouter()
    router.available = False
    with opened(router=router) as chase:
        start(chase, founder)
        assert len(chase.requests) == 1 and not chase.deliveries
    with opened() as chase:
        chase.tick("transport-restored")
        assert len(chase.deliveries) == 1
        chase.tick("transport-quiet")
        assert len(chase.router.messages) == 1


def test_authority_does_not_create_missing_capability(host):
    opened, founder, _ = host
    with opened(genomes=GenomeRegistry()) as chase:
        start(chase, founder)
        assert not gate_executions(chase) and not chase.requests
        assert chase.goals["sandbox:GOAL-001"]["deficits"]


def test_capability_does_not_create_sovereignty(host):
    opened, founder, _ = host
    a = action()
    a["action_class"] = "expansion_of_uniimentes_own_sovereignty"
    spec = goal(now=T0, actions=[a])
    spec["prohibited_actions"] = []  # canonical absolute prohibition must still win
    with opened() as chase:
        start(chase, founder, spec=spec)
        assert not gate_executions(chase)
        assert any("absolutely prohibited" in e.payload["data"].get("reason", "") for e in chase.events)


def test_evaluator_not_given_to_candidate_and_lying_result_retained(host, monkeypatch):
    import egregore.goal_chase_sandbox as sandbox
    original = sandbox.run_sandbox_function
    received = []
    def lies(name, obs, act):
        received.append((name, canonical_copy(obs), canonical_copy(act)))
        result = original(name, obs, act)
        result["artifact"]["source_ids"] = ["sandbox:invented-source"]
        return result
    monkeypatch.setattr(sandbox, "run_sandbox_function", lies)
    opened, founder, _ = host
    with opened() as chase:
        start(chase, founder, spec=goal(now=T0, actions=[action()]))
        assert chase.goals["sandbox:GOAL-001"]["status"] == "FAILED"
        assert not chase.spine.ledger.by_type("outcome")
        rejected = [e for e in chase.events if e.type == "goal.candidate_evaluated"]
        assert rejected[0].payload["data"]["passed"] is False
        assert received[0][1] == observation(now=T0)
        assert set(received[0][2]) == set(action())
        assert DEMO_KEY.decode() not in json.dumps(received)


def test_model_and_network_unavailable_do_not_disable_control(host, monkeypatch):
    import socket
    def forbidden(*a, **kw): raise AssertionError("network or model access attempted")
    monkeypatch.setattr(socket, "socket", forbidden)
    opened, founder, _ = host
    with opened() as chase:
        start(chase, founder, spec=goal(now=T0, actions=[action()]))
        assert_trace(chase)


def test_single_writer_lock_refuses_a_second_session(host):
    opened, founder, _ = host
    with opened():
        with pytest.raises(ContractError):
            with opened(): pass


@pytest.mark.parametrize("damage", ["payload", "genesis", "duplicate_event", "partial_json"])
def test_corrupted_history_refuses_replay(host, tmp_path, damage):
    opened, founder, _ = host
    with opened() as chase: start(chase, founder)
    path = tmp_path / "events.jsonl"
    rows = [json.loads(l) for l in path.read_text().splitlines()]
    if damage == "payload": rows[-1]["payload"]["payload"]["data"]["active_goals"] = 999
    if damage == "genesis": rows[0]["payload"]["constitution_hash"] = "sha256:" + "0" * 64
    if damage in ("payload", "genesis"):
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    elif damage == "duplicate_event":
        from provenance.ledger import EvidenceLedger
        ledger = EvidenceLedger(rows[0]["payload"]["constitution_hash"], str(path))
        ledger.append("event", next(r["payload"] for r in rows if r["record_type"] == "event" and r["payload"].get("type") == "goal.registered"))
    else:
        with path.open("a") as f: f.write('{"partial":')
    with pytest.raises(Exception):
        with opened(): pass


def test_same_action_ids_are_scoped_to_each_goal(host):
    opened, founder, _ = host
    with opened() as chase:
        for i in (1, 2):
            gid = f"sandbox:GOAL-00{i}"
            chase.register(founder.sign("GOAL", goal(gid, now=T0, actions=[action()]), now=T0))
            chase.observe(observation(gid, now=T0, oid=f"sandbox:OBS-00{i}"))
        chase.tick("portfolio")
        assert len(gate_executions(chase)) == 2
        for gid in chase.goals: assert_trace(chase, gid)


@pytest.mark.parametrize("order", list(permutations(range(3))))
def test_source_order_cannot_change_verified_comparison(host, order):
    opened, founder, _ = host
    obs = observation(now=T0)
    obs["payload"]["records"] = [obs["payload"]["records"][i] for i in order]
    with opened() as chase:
        start(chase, founder, spec=goal(now=T0, actions=[action()]), obs=obs)
        assert_trace(chase)
        assert chase.goals["sandbox:GOAL-001"]["reconciled"]["sandbox:research"]["artifact"]["lowest_cost_cents"] == 43000


def test_frozen_evaluator_and_spec_match_preimplementation_seal():
    seal = json.loads((ROOT / "tests/fixtures/goal_chase_v0_seal.json").read_text())
    for path, expected in seal.items(): assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected


def test_fresh_process_pending_boundary_exact_replay_and_closure(tmp_path):
    path = tmp_path / "demo.jsonl"
    def run(phase, expected=None):
        output = tmp_path / (phase + ".json")
        cmd = [sys.executable, "-m", "egregore.goal_chase_demo", str(path), "--phase", phase, "--output", str(output)]
        if expected: cmd += ["--expected-snapshot-hash", expected]
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        return json.loads(output.read_text())
    before = run("begin")
    rebuilt = run("inspect", before["snapshot_hash"])
    assert rebuilt["snapshot"] == before["snapshot"]
    assert rebuilt["ledger_head"] == before["ledger_head"]
    after = run("approve", before["snapshot_hash"])
    assert after["snapshot"]["sandbox:GOAL-001"]["state"] == "ACHIEVED"
    assert after["metrics"]["founder_interruptions"] == 1
    assert after["metrics"]["unreconciled_actions"] == 0
    with open_sandbox(path, founder=SyntheticFounder(DEMO_KEY), clock=lambda: T0 + timedelta(minutes=5)) as chase:
        assert_trace(chase)
        assert len(gate_executions(chase)) == 2


@pytest.mark.parametrize("cut", ["pending", "after_receipt", "after_started"])
def test_real_abrupt_process_exit_at_transition(tmp_path, cut):
    path = tmp_path / "crash.jsonl"
    script = '''
import os, sys
from egregore.goal_chase_demo import T0, DEMO_KEY
from egregore.goal_chase_sandbox import *
f = SyntheticFounder(DEMO_KEY)
with open_sandbox(sys.argv[1], founder=f, clock=lambda:T0) as c:
    c.register(f.sign('GOAL',goal(now=T0),now=T0))
    c.observe(observation(now=T0))
    original = c.spine.ledger.append
    def append(kind,payload,**kw):
        record = original(kind,payload,**kw)
        cut=sys.argv[2]
        stop = (cut=='pending' and payload.get('type')=='goal.approval_requested')
        stop |= (cut=='after_receipt' and payload.get('type')=='goal.action_recorded')
        stop |= (cut=='after_started' and payload.get('type')=='goal.action_started')
        if stop: os._exit(73)
        return record
    c.spine.ledger.append = append
    c.tick('crash')
'''
    result = subprocess.run([sys.executable, "-c", script, str(path), cut], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 73, result.stderr
    founder = SyntheticFounder(DEMO_KEY)
    with open_sandbox(path, founder=founder, clock=lambda: T0) as chase:
        chase.tick("recover")
        if cut == "after_started":
            assert not gate_executions(chase)
            assert chase.metrics()["unreconciled_actions"] == 1
            assert not chase.requests
            assert any("RECONCILIATION_REQUIRED" in e.payload["data"].get("reason", "") for e in chase.events)
            return
        assert len(gate_executions(chase)) == 1
        assert len(chase.requests) == 1
        chase.decide(founder.sign("DECISION", decision(chase.pending_messages()[0]), now=T0))
        chase.tick("resume")
        assert_trace(chase)
        assert len(gate_executions(chase)) == 2
