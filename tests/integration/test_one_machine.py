"""One GREG: a single signed mission through Body, Mind, Genesis, Organs and Hands, across processes.

This is the whole-machine integration test the engineering interview called for (2026-10-14).
Nothing in the chain is a function emitting a success message; every stage is the canonical runtime:

1. Founder mission: the real ``greg mission submit`` interface signs the mission into the inbox
   and exits before the body starts (per-test Ed25519 key; NOT Alfonso's key).
2. Mind: the Competency Compiler classifies a bounded staffing problem; no admitted method fits.
3. Genesis: the CapabilityDeficit names ``assignment.staffing``; Genesis acquires an engine,
   constructs the function by certified reduction, qualifies it against brute force, and
   attaches it read-only inside the signed cone. The Mind answers with a certificate, no model.
4. Organs: DALEOBANKS and WealthMachine run their own code in their own interpreters under OS
   network denial, sign their messages, are verified at the kernel on one trace, and a second
   WealthMachine process reproduces the assessment.
5. Hands: only after both checks pass, a worker process receives the certified answer (bound
   from the passing observation's receipt) and records it with a test in a private clone.
6. Interruption: the body process is SIGKILLed while the worker is mid-run. The worker dies with
   it. On restart the uncertain commission is NOT retried blindly: the founder is asked, inspects
   the retained evidence, and reconciles; the work then runs exactly once more.
7. Appraisal: GREG's separate-process appraiser, then an independent verifier process that
   re-derives the answer by exhaustive search, re-applies the retained patch in a fresh clone and
   re-runs its test, and has WealthMachine re-evaluate the retained packet.
8. Mission Control shows this mission's trace from retained events only.
9. Learning: a later mission in a new process reuses the formed capability (nothing is re-formed),
   and Goal Gravity ranks it with reliability learned from the episode's receipted outcomes.
10. Proof classification: VEPMC stays 0; the sandbox whole-machine diagnostic counts 1.

The worker is a deterministic local CLI test double (``tests/one_machine_worker.py``), declared as
such and unreviewed, so the body is initialized with the founder's ``worker_confinement: supervised``
setting: the worker runs under process supervision and its retained evidence says its filesystem and
network were not confined. A default body refuses it. The organs are real. Requires the four UNIIMENTE_* organ variables (see test_greg_organs.py).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")
if not sys.platform.startswith("linux"):
    pytest.skip("the interruption stage relies on Linux PR_SET_PDEATHSIG", allow_module_level=True)

from greg import metrics, templates  # noqa: E402
from greg.body import Layout, observe  # noqa: E402
from tests.greg_fixtures import make_body  # noqa: E402
from tests.integration.test_greg_mind_constructs_capability import STAFFING  # noqa: E402
from tests.unit.test_greg_organs import SEED, live_organs, organ_roots  # noqa: E402

KERNEL = Path(__file__).resolve().parents[2]
ENV = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
       "PYTHONPATH": os.pathsep.join([str(KERNEL)] + [p for p in sys.path if "-packages" in p])}


def git(repo: Path, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True,
                   capture_output=True)


def sandbox_repo(root: Path) -> Path:
    """An expendable repository holding the signed problem; the worker's private clone comes from it."""
    repo = root / "sandbox"
    (repo / "tests").mkdir(parents=True)
    (repo / "problem.json").write_text(json.dumps(STAFFING, indent=1) + "\n")
    (repo / "README.md").write_text("Expendable sandbox for the one-machine mission.\n")
    (repo / "tests" / "__init__.py").write_text("")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    return repo


def greg(home: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "greg", "--home", str(home), *args], capture_output=True,
                          text=True, timeout=120, cwd=KERNEL, env=ENV)


def start_body(home: Path, worker: Path, log: Path) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-m", "tests.one_machine_body", str(home), str(worker), "60"],
                            cwd=KERNEL, env=ENV, stdout=log.open("a"), stderr=subprocess.STDOUT,
                            start_new_session=True)


def wait_for(predicate, *, timeout: float, what: str, body=None, log: Path | None = None):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        if body is not None and body.poll() is not None:
            break
        time.sleep(0.25)
    tail = log.read_text()[-3000:] if log and log.exists() else ""
    pytest.fail(f"timed out waiting for {what}; body exit={body.poll() if body else None}\n{tail}")


def facts(home: Path, mid: str) -> dict:
    with observe(home, actor="spiffe://uniimente.internal/test/one-machine") as journal:
        return {
            "actions": [e.payload for e in journal.replay("mission.action") if e.payload["mission_id"] == mid],
            "requests": [e.payload for e in journal.replay("decision.requested") if e.payload.get("mission_id") == mid],
            "achieved": [e.payload for e in journal.replay("mission.achieved") if e.payload["mission_id"] == mid],
            "appraised": [e.payload for e in journal.replay("mission.appraised") if e.payload["mission_id"] == mid],
            "organs": [e.payload for e in journal.replay("organ.observed") if e.payload.get("mission_id") == mid],
            "deficits": [e.payload for e in journal.replay("deficit.opened") if e.payload.get("mission_id") == mid],
            "resolved": [e.payload for e in journal.replay("deficit.resolved") if e.payload.get("mission_id") == mid],
            "recovered": [e.payload for e in journal.replay("body.recovered")],
        }


def done(rows, action_id):
    return [a for a in rows if a["action_id"] == action_id and a["status"] == "DONE"]


def worker_processes(worker: Path) -> list[int]:
    """Live processes running ``worker``, read from /proc: the test observes the confined worker from outside
    (where Landlock confines workers, the worker can write nothing but its own clone)."""
    found = []
    for proc in Path("/proc").iterdir():
        if proc.name.isdigit():
            try:
                argv = (proc / "cmdline").read_bytes().split(b"\0")
            except OSError:
                continue
            if str(worker).encode() in argv[:2]:      # executing the script (the body only names it later)
                found.append(int(proc.name))
    return found


def dispatches(home: Path, mid: str, action_id: str) -> list[str]:
    """GREG's own record of each dispatch of one strategy (a founder reconciliation is not a dispatch)."""
    return [a["status"] for a in facts(home, mid)["actions"] if a["action_id"] == action_id
            and a.get("route") != "founder_reconciliation" and "reconciles" not in a]


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:   # a zombie is dead for our purpose
        return Path(f"/proc/{pid}/stat").read_text().split()[2] != "Z"
    except OSError:
        return False


def test_one_signed_mission_runs_the_whole_machine_across_processes(tmp_path):
    organs = live_organs()
    data = tmp_path / "data"
    data.mkdir()
    repo = sandbox_repo(data)
    tools = tmp_path / "tools"
    tools.mkdir()
    worker = tools / "worker.py"
    shutil.copy(KERNEL / "tests" / "one_machine_worker.py", worker)
    home, _, _, _ = make_body(tmp_path, read_roots=[data, *organ_roots(organs)], worker_confinement="supervised")
    key = tmp_path / "founder.pem"
    log = tmp_path / "body.log"
    spec = templates.one_machine(problem_id="staff-om", data=STAFFING, sandbox_repo=str(repo), organs=organs,
                                 seed=SEED, provider="local-cli", workspace_root=Layout(home).workspace)
    mid = spec["mission_id"]
    (tmp_path / "mission.json").write_text(json.dumps(spec))

    # 1. The founder interface signs into the inbox and exits; no body is running yet.
    iface = greg(home, "mission", "submit", str(tmp_path / "mission.json"), "--key", str(key), "--no-passphrase")
    assert iface.returncode == 0, iface.stderr
    assert len(list(Layout(home).inbox.glob("*.json"))) == 1

    # 2-5. A body process runs Mind, Genesis and Organs, then commissions the worker, which holds.
    (tools / "HOLD").touch()
    body = start_body(home, worker, log)
    started = wait_for(lambda: worker_processes(worker), timeout=300, what="the worker to start", body=body,
                       log=log)
    seen = facts(home, mid)
    assert done(seen["actions"], "organs") and done(seen["actions"], "compile")
    assert {d["function"] for d in seen["deficits"]} == {"assignment.staffing", "graph.max_flow"}
    assert {d["function"] for d in seen["deficits"]} == {r.get("function") or d["function"]
                                                         for r in seen["resolved"] for d in seen["deficits"]
                                                         if d["deficit_id"] == r["deficit_id"]}
    assert {o["organ"] for o in seen["organs"]} == {"daleobanks", "wealthmachine"}
    assert not done(seen["actions"], "commission")

    # 6. Kill the body mid-work. The worker dies with it (PR_SET_PDEATHSIG), leaving no receipt.
    [worker_pid] = started
    os.kill(body.pid, signal.SIGKILL)
    body.wait(timeout=30)
    wait_for(lambda: not alive(worker_pid), timeout=30, what="the worker to die with the body")
    # Killed mid-dispatch: no outcome is recorded yet (the restart finds the open dispatch and records it UNCERTAIN).
    assert dispatches(home, mid, "commission") == [] and not worker_processes(worker)
    (tools / "HOLD").unlink()

    body = start_body(home, worker, log)
    request = wait_for(lambda: [r for r in facts(home, mid)["requests"] if r["kind"] == "RECONCILIATION"],
                       timeout=180, what="a reconciliation request", body=body, log=log)[-1]
    time.sleep(2)                                               # the body keeps ticking; it must not retry blind
    assert dispatches(home, mid, "commission") == ["UNCERTAIN"] and not worker_processes(worker), \
        "an uncertain commission was retried without the founder"
    order = spec["strategies"][2]["params"]["order"]
    order_dir = Layout(home).workspace / mid.replace(":", "_") / "work-orders" / order
    assert not (order_dir / "evidence.json").exists()          # the founder's evidence: it never completed
    answer = greg(home, "decide", request["request_id"], "reconcile_not_executed", "--key", str(key),
                  "--no-passphrase", "--reason", "no evidence.json or patch was retained for the order")
    assert answer.returncode == 0, answer.stderr
    wait_for(lambda: facts(home, mid)["appraised"], timeout=300, what="closure and appraisal", body=body, log=log)
    assert greg(home, "stop", "--local").returncode == 0
    assert body.wait(timeout=60) == 0
    (Layout(home).stop_file).unlink()

    closed = facts(home, mid)
    assert len(closed["achieved"]) == 1 and closed["appraised"][-1]["verdict"] == "VERIFIED", closed["appraised"]
    assert len(done(closed["actions"], "commission")) == 1
    assert [a["status"] for a in closed["actions"] if a["action_id"] == "commission"].count(
        "RECONCILED_NOT_EXECUTED") == 1
    assert dispatches(home, mid, "commission") == ["UNCERTAIN", "DONE"]   # interrupted, then once after reconciling
    assert closed["recovered"], "the restart was recorded as a recovery"
    [commission] = done(closed["actions"], "commission")
    supervision = json.loads((order_dir / "evidence.json").read_text())["summary"]["worker"]["isolation"]
    assert supervision["mode"] == "supervised" and supervision["filesystem"].startswith("NOT OS-confined")
    assert commission["bindings"][0]["from_check"] == "answered"

    # 7. Independent verification in separate processes.
    report_path = tmp_path / "verify.json"
    verify = subprocess.run([sys.executable, str(KERNEL / "scripts" / "verify_one_machine.py"), "--home", str(home),
                             "--mission", mid, "--wealthmachine-root", organs["wealthmachine_root"],
                             "--wealthmachine-python", organs["wealthmachine_python"], "--out", str(report_path)],
                            capture_output=True, text=True, timeout=600, cwd=KERNEL, env=ENV)
    report = json.loads(report_path.read_text())
    assert verify.returncode == 0 and report["verdict"] == "REDERIVED", (verify.stdout, report["findings"])
    assert report["greg_appraisal"]["verdict"] == "VERIFIED"
    assert all(report["checks"][k] for k in ("mind_answer_is_optimal", "organ_answer_rederived",
                                             "patch_reapplies_and_its_test_passes", "one_commission_done"))

    # 8. Mission Control: this mission's trace, from retained events only.
    from greg.console import Console
    from greg.mission_control import projection, render_view
    console = Console(home)
    view = projection(console)
    kinds = [s["kind"] for s in view["traces"][mid]]
    capabilities = {s.get("capability") for s in view["traces"][mid] if s["kind"] == "mission.action"}
    assert {"cognition.solve", "organ.exchange", "worker.commission", "fs.write"} <= capabilities
    for kind in ("deficit.opened", "capability.state", "organ.observed", "organ.appraised", "decision.requested",
                 "decision.answered", "mission.achieved", "mission.appraised"):
        assert kind in kinds, kind
    html = render_view(console, "proof", {})
    assert mid in html and "organ.appraised" in html and "never VEPMC" in html

    # 9. Learning survives restart: a later mission in a new process reuses what Genesis formed.
    with observe(home) as journal:
        formed = sorted({e.payload["capability_id"] for e in journal.replay("genesis.verified")
                         if e.payload.get("passed")})
        verified_before = len(journal.replay("genesis.verified"))
    second = templates.compiled_question(problem_id="staff-later", allow_construction=True,
                                         data={**STAFFING, "orders": STAFFING["orders"][:2]})
    (tmp_path / "second.json").write_text(json.dumps(second))
    assert greg(home, "mission", "submit", str(tmp_path / "second.json"), "--key", str(key),
                "--no-passphrase").returncode == 0
    body = start_body(home, worker, log)
    wait_for(lambda: facts(home, second["mission_id"])["appraised"], timeout=300, what="the later mission",
             body=body, log=log)
    assert greg(home, "stop", "--local").returncode == 0
    assert body.wait(timeout=60) == 0
    with observe(home) as journal:
        later = [e.payload for e in journal.replay("mission.appraised")
                 if e.payload["mission_id"] == second["mission_id"]]
        assert later[-1]["verdict"] == "VERIFIED"
        assert len(journal.replay("genesis.verified")) == verified_before, "nothing was re-qualified"
        receipts = [r.payload["result"]["output"] for r in journal.ledger.by_type("receipt")
                    if isinstance(r.payload["result"].get("output"), dict)
                    and r.payload["result"]["output"].get("problem_id") == "staff-later"]
        assert receipts and receipts[-1]["state"] == "ANSWERED"
        assert receipts[-1]["method_or_composition_selected"] in formed
        # ...and the episode's recorded outcomes changed a later decision through a governed pathway: the
        # first Goal Gravity ranking naming the later mission (written before it acted, by a new process)
        # used learned reliability, not the 0.5 prior a capability with no record gets. Ordering only:
        # no authority came with it.
        first = next(e.payload for e in journal.replay("gravity.ranked")
                     if second["mission_id"] in [r["mission_id"] for r in e.payload["ranking"]])
        learned = next(r for r in first["ranking"] if r["mission_id"] == second["mission_id"])
        assert learned["reliability"] > 0.5 and first["authority_created"] is False

        # 10. Proof classification: sandbox integration, never VEPMC.
        assert metrics.vepmc(journal)["VEPMC"] == 0
        sandbox = metrics.sandbox_whole_machine(journal)
        row = [r for r in sandbox["missions"] if r["mission_id"] == mid][0]
        assert row["whole_machine"] is True, row["missing"]
        assert sandbox["SANDBOX_WHOLE_MACHINE_CLOSURES"] == 1     # the later mission exercised only the Mind
        evidence = os.environ.get("UNIIMENTE_ONE_MACHINE_EVIDENCE")
        if evidence:   # retain a reviewable record of this exact run (never read back by the test)
            out = Path(evidence)
            out.mkdir(parents=True, exist_ok=True)
            (out / "verify.json").write_text(report_path.read_text())
            (out / "trace.json").write_text(json.dumps(view["traces"][mid], indent=1, default=str) + "\n")
            (out / "metrics.json").write_text(json.dumps({"vepmc": metrics.vepmc(journal), "sandbox": sandbox},
                                                         indent=1, default=str) + "\n")
            (out / "mission.json").write_text(json.dumps(spec, indent=1) + "\n")
            (out / "run.json").write_text(json.dumps({
                "mission_id": mid, "ledger_head": journal.ledger.head, "worker_dispatches": dispatches(home, mid, "commission"),
                "reconciliation_request": request["request_id"], "boots": len(journal.replay("body.booted")),
                "recoveries": len(journal.replay("body.recovered")), "later_mission": second["mission_id"],
                "later_method": receipts[-1]["method_or_composition_selected"], "formed": formed,
                "organ_heads": [o.get("organ") for o in closed["organs"]],
                "authority": "per-test Ed25519 key; NOT Alfonso's key; synthetic founder authority"},
                indent=1) + "\n")
