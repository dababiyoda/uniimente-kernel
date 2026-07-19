"""Autonomy Licensing: evidence-earned autonomy, exact by construction.

Doctrine (AUTONOMY):
    Assign autonomy to exact capabilities, not personalities.
    Autonomy = Capability × Domain × Action × Resource × Target
               × Consequence Class × Environment × Budget × Duration.

    A0 Observe. A1 Classify. A2 Recommend. A3 Simulate. A4 Prepare.
    A5 Execute reversible low-risk actions. A6 Operate bounded recurring
    workflows. A7 Form temporary subordinate organs. A8 Steward one
    bounded operating domain. A9 Reserved human sovereignty.

    Promotion requires: repeated successful external outcomes; calibrated
    prediction; clean completion; policy fidelity; security; recovery;
    complete reconciliation; lower founder intervention; non-negative
    regenerative effect; and independent verification.
    Autonomy rises slowly. It falls immediately after severe failure.
    A missing outcome record blocks promotion.

Weakest-link rule: ALL promotion criteria must pass; the level granted is
bounded by the weakest criterion. A9 is never granted by this system.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

LEVELS = {
    0: "observe", 1: "classify", 2: "recommend", 3: "simulate", 4: "prepare",
    5: "execute_reversible_low_risk", 6: "operate_bounded_recurring_workflows",
    7: "form_temporary_subordinate_organs", 8: "steward_one_bounded_domain",
    9: "reserved_human_sovereignty",
}
MAX_GRANTABLE = 8          # A9 is reserved; this system never grants it

PROMOTION_CRITERIA = (
    "repeated_successful_external_outcomes", "calibrated_prediction",
    "clean_completion", "policy_fidelity", "security", "recovery",
    "complete_reconciliation", "lower_founder_intervention",
    "non_negative_regenerative_effect", "independent_verification",
)

SEVERE_FAILURES = ("harm", "concealment", "unauthorized_effect",
                   "reconciliation_forgery", "rights_violation")


@dataclass
class AutonomyTuple:
    """The exact dimensions of one autonomy grant."""
    capability: str
    domain: str
    action: str
    resource: str
    target: str
    consequence_class: str
    environment: str
    budget_usd: float
    duration: str                      # e.g. "30 days"

    def key(self) -> str:
        return "|".join([self.capability, self.domain, self.action, self.resource,
                         self.target, self.consequence_class, self.environment,
                         f"{self.budget_usd:.2f}", self.duration])


@dataclass
class PromotionEvidence:
    """The ten promotion criteria, each independently judged."""
    criteria: dict[str, bool]
    independent_verifier: str          # who ran independent verification
    founder_intervention_trend: str    # "declining" | "flat" | "rising"
    missing_outcome_records: int = 0

    def failures(self) -> list[str]:
        failed = [c for c in PROMOTION_CRITERIA if not self.criteria.get(c, False)]
        if self.missing_outcome_records > 0:
            failed.append(f"missing_outcome_records:{self.missing_outcome_records}")
        if self.founder_intervention_trend == "rising":
            failed.append("founder_intervention_rising")
        return failed


@dataclass
class AutonomyLicense:
    license_id: str
    subject: str                       # passport id of the capability holder
    tuple: AutonomyTuple
    level: int                         # 0..8 (9 never granted)
    issued_at: str
    history: list[dict] = field(default_factory=list)
    active: bool = True


class AutonomyAuthority:
    """Grants, promotes, and regresses autonomy licenses.

    Itself bounded: it cannot grant A9, cannot waive criteria, and every
    transition is recorded on the ledger with its evidence.
    """

    def __init__(self, ledger):
        self.ledger = ledger
        self._licenses: dict[str, AutonomyLicense] = {}
        self._by_subject_tuple: dict[tuple[str, str], str] = {}

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _record(self, kind: str, payload: dict) -> None:
        self.ledger.append("event", {"type": f"autonomy.{kind}", **payload})

    def issue(self, subject: str, tuple_: AutonomyTuple, level: int = 0) -> AutonomyLicense:
        if level > MAX_GRANTABLE:
            raise ValueError("A9 is reserved human sovereignty; never granted by the system")
        import uuid
        lic = AutonomyLicense(license_id=str(uuid.uuid4()), subject=subject, tuple=tuple_,
                              level=level, issued_at=self._now(),
                              history=[{"event": "issued", "level": level, "at": self._now()}])
        self._licenses[lic.license_id] = lic
        self._by_subject_tuple[(subject, tuple_.key())] = lic.license_id
        self._record("issued", {"subject": subject, "tuple": asdict(tuple_), "level": level})
        return lic

    def promote(self, license_id: str, evidence: PromotionEvidence) -> AutonomyLicense:
        lic = self._licenses[license_id]
        if not lic.active:
            raise ValueError("license is regressed/inactive; renewal requires fresh cycle")
        if lic.level >= MAX_GRANTABLE:
            raise ValueError(f"already at max grantable level A{MAX_GRANTABLE}")
        failures = evidence.failures()
        if failures:
            self._record("promotion_refused", {"license_id": license_id, "failures": failures})
            raise ValueError(f"promotion criteria unmet (weakest link): {failures}")
        lic.level += 1
        lic.history.append({"event": "promoted", "level": lic.level, "at": self._now(),
                            "verifier": evidence.independent_verifier})
        self._record("promoted", {"license_id": license_id, "level": lic.level,
                                  "verifier": evidence.independent_verifier})
        return lic

    def regress(self, license_id: str, *, failure_class: str, detail: str) -> AutonomyLicense:
        """Autonomy falls IMMEDIATELY after severe failure. No ceremony."""
        lic = self._licenses[license_id]
        if failure_class in SEVERE_FAILURES:
            lic.level = 0
            lic.active = False
        else:
            lic.level = max(0, lic.level - 1)
        lic.history.append({"event": "regressed", "failure_class": failure_class,
                            "detail": detail, "level": lic.level, "at": self._now()})
        self._record("regressed", {"license_id": license_id, "failure_class": failure_class,
                                   "detail": detail, "level": lic.level})
        return lic

    def renew(self, license_id: str, evidence: PromotionEvidence) -> AutonomyLicense:
        """Renewal after regression requires a fresh, complete evidence cycle."""
        lic = self._licenses[license_id]
        failures = evidence.failures()
        if failures:
            raise ValueError(f"renewal criteria unmet: {failures}")
        lic.active = True
        lic.history.append({"event": "renewed", "at": self._now(),
                            "verifier": evidence.independent_verifier})
        self._record("renewed", {"license_id": license_id})
        return lic

    def level_of(self, subject: str, tuple_: AutonomyTuple) -> int:
        lid = self._by_subject_tuple.get((subject, tuple_.key()))
        if lid is None:
            return 0
        lic = self._licenses[lid]
        return lic.level if lic.active else 0
