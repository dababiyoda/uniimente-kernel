"""A capability ask says what an answer does, so Approve never strands a mission silently.

Found by #168 rehearsing the Chromebook runbook. On a capability ask the console and phone offered
Approve; approving only records an answer, the ask leaves every surface, and the mission stays
blocked until a signed CAPABILITY_ATTACH. The surfaces now say so beside the buttons, in the same
words #168 uses, so the two lines merge cleanly.
"""
from __future__ import annotations

from greg import asks
from greg.body import Body
from greg.console import Console, render_home
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace


def test_a_capability_ask_says_approving_attaches_nothing(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:needs-a-tool"
    spec = mission(mid, checks=[note_check("n", workspace(home, mid) / "n.txt", "done")],
                   strategies=[{"action_id": "x", "function": "text.no_such_function_anywhere", "target": "fs:n.txt",
                                "advances": ["n"], "rationale": "needs a capability GREG lacks"}],
                   capabilities=["fs.read"])
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(4):
            body.tick()
            clock.advance(60)
        [ask] = [e.payload for e in body.journal.replay("decision.requested")
                 if e.payload["mission_id"] == mid and e.payload["kind"] == "CAPABILITY_ATTACH"]
    shown = asks.surface(ask)
    assert "only records your answer" in shown["answer_effect"] and "greg attach" in shown["answer_effect"]
    page = render_home(Console(home)).decode()
    assert "What your answer does" in page and "greg attach" in page
