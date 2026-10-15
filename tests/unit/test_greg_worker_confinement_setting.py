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
    def refused():   # the real refusal of an unreviewed provider
        return isolation.prepare_worker(["true"], Path("/tmp"), 10, "t", reviewed=False)
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
        raise isolation.WorkerIsolationError("bubblewrap unavailable on this host",   # as _backend raises it
                                             evidence={"status": "unsupported", "reason": "bubblewrap unavailable"})
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


# -- supervision covers only workers the envelope cannot confine (review findings on the merged trunk) -----

def test_only_a_missing_envelope_or_an_unreviewed_provider_counts_as_unconfinable(monkeypatch):
    """The contract the fallback reads: the host backend's own refusal and the unreviewed refusal are the two
    cases ``supervised`` covers; a refusal of one input or host setting is not."""
    monkeypatch.setattr(isolation, "_landlock_abi", lambda: (_ for _ in ()).throw(isolation.WorkerIsolationError("x")))
    monkeypatch.setattr(isolation.shutil, "which", lambda name, *a, **k: None if name == "bwrap" else "/usr/bin/" + name)
    with pytest.raises(isolation.WorkerIsolationError) as host:
        isolation._backend(require_bubblewrap=True)
    with pytest.raises(isolation.WorkerIsolationError) as unreviewed:
        isolation.prepare_worker(["true"], Path("/tmp"), 10, "t", reviewed=False)
    assert isolation.envelope_cannot_confine(host.value) and isolation.envelope_cannot_confine(unreviewed.value)
    for refusal in ("transport certificate path outside supported certificate roots: SSL_CERT_FILE",
                    "worker credential source must be a regular non-symlink file",
                    "shared UID task count leaves no bounded worker process margin",
                    "worker executable is unavailable"):
        assert not isolation.envelope_cannot_confine(isolation.WorkerIsolationError(refusal))


def test_a_reviewed_provider_refused_over_a_host_setting_is_not_run_unconfined_under_supervised(tmp_path, monkeypatch):
    """Review finding (b4289ca): on a host with the envelope, any refusal fell back to supervision, so a reviewed
    provider ran with the body's filesystem and network because of a CA path outside the supported roots."""
    if not _envelope_available():
        pytest.skip("no envelope on this host")
    outside = tmp_path / "proxy-ca.pem"
    outside.write_text("-----BEGIN CERTIFICATE-----\n")
    monkeypatch.setenv("SSL_CERT_FILE", str(outside))
    work = tmp_path / "order" / "repo"
    work.mkdir(parents=True)
    with pytest.raises(isolation.WorkerIsolationError, match="certificate"):
        workers._confined_or_supervised(
            lambda: isolation.prepare_worker([sys.executable, "-c", "pass"], work, timeout_seconds=10, provider="t",
                                             reviewed=True, source_env={"SSL_CERT_FILE": str(outside)}),
            [sys.executable, "-c", "pass"], work, confinement="supervised")


def test_supervised_acceptance_of_a_workspace_script_runs_in_the_envelope_on_an_envelope_host(tmp_path):
    """Review finding (b4289ca + 9eb226f): ./check.sh was looked up in GREG's own working directory, refused as
    unavailable, and the supervised fallback then ran the worker-modifiable script with the body's filesystem."""
    if not _envelope_available():
        pytest.skip("no envelope on this host")
    clone = tmp_path / "order" / "repo"
    clone.mkdir(parents=True)
    escaped = tmp_path / "escaped.marker"
    script = clone / "check.sh"
    script.write_text(f"#!/bin/sh\necho reached > {escaped} 2>/dev/null\nexit 0\n")
    script.chmod(0o755)
    [result] = workers.run_tests([["./check.sh"]], clone, timeout=30, confinement="supervised")
    assert result["confinement"].startswith("envelope"), result
    assert result["passed"], result["tail"]
    assert not escaped.exists(), "worker-modifiable acceptance wrote outside its clone"


def test_a_workspace_executable_may_not_point_outside_the_workspace(tmp_path):
    clone = tmp_path / "repo"
    clone.mkdir()
    (clone / "check.sh").symlink_to("/bin/true")
    with pytest.raises(isolation.WorkerIsolationError, match="leaves the workspace"):
        isolation.prepare_worker(["./check.sh"], clone, 10, "acceptance-tests", reviewed=True, network=False,
                                 source_env={})


def test_a_launch_that_fails_inside_the_envelope_is_never_reported_as_supervised(tmp_path, monkeypatch):
    """Review finding (f6d146e): a reviewed provider set up in the OS envelope whose launch failed with an
    unexpected error got a receipt saying it ran supervised with its filesystem NOT confined."""
    if not _envelope_available():
        pytest.skip("no envelope on this host")
    from greg.capabilities import InvocationContext

    def fork_fails(argv, **kwargs):
        raise BlockingIOError(11, "Resource temporarily unavailable")
    fake = tmp_path / "codex"
    fake.write_text("#!/bin/sh\necho hi > out.md\n")
    fake.chmod(0o755)
    monkeypatch.setitem(workers.PROVIDERS, "codex",
                        workers.CliAgentWorker("codex", [str(fake), "exec", "-"], reviewed=True, runner=fork_fails))
    ws = tmp_path / "ws"
    ws.mkdir()
    ctx = InvocationContext(workspace=ws, read_roots=(tmp_path,), secrets=None, manifest=None, mission_id="m1",
                            authority_ref="a", grant_id="g", worker_confinement="supervised")
    summary = workers.commission({"order": "doc1", "mode": "document", "objective": "write", "max_budget_usd": 0.5,
                                  "timeout_seconds": 60, "acceptance": {"output": "out.md"},
                                  "allowed_paths": ["out.md"], "provider": "codex"}, ctx)
    assert summary["status"] == "FAILED" and "BlockingIOError" in summary["worker"]["error"]
    assert summary["worker"]["isolation"]["filesystem"] == "os-confined"
    assert summary["worker"]["supervision"] is None
