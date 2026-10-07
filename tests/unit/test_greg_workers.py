"""WorkOrder governance through the real Body: lease, private clone, GREG-collected evidence, independent appraisal.

The provider here is a SCRIPTED TEST DOUBLE that edits files deterministically. It exists to
test GREG's authority and appraisal rules, not worker capability; the real-worker proof is
``scripts/greg_hands_proof.py`` with the Claude Code CLI (evidence under docs/evidence/greg-hands/).
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from greg import templates, workers
from greg.body import Body, Layout
from tests.greg_fixtures import Clock, drop, make_body, signed


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def make_repo(root: Path) -> Path:
    repo = root / "proj"
    (repo / "pkg").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "pkg" / "__init__.py").write_text("")
    (repo / "pkg" / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    (repo / "policy").mkdir()
    (repo / "policy" / "rules.py").write_text("ALLOW = False\n")
    git(repo.parent, "init", "-q", str(repo))
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
    return repo


class ScriptedWorker:
    """Test double: applies fixed edits. Never presented as a frontier worker."""
    name = "scripted-test-double"

    def __init__(self, edits: dict[str, str], cost=0.01):
        self.edits, self.cost, self.calls = edits, cost, 0

    def available(self):
        return True, ""

    def run(self, order, cwd):
        self.calls += 1
        for rel, text in self.edits.items():
            (cwd / rel).parent.mkdir(parents=True, exist_ok=True)
            (cwd / rel).write_text(text)
        return workers.WorkerReport(self.name, self.name, 0, 0.1, self.cost, claim={"confidence": 1.0},
                                    summary="WORK_REPORT: {}")


GOOD = {"pkg/calc.py": "def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n",
        "tests/test_calc.py": "from pkg.calc import sub\n\n\ndef test_sub():\n    assert sub(3, 1) == 2\n"}


def run_mission(tmp_path, monkeypatch, edits, *, ticks=6, allowed=("pkg/*", "tests/*")):
    data = tmp_path / "data"
    data.mkdir()
    repo = make_repo(data)
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data])
    worker = ScriptedWorker(edits)
    monkeypatch.setitem(workers.PROVIDERS, "scripted", worker)
    spec = templates.code_change(repo=str(repo), objective="add sub()", order="add-sub", provider="scripted",
                                 allowed_paths=list(allowed), budget_usd=1.0, workspace_root=Layout(home).workspace)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(ticks):
            body.tick()
            clock.advance(60)
        events = {e.type: e.payload for e in body.journal.replay("mission.")}
        observed = [e.payload for e in body.journal.replay("mission.observed")]
    return home, repo, worker, events, observed


def test_accepted_work_is_committed_on_a_greg_branch_in_a_private_clone_and_the_mission_continues(tmp_path, monkeypatch):
    home, repo, worker, events, observed = run_mission(tmp_path, monkeypatch, GOOD)
    assert worker.calls == 1
    assert "greg.mission.achieved" in events
    accepted = [o for o in observed if o["check_id"] == "work_accepted" and o["passed"]]
    assert accepted
    handoff = Layout(home).workspace / "m_work-add-sub" / "handoff-add-sub.md"
    assert "greg/add-sub" in handoff.read_text()
    assert git(repo, "status", "--porcelain") == "" and git(repo, "branch", "--list", "greg/*") == ""  # source untouched
    clone = Layout(home).workspace / "m_work-add-sub" / "work-orders" / "add-sub" / "repo"
    assert git(clone, "rev-parse", "--abbrev-ref", "HEAD") == "greg/add-sub"
    assert "GREG work order add-sub" in git(clone, "log", "-1", "--format=%an")
    assert git(clone, "remote") == ""                                          # the clone can reach no remote
    evidence = json.loads((clone.parent / "evidence.json").read_text())
    assert evidence["summary"]["greg_tests_passed"] and evidence["summary"]["authority_created"] is False
    lease = json.loads((clone.parent / "lease.json").read_text())
    assert lease["push_rights"] is False and lease["grant_id"].startswith(("grant", "g")) or lease["grant_id"]


def test_a_change_to_a_protected_surface_is_never_accepted(tmp_path, monkeypatch):
    edits = {**GOOD, "policy/rules.py": "ALLOW = True\n"}
    _, _, _, events, observed = run_mission(tmp_path, monkeypatch, edits, allowed=("pkg/*", "tests/*", "policy/*"))
    assert "greg.mission.achieved" not in events
    verdicts = [o for o in observed if o["check_id"] == "work_accepted"]
    assert verdicts and not any(o["passed"] for o in verdicts)
    assert any("NEEDS_FOUNDER_DECISION" in o["detail"] for o in verdicts)


def test_a_change_outside_the_writable_surface_is_rejected(tmp_path, monkeypatch):
    edits = {**GOOD, "README.md": "rewritten\n"}
    _, _, _, events, observed = run_mission(tmp_path, monkeypatch, edits)
    assert "greg.mission.achieved" not in events
    assert any("REJECTED" in o["detail"] for o in observed if o["check_id"] == "work_accepted")


def test_failing_tests_are_rejected_by_the_independent_rerun(tmp_path, monkeypatch):
    edits = {"pkg/calc.py": GOOD["pkg/calc.py"],
             "tests/test_calc.py": "from pkg.calc import sub\n\n\ndef test_sub():\n    assert sub(3, 1) == 99\n"}
    _, _, _, events, observed = run_mission(tmp_path, monkeypatch, edits)
    assert "greg.mission.achieved" not in events


def test_no_test_change_means_no_acceptance(tmp_path, monkeypatch):
    _, _, _, events, _ = run_mission(tmp_path, monkeypatch, {"pkg/calc.py": GOOD["pkg/calc.py"]})
    assert "greg.mission.achieved" not in events


def test_appraisal_rejects_a_tampered_patch(tmp_path, monkeypatch):
    home, _, _, _, _ = run_mission(tmp_path, monkeypatch, GOOD)
    root = Layout(home).workspace / "m_work-add-sub" / "work-orders" / "add-sub"
    (root / "change.patch").write_bytes((root / "change.patch").read_bytes() + b"\n")
    config = json.loads(Layout(home).config.read_text())
    from greg.capabilities import BUILTINS, InvocationContext, SecretBroker
    ctx = InvocationContext(workspace=root.parents[1], read_roots=tuple(Path(r) for r in config["read_roots"]),
                            secrets=SecretBroker(tmp_path / "s.json"), manifest=BUILTINS["worker.appraise"][0])
    result = workers.appraise({"order": "add-sub"}, ctx)
    assert result["verdict"] == "REJECTED" and "digest" in result["findings"][0]


def test_claude_worker_argv_is_bounded():
    order = workers.WorkOrder(order="x", mission_id="m:x", grant_id="g", authority_ref="a", mode="repository",
                              objective="o", acceptance={"tests": [["python", "-m", "pytest"]]},
                              allowed_paths=("greg/*",), provider="claude-code", max_budget_usd=1.5,
                              timeout_seconds=300, repo="/tmp")
    argv = workers.ClaudeCodeWorker(binary="/bin/claude").argv(order)
    assert argv[argv.index("--max-budget-usd") + 1] == "1.50"
    denied = argv[argv.index("--disallowedTools") + 1:]
    assert {"WebFetch", "WebSearch", "Bash(git push:*)", "Bash(git commit:*)"} <= set(denied)
    assert "--strict-mcp-config" in argv and "--no-session-persistence" in argv
    assert not any(a == "Bash" for a in argv[argv.index("--allowedTools") + 1:argv.index("--disallowedTools")])


@pytest.mark.parametrize("params, message", [
    ({"order": "Bad Name"}, "short lowercase"),
    ({"order": "x", "objective": "o", "max_budget_usd": 0}, "max_budget_usd"),
    ({"order": "x", "objective": "o", "max_budget_usd": 1, "allowed_paths": ["*"]}, "bounded writable"),
])
def test_work_order_contract_refuses_unbounded_orders(tmp_path, params, message):
    from greg.capabilities import BUILTINS, InvocationContext, SecretBroker
    ctx = InvocationContext(workspace=tmp_path, read_roots=(tmp_path,), secrets=SecretBroker(tmp_path / "s.json"),
                            manifest=BUILTINS["worker.commission"][0])
    with pytest.raises(workers.WorkerError, match=message):
        workers.WorkOrder.from_params(params, ctx)


def test_a_worker_dies_with_its_body(tmp_path):
    """Regression from the interruption proof: a SIGKILLed body left its worker running under init."""
    import os, signal, sys, time
    if not sys.platform.startswith("linux"):
        pytest.skip("parent-death signal is Linux-only (stated limit)")
    marker = tmp_path / "child.pid"
    body = subprocess.Popen([sys.executable, "-c", (
        "import subprocess, sys, time\n"
        "from greg.workers import _die_with_body\n"
        f"p = subprocess.Popen(['sleep', '60'], preexec_fn=_die_with_body)\n"
        f"open({str(marker)!r}, 'w').write(str(p.pid))\n"
        "time.sleep(60)\n")], cwd=Path(__file__).resolve().parents[2])
    for _ in range(100):
        if marker.exists() and marker.read_text():
            break
        time.sleep(0.05)
    child = int(marker.read_text())
    os.kill(body.pid, signal.SIGKILL)
    body.wait()
    for _ in range(100):
        try:
            os.kill(child, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    os.kill(child, signal.SIGKILL)
    pytest.fail("worker outlived its body")


def test_the_mission_books_the_provider_reported_spend_under_the_signed_cap(tmp_path, monkeypatch):
    home, *_ = run_mission(tmp_path, monkeypatch, GOOD)
    with Body(home) as body:
        action = next(e.payload for e in body.journal.replay("mission.action")
                      if e.payload["capability"] == "worker.commission" and e.payload["status"] == "DONE")
        mission = body.engine.book.missions["m:work-add-sub"]
    assert action["cost_usd"] == 0.01 and action["cost_cap_usd"] == 1.0
    assert action["spend_basis"] == "provider_reported" and action["provider_reported_usd"] == 0.01
    assert mission.spent_usd == pytest.approx(0.01)


@pytest.mark.parametrize("output, booked, basis", [
    ({"worker": {"cost_usd": 0.3}}, 0.3, "provider_reported"),
    ({"worker": {"cost_usd": None}}, 2.0, "signed_cap: provider spend not reported"),
    ({"worker": {}}, 2.0, "signed_cap: provider spend not reported"),
    ({"worker": {"cost_usd": 9.0}}, 2.0, "signed_cap: provider report outside [0, cap]"),
    ({"worker": {"cost_usd": -1}}, 2.0, "signed_cap: provider report outside [0, cap]"),
    ({"worker": {"cost_usd": True}}, 2.0, "signed_cap: provider spend not reported"),
    (None, 2.0, "signed_cap: provider spend not reported"),
])
def test_metered_spend_never_books_less_than_a_trustworthy_report(output, booked, basis):
    from greg.missions import metered_spend
    out = metered_spend("worker.commission", output, 2.0)
    assert out["cost_usd"] == booked and out["spend_basis"] == basis and out["cost_cap_usd"] == 2.0


def test_capabilities_without_a_meter_book_the_signed_cap():
    from greg.missions import metered_spend
    assert metered_spend("browser.session", {"worker": {"cost_usd": 0.0}}, 1.5)["cost_usd"] == 1.5
