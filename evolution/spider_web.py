"""Spider-Web Integrity Engine.

Doctrine: test every surviving strategy as a complete institution across
exactly eight sides:

    1. Reality and failure geometry.
    2. Power and participant geometry.
    3. Eligibility and permission.
    4. Default routing and access.
    5. Proof, truth, and reputation.
    6. Settlement and capital physics.
    7. Distribution, entanglement, and counter-position.
    8. Reliability, governance, regeneration, succession, and continuity.

Every major mechanism must map to at least one governing super-node:
    Eligibility, Default Routing, Proof and Truth, Cashflow and Settlement.
Decorative mechanisms (mapping to none) are removed.

A complete architecture requires: a bounded transaction; a real
beneficiary; a buyer or mandate-capable actor where applicable; a lawful
permission path; an accepted artifact; an external consequence;
participant benefit; a 90-day falsification test; fundable reliability;
recovery; and kill criteria.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

EIGHT_SIDES = (
    "reality_failure_geometry",
    "power_participant_geometry",
    "eligibility_permission",
    "default_routing_access",
    "proof_truth_reputation",
    "settlement_capital_physics",
    "distribution_entanglement_counterposition",
    "reliability_governance_regeneration_succession_continuity",
)

SUPER_NODES = ("eligibility", "default_routing", "proof_and_truth", "cashflow_and_settlement")

COMPLETENESS_REQUIREMENTS = (
    "bounded_transaction", "real_beneficiary", "buyer_or_mandate_actor",
    "lawful_permission_path", "accepted_artifact", "external_consequence",
    "participant_benefit", "ninety_day_falsification_test",
    "fundable_reliability", "recovery_path", "kill_criteria",
)


@dataclass
class MechanismMap:
    """One mechanism mapped to its governing super-node, or none (decorative)."""
    mechanism: str
    super_node: str | None          # must be in SUPER_NODES or None

    @property
    def decorative(self) -> bool:
        return self.super_node is None


@dataclass
class SpiderWebAudit:
    """The complete-institution audit of one strategy."""
    subject: str
    sides: dict[str, dict] = field(default_factory=dict)     # side -> {ok, notes}
    mechanisms: list[MechanismMap] = field(default_factory=list)
    completeness: dict[str, bool] = field(default_factory=dict)
    decorative_removed: list[str] = field(default_factory=list)

    def set_side(self, side: str, ok: bool, notes: str) -> None:
        if side not in EIGHT_SIDES:
            raise ValueError(f"unknown side {side!r}; must be one of the eight")
        self.sides[side] = {"ok": bool(ok), "notes": notes}

    def map_mechanism(self, mechanism: str, super_node: str | None) -> None:
        if super_node is not None and super_node not in SUPER_NODES:
            raise ValueError(f"{super_node!r} is not a governing super-node")
        self.mechanisms.append(MechanismMap(mechanism, super_node))

    def remove_decorative(self) -> list[str]:
        """Decorative mechanisms (no super-node) are removed and named."""
        self.decorative_removed = [m.mechanism for m in self.mechanisms if m.decorative]
        self.mechanisms = [m for m in self.mechanisms if not m.decorative]
        return self.decorative_removed

    def set_completeness(self, requirement: str, ok: bool) -> None:
        if requirement not in COMPLETENESS_REQUIREMENTS:
            raise ValueError(f"unknown completeness requirement {requirement!r}")
        self.completeness[requirement] = bool(ok)

    @property
    def sides_passed(self) -> list[str]:
        return [s for s, v in self.sides.items() if v["ok"]]

    @property
    def sides_failed(self) -> list[str]:
        return [s for s in EIGHT_SIDES if not self.sides.get(s, {}).get("ok", False)]

    @property
    def missing_completeness(self) -> list[str]:
        return [r for r in COMPLETENESS_REQUIREMENTS if not self.completeness.get(r, False)]

    @property
    def verdict(self) -> str:
        if self.sides_failed:
            return "INCOMPLETE"
        if self.missing_completeness:
            return "INCOMPLETE"
        if any(m.decorative for m in self.mechanisms):
            return "DECORATIVE_MECHANISMS_PRESENT"
        return "COMPLETE"

    def to_dict(self) -> dict:
        return {"subject": self.subject, "verdict": self.verdict,
                "sides": self.sides, "sides_failed": self.sides_failed,
                "missing_completeness": self.missing_completeness,
                "mechanisms": [{"mechanism": m.mechanism, "super_node": m.super_node}
                               for m in self.mechanisms],
                "decorative_removed": self.decorative_removed}
