"""Hostile cases on the one-machine path that no earlier test covered (directive 2026-10-14 section 7).

Each test names the attack, the expected refusal or recovery, and asserts the observed result.
The full 20-attack matrix, mapping every attack to the test that exercises it, is
``tests/evidence/one-machine-20261014/adversarial-matrix.json`` (checked by the last test here).
No organ checkout is needed: these run in CI.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import types

import pytest

from greg import organs, templates, workers
from greg.body import Body, Layout
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.integration.test_greg_mind_constructs_capability import STAFFING
from tests.integration.test_one_machine import ENV, KERNEL, alive, dispatches, facts, greg, sandbox_repo, start_body, \
    wait_for, worker_processes

MATRIX = KERNEL / "tests" / "evidence" / "one-machine-20261014" / "adversarial-matrix.json"


def code_mission(home: Path, repo: Path, *, provider: str, order: str = "attack", allowed=("plan/*", "tests/*")):
    spec = templates.code_change(repo=str(repo), objective="record the plan with a test", order=order,
                                 provider=provider, allowed_paths=list(allowed), budget_usd=0.05,
                                 timeout_seconds=300, workspace_root=Layout(home).workspace)
    return spec


class Scripted:
    """Test double: applies fixed edits (and optional .git tampering). Never a frontier worker."""
    name = "scripted-attacker"

    def __init__(self, edits: dict[str, str]):
        self.edits = edits

    def available(self):
        return True, ""

    def run(self, order, cwd, *, stop_check=None):
        for rel, text in self.edits.items():
            (cwd / rel).parent.mkdir(parents=True, exist_ok=True)
            (cwd / rel).write_text(text)
        return workers.WorkerReport(self.name, self.name, 0, 0.1, 0.0, claim={"confidence": 1.0},
                                    summary="WORK_REPORT: {}")


def run_in_process(tmp_path, monkeypatch, provider, *, ticks=6):
    data = tmp_path / "data"
    data.mkdir()
    repo = sandbox_repo(data)
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data])
    monkeypatch.setitem(workers.PROVIDERS, "attacker", provider)
    spec = code_mission(home, repo, provider="attacker")
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        states = []
        for _ in range(ticks):
            states.append(body.tick()["missions"][0]["state"])
            clock.advance(31)
        outputs = [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
                   if isinstance(r.payload["result"].get("output"), dict)]
        return home, spec, states, outputs


TEST_FROM_DOUBLE = (KERNEL / "tests" / "one_machine_worker.py").read_text().split("TEST = '''", 1)[1] \
    .split("'''", 1)[0].replace("\\\\", "\\")


def test_attack_worker_lies_about_the_minds_certified_answer(tmp_path, monkeypatch):
    """Attack: the worker records staffed=9 (the certified optimum is 8) with a test that would check it.
    Expected: GREG runs the exhaustive test itself; it fails; the work is never ACCEPTED; no handoff."""
    lie = {"plan/plan.json": json.dumps({"assignment": [["Ana", "Dock2", 2], ["Ben", "Dock1", 4],
                                                        ["Cy", "Line", 3]], "staffed": 9}),
           "tests/test_plan.py": TEST_FROM_DOUBLE}
    home, spec, states, outputs = run_in_process(tmp_path, monkeypatch, Scripted(lie))
    assert "ACHIEVED" not in states
    receipt = [o for o in outputs if o.get("work_order") == "attack"][0]
    assert receipt["greg_tests_passed"] is False
    assert "ACCEPTED" not in [o.get("verdict") for o in outputs]
    assert not (Layout(home).workspace / spec["mission_id"].replace(":", "_") / "handoff-attack.md").exists()


def test_attack_worker_plants_git_hooks_and_filters_that_never_run(tmp_path, monkeypatch):
    """Attack: the worker writes .git/config (fsmonitor, a clean filter) and a pre-commit hook so that
    GREG's own git commands in the clone execute worker code. Expected: GREG restores the metadata it
    created before any worker code ran; the payload never executes; the honest change is collected."""
    marker = tmp_path / "pwned"
    payload = f"#!/bin/sh\ntouch {marker}\n"
    planted = {"plan/plan.json": json.dumps({"assignment": [["Ana", "Dock2", 2], ["Ben", "Dock1", 4],
                                                            ["Cy", "Line", 2]], "staffed": 8}),
               "tests/test_plan.py": TEST_FROM_DOUBLE, ".gitattributes": "* filter=evil\n",
               ".git/hooks/pre-commit": payload, ".git/evil.sh": payload,
               ".git/config": (f"[core]\n\trepositoryformatversion = 0\n\tfsmonitor = sh {tmp_path}/fsmon.sh\n"
                               f"[filter \"evil\"]\n\tclean = sh -c 'touch {marker}; cat'\n\trequired = true\n")}
    (tmp_path / "fsmon.sh").write_text(payload)
    original_run = Scripted.run

    def run(self, order, cwd, *, stop_check=None):
        report = original_run(self, order, cwd, stop_check=stop_check)
        os.chmod(cwd / ".git" / "hooks" / "pre-commit", 0o755)
        return report

    monkeypatch.setattr(Scripted, "run", run)
    home, spec, states, outputs = run_in_process(tmp_path, monkeypatch, Scripted(planted))
    assert not marker.exists(), "worker-planted git metadata executed inside GREG's collection"
    receipt = [o for o in outputs if o.get("work_order") == "attack"][0]
    assert "plan/plan.json" in receipt["changed_files"]
    assert receipt["worker"]["supervision"]["git_metadata"].startswith("restored")


def test_attack_worker_tampers_with_greg_trusted_git_copy(tmp_path, monkeypatch):
    """Attack: workers are not OS-confined, so a worker that knows the layout rewrites GREG's trusted
    copy of the clone's .git (beside its clone) to smuggle a filter in through the restore.
    Expected: the in-memory digest no longer matches; collection is refused; nothing is committed
    and the payload never runs."""
    marker = tmp_path / "pwned-trusted"
    original_run = Scripted.run

    def run(self, order, cwd, *, stop_check=None):
        report = original_run(self, order, cwd, stop_check=stop_check)
        trusted = cwd.parent / "base.git" / "config"
        trusted.write_text(trusted.read_text() + f"[filter \"evil\"]\n\tclean = sh -c 'touch {marker}; cat'\n")
        (cwd / ".gitattributes").write_text("* filter=evil\n")
        return report

    monkeypatch.setattr(Scripted, "run", run)
    honest = {"plan/plan.json": json.dumps({"assignment": [["Ana", "Dock2", 2], ["Ben", "Dock1", 4],
                                                           ["Cy", "Line", 2]], "staffed": 8}),
              "tests/test_plan.py": TEST_FROM_DOUBLE}
    home, spec, states, outputs = run_in_process(tmp_path, monkeypatch, Scripted(honest))
    assert not marker.exists(), "a filter smuggled through GREG's trusted copy executed"
    assert not [o for o in outputs if o.get("work_order") == "attack" and o.get("commit")]
    assert "ACHIEVED" not in states


def test_attack_worker_test_code_rewrites_git_metadata_during_greg_acceptance(tmp_path, monkeypatch):
    """Attack: the worker adds tests/conftest.py. GREG's own acceptance run executes it (network denied,
    filesystem not confined), and it rewrites the clone's .git after GREG restored it: a gpg program
    for commit signing plus a post-checkout hook, so GREG's own ``checkout -b``/``commit`` run worker
    code. Expected: GREG notices the metadata changed after its acceptance run and refuses to commit;
    the payload never runs."""
    marker = tmp_path / "pwned-acceptance"
    payload = tmp_path / "payload.sh"
    payload.write_text(f"#!/bin/sh\ntouch {marker}\nexit 1\n")
    payload.chmod(0o755)
    conftest = ("import pathlib, os\n"
                "git = pathlib.Path(__file__).resolve().parents[1] / '.git'\n"
                "cfg = git / 'config'\n"
                f"cfg.write_text(cfg.read_text() + '[commit]\\n\\tgpgsign = true\\n[gpg]\\n\\tprogram = {payload}\\n')\n"
                "hook = git / 'hooks' / 'post-checkout'\n"
                "hook.parent.mkdir(exist_ok=True)\n"
                f"hook.write_text('#!/bin/sh\\ntouch {marker}\\n')\n"
                "os.chmod(hook, 0o755)\n")
    planted = {"plan/plan.json": json.dumps({"assignment": [["Ana", "Dock2", 2], ["Ben", "Dock1", 4],
                                                            ["Cy", "Line", 2]], "staffed": 8}),
               "tests/test_plan.py": TEST_FROM_DOUBLE, "tests/conftest.py": conftest}
    home, spec, states, outputs = run_in_process(tmp_path, monkeypatch, Scripted(planted))
    assert not marker.exists(), "worker test code planted git metadata that GREG's git then executed"
    assert not [o for o in outputs if o.get("work_order") == "attack" and o.get("commit")]
    assert "ACHIEVED" not in states


def test_attack_absent_isolation_refuses_the_organ_exchange(tmp_path, monkeypatch):
    """Attack: the OS network filter cannot be installed. Expected: a truthful refusal before any
    organ code runs (never an unconfined run); nothing is recorded."""
    broken = types.ModuleType("offline_test")

    def install_filter():
        raise OSError("seccomp unavailable")

    broken.install_filter = install_filter
    monkeypatch.setitem(sys.modules, "offline_test", broken)
    dale, wmi = tmp_path / "dale", tmp_path / "wmi"
    (dale / "services").mkdir(parents=True)
    (dale / "services" / "idea_refinery.py").write_text("")
    (wmi / "src" / "services").mkdir(parents=True)
    (wmi / "src" / "services" / "opportunity_intake.py").write_text("")
    for root in (dale, wmi):          # committed, so the exchange can pin and snapshot each organ's code
        for cmd in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "c"]):
            subprocess.run(["git", "-C", str(root), *cmd], check=True, capture_output=True,
                           env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "GIT_CONFIG_NOSYSTEM": "1"})
    manifest, _ = BUILTINS["organ.exchange"]
    from events.spine import EventSpine
    from greg.journal import Journal
    from provenance.ledger import EvidenceLedger
    journal = Journal(EventSpine(EvidenceLedger("sha256:" + "1" * 64, path=str(tmp_path / "l.jsonl"))),
                      actor="spiffe://uniimente.internal/test/attack")
    python = Path(sys.executable)
    ctx = InvocationContext(workspace=tmp_path / "w", read_roots=(tmp_path, python.parent), secrets=None,
                            manifest=manifest, journal=journal, mission_id="m:isolation-attack")
    with pytest.raises(CapabilityError, match="network isolation unavailable"):
        organs.exchange({"daleobanks_root": str(dale), "wealthmachine_root": str(wmi),
                         "daleobanks_python": str(python), "wealthmachine_python": str(python),
                         "seed": "anything"}, ctx)
    assert journal.replay("organ.observed") == []


def test_attack_stale_heartbeat_is_never_shown_as_running(tmp_path):
    """Attack: a crashed body leaves a heartbeat saying RUNNING. Expected: Mission Control shows NOT
    RUNNING once the heartbeat is older than three minutes (unobserved health is not health)."""
    from greg.console import Console
    from greg.mission_control import projection
    home, _, _, _ = make_body(tmp_path)
    old = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    Layout(home).heartbeat.write_text(json.dumps({"pid": 1, "at": old, "state": "RUNNING", "missions": []}))
    view = projection(Console(home))
    assert view["identity"]["background"].startswith("NOT RUNNING")


def test_attack_hands_cannot_bind_an_answer_that_never_passed(tmp_path):
    """Attack: a worker strategy binds the Mind's answer from a check that is still failing.
    Expected: the strategy is held as unbound input; the worker is never commissioned."""
    home, key, body_id, _ = make_body(tmp_path)
    spec = templates.compiled_question(problem_id="no-pass", data={"sequence": "ACDE"},
                                       geometry={"geometry": "optimization", "subgeometry": "protein folding"})
    spec["strategies"].append({"action_id": "hands", "capability": "fs.write", "target": "workspace:out.txt",
                               "params": {"relative_path": "out.txt"}, "requires": ["answered"],
                               "bind": [{"param": "content", "from": {"check_id": "answered", "field": "result"},
                                         "type": "object", "render": "json"}],
                               "advances": ["answered"][:0] or ["answered"]})
    # a strategy may not advance a check it requires: give it its own check
    spec["strategies"][-1]["advances"] = ["written"]
    spec["success_checks"].append({"check_id": "written", "description": "out.txt exists",
                                   "sensor": {"capability": "fs.read", "target": "fs:out.txt",
                                              "params": {"path": str(Layout(home).workspace / "x" / "out.txt")}},
                                   "predicate": {"op": "contains", "field": "text", "value": "{"}})
    spec["light_cone"]["capabilities"] += ["fs.write", "fs.read"]
    spec["light_cone"]["targets"] += ["workspace:out.txt", "fs:out.txt"]
    spec["light_cone"]["max_consequence_class"] = "internal_write"
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(4):
            body.tick()
            clock.advance(31)
        assert not [e for e in body.journal.replay("mission.action") if e.payload["action_id"] == "hands"]


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="parent-death signal is Linux-only")
def test_attack_founder_stop_during_ongoing_work_ends_the_worker_now(tmp_path):
    """Attack (on the founder's authority): STOP while a worker is mid-run. Expected: the body exits
    within seconds, not after the worker's timeout; the worker's process group is dead; the dispatch
    is UNCERTAIN, so on restart the founder is asked and nothing is retried blind."""
    data = tmp_path / "data"
    data.mkdir()
    repo = sandbox_repo(data)
    tools = tmp_path / "tools"
    tools.mkdir()
    worker = tools / "worker.py"
    shutil.copy(KERNEL / "tests" / "one_machine_worker.py", worker)
    (tools / "HOLD").touch()
    home, _, _, _ = make_body(tmp_path, read_roots=[data])
    key, log = tmp_path / "founder.pem", tmp_path / "body.log"
    spec = code_mission(home, repo, provider="local-cli", order="stop-me")
    (tmp_path / "m.json").write_text(json.dumps(spec))
    assert greg(home, "mission", "submit", str(tmp_path / "m.json"), "--key", str(key),
                "--no-passphrase").returncode == 0
    body = start_body(home, worker, log)
    [pid] = wait_for(lambda: worker_processes(worker), timeout=120, what="the worker to start", body=body, log=log)
    stopped_at = time.monotonic()
    assert greg(home, "stop", "--local").returncode == 0
    assert body.wait(timeout=30) == 0
    assert time.monotonic() - stopped_at < 30, "STOP waited for the worker instead of ending it"
    wait_for(lambda: not alive(pid), timeout=10, what="the worker to be killed")
    order_dir = Layout(home).workspace / spec["mission_id"].replace(":", "_") / "work-orders" / "stop-me"
    assert (order_dir / "interrupted.json").exists() and not (order_dir / "evidence.json").exists()
    rows = facts(home, spec["mission_id"])["actions"]
    assert [a["status"] for a in rows if a["action_id"] == "commission-worker"] == ["UNCERTAIN"]
    Layout(home).stop_file.unlink()
    body = start_body(home, worker, log)
    wait_for(lambda: [r for r in facts(home, spec["mission_id"])["requests"] if r["kind"] == "RECONCILIATION"],
             timeout=60, what="a reconciliation request after restart", body=body, log=log)
    time.sleep(1.5)
    assert dispatches(home, spec["mission_id"], "commission-worker") == ["UNCERTAIN"] \
        and not worker_processes(worker), "retried without the founder"
    body.send_signal(signal.SIGTERM)
    assert body.wait(timeout=30) == 0


def test_every_attack_in_the_matrix_names_a_test_that_exists():
    """The adversarial matrix is evidence only if each row points at a real test."""
    matrix = json.loads(MATRIX.read_text())
    assert len(matrix["attacks"]) == 20
    for row in matrix["attacks"] + matrix["additional_attacks"]:
        assert row["expected"] and row["tests"], row["attack"]
        for node in row["tests"]:
            path, _, name = node.partition("::")
            source = (KERNEL / path).read_text()
            assert f"def {name.split('::')[-1]}(" in source, node


def test_every_test_in_the_matrix_has_an_observed_outcome():
    """Second review (seals and CI 3): the matrix points at observed-run.json for the outcome of every listed
    test, but rows were added without one. scripts/observe_adversarial_matrix.py regenerates it."""
    matrix = json.loads(MATRIX.read_text())
    observed = json.loads((MATRIX.parent / "observed-run.json").read_text())["results"]
    for row in matrix["attacks"] + matrix["additional_attacks"]:
        for node in row["tests"]:
            path, _, name = node.partition("::")
            *owners, function = name.split("::")             # JUnit: module[.Class]::function
            case = ".".join([path.removesuffix(".py").replace("/", "."), *owners]) + "::" + function
            outcomes = [r["outcome"] for key, r in observed.items() if key == case or key.startswith(case + "[")]
            assert outcomes and set(outcomes) == {"passed"}, (node, outcomes)
