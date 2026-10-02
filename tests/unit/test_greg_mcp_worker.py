"""Real guarded MCP stdio connects the machine, without general child privileges."""
import json

import pytest

from greg import foundry_bridge
from greg.capabilities import CapabilityError
from tests.unit.test_greg_foundry_worker import context
from tests.unit.test_greg_media import canon


def test_first_party_mcp_reaches_actual_retained_machine_state_without_writes(tmp_path):
    ctx = context(tmp_path)
    produced = foundry_bridge.apply({"system": 35, "op": "produce", "args": {"canon": canon()}}, ctx)
    queried = foundry_bridge.query({"system": 28, "op": "foundry_tool", "args": {
        "tool": "foundry_query", "args": {"system": 35, "op": "inspect",
                                        "args_json": json.dumps({"manifest": produced["result"]["manifest"]})}}},
        context(tmp_path, "foundry.query"))
    value = json.loads(queried["result"]["value"])
    assert value["intact"] and value["assets"] == 5
    assert queried["execution"]["persistence"] == "discarded"
    assert not (ctx.workspace / "foundry" / "system-28").exists()
    tools = foundry_bridge.query({"system": 28, "op": "list_foundry_tools"}, context(tmp_path, "foundry.query"))
    assert {t["name"] for t in tools["result"]["tools"]} == {"foundry_query", "price_quote"}


def test_guarded_mcp_cannot_turn_read_only_tool_into_production(tmp_path):
    with pytest.raises(CapabilityError, match="read-only op"):
        foundry_bridge.query({"system": 28, "op": "foundry_tool", "args": {
            "tool": "foundry_query", "args": {"system": 35, "op": "produce", "args_json": json.dumps({"canon": canon()})}}},
            context(tmp_path, "foundry.query"))
    assert not (tmp_path / "ws" / "foundry").exists()


def test_guarded_mcp_provider_and_scope_substitution_are_refused(tmp_path, monkeypatch):
    from foundry.systems import mcp_gateway
    monkeypatch.setenv("GREG_FOUNDRY_STORE", str(tmp_path))
    for provider in ({"name": "unknown", "module": "unreviewed.provider"},
                     {**mcp_gateway.FOUNDRY, "env": {"FOUNDRY_MCP_ROOT": str(tmp_path.parent)}},
                     {**mcp_gateway.FOUNDRY, "env": {"FOUNDRY_MCP_ROOT": str(tmp_path), "PYTHONINSPECT": "1"}}):
        with pytest.raises(mcp_gateway.GatewayError, match="confinement|scope"):
            mcp_gateway._params(provider)
