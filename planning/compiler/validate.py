#!/usr/bin/env python3
"""Validate the planning graph and every artifact projected from it.

Instrument-liveness contract (canonical prompt §31). This script must:

* assert its own subject exists before reporting on it;
* carry a non-vacuity witness — it refuses to pass on an empty graph;
* ship a negative control that FORCES a failure, proving it can fail;
* exit nonzero on any failed assertion;
* use no hardcoded developer paths, and run identically from the repository
  root and from an unrelated working directory;
* record the exact source commit it ran against;
* distinguish "no result" from "passed", and "not run" from "passed".

A counter declared but never incremented is not evidence, so every check below
reports the population it examined, not merely its verdict.

Usage:
    python planning/compiler/validate.py                # validate
    python planning/compiler/validate.py --negative-control
    python planning/compiler/validate.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from planning.compiler.model import (  # noqa: E402
    EVIDENCE_STATUSES,
    GraphError,
    Node,
    PlanningGraph,
    load_graph,
    repo_root,
)

#: A graph smaller than this is almost certainly a broken load rather than a
#: real model, and a validator that passes on it would be vacuous.
MIN_NODES = 10

#: Language that would mean a planning artifact had quietly claimed operational
#: status. Planning output is PROPOSED; nothing here is live.
FORBIDDEN_CLAIMS = (
    "production ready",
    "production-ready",
    "deployed to production",
    "is now live",
    "ready for deployment",
)


class Check:
    """One validation with an explicit examined-population count."""

    def __init__(self, name: str):
        self.name = name
        self.examined = 0
        self.problems: list[str] = []

    @property
    def passed(self) -> bool:
        return not self.problems

    @property
    def vacuous(self) -> bool:
        """True when the check examined nothing — reported as UNKNOWN, not PASS."""
        return self.examined == 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "examined": self.examined,
            "status": "UNKNOWN_VACUOUS"
            if self.vacuous
            else ("PASS" if self.passed else "FAIL"),
            "problems": self.problems,
        }


def _source_commit() -> str:
    """The commit this validator ran against, or an explicit unknown."""
    try:
        out = subprocess.run(
            ["git", "-C", repo_root(), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return out.stdout.strip() if out.returncode == 0 else "UNKNOWN_NOT_A_GIT_CHECKOUT"
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN_GIT_UNAVAILABLE"


def check_schema(graph: PlanningGraph) -> Check:
    check = Check("graph_schema_and_evidence")
    check.examined = len(graph)
    check.problems.extend(graph.validate())
    return check


def check_evidence_discipline(graph: PlanningGraph) -> Check:
    """No node may assert anything without a checkable reference."""
    check = Check("anti_fabrication_evidence_discipline")
    for node in graph:
        check.examined += 1
        if node.evidence_status != "unresolved" and not node.evidence_refs:
            check.problems.append(f"{node.id}: {node.evidence_status} with no evidence")
    return check


def check_protected_intent(graph: PlanningGraph) -> Check:
    """The Founder-Horizon Override must be present and intact.

    Override §2 forbids converting "not implemented today" into "not actually
    intended", so the round fails rather than proceeds if the protected intent
    nodes are missing or unmarked.
    """
    check = Check("protected_intent_present")
    intents = graph.of_kind("protected_intent")
    check.examined = len(intents)
    if len(intents) < 20:
        check.problems.append(
            f"only {len(intents)} protected_intent nodes; the Founder-Horizon "
            "Override has 30 sections and must be frozen before planning proceeds"
        )
    for node in intents:
        if not node.body.get("protected"):
            check.problems.append(f"{node.id}: protected_intent without protected: true")
        if not node.body.get("override_section"):
            check.problems.append(f"{node.id}: no override_section back-reference")
    return check


def check_unavailable_never_cited(graph: PlanningGraph) -> Check:
    """A repository we could not open may never be cited as evidence.

    This is the exact failure mode §8.6 warns about: claiming inspection of an
    inaccessible repository. The check is mechanical rather than trusted.
    """
    check = Check("unavailable_sources_not_cited_as_evidence")
    unavailable = {
        n.body.get("repo_slug", n.id.split(".")[-1])
        for n in graph.of_kind("repository_unavailable")
    }
    forbidden_tokens = {"ivio-nemt", "chario", "obvio", "tgh-control-rail"}
    for node in graph:
        check.examined += 1
        for ref in node.evidence_refs:
            slug = ref.repo.lower()
            if any(token in slug for token in forbidden_tokens):
                check.problems.append(
                    f"{node.id}: cites unavailable repository {ref.repo!r} as evidence"
                )
    if not unavailable:
        check.problems.append(
            "no repository_unavailable nodes recorded; the round must state what it "
            "could not reach rather than leaving the omission silent"
        )
    return check


def check_no_production_claims(root: str) -> Check:
    """No generated planning artifact may claim operational readiness."""
    check = Check("no_production_readiness_claims")
    docs = os.path.join(root, "docs", "planning", "uniimente_v1")
    if not os.path.isdir(docs):
        return check  # vacuous: artifacts not generated yet, reported as UNKNOWN
    for name in sorted(os.listdir(docs)):
        if not name.endswith(".md"):
            continue
        check.examined += 1
        with open(os.path.join(docs, name), encoding="utf-8") as handle:
            lowered = handle.read().lower()
        for phrase in FORBIDDEN_CLAIMS:
            if phrase in lowered:
                check.problems.append(f"{name}: contains forbidden claim {phrase!r}")
    return check


def check_inertness(root: str) -> Check:
    """No kernel package may import `planning`. The dependency runs one way."""
    check = Check("planning_is_inert_and_detachable")
    skip = {"planning", "docs", "artifacts", ".git", "tests", "__pycache__"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".")]
        rel = os.path.relpath(dirpath, root)
        if rel.split(os.sep)[0] in skip:
            continue
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            check.examined += 1
            path = os.path.join(dirpath, filename)
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            if "import planning" in text or "from planning" in text:
                check.problems.append(
                    f"{os.path.relpath(path, root)}: kernel runtime imports planning"
                )
    return check


def run_all(graph: PlanningGraph, root: str) -> list[Check]:
    return [
        check_schema(graph),
        check_evidence_discipline(graph),
        check_protected_intent(graph),
        check_unavailable_never_cited(graph),
        check_no_production_claims(root),
        check_inertness(root),
    ]


def negative_control() -> int:
    """Force a failure to prove this validator can actually fail.

    Builds a graph containing one deliberately invalid node — an assertion with
    no evidence, the precise thing the anti-fabrication rule forbids — and
    requires the validator to reject it. If the checks pass on known-bad input
    they are worthless, so THAT is the failure condition here.
    """
    bad = Node(
        id="negative.control.fabricated",
        kind="finding",
        title="A claim with no evidence whatsoever",
        evidence_status="verified_by_execution",  # a lie: there are no refs
        body={},
        evidence_refs=[],
    )
    graph = PlanningGraph([bad])
    schema = check_schema(graph)
    discipline = check_evidence_discipline(graph)

    if schema.passed:
        print("NEGATIVE CONTROL FAILED: schema check accepted a fabricated node")
        return 1
    if discipline.passed:
        print("NEGATIVE CONTROL FAILED: evidence discipline accepted a fabricated node")
        return 1
    if discipline.examined != 1:
        print(f"NEGATIVE CONTROL FAILED: examined {discipline.examined}, expected 1")
        return 1
    print("NEGATIVE CONTROL PASSED: the validator rejects a fabricated node.")
    print(f"  schema problems     : {len(schema.problems)}")
    print(f"  discipline problems : {len(discipline.problems)}")
    for problem in schema.problems + discipline.problems:
        print(f"    - {problem}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--negative-control",
        action="store_true",
        help="prove this instrument can fail, then exit",
    )
    args = parser.parse_args(argv)

    if args.negative_control:
        return negative_control()

    root = repo_root()
    # Assert the subject exists before reporting on it.
    nodes_dir = os.path.join(root, "planning", "graph", "nodes")
    if not os.path.isdir(nodes_dir):
        print(f"FAIL: planning graph does not exist at {nodes_dir}", file=sys.stderr)
        return 2
    try:
        graph = load_graph()
    except GraphError as exc:
        print(f"FAIL: graph did not load: {exc}", file=sys.stderr)
        return 2

    # Non-vacuity witness: refuse to report success on a trivially small graph.
    if len(graph) < MIN_NODES:
        print(
            f"FAIL: graph has {len(graph)} nodes, below the non-vacuity floor of "
            f"{MIN_NODES}; a pass here would be meaningless",
            file=sys.stderr,
        )
        return 2

    checks = run_all(graph, root)
    report = {
        "source_commit": _source_commit(),
        "repo_root": root,
        "cwd": os.getcwd(),
        "graph_digest": graph.digest(),
        "node_count": len(graph),
        "kinds": graph.kinds(),
        "evidence_summary": graph.evidence_summary(),
        "checks": [c.to_dict() for c in checks],
    }
    failed = [c for c in checks if not c.passed]
    vacuous = [c for c in checks if c.vacuous]
    report["result"] = "FAIL" if failed else "PASS"
    report["vacuous_checks"] = [c.name for c in vacuous]

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"graph digest : {report['graph_digest']}")
        print(f"source commit: {report['source_commit']}")
        print(f"cwd          : {report['cwd']}")
        print(f"nodes        : {report['node_count']} across {len(report['kinds'])} kinds")
        print(f"evidence     : {report['evidence_summary']}")
        print()
        for check in checks:
            status = check.to_dict()["status"]
            print(f"  [{status:16}] {check.name}  (examined {check.examined})")
            for problem in check.problems:
                print(f"      - {problem}")
        print()
        print(f"RESULT: {report['result']}")
        if vacuous:
            print(f"UNKNOWN (examined nothing): {', '.join(c.name for c in vacuous)}")

    return 1 if failed else 0


if __name__ == "__main__":
    # Direct exit status, never a pipeline status. PR #66 recorded three
    # occasions where reading $? after a pipe hid a genuinely failing verifier.
    sys.exit(main())
