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
from greg import worker_isolation as isolation
from greg.body import Body, Layout
from tests.greg_fixtures import Clock, drop, make_body, signed


def _host_envelope() -> str | None:
    """None when this host provides the real worker envelope (bubblewrap namespaces), else why not."""
    try:
        isolation._backend(require_bubblewrap=True)
        return None
    except isolation.WorkerIsolationError as exc:
        return str(exc)


@pytest.fixture(autouse=True)
def acceptance_envelope(monkeypatch, request):
    """These tests check GREG's governance of workers (binding, scope, protected surfaces, spend, collection).

    They use the real confined envelope whenever the host provides one. On a host without usable bubblewrap
    they substitute an envelope labelled ``scripted-test-envelope``, so governance stays tested everywhere;
    real confinement is tested in test_greg_worker_isolation.py and by the tests marked ``real_isolation``,
    which skip there (or fail when GREG_REQUIRE_WORKER_ISOLATION=1)."""
    import os
    unavailable = _host_envelope()
    if unavailable is None:
        return
    if "real_isolation" in request.keywords or os.environ.get("GREG_REQUIRE_WORKER_ISOLATION") == "1":
        if os.environ.get("GREG_REQUIRE_WORKER_ISOLATION") == "1":
            pytest.fail(unavailable)
        pytest.skip(f"host cannot provide the worker envelope: {unavailable}")

    def scripted_envelope(argv, cwd, timeout_seconds, provider, reviewed=False, config_files=None, *,
                          source_env=None, network=True, file_bytes=0):
        if reviewed is not True:
            raise isolation.WorkerIsolationError("unreviewed worker provider refused before dispatch",
                                                 evidence={"status": "unreviewed", "reason": "unreviewed"})
        runtime = Path(cwd).parent / ".worker-runtime" / provider
        runtime.mkdir(parents=True, exist_ok=True)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(runtime), "LANG": "C.UTF-8"}
        return {"argv": list(argv), "env": env, "preexec_fn": None, "runtime_root": runtime,
                "evidence": {"mechanism": "scripted-test-envelope", "network_isolated": not network}}
    monkeypatch.setattr(workers, "prepare_worker", scripted_envelope)


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


def run_mission(tmp_path, monkeypatch, edits, *, ticks=6, allowed=("pkg/*", "tests/*"), cost=0.01):
    data = tmp_path / "data"
    data.mkdir()
    repo = make_repo(data)
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data])
    worker = ScriptedWorker(edits, cost=cost)
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


@pytest.mark.parametrize('protected_path', [
    'policy/rules.py', 'greg/pipeline.py', 'greg/isolation.py',
    'greg/cognition/verification.py', 'greg/cognition/contracts.py',
    'greg/cognition/budget.py', 'greg/cognition/cortex.py', 'greg/cognition/bridge.py',
    'greg/cognition/seed_compat.py',
    'cortex/seed/verify.py', 'cortex/organs/adversarial.py', 'cortex/evaluation/run.py',
])
def test_a_change_to_a_protected_surface_is_never_accepted(tmp_path, monkeypatch, protected_path):
    edits = {**GOOD, protected_path: "ALLOW = True\n"}
    _, _, _, events, observed = run_mission(tmp_path, monkeypatch, edits,
                                         allowed=("pkg/*", "tests/*", "policy/*", "greg/*", "cortex/*"))
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


@pytest.mark.parametrize("raw", [float("nan"), float("inf"), -1, True, "nan", "-1", {}, []])
def test_invalid_spend_reserves_cap_without_fabricating_zero(raw):
    spend = workers.worker_spend(raw, 1)
    assert spend["status"] == "invalid" and spend["reported_usd"] is None
    assert spend["reserved_usd"] == spend["charge_usd"] == 1
    json.dumps(spend, allow_nan=False)


def test_unknown_reported_zero_and_overcap_spend_remain_distinct():
    missing = workers.worker_spend(None, 1)
    assert missing["status"] == "unknown" and missing["reported_usd"] is None
    assert missing["reserved_usd"] == 1
    zero = workers.worker_spend(0, 1)
    assert zero["status"] == "reported" and zero["reported_usd"] == 0
    assert zero["reserved_usd"] == 0
    assert workers.worker_spend(2, 1)["status"] == "over_cap"


def test_claude_worker_argv_is_bounded():
    order = workers.WorkOrder(order="x", mission_id="m:x", grant_id="g", authority_ref="a", mode="repository",
                              objective="o", acceptance={"tests": [["python", "-m", "pytest"]]},
                              allowed_paths=("greg/*",), provider="claude-code", max_budget_usd=1.5,
                              timeout_seconds=300, repo="/tmp")
    argv = workers.ClaudeCodeWorker(binary="/bin/claude").argv(order)
    assert argv[argv.index("--max-budget-usd") + 1] == "1.5"
    denied = argv[argv.index("--disallowedTools") + 1:]
    assert {"WebFetch", "WebSearch", "Bash(git push:*)", "Bash(git commit:*)"} <= set(denied)
    assert "--strict-mcp-config" in argv and "--no-session-persistence" in argv
    assert not any(a == "Bash" for a in argv[argv.index("--allowedTools") + 1:argv.index("--disallowedTools")])


@pytest.mark.parametrize("readdress", [False, True])
def test_appraisal_binds_acceptance_to_the_original_commission(tmp_path, monkeypatch, readdress):
    home, _, _, _, _ = run_mission(tmp_path, monkeypatch, GOOD)
    root = Layout(home).workspace / "m_work-add-sub" / "work-orders" / "add-sub"
    evidence_path = root / "evidence.json"
    evidence = json.loads(evidence_path.read_text())
    evidence["order"]["acceptance"]["tests"] = [["python", "-c", "pass"]]
    if readdress:
        forged = workers.WorkOrder(**evidence["order"]).digest()
        evidence["order_digest"] = forged
        evidence["summary"]["order_digest"] = forged
    evidence_path.write_text(json.dumps(evidence))
    config = json.loads(Layout(home).config.read_text())
    from greg.capabilities import BUILTINS, InvocationContext
    with Body(home) as body:
        ctx = InvocationContext(workspace=root.parents[1], read_roots=tuple(Path(r) for r in config["read_roots"]),
                                secrets=None, manifest=BUILTINS["worker.appraise"][0], journal=body.journal,
                                mission_id="m:work-add-sub")
        result = workers.appraise({"order": "add-sub"}, ctx)
        appraisal = body.appraise("m:work-add-sub")
    assert result["verdict"] == "REJECTED", result
    assert any("digest" in f or "canonical" in f for f in result["findings"])
    assert appraisal["verdict"] == "REFUTED", appraisal
    assert appraisal["checks"]["world_reobserved"] is False
    # Refuted for the binding, not incidentally: on a host without the worker envelope the separate appraiser
    # cannot re-run acceptance tests and refutes every worker mission, which once let a mutant survive in CI.
    assert any("canonical" in f or "digest" in f for f in appraisal["findings"]), appraisal["findings"]


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
    ({"worker": {"cost_usd": 9.0}}, 9.0, "provider_reported: over the signed cap"),   # actual spend, not the cap
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


def test_worker_environment_does_not_inherit_keys_home_or_proxy(tmp_path, monkeypatch):
    for key in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','AWS_SECRET_ACCESS_KEY','GITHUB_TOKEN',
                'GREG_SIGNING_KEY','HOME','HTTPS_PROXY','PYTHONPATH','NODE_OPTIONS'):
        monkeypatch.setenv(key, 'unrelated-host-secret-or-configuration')
    env=workers._worker_env(tmp_path)
    assert env['HOME']==str(tmp_path)
    assert env['TMPDIR']==str(tmp_path)
    assert not set(env) & {'OPENAI_API_KEY','ANTHROPIC_API_KEY','AWS_SECRET_ACCESS_KEY','GITHUB_TOKEN',
                          'GREG_SIGNING_KEY','HTTPS_PROXY','PYTHONPATH','NODE_OPTIONS'}


# -- extracted from #157 (worker OS isolation, bounded supervision, collector hardening) --

def test_provider_budget_is_not_rounded_above_the_signed_cap():
    order = workers.WorkOrder(order="x", mission_id="m:x", grant_id="g", authority_ref="a", mode="document",
                              objective="o", acceptance={"output": "draft.md"}, allowed_paths=("draft.md",),
                              provider="claude-code", max_budget_usd=0.005, timeout_seconds=300)
    argv = workers.ClaudeCodeWorker(binary="/bin/claude").argv(order)
    assert float(argv[argv.index("--max-budget-usd") + 1]) == order.max_budget_usd


def test_optional_provider_metadata_cannot_discard_reported_spend(tmp_path, monkeypatch):
    import sys
    monkeypatch.setattr(workers, "prepare_worker", lambda argv, *args, **kwargs: {
        "argv": argv, "env": {}, "preexec_fn": None, "runtime_root": tmp_path,
        "evidence": {"mechanism": "scripted-test-envelope"}})
    def provider_report(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, json.dumps({"total_cost_usd": 2.0, "result": "draft",
            "modelUsage": ["malformed"], "permission_denials": None, "num_turns": float("nan")}), "")
    order = workers.WorkOrder(order="x", mission_id="m:x", grant_id="g", authority_ref="a", mode="document",
                              objective="o", acceptance={"output": "draft.md"}, allowed_paths=("draft.md",),
                              provider="claude-code", max_budget_usd=1.0, timeout_seconds=300)
    report = workers.ClaudeCodeWorker(binary=sys.executable, runner=provider_report).run(order, tmp_path)
    assert report.cost_usd == 2.0 and workers.worker_spend(report.cost_usd, 1.0)["status"] == "over_cap"
    assert report.served_models == [] and report.permission_denials == [] and report.turns is None


@pytest.mark.parametrize("raw, status, charge", [
    (0, "reported", 0), (0.125, "reported", 0.125), ("0.125", "reported", 0.125),
    (None, "unknown", 1), (True, "invalid", 1), (-1, "invalid", 1),
    (float("nan"), "invalid", 1), (float("inf"), "invalid", 1),
    ("unpriced", "invalid", 1), ({"cost": 0}, "invalid", 1), (1.01, "over_cap", 1.01),
])
def test_spend_is_finite_nonnegative_or_conservatively_reserved(raw, status, charge):
    spend = workers.worker_spend(raw, 1.0)
    assert spend["status"] == status and spend["charge_usd"] == charge
    assert spend["reserved_usd"] == (1 if status in ("unknown", "invalid") else 0)
    json.dumps(spend, allow_nan=False)


@pytest.mark.parametrize("cost, status", [(None, "unknown"), (float("nan"), "invalid"), (1.01, "over_cap")])
def test_worker_spend_evidence_is_retained_and_unsafe_reporting_blocks_acceptance(tmp_path, monkeypatch, cost, status):
    home, _, worker, events, observed = run_mission(tmp_path, monkeypatch, GOOD, cost=cost)
    root = Layout(home).workspace / "m_work-add-sub" / "work-orders" / "add-sub"
    evidence = json.loads((root / "evidence.json").read_text())
    summary = evidence["summary"]
    assert worker.calls == 1
    assert summary["spend"]["status"] == status
    assert summary["cost_usd"] == (1.01 if status == "over_cap" else 1.0)
    assert json.loads((root / "worker-report.json").read_text())["spend"] == summary["spend"]
    if status != "unknown":
        assert "greg.mission.achieved" not in events
        assert summary["commit"] is None and summary["greg_tests"] == []
        assert any("REJECTED" in o["detail"] for o in observed if o["check_id"] == "work_accepted")


def document_work(tmp_path, monkeypatch, text, *, context="Frozen research context."):
    from greg.capabilities import BUILTINS, InvocationContext, SecretBroker
    ctx = InvocationContext(workspace=tmp_path / "workspace", read_roots=(tmp_path,),
                            secrets=SecretBroker(tmp_path / "secrets.json"),
                            manifest=BUILTINS["worker.commission"][0], mission_id="m:doc")
    monkeypatch.setitem(workers.PROVIDERS, "scripted-document", ScriptedWorker({"draft.md": text}))
    params = {"order": "source-draft", "mode": "document", "provider": "scripted-document",
              "objective": "Prepare a source-bound draft", "max_budget_usd": 1.0, "timeout_seconds": 60,
              "allowed_paths": ["draft.md"], "context": context,
              "acceptance": {"output": "draft.md", "require_context_quote": True}}
    summary = workers.commission(params, ctx)
    return summary, workers.appraise({"order": "source-draft"}, ctx)


def test_document_appraisal_accepts_exact_frozen_source_quote(tmp_path, monkeypatch):
    summary, appraisal = document_work(tmp_path, monkeypatch, "Draft analysis.\nFrozen research context.\n")
    assert summary["status"] == "COMPLETED" and appraisal["verdict"] == "ACCEPTED"


@pytest.mark.parametrize("text", ["A draft without source evidence.", "Frozen altered context."])
def test_document_appraisal_rejects_missing_or_altered_source_quote(tmp_path, monkeypatch, text):
    summary, appraisal = document_work(tmp_path, monkeypatch, text)
    assert summary["status"] == "COMPLETED"  # Collection success cannot decide source acceptance.
    assert appraisal["verdict"] == "REJECTED"
    assert any("frozen source context verbatim" in finding for finding in appraisal["findings"])


@pytest.mark.parametrize("config_path", [".git/config", ".gitconfig"])
def test_parent_collection_restores_trusted_git_metadata_before_filters_or_hooks_can_run(tmp_path, monkeypatch, config_path):
    marker = tmp_path / "escaped.marker"
    injection = f"sh -c 'echo escape > {marker}; cat'"
    edits = {**GOOD, ".gitattributes": "pkg/*.py filter=escape\n",
             config_path: ("[core]\nrepositoryformatversion = 0\nbare = false\n"
                             f"[filter \"escape\"]\nclean = {injection}\nrequired = true\n"),
             ".git/hooks/post-commit": f"#!/bin/sh\necho hook > {marker}\n"}
    home, _, _, _, _ = run_mission(tmp_path, monkeypatch, edits)
    assert not marker.exists()
    root = Layout(home).workspace / "m_work-add-sub" / "work-orders" / "add-sub"
    assert "escape" not in (root / "repo" / ".git" / "config").read_text()


def test_bounded_supervision_stops_excess_output_without_pipe_capture(tmp_path):
    import os, sys
    source = "import os; os.write(1, b'x' * (2 * 1024 * 1024))"
    with pytest.raises(workers.WorkerError, match="stdout/stderr ceiling"):
        workers.supervised_run([sys.executable, "-c", source], timeout=5, cwd=tmp_path, env=dict(os.environ))


def test_stop_before_supervision_launch_refuses_without_uncertain_spend(tmp_path):
    import os, sys
    marker = tmp_path / "never-started"
    source = f"from pathlib import Path; Path({str(marker)!r}).write_text('started')"
    with pytest.raises(workers.WorkerIsolationError, match="no provider process started"):
        workers.supervised_run([sys.executable, "-c", source], timeout=5, cwd=tmp_path,
                               env=dict(os.environ), stop_check=lambda: True)
    assert not marker.exists()


@pytest.mark.real_isolation
def test_stop_cancels_provider_namespace_and_preserves_uncertain_work_with_no_blind_retry(tmp_path, monkeypatch):
    import sys, threading, time
    from greg.worker_isolation import _CERT_ENV
    for name in _CERT_ENV:                       # a host CA outside the supported roots refuses dispatch (tested apart)
        monkeypatch.delenv(name, raising=False)
    data = tmp_path / "data"
    data.mkdir()
    repo = make_repo(data)
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data])
    provider = workers.CliAgentWorker("local-scripted-stop-test", [sys.executable, "-c", (
        "from pathlib import Path\nimport time\n"
        "Path('tests').mkdir(exist_ok=True)\n"
        "Path('tests/started.marker').write_text('started')\n"
        "time.sleep(60)\n")], reviewed=True)
    monkeypatch.setitem(workers.PROVIDERS, "local-scripted-stop-test", provider)
    spec = templates.code_change(repo=str(repo), objective="local scripted interruption test", order="stop-worker",
                                 provider="local-scripted-stop-test", allowed_paths=["pkg/*", "tests/*"],
                                 budget_usd=1.0, workspace_root=Layout(home).workspace)
    drop(home, signed(key, body_id, "MISSION", spec))
    root = Layout(home).workspace / "m_work-stop-worker" / "work-orders" / "stop-worker"
    marker = root / "repo" / "tests" / "started.marker"
    def request_stop_after_invocation():
        deadline = time.monotonic() + 10
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        if marker.exists():
            Layout(home).stop_file.write_text("local operator STOP fixture")
    watcher = threading.Thread(target=request_stop_after_invocation, daemon=True)
    watcher.start()
    started = time.monotonic()
    with Body(home) as body:
        body.tick()
        action = body.journal.replay("mission.action")[-1].payload
        assert action["status"] == "UNCERTAIN" and action["cost_usd"] == 1.0, action["reasons"]
        assert action["cost_reserved"]
    watcher.join(timeout=1)
    assert marker.exists() and time.monotonic() - started < 10
    summary = json.loads((root / "evidence.json").read_text())["summary"]
    assert summary["status"] == "UNCERTAIN" and summary["worker"]["interrupted"]
    assert summary["worker"]["isolation"]["mechanism"] == "bubblewrap"
    assert summary["commit"] is None and summary["greg_tests"] == []
    assert summary["spend"]["status"] == "unknown" and summary["spend"]["reserved_usd"] == 1.0
    Layout(home).stop_file.unlink()
    with Body(home) as body:
        body.tick()
        assert len(body.journal.replay("mission.action")) == 1
        assert body.engine.book.missions["m:work-stop-worker"].blocker["type"] == "reconciliation"


@pytest.mark.real_isolation
def test_acceptance_code_cannot_read_or_write_sibling_body_state_or_open_network(tmp_path):
    import sys
    from greg.worker_isolation import prepare_worker, WorkerIsolationError
    work = tmp_path / "clone"
    work.mkdir()
    victim = tmp_path / "body-state.fixture"
    victim.write_text("unchanged")
    source = ("from pathlib import Path\nimport socket\n"
              f"victim = Path({str(victim)!r})\n"
              "assert not victim.exists()\n"
              "try:\n    victim.write_text('escaped')\n"
              "except OSError:\n    pass\n"
              "else:\n    raise AssertionError('filesystem escape')\n"
              "try:\n    socket.create_connection(('1.1.1.1', 443), timeout=1)\n"
              "except OSError:\n    pass\n"
              "else:\n    raise AssertionError('network escape')\n")
    try:
        prepare_worker([sys.executable, "-c", source], work, timeout_seconds=30,
                       provider="acceptance-tests", reviewed=True, source_env={}, network=False)
    except WorkerIsolationError as exc:
        pytest.skip(f"host cannot provide the strict acceptance envelope: {exc}")
    results = workers.run_tests([[sys.executable, "-c", source]], work, timeout=30)
    assert results[0]["passed"], results
    assert victim.read_text() == "unchanged"


class HookPlantingWorker(ScriptedWorker):
    """A worker that plants an EXECUTABLE post-commit hook; ``--no-verify`` does not skip post-commit."""

    def __init__(self, edits, marker):
        super().__init__(edits)
        self.marker = marker

    def run(self, order, cwd):
        report = super().run(order, cwd)
        hook = cwd / ".git" / "hooks" / "post-commit"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text(f"#!/bin/sh\necho executed-in-greg > {self.marker}\n")
        hook.chmod(0o755)
        return report


def test_an_executable_hook_planted_by_the_worker_never_runs_in_gregs_collection(tmp_path, monkeypatch):
    marker = tmp_path / "hook-ran.marker"
    data = tmp_path / "data"
    data.mkdir()
    repo = make_repo(data)
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data])
    monkeypatch.setitem(workers.PROVIDERS, "hook-planter", HookPlantingWorker(GOOD, marker))
    spec = templates.code_change(repo=str(repo), objective="add sub()", order="add-sub", provider="hook-planter",
                                 allowed_paths=["pkg/*", "tests/*"], budget_usd=1.0,
                                 workspace_root=Layout(home).workspace)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(4):
            body.tick()
            clock.advance(60)
    clone = Layout(home).workspace / "m_work-add-sub" / "work-orders" / "add-sub" / "repo"
    assert git(clone, "rev-parse", "--abbrev-ref", "HEAD") == "greg/add-sub"     # GREG did commit the work
    assert not marker.exists()                                                 # and the planted hook never ran
    assert not (clone / ".git" / "hooks" / "post-commit").exists()             # trusted metadata was restored
