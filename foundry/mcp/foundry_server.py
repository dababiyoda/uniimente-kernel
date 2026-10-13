"""The Foundry as an MCP server: read-only Foundry ops for any MCP client.

Only QUERY_OPS are exposed. Write ops are never reachable over MCP: a model
outside UNIIMENTE may read through this door but cannot change state through it.
The store root comes from FOUNDRY_MCP_ROOT.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer

server = MCPServer("uniimente-foundry")


@server.tool()
def foundry_query(system: int, op: str, args_json: str = "{}") -> str:
    """Run a read-only Foundry op and return its JSON result."""
    from foundry.systems import module
    ops = module(int(system)).QUERY_OPS
    if op not in ops:
        raise ValueError(f"system {system} has no read-only op {op!r}")
    root = Path(os.environ.get("FOUNDRY_MCP_ROOT", ".")) / f"system-{int(system):02d}"
    return json.dumps(ops[op](json.loads(args_json), root), sort_keys=True, default=str)


@server.tool()
def price_quote(base_price: float, units: int, customer_tier: int, cost_per_unit: float) -> float:
    """Quote a price with the Foundry pricing DSL."""
    from foundry.systems import dsl
    return float(dsl.run("pricing", "max(base_price * units * (1 - 0.05 * customer_tier), cost_per_unit * units * 1.2)",
                         {"base_price": base_price, "units": units, "customer_tier": customer_tier,
                          "cost_per_unit": cost_per_unit}))


if __name__ == "__main__":
    server.run("stdio")
