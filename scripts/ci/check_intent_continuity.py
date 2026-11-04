#!/usr/bin/env python3
"""No founder intent or capability horizon disappears through cleanup (directive 2026-10-28 sections 11 and 54).

"CLOSE PR does not mean DELETE THE INTENT." "Preserve old founder statements even when superseded." The snapshot
(docs/collaboration/INTENT-CONTINUITY-SNAPSHOT-2026-10-30.json) lists every intent id and horizon id at a pinned
commit, and under ``added`` every id a later re-pin found new. At HEAD each must still be present, or a successor
present at HEAD must name it in its ``supersedes``: once an old record is gone its own ``superseded_by`` cannot be
read, so the successor's ``supersedes`` is the link that keeps its lineage. Succession is typed. An entry names an id
only when the whole entry is that id: prose that mentions an id, or uses a horizon id such as ``voice`` as a word,
names nothing. An intent id is succeeded by an intent record, a horizon by a horizon, a frontier backcast by a
frontier backcast. The check reads the working tree and the snapshot only, never git history (CI clones are
shallow).

``--write-snapshot COMMIT`` re-pins from that commit's tree (``git archive``) and only ever adds. It refuses while
any pinned id is missing at COMMIT, and appends only the ids new at COMMIT. The pinned commit's ids are never
rewritten; tests/unit/test_intent_continuity.py holds their exact counts and digest, so thinning them takes a visible
edit of that test.

Ids by kind:
  intent_records      ``intent_id`` of every record in docs/intent/*.json (a file may hold a list under ``intents``)
  intent_documents    the id in the title line of every docs/intent/*.md record
  ledger_records      every id the Founder Intent Ledger names as a whole token: the ids it declares (a
                      ``| Required field |`` table header, an ``- intent_id:`` line, a heading) and the ids it only
                      mentions, such as an intent kept on a draft branch (a path segment is a link, not a mention)
  horizons, frontier_backcasts   ``id`` of every horizon and frontier backcast on greg/path.json

A JSON record must stay a JSON record; a markdown record may become JSON; a ledger id must stay mentioned in the
ledger or become a record. Additions are always allowed.
"""
from __future__ import annotations

import argparse
import copy
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "docs" / "collaboration" / "INTENT-CONTINUITY-SNAPSHOT-2026-10-30.json"
KINDS = ("intent_records", "intent_documents", "ledger_records", "horizons", "frontier_backcasts")
READ = ("docs/intent", "docs/FOUNDER_INTENT_LEDGER.md", "greg/path.json")
ID = r"(?:[A-Z]+-)?INTENT-[0-9A-Za-z](?:[0-9A-Za-z-]*[0-9A-Za-z])?"
# The kind of record whose supersedes may name an id of each kind.
SUCCESSOR = {"intent_records": "intent", "intent_documents": "intent", "ledger_records": "intent",
             "horizons": "horizons", "frontier_backcasts": "frontier_backcasts"}
RULE = ("every id here stays present at HEAD, or a successor of its kind present at HEAD names it as a whole "
        "supersedes entry; a re-pin only adds")


class SnapshotError(ValueError):
    """A re-pin that would drop a pinned id."""


def _token(identifier: str) -> re.Pattern:
    """The id as a whole token: not a prefix of a longer id, not the tail of a path or a longer name."""
    return re.compile(rf"(?<![\w/-]){re.escape(identifier)}(?![\w-])")


def _json_records(root: Path) -> list[dict]:
    out = []
    for path in sorted((root / "docs/intent").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data.get("intents") if isinstance(data, dict) and "intents" in data else [data]
        out += [r for r in rows if isinstance(r, dict) and r.get("intent_id")]
    return out


def _markdown_ids(root: Path) -> list[str]:
    ids = []
    for path in sorted((root / "docs/intent").glob("*.md")):
        title = path.read_text(encoding="utf-8").lstrip().splitlines()[0]
        found = re.search(ID, title)
        if found:
            ids.append(found.group(0))
    return ids


def _ledger_ids(text: str) -> list[str]:
    """Every intent id the ledger names as a whole token: the ids it declares (a ``| Required field |`` table header,
    an ``- intent_id:`` line, a heading) and the ids it only mentions, such as an intent kept on a draft branch."""
    return re.findall(rf"(?<![\w/-])({ID})(?![\w-])", text)


def _path(root: Path) -> dict:
    return json.loads((root / "greg/path.json").read_text(encoding="utf-8"))


def current_ids(root: Path = ROOT) -> dict:
    data = _path(root)
    ledger = root / "docs/FOUNDER_INTENT_LEDGER.md"
    return {"intent_records": sorted({r["intent_id"] for r in _json_records(root)}),
            "intent_documents": sorted(set(_markdown_ids(root))),
            "ledger_records": sorted(set(_ledger_ids(ledger.read_text(encoding="utf-8")))) if ledger.exists() else [],
            "horizons": sorted({h["id"] for h in data.get("horizons") or []}),
            "frontier_backcasts": sorted({b["id"] for b in data.get("frontier_backcasts") or []})}


def _named(rows: list) -> set[str]:
    """The whole ``supersedes`` entries of ``rows``. An entry names an id only when it is that id; prose that mentions
    an id is a formulation of what changed, not a successor link."""
    out = set()
    for row in rows:
        named = row.get("supersedes")             # an {"unrecorded": ...} marker names nothing
        entries = [named] if isinstance(named, str) else named if isinstance(named, list) else []
        out |= {entry.strip() for entry in entries if isinstance(entry, str)}
    return out


def successors(root: Path = ROOT) -> dict[str, set[str]]:
    """Successor kind -> the ids named by the records of that kind present at HEAD: intent records name intent ids,
    horizons name horizons, frontier backcasts name frontier backcasts."""
    data = _path(root)
    return {"intent": _named(_json_records(root)),
            "horizons": _named(list(data.get("horizons") or [])),
            "frontier_backcasts": _named(list(data.get("frontier_backcasts") or []))}


def pinned(snapshot: dict) -> dict[str, list[str]]:
    """Every id the snapshot pins, by kind: the pinned commit's ids and the ids each later re-pin added."""
    out = {kind: set(snapshot["ids"].get(kind, [])) for kind in KINDS}
    for pin in snapshot.get("added", []):
        for kind in KINDS:
            out[kind] |= set(pin["ids"].get(kind, []))
    return {kind: sorted(ids) for kind, ids in out.items()}


def missing(snapshot: dict, root: Path = ROOT) -> list[tuple[str, str]]:
    """(kind, id) for every pinned id that is gone at HEAD and named by no successor of its kind."""
    now = current_ids(root)
    declared = set(now["intent_records"]) | set(now["intent_documents"])
    ledger_path = root / "docs/FOUNDER_INTENT_LEDGER.md"
    ledger = ledger_path.read_text(encoding="utf-8") if ledger_path.exists() else ""
    named = successors(root)
    present = {"intent_records": lambda i: i in now["intent_records"],
               "intent_documents": lambda i: i in declared,
               "ledger_records": lambda i: i in declared or bool(_token(i).search(ledger)),
               "horizons": lambda i: i in now["horizons"],
               "frontier_backcasts": lambda i: i in now["frontier_backcasts"]}
    out = []
    for kind, ids in pinned(snapshot).items():
        for identifier in ids:
            if present[kind](identifier) or identifier in named[SUCCESSOR[kind]]:
                continue
            out.append((kind, identifier))
    return out


def repin(snapshot: dict | None, sha: str, root: Path) -> dict:
    """The snapshot after pinning commit ``sha``, whose tree is at ``root``. It only adds: the first pin records every
    id; a later one refuses while any pinned id is missing at ``sha`` and appends only the ids new there."""
    ids = current_ids(root)
    if snapshot is None:
        return {"pinned_commit": sha,
                "generated_by": f"python scripts/ci/check_intent_continuity.py --write-snapshot {sha}",
                "rule": RULE, "ids": ids, "added": []}
    gone = missing(snapshot, root)
    if gone:
        raise SnapshotError(f"{sha[:12]} drops pinned ids {gone}: restore them, or name each in a successor's "
                            "supersedes, before re-pinning")
    held = pinned(snapshot)
    new = {kind: sorted(set(ids[kind]) - set(held[kind])) for kind in KINDS}
    out = copy.deepcopy(snapshot)
    out.setdefault("added", [])
    if any(new.values()):
        out["added"].append({"commit": sha, "ids": {kind: found for kind, found in new.items() if found}})
    return out


def write_snapshot(commit: str, target: Path = SNAPSHOT) -> dict:
    """Re-pin ``target`` at ``commit``, read from ``git archive`` of the files this check reads (``repin``)."""
    sha = subprocess.run(["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True, capture_output=True,
                         text=True).stdout.strip()
    archive = subprocess.run(["git", "archive", "--format=tar", sha, *READ], cwd=ROOT, check=True,
                             capture_output=True).stdout
    old = json.loads(target.read_text(encoding="utf-8")) if target.exists() else None
    with tempfile.TemporaryDirectory(prefix="intent-continuity-") as temp:
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(temp, filter="data")
        snapshot = repin(old, sha, Path(temp))
    target.write_text(json.dumps(snapshot, indent=1) + "\n", encoding="utf-8")
    return snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--snapshot", default=str(SNAPSHOT))
    parser.add_argument("--write-snapshot", metavar="COMMIT")
    args = parser.parse_args(argv)
    if args.write_snapshot:
        try:
            snapshot = write_snapshot(args.write_snapshot, Path(args.snapshot))
        except SnapshotError as refusal:
            print(f"REFUSED {refusal}")
            return 1
        print({kind: len(ids) for kind, ids in pinned(snapshot).items()})
        return 0
    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    gone = missing(snapshot, Path(args.root))
    ids = pinned(snapshot)
    distinct = len(set().union(*map(set, ids.values())))     # a record id the ledger names counts twice
    total = sum(len(found) for found in ids.values())
    later = f" and {len(snapshot['added'])} later pins" if snapshot.get("added") else ""
    print(f"{total} ids ({distinct} distinct) pinned at {snapshot['pinned_commit'][:12]}{later}; "
          f"{len(gone)} missing at HEAD")
    for kind, identifier in gone:
        print(f"MISSING {kind} {identifier}: restore it, or name it in a successor's supersedes")
    return int(bool(gone))


if __name__ == "__main__":
    sys.exit(main())
