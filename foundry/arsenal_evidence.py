"""Evidence audit for the 55-technology arsenal.

``foundry/arsenal.py`` declares a status per technology and FoundryComposer
ranks on it. This module binds each status to ``arsenal-evidence.yaml`` and
reports every status that its evidence does not support. It reads files only;
it never upgrades a status and grants nothing.

    python -m foundry.arsenal_evidence          # audit; exit 1 on problems
    python -m foundry.arsenal_evidence --table  # print the doc status table
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import yaml

from .arsenal import ARSENAL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVIDENCE_FILE = os.path.join(ROOT, "foundry", "arsenal-evidence.yaml")
TABLE_BEGIN = "<!-- arsenal-status:begin (generated: python -m foundry.arsenal_evidence --table) -->"
TABLE_END = "<!-- arsenal-status:end -->"


@dataclass(frozen=True)
class Evidence:
    technology_id: int
    implementation: tuple[str, ...]
    tests: tuple[str, ...]
    organ_evidence: tuple[str, ...]
    gap: str
    adopt: tuple[str, ...]


def load_evidence(path: str = EVIDENCE_FILE) -> dict[int, Evidence]:
    with open(path, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return {
        int(key): Evidence(
            technology_id=int(key),
            implementation=tuple(entry.get("implementation", ())),
            tests=tuple(entry.get("tests", ())),
            organ_evidence=tuple(entry.get("organ_evidence", ())),
            gap=entry.get("gap", ""),
            adopt=tuple(entry.get("adopt", ())),
        )
        for key, entry in raw.items()
    }


def audit(arsenal=None, evidence=None, root: str = ROOT) -> list[str]:
    """Return every status claim the evidence does not support."""
    arsenal = ARSENAL if arsenal is None else arsenal
    evidence = load_evidence() if evidence is None else evidence
    problems: list[str] = []
    if set(evidence) != set(arsenal):
        problems.append(
            f"evidence ids {sorted(set(evidence) ^ set(arsenal))} do not match the arsenal"
        )
    for technology_id in sorted(set(arsenal) & set(evidence)):
        spec, record = arsenal[technology_id], evidence[technology_id]
        label = f"technology {technology_id} ({spec.name}, {spec.status})"
        if not record.gap:
            problems.append(f"{label}: gap is required at every status")
        if not record.adopt:
            problems.append(f"{label}: name commodity mechanisms to adopt before building")
        for path in record.implementation + record.tests:
            if not os.path.exists(os.path.join(root, path)):
                problems.append(f"{label}: evidence path {path!r} does not exist")
        for reference in record.organ_evidence:
            organ, _, path = reference.partition(":")
            if not organ or not path:
                problems.append(f"{label}: organ evidence {reference!r} must be REPO:path")
        if spec.status == "executable":
            if not record.implementation:
                problems.append(f"{label}: executable requires a kernel implementation path")
            if not record.tests:
                problems.append(f"{label}: executable requires a kernel test path")
        elif spec.status == "partial":
            if not (record.implementation or record.organ_evidence):
                problems.append(f"{label}: partial requires kernel or organ evidence")
        elif spec.status == "target":
            if record.implementation or record.tests:
                problems.append(
                    f"{label}: target lists kernel evidence; re-audit and promote or remove it"
                )
    return problems


def render_table(arsenal=None, evidence=None) -> str:
    arsenal = ARSENAL if arsenal is None else arsenal
    evidence = load_evidence() if evidence is None else evidence
    lines = [
        TABLE_BEGIN,
        "| # | Technology | Status | Kernel evidence | Residual gap | Adopt before building |",
        "|---|---|---|---|---|---|",
    ]
    for technology_id in sorted(arsenal):
        spec, record = arsenal[technology_id], evidence[technology_id]
        refs = [f"`{p}`" for p in record.implementation]
        refs += [f"`{r}` (organ)" for r in record.organ_evidence]
        lines.append(
            f"| {technology_id} | {spec.name} | {spec.status} | "
            f"{'<br>'.join(refs) or '—'} | {record.gap} | {', '.join(record.adopt)} |"
        )
    counts = {status: sum(1 for s in arsenal.values() if s.status == status)
              for status in ("executable", "partial", "target")}
    lines.append("")
    lines.append(
        f"Totals: {counts['executable']} executable, {counts['partial']} partial, "
        f"{counts['target']} target."
    )
    lines.append(TABLE_END)
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if "--table" in argv:
        print(render_table())
        return 0
    problems = audit()
    for problem in problems:
        print(problem)
    print(f"{len(problems)} unsupported arsenal claims")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
