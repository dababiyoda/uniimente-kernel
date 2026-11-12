"""The founder's combined recovery experiment, finished through an allowed alternative, on real processes.

Founder, 2026-11-12, verbatim: "Combine these capabilities in one experiment: interrupt a mission, invalidate one
supporting observation, remove its preferred tool, and preserve an already completed effect. Determine whether GREG
can repair the missing function through an allowed alternative, obtain appraisal, and finish." And: "Capability
repair cannot restore revoked authority." "Recovery preserves actual incurred costs and completed effects."
"Unreadable evidence remains unknown until reconciled. A timeout does not establish measured failure." "A stale
appraisal cannot qualify a different closure."

tests/integration/test_composed_machine_acceptance.py (#306) answers with the founder attaching the same tool again.
This file asks whether GREG finishes without that. It is written in #306's style: the body is `python -m greg --home
<tmp> run`, its own OS process; every founder act is a separate `greg` CLI process; the test reads the ledger and
files, sends signals and changes the gauge file. One founder-signed mission (per-test Ed25519 key, never a real one):

  effect A    `a`   artifact.store of data/note.txt, $0.10, outside the cone: the founder approves it
  preferred   `b`   artifact.materialize of the retained bytes to copy.txt, $0.25, outside the cone
  alternative `b2`  fs.write of the same text to copy.txt, $0.50, inside the signed cone (the founder allowed it)
  check  C    `c`   the gauge file reads "green" (fs.search); no strategy advances it

`b` ranks above `b2` for check b (it costs less), before the interruption and after it. Both are built-in
capabilities this tree holds, so the separate appraiser, a process of its own, can judge either. They serve check b
with different function tags: the tree holds no two built-in capabilities with one function.

The story, in order (the test waits on the ledger or a file, never on a fixed delay):

  1. signed and submitted through the CLI; the body process picks it up; the founder approves A; A runs
  2. the gauge is made unreadable; the founder approves B; the body is SIGKILLed while B's dispatch is in flight; a
     new process classifies it UNCERTAIN and asks the founder to reconcile
  3. the founder detaches artifact.materialize, then reconciles "not executed"
  4. GREG passes over B (its tool is detached) and runs B2 under B2's own scope; with C unreadable it closes nothing
     and asks about the sensor
  5. the gauge reads green; the mission closes on a fresh reading and the body's separate appraiser judges the
     achievement; the body is stopped
  6. the separate appraiser, run as its own process on the ledger at rest: the achievement, the achievement with the
     working copy tampered with, and restored

Test instrumentation in the body process (a ``sitecustomize`` on its PYTHONPATH, as in #306; no product file is
touched): the adapters of artifact.store, artifact.materialize and fs.write append one line per call to a file, and
artifact.materialize, while a flag file exists, does not return (so the kill lands inside the dispatch, before the
real adapter runs). Nothing else in the body differs from `greg run`.

Reality: LABORATORY (a container, test keys); nothing here counts toward VEPMC, authenticates a person, spends money
or contacts anyone. Set GREG_ALTERNATIVE_EVIDENCE=<dir> to keep what each point of the story held, the ledger and
the body's log.
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

from greg.missions import MissionBook, measured
from tests.greg_fixtures import horizon, workspace
from tests.integration.test_greg_body_supervised import ROOT, greg, heartbeat, history, wait_for

MID = "m:recovery-through-alternative"
NOTE = "alpha: the note this mission retains\n"
ADDRESS = "sha256:" + hashlib.sha256(NOTE.encode()).hexdigest()
NAMESPACE = "retained"
COST_A, COST_B, COST_ALT = 0.10, 0.25, 0.50
EVIDENCE = os.environ.get("GREG_ALTERNATIVE_EVIDENCE")
# #306's story, as its test 8 pins it: the decisions the founder was asked for, in order. It also needed one founder
# command that is not an answer: `greg attach artifact.store`.
COMPOSED_ASKS = [("APPROVAL", "a"), ("APPROVAL", "b"), ("APPROVAL", "b"), ("RECONCILIATION", "b"),
                 ("CAPABILITY_ATTACH", None), ("SENSOR_FAILURE", None), ("NO_STRATEGY", None)]

INSTRUMENTATION = '''
"""Test instrumentation for tests/integration/test_recovery_through_alternative.py. Loaded only by the body process
that test starts (GREG_ALT_CTRL names its control directory). It replaces no product file."""
import os, time
CTRL = os.environ.get("GREG_ALT_CTRL")
if CTRL:
    from greg import capabilities

    def _mark(text):
        with open(os.path.join(CTRL, "calls"), "a") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())

    def _counted(cid):
        manifest, real = capabilities.BUILTINS[cid]

        def adapter(params, ctx):
            _mark(f"{cid} {os.getpid()} {ctx.mission_id} {ctx.grant_id}\\n")
            if cid == "artifact.materialize" and os.path.exists(os.path.join(CTRL, "hang")):
                time.sleep(3600)               # killed here: the Gate claimed the dispatch; no effect, no receipt
            return real(params, ctx)
        capabilities.BUILTINS[cid] = (manifest, adapter)
    for _cid in ("artifact.store", "artifact.materialize", "fs.write"):
        _counted(_cid)
'''


class ScenarioBroken(Exception):
    """The story could not be driven to its end; what the assertions below would read does not exist."""


def mission_spec(home: Path, data: Path) -> dict:
    copy = workspace(home, MID) / "copy.txt"
    return {
        "mission_id": MID, "priority": 60,
        "founder_expression": "Retain the note, keep a working copy of it, and close only while the gauge reads green.",
        "intended_effect": "the note is retained by digest, copy.txt holds it, and the gauge reads green",
        "closure": {"kind": "bounded", "cadence_seconds": 60},
        "success_checks": [
            {"check_id": "a", "description": "the note is retained by digest",
             "sensor": {"capability": "artifact.inspect", "params": {"namespace": NAMESPACE, "address": ADDRESS},
                        "target": f"artifact:{NAMESPACE}"},
             "predicate": {"op": "equals", "field": "present", "value": True}},
            {"check_id": "b", "description": "a working copy of the note exists",
             "sensor": {"capability": "fs.read", "params": {"path": str(copy)}, "target": "fs:copy.txt"},
             "predicate": {"op": "contains", "field": "text", "value": "alpha"}},
            {"check_id": "c", "description": "the gauge reads green",
             "sensor": {"capability": "fs.search", "target": "fs:gauge.txt",
                        "params": {"path": str(data / "gauge.txt"), "phrases": ["green"], "max_seconds": 1}},
             "predicate": {"op": "equals", "field": "queries.0.found", "value": True}}],
        "strategies": [
            {"action_id": "a", "capability": "artifact.store",
             "params": {"namespace": NAMESPACE, "path": str(data / "note.txt")}, "target": f"artifact:{NAMESPACE}",
             "advances": ["a"], "rationale": "retain the note by digest", "cost_usd": COST_A},
            {"action_id": "b", "capability": "artifact.materialize",
             "params": {"namespace": NAMESPACE, "address": ADDRESS, "relative_path": "copy.txt"},
             "target": "workspace:copy.txt", "advances": ["b"], "requires": ["a"],
             "rationale": "restore the retained bytes as the working copy (preferred)", "cost_usd": COST_B},
            {"action_id": "b2", "capability": "fs.write", "params": {"relative_path": "copy.txt", "content": NOTE},
             "target": "workspace:copy.txt", "advances": ["b"], "requires": ["a"],
             "rationale": "write the working copy from the signed text (alternative)", "cost_usd": COST_ALT}],
        "light_cone": {"capabilities": ["fs.read", "fs.search", "artifact.inspect", "fs.write"],
                       "targets": ["fs:*", f"artifact:{NAMESPACE}", "workspace:*"],
                       "max_consequence_class": "internal_write", "budget_usd": 1.0, "horizon": horizon()}}


class Story:
    """The driver. It keeps what it saw at each point (``at``); the tests below assert on that."""

    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.home, self.data = tmp / "body", tmp / "data"
        self.key = tmp / "founder.pem"
        self.ctrl, self.inject, self.log = tmp / "ctrl", tmp / "inject", tmp / "body.log"
        self.gauge = self.data / "gauge.txt"
        self.copy = workspace(self.home, MID) / "copy.txt"
        self.body: subprocess.Popen | None = None
        self.pids: list[int] = []
        self.at: dict[str, dict] = {}
        self.started = time.monotonic()

    # -- processes ---------------------------------------------------------------------------------------------
    def cli(self, *args) -> str:
        return greg(self.home, *args).stdout

    def founder(self, *args) -> str:
        return self.cli(*args, "--key", str(self.key), "--no-passphrase")

    def read(self, *args):
        return json.loads(self.cli(*args))

    def start(self) -> None:
        env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(self.inject), str(ROOT)]),
               "GREG_FOUNDER_PASSPHRASE": "", "GREG_ALT_CTRL": str(self.ctrl)}
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

    def wait(self, predicate, what: str, timeout: float = 120):
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
            m = MissionBook(journal).missions.get(MID)
            state = None if m is None else {
                "status": m.status, "spent_usd": m.spent_usd, "reserved_usd": m.reserved_usd,
                "approved_scopes": sorted(m.approved_scopes), "blocker": m.blocker, "failed": dict(m.failed)}
            return {
                "registered": rows("mission.registered"), "actions": rows("mission.action"),
                "observed": rows("mission.observed"), "intents": intents, "claims": claims, "receipts": receipts,
                "authority": authority, "requested": rows("decision.requested"),
                "answered": rows("decision.answered", mission=False),
                "withdrawn": rows("decision.withdrawn", mission=False), "achieved": rows("mission.achieved"),
                "unmet": rows("mission.unmet"),
                "appraised": [{**a, "_head_seq": position(a["head"])} for a in rows("mission.appraised")],
                "accepted": rows("command.accepted", mission=False), "booted": rows("body.booted", mission=False),
                "capability_state": rows("capability.state", mission=False),
                "chain": ledger.verify_chain()[0], "head": ledger.head, "state": state,
                "calls": (self.ctrl / "calls").read_text().splitlines() if (self.ctrl / "calls").exists() else [],
                "copy": self.copy.read_text() if self.copy.exists() else None}
        finally:
            ledger.close()

    def keep(self, label: str, **readers) -> dict:
        self.at[label] = {**self.facts(), **readers, "elapsed": round(time.monotonic() - self.started, 1)}
        return self.at[label]

    def account(self) -> dict:
        """The founder-facing readers, each its own CLI process."""
        return {"status": self.read("status"), "decisions": self.read("decisions"),
                "blockers": self.read("blockers", "--mission", MID),
                "trace": self.read("foundry", "trace", "--mission", MID)}

    def set_gauge(self, reading: str) -> None:
        """green | unreadable (a directory where the file was)."""
        if self.gauge.is_dir():
            self.gauge.rmdir()
        if reading == "unreadable":
            self.gauge.unlink(missing_ok=True)
            self.gauge.mkdir()
            return
        fresh = self.gauge.with_name("gauge.next")
        fresh.write_text(f"gauge: {reading}\n")
        os.replace(fresh, self.gauge)

    def appraise(self) -> dict:
        """The separate appraiser on the achievement, run as its own process (as greg.body.Body.appraise runs it)."""
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
        out = subprocess.run([sys.executable, "-m", "greg.appraisal"], input=json.dumps(request), capture_output=True,
                             text=True, timeout=120, cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)})
        if out.returncode:
            raise ScenarioBroken("the separate appraiser exited " + str(out.returncode) + ": " + out.stderr[-800:])
        return json.loads(out.stdout)

    # -- the story ---------------------------------------------------------------------------------------------
    def run(self) -> None:
        for d in (self.data, self.ctrl, self.inject):
            d.mkdir()
        (self.inject / "sitecustomize.py").write_text(INSTRUMENTATION)
        (self.data / "note.txt").write_text(NOTE)
        self.set_gauge("green")

        # 1. the entry point, each a CLI process; effect A approved and run
        self.cli("init", "--read-root", str(self.data))
        self.cli("founder", "enroll", "--pubkey",
                 self.cli("founder", "keygen", "--key", str(self.key), "--no-passphrase").strip())
        self.spec = mission_spec(self.home, self.data)
        spec_file = self.tmp / "mission.json"
        spec_file.write_text(json.dumps(self.spec))
        self.founder("mission", "submit", str(spec_file))
        self.start()
        ask_a = self.wait(lambda: self.asks("APPROVAL", "a"), "the approval ask for A")[0]
        self.founder("decide", ask_a["request_id"], "approve", "--reason", "retain the note")
        self.wait(lambda: [a for a in self.actions("a") if a["status"] == "DONE"], "A done")
        ask_b = self.wait(lambda: self.asks("APPROVAL", "b"), "the approval ask for B")[0]
        self.keep("a_done")

        # 2. the gauge becomes unreadable; the founder approves B; the body is killed inside B's dispatch
        self.set_gauge("unreadable")
        (self.ctrl / "hang").touch()
        self.founder("decide", ask_b["request_id"], "approve", "--reason", "restore the working copy")

        def in_flight():
            f = self.facts()
            claimed = [c for c in f["claims"] if c["action_id"] == "b"]
            return f if [c for c in f["calls"] if c.startswith("artifact.materialize ")] and claimed else None
        self.wait(in_flight, "B's dispatch in flight (the adapter called, the Gate's claim on the ledger)")
        self.keep("in_flight")
        self.body.send_signal(signal.SIGKILL)
        self.at["in_flight"]["killed_returncode"] = self.body.wait(timeout=30)
        (self.ctrl / "hang").unlink()
        self.start()
        ask_r = self.wait(lambda: self.asks("RECONCILIATION", "b"), "the reconciliation ask")[0]
        self.turns()
        self.keep("uncertain", **self.account())

        # 3. the founder detaches B's tool, then says the interrupted dispatch did not execute
        self.founder("detach", "artifact.materialize")
        self.wait(lambda: [s for s in self.events("capability.state")
                           if s["capability_id"] == "artifact.materialize" and s["state"] == "DETACHED"], "the detach")
        self.founder("decide", ask_r["request_id"], "reconcile_not_executed", "--reason",
                     "the working copy does not exist")

        # 4. GREG runs the alternative; with C unreadable it closes nothing and asks about the sensor
        self.wait(lambda: [a for a in self.actions("b2") if a["status"] == "DONE"], "the alternative B2 done")
        self.wait(lambda: self.asks("SENSOR_FAILURE"), "the ask about the unreadable gauge")
        self.turns()
        self.keep("alternative", **self.account())

        # 5. the gauge reads green; the mission closes and the body's separate appraiser judges it
        self.set_gauge("green")
        self.wait(lambda: self.events("mission.appraised", mission=True), "the achievement's appraisal")
        self.turns()
        account = self.account()
        self.keep("closed", **account, stopped_returncode=self.stop())

        # 6. the readers and the separate appraiser on the ledger at rest
        end = self.keep("end", **account, routing=self.read("routing"), vepmc=self.read("vepmc"))
        end["reappraised"] = {"achievement": self.appraise()}
        self.copy.write_text("tampered: not what the receipt recorded\n")
        end["reappraised"]["achievement_tampered"] = self.appraise()
        self.copy.write_text(NOTE)
        end["reappraised"]["achievement_restored"] = self.appraise()
        after = self.facts()
        end["chain_after_readers"], end["head_after_readers"] = after["chain"], after["head"]
        end["elapsed"] = round(time.monotonic() - self.started, 1)


@pytest.fixture(scope="module")
def story(tmp_path_factory) -> Story:
    s = Story(tmp_path_factory.mktemp("alternative"))
    try:
        s.run()
    except ScenarioBroken:
        raise
    except BaseException as exc:            # an assertion inside a helper, a failed CLI call, a missing record
        raise ScenarioBroken(f"{type(exc).__name__}: {exc}\nreached: {list(s.at)}\nbody log tail:\n"
                             + (s.log.read_text()[-3000:] if s.log.exists() else "")) from exc
    finally:
        s.reap()
        if EVIDENCE:
            out = Path(EVIDENCE)
            out.mkdir(parents=True, exist_ok=True)
            (out / "story.json").write_text(json.dumps(s.at, indent=1, default=str))
            for name in ("ledger.jsonl", "body.json"):
                if (s.home / name).exists():
                    (out / name).write_bytes((s.home / name).read_bytes())
            if s.log.exists():
                (out / "body.log").write_text(s.log.read_text())
    return s


def by_action(facts: dict, action: str) -> list[dict]:
    return [a for a in facts["actions"] if a["action_id"] == action]


def reading(facts: dict, check: str = "c") -> list[dict]:
    return [o for o in facts["observed"] if o["check_id"] == check]


def calls(facts: dict, capability: str) -> list[list[str]]:
    return [line.split() for line in facts["calls"] if line.startswith(capability + " ")]


def mine(asks: list[dict]) -> list[dict]:
    return [r for r in asks if r.get("mission_id") == MID]


def test_1_effect_a_ran_once_and_stands(story):
    done, end = story.at["a_done"], story.at["end"]
    [a] = by_action(done, "a")
    assert a["status"] == "DONE" and a["cost_usd"] == COST_A
    for at in (story.at["uncertain"], story.at["alternative"], end):
        assert by_action(at, "a") == by_action(done, "a")
        assert len(calls(at, "artifact.store")) == 1
        [claim] = [c for c in at["claims"] if c["action_id"] == "a"]
        assert len([r for r in at["receipts"].values() if r["grant_id"] == claim["grant_id"]]) == 1
    assert [o["passed"] for o in reading(end, "a")][-1] is True


def test_2_the_interrupted_dispatch_is_uncertain_then_settled_by_the_founder(story):
    flight, unc, end = story.at["in_flight"], story.at["uncertain"], story.at["end"]
    assert flight["killed_returncode"] == -signal.SIGKILL
    [claim] = [c for c in flight["claims"] if c["action_id"] == "b"]
    assert [r for r in flight["receipts"].values() if r["grant_id"] == claim["grant_id"]] == []
    assert len(story.pids) == 2 and unc["booted"][-1]["pid"] == story.pids[1] != story.pids[0]
    [b] = by_action(unc, "b")
    assert (b["status"], b["attempt"], b["receipt"], b["grant_id"]) == ("UNCERTAIN", 0, None, claim["grant_id"])
    assert b["reserved_usd"] == COST_B and unc["state"]["reserved_usd"] == COST_B
    [ask] = [r for r in unc["requested"] if r["kind"] == "RECONCILIATION"]
    assert ask["authority_requested"]["grant_id"] == claim["grant_id"]
    assert [(x["status"], x["cost_usd"]) for x in by_action(end, "b")] == [("UNCERTAIN", 0.0),
                                                                           ("RECONCILED_NOT_EXECUTED", 0.0)]


def test_3_the_detached_tool_never_runs_again_and_its_attach_is_never_asked_for(story):
    end = story.at["end"]
    assert [(s["capability_id"], s["state"]) for s in end["capability_state"]] == [("artifact.materialize", "DETACHED")]
    # one call reached the preferred tool's adapter: the dispatch the first process was killed inside, before the real
    # adapter ran. After the detach none did, and the engine never handed the detached tool to the office
    [killed] = calls(end, "artifact.materialize")
    assert int(killed[1]) == story.pids[0]
    assert len([c for c in end["claims"] if c["action_id"] == "b"]) == 1
    assert [e for e in end["authority"] if e["type"] == "greg.authority.refused_unattached"] == []
    assert [r for r in end["requested"] if r["kind"] == "CAPABILITY_ATTACH"] == []
    assert not [c for c in end["accepted"] if c["kind"] == "CAPABILITY_ATTACH"]
    # the working copy's one writer is the alternative's receipt
    [b2] = by_action(end, "b2")
    assert end["receipts"][b2["receipt"]]["result"]["output"]["sha256"] == hashlib.sha256(NOTE.encode()).hexdigest()


def test_4_greg_finishes_through_the_alternative_under_its_own_scope(story):
    alt, end = story.at["alternative"], story.at["end"]
    [b2] = by_action(alt, "b2")
    assert (b2["status"], b2["capability"], b2["cost_usd"], b2["attempt"]) == ("DONE", "fs.write", COST_ALT, 0)
    # it ran after the founder's reconciliation, and was never asked for: the signed cone admits it
    settled = [x for x in by_action(alt, "b") if x["status"] == "RECONCILED_NOT_EXECUTED"][0]
    assert settled["_seq"] < b2["_seq"]
    assert [r for r in alt["requested"] if r.get("action_id") == "b2"] == []
    [grant] = [e for e in alt["authority"] if e["type"] == "greg.authority.grant_issued"
               and e["proposal_id"] in {i["proposal_id"] for i in alt["intents"] if i["action_id"] == "b2"}]
    assert grant["founder_approved_scope"] is False and "pre_approved_in_signed_mission" not in grant
    # the record says why: B ranked above B2 and was passed over because its tool is detached
    [passed] = b2["routing"]["passed_over"]
    assert (b2["routing"]["chosen"], passed["action_id"], passed["capability"]) == ("b2", "b", "artifact.materialize")
    assert "the founder detached artifact.materialize" in passed["why"]
    assert passed["expected_value"] > b2["routing"]["expected_value"]


def test_5_the_unreadable_reading_stays_unmeasured_and_closes_nothing(story):
    alt, end = story.at["alternative"], story.at["end"]
    unreadable = [o for o in reading(alt) if not o["passed"]]
    assert unreadable and all(o["detail"].startswith("sensor REFUSED") and not measured(o) for o in unreadable)
    [b2] = by_action(alt, "b2")
    assert [o for o in unreadable if o["_seq"] > b2["_seq"]]
    assert alt["achieved"] == [] and alt["unmet"] == [] and alt["appraised"] == []
    [sensor] = [r for r in alt["requested"] if r["kind"] == "SENSOR_FAILURE"]
    assert sensor["authority_requested"] == {"checks": ["c"]}
    assert alt["state"]["blocker"]["sensing"] is True
    [row] = alt["status"]["missions"]
    assert row["achieved"] is False
    # green again: the mission closes on a reading taken after every unreadable one, never on an earlier pass
    [achieved] = end["achieved"]
    last_unreadable = max(o["_seq"] for o in reading(end) if not o["passed"])
    cited = [o for o in reading(end) if o["receipt"] in achieved["evidence"]]
    assert len(cited) == 1 and cited[0]["passed"] and last_unreadable < cited[0]["_seq"] < achieved["_seq"]
    [withdrawn] = [w for w in end["withdrawn"] if w["request_id"] == sensor["request_id"]]
    assert "read again" in withdrawn["why"]


def test_6_the_separate_appraiser_verifies_the_achievement_it_judged(story):
    end = story.at["end"]
    [achieved], [appraised] = end["achieved"], end["appraised"]
    assert appraised["verdict"] == "VERIFIED" and appraised["findings"] == []
    assert "closure_event" not in appraised
    assert achieved["_seq"] <= appraised["_head_seq"] < appraised["_seq"]
    assert all(appraised["checks"][k] for k in (
        "closure_evidence_bound", "checks_rederived_from_receipts", "world_reobserved", "exactly_once",
        "approval_boundaries_honored", "founder_signature_verified", "preconditions_honored"))
    again = end["reappraised"]
    assert again["achievement"]["verdict"] == "VERIFIED"
    tampered = again["achievement_tampered"]
    assert tampered["verdict"] == "REFUTED" and any(f.startswith("b: world no longer matches")
                                                    for f in tampered["findings"])
    assert again["achievement_restored"]["verdict"] == "VERIFIED"
    assert end["head_after_readers"] == end["head"] and end["chain"] and end["chain_after_readers"]
    [row] = [m for m in end["vepmc"]["missions"] if m["mission_id"] == MID]
    assert row["closure_event_id"] == achieved["_id"] and row["appraised_verified"] is True


def test_7_costs_are_the_sum_of_what_ran(story):
    end = story.at["end"]
    booked = [(a["action_id"], a["status"], a["cost_usd"]) for a in end["actions"] if a["cost_usd"]]
    assert booked == [("a", "DONE", COST_A), ("b2", "DONE", COST_ALT)]
    assert end["state"]["spent_usd"] == pytest.approx(COST_A + COST_ALT) and end["state"]["reserved_usd"] == 0.0
    assert end["trace"]["metrics"]["cost_usd"] == pytest.approx(COST_A + COST_ALT)
    [row] = end["status"]["missions"]
    assert row["achieved"] is True and row["active_constraint"] is None
    assert mine(end["decisions"]) == [] and end["blockers"] == []


def test_8_the_founder_was_asked_three_decisions_and_one_question_about_a_sensor(story):
    end = story.at["end"]
    asked = [(r["kind"], r.get("action_id")) for r in end["requested"]]
    assert asked == [("APPROVAL", "a"), ("APPROVAL", "b"), ("RECONCILIATION", "b"), ("SENSOR_FAILURE", None)]
    commands = [c["kind"] for c in end["accepted"]]
    assert commands == ["MISSION", "DECISION", "DECISION", "CAPABILITY_DETACH", "DECISION"]
    # against #306: no CAPABILITY_ATTACH ask and no re-attach. Its second APPROVAL of B (the revoked phone) and its
    # NO_STRATEGY (the gauge read red) belong to that story's other events, not to the alternative
    assert ("CAPABILITY_ATTACH", None) in COMPOSED_ASKS and ("CAPABILITY_ATTACH", None) not in asked
    assert end["elapsed"] < 600
