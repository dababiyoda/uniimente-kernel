"""ONE MACHINE, TEN STEPS: the founder's whole-machine proof on one supervised body, one ledger, real processes.

The body runs as its own OS process under supervisord. Every founder act goes through a real interface
process (the console over HTTP, or the CLI) that exits before the body acts. Workers, organs, solvers and
the appraiser are separate processes. The test only reads retained history and files, and sends real
signals. The steps, in the order the episode runs them:

   1. an authenticated mission through the real interface (console ask -> review -> sign)
   2. the mission survives the interface closing (the console process is terminated)
   7. SIGKILL mid-operation, autonomous restart, no duplicate consequence
   8. an independent appraiser process re-derives the evidence of every closure
   3. the Competency Compiler picks a non-LLM solver (CP-SAT / Z3) with an independent verifier
   5. a real missing function: Genesis constructs it over an engine it certifies and attaches it only
      inside the founder-signed scope
   4. the Hands commission a confined worker (a founder-signed script in a bubblewrap envelope with no
      network) that changes a private clone; GREG re-runs the tests in a fresh clone before accepting
      (7b: a SIGKILL while that worker is in flight asks the founder once and the work runs exactly once
      more; 7c: the same kill under a founder-signed standing mandate is settled with a recorded proof that
      the run was consequence-inert, asks the founder nothing, and the work still runs exactly once more)
   6. DALEOBANKS and WealthMachine, as two organ processes, exchange authenticated messages through a
      Kernel-led mission trace
   9. Mission Control renders the body's own truth at desktop, Chromebook and phone widths
  10. a verified correction changes a later decision: founder labels on briefs become a shadow policy that
      is kept only after it wins on three later briefs, and the next brief runs with it

Adversarial checks ride along: an envelope signed by another key is refused, a byte-identical replay has
no second effect, a different command reusing an accepted nonce is refused, a duplicate approval causes no
duplicate action, a signed STOP ends the body, and the separate-process appraiser refutes a tampered
deliverable and verifies it again once restored.

Reality: LABORATORY-VERIFIED on the host that runs it. A per-test Ed25519 key stands in for the founder;
nothing here counts toward VEPMC, authenticates Alfonso, spends money, publishes or contacts anyone.
Set GREG_ONE_MACHINE_EVIDENCE=<dir> to keep the ledger, traces, screenshots and summary.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

import pytest

pytest.importorskip("z3")
pytest.importorskip("ortools")
pytest.importorskip("networkx")
pytest.importorskip("scipy")

from greg import service, templates, workers                                              # noqa: E402
from greg import worker_isolation as isolation                                           # noqa: E402
from greg.templates import compiled_question, engineering_brief, organ_exchange          # noqa: E402
from tests.greg_fixtures import signed as sign_envelope                                  # noqa: E402
from tests.integration.test_greg_body_supervised import (ROOT, SUPERVISORD, events, greg, heartbeat, history,  # noqa: E402
                                                         supervisor_endpoint, wait_for)
from tests.integration.test_greg_cortex_mission import cortex_mission, cortex_params     # noqa: E402
from tests.integration.test_greg_mind_constructs_capability import STAFFING              # noqa: E402
from tests.integration.test_greg_product_path import console, free_port, http            # noqa: E402
from tests.unit.test_greg_organ_exchange import SIGNAL, _write                          # noqa: E402
from tests.unit.test_greg_script_worker import SCRIPT                                    # noqa: E402
from tests.unit.test_greg_workers import make_repo                                       # noqa: E402

pytestmark = pytest.mark.skipif(SUPERVISORD is None, reason="supervisord (requirements-dev) not installed")

EVIDENCE = os.environ.get("GREG_ONE_MACHINE_EVIDENCE")
VIEWPORTS = {"desktop": {"width": 1920, "height": 1080}, "chromebook": {"width": 1366, "height": 768},
             "phone": {"width": 390, "height": 844}}
QUESTIONS = ("What is GREG?", "What can it actually do right now?", "What is it doing?",
             "What valuable work can I command?", "What needs my authority?")
NOISE_KEY = "local:kernel"      # the brief flags the dirty local checkout; the founder calls that noise
SLOW_SCRIPT = '''
import time
from pathlib import Path
Path("tests").mkdir(exist_ok=True)
Path("tests/started.txt").write_text("in flight\\n")      # visible from outside: the worker is running
time.sleep(6)
''' + SCRIPT


def _need_envelope():
    try:
        isolation._backend(require_bubblewrap=True)
    except isolation.WorkerIsolationError as exc:
        pytest.skip(f"the Hands step needs the real worker envelope: {exc}")


def _chromium():
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return None
    for candidate in (os.environ.get("GREG_CHROMIUM"), "/opt/pw-browsers/chromium", shutil.which("chromium"),
                      shutil.which("chromium-browser"), shutil.which("google-chrome")):
        if candidate and Path(candidate).exists():
            return candidate
    return None


class Episode:
    """One body, one founder key, one ledger; every act through a real interface process."""

    def __init__(self, tmp_path):
        self.tmp = tmp_path
        self.home, self.key = tmp_path / "body", tmp_path / "founder.pem"
        self.data = tmp_path / "data"
        self.data.mkdir()
        self.deliveries = tmp_path / "Deliveries"
        self.trace = {"steps": {}, "adversarial": {}, "missions": {}}
        self.started = time.monotonic()

    # -- founder interface processes -----------------------------------------------------------------
    def submit(self, spec: dict, name: str) -> str:
        path = self.tmp / f"{name}.json"
        path.write_text(json.dumps(spec))
        greg(self.home, "mission", "submit", str(path), "--key", str(self.key), "--no-passphrase")
        return spec["mission_id"]

    def decide(self, request_id: str, answer: str = "approve"):
        greg(self.home, "decide", request_id, answer, "--reason", "one-machine proof", "--key", str(self.key),
             "--no-passphrase")

    def request_for(self, mission_id: str):
        return [r for r in events(self.home, "decision.requested") if r.get("mission_id") == mission_id]

    def achieved(self, mission_id: str) -> bool:
        return any(e["mission_id"] == mission_id for e in events(self.home, "mission.achieved"))

    def run_to_closure(self, mission_id: str, *, timeout: float = 120, answered=()) -> dict:
        """Wait for the mission to close, approving at most one founder decision per distinct request."""
        answered = set(answered)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.achieved(mission_id):
                break
            for request in self.request_for(mission_id):
                if request["request_id"] not in answered:
                    self.decide(request["request_id"])
                    answered.add(request["request_id"])
            time.sleep(0.3)
        assert self.achieved(mission_id), f"{mission_id} did not close; requests={self.request_for(mission_id)}"
        appraisal = wait_for(lambda: [a for a in events(self.home, "mission.appraised") if a["mission_id"] == mission_id],
                             timeout=90, what=f"independent appraisal of {mission_id}")[-1]
        self.trace["missions"][mission_id] = {"appraisal": appraisal["verdict"], "approvals": sorted(answered),
                                              "done_actions": self.done(mission_id)}
        return appraisal

    def done(self, mission_id: str) -> list:
        return [a["action_id"] for a in events(self.home, "mission.action")
                if a["mission_id"] == mission_id and a["status"] == "DONE"]

    def receipt_outputs(self, predicate):
        ledger, _ = history(self.home)
        try:
            return [r.payload["result"]["output"] for r in ledger.by_type("receipt")
                    if isinstance(r.payload["result"].get("output"), dict) and predicate(r.payload["result"]["output"])]
        finally:
            ledger.close()

    def event_id_of_done(self, mission_id: str) -> str:
        ledger, journal = history(self.home)
        try:
            return [e.event_id for e in journal.replay("mission.action")
                    if e.payload["mission_id"] == mission_id and e.payload["status"] == "DONE"][-1]
        finally:
            ledger.close()


def _organ_roots(ep: Episode) -> tuple[Path, Path]:
    real = os.environ.get("GREG_TEST_DALEOBANKS"), os.environ.get("GREG_TEST_WMI")
    if all(real):
        ep.trace["organs"] = "real checkouts"
        return Path(real[0]), Path(real[1])
    # CI: the stand-in organs with the real organs' entry points and the real Kernel bridge transport
    from tests.unit import test_greg_organ_exchange as ox_test
    d, w = ep.data / "organs" / "daleobanks", ep.data / "organs" / "wmi"
    for name, text in (("services/__init__.py", ""), ("services/context_packet.py", ox_test.CONTEXT_PACKET_STUB),
                       ("services/venture_protocol.py", ox_test.VENTURE_PROTOCOL_STUB),
                       ("services/bridge_security.py", "from adapters.bridge_transport import *\n"),
                       ("services/ledger.py", ox_test.LEDGER_STUB), ("db/__init__.py", ""), ("db/models.py", ox_test.MODELS_STUB)):
        _write(d / name, text)
    for name, text in (("src/__init__.py", ""), ("src/services/__init__.py", ""),
                       ("src/services/opportunity_intake.py", ox_test.WMI_STUB)):
        _write(w / name, text)
    ep.trace["organs"] = "stand-in organs (set GREG_TEST_DALEOBANKS and GREG_TEST_WMI for the real checkouts)"
    return d, w


def _git(repo: Path, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def _appraise(ep: Episode, mission_id: str) -> dict:
    """Run the appraiser as its own process over the head-pinned ledger, exactly as the body does."""
    config = json.loads((ep.home / "body.json").read_text())
    ledger, _ = history(ep.home)
    try:
        head = ledger.head
    finally:
        ledger.close()
    request = {"ledger": str(ep.home / "ledger.jsonl"), "constitution": config["constitution_hash"], "head": head,
               "mission_id": mission_id, "read_roots": config["read_roots"], "deliver_root": config["deliver_root"],
               "artifact_root": str(ep.home / "artifacts"),
               "workspace": str(ep.home / "workspace" / mission_id.replace(":", "_")),
               # the postures the original ran in, as Body.appraisal_request passes them
               "worker_confinement": workers.confinement_mode(config.get("worker_confinement")),
               "confined_egress": bool(config.get("confined_egress"))}
    out = subprocess.run([sys.executable, "-m", "greg.appraisal"], input=json.dumps(request), capture_output=True,
                         text=True, timeout=120, cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)})
    assert out.returncode == 0, out.stderr[-800:]
    return json.loads(out.stdout)


def _age_briefs(deliveries: Path, hours: float = 25):
    folder = deliveries / "briefs"
    for path in folder.glob("*.md") if folder.exists() else []:
        aged = time.time() - hours * 3600
        os.utime(path, (aged, aged))


def test_one_machine_ten_steps_on_one_body_with_real_processes(tmp_path):
    _need_envelope()
    ep = Episode(tmp_path)
    # the world: a dirty local checkout (the brief flags it), a code repository for the Hands, a signal for the organs
    kernel = ep.data / "kernel"
    kernel.mkdir()
    _git(kernel, "init", "-q", "-b", "main")
    (kernel / "a.txt").write_text("one")
    _git(kernel, "add", "a.txt")
    _git(kernel, "commit", "-q", "-m", "first")
    (kernel / "dirty.txt").write_text("uncommitted")
    proj = make_repo(ep.data)
    signal_file = _write(ep.data / "signals" / "pod.json", json.dumps(SIGNAL))
    daleobanks_root, wmi_root = _organ_roots(ep)
    read_roots = [ep.data] + ([daleobanks_root, wmi_root] if "real" in ep.trace["organs"] else [])

    init = ["init", "--deliver-root", str(ep.deliveries)]
    for root in read_roots:
        init += ["--read-root", str(root)]
    greg(ep.home, *init)
    public = greg(ep.home, "founder", "keygen", "--key", str(ep.key), "--no-passphrase").stdout.strip()
    greg(ep.home, "founder", "enroll", "--pubkey", public)
    body_id = json.loads((ep.home / "body.json").read_text())["body_id"]

    conf = tmp_path / "supervisord.conf"
    (ep.home / "logs").mkdir(exist_ok=True)
    endpoint, ctl = supervisor_endpoint(tmp_path)
    conf.write_text(f"[supervisord]\nnodaemon=true\nlogfile={tmp_path / 'sd.log'}\npidfile={tmp_path / 'sd.pid'}\n"
                    + endpoint + "[rpcinterface:supervisor]\nsupervisor.rpcinterface_factory = "
                    "supervisor.rpcinterface:make_main_rpcinterface\n" + ctl
                    + service.supervisord_program(ep.home, tick_seconds=0.3))
    supervisor = subprocess.Popen([SUPERVISORD, "-c", str(conf)], cwd=ROOT, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
    port = free_port()
    ui = None
    try:
        first = wait_for(lambda: heartbeat(ep.home)["state"] == "RUNNING" and heartbeat(ep.home), what="body start")
        ep.trace["body"] = {"pid_at_start": first["pid"], "boot_id": first.get("boot_id")}

        # ---- 1. authenticated mission through the real interface; 2. the interface closes -------------------
        ui = console(ep.home, ep.key, port)
        token = re.search(r"name=csrf value='([^']+)'", http(port, "/")[1]).group(1)
        # naming the two local checkouts keeps the brief local in both modes (the real organs have GitHub remotes)
        url, review = http(port, "/ask", {"csrf": token, "text": "Brief me on the state of my kernel and proj repositories"})
        assert "Must ask you first" in review and "brief.engineering" in review
        http(port, "/sign", {"csrf": token, "proposal": url.rsplit("/", 1)[1]})
        ui.terminate()
        ui.wait(10)
        ui = None                                                        # step 2: no interface process is alive
        request = wait_for(lambda: events(ep.home, "decision.requested"), what="approval boundary")[0]
        brief_mission = request["mission_id"]
        assert request["kind"] == "APPROVAL" and request["authority_requested"]["capability"] == "brief.engineering"
        assert not (ep.deliveries / "briefs").exists() or not list((ep.deliveries / "briefs").glob("*.md"))
        ep.trace["steps"]["1_authenticated_mission_via_real_interface"] = {
            "interface": "greg console subprocess over HTTP (ask -> review -> sign)", "mission_id": brief_mission}
        ep.trace["steps"]["2_mission_survives_interface_close"] = {
            "console_terminated": True, "body_reached_approval_boundary_alone": True}

        # ---- adversarial: another key's envelope and a replayed envelope are refused ----------------------------
        other_key = tmp_path / "other.pem"
        greg(ep.home, "founder", "keygen", "--key", str(other_key), "--no-passphrase")
        from greg.founder import load_founder_key
        forged = sign_envelope(load_founder_key(other_key, None), body_id, "MISSION",
                               engineering_brief(local={"kernel": str(kernel)}, github=[], today="forged"))
        (ep.home / "inbox" / "forged.json").write_text(json.dumps(forged))
        rejected = wait_for(lambda: events(ep.home, "command.rejected"), what="forged envelope refused")
        assert rejected and not any(e["mission_id"] == "m:engineering-brief-forged" for e in events(ep.home, "mission.registered"))
        genuine = sign_envelope(load_founder_key(ep.key, None), body_id, "BODY_PAUSE", {})
        (ep.home / "inbox" / "pause-1.json").write_text(json.dumps(genuine))
        wait_for(lambda: events(ep.home, "body.paused") and heartbeat(ep.home)["state"] == "PAUSED", what="pause")
        # a byte-identical replay is an idempotent no-op (the inbox is idempotent on digest): no second effect
        (ep.home / "inbox" / "pause-replay.json").write_text(json.dumps(genuine))
        wait_for(lambda: (ep.home / "inbox" / "processed" / "pause-replay.json").exists(), what="replay consumed")
        assert len(events(ep.home, "body.paused")) == 1
        # a different command that reuses an accepted nonce is refused, and changes nothing
        reused = sign_envelope(load_founder_key(ep.key, None), body_id, "BODY_RESUME", {}, nonce=genuine["nonce"])
        (ep.home / "inbox" / "resume-reused-nonce.json").write_text(json.dumps(reused))
        replayed = wait_for(lambda: [r for r in events(ep.home, "command.rejected") if r["file"] == "resume-reused-nonce.json"],
                            what="reused nonce refused")
        assert "replayed command nonce" in replayed[0]["reason"] and heartbeat(ep.home)["state"] == "PAUSED"
        assert not events(ep.home, "body.resumed")
        greg(ep.home, "resume", "--key", str(ep.key), "--no-passphrase")
        wait_for(lambda: events(ep.home, "body.resumed") and heartbeat(ep.home)["state"] == "RUNNING", what="resume")
        ep.trace["adversarial"]["forged_key_envelope_refused"] = str(rejected[0].get("reason") or rejected[0])[:200]
        ep.trace["adversarial"]["byte_identical_replay_no_second_effect"] = {"body_paused_events": 1}
        ep.trace["adversarial"]["reused_nonce_refused"] = replayed[0]["reason"][:200]

        # ---- 7. SIGKILL while waiting at the approval boundary; autonomous restart; no duplicate ----------------
        os.kill(first["pid"], signal.SIGKILL)
        second = wait_for(lambda: heartbeat(ep.home)["pid"] != first["pid"] and heartbeat(ep.home)["state"] == "RUNNING"
                          and heartbeat(ep.home), what="supervisor restart after SIGKILL")
        wait_for(lambda: events(ep.home, "body.recovered"), what="recovery record")
        time.sleep(1.5)
        assert len(ep.request_for(brief_mission)) == 1, "remembered, not re-escalated"
        ep.trace["steps"]["7_sigkill_restart_no_duplicate"] = {"killed_pid": first["pid"], "restarted_pid": second["pid"],
                                                               "decision_requests_after_restart": 1}

        # ---- approval through a fresh interface process; 8. the separate-process appraiser verifies -------------
        ep.decide(request["request_id"])
        appraisal = ep.run_to_closure(brief_mission)
        assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
        assert appraisal["checks"]["founder_signature_verified"] and appraisal["checks"]["world_reobserved"]
        briefs_delivered = sorted((ep.deliveries / "briefs").glob("*.md"))
        assert len(briefs_delivered) == 1 and ep.done(brief_mission) == ["deliver-engineering-brief"]
        ep.decide(request["request_id"])                                 # adversarial: a duplicate approval
        time.sleep(1.5)
        assert ep.done(brief_mission) == ["deliver-engineering-brief"] and len(list((ep.deliveries / "briefs").glob("*.md"))) == 1
        ep.trace["adversarial"]["duplicate_approval_no_duplicate_action"] = True
        ep.trace["steps"]["8_independent_appraiser_process"] = {
            "mechanism": "python -m greg.appraisal in a separate process over a head-pinned read-only ledger",
            "first_verdict": appraisal["verdict"], "checks": appraisal["checks"]}

        # ---- 3. the Competency Compiler picks a non-LLM solver with an independent verifier --------------------
        cortex_id = ep.submit(cortex_mission("m:one-cortex", cortex_params()), "cortex")
        appraisal = ep.run_to_closure(cortex_id)
        assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
        receipts = ep.receipt_outputs(lambda o: o.get("proof_type") == "cortex_receipt")
        assert receipts and receipts[-1]["output"]["answer"]["objective"] == 7
        r = receipts[-1]
        assert r["method"].startswith("cognition.cortex.") and r["authority_created"] is False, r["method"]
        certificate = r["proof_artifact"]["proof_artifacts"][0]["certificate"]
        assert certificate["status"] == "CERTIFIED" and r["outcome"]["outcome"] == "ANSWERED_WITHIN_SCOPE"
        ep.trace["steps"]["3_competency_compiler_non_llm_solver_independent_verifier"] = {
            "mission_id": cortex_id, "method": r["method"], "certificate_status": certificate["status"],
            "certificate_checker": {k: v for k, v in certificate.items() if k != "status"} if isinstance(certificate, dict) else None,
            "outcome": r["outcome"]["outcome"], "objective": r["output"]["answer"]["objective"],
            "appraisal": appraisal["verdict"]}

        # ---- 5. a real missing function: Genesis constructs it and attaches only inside the signed scope -------
        compiled_id = ep.submit(compiled_question(problem_id="one-staff", data=STAFFING, allow_construction=True,
                                                  objective="staff the docks and the line"), "compiled")
        appraisal = ep.run_to_closure(compiled_id)
        assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
        compiled = ep.receipt_outputs(lambda o: str(o.get("schema", "")).startswith("greg-competency-compilation/"))
        assert compiled[0]["state"] == "CAPABILITY_DEFICIT" and compiled[0]["capability_deficit"]["function"] == "assignment.staffing"
        assert compiled[-1]["state"] == "ANSWERED" and compiled[-1]["method_or_composition_selected"].startswith("composed.assignment.staffing.")
        assert compiled[-1]["result"]["staffed"] == 8 and compiled[-1]["authority_created"] is False
        opened = [e["function"] for e in events(ep.home, "deficit.opened")]
        attached = [s for s in events(ep.home, "capability.state") if s["state"] == "ATTACHED"
                    and s["capability_id"].startswith(("composed.", "acquired."))]
        assert opened[:2] == ["assignment.staffing", "graph.max_flow"] and attached
        ep.trace["steps"]["5_genesis_constructs_missing_function"] = {
            "mission_id": compiled_id, "deficits_opened": opened, "constructed": compiled[-1]["method_or_composition_selected"],
            "attached_by": sorted({str(a.get("by")) for a in attached}), "appraisal": appraisal["verdict"]}

        # ---- 4. the Hands: a confined worker changes a repository and GREG re-runs the tests ------------------
        work_id = ep.submit(templates.code_change(repo=str(proj), objective="add sub() with a founder-signed script",
                                                  order="one-sub", provider="script", allowed_paths=["pkg/*", "tests/*"],
                                                  budget_usd=0.01, script=SCRIPT, workspace_root=ep.home / "workspace"),
                            "work")
        appraisal = ep.run_to_closure(work_id, timeout=240)
        assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
        order_root = ep.home / "workspace" / work_id.replace(":", "_") / "work-orders" / "one-sub"
        summary = json.loads((order_root / "evidence.json").read_text())["summary"]
        report = json.loads((order_root / "worker-report.json").read_text())
        assert summary["status"] == "COMPLETED" and summary["greg_tests_passed"] and summary["commit"]
        assert report["isolation"]["mechanism"] == "bubblewrap" and report["isolation"]["network_isolated"] is True
        envelope = (order_root / "repo" / "tests" / "envelope.txt").read_text()
        assert "network=denied" in envelope and "leaked=[]" in envelope
        assert not (proj / "pkg" / "sub.py").exists(), "the source checkout is never touched"
        ep.trace["steps"]["4_hands_confined_worker_changes_repo_and_tests_rerun"] = {
            "mission_id": work_id, "provider": report["provider"], "isolation": report["isolation"]["mechanism"],
            "network": report["isolation"]["network"], "greg_tests_passed": summary["greg_tests_passed"], "commit": summary["commit"],
            "appraisal": appraisal["verdict"]}

        # ---- 7b. SIGKILL while a confined worker is in flight: the outcome is UNCERTAIN, never blindly re-run ----
        slow_id = ep.submit(templates.code_change(repo=str(proj), objective="add sub() after a pause", order="slow-sub",
                                                  provider="script", allowed_paths=["pkg/*", "tests/*"], budget_usd=0.01,
                                                  script=SLOW_SCRIPT, workspace_root=ep.home / "workspace"), "slow")
        slow_root = ep.home / "workspace" / slow_id.replace(":", "_") / "work-orders" / "slow-sub"
        wait_for(lambda: (slow_root / "repo" / "tests" / "started.txt").exists(), timeout=90, what="worker in flight")
        killed = heartbeat(ep.home)["pid"]
        os.kill(killed, signal.SIGKILL)
        restarted = wait_for(lambda: heartbeat(ep.home)["pid"] != killed and heartbeat(ep.home)["state"] == "RUNNING"
                             and heartbeat(ep.home), what="restart after the in-flight kill")
        asked = wait_for(lambda: [r for r in ep.request_for(slow_id) if r["kind"] == "RECONCILIATION"],
                         timeout=60, what="reconciliation request")
        time.sleep(1.5)
        commissions = lambda: [a for a in events(ep.home, "mission.action")
                               if a["mission_id"] == slow_id and a["action_id"] == "commission-worker"]
        assert [a["status"] for a in commissions()] == ["UNCERTAIN"], commissions()
        assert "dispatch claimed without receipt" in commissions()[0]["reasons"][0]
        assert commissions()[0]["reserved_usd"] == 0.01 and commissions()[0]["cost_usd"] == 0.0   # unknown spend: cap held, none booked
        assert not (slow_root / "evidence.json").exists() and len(asked) == 1, "no blind re-run, one question"
        ep.decide(asked[0]["request_id"], "reconcile_not_executed")       # the founder states it did not finish
        appraisal = ep.run_to_closure(slow_id, timeout=240, answered={asked[0]["request_id"]})
        assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
        statuses = [a["status"] for a in commissions()]
        assert statuses == ["UNCERTAIN", "RECONCILED_NOT_EXECUTED", "DONE"], statuses
        slow_summary = json.loads((slow_root / "evidence.json").read_text())["summary"]
        assert slow_summary["status"] == "COMPLETED" and slow_summary["greg_tests_passed"]
        ep.trace["steps"]["7b_sigkill_in_flight_worker_reconciled_not_rerun"] = {
            "mission_id": slow_id, "killed_pid": killed, "restarted_pid": restarted["pid"],
            "commission_statuses": statuses, "reconciliation_request": asked[0]["request_id"],
            "founder_answer": "reconcile_not_executed", "completed_runs": statuses.count("DONE"),
            "commit": slow_summary["commit"], "appraisal": appraisal["verdict"]}

        # ---- 7c. The same interruption under the founder's standing mandate: settled with its proof, run once ----
        standing = templates.code_change(repo=str(proj), objective="add sub() after a pause, standing mandate",
                                         order="slow-standing", provider="script", allowed_paths=["pkg/*", "tests/*"],
                                         budget_usd=0.01, script=SLOW_SCRIPT, workspace_root=ep.home / "workspace")
        standing["standing_reconciliation"] = {"consequence_inert": True}      # signed by the founder with the mission
        standing_id = ep.submit(standing, "slow-standing")
        standing_root = ep.home / "workspace" / standing_id.replace(":", "_") / "work-orders" / "slow-standing"
        wait_for(lambda: (standing_root / "repo" / "tests" / "started.txt").exists(), timeout=90,
                 what="the standing-mandate worker in flight")
        killed_again = heartbeat(ep.home)["pid"]
        os.kill(killed_again, signal.SIGKILL)
        wait_for(lambda: heartbeat(ep.home)["pid"] != killed_again and heartbeat(ep.home)["state"] == "RUNNING"
                 and heartbeat(ep.home), what="restart after the second in-flight kill")
        wait_for(lambda: ep.achieved(standing_id), timeout=240, what="closure under the standing mandate")
        assert not ep.request_for(standing_id), "a provably inert interruption asks the founder nothing"
        appraisal = ep.run_to_closure(standing_id, timeout=120)
        assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
        standing_acts = [a for a in events(ep.home, "mission.action")
                         if a["mission_id"] == standing_id and a["action_id"] == "commission-worker"]
        assert [a["status"] for a in standing_acts] == ["UNCERTAIN", "RECONCILED_NOT_EXECUTED", "DONE"], standing_acts
        settled = standing_acts[1]
        assert settled["route"] == "standing_reconciliation" and settled["proof"]["holds"], settled
        assert json.loads((standing_root / "evidence.json").read_text())["summary"]["status"] == "COMPLETED"
        ep.trace["steps"]["7c_sigkill_in_flight_worker_settled_under_standing_mandate"] = {
            "mission_id": standing_id, "killed_pid": killed_again,
            "commission_statuses": [a["status"] for a in standing_acts], "founder_questions": 0,
            "completed_runs": [a["status"] for a in standing_acts].count("DONE"),
            "proof_predicates": settled["proof"]["predicates"],
            "comparison": {"7b_founder_questions": len(asked), "7c_founder_questions": len(ep.request_for(standing_id)),
                           "duplicate_consequences": statuses.count("DONE") - 1
                           + [a["status"] for a in standing_acts].count("DONE") - 1},
            "appraisal": appraisal["verdict"]}

        # ---- 6. two organ processes exchange authenticated messages through a Kernel-led trace -----------------
        organs_id = ep.submit(organ_exchange(daleobanks_root=str(daleobanks_root), wmi_root=str(wmi_root),
                                             signal=str(signal_file)), "organs")
        appraisal = ep.run_to_closure(organs_id, timeout=180)
        assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
        exchange = ep.receipt_outputs(lambda o: o.get("inputs", {}).get("renderer") == "greg.organ_exchange/one-greg-1")[-1]
        assert exchange["legs_verified"] == {"wealthmachine_verified_request": True, "daleobanks_verified_response": True}
        assert exchange["verdict"] == "needs_more_evidence" and exchange["inputs"]["acceptance"]["ledger_chain_ok"]
        assert Path(exchange["path"]).is_file()
        ep.trace["steps"]["6_two_organs_authenticated_exchange_kernel_led"] = {
            "mission_id": organs_id, "organs": ep.trace["organs"], "packet_id": exchange["packet_id"],
            "legs_verified": exchange["legs_verified"], "relay_checks": {k: v["passed"] for k, v in exchange["inputs"]["relay_checks"].items()},
            "engine_verdict": exchange["engine_verdict"], "binding_verdict": exchange["verdict"], "appraisal": appraisal["verdict"]}

        # ---- 10. a verified correction changes a later decision ------------------------------------------------
        from greg import briefs
        brief_outputs = ep.receipt_outputs(lambda o: isinstance(o.get("inputs"), dict) and "local" in o["inputs"])
        assert brief_outputs and NOISE_KEY in briefs.flagged_keys(brief_outputs[0]["inputs"]), "the baseline brief flags the dirty checkout"
        critique = lambda mission: greg(ep.home, "critique", ep.event_id_of_done(mission), "--verdict", "note",
                                        "--evidence-type", "founder_judgment", "--text", "morning review of the brief",
                                        "--noise", NOISE_KEY, "--key", str(ep.key), "--no-passphrase")
        critique(brief_mission)
        proposed = wait_for(lambda: events(ep.home, "improvement.proposed"), what="shadow candidate from the label")
        assert proposed[0]["state"] == "SHADOW" and proposed[0]["authority_changed"] is False
        held_out = []
        for k in range(3):                                                      # three later briefs it was not derived from
            _age_briefs(ep.deliveries)
            mid = ep.submit(engineering_brief(local={"kernel": str(kernel)}, github=[], today=f"one-machine-{k}",
                                              preauthorize_delivery=True), f"brief-{k}")
            ep.run_to_closure(mid)
            latest = ep.receipt_outputs(lambda o: isinstance(o.get("inputs"), dict) and "local" in o["inputs"])[-1]
            assert "attention_policy" not in latest["inputs"], "production keeps the unchanged policy while in shadow"
            assert not events(ep.home, "improvement.retained")
            held_out.append(mid)
            critique(mid)
        retained = wait_for(lambda: events(ep.home, "improvement.retained"), what="the candidate wins on held-out briefs")
        assert len(retained[0]["held_out"]) == 3 and not set(retained[0]["held_out"]) & set(proposed[0]["derived_from"])
        _age_briefs(ep.deliveries)
        learned_id = ep.submit(engineering_brief(local={"kernel": str(kernel)}, github=[], today="one-machine-learned",
                                                 preauthorize_delivery=True), "brief-learned")
        appraisal = ep.run_to_closure(learned_id)
        learned = ep.receipt_outputs(lambda o: isinstance(o.get("inputs"), dict) and "local" in o["inputs"])[-1]
        assert "attention_policy" in learned["inputs"] and NOISE_KEY not in briefs.flagged_keys(learned["inputs"])
        assert appraisal["verdict"] == "VERIFIED"
        ep.trace["steps"]["10_verified_correction_changes_later_decision"] = {
            "lever": proposed[0].get("lever"), "candidate_policy": proposed[0]["policy"], "held_out_briefs": held_out,
            "retained_errors": retained[0]["errors"], "learned_policy_in_next_brief": learned["inputs"]["attention_policy"],
            "noise_key_flagged_before": True, "noise_key_flagged_after": False}

        # ---- 9. Mission Control renders the body's own truth at three widths ---------------------------------
        chromium = _chromium()
        if chromium is None:
            ep.trace["steps"]["9_mission_control_three_widths"] = {"status": "NOT_RUN", "why": "no Playwright/Chromium on this host"}
        else:
            from playwright.sync_api import sync_playwright
            proc = subprocess.Popen([sys.executable, "-m", "greg", "--home", str(ep.home), "console", "--key", str(ep.key),
                                     "--no-passphrase", "--no-model", "--port", str(port)], cwd=ROOT,
                                    env={**os.environ, "PYTHONPATH": str(ROOT)}, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True)
            link, deadline = "", time.time() + 30
            while time.time() < deadline and not link:
                line = proc.stdout.readline()
                assert line or proc.poll() is None, "console exited before printing its private link"
                if "?access=" in line:
                    link = line.strip()
            assert link
            rendered = {}
            mission_ids = [brief_mission, cortex_id, compiled_id, work_id, organs_id, learned_id]
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=chromium, args=["--no-sandbox"])
                context = browser.new_context(viewport=VIEWPORTS["desktop"])
                page = context.new_page()
                page.goto(link)                                                   # the single-use private link, once
                owner = page.url.split("?")[0].rstrip("/")
                for device, size in VIEWPORTS.items():
                    page.set_viewport_size(size)
                    page.goto(owner + "/")
                    text = page.inner_text("main")
                    fits = page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
                    page.goto(owner + "/mc/proof")
                    proof = page.inner_text("main")
                    page.goto(owner + "/mc/goals")
                    goals = page.inner_text("main")
                    everywhere = text + proof + goals
                    rendered[device] = {"five_questions": all(q in text for q in QUESTIONS), "fits_viewport": fits,
                                        "verified_closures_shown": "VERIFIED" in proof,
                                        "missions_shown": sorted(m for m in mission_ids if m in everywhere),
                                        "vepmc_zero": bool(re.search(r"VEPMC\D{0,40}0", proof))}
                    if EVIDENCE:
                        Path(EVIDENCE).mkdir(parents=True, exist_ok=True)
                        page.goto(owner + "/")
                        page.screenshot(path=str(Path(EVIDENCE) / f"mission-control-{device}.png"))
                browser.close()
            proc.terminate()
            proc.wait(10)
            for device, r in rendered.items():
                assert r["five_questions"] and r["fits_viewport"] and r["verified_closures_shown"], (device, r)
                assert r["vepmc_zero"], (device, proof[:500])
            ep.trace["steps"]["9_mission_control_three_widths"] = {"status": "RENDERED", "viewports": VIEWPORTS, "rendered": rendered}

        # ---- signed stop ends the body; the trace is read from the ledger by separate processes ------------------
        greg(ep.home, "stop", "--key", str(ep.key), "--no-passphrase")
        wait_for(lambda: heartbeat(ep.home)["state"] == "STOPPED", what="signed stop")
        time.sleep(2.0)
        status = subprocess.run(["supervisorctl", "-c", str(conf), "status"], capture_output=True, text=True)
        assert "EXITED" in status.stdout, status.stdout
    finally:
        if ui is not None:
            ui.terminate()
            ui.wait(10)
        supervisor.send_signal(signal.SIGTERM)
        try:
            supervisor.wait(timeout=30)
        except subprocess.TimeoutExpired:
            supervisor.kill()

    ledger, journal = history(ep.home)
    try:
        ok, why = ledger.verify_chain()
        assert ok, why
        receipts = ledger.by_type("receipt")
        assert len(receipts) == len({r.hash for r in receipts})
        boots = journal.replay("body.booted")
        ep.trace["body"].update(boots=len(boots), receipts=len(receipts), chain_verified=ok)
    finally:
        ledger.close()
    # ---- adversarial: the separate-process appraiser refuses a tampered deliverable, and verifies it restored ----
    memo = Path(exchange["path"])
    original = memo.read_bytes()
    memo.write_bytes(original.replace(b"needs_more_evidence", b"go", 1) if b"needs_more_evidence" in original
                     else original + b"\nverdict: go\n")
    tampered = _appraise(ep, organs_id)
    memo.write_bytes(original)
    restored = _appraise(ep, organs_id)
    assert tampered["verdict"] == "REFUTED" and tampered["checks"]["deliveries_bound_to_evidence"] is False, tampered
    assert restored["verdict"] == "VERIFIED", restored["findings"]
    ep.trace["adversarial"]["tampered_deliverable_refuted"] = {"tampered": tampered["verdict"],
                                                               "findings": tampered["findings"][:3],
                                                               "restored": restored["verdict"]}
    vepmc = json.loads(greg(ep.home, "vepmc").stdout)
    acceptance = json.loads(greg(ep.home, "acceptance").stdout)
    assert vepmc["VEPMC"] == 0 and acceptance["vepmc"] == 0 and acceptance["authority_created"] is False
    assert acceptance["reality"].startswith("LOCAL"), acceptance["reality"]
    traces = {}
    for mid in ep.trace["missions"]:
        out = subprocess.run([sys.executable, str(ROOT / "scripts" / "mission_trace.py"), str(ep.home), mid],
                             cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)}, capture_output=True, text=True, timeout=120)
        assert out.returncode == 0, out.stderr[-500:]
        traces[mid] = json.loads(out.stdout)
        assert traces[mid]["proof"]["achieved"] and traces[mid]["persistence"]["ledger_chain_verified"]
    ep.trace["summary"] = {"missions_closed": len(ep.trace["missions"]), "vepmc": vepmc["VEPMC"],
                           "external_confirmation_required": vepmc.get("external_confirmation_required"),
                           "acceptance_reality": acceptance["reality"], "seconds": round(time.monotonic() - ep.started, 1),
                           "founder_key": "per-test Ed25519 key; NOT Alfonso", "counts_toward_vepmc": False}
    if EVIDENCE:
        out_dir = Path(EVIDENCE)
        out_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(ep.home / "ledger.jsonl", out_dir / "ledger.jsonl")
        (out_dir / "one-machine-trace.json").write_text(json.dumps(ep.trace, indent=1, default=str))
        (out_dir / "mission-traces.json").write_text(json.dumps(traces, indent=1, default=str))
        (out_dir / "vepmc.json").write_text(json.dumps(vepmc, indent=1))
        (out_dir / "acceptance.json").write_text(json.dumps(acceptance, indent=1))
