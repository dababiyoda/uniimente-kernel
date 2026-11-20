"""Capability readiness ladder (directive section 32): KNOWN, INSTALLED, CREDENTIALLED, GRANTED, EXERCISED, VERIFIED.

Every fixture is a real body: a real Ed25519 test key (not Alfonso's), founder-signed missions, receipts produced by
the real Kernel Gate, and every VERIFIED and REFUTED verdict recorded by the body's separate appraiser process. Seven
kinds of fact are also recorded directly, in the fields their one writer gives them, where producing them for real is
not what is under test:

- ``mission.action`` DONE records, written by ``_act_through_gate`` after a real AuthorityOffice and Gate act (the engine
  writes them in greg/missions.py; the attribution of receipts to closures depends on them);
- ``mission.achieved`` and ``mission.unmet`` closure claims the engine did not make, for the real appraiser to judge;
- ``mission.appraised`` VERIFIED_UNMET and UNAVAILABLE rows (greg/appraisal.py ``_verdict``, greg/body.py);
- ``routing.outcome`` rows (greg/missions.py ``_record_routing_outcomes``), one of them with a verdict no writer gives;
- ``capability.registered`` and ``capability.state`` (greg/genesis.py).

Elsewhere the engine's own tick writes them. The planted secret value is a test string; no real credential is used.
"""
from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path

import pytest

from greg import cli, routing
from greg.body import Body, Layout, status
from greg.capabilities import BUILTINS, CapabilityManifest, SecretBroker
from greg.mission_control import classify_capability
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy

PLANTED = "planted-secret-value-7f3a91c2-never-printed"
NO_PROVIDERS: dict = {}


class _Readiness:
    """greg.readiness, imported when a test runs, so a body without the module fails each test, not collection."""

    def __getattr__(self, name):
        from greg import readiness as module
        return getattr(module, name)


readiness = _Readiness()


def _row(report: dict, cid: str) -> dict:
    return next(row for row in report["capabilities"] if row["capability_id"] == cid)


def _cli(home: Path, *args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(["--home", str(home), "readiness", *args])
    return code, out.getvalue(), err.getvalue()


def _note_mission(home: Path, mid: str, text: str = "hello", capabilities=("fs.read", "fs.write"), **kw) -> dict:
    ws = workspace(home, mid)
    return mission(mid, checks=[note_check("n", ws / "n.txt", text)],
                   strategies=[write_strategy("w", "n.txt", text, ["n"])], capabilities=list(capabilities), **kw)


def _run_to_closure(home: Path, key, body_id: str, mid: str, text: str = "hello") -> None:
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        drop(home, signed(key, body_id, "MISSION", _note_mission(home, mid, text), now=clock.now))
        for _ in range(6):
            body.tick()
            clock.advance(1)
    verdicts = _verdicts(home, mid)
    assert verdicts == ["VERIFIED"], verdicts


def _verdicts(home: Path, mid: str) -> list:
    from greg.body import observe
    with observe(home) as journal:
        return [e.payload["verdict"] for e in journal.replay("mission.appraised") if e.payload["mission_id"] == mid]


def _act_through_gate(body: Body, mid: str, capability: str, params: dict, target: str, *, action_id: str = "w") -> str:
    """One action through the real AuthorityOffice and Gate for an open mission. Its ``mission.action`` DONE record is
    written here, in the fields the engine writes (greg/missions.py), because the tick is not what is under test."""
    state = body.engine.book.missions[mid]
    manifest, adapter, _ = body.engine._resolve({"capability": capability})
    outcome = body.office.act(
        mission_id=mid, cone=state.cone, command_digest=state.command_digest, manifest=manifest, adapter=adapter,
        ctx=body.engine._context(state, manifest), params=params, target=target, cost_usd=0.0,
        expected_outcome="strategy executed", evidence_refs=[], attempt=0, spent_usd=0.0, approved_scopes=set())
    assert outcome.status == "DONE", outcome.reasons
    body.journal.record("mission.action", {
        "mission_id": mid, "action_id": action_id, "attempt": 0, "status": "DONE", "capability": capability,
        "receipt": outcome.receipt_hash, "scope_digest": outcome.scope_digest}, key=[mid, action_id, 0])
    return outcome.receipt_hash


def _write_through_gate(body: Body, mid: str, *, content: str = "done") -> str:
    return _act_through_gate(body, mid, "fs.write", {"relative_path": "n.txt", "content": content}, "workspace:n.txt")


# -- fail-before: the command did not exist --------------------------------------------------------------------------

def test_greg_readiness_prints_the_ladder_as_json(tmp_path):
    home, _key, _body_id, _ = make_body(tmp_path)
    code, out, _err = _cli(home)
    assert code == 0
    report = json.loads(out)
    assert report["rungs"] == ["KNOWN", "INSTALLED", "CREDENTIALLED", "GRANTED", "EXERCISED", "VERIFIED"]
    assert report["summary"]["capabilities"] == len(BUILTINS)
    code, out, _err = _cli(home, "--capability", "fs.write", "--capability", "github.pulls")
    assert code == 0
    assert [r["capability_id"] for r in json.loads(out)["capabilities"]] == ["fs.write", "github.pulls"]


# -- a fresh body: KNOWN and INSTALLED only --------------------------------------------------------------------------

def test_a_fresh_body_reads_known_and_installed_only(tmp_path):
    home, _key, _body_id, _ = make_body(tmp_path)
    report = readiness.report(home)
    for row in report["capabilities"]:
        manifest = BUILTINS[row["capability_id"]][0]
        assert set(row["reached"]) <= {"KNOWN", "INSTALLED"}, row
        assert row["rungs"]["KNOWN"]["status"] == "reached"
        assert (row["rungs"]["INSTALLED"]["status"] == "reached") == manifest.available()[0], row
        assert row["rungs"]["CREDENTIALLED"]["status"] == ("missing" if manifest.credentials else "not_applicable")
        for rung in ("GRANTED", "EXERCISED", "VERIFIED"):
            assert row["rungs"][rung]["status"] == "missing", (row["capability_id"], rung)
        assert row["first_missing"] in ("INSTALLED", "CREDENTIALLED", "GRANTED") and row["why"]
    assert {r: report["summary"]["reached"][r] for r in ("CREDENTIALLED", "GRANTED", "EXERCISED", "VERIFIED")} \
        == {"CREDENTIALLED": 0, "GRANTED": 0, "EXERCISED": 0, "VERIFIED": 0}
    pulls = _row(report, "github.pulls")
    assert pulls["first_missing"] == "CREDENTIALLED" and "github_token" in pulls["why"]
    unattached = _row(report, "cognition.graph")               # catalog state VERIFIED: never attached by default
    assert unattached["lifecycle_state"] == "VERIFIED" and "attaching it is the founder's decision" in unattached["why"]


def test_mission_control_classes_are_the_same_reader(tmp_path):
    """Parity: each row carries the class Mission Control's own classifier gives the body.status row."""
    home, _key, _body_id, _ = make_body(tmp_path)
    from greg.body import observe
    with observe(home) as journal:
        report = readiness.ladder(journal, secrets=SecretBroker(Layout(home).secrets), providers=NO_PROVIDERS)
    expected = {c["capability_id"]: classify_capability(c, NO_PROVIDERS)["class"] for c in status(home)["capabilities"]}
    assert {r["capability_id"]: r["mission_control_class"] for r in report["capabilities"]} == expected


# -- CREDENTIALLED: names only; values never leave the store -----------------------------------------------------------

def test_a_stored_handle_without_a_grant_stops_at_credentialled(tmp_path):
    home, _key, _body_id, _ = make_body(tmp_path)
    SecretBroker(Layout(home).secrets).put("github_token", PLANTED)
    report = readiness.report(home)
    pulls = _row(report, "github.pulls")
    assert pulls["reached"] == ["KNOWN", "INSTALLED", "CREDENTIALLED"]
    assert pulls["first_missing"] == "GRANTED"
    assert pulls["rungs"]["CREDENTIALLED"]["evidence"] == [{"kind": "stored_handle", "ref": "github_token"}]
    # Mission Control reads BLOCKED for any declared credential; the difference is reported, not smoothed over.
    assert any(d["capability_id"] == "github.pulls" and "BLOCKED" in d["detail"] for d in report["disagreements"])


def test_a_secret_value_never_appears_in_the_output(tmp_path):
    home, _key, _body_id, _ = make_body(tmp_path)
    broker = SecretBroker(Layout(home).secrets)
    broker.put("github_token", PLANTED)
    broker.put("unrelated_handle", PLANTED + "-2")
    for args in ((), ("--capability", "github.pulls"), ("--capability", "brief.engineering")):
        code, out, err = _cli(home, *args)
        assert code == 0
        assert "github_token" in out                      # the handle's name is the evidence
        assert PLANTED not in out and PLANTED not in err
    assert PLANTED not in json.dumps(readiness.report(home))


@pytest.mark.parametrize("content,mode", [(json.dumps({"github_token": PLANTED}), 0o644), ("null", 0o600),
                                          ("[1, 2]", 0o600)])
def test_an_unreadable_secret_store_is_reported_not_guessed(tmp_path, content, mode):
    """Review finding F4: a store the broker refuses (not 0600), or one that is not a mapping of names, reads
    CREDENTIALLED missing with the reason; it is never read as empty, never crashes the command, never prints."""
    home, _key, _body_id, _ = make_body(tmp_path)
    path = Layout(home).secrets
    path.write_text(content)
    os.chmod(path, mode)
    code, out, err = _cli(home, "--capability", "github.pulls")
    assert code == 0 and PLANTED not in out and PLANTED not in err
    credentialled = json.loads(out)["capabilities"][0]["rungs"]["CREDENTIALLED"]
    assert credentialled["status"] == "missing" and "the secret store could not be read" in credentialled["why"]


# -- GRANTED and EXERCISED: a live founder grant and a Gate receipt ----------------------------------------------------

def test_a_live_grant_and_a_receipt_read_exercised(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:open"
    spec = _note_mission(home, mid, capabilities=("fs.read", "fs.write", "cognition.graph"),
                         targets=("fs:*", "workspace:*", "cognition:*"))
    with Body(home) as body:
        body.apply(signed(key, body_id, "MISSION", spec), channel="inbox")
        granted_only = readiness.report(home)
        receipt = _write_through_gate(body, mid)
    assert _row(granted_only, "fs.write")["reached"] == ["KNOWN", "INSTALLED", "GRANTED"]
    # a live cone names it, but a capability the founder never attached is not granted by it
    unattached = _row(granted_only, "cognition.graph")["rungs"]["GRANTED"]
    assert unattached["status"] == "missing" and unattached["evidence"][0]["ref"] == mid
    assert "a live grant names it, but its lifecycle state is VERIFIED" in unattached["why"]
    report = readiness.report(home)
    write = _row(report, "fs.write")
    assert write["reached"] == ["KNOWN", "INSTALLED", "GRANTED", "EXERCISED"]
    assert write["first_missing"] == "VERIFIED"
    assert write["rungs"]["GRANTED"]["evidence"][0]["kind"] == "light_cone"
    assert write["rungs"]["GRANTED"]["evidence"][0]["ref"] == mid
    assert write["rungs"]["EXERCISED"]["evidence"][0]["ref"] == receipt
    assert _row(report, "git.inspect")["first_missing"] == "GRANTED"     # not in the signed cone
    # A grant is live only inside its horizon.
    later = readiness.report(home, now=datetime.now(timezone.utc) + timedelta(days=30))
    assert _row(later, "fs.write")["rungs"]["GRANTED"]["status"] == "missing"
    assert _row(later, "fs.write")["rungs"]["EXERCISED"]["status"] == "reached"


def test_a_cone_ceiling_below_the_capability_or_a_paused_mission_grants_nothing(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        body.apply(signed(key, body_id, "MISSION", _note_mission(home, "m:read-only", ceiling="read_only")),
                   channel="inbox")
        report = readiness.report(home)
        write = _row(report, "fs.write")["rungs"]["GRANTED"]
        assert write["status"] == "missing" and "exceeds its ceiling read_only" in write["why"]
        assert _row(report, "fs.read")["rungs"]["GRANTED"]["status"] == "reached"
        body.apply(signed(key, body_id, "LIFECYCLE", {"mission_id": "m:read-only", "state": "PAUSED",
                                                      "reason": "test pause"}), channel="inbox")
    assert _row(readiness.report(home), "fs.read")["rungs"]["GRANTED"]["status"] == "missing"


def test_a_cone_whose_targets_cannot_reach_the_capability_grants_nothing(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    spec = mission("m:fs-only", checks=[note_check("n", data / "n.txt", "hello")],
                   strategies=[write_strategy("w", "n.txt", "hello", ["n"])], capabilities=["fs.read", "fs.write"],
                   targets=("fs:*",))
    with Body(home) as body:
        body.apply(signed(key, body_id, "MISSION", spec), channel="inbox")
    report = readiness.report(home)
    write = _row(report, "fs.write")["rungs"]["GRANTED"]           # fs.write acts only on workspace: targets
    assert write["status"] == "missing" and "can fall under its prefix 'workspace:'" in write["why"]
    assert _row(report, "fs.read")["rungs"]["GRANTED"]["status"] == "reached"


@pytest.mark.parametrize("pattern", ["workspace:n.txt", "work*"])
def test_a_cone_target_that_can_name_a_target_under_the_prefix_grants(tmp_path, pattern):
    """An exact target under the prefix, and a pattern whose literal head is shorter than the prefix, both can."""
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        body.apply(signed(key, body_id, "MISSION", _note_mission(home, "m:targets", targets=("fs:*", pattern))),
                   channel="inbox")
    assert _row(readiness.report(home), "fs.write")["rungs"]["GRANTED"]["status"] == "reached"


@pytest.mark.parametrize("signed_class", ["internal_write", "read_only"])
def test_a_pre_approved_step_grants_only_what_the_engine_runs_as_pre_approved(tmp_path, signed_class):
    """A signed pre-approval admits one step past the cone exactly when greg.missions.pre_approved does: that step's
    action, capability and target, the manifest's own consequence class, no cost. A step signed with another class is
    not run as pre-approved (the engine asks), so it grants nothing here either."""
    from greg.missions import pre_approved
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:pre"
    strategy = write_strategy("w", "n.txt", "hello", ["n"])
    spec = mission(mid, checks=[note_check("n", workspace(home, mid) / "n.txt", "hello")], strategies=[strategy],
                   capabilities=["fs.read"], ceiling="read_only")          # the cone itself does not admit fs.write
    spec["pre_approved_steps"] = [{"action_id": "w", "capability": "fs.write", "target": strategy["target"],
                                   "consequence_class": signed_class, "cost_usd": 0}]
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        body.apply(signed(key, body_id, "MISSION", spec, now=clock.now), channel="inbox")
        granted = _row(readiness.report(home), "fs.write")["rungs"]["GRANTED"]
        for _ in range(6):
            body.tick()
            clock.advance(1)
        ran = [e.payload["action_id"] for e in body.journal.replay("mission.action") if e.payload["status"] == "DONE"]
        asked = [e.payload["kind"] for e in body.journal.replay("decision.requested")]
    engine_runs_it = pre_approved(spec, strategy, BUILTINS["fs.write"][0])
    assert engine_runs_it == (signed_class == "internal_write")
    if engine_runs_it:
        assert ran == ["w"] and "APPROVAL" not in asked
        assert granted["status"] == "reached"
        assert [(e["kind"], e["steps"]) for e in granted["evidence"]] == [("signed_pre_approval", ["w"])]
    else:
        assert ran == [] and "APPROVAL" in asked
        assert granted["status"] == "missing" and "pre-approval of w is not one the engine runs" in granted["why"]


def test_a_refused_invocation_is_not_exercise(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:refused"
    with Body(home) as body:
        body.apply(signed(key, body_id, "MISSION", _note_mission(home, mid)), channel="inbox")
        state = body.engine.book.missions[mid]
        manifest, adapter, _ = body.engine._resolve({"capability": "fs.write"})
        outcome = body.office.act(       # an over-ceiling write: the adapter refuses after the Gate dispatched it
            mission_id=mid, cone=state.cone, command_digest=state.command_digest, manifest=manifest, adapter=adapter,
            ctx=body.engine._context(state, manifest), params={"relative_path": "n.txt", "content": "x" * 300_000},
            target="workspace:n.txt", cost_usd=0.0, expected_outcome="strategy executed", evidence_refs=[],
            attempt=0, spent_usd=0.0, approved_scopes=set())
    assert outcome.status == "REFUSED" and outcome.receipt_hash
    write = _row(readiness.report(home), "fs.write")["rungs"]["EXERCISED"]
    assert write["status"] == "missing" and "1 invocation(s) were receipted, none positive" in write["why"]


# -- VERIFIED: an independent appraisal; a later REFUTED or ineffective verdict drops it ------------------------------

def test_an_independent_verified_appraisal_reads_verified(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    listing = mission("m:list", checks=[note_check("n", data / "absent.txt", "x")],
                      strategies=[{"action_id": "w", "capability": "fs.list", "params": {"path": str(data)},
                                   "target": "fs:data", "advances": ["n"], "rationale": "list"}],
                      capabilities=["fs.read", "fs.list"], targets=("fs:*",), ceiling="read_only")
    with Body(home) as body:                            # exercised in another mission that no appraisal judges
        body.apply(signed(key, body_id, "MISSION", listing), channel="inbox")
        _act_through_gate(body, "m:list", "fs.list", {"path": str(data)}, "fs:data")
        body.apply(signed(key, body_id, "LIFECYCLE", {"mission_id": "m:list", "state": "PAUSED",
                                                      "reason": "keep it out of the ticks"}), channel="inbox")
    _run_to_closure(home, key, body_id, "m:first")
    report = readiness.report(home)
    assert _row(report, "fs.list")["rungs"]["EXERCISED"]["status"] == "reached"
    assert _row(report, "fs.list")["rungs"]["VERIFIED"]["status"] == "missing"
    for cid in ("fs.write", "fs.read"):                 # the strategy and the closure's sensor
        row = _row(report, cid)
        assert {"EXERCISED", "VERIFIED"} <= set(row["reached"]), row
        assert row["rungs"]["VERIFIED"]["evidence"][0]["mission_id"] == "m:first"
        # the mission closed, so no live grant remains: the next use needs a new signed mission
        assert row["first_missing"] == "GRANTED" and "spent by its one act" in row["why"]
    assert _row(report, "git.inspect")["rungs"]["VERIFIED"]["status"] == "missing"
    assert report["summary"]["reached"]["VERIFIED"] == 2
    # fs.read is verified only as the closure's sensor, which routing's track record does not read: reported
    assert any(d["capability_id"] == "fs.read" and "counts no verified action" in d["detail"]
               for d in report["disagreements"])
    with Body(home) as body:                            # a new open mission over the same cone: every rung reached
        body.apply(signed(key, body_id, "MISSION", _note_mission(home, "m:next")), channel="inbox")
    write = _row(readiness.report(home), "fs.write")
    assert write["first_missing"] is None
    assert write["reached"] == ["KNOWN", "INSTALLED", "GRANTED", "EXERCISED", "VERIFIED"]


def test_a_later_refuted_appraisal_drops_verified_and_a_later_verified_restores_it(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    _run_to_closure(home, key, body_id, "m:first")
    mid = "m:claimed"
    from greg.body import observe
    with observe(home) as journal:          # an observation receipt of another mission, cited by the claim
        foreign = [e.payload["receipt"] for e in journal.replay("mission.observed")
                   if e.payload["mission_id"] == "m:first" and e.payload.get("receipt")][-1]
    with Body(home) as body:
        body.apply(signed(key, body_id, "MISSION", _note_mission(home, mid)), channel="inbox")
        _write_through_gate(body, mid)
        body.journal.record("mission.achieved", {"mission_id": mid, "evidence": [foreign], "actions_done": 1,
                                                 "note": "untrusted closure claim"}, key=[mid, "claim"])
        body.tick()                                     # the body's separate appraiser judges the claim
    assert _verdicts(home, mid) == ["REFUTED"]
    report = readiness.report(home)
    write = _row(report, "fs.write")
    assert write["rungs"]["VERIFIED"]["status"] == "missing"
    assert "latest verdict is REFUTED" in write["rungs"]["VERIFIED"]["why"]
    assert _row(report, "fs.read")["rungs"]["VERIFIED"]["status"] == "reached"   # the refuted closure judged no read
    _run_to_closure(home, key, body_id, "m:again", text="again")
    assert _row(readiness.report(home), "fs.write")["rungs"]["VERIFIED"]["status"] == "reached"


def test_an_ineffective_routing_verdict_drops_verified(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    _run_to_closure(home, key, body_id, "m:first")
    with Body(home) as body:     # a verdict other than ineffective (none is written today) is read by neither reader
        body.journal.record("routing.outcome", {"mission_id": "m:other", "action_id": "w", "capability": "fs.write",
                                                "verdict": "effective", "receipt": None}, key=["m:other", "w", 0])
    assert _row(readiness.report(home), "fs.write")["rungs"]["VERIFIED"]["status"] == "reached"
    from greg.body import observe
    with observe(home) as journal:
        assert not routing.track_record(journal)["fs.write"]["ineffective"]
    with Body(home) as body:
        body.journal.record("routing.outcome", {"mission_id": "m:later", "action_id": "w", "capability": "fs.write",
                                                "verdict": "ineffective", "receipt": None,
                                                "reason": "executed but n still failing"}, key=["m:later", "w", 0])
    write = _row(readiness.report(home), "fs.write")["rungs"]["VERIFIED"]
    assert write["status"] == "missing" and "latest verdict is INEFFECTIVE" in write["why"]


def test_a_strategy_routing_ruled_ineffective_is_not_verified_by_a_sibling_s_success(tmp_path):
    """Review finding F1. A mission with two strategies: fs.list runs first and changes nothing (routing records it
    ineffective), fs.write then achieves the goal and the separate appraiser verifies the closure. That closure's
    exactly-once check covers the fs.list receipt, but nothing about the closure vouches for its effect."""
    home, key, body_id, data = make_body(tmp_path)
    mid = "m:mixed"
    spec = mission(mid, checks=[note_check("n", workspace(home, mid) / "n.txt", "hello")],
                   strategies=[{"action_id": "a_list", "capability": "fs.list", "params": {"path": str(data)},
                                "target": "fs:data", "advances": ["n"], "rationale": "a read that changes nothing"},
                               write_strategy("b_write", "n.txt", "hello", ["n"])],
                   capabilities=["fs.read", "fs.list", "fs.write"])
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        drop(home, signed(key, body_id, "MISSION", spec, now=clock.now))
        for _ in range(12):
            body.tick()
            clock.advance(1)
        done = {e.payload["action_id"]: e.payload["receipt"] for e in body.journal.replay("mission.action")
                if e.payload["status"] == "DONE"}
        outcomes = [(e.payload["capability"], e.payload["verdict"], e.payload["receipt"])
                    for e in body.journal.replay("routing.outcome")]
        track = routing.track_record(body.journal)["fs.list"]
    assert outcomes == [("fs.list", "ineffective", done["a_list"])]
    assert _verdicts(home, mid) == ["VERIFIED"]
    assert track["verified"] == 1 and track["ineffective"] == 1          # routing credits it with the closure
    report = readiness.report(home)
    listing = _row(report, "fs.list")
    assert listing["rungs"]["EXERCISED"]["status"] == "reached"
    assert listing["rungs"]["VERIFIED"]["status"] == "missing"
    assert "routing recorded it ineffective" in listing["rungs"]["VERIFIED"]["why"]
    write = _row(report, "fs.write")["rungs"]["VERIFIED"]
    assert write["status"] == "reached" and write["evidence"][0]["receipts"] == [done["b_write"]]
    assert any(d["capability_id"] == "fs.list" and "greg.routing.track_record" in d["readers"]
               and "ineffective" in d["detail"] for d in report["disagreements"])


def test_a_strategy_blamed_for_breaking_a_passing_check_is_not_credited_by_the_closure(tmp_path):
    """The same class: the engine blames `boost` and `restore` for each breaking a check that passed (section 13);
    `balanced` then achieves both and the appraiser verifies. Only `balanced`'s receipt is credited."""
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:plant"
    ws = workspace(home, mid)
    ws.mkdir(parents=True)
    (ws / "plant.txt").write_text("safe")
    spec = mission(mid, checks=[note_check("throughput", ws / "plant.txt", "fast"),
                                note_check("safety", ws / "plant.txt", "safe")],
                   strategies=[write_strategy("boost", "plant.txt", "fast", ["throughput"]),
                               write_strategy("restore", "plant.txt", "safe", ["safety"]),
                               write_strategy("balanced", "plant.txt", "safe and fast", ["throughput", "safety"])],
                   capabilities=["fs.read", "fs.write"])
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(14):
            clock.advance(60)
            body.tick()
        done = {e.payload["action_id"]: e.payload["receipt"] for e in body.journal.replay("mission.action")
                if e.payload["status"] == "DONE"}
        failed = body.engine.book.missions[mid].failed
    assert list(done) == ["boost", "restore", "balanced"]
    assert failed["boost"].startswith("regressed safety") and failed["restore"].startswith("regressed throughput")
    assert _verdicts(home, mid) == ["VERIFIED"]
    write = _row(readiness.report(home), "fs.write")["rungs"]["VERIFIED"]
    assert write["status"] == "reached"
    assert write["evidence"][0]["receipts"] == [done["balanced"]]
    uncredited = write["evidence"][0]["not_credited"]
    assert sorted(u["receipt"] for u in uncredited) == sorted([done["boost"], done["restore"]])
    assert all(u["why"].startswith("regressed ") for u in uncredited)


def test_a_capability_first_exercised_after_a_verified_hold_is_not_verified_by_it(tmp_path):
    """A standing mission's hold judges the actions before it; one completed after it waits for the next hold."""
    home, key, body_id, data = make_body(tmp_path)
    mid = "m:standing"
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        drop(home, signed(key, body_id, "MISSION", _note_mission(
            home, mid, capabilities=("fs.read", "fs.write", "fs.list"), closure={"kind": "infinite"}), now=clock.now))
        for _ in range(6):
            body.tick()
            clock.advance(1)
    assert _verdicts(home, mid) == ["VERIFIED"]
    with Body(home, clock=clock) as body:
        _act_through_gate(body, mid, "fs.list", {"path": str(data)}, "fs:data", action_id="later")
    report = readiness.report(home)
    assert _row(report, "fs.write")["rungs"]["VERIFIED"]["status"] == "reached"
    listing = _row(report, "fs.list")["rungs"]
    assert listing["EXERCISED"]["status"] == "reached" and listing["VERIFIED"]["status"] == "missing"


def test_a_refutation_whose_effect_checks_held_drops_verified_and_is_reported(tmp_path):
    """An act no signed strategy names is slipped into a mission the engine then closes honestly: the world checks
    re-derive, the appraiser refutes the closure on its approval boundary. Routing does not count that refutation
    (its effect checks held); the ladder drops VERIFIED and reports the difference."""
    home, key, body_id, _ = make_body(tmp_path)
    _run_to_closure(home, key, body_id, "m:first")
    mid = "m:forged"
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        body.apply(signed(key, body_id, "MISSION", _note_mission(home, mid), now=clock.now), channel="inbox")
        _act_through_gate(body, mid, "fs.write", {"relative_path": "other.txt", "content": "x"},
                          "workspace:other.txt", action_id="x")
        for _ in range(6):
            body.tick()
            clock.advance(1)
        appraisals = [e.payload for e in body.journal.replay("mission.appraised") if e.payload["mission_id"] == mid]
        track = routing.track_record(body.journal)["fs.write"]
    assert [a["verdict"] for a in appraisals] == ["REFUTED"]
    assert all(appraisals[0]["checks"][c] for c in routing.EFFECT_CHECKS)
    assert track["verified"] >= 1 and not track["refuted"] and not track["ineffective"]
    report = readiness.report(home)
    write = _row(report, "fs.write")["rungs"]["VERIFIED"]
    assert write["status"] == "missing" and "(its effect checks held)" in write["why"]
    assert any(d["capability_id"] == "fs.write" and "does not count a refutation whose effect checks held"
               in d["detail"] for d in report["disagreements"])


def test_a_refuted_failure_closure_drops_verified_and_is_named_a_failure_closure(tmp_path):
    """Review finding F3. A REFUTED appraisal of any closure that judged the capability's receipts drops VERIFIED, a
    failure closure's included (the scope: a REFUTED latest outcome never reads VERIFIED; routing's track record
    counts it refuted too). The reason says which kind of closure was refuted, so a reader can weigh it."""
    home, key, body_id, _ = make_body(tmp_path)
    _run_to_closure(home, key, body_id, "m:first")
    mid = "m:unmet"
    with Body(home) as body:
        body.apply(signed(key, body_id, "MISSION", _note_mission(home, mid)), channel="inbox")
        _write_through_gate(body, mid)
        body.journal.record("mission.unmet", {"mission_id": mid, "failing_checks": ["n"], "actions_done": 1,
                                              "closure_rule": "an unobserved failure claim",
                                              "at": "2026-10-30T00:00:00Z"}, key=[mid, "unmet", 1])
        body.apply(signed(key, body_id, "LIFECYCLE", {"mission_id": mid, "state": "PAUSED",
                                                      "reason": "keep it out of the ticks"}), channel="inbox")
        body.tick()                                     # the body's separate appraiser judges the failure claim
        appraisals = [e.payload for e in body.journal.replay("mission.appraised") if e.payload["mission_id"] == mid]
    assert [(a["verdict"], a.get("closure")) for a in appraisals] == [("REFUTED", "unmet")]
    write = _row(readiness.report(home), "fs.write")["rungs"]["VERIFIED"]
    assert write["status"] == "missing" and "REFUTED a failure closure of m:unmet" in write["why"]


def test_a_verified_failure_closure_verifies_nothing(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:unmet"
    with Body(home) as body:
        body.apply(signed(key, body_id, "MISSION", _note_mission(home, mid)), channel="inbox")
        _write_through_gate(body, mid)
        closure = body.journal.record("mission.unmet", {"mission_id": mid, "failing_checks": ["n"],
                                                        "actions_done": 1, "at": "2026-10-30T00:00:00Z"},
                                      key=[mid, "unmet", 1])
        for verdict in ("VERIFIED_UNMET", "UNAVAILABLE"):
            body.journal.record("mission.appraised", {"mission_id": mid, "verdict": verdict, "checks": {},
                                                      "findings": [], "head": "h", "closure_event": closure.event_id},
                                key=[mid, "appraised", verdict])
    assert _row(readiness.report(home), "fs.write")["rungs"]["VERIFIED"]["status"] == "missing"


# -- the registry the body uses: capabilities Genesis registered ------------------------------------------------------

def _formed(cid: str, provider: str, **kw) -> CapabilityManifest:
    return CapabilityManifest(capability_id=cid, version="1.0.0", provider=provider, function="hash.sha256",
                              description="a formed test capability", route=kw.pop("route", "internal"),
                              consequence_class="read_only", inputs={"path": "str"}, outputs={"digest": "str"},
                              target_prefix="fs:", strengthens=("proof",), **kw)


def test_capabilities_genesis_registered_are_on_the_ladder(tmp_path):
    home, _key, _body_id, _ = make_body(tmp_path)
    import importlib.metadata
    pytest_version = importlib.metadata.version("pytest")
    formed = [_formed("acquired.hash.sha256.missing", "installed:/nonexistent/greg-readiness-probe", route="cli",
                      binaries=("/nonexistent/greg-readiness-probe",)),
              _formed("acquired.hash.sha256.pytest", f"installed:python:pytest=={pytest_version}"),
              _formed("acquired.hash.sha256.stale", "installed:python:pytest==0.0.1"),
              _formed("acquired.hash.sha256.unformed", "vendor:acme")]          # not a provider Genesis forms
    with Body(home) as body:
        for manifest in formed:
            body.journal.record("capability.registered", {"manifest": manifest.to_dict(), "state": "VERIFIED"},
                                key=[manifest.capability_id, "registered"])
        body.journal.record("capability.state", {"capability_id": "acquired.hash.sha256.pytest",
                                                 "state": "QUARANTINED", "why": "test"},
                            key=["acquired.hash.sha256.pytest", "quarantined"])
    report = readiness.report(home)
    missing = _row(report, "acquired.hash.sha256.missing")
    assert missing["source"] == "registered" and missing["reached"] == ["KNOWN"]
    assert missing["first_missing"] == "INSTALLED" and "not installed" in missing["why"]
    present = _row(report, "acquired.hash.sha256.pytest")
    assert present["reached"] == ["KNOWN", "INSTALLED"] and present["lifecycle_state"] == "QUARANTINED"
    assert "quarantined" in present["why"]
    stale = _row(report, "acquired.hash.sha256.stale")
    assert stale["first_missing"] == "INSTALLED" and "pins 0.0.1" in stale["why"]
    assert report["summary"]["capabilities"] == len(BUILTINS) + 3
    assert "acquired.hash.sha256.unformed" not in {r["capability_id"] for r in report["capabilities"]}
    # body.status (Mission Control's list) omits them; the running body re-registers them: reported, not hidden
    omitted = [d for d in report["disagreements"] if d["capability_id"] is None]
    assert len(omitted) == 1 and "acquired.hash.sha256.missing" in omitted[0]["detail"]
    assert "acquired.hash.sha256.missing" not in {c["capability_id"] for c in status(home)["capabilities"]}
