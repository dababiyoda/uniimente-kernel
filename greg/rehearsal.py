"""Development rehearsal: the whole founder path with no credentials, on a throwaway body.

    python -m greg rehearse [--dir DIR] [--kernel-root PATH] [--effort 8] [--console PORT]

It creates a NEW body in a scratch folder, generates a throwaway Ed25519 key whose file name and
every signed command are labelled REHEARSAL, and runs the Founder's First Mission through the real
signed-command path: attach the exact selection engine, sign the mission, tick the body until it
settles, then crash and restart it to show nothing repeats. With ``--console`` it serves Mission
Control on that body so the founder can look at every view.

What it is not: the throwaway key is not Alfonso's key and authenticates no one; the rehearsal body
is not a founder-designated body, so nothing it does counts toward VEPMC; no network, model, money,
message or publication is used. It reads only the kernel checkout it is pointed at.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time

REHEARSAL = "REHEARSAL"


def rehearse(*, directory: Path | None = None, kernel_root: Path | None = None, effort_budget: int = 8,
             max_ticks: int = 12) -> dict:
    from greg.body import Body, init_body, send_signed
    from greg.founder import generate_founder_key, load_founder_key
    from greg.templates import first_mission
    started = time.monotonic()
    work = Path(directory or tempfile.mkdtemp(prefix="greg-rehearsal-")).resolve()
    kernel = Path(kernel_root or Path(__file__).resolve().parents[1]).resolve()
    if (work / "body").exists():
        raise FileExistsError(f"{work / 'body'} exists; a rehearsal always starts from a new body")
    work.mkdir(parents=True, exist_ok=True)
    init_body(work / "body", read_roots=[str(kernel)])
    keyfile = work / f"{REHEARSAL}-throwaway-founder-key.pem"
    public = generate_founder_key(keyfile, None)
    key = load_founder_key(keyfile, None)
    home = work / "body"
    with Body(home) as body:
        body.enroll_founder(public)
    send_signed(home, key, "CAPABILITY_ATTACH", {"capability_id": "cognition.dp_knapsack"})
    spec = first_mission(kernel_root=str(kernel), effort_budget=effort_budget, run=REHEARSAL.lower(),
                         founder_expression=f"[{REHEARSAL}] Run the Founder's First Mission with a throwaway key.")
    send_signed(home, key, "MISSION", spec)
    trace = []
    with Body(home) as body:                       # first process: one step, then a simulated crash
        body.boot()
        trace.append(body.tick()["missions"])
    with Body(home) as body:                       # second process: resume from the journal
        body.boot()
        for _ in range(max_ticks):
            out = body.tick()["missions"]
            trace.append(out)
            if out and out[0]["state"] in ("ACHIEVED", "BLOCKED"):
                break
        actions = [e.payload for e in body.journal.replay("mission.action") if e.payload["mission_id"] == spec["mission_id"]]
        appraisals = [e.payload for e in body.journal.replay("mission.appraised") if e.payload["mission_id"] == spec["mission_id"]]
        chain_ok, _ = body.ledger.verify_chain()
    done = [a["action_id"] for a in actions if a["status"] == "DONE"]
    dossiers = sorted((home / "deliveries" / "first-mission").glob("*.md"))
    return {"label": REHEARSAL, "directory": str(work), "home": str(home), "throwaway_key": str(keyfile),
            "kernel_root": str(kernel), "mission_id": spec["mission_id"],
            "state": trace[-1][0]["state"] if trace and trace[-1] else "UNKNOWN",
            "steps_done": done, "steps_repeated": sorted({a for a in done if done.count(a) > 1}),
            "appraisal": appraisals[-1]["verdict"] if appraisals else None,
            "dossier": str(dossiers[-1]) if dossiers else None, "ledger_chain_verified": chain_ok,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "counts_toward_vepmc": False, "authenticates_founder": False,
            "used": {"network": False, "models": False, "money": False, "messages": False}}


def main(args) -> int:
    result = rehearse(directory=Path(args.dir) if args.dir else None,
                      kernel_root=Path(args.kernel_root) if args.kernel_root else None, effort_budget=args.effort)
    print(json.dumps(result, indent=1))
    if args.console:
        from greg.console import Console, serve
        from greg.founder import load_founder_key
        console = Console(result["home"], key=load_founder_key(result["throwaway_key"], None))
        server = serve(console, port=args.console)
        print(f"[{REHEARSAL}] Mission Control: http://127.0.0.1:{server.server_address[1]}/  (Ctrl-C to stop)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    return 0 if result["state"] == "ACHIEVED" and result["appraisal"] == "VERIFIED" else 1
