"""Directive section 60, first example: "I need access to this account to answer reliably."

GitHub refuses reads the brief needs (rate limit, or a private repository without a token);
the brief is still delivered with its gaps, and GREG raises ONE account-access ask with the
evidence, costs and a no-cost option. The founder answers by storing a read-only token on the
body with `greg secret set`, which never reaches the ledger, the inbox or the command line.
"""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

import pytest

from greg import asks, briefs
from greg.body import Body, Layout, status
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.unit.test_greg_briefs import _brief_mission, _open_request, _run, fake_github, repo  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
TOKEN = "github_pat_TEST_ONLY_0123456789abcdef"


def greg_cli(home, *args, stdin=""):
    return subprocess.run([sys.executable, "-m", "greg", "--home", str(home), *args], input=stdin, text=True,
                          capture_output=True, cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)}, timeout=60)


def run_brief(tmp_path, repo, monkeypatch, fetch):
    monkeypatch.setattr(briefs, "FETCH", fetch)
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _brief_mission(repo)))
    clock = Clock()
    body = Body(home, clock=clock).open()
    body.boot()
    _run(body, clock)
    drop(home, signed(key, body_id, "DECISION", {"request_id": _open_request(body)["request_id"], "answer": "approve"}))
    states = [t["missions"][0]["state"] for t in _run(body, clock, 4)]
    return home, body, states


def access_asks(body):
    return [e.payload for e in body.journal.replay("decision.requested") if e.payload["kind"] == "ACCOUNT_ACCESS"]


def test_refused_reads_become_one_evidenced_access_ask_and_the_mission_still_closes(tmp_path, repo, monkeypatch):
    home, body, states = run_brief(tmp_path, repo, monkeypatch, fake_github([], refuse_checks=True))
    try:
        assert states[:2] == ["ACTED", "ACHIEVED"]                        # the ask never blocks the result
        [ask] = access_asks(body)
        asks.validate(ask)
        assert ask["resource"] == "account_access" and "wording_withheld" not in ask
        assert ask["evidence"]["rate_limited"] is True and "acme/organ" in ask["evidence"]["refused"]
        assert "greg secret set github_token" in ask["recommendation"]
        assert ask["options"][-1]["cost"] == "none" and ask["authority_requested"]["spend"] == "none requested"
        assert ask["request_id"] in {r["request_id"] for r in status(home)["decisions_required"]}
        _run(body, Clock(), 3)
        assert len(access_asks(body)) == 1                                # asked once, never nagged
    finally:
        body.close()


@pytest.mark.parametrize("answer, asked", [((404, None), True), ((None, {"unreachable": "offline"}), False)])
def test_a_private_repository_is_an_access_gap_but_being_offline_is_not(tmp_path, repo, monkeypatch, answer, asked):
    home, body, states = run_brief(tmp_path, repo, monkeypatch, lambda url, token: answer)
    try:
        assert "ACHIEVED" in states and bool(access_asks(body)) is asked
    finally:
        body.close()


def test_a_token_stored_on_the_body_is_used_never_recorded_and_ends_the_ask(tmp_path, repo, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path)
    assert greg_cli(home, "secret", "set", "github_token", TOKEN).returncode == 2   # never a command-line value
    assert greg_cli(home, "secret", "set", "gihtub_token", stdin=TOKEN + "\n").returncode == 2   # typo refused
    stored = greg_cli(home, "secret", "set", "github_token", stdin=TOKEN + "\n")
    assert stored.returncode == 0 and TOKEN not in stored.stdout
    secrets = Layout(home).secrets
    assert stat.S_IMODE(secrets.stat().st_mode) == 0o600
    listing = json.loads(greg_cli(home, "secret", "list").stdout)
    assert listing["stored"] == ["github_token"] and TOKEN not in json.dumps(listing)

    seen = []

    def fetch(url, token):
        seen.append(token)
        return fake_github([], refuse_checks=token is None)(url, token)
    monkeypatch.setattr(briefs, "FETCH", fetch)
    drop(home, signed(key, body_id, "MISSION", _brief_mission(repo)))
    clock = Clock()
    body = Body(home, clock=clock).open()
    body.boot()
    try:
        _run(body, clock)
        drop(home, signed(key, body_id, "DECISION", {"request_id": _open_request(body)["request_id"],
                                                     "answer": "approve"}))
        _run(body, clock, 3)
        assert seen and set(seen) == {TOKEN} and access_asks(body) == []  # authenticated: nothing to ask
    finally:
        body.close()
    assert TOKEN.encode() not in Layout(home).ledger.read_bytes()        # the value never enters history
    assert not any(TOKEN.encode() in p.read_bytes() for p in Layout(home).inbox.rglob("*.json"))
    removed = json.loads(greg_cli(home, "secret", "remove", "github_token").stdout)
    assert removed == {"removed": "github_token"} and json.loads(greg_cli(home, "secret", "list").stdout)["stored"] == []


def test_a_capability_cannot_ask_for_a_credential_it_does_not_declare(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        manifest = body.registry.manifests["fs.read"]
        m = type("M", (), {"mission_id": "m:x", "spec": {}})()
        assert body.engine._access_ask(m, "a", manifest, {"credential": "github_token", "service": "x",
                                                            "evidence": {"refused": {}}}, Clock()()) is None
        assert body.journal.replay("decision.requested") == []


def test_start_after_a_stop_names_this_platforms_restart_command(tmp_path):
    home, *_ = make_body(tmp_path)
    Layout(home).stop_file.write_text("test")
    out = json.loads(greg_cli(home, "start", "--local").stdout)
    expected = "launchctl" if sys.platform == "darwin" else "systemctl --user start greg-body.service"
    assert expected in out["next"] and out["cleared_stop"] == "test"


def test_an_authenticated_refusal_does_not_ask_for_the_token_it_already_has():
    refused = {"repos": {"acme/x": {"fetched": False, "gap": "GitHub refused (403); rate limit or access"}},
               "api_calls": 1, "rate_limited": True}
    assert briefs.access_gap({**refused, "authenticated": False})["credential"] == "github_token"
    assert briefs.access_gap({**refused, "authenticated": True}) is None
