"""#13 Linker: compose Foundry systems into a temporary, typed, executable system.

A composition is an ordered list of stages. Each stage names a Foundry system
and op, literal args, which context values it binds into its args (``bind``),
the types it needs from the context (``needs``) and the typed values it adds to
the context from its result (``provides``: key -> {path, type}).

``link`` checks the whole composition before anything runs: every needed key
must be provided earlier with the same type (the mismatch is named), every op
must exist, and every stage that names a genome must be ATTACHED in the #12
registry. The composite authority is the highest consequence among its stages
(a query op is read_only, an apply op internal_write). ``run`` refuses a plan
whose composite authority exceeds the ceiling it is granted, checks each
declared output at runtime, and returns the context plus a per-stage trace.

The organ-level InstitutionalLinker (linker/linker.py) keeps resolving
contract edges between organ manifests; this links capabilities inside one run.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from capabilities.genome import CONSEQUENCE_CLASSES

TYPES = {"str": str, "int": int, "float": (int, float), "bool": bool, "list": list, "dict": dict}


class LinkError(ValueError):
    pass


def _op_class(system: int, op: str) -> str:
    from foundry.systems import module
    mod = module(system)
    if op in mod.QUERY_OPS:
        return "read_only"
    if op in mod.APPLY_OPS:
        return "internal_write"
    raise LinkError(f"system {system} has no op {op!r}")


def _get(value, path: str):
    for part in path.split(".") if path else []:
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def _set(target: dict, path: str, value) -> None:
    *parents, leaf = path.split(".")
    for part in parents:
        target = target.setdefault(part, {})
    target[leaf] = value


def link(stages: list[dict], *, initial: dict | None = None, registry_root: Path | None = None) -> dict:
    """Type-check a composition; return a plan with its composite authority and hash."""
    from foundry.systems import registry
    available = {k: type(v).__name__ if not isinstance(v, bool) else "bool" for k, v in (initial or {}).items()}
    available = {k: ("float" if t == "int" else t) for k, t in available.items()}
    genomes = registry._load(registry_root)["genomes"] if registry_root else {}
    classes, names = [], set()
    for i, stage in enumerate(stages):
        name = stage.get("name") or f"stage-{i}"
        if name in names:
            raise LinkError(f"duplicate stage name {name!r}")
        names.add(name)
        classes.append(_op_class(int(stage["system"]), stage["op"]))
        for key, want in stage.get("needs", {}).items():
            if want not in TYPES:
                raise LinkError(f"{name}: unknown type {want!r}")
            have = available.get(key)
            if have is None:
                raise LinkError(f"{name} needs {key}:{want} but no earlier stage provides it")
            if have != want and not (want == "float" and have == "int"):
                raise LinkError(f"type mismatch at {name}: needs {key}:{want}, earlier stage provides {key}:{have}")
        for arg, key in stage.get("bind", {}).items():
            if key not in stage.get("needs", {}):
                raise LinkError(f"{name} binds {arg} from {key} without declaring it in needs")
        if stage.get("genome"):
            entry = genomes.get(stage["genome"])
            if not entry or entry["state"] != "ATTACHED":
                raise LinkError(f"{name} uses genome {stage['genome']!r}, which is not attached in the registry")
        for key, out in stage.get("provides", {}).items():
            if out["type"] not in TYPES:
                raise LinkError(f"{name}: unknown type {out['type']!r}")
            available[key] = out["type"]
    authority = max(classes, key=CONSEQUENCE_CLASSES.index) if classes else "read_only"
    body = {"stages": stages, "authority": authority}
    return {**body, "plan_hash": hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()}


def run(plan: dict, root: Path, *, ceiling: str, initial: dict | None = None) -> dict:
    """Execute a linked plan under an authority ceiling; each stage gets its own store."""
    from foundry.systems import module
    relinked = link(plan["stages"], initial=initial)
    if relinked["plan_hash"] != plan["plan_hash"]:
        raise LinkError("plan changed after linking")
    if CONSEQUENCE_CLASSES.index(plan["authority"]) > CONSEQUENCE_CLASSES.index(ceiling):
        raise LinkError(f"composite authority {plan['authority']} exceeds granted ceiling {ceiling}")
    ctx, trace = dict(initial or {}), []
    for i, stage in enumerate(plan["stages"]):
        name = stage.get("name") or f"stage-{i}"
        mod = module(int(stage["system"]))
        op = mod.QUERY_OPS.get(stage["op"]) or mod.APPLY_OPS[stage["op"]]
        args = json.loads(json.dumps(stage.get("args", {})))
        for arg, key in stage.get("bind", {}).items():
            _set(args, arg, ctx[key])
        result = op(args, Path(root) / f"system-{int(stage['system']):02d}")
        for key, out in stage.get("provides", {}).items():
            try:
                value = _get(result, out["path"])
            except (KeyError, IndexError, TypeError):
                raise LinkError(f"{name} did not produce {out['path']!r} for {key}") from None
            if not isinstance(value, TYPES[out["type"]]) or (out["type"] != "bool" and isinstance(value, bool)):
                raise LinkError(f"{name} produced {key} as {type(value).__name__}, contract says {out['type']}")
            ctx[key] = value
        trace.append({"stage": name, "system": int(stage["system"]), "op": stage["op"],
                      "provided": sorted(stage.get("provides", {}))})
    return {"context": ctx, "trace": trace, "authority": plan["authority"], "plan_hash": plan["plan_hash"]}


QUERY_OPS = {"link": lambda a, r: link(a["stages"], initial=a.get("initial"),
                                       registry_root=Path(r).parent / "system-12" if a.get("use_registry") else None),
             "run_read_only": lambda a, r: run(link(a["stages"], initial=a.get("initial")), r, ceiling="read_only",
                                               initial=a.get("initial"))}
APPLY_OPS = {"run": lambda a, r: run(link(a["stages"], initial=a.get("initial")), r, ceiling="internal_write",
                                     initial=a.get("initial"))}


NOW = "2026-09-27T00:00:00Z"
RECORDS = [{"subject": "supplier-a", "context": "*", "verdict": "VERIFIED", "at": NOW, "evidence": [f"r{n}"]}
           for n in range(6)] + [{"subject": "supplier-a", "context": "*", "verdict": "REFUTED", "at": NOW,
                                  "evidence": ["r-bad"]}]


def demo_stages(*, post: bool = False) -> list[dict]:
    stages = [
        {"name": "rate", "system": 41, "op": "score", "args": {"records": RECORDS, "now": NOW},
         "provides": {"trust": {"path": "subjects.0.lower_bound", "type": "float"}}},
        {"name": "price", "system": 2, "op": "run", "needs": {"trust": "float"}, "bind": {"inputs.customer_tier": "trust"},
         "args": {"language": "pricing", "source": "base_price * units * (1 + 0.5 * customer_tier)",
                  "inputs": {"base_price": 100, "units": 3}},
         "provides": {"price": {"path": "value", "type": "float"}}},
    ]
    if post:
        stages.append({"name": "book", "system": 39, "op": "open_account", "needs": {"price": "float"},
                       "args": {"account": "revenue:quotes", "type": "revenue", "currency": "USD"}, "provides": {}})
    return stages


def exercise(root) -> dict:
    from foundry.systems import registry
    root = Path(root)
    plan = link(demo_stages())
    result = run(plan, root / "run", ceiling="read_only")
    refusals = {}
    def refused(label, fn):
        try:
            fn()
            refusals[label] = False
        except LinkError as exc:
            refusals[label] = str(exc)
    bad = demo_stages()
    bad[1]["needs"] = {"trust": "list"}
    refused("type_mismatch", lambda: link(bad))
    missing = demo_stages()[1:]
    refused("missing_provider", lambda: link(missing))
    refused("unknown_op", lambda: link([{"system": 41, "op": "rewrite_history"}]))
    write_plan = link(demo_stages(post=True))
    refused("authority_ceiling", lambda: run(write_plan, root / "run2", ceiling="read_only"))
    tampered = dict(plan, stages=plan["stages"] + [{"system": 17, "op": "search"}])
    refused("tampered_plan", lambda: run(tampered, root / "run3", ceiling="read_only"))
    reg = root / "registry"
    registry.install(reg, registry.spec("pricing", "1.0", ["price"]), "dsl", tests_pass=True)
    genome_stages = demo_stages()
    genome_stages[1]["genome"] = "pricing"
    refused("genome_not_attached", lambda: link(genome_stages, registry_root=reg))
    registry.attach(reg, "pricing")
    attached = link(genome_stages, registry_root=reg)
    return {"price": result["context"]["price"], "trust": result["context"]["trust"], "trace": result["trace"],
            "plan_authority": plan["authority"], "write_plan_authority": write_plan["authority"],
            "refusals": refusals, "linked_with_attached_genome": attached["plan_hash"][:16]}
