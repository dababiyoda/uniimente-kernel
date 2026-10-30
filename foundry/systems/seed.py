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
- **Then every other file.** A file written after the ledger was read holds at most content newer than the recovery
  point. A file the body moved or removed after it was listed is left out.
- **Derived files are never packed or restored** (``DERIVED``): the body rewrites them from its own ledger. Packed
  after the ledger, the heartbeat could name a head the packed ledger does not hold, and the restored body would
  refuse its own history (``greg.body.Body._require_published_head``); a restored body writes its own on its first
  turn. The ledger's lookup indexes live in memory and are rebuilt on every open.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

from foundry.systems import cas

SECRET_MARKERS = ("_ed25519.pem", "founder.pem", "vault", "secrets", "witness.key", ".lock")
LEDGER = "ledger.jsonl"
# Rewritten by the body from its ledger (greg.body.Body._heartbeat): never truth of their own, so never packed and
# never restored.
DERIVED = ("heartbeat.json", "heartbeat.tmp")


class SeedError(ValueError):
    """The body's ledger does not verify, so no seed of it could ever be restored."""


def _excluded(rel: str) -> bool:
    return any(marker in rel for marker in SECRET_MARKERS)


def _listed(home: Path) -> list[str]:
    # os.walk ignores a directory removed while it is walked (a running body's scratch space); like rglob it does not
    # descend a symbolic link to a directory.
    return sorted(os.path.relpath(os.path.join(top, name), home)
                  for top, _, names in os.walk(home) for name in names)


def make_seed(home: Path, store: Path) -> dict:
    home = Path(home)
    # The recovery point: the verified ledger prefix, read before anything else. Anything the body records after this
    # instant is not in the seed.
    ledger, head = ledger_prefix(home)
    backed_up_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    files, excluded, derived = {}, [], []
    if ledger is not None:
        files[LEDGER] = cas.put(store, ledger)
    for rel in _listed(home):
        if rel == LEDGER:
            continue
        if _excluded(rel):
            excluded.append(rel)
            continue
        if rel in DERIVED:
            derived.append(rel)
            continue
        path = home / rel
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except FileNotFoundError:          # moved or removed by the running body after it was listed
            continue
        files[rel] = cas.put(store, data)
    seed = {"format": "uniimente-seed/1", "files": files, "excluded_secrets": excluded, "derived_not_packed": derived,
            "backed_up_at": backed_up_at, "ledger_head": head}
    return {"seed": cas.put(store, json.dumps(seed, sort_keys=True).encode()), "files": len(files), "excluded": excluded,
            "backed_up_at": seed["backed_up_at"], "ledger_head": seed["ledger_head"]}


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


def ledger_prefix(home: Path) -> tuple[bytes | None, str | None]:
    """The ledger's complete lines, read once, and the head they end at; ``(None, None)`` without a ledger.

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
        finally:
            ledger.close()
    if not ok:
        raise SeedError(f"the ledger does not verify, so no seed of it would restore: {why}")
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
