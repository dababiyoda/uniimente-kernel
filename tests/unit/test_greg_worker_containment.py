"""Acceptance I.G6 (Mission I): a commissioned worker cannot escape its work directory or replace its own evaluator.

Mission I: "Attempt ... evaluator substitution, ... worker escape ... Verify refusal, containment, retained
evidence, and recoverability." Two defects found while extending the live attack campaign:

- Worker escape. ``worker.commission`` ran its provider with a scrubbed environment but no OS confinement, so the
  worker (and anything it started) could read the Body home: the witness key, the device key, the ledger, the inbox,
  other missions' workspaces, and the Body's own environment through ``/proc/<pid>/environ``. On Linux with
  Landlock the worker now reads only the host runtime and writes only its own work directory
  (``greg.isolation.worker_grants``); ``/proc`` is limited to kernel information and the worker's own pid, because
  Landlock's ptrace scope does not cover another process's ``environ`` (probed 2026-10-15).
- Evaluator substitution. A repository order whose writable paths include its tests let the worker rewrite the
  frozen acceptance test (or add a ``conftest.py`` that turns failures into passes); the independent appraisal then
  re-ran the substituted evaluator and ACCEPTED wrong code. The appraisal now refuses a patch that modifies a file
  its explicit acceptance commands name, or adds or changes runner configuration.

Also fixed: ``CliAgentWorker`` executed its template's bare program name under the scrubbed ``PATH``, so a provider
installed where that PATH does not look (e.g. /usr/local/bin) could never start.

In-process Body with a test clock (SANDBOX) and real worker subprocesses; the founder key is a per-test key.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

from greg import isolation, workers
from greg.body import Body
from tests.greg_fixtures import Clock, drop, horizon, make_body, signed

LANDLOCK = isolation.available().get("available")


def order(name: str, *, mode="document", acceptance=None, allowed=("out.md",), provider="agent") -> workers.WorkOrder:
    return workers.WorkOrder(order=name, mission_id="m:x", grant_id="g", authority_ref="a", mode=mode,
                             objective="probe", acceptance=acceptance or {"output": "out.md"}, allowed_paths=allowed,
                             provider=provider, max_budget_usd=0.5, timeout_seconds=60)


def agent(tmp_path: Path, body: str) -> workers.CliAgentWorker:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    script = bin_dir / "probe-agent"
    script.write_text(f"#!{sys.executable}\n{body}\n")
    script.chmod(0o755)
    worker = workers.CliAgentWorker("probe-agent", ["probe-agent", "-"])
    worker.binary = str(script)              # what shutil.which would find with bin_dir on the host PATH
    return worker


def workdir(tmp_path: Path) -> Path:
    work = tmp_path / "body" / "workspace" / "m_x" / "work-orders" / "probe" / "work"
    work.mkdir(parents=True)
    return work


def test_a_cli_agent_runs_from_where_the_host_found_it_not_from_the_scrubbed_path(tmp_path):
    worker = agent(tmp_path, 'print("WORK_REPORT: {\\"confidence\\": 0.5}")')
    assert str(tmp_path / "bin") not in workers._worker_env(tmp_path)["PATH"]
    report = worker.run(order("probe"), workdir(tmp_path))
    assert report.exit_code == 0 and report.claim == {"confidence": 0.5}, report


@pytest.mark.skipif(not LANDLOCK, reason="Landlock ABI >= 3 is not available on this kernel")
def test_a_confined_worker_reads_nothing_of_the_body_and_writes_only_its_work_directory(tmp_path, monkeypatch):
    work = workdir(tmp_path)
    secret = tmp_path / "body" / "witness.key"
    secret.write_bytes(b"witness-secret")
    sibling, outside = tmp_path / "body" / "workspace" / "m_y" / "n.txt", tmp_path / "outside.txt"
    monkeypatch.setenv("GREG_CANARY", "canary-value")      # in the Body's own environment, never the worker's
    worker = agent(tmp_path, f"""
import os
results = []
for kind, path in [("read", {str(secret)!r}), ("read", "/proc/%d/environ" % os.getppid()),
                   ("write", {str(sibling)!r}), ("write", {str(outside)!r})]:
    try:
        if kind == "read":
            data = open(path, "rb").read()
            results.append("LEAK " + data.decode("utf-8", "replace"))
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").write("x")
            results.append("WROTE " + path)
    except OSError:
        results.append("denied")
open("out.md", "w").write("\\n".join(results))
""")
    report = worker.run(order("probe"), work)
    out = (work / "out.md").read_text()
    assert out.splitlines() == ["denied"] * 4, out
    assert "witness-secret" not in out and "canary-value" not in out
    assert not sibling.exists() and not outside.exists()
    assert report.confinement["filesystem"] == "landlock"
    inside_body = [r for r in report.confinement["readable"] if Path(r).is_relative_to(tmp_path / "body")]
    assert inside_body == [str(work.parent / "probe.prompt.txt")], inside_body   # its own prompt, nothing else


@pytest.mark.skipif(not LANDLOCK, reason="Landlock ABI >= 3 is not available on this kernel")
def test_a_worker_declared_as_an_interpreter_and_its_script_starts_and_stays_confined(tmp_path):
    """A provider declared as ``[python, script.py]`` (one-machine's local CLI): the confined worker can read the
    script its own argv names, or it cannot even start; it still cannot write beside that script."""
    tools = tmp_path / "tools"
    tools.mkdir()
    script, beside = tools / "worker.py", tools / "started"
    script.write_text(f"""
import sys
sys.stdin.read()
try:
    open({str(beside)!r}, "w").write("x")
    wrote = "WROTE"
except OSError:
    wrote = "denied"
open("out.md", "w").write(wrote)
print('WORK_REPORT: {{"confidence": 0.5}}')
""")
    worker = workers.CliAgentWorker("local-cli", [sys.executable, str(script)], stdin=True)
    work = workdir(tmp_path)
    report = worker.run(order("probe"), work)
    assert report.exit_code == 0, report
    assert (work / "out.md").read_text() == "denied" and not beside.exists()
    assert str(script) in report.confinement["readable"] and report.confinement["filesystem"] == "landlock"


@pytest.mark.skipif(not LANDLOCK, reason="Landlock ABI >= 3 is not available on this kernel")
def test_a_runtime_root_that_would_expose_the_body_home_refuses_the_worker(tmp_path):
    work = workdir(tmp_path)
    exposed = tmp_path / "body" / "probe-agent"              # an executable sitting in the Body home itself
    exposed.write_text(f"#!{sys.executable}\nprint('ran')\n")
    exposed.chmod(0o755)
    worker = workers.CliAgentWorker("probe-agent", ["probe-agent", "-"])
    worker.binary = str(exposed)
    with pytest.raises(workers.WorkerError, match="cannot be confined"):
        worker.run(order("probe"), work)


@pytest.mark.parametrize("name_status, replaced, shared", [
    ("M\ttests/test_calc.py\nM\tpkg/calc.py", ["tests/test_calc.py"], []),         # a named test weakened
    ("D\ttests/test_calc.py", ["tests/test_calc.py"], []),                          # or deleted
    ("A\ttests/conftest.py\nM\tpkg/calc.py", ["tests/conftest.py"], []),            # a runner hook added
    ("A\tpytest.ini", ["pytest.ini"], []),
    ("A\ttests/test_more.py\nM\tpkg/calc.py", [], []),                              # extending the suite is fine
    ("M\tpyproject.toml\nM\tpkg/calc.py", [], ["pyproject.toml"]),                  # may configure pytest: ask
])
def test_the_frozen_evaluator_is_the_named_acceptance_and_the_runner_configuration(name_status, replaced, shared):
    acceptance = {"tests": [["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_calc.py::test_sub"]]}
    assert workers.evaluator_findings(name_status, acceptance) == {"replaced": replaced, "shared": shared}


def test_worker_written_tests_are_not_a_frozen_evaluator():
    # ``run_changed_tests`` asks the worker to add or change tests; nothing is named, so only runner configuration counts.
    assert workers.evaluator_findings("M\ttests/test_calc.py", {"run_changed_tests": True}) == {"replaced": [],
                                                                                                "shared": []}
    assert workers.evaluator_findings("A\ttests/conftest.py", {"run_changed_tests": True})["replaced"] == [
        "tests/conftest.py"]


FORCE_PASS = """import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    outcome.get_result().outcome = "passed"
"""


class Substitute:
    """A scripted worker that writes a wrong sub() and replaces its evaluator in one of two ways."""
    name = "scripted-substitute"

    def __init__(self, how: str):
        self.how = how

    def available(self):
        return True, ""

    def run(self, order, cwd):
        (cwd / "pkg" / "calc.py").write_text("def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a + b\n")
        if self.how == "weaken":
            (cwd / "tests" / "test_calc.py").write_text("def test_sub():\n    assert True\n")
        else:
            (cwd / "tests" / "conftest.py").write_text(FORCE_PASS)
        return workers.WorkerReport(self.name, self.name, 0, 0.1, 0.1, claim={"confidence": 1.0},
                                    summary='WORK_REPORT: {"confidence": 1.0}')


def _repo(root: Path) -> Path:
    repo = root / "proj"
    (repo / "pkg").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "pkg" / "__init__.py").write_text("")
    (repo / "pkg" / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    (repo / "tests" / "test_calc.py").write_text("from pkg.calc import sub\n\n\ndef test_sub():\n    assert sub(3, 1) == 2\n")
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    subprocess.run([*git, "add", "-A"], check=True, capture_output=True)
    subprocess.run([*git, "commit", "-qm", "base"], check=True, capture_output=True)
    return repo


@pytest.mark.parametrize("how", ["weaken", "conftest"])
def test_a_worker_that_replaces_its_evaluator_never_closes_its_mission(tmp_path, monkeypatch, how):
    data = tmp_path / "data"
    data.mkdir()
    repo = _repo(data)
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data])
    monkeypatch.setitem(workers.PROVIDERS, "scripted", Substitute(how))
    strategy = {"action_id": "sub", "capability": "worker.commission", "target": "work:sub", "cost_usd": 0.5,
                "params": {"order": "sub", "mode": "repository", "repo": str(repo), "objective": "add sub()",
                           "acceptance": {"tests": [["python", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                                                     "tests/test_calc.py"]]},
                           "allowed_paths": ["pkg/*", "tests/*"], "provider": "scripted", "max_budget_usd": 0.5,
                           "timeout_seconds": 60}, "advances": ["sub_accepted"], "rationale": "sub"}
    check = {"check_id": "sub_accepted", "description": "independently accepted",
             "sensor": {"capability": "worker.appraise", "params": {"order": "sub"}, "target": "work:sub"},
             "predicate": {"op": "equals", "field": "verdict", "value": "ACCEPTED"}}
    drop(home, signed(key, body_id, "MISSION", {
        "mission_id": "m:sub", "founder_expression": "add sub", "intended_effect": "sub() correct", "priority": 50,
        "closure": {"kind": "bounded"}, "success_checks": [check], "strategies": [strategy],
        "light_cone": {"capabilities": ["worker.commission", "worker.appraise"], "targets": ["work:*"],
                       "max_consequence_class": "internal_write", "budget_usd": 1.0, "horizon": horizon()}}))
    clock = Clock()
    with Body(home, clock=clock) as b:
        for _ in range(6):
            b.tick()
            clock.advance(60)
        assert b.engine.book.missions["m:sub"].status != "ACHIEVED"
        observed = [e.payload for e in b.journal.replay("mission.observed") if e.payload["receipt"]]
        verdict = b.ledger.find(observed[-1]["receipt"]).payload["result"]["output"]
    assert verdict["verdict"] == "REJECTED", verdict
    assert any("frozen evaluator" in f for f in verdict["findings"]), verdict
    # The substituted evaluator really would have passed: the tests GREG ran on the patched clone are green.
    assert verdict["independent_tests"] and all(t["passed"] for t in verdict["independent_tests"]), verdict


@pytest.mark.skipif(not LANDLOCK, reason="Landlock ABI >= 3 is not available on this kernel")
def test_gregs_own_acceptance_run_is_confined_to_the_clone(tmp_path):
    """GREG's acceptance commands run the worker's patch, so run_tests confines them as the worker was: the run
    reports Landlock with the clone as its only writable root, writing outside the clone fails, and a temporary
    directory inside the clone still works."""
    clone, outside = tmp_path / "clone", tmp_path / "outside.txt"
    clone.mkdir()
    script = (f"import pathlib, tempfile\n"
              f"pathlib.Path(tempfile.mkdtemp(), 'ok').write_text('ok')\n"
              f"pathlib.Path({str(outside)!r}).write_text('x')\n")
    [result] = workers.run_tests([["python", "-c", script]], clone, timeout=60)
    assert not result["passed"] and "PermissionError" in result["tail"], result["tail"]
    assert not outside.exists()
    assert result["confinement"]["filesystem"] == "landlock"
    assert result["confinement"]["writable"] == [str(clone.resolve())]


@pytest.mark.skipif(not LANDLOCK, reason="Landlock ABI >= 3 is not available on this kernel")
def test_a_worker_cannot_plant_gregs_scratch_directory_to_make_its_own_run_uncertain(tmp_path, monkeypatch):
    """Merge review of 1e55bbd: GREG's confined acceptance run created a fixed ``.greg-tmp`` in the worker's clone.
    A worker that planted that name made the run raise before any test started; the error escaped the dispatch,
    which became UNCERTAIN, reserved the signed cap and asked the founder to reconcile a run that never left
    the clone. Each run now gets a fresh scratch name, and a clone that cannot host the run fails acceptance."""
    from tests.unit.test_greg_workers import GOOD, run_mission
    from greg.body import observe
    home, _, worker, _, _ = run_mission(tmp_path, monkeypatch, {**GOOD, ".greg-tmp": "planted\n"},
                                        allowed=("pkg/*", "tests/*", ".greg-tmp"))
    with observe(home, actor="spiffe://uniimente.internal/test/plant") as journal:
        commission = [e.payload for e in journal.replay("mission.action")
                      if e.payload.get("capability") == "worker.commission"]
        asks = [e.payload["kind"] for e in journal.replay("decision.requested")]
    assert worker.calls == 1 and [a["status"] for a in commission][:1] != ["UNCERTAIN"], commission
    assert "RECONCILIATION" not in asks


def test_a_clone_that_cannot_host_gregs_acceptance_run_fails_it_rather_than_raising(tmp_path, monkeypatch):
    def unwritable(*args, **kwargs):
        raise PermissionError(13, "Permission denied", str(tmp_path))
    monkeypatch.setattr(workers, "run_isolated", lambda *a, **k: unwritable())
    [result] = workers.run_tests([["python", "-c", "pass"]], tmp_path, timeout=10)
    assert result["passed"] is False and "could not run in the worker's clone" in result["tail"]


@pytest.mark.skipif(not LANDLOCK, reason="Landlock ABI >= 3 is not available on this kernel")
def test_a_provider_installed_in_the_founders_home_does_not_open_the_home_to_the_worker(tmp_path, monkeypatch):
    """Merge review of 1e55bbd: the worker was granted the parent of its binary's directory as an install tree, so
    a provider in ``~/.local/bin`` (a ``pip install --user`` script) made all of ``~/.local`` readable, and one in
    ``~/bin`` the whole home. Only a virtual environment directly in the home is granted whole; otherwise only its
    ``lib`` directory, and never the home or anything containing it."""
    home = tmp_path / "home"
    secret = home / ".local/share/keyrings/login.keyring"
    secret.parent.mkdir(parents=True)
    secret.write_text("FOUNDER-SECRET")
    venv = home / "venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = /usr/bin\n")
    monkeypatch.setenv("HOME", str(home))
    work = tmp_path / "body" / "workspace" / "repo"
    work.mkdir(parents=True)
    for where in (home / ".local/bin", home / "bin"):
        where.mkdir(parents=True, exist_ok=True)
        agent = where / "agent"
        agent.write_text(f"#!{sys.executable}\nimport sys\ntry:\n print('READ:' + open({str(secret)!r}).read())\n"
                         "except OSError as e:\n print('DENIED')\n")
        agent.chmod(0o755)
        granted = set(isolation.worker_grants(work, binaries=[str(agent)]))
        assert home.resolve() not in granted and (home / ".local").resolve() not in granted
        preexec, _ = workers._confined(work, str(agent))
        out = subprocess.run([str(agent)], capture_output=True, text=True, cwd=work, env=workers._worker_env(work),
                             preexec_fn=preexec, timeout=30).stdout
        assert out.strip() == "DENIED", (where, out)
    assert venv.resolve() in set(isolation.worker_grants(work, binaries=[str(venv / "bin" / "python")]))
