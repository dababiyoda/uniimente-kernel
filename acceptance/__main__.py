"""python -m acceptance {check,run,report,directive}: the whole-machine acceptance harness (Missions A-L).

  check      validate missions.json, completion-contract.json and directive-sections.json against this tree
             (static; no test runs)
  run        run every cited test once, then report what each requirement, mission and function attained
  report     the same report from a recorded outcomes file, without running anything
  directive  the 2026-10-28 directive section by section: each section's status computed from its asks, the
             BUILDABLE_NOT_BUILT asks in dependency order, and whether the prompt is completely built
             (--collect also runs pytest's collection over every node the map cites; --outcomes recomputes
             the tiers from a recorded run; --against <git ref> refuses a pinned ask that disappeared or whose
             pinned blocker class left BUILDABLE_NOT_BUILT since that ref)

``run`` exits 0 only when every tested requirement and every Mission L trace link attained its declared
tier and no cited test failed, errored or collected nothing (a requirement of coverage 'gap' declares no tier,
but its failing tests still count); any shortfall exits 1 and names it. Reaching a tier is not covering an
obligation: the report also says how many requirements, missions and contract functions cover their whole
obligation and how many only part.
Nothing here grants, attaches or activates anything.
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

from acceptance import CONTRACT, MANIFEST, ROOT, load, minimal_nodes, problems, report, shortfall_names
from acceptance import directive


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
        broken = [rid for rid, r in m["requirements"].items() if r["failing"] and not r.get("declared_tier")]
        part = "whole obligation" if m["coverage"] == "covered" else "part of obligation"
        print(f"  Mission {mid}: {m['status']:<20} {part:<18} {m['title']}"
              + (f"  [short of declared tier: {', '.join(short)}]" if short and rep["ran"] else "")
              + (f"  [cited tests failing, no tier declared: {', '.join(broken)}]" if broken else ""))
        observed = [(rid, line) for rid, r in m["requirements"].items() for line in r["observed"]]
        for rid, line in observed if rep["ran"] else []:      # what the cited tests did where it falls short
            print(f"    {rid}: {line[:300]}")
        if m.get("trace"):
            links = ", ".join(f"{x['link']} {x['status']}" for x in m["trace"])
            short = [x["link"] for x in m["trace"] if not x["attained"]]
            print(f"    trace: {links}"
                  + (f"  [short of declared tier: {', '.join(short)}]" if short and rep["ran"] else ""))
            observed = [(x["link"], line) for x in m["trace"] for line in x["observed"]]
            for link, line in observed if rep["ran"] else []:
                print(f"    trace {link}: {line[:300]}")
    s = rep["summary"]
    print(f"{s['attained_declared_tier']}/{s['requirements']} requirements reach their declared tier; "
          f"{s['attained_whole_obligation']} of them cover the whole obligation, "
          f"{s['attained_part_obligation']} only part.")
    if rep["ran"]:
        print(f"{s['requirements_citing_failing_tests']} requirements cite a test that failed, errored or collected "
              f"nothing (each fails the run, with or without a declared tier).")
    print(f"{s['trace_links_attained']}/{s['trace_links']} trace links reach their declared tier. "
          f"{s['contract_functions_whole_obligation']}/{s['contract_functions']} contract functions rest only on "
          f"requirements that cover their whole obligation.")
    print(f"No test can establish {', '.join(s['statuses_no_test_can_establish'])}.")


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
    dire = sub.add_parser("directive")
    dire.add_argument("--collect", action="store_true", help="also check that every cited node collects a test")
    dire.add_argument("--outcomes", help="recompute tiers from a recorded outcomes file")
    dire.add_argument("--against", metavar="REF", help="compare the pinned asks with the pin at a git ref (a PR's base)")
    dire.add_argument("--out")
    args = parser.parse_args(argv)

    manifest, contract = load(MANIFEST), load(CONTRACT)
    found = problems(manifest, contract)
    if found:
        print("acceptance manifest or contract is unsound:", *found, sep="\n  ")
        return 2
    if args.cmd in ("check", "directive"):
        sections = directive.load_map()
        found = directive.directive_problems(sections, manifest, contract)
        if args.cmd == "directive" and args.against and not found:
            base, why = directive.pin_at(args.against)
            if why:
                found = [why]
            elif base is None:
                print(f"no pin at {args.against}: nothing to ratchet against")
            else:
                found = directive.pin_ratchet_problems(base, directive.load_map(directive.PIN))
                if not found:
                    print(f"the pinned asks hold against {args.against}")
        if args.cmd == "directive" and args.collect and not found:
            nodes = directive.cited_nodes(sections)
            found = directive.collect_problems(nodes)
            if not found:
                print(f"all {len(nodes)} distinct cited nodes collect at least one test")
        if found:
            print("directive map is unsound:", *found, sep="\n  ")
            return 2
        outcomes = json.loads(Path(args.outcomes).read_text()) if getattr(args, "outcomes", None) else None
        drep = directive.directive_report(sections, manifest, contract, outcomes)
    if args.cmd == "check":
        nodes = _nodes(manifest, None)
        print(f"sound: {len(manifest['missions'])} missions, "
              f"{sum(len(m['requirements']) for m in manifest['missions'])} requirements, "
              f"{len(nodes)} distinct test nodes, {len(contract['functions'])} contract functions")
        print(directive.summary_line(drep))
        return 0
    if args.cmd == "directive":
        if args.out:
            Path(args.out).write_text(json.dumps(drep, indent=1, sort_keys=True) + "\n")
        directive.print_report(drep, sections)
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
    return 1 if shortfall_names(rep) else 0


if __name__ == "__main__":
    sys.exit(main())
