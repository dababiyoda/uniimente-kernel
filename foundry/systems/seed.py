"""#46 Backup and disaster recovery: the Institutional Seed.

``make_seed`` packs a GREG body home (ledger, body config, enrolled public keys,
deliveries) into a content-addressed seed (#36) with a manifest of hashes.
Private keys are never packed: the seed records which key files were excluded,
so recovery demands the founder's own key backup. ``restore`` rebuilds the home
on a fresh machine, re-verifies every byte and reports whether the restored
ledger chain equals the original head.
"""
from __future__ import annotations

import json
from pathlib import Path

from foundry.systems import cas

SECRET_MARKERS = ("_ed25519.pem", "founder.pem", "vault", "secrets", "witness.key", ".lock")


def _excluded(rel: str) -> bool:
    return any(marker in rel for marker in SECRET_MARKERS)


def make_seed(home: Path, store: Path) -> dict:
    home = Path(home)
    files, excluded = {}, []
    for path in sorted(home.rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(home))
        if _excluded(rel):
            excluded.append(rel)
            continue
        files[rel] = cas.put(store, path.read_bytes())
    seed = {"format": "uniimente-seed/1", "files": files, "excluded_secrets": excluded}
    return {"seed": cas.put(store, json.dumps(seed, sort_keys=True).encode()), "files": len(files), "excluded": excluded}


def restore(store: Path, seed_address: str, target: Path) -> dict:
    target = Path(target)
    if target.exists() and any(target.iterdir()):
        raise FileExistsError("restore target must be empty; the seed never overwrites a living body")
    seed = json.loads(cas.get(store, seed_address))  # refuses a tampered seed manifest
    for rel, address in seed["files"].items():
        out = target / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(cas.get(store, address))       # refuses a tampered object
    return {"restored": len(seed["files"]), "needs_from_founder": seed["excluded_secrets"]}


def ledger_head(ledger: Path) -> str | None:
    lines = Path(ledger).read_text().splitlines() if Path(ledger).exists() else []
    return json.loads(lines[-1]).get("hash") if lines else None


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
