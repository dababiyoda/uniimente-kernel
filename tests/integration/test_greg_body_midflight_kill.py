"""Mission H (fault recovery) at the real-process tier: the Body is SIGKILLed mid-effect.

Directive section 33, Mission H: "no unbounded retry loop, no duplicate irreversible consequence, and
truthful handling of unknown completion." Here the Body runs as its own OS process through the canonical
main loop (Body.run, exactly what `greg run` runs) with one extra, non-retry-safe internal_write capability
whose adapter appends to an append-only effect log. The test kills the process with SIGKILL while the
Consequence Gate has claimed the dispatch (grant_dispatch on the ledger) and before any receipt, either
before the effect or after it, then starts the Body again.

Truthful unknown completion: after the restart the dispatch is recorded UNCERTAIN, bound to the claimed
grant, its signed cap is reserved, exactly one RECONCILIATION request names that one dispatch, and nothing is
redispatched while it waits. The founder's signed answer (through the `greg decide` CLI, a separate process)
settles it: "executed" closes the mission with no second effect; "not executed" allows exactly one new
dispatch under a new grant. The effect log ends with exactly one line either way.

The founder key is a per-test Ed25519 key, not Alfonso's; the capability is a test double.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from events.spine import EventSpine
from greg.journal import Journal
from provenance.ledger import EvidenceLedger

ROOT = Path(__file__).resolve().parents[2]

DRIVER = '''
import os, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from greg.body import Body
from greg.capabilities import CapabilityManifest

home, effects, mode_file = Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
MANIFEST = CapabilityManifest(
    capability_id="test.ledger_post", version="1.0.0", provider="test", function="test.ledger_post",
    description="appends one line to an append-only effect log (not retry-safe)", route="api",
    consequence_class="internal_write", inputs={"entry": "str"}, outputs={"posted": "bool"},
    strengthens=("proof",), target_prefix="probe:", retry_safe=False)


def adapter(params, ctx):
    mode = mode_file.read_text().strip() if mode_file.exists() else "normal"
    (mode_file.parent / "calls").open("a").write(f"{os.getpid()} {ctx.grant_id}\\n")
    if mode == "hang-before":
        time.sleep(3600)                       # killed here: dispatch claimed, no effect, no receipt
    with effects.open("a") as f:
        f.write(f"posted {params['entry']} {ctx.grant_id}\\n")
        f.flush()
        os.fsync(f.fileno())
    if mode == "hang-after":
        time.sleep(3600)                       # killed here: dispatch claimed, effect made, no receipt
    return {"posted": True}


class TestBody(Body):
    def open(self):
        super().open()
        self.registry.register(MANIFEST, adapter, state="ATTACHED")
        return self


sys.exit(TestBody(home).run(tick_seconds=0.2))
'''


def greg(home, *args):
    env = {**os.environ, "GREG_FOUNDER_PASSPHRASE": "", "PYTHONPATH": str(ROOT)}
    proc = subprocess.run([sys.executable, "-m", "greg", "--home", str(home), *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return proc


def read(home):
    """Read-only view of the Body's canonical ledger (the Body process owns the writer)."""
    config = json.loads((Path(home) / "body.json").read_text())
    ledger = EvidenceLedger(config["constitution_hash"], str(Path(home) / "ledger.jsonl"), read_only=True)
    try:
        journal = Journal(EventSpine(ledger), actor="spiffe://uniimente.internal/greg/test-observer")
        out = {kind: [e.payload for e in journal.replay(kind)]
               for kind in ("mission.action", "decision.requested", "mission.achieved", "body.recovered",
                            "mission.blocked", "mission.appraised")}
        out["dispatch"] = [r.payload for r in ledger.by_type("grant_dispatch")]
        out["receipt"] = [r.payload for r in ledger.by_type("receipt")]
        out["chain"] = ledger.verify_chain()[0]
        return out
    finally:
        ledger.close()


def wait_for(predicate, timeout=60, what="condition"):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            value = predicate()
        except (FileNotFoundError, json.JSONDecodeError, ValueError, KeyError):
            value = None
        if value:
            return value
        time.sleep(0.2)
    raise AssertionError(f"timed out waiting for {what}")


def start(tmp_path, home, effects, mode_file):
    driver = tmp_path / "driver.py"
    driver.write_text(DRIVER)
    log = (tmp_path / "body.log").open("a")
    return subprocess.Popen([sys.executable, str(driver), str(ROOT), str(home), str(effects), str(mode_file)],
                            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                            env={**os.environ, "PYTHONPATH": str(ROOT)})


def ours(dispatches, proposals):
    return [d for d in dispatches if d.get("proposal_id") in proposals]


@pytest.mark.parametrize("kill_point, answer", [("hang-after", "reconcile_executed"),
                                                ("hang-before", "reconcile_not_executed")])
def test_sigkill_between_dispatch_and_receipt_is_reconciled_never_redispatched(tmp_path, kill_point, answer):
    home, data, key = tmp_path / "body", tmp_path / "data", tmp_path / "founder.pem"
    data.mkdir()
    effects, mode_file = data / "effects.log", tmp_path / "mode"
    greg(home, "init", "--read-root", str(data))
    public = greg(home, "founder", "keygen", "--key", str(key), "--no-passphrase").stdout.strip()
    greg(home, "founder", "enroll", "--pubkey", public)
    mode_file.write_text(kill_point)
    horizon = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace("+00:00", "Z")
    spec = {"mission_id": "m:post-once", "founder_expression": "Post the entry exactly once.",
            "intended_effect": "the effect log holds the entry", "priority": 80, "closure": {"kind": "bounded"},
            "success_checks": [{"check_id": "posted", "description": "the entry is in the effect log",
                                "sensor": {"capability": "fs.read", "params": {"path": str(effects)},
                                           "target": "fs:effects.log"},
                                "predicate": {"op": "contains", "field": "text", "value": "posted entry-1"}}],
            "strategies": [{"action_id": "post", "capability": "test.ledger_post", "params": {"entry": "entry-1"},
                            "target": "probe:effects", "advances": ["posted"], "rationale": "post once",
                            "cost_usd": 0.25}],
            "light_cone": {"capabilities": ["fs.read", "test.ledger_post"], "targets": ["fs:*", "probe:*"],
                           "max_consequence_class": "internal_write", "budget_usd": 1.0, "horizon": horizon}}
    (tmp_path / "mission.json").write_text(json.dumps(spec))
    greg(home, "mission", "submit", str(tmp_path / "mission.json"), "--key", str(key), "--no-passphrase")

    body = start(tmp_path, home, effects, mode_file)
    try:
        # The adapter is inside its effect: the Gate claimed the dispatch and no receipt exists.
        wait_for(lambda: (tmp_path / "calls").exists() and read(home)["dispatch"], what="the dispatch claim")
        if kill_point == "hang-after":
            wait_for(lambda: effects.exists() and effects.read_text(), what="the effect")
        before = read(home)
        assert len(before["dispatch"]) >= 1 and not [r for r in before["receipt"]
                                                    if r["grant_id"] == before["dispatch"][-1]["grant_id"]]
        assert before["mission.action"] == []          # the Body died before it could record anything
        body.send_signal(signal.SIGKILL)
        body.wait(timeout=20)
    finally:
        if body.poll() is None:
            body.kill()

    mode_file.write_text("normal")
    killed_grant = before["dispatch"][-1]["grant_id"]
    body = start(tmp_path, home, effects, mode_file)
    try:
        request = wait_for(lambda: [r for r in read(home)["decision.requested"] if r["kind"] == "RECONCILIATION"],
                           what="the reconciliation request")[0]
        time.sleep(2.0)                                 # ~10 ticks while the founder has not answered
        waiting = read(home)
        assert waiting["body.recovered"], "the restart reconstructs from retained history"
        assert [(a["status"], a["attempt"]) for a in waiting["mission.action"]] == [("UNCERTAIN", 0)]
        uncertain = waiting["mission.action"][0]
        assert uncertain["grant_id"] == killed_grant and uncertain["reserved_usd"] == 0.25
        assert uncertain["cost_usd"] == 0.0             # unknown spend is reserved, not booked as zero-and-free
        assert request["authority_requested"]["grant_id"] == killed_grant
        assert request["authority_requested"]["attempt"] == 0
        assert len([r for r in waiting["decision.requested"] if r["kind"] == "RECONCILIATION"]) == 1
        calls = (tmp_path / "calls").read_text().splitlines()
        assert len(calls) == 1, "nothing is redispatched while the reconciliation is open"

        greg(home, "decide", request["request_id"], answer, "--reason", "inspected the effect log",
             "--key", str(key), "--no-passphrase")
        wait_for(lambda: read(home)["mission.achieved"], what="mission closure")
        time.sleep(1.0)
        final = read(home)
    finally:
        body.send_signal(signal.SIGTERM)
        try:
            body.wait(timeout=20)
        except subprocess.TimeoutExpired:
            body.kill()

    lines = effects.read_text().splitlines()
    assert len(lines) == 1 and lines[0].startswith("posted entry-1"), lines   # exactly one effect
    calls = (tmp_path / "calls").read_text().splitlines()
    statuses = [(a["status"], a["attempt"]) for a in final["mission.action"]]
    if answer == "reconcile_executed":
        assert len(calls) == 1, "an executed dispatch is never dispatched again"
        assert statuses == [("UNCERTAIN", 0), ("DONE", 0)]
        done = final["mission.action"][-1]
        assert done["reconciles"]["grant_id"] == killed_grant and done["cost_usd"] == 0.25
        assert lines[0].endswith(killed_grant)
    else:
        assert len(calls) == 2, "exactly one new dispatch after a not-executed answer"
        assert statuses == [("UNCERTAIN", 0), ("RECONCILED_NOT_EXECUTED", 0), ("DONE", 1)]
        assert final["mission.action"][-1]["receipt"] and not lines[0].endswith(killed_grant)
    grants = [d["grant_id"] for d in final["dispatch"]]
    assert len(grants) == len(set(grants)), "every grant is dispatched at most once"
    receipted = [r["grant_id"] for r in final["receipt"]]
    assert killed_grant not in receipted and len(receipted) == len(set(receipted))
    assert final["chain"]
