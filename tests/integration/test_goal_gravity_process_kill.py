"""Section-25 scenario 9 across a real process boundary.

A child process authorizes a goal and dispatches its move through the Consequence Gate; the
executor SIGKILLs the child after the Gate's durable dispatch claim and before any result. The
parent then reopens the same JSONL ledger in a new process image and proves: the goal survived,
the move is never re-dispatched blindly, reconciliation reports it unresolved until an
accountable resolution with evidence exists, and a later re-dispatch is a distinguishable,
attempt-numbered Gate record. No scheduler is involved; the test drives both processes.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import textwrap

import pytest

from compiler.ucl_compiler import compile_constitution
from egregore.gravity import GoalGravityLoop
from egregore.resources import ResourceGovernor
from identity.machine_passport import PassportRegistry
from policy.consequence_gate import ConsequenceGate
from provenance.commit_witness import WitnessSigner
from provenance.ledger import EvidenceLedger

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CHILD = textwrap.dedent('''
    import os, signal, sys
    sys.path.insert(0, {root!r})
    from capabilities.genome import GenomeRegistry
    from compiler.ucl_compiler import compile_constitution
    from egregore.gravity import GoalGravityLoop
    from egregore.resources import ResourceGovernor
    from identity.machine_passport import PassportRegistry
    from policy.consequence_gate import ConsequenceGate
    from provenance.commit_witness import WitnessSigner
    from provenance.ledger import EvidenceLedger
    from tests.unit.test_goal_gravity import brief_move, robotics_goal, signal as make_signal, obs

    compiled = compile_constitution({root!r})
    passports = PassportRegistry()
    ledger = EvidenceLedger(compiled.constitution_hash, path={path!r})
    gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger, signer=WitnessSigner(env="development"))
    actor = passports.issue(kind="agent", creator="alfonso", owner_organ="uniimente-kernel", legal_principal="alfonso_lopez",
                            declared_capabilities=["research.brief", "outreach.contact"], budget_ceiling_usd=5.0,
                            consequence_class="external_contact")
    loop = GoalGravityLoop(ledger=ledger, compiled=compiled, passports=passports, actor=actor.passport_id,
                           legal_principal="alfonso_lopez", genomes=GenomeRegistry())
    spec = robotics_goal(second_node=False)
    goal_id = loop.registry.authorize(spec, now="2026-10-13T12:00:00Z")
    proposal = loop.classifier.proposal_for(spec, brief_move(), evidence_refs=["x"], evidence_confidence=0.9)
    grant = gate.grants.issue_single_action(proposal=proposal, policy_version="1.0.0")
    print("GOAL", goal_id, flush=True)

    def die(_proposal):
        os.kill(os.getpid(), signal.SIGKILL)   # the effect may have happened; nothing after this is written

    loop.turn(trigger_id="child-1", now="2026-10-13T13:00:00Z", resources=ResourceGovernor(max_model_calls=10, max_estimated_cost_usd=1.0),
              gate=gate, executor=die, grants={{"research.brief": grant}}, evidence_confidence=0.9,
              signals=[make_signal("e1", domain="hardware", tags=["robotics"], observations=[obs("actuator", "cost_usd", 420)])])
    print("UNREACHABLE", flush=True)
''')


def _parent_stack(path):
    compiled = compile_constitution(ROOT)
    passports = PassportRegistry()
    ledger = EvidenceLedger(compiled.constitution_hash, path=path)
    gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger, signer=WitnessSigner(env="development"))
    actor = passports.issue(kind="agent", creator="alfonso", owner_organ="uniimente-kernel", legal_principal="alfonso_lopez",
                            declared_capabilities=["research.brief", "outreach.contact"], budget_ceiling_usd=5.0,
                            consequence_class="external_contact")
    from capabilities.genome import GenomeRegistry
    loop = GoalGravityLoop(ledger=ledger, compiled=compiled, passports=passports, actor=actor.passport_id,
                           legal_principal="alfonso_lopez", genomes=GenomeRegistry())
    return ledger, gate, loop


@pytest.mark.skipif(not hasattr(signal, "SIGKILL"), reason="needs POSIX SIGKILL")
def test_sigkill_after_gate_dispatch_is_never_redispatched_across_processes():
    from tests.unit.test_goal_gravity import GOOD, brief_move, robotics_goal
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "ledger.jsonl")
        child = subprocess.run([sys.executable, "-c", CHILD.format(root=ROOT, path=path)], cwd=ROOT,
                               capture_output=True, text=True, timeout=120)
        assert child.returncode == -signal.SIGKILL, (child.returncode, child.stdout, child.stderr[-2000:])
        assert "UNREACHABLE" not in child.stdout
        goal_id = child.stdout.split("GOAL", 1)[1].split()[0]

        ledger, gate, loop = _parent_stack(path)
        ok, msg = ledger.verify_chain()
        assert ok, msg
        # The goal and its open attempt survived the process death.
        assert goal_id in loop.registry.goals()
        spec = loop.registry.get(goal_id)
        route = brief_move().route_hash
        states = [r.payload["evidence_state"] for r in ledger.by_type(loop.INTERVENTION_RECORD)
                  if r.payload["goal_id"] == goal_id and r.payload["intervention"]["route_hash"] == route]
        assert states[-1] == "attempted"
        claims = [r.payload for r in ledger.by_type("grant_dispatch")]
        assert len(claims) == 1 and claims[0]["proposal_id"].endswith(route[:23])
        assert [r.payload["type"] for r in ledger.by_type("event") if r.payload.get("type", "").startswith("action.")][-1] == "action.executing"

        # A new process with a fresh grant never re-dispatches the open route.
        calls = []
        proposal = loop.classifier.proposal_for(spec, brief_move(), evidence_refs=["x"], evidence_confidence=0.9)
        fresh = gate.grants.issue_single_action(proposal=proposal, policy_version="1.0.0")
        loop.registry.wake(goal_id, reason="restart", now="2026-10-14T13:00:00Z")
        turn = loop.turn(trigger_id="parent-1", now="2026-10-14T13:00:00Z",
                         resources=ResourceGovernor(max_model_calls=10, max_estimated_cost_usd=1.0), gate=gate,
                         executor=lambda p: calls.append(p) or GOOD(p), grants={"research.brief": fresh}, evidence_confidence=0.9)
        assert calls == []
        assert turn.processed[0]["decisions"][0]["note"] == "already attempted; no duplicate consequential action"
        assert any("reconciliation" in b for b in loop.registry.state(goal_id).blockers)

        # The Gate left it at executing: unresolved until an accountable resolution with evidence.
        first = loop.reconcile(goal_id, now="2026-10-14T14:00:00Z")
        assert first["unresolved"] == [route]
        second = loop.reconcile(goal_id, now="2026-10-14T15:00:00Z", resolutions={route: {
            "state": "failed", "reconciled_by": "ops:alfonso_lopez", "evidence_refs": ["incident:child-sigkill"],
            "note": "brief output directory empty after the crash; nothing was produced"}})
        assert second["resolved"][0]["to"] == "failed"

        # Only now may the route run again, once, under an attempt-numbered proposal id.
        proposal_r1 = loop.classifier.proposal_for(spec, brief_move(), evidence_refs=["x"], evidence_confidence=0.9, attempt=1)
        grant_r1 = gate.grants.issue_single_action(proposal=proposal_r1, policy_version="1.0.0")
        loop.registry.wake(goal_id, reason="retry after reconciliation", now="2026-10-14T16:00:00Z")
        again = loop.turn(trigger_id="parent-2", now="2026-10-14T16:00:00Z",
                          resources=ResourceGovernor(max_model_calls=10, max_estimated_cost_usd=1.0), gate=gate,
                          executor=lambda p: calls.append(p) or GOOD(p), grants={"research.brief": grant_r1}, evidence_confidence=0.9)
        assert len(calls) == 1 and calls[0].proposal_id.endswith(":r1")
        assert again.executed[0]["evidence_state"] == "executed"
        ok, msg = ledger.verify_chain()
        assert ok, msg
        ledger.close()


CHILD_BEFORE_GATE = CHILD.replace(
    "def die(_proposal):\n    os.kill(os.getpid(), signal.SIGKILL)   # the effect may have happened; nothing after this is written\n",
    "def die(_proposal):\n    raise AssertionError('the executor must never be reached in this scenario')\n"
    "def killed_before_gate(*args, **kwargs):\n    os.kill(os.getpid(), signal.SIGKILL)   # after the durable attempted record, before the Gate\n"
    "gate.run = killed_before_gate\n")


@pytest.mark.skipif(not hasattr(signal, "SIGKILL"), reason="needs POSIX SIGKILL")
def test_sigkill_between_the_attempted_record_and_the_gate_leaves_an_open_attempt_and_no_gate_trace():
    from tests.unit.test_goal_gravity import GOOD, brief_move
    assert CHILD_BEFORE_GATE != CHILD
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "ledger.jsonl")
        child = subprocess.run([sys.executable, "-c", CHILD_BEFORE_GATE.format(root=ROOT, path=path)], cwd=ROOT,
                               capture_output=True, text=True, timeout=120)
        assert child.returncode == -signal.SIGKILL, (child.returncode, child.stderr[-2000:])
        goal_id = child.stdout.split("GOAL", 1)[1].split()[0]
        ledger, gate, loop = _parent_stack(path)
        route = brief_move().route_hash
        states = [r.payload["evidence_state"] for r in ledger.by_type(loop.INTERVENTION_RECORD)
                  if r.payload["goal_id"] == goal_id and r.payload["intervention"]["route_hash"] == route]
        assert states[-1] == "attempted"
        assert ledger.by_type("grant_dispatch") == []
        assert not [r for r in ledger.by_type("event") if str(r.payload.get("type", "")).startswith("action.")]
        calls = []
        spec = loop.registry.get(goal_id)
        fresh = gate.grants.issue_single_action(
            proposal=loop.classifier.proposal_for(spec, brief_move(), evidence_refs=["x"], evidence_confidence=0.9),
            policy_version="1.0.0")
        loop.registry.wake(goal_id, reason="restart", now="2026-10-14T13:00:00Z")
        loop.turn(trigger_id="parent-1", now="2026-10-14T13:00:00Z",
                  resources=ResourceGovernor(max_model_calls=10, max_estimated_cost_usd=1.0), gate=gate,
                  executor=lambda p: calls.append(p) or GOOD(p), grants={"research.brief": fresh}, evidence_confidence=0.9)
        assert calls == []   # an attempt with no Gate trace is still never re-dispatched blindly
        assert loop.reconcile(goal_id, now="2026-10-14T14:00:00Z")["unresolved"] == [route]
        ledger.close()


def test_a_torn_ledger_tail_refuses_to_open_a_known_liveness_gap_recorded_as_negative_evidence():
    """Fail-closed today: a partially written last line makes the ledger refuse to open. That protects
    history but stops the body; any repair procedure must quarantine a copy of the original first.
    This test characterizes current behaviour; it is not a claim that the behaviour is sufficient."""
    compiled = compile_constitution(ROOT)
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "ledger.jsonl")
        ledger = EvidenceLedger(compiled.constitution_hash, path=path)
        ledger.append("event", {"type": "probe", "n": 1})
        ledger.close()
        with open(path, "a", encoding="utf-8") as fh:
            fh.write('{"seq": 2, "partial')   # a crash mid-append
        with pytest.raises(Exception):
            EvidenceLedger(compiled.constitution_hash, path=path)
