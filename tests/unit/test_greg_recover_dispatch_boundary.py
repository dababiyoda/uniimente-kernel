"""Mission H (H3) boundary: which dispatches a restarted body must settle before it observes.

The real-process test (tests/integration/test_greg_body_midflight_kill.py) proves that a body killed inside a
consequential dispatch reconciles it before the mission can close. This in-process test pins the boundary of
that rule deterministically: the adapter "dies" with a BaseException after the Consequence Gate claimed the
dispatch and before any receipt (the Gate's own ``except Exception`` cannot see it, exactly as with SIGKILL),
then the world comes to satisfy the goal by other means and a fresh body opens on the same home.

- A free read_only dispatch cannot have changed the world or the budget: observation decides first and the
  mission closes, with no reconciliation and no second dispatch (the regression this file was written for:
  recovery had turned an answerable cognition mission into a needless RECONCILIATION).
- A read_only dispatch with a signed cost may have spent money: it is settled UNCERTAIN with its cap reserved.
- An internal_write dispatch may have changed the world: it is settled UNCERTAIN before observation.

The founder key is a per-test Ed25519 key, not Alfonso's; the capabilities are test doubles.
"""
from __future__ import annotations

import pytest

from greg.body import Body
from greg.capabilities import CapabilityManifest
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed


class Died(BaseException):
    """The process stopped inside the adapter: no exception handler in the body or the Gate runs."""


def probe_body(calls: list):
    def adapter(params, ctx):
        calls.append(ctx.grant_id)
        raise Died()

    class ProbeBody(Body):
        def open(self):
            super().open()
            for cid, consequence in (("test.probe_read", "read_only"), ("test.probe_write", "internal_write")):
                self.registry.register(CapabilityManifest(
                    capability_id=cid, version="1.0.0", provider="test", function=cid,
                    description="dies after the Gate claimed its dispatch", route="api",
                    consequence_class=consequence, inputs={"probe": "str"}, outputs={"ok": "bool"}, strengthens=("proof",),
                    target_prefix="probe:", retry_safe=False), adapter, state="ATTACHED")
            return self
    return ProbeBody


def events(body, kind):
    return [e.payload for e in body.journal.replay(kind)]


def ours(body, proposal_id, record_type):
    """The probe dispatch's own Gate records (the fs.read sensor dispatches through the Gate too)."""
    return [r for r in body.ledger.by_type(record_type) if r.payload.get("proposal_id") == proposal_id]


@pytest.mark.parametrize("capability, cost, settles_first", [
    ("test.probe_read", 0.0, False),        # cannot have changed the world or the budget: observe first
    ("test.probe_read", 0.25, True),        # may have spent: reserve the cap, reconcile that one dispatch
    ("test.probe_write", 0.0, True),        # may have changed the world: reconcile before observing
])
def test_a_dispatch_interrupted_after_its_claim_is_settled_first_only_when_it_could_matter(
        tmp_path, capability, cost, settles_first):
    home, key, body_id, data = make_body(tmp_path)
    goal = data / "answer.txt"
    spec = mission("m:probe", checks=[note_check("answered", goal, "answered")],
                   strategies=[{"action_id": "probe", "capability": capability, "params": {"probe": "once"},
                                "target": "probe:x", "advances": ["answered"], "rationale": "probe once", "cost_usd": cost}],
                   capabilities=["fs.read", capability], targets=("fs:*", "probe:*"), budget=1.0)
    drop(home, signed(key, body_id, "MISSION", spec))
    calls, clock = [], Clock()
    ProbeBody = probe_body(calls)

    with ProbeBody(home, clock=clock) as body:
        with pytest.raises(Died):
            for _ in range(6):
                body.tick()
                clock.advance(1)
        [intent] = events(body, "mission.dispatching")
        [claim] = ours(body, intent["proposal_id"], "grant_dispatch")
        assert not ours(body, intent["proposal_id"], "receipt") and not events(body, "mission.action")

    goal.write_text("answered")                    # the world now satisfies the goal by other means

    with ProbeBody(home, clock=clock) as body:
        for _ in range(4):
            body.tick()
            clock.advance(1)
        state = body.engine.book.missions["m:probe"]
        actions = events(body, "mission.action")
        reconciliations = [r for r in events(body, "decision.requested") if r["kind"] == "RECONCILIATION"]
        assert len(ours(body, intent["proposal_id"], "grant_dispatch")) == 1     # the one claim, never a second
    assert len(calls) == 1, "nothing is dispatched twice"
    if settles_first:
        assert state.status != "ACHIEVED"
        claimed = claim.payload["grant_id"]
        assert [(a["status"], a["attempt"], a["grant_id"]) for a in actions] == [("UNCERTAIN", 0, claimed)]
        assert actions[0]["reserved_usd"] == cost and actions[0]["cost_usd"] == 0.0
        assert len(reconciliations) == 1 and reconciliations[0]["authority_requested"]["grant_id"] == claimed
    else:
        assert state.status == "ACHIEVED"
        assert actions == [] and reconciliations == []
