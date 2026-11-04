"""Reproduce the qualification evidence for open-source engines GREG may depend on.

    python scripts/qualify_open_source_engines.py tests/evidence/greg-open-source-genesis-2026-10-01

For every package candidate in Capability Genesis's catalog that is installed here, this
writes its Mechanism Card and its qualification report (frozen oracle, GREG certificate,
scale probe against the simplest local implementation). It installs nothing, attaches
nothing and grants nothing; it is the same check genesis runs inside a mission.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from greg import genesis, mechanisms  # noqa: E402

SEED = 20261001


def main(out_dir: str) -> int:
    rows = []
    for function, spec in genesis.CATALOG.items():
        if spec.get("kind") != "package":
            continue
        for candidate in spec["candidates"]:
            dist = mechanisms.installed(candidate.distribution)
            if dist is None:
                rows.append({"function": function, "distribution": candidate.distribution, "installed": False})
                continue
            card = mechanisms.card(candidate, function, dist)
            passed, report = genesis.qualify_package(function, candidate, card, SEED)
            rows.append({"function": function, "distribution": candidate.distribution, "installed": True,
                         "passed": passed, "card": card, "report": report})
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    record = {"generated_at": datetime.now(timezone.utc).isoformat(), "seed": SEED,
              "python": sys.version.split()[0], "platform": platform.platform(),
              "command": "python scripts/qualify_open_source_engines.py " + out_dir,
              "authority_created": False, "installed_by_greg": False, "results": rows}
    (out / "qualification.json").write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
    for row in rows:
        verdict = "not installed" if not row["installed"] else ("QUALIFIED" if row["passed"] else "FAILED")
        probe = row.get("report", {}).get("scale_probe", {})
        local = f"local {probe['local_seconds']}s" if "local_seconds" in probe else "no simple local alternative"
        print(f"{row['function']:22} {row['distribution']:9} {verdict:10} "
              f"solve {probe.get('package_solve_seconds')}s  {local}")
    return 0 if all(r.get("passed", True) for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "tests/evidence/greg-open-source-genesis-2026-10-01"))
