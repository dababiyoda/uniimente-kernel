"""#46 Backup and disaster recovery: the Institutional Seed.

``make_seed`` packs a GREG body home (ledger, body config, enrolled public keys,
deliveries) into a content-addressed seed (#36) with a manifest of hashes.
Private keys are never packed: the seed records which key files were excluded,
so recovery demands the founder's own key backup. ``restore`` rebuilds the home
on a fresh machine, re-verifies every byte and reports whether the restored
ledger chain equals the original head. The seed records its recovery point
(when it was taken and the ledger head then); ``greg.recovery.restore_body``
completes a GREG body restore on top of ``restore``.

A seed of a running body is consistent by construction, with no lock on the writer:

- **The ledger first.** It is read once, before any other file, and only its complete lines are packed: a final line
  without its newline was never acknowledged (a write in progress, or one torn by a crash). Those lines must verify as
  one hash chain, exactly as a restore verifies them, and their last record is the seed's ``ledger_head``. Whatever
  the body appends meanwhile, the recorded head is where the packed ledger ends.
- **The queues just before it.** The items waiting in the body's queues (``QUEUES``: founder commands in ``inbox/``,
  untrusted items in ``intake/``) are read immediately before the ledger, so an item that was waiting is carried even
  when the running body consumes it, and moves it aside, after its ledger was read. The restored body reads it again:
  one the ledger shows consumed is a retained fact (intake) or a spent nonce (inbox), never a second effect.
- **Then every other file.** A file written after the ledger was read holds at most content newer than the recovery
  point. A file the body moved or removed after it was listed is left out.
- **Only regular files, never through a link.** Each directory is opened by ``os.fwalk`` without following a
  symbolic link, and each file is opened with ``O_NOFOLLOW`` after ``lstat`` says it is regular: a link planted in a
  workspace can never pack a key, a file outside the home or ``/proc``, and a device, pipe or socket is never opened.
  A file sharing its inode with excluded key material is not packed either. What is left out, and why (a link, not
  a regular file, unreadable, removed meanwhile), is listed in the manifest's ``not_packed``; one unreadable file
  never stops a backup.
- **Derived files are never packed or restored** (``DERIVED``): the body rewrites them from its own ledger. Packed
  after the ledger, the heartbeat could name a head the packed ledger does not hold, and the restored body would
  refuse its own history (``greg.body.Body._require_published_head``); a restored body writes its own on its first
  turn. The ledger's lookup indexes live in memory and are rebuilt on every open.
"""
from __future__ import annotations

from datetime import datetime, timezone
import errno
import json
import os
from pathlib import Path
import stat
import tempfile

from foundry.systems import cas

SECRET_MARKERS = ("_ed25519.pem", "founder.pem", "vault", "secrets", "witness.key", ".lock")
LEDGER = "ledger.jsonl"
# Rewritten by the body from its ledger (greg.body.Body._heartbeat): never truth of their own, so never packed and
# never restored.
DERIVED = ("heartbeat.json", "heartbeat.tmp")
# A running body consumes the *.json items waiting here into its ledger, then moves them aside (greg.body.Layout).
QUEUES = ("inbox", "intake")


class SeedError(ValueError):
    """The body's ledger does not verify, so no seed of it could ever be restored."""


def _excluded(rel: str) -> bool:
    return any(marker in rel for marker in SECRET_MARKERS)


def _walk(home: Path):
    """``(rel, dirfd, name)`` for every entry under ``home`` that is not a directory it descends, in name order.

    ``os.fwalk`` opens each directory itself, relative to its parent's descriptor, and never descends a symbolic link
    (nor a directory swapped for one while it is walked), so every name it yields lies inside ``home`` by every path
    component. A link to a directory is yielded as an entry, so it is recorded rather than silently skipped. A
    directory removed while it is walked (a running body's scratch space) is ignored. A home that is itself a link
    (``~/.greg`` on another disk, say) is walked where it leads."""
    root = os.path.realpath(home)
    for top, dirs, names, dirfd in os.fwalk(root):
        links = [d for d in dirs if _is_link(dirfd, d)]
        dirs[:] = sorted(d for d in dirs if d not in links)
        for name in sorted(names + links):
            yield os.path.relpath(os.path.join(top, name), root), dirfd, name


def _is_link(dirfd: int, name: str) -> bool:
    try:
        return stat.S_ISLNK(os.stat(name, dir_fd=dirfd, follow_symlinks=False).st_mode)
    except OSError:
        return False


def _key_inodes(home: Path) -> frozenset:
    """The inodes of the key material in ``home``: another name for one of them (a hard link) is never packed."""
    inodes = set()
    for rel, dirfd, name in _walk(home):
        if _excluded(rel):
            try:
                info = os.stat(name, dir_fd=dirfd, follow_symlinks=False)
            except OSError:
                continue
            if stat.S_ISREG(info.st_mode):
                inodes.add((info.st_dev, info.st_ino))
    return frozenset(inodes)


def _why(exc: OSError) -> str:
    return f"unreadable: {errno.errorcode.get(exc.errno, type(exc).__name__)}"


def _contents(dirfd: int, name: str, listed: os.stat_result) -> bytes | None:
    """The bytes of the regular file ``lstat`` listed, read without following a link (the precedent is
    ``greg.body._read_intake``); None when another file took its name meanwhile."""
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dirfd)
    with os.fdopen(fd, "rb") as handle:
        opened = os.fstat(handle.fileno())
        if (opened.st_dev, opened.st_ino) != (listed.st_dev, listed.st_ino) or not stat.S_ISREG(opened.st_mode):
            return None
        return handle.read()


def _read(dirfd: int, name: str, keys: frozenset) -> tuple[bytes | None, str | None]:
    """The bytes of one regular file, or why it is not packed."""
    try:
        listed = os.stat(name, dir_fd=dirfd, follow_symlinks=False)
    except FileNotFoundError:
        return None, "removed while the seed was taken"
    except OSError as exc:
        return None, _why(exc)
    if stat.S_ISLNK(listed.st_mode):
        return None, "symbolic link"
    if not stat.S_ISREG(listed.st_mode):
        return None, "not a regular file"
    if (listed.st_dev, listed.st_ino) in keys:
        return None, "another name for excluded key material"
    try:
        data = _contents(dirfd, name, listed)
    except FileNotFoundError:
        return None, "removed while the seed was taken"
    except OSError as exc:                 # EIO, a permission the body lacks, a link swapped in (ELOOP)
        return None, _why(exc)
    return (data, None) if data is not None else (None, "replaced while the seed was taken")


def _waiting(home: Path, keys: frozenset) -> dict:
    """Every item waiting in the body's queues, read whole: ``{rel: bytes}``."""
    items = {}
    for queue in QUEUES:
        try:
            dirfd = os.open(Path(home) / queue, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        except OSError:                    # no such queue, or not a directory of this home
            continue
        try:
            for name in sorted(os.listdir(dirfd)):
                if name.endswith(".json") and not _excluded(f"{queue}/{name}"):
                    data, why = _read(dirfd, name, keys)
                    if why is None:
                        items[f"{queue}/{name}"] = data
        finally:
            os.close(dirfd)
    return items


def make_seed(home: Path, store: Path, *, end: str | None = None) -> dict:
    """Pack ``home`` into ``store``. ``end`` names an earlier recovery point: the hash of the last ledger record to
    pack, which must lie in the verified prefix (by default the prefix's own last record)."""
    home = Path(home)
    keys = _key_inodes(home)
    # The queues, then the recovery point: the verified ledger prefix. Anything the body records after this instant is
    # not in the seed; an item waiting in a queue just before it is, whatever the body does with it next.
    waiting = _waiting(home, keys)
    ledger, head = ledger_prefix(home, end=end)
    backed_up_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    files, excluded, derived, not_packed = {}, [], [], {}
    if ledger is not None:
        files[LEDGER] = cas.put(store, ledger)
    for rel, data in waiting.items():
        files[rel] = cas.put(store, data)
    for rel, dirfd, name in _walk(home):
        if rel == LEDGER:
            continue
        if rel in waiting:
            continue
        if _excluded(rel):
            excluded.append(rel)
            continue
        if rel in DERIVED:
            derived.append(rel)
            continue
        data, why = _read(dirfd, name, keys)
        if why is not None:
            not_packed[rel] = why
            continue
        files[rel] = cas.put(store, data)
    excluded.sort()
    derived.sort()
    seed = {"format": "uniimente-seed/1", "files": files, "excluded_secrets": excluded, "derived_not_packed": derived,
            "not_packed": not_packed, "backed_up_at": backed_up_at, "ledger_head": head}
    return {"seed": cas.put(store, json.dumps(seed, sort_keys=True).encode()), "files": len(files), "excluded": excluded,
            "not_packed": not_packed, "backed_up_at": seed["backed_up_at"], "ledger_head": seed["ledger_head"]}


def restore(store: Path, seed_address: str, target: Path) -> dict:
    target = Path(target)
    if target.exists() and any(target.iterdir()):
        raise FileExistsError("restore target must be empty; the seed never overwrites a living body")
    seed = json.loads(cas.get(store, seed_address))  # refuses a tampered seed manifest
    root = target.resolve()
    for rel in seed["files"]:
        # Integrity proves the files are the manifest's, not that the manifest is benign: a seed someone else
        # built may name a path outside the target, or carry key material no seed of a body ever holds.
        if Path(rel).is_absolute() or root not in (root / rel).resolve().parents:
            raise ValueError(f"seed path {rel!r} leaves the restore target")
        if _excluded(rel):
            raise ValueError(f"seed carries {rel!r}; a seed never holds key material")
    restored = 0
    for rel, address in seed["files"].items():
        if rel in DERIVED:                              # a seed made before they were left out: the body rewrites them
            continue
        out = target / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(cas.get(store, address))       # refuses a tampered object
        restored += 1
    return {"restored": restored, "needs_from_founder": seed["excluded_secrets"]}


def _complete(raw: bytes) -> bytes:
    return raw[:raw.rfind(b"\n") + 1]                  # a final line without its newline was never acknowledged


def ledger_head(ledger: Path) -> str | None:
    lines = _complete(Path(ledger).read_bytes()).splitlines() if Path(ledger).exists() else []
    return json.loads(lines[-1]).get("hash") if lines else None


def ledger_prefix(home: Path, *, end: str | None = None) -> tuple[bytes | None, str | None]:
    """The ledger's complete lines, read once, and the head they end at; ``(None, None)`` without a ledger. With
    ``end``, only the lines up to and including the verified record whose hash it is.

    In a GREG body (its ``body.json`` names the constitution its history is bound to) the lines are verified exactly
    as ``greg.recovery.restore_body`` verifies a restored ledger: ``SeedError`` when they do not. Any other home has no
    chain format known here, and its head is its last complete record's ``hash``."""
    home = Path(home)
    try:
        raw = (home / LEDGER).read_bytes()
    except FileNotFoundError:
        return None, None
    prefix = _complete(raw)
    try:
        constitution = json.loads((home / "body.json").read_text()).get("constitution_hash")
    except (OSError, ValueError, AttributeError):
        constitution = None
    if not constitution:
        if end is not None:
            raise SeedError("an earlier recovery point needs a GREG body's verifiable ledger")
        lines = prefix.splitlines()
        return prefix, json.loads(lines[-1]).get("hash") if lines else None
    from provenance.ledger import EvidenceLedger
    with tempfile.TemporaryDirectory() as scratch:
        copy = os.path.join(scratch, LEDGER)
        with open(copy, "wb") as fh:
            fh.write(prefix)
        try:
            ledger = EvidenceLedger(constitution, copy, read_only=True)    # verifies itself as it loads
        except ValueError as exc:
            raise SeedError(f"the ledger does not verify, so no seed of it would restore: {exc}") from exc
        try:
            ok, why = ledger.verify_chain()
            head = ledger.head
            cut = ledger.find(end) if end is not None else None
        finally:
            ledger.close()
    if not ok:
        raise SeedError(f"the ledger does not verify, so no seed of it would restore: {why}")
    if end is not None:
        if cut is None:
            raise SeedError(f"the recovery point {end} is not in this body's verified ledger")
        prefix, head = b"\n".join(prefix.split(b"\n")[:cut.seq + 1]) + b"\n", end   # line i holds record seq i
    return prefix, head


QUERY_OPS: dict = {}
APPLY_OPS = {"seed": lambda a, r: make_seed(Path(a["home"]), r / "store")}


def exercise(root) -> dict:
    root = Path(root)
    home = root / "body"
    (home / "deliveries").mkdir(parents=True)
    records, prev = [], None
    for n in range(3):
        rec = {"seq": n, "prev": prev, "payload": f"event {n}"}
        rec["hash"] = cas.digest(json.dumps(rec, sort_keys=True).encode())
        records.append(rec)
        prev = rec["hash"]
    (home / "ledger.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    (home / "body.json").write_text(json.dumps({"body_id": "body-test"}))
    (home / "device_ed25519.pem").write_text("PRIVATE")
    (home / "deliveries" / "brief.md").write_text("# brief\n")
    made = make_seed(home, root / "store")
    restored = restore(root / "store", made["seed"], root / "fresh-machine")
    try:
        restore(root / "store", made["seed"], root / "fresh-machine")
        overwrite_refused = False
    except FileExistsError:
        overwrite_refused = True
    return {"files": made["files"], "private_key_not_packed": not (root / "fresh-machine" / "device_ed25519.pem").exists(),
            "needs_from_founder": restored["needs_from_founder"],
            "ledger_head_equal": ledger_head(root / "fresh-machine" / "ledger.jsonl") == ledger_head(home / "ledger.jsonl"),
            "overwrite_refused": overwrite_refused}
