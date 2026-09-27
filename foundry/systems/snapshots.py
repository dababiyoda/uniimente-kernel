"""#21 Snapshots and forks: institutional state copied into isolated branches.

A snapshot is a content-addressed manifest (#36) of every file under a state
directory. ``fork`` materializes a snapshot into a separate branch directory;
branches evolve independently and never write to the source. ``compare`` diffs
two branches file by file; ``discard`` removes a branch; ``promote`` returns the
manifest a founder could choose to adopt (adoption itself stays a separate,
authorized act).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from foundry.systems import cas


def snapshot(state: Path, store: Path) -> str:
    files = {}
    for path in sorted(Path(state).rglob("*")):
        if path.is_file():
            files[str(path.relative_to(state))] = cas.put(store, path.read_bytes())
    return cas.put(store, json.dumps({"files": files}, sort_keys=True).encode())


def manifest(store: Path, snap: str) -> dict:
    return json.loads(cas.get(store, snap))["files"]


def fork(store: Path, snap: str, branch_dir: Path) -> Path:
    branch_dir = Path(branch_dir)
    if branch_dir.exists():
        raise FileExistsError(f"branch {branch_dir} exists; forks never overwrite")
    for rel, address in manifest(store, snap).items():
        target = branch_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(cas.get(store, address))
    return branch_dir


def compare(a: Path, b: Path) -> dict:
    files = lambda d: {str(p.relative_to(d)): cas.digest(p.read_bytes()) for p in Path(d).rglob("*") if p.is_file()}
    fa, fb = files(a), files(b)
    return {"only_a": sorted(set(fa) - set(fb)), "only_b": sorted(set(fb) - set(fa)),
            "changed": sorted(k for k in set(fa) & set(fb) if fa[k] != fb[k])}


def discard(branch_dir: Path) -> None:
    shutil.rmtree(branch_dir)


QUERY_OPS = {"compare": lambda a, r: compare(r / a["a"], r / a["b"])}
APPLY_OPS = {"snapshot": lambda a, r: {"snapshot": snapshot(r / a["state"], r / "store")},
             "fork": lambda a, r: {"branch": str(fork(r / "store", a["snapshot"], r / "branches" / a["branch"]).name)}}


def exercise(root) -> dict:
    root = Path(root)
    prod = root / "production"
    (prod / "policy").mkdir(parents=True)
    (prod / "policy" / "pricing.json").write_text(json.dumps({"price": 49}))
    (prod / "ledger.txt").write_text("sale 49\n")
    snap = snapshot(prod, root / "store")
    a = fork(root / "store", snap, root / "branches" / "price-39")
    b = fork(root / "store", snap, root / "branches" / "price-79")
    (a / "policy" / "pricing.json").write_text(json.dumps({"price": 39}))
    (b / "policy" / "pricing.json").write_text(json.dumps({"price": 79}))
    (b / "experiment.txt").write_text("premium tier\n")
    diff = compare(a, b)
    try:
        fork(root / "store", snap, a)
        overwrite_refused = False
    except FileExistsError:
        overwrite_refused = True
    discard(a)
    return {"production_untouched": json.loads((prod / "policy" / "pricing.json").read_text()) == {"price": 49},
            "diff": diff, "overwrite_refused": overwrite_refused, "discarded": not a.exists(),
            "snapshot_reproducible": snapshot(prod, root / "store") == snap}
