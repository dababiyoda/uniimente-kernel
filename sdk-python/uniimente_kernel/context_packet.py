"""ContextPacket builders: every sensor speaks one structured language.

Extracted from DALEOBANKS ``services/context_packet.py`` (kernel Phase 2)
and generalized onto ``contracts/context-packet.schema.json``. Raw
articles, posts, DMs, trends, and self-signals are distilled into
``ContextPacketData`` — sanitized text plus extracted claims, stakes,
incentives, human cost, system failure, evidence needs, and injection
risk — before they can influence planning or generation. The firewall
runs here, once, at the boundary, so downstream consumers never touch raw
external text.

Generalization points versus the DALEOBANKS original:

- No ORM. ``ContextPacketData`` is a plain dataclass mirroring the kernel
  contract; organs adapt their persistence.
- Vault and firewall are injected, not singletons.
- The DALEOBANKS heuristics (claim extraction, marker lists, stakes
  logic) are preserved exactly. Contract-required fields the organ model
  lacked are derived conservatively and documented:

  - ``risk`` (contract enum) bands from the numeric scan risk:
    >= 0.7 high, >= 0.4 medium, else low.
  - ``recommended_action`` (contract enum) kernel default policy:
    high/medium risk -> human_review; evidence needed -> research_first;
    else save. Organs may override before emitting.
  - ``provenance.sanitized`` is always True by construction here.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

from uniimente_kernel.prompt_firewall import PromptFirewall
from uniimente_kernel.raw_vault import RawVault

_STAKES_HIGH_MARKERS = [
    "death", "died", "lawsuit", "outage", "breach", "emergency", "recall",
    "explosion", "crisis", "evacuation", "fatal",
]
_INCENTIVE_MARKERS = [
    "profit", "funding", "subsidy", "election", "lobbying", "bonus",
    "market share", "quarterly", "donor",
]
_HUMAN_COST_MARKERS = [
    "died", "deaths", "jobs lost", "layoffs", "evicted", "sick", "injured",
    "unemployed", "homeless", "waitlist",
]
_SYSTEM_FAILURE_MARKERS = [
    "outage", "backlog", "queue", "collapse", "failure", "shortage",
    "bottleneck", "delay", "understaffed", "cost overrun",
]
_SOURCE_MARKERS = ["http://", "https://", "source:", "according to"]

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class ContextPacketData:
    """Kernel contract shape for shared normalized sensor output."""

    source: str
    raw_ref: str
    text: str
    claims: List[str]
    evidence_needed: bool
    risk: str                       # low | medium | high (contract enum)
    recommended_action: str         # ignore | save | research_first | reply | post | human_review
    confidence: float
    packet_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    actor: Optional[str] = None
    topic: Optional[str] = None
    stakes: List[str] = field(default_factory=list)
    incentives: List[str] = field(default_factory=list)
    human_cost: Optional[str] = None
    system_failure: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    provenance: Dict[str, Any] = field(default_factory=dict)
    numeric_injection_risk: float = 0.0   # preserved scan detail; not in the contract

    def to_contract_dict(self) -> Dict[str, Any]:
        """Serialize to the contracts/context-packet.schema.json shape."""
        return {
            "packet_id": self.packet_id,
            "source": self.source,
            "raw_ref": self.raw_ref,
            "actor": self.actor,
            "topic": self.topic,
            "claims": self.claims,
            "stakes": self.stakes,
            "incentives": self.incentives,
            "human_cost": self.human_cost,
            "system_failure": self.system_failure,
            "evidence_needed": self.evidence_needed,
            "risk": self.risk,
            "recommended_action": self.recommended_action,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "provenance": self.provenance,
        }


def _extract_claims(text: str) -> List[str]:
    """Sentences that assert something checkable (figures, studies)."""
    claims = []
    for sentence in _SENTENCE_RE.split(text or ""):
        sentence = sentence.strip()
        if not sentence:
            continue
        lower = sentence.lower()
        if any(c.isdigit() for c in sentence) or "%" in sentence or "$" in sentence \
                or "study" in lower or "research" in lower:
            claims.append(sentence[:200])
    return claims[:5]


def _first_marker(lower: str, markers: List[str]) -> Optional[str]:
    for marker in markers:
        if marker in lower:
            return marker
    return None


def _risk_band(numeric_risk: float) -> str:
    if numeric_risk >= 0.7:
        return "high"
    if numeric_risk >= 0.4:
        return "medium"
    return "low"


def _default_action(numeric_risk: float, evidence_needed: bool) -> str:
    if numeric_risk >= 0.4:
        return "human_review"
    if evidence_needed:
        return "research_first"
    return "save"


def build_packet(
    *,
    source: str,
    raw_ref: str = "",
    text: str = "",
    actor: Optional[str] = None,
    topic: Optional[str] = None,
    trust: str = "untrusted",
    firewall: Optional[PromptFirewall] = None,
    vault: Optional[RawVault] = None,
) -> ContextPacketData:
    fw = firewall or PromptFirewall()
    scan = fw.scan(text or "")
    sanitized = fw.sanitize(text or "")
    lower = sanitized.lower()

    # The sanitizer never destroys the source: raw text goes to the vault
    # verbatim (with provenance) so audits and replays see what actually
    # arrived, while only the sanitized form may travel toward prompts.
    vault_id = None
    if text and vault is not None:
        vault_id = vault.deposit(
            source=source, text=text, raw_ref=raw_ref, actor=actor,
            meta={"trust": trust, "injection_patterns": scan["patterns"]},
            instruction_shaped=scan["risk"] >= 0.4,
        )

    claims = _extract_claims(sanitized)
    has_source = any(marker in lower for marker in _SOURCE_MARKERS)
    stakes: List[str] = []
    high = _first_marker(lower, _STAKES_HIGH_MARKERS)
    if high:
        stakes.append("high")
    elif claims:
        stakes.append("medium")
    else:
        stakes.append("low")

    evidence_needed = bool(claims) and not has_source
    incentive = _first_marker(lower, _INCENTIVE_MARKERS)
    numeric_risk = scan["risk"]

    return ContextPacketData(
        source=source,
        raw_ref=str(raw_ref or ""),
        actor=actor,
        topic=topic,
        text=sanitized,
        claims=claims,
        stakes=stakes,
        incentives=[incentive] if incentive else [],
        human_cost=_first_marker(lower, _HUMAN_COST_MARKERS),
        system_failure=_first_marker(lower, _SYSTEM_FAILURE_MARKERS),
        evidence_needed=evidence_needed,
        risk=_risk_band(numeric_risk),
        recommended_action=_default_action(numeric_risk, evidence_needed),
        confidence=round(max(0.0, 1.0 - numeric_risk * 0.7), 3),
        numeric_injection_risk=numeric_risk,
        provenance={
            "trust": trust,
            "injection_patterns": scan["patterns"],
            "vault_id": vault_id,
            "evidence_refs": [],
            "sanitized": True,
        },
    )


def from_mention(mention: Dict[str, Any], topic: Optional[str] = None, **kw) -> ContextPacketData:
    return build_packet(
        source="mention",
        raw_ref=mention.get("id", ""),
        text=mention.get("text", ""),
        actor=mention.get("username") or mention.get("author_id"),
        topic=topic,
        **kw,
    )


def from_dm(event: Dict[str, Any], **kw) -> ContextPacketData:
    return build_packet(
        source="dm",
        raw_ref=event.get("id", ""),
        text=event.get("text", ""),
        actor=event.get("sender_id"),
        **kw,
    )


def from_timeline_post(post: Dict[str, Any], **kw) -> ContextPacketData:
    return build_packet(
        source="timeline",
        raw_ref=post.get("id", ""),
        text=post.get("text", ""),
        actor=post.get("username") or post.get("author_id"),
        **kw,
    )


def from_trend(trend: Any, **kw) -> ContextPacketData:
    name = trend.get("name") if isinstance(trend, dict) else str(trend)
    return build_packet(source="trend", text=str(name or ""), topic=str(name or ""), **kw)


def from_self_signal(signal_id: str, text: str, **kw) -> ContextPacketData:
    # The operator is trusted, but their thoughts are still signals to
    # weigh, so they travel in the same structured form as everything else.
    return build_packet(
        source="self_signal",
        raw_ref=signal_id,
        text=text,
        actor="operator",
        trust="operator",
        **kw,
    )


__all__ = [
    "ContextPacketData",
    "build_packet",
    "from_mention",
    "from_dm",
    "from_timeline_post",
    "from_trend",
    "from_self_signal",
]
