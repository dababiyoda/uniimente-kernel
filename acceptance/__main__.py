"""python -m acceptance {check,run,report}: the whole-machine acceptance harness (Missions A-L).

  check   validate missions.json and completion-contract.json against this tree (static; no test runs)
  run     run every cited test once, then report what each requirement, mission and function attained
  report  the same report from a recorded outcomes file, without running anything

``run`` exits 0 only when every tested requirement attained its declared tier; any shortfall exits 1 and
names it. Nothing here grants, attaches or activates anything.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from acceptance import CONTRACT, MANIFEST, ROOT, load, minimal_nodes, problems, report


def _head() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _nodes(manifest: dict, only: set[str] | None) -> list[str]:
    nodes = []
    for m in manifest["missions"]:
        if only and m["id"] not in only:
            continue
        for r in m["requirements"]:
            nodes += r.get("tests", [])
        for link in m.get("trace", []):
            nodes += link["proof"]
    return minimal_nodes(nodes)


def _run(nodes: list[str], timeout: int) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "outcomes.json"
        env = {**os.environ, "ACCEPTANCE_OUTCOMES": str(target)}
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "acceptance._plugin", "-p", "no:cacheprovider", *nodes]
        subprocess.run(cmd, cwd=ROOT, env=env, timeout=timeout)
        return json.loads(target.read_text()) if target.exists() else {}


def _print(rep: dict) -> None:
    print(f"acceptance at {rep.get('head') or 'unknown head'} "
          f"({'tests ran' if rep['ran'] else 'no tests ran: declarations only'})")
    for mid, m in rep["missions"].items():
        short = [rid for rid, r in m["requirements"].items() if r.get("declared_tier") and not r["attained"]]
        print(f"  Mission {mid}: {m['status']:<20} {m['title']}"
              + (f"  [short of declared tier: {', '.join(short)}]" if short and rep["ran"] else ""))
    s = rep["summary"]
    print(f"{s['attained_declared_tier']}/{s['requirements']} requirements attained their declared tier; "
          f"no test can establish {', '.join(s['statuses_no_test_can_establish'])}.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m acceptance")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    run = sub.add_parser("run")
    run.add_argument("--mission", action="append", choices=list("ABCDEFGHIJKL"))
    run.add_argument("--out")
    run.add_argument("--timeout", type=int, default=7200)
    rep = sub.add_parser("report")
    rep.add_argument("--outcomes", required=True)
    rep.add_argument("--out")
    args = parser.parse_args(argv)

    manifest, contract = load(MANIFEST), load(CONTRACT)
    found = problems(manifest, contract)
    if found:
        print("acceptance manifest or contract is unsound:", *found, sep="\n  ")
        return 2
    if args.cmd == "check":
        nodes = _nodes(manifest, None)
        print(f"sound: {len(manifest['missions'])} missions, "
              f"{sum(len(m['requirements']) for m in manifest['missions'])} requirements, "
              f"{len(nodes)} distinct test nodes, {len(contract['functions'])} contract functions")
        return 0
    meta = {"head": _head(), "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
    if args.cmd == "run":
        only = set(args.mission) if args.mission else None
        outcomes = _run(_nodes(manifest, only), args.timeout)
        if only:
            manifest = {**manifest, "missions": [m for m in manifest["missions"] if m["id"] in only]}
            missions = {m["id"] for m in manifest["missions"]}
            contract = {**contract, "functions": [f for f in contract["functions"]
                                                  if all(e.split(".")[0] in missions for e in f["evidence"])]}
    else:
        outcomes = json.loads(Path(args.outcomes).read_text())
    rep = report(manifest, contract, outcomes, meta)
    if args.out:
        Path(args.out).write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n")
    _print(rep)
    short = [(mid, rid) for mid, m in rep["missions"].items() for rid, r in m["requirements"].items()
             if r.get("declared_tier") and not r["attained"]]
    return 1 if short else 0


if __name__ == "__main__":
    sys.exit(main())
