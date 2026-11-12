"""The intake recommendation as an ordinary signed mission: Body -> MissionEngine -> Gate -> file -> appraiser.

Founder requirement of 2026-11-12: "Make GREG useful to its own development first." These tests run the mission
through GREG's real entry point: a founder-signed MISSION dropped in the body's inbox, the engine's own observation
and dispatch, the Consequence Gate's receipt, the delivered file, and the appraiser in its separate process. The
founder key is a per-test key (not Alfonso's); the repository is the small real one of ``tests/intake_fixtures.py``.

The first test runs the heads' tests with real pytest inside the real worker envelope (the ``supervised`` floor on a
host without bubblewrap). The others are about the engine, so ``Script`` stands in for the envelope's test run.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from greg import briefs, intake, workers
from greg.body import Body, Layout
from greg.templates import intake_recommendation
from greg.worker_isolation import WorkerIsolationError
from tests.greg_fixtures import Clock, drop, host_worker_confinement, make_body, signed
from tests.intake_fixtures import TOTAL, Script, breaks_with_steeper, build_repo, state


def start(tmp_path, *, confinement="required"):
    home, key, body_id, data = make_body(tmp_path, worker_confinement=confinement)
    repo = data / "repo"
    shas = build_repo(repo)
    return home, key, body_id, repo, shas


def spec_for(repo, shas, names, **more) -> dict:
    return intake_recommendation(repository=str(repo), base=shas["base"],
                                 units=[{"name": n, "sha": shas[n]} for n in names], **more)


def ticks(body, clock, n=1) -> list[str]:
    states = []
    for _ in range(n):
        clock.advance(30)
        report = body.tick()
        states.append(report["missions"][0]["state"] if report["missions"] else "NONE")
    return states


def state_of(body, mission_id: str, clock) -> str:
    clock.advance(30)
    return next(m["state"] for m in body.tick()["missions"] if m["mission_id"] == mission_id)


def open_requests(body) -> list[dict]:
    body.engine.book.rebuild()
    return body.engine.book.open_requests()


def recommendations(home) -> list[Path]:
    return sorted((Layout(home).home / "deliveries" / "briefs").glob("*-intake-brief*.md"))


def actions(body, mission_id: str) -> list[tuple[str, str]]:
    return [(e.payload["action_id"], e.payload["status"]) for e in body.journal.replay("mission.action")
            if e.payload["mission_id"] == mission_id]


def appraisals(body, mission_id: str) -> list[dict]:
    return [e.payload for e in body.journal.replay("mission.appraised") if e.payload["mission_id"] == mission_id]


def test_the_mission_stops_for_approval_delivers_once_reobserves_closes_and_is_appraised(tmp_path):
    """Real pytest in the real envelope, through the whole path. ``steeper`` and ``consumer`` merge cleanly and
    break ``consumer``'s test; the delivered recommendation holds both and says why."""
    home, key, body_id, repo, shas = start(tmp_path, confinement=host_worker_confinement())
    claims = {"consumer": {"head_sha": shas["consumer"], "validation": [
        {"command": "pytest tests/test_total.py", "result": "pass", "evidence": "local run"}],
        "checks": [{"name": "ci", "head_sha": shas["consumer"], "conclusion": "success"}]}}
    spec = spec_for(repo, shas, ["steeper", "consumer", "label"], claims=claims, timeout_seconds=120)
    assert spec["light_cone"]["max_consequence_class"] == "read_only" and "brief.intake" not in \
        spec["light_cone"]["capabilities"]
    before = state(repo)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert ticks(body, clock) == ["WAITING"]                            # the delivery is outside the read-only cone
        [request] = open_requests(body)
        assert request["kind"] == "APPROVAL" and request["authority_requested"]["capability"] == "brief.intake"
        assert recommendations(home) == [] and actions(body, spec["mission_id"]) == []
        observed = [e.payload for e in body.journal.replay("mission.observed")]
        assert observed and not observed[-1]["passed"] and observed[-1]["capability"] == "brief.intake_status"

        drop(home, signed(key, body_id, "DECISION", {"request_id": request["request_id"], "answer": "approve"}))
        assert ticks(body, clock, 2) == ["ACTED", "ACHIEVED"]               # delivered, then re-observed and closed
        [delivered] = recommendations(home)
        assert state(repo) == before, "the mission changed the repository it reads"
        assert actions(body, spec["mission_id"]) == [("deliver-intake-recommendation", "DONE")]
        done = [e.payload for e in body.journal.replay("mission.action") if e.payload["status"] == "DONE"]
        output = body.ledger.find(done[0]["receipt"]).payload["result"]["output"]
        text = delivered.read_text()
        assert intake.render(output["inputs"]) == text                       # the file is f(receipted inputs)
        assert output["request_digest"] == spec["success_checks"][0]["sensor"]["params"]["request_digest"]
        assert output["recommendations"]["label"] == "ready to take"
        assert output["recommendations"]["consumer"].startswith("hold: behavioural conflict: its test "
                                                                "tests/test_total.py::test_total")
        assert output["recommendations"]["steeper"].startswith("hold: behavioural conflict: merging it breaks consumer")
        assert "Cause: **steeper**; passes when this head is left out." in text
        assert '"pytest tests/test_total.py" (claimed: pass): **re-executed here: same result**' in text
        assert output["checks"] == {"ran": True, "why": None}
        assert "refused" not in output["inputs"]["confinement"]["modes"]
        assert intake.BOUNDARY in text

        # the independent appraiser's verdict on this closure, as the body recorded it
        [appraisal] = appraisals(body, spec["mission_id"])
        assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
        for check in ("deliveries_bound_to_evidence", "world_reobserved", "checks_rederived_from_receipts",
                      "exactly_once", "approval_boundaries_honored", "approval_boundary_encountered",
                      "closure_evidence_bound", "founder_signature_verified"):
            assert appraisal["checks"][check] is True, (check, appraisal["findings"])
        assert appraisal["findings"] == []

        # an edit after delivery is caught by the same appraiser
        delivered.write_text(text.replace("hold: behavioural conflict", "ready to take"))
        verdict = body.appraise(spec["mission_id"])
        assert verdict["verdict"] == "REFUTED"
        assert any("differs from the render of the receipted inputs" in f for f in verdict["findings"])
        assert verdict["checks"]["deliveries_bound_to_evidence"] is False
        assert verdict["checks"]["world_reobserved"] is False               # the sensor no longer counts the edited file
        assert len(recommendations(home)) == 1


def test_a_recommendation_about_other_heads_does_not_close_this_mission(tmp_path, monkeypatch):
    monkeypatch.setattr(workers, "run_tests", Script())
    home, key, body_id, repo, shas = start(tmp_path)
    first = spec_for(repo, shas, ["label"], preauthorize_delivery=True)
    second = spec_for(repo, shas, ["consumer"])                              # other heads; delivery needs approval
    assert first["mission_id"] != second["mission_id"]
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        drop(home, signed(key, body_id, "MISSION", first))
        assert ticks(body, clock, 2) == ["ACTED", "ACHIEVED"]
        assert len(recommendations(home)) == 1                               # a fresh recommendation exists ...
        drop(home, signed(key, body_id, "MISSION", second))
        assert state_of(body, second["mission_id"], clock) == "WAITING"     # ... and it closes nothing here
        seen = [e.payload for e in body.journal.replay("mission.observed")
                if e.payload["mission_id"] == second["mission_id"]]
        assert seen and not any(o["passed"] for o in seen)
        reading = body.ledger.find(seen[-1]["receipt"]).payload["result"]["output"]
        assert reading["matching"] == 0 and reading["for_other_requests"] == 1
        [request] = [r for r in open_requests(body) if r["mission_id"] == second["mission_id"]]
        assert request["kind"] == "APPROVAL"
        drop(home, signed(key, body_id, "DECISION", {"request_id": request["request_id"], "answer": "approve"}))
        states = [state_of(body, second["mission_id"], clock) for _ in range(2)]
        assert states == ["ACTED", "ACHIEVED"] and len(recommendations(home)) == 2
        assert [a["verdict"] for a in appraisals(body, first["mission_id"]) + appraisals(body, second["mission_id"])] \
            == ["VERIFIED", "VERIFIED"]
        # the same selection signed again is the same mission id: the body does not register it twice
        assert spec_for(repo, shas, ["consumer"])["mission_id"] == second["mission_id"]


def test_an_interrupted_delivery_is_reconciled_and_exactly_one_file_is_delivered(tmp_path, monkeypatch):
    """The process dies after the rehearsal's scratch work and before the file. The dispatch is recorded UNCERTAIN,
    never retried blind: the founder is asked once, answers that it did not execute, and one file is delivered."""
    monkeypatch.setattr(workers, "run_tests", Script({TOTAL: breaks_with_steeper}))
    home, key, body_id, repo, shas = start(tmp_path)
    spec = spec_for(repo, shas, ["steeper", "consumer"], preauthorize_delivery=True)
    real, calls = briefs.deliver, []

    def power_lost_once(text, ctx, **kw):
        calls.append(len(text))
        if len(calls) == 1:
            raise RuntimeError("power lost before the file was written")
        return real(text, ctx, **kw)
    monkeypatch.setattr(briefs, "deliver", power_lost_once)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert ticks(body, clock, 3) == ["BLOCKED", "WAITING", "WAITING"]   # truthful: it does not know, and waits
        assert actions(body, spec["mission_id"]) == [("deliver-intake-recommendation", "UNCERTAIN")]
        assert recommendations(home) == [] and len(calls) == 1               # nothing delivered, nothing retried
        workspace = Layout(home).workspace / spec["mission_id"].replace(":", "_")
        assert not (workspace / "intake-scratch").exists()                   # the scratch work was removed
        [request] = open_requests(body)
        assert request["kind"] == "RECONCILIATION" and request["action_id"] == "deliver-intake-recommendation"
        drop(home, signed(key, body_id, "DECISION", {"request_id": request["request_id"],
                                                     "answer": "reconcile_not_executed", "reason": "no file exists"}))
        states = ticks(body, clock, 4)
        assert "ACHIEVED" in states, states
        assert len(recommendations(home)) == 1 and len(calls) == 2           # exactly one file in the end
        assert [s for _, s in actions(body, spec["mission_id"])].count("DONE") == 1
        twins = sorted((Layout(home).home / "deliveries" / "briefs").glob("*.json"))
        assert len(twins) == 1 and json.loads(twins[0].read_text())["request_digest"] == \
            spec["success_checks"][0]["sensor"]["params"]["request_digest"]
        [verdict] = appraisals(body, spec["mission_id"])
        assert verdict["verdict"] == "VERIFIED" and verdict["findings"] == [], verdict["findings"]
        assert verdict["checks"]["exactly_once"] is True and verdict["checks"]["deliveries_bound_to_evidence"] is True


def test_a_refused_request_leaves_no_file_and_the_mission_says_it_cannot_proceed(tmp_path, monkeypatch):
    """The capability refuses (a revision that is not in the repository). Nothing is delivered, the refusal has a
    receipt, and the mission asks the founder instead of closing or retrying."""
    monkeypatch.setattr(workers, "run_tests", Script())
    home, key, body_id, repo, shas = start(tmp_path)
    spec = spec_for(repo, {**shas, "label": "f" * 40}, ["label"], preauthorize_delivery=True)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        states = ticks(body, clock, 3)
        assert "ACHIEVED" not in states and states[-1] in ("BLOCKED", "WAITING"), states
        assert recommendations(home) == []
        refused = [e.payload for e in body.journal.replay("mission.action")
                   if e.payload["mission_id"] == spec["mission_id"] and e.payload["status"] == "REFUSED"]
        assert len(refused) == 1 and "is not in this repository" in " ".join(refused[0]["reasons"])
        assert [r["kind"] for r in open_requests(body)] == ["NO_STRATEGY"]
        assert appraisals(body, spec["mission_id"]) == []                    # nothing closed, nothing to appraise


def test_under_required_with_no_envelope_the_delivered_recommendation_says_nothing_ran(tmp_path, monkeypatch):
    """The body's default setting is ``required``. On a host that cannot provide the envelope, the heads' tests are
    refused, exactly as a worker's acceptance tests are: the mission still delivers a recommendation, and it says
    for every unit that its checks did not run. No unit is ready. The founder's other choice, ``supervised``, is a
    body setting; the capability does not make it."""
    def no_envelope(*args, **kwargs):
        raise WorkerIsolationError("worker OS filesystem isolation unavailable: bubblewrap is unavailable on this host",
                                   evidence={"status": "unsupported", "reason": "bubblewrap is unavailable"})
    monkeypatch.setattr(workers, "prepare_worker", no_envelope)
    monkeypatch.setattr("greg.worker_isolation.host_has_envelope", lambda: False)
    home, key, body_id, repo, shas = start(tmp_path, confinement="required")
    spec = spec_for(repo, shas, ["steeper", "consumer"], preauthorize_delivery=True)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert ticks(body, clock, 2) == ["ACTED", "ACHIEVED"]
        [delivered] = recommendations(home)
        text = delivered.read_text()
        done = [e.payload for e in body.journal.replay("mission.action") if e.payload["status"] == "DONE"]
        output = body.ledger.find(done[0]["receipt"]).payload["result"]["output"]
        assert output["checks"] == {"ran": False, "why": "not run: envelope unavailable"}
        assert output["counts"]["ready"] == 0 and output["counts"]["not_checked"] == 2
        assert output["counts"]["test_runs"] == {"passed": 0, "failed": 0, "timed_out": 0, "not_run": 4, "errored": 0}
        assert all(r.startswith("not checked: ") and "envelope unavailable" in r
                   for r in output["recommendations"].values())
        assert "**The checks were NOT run (envelope unavailable).**" in text and "| passed |" not in text
        assert output["inputs"]["confinement"]["body_setting"] == "required"
        assert output["inputs"]["confinement"]["modes"] == ["refused"]
        assert output["inputs"]["rehearsal"]["behavioural_conflicts"] == []  # none measured; the file says none could be
        assert "None could be measured: no test ran." in text
        assert appraisals(body, spec["mission_id"])[-1]["verdict"] == "VERIFIED", \
            appraisals(body, spec["mission_id"])[-1]["findings"]


def test_the_founders_command_drafts_and_signs_the_mission_and_the_body_runs_it(tmp_path, monkeypatch, capsys):
    """``greg mission new intake-recommendation --intake FILE``: the ordinary way in. The command validates the
    request, signs the mission with the founder's key and drops it in the inbox; the body does the rest."""
    from greg import cli
    monkeypatch.setattr(workers, "run_tests", Script())
    home, _, _, repo, shas = start(tmp_path)
    key, asked = tmp_path / "founder.pem", tmp_path / "request.json"
    asked.write_text(json.dumps({"repository": str(repo), "base": shas["base"],
                                 "units": [{"name": "label", "sha": shas["label"]}], "timeout_seconds": 60}))
    base = ["--home", str(home), "mission", "new", "intake-recommendation", "--key", str(key), "--no-passphrase"]
    assert cli.main(base) == 2 and "needs --intake" in capsys.readouterr().err
    short = tmp_path / "short.json"
    short.write_text(json.dumps({"repository": str(repo), "base": "base", "units": [{"name": "label", "sha": "label"}]}))
    assert cli.main(base + ["--intake", str(short)]) == 2
    assert "full 40-character commit SHA" in capsys.readouterr().err
    extra = tmp_path / "extra.json"
    extra.write_text(json.dumps({**json.loads(asked.read_text()), "approve": True}))
    assert cli.main(base + ["--intake", str(extra)]) == 2 and "must hold repository, base and units" in \
        capsys.readouterr().err
    assert list((Path(home) / "inbox").glob("*.json")) == []                 # a refused request signs nothing
    assert cli.main(base + ["--intake", str(asked), "--print-only"]) == 0
    spec = json.loads(capsys.readouterr().out)
    assert spec["mission_id"].startswith("m:intake-") and spec["light_cone"]["max_consequence_class"] == "read_only"
    assert cli.main(base + ["--intake", str(asked), "--preauthorize-delivery"]) == 0
    capsys.readouterr()
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert ticks(body, clock, 2) == ["ACTED", "ACHIEVED"]
        assert len(recommendations(home)) == 1
        [verdict] = appraisals(body, spec["mission_id"])
        assert verdict["verdict"] == "VERIFIED", verdict["findings"]
