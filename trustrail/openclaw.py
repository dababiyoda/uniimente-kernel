"""Bounded OpenClaw boundary: named executors in, no arbitrary callables out."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from trustrail.credentials import TrustRailRefused
from trustrail.models import RealityStatus, SettlementAuthorization
from trustrail.rail import ProofToSettlementRail


class OpenClawTrustBoundary:
    """Host-side facade intended for exposure through an external MCP server.

    OpenClaw callers select a pre-registered executor. They cannot supply code,
    override the Consequence Gate, or invoke settlement commit.
    """

    def __init__(self, *, consequence_gate: Any, rail: ProofToSettlementRail,
                 proposal_factory: Callable[[dict[str, Any]], Any],
                 executors: dict[str, Callable[[Any], dict]],
                 allowed_callers: set[str], allowed_target_prefixes: tuple[str, ...],
                 live_actions_enabled: bool = False):
        if not executors or not allowed_callers or not allowed_target_prefixes:
            raise TrustRailRefused("OpenClaw boundary scopes cannot be empty")
        self.gate = consequence_gate
        self.rail = rail
        self.proposal_factory = proposal_factory
        self._executors = dict(executors)
        self.allowed_callers = frozenset(allowed_callers)
        self.allowed_target_prefixes = tuple(allowed_target_prefixes)
        self.live_actions_enabled = live_actions_enabled

    def execute_action(self, *, caller_id: str, executor_id: str,
                       proposal_input: dict[str, Any],
                       reality_status: RealityStatus = RealityStatus.SANDBOX):
        if caller_id not in self.allowed_callers:
            raise TrustRailRefused("OpenClaw caller is not allowlisted")
        executor = self._executors.get(executor_id)
        if executor is None:
            raise TrustRailRefused("executor is not pre-registered")
        if reality_status == RealityStatus.LIVE and not self.live_actions_enabled:
            raise TrustRailRefused("live OpenClaw actions are disabled")
        target = str(proposal_input.get("target", ""))
        if not any(target.startswith(prefix) for prefix in self.allowed_target_prefixes):
            raise TrustRailRefused("action target is outside the OpenClaw capability scope")
        proposal = self.proposal_factory(dict(proposal_input))
        actor = getattr(proposal, "actor", None)
        if actor is None and isinstance(proposal, dict):
            actor = proposal.get("actor")
        if actor != caller_id:
            raise TrustRailRefused("proposal actor does not match authenticated caller")
        return self.gate.run(proposal, executor=executor)

    def request_settlement(self, authorization: SettlementAuthorization, *,
                           caller_id: str, amount: str):
        if caller_id not in self.allowed_callers:
            raise TrustRailRefused("OpenClaw caller is not allowlisted")
        return self.rail.create_settlement_intent(
            authorization, requested_by=caller_id, amount=amount
        )

    def credential_status(self, credential_id: str) -> dict:
        return self.rail.credential_status(credential_id)

    def health(self) -> dict[str, Any]:
        return {
            "service": "uniimente-openclaw-trust-boundary",
            "live_actions_enabled": self.live_actions_enabled,
            "registered_executors": sorted(self._executors),
            "metrics": self.rail.metrics(),
        }
