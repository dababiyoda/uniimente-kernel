"""Typed victim-protection and deterrence modeling. Output is a review packet only."""
from dataclasses import asdict, dataclass, field

from .contracts import CognitionError, ConsequenceVector, number


@dataclass(frozen=True)
class AffectedParty:
    affected_party: str
    immediate_harm: float = 0
    continuing_harm: float = 0
    retaliation_risk: float = 0
    privacy_risk: float = 0
    financial_harm: float = 0
    reputational_harm: float = 0
    rights_impact: float = 0
    evidence_at_risk: bool = False
    safe_contact_channel: str | None = None
    required_authority: str = "authenticated qualified human through the existing Kernel authority path"
    notification_obligations: list[str] = field(default_factory=list)
    containment_options: list[str] = field(default_factory=list)
    restitution_options: list[str] = field(default_factory=list)
    recurrence_controls: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not isinstance(self.affected_party, str) or not 1 <= len(self.affected_party) <= 128:
            raise CognitionError("bounded affected-party pseudonym required")
        for name in ("immediate_harm", "continuing_harm", "retaliation_risk", "privacy_risk", "financial_harm", "reputational_harm", "rights_impact"):
            number(getattr(self, name), low=0, high=1)
        if type(self.evidence_at_risk) is not bool:
            raise CognitionError("evidence_at_risk must be boolean")
        if not isinstance(self.required_authority, str) or not self.required_authority:
            raise CognitionError("required authority cannot be empty")
        if self.safe_contact_channel is not None and not isinstance(self.safe_contact_channel, str):
            raise CognitionError("safe_contact_channel must be a reference or unknown")
        for name in ("notification_obligations", "containment_options", "restitution_options", "recurrence_controls"):
            values = getattr(self, name)
            if not isinstance(values, list) or len(values) > 32 or any(not isinstance(v, str) for v in values):
                raise CognitionError("bounded proposal/reference lists required")


def assess(data, geometry):
    from .solvers import result
    party = AffectedParty(**data["affected_party"])
    consequences = ConsequenceVector(**data.get("consequences", {}))
    options = data.get("interventions", [])
    if len(options) > 32:
        raise CognitionError("at most 32 supplied intervention proposals")
    modeled = []
    for option in options:
        # Legality and consent are assertions requiring human authentication, not model findings.
        permitted = option.get("lawful") is True and option.get("consent") is True
        risk = ConsequenceVector(**option.get("consequences", {}))
        blocked = not permitted or risk.prohibited or consequences.prohibited
        benefit = number(option["exploit_payoff"], low=0)
        opportunity = number(option["opportunity"], low=0, high=1)
        detection = number(option["detection_probability"], low=0, high=1)
        durability = number(option["evidence_durability"], low=0, high=1)
        accountability = number(option["accountability_probability"], low=0, high=1)
        restitution = number(option["restitution_cost"], low=0)
        modeled.append({"id": option["id"], "blocked": blocked,
                        "conditional_expected_exploit_payoff": benefit * opportunity - detection * durability * accountability * restitution,
                        "consequences": asdict(risk),
                        "limitations": "supplied hypothetical incentives; legality, consent and empirical probabilities unverified"})
    actions = []
    if party.immediate_harm or party.continuing_harm:
        actions.extend(["protect_now", "contain_harm"])
    if party.evidence_at_risk:
        actions.append("preserve_evidence")
    actions.extend(["investigate", "escalate", "repair", "prevent_recurrence"])
    out = {"affected_party": asdict(party), "review_priorities": actions, "interventions": modeled,
           "recommendation": None, "authority_created": False}
    proof = {"payoffs": modeled, "strategies": "supplied proposals only", "value": None,
             "constraints": {"rights_are_hard_constraints": True, "lawful_and_consensual_required": True,
                            "vector": asdict(consequences), "human_legitimate_authority_required": True}}
    return result(out, proof, status="HUMAN_REVIEW_REQUIRED",
                  missing=("authenticated legal/consent judgment, empirical input validation and victim-safe review",))
