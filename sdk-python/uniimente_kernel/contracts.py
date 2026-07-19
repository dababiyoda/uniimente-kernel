"""Wire contracts: the stable protocol between organs.

Unified in kernel Phase 3 from DALEOBANKS ``services/venture_protocol.py``
and WealthMachineIntelligence ``src/services/venture_protocol.py`` — the two
mirrored copies are replaced by imports of this module. The validators here
are the exact union both repos ran: WMI's strict inbound packet check and
DALEOBANKS' outbound serializers, assessment check, and identity gate, plus
WMI's rule that an assessment with ``requires_human_approval`` not equal to
True is a contract violation everywhere, on both sides of the wire.

What these types are: the *signal wire* — a business signal out, an
evaluation back. Formalized as kernel contracts
``contracts/venture-signal.schema.json`` and
``contracts/signal-assessment.schema.json`` (version 1.1, byte-compatible
with what the organs already exchange).

What they are not: the institutional ``OpportunityPacket`` /
``VentureAssessment`` of ``contracts/opportunity-packet.schema.json`` and
``contracts/venture-assessment.schema.json`` — the mature artifacts with
pain/budget owners, governing bottlenecks, adversarial cases, and SPIFFE
identities. A signal matures into an institutional packet only through
evaluation and a human gate; nothing here fabricates those fields.
``docs/EXTRACTION_MAP.md`` records the maturation mapping.

The core rule stands: the machine prepares, the human authorizes, the
world responds, the system learns. Nothing in this module executes
anything, and inbound wire data is untrusted input — validated as data,
never followed as instruction.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

SCHEMA_VERSION = "1.1"

ALLOWED_SIGNAL_TYPES = frozenset({
    "social_complaint",
    "news_trend",
    "regulatory_shift",
    "audience_reaction",
    "repeated_question",
    "relationship_signal",
    "content_opportunity",
    "product_opportunity",
    "partnership_opportunity",
    "operator_thought",
})

ALLOWED_GO_NO_GO = frozenset({"go", "defer", "kill", "needs_more_evidence"})

ALLOWED_URGENCY = frozenset({"low", "medium", "high"})

ALLOWED_STATUSES = frozenset({"pending", "approved", "rejected", "sent", "assessed"})

ALLOWED_RISK_LEVELS = frozenset({"low", "medium", "high"})

# ValidationResult contract (organ-side storage today; the outcome wire
# arrives with the event spine in Phase 4): outcomes the world can hand
# back. Negative (no response) is a legitimate, recorded outcome — never
# an absence.
ALLOWED_RESULT_CLASSIFICATIONS = frozenset({
    "success", "failure", "mixed", "inconclusive", "negative",
})

# Evidence tiers, strongest first. Payment outranks commitment outranks
# conversation outranks engagement outranks passive observation.
ALLOWED_EVIDENCE_TIERS = frozenset({
    "payment", "commitment", "conversation", "engagement", "observation",
})

ALLOWED_IDENTITY_TYPES = frozenset({
    "main_identity",
    "brand_account",
    "project_account",
    "pseudonymous_brand",
    "faceless_media_page",
    "company_page",
})

FORBIDDEN_IDENTITY_TYPES = frozenset({
    "fake_person",
    "impersonation",
    "fake_expert_identity",
    "ban_evasion_account",
    "engagement_manipulation_account",
})

# Risk flags that force human/legal escalation. A packet carrying any of
# these is never a "go" — serious money/legal/contract decisions belong to
# the operator, not the engine.
LEGAL_RISK_FLAGS = frozenset({"legal_risk", "regulated_product", "licensing_required"})

# Finance content must remain educational: no personalized investment
# advice, no income promises. This flag travels on the packet and hardens
# the assessment (legal review required, educational reasons attached).
FINANCE_EDUCATION_FLAG = "finance_education_only"

# Hardcoded, non-configurable media-company policy. These are not settings.
LANE_POLICY = (
    "No account may be used to simulate independent public support for another account.",
    "No fake consensus.",
    "No coordinated inauthentic amplification.",
    "No auto-DMs at scale.",
    "No impersonation.",
    "No undisclosed sponsorships.",
    "No stolen media.",
    "No guaranteed financial claims.",
    "No personalized legal or financial advice unless reviewed by a qualified professional.",
    "Every account lane must have a distinct purpose, audience, and content policy.",
)


# ---------------------------------------------------------------------- #
# Outbound: dataclass -> wire (emitter side)
# ---------------------------------------------------------------------- #
def packet_to_wire(packet: Any) -> Dict[str, Any]:
    """Serialize a signal packet for transport (JSON-safe)."""
    payload = asdict(packet)
    payload["schema_version"] = SCHEMA_VERSION
    payload["created_at"] = packet.created_at.isoformat()
    return payload


def assessment_to_wire(assessment: Any) -> Dict[str, Any]:
    payload = asdict(assessment)
    payload["schema_version"] = SCHEMA_VERSION
    payload["created_at"] = assessment.created_at.isoformat()
    return payload


# ---------------------------------------------------------------------- #
# Inbound: wire -> validated data (receiver side)
# ---------------------------------------------------------------------- #
def _require_str(payload: Dict[str, Any], key: str, default: str = "") -> str:
    value = payload.get(key, default)
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _require_str_list(payload: Dict[str, Any], key: str) -> List[str]:
    value = payload.get(key) or []
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"{key} must be a list of strings")
    return value


def validate_packet_wire(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate an inbound signal packet and return a normalized copy.
    Raises ValueError on a contract violation.

    Every string field is treated strictly as data: it is stored, scored,
    and echoed back in drafts for human review — never interpreted as an
    instruction to this system.
    """
    if not isinstance(payload, dict):
        raise ValueError("opportunity packet payload must be an object")

    packet_id = _require_str(payload, "id")
    if not packet_id:
        raise ValueError("id is required")

    signal_type = _require_str(payload, "signal_type", "operator_thought") or "operator_thought"
    if signal_type not in ALLOWED_SIGNAL_TYPES:
        raise ValueError(f"signal_type must be one of {sorted(ALLOWED_SIGNAL_TYPES)}")

    urgency = _require_str(payload, "urgency", "medium") or "medium"
    if urgency not in ALLOWED_URGENCY:
        raise ValueError(f"urgency must be one of {sorted(ALLOWED_URGENCY)}")

    core_thesis = _require_str(payload, "core_thesis")
    observed_pain = _require_str(payload, "observed_pain")
    if not core_thesis and not observed_pain:
        raise ValueError("at least one of core_thesis or observed_pain is required")

    confidence = payload.get("confidence", 0.5)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        raise ValueError("confidence must be a number")
    if not (0.0 <= confidence <= 1.0):
        raise ValueError("confidence must be within [0, 1]")

    return {
        "id": packet_id,
        "source": _require_str(payload, "source"),
        "source_ref": _require_str(payload, "source_ref"),
        "signal_type": signal_type,
        "observed_pain": observed_pain,
        "core_thesis": core_thesis,
        "audience": _require_str(payload, "audience"),
        "cultural_context": _require_str(payload, "cultural_context"),
        "language": _require_str(payload, "language", "en") or "en",
        "customer_segment": _require_str(payload, "customer_segment"),
        "buyer_type": _require_str(payload, "buyer_type"),
        "urgency": urgency,
        "evidence": _require_str_list(payload, "evidence"),
        "possible_offer": _require_str(payload, "possible_offer"),
        "monetization_paths": _require_str_list(payload, "monetization_paths"),
        "risk_flags": _require_str_list(payload, "risk_flags"),
        "smallest_validation_action": _require_str(payload, "smallest_validation_action"),
        "confidence": confidence,
        "schema_version": _require_str(payload, "schema_version", SCHEMA_VERSION) or SCHEMA_VERSION,
    }


def validate_assessment_wire(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a signal assessment payload, on either side of the wire.
    An assessment that could execute anything is a contract violation:
    ``requires_human_approval`` must be exactly True."""
    if not isinstance(payload, dict):
        raise ValueError("assessment payload must be an object")
    go_no_go = payload.get("go_no_go")
    if go_no_go not in ALLOWED_GO_NO_GO:
        raise ValueError(f"go_no_go must be one of {sorted(ALLOWED_GO_NO_GO)}")
    if not payload.get("opportunity_packet_id"):
        raise ValueError("opportunity_packet_id is required")
    score = payload.get("opportunity_score")
    if score is not None and not (0.0 <= float(score) <= 1.0):
        raise ValueError("opportunity_score must be within [0, 1]")
    if payload.get("requires_human_approval") is not True:
        raise ValueError("requires_human_approval must be true; assessments never self-execute")
    return payload


def validate_identity_type(identity_type: str) -> str:
    """The load-bearing gate for account lanes: authentic lanes only."""
    if identity_type in FORBIDDEN_IDENTITY_TYPES:
        raise ValueError(
            f"identity_type '{identity_type}' is forbidden: account lanes are "
            "brands and projects, never fake people, impersonation, or "
            "engagement manipulation"
        )
    if identity_type not in ALLOWED_IDENTITY_TYPES:
        raise ValueError(
            f"identity_type '{identity_type}' is not recognized; allowed: "
            f"{sorted(ALLOWED_IDENTITY_TYPES)}"
        )
    return identity_type


__all__ = [
    "SCHEMA_VERSION",
    "ALLOWED_SIGNAL_TYPES",
    "ALLOWED_GO_NO_GO",
    "ALLOWED_URGENCY",
    "ALLOWED_STATUSES",
    "ALLOWED_RISK_LEVELS",
    "ALLOWED_RESULT_CLASSIFICATIONS",
    "ALLOWED_EVIDENCE_TIERS",
    "ALLOWED_IDENTITY_TYPES",
    "FORBIDDEN_IDENTITY_TYPES",
    "LEGAL_RISK_FLAGS",
    "FINANCE_EDUCATION_FLAG",
    "LANE_POLICY",
    "packet_to_wire",
    "assessment_to_wire",
    "validate_packet_wire",
    "validate_assessment_wire",
    "validate_identity_type",
]
