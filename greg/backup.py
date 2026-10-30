"""A founder-signed backup cadence for this body, each backup proven by a restore drill (WU-14).

The effect is that the loss of the body's disk or computer is survivable from a known recovery point that has been
shown to restore. It is a standing mission over two capabilities, so it needs no body command and grants nothing by
itself; without a signed mission nothing is ever backed up:

- ``body.backup_status`` (read_only) observes whether the latest verified backup to the signed store is younger than
  the signed recovery-point objective (``rpo_seconds``, ``fresh``) and is still in the store: the store is there, its
  objects directory is a real directory of the store's filesystem, and the seed's manifest and every object it names
  still hash to their addresses. A store that is gone (a disk unplugged) or a backup that has rotted is never fresh.
  The mission's check reads ``current``: fresh, or the first read since the latest verified backup, when that backup
  was within the RPO as it was taken. The engine judges a backup by the next read of its check; a body stopped,
  asleep or paused between the backup and that read would otherwise find the backup it just took stale, blame the
  backup itself and stop the cadence on a founder ask although nothing failed. The read after it judges by age, so
  a backup is due again at most one cadence later.
- ``body.backup`` (internal_write) does three things, in order:
  - writes one Institutional Seed of this body (``foundry.systems.seed``, private keys excluded) to exactly the store
    the founder signed as its target;
  - restores that seed into a scratch home with ``greg.recovery.drill``, which re-verifies the restored ledger,
    requires the restored body to be held, reports the head it was restored to and removes the scratch home;
  - returns the seed, its head and the head the drill restored. The Gate's positive receipt of that output on the
    body's own ledger is the record that the backup is verified; a seed that does not restore raises, so the action
    fails and no such receipt exists. ``body.backup_status`` reads only those receipts, never a file in the store.

The store is the signed target ``backup:<absolute path>``, in canonical form (``mission`` writes it so); no parameter
can move it. It is refused:

- inside, or equal to, the body home or a read root, and when the body home or a read root is, or lies inside, the
  store's ``objects`` directory, where every object is written: a backup never lands where the body or a mission
  reads;
- when it does not exist: a backup never creates its store, because a missing mount point would put it on the body's
  own disk. The founder creates or mounts it;
- on a filesystem held in memory (``tmpfs``, ``ramfs``: ``VOLATILE``), which the next reboot empties, so it is no
  backup at all. The type is read from ``/proc/self/mountinfo``; where that is unavailable it is not checked;
- on the body's own filesystem, unless the founder signed ``accept_same_filesystem`` (such a backup survives a
  damaged body home, not the loss of the disk). What is compared is the filesystem (``st_dev``), not the disk: two
  filesystems of one disk (partitions, btrfs subvolumes) pass, and survive only what that disk survives;
- when its ``objects`` directory is a symbolic link, on another filesystem than the store, holds a link, or cannot be
  kept private. Every object of a backup lies under it, so it is created ``0700`` (or made so) and nobody but the
  body's user can read the body's history from the store;
- when the store or its ``objects`` directory changes while a backup is written (unmounted and recreated, say);
- when its path holds a glob character (``* ? [ ]``): light-cone targets are patterns, and such a path would not
  admit its own target, or would admit others.

``mission`` builds the spec for the founder to review and sign (``python -m greg.backup --store DIR > backup.json``,
then ``greg mission submit backup.json``).

Limits:

- The recovery point is the instant just before the backup's own dispatch began (``before_dispatch``), so a restored
  body finds no interrupted backup to reconcile; the records of that dispatch itself are after the recovery point.
- ``mission`` refuses an RPO shorter than twice the cadence. The cadence is how often the body reads the check, so
  the recovery point can pass the RPO by up to one cadence before the next backup; the rule keeps that overshoot to at
  most half the RPO. While the cadence runs, the latest recovery point is at most the RPO plus one cadence (plus a
  tick and a drill) old; after the body was stopped, asleep or paused, at most that long after it runs again.
- An unwritable store, or a drill that fails, fails the action; the mission then asks the founder once, and the body
  keeps running.
- ``body.backup_status`` re-hashes every object of the latest backup on every read: its cost grows with the backup.
- Off-site stores, encryption at rest and a schedule verified across a reboot are not here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import stat

PREFIX = "backup:"
ACCEPT = "accept_same_filesystem"               # the one signed parameter of body.backup
OBJECTS = "objects"                             # where foundry.systems.cas writes every object, under the store
VOLATILE = ("tmpfs", "ramfs")                   # filesystems held in memory: the next reboot empties them


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


GLOB = "*?[]"                                   # light-cone targets are fnmatch patterns (greg/lightcone.py)


def _store(ctx) -> Path:
    """The signed store: the target ``backup:<absolute path>`` in canonical form, outside the body home and every read
    root."""
    target = ctx.target or ""
    raw = target[len(PREFIX):] if target.startswith(PREFIX) else ""
    if not raw or not Path(raw).is_absolute():
        raise _refused(f"the signed target {target!r} must be backup:<absolute path>")
    if any(c in raw for c in GLOB):
        raise _refused(f"the backup store {raw!r} holds a glob character ({GLOB}); light-cone targets are patterns")
    store = Path(raw).resolve()
    if target != PREFIX + str(store):
        # Its verified backups are found by the exact target; any other spelling would back up unseen.
        raise _refused(f"the signed target {target!r} is not in canonical form; sign {PREFIX + str(store)!r}")
    objects = store / OBJECTS
    for name, root in (("the body home", _home(ctx)), *(("a read root", Path(r).resolve()) for r in ctx.read_roots)):
        if store == root or root in store.parents:
            raise _refused(f"the backup store {store} is inside {name} ({root}); a backup is written only outside "
                           "the body and every read root")
        if root == objects or objects in root.parents:
            raise _refused(f"{name} ({root}) lies inside the backup store's {OBJECTS} directory, where every object "
                           "of a backup is written; a backup is written only outside the body and every read root")
    return store


def _volatile(store: Path) -> str | None:
    """The store's filesystem type when it is held in memory (``VOLATILE``), from ``/proc/self/mountinfo``; None when
    it is not, or where the type cannot be read (not Linux)."""
    try:
        device = os.stat(store).st_dev
        mounts = Path("/proc/self/mountinfo").read_text()
    except OSError:
        return None
    wanted = f"{os.major(device)}:{os.minor(device)}"
    for line in mounts.splitlines():
        fields, _, rest = line.partition(" - ")
        if fields.split()[2:3] == [wanted] and rest.split()[:1]:
            return rest.split()[0] if rest.split()[0] in VOLATILE else None
    return None


def _objects(store: Path, device: int) -> tuple[int, int]:
    """Make ``<store>/objects`` ready to hold a backup and return its (device, inode): a real directory of the store's
    own filesystem (``device``), created ``0700`` or made so, holding no link. Every object is written under it, so a
    link there, or a separate mount, would put the whole backup somewhere no check looked, and a directory other users
    may enter would show them the body's history."""
    objects = store / OBJECTS
    try:
        os.mkdir(objects, 0o700)
    except FileExistsError:
        pass
    info = os.lstat(objects)
    if not stat.S_ISDIR(info.st_mode):
        raise _refused(f"{objects} is not a directory (a symbolic link?); every object of a backup is written there, "
                       "so it must be a real directory of the store")
    if info.st_dev != device:
        raise _refused(f"{objects} is on another filesystem than the store {store}; the store's checks would not "
                       "cover where the backup is written")
    if stat.S_IMODE(info.st_mode) & 0o077:
        try:
            os.chmod(objects, 0o700)
        except OSError:
            pass
        info = os.lstat(objects)
        if stat.S_IMODE(info.st_mode) & 0o077:
            raise _refused(f"{objects} cannot be made private (mode {stat.S_IMODE(info.st_mode):o}): other users could "
                           "read the body's history there; use a filesystem that keeps permissions, or mount it so "
                           "only this user can read it")
    with os.scandir(objects) as entries:
        links = sorted(e.name for e in entries if e.is_symlink())
    if links:
        raise _refused(f"{objects} holds symbolic links ({', '.join(links[:3])}); objects written through them would "
                       "land outside the store")
    return info.st_dev, info.st_ino


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
    if set(params) - {ACCEPT}:
        raise _refused(f"body.backup takes only {ACCEPT!r}, not {sorted(set(params) - {ACCEPT})}")
    accepted = params.get(ACCEPT) is True
    home = _home(ctx)
    before = _identity(store)
    if before is None:
        raise _refused(f"the backup store {store} is not an existing directory: mount or create it. A backup never "
                       "creates its store, because a missing mount point would put it on the body's own disk")
    volatile = _volatile(store)
    if volatile is not None:
        raise _refused(f"the backup store {store} is on a {volatile} filesystem, held in memory: the next reboot "
                       "empties it, so it is no backup. Use a store on a disk")
    same = before[0] == os.stat(home).st_dev
    if same and not accepted:
        raise _refused(f"the backup store {store} is on the body's own filesystem, so it does not survive the loss of "
                       f"this disk; use a store on another disk, or sign {ACCEPT}: true to accept it")
    objects = _objects(store, before[0])
    try:
        made = seed.make_seed(home, store, end=before_dispatch(home, ctx.grant_id))
    except Exception as exc:                     # noqa: BLE001 - unwritable or damaged store, unverifiable ledger
        raise _refused(f"no seed of this body could be written to {store}: {type(exc).__name__}: {exc}") from exc
    try:
        proof = drill(store, made["seed"])
    except Exception as exc:                     # noqa: BLE001 - a seed that does not restore is not a backup
        raise _refused(f"the restore drill of seed {made['seed']} failed, so it is not a verified backup: "
                       f"{type(exc).__name__}: {exc}") from exc
    if _identity(store) != before or _identity(store / OBJECTS, follow=False) != objects:
        raise _refused(f"the backup store {store} changed while the backup was written (unmounted or replaced), so "
                       "the seed is not where it was drilled")
    return {"store": str(store), "seed": made["seed"], "files": made["files"], "backed_up_at": made["backed_up_at"],
            "ledger_head": made["ledger_head"], "restored_head": proof["restored_head"],
            "restored_records": proof["restored_records"], "held": proof["held"], "same_filesystem": same,
            "not_packed": len(made["not_packed"]), "repaired_objects": len(made["repaired"]),
            "drill_seconds": proof["drill_seconds"], "verified_at": _iso(_now())}


def _identity(path: Path, *, follow: bool = True) -> tuple[int, int] | None:
    """The directory's (device, inode), or None when it is not an existing directory (with ``follow=False``, a link
    is not one)."""
    try:
        info = os.stat(path, follow_symlinks=follow)
    except OSError:
        return None
    return (info.st_dev, info.st_ino) if stat.S_ISDIR(info.st_mode) else None


def _gone(home: Path, store: Path, latest: dict) -> str | None:
    """Why the latest verified backup is no longer where it was verified, or None while it is."""
    identity = _identity(store)
    if identity is None:
        return "the store is not there (a disk unmounted or removed?)"
    if identity[0] == os.stat(home).st_dev and not latest.get("same_filesystem"):
        return "the store is now on the body's own filesystem (its disk is no longer mounted?)"
    objects = _identity(store / OBJECTS, follow=False)
    if objects is None or objects[0] != identity[0]:
        return f"the store's {OBJECTS} directory is gone, a link or on another filesystem"
    if not _intact(store, latest):
        return "the latest verified backup is missing or damaged in the store"
    return None


def _intact(store: Path, latest: dict) -> bool:
    """The latest verified backup still restores from the store: its manifest and every object it names are there and
    still hash to their addresses (each re-hashed in chunks)."""
    from foundry.systems import cas
    try:
        manifest = json.loads(cas.get(store, latest["seed"]))
        return all(cas.intact(store, address) for address in manifest["files"].values())
    except Exception:                            # noqa: BLE001 - missing, damaged or not a seed manifest
        return False


def _verified(ledger, store: Path) -> list[tuple[int, dict]]:
    rows = []
    for witness in ledger.select("witness", capability="body.backup", target=PREFIX + str(store)):
        for receipt in ledger.select("receipt", witness_id=witness.payload["witness_id"]):
            result = receipt.payload.get("result") or {}
            output = result.get("output")
            if result.get("result_class") == "positive" and isinstance(output, dict) and output.get("verified_at"):
                rows.append((receipt.seq, output))
    return sorted(rows, key=lambda row: row[0])


def verified(home: Path, store: Path) -> list[dict]:
    """Every verified backup to ``store`` the body's own ledger holds, oldest first: the output of each positive Gate
    receipt for a ``body.backup`` dispatch whose witness names exactly this store. A file in the store is never
    evidence of a backup; only the body's ledger is."""
    ledger = _reader(home)
    try:
        return [output for _, output in _verified(ledger, store)]
    finally:
        ledger.close()


def _read_since(ledger, store: Path, seq: int) -> bool:
    """Whether a status read of ``store`` was receipted after record ``seq``. The read in progress has no receipt yet:
    the Gate records it after this capability returns."""
    for witness in ledger.select("witness", capability="body.backup_status", target=PREFIX + str(store)):
        if witness.seq > seq and any((r.payload.get("result") or {}).get("result_class") == "positive"
                                     for r in ledger.select("receipt", witness_id=witness.payload["witness_id"])):
            return True
    return False


def _seconds(later: str, earlier: str) -> float:
    return (datetime.fromisoformat(later.replace("Z", "+00:00"))
            - datetime.fromisoformat(earlier.replace("Z", "+00:00"))).total_seconds()


def status(params, ctx) -> dict:
    """Whether the recovery point of the latest verified backup to the signed store is younger than ``rpo_seconds``
    and that backup still restores from the store, on the filesystem it was taken to (``fresh``; ``why`` says what is
    not), and whether a backup is due (``current`` is False then: see the module docstring)."""
    store = _store(ctx)
    rpo = params.get("rpo_seconds")
    if type(rpo) is not int or rpo <= 0:
        raise _refused("rpo_seconds must be a positive integer")
    home = _home(ctx)
    ledger = _reader(home)
    try:
        rows = _verified(ledger, store)
        first = bool(rows) and not _read_since(ledger, store, rows[-1][0])
    finally:
        ledger.close()
    if not rows:
        return {"store": str(store), "rpo_seconds": rpo, "fresh": False, "current": False, "latest": None,
                "age_seconds": None, "why": "no verified backup to this store"}
    latest = rows[-1][1]                         # the recovery point's age is what a loss now would cost
    age = (_now() - datetime.fromisoformat(latest["backed_up_at"].replace("Z", "+00:00"))).total_seconds()
    why = _gone(home, store, latest)
    fresh = why is None and age <= rpo
    # The first read since a backup judges what the backup did: it was within the RPO when it was taken. The age it
    # has gained since is the time the body was not running to read it; the next read judges by age.
    current = fresh or (why is None and first and _seconds(latest["verified_at"], latest["backed_up_at"]) <= rpo)
    if why is None and not fresh:
        why = "the latest verified backup is older than the RPO" + (
            "; it was within the RPO when taken and this is its first read (the body was stopped, asleep or paused "
            "meanwhile), so the next read takes a new one if it is still due" if current else "")
    return {"store": str(store), "rpo_seconds": rpo, "fresh": fresh, "current": current, "first_read": first,
            "age_seconds": round(age, 3), "why": why,
            "latest": {k: latest[k] for k in ("seed", "backed_up_at", "ledger_head", "restored_head", "verified_at")}}


def mission(*, store: str | Path, rpo_seconds: int = 86400, cadence_seconds: int = 3600,
            horizon_days: float = 30, mission_id: str = "m:backup", accept_same_filesystem: bool = False) -> dict:
    """A standing backup mission for the founder to review and sign: nothing is backed up until it is signed.

    The RPO must be at least twice the cadence (see the limits above)."""
    store = Path(store).expanduser()
    if not store.is_absolute():
        raise ValueError("the backup store must be an absolute path")
    if any(c in str(store) for c in GLOB):
        raise ValueError(f"the backup store path may not hold a glob character ({GLOB}): light-cone targets are "
                         "patterns")
    if type(rpo_seconds) is not int or type(cadence_seconds) is not int or cadence_seconds <= 0:
        raise ValueError("rpo_seconds and cadence_seconds must be positive integers")
    if rpo_seconds < 2 * cadence_seconds:
        raise ValueError(f"an RPO of {rpo_seconds} s needs a cadence of at most {rpo_seconds // 2} s (half the RPO), "
                         f"not {cadence_seconds} s: the body reads the check once per cadence, so the recovery point "
                         "can pass the RPO by up to one cadence before the next backup")
    target = PREFIX + str(store.resolve())
    where = (" The founder accepts a store on the body's own filesystem: it survives a damaged body home, not the "
             "loss of this disk." if accept_same_filesystem else "")
    return {
        "mission_id": mission_id,
        "founder_expression": f"Back up my body to {store} so that losing this disk or computer is survivable, "
                              "and prove that every backup restores." + where,
        "intended_effect": f"a verified backup no older than {rpo_seconds} seconds, plus the cadence, is always "
                           f"in {store}; each one was restored in a scratch home and its ledger re-verified",
        "beneficiaries": ["Alfonso"],
        "unacceptable_outcomes": ["a backup inside the body home or a read root", "a private key in a backup",
                                  "a backup recorded as verified that did not restore"],
        "priority": 60,
        "closure": {"kind": "infinite", "cadence_seconds": cadence_seconds},
        "success_checks": [{
            "check_id": "verified-backup-fresh",
            "description": f"no backup is due: the latest verified backup in {store} is at most {rpo_seconds} seconds "
                           "old, or this is its first read and it was when it was taken",
            "sensor": {"capability": "body.backup_status", "params": {"rpo_seconds": rpo_seconds}, "target": target},
            "predicate": {"op": "equals", "field": "current", "value": True}}],
        "strategies": [{
            "action_id": "backup", "capability": "body.backup",
            "params": {ACCEPT: True} if accept_same_filesystem else {}, "target": target,
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
            inputs={ACCEPT: "bool, optional: the founder accepts a store on the body's own filesystem"},
            outputs={"seed": "str", "ledger_head": "str", "restored_head": "str", "held": "bool"},
            filesystem="named-write", strengthens=("reliability", "proof"), tests=tests, provenance=source),
            lazy("greg.backup", "backup")),
        "body.backup_status": (manifest_type(
            capability_id="body.backup_status", version="1.0.0", provider="greg-builtin",
            function="body.backup_status",
            description="Whether the latest verified backup to the signed store is younger than the signed RPO",
            route="internal", consequence_class="read_only", target_prefix=PREFIX,
            inputs={"rpo_seconds": "int > 0"},
            outputs={"fresh": "bool", "current": "bool", "age_seconds": "float|null", "latest": "dict|null",
                     "why": "str|null"},
            retry_safe=True,
            strengthens=("reliability", "proof"), tests=tests, provenance=source),
            lazy("greg.backup", "status")),
    }


if __name__ == "__main__":
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="print a standing backup mission for the founder to sign")
    parser.add_argument("--store", required=True, help="absolute path of the store, outside the body home")
    parser.add_argument("--rpo-hours", type=float, default=24.0)
    parser.add_argument("--cadence-seconds", type=int, default=3600)
    parser.add_argument("--horizon-days", type=float, default=30)
    parser.add_argument("--accept-same-filesystem", action="store_true",
                        help="accept a store on the body's own filesystem (survives a damaged home, not a lost disk)")
    args = parser.parse_args()
    try:
        spec = mission(store=args.store, rpo_seconds=int(args.rpo_hours * 3600), cadence_seconds=args.cadence_seconds,
                       horizon_days=args.horizon_days, accept_same_filesystem=args.accept_same_filesystem)
    except ValueError as exc:
        parser.error(str(exc))
    if not Path(args.store).expanduser().is_dir():
        print(f"note: {args.store} does not exist yet; create or mount it before the first backup", file=sys.stderr)
    print(json.dumps(spec, indent=1))
