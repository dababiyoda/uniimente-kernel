"""The composed machine's acceptance mission: seven behaviours on one mission, one body, one ledger, real processes.

Founder, 2026-11-12: "Prove that the composed machine can: Execute an authorized mission through its actual entry
point. Preserve correct outcomes through interruption and restart. Respect capability identity and device
revocation. Preserve completed work when a dependency fails. Distinguish uncertainty, timeout, refusal, failure, and
refutation. Bind an appraisal to the specific closure and evidence it actually evaluates. Explain its outcome,
costs, remaining uncertainty, and next step." And: "interrupt a mission, invalidate one supporting observation,
remove its preferred tool, and preserve an already completed effect." "Green results on separate branches do not
establish compatibility."

This file is an acceptance test of the tree it runs on. It changes no product code. The body is `python -m greg
--home <tmp> run`, its own OS process; every founder and device act is a separate `greg` CLI process; the founder
reads with CLI processes and with Mission Control's JSON over HTTP. The test reads the ledger and files, sends
signals, and changes one file the mission's sensor reads.

One founder-signed mission (per-test Ed25519 keys, never a real one):

  effect A   `a`        fs.write of note.txt, $0.10, outside the cone: a delegated device key approves it
  effect B   `b`        artifact.store of that note, $0.25, outside the cone: the tool that is later detached
  repair     `refresh`  a free, pre-approved write that asks for the gauge to be refreshed (advances check c)
  check  C   `c`        the gauge file reads "green", through fs.search with a one-second time limit

The story, in order (the test waits on the ledger or a file, never on a fixed delay):

  1. signed and submitted through the CLI; the body process picks it up from its inbox
  2. the phone approves A, A runs; the phone approves B, the founder revokes the phone before B is dispatched; the
     mission asks again; the revoked phone's next answer is refused; the founder approves
  3. the gauge is made unreadable; the body is SIGKILLed while B's dispatch is in flight; a new process classifies
     it UNCERTAIN and asks the founder to reconcile
  4. the founder detaches artifact.store and reconciles "not executed"; the mission names the attach it needs; the
     body is stopped, the office is asked directly for B (under its own identity, and under another), and refuses
  5. the gauge is made to exceed the sensor's time limit; the founder attaches the tool again, B runs; with A and B
     done and C unmeasured the mission closes nothing and asks about the sensor; the gauge is made to read "red": a
     measured failure, and a failure closure
  6. the body is SIGKILLed after that closure's appraiser ran and before its verdict was recorded; while it is down
     the gauge turns "green"; a new process closes the mission and appraises both closures
  7. the separate appraiser is run on the achievement with A's deliverable tampered with (REFUTED), and restored
     (VERIFIED)

Test instrumentation in the body process (a ``sitecustomize`` on its PYTHONPATH, as in
tests/integration/test_greg_retained_receipt_process.py; no product file is touched): the artifact.store adapter
appends one line per call to a file and, while a flag file exists, does not return (so the kill lands inside the
dispatch); and the first attempt to record a failure closure's appraisal, while another flag file exists, kills the
process. Nothing else in the body differs from `greg run`.

Behaviours this tree does not have are each one small ``xfail(strict=True)`` test below, with the defect and where
it lives. They pass today as expected failures and fail the day the defect is fixed.

What this file does not show, so that nothing above is read further than it holds:

- the mission engine never hands the office a detached capability (it resolves the strategy first and asks for the
  attach), so the office's refusal in step 4 is the office answering a direct caller on the same body and ledger,
  between two body processes; the mission's own record of the detach is its typed blocker and its attach ask;
- the gauge stops reading green before any closure (a bounded mission that has achieved takes no further reading);
  after the failure closure it changes once more, to green, and the mission closes on a fresh reading;
- the tampered-deliverable verdict and its VERIFIED counterpart are the separate appraiser's answers when run as
  its own process over the ledger at rest; the body appraises a closure once, so they are not ledger records;
- a Competency Compiler receipt whose solver the host stalled is not exercised (it needs solver packages); the
  timeout here is a sensor's own time limit;
- the mission is named ``m:first-mission-...`` only because the acceptance report reads missions of that name; it
  is not a run of the First Mission template.

Needs no bubblewrap, supervisord, browser or solver package. Reality: LABORATORY (a container, test keys); nothing
here counts toward VEPMC, authenticates a person, spends money or contacts anyone. Set
GREG_COMPOSED_ACCEPTANCE_EVIDENCE=<dir> to keep what each point of the story held, the ledger and the body's log.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from greg.body import Body, observe
from greg.capabilities import InvocationContext
from greg.missions import MissionBook, measured
from tests.greg_fixtures import horizon, workspace
from tests.integration.test_greg_body_supervised import ROOT, greg, heartbeat, history, wait_for
from tests.integration.test_greg_product_path import enter_console, free_port, http

MID = "m:first-mission-composed-acceptance"   # the acceptance report reads missions named m:first-mission-*
NOTE = "alpha: the first effect of the acceptance mission\n"
ADDRESS = "sha256:" + hashlib.sha256(NOTE.encode()).hexdigest()
REFRESH = "please refresh the gauge\n"
SENSOR_SECONDS = 1
COST_A, COST_B = 0.10, 0.25
LINE = b"gauge reading pending " * 46 + b"\n"          # about 1 KiB of text that never says "green"
EVIDENCE = os.environ.get("GREG_COMPOSED_ACCEPTANCE_EVIDENCE")   # a directory to keep the story and the ledger in

INSTRUMENTATION = '''
"""Test instrumentation for tests/integration/test_composed_machine_acceptance.py. Loaded only by the body process
that test starts (GREG_ACCEPT_CTRL names its control directory). It replaces no product file."""
import os, signal, time
CTRL = os.environ.get("GREG_ACCEPT_CTRL")
if CTRL:
    from greg import capabilities
    import greg.journal as journal

    def _mark(name, text):
        with open(os.path.join(CTRL, name), "a") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())

    manifest, real_store = capabilities.BUILTINS["artifact.store"]

    def store(params, ctx):
        _mark("calls", f"{os.getpid()} {ctx.mission_id} {ctx.grant_id}\\n")
        if os.path.exists(os.path.join(CTRL, "hang")):
            time.sleep(3600)                   # killed here: the Gate claimed the dispatch; no effect, no receipt
        return real_store(params, ctx)
    capabilities.BUILTINS["artifact.store"] = (manifest, store)

    real_record = journal.Journal.record

    def record(self, kind, data, **kw):
        if (kind == "mission.appraised" and data.get("closure_event")
                and os.path.exists(os.path.join(CTRL, "kill-before-appraisal-record"))
                and not os.path.exists(os.path.join(CTRL, "killed"))):
            _mark("killed", kind + " " + str(data.get("verdict")))
            os.kill(os.getpid(), signal.SIGKILL)   # no shutdown, no flush, no handler
        return real_record(self, kind, data, **kw)
    journal.Journal.record = record
'''


class ScenarioBroken(Exception):
    """The story could not be driven to its end; what the assertions below would read does not exist."""


def mission_spec(home: Path, gauge: Path) -> dict:
    note = workspace(home, MID) / "note.txt"
    return {
        "mission_id": MID, "priority": 60,
        "founder_expression": "Write the note, retain it by digest, and close only while the gauge reads green.",
        "intended_effect": "note.txt holds the note, the artifact store retains it, and the gauge reads green",
        "closure": {"kind": "bounded", "cadence_seconds": 60},
        "success_checks": [
            {"check_id": "a", "description": "the note is written",
             "sensor": {"capability": "fs.read", "params": {"path": str(note)}, "target": "fs:note.txt"},
             "predicate": {"op": "contains", "field": "text", "value": "alpha"}},
            {"check_id": "b", "description": "the note is retained by digest",
             "sensor": {"capability": "artifact.inspect", "params": {"namespace": "acceptance", "address": ADDRESS},
                        "target": "artifact:acceptance"},
             "predicate": {"op": "equals", "field": "present", "value": True}},
            {"check_id": "c", "description": "the gauge reads green",
             "sensor": {"capability": "fs.search", "target": "fs:gauge.txt",
                        "params": {"path": str(gauge), "phrases": ["green"], "max_seconds": SENSOR_SECONDS}},
             "predicate": {"op": "equals", "field": "queries.0.found", "value": True}}],
        "strategies": [
            {"action_id": "a", "capability": "fs.write", "params": {"relative_path": "note.txt", "content": NOTE},
             "target": "workspace:note.txt", "advances": ["a"], "rationale": "write the note", "cost_usd": COST_A},
            {"action_id": "b", "capability": "artifact.store", "params": {"namespace": "acceptance", "path": str(note)},
             "target": "artifact:acceptance", "advances": ["b"], "requires": ["a"],
             "rationale": "retain the note by digest", "cost_usd": COST_B},
            {"action_id": "refresh", "capability": "fs.write",
             "params": {"relative_path": "gauge-request.txt", "content": REFRESH},
             "target": "workspace:gauge-request.txt", "advances": ["c"], "rationale": "ask for a gauge refresh"}],
        "pre_approved_steps": [{"action_id": "refresh", "capability": "fs.write",
                                "target": "workspace:gauge-request.txt", "consequence_class": "internal_write",
                                "cost_usd": 0}],
        "light_cone": {"capabilities": ["fs.read", "fs.search", "artifact.inspect"],
                       "targets": ["fs:*", "artifact:acceptance", "workspace:*"],
                       "max_consequence_class": "internal_write", "budget_usd": 1.0, "horizon": horizon()}}


def slow_gauge_megabytes() -> int:
    """How much text the sensor cannot search within its time limit on this machine now: four times what the
    product's own search read in the limit, measured here (at least 64 MiB)."""
    from greg.textquery import Query
    block, query, fed = LINE * 1024, Query(["green"]), 0
    start = time.perf_counter()
    while time.perf_counter() - start < 0.5:
        query.feed(block)
        fed += len(block)
    rate = fed / (time.perf_counter() - start)
    size = max(64, int(4 * rate * SENSOR_SECONDS / 2 ** 20) + 1)
    if size > 2048:
        pytest.fail(f"this machine searches {rate / 2 ** 20:.0f} MiB/s: a gauge file the sensor cannot finish in "
                    f"{SENSOR_SECONDS} s would need {size} MiB")
    return size


class Story:
    """The driver. It keeps what it saw at each point (``at``); the tests below assert on that."""

    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.home, self.data = tmp / "body", tmp / "data"
        self.key, self.phone = tmp / "founder.pem", tmp / "phone.pem"
        self.ctrl, self.inject, self.log = tmp / "ctrl", tmp / "inject", tmp / "body.log"
        self.gauge = self.data / "gauge.txt"
        self.note = self.home / "workspace" / MID.replace(":", "_") / "note.txt"
        self.body: subprocess.Popen | None = None
        self.pids: list[int] = []
        self.at: dict[str, dict] = {}        # label -> what the ledger, the files and the CLI readers said then
        self.started = time.monotonic()

    # -- processes ---------------------------------------------------------------------------------------------
    def cli(self, *args) -> str:
        return greg(self.home, *args).stdout

    def founder(self, *args) -> str:
        return self.cli(*args, "--key", str(self.key), "--no-passphrase")

    def device(self, *args) -> str:
        return self.cli(*args, "--key", str(self.phone), "--no-passphrase")

    def read(self, *args):
        return json.loads(self.cli(*args))

    def start(self) -> None:
        env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(self.inject), str(ROOT)]),
               "GREG_FOUNDER_PASSPHRASE": "", "GREG_ACCEPT_CTRL": str(self.ctrl)}
        self.body = subprocess.Popen([sys.executable, "-m", "greg", "--home", str(self.home), "run",
                                      "--tick-seconds", "0.1"], cwd=ROOT, env=env, stdout=self.log.open("a"),
                                     stderr=subprocess.STDOUT)
        self.pids.append(self.body.pid)
        self.wait(lambda: [b for b in self.events("body.booted") if b["pid"] == self.body.pid], "the body's boot")

    def stop(self) -> int:
        self.body.send_signal(signal.SIGTERM)
        return self.body.wait(timeout=60)

    def reap(self) -> None:
        if self.body is not None and self.body.poll() is None:
            self.body.terminate()
            try:
                self.body.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.body.kill()
                self.body.wait(timeout=20)

    # -- reading -----------------------------------------------------------------------------------------------
    def events(self, prefix: str, mission: bool = False) -> list[dict]:
        ledger, journal = history(self.home)
        try:
            return [e.payload for e in journal.replay(prefix) if not mission or e.payload.get("mission_id") == MID]
        finally:
            ledger.close()

    def wait(self, predicate, what: str, timeout: float = 90):
        try:
            return wait_for(predicate, timeout=timeout, what=what)
        except AssertionError as exc:
            alive = self.body is not None and self.body.poll() is None
            raise ScenarioBroken(f"{exc} (body {'running' if alive else 'not running'}); body log tail:\n"
                                 + self.log.read_text()[-3000:]) from None

    def turns(self, n: int = 3) -> None:
        """Wait until the running body has finished ``n`` more turns (its heartbeat is written once a turn)."""
        seen = {heartbeat(self.home)["at"]}

        def more():
            seen.add(heartbeat(self.home)["at"])
            return len(seen) > n
        self.wait(more, f"{n} more turns of the body")

    def asks(self, kind: str, action: str | None = None) -> list[dict]:
        return [r for r in self.events("decision.requested", mission=True)
                if r["kind"] == kind and (action is None or r.get("action_id") == action)]

    def actions(self, action: str) -> list[dict]:
        return [a for a in self.events("mission.action", mission=True) if a["action_id"] == action]

    def facts(self) -> dict:
        """This mission's retained facts, read from the ledger file (read-only; safe while the body runs)."""
        ledger, journal = history(self.home)
        try:
            seq = {r.payload.get("event_id"): r.seq for r in ledger.by_type("event")}

            def rows(prefix, mission=True):
                return [{**e.payload, "_id": e.event_id, "_seq": seq.get(e.event_id), "_type": e.type}
                        for e in journal.replay(prefix) if not mission or e.payload.get("mission_id") == MID]

            def position(record_hash):
                record = ledger.find(record_hash)
                return None if record is None else record.seq
            intents = rows("mission.dispatching")
            proposals = {i["proposal_id"]: i["action_id"] for i in intents}
            claims = [{**r.payload, "_seq": r.seq, "action_id": proposals[r.payload["proposal_id"]]}
                      for r in ledger.by_type("grant_dispatch") if r.payload.get("proposal_id") in proposals]
            receipts = {r.hash: {**r.payload, "_seq": r.seq} for r in ledger.by_type("receipt")}
            authority = [{**r.payload, "_seq": r.seq} for r in ledger.by_type("event")
                         if str(r.payload.get("type", "")).startswith("greg.authority.")
                         and (r.payload.get("mission_id") == MID or r.payload.get("proposal_id") in proposals)]
            book = MissionBook(journal)
            m = book.missions.get(MID)
            state = None if m is None else {
                "status": m.status, "spent_usd": m.spent_usd, "reserved_usd": m.reserved_usd,
                "approved_scopes": sorted(m.approved_scopes), "blocker": m.blocker, "failed": dict(m.failed),
                "actions_done": m.actions_done, "attempts": dict(m.attempts)}
            return {
                "registered": rows("mission.registered"), "actions": rows("mission.action"),
                "observed": rows("mission.observed"), "intents": intents, "claims": claims, "receipts": receipts,
                "authority": authority, "requested": rows("decision.requested"),
                "answered": rows("decision.answered", mission=False),
                "withdrawn": rows("decision.withdrawn", mission=False), "blocked": rows("mission.blocked"),
                "unmet": rows("mission.unmet"), "achieved": rows("mission.achieved"),
                "appraised": [{**a, "_head_seq": position(a["head"])} for a in rows("mission.appraised")],
                "routing": rows("routing.outcome"),
                "schedule": rows("mission.schedule"),
                "accepted": rows("command.accepted", mission=False),
                "rejected": rows("command.rejected", mission=False),
                "booted": rows("body.booted", mission=False), "recovered": rows("body.recovered", mission=False),
                "stopped": rows("body.stopped", mission=False), "paused": rows("body.paused", mission=False),
                "resumed": rows("body.resumed", mission=False),
                "devices": rows("device.", mission=False), "capability_state": rows("capability.state", mission=False),
                "model_spend": rows("genesis.buil", mission=False) + rows("cognition.receipt", mission=False),
                "chain": ledger.verify_chain()[0], "head": ledger.head, "state": state,
                "calls": (self.ctrl / "calls").read_text().splitlines() if (self.ctrl / "calls").exists() else [],
                "note": self.note.read_text() if self.note.exists() else None,
                "note_file": (self.note.stat().st_ino, self.note.stat().st_mtime_ns) if self.note.exists() else None}
        finally:
            ledger.close()

    def keep(self, label: str, **readers) -> dict:
        self.at[label] = {**self.facts(), **readers, "elapsed": round(time.monotonic() - self.started, 1)}
        return self.at[label]

    # -- the world the sensor of check C reads -----------------------------------------------------------------
    def set_gauge(self, reading: str) -> None:
        """green | red | unreadable (a directory where the file was) | slow (more text than the sensor's time limit
        lets it search). Only called while the mission cannot be observing: it waits on a decision, or is down."""
        if self.gauge.is_dir():
            self.gauge.rmdir()
        if reading == "unreadable":
            self.gauge.unlink(missing_ok=True)
            self.gauge.mkdir()
            return
        fresh = self.gauge.with_name("gauge.next")
        with fresh.open("wb") as out:
            if reading == "slow":
                block = LINE * 1024
                for _ in range(self.slow_megabytes):
                    out.write(block)
            else:
                out.write(f"gauge: {reading}\n".encode())
        os.replace(fresh, self.gauge)

    # -- the separate appraiser, run as its own process (as greg.body.Body.appraise runs it) ---------------------
    def appraise(self, closure_event: str | None = None) -> dict:
        config = json.loads((self.home / "body.json").read_text())
        ledger, _ = history(self.home)
        try:
            head = ledger.head
        finally:
            ledger.close()
        request = {"ledger": str(self.home / "ledger.jsonl"), "constitution": config["constitution_hash"],
                   "head": head, "mission_id": MID, "read_roots": config["read_roots"],
                   "deliver_root": config["deliver_root"], "artifact_root": str(self.home / "artifacts"),
                   "workspace": str(self.home / "workspace" / MID.replace(":", "_")),
                   "worker_confinement": config.get("worker_confinement") or "required",
                   "confined_egress": bool(config.get("confined_egress"))}
        if closure_event:
            request["closure_event"] = closure_event
        out = subprocess.run([sys.executable, "-m", "greg.appraisal"], input=json.dumps(request), capture_output=True,
                             text=True, timeout=120, cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)})
        if out.returncode:
            raise ScenarioBroken("the separate appraiser exited " + str(out.returncode) + ": " + out.stderr[-800:])
        return json.loads(out.stdout)

    # -- the office, asked directly while no body process runs -------------------------------------------------
    def ask_the_office(self) -> dict:
        """What the authority office answers a caller that reaches it without the mission engine, for effect B: with
        B's own registered adapter and manifest, at the exact scope the founder approved and the attempt the engine
        would use next; and with B's adapter presented under an attached capability's manifest."""
        from greg.artifacts import ArtifactStore
        from greg.capabilities import CapabilityError
        b = next(s for s in self.spec["strategies"] if s["action_id"] == "b")
        with Body(self.home) as body:
            m = MissionBook(body.journal).missions[MID]
            store, inspect = body.registry.manifests["artifact.store"], body.registry.manifests["artifact.inspect"]
            adapter = body.registry.adapters["artifact.store"]

            def act(manifest, ctx_manifest, attempt):
                ctx = InvocationContext(workspace=workspace(self.home, MID), read_roots=(self.data,),
                                        secrets=body.secrets, manifest=ctx_manifest, journal=body.journal,
                                        artifact_root=body.layout.artifacts)
                out = body.office.act(mission_id=MID, cone=m.cone, command_digest=m.command_digest, manifest=manifest,
                                      adapter=adapter, ctx=ctx, params=b["params"], target=b["target"],
                                      cost_usd=b["cost_usd"], expected_outcome="strategy executed", evidence_refs=[],
                                      attempt=attempt, spent_usd=m.committed_usd, approved_scopes=m.approved_scopes)
                return {"status": out.status, "reasons": list(out.reasons), "receipt": out.receipt_hash,
                        "grant_id": out.grant_id, "proposal_id": out.proposal_id, "scope_digest": out.scope_digest}
            own = act(store, store, m.attempts["b"])
            other = act(inspect, store, "acceptance-probe-other-identity")
            try:
                ArtifactStore(body.layout.artifacts).read(ADDRESS)
                retained = True
            except CapabilityError:
                retained = False
            return {"own_identity": own, "other_identity": other, "retained": retained,
                    "registry_state": body.registry.state["artifact.store"],
                    "approved_scopes": sorted(m.approved_scopes)}

    # -- Mission Control's data, read over HTTP from a read-only console process -------------------------------
    def mission_control(self) -> dict:
        port = free_port()
        proc = subprocess.Popen([sys.executable, "-m", "greg", "--home", str(self.home), "console", "--no-model",
                                 "--port", str(port)], cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)},
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            enter_console(proc, port)
            return json.loads(http(port, "/api/mc")[1])
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=20)

    def account(self) -> dict:
        """The founder-facing readers, each its own CLI process."""
        return {"status": self.read("status"), "decisions": self.read("decisions"),
                "blockers": self.read("blockers", "--mission", MID),
                "trace": self.read("foundry", "trace", "--mission", MID)}

    # -- the story ---------------------------------------------------------------------------------------------
    def run(self) -> None:
        self.data.mkdir()
        self.ctrl.mkdir()
        self.inject.mkdir()
        (self.inject / "sitecustomize.py").write_text(INSTRUMENTATION)
        self.slow_megabytes = slow_gauge_megabytes()
        self.at["setup"] = {"slow_gauge_megabytes": self.slow_megabytes, "elapsed": 0.0}
        self.set_gauge("green")

        # 1. the entry point: init, keys, enrollment, delegation and the signed mission, each a CLI process
        self.cli("init", "--read-root", str(self.data))
        self.cli("founder", "enroll", "--pubkey",
                 self.cli("founder", "keygen", "--key", str(self.key), "--no-passphrase").strip())
        phone_public = self.cli("founder", "keygen", "--key", str(self.phone), "--no-passphrase").strip()
        self.founder("device", "enroll", "--pubkey", phone_public, "--label", "phone", "--kinds", "DECISION")
        self.spec = mission_spec(self.home, self.gauge)
        spec_file = self.tmp / "mission.json"
        spec_file.write_text(json.dumps(self.spec))
        self.founder("mission", "submit", str(spec_file))
        self.start()
        ask_a = self.wait(lambda: self.asks("APPROVAL", "a"), "the approval ask for A")[0]
        self.keep("asked_a", status=self.read("status"), decisions=self.read("decisions"))

        # 2. the phone approves A; the phone approves B; the founder revokes the phone before B is dispatched
        self.device("decide", ask_a["request_id"], "approve", "--reason", "approve A from the phone")
        self.wait(lambda: [a for a in self.actions("a") if a["status"] == "DONE"], "A done")
        ask_b = self.wait(lambda: self.asks("APPROVAL", "b"), "the approval ask for B")[0]
        self.keep("a_done")
        [device] = self.read("status")["security"]["devices"]
        self.founder("pause")
        self.wait(lambda: self.events("body.paused"), "the pause")
        self.device("decide", ask_b["request_id"], "approve", "--reason", "approve B from the phone")
        self.wait(lambda: [d for d in self.events("decision.answered") if d["request_id"] == ask_b["request_id"]],
                  "the phone's approval of B on the ledger")
        self.founder("device", "revoke", device["device_key_id"])
        self.wait(lambda: self.events("device.revoked"), "the revocation")
        self.keep("revoked_while_paused")
        self.founder("resume")
        ask_b2 = self.wait(lambda: [r for r in self.asks("APPROVAL", "b") if r["request_id"] != ask_b["request_id"]],
                           "the second approval ask for B")[0]
        self.device("decide", ask_b2["request_id"], "approve", "--reason", "the revoked phone tries again")
        self.wait(lambda: [r for r in self.events("command.rejected") if "revoked" in r["reason"]],
                  "the refusal of the revoked phone's answer")
        self.turns()
        self.keep("asked_again", status=self.read("status"), reviews=self.read("device", "reviews"))

        # 3. the gauge becomes unreadable; the founder approves B; the body is killed inside B's dispatch
        self.set_gauge("unreadable")
        (self.ctrl / "hang").touch()
        self.founder("decide", ask_b2["request_id"], "approve", "--reason", "approve B with the founder key")

        def in_flight():
            f = self.facts()
            claimed = [c for c in f["claims"] if c["action_id"] == "b"]
            return f if f["calls"] and claimed else None
        self.wait(in_flight, "B's dispatch in flight (the adapter called, the Gate's claim on the ledger)")
        self.keep("in_flight")
        self.body.send_signal(signal.SIGKILL)
        self.at["in_flight"]["killed_returncode"] = self.body.wait(timeout=30)
        self.keep("after_kill")
        (self.ctrl / "hang").unlink()
        self.start()
        ask_r = self.wait(lambda: self.asks("RECONCILIATION", "b"), "the reconciliation ask")[0]
        self.turns(5)
        self.keep("uncertain", **self.account())

        # 4. the founder detaches B's tool, then says the interrupted dispatch did not execute
        self.founder("detach", "artifact.store")
        self.wait(lambda: [s for s in self.events("capability.state")
                           if s["capability_id"] == "artifact.store" and s["state"] == "DETACHED"], "the detach")
        self.set_gauge("slow")
        self.founder("decide", ask_r["request_id"], "reconcile_not_executed", "--reason",
                     "the artifact store holds nothing at that address")
        self.wait(lambda: self.asks("CAPABILITY_ATTACH"), "the attach ask")
        self.turns()
        self.keep("detached", **self.account())
        self.at["detached"]["stopped_returncode"] = self.stop()
        self.at["detached"]["office"] = self.ask_the_office()
        self.keep("office_asked")

        # 5. the founder attaches the tool again; B runs; C cannot be measured, then reads red
        self.start()
        self.founder("attach", "artifact.store")
        self.wait(lambda: [a for a in self.actions("b") if a["status"] == "DONE"], "B done")
        ask_s = self.wait(lambda: self.asks("SENSOR_FAILURE"), "the ask about the sensor")[0]

        def scheduled():
            f = self.facts()
            asked = next(r["_seq"] for r in f["requested"] if r["request_id"] == ask_s["request_id"])
            return f if [s for s in f["schedule"] if s["_seq"] > asked] else None
        self.wait(scheduled, "the mission's next look at the unread gauge to be scheduled")
        self.keep("unmeasured", **self.account())
        (self.ctrl / "kill-before-appraisal-record").touch()
        self.set_gauge("red")

        # 6. killed between the failure closure's appraiser run and its record; the gauge turns green meanwhile
        try:
            code = self.body.wait(timeout=240)
        except subprocess.TimeoutExpired:
            raise ScenarioBroken("the body did not reach the failure closure's appraisal; body log tail:\n"
                                 + self.log.read_text()[-3000:]) from None
        self.keep("failure_closure", killed_returncode=code,
                  killed_mark=(self.ctrl / "killed").read_text() if (self.ctrl / "killed").exists() else None,
                  status=self.read("status"), decisions=self.read("decisions"))
        self.set_gauge("green")
        self.start()
        self.wait(lambda: len(self.events("mission.appraised", mission=True)) >= 2, "both closures' appraisals")
        self.turns()
        account = self.account()
        self.keep("closed", **account, stopped_returncode=self.stop())

        # the readers, each a process, on the ledger at rest
        end = self.keep("end", **account, vepmc=self.read("vepmc"), routing=self.read("routing"),
                        sop_trend=self.read("sop", "trend"), acceptance=self.read("acceptance"),
                        reviews=self.read("device", "reviews"), mission_control=self.mission_control())
        with observe(self.home, actor="spiffe://uniimente.internal/greg/composed-acceptance-test") as journal:
            from greg import sop
            from greg.cognition import settlement
            settling = settlement._settling_appraisals(journal)
            by_observation = settlement._observation_appraisal(journal, settling)
            last_c = [e for e in journal.replay("mission.observed")
                      if e.payload["mission_id"] == MID and e.payload["check_id"] == "c"][-1]
            end["functions"] = {
                "sop.verified_appraisals": sop.verified_appraisals(journal).get(MID),
                "settlement._settling_appraisals": (settling.get(MID).event_id if settling.get(MID) else None),
                "settlement._observation_appraisal(last reading of c)":
                    getattr(by_observation(last_c), "event_id", None)}

        # 7. the separate appraiser on the achievement: A's deliverable tampered with, then restored
        end["note_file_before_tamper"] = (self.note.stat().st_ino, self.note.stat().st_mtime_ns)
        [unmet] = end["unmet"]
        end["reappraised"] = {"achievement": self.appraise(), "failure_closure": self.appraise(unmet["_id"])}
        self.note.write_text("tampered: not what the receipt recorded\n")
        end["reappraised"]["achievement_tampered"] = self.appraise()
        self.note.write_text(NOTE)
        end["reappraised"]["achievement_restored"] = self.appraise()
        after = self.facts()
        end["chain_after_readers"], end["head_after_readers"] = after["chain"], after["head"]
        end["elapsed"] = round(time.monotonic() - self.started, 1)


@pytest.fixture(scope="module")
def story(tmp_path_factory) -> Story:
    s = Story(tmp_path_factory.mktemp("composed"))
    try:
        s.run()
    except ScenarioBroken:
        raise
    except BaseException as exc:            # an assertion inside a helper, a failed CLI call, a missing record
        raise ScenarioBroken(f"{type(exc).__name__}: {exc}\nreached: {list(s.at)}\nbody log tail:\n"
                             + (s.log.read_text()[-3000:] if s.log.exists() else "")) from exc
    finally:
        s.reap()
        if s.gauge.is_file():
            s.gauge.unlink()                # the slow reading is large; nothing below reads the gauge
        if EVIDENCE:                        # what each point of the story held, and the ledger, for a reader
            out = Path(EVIDENCE)
            out.mkdir(parents=True, exist_ok=True)
            (out / "story.json").write_text(json.dumps(s.at, indent=1, default=str))
            for name in ("ledger.jsonl", "body.json"):
                if (s.home / name).exists():
                    (out / name).write_bytes((s.home / name).read_bytes())
            if s.log.exists():
                (out / "body.log").write_text(s.log.read_text())
    return s


GAP = dict(strict=True, raises=AssertionError)     # a broken story is an error, never an expected failure


def require(holds, what: str) -> None:
    """A fact a gap test stands on. When it does not hold the gap test fails outright (pytest.fail is not an
    AssertionError), so an expected failure is only ever the one assertion that states the missing behaviour."""
    if not holds:
        pytest.fail(f"the gap test's ground does not hold: {what}")


def mine(asks: list[dict]) -> list[dict]:
    """This mission's open asks. The body may hold asks of its own beside them (on a host with little free disk it
    asks about compute), and those are not this mission's."""
    return [r for r in asks if r.get("mission_id") == MID]


def by_action(facts: dict, action: str) -> list[dict]:
    return [a for a in facts["actions"] if a["action_id"] == action]


def reading(facts: dict, check: str = "c") -> list[dict]:
    return [o for o in facts["observed"] if o["check_id"] == check]


def receipt_of(facts: dict, row: dict) -> dict:
    return facts["receipts"][row["receipt"]]["result"]


def approved_grants(facts: dict, action: str) -> list[dict]:
    proposals = {i["proposal_id"] for i in facts["intents"] if i["action_id"] == action}
    return [e for e in facts["authority"] if e["type"] == "greg.authority.grant_issued"
            and e["proposal_id"] in proposals and e.get("founder_approved_scope")]


# -- 1. an authorized mission through the actual entry point ----------------------------------------------------

def test_1_the_signed_mission_enters_through_the_cli_and_a_body_process_picks_it_up(story):
    first, end = story.at["asked_a"], story.at["end"]
    [registered] = end["registered"]
    assert registered["spec"] == story.spec
    [accepted] = [c for c in end["accepted"] if c["kind"] == "MISSION"]
    assert accepted["digest"] == registered["command_digest"] and accepted["channel"] == "inbox"
    assert accepted["signer"] == "founder" and accepted["envelope"]["body"] == registered["spec"]
    assert accepted["founder_key_id"] in first["status"]["security"]["founder_keys_enrolled"]
    # picked up by the process the test started with `python -m greg --home <tmp> run`: its pid booted the main loop
    assert [(b["pid"], b.get("main_loop")) for b in first["booted"]] == [(story.pids[0], True)]
    assert first["status"]["background"]["pid"] == story.pids[0]
    # the body acted on it alone: it observed through the Gate and stopped at the approval boundary
    assert {o["check_id"]: o["passed"] for o in first["observed"]} == {"a": False, "b": False, "c": True}
    [ask] = mine(first["decisions"])
    assert (ask["kind"], ask["action_id"], ask["authority_requested"]["capability"]) == ("APPROVAL", "a", "fs.write")
    assert first["actions"] == [] and first["note"] is None
    assert [m["mission_id"] for m in first["status"]["missions"]] == [MID]
    assert end["chain"] and end["chain_after_readers"]
    assert end["head_after_readers"] == end["head"]          # every reader below, and the appraiser, wrote nothing


# -- 2. device approval and revocation ---------------------------------------------------------------------------

def test_2_a_revoked_device_approval_authorizes_nothing_and_what_it_approved_before_stands(story):
    done, paused, again = story.at["a_done"], story.at["revoked_while_paused"], story.at["asked_again"]
    end = story.at["end"]
    # A ran on the phone's approval and is receipted
    [a] = by_action(done, "a")
    assert a["status"] == "DONE" and a["cost_usd"] == COST_A and receipt_of(done, a)["result_class"] == "positive"
    ask_a, ask_b1, ask_b2 = (r for r in again["requested"] if r["kind"] == "APPROVAL")
    signer = {c["digest"]: c["signer"] for c in end["accepted"] if c["kind"] == "DECISION"}
    answers = {d["request_id"]: d for d in again["answered"]}
    assert signer[answers[ask_a["request_id"]]["command_digest"]] == "device:phone"
    assert len(approved_grants(done, "a")) == 1 and done["note"] == NOTE
    # the same phone approved B, and the founder revoked it before the body stepped the mission again
    assert signer[answers[ask_b1["request_id"]]["command_digest"]] == "device:phone"
    assert answers[ask_b1["request_id"]]["answer"] == "approve"
    [revoked] = [d for d in paused["devices"] if d["_type"] == "greg.device.revoked"]
    assert answers[ask_b1["request_id"]]["_seq"] < revoked["_seq"]
    [void] = [w for w in again["withdrawn"] if w["request_id"] == ask_b1["request_id"]]
    assert void["voids_approval"] is True and void["voided_by"]["signer"] == "device:phone"
    assert void["voided_by"]["revocation_event"] == revoked["_id"]
    # B did not run on the revoked approval: no adapter call, no grant, no dispatch claim, no record
    for at in (paused, again):
        assert at["calls"] == [] and by_action(at, "b") == [] and approved_grants(at, "b") == []
        assert [c for c in at["claims"] if c["action_id"] == "b"] == []
    assert again["state"]["approved_scopes"] == [] and again["state"]["status"] == "ACTIVE"
    # the mission asks again, for the same exact scope, under a new request id
    assert ask_b2["request_id"] != ask_b1["request_id"] and ask_b2["scope_digest"] == ask_b1["scope_digest"]
    assert again["state"]["blocker"]["request_id"] == ask_b2["request_id"]
    assert [r["request_id"] for r in mine(again["status"]["decisions_required"])] == [ask_b2["request_id"]]
    # the revoked phone's answer to the new ask is refused as data
    [refused] = again["rejected"]
    assert "not enrolled or revoked" in refused["reason"] and refused["instruction_status"] == "data_only"
    assert ask_b2["request_id"] not in answers
    [summary] = again["reviews"]["revocations"]
    assert summary["voided_requests"] == [ask_b1["request_id"]]
    # A's receipt and effect stand through the revocation, and to the end
    for at in (paused, again, end):
        assert by_action(at, "a") == by_action(done, "a") and at["note"] == NOTE
    # the founder key lets B proceed: the dispatch that follows is granted on the founder's answer
    flight = story.at["in_flight"]
    assert signer[{d["request_id"]: d for d in flight["answered"]}[ask_b2["request_id"]]["command_digest"]] == "founder"
    assert len(approved_grants(flight, "b")) == 1 and len(flight["calls"]) == 1


# -- 3. interruption and restart ---------------------------------------------------------------------------------

def test_3_a_dispatch_killed_in_flight_is_uncertain_asked_about_and_never_redispatched_blind(story):
    flight, dead, unc, done = (story.at[k] for k in ("in_flight", "after_kill", "uncertain", "a_done"))
    assert flight["killed_returncode"] == -signal.SIGKILL
    # what reached the disk: the Gate's claim of B's dispatch, no receipt for its grant, no record of the action
    for at in (flight, dead):
        [claim] = [c for c in at["claims"] if c["action_id"] == "b"]
        assert [r for r in at["receipts"].values() if r["grant_id"] == claim["grant_id"]] == []
        assert by_action(at, "b") == [] and len(at["calls"]) == 1
    assert dead["chain"] and int(dead["calls"][0].split()[0]) == story.pids[0]
    # a new process (another pid) reconstructs from the ledger and classifies the dispatch from the Gate's record
    assert len(unc["booted"]) == 2 and unc["booted"][1]["pid"] == story.pids[1] != story.pids[0]
    assert len(unc["recovered"]) == 1
    [b] = by_action(unc, "b")
    assert b["status"] == "UNCERTAIN" and b["attempt"] == 0 and b["receipt"] is None
    assert b["grant_id"] == claim["grant_id"] and "outcome is unknown" in b["reasons"][0]
    # the founder is asked to reconcile exactly that dispatch; nothing is redispatched while the ask is open
    [ask] = [r for r in unc["requested"] if r["kind"] == "RECONCILIATION"]
    assert ask["action_id"] == "b" and ask["alternatives"] == ["reconcile_executed", "reconcile_not_executed"]
    assert ask["authority_requested"]["grant_id"] == claim["grant_id"]
    assert ask["authority_requested"]["attempt"] == 0
    assert unc["state"]["blocker"]["type"] == "reconciliation"
    # which of the two settles it on this tree: the Gate's record classifies it (a claim, no receipt), and the
    # founder's answer settles it. Until that answer there is no other record of B
    assert [a["status"] for a in by_action(unc, "b")] == ["UNCERTAIN"] and unc["state"]["status"] == "ACTIVE"
    assert len(unc["calls"]) == 1 and len([c for c in unc["claims"] if c["action_id"] == "b"]) == 1
    assert len([i for i in unc["intents"] if i["action_id"] == "b"]) == 1
    # effect A is not replayed: one record, one Gate claim, one receipt, the same file (inode and mtime), same bytes
    end = story.at["end"]
    for at in (unc, end):
        assert by_action(at, "a") == by_action(done, "a")
        [a_claim] = [c for c in at["claims"] if c["action_id"] == "a"]
        assert len([r for r in at["receipts"].values() if r["grant_id"] == a_claim["grant_id"]]) == 1
        assert at["note"] == NOTE
    assert unc["note_file"] == done["note_file"] == end["note_file_before_tamper"]
    assert receipt_of(end, by_action(end, "a")[0])["output"]["sha256"] == hashlib.sha256(NOTE.encode()).hexdigest()
    # no cost is booked twice: the unknown dispatch reserves its signed cap and books nothing
    assert b["cost_usd"] == 0.0 and b["reserved_usd"] == COST_B
    assert unc["state"]["spent_usd"] == COST_A and unc["state"]["reserved_usd"] == COST_B
    assert ask["evidence"]["reserved_usd"] == COST_B
    booked = [(a["action_id"], a["attempt"], a["status"], a["cost_usd"]) for a in end["actions"] if a["cost_usd"]]
    assert booked == [("a", 0, "DONE", COST_A), ("b", 1, "DONE", COST_B)]
    assert end["state"]["spent_usd"] == pytest.approx(COST_A + COST_B) and end["state"]["reserved_usd"] == 0.0


# -- 4. the preferred tool removed -------------------------------------------------------------------------------

def test_4_a_detached_tool_is_refused_by_the_office_and_the_mission_names_what_it_needs(story):
    det, asked, done = story.at["detached"], story.at["office_asked"], story.at["a_done"]
    assert [(s["capability_id"], s["state"]) for s in det["capability_state"]] == [("artifact.store", "DETACHED")]
    # the founder's "not executed" settles the interrupted dispatch and releases its reserved cap
    assert [(a["attempt"], a["status"]) for a in by_action(det, "b")] == [(0, "UNCERTAIN"),
                                                                        (0, "RECONCILED_NOT_EXECUTED")]
    assert det["state"]["spent_usd"] == COST_A and det["state"]["reserved_usd"] == 0.0
    # the mission does not run B: no new intent, claim or adapter call; it is blocked on the tool, by name
    assert len(det["calls"]) == 1 and len([c for c in det["claims"] if c["action_id"] == "b"]) == 1
    assert len([i for i in det["intents"] if i["action_id"] == "b"]) == 1
    blocker = det["state"]["blocker"]
    assert (blocker["type"], blocker["capability_id"]) == ("capability", "artifact.store")
    [ask] = [r for r in det["requested"] if r["kind"] == "CAPABILITY_ATTACH"]
    assert blocker["request_id"] == ask["request_id"]
    [typed] = det["blockers"]
    assert typed["kind"] == "capability" and "state DETACHED" in typed["required_evidence"]
    assert "greg attach artifact.store" in typed["next_move"]
    [row] = det["status"]["missions"]
    assert row["active_constraint"]["blocker"]["kind"] == "CAPABILITY_ATTACH"
    assert row["active_constraint"]["blocker"]["lifted_by"] == "capability"
    assert [r["request_id"] for r in mine(det["decisions"])] == [ask["request_id"]]
    # the office itself, asked for B at the scope the founder approved, refuses: before any grant, with no receipt
    assert det["stopped_returncode"] == 0
    office = det["office"]
    assert office["registry_state"] == "DETACHED" and len(office["approved_scopes"]) == 1
    own, other = office["own_identity"], office["other_identity"]
    assert own["status"] == "REFUSED" and "DETACHED" in own["reasons"][0]
    assert own["receipt"] is None and own["grant_id"] is None and own["scope_digest"] in office["approved_scopes"]
    assert other["status"] == "REFUSED" and "adapter presented for artifact.inspect" in other["reasons"][0]
    assert other["receipt"] is None and other["grant_id"] is None
    assert office["retained"] is False and len(asked["calls"]) == 1
    # recorded as refusals, on this mission, and as nothing else: no grant, no claim, no receipt, no action record
    refusals = [e for e in asked["authority"] if e["type"] == "greg.authority.refused_unattached"]
    assert [(e["capability"], e["mission_id"]) for e in refusals] == [("artifact.store", MID),
                                                                      ("artifact.inspect", MID)]
    assert [e["proposal_id"] for e in refusals] == [own["proposal_id"], other["proposal_id"]]
    grants = lambda at: [e for e in at["authority"] if e["type"] == "greg.authority.grant_issued"]   # noqa: E731
    assert len(grants(asked)) == len(grants(det)) and asked["claims"] == det["claims"]
    assert len(asked["receipts"]) == len(det["receipts"]) and asked["actions"] == det["actions"]
    # the completed effect still stands
    assert by_action(asked, "a") == by_action(done, "a") and asked["note"] == NOTE
    # once the founder attaches the tool again, the same approved scope runs once, as attempt 1
    end = story.at["end"]
    assert [(s["capability_id"], s["state"]) for s in end["capability_state"]][-1] == ("artifact.store", "ATTACHED")
    assert [(a["attempt"], a["status"]) for a in by_action(end, "b")][-1] == (1, "DONE")
    assert len(end["calls"]) == 2 and len([c for c in end["claims"] if c["action_id"] == "b"]) == 2


# -- 5. the supporting observation invalidated -------------------------------------------------------------------

def test_5_an_unreadable_or_timed_out_reading_is_unmeasured_and_a_false_one_is_a_measured_failure(story):
    flight, det, unm, fail, end = (story.at[k] for k in ("in_flight", "detached", "unmeasured", "failure_closure",
                                                         "end"))
    # the earlier readings of C passed; none of them is counted once the gauge changed
    passing = [o for o in reading(end) if o["passed"]]
    first_bad = min(o["_seq"] for o in reading(end) if not o["passed"])
    assert len([o for o in passing if o["_seq"] < first_bad]) >= 4
    # unreadable: recorded as unmeasured (a refused sensor call with a negative receipt), not as a failed check
    unreadable = [o for o in reading(flight) if not o["passed"]]
    assert unreadable and all(o["detail"].startswith("sensor REFUSED: capability refused: gauge.txt is not a "
                                                    "regular file") and not measured(o) for o in unreadable)
    assert all(receipt_of(flight, o)["result_class"] == "negative" for o in unreadable)
    # the repair for C ran on that reading; the next reading was unreadable again, and the repair is not blamed
    [refresh] = by_action(flight, "refresh")
    assert refresh["status"] == "DONE" and unreadable[0]["_seq"] < refresh["_seq"] < unreadable[-1]["_seq"]
    assert flight["state"]["failed"]["refresh"].startswith("executed but c still failing: sensor REFUSED")
    assert flight["routing"] == [] and det["routing"] == [] and unm["routing"] == []
    # with A and B done and C unmeasured (unreadable, then past its time limit) the mission closes nothing: no
    # achievement, no failure closure; after three unmeasured rounds it asks about the sensor, and blames no strategy
    assert [a["status"] for a in by_action(unm, "b")][-1] == "DONE"
    latest = {c: reading(unm, c)[-1] for c in "abc"}
    assert latest["a"]["passed"] and latest["b"]["passed"] and not latest["c"]["passed"] and not measured(latest["c"])
    assert unm["achieved"] == [] and unm["unmet"] == [] and unm["appraised"] == []
    [sensor_ask] = [r for r in unm["requested"] if r["kind"] == "SENSOR_FAILURE"]
    assert sensor_ask["authority_requested"] == {"checks": ["c"]}
    assert unm["state"]["blocker"]["sensing"] is True and unm["state"]["status"] == "ACTIVE"
    assert [r["kind"] for r in mine(unm["decisions"])] == ["SENSOR_FAILURE"]
    [row] = unm["status"]["missions"]
    assert row["active_constraint"]["check_id"] == "c" and "time limit" in row["active_constraint"]["observed"]
    assert not [r for r in unm["requested"] if r["kind"] == "NO_STRATEGY"]
    # red: a measured failure. The sensor ask is withdrawn (the gauge is read again), the repair is now blamed for a
    # reading that measured the world, and the mission closes as a failure naming C, on the reading it just took
    red = [o for o in reading(fail) if not o["passed"] and measured(o)]
    assert red and all(o["detail"] == "False == True" for o in red)
    assert all(receipt_of(fail, o)["result_class"] == "positive" for o in red)
    assert all(receipt_of(fail, o)["output"]["complete"] is True for o in red)
    [withdrawn] = [w for w in fail["withdrawn"] if w["request_id"] == sensor_ask["request_id"]]
    assert "read again" in withdrawn["why"]
    [blame] = fail["routing"]
    assert (blame["action_id"], blame["verdict"]) == ("refresh", "ineffective") and blame["_seq"] > red[0]["_seq"]
    [unmet] = fail["unmet"]
    assert unmet["failing_checks"] == ["c"] and "unmeasured_checks" not in unmet and unmet["_seq"] > red[-1]["_seq"]
    assert fail["achieved"] == [] and fail["state"]["status"] == "ACTIVE"
    [no_strategy] = [r for r in fail["requested"] if r["kind"] == "NO_STRATEGY"]
    assert no_strategy["evidence"]["failing_checks"] == ["c"]
    assert [r["request_id"] for r in mine(fail["decisions"])] == [no_strategy["request_id"]]
    # green again: the mission closes on a reading taken after the red ones, never on an earlier pass
    [achieved] = end["achieved"]
    green = [o for o in reading(end) if o["passed"] and red[-1]["_seq"] < o["_seq"] < achieved["_seq"]]
    assert len(green) == 1 and green[0]["receipt"] in achieved["evidence"]


# -- 6. five outcomes kept apart ---------------------------------------------------------------------------------

def test_6_uncertain_timeout_refusal_failure_and_refutation_are_five_different_records(story):
    end = story.at["end"]
    # UNCERTAIN: mission.action.status, for the dispatch the body was killed inside
    uncertain = [a for a in end["actions"] if a["status"] == "UNCERTAIN"]
    assert [(a["action_id"], a["attempt"], a["receipt"]) for a in uncertain] == [("b", 0, None)]
    # TIMEOUT: a reading whose own receipt says the sensor stopped at its time limit; unmeasured, and no failure
    timeouts = [o for o in reading(end) if o.get("receipt") and
                str((receipt_of(end, o).get("output") or {}).get("stopped") or "").startswith("time limit")]
    assert len(timeouts) >= 3
    for o in timeouts:
        result = receipt_of(end, o)
        assert result["result_class"] == "positive" and result["output"]["complete"] is False
        assert result["output"]["queries"][0]["found"] is None
        assert o["detail"].startswith("sensor inconclusive (incomplete evidence)") and "time limit" in o["detail"]
        assert not o["passed"] and not measured(o)
    # REFUSAL: the office's own record that it ran nothing for an unattached capability; and the revoked key's answer
    refusals = [e for e in end["authority"] if e["type"] == "greg.authority.refused_unattached"]
    assert len(refusals) == 2 and all(e["mission_id"] == MID for e in refusals)
    assert len(end["rejected"]) == 1 and "revoked" in end["rejected"][0]["reason"]
    # FAILURE: a reading that measured the world and found the check false (a complete read, a positive receipt)
    failures = [o for o in reading(end) if not o["passed"] and measured(o)]
    assert failures and all(receipt_of(end, o)["output"]["complete"] is True for o in failures)
    [unmet] = end["unmet"]
    # REFUTATION: the separate appraiser's verdict on the achievement once A's deliverable was tampered with; with
    # the deliverable restored the same closure is VERIFIED again. (The appraiser ran as its own process over the
    # ledger at rest. The body appraises a closure once, when it records it, so these two verdicts are that
    # process's answers and not ledger records.)
    tampered, restored = end["reappraised"]["achievement_tampered"], end["reappraised"]["achievement_restored"]
    assert tampered["verdict"] == "REFUTED" and tampered["checks"]["world_reobserved"] is False
    assert any(f.startswith("a: world no longer matches") for f in tampered["findings"])
    assert tampered["checks"]["exactly_once"] and tampered["checks"]["checks_rederived_from_receipts"]
    assert restored["verdict"] == "VERIFIED" and restored["findings"] == []
    # none is folded into another: the five sets of records are disjoint, and each is named by its own field
    unreadable = [o for o in reading(end) if o["detail"].startswith("sensor REFUSED")]
    ids = [{a["_id"] for a in uncertain}, {o["_id"] for o in timeouts}, {o["_id"] for o in unreadable},
           {o["_id"] for o in failures}, {e["proposal_id"] for e in refusals}]
    assert all(ids) and sum(len(s) for s in ids) == len(set().union(*ids))
    assert tampered["head"] == restored["head"] == end["head"]      # the same ledger; only the deliverable differed
    assert not [a for a in end["actions"] if a["status"] in ("REFUSED", "UNAVAILABLE", "FAILED")]
    assert unmet["failing_checks"] == ["c"]                 # the failure closure rests on measured readings only:
    window = [o for o in reading(end) if o["_seq"] < unmet["_seq"]]
    assert measured(window[-1]) and not window[-1]["passed"]
    # a refusal has no grant and no receipt (when the office refused, nothing named its proposals); a failed read,
    # a timed-out read and a measured failure each have a Gate receipt of their own
    then = story.at["office_asked"]
    assert not [e for e in then["authority"] if e["type"] == "greg.authority.grant_issued"
                and e["proposal_id"] in {r["proposal_id"] for r in refusals}]
    assert all(o["receipt"] in end["receipts"] for o in timeouts + failures + unreadable)
    # the uncertain dispatch became neither a success nor a failure by itself: the founder's answer settled it
    settled = [a for a in end["actions"] if a["action_id"] == "b" and a["attempt"] == 0][-1]
    assert settled["status"] == "RECONCILED_NOT_EXECUTED" and settled["route"] == "founder_reconciliation"
    assert end["model_spend"] == []


@pytest.mark.xfail(reason="greg/routing.py:32 counts UNCERTAIN and RECONCILED_NOT_EXECUTED as FAILURE, so `greg "
                          "routing` reports the dispatch the body was killed inside as a failure of its capability",
                   **GAP)
def test_6_gap_the_routing_reader_does_not_fold_the_uncertain_dispatch_into_failed(story):
    end = story.at["end"]
    require([(a["attempt"], a["status"]) for a in by_action(end, "b")] == [
        (0, "UNCERTAIN"), (0, "RECONCILED_NOT_EXECUTED"), (1, "DONE")], "B's three records")
    row = {r["capability"]: r for r in end["routing"]}["artifact.store"]
    require(row["done"] == 1, "the one receipted run of artifact.store is counted done")
    assert row["failed"] == 0, row


# -- 7. an appraisal bound to the closure it judged --------------------------------------------------------------

def test_7_each_appraisal_record_names_the_closure_it_judged(story):
    end = story.at["end"]
    [unmet], [achieved] = end["unmet"], end["achieved"]
    assert unmet["_seq"] < achieved["_seq"] and story.at["failure_closure"]["killed_returncode"] == -signal.SIGKILL
    assert story.at["failure_closure"]["killed_mark"] == "mission.appraised VERIFIED_UNMET"
    assert story.at["failure_closure"]["appraised"] == []        # the verdict the killed process held was never kept
    [of_failure] = [a for a in end["appraised"] if a.get("closure_event")]
    [of_achievement] = [a for a in end["appraised"] if not a.get("closure_event")]
    # the failure closure's appraisal names it by event id and kind; the achievement's names no other closure
    assert of_failure["closure_event"] == unmet["_id"] and of_failure["closure"] == "unmet"
    assert "closure_event" not in of_achievement and "closure" not in of_achievement
    # each is pinned to the ledger head it read, and that head lies after the closure it judged
    assert achieved["_seq"] <= of_achievement["_head_seq"] < of_achievement["_seq"]
    assert unmet["_seq"] < of_failure["_head_seq"] < of_failure["_seq"]
    # the achievement's verdict rests on the achievement's evidence: the readings its record cites
    assert of_achievement["verdict"] == "VERIFIED" and all(of_achievement["checks"][k] for k in (
        "closure_evidence_bound", "checks_rederived_from_receipts", "world_reobserved", "exactly_once",
        "approval_boundaries_honored", "founder_signature_verified"))
    cited = set(achieved["evidence"])
    assert {reading(end, c)[-1]["receipt"] for c in "abc"} == cited
    # asked again, each closure gets its own answer from the separate appraiser, whatever the other's was
    again = end["reappraised"]
    assert again["achievement"]["verdict"] == "VERIFIED" and "closure_event" not in again["achievement"]
    assert again["failure_closure"]["closure_event"] == unmet["_id"] and again["failure_closure"]["closure"] == "unmet"
    # Mission Control says which closure each verdict is for
    rows = [r for r in end["mission_control"]["appraisals"] if r["mission_id"] == MID]
    assert sorted((r["closure"], r["verdict"]) for r in rows) == [
        ("achievement", "VERIFIED"), ("failure closure " + unmet["_id"][:8], of_failure["verdict"])]
    # settlement reads an observation under its own closure's appraisal
    assert end["functions"]["settlement._observation_appraisal(last reading of c)"] == of_achievement["_id"]


@pytest.mark.xfail(reason="greg/appraisal.py:638 leaves a late re-reading open only when the closure waited on a "
                          "detached capability; a failure closure first appraised after a restart is REFUTED by a "
                          "world that changed after it, though its own receipts hold", **GAP)
def test_7_gap_a_closure_appraised_after_a_restart_is_not_refuted_by_a_world_that_changed_since(story):
    end = story.at["end"]
    [unmet] = end["unmet"]
    of_failure = [a for a in end["appraised"] if a.get("closure_event") == unmet["_id"]][-1]
    # appraised in time, by the process that was then killed before it could record the verdict, it was a verified
    # failure; its own evidence still holds (the appraiser says so); only the gauge as read later disagrees
    require(story.at["failure_closure"]["killed_mark"] == "mission.appraised VERIFIED_UNMET",
            "the first, unrecorded appraisal of this closure was VERIFIED_UNMET")
    require(of_failure["checks"]["checks_rederived_from_receipts"] and of_failure["checks"]["closure_evidence_bound"],
            "the failure closure's own receipts hold")
    require(of_failure["findings"] == ["c: world no longer matches (True == True)"], "the one finding is the late "
            "re-reading of the gauge")
    assert of_failure["verdict"] != "REFUTED", of_failure["verdict"]


def achievement_verified(end: dict) -> dict:
    """The achievement's own appraisal, which is VERIFIED; a gap test below is about how a reader reads it."""
    own = [a for a in end["appraised"] if "closure_event" not in a]
    require(len(own) == 1 and own[0]["verdict"] == "VERIFIED", "the achievement's own appraisal is VERIFIED")
    require(end["appraised"][-1] is not own[0], "a later appraisal, of the earlier failure closure, follows it")
    return own[0]


def test_7_vepmc_reads_the_achievements_own_appraisal(story):
    end = story.at["end"]
    achievement_verified(end)
    [row] = [m for m in end["vepmc"]["missions"] if m["mission_id"] == MID]
    require(row["closure_event_id"] == end["achieved"][0]["_id"], "the row is about the achievement")
    assert row["appraised_verified"] is True, row


def test_7_the_acceptance_report_reads_the_achievements_own_appraisal(story):
    end = story.at["end"]
    achievement_verified(end)
    properties = {p["property"]: p["status"] for p in end["acceptance"]["properties"]}
    assert properties["first_mission_verified"] == "PASS", properties["first_mission_verified"]


def test_7_routing_credits_actions_under_the_closure_that_covered_them(story):
    end = story.at["end"]
    achievement_verified(end)
    rows = {r["capability"]: r for r in end["routing"]}
    require(rows["artifact.store"]["done"] == 1 and rows["fs.write"]["done"] == 2, "three receipted runs")
    assert [(rows[c]["verified"], rows[c]["refuted"]) for c in ("artifact.store", "fs.write")] == [(1, 0), (2, 0)], rows


def test_7_sop_reads_the_achievements_own_appraisal(story):
    end = story.at["end"]
    require(end["sop_trend"] == {"procedures": []}, "`greg sop trend`: no procedure was learned or run here")
    assert end["functions"]["sop.verified_appraisals"] == achievement_verified(end)["_id"]


def test_7_settlement_settling_appraisal_is_the_achievements_own(story):
    end = story.at["end"]
    assert end["functions"]["settlement._settling_appraisals"] == achievement_verified(end)["_id"]


@pytest.mark.xfail(reason="foundry/systems/observability.py:56 gives an appraisal span its verdict and no closure: "
                          "`greg foundry trace` shows two verdicts for the mission and not which closure each judged",
                   **GAP)
def test_7_gap_the_trace_says_which_closure_each_verdict_judged(story):
    end = story.at["end"]
    spans = [s for s in end["trace"]["missions"][MID]["spans"] if s["kind"] == "mission.appraised"]
    require([s["event_id"] for s in spans] == [a["_id"] for a in end["appraised"]], "one span per appraisal record")
    [unmet] = end["unmet"]
    of_failure = next(s for s, a in zip(spans, end["appraised"]) if a.get("closure_event"))
    assert unmet["_id"] in [str(v) for v in of_failure.values()], sorted(of_failure)


# -- 8. the account ----------------------------------------------------------------------------------------------

def test_8_the_founder_facing_readers_state_outcome_costs_uncertainty_and_next_step(story):
    unc, det, end = story.at["uncertain"], story.at["detached"], story.at["end"]
    # while the dispatch is uncertain: what is uncertain, and the decision waited on
    [row] = unc["status"]["missions"]
    assert row["achieved"] is False and row["active_constraint"]["blocker"]["kind"] == "RECONCILIATION"
    assert row["active_constraint"]["blocker"]["lifted_by"] == "evidence of what happened"
    [ask] = mine(unc["decisions"])
    assert ask["kind"] == "RECONCILIATION" and ask["action_id"] == "b"
    assert ask["why_now"] == "an action may or may not have executed before an interruption"
    assert ask["evidence"]["booked_usd_by_answer"] == {"reconcile_executed": COST_B, "reconcile_not_executed": 0.0}
    assert ask["consequence_of_no_response"] == "the mission waits; no action is taken"
    [typed] = unc["blockers"]
    assert typed["kind"] == "reconciliation" and typed["mission_id"] == MID
    spans = [s for s in unc["trace"]["missions"][MID]["spans"] if s["kind"] == "mission.action"]
    assert [(s["capability"], s["status"], s["cost_usd"]) for s in spans] == [
        ("fs.write", "DONE", COST_A), ("fs.write", "DONE", 0.0), ("artifact.store", "UNCERTAIN", 0.0)]
    assert unc["trace"]["metrics"]["cost_usd"] == COST_A
    # while the tool is detached: the next step is named
    assert "greg attach artifact.store" in det["blockers"][0]["next_move"]
    # at the end: the outcome
    [row] = end["status"]["missions"]
    assert row["achieved"] is True and row["active_constraint"] is None
    assert mine(end["decisions"]) == [] and end["blockers"] == []
    assert mine(end["status"]["decisions_required"]) == []
    assert end["status"]["security"]["chain_verified"] is True and end["status"]["boots"] == 4 == len(story.pids)
    assert [d["voided_requests"] for d in end["status"]["security"]["device_revocations"]] == [
        [r["request_id"] for r in end["requested"] if r["kind"] == "APPROVAL"][1:2]]
    assert end["status"]["security"]["devices"] == []
    [mc] = [m for m in end["mission_control"]["missions"] if m["mission_id"] == MID]
    assert (mc["status"], mc["blocker"], mc["actions_done"]) == ("ACHIEVED", None, 3)
    # every action and what it cost: the trace's rows are the ledger's records, at the cost the ledger booked
    spans = [s for s in end["trace"]["missions"][MID]["spans"] if s["kind"] == "mission.action"]
    assert [(s["event_id"], s["status"], s["cost_usd"], s["receipt"]) for s in spans] == [
        (a["_id"], a["status"], a["cost_usd"], a["receipt"]) for a in end["actions"]]
    assert [(s["capability"], s["status"], s["cost_usd"]) for s in spans] == [
        ("fs.write", "DONE", COST_A), ("fs.write", "DONE", 0.0), ("artifact.store", "UNCERTAIN", 0.0),
        ("artifact.store", "RECONCILED_NOT_EXECUTED", 0.0), ("artifact.store", "DONE", COST_B)]
    assert end["trace"]["metrics"]["cost_usd"] == pytest.approx(COST_A + COST_B)
    assert end["trace"]["metrics"]["closures"] == 1.0
    # the count of dispatches: four reached the Gate (A, the repair, B twice); the trace shows the same four
    dispatched = [s for s in spans if s["status"] in ("DONE", "UNCERTAIN")]
    assert len(dispatched) == len(end["claims"]) == 4 and len(end["calls"]) == 2
    # zero model spend: the mission names no model origin and nothing was built or reasoned by a model
    assert end["model_spend"] == [] and end["status"]["cognition"]["receipts"] == []
    assert "provenance" not in end["registered"][0]["spec"]
    # the decisions the founder was asked for, in order, and how each ended
    asked = [(r["kind"], r.get("action_id")) for r in end["requested"]]
    assert asked == [("APPROVAL", "a"), ("APPROVAL", "b"), ("APPROVAL", "b"), ("RECONCILIATION", "b"),
                     ("CAPABILITY_ATTACH", None), ("SENSOR_FAILURE", None), ("NO_STRATEGY", None)]
    answered = {d["request_id"]: d["answer"] for d in end["answered"]}
    withdrawn = {w["request_id"] for w in end["withdrawn"]}
    ended = ["answered " + answered[r["request_id"]] + (", then voided" if r["request_id"] in withdrawn else "")
             if r["request_id"] in answered else "withdrawn" if r["request_id"] in withdrawn else "open"
             for r in end["requested"]]
    assert ended == ["answered approve", "answered approve, then voided", "answered approve",
                     "answered reconcile_not_executed", "withdrawn", "withdrawn", "withdrawn"]
    # the outcome's proof, as Mission Control shows it: both verdicts, each with its closure
    assert [r["verdict"] for r in end["mission_control"]["appraisals"]
            if r["mission_id"] == MID and r["closure"] == "achievement"] == ["VERIFIED"]
    assert story.at["end"]["elapsed"] < 600
