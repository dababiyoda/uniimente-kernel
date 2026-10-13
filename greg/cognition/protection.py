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
    investigation_scope: list[str] = field(default_factory=list)
    disclosure_controls: list[str] = field(default_factory=list)

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
        for name in ("notification_obligations", "containment_options", "restitution_options", "recurrence_controls",
                     "investigation_scope", "disclosure_controls"):
            values = getattr(self, name)
            if not isinstance(values, list) or len(values) > 32 or any(not isinstance(v, str) for v in values):
                raise CognitionError("bounded proposal/reference lists required")


# Lawful deterrence works through evidence, detection and legitimate process. These kinds
# are refused before anything is modeled; an unknown kind is malformed input.
PROHIBITED_KINDS = ("threat", "retaliation", "intimidation", "extortion", "deception", "doxxing",
                    "unconsented_surveillance", "vigilantism", "harassment", "coercion", "sabotage",
                    "unauthorized_identification", "corrupt_influence")
LAWFUL_KINDS = ("detection", "evidence_preservation", "access_control", "process_change", "independent_audit",
                "victim_support", "report_to_authority", "contractual_remedy", "transparency", "restitution")
# Which term of the incentive each modeled input moves (Nagin 2013: certainty deters more reliably than severity).
LEVERS = {"opportunity": "opportunity", "detection_probability": "certainty", "evidence_durability": "certainty",
          "accountability_probability": "certainty", "restitution_cost": "severity", "exploit_payoff": "opportunity"}


def _gaps(party):
    gaps = []
    if (party.immediate_harm >= .5 or party.continuing_harm >= .5) and not party.containment_options:
        gaps.append("harm is ongoing or immediate but no containment option is named")
    if party.evidence_at_risk and "preserve_evidence" not in party.containment_options and not party.investigation_scope:
        gaps.append("evidence is at risk; name how it is preserved and who may access it")
    if party.retaliation_risk >= .5 and not party.disclosure_controls:
        gaps.append("retaliation risk is material; disclosure controls are required before anyone is contacted")
    if (party.immediate_harm or party.retaliation_risk) and party.safe_contact_channel is None:
        gaps.append("no safe contact channel is declared")
    return gaps


def assess(data, geometry):
    from .gates import evaluate
    from .solvers import result
    party = AffectedParty(**data["affected_party"])
    consequences = ConsequenceVector(**data.get("consequences", {}))
    options = data.get("interventions", [])
    if len(options) > 32:
        raise CognitionError("at most 32 supplied intervention proposals")
    modeled, refused = [], []
    for option in options:
        kind = option.get("kind", "process_change")
        if kind in PROHIBITED_KINDS:
            refused.append({"id": option["id"], "kind": kind, "why": "coercive or rights-violating; never modeled or ranked"})
            continue
        if kind not in LAWFUL_KINDS:
            raise CognitionError(f"unknown intervention kind {kind!r}")
        # Legality and consent come from records of decisions made elsewhere, never from a
        # bare assertion; a missing prohibition is not permission.
        records = list(option.get("legitimacy", []))
        for gate in ("lawful", "consent"):
            if option.get(gate) is False:
                records.append({"gate": "law" if gate == "lawful" else "consent", "state": "prohibited",
                                "origin": "self_asserted", "scope": "proposal", "provenance": "supplied flag"})
        gates = evaluate(records, consequential=True)
        risk = ConsequenceVector(**option.get("consequences", {}))
        hard = risk.prohibited or consequences.prohibited or option.get("lawful") is False or option.get("consent") is False
        blocked = hard or gates["verdict"] != "PASS"
        benefit = number(option["exploit_payoff"], low=0)
        opportunity = number(option["opportunity"], low=0, high=1)
        detection = number(option["detection_probability"], low=0, high=1)
        durability = number(option["evidence_durability"], low=0, high=1)
        accountability = number(option["accountability_probability"], low=0, high=1)
        restitution = number(option["restitution_cost"], low=0)
        levers = sorted({LEVERS[k] for k in option.get("moves", [])} if option.get("moves") else set())
        modeled.append({"id": option["id"], "kind": kind, "blocked": blocked,
                        "blocked_by": ([] if not hard else ["hard constraint"]) + gates["prohibited"] + gates["unresolved"],
                        "reaches_another_party": kind in ("report_to_authority", "contractual_remedy", "transparency", "restitution"),
                        "levers": levers, "severity_only": levers == ["severity"],
                        "conditional_expected_exploit_payoff": benefit * opportunity - detection * durability * accountability * restitution,
                        "consequences": asdict(risk), "legitimacy": gates,
                        "limitations": "supplied hypothetical incentives; empirical probabilities unverified"})
    actions = []
    if party.immediate_harm:
        actions.append("protect_now")
    if party.evidence_at_risk:
        actions.append("preserve_evidence")
    if party.immediate_harm or party.continuing_harm:
        actions.append("contain_harm")
    actions.extend(["investigate", "escalate", "repair", "prevent_recurrence"])
    out = {"affected_party": asdict(party), "review_priorities": actions, "interventions": modeled,
           "refused": refused, "gaps": _gaps(party), "recommendation": None, "authority_created": False}
    proof = {"payoffs": modeled, "strategies": "supplied proposals only", "value": None,
             "constraints": {"rights_are_hard_constraints": True, "lawful_and_consensual_required": True,
                            "legitimacy": "evidence-backed records; bare assertions settle nothing",
                            "refused_kinds": list(PROHIBITED_KINDS),
                            "vector": asdict(consequences), "human_legitimate_authority_required": True},
             "deterrence_note": ("certainty of detection and accountability deters more reliably than severity "
                                 "(Nagin 2013); a severity-only option is flagged, not preferred")}
    return result(out, proof, status="HUMAN_REVIEW_REQUIRED",
                  missing=("authenticated legal/consent judgment, empirical input validation and victim-safe review",))
