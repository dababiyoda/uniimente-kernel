"""Founder-attention regression controls; all effects remain synthetic.

The original v0 evaluator is unchanged. These tests distinguish repeated intake
from changed decision evidence and keep freshness/approval limits independent.
"""
from datetime import timedelta

import pytest

from egregore.contracts import ContractError, IntegrityConflict, digest
from egregore.goal_chase import CommunicationRouter
from egregore.goal_chase_demo import T0
from egregore.goal_chase_sandbox import goal, observation, decision
from tests.integration.test_goal_chase import host, start, gate_executions, assert_trace


@pytest.mark.parametrize("change", ["id_only", "timestamp", "record_order"])
def test_unchanged_intake_keeps_one_question_and_exact_original_approval(host, change):
    opened, founder, time = host
    with opened() as chase:
        start(chase, founder)
        message = chase.pending_messages()[0]
        original = observation(now=T0)
        time[0] += timedelta(seconds=10)
        repeated = observation(now=T0 if change == "id_only" else time[0], oid="sandbox:repeated")
        if change == "record_order": repeated["payload"]["records"].reverse()
        chase.observe(repeated)
        chase.tick("same-facts")
        assert len(chase.requests) == len(chase.deliveries) == 1
        assert chase.pending_messages() == [message]
        assert chase.goals[message["goal_id"]]["observations"]["sources"] == original
        reaffirmed = [e for e in chase.events if e.type == "goal.observation_reconfirmed"]
        assert reaffirmed[0].payload["data"]["observation"] == repeated
        assert reaffirmed[0].payload["data"]["basis_digest"] == digest(original)
        before = len(chase.events)
        chase.observe(repeated)
        assert len(chase.events) == before
        chase.decide(founder.sign("DECISION", decision(message), now=time[0]))
        chase.tick("approved-original-scope")
        assert_trace(chase)
        assert len(gate_executions(chase)) == 2


@pytest.mark.parametrize("change", ["quote", "eligibility", "source_record", "negative_evidence"])
def test_changed_facts_still_require_a_new_exact_decision(host, change):
    opened, founder, time = host
    with opened() as chase:
        start(chase, founder)
        old = chase.pending_messages()[0]
        time[0] += timedelta(seconds=10)
        obs = observation(now=time[0], oid="sandbox:material-change")
        if change == "quote": obs["payload"]["records"][0]["cost_cents"] += 1
        if change == "eligibility": obs["payload"]["records"][0]["usable"] = False
        if change == "source_record": obs["payload"]["records"][0]["source_id"] = "sandbox:replacement-source"
        if change == "negative_evidence": obs["payload"]["records"][-1]["cost_cents"] += 1
        chase.observe(obs)
        with pytest.raises(ContractError):
            chase.decide(founder.sign("DECISION", decision(old), now=time[0]))
        chase.tick("changed-facts")
        assert len(chase.requests) == 2
        assert len(chase.pending_messages()) == 1
        assert len(gate_executions(chase)) == 1


def test_reconfirmation_cannot_extend_freshness_or_authority(host):
    opened, founder, time = host
    with opened() as chase:
        spec = goal(now=T0)
        spec["evidence_requirements"]["max_age_seconds"] = 60
        start(chase, founder, spec=spec)
        old = chase.pending_messages()[0]
        time[0] += timedelta(seconds=30)
        chase.observe(observation(now=time[0], oid="sandbox:repeat-before-expiry"))
        chase.tick("still-the-same-question")
        assert chase.pending_messages() == [old]
        time[0] += timedelta(seconds=31)
        chase.tick("basis-expired")
        assert not chase.pending_messages()
        assert chase.goals[old["goal_id"]]["status"] == "NEEDS_EVIDENCE"
        assert len(gate_executions(chase)) == 1
        # New intake after expiry may create a fresh question. Old approval
        # never transfers and expiry is not silently extended by suppression.
        chase.observe(observation(now=time[0], oid="sandbox:fresh-after-expiry"))
        chase.tick("fresh-evidence")
        assert len(chase.requests) == 2
        with pytest.raises(ContractError):
            chase.decide(founder.sign("DECISION", decision(old), now=time[0]))
        fresh = chase.pending_messages()[0]
        chase.decide(founder.sign("DECISION", decision(fresh), now=time[0]))
        chase.tick("approved-fresh-scope")
        assert_trace(chase)


def test_restart_preserves_question_and_observation_high_water_mark(host):
    opened, founder, time = host
    with opened() as chase:
        start(chase, founder)
        original = chase.pending_messages()[0]
        time[0] += timedelta(seconds=20)
        chase.observe(observation(now=time[0], oid="sandbox:repeat-newer"))
        chase.tick("reconfirmed")
        before = chase.snapshot()
    with opened() as chase:
        assert chase.snapshot() == before
        chase.tick("restart-quiet")
        assert chase.pending_messages() == [original]
        assert not chase.router.messages
        late = observation(now=T0 + timedelta(seconds=10), oid="sandbox:late-contradiction")
        late["payload"]["records"][0]["cost_cents"] = 1
        with pytest.raises(ContractError, match="older"):
            chase.observe(late)
        assert chase.pending_messages() == [original]
        assert any(e.type == "goal.input_rejected" for e in chase.events)
        chase.decide(founder.sign("DECISION", decision(original), now=time[0]))
        chase.tick("resume-after-restart")
        assert_trace(chase)


def test_observation_id_cannot_change_content_across_intake_variants(host):
    opened, founder, time = host
    with opened() as chase:
        start(chase, founder)
        time[0] += timedelta(seconds=1)
        collision = observation(now=time[0])  # ID already bound to original observation
        with pytest.raises(IntegrityConflict): chase.observe(collision)
        repeated = observation(now=time[0], oid="sandbox:reconfirmation")
        chase.observe(repeated)
        repeated["payload"]["records"][0]["cost_cents"] = 1
        with pytest.raises(IntegrityConflict): chase.observe(repeated)
        assert len(chase.requests) == 1


@pytest.mark.parametrize("damage", ["changed_facts", "duplicate_identity", "older_intake"])
def test_replayed_false_reconfirmation_fails_closed(host, damage):
    opened, founder, _ = host
    with opened() as chase:
        start(chase, founder)
        false = observation(now=T0, oid="sandbox:false-confirmation")
        if damage == "changed_facts": false["payload"]["records"][0]["cost_cents"] = 1
        if damage == "duplicate_identity": false["observation_id"] = observation(now=T0)["observation_id"]
        if damage == "older_intake":
            false = observation(now=T0 - timedelta(seconds=1), oid="sandbox:replayed-old")
        with pytest.raises(IntegrityConflict):
            chase._emit("observation_reconfirmed", false["observation_id"], false["goal_id"],
                        {"observation": false, "basis_digest": digest(observation(now=T0))})
    with pytest.raises(IntegrityConflict):
        with opened(): pass


def test_expired_question_is_not_delivered_when_transport_recovers(host):
    opened, founder, time = host
    channel = CommunicationRouter()
    channel.available = False
    with opened(router=channel) as chase:
        spec = goal(now=T0)
        spec["evidence_requirements"]["max_age_seconds"] = 7200
        start(chase, founder, spec=spec)
        assert len(chase.requests) == 1 and not chase.deliveries
        time[0] += timedelta(hours=1, seconds=1)  # goal/request expired; evidence still fresh
        channel.available = True
        chase.tick("transport-restored-after-expiry")
        assert not chase.pending_messages()
        assert not chase.deliveries and not channel.messages
        assert len(gate_executions(chase)) == 1
