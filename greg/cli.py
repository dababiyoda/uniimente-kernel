"""GREG's face (developer mode): one command, one persistent institution.

    greg init --read-root ~/Projects          create this computer's body
    greg founder keygen --key ~/.greg-founder.pem   (on Alfonso's own device)
    greg founder enroll --pubkey HEX          trust-on-first-use enrollment
    greg mission submit mission.json --key K  signed goal -> inbox; the body runs it
    greg status | greg decisions | greg morning
    greg decide REQUEST_ID approve|reject --key K
    greg critique EVENT_ID --verdict reject --evidence-type founder_judgment --text ... --key K
    greg critique EVENT_ID --classification PREFERENCE --needs owner/repo#12 --text ... --key K   (typed review)
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
from greg.body import (Body, BodyError, Layout, init_body, morning_projection, observe, send_signed,
                       status)
from greg.founder import generate_founder_key, load_founder_key
from greg.tribunal import mark_reviewed, morning_report
from provenance.ledger import WriterConflict

DEFAULT_HOME = os.environ.get("GREG_HOME", str(Path.home() / ".uniimente" / "greg"))


def _passphrase(args) -> bytes | None:
    env = os.environ.get("GREG_FOUNDER_PASSPHRASE")
    if env is not None:
        return env.encode() or None
    if getattr(args, "no_passphrase", False):
        return None
    return getpass.getpass("founder key passphrase: ").encode() or None


def _drop(home: str, kind: str, body: dict, args) -> Path:
    key = load_founder_key(args.key, _passphrase(args))
    return send_signed(home, key, kind, body, ttl=timedelta(hours=getattr(args, "ttl_hours", 24)))


def _model_builder(secrets, config):
    """Builder factory for ``run --builder models``: every reachable model route behind one router."""
    from greg.builders import BuildError, ModelBuilder
    from greg.models import ModelRouter, available_routes
    routes, unavailable = available_routes(secrets, config=config.get("models"))
    if not routes:
        raise BuildError(f"no model route is available: {unavailable}")
    return ModelBuilder(ModelRouter(routes))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="greg", description="GREG: persistent personal agentic operating layer")
    p.add_argument("--home", default=DEFAULT_HOME)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init"); s.add_argument("--read-root", action="append", default=[])
    s.add_argument("--deliver-root", help="founder-visible folder for deliverables (default: <home>/deliveries)")
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
            q.add_argument("--local", action="append", default=[], help="name=path (engineering-brief)")
            q.add_argument("--github", action="append", default=[], help="owner/name (engineering-brief)")
            q.add_argument("--daily", action="store_true", help="engineering-brief: standing daily mission")
            q.add_argument("--preauthorize-delivery", action="store_true",
                           help="engineering-brief: sign delivery into the cone (no approval stop)")
            q.add_argument("--stale-days", type=int, default=14)
            q.add_argument("--print-only", action="store_true", help="show the mission without signing")
        if name == "accept":
            q.add_argument("event_id"); q.add_argument("--text", default="accepted after morning review")
        if name == "decide":
            q.add_argument("request_id"); q.add_argument("answer"); q.add_argument("--reason", default="")
        if name == "critique":
            q.add_argument("event_id"); q.add_argument("--verdict")
            q.add_argument("--evidence-type"); q.add_argument("--text", required=True)
            q.add_argument("--exclude-strategy", action="store_true"); q.add_argument("--regression")
            q.add_argument("--classification", choices=["ACCEPT", "REJECT", "CORRECT", "PREFERENCE", "FAILURE_CLAIM"],
                           help="typed review of a result: GREG may learn from it, only after a held-out test")
            q.add_argument("--needs", action="append", default=[], metavar="REF",
                           help="what truly needed your decision in this result (owner/repo#N or a repo); repeat")
            q.add_argument("--claim-missed", action="append", default=[], metavar="OWNER/REPO#N",
                           help="a failure you claim the result missed; GREG checks it independently")
            q.add_argument("--knob"); q.add_argument("--value")
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
    st = sub.add_parser("start", help="clear a persisted stop (local physical authority)")
    st.add_argument("--local", action="store_true", required=True)
    sub.add_parser("status"); sub.add_parser("decisions"); sub.add_parser("vepmc"); sub.add_parser("routing"); sub.add_parser("learning")
    c = sub.add_parser("console", help="the founder console on http://127.0.0.1:PORT")
    c.add_argument("--key", help="founder key; without it the console is read-only")
    c.add_argument("--no-passphrase", action="store_true"); c.add_argument("--port", type=int, default=8766)
    c.add_argument("--no-model", action="store_true", help="plan with templates only (no model calls)")
    m = sub.add_parser("morning"); m.add_argument("--mark-reviewed", action="store_true")
    r = sub.add_parser("run"); r.add_argument("--tick-seconds", type=float, default=30.0)
    r.add_argument("--max-ticks", type=int)
    r.add_argument("--builder", choices=["none", "claude-code", "models"], default="none",
                   help="Capability Genesis builder: claude-code (local CLI) or models (every reachable route: "
                        "Anthropic API, OpenAI API, Claude Code, with failover). Spends only a mission's signed "
                        "build budget")
    r.add_argument("--clear-stop", action="store_true",
                   help="remove a previous local STOP file (a deliberate human restart)")
    sv = sub.add_parser("service"); svs = sv.add_subparsers(dest="service_cmd", required=True)
    si = svs.add_parser("install"); si.add_argument("--platform", required=True, choices=["macos", "linux", "supervisord"])
    si.add_argument("--target-dir")
    si.add_argument("--remote", action="store_true", help="the phone channel (greg serve) instead of the body")
    si.add_argument("--builder", choices=["none", "claude-code", "models"], default="none",
                    help="let the installed body build and repair capabilities (spends only signed build budgets)")
    args = p.parse_args(argv)
    home = args.home

    try:
        if args.cmd == "init":
            print(json.dumps(init_body(home, read_roots=args.read_root or [str(Path.home())],
                                       deliver_root=args.deliver_root), indent=1))
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
                elif args.target == "engineering-brief":
                    spec = templates.engineering_brief(local=dict(r.split("=", 1) for r in args.local),
                                                       github=args.github, daily=args.daily,
                                                       preauthorize_delivery=args.preauthorize_delivery,
                                                       stale_days=args.stale_days)
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
        elif args.cmd in ("vepmc", "routing", "learning"):
            from greg import learning, metrics, routing
            with observe(home, actor="spiffe://uniimente.internal/greg/cli-reader") as journal:
                data = (metrics.vepmc(journal) if args.cmd == "vepmc" else learning.summary(journal)
                        if args.cmd == "learning" else routing.routing_knowledge(journal))
            print(json.dumps(data, indent=1))
        elif args.cmd == "decide":
            print(_drop(home, "DECISION", {"request_id": args.request_id, "answer": args.answer,
                                           "reason": args.reason}, args))
        elif args.cmd == "critique":
            implied = {"ACCEPT": ("accept", "founder_judgment"), "REJECT": ("reject", "founder_judgment"),
                       "CORRECT": ("note", "founder_judgment"), "PREFERENCE": ("note", "founder_judgment"),
                       "FAILURE_CLAIM": ("reject", "objective_failure")}.get(args.classification, (None, None))
            verdict, evidence_type = args.verdict or implied[0], args.evidence_type or implied[1]
            if not verdict or not evidence_type:
                raise BodyError("critique needs --verdict and --evidence-type, or a --classification")
            body = {"target_event_id": args.event_id, "verdict": verdict,
                    "evidence_type": evidence_type, "text": args.text}
            if args.classification:
                review = {"classification": args.classification}
                if args.needs:
                    review["labels"] = {"needs_decision": args.needs}
                if args.claim_missed:
                    review["claimed_missed"] = args.claim_missed
                if args.knob or args.value:
                    review["correction"] = {"knob": args.knob or "", "value": args.value or ""}
                body["review"] = review
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
        elif args.cmd == "console":
            from greg import planner
            from greg.capabilities import SecretBroker
            from greg.console import Console, serve
            key = load_founder_key(args.key, _passphrase(args)) if args.key else None
            layout = Layout(home)
            models_config = (json.loads(layout.config.read_text()).get("models")
                             if layout.config.is_file() else None)
            transport = None if args.no_model else planner.default_transport(SecretBroker(layout.secrets),
                                                                            config=models_config)
            server = serve(Console(home, key=key, transport=transport), port=args.port)
            print(f"GREG console on http://127.0.0.1:{args.port}  (model route: "
                  f"{transport.name if transport else 'off'}; {'signing enabled' if key else 'read-only'}). "
                  "Ctrl-C closes the console; the body keeps running.", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
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
        elif args.cmd == "start":
            stop = Layout(home).stop_file
            prior = stop.read_text() if stop.exists() else None
            stop.unlink(missing_ok=True)
            print(json.dumps({"cleared_stop": prior, "next": "launchctl kickstart gui/$(id -u)/"
                              + service.LABEL + "  (or start the supervisor unit)"}, indent=1))
        elif args.cmd == "status":
            print(json.dumps(status(home), indent=1, default=str))
        elif args.cmd == "decisions":
            print(json.dumps(status(home)["decisions_required"], indent=1))
        elif args.cmd == "morning":
            if args.mark_reviewed:  # advancing the review window writes history: the body must be stopped
                try:
                    with Body(home) as body:
                        report = morning_report(body.journal, body.engine)
                        mark_reviewed(body.journal, report)
                except WriterConflict:
                    raise BodyError("the body is running and owns the ledger; read the report without "
                                    "--mark-reviewed, or accept/critique the closure (signed) instead")
            else:
                report = morning_projection(home)
            print(json.dumps(report, indent=1, default=str))
        elif args.cmd == "run":
            if args.clear_stop:
                Layout(home).stop_file.unlink(missing_ok=True)
            builder = None
            if args.builder == "claude-code":
                from greg.builders import ClaudeCodeBuilder
                builder = ClaudeCodeBuilder()
            elif args.builder == "models":
                builder = _model_builder
            return Body(home, builder=builder).run(tick_seconds=args.tick_seconds, max_ticks=args.max_ticks)
        elif args.cmd == "service":
            target = service.install(Path(home), args.platform, remote=args.remote, builder=args.builder,
                                     target_dir=Path(args.target_dir) if args.target_dir else None)
            print(json.dumps({"written": str(target), "loaded": False,
                              "to_load": service.load_instructions(args.platform, target)}, indent=1))
        return 0
    except BodyError as exc:
        print(f"greg: {exc}", file=sys.stderr)
        return 2
