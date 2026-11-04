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

The body is marked as a rehearsal body in its body.json (``mark_body``) before the throwaway key is enrolled, and
every MISSION it signs opens its founder_expression with ``LABEL``, so its own hash-chained ledger says so too.
greg.metrics.founder_tier never puts a mission of a body marked or labelled either way at the founder tier, even
when that unprotected key signs a FOUNDER_TIER attestation itself. The label covers a body made before the mark
existed and a body.json edited since. Both guard against promoting a rehearsal by accident, not against an operator
who builds a body by hand.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time

REHEARSAL = "REHEARSAL"
# Opens the founder_expression of every MISSION `greg rehearse` signs, as it has since this file was first written
# (53ef9d08, 2026-10-14); greg.metrics.rehearsal_body reads it from the ledger.
LABEL = f"[{REHEARSAL}]"


def mark_body(home: Path) -> dict:
    """Write the rehearsal mark (greg.metrics.REHEARSAL_MARK) into a body `greg rehearse` has just created.

    body.json is replaced whole, through a new 0600 file as init_body wrote it, so a reader never sees half of it.
    Called before any key is enrolled, so no command of this body predates the mark."""
    from greg.body import _private_write
    from greg.metrics import REHEARSAL_BODY, REHEARSAL_MARK
    config_file = Path(home) / "body.json"
    config = json.loads(config_file.read_text())
    config[REHEARSAL_MARK] = {"label": REHEARSAL, "created_by": "greg rehearse", "founder_tier": REHEARSAL_BODY}
    temporary = config_file.with_name("body.json.rehearsal-tmp")
    _private_write(temporary, json.dumps(config, indent=2).encode())
    os.replace(temporary, config_file)
    return config


def settle(home: Path, mission_id: str, max_ticks: int = 12) -> str:
    from greg.body import Body
    state = "UNKNOWN"
    with Body(home) as body:
        body.boot()
        for _ in range(max_ticks):
            state = {m["mission_id"]: m["state"] for m in body.tick()["missions"]}.get(mission_id, state)
            if state in ("ACHIEVED", "BLOCKED"):
                break
        if state == "ACHIEVED" and body.appraise(mission_id)["verdict"] != "VERIFIED":
            state = "ACHIEVED_BUT_REFUTED"
    return state


def rehearse(*, directory: Path | None = None, kernel_root: Path | None = None, effort_budget: int = 8,
             max_ticks: int = 12, with_venture: bool = True) -> dict:
    from greg.body import Body, init_body, send_signed
    from greg.founder import generate_founder_key, load_founder_key
    from greg.templates import first_mission
    started = time.monotonic()
    work = Path(directory or tempfile.mkdtemp(prefix="greg-rehearsal-")).resolve()
    kernel = Path(kernel_root or Path(__file__).resolve().parents[1]).resolve()
    if (work / "body").exists():
        raise FileExistsError(f"{work / 'body'} exists; a rehearsal always starts from a new body")
    work.mkdir(parents=True, exist_ok=True)
    home = work / "body"
    init_body(home, read_roots=[str(kernel)])
    mark_body(home)                                # before any key exists: no command of this body predates the mark
    keyfile = work / f"{REHEARSAL}-throwaway-founder-key.pem"
    public = generate_founder_key(keyfile, None)
    key = load_founder_key(keyfile, None)
    with Body(home) as body:
        body.enroll_founder(public)
    send_signed(home, key, "CAPABILITY_ATTACH", {"capability_id": "cognition.dp_knapsack"})
    spec = first_mission(kernel_root=str(kernel), effort_budget=effort_budget, run=REHEARSAL.lower(),
                         founder_expression=f"{LABEL} Run the Founder's First Mission with a throwaway key.")
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
    venture = second = None
    if trace and trace[-1] and trace[-1][0]["state"] == "ACHIEVED" and with_venture:
        from greg.venture_rehearsal import books, latest_canon, venture_rehearsal
        canon, _ = latest_canon(home / "deliveries")
        vspec = venture_rehearsal(canon=canon)
        send_signed(home, key, "MISSION", vspec)
        state = settle(home, vspec["mission_id"], max_ticks)
        venture = {"mission_id": vspec["mission_id"], "state": state, "books": books(home, vspec["mission_id"])}
        # A second First Mission reads the first one's retained result: memory across missions, not a cache.
        again = first_mission(kernel_root=str(kernel), effort_budget=effort_budget, run=REHEARSAL.lower() + "-2",
                              founder_expression=f"{LABEL} Run the Founder's First Mission again.")
        send_signed(home, key, "MISSION", again)
        second_state = settle(home, again["mission_id"], max_ticks)
        doc = json.loads(next((home / "deliveries" / "first-mission").glob(again["mission_id"].replace(":", "_") + ".json")).read_text())
        second = {"mission_id": again["mission_id"], "state": second_state, "since_last": doc.get("since_last"),
                  "lesson": doc.get("lesson")}
    return {"label": REHEARSAL, "directory": str(work), "home": str(home), "throwaway_key": str(keyfile),
            "kernel_root": str(kernel), "mission_id": spec["mission_id"],
            "state": trace[-1][0]["state"] if trace and trace[-1] else "UNKNOWN",
            "steps_done": done, "steps_repeated": sorted({a for a in done if done.count(a) > 1}),
            "appraisal": appraisals[-1]["verdict"] if appraisals else None,
            "dossier": str(dossiers[0]) if dossiers else None, "ledger_chain_verified": chain_ok,
            "venture_rehearsal": venture, "second_first_mission": second,
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
        print(f"[{REHEARSAL}] Mission Control (private link, works once): "
              f"{console.owner_url(server.server_address[1])}  (Ctrl-C to stop)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    ok = result["state"] == "ACHIEVED" and result["appraisal"] == "VERIFIED"
    ok = ok and (result["venture_rehearsal"] or {}).get("state") == "ACHIEVED"
    ok = ok and (result["second_first_mission"] or {}).get("state") == "ACHIEVED"
    return 0 if ok else 1
