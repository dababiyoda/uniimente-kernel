"""Mission H recovery scenarios, read from tests/recovery/recovery-tests.yaml and run against real Body processes.

Acceptance gap H.G10: the YAML declared four recovery scenarios and no test consumed it. This harness loads it and
runs each scenario it can exercise against a real Body process on its own ledger.jsonl, driven by commands signed
with per-test Ed25519 keys (not Alfonso's). A scenario it cannot exercise, and any scenario the YAML adds before a
runner exists for it, is reported as skipped with the reason: NOT RUN, never passed.

* mid_execution_kill_resume: one SIGKILL per fresh body, across one mission with a read step (fs.read through the
  Gate, the write's precondition), a write step (fs.write), an approval step (the delivery is outside the signed
  cone) and a delivery step (brief.engineering writes one brief into the delivery root). Three families of kill:
  - seeded: TRIALS kills at offsets random.Random(SEED) draws up to the record that closes the mission in an
    uninterrupted calibration run. A separate trigger process SIGKILLs the body when its ledger reaches the offset.
  - boundary: one kill at every record from the write's and the delivery's Gate claim through its receipt
    (located in the calibration ledger). The body may append a record before such a kill lands, so these can miss
    the dispatch window; where each kill landed is read from the ledger and reported.
  - window: four kills that cannot miss it. The body is a Body.run driver (the loop `greg run` runs) in which the
    real fs.write or brief.engineering adapter is held inside its Gate dispatch, after the claim and before or
    after its effect; the harness SIGKILLs it there.
  The harness restarts the killed body with `greg run`, as a supervisor would, and plays a truthful founder: it
  approves the delivery's ask and answers a reconciliation ask from what the world shows. Asserted on every trial:
  no duplicate receipt or dispatch claim per grant or proposal; no consequential dispatch claimed again unless the
  founder answered reconcile_not_executed for the claim before it (no blind retry under a fresh grant); every
  UNCERTAIN action names a dispatch the Gate claimed and has exactly one reconciliation request for it; at most one
  brief, one completed note, one completed delivery, one approval ask and one closure; and, once the mission
  closed, every consequential claim settled by its receipt or by a founder answer naming its grant. Asserted over
  the families: the YAML's declared success rate for each; and coverage, not luck: in each consequential
  capability at least one kill landed between a dispatch claim and its receipt, and both reconcile_executed and
  reconcile_not_executed were answered there.
* corrupted_ledger_head: a head record that fails verification, and a ledger rolled back behind the head the
  previous process published (after a clean stop, and after a SIGKILL with the heartbeat still RUNNING), are
  refused before anything is written to them, on every restart.
* old_token_reactivation: a command a device signed before its delegation was revoked never verifies again, not
  after a SIGKILL restart and not after the founder re-delegates the same key; nor does one it signed after a
  re-delegation envelope the founder prepared in advance but before the revocation, or one signed while the key
  stood revoked. A new short-lived device identity is honoured.
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
from greg.founder import generate_founder_key, instant, key_id, load_founder_key, sign_command, stamp
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
# A trial that has not closed by then counts as a failed recovery. A liveness bound, not a speed requirement: an
# honest trial closes in a few seconds, and nothing a trial asserts waits on a shorter timeout.
TRIAL_SECONDS = 180
MID = "m:recovery-chain"
NOTE = "read source alpha; noted"
# The mission's consequential (not read-only) capabilities and the one action each serves.
CONSEQUENTIAL = {"fs.write": "note", "brief.engineering": "deliver"}
# Where a window trial holds the adapter inside its dispatch, and what a truthful founder then answers.
WINDOW = {"before": "reconcile_not_executed", "after": "reconcile_executed"}

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
        # The Gate's witness precedes its dispatch claim and names the claim's grant and capability.
        out["capability_of_grant"] = {r.payload["grant_id"]: r.payload["capability"]
                                      for r in ledger.by_type("witness")}
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


def landed(at_kill: dict) -> tuple[str, str | None]:
    """Where the kill landed, read from the ledger the killed process left, and the grant of the dispatch it
    landed inside (None when it landed between dispatches)."""
    receipted = {r["grant_id"] for r in at_kill["receipt"]}
    open_claims = [d for d in at_kill["dispatch"] if d["grant_id"] not in receipted]
    if open_claims:
        grant = open_claims[-1]["grant_id"]
        capability = at_kill["capability_of_grant"].get(grant)
        return ("inside " + (capability if capability in CONSEQUENTIAL else "a sensor read") + " dispatch", grant)
    return "after " + str(at_kill["last"]), None


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

# A window trial's body: Body.run, the loop `greg run` runs, with one change. The real adapter of one consequential
# capability is held inside its Gate dispatch (the claim is on the ledger, the receipt is not): before its effect,
# or after it. It reports the grant it holds through an atomically written flag file and blocks until the harness
# SIGKILLs the process there, so the kill cannot miss the window whatever the machine's speed.
WINDOW_DRIVER = '''
import os, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from greg.body import Body
from greg.capabilities import BUILTINS

home, capability, point, reached = Path(sys.argv[2]), sys.argv[3], sys.argv[4], Path(sys.argv[5])
manifest, real = BUILTINS[capability]


def held(params, ctx):
    if point == "after":
        real(params, ctx)                    # the effect happens; the Gate's receipt never will
    partial = reached.with_name(reached.name + ".partial")
    partial.write_text(ctx.grant_id)
    os.replace(partial, reached)
    while True:                              # held inside the dispatch until the harness SIGKILLs this process
        time.sleep(60)


class WindowBody(Body):
    def open(self):
        super().open()
        self.registry.register(manifest, held, state=self.registry.state[capability])   # its manifest and state
        return self


sys.exit(WindowBody(home).run(tick_seconds=float(sys.argv[6])))
'''


def start_window(tmp: Path, home: Path, log: Path, capability: str, point: str, reached: Path) -> subprocess.Popen:
    driver = tmp / "window_driver.py"
    driver.write_text(WINDOW_DRIVER)
    return subprocess.Popen([sys.executable, str(driver), str(ROOT), str(home), capability, point, str(reached), TICK],
                            cwd=ROOT, env=ENV, stdout=log.open("a"), stderr=subprocess.STDOUT)


def run_trial(tmp: Path, offset: int | None = None, window: tuple[str, str] | None = None) -> dict:
    """One fresh body, one mission, at most one SIGKILL then a `greg run` restart. ``offset``: kill once the ledger
    has grown by that many records. ``window``: (capability, point): kill while that capability's real adapter is
    held inside its Gate dispatch, before or after its effect. Neither: the uninterrupted calibration run."""
    tmp.mkdir(parents=True)
    home, key, body_id, data = make_body(tmp)
    spec = chain_mission(home, data)
    note = workspace(home, MID) / "note.txt"
    briefs = home / "deliveries" / "briefs"
    reached = tmp / "window-reached"

    def executed(action_id):
        if action_id == "note":
            return note.exists() and note.read_text() == NOTE
        return briefs.exists() and bool(list(briefs.glob("*.md")))

    drop(home, signed(key, body_id, "MISSION", spec))
    log, answered = tmp / "body.log", set()
    base, began = records(home), time.time()
    body = start_window(tmp, home, log, *window, reached) if window else start(home, log)
    watcher = None if offset is None else subprocess.Popen(
        [sys.executable, "-c", WATCHER, str(home / "ledger.jsonl"), str(body.pid), str(base + offset)])
    out = {"offset": offset, "window": "/".join(window) if window else None, "killed": False, "closed": False}
    try:
        while time.time() < began + TRIAL_SECONDS:
            if not out["killed"] and ((watcher is not None and watcher.poll() is not None)
                                      or (window is not None and reached.exists())):
                if window is not None:
                    body.send_signal(signal.SIGKILL)    # it is blocked inside the dispatch: nothing races this
                else:
                    assert watcher.returncode == 0, "the body exited before the kill offset"
                body.wait(timeout=20)
                assert body.returncode == -signal.SIGKILL
                at_kill = view(home)
                where, grant = landed(at_kill)
                out.update(killed=True, killed_at=records(home) - base, landed=where, landed_grant=grant,
                           held_grant=reached.read_text() if window else None,
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


def dispatches(final: dict) -> dict:
    """The consequential Gate dispatch claims of one trial, per capability in ledger order, each with its receipts
    and the founder's answers to reconciliation requests naming its grant."""
    receipts, answered = {}, {}
    for r in final["receipt"]:
        receipts.setdefault(r["grant_id"], []).append(r)
    answers = {a["request_id"]: a["answer"] for a in final["decision.answered"]}
    for r in final["decision.requested"]:
        if r["kind"] == "RECONCILIATION" and r["request_id"] in answers:
            answered.setdefault(r["authority_requested"].get("grant_id"), []).append(answers[r["request_id"]])
    out = {capability: [] for capability in CONSEQUENTIAL}
    for claim in final["dispatch"]:
        capability = final["capability_of_grant"].get(claim["grant_id"])
        if capability in out:
            out[capability].append({"grant_id": claim["grant_id"], "proposal_id": claim["proposal_id"],
                                    "receipts": receipts.get(claim["grant_id"], []),
                                    "answers": answered.get(claim["grant_id"], [])})
    return out


def judge(trial: dict) -> dict:
    """Did the killed body resume from its recorded state and complete, with every invariant intact?"""
    final = trial["final"]
    receipts = [r["grant_id"] for r in final["receipt"]]
    claims = [d["grant_id"] for d in final["dispatch"]]
    proposals = [d["proposal_id"] for d in final["dispatch"]]
    duplicates = ((len(receipts) - len(set(receipts))) + (len(claims) - len(set(claims)))
                  + (len(proposals) - len(set(proposals))))
    claimed = dispatches(final)
    # A consequential dispatch is claimed again only after the founder said the claim before it did not execute
    # (or its receipt says the capability refused): anything else is a blind retry under a fresh grant.
    blind = [later["grant_id"] for chain in claimed.values() for earlier, later in zip(chain, chain[1:])
             if not (earlier["answers"] == ["reconcile_not_executed"] and not earlier["receipts"])
             and not (earlier["receipts"] and all(r["result"].get("result_class") != "positive"
                                                  for r in earlier["receipts"]))]
    unsettled = [c["grant_id"] for chain in claimed.values() for c in chain if not c["receipts"] and not c["answers"]]
    uncertain = [a for a in final["mission.action"] if a["status"] == "UNCERTAIN"]
    reconciliations = [r for r in final["decision.requested"] if r["kind"] == "RECONCILIATION"]
    approvals = [r for r in final["decision.requested"] if r["kind"] == "APPROVAL"]
    unreconciled = [a for a in uncertain
                    if len([r for r in reconciliations
                            if r["authority_requested"].get("grant_id") == a.get("grant_id")]) != 1]
    phantom = [a for a in uncertain if a.get("grant_id") not in set(claims)]   # names a dispatch never claimed
    done = [a for a in final["mission.action"] if a["status"] == "DONE"]
    counts = {"briefs": len(trial["briefs"]), "note_done": [a["action_id"] for a in done].count("note"),
              "deliver_done": [a["action_id"] for a in done].count("deliver"), "approval_asks": len(approvals),
              "closures": len(final["mission.achieved"])}
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
    reconciled = {capability: sorted(a for c in chain for a in c["answers"]) for capability, chain in claimed.items()}
    window_hit = None
    if trial.get("window"):
        # The kill landed inside exactly the dispatch the driver held, and the truthful answer followed the world.
        capability, point = trial["window"].split("/")
        window_hit = (trial.get("landed") == f"inside {capability} dispatch"
                      and trial.get("landed_grant") == trial.get("held_grant")
                      and reconciled[capability] == [WINDOW[point]])
    completed = (trial["killed"] and trial["closed"] and not trial.get("closed_before_kill")
                 and bool(final["body.recovered"]) and counts["closures"] == 1
                 and trial["note"] == NOTE and counts["briefs"] == 1 and final["chain"]
                 and counts["note_done"] == 1 and counts["deliver_done"] == 1
                 and duplicates == 0 and not blind and not unsettled and not unreconciled and not phantom
                 and counts["approval_asks"] == 1                                 # the decision is remembered
                 and window_hit is not False
                 and (appraised == "VERIFIED" or appraised.startswith("WITHHELD")))
    return {"completed": completed, "offset": trial["offset"], "window": trial.get("window"),
            "killed_at": trial.get("killed_at"), "landed": trial.get("landed"), "window_hit": window_hit,
            "seconds": trial["seconds"], "closed": trial["closed"], "duplicate_receipts_or_claims": duplicates,
            "blind_retries": blind, "unsettled_claims": unsettled, "uncertain": len(uncertain),
            "uncertain_without_reconciliation": len(unreconciled), "uncertain_naming_no_claim": len(phantom),
            **counts, "reconciled": reconciled,
            "answers": sorted(a["answer"] for a in final["decision.answered"]), "appraisal": appraised,
            **({"exited_unasked": trial.get("exited_unasked"), "log_tail": trial.get("log_tail"),
                "diag": trial.get("diag")}
               if not completed else {})}


def kill_resume(scenario: dict, tmp_path: Path) -> None:
    target = declared_rate(scenario)
    calibration = run_trial(tmp_path / "calibration")
    clean = calibration["final"]
    assert calibration["closed"] and clean["mission.appraised"][-1]["verdict"] == "VERIFIED", clean["mission.appraised"]
    assert calibration["note"] == NOTE and len(calibration["briefs"]) == 1
    closing = calibration["closing"]             # the record that closes the mission, counted from the start
    spans = calibration["dispatch_spans"]
    assert set(spans) == set(CONSEQUENTIAL), spans
    rng = random.Random(SEED)
    seeded = [rng.randint(1, closing) for _ in range(TRIALS)]
    # Uniform offsets rarely fall on the few records inside a consequential dispatch, so every record from the
    # write's and the delivery's Gate claim through its receipt is also killed once: these offsets are located in
    # the calibration ledger, not drawn. Either kind can miss the window (the body may append before the kill lands),
    # so the window family holds each consequential adapter inside its dispatch, before and after its effect.
    boundary = [o for first, last in spans.values() for o in range(first, last + 1)]
    windows = [(capability, point) for capability in CONSEQUENTIAL for point in WINDOW]
    plan = ([("seeded", {"offset": o}) for o in seeded] + [("boundary", {"offset": o}) for o in boundary]
            + [("window", {"window": w}) for w in windows])
    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        trials = list(pool.map(lambda i: run_trial(tmp_path / f"trial-{i:02d}", **plan[i][1]), range(len(plan))))
    verdicts = [{"family": family, **judge(t)} for (family, _), t in zip(plan, trials)]
    families = ("seeded", "boundary", "window")
    rates = {family: sum(v["completed"] for v in verdicts if v["family"] == family)
             / sum(1 for v in verdicts if v["family"] == family) for family in families}
    coverage = {capability: {"kills_inside": sum(1 for v in verdicts if v["landed"] == f"inside {capability} dispatch"),
                             "answers": sorted({a for v in verdicts if v["landed"] == f"inside {capability} dispatch"
                                                for a in v["reconciled"][capability]})}
                for capability in CONSEQUENTIAL}
    report = {"scenario": "mid_execution_kill_resume", "seed": SEED, "seeded_trials": TRIALS,
              "boundary_trials": len(boundary), "window_trials": len(windows),
              "calibration_records": calibration["records"], "calibration_closing_record": closing,
              "calibration_dispatch_spans": spans, "declared_success_rate": target, "success_rate": rates,
              "coverage": coverage, "verdicts": verdicts}
    (tmp_path / "report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
    assert all(t["killed"] and not t.get("closed_before_kill") for t in trials), \
        "every trial is killed before its mission closed: an uninterrupted run is not a recovery"
    # Safety, on every trial whatever its outcome: never two effects, never a blind retry, never an unknown
    # completion left without its one reconciliation, never a reconciliation of a dispatch that was not claimed.
    for v in verdicts:
        assert v["duplicate_receipts_or_claims"] == 0 and not v["blind_retries"], v
        assert v["uncertain_without_reconciliation"] == 0 and v["uncertain_naming_no_claim"] == 0, v
        assert max(v["briefs"], v["note_done"], v["deliver_done"], v["approval_asks"], v["closures"]) <= 1, v
        assert not (v["closed"] and v["unsettled_claims"]), v    # a closed mission left no claim unsettled
    assert all(rates[family] >= target for family in families), report
    # Coverage of the dispatch window is asserted, not left to where the kills happened to land.
    for capability, seen in coverage.items():
        assert seen["kills_inside"] >= 1 and seen["answers"] == sorted(WINDOW.values()), (capability, coverage)


# -- corrupted_ledger_head --------------------------------------------------------------------------------------------

DAMAGES = ("head_fails_verification", "head_rolled_back", "head_rolled_back_after_sigkill")


def corrupted_head(scenario: dict, tmp_path: Path) -> None:
    for damage in DAMAGES:
        sealed_head_is_refused(tmp_path / damage, damage)


def sealed_head_is_refused(tmp: Path, damage: str) -> None:
    """The head a body last published is the one its ledger must still verify to; a ledger that does not is refused.

    A clean stop publishes the sealed head (heartbeat STOPPED); a SIGKILL leaves the head of the last turn published
    (heartbeat RUNNING), and the refusal must not depend on which."""
    tmp.mkdir()
    home, key, body_id, _ = make_body(tmp)
    note, log = workspace(home, "m:sealed") / "n.txt", tmp / "body.log"
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:sealed", checks=[note_check("n", note, "sealed")], strategies=[write_strategy("w", "n.txt", "sealed", ["n"])],
        capabilities=["fs.read", "fs.write"])))
    killed = damage == "head_rolled_back_after_sigkill"
    body = start(home, log)
    try:
        wait_for(lambda: events(home, "mission.appraised"), what="the mission's appraisal")
        if killed:                                         # a turn has published its head: heartbeat RUNNING
            wait_for(lambda: json.loads((home / "heartbeat.json").read_text())["state"] == "RUNNING",
                     what="a RUNNING heartbeat")
    finally:
        stop(body, signal.SIGKILL if killed else signal.SIGTERM)   # SIGTERM: a clean stop, heartbeat STOPPED
    heartbeat = (home / "heartbeat.json").read_text()
    published = json.loads(heartbeat)
    lines = (home / "ledger.jsonl").read_text().splitlines(keepends=True)
    heads = [json.loads(line)["hash"] if line.endswith("\n") else None for line in lines]
    if killed:
        # The heartbeat still says RUNNING, and the head it names is on the ledger (perhaps with records after it).
        assert published["state"] == "RUNNING" and published["ledger_head"] in heads, published
        lines = lines[:heads.index(published["ledger_head"])]   # a rollback behind the published head
        reason = "is not in this ledger"
    else:
        assert published["state"] == "STOPPED" and heads[-1] == published["ledger_head"]
        if damage == "head_fails_verification":
            record = json.loads(lines[-1])
            record["payload"]["tampered"] = True           # the sealed head's bytes no longer match its hash
            lines[-1] = json.dumps(record) + "\n"
            reason = "failed verification on load"
        else:
            lines = lines[:-3]                             # a whole-record rollback: the prefix still verifies
            reason = "is not in this ledger"
    damaged = "".join(lines)
    (home / "ledger.jsonl").write_text(damaged)
    waiting = drop(home, signed(key, body_id, "MISSION", mission(
        "m:after-damage", checks=[note_check("n", workspace(home, "m:after-damage") / "n.txt", "x")],
        strategies=[write_strategy("w", "n.txt", "x", ["n"])], capabilities=["fs.read", "fs.write"])))
    for _ in range(2):                                     # a supervisor restarts it; each start is refused alike
        refused = subprocess.run([sys.executable, "-m", "greg", "--home", str(home), "run", "--tick-seconds", "0.05",
                                  "--max-ticks", "3"], cwd=ROOT, env=ENV, capture_output=True, text=True, timeout=60)
        assert refused.returncode != 0 and reason in refused.stderr, \
            (damage, refused.returncode, refused.stderr[-1500:])
        assert (home / "ledger.jsonl").read_text() == damaged, "nothing written, nothing repaired away"
        assert (home / "heartbeat.json").read_text() == heartbeat, "no new process reported itself running"
        assert waiting.exists(), "no command was read: normal operation did not resume"
    assert not (workspace(home, "m:after-damage") / "n.txt").exists()


# -- old_token_reactivation -------------------------------------------------------------------------------------------

def old_tokens(scenario: dict, tmp_path: Path) -> None:
    """A compromised device's old signed commands never verify again; a new short-lived identity does.

    Three old tokens, each an approval of the same request by the phone's key, all presented after the founder
    re-delegates that key: one signed under the delegation (before everything), one signed under it after the
    founder had already signed the re-delegation envelope (prepared in advance), and one signed while the key stood
    revoked. The re-delegation verifies only what the key signs after this body recorded it (greg.body
    device_delegations): anchoring it at the revocation would reactivate the third, at the envelope's issued_at the
    second and third. The instants the test relies on are asserted, all on this machine's one clock."""
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

    def after(*stamps):
        """Return once this machine's clock has passed every instant given, so the next one signed is later."""
        wait_for(lambda: datetime.now(timezone.utc) > max(instant(t) for t in stamps), what="the clock to advance")

    def present(token, name):
        """Drop an old token under ``name`` and wait until the body has read it; it must have refused it."""
        drop(home, token, name)
        wait_for(lambda: not (home / "inbox" / name).exists(), what=f"the body to read {name}")
        assert (home / "inbox" / "rejected" / name).exists() and not (home / "inbox" / "processed" / name).exists(), \
            f"{name}: a command signed before the key's current delegation was accepted"

    body = start(home, log)
    try:
        wait_for(lambda: events(home, "device.enrolled") and ask("m:old-token") and ask("m:redelegated"),
                 what="the delegation and both asks")
        old = answer(phone, "m:old-token")                 # signed while the phone was delegated, never used
        after(old["issued_at"])
        redelegation = sign_command(key, "DEVICE_ENROLL", grant, body_id=body_id)   # prepared in advance
        after(redelegation["issued_at"])
        presigned = answer(phone, "m:old-token")           # still under the delegation, after that envelope
        after(presigned["issued_at"])
        drop(home, sign_command(key, "DEVICE_REVOKE", {"device_key_id": key_id(phone_public)}, body_id=body_id),
             "c-revoke.json")
        [revoked] = wait_for(lambda: events(home, "device.revoked"), what="the revocation")
        after(revoked["at"])
        between = answer(phone, "m:old-token")             # signed while the key stood revoked
        after(between["issued_at"])
    finally:
        stop(body, signal.SIGKILL)                         # shut down hard with the old tokens outstanding

    body = start(home, log)                                # recovery runs
    try:
        wait_for(lambda: events(home, "body.recovered"), what="the restart")
        present(old, "old-token-1.json")
        # The founder re-delegates the same phone key (revoke, then re-delegate, is how a delegation changes).
        drop(home, redelegation, "d-redelegate.json")
        enrolled = wait_for(lambda: events(home, "device.enrolled")[1:], what="the re-delegation")[0]
        on_one_clock = [instant(t) for t in (old["issued_at"], redelegation["issued_at"], presigned["issued_at"],
                                             revoked["at"], between["issued_at"], enrolled["at"])]
        assert on_one_clock == sorted(on_one_clock) and len(set(on_one_clock)) == len(on_one_clock), on_one_clock
        present(old, "old-token-2.json")                   # the old token, presented under the new delegation
        present(presigned, "old-token-presigned.json")
        present(between, "old-token-between.json")
        drop(home, answer(phone, "m:redelegated"), "e-fresh.json")   # what the phone signs now is honoured
        wait_for(lambda: notes["m:redelegated"].exists(), what="the re-delegated phone's fresh answer")
        assert not notes["m:old-token"].exists()
        # A new short-lived identity, issued after the recovery, answers the request the old tokens could not.
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
    assert [r["file"] for r in rejected] == ["old-token-1.json", "old-token-2.json", "old-token-presigned.json",
                                             "old-token-between.json"], rejected
    assert all(r["instruction_status"] == "data_only" for r in rejected)
    assert "not enrolled or revoked" in rejected[0]["reason"]
    assert all("before this device key's current delegation" in r["reason"] for r in rejected[1:]), \
        [r["reason"] for r in rejected]
    answered = {a["request_id"]: a for a in events(home, "decision.answered")}
    signers = {c["digest"]: c["signer"] for c in events(home, "command.accepted") if c["kind"] == "DECISION"}
    assert sorted(signers.values()) == ["device:phone", "device:phone-2"]
    assert signers[answered[ask("m:old-token")[0]["request_id"]]["command_digest"]] == "device:phone-2"
    assert signers[answered[ask("m:redelegated")[0]["request_id"]]["command_digest"]] == "device:phone"
    assert all(notes[m].read_text() == "approved" for m in notes)


# -- the harness ------------------------------------------------------------------------------------------------------
# One test per scenario this harness can exercise, each calling its runner directly (so the static reader in
# acceptance/ sees which process each starts); every other scenario the YAML declares is reported NOT RUN.

RUNNERS = {"mid_execution_kill_resume": kill_resume, "corrupted_ledger_head": corrupted_head,
           "old_token_reactivation": old_tokens}


def test_the_harness_reads_the_scenarios_the_yaml_declares():
    """Every runner and every NOT_RUN reason names a scenario the YAML declares (a scenario the YAML adds later is
    reported NOT RUN by test_recovery_scenario_not_run until a runner exists for it), and each runner has its test."""
    assert all({"given", "then"} <= set(s) for s in SCENARIOS.values())
    assert set(RUNNERS) <= set(SCENARIOS) and set(NOT_RUN) <= set(SCENARIOS) and not set(RUNNERS) & set(NOT_RUN)
    assert all(callable(globals().get(f"test_{name}")) for name in RUNNERS)


def test_mid_execution_kill_resume(tmp_path):
    kill_resume(SCENARIOS["mid_execution_kill_resume"], tmp_path)


def test_corrupted_ledger_head(tmp_path):
    corrupted_head(SCENARIOS["corrupted_ledger_head"], tmp_path)


def test_old_token_reactivation(tmp_path):
    old_tokens(SCENARIOS["old_token_reactivation"], tmp_path)


@pytest.mark.parametrize("name", sorted(set(SCENARIOS) - set(RUNNERS)))
def test_recovery_scenario_not_run(name):
    pytest.skip(f"NOT RUN: {name}: {NOT_RUN.get(name, 'no runner in this harness')}")
