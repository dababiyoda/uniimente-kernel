"""Venture contracts.

VentureAssessment enforces Hard Rule 3 at the type level:
``requires_human_approval`` is Literal[True] — it can never be set False.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from .base import KernelModel
from .institutional import ContextPacket


class OpportunityPacket(KernelModel):
    source: str
    signal_summary: str
    context: ContextPacket
    observed_at: datetime


class VentureAssessment(KernelModel):
    packet_id: str
    verdict: Literal["go", "defer", "kill", "needs_more_evidence"]
    reasoning_trace: list[str]
    requires_human_approval: Literal[True] = True
