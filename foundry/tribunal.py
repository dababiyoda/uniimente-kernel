"""Eight-sided Spider-Web tribunal for Advantage Architectures.

The tribunal is an evidence and disagreement contract. It does not generate
truth, authority, or execution. Every lens must be represented exactly once,
negative findings are preserved, and the architecture must explicitly address
Eligibility, Default Routing, Proof and Truth, and Cashflow and Settlement.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
from typing import Iterable

from .advantage import AdvantageArchitecture, AdvantageRefused

TRIBUNAL_LENSES = (
    "reality_and_failure_geometry",
    "power_and_participant_geometry",
    "eligibility_and_permission",
    "routing_and_access",
    "proof_truth_and_reputation",
    "settlement_and_capital_physics",
    "distribution_and_counter_position",
    "reliability_governance_regeneration_continuity",
)
CONTROL_SUPER_NODES = (
    "eligibility",
    "default_routing",
    "proof_and_truth",
    "cashflow_and_settlement",
)


class TribunalJudgment(str, Enum):
    PASS = "PASS"
    RECONFIGURE = "RECONFIGURE"
    BLOCK = "BLOCK"


class TribunalVerdict(str, Enum):
    PASSED = "PASSED"
    RECONFIGURE = "RECONFIGURE"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class TribunalFinding:
    lens: str
    judgment: TribunalJudgment
    thesis: str
    evidence_refs: tuple[str, ...]
    strongest_countercase: str
    required_changes: tuple[str, ...] = ()
    addressed_control_nodes: tuple[str, ...] = ()
    confidence: float = 0.0

    def validate(self) -> None:
        if self.lens not in TRIBUNAL_LENSES:
            raise AdvantageRefused(f"unknown tribunal lens {self.lens!r}")
        if not self.thesis or not self.strongest_countercase:
            raise AdvantageRefused("tribunal thesis and strongest countercase are required")
        if not self.evidence_refs:
            raise AdvantageRefused("every tribunal finding requires evidence")
        if not 0.0 <= self.confidence <= 1.0:
            raise AdvantageRefused("tribunal confidence must be within [0,1]")
        unknown = sorted(set(self.addressed_control_nodes) - set(CONTROL_SUPER_NODES))
        if unknown:
            raise AdvantageRefused(f"unknown control super-nodes: {unknown}")
        if self.judgment is TribunalJudgment.RECONFIGURE and not self.required_changes:
            raise AdvantageRefused("RECONFIGURE findings must specify required changes")


@dataclass(frozen=True)
class TribunalReport:
    report_id: str
    architecture_hash: str
    verdict: TribunalVerdict
    findings: tuple[TribunalFinding, ...]
    addressed_control_nodes: tuple[str, ...]
    strongest_countercase: str
    required_changes: tuple[str, ...]

    @property
    def digest(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), default=str)
        return "sha256:" + sha256(payload.encode()).hexdigest()


class SpiderWebTribunal:
    """Evaluate a supplied set of eight evidence-backed findings."""

    def __init__(self, ledger=None) -> None:
        self.ledger = ledger
        self._reports: dict[str, TribunalReport] = {}

    def evaluate(
        self,
        architecture: AdvantageArchitecture,
        findings: Iterable[TribunalFinding],
    ) -> TribunalReport:
        finding_list = tuple(findings)
        for finding in finding_list:
            finding.validate()
        lenses = [finding.lens for finding in finding_list]
        if len(lenses) != len(TRIBUNAL_LENSES) or set(lenses) != set(TRIBUNAL_LENSES):
            raise AdvantageRefused("all eight tribunal lenses must appear exactly once")

        addressed = tuple(sorted({
            node for finding in finding_list for node in finding.addressed_control_nodes
        }))
        missing_nodes = sorted(set(CONTROL_SUPER_NODES) - set(addressed))
        blocks = [finding for finding in finding_list if finding.judgment is TribunalJudgment.BLOCK]
        reconfigure = [
            finding for finding in finding_list
            if finding.judgment is TribunalJudgment.RECONFIGURE
        ]
        if blocks:
            verdict = TribunalVerdict.REJECTED
        elif reconfigure or missing_nodes:
            verdict = TribunalVerdict.RECONFIGURE
        else:
            verdict = TribunalVerdict.PASSED

        required_changes = tuple(dict.fromkeys(
            [change for finding in finding_list for change in finding.required_changes]
            + [f"address control super-node: {node}" for node in missing_nodes]
        ))
        countercase_finding = min(
            finding_list,
            key=lambda finding: (
                0 if finding.judgment is TribunalJudgment.BLOCK else
                1 if finding.judgment is TribunalJudgment.RECONFIGURE else 2,
                finding.confidence,
                finding.lens,
            ),
        )
        seed = f"{architecture.digest}|{'|'.join(sorted(lenses))}"
        report = TribunalReport(
            report_id="tribunal-" + sha256(seed.encode()).hexdigest()[:16],
            architecture_hash=architecture.digest,
            verdict=verdict,
            findings=finding_list,
            addressed_control_nodes=addressed,
            strongest_countercase=countercase_finding.strongest_countercase,
            required_changes=required_changes,
        )
        prior = self._reports.get(report.report_id)
        if prior is not None and prior.digest != report.digest:
            raise AdvantageRefused("tribunal report id collision with different evidence")
        self._reports[report.report_id] = report
        if self.ledger is not None:
            self.ledger.append("event", {
                "type": "advantage.tribunal_completed",
                "report_id": report.report_id,
                "report_hash": report.digest,
                "architecture_hash": report.architecture_hash,
                "verdict": report.verdict.value,
                "addressed_control_nodes": list(report.addressed_control_nodes),
                "strongest_countercase": report.strongest_countercase,
                "required_changes": list(report.required_changes),
                "findings": [asdict(finding) for finding in report.findings],
            })
        return report

    def require_passed(
        self, architecture: AdvantageArchitecture, report: TribunalReport
    ) -> None:
        stored = self._reports.get(report.report_id)
        if stored is None or stored.digest != report.digest:
            raise AdvantageRefused("tribunal report is unknown or changed")
        if report.architecture_hash != architecture.digest:
            raise AdvantageRefused("tribunal report belongs to another architecture")
        if report.verdict is not TribunalVerdict.PASSED:
            raise AdvantageRefused(
                f"architecture has not passed the tribunal: {report.verdict.value}"
            )
        if set(report.addressed_control_nodes) != set(CONTROL_SUPER_NODES):
            raise AdvantageRefused("all four control super-nodes must be addressed")

    def get(self, report_id: str) -> TribunalReport | None:
        return self._reports.get(report_id)
