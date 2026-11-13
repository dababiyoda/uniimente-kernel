"""A paid move whose run books $0 (the founder-signed script worker always reports cost_usd=0.0) keeps its
approval: the scope digest binds the mission's spend, which a $0 run does not change. What the founder is told
an approve means (``approve_means``) must match what the engine then does with it."""
from __future__ import annotations

import os

import pytest

from greg import goal_gravity as gg, templates
from greg import worker_isolation as isolation
from greg.body import Body, Layout
from greg.capabilities import BUILTINS
from greg.missions import MissionBook
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.unit.test_greg_workers import make_repo

pytestmark = pytest.mark.real_isolation

SCRIPT = '''
from pathlib import Path
Path("tests").mkdir(exist_ok=True)
Path("pkg/sub.py").write_text("from pkg.calc import add\\n\\n\\ndef sub(a, b):\\n    return add(a, -b)\\n")
Path("tests/test_sub.py").write_text("from pkg.sub import sub\\n\\n\\ndef test_sub():\\n    assert sub(5, 3) == 2\\n")
print("GREG-REPORT {\\"changed\\": [\\"pkg/sub.py\\", \\"tests/test_sub.py\\"], \\"tests_run\\": [], \\"unresolved\\": [], \\"confidence\\": 1}")
'''


@pytest.fixture(autouse=True)
def need_envelope():
    try:
        isolation._backend(require_bubblewrap=True)
    except isolation.WorkerIsolationError as exc:
        if os.environ.get("GREG_REQUIRE_WORKER_ISOLATION") == "1":
            pytest.fail(str(exc))
        pytest.skip(f"host cannot provide the worker envelope: {exc}")


def test_what_an_approve_of_a_zero_booked_paid_move_is_said_to_mean_matches_what_it_does(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    repo = make_repo(data)
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data])
    spec = templates.code_change(repo=str(repo), objective="add sub() with a founder-signed script", order="add-sub",
                                 provider="script", script=SCRIPT, allowed_paths=["pkg/*", "tests/*"],
                                 budget_usd=0.01, workspace_root=Layout(home).workspace)
    spec["light_cone"]["capabilities"].remove("worker.commission")    # the founder decides the commission
    spec["closure"] = {"kind": "infinite", "cadence_seconds": 3600}
    mid = spec["mission_id"]
    goal = gg.goal_from_mission(spec, {mf.capability_id: mf for mf, _ in BUILTINS.values()})["goal_command"]
    drop(home, signed(key, body_id, "MISSION", spec), "a-mission.json")
    drop(home, signed(key, body_id, "GOAL", goal), "b-goal.json")
    clock = Clock()

    def run(n, step=60):
        with Body(home, clock=clock) as body:
            for _ in range(n):
                body.tick()
                clock.advance(step)

    def state():
        with Body(home, clock=clock) as body:
            book = MissionBook(body.journal)
            asks = [rid for rid, r in book.requests.items() if r.get("action_id") == "commission-worker"]
            runs = [e.payload for e in body.journal.replay("mission.action")
                    if e.payload["action_id"] == "commission-worker" and e.payload["status"] == "DONE"]
            gid = gg.projection(body.journal)["goals"][0]["goal_id"]
            told = {a["request_id"]: a["approve_means"] for a in gg.evidence(body.journal, gid)["asks"]}
        return asks, runs, told

    run(4)
    asks, runs, told = state()
    assert len(asks) == 1 and not runs
    said = told[asks[0]]                       # what `greg gravity evidence` tells the founder about this ask
    drop(home, signed(key, body_id, "DECISION", {"request_id": asks[0], "answer": "approve", "reason": "go"}))
    run(6)
    asks, runs, _ = state()
    assert len(runs) == 1 and runs[0]["cost_usd"] == 0.0 and runs[0]["spend_basis"] == "provider_reported"

    # the work regresses: the independent appraisal no longer accepts it, so the mission's loop selects it again
    (Layout(home).workspace / mid.replace(":", "_") / "work-orders" / "add-sub" / "evidence.json").unlink()
    clock.advance(3700)
    run(6)
    asks, runs, _ = state()
    print("told:", said[:70], "| runs:", len(runs), "| asks:", len(asks))
    if "runs it once" in said:                 # APPROVE_MEANS_PAID: "the mission runs it once ... asks you again"
        assert len(runs) <= len(asks), \
            f"told the approve funds one run, but the move ran {len(runs)} times on {len(asks)} ask(s)"
