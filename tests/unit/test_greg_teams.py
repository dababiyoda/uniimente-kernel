"""WU-03: one signed sandbox mission fields two genuinely concurrent workers under one grant (``worker.team``).

The team is Foundry #48, reached only through ``foundry.apply`` / ``foundry.query`` (greg/teams.py). Founder decision
on #96 (2026-11-21): each worker has a distinct role and work order; both enter their assigned work before either is
released; their combined spend stays within the parent cap; their outputs are independently appraisable;
dissolution prevents further action; a paid role whose spend cannot be metered is refused.

The founder key is a per-test Ed25519 key, not Alfonso's; the workers are scripted test doubles, not frontier
workers, run through the Body's main loop (Body.run) in a thread with a real clock.
"""
from __future__ import annotations

import json
import threading
import time

import pytest

from greg import foundry_bridge, workers
from greg.body import Body, Layout, observe
from greg.capabilities import CapabilityError
from tests.greg_fixtures import drop, horizon, make_body, signed
from tests.unit.test_greg_workers import GOOD, ScriptedWorker, acceptance_envelope, make_repo  # noqa: F401

WAIT = 30
MUL = {"pkg/ops.py": "def mul(a, b):\n    return a * b\n",
       "tests/test_ops.py": "from pkg.ops import mul\n\n\ndef test_mul():\n    assert mul(3, 2) == 6\n"}


class MeteredHoldingWorker(ScriptedWorker):
    """A metered paid worker double: it reports its own cost the way Claude Code reports total_cost_usd.

    Every member waits at one shared barrier when it enters its work, so a member can pass only once all of them
    are working at once; then it holds until the test releases the team."""
    METERS_SPEND = True

    def __init__(self, edits, *, cost, barrier, release, entered):
        super().__init__(edits, cost=cost)
        self.barrier, self.release, self.entered = barrier, release, entered

    def run(self, order, cwd):
        self.entered.append((order.order, threading.current_thread().name))
        self.barrier.wait(WAIT)                  # BrokenBarrierError if the other member never starts
        if not self.release.wait(WAIT):
            raise AssertionError("the test never released the team")
        return super().run(order, cwd)


class UnmeteredWorker(ScriptedWorker):
    """A paid CLI double that reports no spend GREG can book (like codex or aider)."""


def member(role, order, repo, provider, cap, objective):
    return {"role": role, "order": {"order": order, "mode": "repository", "repo": str(repo), "objective": objective,
                                    "acceptance": {"run_changed_tests": True, "max_changed_files": 4},
                                    "allowed_paths": ["pkg/*", "tests/*"], "provider": provider,
                                    "max_budget_usd": cap, "timeout_seconds": 120}}


def team_mission(repo, *, mission_id="m:team", team="calc-team", cap=1.0, members=None, priority=50):
    members = members or [member("adder", "add-sub", repo, "team-a", 0.4, "add sub()"),
                          member("multiplier", "add-mul", repo, "team-b", 0.4, "add mul()")]
    checks = [{"check_id": f"{m['role']}_accepted", "description": f"worker.appraise ACCEPTED {m['order']['order']}",
               "sensor": {"capability": "worker.appraise", "params": {"order": m["order"]["order"]},
                          "target": f"work:{m['order']['order']}"},
               "predicate": {"op": "equals", "field": "verdict", "value": "ACCEPTED"}} for m in members]
    return {"mission_id": mission_id, "founder_expression": "Two workers at once: sub() and mul()",
            "intended_effect": "two independently appraised changes from one temporary team under one grant",
            "priority": priority, "closure": {"kind": "bounded"}, "constraints": [],
            "success_checks": checks,
            "strategies": [{"action_id": "field-team", "capability": "worker.team", "target": f"team:{team}",
                            "params": {"team": team, "objective": "add sub() and mul() in parallel",
                                       "max_budget_usd": cap, "members": members},
                            "cost_usd": cap, "advances": [c["check_id"] for c in checks],
                            "rationale": "two independent changes: parallel workers halve the wall time"}],
            "light_cone": {"capabilities": ["worker.team", "worker.appraise"],
                           "targets": [f"team:{team}"] + [f"work:{m['order']['order']}" for m in members],
                           "max_consequence_class": "internal_write", "budget_usd": cap, "horizon": horizon()}}


def wait_for(predicate, what, timeout=WAIT):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    pytest.fail(f"timed out waiting for {what}")


def payloads(home, kind):
    with observe(home, actor="spiffe://uniimente.internal/test/teams") as journal:
        return [e.payload for e in journal.replay(kind)]


def start(body):
    loop = threading.Thread(target=body.run, kwargs={"tick_seconds": 0.05}, daemon=True)
    loop.start()
    return loop


def stop(body, loop):
    body.stop_requested = True
    loop.join(WAIT)
    assert not loop.is_alive(), "the body did not stop"


def team_ready(tmp_path, monkeypatch, **kw):
    data = tmp_path / "data"
    data.mkdir()
    repo = make_repo(data)
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data])
    barrier, release, entered = threading.Barrier(2), threading.Event(), []
    a = MeteredHoldingWorker(GOOD, cost=0.15, barrier=barrier, release=release, entered=entered)
    b = MeteredHoldingWorker(MUL, cost=0.25, barrier=barrier, release=release, entered=entered)
    monkeypatch.setitem(workers.PROVIDERS, "team-a", a)
    monkeypatch.setitem(workers.PROVIDERS, "team-b", b)
    return home, key, body_id, repo, (a, b, barrier, release, entered)


def actions(home, capability):
    return [p for p in payloads(home, "mission.action") if p.get("capability") == capability]


def test_one_signed_action_fields_two_concurrent_workers_under_one_grant(tmp_path, monkeypatch):
    home, key, body_id, repo, (a, b, barrier, release, entered) = team_ready(tmp_path, monkeypatch)
    drop(home, signed(key, body_id, "MISSION", team_mission(repo)))
    body = Body(home)
    loop = start(body)
    try:
        wait_for(lambda: len(entered) == 2, "both members to enter their work")
        # Both are inside their assigned work at once, neither released: the barrier let them through together.
        assert not release.is_set() and a.calls == 0 and b.calls == 0
        wait_for(lambda: barrier.n_waiting == 0 and not barrier.broken, "both members to pass the barrier together")
        assert sorted(order for order, _ in entered) == ["add-mul", "add-sub"]
        assert len({thread for _, thread in entered}) == 2          # two threads, not one after the other
        release.set()
        wait_for(lambda: "m:team" in [p["mission_id"] for p in payloads(home, "mission.achieved")],
                 "the team mission to close on two independent appraisals")
    finally:
        release.set()
        stop(body, loop)
    team = actions(home, "worker.team")
    assert len(team) == 1 and team[0]["status"] == "DONE"            # one signed action, one grant
    assert a.calls == 1 and b.calls == 1
    # Combined spend stays within the parent cap and is booked as measured.
    assert team[0]["cost_usd"] == pytest.approx(0.40) and team[0]["cost_usd"] <= 1.0
    out = team_output(home)
    assert out["team"]["state"] == "DISSOLVED" and out["team"]["spent_usd"] == pytest.approx(0.40)
    assert out["team"]["foundry_spent_usd"] == pytest.approx(0.40)
    assert set(out["team"]["members"]) == {"adder", "multiplier"}   # distinct roles inside the grant
    assert sorted(out["members"]) == ["add-mul", "add-sub"]          # distinct work orders, one entry each
    assert len({m["grant_id"] for m in out["members"].values()}) == 1   # both under the one action's grant
    assert {m["grant_id"] for m in out["members"].values()} == {receipt_grant(home)}
    # Independently appraisable: each order was appraised by its own sensor, ACCEPTED.
    verdicts = {p["check_id"]: p["passed"] for p in payloads(home, "mission.observed")}
    assert verdicts["adder_accepted"] and verdicts["multiplier_accepted"]
    # Dissolution prevents further action: the team's own store refuses another act.
    with pytest.raises(CapabilityError, match="DISSOLVED"):
        team_act(home, "m:team", "calc-team", "adder")


def team_output(home, mission_id="m:team"):
    with observe(home, actor="spiffe://uniimente.internal/test/teams") as journal:
        team = [e.payload for e in journal.replay("mission.action")
                if e.payload.get("capability") == "worker.team" and e.payload.get("mission_id") == mission_id]
        record = journal.ledger.find(team[-1]["receipt"])
        return record.payload["result"]["output"]


def receipt_grant(home, mission_id="m:team"):
    with observe(home, actor="spiffe://uniimente.internal/test/teams") as journal:
        team = [e.payload for e in journal.replay("mission.action")
                if e.payload.get("capability") == "worker.team" and e.payload.get("mission_id") == mission_id]
        return journal.ledger.find(team[-1]["receipt"]).payload["grant_id"]


def team_act(home, mission_id, team_id, role):
    from dataclasses import dataclass, field
    ws = Layout(home).workspace / mission_id.replace(":", "_") / "teams" / team_id

    @dataclass
    class Ctx:                                         # the bridge reads only these fields
        workspace: object
        journal: object = None
        mission_id: str = ""
        target: str = ""
        stop_check: object = None
        extra: dict = field(default_factory=dict)
    return foundry_bridge.apply({"system": 48, "op": "act",
                                 "args": {"team_id": team_id, "role": role, "system": 36, "op": "put",
                                          "args": {"text": "after dissolution"}}}, Ctx(workspace=ws))


def refused_mission(tmp_path, monkeypatch, members, cap=1.0):
    data = tmp_path / "data"
    data.mkdir()
    repo = make_repo(data)
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data])
    drop(home, signed(key, body_id, "MISSION", team_mission(repo, members=members(repo), cap=cap)))
    body = Body(home)
    loop = start(body)
    try:
        wait_for(lambda: actions(home, "worker.team"), "the team action to be decided")
    finally:
        stop(body, loop)
    return home, actions(home, "worker.team")


def test_a_paid_role_whose_spend_cannot_be_metered_is_refused_before_anyone_works(tmp_path, monkeypatch):
    metered = ScriptedWorker(GOOD, cost=0.1)
    metered.METERS_SPEND = True                        # instance attribute is ignored: metering is the class's word
    cli = UnmeteredWorker(MUL, cost=0.1)
    monkeypatch.setitem(workers.PROVIDERS, "team-a", metered)
    monkeypatch.setitem(workers.PROVIDERS, "team-cli", cli)
    home, acted = refused_mission(tmp_path, monkeypatch, lambda repo: [
        member("adder", "add-sub", repo, "team-a", 0.4, "add sub()"),
        member("multiplier", "add-mul", repo, "team-cli", 0.4, "add mul()")])
    assert acted[0]["status"] != "DONE"
    assert any("cannot meter" in r for r in acted[0]["reasons"])
    assert metered.calls == 0 and cli.calls == 0                   # refused before the team formed or anyone ran
    assert not (Layout(home).workspace / "m_team" / "teams" / "calc-team").exists()


def test_members_whose_caps_exceed_the_signed_cap_never_start(tmp_path, monkeypatch):
    class Metered(ScriptedWorker):
        METERS_SPEND = True
    a, b = Metered(GOOD, cost=0.1), Metered(MUL, cost=0.1)
    monkeypatch.setitem(workers.PROVIDERS, "team-a", a)
    monkeypatch.setitem(workers.PROVIDERS, "team-b", b)
    home, acted = refused_mission(tmp_path, monkeypatch, lambda repo: [
        member("adder", "add-sub", repo, "team-a", 0.6, "add sub()"),
        member("multiplier", "add-mul", repo, "team-b", 0.6, "add mul()")], cap=1.0)
    assert acted[0]["status"] != "DONE"
    assert any("above the action's signed cap" in r for r in acted[0]["reasons"])
    assert a.calls == 0 and b.calls == 0


def test_two_members_may_not_share_a_role_or_a_work_order(tmp_path, monkeypatch):
    from greg import teams

    class Metered(ScriptedWorker):
        METERS_SPEND = True
    monkeypatch.setitem(workers.PROVIDERS, "team-a", Metered(GOOD, cost=0.1))
    repo = tmp_path / "proj"
    with pytest.raises(teams.TeamRefused, match="distinct"):
        teams._members({"members": [member("adder", "add-sub", repo, "team-a", 0.4, "x"),
                                    member("adder", "add-mul", repo, "team-a", 0.4, "y")]}, 1.0)
    with pytest.raises(teams.TeamRefused, match="its own"):
        teams._members({"members": [member("adder", "add-sub", repo, "team-a", 0.4, "x"),
                                    member("multiplier", "add-sub", repo, "team-a", 0.4, "y")]}, 1.0)
    with pytest.raises(teams.TeamRefused, match="2 to"):
        teams._members({"members": [member("adder", "add-sub", repo, "team-a", 0.4, "x")]}, 1.0)


def test_the_shipped_providers_are_metered_free_or_refused_as_paid_roles():
    from greg import teams
    assert teams.spend_metering(workers.PROVIDERS["claude-code"]) == "metered"   # reports total_cost_usd
    assert teams.spend_metering(workers.PROVIDERS["script"]) == "none"           # no provider route to charge
    assert teams.spend_metering(workers.PROVIDERS["codex"]) == "unmetered"       # reports no cost
    assert teams.spend_metering(workers.PROVIDERS["aider"]) == "unmetered"


def test_a_team_the_founder_ends_mid_work_dissolves_and_keeps_its_cap_until_reconciled(tmp_path, monkeypatch):
    home, key, body_id, repo, (a, b, barrier, release, entered) = team_ready(tmp_path, monkeypatch)
    drop(home, signed(key, body_id, "MISSION", team_mission(repo)))
    body = Body(home)
    loop = start(body)
    try:
        wait_for(lambda: len(entered) == 2, "both members to enter their work")
        drop(home, signed(key, body_id, "LIFECYCLE", {"mission_id": "m:team", "state": "ABANDONED",
                                                      "reason": "the founder ends the team mid-work"}))
        wait_for(lambda: any(p["state"] == "ABANDONED" for p in payloads(home, "mission.lifecycle")),
                 "the founder's cancel to be recorded")
        release.set()
        wait_for(lambda: actions(home, "worker.team"), "the team's outcome to be recorded")
        time.sleep(0.5)
    finally:
        release.set()
        stop(body, loop)
    team = actions(home, "worker.team")
    assert len(team) == 1 and team[0]["status"] == "UNCERTAIN"       # never booked as an ordinary success
    assert team[0]["spend_basis"].startswith("reserved")             # the signed cap counts until reconciled
    assert "m:team" not in [p["mission_id"] for p in payloads(home, "mission.achieved")]
    assert not [p for p in payloads(home, "mission.observed") if p.get("passed")]   # nothing appraised after the end
    state = json.loads((Layout(home).workspace / "m_team" / "teams" / "calc-team" / "foundry" / "system-48"
                        / "team-calc-team.json").read_text())
    assert state["state"] == "DISSOLVED"
    with pytest.raises(CapabilityError, match="DISSOLVED"):
        team_act(home, "m:team", "calc-team", "multiplier")
