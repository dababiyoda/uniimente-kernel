"""GREG's face (developer mode): one command, one persistent institution.

    greg init --read-root ~/Projects          create this computer's body
    greg founder keygen --key ~/.greg-founder.pem   (on Alfonso's own device)
    greg founder enroll --pubkey HEX          trust-on-first-use enrollment
    greg mission submit mission.json --key K  signed goal -> inbox; the body runs it
    greg status | greg decisions | greg morning
    greg decide REQUEST_ID approve|reject --key K
    greg critique EVENT_ID --verdict reject --evidence-type founder_judgment --text ... --key K
    greg pause|resume|stop --key K            (or: greg stop --local, touching STOP)
    greg run                                  the host loop (normally started by the supervisor)
    greg service install --platform macos|linux|supervisord [--remote]
    greg device enroll --pubkey HEX --label phone --key K   delegate a narrow key to a phone
    greg serve                                   loopback remote channel for the phone

The CLI never opens the ledger as a writer while the body runs: commands are
signed files dropped into the body inbox, so any interface can close at any time.
"""
from __future__ import annotations

import argparse
from datetime import timedelta
import getpass
import json
import os
from pathlib import Path
import sys

from greg import service
from greg.body import Body, BodyError, Layout, init_body, status
from greg.founder import generate_founder_key, load_founder_key, sign_command
from greg.tribunal import mark_reviewed, morning_report

DEFAULT_HOME = os.environ.get("GREG_HOME", str(Path.home() / ".uniimente" / "greg"))


def _passphrase(args) -> bytes | None:
    env = os.environ.get("GREG_FOUNDER_PASSPHRASE")
    if env is not None:
        return env.encode() or None
    if getattr(args, "no_passphrase", False):
        return None
    return getpass.getpass("founder key passphrase: ").encode() or None


def _drop(home: str, kind: str, body: dict, args) -> Path:
    layout = Layout(home)
    config = json.loads(layout.config.read_text())
    key = load_founder_key(args.key, _passphrase(args))
    envelope = sign_command(key, kind, body, body_id=config["body_id"],
                            ttl=timedelta(hours=getattr(args, "ttl_hours", 24)))
    target = layout.inbox / f"{envelope['issued_at'].replace(':', '')}-{kind.lower()}-{envelope['nonce'][:8]}.json"
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(envelope, indent=1))
    tmp.replace(target)
    return target


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="greg", description="GREG: persistent personal agentic operating layer")
    p.add_argument("--home", default=DEFAULT_HOME)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init"); s.add_argument("--read-root", action="append", default=[])
    f = sub.add_parser("founder"); fs = f.add_subparsers(dest="founder_cmd", required=True)
    k = fs.add_parser("keygen"); k.add_argument("--key", required=True); k.add_argument("--no-passphrase", action="store_true")
    e = fs.add_parser("enroll"); e.add_argument("--pubkey", required=True)

    for name in ("mission", "decide", "critique", "pause", "resume", "stop", "attach", "detach", "lifecycle",
                 "accept"):
        q = sub.add_parser(name)
        q.add_argument("--key")
        q.add_argument("--no-passphrase", action="store_true")
        q.add_argument("--ttl-hours", type=int, default=24)
        if name == "mission":
            q.add_argument("action", choices=["submit", "new"])
            q.add_argument("target", help="mission JSON file (submit) or template name (new)")
            q.add_argument("--repo", action="append", default=[], help="role=path (repo-guardian, integration-watch)")
            q.add_argument("--pin"); q.add_argument("--version", dest="pkg_version")
            q.add_argument("--cadence-seconds", type=int, default=21600)
            q.add_argument("--text"); q.add_argument("--must-contain")
            q.add_argument("--print-only", action="store_true", help="show the mission without signing")
        if name == "accept":
            q.add_argument("event_id"); q.add_argument("--text", default="accepted after morning review")
        if name == "decide":
            q.add_argument("request_id"); q.add_argument("answer"); q.add_argument("--reason", default="")
        if name == "critique":
            q.add_argument("event_id"); q.add_argument("--verdict", required=True)
            q.add_argument("--evidence-type", required=True); q.add_argument("--text", required=True)
            q.add_argument("--exclude-strategy", action="store_true"); q.add_argument("--regression")
        if name == "stop":
            q.add_argument("--local", action="store_true")
        if name in ("attach", "detach"):
            q.add_argument("capability_id")
        if name == "lifecycle":
            q.add_argument("mission_id"); q.add_argument("state"); q.add_argument("--reason", default="")

    d = sub.add_parser("device", help="delegate a narrow, expiring key to a phone (founder-signed)")
    ds = d.add_subparsers(dest="device_cmd", required=True)
    de = ds.add_parser("enroll"); de.add_argument("--pubkey", required=True); de.add_argument("--label", required=True)
    de.add_argument("--kinds", default="DECISION,CRITIQUE,BODY_PAUSE,BODY_RESUME,BODY_STOP")
    de.add_argument("--days", type=int, default=30)
    dr = ds.add_parser("revoke"); dr.add_argument("device_key_id")
    for q in (de, dr):
        q.add_argument("--key", required=True); q.add_argument("--no-passphrase", action="store_true")
        q.add_argument("--ttl-hours", type=int, default=24)
    sv2 = sub.add_parser("serve", help="remote channel for the phone (loopback; expose via tailscale serve)")
    sv2.add_argument("--host", default="127.0.0.1"); sv2.add_argument("--port", type=int, default=8765)
    sub.add_parser("status"); sub.add_parser("decisions"); sub.add_parser("vepmc"); sub.add_parser("routing")
    m = sub.add_parser("morning"); m.add_argument("--mark-reviewed", action="store_true")
    r = sub.add_parser("run"); r.add_argument("--tick-seconds", type=float, default=30.0)
    r.add_argument("--max-ticks", type=int)
    r.add_argument("--clear-stop", action="store_true",
                   help="remove a previous local STOP file (a deliberate human restart)")
    sv = sub.add_parser("service"); svs = sv.add_subparsers(dest="service_cmd", required=True)
    si = svs.add_parser("install"); si.add_argument("--platform", required=True, choices=["macos", "linux", "supervisord"])
    si.add_argument("--target-dir")
    si.add_argument("--remote", action="store_true", help="the phone channel (greg serve) instead of the body")
    args = p.parse_args(argv)
    home = args.home

    try:
        if args.cmd == "init":
            print(json.dumps(init_body(home, read_roots=args.read_root or [str(Path.home())]), indent=1))
        elif args.cmd == "founder" and args.founder_cmd == "keygen":
            print(generate_founder_key(args.key, _passphrase(args)))
        elif args.cmd == "founder" and args.founder_cmd == "enroll":
            with Body(home) as body:
                print(json.dumps(body.enroll_founder(args.pubkey), indent=1))
        elif args.cmd == "mission":
            if args.action == "submit":
                spec = json.loads(Path(args.target).read_text())
            else:
                from greg import templates
                if args.target in ("repo-guardian", "integration-watch"):
                    spec = templates.TEMPLATES[args.target](repositories=dict(r.split("=", 1) for r in args.repo),
                                                   expected_pin=args.pin, expected_version=args.pkg_version,
                                                   cadence_seconds=args.cadence_seconds)
                elif args.target == "workspace-note":
                    note = Layout(home).workspace / "m_first-note" / "note.txt"
                    spec = templates.workspace_note(text=args.text, must_contain=args.must_contain,
                                                    workspace_file=note)
                else:
                    raise BodyError(f"unknown template {args.target}; known: {sorted(templates.TEMPLATES)}")
            from greg.missions import validate_mission
            validate_mission(spec)
            if getattr(args, "print_only", False):
                print(json.dumps(spec, indent=1))
            else:
                print(_drop(home, "MISSION", spec, args))
        elif args.cmd == "accept":
            print(_drop(home, "CRITIQUE", {"target_event_id": args.event_id, "verdict": "accept",
                                           "evidence_type": "founder_judgment", "text": args.text}, args))
        elif args.cmd in ("vepmc", "routing"):
            from events.spine import EventSpine
            from greg import metrics, routing
            from greg.journal import Journal
            from provenance.ledger import EvidenceLedger
            config = json.loads(Layout(home).config.read_text())
            ledger = EvidenceLedger(config["constitution_hash"], str(Layout(home).ledger), read_only=True)
            try:
                journal = Journal(EventSpine(ledger), actor="spiffe://uniimente.internal/greg/cli-reader")
                data = metrics.vepmc(journal) if args.cmd == "vepmc" else routing.routing_knowledge(journal)
            finally:
                ledger.close()
            print(json.dumps(data, indent=1))
        elif args.cmd == "decide":
            print(_drop(home, "DECISION", {"request_id": args.request_id, "answer": args.answer,
                                           "reason": args.reason}, args))
        elif args.cmd == "critique":
            body = {"target_event_id": args.event_id, "verdict": args.verdict,
                    "evidence_type": args.evidence_type, "text": args.text}
            if args.exclude_strategy:
                body["exclude_strategy"] = True
            if args.regression:
                body["regression"] = args.regression
            print(_drop(home, "CRITIQUE", body, args))
        elif args.cmd in ("pause", "resume"):
            print(_drop(home, "BODY_" + args.cmd.upper(), {}, args))
        elif args.cmd == "stop":
            if args.local:  # physical/OS-level authority over this machine always works
                Layout(home).stop_file.touch()
                print("STOP file written; the body exits at its next check")
            else:
                print(_drop(home, "BODY_STOP", {}, args))
        elif args.cmd in ("attach", "detach"):
            print(_drop(home, "CAPABILITY_" + args.cmd.upper(), {"capability_id": args.capability_id}, args))
        elif args.cmd == "lifecycle":
            print(_drop(home, "LIFECYCLE", {"mission_id": args.mission_id, "state": args.state,
                                            "reason": args.reason}, args))
        elif args.cmd == "device" and args.device_cmd == "enroll":
            from datetime import datetime, timezone
            expires = datetime.now(timezone.utc) + timedelta(days=args.days)
            print(_drop(home, "DEVICE_ENROLL", {"public_key": args.pubkey, "label": args.label,
                                                "kinds": [k.strip() for k in args.kinds.split(",") if k.strip()],
                                                "expires_at": expires.isoformat().replace("+00:00", "Z")}, args))
        elif args.cmd == "device" and args.device_cmd == "revoke":
            print(_drop(home, "DEVICE_REVOKE", {"device_key_id": args.device_key_id}, args))
        elif args.cmd == "serve":
            from greg.remote import serve
            print(f"greg remote channel on http://{args.host}:{args.port} (loopback only). For the phone: "
                  f"tailscale serve --bg --https=443 http://{args.host}:{args.port}", flush=True)
            return serve(home, args.host, args.port)
        elif args.cmd == "status":
            print(json.dumps(status(home), indent=1, default=str))
        elif args.cmd == "decisions":
            print(json.dumps(status(home)["decisions_required"], indent=1))
        elif args.cmd == "morning":
            with Body(home) as body:
                report = morning_report(body.journal, body.engine)
                if args.mark_reviewed:
                    mark_reviewed(body.journal, report)
            print(json.dumps(report, indent=1, default=str))
        elif args.cmd == "run":
            if args.clear_stop:
                Layout(home).stop_file.unlink(missing_ok=True)
            return Body(home).run(tick_seconds=args.tick_seconds, max_ticks=args.max_ticks)
        elif args.cmd == "service":
            target = service.install(Path(home), args.platform, remote=args.remote,
                                     target_dir=Path(args.target_dir) if args.target_dir else None)
            print(json.dumps({"written": str(target), "loaded": False,
                              "to_load": service.load_instructions(args.platform, target)}, indent=1))
        return 0
    except BodyError as exc:
        print(f"greg: {exc}", file=sys.stderr)
        return 2
