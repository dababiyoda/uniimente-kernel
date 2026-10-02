"""#28 MCP behind Kernel identity, authority and the Consequence Gate.

MCP (the official Python SDK, adopted) connects GREG to tool providers over
stdio. UNIIMENTE keeps three things the providers never get:

  identity   every call names a Kernel passport; unknown callers are refused
  authority  UNIIMENTE's own tool policy sets each tool's consequence class.
             Provider annotations (e.g. ``readOnlyHint``) are recorded as claims
             and never trusted; an unlisted tool is ``irreversible`` and refused.
  commit     read-only tools inside the caller's grant run directly; anything
             above read_only runs only as the executor of a Kernel
             ConsequenceGate decision with its own grant, so an ungranted call
             never reaches the provider.

Providers are interchangeable: a tool may list several; the gateway uses the
first healthy one and fails over on error, and the answer is checked against a
second provider when ``cross_check`` is set. The Foundry itself is served as an
MCP server (foundry/mcp/foundry_server.py) exposing read-only ops only.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

from capabilities.genome import CONSEQUENCE_CLASSES

ROOT = Path(__file__).resolve().parents[2]


class GatewayError(RuntimeError):
    pass


def _params(provider: dict):
    from mcp.client.stdio import StdioServerParameters
    scope = os.environ.get("GREG_FOUNDRY_STORE")
    if scope:
        if provider.get("module") != "foundry.mcp.foundry_server" or set(provider.get("env", {})) != {"FOUNDRY_MCP_ROOT"}:
            raise GatewayError("unreviewed MCP providers require OS filesystem confinement")
        if Path(provider["env"]["FOUNDRY_MCP_ROOT"]).resolve() != Path(scope).resolve():
            raise GatewayError("first-party MCP store scope is fixed")
        env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONPATH": str(ROOT),
               "PYTHONDONTWRITEBYTECODE": "1", "GREG_FOUNDRY_STORE": scope,
               "HOME": os.environ["HOME"], "FOUNDRY_MCP_ROOT": str(Path(scope).resolve())}
        return StdioServerParameters(command=sys.executable,
                                     args=["-s", "-m", "greg.foundry_protocol_worker", "mcp-foundry"],
                                     env=env, cwd=str(ROOT))
    env = {**{k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG")},
           "PYTHONPATH": str(ROOT), **provider.get("env", {})}
    return StdioServerParameters(command=sys.executable, args=["-s", "-m", provider["module"]], env=env, cwd=str(ROOT))


def _claim(tool) -> bool | None:
    """The provider's own read-only claim, recorded as a claim and never used for authority."""
    a = tool.annotations
    return None if a is None else getattr(a, "read_only_hint", getattr(a, "readOnlyHint", None))


async def _call(provider: dict, tool: str, args: dict) -> dict:
    from mcp import Client
    async with Client(_params(provider), read_timeout_seconds=30) as client:
        listed = {t.name: t for t in (await client.list_tools()).tools}
        if tool not in listed:
            raise GatewayError(f"provider {provider['name']} does not offer {tool}")
        claim = _claim(listed[tool])
        result = await client.call_tool(tool, args)
        if result.is_error:
            raise GatewayError(f"{provider['name']}.{tool} failed: {result.content[0].text if result.content else ''}")
        value = result.structured_content.get("result") if result.structured_content else result.content[0].text
        return {"provider": provider["name"], "value": value, "provider_claims_read_only": claim}


def list_tools(provider: dict) -> list[dict]:
    async def run():
        from mcp import Client
        async with Client(_params(provider), read_timeout_seconds=30) as client:
            return [{"name": t.name, "description": t.description,
                     "claims_read_only": _claim(t)}
                    for t in (await client.list_tools()).tools]
    return asyncio.run(run())


class Gateway:
    def __init__(self, *, providers: dict[str, dict], policy: dict[str, dict], passports, gate, journal: Path):
        self.providers, self.policy, self.passports, self.gate = providers, policy, passports, gate
        self.journal = Path(journal)

    def _record(self, entry: dict) -> None:
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        with self.journal.open("a") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")

    def _invoke(self, tool: str, args: dict, *, cross_check: bool = False) -> dict:
        errors, first = [], None
        for name in self.policy[tool]["providers"]:
            try:
                out = asyncio.run(_call(self.providers[name], tool, args))
            except Exception as exc:  # outage, protocol error, provider refusal: try the next provider
                errors.append(f"{name}: {type(exc).__name__}: {str(exc)[:120]}")
                continue
            if first is None:
                first = out
                if not cross_check:
                    break
            elif out["value"] != first["value"]:
                raise GatewayError(f"providers disagree on {tool}: {first['provider']}={first['value']!r} "
                                   f"{out['provider']}={out['value']!r}")
            else:
                first["cross_checked_with"] = out["provider"]
                break
        if first is None:
            raise GatewayError(f"every provider failed for {tool}: {errors}")
        return {**first, "failed_over": errors}

    def call(self, *, caller: str, tool: str, args: dict, grant: dict | None = None, cross_check: bool = False) -> dict:
        from foundry.systems.kernel_stack import proposal
        entry = {"caller": caller, "tool": tool, "args_sha256": hashlib.sha256(
            json.dumps(args, sort_keys=True).encode()).hexdigest()[:16]}
        try:
            valid, why = self.passports.verify(caller)
            if not valid:
                raise GatewayError(f"caller {caller!r} has no valid Kernel passport: {why}")
            rule = self.policy.get(tool)
            if rule is None:
                raise GatewayError(f"{tool} is not in UNIIMENTE's tool policy (treated as irreversible)")
            cls = rule["consequence_class"]
            if cls == "read_only":
                out = self._invoke(tool, args, cross_check=cross_check)
                entry.update(decision="read_only", provider=out["provider"])
            else:
                result: dict = {}

                def executor(p):
                    result.update(self._invoke(tool, args))
                    return {"provider": result["provider"], "value": str(result["value"])}
                run = self.gate.run(proposal(caller, consequence_class=cls, payload={"tool": tool, "args": args},
                                             expected_outcome=f"{tool} executed"),
                                    executor=executor, standing_grant=grant)
                if not result:
                    raise GatewayError(f"Consequence Gate {run.state}: {tool} was not executed")
                out = result
                entry.update(decision=f"gate:{run.state}", provider=out["provider"])
        except GatewayError as exc:
            entry.update(decision="refused", why=str(exc)[:200])
            self._record(entry)
            raise
        self._record({**entry, "value_sha256": hashlib.sha256(str(out["value"]).encode()).hexdigest()[:16]})
        return out


FOUNDRY = {"name": "uniimente-foundry", "module": "foundry.mcp.foundry_server"}


def ecosystem(name: str, log: Path, *, flaky: bool = False) -> dict:
    return {"name": name, "module": "foundry.mcp.ecosystem_server",
            "env": {"PROVIDER_NAME": name, "ECOSYSTEM_LOG": str(log), "FLAKY": "1" if flaky else "0"}}


def _query(args, root):
    """Read-only: call a read-only tool on the Foundry's own MCP server."""
    if not isinstance(args, dict) or "tool" not in args or set(args) - {"tool", "args"}:
        raise GatewayError("first-party MCP accepts only tool and args")
    if args["tool"] not in {"foundry_query", "price_quote"}:
        raise GatewayError("unlisted first-party MCP tool")
    if args["tool"] == "foundry_query":
        from foundry.systems import module
        request = args.get("args") or {}
        if not isinstance(request, dict) or "system" not in request or "op" not in request:
            raise GatewayError("read-only Foundry query needs system and op")
        if request["op"] not in module(int(request["system"])).QUERY_OPS:
            raise GatewayError(f"system {request['system']} has no read-only op {request['op']!r}")
    provider = {**FOUNDRY, "env": {"FOUNDRY_MCP_ROOT": str(Path(root).parent)}}
    return asyncio.run(_call(provider, args["tool"], args.get("args", {})))


QUERY_OPS = {"foundry_tool": _query, "list_foundry_tools": lambda a, r: {"tools": list_tools({**FOUNDRY, "env": {"FOUNDRY_MCP_ROOT": str(Path(r).parent)}})}}
APPLY_OPS: dict = {}


def exercise(root) -> dict:
    from foundry.systems.kernel_stack import agent, gate_stack, proposal
    root = Path(root)
    log = root / "provider-calls.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.touch()
    providers = {"foundry": {**FOUNDRY, "env": {"FOUNDRY_MCP_ROOT": str(root / "stores")}},
                 "eco-a": ecosystem("eco-a", log, flaky=True), "eco-b": ecosystem("eco-b", log)}
    policy = {"price_quote": {"consequence_class": "read_only", "providers": ["eco-a", "eco-b", "foundry"]},
              "send_message": {"consequence_class": "external_contact", "providers": ["eco-b"]}}
    gate, passports, ledger = gate_stack()
    caller = agent(passports).passport_id
    gw = Gateway(providers=providers, policy=policy, passports=passports, gate=gate, journal=root / "gateway.jsonl")
    quote_args = {"base_price": 100, "units": 3, "customer_tier": 2, "cost_per_unit": 50}
    quote = gw.call(caller=caller, tool="price_quote", args=quote_args, cross_check=True)
    refusals = {}
    def refused(label, fn):
        try:
            fn()
            refusals[label] = None
        except GatewayError as exc:
            refusals[label] = str(exc)[:160]
    refused("unknown_caller", lambda: gw.call(caller="passport:nobody", tool="price_quote", args=quote_args))
    refused("unlisted_tool", lambda: gw.call(caller=caller, tool="delete_everything", args={}))
    msg = {"to": "buyer@example.test", "text": "hello"}
    refused("send_without_grant", lambda: gw.call(caller=caller, tool="send_message", args=msg))
    calls_before_grant = len(log.read_text().splitlines())
    p = proposal(caller, consequence_class="external_contact", payload={"tool": "send_message", "args": msg},
                 expected_outcome="send_message executed")
    grant = gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")
    sent = gw.call(caller=caller, tool="send_message", args=msg, grant=grant)
    refused("grant_replayed", lambda: gw.call(caller=caller, tool="send_message", args=msg, grant=grant))
    tools = list_tools(providers["eco-b"])
    return {"quote": quote["value"], "quote_provider": quote["provider"], "failed_over_from": [e.split(":")[0] for e in quote["failed_over"]],
            "cross_checked_with": quote.get("cross_checked_with"), "refusals": refusals,
            "provider_calls_before_grant": calls_before_grant, "sent_via": sent["provider"],
            "provider_calls_after": len(log.read_text().splitlines()),
            "provider_claims_send_is_read_only": next(t["claims_read_only"] for t in tools if t["name"] == "send_message"),
            "chain_ok": ledger.verify_chain()[0]}
