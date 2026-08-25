"""Institutional contracts.

InstitutionalEvent supports Hard Rule 4 (append-only spine): ``spine_seq`` is
assigned by the spine on append — never by callers. EvidencePacket carries the
``freshness_deadline`` the gate enforces (stale evidence fails closed).
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from .base import KernelModel


class InstitutionalEvent(KernelModel):
    event_type: str
    actor_id: str
    organ_id: str
    payload_hash: str
    spine_seq: int = -1  # set by the spine on append; -1 = not yet sequenced


class EvidencePacket(KernelModel):
    source_uri: str
    source_hash: str
    authority_class: Literal["primary", "secondary", "derived", "simulated"]
    claims: list[str]
    contradiction_state: Literal["none", "open", "resolved"] = "none"
    freshness_deadline: datetime


class ContextPacket(KernelModel):
    subject: str
    evidence: list[EvidencePacket] = []
    unknowns: list[str] = []
