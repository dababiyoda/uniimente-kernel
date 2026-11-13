"""3ded0a7 regression: on a 'supervised' body whose host has no worker envelope (macOS: bubblewrap is Linux-only),
acceptance must fall back to #178 supervision (ONE_GREG_SYSTEM_SPEC section 6; run_tests docstring). macOS puts every
tempfile.TemporaryDirectory under a symlink (/var -> /private/var, /tmp -> /private/tmp), so worker.appraise's
fresh clone trips prepare_worker's symlink-cwd check, which raises status 'refused' before the backend probe and so
skips the fallback: the independent appraisal REJECTS work the commission receipt says passed."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from greg import templates, workers
from greg import worker_isolation as isolation
from greg.body import Body, Layout
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.unit.test_greg_workers import GOOD, ScriptedWorker, make_repo


def _no_backend(*, require_bubblewrap=False):
    # Exactly what _backend raises on darwin: no Landlock, and bwrap is only looked up on linux.
    reason = "Landlock requires supported Linux x86_64/aarch64; bubblewrap is unavailable on this host"
    raise isolation.WorkerIsolationError("worker OS filesystem isolation unavailable: " + reason,
                                         evidence={"status": "unsupported", "reason": reason,
                                                   "network": "provider-network-required"})


def _macos_like_host(tmp_path, monkeypatch):
    monkeypatch.setattr(isolation, "_backend", _no_backend)
    real = tmp_path / "private" / "var-folders-T"
    real.mkdir(parents=True)
    link = tmp_path / "var-folders-T"
    link.symlink_to(real)                          # as /var/folders/... -> /private/var/folders/...
    monkeypatch.setattr(tempfile, "tempdir", str(link))
    return link


def test_supervised_acceptance_without_backend_runs_supervised_in_symlinked_tmp(tmp_path, monkeypatch):
    link = _macos_like_host(tmp_path, monkeypatch)
    with tempfile.TemporaryDirectory(prefix="greg-appraise-") as tmp:   # what worker.appraise does
        fresh = Path(tmp) / "fresh"
        fresh.mkdir()
        [result] = workers.run_tests([[sys.executable, "-c", "pass"]], fresh, timeout=30, confinement="supervised")
    assert str(fresh).startswith(str(link))
    assert result["confinement"].startswith("supervised"), result
    assert result["passed"], result


def test_supervised_code_change_mission_on_host_without_backend_is_accepted(tmp_path, monkeypatch):
    _macos_like_host(tmp_path, monkeypatch)
    data = tmp_path / "data"
    data.mkdir()
    repo = make_repo(data)
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data], worker_confinement="supervised")
    monkeypatch.setitem(workers.PROVIDERS, "scripted", ScriptedWorker(GOOD))
    spec = templates.code_change(repo=str(repo), objective="add sub()", order="add-sub", provider="scripted",
                                 allowed_paths=["pkg/*", "tests/*"], budget_usd=1.0,
                                 workspace_root=Layout(home).workspace)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(6):
            body.tick()
            clock.advance(60)
        achieved = [e for e in body.journal.replay("mission.achieved")]
        outputs = [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
                   if isinstance(r.payload["result"].get("output"), dict)]
    [commission] = [o for o in outputs if o.get("work_order") == "add-sub"]
    verdicts = [o["verdict"] for o in outputs if "verdict" in o and o["verdict"] != "ABSENT"]
    # The commission receipt says acceptance passed under supervision ...
    assert commission["greg_tests_passed"] is True
    assert all(t["confinement"].startswith("supervised") for t in commission["greg_tests"])
    # ... so the independent re-run of the same acceptance on the same host must agree.
    assert verdicts and set(verdicts) == {"ACCEPTED"}, verdicts
    assert achieved
