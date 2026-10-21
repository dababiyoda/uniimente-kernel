"""Node N4: a repeatedly verified procedure becomes a ratified SOP and then a workflow, and founder
interventions and model cost per verified outcome fall without quality loss.

The workflow is the least general generalization of the founder-signed specs of verified runs; only
parameter positions may become slots. A ratified SOP runs with zero model calls; steps Alfonso approved
in every verified run may be pre-approved into the cone he signs for each later run. The trend and the
N4 predicate count only exact runs of the ratified workflow, on the designated body, appraised VERIFIED.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from greg import path as devpath, planner, sop, templates
from greg.body import Body, status
from greg.missions import validate_mission
from greg.tribunal import morning_report
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy

ROOT = Path(__file__).resolve().parents[2]
CHECKS = {c: True for c in sop.REQUIRED_CHECKS}


def note_mission(home, mid: str, text: str, **kw) -> dict:
    """Write a note, then observe it: the write is outside the read-only cone, so it asks Alfonso."""
    return mission(mid, checks=[note_check("n", workspace(home, mid) / "n.txt", text)],
                   strategies=[write_strategy("w", "n.txt", text, ["n"])], capabilities=["fs.read"],
                   ceiling="read_only", **kw)


def record_like(workflow: dict, pre_approved=()) -> dict:
    return {"procedure_id": "sop-0123456789abcdef", "command_digest": "sha256:ratify", "steps": ["fs.write"],
            "workflow": {**workflow, "horizon_days": 2.0}, "pre_approved_steps": list(pre_approved)}


# -- generalization ---------------------------------------------------------------------------

@pytest.mark.parametrize("make, slots", [
    (lambda n, ws: templates.word_limit(file=Path(f"/data/drafts/essay-{n}.md"), max_words=300 + 150 * n,
                                        workspace_root=ws), {"path": "string", "words": "integer"}),
    (lambda n, ws: templates.verify_download(file=Path(f"/data/dl/release-{n}.tar.gz"), sha256="abc"[n] * 64,
                                             workspace_root=ws), {"path": "string", "sha256": "string"}),
])
def test_the_workflow_is_what_varied_in_the_signed_runs_and_rebuilds_each_one(tmp_path, make, slots):
    specs = [make(n, tmp_path) for n in range(3)]
    workflow = sop.generalize(specs)
    assert {k: v["type"] for k, v in workflow["slots"].items()} == slots    # the template's own inputs, no more
    record = record_like(workflow)
    for spec in specs:                                  # every run is reproduced exactly from its inputs
        values = {name: slot["examples"][specs.index(spec)] for name, slot in workflow["slots"].items()}
        rebuilt = sop.instantiate(record, values, mission_id=spec["mission_id"])
        assert sop._strip(rebuilt) == sop._strip(spec)
    fresh = sop.instantiate(record, {k: v["examples"][0] for k, v in workflow["slots"].items()})
    assert fresh["provenance"]["model_calls"] == 0 and fresh["provenance"]["origin"] == "sop:sop-0123456789abcdef"
    folder = fresh["mission_id"].replace(":", "_")      # derived values follow the new run, never the old one
    assert folder in fresh["success_checks"][1]["sensor"]["params"]["path"]


@pytest.mark.parametrize("mutate, where", [
    (lambda s: s["light_cone"].update(budget_usd=5), "light_cone.budget_usd"),
    (lambda s: s["light_cone"].update(max_consequence_class="internal_write"), "light_cone.max_consequence_class"),
    (lambda s: s["success_checks"][0]["predicate"].update(op="equals"), "success_checks.0.predicate.op"),
    (lambda s: s["strategies"][0].update(capability="fs.append"), "strategies.0.capability"),
    (lambda s: s["closure"].update(kind="infinite"), "closure.kind"),
])
def test_runs_that_differ_in_authority_or_acceptance_are_not_one_procedure(tmp_path, mutate, where):
    specs = [note_mission(tmp_path, f"m:note-{n}", f"done {n}") for n in range(3)]
    mutate(specs[2])
    with pytest.raises(sop.SopError, match=where.replace(".", r"\.")):
        sop.generalize(specs)
    assert sop.shape(specs[2]) != sop.shape(specs[0])   # and the observer never groups them


def test_text_with_braces_and_numbers_round_trips_and_slots_are_checked_before_signing(tmp_path):
    specs = []
    for n in range(3):
        text = json.dumps({"run": n + 10, "ok": True})            # literal braces inside a varying value
        specs.append(note_mission(tmp_path, f"m:json-{n}", text))
    workflow = sop.generalize(specs)
    assert list(workflow["slots"]) == ["text"]
    record = record_like(workflow)
    rebuilt = sop.instantiate(record, {"text": '{"run": 11, "ok": true}'}, mission_id="m:json-1")
    assert sop._strip(rebuilt) == sop._strip(specs[1])
    for bad, why in [({}, "missing"), ({"text": "x", "extra": 1}, "unknown"), ({"text": 7}, "must be a string"),
                     ({"text": ""}, "must be a string")]:
        with pytest.raises(sop.SopError, match=why):
            sop.instantiate(record, bad)
    with pytest.raises(sop.SopError, match="at most 2.0 days"):
        sop.instantiate(record, {"text": "x"}, horizon_days=30)


# -- crafted histories: what the trend refuses to count ---------------------------------------

def closure(j, spec, *, approvals=("w",), verdict="VERIFIED", build_cost=None, approved_class="internal_write",
            approved_cost=0.0):
    mid = spec["mission_id"]
    j.record("mission.registered", {"mission_id": mid, "spec": spec, "command_digest": "sha256:" + mid}, key=mid)
    for aid in approvals:
        rid = f"req-{mid}-{aid}"
        j.record("decision.requested", {"request_id": rid, "mission_id": mid, "kind": "APPROVAL", "action_id": aid,
                                        "scope_digest": "s", "authority_requested": {
                                            "capability": "fs.write", "consequence_class": approved_class,
                                            "cost_usd": approved_cost, "target": "workspace:n.txt"}}, key=rid)
        j.record("decision.answered", {"request_id": rid, "mission_id": mid, "answer": "approve", "reason": "",
                                       "command_digest": "sha256:d"}, key=rid)
    if build_cost is not None:
        j.record("deficit.opened", {"deficit_id": f"d-{mid}", "mission_id": mid, "function": "f"}, key=f"d-{mid}")
        j.record("genesis.built", {"deficit_id": f"d-{mid}", "attempt": 0, "builder": "model:openai",
                                   "cost_usd": build_cost}, key=f"b-{mid}")
    j.record("mission.action", {"mission_id": mid, "action_id": "w", "attempt": 0, "status": "DONE",
                                "reasons": [], "receipt": None, "capability": "fs.write", "route": "builtin",
                                "cost_usd": 0.0, "scope_digest": "s", "at": "t"}, key=[mid, "w"])
    achieved = j.record("mission.achieved", {"mission_id": mid, "evidence": []}, key=[mid, "achieved"])
    j.record("mission.appraised", {"mission_id": mid, "verdict": verdict, "checks": CHECKS, "findings": []},
             key=[mid, "appraised"])
    return achieved


def taught_and_ratified(j, home, *, pre_approve=("w",)):
    for n in range(3):
        closure(j, note_mission(home, f"m:note-{n}", f"done {n}"))
    [proposal] = sop.propose(j)
    record = sop.ratify(j, {"procedure_id": proposal["procedure_id"], "pre_approve": list(pre_approve)},
                        "sha256:ratify")
    return proposal, record


@pytest.mark.parametrize("case, expect", [
    ("ok", None),
    ("still_asks", "founder interventions per outcome did not fall"),
    ("refuted", "quality not held"),
    ("rejected", "quality not held"),
    ("doctored", "2 of 3 verified runs"),
    ("long_mandate", "2 of 3 verified runs"),
    ("model_cost", "model cost per outcome did not fall"),
])
def test_the_trend_counts_only_exact_runs_that_held_quality_and_cut_interventions(tmp_path, case, expect):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        j = body.journal
        proposal, record = taught_and_ratified(j, home)
        assert record["authority_inherited"] is False and record["pre_approved_steps"][0]["action_id"] == "w"
        for n in range(3):
            spec = sop.instantiate(record, {"text": f"sop run {n}"},
                                   now=datetime.now(timezone.utc) + timedelta(seconds=n))
            assert "fs.write" in spec["light_cone"]["capabilities"]
            assert spec["light_cone"]["max_consequence_class"] == "internal_write"
            if n == 2 and case == "doctored":
                spec["light_cone"]["budget_usd"] = 5                     # signed, but not this procedure
            if n == 2 and case == "long_mandate":
                spec = sop.instantiate(record, {"text": "x"}, now=datetime.now(timezone.utc) + timedelta(days=28))
            achieved = closure(j, spec, approvals=("w",) if case == "still_asks" else (),
                               verdict="REFUTED" if case == "refuted" and n == 1 else "VERIFIED",
                               build_cost=0.25 if case == "model_cost" and n == 0 else None)
            if case == "rejected" and n == 0:
                j.record("critique.recorded", {"critique_id": "crit-1", "target_event_id": achieved.event_id,
                                               "verdict": "reject", "evidence_type": "founder_judgment",
                                               "text": "wrong note"}, key="crit-1")
        [entry] = sop.trend(j)["procedures"]
        assert entry["baseline"]["interventions_per_outcome"] == 1.0
        if expect is None:
            assert entry["compounding"] is True and entry["sop_runs"]["interventions_per_outcome"] == 0.0
            assert entry["sop_runs"]["model_calls_per_outcome"] == 0.0
            assert len(sop.propose(j)) == 0            # runs of an SOP are measurements, not new proposals
        else:
            assert entry["compounding"] is False and any(expect in w for w in entry["why_not"]), entry["why_not"]
        if case in ("doctored", "long_mandate"):
            assert len(entry["sop_runs"]["claimed_but_not_instantiating"]) == 1
        result = devpath.sop_compounding(j)               # a crafted ledger is never body evidence
        assert result["met"] is False
        missing = result["incomplete"][0]["missing"]
        if expect is None:
            assert missing == ["sop_run_not_founder_body", "sop_run_not_interface_detached",
                               "sop_run_not_persistent_runtime", "sop_run_not_real_capability"]
        else:
            assert any(expect in m for m in missing)


def test_pre_approval_is_limited_to_steps_approved_in_every_verified_run(tmp_path):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        j = body.journal
        closure(j, note_mission(home, "m:note-0", "done 0"))
        closure(j, note_mission(home, "m:note-1", "done 1"))
        closure(j, note_mission(home, "m:note-2", "done 2"), approvals=())   # this run never asked
        [proposal] = sop.propose(j)
        assert proposal["pre_approvable"] == []
        with pytest.raises(ValueError, match="only steps you approved in every verified run"):
            sop.ratify(j, {"procedure_id": proposal["procedure_id"], "pre_approve": ["w"]}, "sha256:r")
        record = sop.ratify(j, {"procedure_id": proposal["procedure_id"]}, "sha256:r")
        spec = sop.instantiate(record, {"text": "x"})
        assert spec["light_cone"]["capabilities"] == ["fs.read"]            # nothing widened without consent
        assert spec["light_cone"]["max_consequence_class"] == "read_only"


# -- the body: N4 closes only after three runs from the ratified SOP -------------------------

def tick(body, clock, ticks=3):
    for _ in range(ticks):
        body.tick()
        clock.advance(1)


def asks(body, mid):
    return [e.payload for e in body.journal.replay("decision.requested") if e.payload["mission_id"] == mid]


def achieved(body, mid):
    return any(e.payload["mission_id"] == mid for e in body.journal.replay("mission.achieved"))


def test_a_ratified_procedure_runs_without_a_model_or_an_approval_stop_and_closes_n4(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    body = Body(home, clock=clock).open()
    body.boot()
    try:
        drop(home, signed(key, body_id, "BODY_DESIGNATE", {"purpose": "first_founder_body"}, now=clock.now))
        tick(body, clock, 1)
        for n in range(3):                              # three runs taught by hand: each stops to ask
            mid = f"m:weekly-note-{n}"
            drop(home, signed(key, body_id, "MISSION", note_mission(home, mid, f"done {n}"), now=clock.now))
            tick(body, clock)
            [ask] = asks(body, mid)
            assert ask["kind"] == "APPROVAL" and ask["action_id"] == "w"
            drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"},
                              now=clock.now))
            tick(body, clock, 4)
            assert achieved(body, mid)
        [proposal] = [e.payload for e in body.journal.replay("sop.proposed")]
        assert list(proposal["workflow"]["slots"]) == ["text"]
        assert [s["action_id"] for s in proposal["pre_approvable"]] == ["w"]
        assert devpath.sop_compounding(body.journal)["incomplete"][0]["missing"] == ["not ratified"]

        drop(home, signed(key, body_id, "SOP_RATIFY", {"procedure_id": proposal["procedure_id"],
                                                       "pre_approve": ["file-everything"]}, now=clock.now))
        tick(body, clock, 1)
        assert not body.journal.replay("sop.ratified") and body.journal.replay("command.rejected")
        drop(home, signed(key, body_id, "SOP_RATIFY", {"procedure_id": proposal["procedure_id"],
                                                       "pre_approve": ["w"]}, now=clock.now))
        tick(body, clock, 1)
        record = sop.ratified(body.journal)[proposal["procedure_id"]]["record"]

        for n in range(3):                              # three runs from the SOP: signed, never asked
            spec = sop.instantiate(record, {"text": f"from the sop {n}"}, now=clock.now)
            drop(home, signed(key, body_id, "MISSION", spec, now=clock.now))
            tick(body, clock, 4)
            assert achieved(body, spec["mission_id"]) and asks(body, spec["mission_id"]) == []
            assert (workspace(home, spec["mission_id"]) / "n.txt").read_text() == f"from the sop {n}"
            measured = devpath.sop_compounding(body.journal)
            assert measured["met"] is (n == 2), measured
        [done] = measured["procedures"]
        assert done["before"]["interventions_per_outcome"] == 1.0 and done["after"]["interventions_per_outcome"] == 0.0
        assert done["after"]["model_calls_per_outcome"] == 0.0 and done["after"]["quality_failures"] == []
        assert len(body.journal.replay("sop.proposed")) == 1
        where = devpath.position(body.journal)      # N4 measured does not skip the path: N1 stays primary
        assert where["active"]["id"] == "N1" and "N4" not in where["achieved"]
        # but the founder sees that it is met: measured ahead, not achieved
        assert where["met_ahead"] == [{"id": "N4", "title": next(n["title"] for n in devpath.load()["nodes"]
                                                                  if n["id"] == "N4")}]
        assert status(home)["developmental_position"]["met_ahead"] == ["N4"]
    finally:
        body.close()


def test_n4_is_wired_to_its_ledger_predicate_and_unmet_on_an_empty_ledger(tmp_path):
    node = next(n for n in devpath.load()["nodes"] if n["id"] == "N4")
    assert node["predicate"] == "sop_compounding" and node["predicate"] in devpath.PREDICATES
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        empty = devpath.sop_compounding(body.journal)
    assert empty["met"] is False and "three verified closures" in empty["missing"][0]


# -- measurement surfaces ----------------------------------------------------------------------

def test_the_planner_records_model_calls_and_cost_and_the_morning_report_counts_them(tmp_path):
    from greg import models
    from tests.unit.test_greg_interface import GOOD as DRAFT, inventory
    from tests.unit.test_greg_models import FakeAnthropic, FakeOpenAI
    ctx = planner.PlannerContext(read_roots=(), capabilities=inventory(), repositories={}, today="2026-10-13")
    router = models.ModelRouter([models.AnthropicRoute("k", client=FakeAnthropic(TimeoutError("slow"))),
                                 models.OpenAIRoute("k", client=FakeOpenAI(json.dumps(DRAFT)), price=(1.0, 4.0))])
    prov = planner.model_route("watch my notes", ctx, router)["spec"]["provenance"]
    assert prov["model_calls"] == 1 and prov["model_cost_usd"] == pytest.approx(0.009)

    class Legacy:                                       # a transport that reports no cost
        name = "legacy"

        def complete(self, system, user):
            return json.dumps(DRAFT)
    legacy = planner.model_route("watch my notes", ctx, Legacy())["spec"]
    assert legacy["provenance"]["model_calls"] == 1 and "model_cost_usd" not in legacy["provenance"]

    home, *_ = make_body(tmp_path)
    drafted = validate_mission({**planner.model_route("watch my notes", ctx, models.ModelRouter(
        [models.OpenAIRoute("k", client=FakeOpenAI(json.dumps(DRAFT)), price=(1.0, 4.0))]))["spec"]})
    with Body(home) as body:
        body.journal.record("mission.registered", {"mission_id": drafted["mission_id"], "spec": drafted,
                                                   "command_digest": "sha256:x"}, key=drafted["mission_id"])
        body.journal.record("mission.registered", {"mission_id": legacy["mission_id"] + "-2",
                                                   "spec": {**legacy, "mission_id": legacy["mission_id"] + "-2"},
                                                   "command_digest": "sha256:y"}, key="legacy")
        body.journal.record("model.route", {"route": "openai:gpt-5.5", "provider": "openai", "outcome": "failed",
                                            "at": "2026-10-13T00:00:00Z", "why": "timeout"}, key="r1")
        metrics = morning_report(body.journal)["metrics"]
    assert metrics["model_calls"] == 2 and metrics["model_cost_usd"] == pytest.approx(0.009)
    assert metrics["model_route_attempts_recorded"] == 1            # a failed attempt tied to no mission still counts
    assert metrics["model_cost_known"] is False                    # the legacy draft's cost is unknown, not zero


def test_the_cli_shows_ratifies_and_runs_a_procedure(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        for n in range(3):
            closure(body.journal, note_mission(home, f"m:note-{n}", f"done {n}"))
        [proposal] = sop.propose(body.journal)
    pid = proposal["procedure_id"]
    keyfile = str(tmp_path / "founder.pem")
    from greg.console import Console, render_morning
    page = render_morning(Console(home)).decode()          # the morning page shows what waits for you
    assert "sops_awaiting_ratification" in page and f"greg sop ratify {pid}" in page

    def cli(*args):
        out = subprocess.run([sys.executable, "-m", "greg", "--home", str(home), "sop", *args], capture_output=True,
                             text=True, cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)}, timeout=60)
        return out.returncode, (json.loads(out.stdout) if out.returncode == 0 else out.stderr + out.stdout)

    code, listed = cli("list")
    assert code == 0 and listed["awaiting_ratification"][0]["slots"] == ["text"]
    assert listed["awaiting_ratification"][0]["pre_approvable"] == ["w"]
    code, why = cli("run", pid, "--set", "text=x", "--print-only")
    assert code != 0 and "not ratified" in why
    code, why = cli("ratify", pid, "--pre-approve", "x", "--key", keyfile, "--no-passphrase")
    assert code != 0 and "only these steps can be pre-approved" in why
    code, dropped = cli("ratify", pid, "--pre-approve", "w", "--key", keyfile, "--no-passphrase")
    assert code == 0 and Path(dropped["dropped"]).exists()
    clock = Clock()
    body = Body(home, clock=clock).open()
    body.boot()
    try:
        body.tick()
    finally:
        body.close()
    code, why = cli("run", pid, "--set", "words=3", "--print-only")
    assert code != 0 and "SLOT=VALUE" in why
    code, shown = cli("run", pid, "--set", "text=from the cli", "--print-only")
    assert code == 0 and shown["mission"]["strategies"][0]["params"]["content"] == "from the cli"
    assert any(line.startswith("w: fs.write") for line in shown["signing_lets_greg"]["may_do_without_asking"])
    assert shown["signing_lets_greg"]["must_ask_you_first"] == []
    code, measured = cli("trend")
    assert code == 0 and measured["procedures"][0]["state"] == "RATIFIED"


def test_a_run_signed_before_ratification_is_not_counted(tmp_path):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        j = body.journal
        for n in range(3):
            closure(j, note_mission(home, f"m:note-{n}", f"done {n}"))
        [proposal] = sop.propose(j)
        early = {"procedure_id": proposal["procedure_id"], "command_digest": "sha256:ratify",
                 "workflow": proposal["workflow"], "pre_approved_steps": proposal["pre_approvable"]}
        closure(j, sop.instantiate(early, {"text": "too early"}), approvals=())   # claims the SOP before it exists
        record = sop.ratify(j, {"procedure_id": proposal["procedure_id"], "pre_approve": ["w"]}, "sha256:ratify")
        for n in range(2):
            closure(j, sop.instantiate(record, {"text": f"run {n}"}), approvals=())
        [entry] = sop.trend(j)["procedures"]
    assert entry["compounding"] is False and "2 of 3 verified runs from the SOP" in entry["why_not"][0]
    assert len(entry["sop_runs"]["claimed_but_not_instantiating"]) == 1


@pytest.mark.parametrize("approved_class, approved_cost", [("external_contact", 0.0), ("internal_write", 1.5)])
def test_contact_with_the_world_or_spend_is_never_pre_approvable(tmp_path, approved_class, approved_cost):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        for n in range(3):
            closure(body.journal, note_mission(home, f"m:note-{n}", f"done {n}"), approved_class=approved_class,
                    approved_cost=approved_cost)
        [proposal] = sop.propose(body.journal)
    assert proposal["pre_approvable"] == []           # approved three times, still asks every run


def test_a_value_seen_in_only_some_runs_is_not_derived_from_it(tmp_path):
    specs = [note_mission(tmp_path, f"m:note-{n}", f"done {n}") for n in range(3)]
    for n, words in enumerate(("filed after done 0", "filed after done 1", "filed late")):
        specs[n]["strategies"][0]["rationale"] = words
    workflow = sop.generalize(specs)
    assert set(workflow["slots"]) == {"text", "rationale"}   # not "filed after {text}", which run 2 contradicts


def test_a_workflow_that_cannot_reproduce_its_own_runs_is_refused(tmp_path, monkeypatch):
    specs = [note_mission(tmp_path, f"m:note-{n}", f"done {n}") for n in range(3)]
    monkeypatch.setattr(sop, "_derive", lambda values, env: "{mission_id}")  # a faulty derivation
    with pytest.raises(sop.SopError, match="does not reproduce"):
        sop.generalize(specs)


def test_a_procedure_without_a_workflow_says_why_it_cannot_run(tmp_path):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        j = body.journal
        specs = [note_mission(home, f"m:note-{n}", f"done {n}") for n in range(3)]
        specs[2]["unacceptable_outcomes"] = ["the note is lost"]     # differs, and is no parameter
        for spec in specs:
            closure(j, spec)
        assert sop.propose(j) == []                       # two signed shapes: not one procedure of three
        legacy = {"procedure_id": "sop-ffffffffffffffff", "steps": ["fs.write"], "occurrences": 3,
                  "missions": [s["mission_id"] for s in specs], "state": "PROPOSED"}   # recorded before workflows
        j.record("sop.proposed", legacy, key=legacy["procedure_id"])
        record = sop.ratify(j, {"procedure_id": legacy["procedure_id"]}, "sha256:r")
        assert "workflow" not in record
        with pytest.raises(sop.SopError, match="carries no workflow"):
            sop.instantiate(record, {})
        [entry] = sop.trend(j)["procedures"]
    assert entry["compounding"] is False
    assert entry["why_not"][0] == "no workflow to run: ratified before workflows existed"
