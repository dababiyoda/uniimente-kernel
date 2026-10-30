#!/usr/bin/env python3
"""No founder intent or capability horizon disappears through cleanup (directive 2026-10-28 sections 11 and 54).

"CLOSE PR does not mean DELETE THE INTENT." "Preserve old founder statements even when superseded." The snapshot
(docs/collaboration/INTENT-CONTINUITY-SNAPSHOT-2026-10-30.json) lists every intent id and horizon id at a pinned
commit. At HEAD each must still be present, or a record present at HEAD must name it in its ``supersedes``: once
an old record is gone its own ``superseded_by`` cannot be read, so the successor's ``supersedes`` is the link that
keeps its lineage. The check reads the working tree and the snapshot only, never git history (CI clones are
shallow). ``--write-snapshot COMMIT`` regenerates the snapshot from that commit's tree with ``git archive``.

Ids by kind:
  intent_records      ``intent_id`` of every record in docs/intent/*.json (a file may hold a list under ``intents``)
  intent_documents    the id in the title line of every docs/intent/*.md record
  ledger_records      ids the Founder Intent Ledger declares itself: a ``| Required field |`` table header, an
                      ``- intent_id:`` line, a heading or a line that begins with the id
  horizons, frontier_backcasts   ``id`` of every horizon and frontier backcast on greg/path.json

A JSON record must stay a JSON record; a markdown record may become JSON; a ledger id must stay mentioned in the
ledger or become a record. Additions are always allowed.
"""
from __future__ import annotations

import argparse
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
    ids = []
    for line in text.splitlines():
        header = re.match(r"^\| Required field \|(.*)\|\s*$", line)
        if header:
            ids += [cell.strip() for cell in header.group(1).split("|") if re.fullmatch(ID, cell.strip())]
            continue
        declared = (re.match(rf"^- intent_id: ({ID})\s*$", line) or re.match(rf"^#+ ({ID})\b", line)
                    or re.match(rf"^({ID}): ", line))
        if declared:
            ids.append(declared.group(1))
    return ids


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


def successors(root: Path = ROOT) -> list[str]:
    """Every ``supersedes`` entry of a record present at HEAD: intent records, horizons and frontier backcasts."""
    data = _path(root)
    rows = _json_records(root) + list(data.get("horizons") or []) + list(data.get("frontier_backcasts") or [])
    out = []
    for row in rows:
        named = row.get("supersedes")             # an {"unrecorded": ...} marker names nothing
        out += [named] if isinstance(named, str) else [s for s in named if isinstance(s, str)] \
            if isinstance(named, list) else []
    return out


def missing(snapshot: dict, root: Path = ROOT) -> list[tuple[str, str]]:
    """(kind, id) for every snapshot id that is gone at HEAD and named by no successor's ``supersedes``."""
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
    for kind in KINDS:
        for identifier in snapshot["ids"].get(kind, []):
            if present[kind](identifier):
                continue
            if any(_token(identifier).search(entry) for entry in named):
                continue
            out.append((kind, identifier))
    return out


def write_snapshot(commit: str, target: Path = SNAPSHOT) -> dict:
    """The ids at ``commit``, read from ``git archive`` of the files this check reads."""
    sha = subprocess.run(["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True, capture_output=True,
                         text=True).stdout.strip()
    archive = subprocess.run(["git", "archive", "--format=tar", sha, *READ], cwd=ROOT, check=True,
                             capture_output=True).stdout
    with tempfile.TemporaryDirectory(prefix="intent-continuity-") as temp:
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(temp, filter="data")
        ids = current_ids(Path(temp))
    snapshot = {"pinned_commit": sha, "generated_by": f"python scripts/ci/check_intent_continuity.py --write-snapshot {sha}",
                "rule": "every id here stays present at HEAD, or a record present at HEAD names it in its supersedes",
                "ids": ids}
    target.write_text(json.dumps(snapshot, indent=1) + "\n", encoding="utf-8")
    return snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--snapshot", default=str(SNAPSHOT))
    parser.add_argument("--write-snapshot", metavar="COMMIT")
    args = parser.parse_args(argv)
    if args.write_snapshot:
        snapshot = write_snapshot(args.write_snapshot, Path(args.snapshot))
        print({kind: len(ids) for kind, ids in snapshot["ids"].items()})
        return 0
    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    gone = missing(snapshot, Path(args.root))
    total = sum(len(ids) for ids in snapshot["ids"].values())
    print(f"{total} ids pinned at {snapshot['pinned_commit'][:12]}; {len(gone)} missing at HEAD")
    for kind, identifier in gone:
        print(f"MISSING {kind} {identifier}: restore it, or name it in a successor's supersedes")
    return int(bool(gone))


if __name__ == "__main__":
    sys.exit(main())
