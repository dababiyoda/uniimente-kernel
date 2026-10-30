"""A founder-signed backup cadence for this body, each backup proven by a restore drill (WU-14).

The effect is that the loss of the body's disk or computer is survivable from a known recovery point that has been
shown to restore. It is a standing mission over two capabilities, so it needs no body command and grants nothing by
itself; without a signed mission nothing is ever backed up:

- ``body.backup_status`` (read_only) observes whether the latest verified backup to the signed store is younger than
  the signed recovery-point objective (``rpo_seconds``).
- ``body.backup`` (internal_write) does three things, in order:
  - writes one Institutional Seed of this body (``foundry.systems.seed``, private keys excluded) to exactly the store
    the founder signed as its target;
  - restores that seed into a scratch home with ``greg.recovery.drill``, which re-verifies the restored ledger,
    reports the head it was restored to and removes the scratch home;
  - returns the seed, its head and the head the drill restored. The Gate's positive receipt of that output on the
    body's own ledger is the record that the backup is verified; a seed that does not restore raises, so the action
    fails and no such receipt exists. ``body.backup_status`` reads only those receipts, never a file in the store.

The store is the signed target ``backup:<absolute path>``; no parameter can move it. A store inside the body home or
inside a read root is refused, so a backup never lands where the body or a mission reads.

``mission`` builds the spec for the founder to review and sign (``python -m greg.backup --store DIR > backup.json``,
then ``greg mission submit backup.json``).

Limits:

- The recovery point is the instant just before the backup's own dispatch began (``before_dispatch``), so a restored
  body finds no interrupted backup to reconcile; the records of that dispatch itself are after the recovery point.
- A recovery point is at most the RPO plus the mission's cadence old.
- An unwritable store, or a drill that fails, fails the action; the mission then asks the founder once, and the body
  keeps running.
- Off-site stores, encryption at rest and a schedule verified across a reboot are not here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

PREFIX = "backup:"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _refused(message: str):
    from greg.capabilities import CapabilityError    # imported here: greg.capabilities registers this module
    return CapabilityError(message)


def _iso(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


def _home(ctx) -> Path:
    """The body home above this mission's workspace (it holds body.json)."""
    workspace = Path(ctx.workspace).resolve()
    home = next((p for p in workspace.parents if (p / "body.json").is_file()), None)
    if home is None:
        raise _refused("no body home above this mission's workspace")
    return home


def _store(ctx) -> Path:
    """The signed store: the target ``backup:<absolute path>``, outside the body home and every read root."""
    target = ctx.target or ""
    raw = target[len(PREFIX):] if target.startswith(PREFIX) else ""
    if not raw or not Path(raw).is_absolute():
        raise _refused(f"the signed target {target!r} must be backup:<absolute path>")
    store = Path(raw).resolve()
    for name, root in (("the body home", _home(ctx)), *(("a read root", Path(r).resolve()) for r in ctx.read_roots)):
        if store == root or root in store.parents:
            raise _refused(f"the backup store {store} is inside {name} ({root}); a backup is written only outside "
                           "the body and every read root")
    return store


def _reader(home: Path):
    from provenance.ledger import EvidenceLedger
    config = json.loads((home / "body.json").read_text())
    return EvidenceLedger(config["constitution_hash"], str(home / "ledger.jsonl"), read_only=True, tail="ignore")


def before_dispatch(home: Path, grant_id: str) -> str | None:
    """The head just before the dispatch holding ``grant_id`` began (its ``mission.dispatching`` record), or None.

    A seed taken there holds none of the backup's own dispatch, so a body restored from it finds no interrupted
    action to reconcile: once resumed, its mission simply takes the next backup."""
    if not grant_id:
        return None
    ledger = _reader(home)
    try:
        grant = next(iter(ledger.select("event", grant_id=grant_id)), None)
        proposal = grant.payload.get("proposal_id") if grant is not None else None
        began = next((r for r in reversed(ledger.select("event", type="greg.mission.dispatching"))
                      if proposal and (r.payload.get("payload") or {}).get("proposal_id") == proposal), None)
        return ledger.records[began.seq - 1].hash if began is not None else None
    finally:
        ledger.close()


def backup(params, ctx) -> dict:
    """Write one seed of this body to the signed store and prove it restores; the Gate's receipt of this output, on
    the body's own ledger, is the record that the backup is verified."""
    from foundry.systems import seed
    from greg.recovery import drill
    store = _store(ctx)
    try:
        store.mkdir(parents=True, exist_ok=True)
        home = _home(ctx)
        made = seed.make_seed(home, store, end=before_dispatch(home, ctx.grant_id))
    except Exception as exc:                     # noqa: BLE001 - unwritable or damaged store, unverifiable ledger
        raise _refused(f"no seed of this body could be written to {store}: {type(exc).__name__}: {exc}") from exc
    try:
        proof = drill(store, made["seed"])
    except Exception as exc:                     # noqa: BLE001 - a seed that does not restore is not a backup
        raise _refused(f"the restore drill of seed {made['seed']} failed, so it is not a verified backup: "
                       f"{type(exc).__name__}: {exc}") from exc
    return {"store": str(store), "seed": made["seed"], "files": made["files"], "backed_up_at": made["backed_up_at"],
            "ledger_head": made["ledger_head"], "restored_head": proof["restored_head"],
            "restored_records": proof["restored_records"], "held": proof["held"],
            "drill_seconds": proof["drill_seconds"], "verified_at": _iso(_now())}


def verified(home: Path, store: Path) -> list[dict]:
    """Every verified backup to ``store`` the body's own ledger holds, oldest first: the output of each positive Gate
    receipt for a ``body.backup`` dispatch whose witness names exactly this store. A file in the store is never
    evidence of a backup; only the body's ledger is."""
    ledger = _reader(home)
    try:
        rows = []
        for witness in ledger.select("witness", capability="body.backup", target=PREFIX + str(store)):
            for receipt in ledger.select("receipt", witness_id=witness.payload["witness_id"]):
                result = receipt.payload.get("result") or {}
                output = result.get("output")
                if result.get("result_class") == "positive" and isinstance(output, dict) and output.get("verified_at"):
                    rows.append((receipt.seq, output))
    finally:
        ledger.close()
    return [output for _, output in sorted(rows, key=lambda row: row[0])]


def status(params, ctx) -> dict:
    """Whether the recovery point of the latest verified backup to the signed store is younger than ``rpo_seconds``."""
    store = _store(ctx)
    rpo = params.get("rpo_seconds")
    if type(rpo) is not int or rpo <= 0:
        raise _refused("rpo_seconds must be a positive integer")
    rows = verified(_home(ctx), store)
    if not rows:
        return {"store": str(store), "rpo_seconds": rpo, "fresh": False, "latest": None, "age_seconds": None}
    latest = rows[-1]                            # the recovery point's age is what a loss now would cost
    age = (_now() - datetime.fromisoformat(latest["backed_up_at"].replace("Z", "+00:00"))).total_seconds()
    return {"store": str(store), "rpo_seconds": rpo, "fresh": age <= rpo, "age_seconds": round(age, 3),
            "latest": {k: latest[k] for k in ("seed", "backed_up_at", "ledger_head", "restored_head", "verified_at")}}


def mission(*, store: str | Path, rpo_seconds: int = 86400, cadence_seconds: int = 3600,
            horizon_days: float = 30, mission_id: str = "m:backup") -> dict:
    """A standing backup mission for the founder to review and sign: nothing is backed up until it is signed."""
    store = Path(store).expanduser()
    if not store.is_absolute():
        raise ValueError("the backup store must be an absolute path")
    target = PREFIX + str(store.resolve())
    return {
        "mission_id": mission_id,
        "founder_expression": f"Back up my body to {store} so that losing this disk or computer is survivable, "
                              "and prove that every backup restores.",
        "intended_effect": f"a verified backup no older than {rpo_seconds} seconds, plus the cadence, is always "
                           f"in {store}; each one was restored in a scratch home and its ledger re-verified",
        "beneficiaries": ["Alfonso"],
        "unacceptable_outcomes": ["a backup inside the body home or a read root", "a private key in a backup",
                                  "a backup recorded as verified that did not restore"],
        "priority": 60,
        "closure": {"kind": "infinite", "cadence_seconds": cadence_seconds},
        "success_checks": [{
            "check_id": "verified-backup-fresh",
            "description": f"the latest verified backup in {store} is at most {rpo_seconds} seconds old",
            "sensor": {"capability": "body.backup_status", "params": {"rpo_seconds": rpo_seconds}, "target": target},
            "predicate": {"op": "equals", "field": "fresh", "value": True}}],
        "strategies": [{
            "action_id": "backup", "capability": "body.backup", "params": {}, "target": target,
            "advances": ["verified-backup-fresh"],
            "rationale": "write one seed of this body to the signed store and prove it restores"}],
        "light_cone": {"capabilities": ["body.backup_status", "body.backup"], "targets": [target],
                       "max_consequence_class": "internal_write", "budget_usd": 0,
                       "horizon": _iso(_now() + timedelta(days=horizon_days))},
    }


def builtin_entries(manifest_type, lazy) -> dict:
    """The two manifests, registered with every other built-in (greg/capabilities.py)."""
    source = {"source": "uniimente-kernel/greg/backup.py",
              "mechanism_from": "foundry/systems/seed.py (#46) and greg/recovery.py restore_body"}
    tests = ("tests/unit/test_greg_backup.py", "tests/integration/test_greg_backup_process.py")
    return {
        "body.backup": (manifest_type(
            capability_id="body.backup", version="1.0.0", provider="greg-builtin", function="body.backup",
            description="Write one Institutional Seed of this body (private keys excluded) to the founder-signed "
                        "store and prove it restores in a scratch home",
            route="internal", consequence_class="internal_write", target_prefix=PREFIX,
            inputs={"none": "no parameters"},
            outputs={"seed": "str", "ledger_head": "str", "restored_head": "str", "held": "bool"},
            filesystem="named-write", strengthens=("reliability", "proof"), tests=tests, provenance=source),
            lazy("greg.backup", "backup")),
        "body.backup_status": (manifest_type(
            capability_id="body.backup_status", version="1.0.0", provider="greg-builtin",
            function="body.backup_status",
            description="Whether the latest verified backup to the signed store is younger than the signed RPO",
            route="internal", consequence_class="read_only", target_prefix=PREFIX,
            inputs={"rpo_seconds": "int > 0"},
            outputs={"fresh": "bool", "age_seconds": "float|null", "latest": "dict|null"}, retry_safe=True,
            strengthens=("reliability", "proof"), tests=tests, provenance=source),
            lazy("greg.backup", "status")),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="print a standing backup mission for the founder to sign")
    parser.add_argument("--store", required=True, help="absolute path of the store, outside the body home")
    parser.add_argument("--rpo-hours", type=float, default=24.0)
    parser.add_argument("--cadence-seconds", type=int, default=3600)
    parser.add_argument("--horizon-days", type=float, default=30)
    args = parser.parse_args()
    print(json.dumps(mission(store=args.store, rpo_seconds=int(args.rpo_hours * 3600),
                             cadence_seconds=args.cadence_seconds, horizon_days=args.horizon_days), indent=1))
