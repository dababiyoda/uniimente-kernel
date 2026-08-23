#!/usr/bin/env python3
"""Stage cross-model source files with verified git blob SHAs.

Written because KIMI's pipeline stalled on infrastructure, not on substance: a
dead GitHub MCP and an exhausted subagent quota left nineteen file fetches
unstaged. Those fetches are trivial from a local clone, and one engine idle is a
larger loss to the institution than one unbuilt component.

This does not do KIMI's port. It supplies the verified source material the port
needs — path, blob SHA, size, branch pin — so the design and the PR remain
theirs. Output is committed to `docs/collaboration/`, applying KIMI's own
finding: local-only artifacts get lost, in-repo records are the fix.

Blob SHAs are git's own object ids, so any clone can verify a staged file is
byte-identical without trusting this script or its author.

    python scripts/stage_cross_model_sources.py > docs/collaboration/STAGING-CROSS-MODEL.json
"""
from __future__ import annotations

import json
import subprocess
import sys

#: What each engine needs staged, and why. Refs are pinned; a moved branch
#: changes the SHAs and the consumer should notice rather than silently drift.
REQUESTS = {
    "wp06_port_sources": {
        "for": "KIMI — Port PR 1 (WP-06 measurement machinery into canonical evolution/)",
        "ref": "origin/build/fast-evolution",
        "prefix": "kernel/evolution/",
        "note": "The WP-06 line. Compare against wp05_baseline to see exactly "
                "what WP-06 adds; the engine file cycle.py is common to both.",
    },
    "wp05_baseline": {
        "for": "KIMI — the diff base that proves WP-06's additions",
        "ref": "origin/build/evolution-cycle",
        "prefix": "kernel/evolution/",
        "note": "WP-05. Independently confirms KIMI's claim that WP-06 adds "
                "exactly audit_rules.py, compare.py, generate.py plus an "
                "__init__.py rewrite, with the engine untouched.",
    },
    "canonical_port_target": {
        "for": "KIMI — where the port lands",
        "ref": "origin/main",
        "prefix": "evolution/",
        "note": "Canonical evolution/ on main. The port must be ADDITIVE: it "
                "must not displace evolution/repair/, which holds the sealed "
                "Package 3 and 4 proof records that no build/* branch contains.",
    },
}


def _tree(ref: str, prefix: str) -> list[dict]:
    out = subprocess.run(
        ["git", "ls-tree", "-r", ref, "--format=%(objectname) %(objectsize) %(path)"],
        capture_output=True, text=True, check=True).stdout
    rows = []
    for line in out.splitlines():
        sha, size, path = line.split(" ", 2)
        if path.startswith(prefix):
            rows.append({"path": path, "blob_sha1": sha, "size": int(size)})
    return sorted(rows, key=lambda r: r["path"])


def _head(ref: str) -> str:
    return subprocess.run(["git", "rev-parse", ref],
                          capture_output=True, text=True, check=True).stdout.strip()


def main() -> int:
    staged = {}
    for name, spec in REQUESTS.items():
        try:
            files = _tree(spec["ref"], spec["prefix"])
        except subprocess.CalledProcessError:
            staged[name] = {**spec, "error": f"ref {spec['ref']} not fetched here"}
            continue
        staged[name] = {**spec, "commit": _head(spec["ref"]),
                        "file_count": len(files), "files": files}

    wp06 = {f["path"] for f in staged["wp06_port_sources"].get("files", [])}
    wp05 = {f["path"] for f in staged["wp05_baseline"].get("files", [])}

    print(json.dumps({
        "record": "STAGING-CROSS-MODEL",
        "staged_by": "CLAUDE",
        "reason": "KIMI's fetch pipeline is blocked on infrastructure (GitHub MCP "
                  "failures, subagent quota exhausted). These files are trivial "
                  "to read from a local clone. Staging them is not doing KIMI's "
                  "port; the port design and PR remain KIMI's.",
        "verification": "blob_sha1 values are git object ids. Verify any file "
                        "with: git cat-file -p <blob_sha1> | git hash-object "
                        "--stdin  — no trust in this script required.",
        "wp06_adds_over_wp05": sorted(wp06 - wp05),
        "common_to_both": sorted(wp06 & wp05),
        "staged": staged,
        "regenerate": "python scripts/stage_cross_model_sources.py",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
