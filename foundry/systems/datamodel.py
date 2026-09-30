"""#4 Institutional data model: one SQLite store joining intelligence, authority, action, outcome and money.

SQLite is the mature substrate (single file, transactional, zero operations). What
UNIIMENTE adds is the model and its discipline:

  - tables for signals, decisions, authority, actions, outcomes, customers and money;
  - migrations are numbered, checksummed and reversible; a down migration exports
    the data it removes to a backup file and the next up migration restores it, so
    moving between versions never loses rows;
  - GREG's journal is ingested idempotently by event id (re-ingesting is a no-op);
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
        "CREATE VIEW mission_ledger AS SELECT d.mission_id, d.expression, "
        "(SELECT group_concat(a.answer, ',') FROM authority a WHERE a.mission_id = d.mission_id) AS authority, "
        "(SELECT count(*) FROM actions x WHERE x.mission_id = d.mission_id AND x.status = 'DONE') AS actions_done, "
        "(SELECT coalesce(sum(x.cost_usd), 0) FROM actions x WHERE x.mission_id = d.mission_id) AS cost_usd, "
        "(SELECT o.verdict FROM outcomes o WHERE o.mission_id = d.mission_id ORDER BY o.at DESC, o.id DESC LIMIT 1) "
        "AS last_verdict, "
        "(SELECT coalesce(sum(m.amount_cents), 0) FROM money m WHERE m.mission_id = d.mission_id) AS revenue_cents "
        "FROM decisions d",
    ], ["DROP VIEW mission_ledger", "DROP INDEX actions_mission"], []),
]


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
        return {"rows_changed": db.total_changes - before}
    finally:
        db.close()


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
