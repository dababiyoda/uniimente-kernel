"""#48 Temporary specialist teams: formed for one bounded objective, dissolved on completion.

A team is formed from a swarm contract compiled by #1 and a grant (the
authority the founder or a mission gives the team). Each member's role needs a
competence that is ATTACHED in the #12 registry. Each member's effective
authority is the intersection of its declared capabilities and consequence with
the grant's; nobody in the team can exceed the grant, and the team's spend
cannot exceed its budget. Members act through Foundry ops, every act is
journaled, and the team dissolves when its objective check passes (or on
explicit dissolution); after that every act is refused. The team is data plus
this enforcement, not a new runtime: members' work runs through the same ops
GREG uses.
"""
from __future__ import annotations

import json
from pathlib import Path

from capabilities.genome import CONSEQUENCE_CLASSES


class TeamError(RuntimeError):
    pass


def _path(root: Path, team_id: str) -> Path:
    return Path(root) / f"team-{team_id}.json"


def _load(root, team_id) -> dict:
    p = _path(root, team_id)
    if not p.exists():
        raise TeamError(f"no team {team_id}")
    return json.loads(p.read_text())


def _save(root, team: dict) -> None:
    Path(root).mkdir(parents=True, exist_ok=True)
    tmp = _path(root, team["id"]).with_suffix(".tmp")
    tmp.write_text(json.dumps(team, sort_keys=True, indent=1))
    tmp.replace(_path(root, team["id"]))


def _lower(a: str, b: str) -> str:
    return min(a, b, key=CONSEQUENCE_CLASSES.index)


def form(root: Path, contract: dict, grant: dict, *, registry_root: Path, objective_check: dict) -> dict:
    from foundry.systems import registry
    if contract.get("kind") != "swarm_contract":
        raise TeamError("teams form from a compiled swarm_contract (#1)")
    c = contract["object"]
    if _path(root, c["id"]).exists():
        raise TeamError(f"team {c['id']} already exists")
    genomes = registry._load(registry_root)["genomes"]
    members = {}
    for m in c["members"]:
        g = genomes.get(m.get("competence", m["role"]))
        if not g or g["state"] != "ATTACHED":
            raise TeamError(f"role {m['role']} needs competence {m.get('competence', m['role'])!r} attached in the registry")
        caps = sorted(set(m["capabilities"]) & set(grant["capabilities"]))
        if not caps:
            raise TeamError(f"role {m['role']} has no capability inside the grant")
        members[m["role"]] = {"capabilities": caps, "max_consequence": _lower(m["max_consequence"], grant["max_consequence"])}
    team = {"id": c["id"], "objective": c["objective"], "members": members, "contract_hash": contract["hash"],
            "budget_usd": min(float(c["budget_usd"]), float(grant.get("budget_usd", 0))), "spent_usd": 0.0,
            "objective_check": objective_check, "state": "ACTIVE", "journal": []}
    _save(root, team)
    return {"team": team["id"], "members": members, "budget_usd": team["budget_usd"]}


def act(root: Path, team_id: str, role: str, *, system: int, op: str, args: dict, cost_usd: float = 0.0) -> dict:
    from foundry.systems import module
    from foundry.systems.linking import _op_class
    team = _load(root, team_id)
    entry = {"role": role, "system": system, "op": op}
    try:
        if team["state"] != "ACTIVE":
            raise TeamError(f"team {team_id} is {team['state']}")
        member = team["members"].get(role) or (_ for _ in ()).throw(TeamError(f"no role {role} in team"))
        cls = _op_class(int(system), op)
        capability = "foundry.query" if cls == "read_only" else "foundry.apply"
        if capability not in member["capabilities"]:
            raise TeamError(f"{role} holds {member['capabilities']}, not {capability}")
        if CONSEQUENCE_CLASSES.index(cls) > CONSEQUENCE_CLASSES.index(member["max_consequence"]):
            raise TeamError(f"{role} is capped at {member['max_consequence']}; {op} is {cls}")
        if team["spent_usd"] + cost_usd > team["budget_usd"] + 1e-9:
            raise TeamError(f"budget {team['budget_usd']} would be exceeded")
        mod = module(int(system))
        result = (mod.QUERY_OPS.get(op) or mod.APPLY_OPS[op])(args, Path(root) / "stores" / f"system-{int(system):02d}")
    except Exception as exc:
        team["journal"].append({**entry, "outcome": f"refused: {exc}"[:300]})
        _save(root, team)
        raise TeamError(str(exc)) from None
    team["spent_usd"] += cost_usd
    team["journal"].append({**entry, "outcome": "ok"})
    check = team["objective_check"]
    probe = module(int(check["system"])).QUERY_OPS[check["op"]](check.get("args", {}),
                                                                Path(root) / "stores" / f"system-{int(check['system']):02d}")
    met = float(probe.get(check["field"], 0)) >= float(check["gte"])
    if met:
        team["state"] = "DISSOLVED"
        team["journal"].append({"role": "-", "outcome": "objective met; team dissolved"})
    _save(root, team)
    return {"result": result, "objective_met": met, "state": team["state"]}


def dissolve(root: Path, team_id: str, *, reason: str) -> dict:
    team = _load(root, team_id)
    team["state"] = "DISSOLVED"
    team["journal"].append({"role": "-", "outcome": f"dissolved: {reason}"})
    _save(root, team)
    return {"team": team_id, "state": "DISSOLVED"}


def report(root: Path, team_id: str) -> dict:
    t = _load(root, team_id)
    return {k: t[k] for k in ("id", "state", "members", "spent_usd", "budget_usd", "journal")}


QUERY_OPS = {"report": lambda a, r: report(r, a["team_id"])}
APPLY_OPS = {"form": lambda a, r: form(r, a["contract"], a["grant"], registry_root=Path(r).parent / "system-12",
                                       objective_check=a["objective_check"]),
             "act": lambda a, r: act(r, a["team_id"], a["role"], system=int(a["system"]), op=a["op"],
                                     args=a.get("args", {}), cost_usd=float(a.get("cost_usd", 0.0))),
             "dissolve": lambda a, r: dissolve(r, a["team_id"], reason=a["reason"])}


def exercise(root) -> dict:
    from foundry.systems import compiler, registry
    root = Path(root)
    reg = root / "registry"
    contract = compiler.compile_source(compiler.SOURCES["swarm.yaml"], "swarm.yaml")
    check = {"system": 36, "op": "verify", "field": "objects", "gte": 1}
    grant = {"capabilities": ["foundry.query", "foundry.apply"], "max_consequence": "internal_write", "budget_usd": 0}
    refusals = {}
    def refused(label, fn):
        try:
            fn()
            refusals[label] = None
        except TeamError as exc:
            refusals[label] = str(exc)
    refused("competence_not_registered", lambda: form(root / "t0", contract, grant, registry_root=reg,
                                                      objective_check=check))
    for role in ("analyst", "writer"):
        registry.install(reg, registry.spec(role, "1.0", ["out"]), role, tests_pass=True)
        registry.attach(reg, role)
    formed = form(root / "t1", contract, grant, registry_root=reg, objective_check=check)
    cases = [{"id": "a", "text": "delivery proof audit sold to distributor", "outcome_quality": 0.9},
             {"id": "b", "text": "delivery proof audit offered to retailer", "outcome_quality": 0.1}]
    read = act(root / "t1", "offer-sprint", "analyst", system=17, op="precedents",
               args={"cases": cases, "query": "delivery proof audit for distributor"})
    refused("analyst_writes", lambda: act(root / "t1", "offer-sprint", "analyst", system=36, op="put",
                                          args={"text": "x"}))
    refused("over_budget", lambda: act(root / "t1", "offer-sprint", "writer", system=36, op="put",
                                       args={"text": "x"}, cost_usd=1.0))
    wrote = act(root / "t1", "offer-sprint", "writer", system=36, op="put", args={"text": "offer draft v1"})
    refused("after_dissolution", lambda: act(root / "t1", "offer-sprint", "writer", system=36, op="put",
                                             args={"text": "v2"}))
    narrow = form(root / "t2", contract, {**grant, "max_consequence": "read_only"}, registry_root=reg,
                  objective_check=check)
    refused("grant_caps_writer", lambda: act(root / "t2", "offer-sprint", "writer", system=36, op="put",
                                             args={"text": "x"}))
    refused("grant_without_role_capability", lambda: form(root / "t3", contract, {**grant, "capabilities": ["web.fetch"]},
                                                          registry_root=reg, objective_check=check))
    return {"formed": formed["members"], "narrow_grant_members": narrow["members"],
            "analyst_read": read["result"]["closest_worked"]["id"], "writer_wrote_and_dissolved": [wrote["objective_met"], wrote["state"]],
            "refusals": refusals, "journal": [j["outcome"][:40] for j in report(root / "t1", "offer-sprint")["journal"]]}
