"""Development rehearsal: the whole founder path with no credentials, on a throwaway body.

    python -m greg rehearse [--dir DIR] [--kernel-root PATH] [--effort 8] [--console PORT]
    python -m greg rehearse --path [--dir DIR] [--kernel-root PATH]

It creates a NEW body in a scratch folder, generates a throwaway Ed25519 key whose file name and
every signed command are labelled REHEARSAL, and runs the Founder's First Mission through the real
signed-command path: attach the exact selection engine, sign the mission, tick the body until it
settles, then crash and restart it to show nothing repeats. With ``--console`` it serves Mission
Control on that body so the founder can look at every view.

``--path`` does not run that first mission. It runs the buildable business path on that one
throwaway body, in order: N3 (one closed case), then N4 (a ratified procedure whose own runs cut
founder interventions), then N7 (that procedure transplanted into a second venture, whose reconciled
revenue funds the signed obligations and reserves with surplus left). People, not GREG, do every
outward act: the driver writes the same local evidence files the N3 body test writes. No payment
provider, no edit to the treasury, and no founder key. The throwaway key stays below the founder
tier, so the nodes are structurally met and the founder's path does not move. Three bodies that
each meet one node are not this command.

What it is not: the throwaway key is not Alfonso's key and authenticates no one; the rehearsal body
is not a founder-designated body, so nothing it does counts toward VEPMC; no network, model, money,
message or publication is used. It reads only the kernel checkout it is pointed at.

``--dir`` has to be a new scratch folder. It is refused when that folder holds ``body.json``, or when
it equals, contains, or is inside the real GREG home (``GREG_HOME`` when set, and ``~/.uniimente/greg``
either way). Aimed at either, the command would nest a rehearsal body in the founder's tree and write
an unencrypted throwaway key there.

The body is marked as a rehearsal body in its body.json (``mark_body``) before the throwaway key is enrolled, and
every MISSION it signs opens its founder_expression with ``LABEL``, so its own hash-chained ledger says so too.
greg.metrics.founder_tier never puts a mission of a body marked or labelled either way at the founder tier, even
when that unprotected key signs a FOUNDER_TIER attestation itself. The label covers a body made before the mark
existed and a body.json edited since. Both guard against promoting a rehearsal by accident, not against an operator
who builds a body by hand.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
    work = _rehearsal_work(directory, "greg-rehearsal-")
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
        # the verdict of the mission's current closure (greg/appraisal.py standings), not of its latest record
        from greg.appraisal import standings
        closure = standings(body.journal).current(spec["mission_id"])
        appraised = closure.record.payload["verdict"] if closure is not None and closure.record is not None else None
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
            "appraisal": appraised,
            "dossier": str(dossiers[0]) if dossiers else None, "ledger_chain_verified": chain_ok,
            "venture_rehearsal": venture, "second_first_mission": second,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "counts_toward_vepmc": False, "authenticates_founder": False,
            "used": {"network": False, "models": False, "money": False, "messages": False}}


# The buildable business path this command can close without a founder key, a payment provider, or a change to
# the treasury. N1 and N2 stay on `greg rehearse` without --path; N5 and N8 have no ledger predicate; N6 is a
# different mission shape and is not part of this sequence.
PATH_NODES = ("N3", "N4", "N7")
STATEMENT_HEADER = "date,description,amount,currency\n"


class PathRehearsalError(RuntimeError):
    """The one-body path did not reach N3, then N4, then N7."""


class RehearsalDirError(RuntimeError):
    """``--dir`` would write a rehearsal body or an unencrypted throwaway key into a real home or an existing body."""


def _greg_homes() -> tuple[Path, ...]:
    """Homes a rehearsal must not touch: ``GREG_HOME`` when set, and the default ``~/.uniimente/greg``.

    The environment variable is the real home for this process. The default path stays protected when
    that variable points somewhere else, so a scratch ``GREG_HOME`` does not open the founder's default tree.
    """
    candidates = []
    configured = os.environ.get("GREG_HOME", "").strip()
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.append(Path.home() / ".uniimente" / "greg")
    homes, seen = [], set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen:
            seen.add(resolved)
            homes.append(resolved)
    return tuple(homes)


def _path_nested(outer: Path, inner: Path) -> bool:
    try:
        inner.relative_to(outer)
    except ValueError:
        return False
    return True


def refuse_rehearsal_directory(directory: Path) -> Path:
    """Resolve a ``--dir`` or raise before a rehearsal creates anything there.

    Refused when the path holds ``body.json``, or when it equals, contains, or is inside a GREG home.
    """
    work = Path(directory).expanduser().resolve()
    for home in _greg_homes():
        if work == home or _path_nested(work, home) or _path_nested(home, work):
            raise RehearsalDirError(
                f"{work} equals, contains, or is inside the GREG home {home}; "
                "a rehearsal will not write an unencrypted throwaway key there")
    if (work / "body.json").is_file():
        raise RehearsalDirError(
            f"{work} holds body.json; a rehearsal will not nest a body or write a throwaway key "
            "inside an existing body")
    return work


def _rehearsal_work(directory: Path | None, prefix: str) -> Path:
    if directory is None:
        return Path(tempfile.mkdtemp(prefix=prefix)).resolve()
    return refuse_rehearsal_directory(directory)


class _Clock:
    def __init__(self):
        self.now = datetime.now(timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds: float):
        self.now += timedelta(seconds=seconds)


def _post(home: Path, key, body_id: str, clock: _Clock, kind: str, body: dict) -> None:
    from greg.founder import sign_command
    envelope = sign_command(key, kind, body, body_id=body_id, now=clock.now)
    target = Path(home) / "inbox" / f"{envelope['nonce']}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(envelope))
    os.replace(temporary, target)


def _tick(body, clock: _Clock, ticks: int = 3) -> None:
    clock.advance(4000)
    for _ in range(ticks):
        body.tick()
        clock.advance(1)


def _asks(body, mission_id: str, kind: str) -> list:
    return [event.payload for event in body.journal.replay("decision.requested")
            if event.payload["mission_id"] == mission_id and event.payload["kind"] == kind]


def _approve(home, key, body_id, clock, body, mission_id: str) -> None:
    answered = {event.payload["request_id"] for event in body.journal.replay("decision.answered")}
    for ask in _asks(body, mission_id, "APPROVAL"):
        if ask["request_id"] not in answered:
            _post(home, key, body_id, clock, "DECISION",
                  {"request_id": ask["request_id"], "answer": "approve"})
            _tick(body, clock)


def _step(home, key, body_id, clock, body, mission_id: str) -> None:
    _tick(body, clock)
    _approve(home, key, body_id, clock, body, mission_id)


def _case_spec(home: Path, n: int, venture: str, **kwargs) -> dict:
    from greg.missions import validate_mission
    from greg.templates import business_case
    spec = business_case(
        case=f"{venture} case {n:02d}", buyer=f"Buyer {venture} {n}", offer=f"{venture} service {n}",
        price=str(200 + 50 * n), currency="USD", acceptance=f"done within {n + 2} business days",
        workspace_root=Path(home).resolve() / "workspace", venture=venture, **kwargs)
    spec["founder_expression"] = f"{LABEL} {spec['founder_expression']}"
    return validate_mission(spec)


def _run_case(home, key, body_id, clock, body, spec: dict) -> str:
    """Sign one case and do every person's step. GREG's writes are approved only when the cone asks."""
    mission_id = spec["mission_id"]
    paid = spec["success_checks"][2]["sensor"]["params"]
    reference, amount = paid["reference"], paid["amount"]
    folder = Path(home).resolve() / "workspace" / mission_id.replace(":", "_")
    _post(home, key, body_id, clock, "MISSION", spec)
    _step(home, key, body_id, clock, body, mission_id)
    for name, text in (("acceptance.txt", f"accepted {reference}"),
                       ("statement.csv", STATEMENT_HEADER + f"2026-10-02,Pay {reference},{amount},USD\n"),
                       ("delivery.txt", f"delivered {reference}"),
                       ("outcome.txt", f"confirmed {reference}")):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(text + "\n")
        _step(home, key, body_id, clock, body, mission_id)
    _step(home, key, body_id, clock, body, mission_id)
    achieved = [event for event in body.journal.replay("mission.achieved")
                if event.payload["mission_id"] == mission_id]
    if len(achieved) != 1:
        appraisal = [event.payload for event in body.journal.replay("mission.appraised")
                     if event.payload["mission_id"] == mission_id]
        raise PathRehearsalError(f"{mission_id} did not close; appraisal={appraisal}")
    _post(home, key, body_id, clock, "CRITIQUE",
          {"target_event_id": achieved[0].event_id, "verdict": "accept", "evidence_type": "founder_judgment",
           "text": "rehearsal acceptance of a named buyer; not a founder-tier attestation"})
    _tick(body, clock, 1)
    return mission_id


def _measure(journal) -> dict:
    from greg import path as devpath
    rows = {}
    for node, predicate in (("N3", devpath.business_loop_closed), ("N4", devpath.sop_compounding),
                            ("N7", devpath.venture_compounding)):
        measured = predicate(journal)
        rows[node] = {"structurally_met": bool(measured.get("structurally_met")),
                      "met": bool(measured.get("met")),
                      "evidence_level": measured.get("evidence_level")}
    return rows


def _note(phase: str, journal, appeared: list, order: list, phases: list) -> dict:
    measured = _measure(journal)
    met = [node for node in PATH_NODES if measured[node]["structurally_met"]]
    new = [node for node in met if node not in appeared]
    head = journal.ledger.head
    if new:
        expected = PATH_NODES[len(appeared)]
        if new != [expected]:
            raise PathRehearsalError(
                f"after {phase}, {new} became structurally met; the one-body order requires {expected} next "
                f"(already {appeared or 'nothing'})")
        appeared.extend(new)
        order.append({"node": expected, "phase": phase, "ledger_head": head,
                      "structurally_met": list(met),
                      "met": {node: measured[node]["met"] for node in PATH_NODES}})
    phases.append({"phase": phase, "structurally_met": list(met), "ledger_head": head})
    return measured


def rehearse_path(*, directory: Path | None = None, kernel_root: Path | None = None) -> dict:
    """N3, then N4, then N7, structurally, on one throwaway rehearsal body.

    The founder's path does not move: the body is marked before the throwaway key exists, and every mission's
    founder expression opens with ``LABEL``. Separate bodies are not produced and would not satisfy the result:
    ``order`` names three heads of this one ledger, each the first moment that node was structurally met.
    """
    from greg import sop, venture_books
    from greg.body import Body, init_body
    from greg.founder import generate_founder_key, load_founder_key
    started = time.monotonic()
    work = _rehearsal_work(directory, "greg-rehearsal-path-")
    kernel = Path(kernel_root or Path(__file__).resolve().parents[1]).resolve()
    if (work / "body").exists():
        raise FileExistsError(f"{work / 'body'} exists; a path rehearsal always starts from a new body")
    work.mkdir(parents=True, exist_ok=True)
    home = work / "body"
    config = init_body(home, read_roots=[str(kernel)])
    mark_body(home)
    keyfile = work / f"{REHEARSAL}-throwaway-founder-key.pem"
    public = generate_founder_key(keyfile, None)
    key = load_founder_key(keyfile, None)
    body_id = config["body_id"]
    with Body(home) as enrolling:
        enrolling.enroll_founder(public)
    clock = _Clock()
    appeared, order, phases = [], [], []
    body = Body(home, clock=clock).open()
    try:
        body.boot()
        _post(home, key, body_id, clock, "BODY_DESIGNATE", {"purpose": "first_founder_body"})
        _tick(body, clock, 1)
        taught = []
        for n in range(3):
            taught.append(_run_case(home, key, body_id, clock, body,
                                    _case_spec(home, n, "leases", approve_writes=True)))
            _note(f"taught_case_{n}", body.journal, appeared, order, phases)
        proposals = [event.payload for event in body.journal.replay("sop.proposed")]
        if len(proposals) != 1:
            raise PathRehearsalError(f"expected one SOP proposal from the three teaching cases, got {len(proposals)}")
        proposal = proposals[0]
        _post(home, key, body_id, clock, "SOP_RATIFY",
              {"procedure_id": proposal["procedure_id"], "pre_approve": ["draft-offer", "record-settlement"]})
        _tick(body, clock, 1)
        ratified = sop.ratified(body.journal).get(proposal["procedure_id"])
        if not ratified:
            rejected = [event.payload for event in body.journal.replay("command.rejected")]
            raise PathRehearsalError(f"SOP_RATIFY was not accepted; rejected={rejected[-1] if rejected else None}")
        record = ratified["record"]
        _note("ratified", body.journal, appeared, order, phases)
        for n in (1, 2, 3):
            spec = sop.instantiate(
                record, {"reference": f"CASE-AUDIT-{n:02d}", "buyer": f"Audit client {n}",
                         "offer": f"an audit memo {n}", "price": "300.00",
                         "acceptance": "memo within 5 business days"},
                venture="audits", now=datetime.now(timezone.utc))
            if not str(spec.get("founder_expression", "")).startswith(LABEL):
                raise PathRehearsalError("a run of the ratified procedure dropped the rehearsal label")
            _run_case(home, key, body_id, clock, body, spec)
            _note(f"sop_run_{n}", body.journal, appeared, order, phases)
        if [row["node"] for row in order] != ["N3", "N4"]:
            from greg import path as devpath
            detail = devpath.sop_compounding(body.journal)
            raise PathRehearsalError(
                f"N4 did not follow N3 on this body; order so far is {[row['node'] for row in order]}; "
                f"sop missing={detail.get('incomplete') or detail.get('missing')}")
        before = _measure(body.journal)
        if before["N7"]["structurally_met"]:
            raise PathRehearsalError("N7 was structurally met before any treasury requirements were signed")
        tiers = venture_books.load_waterfall()
        _post(home, key, body_id, clock, "TREASURY_REQUIREMENTS",
              {"venture": "audits", "currency": "USD",
               "requirements": {tiers[0]: "120", tiers[3]: "80"}})
        _tick(body, clock, 1)
        final = _note("treasury", body.journal, appeared, order, phases)
        chain_ok, chain_why = body.ledger.verify_chain()
    finally:
        body.close()
    if [row["node"] for row in order] != list(PATH_NODES):
        raise PathRehearsalError(f"the one-body sequence is {[row['node'] for row in order]}, not {list(PATH_NODES)}")
    if not all(final[node]["structurally_met"] and not final[node]["met"] for node in PATH_NODES):
        raise PathRehearsalError(f"structural exit on the throwaway body was {final}")
    if not chain_ok:
        raise PathRehearsalError(f"the rehearsal ledger chain did not verify: {chain_why}")
    return {"label": REHEARSAL, "mode": "path", "directory": str(work), "home": str(home),
            "throwaway_key": str(keyfile), "kernel_root": str(kernel), "one_body": True,
            "taught_missions": taught, "sequence": [row["node"] for row in order], "order": order,
            "phases": phases, "nodes": final, "ledger_chain_verified": chain_ok,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "counts_toward_vepmc": False, "authenticates_founder": False, "founder_tier": False,
            "used": {"network": False, "models": False, "money": False, "messages": False,
                     "payment_provider": False, "founder_key": False}}


def main(args) -> int:
    if getattr(args, "path", False):
        try:
            result = rehearse_path(directory=Path(args.dir) if args.dir else None,
                                   kernel_root=Path(args.kernel_root) if args.kernel_root else None)
        except (PathRehearsalError, FileExistsError, RehearsalDirError) as exc:
            print(json.dumps({"label": REHEARSAL, "mode": "path", "ok": False, "error": str(exc)}, indent=1))
            return 1
        print(json.dumps(result, indent=1))
        ok = result["sequence"] == list(PATH_NODES) and result["one_body"] is True
        if args.console and ok:
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
        return 0 if ok else 1
    try:
        result = rehearse(directory=Path(args.dir) if args.dir else None,
                          kernel_root=Path(args.kernel_root) if args.kernel_root else None,
                          effort_budget=args.effort)
    except RehearsalDirError as exc:
        print(json.dumps({"label": REHEARSAL, "ok": False, "error": str(exc)}, indent=1))
        return 1
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
