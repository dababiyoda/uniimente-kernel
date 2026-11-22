"""``worker.team`` (WU-03): one signed action fields a role-scoped temporary worker organization under one grant.

The team itself is Foundry system #48 (``foundry.systems.teams``, the canonical owner of temporary specialist teams,
OWN-FN-TEMPORARY-TEAMS). This adapter reaches it only through ``foundry.apply`` / ``foundry.query``
(``greg.foundry_bridge``), so every team operation runs in the same disposable, network-denied Foundry worker as any
other mission's Foundry call:

    foundry.query  #1  compile    the team's swarm contract, compiled from the signed params
    foundry.apply  #12 install    one competence per member provider, then attach it
    foundry.apply  #48 form       members' authority = their capabilities intersected with the grant; budget capped
                                  at the signed action's max_budget_usd
    worker.commission (one thread per member, all at once)
                                  each member is an ordinary WorkOrder under this action's grant, in its own private
                                  workspace; nothing here widens what a WorkOrder may do
    foundry.apply  #48 act        each finished member's result is recorded by that member, charged at its metered
                                  spend; the team dissolves when every member has recorded (#36 holds one object each)
    foundry.apply  #48 dissolve   on any refusal, failure or stop, before the action returns
    foundry.query  #48 report     the journal and spend returned in the receipt

What the founder signed bounds everything: one action, one grant, one cap. The members' caps are reserved before
any member starts, so their combined spend can never pass the cap even if every member spends its whole cap; #48
then checks each charge again when it is recorded. A role whose provider can spend money GREG cannot measure (a
headless CLI that reports no cost) is refused before the team forms. A role whose provider cannot spend at all (the
script worker) needs no meter.

Each member's output is its own work order (``work-orders/<order>/``) and its own entry in the receipt's
``members``, so ``worker.appraise`` judges it alone, bound to this action's canonical receipt.

The team's Foundry stores live in ``teams/<team>/`` inside the mission workspace and are created fresh for each
grant. They are this action's private working state, recorded in its receipt; the mission's own Foundry store
(``foundry/``) is untouched.
"""
from __future__ import annotations

import dataclasses
import json
import shutil
import threading
from pathlib import Path

from greg.capabilities import CapabilityError, InvocationContext

MAX_MEMBERS = 8
MEMBER_CAPABILITIES = ["foundry.query", "foundry.apply"]   # what a member needs to record its result through #48
RECORD = {"system": 36, "op": "put"}                    # a member's act: its result into the team's #36 store


class TeamRefused(CapabilityError):
    pass


def spend_metering(provider) -> str:
    """How a provider's spend is known: ``none`` (it cannot spend), ``metered`` (it reports provider-measured spend
    that GREG books), or ``unmetered`` (it may spend and reports nothing GREG can book)."""
    cls = type(provider)
    if str((getattr(cls, "GUARANTEES", None) or {}).get("spend", "")).startswith("none"):
        return "none"
    if getattr(cls, "METERS_SPEND", False) is True:
        return "metered"
    return "unmetered"


def _members(params: dict, budget: float) -> list[dict]:
    from greg import workers
    members = params.get("members")
    if not isinstance(members, list) or not 2 <= len(members) <= MAX_MEMBERS:
        raise TeamRefused(f"a team has 2 to {MAX_MEMBERS} members")
    roles, orders, reserved, out = set(), set(), 0.0, []
    for m in members:
        if not isinstance(m, dict) or not isinstance(m.get("order"), dict):
            raise TeamRefused("each member names a role and its work order")
        role, order = str(m.get("role", "")), dict(m["order"])
        if not workers.ORDER_NAME.match(role) or role in roles:
            raise TeamRefused(f"member role {role!r} must be a distinct short lowercase name")
        name = str(order.get("order", ""))
        if name in orders:
            raise TeamRefused(f"members {role!r} and another share work order {name!r}; each needs its own")
        provider_name = str(order.get("provider", "claude-code"))
        provider = workers.PROVIDERS.get(provider_name)
        if provider is None:
            raise TeamRefused(f"member {role!r}: unknown worker provider {provider_name!r}")
        metering = spend_metering(provider)
        if metering == "unmetered":
            raise TeamRefused(f"member {role!r}: provider {provider_name!r} can spend but GREG cannot meter its "
                              "spend; a paid role needs a metered provider")
        try:
            cap = float(order.get("max_budget_usd"))
        except (TypeError, ValueError):
            raise TeamRefused(f"member {role!r} signs no max_budget_usd") from None
        reserved += cap
        roles.add(role)
        orders.add(name)
        out.append({"role": role, "order": order, "provider": provider_name, "metering": metering, "cap": cap})
    if reserved > budget + 1e-9:
        raise TeamRefused(f"members' caps total {reserved:.2f}, above the action's signed cap {budget:.2f}")
    return out


def _source(team_id: str, objective: str, budget: float, members: list[dict]) -> str:
    doc = {"kind": "swarm_contract", "id": team_id, "objective": objective, "budget_usd": budget,
           "dissolve_on": "every member has recorded its result, or any refusal, failure or stop",
           "members": [{"role": m["role"], "competence": f"worker.{m['provider']}",
                        "capabilities": list(MEMBER_CAPABILITIES), "max_consequence": "internal_write"}
                       for m in members]}
    return json.dumps(doc, sort_keys=True)            # JSON is YAML; #1 compiles it


def _competence(provider: str) -> dict:
    return {"name": f"worker.{provider}", "version": "1.0",
            "description": f"WorkOrders run by GREG's {provider!r} worker provider (greg.workers.PROVIDERS)",
            "interface": {"inputs": {"order": "str"}, "outputs": {"work_order": "str"}},
            "authority": {"max_consequence_class": "internal_write", "budget_ceiling_usd": 0.0},
            "acceptance_tests": ["tests/unit/test_greg_workers.py", "tests/unit/test_greg_teams.py"],
            "failure_modes": ["worker failed", "worker interrupted"], "recovery_path": "dissolve the team; reconcile",
            "dependencies": [], "contraindications": []}


def field(params: dict, ctx: InvocationContext) -> dict:
    """``worker.team``: form a #48 team, run its members' WorkOrders at once, record each, dissolve, report."""
    from greg import foundry_bridge, workers
    team_id = str(params.get("team", ""))
    if not workers.ORDER_NAME.match(team_id):
        raise TeamRefused("team must be a short lowercase name")
    objective = str(params.get("objective", "")).strip()
    if not objective:
        raise TeamRefused("a team states its objective")
    try:
        budget = float(params["max_budget_usd"])
    except (KeyError, TypeError, ValueError):
        raise TeamRefused("worker.team signs max_budget_usd") from None
    members = _members(params, budget)
    for m in members:                                 # every order validates before anything forms or runs
        try:
            workers.WorkOrder.from_params(m["order"], ctx)
        except workers.WorkerError as exc:
            raise TeamRefused(f"member {m['role']!r}: {exc}") from None
    home = ctx.workspace / "teams" / team_id
    if home.exists():                                 # an earlier grant's team: never this grant's
        shutil.rmtree(home)
    home.mkdir(parents=True)
    # The team's stores are this action's own working state (see the module docstring): no mission journal is
    # consulted for them, and the mission's own foundry/ store is not touched.
    tctx = dataclasses.replace(ctx, workspace=home, journal=None, mission_id="", target=f"team:{team_id}")

    # Once members have started, money may have been spent: recording, dissolving and reporting must then finish
    # even under a stop, or the action would end REFUSED and book nothing for what the members spent. Those calls
    # only touch this action's private team store; the members themselves still obey the stop.
    closing = dataclasses.replace(tctx, stop_check=None)

    def foundry(apply: bool, system: int, op: str, args: dict, *, after_start: bool = False) -> dict:
        call = foundry_bridge.apply if apply else foundry_bridge.query
        return call({"system": system, "op": op, "args": args}, closing if after_start else tctx)["result"]

    compiled = foundry(False, 1, "compile", {"source": _source(team_id, objective, budget, members),
                                            "filename": f"team-{team_id}.yaml"})
    if not compiled.get("ok"):
        raise TeamRefused(f"the team's swarm contract does not compile: {compiled.get('errors')}")
    for provider in sorted({m["provider"] for m in members}):
        foundry(True, 12, "install", {"spec": _competence(provider), "code": f"greg.workers.PROVIDERS[{provider!r}]",
                                      "tests_pass": True})
        foundry(True, 12, "attach", {"name": f"worker.{provider}"})
    grant = {"capabilities": list(MEMBER_CAPABILITIES), "max_consequence": "internal_write", "budget_usd": budget}
    formed = foundry(True, 48, "form", {"contract": compiled["compiled"], "grant": grant,
                                        "objective_check": {"system": 36, "op": "verify", "field": "objects",
                                                            "gte": len(members)}})

    results: dict[str, dict] = {}
    errors: dict[str, str] = {}
    lock = threading.Lock()

    def run(m):
        try:
            out = workers.commission(m["order"], ctx)
        except Exception as exc:                      # recorded and the team dissolved below; never swallowed
            with lock:
                errors[m["role"]] = f"{type(exc).__name__}: {str(exc)[:300]}"
            return
        with lock:
            results[m["role"]] = out

    threads = [threading.Thread(target=run, args=(m,), name=f"team-{team_id}-{m['role']}", daemon=True)
               for m in members]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    recorded, refusals = {}, {}
    for m in members:                                 # serialized: one #48 act per finished member, in role order
        out = results.get(m["role"])
        if out is None:
            continue
        charge = float(out.get("cost_usd") or 0.0) if m["metering"] != "none" else 0.0
        record = {"role": m["role"], "work_order": out.get("work_order"), "status": out.get("status"),
                  "patch_sha256": out.get("patch_sha256"), "charge_usd": charge}
        try:
            recorded[m["role"]] = foundry(True, 48, "act", {"team_id": team_id, "role": m["role"], **RECORD,
                                                            "args": {"text": json.dumps(record, sort_keys=True)},
                                                            "cost_usd": charge}, after_start=True)
        except CapabilityError as exc:
            refusals[m["role"]] = str(exc)[:300]
    stopped = bool(ctx.stop_check and ctx.stop_check())
    state = foundry(False, 48, "report", {"team_id": team_id}, after_start=True)
    if state["state"] != "DISSOLVED":
        why = "a stop while the team worked" if stopped else "a member did not finish and record"
        foundry(True, 48, "dissolve", {"team_id": team_id, "reason": why}, after_start=True)
        state = foundry(False, 48, "report", {"team_id": team_id}, after_start=True)
    # A member that raised may have spent before it did: it is charged at its whole cap until reconciled.
    spent = round(sum(float(o.get("cost_usd") or 0.0) for o in results.values())
                  + sum(m["cap"] for m in members if m["role"] in errors and m["metering"] != "none"), 6)
    # A stop during the work leaves the outcome for reconciliation, never an ordinary success (the members may
    # have finished before they saw it).
    uncertain = stopped or bool(errors) or any(o.get("status") == "UNCERTAIN" for o in results.values())
    return {"team": {"id": team_id, "objective": objective, "state": state["state"], "budget_usd": budget,
                     "spent_usd": spent, "foundry_spent_usd": state["spent_usd"], "members": formed["members"],
                     "journal": state["journal"], "errors": errors, "refusals": refusals,
                     "contract_hash": compiled["compiled"]["hash"]},
            "status": "UNCERTAIN" if uncertain else ("COMPLETED" if len(recorded) == len(members) else "FAILED"),
            "members": {o["work_order"]: {**o, "role": role} for role, o in results.items()},
            "authority_created": False}
