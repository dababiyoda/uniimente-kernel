"""#4 Institutional data model: one SQLite store joining intelligence, authority, action, outcome and money.

SQLite is the mature substrate (single file, transactional, zero operations). What
UNIIMENTE adds is the model and its discipline:

  - tables for signals, decisions, authority, actions, outcomes, customers and money;
  - migrations are numbered, checksummed and reversible; a down migration exports
    the data it removes to a backup file and the next up migration restores it, so
    moving between versions never loses rows;
  - GREG's journal is ingested idempotently by event id (re-ingesting is a no-op), and what it says about each
    mission's closures is read in the journal's own order: each event's ledger position (``seq``), which GREG's
    export carries (greg/journal.py ``foundry_events``), never the wall clock, which a correction can set back;
  - ``mission_ledger`` answers, per mission, what was intended, who authorized it,
    what was done at what cost, what reality said, and what money moved.

The ledger stays the source of truth; this is a queryable projection rebuilt
from it at any time.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

# Migration 3's view, kept byte for byte (an applied migration is checksummed): its ``last_verdict`` is the verdict of
# the mission's latest outcome row, whatever closure that row judged. Migration 4 replaces it with ``current_verdict``.
V3_LEDGER_VIEW = (
    "CREATE VIEW mission_ledger AS SELECT d.mission_id, d.expression, "
    "(SELECT group_concat(a.answer, ',') FROM authority a WHERE a.mission_id = d.mission_id) AS authority, "
    "(SELECT count(*) FROM actions x WHERE x.mission_id = d.mission_id AND x.status = 'DONE') AS actions_done, "
    "(SELECT coalesce(sum(x.cost_usd), 0) FROM actions x WHERE x.mission_id = d.mission_id) AS cost_usd, "
    "(SELECT o.verdict FROM outcomes o WHERE o.mission_id = d.mission_id ORDER BY o.at DESC, o.id DESC LIMIT 1) "
    "AS last_verdict, "
    "(SELECT coalesce(sum(m.amount_cents), 0) FROM money m WHERE m.mission_id = d.mission_id) AS revenue_cents "
    "FROM decisions d")
MIGRATIONS = [
    (1, "core", [
        "CREATE TABLE signals (id TEXT PRIMARY KEY, at TEXT, source TEXT, content TEXT, evidence TEXT)",
        "CREATE TABLE decisions (id TEXT PRIMARY KEY, mission_id TEXT UNIQUE, at TEXT, expression TEXT)",
        "CREATE TABLE authority (id TEXT PRIMARY KEY, mission_id TEXT, request_id TEXT, capability TEXT, "
        "requested_at TEXT, answer TEXT, answered_at TEXT)",
        "CREATE TABLE actions (id TEXT PRIMARY KEY, mission_id TEXT, at TEXT, capability TEXT, status TEXT, "
        "receipt TEXT, cost_usd REAL)",
        "CREATE TABLE outcomes (id TEXT PRIMARY KEY, mission_id TEXT, at TEXT, verdict TEXT)",
    ], ["DROP TABLE outcomes", "DROP TABLE actions", "DROP TABLE authority", "DROP TABLE decisions",
        "DROP TABLE signals"], ["signals", "decisions", "authority", "actions", "outcomes"]),
    (2, "customers and money", [
        "CREATE TABLE customers (id TEXT PRIMARY KEY, name TEXT, first_seen TEXT)",
        "CREATE TABLE money (id TEXT PRIMARY KEY, at TEXT, mission_id TEXT, customer_id TEXT REFERENCES customers(id), "
        "amount_cents INTEGER NOT NULL, currency TEXT NOT NULL, kind TEXT NOT NULL, evidence TEXT NOT NULL)",
    ], ["DROP TABLE money", "DROP TABLE customers"], ["customers", "money"]),
    (3, "mission ledger view", [
        "CREATE INDEX actions_mission ON actions(mission_id)",
        V3_LEDGER_VIEW,
    ], ["DROP VIEW mission_ledger", "DROP INDEX actions_mission"], []),
    # The outcome that stands for each mission's current closure (greg/appraisal.py ``standings``): an appraisal counts
    # only for the closure it judged, and a final UNAVAILABLE establishes nothing. ``last_verdict`` read the latest
    # outcome row, so a late verdict on an earlier closure replaced the standing of a newer one (founder ruling of
    # 2026-11-12: "A stale appraisal cannot qualify a different closure"). ``closure_facts`` keeps every fact that
    # rule reads (registrations, closures, appraisals with the closure each names), one row per event id with its
    # ledger position (``seq``) when it was handed over with one, and ``standings`` is derived from all of them after
    # every ingest and on this migration (``_derive_standings``), each mission's facts in ledger order: it is a
    # function of the facts the model holds, not of the order or grouping of the ingest calls that brought them.
    # ``bound`` is 0 only on an appraisal row carried from schema 3's ``outcomes``, which kept no closures: the
    # closure it judged is unknown until the journal is ingested again. (``seq`` was added before this migration left
    # its draft branch; a model built at the draft's first version of it is refused by its checksum.)
    (4, "closure standings", [
        "CREATE TABLE closure_facts (id TEXT PRIMARY KEY, mission_id TEXT, at TEXT, kind TEXT, closure_event TEXT, "
        "verdict TEXT, bound INTEGER NOT NULL, seq INTEGER)",
        "CREATE TABLE standings (mission_id TEXT PRIMARY KEY, closure TEXT, outcome_id TEXT, verdict TEXT, "
        "basis TEXT)",
        "DROP VIEW mission_ledger",
        "CREATE VIEW mission_ledger AS SELECT d.mission_id, d.expression, "
        "(SELECT group_concat(a.answer, ',') FROM authority a WHERE a.mission_id = d.mission_id) AS authority, "
        "(SELECT count(*) FROM actions x WHERE x.mission_id = d.mission_id AND x.status = 'DONE') AS actions_done, "
        "(SELECT coalesce(sum(x.cost_usd), 0) FROM actions x WHERE x.mission_id = d.mission_id) AS cost_usd, "
        "(SELECT s.verdict FROM standings s WHERE s.mission_id = d.mission_id) AS current_verdict, "
        "(SELECT s.basis FROM standings s WHERE s.mission_id = d.mission_id) AS current_basis, "
        "(SELECT coalesce(sum(m.amount_cents), 0) FROM money m WHERE m.mission_id = d.mission_id) AS revenue_cents "
        "FROM decisions d",
    ], ["DROP VIEW mission_ledger", V3_LEDGER_VIEW, "DROP TABLE standings", "DROP TABLE closure_facts"],
     ["closure_facts"]),
]
# The facts ``standings`` reads, and what a standing row says it rests on.
CLOSURE_FACTS = ("mission.registered", "mission.held", "mission.achieved", "mission.unmet", "mission.appraised")
FROM_CLOSURES = "closure"
CLOCK_ORDER = ("closure, in recorded-time order: some of this mission's closure facts were handed over without their "
               "ledger position (seq), so they are read in (at, event id) order, and a wall clock set back can put a "
               "newer closure before an older one; hand them over again from greg.journal.foundry_events")
UNBOUND = ("unbound: appraisals ingested under schema 3, which kept no closures, cannot be bound to the closure each "
           "judged; ingest the journal again to derive the standing")


class ModelError(RuntimeError):
    pass


def _checksum(up: list[str]) -> str:
    return hashlib.sha256("\n".join(up).encode()).hexdigest()[:16]


def connect(root: Path) -> sqlite3.Connection:
    Path(root).mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(Path(root) / "institution.sqlite")
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name TEXT, checksum TEXT)")
    return db


def version(db) -> int:
    return db.execute("SELECT coalesce(max(version), 0) FROM schema_migrations").fetchone()[0]


def migrate(root: Path, to: int) -> dict:
    known = {v for v, *_ in MIGRATIONS}
    if to != 0 and to not in known:
        raise ModelError(f"unknown schema version {to}")
    db = connect(root)
    try:
        for v, name, up, _, _ in MIGRATIONS:   # applied migrations must not have been edited since
            row = db.execute("SELECT checksum FROM schema_migrations WHERE version = ?", (v,)).fetchone()
            if row and row[0] != _checksum(up):
                raise ModelError(f"migration {v} changed after it was applied (checksum mismatch)")
        steps = []
        with db:
            while version(db) < to:
                v, name, up, _, tables = MIGRATIONS[version(db)]
                for sql in up:
                    db.execute(sql)
                backup = Path(root) / f"backup-v{v}.json"
                if backup.exists():                    # restore what the down migration exported
                    for table, rows in json.loads(backup.read_text()).items():
                        for r in rows:
                            db.execute(f"INSERT INTO {table} VALUES ({','.join('?' * len(r))})", r)
                    backup.unlink()
                if v in AFTER_UP:                      # derived from what is stored now, the restored rows included
                    AFTER_UP[v](db)
                db.execute("INSERT INTO schema_migrations VALUES (?, ?, ?)", (v, name, _checksum(up)))
                steps.append(f"up {v}")
            while version(db) > to:
                v, name, _, down, tables = MIGRATIONS[version(db) - 1]
                export = {t: [list(r) for r in db.execute(f"SELECT * FROM {t} ORDER BY rowid")] for t in tables}
                if any(export.values()):
                    (Path(root) / f"backup-v{v}.json").write_text(json.dumps(export))
                for sql in down:
                    db.execute(sql)
                db.execute("DELETE FROM schema_migrations WHERE version = ?", (v,))
                steps.append(f"down {v}")
        return {"version": version(db), "steps": steps}
    finally:
        db.close()


def ingest_greg(root: Path, events: list[dict]) -> dict:
    db = connect(root)
    if version(db) < 3:
        db.close()
        raise ModelError("schema is not at the current version; migrate first")
    events = list(events)
    before = db.total_changes
    requested = {}
    try:
        with db:
            for e in sorted(events, key=lambda e: (e["at"], e["event_id"])):
                kind, p, eid = e["type"].removeprefix("greg."), e["payload"], e["event_id"]
                if kind == "mission.registered":
                    db.execute("INSERT OR IGNORE INTO decisions VALUES (?,?,?,?)",
                               (eid, p["mission_id"], e["at"], (p.get("spec") or {}).get("founder_expression", "")))
                elif kind == "decision.requested":
                    requested[p["request_id"]] = eid
                    db.execute("INSERT OR IGNORE INTO authority VALUES (?,?,?,?,?,?,?)",
                               (p["request_id"], p.get("mission_id"), p["request_id"],
                                (p.get("authority_requested") or {}).get("capability"), e["at"], None, None))
                elif kind == "decision.answered":
                    db.execute("UPDATE authority SET answer = ?, answered_at = ? WHERE request_id = ? "
                               "AND (answer IS NOT ? OR answered_at IS NOT ?)",
                               (p.get("answer"), e["at"], p["request_id"], p.get("answer"), e["at"]))
                elif kind == "mission.action":
                    db.execute("INSERT OR IGNORE INTO actions VALUES (?,?,?,?,?,?,?)",
                               (eid, p["mission_id"], e["at"], p.get("capability"), p.get("status"), p.get("receipt"),
                                float(p.get("cost_usd") or 0.0)))
                elif kind == "mission.appraised":
                    db.execute("INSERT OR IGNORE INTO outcomes VALUES (?,?,?,?)", (eid, p["mission_id"], e["at"],
                                                                                  p.get("verdict")))
                elif kind == "external.ingested":
                    db.execute("INSERT OR IGNORE INTO signals VALUES (?,?,?,?,?)",
                               (eid, e["at"], p.get("source"), json.dumps(p.get("summary") or p.get("content")),
                                json.dumps(p.get("evidence"))))
            if version(db) >= 4:
                for e in events:
                    kind, p = e["type"].removeprefix("greg."), e["payload"]
                    if kind not in CLOSURE_FACTS:
                        continue
                    seq = _position(e)
                    held = db.execute("SELECT seq FROM closure_facts WHERE id = ?", (e["event_id"],)).fetchone()
                    if seq is not None and held is not None and held[0] is not None and held[0] != seq:
                        raise ModelError(f"event {e['event_id']} was handed over at ledger position {seq}, but the "
                                         f"model holds it at {held[0]}: one model follows one ledger's order; "
                                         "rebuild it from that ledger")
                    # the fact as recorded; it replaces only a row carried unbound
                    db.execute("INSERT INTO closure_facts VALUES (?,?,?,?,?,?,1,?) ON CONFLICT(id) DO UPDATE SET "
                               "mission_id = excluded.mission_id, at = excluded.at, kind = excluded.kind, "
                               "closure_event = excluded.closure_event, verdict = excluded.verdict, bound = 1, "
                               "seq = coalesce(closure_facts.seq, excluded.seq) "
                               "WHERE closure_facts.bound = 0",
                               (e["event_id"], p.get("mission_id"), e["at"], kind, p.get("closure_event"),
                                p.get("verdict"), seq))
                    if seq is not None:           # a fact handed over again with its position gains it
                        db.execute("UPDATE closure_facts SET seq = ? WHERE id = ? AND seq IS NULL",
                                   (seq, e["event_id"]))
                _derive_standings(db)
        return {"rows_changed": db.total_changes - before}
    finally:
        db.close()


def _position(event: dict):
    """The event's ledger position as handed over (``seq``: greg/journal.py ``foundry_events``), or None."""
    seq = event.get("seq")
    return seq if type(seq) is int and seq >= 0 else None


def _derive_standings(db) -> None:
    """Each mission's current closure (its achievement, or its newest closure) and the outcome that stands for it,
    derived by greg/appraisal.py ``standings`` from every closure fact the model holds, each mission's facts in their
    ledger order (``seq``), as greg's own standings reads them. So it depends only on the set of facts ingested,
    never on the order or grouping of the ingest calls; re-ingesting what the model holds changes nothing. The
    verdict is NULL while that closure has no verdict of its own.

    The one fallback: a mission with a fact that was handed over without its position is folded in (at, event id)
    order and its basis says so (``CLOCK_ORDER``). That order is the ledger's only while the wall clock never went
    back: after a correction (an NTP step, a restored virtual machine, a manual change) a newer closure stamped
    earlier sorts first, so the row can show an older closure's verdict for a mission whose current closure has none
    (a stale appraisal standing for a different closure), or leave an appraisal stamped before the closure it names
    unbound; equal stamps fall to the event id, not the ledger. Handing the facts over again with their positions
    ends it. A mission with an appraisal row carried unbound from schema 3 gets no verdict and the ``UNBOUND`` basis:
    the closure that row judged is unknown, and reading it as the latest row would let a late verdict on an earlier
    closure stand for a newer one (founder ruling of 2026-11-12)."""
    from greg.appraisal import standings_of_events
    facts = db.execute("SELECT id, mission_id, at, kind, closure_event, verdict, bound, seq FROM closure_facts")
    unbound, missions = set(), {}
    for fact in facts:
        if not fact[6]:
            unbound.add(fact[1])
        missions.setdefault(fact[1], []).append(fact)
    ordered, clock = [], set()
    for mid, rows in missions.items():
        if mid in unbound:
            continue
        if all(seq is not None for *_, seq in rows):
            rows.sort(key=lambda f: (f[7], f[0]))                 # the ledger's order
        else:
            clock.add(mid)
            rows.sort(key=lambda f: (f[2], f[0]))                 # the fallback: (at, event id)
        ordered += rows
    book = standings_of_events(
        {"type": "greg." + kind, "event_id": eid,
         "payload": {"mission_id": mid, **({"closure_event": named} if named else {}),
                     **({"verdict": verdict} if verdict is not None else {})}}
        for eid, mid, _, kind, named, verdict, _, _ in ordered)
    derived = {mid: (None, None, None, UNBOUND) for mid in unbound}
    for mid in book.missions():
        current = book.current(mid)
        stands = current.standing
        derived[mid] = (current.event_id or "achievement", stands.event_id if stands is not None else None,
                        current.verdict, CLOCK_ORDER if mid in clock else FROM_CLOSURES)
    for mid, row in derived.items():
        db.execute("INSERT INTO standings VALUES (?,?,?,?,?) ON CONFLICT(mission_id) DO UPDATE SET "
                   "closure = excluded.closure, outcome_id = excluded.outcome_id, verdict = excluded.verdict, "
                   "basis = excluded.basis WHERE closure IS NOT excluded.closure OR outcome_id IS NOT "
                   "excluded.outcome_id OR verdict IS NOT excluded.verdict OR basis IS NOT excluded.basis",
                   (mid, *row))


def _from_schema_3(db) -> None:
    """Migration 4's derivation from what a schema-3 model stores: each registration (``decisions``) as a closure
    fact, and each appraisal row (``outcomes``) as one whose closure is unknown (``bound`` 0), unless the fact itself
    is already held (restored from a down migration's backup). Then ``_derive_standings``."""
    db.execute("INSERT OR IGNORE INTO closure_facts SELECT id, mission_id, at, 'mission.registered', NULL, NULL, 1, "
               "NULL FROM decisions")
    db.execute("INSERT OR IGNORE INTO closure_facts SELECT id, mission_id, at, 'mission.appraised', NULL, verdict, 0, "
               "NULL FROM outcomes")
    _derive_standings(db)


AFTER_UP = {4: _from_schema_3}       # run by ``migrate`` after a migration's up statements and backup restore


def record_money(root: Path, *, id: str, at: str, mission_id: str, customer: dict, amount_cents: int,
                 currency: str, kind: str, evidence: str) -> dict:
    if not evidence:
        raise ModelError("money without evidence is not recorded")
    if not isinstance(amount_cents, int):
        raise ModelError("money is integer cents")
    db = connect(root)
    try:
        with db:
            db.execute("INSERT OR IGNORE INTO customers VALUES (?,?,?)", (customer["id"], customer["name"], at))
            db.execute("INSERT INTO money VALUES (?,?,?,?,?,?,?,?)",
                       (id, at, mission_id, customer["id"], amount_cents, currency, kind, evidence))
        return {"recorded": id}
    except sqlite3.IntegrityError as exc:
        raise ModelError(f"money record refused: {exc}") from None
    finally:
        db.close()


def mission_ledger(root: Path) -> list[dict]:
    db = connect(root)
    try:
        cols = [c[0] for c in db.execute("SELECT * FROM mission_ledger LIMIT 0").description]
        return [dict(zip(cols, r)) for r in db.execute("SELECT * FROM mission_ledger ORDER BY mission_id")]
    finally:
        db.close()


QUERY_OPS = {"mission_ledger": lambda a, r: {"missions": mission_ledger(r)},
             "version": lambda a, r: {"version": (lambda d: (version(d), d.close())[0])(connect(r))}}
APPLY_OPS = {"migrate": lambda a, r: migrate(r, int(a["to"])),
             "ingest_greg": lambda a, r: ingest_greg(r, a["events"]),
             "record_money": lambda a, r: record_money(r, **a)}


def exercise(root) -> dict:
    from foundry.systems.observability import sample_events
    root = Path(root)
    up = migrate(root, 3)
    first = ingest_greg(root, sample_events())
    again = ingest_greg(root, sample_events())
    record_money(root, id="pay-1", at="2026-09-12T12:00:00Z", mission_id="m:research",
                 customer={"id": "c-1", "name": "Distributor A"}, amount_cents=90000, currency="USD", kind="payment",
                 evidence="receipt:rc21")
    refusals = {}
    for label, kw in {"no_evidence": dict(evidence=""), "float_money": dict(amount_cents=10.5),
                      "duplicate": dict()}.items():
        try:
            record_money(root, **{**dict(id="pay-1", at="2026-09-12T12:00:00Z", mission_id="m:research",
                                         customer={"id": "c-1", "name": "Distributor A"}, amount_cents=90000,
                                         currency="USD", kind="payment", evidence="receipt:rc21"), **kw})
            refusals[label] = None
        except ModelError as exc:
            refusals[label] = str(exc)
    ledger = mission_ledger(root)
    down = migrate(root, 1)                 # money and customers leave the schema, exported to a backup
    backup_written = (root / "backup-v2.json").exists()
    back_up = migrate(root, 3)              # and come back intact
    restored = mission_ledger(root)
    return {"migrations": up["steps"], "rows_first_ingest": first["rows_changed"],
            "rows_second_ingest": again["rows_changed"], "refusals": refusals, "mission_ledger": ledger,
            "down": down["steps"], "backup_written": backup_written, "up_again": back_up["steps"],
            "lossless_round_trip": restored == ledger}
