"""Refresh foundry/owned-source.json deliberately: the git-tracked files the packaging build owns.

The inventory is the confined Foundry worker's read allowance and the packaging build's file list, so it
must equal what the committed tree contains (CI scans a checkout): tracked files only, never local
scratch. Run after staging new owned runtime sources; review the diff like any other permission change.
"""
import json
from pathlib import Path
import subprocess

from foundry.systems import build

ROOT = build.ROOT
INVENTORY = ROOT / "foundry" / "owned-source.json"


def main():
    tracked = set(subprocess.check_output(["git", "ls-files", "--cached"], cwd=ROOT, text=True).split("\n"))
    files = [p.relative_to(ROOT).as_posix() for p in build._files(ROOT)]
    record = json.loads(INVENTORY.read_text())
    before = set(record["files"])
    record["files"] = sorted(f for f in files if f in tracked)
    INVENTORY.write_text(json.dumps(record, indent=2) + "\n")
    after = set(record["files"])
    print(json.dumps({"added": sorted(after - before), "removed": sorted(before - after)}, indent=1))


if __name__ == "__main__":
    main()
