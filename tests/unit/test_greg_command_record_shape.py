"""A ``command.accepted`` keeps the founder's signed body once, inside its envelope (2026-10-23).

Before, each record also carried a top-level ``body`` copy beside the envelope, which itself holds the body, so a
large signed MISSION was stored once more than needed. New records carry only the envelope; records already
written keep both fields and are never rewritten. Both shapes must replay, verify and appraise alike: the founder's
signature is re-verified from the retained envelope's own bytes in either case."""
from __future__ import annotations

import json

import pytest

from greg import goal_gravity as gg
from greg import metrics
from greg.body import Body
from greg.founder import FOUNDER_TIER_BODY, accepted_body
from greg.journal import Journal
from tests.greg_fixtures import Clock, make_body, mission, note_check, signed, workspace, write_strategy


def _old_writer(monkeypatch):
    """Record every acceptance exactly as Body.apply wrote it before 2026-10-23: ``body`` beside ``envelope``."""
    record = Journal.record

    def old_shape(self, kind, data, **kw):
        if kind == "command.accepted" and isinstance(data.get("envelope"), dict) and "body" not in data:
            data = {**{k: v for k, v in data.items() if k not in ("envelope", "channel", "result")},
                    "body": data["envelope"]["body"], "envelope": data["envelope"], "channel": data["channel"],
                    "result": data["result"]}
        return record(self, kind, data, **kw)
    monkeypatch.setattr(Journal, "record", old_shape)


@pytest.mark.parametrize("shape", ["new", "old"])
def test_either_record_shape_replays_verifies_and_appraises(tmp_path, monkeypatch, shape):
    if shape == "old":
        _old_writer(monkeypatch)
    home, key, body_id, _ = make_body(tmp_path)
    mid = f"m:shape-{shape}"
    check = note_check("written", workspace(home, mid) / "effect.txt", "done")
    spec = mission(mid, checks=[check], strategies=[write_strategy("effect", "effect.txt", "done", ["written"])],
                   capabilities=["fs.read", "fs.write"])
    clock = Clock()
    tier = signed(key, body_id, "FOUNDER_TIER", dict(FOUNDER_TIER_BODY))
    command = signed(key, body_id, "MISSION", spec)
    with Body(home, clock=clock) as body:
        body.boot()
        assert body.apply(tier, channel="inbox")["status"] == "APPLIED"
        assert body.apply(command, channel="inbox")["status"] == "APPLIED"
        for _ in range(4):
            body.tick()
            clock.advance(31)
    monkeypatch.undo()                                       # read everything back with today's code only
    with Body(home, clock=clock) as body:                    # a new process replays the retained ledger
        accepted = {e.payload["kind"]: e.payload for e in body.journal.replay("command.accepted")}
        assert ("body" in accepted["MISSION"]) == (shape == "old")
        assert accepted_body(accepted["MISSION"]) == spec and accepted_body(accepted["FOUNDER_TIER"]) == FOUNDER_TIER_BODY
        assert body.apply(command)["status"] == "ALREADY_APPLIED"
        assert body.engine.book.missions[mid].status == "ACHIEVED"
        assert gg.signed_mission_spec(body.journal, mid) == spec       # re-verified from the retained envelope
        [appraised] = [e.payload for e in body.journal.replay("mission.appraised")]
        assert appraised["verdict"] == "VERIFIED" and appraised["checks"]["founder_signature_verified"]
        assert body.appraise(mid)["verdict"] == "VERIFIED"           # the separate process, run again now
        assert metrics.founder_tier(body.journal)[mid]["tier"] == metrics.FOUNDER_TIER
        assert metrics.tier_status(body.journal, list(body.enrolled_keys()))["enrolled_key_attested"]


def test_a_record_naming_a_body_its_envelope_did_not_sign_reads_as_the_envelope():
    """A retained record whose bare ``body`` differs from its envelope's reads as what was signed, never the copy."""
    env = {"body": {"key_custody": "passphrase"}}
    assert accepted_body({"body": {"key_custody": "none"}, "envelope": env}) == FOUNDER_TIER_BODY
    assert accepted_body({"body": {"x": 1}}) == {"x": 1}      # no envelope at all: the only body there is
    assert accepted_body(None) is None and accepted_body({}) is None


def test_a_new_acceptance_stores_the_signed_body_only_inside_its_envelope(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    spec = mission("m:once", checks=[note_check("n", workspace(home, "m:once") / "n.txt", "x")],
                   strategies=[write_strategy("w", "n.txt", "x", ["n"])], capabilities=["fs.read", "fs.write"])
    with Body(home) as body:
        body.apply(signed(key, body_id, "MISSION", spec))
        [payload] = [e.payload for e in body.journal.replay("command.accepted")]
    assert "body" not in payload and payload["envelope"]["body"] == spec
    assert json.dumps(payload).count('"founder_expression"') == 1
