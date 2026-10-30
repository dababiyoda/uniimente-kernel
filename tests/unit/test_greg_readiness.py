"""Capability readiness ladder (directive section 32): KNOWN, INSTALLED, CREDENTIALLED, GRANTED, EXERCISED, VERIFIED.

Every fixture is a real body: a real Ed25519 test key (not Alfonso's), founder-signed missions, receipts produced by
the real Kernel Gate, and appraisals recorded by the body's separate appraiser process. Two kinds of fact are recorded
directly, in the shape their one writer gives them, because producing them for real is not what is under test: an
ineffective ``routing.outcome`` (greg/missions.py ``_record_routing_outcomes``) and a capability Genesis registered
(greg/genesis.py). The planted secret value is a test string; no real credential is used.
"""
from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path

from greg import cli
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


def _act_through_gate(body: Body, mid: str, capability: str, params: dict, target: str) -> str:
    """One action through the real AuthorityOffice and Gate for an open mission, recorded as the engine does."""
    state = body.engine.book.missions[mid]
    manifest, adapter, _ = body.engine._resolve({"capability": capability})
    outcome = body.office.act(
        mission_id=mid, cone=state.cone, command_digest=state.command_digest, manifest=manifest, adapter=adapter,
        ctx=body.engine._context(state, manifest), params=params, target=target, cost_usd=0.0,
        expected_outcome="strategy executed", evidence_refs=[], attempt=0, spent_usd=0.0, approved_scopes=set())
    assert outcome.status == "DONE", outcome.reasons
    body.journal.record("mission.action", {
        "mission_id": mid, "action_id": "w", "attempt": 0, "status": "DONE", "capability": capability,
        "receipt": outcome.receipt_hash, "scope_digest": outcome.scope_digest}, key=[mid, "w", 0])
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
    with Body(home) as body:                            # a new open mission over the same cone: every rung reached
        body.apply(signed(key, body_id, "MISSION", _note_mission(home, "m:next")), channel="inbox")
    write = _row(readiness.report(home), "fs.write")
    assert write["first_missing"] is None
    assert write["reached"] == ["KNOWN", "INSTALLED", "GRANTED", "EXERCISED", "VERIFIED"]


def test_a_later_refuted_appraisal_drops_verified_and_a_later_verified_restores_it(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    _run_to_closure(home, key, body_id, "m:first")
    mid = "m:claimed"
    with Body(home) as body:
        body.apply(signed(key, body_id, "MISSION", _note_mission(home, mid)), channel="inbox")
        _write_through_gate(body, mid)
        body.journal.record("mission.achieved", {"mission_id": mid, "evidence": [], "actions_done": 1,
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
    with Body(home) as body:
        body.journal.record("routing.outcome", {"mission_id": "m:later", "action_id": "w", "capability": "fs.write",
                                                "verdict": "ineffective", "receipt": None,
                                                "reason": "executed but n still failing"}, key=["m:later", "w", 0])
    write = _row(readiness.report(home), "fs.write")["rungs"]["VERIFIED"]
    assert write["status"] == "missing" and "latest verdict is INEFFECTIVE" in write["why"]


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
              _formed("acquired.hash.sha256.stale", "installed:python:pytest==0.0.1")]
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
    # body.status (Mission Control's list) omits them; the running body re-registers them: reported, not hidden
    omitted = [d for d in report["disagreements"] if d["capability_id"] is None]
    assert len(omitted) == 1 and "acquired.hash.sha256.missing" in omitted[0]["detail"]
    assert "acquired.hash.sha256.missing" not in {c["capability_id"] for c in status(home)["capabilities"]}
