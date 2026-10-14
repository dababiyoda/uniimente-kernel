"""Goal Gravity on the GREG body: founder operation without code (ADR-GOAL-GRAVITY-002, graft 7 and 8).

The founder signs a GOAL derived from a signed mission, reads goals and their evidence while the body runs, and
sees persistent goals apart from missions on status, the phone's /api/status, the morning report and the console.
Real Body, real Ed25519 test founder key (NOT Alfonso's key).
"""
from __future__ import annotations

import json

from greg import goal_gravity as gg
from greg.body import status
from tests.unit.test_greg_goal_gravity import MID, fast, world  # noqa: F401  (shared fixtures)



def test_goal_from_a_signed_mission_is_deterministic_and_admissible(world, fast):
    from greg.capabilities import BUILTINS
    manifests = {m.capability_id: m for m, _ in BUILTINS.values()}
    spec = world.mission_spec()
    derived = gg.goal_from_mission(spec, manifests)
    assert derived == gg.goal_from_mission(spec, manifests)
    command = derived["goal_command"]
    assert command["missions"] == [MID] and command["max_consequence_class"] == "internal_write"
    moves = [i["intervention_id"] for n in command["goal"]["plan"] for i in n["interventions"]]
    assert moves == ["w2"]                                   # only the out-of-cone strategy needs a decision
    assert [n["sbm"] for n in command["goal"]["plan"]] == [f"{MID}.c", f"{MID}.d"]
    world.submit("MISSION", spec, "a.json")
    world.tick()
    world.submit("GOAL", command, "b.json")
    world.tick()
    assert len(world.projection()["goals"]) == 1


def test_the_cli_is_one_entry_for_goals(world, fast, capsys):
    from greg import cli
    home = str(world.home)
    world.submit("MISSION", world.mission_spec(), "a.json")
    world.tick()
    assert cli.main(["--home", home, "gravity", "authorize", "--from-mission", MID, "--print-only"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["kind"] == "GOAL" and printed["body"]["missions"] == [MID]
    assert cli.main(["--home", home, "gravity", "authorize", "--from-mission", MID, "--key",
                     str(world.tmp / "founder.pem"), "--no-passphrase"]) == 0
    capsys.readouterr()
    world.tick()
    gid = world.projection()["goals"][0]["goal_id"]
    with world.body():                                       # read-only views work while the body holds the lock
        assert cli.main(["--home", home, "gravity", "goals"]) == 0
        assert json.loads(capsys.readouterr().out)["goals"][0]["goal_id"] == gid
        assert cli.main(["--home", home, "gravity", "evidence", gid[:20]]) == 0
        evidence = json.loads(capsys.readouterr().out)
        assert evidence["admitted"] and evidence["authorization_record"] and evidence["signed_goal_command"]
    assert cli.main(["--home", home, "gravity", "control", gid[:20], "--kind", "stop_pushing", "--value", "true",
                     "--key", str(world.tmp / "founder.pem"), "--no-passphrase"]) == 0
    capsys.readouterr()
    world.tick()
    assert world.registry().state(gid).status == "paused"
    assert cli.main(["--home", home, "gravity"]) == 2       # no action and no situation: a usage refusal
    assert cli.main(["--home", home, "gravity", "control", gid[:20], "--kind", "explode", "--key", "k"]) == 2


def test_status_morning_report_and_console_show_goals_apart_from_missions(world):
    gid, _ = world.start()
    world.tick(3)
    st = status(world.home)
    assert st["missions"] == st["goals"] and st["missions"][0]["mission_id"] == MID
    assert "legacy alias" in st["keys"]["goals"]
    assert [g["goal_id"] for g in st["gravity"]["goals"]] == [gid] and st["gravity"]["execution_authority"] == "none"
    from greg.body import morning_projection
    section = morning_projection(world.home)["goal_gravity"]
    assert section["goals"][0]["goal_id"] == gid and section["closure"]["ok"]
    from greg.console import Console, render_home
    page = render_home(Console(world.home)).decode()
    assert "Persistent goals" in page and "d shipped and N1 reached" in page
