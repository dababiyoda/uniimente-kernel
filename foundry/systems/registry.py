"""#12 Capability Genome Registry: install, attach, measure, migrate and detach capabilities.

A genome is the Kernel's CapabilityGenome (validated by capabilities/genome.py,
the single validation owner) plus what makes it inheritable: code stored by
content (#36), a versioned record (#3), dependencies, contraindications,
performance history and incidents (scored by #41), and a rollback target.

Lifecycle: INSTALLED -> ATTACHED -> DETACHED (never deleted). Attach refuses
missing or detached dependencies and declared contraindications; detach
refuses while attached dependents rely on it; migrate installs a new version
only if its acceptance tests pass and its interface still serves dependents,
and keeps the old version as the rollback target.
"""
from __future__ import annotations

import json
from pathlib import Path

from foundry.systems import cas, reputation, versions


class RegistryError(RuntimeError):
    pass


def _state_path(root: Path) -> Path:
    return Path(root) / "registry.json"


def _load(root: Path) -> dict:
    p = _state_path(root)
    return json.loads(p.read_text()) if p.exists() else {"genomes": {}}


def _save(root: Path, state: dict) -> None:
    Path(root).mkdir(parents=True, exist_ok=True)
    tmp = _state_path(root).with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True, indent=1))
    tmp.replace(_state_path(root))


def _genome(spec: dict):
    from capabilities.genome import AuthorityEnvelope, CapabilityGenome, GenomeRegistry
    g = CapabilityGenome(name=spec["name"], version=spec["version"], description=spec["description"],
                         interface=spec["interface"], contracts=spec.get("contracts", []),
                         authority=AuthorityEnvelope(**spec["authority"]), acceptance_tests=spec["acceptance_tests"],
                         failure_modes=spec["failure_modes"], recovery_path=spec["recovery_path"])
    GenomeRegistry().register(g)  # the Kernel's validator; raises on an invalid genome
    return g


def install(root: Path, spec: dict, code: str, *, tests_pass: bool) -> dict:
    _genome(spec)
    if not tests_pass:
        raise RegistryError(f"{spec['name']}@{spec['version']}: acceptance tests failed; not installed")
    state = _load(root)
    entry = state["genomes"].setdefault(spec["name"], {"versions": {}, "active": None, "state": "INSTALLED",
                                                        "outcomes": [], "incidents": []})
    if spec["version"] in entry["versions"]:
        raise RegistryError(f"{spec['name']}@{spec['version']} already installed; versions are immutable")
    entry["versions"][spec["version"]] = {"spec": spec, "code": cas.put(root, code.encode())}
    record = versions.commit(Path(root) / "records", spec["name"], {"version": spec["version"], "spec": spec},
                             reason=f"install {spec['version']}", evidence=spec["acceptance_tests"])
    entry["versions"][spec["version"]]["record"] = record["address"]
    if entry["active"] is None:
        entry["active"] = spec["version"]
    _save(root, state)
    return {"name": spec["name"], "version": spec["version"], "state": entry["state"]}


def attach(root: Path, name: str, *, environment: dict | None = None) -> dict:
    state = _load(root)
    entry = state["genomes"].get(name) or (_ for _ in ()).throw(RegistryError(f"{name} is not installed"))
    spec = entry["versions"][entry["active"]]["spec"]
    for dep in spec.get("dependencies", []):
        dep_entry = state["genomes"].get(dep)
        if not dep_entry or dep_entry["state"] != "ATTACHED":
            raise RegistryError(f"{name} needs {dep} attached first")
    for condition in spec.get("contraindications", []):
        if (environment or {}).get(condition):
            raise RegistryError(f"{name} is contraindicated when {condition}")
    entry["state"] = "ATTACHED"
    _save(root, state)
    return {"name": name, "state": "ATTACHED", "version": entry["active"]}


def detach(root: Path, name: str) -> dict:
    state = _load(root)
    dependents = [n for n, e in state["genomes"].items() if e["state"] == "ATTACHED"
                  and name in e["versions"][e["active"]]["spec"].get("dependencies", [])]
    if dependents:
        raise RegistryError(f"cannot detach {name}: attached dependents {dependents}")
    state["genomes"][name]["state"] = "DETACHED"
    _save(root, state)
    return {"name": name, "state": "DETACHED", "retained_versions": sorted(state["genomes"][name]["versions"])}


def measure(root: Path, name: str, *, verdict: str, at: str, evidence: str, incident: bool = False,
            recovered: bool = False) -> dict:
    state = _load(root)
    entry = state["genomes"][name]
    entry["outcomes"].append({"subject": name, "context": entry["active"], "verdict": verdict, "at": at,
                              "evidence": [evidence], "incident": incident, "recovered": recovered})
    if incident:
        entry["incidents"].append({"at": at, "evidence": evidence, "recovered": recovered})
    _save(root, state)
    return {"name": name, "outcomes": len(entry["outcomes"])}


def migrate(root: Path, name: str, spec: dict, code: str, *, tests_pass: bool) -> dict:
    state = _load(root)
    entry = state["genomes"][name]
    old = entry["versions"][entry["active"]]["spec"]
    missing = sorted(set(old["interface"]["outputs"]) - set(spec["interface"]["outputs"]))
    dependents = [n for n, e in state["genomes"].items() if name in e["versions"][e["active"]]["spec"].get("dependencies", [])]
    if missing and dependents:
        raise RegistryError(f"migration drops outputs {missing} that dependents {dependents} rely on")
    install(root, spec, code, tests_pass=tests_pass)
    state = _load(root)
    state["genomes"][name]["rollback_to"] = state["genomes"][name]["active"]
    state["genomes"][name]["active"] = spec["version"]
    _save(root, state)
    return {"name": name, "active": spec["version"], "rollback_to": old["version"]}


def rollback(root: Path, name: str) -> dict:
    state = _load(root)
    entry = state["genomes"][name]
    target = entry.get("rollback_to") or (_ for _ in ()).throw(RegistryError(f"{name} has no rollback target"))
    entry["rollback_to"], entry["active"] = entry["active"], target
    _save(root, state)
    return {"name": name, "active": target}


def report(root: Path, now: str) -> dict:
    state = _load(root)
    outcomes = [o for e in state["genomes"].values() for o in e["outcomes"]]
    return {"genomes": {n: {"state": e["state"], "active": e["active"], "versions": sorted(e["versions"]),
                            "incidents": len(e["incidents"])} for n, e in sorted(state["genomes"].items())},
            "reputation": reputation.score(outcomes, now=now)["subjects"]}


QUERY_OPS = {"report": lambda a, r: report(r, a["now"])}
APPLY_OPS = {"install": lambda a, r: install(r, a["spec"], a["code"], tests_pass=bool(a["tests_pass"])),
             "attach": lambda a, r: attach(r, a["name"], environment=a.get("environment")),
             "detach": lambda a, r: detach(r, a["name"]),
             "measure": lambda a, r: measure(r, a["name"], verdict=a["verdict"], at=a["at"], evidence=a["evidence"],
                                             incident=a.get("incident", False), recovered=a.get("recovered", False)),
             "rollback": lambda a, r: rollback(r, a["name"])}


def spec(name, version, outputs, *, deps=(), contra=(), consequence="read_only"):
    return {"name": name, "version": version, "description": f"{name} capability",
            "interface": {"inputs": {"query": "str"}, "outputs": {o: "str" for o in outputs}},
            "authority": {"max_consequence_class": consequence, "budget_ceiling_usd": 0.0},
            "acceptance_tests": [f"tests::{name}"], "failure_modes": ["timeout"], "recovery_path": "detach and retry",
            "dependencies": list(deps), "contraindications": list(contra)}


def exercise(root) -> dict:
    root = Path(root)
    now = "2026-09-27T00:00:00Z"
    install(root, spec("buyer-scoring", "1.0", ["score", "reasons"]), "def score(): ...", tests_pass=True)
    install(root, spec("offer-design", "1.0", ["offer"], deps=["buyer-scoring"], contra=["regulated_health_data"]),
            "def offer(): ...", tests_pass=True)
    refusals = {}
    def refused(label, fn):
        try:
            fn()
            refusals[label] = False
        except (RegistryError, ValueError) as exc:
            refusals[label] = f"{type(exc).__name__}: {exc}"
    refused("attach_before_dependency", lambda: attach(root, "offer-design"))
    attach(root, "buyer-scoring")
    refused("contraindicated", lambda: attach(root, "offer-design", environment={"regulated_health_data": True}))
    attach(root, "offer-design")
    refused("detach_with_dependents", lambda: detach(root, "buyer-scoring"))
    refused("failing_tests_install", lambda: install(root, spec("x", "1.0", ["y"]), "", tests_pass=False))
    refused("invalid_genome", lambda: install(root, spec("bad", "1.0", ["y"], consequence="financial"), "", tests_pass=True))
    refused("breaking_migration", lambda: migrate(root, "buyer-scoring", spec("buyer-scoring", "2.0", ["score"]), "v2",
                                                  tests_pass=True))
    migrated = migrate(root, "buyer-scoring", spec("buyer-scoring", "2.0", ["score", "reasons", "confidence"]), "v2",
                       tests_pass=True)
    for n in range(4):
        measure(root, "buyer-scoring", verdict="VERIFIED", at=now, evidence=f"receipt-{n}")
    measure(root, "buyer-scoring", verdict="REFUTED", at=now, evidence="receipt-bad", incident=True)
    rolled = rollback(root, "buyer-scoring")
    detach(root, "offer-design")
    detached = detach(root, "buyer-scoring")
    return {"refusals": refusals, "migrated": migrated, "rolled_back_to": rolled["active"],
            "detached_keeps_versions": detached["retained_versions"],
            "report": report(root, now)["genomes"]}
