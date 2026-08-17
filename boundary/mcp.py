"""MCP 1.0.0 adapter into the proposal-only boundary."""
from __future__ import annotations

from datetime import datetime

from .core import AdmittedProposal, ProposalBoundary


class MCPBoundary:
    def __init__(self, core: ProposalBoundary):
        if not isinstance(core, ProposalBoundary):
            raise TypeError("core must be ProposalBoundary")
        self._core = core

    def admit(self, document: dict, *, now: datetime | None = None) -> AdmittedProposal:
        return self._core.admit(document, expected_protocol="mcp", now=now)


__all__ = ["MCPBoundary"]
