"""MCP tool surface for OpenClaw.

The optional ``mcp>=1,<2`` package is intentionally imported lazily so the
kernel does not acquire a runtime dependency when this integration is unused.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from trustrail.models import RealityStatus, SettlementAuthorization
from trustrail.openclaw import OpenClawTrustBoundary


def _wire(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return value
    return {"result": str(value)}


def create_server(boundary: OpenClawTrustBoundary, *, authenticated_caller_id: str):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - optional integration dependency
        raise RuntimeError("OpenClaw MCP integration requires mcp>=1,<2") from exc

    server = FastMCP("UNIIMENTE Trust Rail")

    @server.tool()
    def execute_bounded_action(executor_id: str, proposal: dict[str, Any],
                               reality_status: str = "SANDBOX") -> dict[str, Any]:
        """Route one proposal through a named executor and the Consequence Gate."""
        bound_proposal = dict(proposal)
        bound_proposal["actor"] = authenticated_caller_id
        result = boundary.execute_action(
            caller_id=authenticated_caller_id,
            executor_id=executor_id,
            proposal_input=bound_proposal,
            reality_status=RealityStatus(reality_status),
        )
        return _wire(result)

    @server.tool()
    def request_settlement_intent(authorization: dict[str, Any], amount: str) -> dict[str, Any]:
        """Create an intent from principal-signed authority; never commit payment."""
        payload = dict(authorization)
        payload["reality_status"] = RealityStatus(payload["reality_status"])
        intent = boundary.request_settlement(
            SettlementAuthorization(**payload),
            caller_id=authenticated_caller_id,
            amount=amount,
        )
        return intent.to_dict()

    @server.tool()
    def verify_outcome_credential(credential_id: str) -> dict[str, Any]:
        """Return the signed credential plus its current revocation state."""
        return boundary.credential_status(credential_id)

    @server.tool()
    def trust_rail_health() -> dict[str, Any]:
        """Return bounded configuration and integrity counters."""
        return boundary.health()

    return server
