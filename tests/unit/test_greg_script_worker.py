"""The founder-signed script worker: GREG's Hands with no model, no provider network and no credentials.

Every test here needs the real bubblewrap envelope (``real_isolation``): the point of the provider is the
confinement it runs under, so a substitute envelope would not test it. On a host without bubblewrap they skip.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import threading
import time

import pytest

from greg import templates, workers
from greg import worker_isolation as isolation
from greg.body import Body, Layout
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.unit.test_greg_workers import git, make_repo

pytestmark = pytest.mark.real_isolation


@pytest.fixture(autouse=True)
def need_envelope():
    try:
        isolation._backend(require_bubblewrap=True)
    except isolation.WorkerIsolationError as exc:
        if os.environ.get("GREG_REQUIRE_WORKER_ISOLATION") == "1":
            pytest.fail(str(exc))
        pytest.skip(f"host cannot provide the worker envelope: {exc}")


SCRIPT = '''
import os, socket, sys
from pathlib import Path
# 1. the work: a new function and its test, inside the allowed paths (git tracks no empty tests/ dir)
Path("tests").mkdir(exist_ok=True)
Path("pkg/sub.py").write_text("from pkg.calc import add\\n\\n\\ndef sub(a, b):\\n    return add(a, -b)\\n")
Path("tests/test_sub.py").write_text("from pkg.sub import sub\\n\\n\\ndef test_sub():\\n    assert sub(5, 3) == 2\\n")
# 2. what the envelope allowed: no network, no GREG environment, no founder home
try:
    socket.create_connection(("1.1.1.1", 443), timeout=2)
    network = "reached"
except OSError:
    network = "denied"
leaked = sorted(k for k in os.environ if "GREG" in k or "TOKEN" in k or "KEY" in k)
Path("tests/envelope.txt").write_text(f"network={network}\\nleaked={leaked}\\nhome={os.environ.get('HOME')}\\n")
print("GREG-REPORT {\\"changed\\": [\\"pkg/sub.py\\", \\"tests/test_sub.py\\"], \\"tests_run\\": [], \\"unresolved\\": [], \\"confidence\\": 1}")
'''


def run_mission(tmp_path, script, *, allowed=("pkg/*", "tests/*"), ticks=6, order="add-sub"):
    data = tmp_path / "data"
    data.mkdir()
    repo = make_repo(data)
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data])
    spec = templates.code_change(repo=str(repo), objective="add sub() with a founder-signed script", order=order,
                                 provider="script", allowed_paths=list(allowed), budget_usd=0.01, script=script,
                                 workspace_root=Layout(home).workspace)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(ticks):
            body.tick()
            clock.advance(60)
        events = {e.type: e.payload for e in body.journal.replay("mission.")}
        observed = [e.payload for e in body.journal.replay("mission.observed")]
        appraisal = body.appraise(spec["mission_id"]) if "greg.mission.achieved" in events else None
    return home, repo, spec, events, observed, appraisal


def test_a_signed_script_changes_the_clone_offline_and_greg_accepts_it_only_after_rerunning_the_tests(tmp_path):
    home, repo, spec, events, observed, appraisal = run_mission(tmp_path, SCRIPT)
    assert "greg.mission.achieved" in events, sorted(events)
    root = Layout(home).workspace / "m_work-add-sub" / "work-orders" / "add-sub"
    summary = json.loads((root / "evidence.json").read_text())["summary"]
    report = json.loads((root / "worker-report.json").read_text())
    assert summary["status"] == "COMPLETED" and summary["greg_tests_passed"] and summary["commit"]
    assert report["provider"] == "script" and report["identity"].startswith("script:") and report["cost_usd"] == 0.0
    assert report["spend"]["status"] == "reported" and report["spend"]["charge_usd"] == 0
    assert report["isolation"]["mechanism"] == "bubblewrap" and report["isolation"]["network_isolated"] is True
    assert report["isolation"]["network"] == "isolated-network-namespace"
    clone = root / "repo"
    assert git(clone, "rev-parse", "--abbrev-ref", "HEAD") == "greg/add-sub"
    envelope = (clone / "tests" / "envelope.txt").read_text()
    assert "network=denied" in envelope and "leaked=[]" in envelope and str(root) in envelope.split("home=")[1]
    assert (clone / "pkg" / "sub.py").is_file() and not (repo / "pkg" / "sub.py").exists(), "the source checkout is untouched"
    accepted = [o for o in observed if o["check_id"] == "work_accepted" and o["passed"]]
    assert accepted, observed
    assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]


def test_a_script_outside_the_allowed_paths_is_rejected_not_committed(tmp_path):
    escape = SCRIPT.replace('Path("pkg/sub.py")', 'Path("policy/rules.py").write_text("ALLOW = True\\n"); Path("pkg/sub.py")')
    home, repo, spec, events, observed, _ = run_mission(tmp_path, escape, ticks=4)
    assert "greg.mission.achieved" not in events
    root = Layout(home).workspace / "m_work-add-sub" / "work-orders" / "add-sub"
    summary = json.loads((root / "evidence.json").read_text())["summary"]
    # GREG keeps the collected change on its private greg/ branch as evidence; the independent appraisal
    # rejects it for scope, so nothing is accepted, handed off or promoted.
    assert "policy/rules.py" in summary["scope"]["outside_allowed"]
    assert any("REJECTED" in o["detail"] for o in observed if o["check_id"] == "work_accepted")
    assert (repo / "policy" / "rules.py").read_text() == "ALLOW = False\n"


def test_an_empty_script_is_refused_before_any_process_starts(tmp_path):
    order = workers.WorkOrder(order="x", mission_id="m:x", grant_id="g", authority_ref="a", mode="repository",
                              objective="o", acceptance={"run_changed_tests": True}, allowed_paths=("pkg/*",),
                              provider="script", max_budget_usd=0.01, timeout_seconds=60, context="   ")
    with pytest.raises(workers.WorkerError, match="script source"):
        workers.ScriptWorker().run(order, tmp_path)
    assert not (tmp_path.parent / ".worker-runtime").exists()


def test_a_signed_stop_interrupts_a_running_script_and_books_it_uncertain(tmp_path):
    sleeper = 'from pathlib import Path\nimport time\nPath("tests").mkdir(exist_ok=True)\nPath("tests/started.marker").write_text("started")\ntime.sleep(60)\n'
    data = tmp_path / "data"
    data.mkdir()
    repo = make_repo(data)
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data])
    spec = templates.code_change(repo=str(repo), objective="sleep", order="stop-script", provider="script",
                                 allowed_paths=["pkg/*", "tests/*"], budget_usd=0.01, script=sleeper,
                                 workspace_root=Layout(home).workspace)
    drop(home, signed(key, body_id, "MISSION", spec))
    root = Layout(home).workspace / "m_work-stop-script" / "work-orders" / "stop-script"
    marker = root / "repo" / "tests" / "started.marker"

    def stop_once_started():
        deadline = time.monotonic() + 15
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        if marker.exists():
            Layout(home).stop_file.write_text("local operator STOP fixture")
    threading.Thread(target=stop_once_started, daemon=True).start()
    started = time.monotonic()
    with Body(home) as body:
        body.tick()
        action = body.journal.replay("mission.action")[-1].payload
    assert marker.exists() and time.monotonic() - started < 15
    assert action["status"] == "UNCERTAIN", action
    summary = json.loads((root / "evidence.json").read_text())["summary"]
    assert summary["status"] == "UNCERTAIN" and summary["worker"]["interrupted"] and summary["commit"] is None
