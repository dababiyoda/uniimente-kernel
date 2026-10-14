"""Five orthogonal closures for the GREG body (persistent operating layer).

Each check builds a real temporary body, a real Ed25519 test founder key and real
signed commands, then executes behavior. Nothing is declared closed by prose.
Economic closure here means capital protection and founder-attention economy;
no revenue or external business outcome is claimed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import time

from closure.framework import ClosureRegistry, ModuleClosures


def _world():
    from greg.body import Body, init_body
    from greg.founder import generate_founder_key, load_founder_key, sign_command
    tmp = Path(tempfile.mkdtemp(prefix="greg-closure-"))
    (tmp / "data").mkdir()
    config = init_body(tmp / "body", read_roots=[str(tmp / "data")])
    public = generate_founder_key(tmp / "k.pem", None)
    key = load_founder_key(tmp / "k.pem", None)
    with Body(tmp / "body") as body:
        body.enroll_founder(public)
    home = tmp / "body"
    ws = home.resolve() / "workspace" / "m_closure-note"

    def command(kind, body):
        env = sign_command(key, kind, body, body_id=config["body_id"])
        (home / "inbox" / f"{env['nonce']}.json").write_text(json.dumps(env))
        return env

    def spec(capabilities, *, cost=0.0, budget=0.0, ceiling="internal_write"):
        horizon = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        return {"mission_id": "m:closure-note", "founder_expression": "closure check", "intended_effect": "note",
                "priority": 1, "closure": {"kind": "bounded"},
                "success_checks": [{"check_id": "n", "description": "note", "sensor": {
                    "capability": "fs.read", "params": {"path": str(ws / "n.txt")}, "target": "fs:n.txt"},
                    "predicate": {"op": "contains", "field": "text", "value": "ok"}}],
                "strategies": [{"action_id": "w", "capability": "fs.write", "params": {
                    "relative_path": "n.txt", "content": "ok"}, "target": "workspace:n.txt", "advances": ["n"],
                    "rationale": "write", "cost_usd": cost}],
                "light_cone": {"capabilities": capabilities, "targets": ["fs:*", "workspace:*"],
                               "max_consequence_class": ceiling, "budget_usd": budget, "horizon": horizon}}
    return tmp, home, ws, command, spec, Body


def register_greg_closures(registry: ClosureRegistry) -> ClosureRegistry:
    def technical():
        tmp, home, ws, command, spec, Body = _world()
        command("MISSION", spec(["fs.read", "fs.write"]))
        with Body(home) as body:
            for _ in range(4):
                body.tick()
        with Body(home) as body:  # a fresh process view reconstructs the same truth
            m = body.engine.book.missions["m:closure-note"]
            return (m.status == "ACHIEVED" and (ws / "n.txt").read_text() == "ok",
                    "signed mission closes on re-observed evidence and reconstructs after reopen")

    def authority():
        tmp, home, ws, command, spec, Body = _world()
        env = command("MISSION", spec(["fs.read"]))  # fs.write outside the cone
        forged = dict(env, nonce="f" * 32)
        (home / "inbox" / "forged.json").write_text(json.dumps(forged))
        with Body(home) as body:
            for _ in range(3):
                body.tick()
            rejected = body.journal.replay("command.rejected")
            requests = body.engine.book.open_requests()
        return (not (ws / "n.txt").exists() and len(rejected) == 1 and len(requests) == 1
                and requests[0]["kind"] == "APPROVAL",
                "forged command rejected; out-of-cone action gets no grant and asks the founder once")

    def evidence():
        tmp, home, ws, command, spec, Body = _world()
        command("MISSION", spec(["fs.read", "fs.write"]))
        with Body(home) as body:
            for _ in range(4):
                body.tick()
            ok, why = body.ledger.verify_chain()
            done = [e.payload for e in body.journal.replay("mission.action") if e.payload["status"] == "DONE"]
            receipts = {r.hash for r in body.ledger.by_type("receipt")}
        return (ok and done and all(d["receipt"] in receipts for d in done),
                f"every executed action has a Gate receipt on a verified chain ({why})")

    def economic():
        tmp, home, ws, command, spec, Body = _world()
        command("MISSION", spec(["fs.read", "fs.write"], cost=5.0, budget=1.0))
        with Body(home) as body:
            for _ in range(6):
                body.tick()
            m = body.engine.book.missions["m:closure-note"]
            requests = body.engine.book.open_requests()
        return (m.spent_usd == 0.0 and not (ws / "n.txt").exists() and len(requests) == 1,
                "spend above the founder budget never executes; one decision request, no repeated escalation")

    def regenerative():
        import subprocess
        import sys
        tmp, home, ws, command, spec, Body = _world()
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.Popen([sys.executable, "-m", "greg", "--home", str(home), "run", "--tick-seconds", "0.2"],
                                cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        deadline = time.time() + 15
        while time.time() < deadline and not (home / "heartbeat.json").exists():
            time.sleep(0.1)
        (home / "STOP").touch()
        try:
            code = proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            return False, "body ignored STOP"
        stopped = json.loads((home / "heartbeat.json").read_text())["state"] == "STOPPED"
        return (code == 0 and stopped, "a separate body process exits 0 on local STOP (shutdown authority wins)")

    registry.register(ModuleClosures("greg_body", {"technical": technical, "authority": authority,
                                                   "evidence": evidence, "economic": economic,
                                                   "regenerative": regenerative}))
    return registry
