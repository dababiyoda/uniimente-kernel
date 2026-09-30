"""A process-replacement proof for an actual timed sandbox host, not Mac deployment."""
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import subprocess
import sys

import pytest

from egregore.goal_chase_demo import DEMO_KEY, T0
from egregore.goal_chase_host import inspect_or_tick
from egregore.goal_chase_sandbox import SyntheticFounder, goal, observation, open_sandbox
from policy.engine import Proposal


ROOT = Path(__file__).resolve().parents[2]


def _host(path, *, at):
    result = subprocess.run(
        [sys.executable, "-m", "egregore.goal_chase_host", str(path),
         "--mode", "once", "--at", at.isoformat()],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def test_host_wakes_registered_mission_once_across_processes_and_pauses(tmp_path):
    path = tmp_path / "sandbox.jsonl"
    founder = SyntheticFounder(DEMO_KEY)
    with open_sandbox(path, founder=founder, clock=lambda: T0) as chase:
        chase.register(founder.sign("GOAL", goal(now=T0), now=T0))
        chase.observe(observation(now=T0))

    first = _host(path, at=T0 + timedelta(minutes=5))
    assert first["host_status"] == "TICKED"
    assert first["metrics"]["decision_requests"] == 1
    assert first["metrics"]["real_verified_outcomes"] == 0
    assert first["decisions_needed"]
    same_slot = _host(path, at=T0 + timedelta(minutes=5, seconds=30))
    assert same_slot["trigger_id"] == first["trigger_id"]
    assert same_slot["ledger_head"] == first["ledger_head"]
    assert same_slot["new_event_ids"] == []

    pause = path.with_suffix(".jsonl.pause")
    pause.touch()
    paused = _host(path, at=T0 + timedelta(minutes=6))
    assert paused["host_status"] == "PAUSED"
    assert paused["trigger_id"] is None
    assert paused["ledger_head"] == first["ledger_head"]
    pause.unlink()
    resumed = _host(path, at=T0 + timedelta(minutes=6))
    assert resumed["trigger_id"] != first["trigger_id"]
    assert resumed["metrics"]["decision_requests"] == 1
    assert resumed["real_world_verified_outcomes"] == 0


def test_host_never_creates_a_mission_or_ticks_during_report(tmp_path):
    path = tmp_path / "missing.jsonl"
    with pytest.raises(FileNotFoundError):
        inspect_or_tick(path, now=T0)
    assert not path.exists()
    founder = SyntheticFounder(DEMO_KEY)
    with open_sandbox(path, founder=founder, clock=lambda: T0) as chase:
        chase.register(founder.sign("GOAL", goal(now=T0), now=T0))
    before = path.read_bytes()
    report = inspect_or_tick(path, now=T0, tick=False)
    assert report["host_status"] == "READ_ONLY"
    assert report["trigger_id"] is None
    assert path.read_bytes() == before


def test_host_refuses_invalid_clock_and_does_not_rewrite_ledger(tmp_path):
    path = tmp_path / "sandbox.jsonl"
    founder = SyntheticFounder(DEMO_KEY)
    with open_sandbox(path, founder=founder, clock=lambda: T0) as chase:
        chase.register(founder.sign("GOAL", goal(now=T0), now=T0))
    before = path.read_bytes()
    with pytest.raises(ValueError, match="time zone"):
        inspect_or_tick(path, now=T0.replace(tzinfo=None))
    assert path.read_bytes() == before


def test_synthetic_host_cannot_grant_a_different_effect_from_signed_action(tmp_path):
    founder = SyntheticFounder(DEMO_KEY)
    spec = goal(now=T0)
    signed = founder.sign("GOAL", spec, now=T0)
    with open_sandbox(tmp_path / "sandbox.jsonl", founder=founder, clock=lambda: T0) as chase:
        chase.register(signed)
        obs = observation(now=T0)
        chase.observe(obs)
        authorized = spec["actions"][0]
        scope = chase._scope(spec["goal_id"], authorized, obs)
        proposal = Proposal(
            actor=chase.actor, legal_principal="alfonso_lopez",
            action_class=authorized["action_class"], objective=spec["goal_id"],
            payload={"scope": scope, "simulation": True},
            target=authorized["target"], consequence_class=authorized["consequence_class"],
            evidence_confidence=1.0, evidence_refs=[], estimated_cost_usd=0,
            requested_capability=authorized["capability"],
            expected_outcome=authorized["expected_outcome"], proposal_id="sandbox:grant-test",
        )
        assert chase.grant_for(proposal, signed, None) is not None
        for changed in (
            replace(proposal, target="sandbox:different"),
            replace(proposal, requested_capability="prototype.simulate"),
            replace(proposal, action_class="spending_above_predefined_thresholds"),
            replace(proposal, estimated_cost_usd=1),
            replace(proposal, payload={"scope": scope, "simulation": False}),
        ):
            assert chase.grant_for(changed, signed, None) is None
