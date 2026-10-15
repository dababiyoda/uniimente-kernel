"""Mission H recovery scenarios, read from tests/recovery/recovery-tests.yaml and run against real Body processes.

Acceptance gap H.G10: the YAML declared four recovery scenarios and no test consumed it. This harness loads it and
runs each scenario it can exercise against a real `greg run` process on its own ledger.jsonl, driven by commands
signed with per-test Ed25519 keys (not Alfonso's). A scenario it cannot exercise, and any scenario the YAML adds
before a runner exists for it, is reported as skipped with the reason: NOT RUN, never passed.

* mid_execution_kill_resume: TRIALS seeded SIGKILLs, one per fresh body, each when that body's ledger has grown by
  a seeded number of records, across one mission with a read step (fs.read through the Gate, the write's
  precondition), a write step (fs.write), an approval step (the delivery is outside the signed cone) and a delivery
  step (brief.engineering writes one brief into the delivery root). The offsets are drawn from random.Random(SEED)
  up to the record that closes the mission in an uninterrupted calibration run. A separate trigger process SIGKILLs
  the body when its ledger reaches the offset; the body may append a record in the meantime, so where each kill
  landed is read from the ledger and reported. The harness
  restarts the process itself, as a supervisor would, and plays a truthful founder: it approves the delivery's ask
  and answers a reconciliation ask from what the world shows. Because uniform offsets rarely fall inside a
  consequential dispatch, one more kill is made at every record from the write's and the delivery's Gate claim
  through its receipt (located in the calibration ledger). Asserted: the YAML's declared success rate, 0
  duplicate receipts (or dispatch claims) per grant, and 0 UNCERTAIN actions without exactly one reconciliation
  request for that dispatch.
* corrupted_ledger_head: a head record that fails verification, and a ledger rolled back behind the head the
  previous process published, are both refused before anything is written to them, on every restart.
* old_token_reactivation: a command a device signed before its delegation was revoked never verifies again, not
  after a SIGKILL restart and not after the founder re-delegates the same key; a new short-lived device identity
  is honoured.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import random
import re
import signal
import subprocess
import sys
import time

import pytest
import yaml

from events.spine import EventSpine
from greg.body import observe
from greg.founder import generate_founder_key, key_id, load_founder_key, sign_command, stamp
from greg.journal import Journal
from provenance.ledger import EvidenceLedger
from tests.greg_fixtures import make_body, mission, note_check, signed, workspace, write_strategy

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = yaml.safe_load((ROOT / "tests" / "recovery" / "recovery-tests.yaml").read_text())["tests"]
ENV = {**os.environ, "PYTHONPATH": str(ROOT), "GREG_FOUNDER_PASSPHRASE": ""}
TICK = "0.1"

SEED = 20261015      # the kill offsets are random.Random(SEED) draws
TRIALS = 20          # the number of kills the gap asked for: one per fresh body
PARALLEL = 4         # bodies run at once
TRIAL_SECONDS = 45   # a trial that has not closed by then counts as a failed recovery
MID = "m:recovery-chain"
NOTE = "read source alpha; noted"

NOT_RUN = {
    "black_start_environment": "needs the primary cloud to be unavailable and a separate read-only recovery core "
                               "(read ledger and constitution, assert shutdown, revoke credentials, notify Alfonso; "
                               "workflows/shutdown-recovery.yaml stage 1). No such core exists in this repository and "
                               "a GREG body has no primary cloud, so nothing here can exercise it.",
}


# -- process plumbing -------------------------------------------------------------------------------------------------

def drop(home: Path, envelope: dict, name: str | None = None) -> Path:
    """Put one signed envelope in the inbox atomically, as `greg decide` and the remote channel do: the running
    body may read the inbox at any instant, and a half-written file is rejected as malformed."""
    path = Path(home) / "inbox" / (name or f"{envelope['nonce']}.json")
    partial = path.with_name(path.name + ".partial")
    partial.write_text(json.dumps(envelope))
    os.replace(partial, path)
    return path


def start(home: Path, log: Path) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-m", "greg", "--home", str(home), "run", "--tick-seconds", TICK],
                            cwd=ROOT, env=ENV, stdout=log.open("a"), stderr=subprocess.STDOUT)


def stop(body: subprocess.Popen, sig=signal.SIGTERM) -> None:
    if body.poll() is None:
        body.send_signal(sig)
    try:
        body.wait(timeout=30)
    except subprocess.TimeoutExpired:
        body.kill()
        body.wait(timeout=10)


def records(home: Path) -> int:
    """Complete (newline-terminated) records in the body's ledger: the unit the kill offsets are drawn in."""
    try:
        return (Path(home) / "ledger.jsonl").read_bytes().count(b"\n")
    except FileNotFoundError:
        return 0


def events(home: Path, prefix: str) -> list[dict]:
    with observe(home, actor="spiffe://uniimente.internal/greg/recovery-harness") as journal:
        return [e.payload for e in journal.replay(prefix)]


def view(home: Path) -> dict:
    """Read-only view of the ledger (the body process owns the writer)."""
    config = json.loads((Path(home) / "body.json").read_text())
    ledger = EvidenceLedger(config["constitution_hash"], str(Path(home) / "ledger.jsonl"), read_only=True,
                            tail="ignore")
    try:
        journal = Journal(EventSpine(ledger), actor="spiffe://uniimente.internal/greg/recovery-harness")
        out = {kind: [e.payload for e in journal.replay(kind)]
               for kind in ("mission.action", "mission.dispatching", "decision.requested", "decision.answered",
                            "mission.achieved", "mission.appraised", "body.recovered")}
        out["dispatch"] = [r.payload for r in ledger.by_type("grant_dispatch")]
        out["receipt"] = [r.payload for r in ledger.by_type("receipt")]
        out["chain"] = ledger.verify_chain()[0]
        last = ledger.records[-1]
        out["last"] = last.payload.get("type") or last.record_type
        return out
    finally:
        ledger.close()


def wait_for(predicate, *, timeout=60, what="condition"):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            value = predicate()
        except (FileNotFoundError, json.JSONDecodeError, ValueError, KeyError):
            value = None
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {what}")


# -- mid_execution_kill_resume ----------------------------------------------------------------------------------------

def declared_rate(scenario: dict) -> float:
    found = re.search(r"success rate target at least ([0-9.]+)", scenario["then"])
    assert found, "the YAML declares the success rate the harness must meet"
    return float(found.group(1))


def chain_mission(home: Path, data: Path) -> dict:
    """read (the write's precondition) -> write -> approval -> delivery, all through the Gate, one signed cone."""
    repo = data / "kernel"
    repo.mkdir()
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "init", "-q", "-b", "main"], check=True, capture_output=True)
    (repo / "a").write_text("a")
    subprocess.run([*git, "add", "a"], check=True, capture_output=True)
    subprocess.run([*git, "commit", "-q", "-m", "first"], check=True, capture_output=True)
    (data / "source.txt").write_text("source alpha\n")
    note = workspace(home, MID) / "note.txt"
    checks = [note_check("source-read", data / "source.txt", "source alpha"),
              note_check("noted", note, NOTE),
              {"check_id": "fresh-brief", "description": "an engineering brief is in the delivery root",
               "sensor": {"capability": "brief.freshness", "params": {"kind": "engineering"},
                          "target": "deliver:briefs"},
               "predicate": {"op": "lte", "field": "age_hours", "value": 12}}]
    strategies = [write_strategy("note", "note.txt", NOTE, ["noted"], requires=["source-read"]),
                  {"action_id": "deliver", "capability": "brief.engineering",
                   "params": {"local": [{"name": "kernel", "path": str(repo.resolve())}], "github": [],
                              "stale_days": 14},
                   "target": "deliver:briefs", "advances": ["fresh-brief"], "requires": ["noted"],
                   "rationale": "one founder-visible brief, after the note is written"}]
    # brief.engineering is not in the signed cone: the delivery waits for one exact-scope founder approval.
    return mission(MID, checks=checks, strategies=strategies, capabilities=["fs.read", "fs.write", "brief.freshness"],
                   targets=("fs:*", "workspace:*", "deliver:*"))


def founder_turn(home: Path, key, body_id: str, answered: set, executed) -> None:
    """A truthful founder: approves the delivery's ask; answers a reconciliation from what the world shows.
    An ask about something else (a body-level COMPUTE recommendation on a nearly full disk, say) is left alone."""
    with observe(home, actor="spiffe://uniimente.internal/greg/recovery-founder") as journal:
        closed = {e.payload["request_id"] for e in journal.replay("decision.")
                  if e.type in ("greg.decision.answered", "greg.decision.withdrawn")}
        asks = [e.payload for e in journal.replay("decision.requested")]
    for ask in asks:
        rid = ask["request_id"]
        if rid in closed or rid in answered or ask.get("mission_id") != MID:
            continue
        if ask["kind"] == "APPROVAL":
            answer = "approve"
        elif ask["kind"] == "RECONCILIATION":
            answer = "reconcile_executed" if executed(ask["action_id"]) else "reconcile_not_executed"
        else:
            raise AssertionError(f"unexpected founder ask {ask['kind']}: {ask.get('why_now')}")
        drop(home, signed(key, body_id, "DECISION", {"request_id": rid, "answer": answer,
                                                      "reason": "recovery harness founder"}))
        answered.add(rid)


def landed(at_kill: dict) -> str:
    """Where the kill landed, read from the ledger the killed process left."""
    receipted = {r["grant_id"] for r in at_kill["receipt"]}
    open_claims = [d for d in at_kill["dispatch"] if d["grant_id"] not in receipted]
    intents = {i["proposal_id"]: i["capability"] for i in at_kill["mission.dispatching"]}
    if open_claims:
        return "inside " + intents.get(open_claims[-1].get("proposal_id"), "a sensor read") + " dispatch"
    return "after " + str(at_kill["last"])


# The kill trigger is its own small process, so it polls the ledger every millisecond whatever the harness is doing:
# it SIGKILLs the body as soon as the ledger holds ``target`` complete records (reading only the bytes appended since
# its last read). The body can append one more record in that millisecond; where the kill landed is read afterwards.
WATCHER = """
import os, signal, sys, time
path, pid, target = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
seen = position = 0
while True:
    try:
        with open(path, "rb") as fh:
            fh.seek(position)
            chunk = fh.read()
    except FileNotFoundError:
        chunk = b""
    seen, position = seen + chunk.count(b"\\n"), position + len(chunk)
    if seen >= target:
        os.kill(pid, signal.SIGKILL)
        sys.exit(0)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        sys.exit(3)
    time.sleep(0.001)
"""


def run_trial(tmp: Path, offset: int | None) -> dict:
    """One fresh body, one mission; SIGKILL once its ledger has grown by ``offset`` records, then restart it."""
    tmp.mkdir(parents=True)
    home, key, body_id, data = make_body(tmp)
    spec = chain_mission(home, data)
    note = workspace(home, MID) / "note.txt"
    briefs = home / "deliveries" / "briefs"

    def executed(action_id):
        if action_id == "note":
            return note.exists() and note.read_text() == NOTE
        return briefs.exists() and bool(list(briefs.glob("*.md")))

    drop(home, signed(key, body_id, "MISSION", spec))
    log, answered = tmp / "body.log", set()
    base, began = records(home), time.time()
    body = start(home, log)
    watcher = None if offset is None else subprocess.Popen(
        [sys.executable, "-c", WATCHER, str(home / "ledger.jsonl"), str(body.pid), str(base + offset)])
    out = {"offset": offset, "killed": False, "closed": False}
    try:
        while time.time() < began + TRIAL_SECONDS:
            if watcher is not None and watcher.poll() is not None and not out["killed"]:
                assert watcher.returncode == 0, "the body exited before the kill offset"
                body.wait(timeout=20)
                assert body.returncode == -signal.SIGKILL
                at_kill = view(home)
                out.update(killed=True, killed_at=records(home) - base, landed=landed(at_kill),
                           closed_before_kill=bool(at_kill["mission.appraised"]))
                body = start(home, log)
            founder_turn(home, key, body_id, answered, executed)
            if events(home, "mission.appraised"):
                out["closed"] = True
                break
            time.sleep(0.05)
        out["exited_unasked"] = body.poll()      # a body that died on its own (no supervisor restarts it here)
    finally:
        stop(body)
        if watcher is not None and watcher.poll() is None:
            watcher.kill()
            watcher.wait(timeout=10)
    out.update(final=view(home), note=note.read_text() if note.exists() else None,
               briefs=sorted(p.name for p in briefs.glob("*.md")) if briefs.exists() else [],
               seconds=round(time.time() - began, 1), **positions(home, base))
    if not out["closed"]:                       # what a failed recovery needs to be diagnosed
        out["log_tail"] = log.read_text()[-3000:]
        out["diag"] = {"inbox": sorted(p.name for p in (home / "inbox").glob("*.json")),
                       "rejected": [r["reason"] for r in events(home, "command.rejected")],
                       "open_asks": [r["kind"] for r in events(home, "decision.requested")
                                     if r["request_id"] not in {a["request_id"] for a in
                                                                events(home, "decision.answered")}]}
    return out


def positions(home: Path, base: int) -> dict:
    """Offsets (records since the start, 1-based) of the mission's closure and of each consequential dispatch:
    from its Gate claim through its receipt, for the write and the delivery."""
    rows = [json.loads(line) for line in (home / "ledger.jsonl").read_bytes().splitlines()[base:]]
    closing = next((i + 1 for i, r in enumerate(rows) if r["payload"].get("type") == "greg.mission.achieved"), None)
    intents = {r["payload"]["payload"]["proposal_id"]: r["payload"]["payload"]["capability"] for r in rows
               if r["payload"].get("type") == "greg.mission.dispatching"}
    claims = {r["payload"]["grant_id"]: (intents[r["payload"]["proposal_id"]], i + 1) for i, r in enumerate(rows)
              if r["record_type"] == "grant_dispatch" and r["payload"].get("proposal_id") in intents}
    spans = {claims[r["payload"]["grant_id"]][0]: (claims[r["payload"]["grant_id"]][1], i + 1)
             for i, r in enumerate(rows) if r["record_type"] == "receipt" and r["payload"]["grant_id"] in claims}
    return {"records": len(rows), "closing": closing, "dispatch_spans": spans}


def judge(trial: dict) -> dict:
    """Did the killed body resume from its recorded state and complete, with every invariant intact?"""
    final = trial["final"]
    receipts = [r["grant_id"] for r in final["receipt"]]
    claims = [d["grant_id"] for d in final["dispatch"]]
    duplicates = (len(receipts) - len(set(receipts))) + (len(claims) - len(set(claims)))
    uncertain = [a for a in final["mission.action"] if a["status"] == "UNCERTAIN"]
    reconciliations = [r for r in final["decision.requested"] if r["kind"] == "RECONCILIATION"]
    approvals = [r for r in final["decision.requested"] if r["kind"] == "APPROVAL"]
    unreconciled = [a for a in uncertain
                    if len([r for r in reconciliations
                            if r["authority_requested"].get("grant_id") == a.get("grant_id")]) != 1]
    done = [a for a in final["mission.action"] if a["status"] == "DONE"]
    founder_settled = [a for a in done if a.get("reconciles")]
    appraisal = final["mission.appraised"][-1] if final["mission.appraised"] else {}
    failing = sorted(k for k, v in appraisal.get("checks", {}).items()
                     if v is False and k != "approval_boundary_encountered")
    if appraisal.get("verdict") == "VERIFIED":
        appraised = "VERIFIED"
    elif founder_settled and failing == sorted(["exactly_once"] + (
            ["deliveries_bound_to_evidence"] if any(a["capability"] == "brief.engineering"
                                                    for a in founder_settled) else [])):
        # A dispatch the founder reconciled as executed is settled by a signed answer, not a Gate receipt; the
        # separate appraiser re-derives closures from receipts only and withholds VERIFIED. Nothing else may fail.
        appraised = "WITHHELD: founder-reconciled dispatch has no receipt"
    else:
        appraised = appraisal.get("verdict", "MISSING")
    completed = (trial["killed"] and trial["closed"] and not trial.get("closed_before_kill")
                 and bool(final["body.recovered"]) and len(final["mission.achieved"]) == 1
                 and trial["note"] == NOTE and len(trial["briefs"]) == 1 and final["chain"]
                 and [a["action_id"] for a in done].count("note") == 1
                 and [a["action_id"] for a in done].count("deliver") == 1
                 and duplicates == 0 and not unreconciled and len(approvals) == 1   # the decision is remembered
                 and (appraised == "VERIFIED" or appraised.startswith("WITHHELD")))
    return {"completed": completed, "offset": trial["offset"], "killed_at": trial.get("killed_at"),
            "landed": trial.get("landed"), "seconds": trial["seconds"], "duplicate_receipts_or_claims": duplicates,
            "uncertain": len(uncertain), "uncertain_without_reconciliation": len(unreconciled),
            "approval_asks": len(approvals),
            "answers": sorted(a["answer"] for a in final["decision.answered"]), "appraisal": appraised,
            **({"exited_unasked": trial.get("exited_unasked"), "log_tail": trial.get("log_tail"),
                "diag": trial.get("diag")}
               if not completed else {})}


def kill_resume(scenario: dict, tmp_path: Path) -> None:
    target = declared_rate(scenario)
    calibration = run_trial(tmp_path / "calibration", None)
    clean = calibration["final"]
    assert calibration["closed"] and clean["mission.appraised"][-1]["verdict"] == "VERIFIED", clean["mission.appraised"]
    assert calibration["note"] == NOTE and len(calibration["briefs"]) == 1
    closing = calibration["closing"]             # the record that closes the mission, counted from the start
    spans = calibration["dispatch_spans"]
    assert set(spans) == {"fs.write", "brief.engineering"}, spans
    rng = random.Random(SEED)
    seeded = [rng.randint(1, closing) for _ in range(TRIALS)]
    # Uniform offsets rarely fall on the few records inside a consequential dispatch, so every record from the
    # write's and the delivery's Gate claim through its receipt is also killed once: these offsets are located in
    # the calibration ledger, not drawn.
    boundary = [o for first, last in spans.values() for o in range(first, last + 1)]
    plan = [("seeded", o) for o in seeded] + [("boundary", o) for o in boundary]
    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        trials = list(pool.map(lambda i: run_trial(tmp_path / f"trial-{i:02d}", plan[i][1]), range(len(plan))))
    verdicts = [{"family": family, **judge(t)} for (family, _), t in zip(plan, trials)]
    rates = {family: sum(v["completed"] for v in verdicts if v["family"] == family)
             / sum(1 for v in verdicts if v["family"] == family) for family in ("seeded", "boundary")}
    report = {"scenario": "mid_execution_kill_resume", "seed": SEED, "seeded_trials": TRIALS,
              "boundary_trials": len(boundary), "calibration_records": calibration["records"],
              "calibration_closing_record": closing, "calibration_dispatch_spans": spans,
              "declared_success_rate": target, "success_rate": rates, "verdicts": verdicts}
    (tmp_path / "report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
    assert all(t["killed"] and not t.get("closed_before_kill") for t in trials), \
        "every trial is killed before its mission closed: an uninterrupted run is not a recovery"
    assert rates["seeded"] >= target and rates["boundary"] >= target, report
    assert sum(v["duplicate_receipts_or_claims"] for v in verdicts) == 0, report
    assert sum(v["uncertain_without_reconciliation"] for v in verdicts) == 0, report


# -- corrupted_ledger_head --------------------------------------------------------------------------------------------

def corrupted_head(scenario: dict, tmp_path: Path) -> None:
    for damage in ("head_fails_verification", "head_rolled_back"):
        sealed_head_is_refused(tmp_path / damage, damage)


def sealed_head_is_refused(tmp: Path, damage: str) -> None:
    """A body stopped cleanly publishes its sealed head; a ledger that no longer verifies to it is refused."""
    tmp.mkdir()
    home, key, body_id, _ = make_body(tmp)
    note, log = workspace(home, "m:sealed") / "n.txt", tmp / "body.log"
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:sealed", checks=[note_check("n", note, "sealed")], strategies=[write_strategy("w", "n.txt", "sealed", ["n"])],
        capabilities=["fs.read", "fs.write"])))
    body = start(home, log)
    try:
        wait_for(lambda: events(home, "mission.appraised"), what="the mission's appraisal")
    finally:
        stop(body)                                         # a clean stop: body.stopped, heartbeat STOPPED
    heartbeat = (home / "heartbeat.json").read_text()
    sealed = json.loads(heartbeat)
    lines = (home / "ledger.jsonl").read_text().splitlines(keepends=True)
    assert sealed["state"] == "STOPPED" and json.loads(lines[-1])["hash"] == sealed["ledger_head"]
    if damage == "head_fails_verification":
        record = json.loads(lines[-1])
        record["payload"]["tampered"] = True               # the sealed head's bytes no longer match its hash
        lines[-1] = json.dumps(record) + "\n"
        reason = "failed verification on load"
    else:
        lines = lines[:-3]                                 # a whole-record rollback: the prefix still verifies
        reason = "is not in this ledger"
    damaged = "".join(lines)
    (home / "ledger.jsonl").write_text(damaged)
    waiting = drop(home, signed(key, body_id, "MISSION", mission(
        "m:after-damage", checks=[note_check("n", workspace(home, "m:after-damage") / "n.txt", "x")],
        strategies=[write_strategy("w", "n.txt", "x", ["n"])], capabilities=["fs.read", "fs.write"])))
    for _ in range(2):                                     # a supervisor restarts it; each start is refused alike
        refused = subprocess.run([sys.executable, "-m", "greg", "--home", str(home), "run", "--tick-seconds", "0.05",
                                  "--max-ticks", "3"], cwd=ROOT, env=ENV, capture_output=True, text=True, timeout=60)
        assert refused.returncode != 0 and reason in refused.stderr, (refused.returncode, refused.stderr[-1500:])
        assert (home / "ledger.jsonl").read_text() == damaged, "nothing written, nothing repaired away"
        assert (home / "heartbeat.json").read_text() == heartbeat, "no new process reported itself running"
        assert waiting.exists(), "no command was read: normal operation did not resume"
    assert not (workspace(home, "m:after-damage") / "n.txt").exists()


# -- old_token_reactivation -------------------------------------------------------------------------------------------

def old_tokens(scenario: dict, tmp_path: Path) -> None:
    """A compromised device's old signed command never verifies again; a new short-lived identity does."""
    home, key, body_id, _ = make_body(tmp_path)
    log = tmp_path / "body.log"
    phone_public = generate_founder_key(tmp_path / "phone.pem", None)
    phone = load_founder_key(tmp_path / "phone.pem", None)
    month = stamp(datetime.now(timezone.utc) + timedelta(days=30))
    grant = {"public_key": phone_public, "label": "phone", "kinds": ["DECISION"], "expires_at": month}
    drop(home, sign_command(key, "DEVICE_ENROLL", grant, body_id=body_id), "a-phone.json")
    notes = {}
    for name in ("m:old-token", "m:redelegated"):          # each write is outside its cone: each asks once
        notes[name] = workspace(home, name) / "n.txt"
        drop(home, sign_command(key, "MISSION", mission(name, checks=[note_check("n", notes[name], "approved")],
                                                        strategies=[write_strategy("w", "n.txt", "approved", ["n"])],
                                                        capabilities=["fs.read"], ceiling="read_only"),
                                body_id=body_id), f"b-{name[2:]}.json")

    def ask(mid):
        return [r for r in events(home, "decision.requested") if r["mission_id"] == mid]

    def answer(signer, mid):
        return sign_command(signer, "DECISION", {"request_id": ask(mid)[0]["request_id"], "answer": "approve"},
                            body_id=body_id)

    def refusals():
        return [r for r in events(home, "command.rejected") if r["file"].startswith("old-token")]

    def present(name):
        """Drop the old token under ``name`` and wait until the body has read it; it must have refused it."""
        drop(home, old, name)
        wait_for(lambda: not (home / "inbox" / name).exists(), what=f"the body to read {name}")
        assert (home / "inbox" / "rejected" / name).exists() and not (home / "inbox" / "processed" / name).exists(), \
            f"{name}: a command signed under a revoked delegation was accepted"

    body = start(home, log)
    try:
        wait_for(lambda: events(home, "device.enrolled") and ask("m:old-token") and ask("m:redelegated"),
                 what="the delegation and both asks")
        old = answer(phone, "m:old-token")                 # signed while the phone was delegated, never used
        drop(home, sign_command(key, "DEVICE_REVOKE", {"device_key_id": key_id(phone_public)}, body_id=body_id),
             "c-revoke.json")
        wait_for(lambda: events(home, "device.revoked"), what="the revocation")
    finally:
        stop(body, signal.SIGKILL)                         # shut down hard with the old token outstanding

    body = start(home, log)                                # recovery runs
    try:
        wait_for(lambda: events(home, "body.recovered"), what="the restart")
        present("old-token-1.json")
        # The founder re-delegates the same phone key (revoke, then re-delegate, is how a delegation changes).
        drop(home, sign_command(key, "DEVICE_ENROLL", grant, body_id=body_id), "d-redelegate.json")
        wait_for(lambda: len(events(home, "device.enrolled")) == 2, what="the re-delegation")
        present("old-token-2.json")                        # the old token, presented under the new delegation
        drop(home, answer(phone, "m:redelegated"), "e-fresh.json")   # what the phone signs now is honoured
        wait_for(lambda: notes["m:redelegated"].exists(), what="the re-delegated phone's fresh answer")
        assert not notes["m:old-token"].exists()
        # A new short-lived identity, issued after the recovery, answers the request the old token could not.
        fresh_public = generate_founder_key(tmp_path / "phone-2.pem", None)
        hour = stamp(datetime.now(timezone.utc) + timedelta(hours=1))
        drop(home, sign_command(key, "DEVICE_ENROLL", {"public_key": fresh_public, "label": "phone-2",
                                                       "kinds": ["DECISION"], "expires_at": hour}, body_id=body_id),
             "f-new-identity.json")
        issued = wait_for(lambda: [d for d in events(home, "device.enrolled") if d["label"] == "phone-2"],
                          what="the new identity")
        assert issued[0]["expires_at"] == hour                     # short-lived: one hour, not the phone's month
        drop(home, answer(load_founder_key(tmp_path / "phone-2.pem", None), "m:old-token"), "g-new.json")
        wait_for(lambda: notes["m:old-token"].exists(), what="the new identity's answer")
    finally:
        stop(body)

    rejected = refusals()
    assert [r["instruction_status"] for r in rejected] == ["data_only", "data_only"]
    assert "not enrolled or revoked" in rejected[0]["reason"]
    assert "revoked delegation" in rejected[1]["reason"], rejected[1]["reason"]
    answered = {a["request_id"]: a for a in events(home, "decision.answered")}
    signers = {c["digest"]: c["signer"] for c in events(home, "command.accepted") if c["kind"] == "DECISION"}
    assert sorted(signers.values()) == ["device:phone", "device:phone-2"]
    assert signers[answered[ask("m:old-token")[0]["request_id"]]["command_digest"]] == "device:phone-2"
    assert signers[answered[ask("m:redelegated")[0]["request_id"]]["command_digest"]] == "device:phone"
    assert all(notes[m].read_text() == "approved" for m in notes)


# -- the harness ------------------------------------------------------------------------------------------------------

RUNNERS = {"mid_execution_kill_resume": kill_resume, "corrupted_ledger_head": corrupted_head,
           "old_token_reactivation": old_tokens}


def test_the_harness_reads_the_scenarios_the_yaml_declares():
    """Every runner and every NOT_RUN reason names a scenario the YAML declares (a scenario the YAML adds later is
    reported NOT RUN by test_recovery_scenario until a runner exists for it)."""
    assert all({"given", "then"} <= set(s) for s in SCENARIOS.values())
    assert set(RUNNERS) <= set(SCENARIOS) and set(NOT_RUN) <= set(SCENARIOS) and not set(RUNNERS) & set(NOT_RUN)


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_recovery_scenario(name, tmp_path):
    if name in NOT_RUN:
        pytest.skip(f"NOT RUN: {name}: {NOT_RUN[name]}")
    if name not in RUNNERS:
        pytest.skip(f"NOT RUN: {name}: no runner in this harness")
    RUNNERS[name](SCENARIOS[name], tmp_path)
