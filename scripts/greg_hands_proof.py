"""Run GREG's execution fabric end to end through the canonical Body (real worker, real browser, real organ).

    python scripts/greg_hands_proof.py init   --home H --read-root R [...]
    python scripts/greg_hands_proof.py ask    --home H "Improve GREG: ..."        # plain words -> signed MISSION
    python scripts/greg_hands_proof.py submit --home H --template browser|media ...
    python scripts/greg_hands_proof.py run    --home H [--ticks N] [--kill-when-leased]
    python scripts/greg_hands_proof.py answer --home H --kind RECONCILIATION|APPROVAL --answer ...
    python scripts/greg_hands_proof.py report --home H --out evidence.json

The founder key created by ``init`` is an OPERATOR TEST KEY held by this script. It is real
Ed25519 cryptography but it is NOT Alfonso's key; nothing here claims founder authentication
of a real person, founder-device verification or production authority.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from greg.body import Body, Layout, init_body  # noqa: E402
from greg.capabilities import CapabilityRegistry  # noqa: E402
from greg.founder import generate_founder_key, load_founder_key, sign_command  # noqa: E402
from greg.planner import PlannerContext, template_route  # noqa: E402
from greg import templates  # noqa: E402


def _key(home: Path):
    return load_founder_key(home.parent / f"{home.name}-operator-test-founder.pem", None)


def _drop(home: Path, kind: str, body: dict) -> dict:
    config = json.loads(Layout(home).config.read_text())
    envelope = sign_command(_key(home), kind, body, body_id=config["body_id"])
    (Layout(home).inbox / f"{envelope['nonce']}.json").write_text(json.dumps(envelope))
    return envelope


def cmd_init(args):
    home = Path(args.home).resolve()
    init_body(home, read_roots=args.read_root)
    public = generate_founder_key(home.parent / f"{home.name}-operator-test-founder.pem", None)
    with Body(home) as body:
        body.enroll_founder(public)
    print(json.dumps({"home": str(home), "founder_key": "operator test key (not Alfonso)"}))


def cmd_ask(args):
    home = Path(args.home).resolve()
    config = json.loads(Layout(home).config.read_text())
    with Body(home) as body:
        inventory = body.registry.inventory()
    ctx = PlannerContext(read_roots=tuple(config["read_roots"]), capabilities=inventory,
                         workspace=Layout(home).workspace)
    proposal = template_route(args.text, ctx)
    if not proposal or proposal["status"] != "PROPOSED":
        print(json.dumps(proposal, indent=2))
        raise SystemExit(2)
    spec = proposal["spec"]
    if args.budget is not None:
        strategy = spec["strategies"][0]
        strategy["cost_usd"] = strategy["params"]["max_budget_usd"] = args.budget
        spec["light_cone"]["budget_usd"] = args.budget
    envelope = _drop(home, "MISSION", spec)
    print(json.dumps({"proposal_origin": proposal["origin"], "notes": proposal.get("notes"),
                      "mission_id": spec["mission_id"], "signed_nonce": envelope["nonce"]}, indent=2))


def cmd_submit(args):
    home = Path(args.home).resolve()
    spec = json.loads(Path(args.spec).read_text())
    envelope = _drop(home, "MISSION", spec)
    print(json.dumps({"mission_id": spec["mission_id"], "signed_nonce": envelope["nonce"]}))


def cmd_run(args):
    """Tick the real Body. Each tick advances a virtual clock by 60 s so cadence waits do not stall."""
    home = Path(args.home).resolve()
    clock_file = home.parent / f"{home.name}-clock.txt"
    now = (datetime.fromisoformat(clock_file.read_text()) if clock_file.exists()
           else datetime.now(timezone.utc))
    with Body(home, clock=lambda: now) as body:
        for index in range(args.ticks):
            summary = body.tick()
            states = [(m.get("mission_id"), m.get("state"), m.get("action") or m.get("blocker", {}).get("why"))
                      for m in summary.get("missions") or []]
            print(json.dumps({"tick": index, "at": now.isoformat(), "summary": states}, default=str), flush=True)
            now = max(now + timedelta(seconds=60), datetime.now(timezone.utc))
            clock_file.write_text(now.isoformat())
            missions = body.engine.book.missions
            if missions and all(m.status in ("ACHIEVED", "ABANDONED", "SUPERSEDED") or m.blocker
                                for m in missions.values()):
                break


def cmd_run_and_kill(args):
    """Start ``run`` as a child process and SIGKILL it once a WorkOrder lease exists (mid-worker)."""
    home = Path(args.home).resolve()
    child = subprocess.Popen([sys.executable, __file__, "run", "--home", str(home), "--ticks", str(args.ticks)])
    deadline = time.monotonic() + args.wait
    leases = []
    while time.monotonic() < deadline and child.poll() is None:
        leases = list((Layout(home).workspace).glob("*/work-orders/*/lease.json"))
        if leases:
            time.sleep(args.after)
            break
        time.sleep(0.5)
    killed = child.poll() is None
    if killed:
        os.kill(child.pid, signal.SIGKILL)
    child.wait()
    print(json.dumps({"killed_mid_worker": killed and bool(leases), "lease": [str(p) for p in leases],
                      "returncode": child.returncode}))


def cmd_answer(args):
    home = Path(args.home).resolve()
    with Body(home) as body:
        requests = [e.payload for e in body.journal.replay("decision.requested")
                    if e.payload["kind"] == args.kind]
        answered = {e.payload["request_id"] for e in body.journal.replay("decision.answered")}
    pending = [r for r in requests if r["request_id"] not in answered]
    if not pending:
        raise SystemExit(f"no open {args.kind} request")
    envelope = _drop(home, "DECISION", {"request_id": pending[-1]["request_id"], "answer": args.answer,
                                        "reason": args.reason})
    print(json.dumps({"request_id": pending[-1]["request_id"], "answer": args.answer, "nonce": envelope["nonce"]}))


def cmd_report(args):
    home = Path(args.home).resolve()
    with Body(home) as body:
        events = [{"type": e.type, "payload": e.payload} for e in body.journal.replay("")
                  if e.type.startswith(("greg.mission", "greg.decision", "greg.deficit", "greg.authority"))]
        receipts = [{"seq": r.seq, "hash": r.hash, "grant_id": r.payload.get("grant_id"),
                     "observed": r.payload.get("result", {}).get("observed_outcome")}
                    for r in body.ledger.by_type("receipt")]
        chain = body.ledger.verify_chain()
    out = {"home": str(home), "ledger_chain_intact": chain[0] if isinstance(chain, tuple) else chain,
           "events": events, "receipts": receipts,
           "founder_key": "operator test key generated by scripts/greg_hands_proof.py; not Alfonso's key"}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps({"events": len(events), "receipts": len(receipts), "chain": out["ledger_chain_intact"]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("--home", required=True); p.add_argument("--read-root", action="append", required=True)
    p.set_defaults(fn=cmd_init)
    p = sub.add_parser("ask"); p.add_argument("--home", required=True); p.add_argument("text")
    p.add_argument("--budget", type=float); p.set_defaults(fn=cmd_ask)
    p = sub.add_parser("submit"); p.add_argument("--home", required=True); p.add_argument("--spec", required=True)
    p.set_defaults(fn=cmd_submit)
    p = sub.add_parser("run"); p.add_argument("--home", required=True); p.add_argument("--ticks", type=int, default=12)
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("run-and-kill"); p.add_argument("--home", required=True)
    p.add_argument("--ticks", type=int, default=6); p.add_argument("--wait", type=float, default=120)
    p.add_argument("--after", type=float, default=20); p.set_defaults(fn=cmd_run_and_kill)
    p = sub.add_parser("answer"); p.add_argument("--home", required=True); p.add_argument("--kind", required=True)
    p.add_argument("--answer", required=True); p.add_argument("--reason", default="")
    p.set_defaults(fn=cmd_answer)
    p = sub.add_parser("report"); p.add_argument("--home", required=True); p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_report)
    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
