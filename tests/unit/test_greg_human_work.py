"""Directive section 60: "I need a licensed professional for this decision." / a human worker's time.

A step only a person may do is never searched for, built or attached as software. GREG raises
one costed ask (resource ``professional`` or ``human_worker``), contacts and pays no one, keeps
observing the mission's own check, and closes the ask when the deliverable exists, without acting.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from greg import asks
from greg.body import Body, Layout, status
from greg.capabilities import BUILTINS, CapabilityError, CapabilityRegistry
from greg.missions import validate_mission
from greg.templates import human_work
from tests.greg_fixtures import Clock, drop, make_body, signed

ROOT = Path(__file__).resolve().parents[2]


def run(home, clock, ticks):
    with Body(home, clock=clock) as body:
        for _ in range(ticks):
            body.tick()
            clock.advance(1)


def events(home, kind):
    with Body(home) as body:
        return [e.payload for e in body.journal.replay(kind)]


def mission(home, function="professional.legal_review"):
    return human_work(function=function, purpose="Have my lease reviewed before I sign it",
                      deliverable="lease-review.pdf", workspace_root=Layout(home).workspace)


def test_a_professional_step_is_one_costed_ask_and_nothing_is_searched_built_or_contacted(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    spec = validate_mission(mission(home))
    drop(home, signed(key, body_id, "MISSION", spec))
    run(home, Clock(), 4)
    [ask] = events(home, "decision.requested")
    asks.validate(ask)
    assert ask["kind"] == "HUMAN_WORK" and ask["resource"] == "professional" and "wording_withheld" not in ask
    assert ask["authority_requested"]["spend"].startswith("none requested")
    assert ask["authority_requested"]["contact"] == "none; GREG contacts no one"
    assert [o for o in ask["options"] if o["cost"] == "none"]                 # refusing costs nothing
    assert "no price was looked up" in ask["uncertainty"] and "not its professional quality" in ask["uncertainty"]
    [watched] = ask["evidence"]["deliverable_observed_by"]
    assert watched["check_id"] == "deliverable_present" and watched["params"]["path"].endswith("lease-review.pdf")
    assert not events(home, "deficit.opened") and not events(home, "genesis.route")   # no software substitute
    assert not events(home, "mission.action")                                         # GREG did nothing itself
    [shown] = [r for r in status(home)["decisions_required"] if r["request_id"] == ask["request_id"]]
    assert "hires and pays no one" in shown["answer_effect"]                      # "Approve" is not hiring
    from greg.console import _ask_details
    assert "What your answer does:" in _ask_details(shown) and "their fee, unknown to GREG" in _ask_details(shown)
    assert "answer_effect" not in asks.surface({**ask, "kind": "APPROVAL"})        # only where an answer is a record
    run(home, Clock(), 3)
    assert len(events(home, "decision.requested")) == 1                                # asked once, never nagged


def test_the_deliverable_closes_the_ask_and_the_mission_without_greg_acting(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    spec = mission(home)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    run(home, clock, 3)
    [ask] = events(home, "decision.requested")
    drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"}))
    clock.advance(4000)
    run(home, clock, 2)
    assert not events(home, "mission.achieved")                   # an answer is not the work
    assert not events(home, "mission.unblocked")                  # and it does not churn the block
    path = Path(ask["evidence"]["deliverable_observed_by"][0]["params"]["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4 attorney opinion\n")              # the person's deliverable arrives
    clock.advance(4000)
    run(home, clock, 3)
    [withdrawn] = events(home, "decision.withdrawn")
    assert withdrawn["request_id"] == ask["request_id"] and "GREG took no action" in withdrawn["why"]
    [achieved] = events(home, "mission.achieved")
    assert achieved["mission_id"] == spec["mission_id"] and not events(home, "mission.action")


def test_a_human_task_asks_for_a_person_and_other_checks_resume_once_it_is_observed(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    spec = mission(home, function="human.photograph_meter")
    note = Layout(home).workspace / spec["mission_id"].replace(":", "_") / "note.txt"
    spec["success_checks"].append({"check_id": "noted", "description": "a note names the reading",
                                   "sensor": {"capability": "fs.read", "params": {"path": str(note)},
                                              "target": "fs:note.txt"},
                                   "predicate": {"op": "contains", "field": "text", "value": "reading filed"}})
    spec["strategies"].append({"action_id": "write-note", "capability": "fs.write", "requires": ["deliverable_present"],
                               "params": {"relative_path": "note.txt", "content": "reading filed\n"},
                               "target": "workspace:note.txt", "advances": ["noted"],
                               "rationale": "record the reading only after the photo exists"})
    spec["light_cone"]["capabilities"].append("fs.write")
    spec["light_cone"]["targets"].append("workspace:*")
    spec["light_cone"]["max_consequence_class"] = "internal_write"
    drop(home, signed(key, body_id, "MISSION", validate_mission(spec)))
    clock = Clock()
    run(home, clock, 3)
    [ask] = [r for r in events(home, "decision.requested") if r["kind"] == "HUMAN_WORK"]
    assert ask["resource"] == "human_worker" and "only a person may do" in ask["why_now"]
    Path(ask["evidence"]["deliverable_observed_by"][0]["params"]["path"]).parent.mkdir(parents=True, exist_ok=True)
    Path(ask["evidence"]["deliverable_observed_by"][0]["params"]["path"]).write_bytes(b"jpeg")
    clock.advance(4000)
    run(home, clock, 6)
    assert [w["request_id"] for w in events(home, "decision.withdrawn")] == [ask["request_id"]]
    assert note.read_text() == "reading filed\n"                  # the gated machine step ran only afterwards
    assert events(home, "mission.achieved")


@pytest.mark.parametrize("function", ["professional.legal_review", "human.sign_lease"])
def test_no_software_may_be_registered_in_a_persons_place(function):
    registry = CapabilityRegistry()
    manifest, adapter = BUILTINS["fs.read"]
    fake = type(manifest)(**{**manifest.__dict__, "capability_id": f"acquired.{function}.x", "function": function})
    with pytest.raises(CapabilityError, match="only a person may do"):
        registry.register(fake, adapter, state="ATTACHED")


@pytest.mark.parametrize("function, deliverable", [("legal_review", "x.pdf"), ("professional.x", "../escape.pdf"),
                                                   ("professional.Legal", "x.pdf"), ("human.x", ".hidden")])
def test_the_template_refuses_what_it_cannot_honestly_watch(tmp_path, function, deliverable):
    with pytest.raises(ValueError):
        human_work(function=function, purpose="p", deliverable=deliverable, workspace_root=tmp_path)


def test_the_cli_drafts_a_human_work_mission_without_signing(tmp_path):
    home, *_ = make_body(tmp_path)
    out = subprocess.run([sys.executable, "-m", "greg", "--home", str(home), "mission", "new", "human-work",
                          "--function", "professional.tax_return", "--purpose", "File this year's return",
                          "--deliverable", "return.pdf", "--print-only"], capture_output=True, text=True,
                         cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)}, timeout=60)
    assert out.returncode == 0, out.stderr
    spec = json.loads(out.stdout)
    spec = spec.get("spec", spec)
    assert spec["strategies"][0]["function"] == "professional.tax_return"
    assert spec["success_checks"][0]["sensor"]["params"]["path"].endswith("return.pdf")
