"""The founder's ``worker_confinement`` body setting: fail closed by default, supervised only by founder choice.

#169 (from #157) refuses any worker the bubblewrap envelope cannot confine. #178 ran every worker under process
supervision with the filesystem and network stated as not confined. Both were real choices with real tradeoffs,
and which one a body uses is the founder's decision (NEEDS_FOUNDER_DECISION, safe default fail closed). These
tests pin that decision to the founder's own ``init_body`` choice and pin what each mode does and reports.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from greg import templates, workers
from greg import worker_isolation as isolation
from greg.body import Body, Layout, init_body
from tests.greg_fixtures import Clock, drop, make_body, signed

AGENT = '''import sys
from pathlib import Path
Path(sys.argv[1]).write_text("ran with the body's reach")     # outside the clone: only an unconfined worker can
sys.stdin.read()
Path("pkg/calc.py").write_text("def add(a, b):\\n    return a + b\\n\\n\\ndef sub(a, b):\\n    return a - b\\n")
Path("tests").mkdir(exist_ok=True)
Path("tests/test_calc.py").write_text("from pkg.calc import sub\\n\\n\\ndef test_sub():\\n    assert sub(3, 1) == 2\\n")
print('WORK_REPORT: {"changed": ["pkg/calc.py", "tests/test_calc.py"], "confidence": 0.9}')
'''


def _envelope_available() -> bool:
    try:
        isolation._backend(require_bubblewrap=True)
        return True
    except isolation.WorkerIsolationError:
        return False


def _repo(root: Path) -> Path:
    repo = root / "proj"
    (repo / "pkg").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "pkg" / "__init__.py").write_text("")
    (repo / "pkg" / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    for args in (["add", "-A"], ["commit", "-qm", "base"]):
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True,
                       capture_output=True)
    return repo


@pytest.fixture(autouse=True)
def _no_host_ca_override(monkeypatch):
    # A host CA outside the supported roots refuses the envelope (tested in test_greg_worker_isolation.py).
    for name in isolation._CERT_ENV:
        monkeypatch.delenv(name, raising=False)


def _mission(tmp_path, monkeypatch, confinement: str):
    data = tmp_path / "data"
    data.mkdir()
    repo = _repo(data)
    agent = tmp_path / "tools" / "agent.py"
    agent.parent.mkdir()
    agent.write_text(AGENT)
    marker = tmp_path / "tools" / "reach.marker"
    # An unreviewed headless CLI, as #178's one-machine harness declares its local worker.
    monkeypatch.setitem(workers.PROVIDERS, "local-cli",
                        workers.CliAgentWorker("local-cli", [sys.executable, str(agent), str(marker)], stdin=True))
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data], worker_confinement=confinement)
    spec = templates.code_change(repo=str(repo), objective="add sub()", order="add-sub", provider="local-cli",
                                 allowed_paths=["pkg/*", "tests/*"], budget_usd=0.5,
                                 workspace_root=Layout(home).workspace)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        assert body.engine.worker_confinement == confinement
        for _ in range(4):
            body.tick()
            clock.advance(60)
        actions = [e.payload for e in body.journal.replay("mission.action")]
    evidence = Layout(home).workspace / spec["mission_id"].replace(":", "_") / "work-orders" / "add-sub" / "evidence.json"
    return actions, marker, evidence, home


@pytest.mark.parametrize("value,expected", [("supervised", "supervised"), ("required", "required"),
                                            (None, "required"), ("Supervised", "required"), (True, "required"),
                                            ("unconfined", "required")])
def test_only_an_exact_supervised_setting_leaves_the_fail_closed_default(value, expected):
    assert workers.confinement_mode(value) == expected


def test_the_default_body_records_no_setting_and_runs_required(tmp_path):
    config = init_body(tmp_path / "body", read_roots=[str(tmp_path)])
    assert "worker_confinement" not in config
    with Body(tmp_path / "body") as body:
        assert body.engine.worker_confinement == "required"


def test_supervised_is_written_once_by_the_founders_init_and_an_unknown_value_is_refused(tmp_path):
    config = init_body(tmp_path / "a", read_roots=[str(tmp_path)], worker_confinement="supervised")
    assert config["worker_confinement"] == "supervised"
    assert json.loads(Layout(tmp_path / "a").config.read_text())["worker_confinement"] == "supervised"
    with pytest.raises(ValueError):
        init_body(tmp_path / "b", read_roots=[str(tmp_path)], worker_confinement="none")


def test_a_hand_edited_unknown_value_in_body_config_runs_fail_closed(tmp_path):
    init_body(tmp_path / "body", read_roots=[str(tmp_path)])
    path = Layout(tmp_path / "body").config
    config = json.loads(path.read_text())
    path.write_text(json.dumps({**config, "worker_confinement": "off"}))
    with Body(tmp_path / "body") as body:
        assert body.engine.worker_confinement == "required"


def test_required_refuses_an_unconfinable_worker_before_any_process_starts(tmp_path, monkeypatch):
    actions, marker, evidence, _ = _mission(tmp_path, monkeypatch, "required")
    commission = [a for a in actions if a["action_id"] == "commission-worker"]
    assert commission and all(a["status"] != "DONE" for a in commission)
    assert any("unreviewed worker provider refused before dispatch" in r for a in commission for r in a["reasons"])
    assert not marker.exists(), "a refused worker must never run"
    assert not evidence.exists()


@pytest.mark.skipif(not _envelope_available(), reason="acceptance needs the envelope on this host")
def test_supervised_runs_the_worker_and_says_exactly_what_was_not_confined(tmp_path, monkeypatch):
    actions, marker, evidence, _ = _mission(tmp_path, monkeypatch, "supervised")
    assert [a["status"] for a in actions if a["action_id"] == "commission-worker"] == ["DONE"]
    summary = json.loads(evidence.read_text())["summary"]
    assert summary["status"] == "COMPLETED" and summary["commit"]
    iso = summary["worker"]["isolation"]
    assert iso["mode"] == "supervised" and iso["filesystem"].startswith("NOT OS-confined")
    assert iso["network"].startswith("NOT isolated") and "unreviewed" in iso["envelope_refused"]
    # The evidence is true: the worker did reach outside its clone.
    assert marker.exists()
    # Acceptance still ran in the envelope, because this host provides it.
    assert summary["greg_tests_passed"]
    assert all(t["confinement"].startswith("envelope") for t in summary["greg_tests"])


def test_confined_egress_is_never_traded_for_supervision():
    def refused():
        raise isolation.WorkerIsolationError("unreviewed worker provider refused before dispatch")
    with pytest.raises(isolation.WorkerIsolationError, match="confines egress"):
        workers._confined_or_supervised(refused, ["true"], Path("/tmp"), confinement="supervised", door=object())


def test_a_reviewed_provider_on_an_envelope_host_stays_confined_under_supervised(tmp_path):
    if not _envelope_available():
        pytest.skip("no envelope on this host")
    work = tmp_path / "order" / "repo"
    work.mkdir(parents=True)
    envelope = workers._confined_or_supervised(
        lambda: isolation.prepare_worker([sys.executable, "-c", "pass"], work, timeout_seconds=10, provider="t",
                                         reviewed=True),
        [sys.executable, "-c", "pass"], work, confinement="supervised")
    assert envelope["evidence"]["filesystem"] == "os-confined"


@pytest.mark.parametrize("confinement", ["required", "supervised"])
def test_acceptance_without_an_envelope_follows_the_setting_and_never_opens_the_network(tmp_path, monkeypatch,
                                                                                       confinement):
    def no_envelope(*args, **kwargs):
        raise isolation.WorkerIsolationError("bubblewrap unavailable on this host")
    monkeypatch.setattr(workers, "prepare_worker", no_envelope)
    probe = ("import socket\n"
             "try:\n    socket.socket(socket.AF_INET, socket.SOCK_STREAM)\nexcept OSError:\n    raise SystemExit(0)\n"
             "raise SystemExit('network was open')\n")
    [result] = workers.run_tests([["python", "-c", probe]], tmp_path, timeout=30, confinement=confinement)
    if confinement == "required":
        assert not result["passed"] and result["confinement"] == "refused"
        assert "bubblewrap unavailable" in result["tail"]
    elif result["confinement"] == "refused":          # this host has no network filter either: refused, not run
        assert "network isolation unavailable" in result["tail"]
    else:
        assert result["confinement"].startswith("supervised") and "NOT confined" in result["confinement"]
        assert result["passed"], result["tail"]        # the socket was refused: the network stayed closed


def test_the_separate_appraiser_receives_the_founders_setting(tmp_path, monkeypatch):
    init_body(tmp_path / "body", read_roots=[str(tmp_path)], worker_confinement="supervised")
    seen = {}

    def fake_run(argv, input=None, **kwargs):
        seen.update(json.loads(input))
        return subprocess.CompletedProcess(argv, 1, "", "stopped by test")
    monkeypatch.setattr(subprocess, "run", fake_run)
    with Body(tmp_path / "body") as body:
        body.appraise("m:none")
    assert seen["worker_confinement"] == "supervised"
