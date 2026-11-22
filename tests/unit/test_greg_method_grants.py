"""Standing method grants (greg/method_grants.py): one signed, bounded, revocable grant lets read-only missions
use a reviewed set of read-only methods without an attach per question.

Baseline (tests/unit/test_greg_cognition_genesis.py::test_a_deficit_that_fits_a_withheld_genome_names_it_as_
the_attach_candidate): the same mission blocks until a CAPABILITY_ATTACH."""
from __future__ import annotations

from datetime import timedelta
import json

import pytest

pytest.importorskip("scipy")

from greg.body import Body  # noqa: E402
from greg.missions import MissionError  # noqa: E402
from greg.cognition import compiler  # noqa: E402
from greg.cognition.genomes import library  # noqa: E402
from greg import method_grants  # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, mission, signed  # noqa: E402

METHOD = "cognition.queue_erlang"


@pytest.fixture
def index(tmp_path, monkeypatch):
    path = tmp_path / "index.json"
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", path)
    item = library.executables()["queue_erlang"]
    path.write_text(json.dumps({"genomes": {"queue_erlang": {
        "status": "DEFAULT_FOR_GEOMETRY", "version": item.genome.version, "evidence": "results.json#queue_erlang"}},
        "recipes": {}, "routing": {}}))
    return item


def _dir(path):
    path.mkdir(parents=True, exist_ok=True)
    return path


def staffing(mission_id, item, seed=2, ceiling="read_only"):
    params = {"problem_id": f"real:{mission_id}", "compile": {
        "geometry": {"geometry": item.genome.epistemic_class, "subgeometry": "staffing"},
        "data": item.instance(seed)[0]}}
    return mission(mission_id, checks=[{
        "check_id": "answered", "description": "a competent method answered",
        "sensor": {"capability": "cognition.solve", "target": "cognition:staffing", "params": params},
        "predicate": {"op": "equals", "field": "state", "value": "ANSWERED"}}],
        strategies=[], capabilities=["cognition.solve"], targets=("cognition:*",), ceiling=ceiling)


def grant(clock, **kw):
    body = {"grant_id": "g:staffing", "capabilities": [METHOD], "targets": ["cognition:staffing"],
            "until": (clock() + timedelta(days=7)).isoformat(), "max_uses": 10,
            "purpose": "reviewed queueing methods for staffing questions"}
    body.update(kw)
    return body


def run(body, clock, n=3):
    states = []
    for _ in range(n):
        states.append(body.tick()["missions"])
        clock.advance(31)
    return states


def state_of(body, mission_id):
    return body.engine.book.missions[mission_id].status


def attach_asks(body):
    return [e.payload for e in body.journal.replay("decision.requested") if e.payload["kind"] == "CAPABILITY_ATTACH"]


def test_inside_the_grant_the_mission_closes_with_no_ask_and_nothing_is_attached(tmp_path, index):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        body.apply(signed(key, body_id, "METHOD_GRANT", grant(clock)))
        body.apply(signed(key, body_id, "MISSION", staffing("m:staff", index)))
        run(body, clock)
        assert state_of(body, "m:staff") == "ACHIEVED"
        assert attach_asks(body) == []                                   # no founder action per question
        assert body.registry.state[METHOD] == "VERIFIED"                 # the grant attached nothing
        assert not [e for e in body.journal.replay("capability.state") if e.payload["state"] == "ATTACHED"]
        [used] = [e.payload for e in body.journal.replay("method_grant.used")]
        assert used["grant_id"] == "g:staffing" and used["capability_id"] == METHOD and used["receipt"]
        assert body.ledger.find(used["receipt"]) is not None              # bound to the answer's own receipt
        assert method_grants.summary(body.journal, clock())[0]["uses"] == 1


def test_revoked_expired_or_used_up_grants_stop_at_once_and_the_mission_asks_as_before(tmp_path, index):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        body.apply(signed(key, body_id, "METHOD_GRANT", grant(clock, max_uses=1)))
        body.apply(signed(key, body_id, "MISSION", staffing("m:one", index)))
        run(body, clock)
        assert state_of(body, "m:one") == "ACHIEVED"
        body.apply(signed(key, body_id, "MISSION", staffing("m:two", index, seed=3)))
        run(body, clock)
        assert state_of(body, "m:two") != "ACHIEVED"                     # used up: the second question asks
        assert method_grants.summary(body.journal, clock())[0]["status"] == "USED_UP"
        assert attach_asks(body)

    home, key, body_id, _ = make_body(_dir(tmp_path / "revoked"))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        body.apply(signed(key, body_id, "METHOD_GRANT", grant(clock)))
        body.apply(signed(key, body_id, "METHOD_GRANT_REVOKE", {"grant_id": "g:staffing", "reason": "test"}))
        body.apply(signed(key, body_id, "MISSION", staffing("m:revoked", index)))
        run(body, clock)
        assert state_of(body, "m:revoked") != "ACHIEVED" and attach_asks(body)
        assert not list(body.journal.replay("method_grant.used"))

    home, key, body_id, _ = make_body(_dir(tmp_path / "expired"))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        body.apply(signed(key, body_id, "METHOD_GRANT", grant(clock, until=(clock() + timedelta(hours=1)).isoformat())))
        clock.advance(2 * 3600)
        body.apply(signed(key, body_id, "MISSION", staffing("m:late", index)))
        run(body, clock)
        assert state_of(body, "m:late") != "ACHIEVED" and attach_asks(body)
        assert method_grants.summary(body.journal, clock())[0]["status"] == "EXPIRED"


def test_a_founder_detach_and_uncovered_targets_or_ceilings_are_never_lifted(tmp_path, index):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        body.apply(signed(key, body_id, "METHOD_GRANT", grant(clock)))
        body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": METHOD}))
        body.apply(signed(key, body_id, "MISSION", staffing("m:detached", index)))
        run(body, clock)
        assert state_of(body, "m:detached") != "ACHIEVED"               # the founder's detach wins over the grant
        assert not list(body.journal.replay("method_grant.used"))
    live = [{"grant_id": "g", "capabilities": [METHOD], "targets": ["cognition:staffing"], "until": "2999-01-01T00:00:00+00:00",
             "max_uses": 5, "revoked": None, "uses": 0, "purpose": "p"}]
    assert method_grants._covers_target(live[0], "cognition:staffing")
    assert not method_grants._covers_target(live[0], "cognition:other")
    with Body(make_body(_dir(tmp_path / "v"))[0], clock=Clock()) as body:
        body.boot()
        view = method_grants.GrantView(body.registry, live)
        assert view.usable(METHOD)[0] and body.registry.usable(METHOD)[0] is False
        with pytest.raises(PermissionError):
            view.set_state(METHOD, "ATTACHED")
        assert method_grants.covering(body.journal, target="cognition:staffing", ceiling="internal_write",
                                      now=Clock()()) == []               # only read-only missions are covered


@pytest.mark.parametrize("change, message", [
    ({"capabilities": ["mcp.act"]}, "cognition"),
    ({"capabilities": ["cognition.*"]}, "no wildcards"),
    ({"targets": ["*"]}, "refused"),
    ({"max_uses": 0}, "max_uses"),
    ({"until": "2000-01-01T00:00:00+00:00"}, "future"),
])
def test_a_grant_is_exact_and_bounded_at_issue(tmp_path, index, change, message):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        with pytest.raises(MissionError, match=message):
            body.apply(signed(key, body_id, "METHOD_GRANT", grant(clock, **change)))
        assert method_grants.grants(body.journal) == {}


def test_consequential_steps_in_a_granted_mission_still_need_their_own_authority(tmp_path, index):
    """The grant lifts read-only cognition methods only: a mission whose ceiling allows writes is not covered,
    and the grant can never name a capability that acts."""
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        body.apply(signed(key, body_id, "METHOD_GRANT", grant(clock)))
        body.apply(signed(key, body_id, "MISSION", staffing("m:write", index, ceiling="internal_write")))
        run(body, clock)
        assert state_of(body, "m:write") != "ACHIEVED"
        assert not list(body.journal.replay("method_grant.used"))
        with pytest.raises(MissionError, match="cognition"):
            body.apply(signed(key, body_id, "METHOD_GRANT", grant(clock, grant_id="g:acting",
                                                                  capabilities=["deliver.write"])))
        with pytest.raises(MissionError, match="already issued"):     # a grant is never reissued or widened
            body.apply(signed(key, body_id, "METHOD_GRANT", grant(clock, capabilities=[METHOD, "cognition.x"])))


def test_the_founder_issues_lists_and_revokes_a_grant_from_the_command_line(tmp_path, index, capsys):
    from greg.cli import main
    home, key, body_id, _ = make_body(tmp_path)
    keyfile = str(tmp_path / "founder.pem")
    assert main(["--home", str(home), "grant", "issue", "g:cli", "--method", METHOD, "--target", "cognition:staffing",
                 "--days", "2", "--max-uses", "3", "--purpose", "reviewed queueing", "--key", keyfile,
                 "--no-passphrase"]) == 0
    with Body(home) as body:
        body.boot()
        body.tick()
    capsys.readouterr()
    assert main(["--home", str(home), "grant", "list"]) == 0
    [row] = json.loads(capsys.readouterr().out)
    assert row["grant_id"] == "g:cli" and row["status"] == "LIVE" and row["max_uses"] == 3
    assert main(["--home", str(home), "grant", "revoke", "g:cli", "--reason", "done", "--key", keyfile,
                 "--no-passphrase"]) == 0
    with Body(home) as body:
        body.boot()
        body.tick()
    capsys.readouterr()
    assert main(["--home", str(home), "grant", "list"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["status"] == "REVOKED"
    assert main(["--home", str(home), "grant", "issue", "g:bad", "--method", "cognition.*", "--target", "x",
                 "--purpose", "p", "--key", keyfile, "--no-passphrase"]) != 0
