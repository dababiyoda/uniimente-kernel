"""Shared GREG test fixtures: a real body, a real Ed25519 founder key, signed commands.

The founder key here is a test key generated per test. It is real cryptography but
it is NOT Alfonso's key; no test claims founder authentication of a real person.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from greg.body import Body, init_body
from greg.founder import generate_founder_key, load_founder_key, sign_command


class Clock:
    def __init__(self, start: datetime | None = None):
        self.now = start or datetime.now(timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds: float):
        self.now += timedelta(seconds=seconds)


def make_body(tmp: Path, *, read_roots=None):
    tmp = Path(tmp)
    data = tmp / "data"
    data.mkdir(exist_ok=True)
    home = tmp / "body"
    config = init_body(home, read_roots=[str(p) for p in (read_roots or [data])])
    public = generate_founder_key(tmp / "founder.pem", None)
    key = load_founder_key(tmp / "founder.pem", None)
    with Body(home) as body:
        body.enroll_founder(public)
    return home, key, config["body_id"], data


def horizon(days: float = 2) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat().replace("+00:00", "Z")


def mission(mission_id: str, *, checks: list, strategies: list, capabilities: list, targets=("fs:*", "workspace:*"),
            ceiling="internal_write", closure=None, budget=0.0, auto_attach=False, priority=50) -> dict:
    spec = {"mission_id": mission_id, "founder_expression": f"test founder words for {mission_id}",
            "intended_effect": f"observable effect of {mission_id}", "priority": priority,
            "closure": closure or {"kind": "bounded"}, "success_checks": checks, "strategies": strategies,
            "light_cone": {"capabilities": capabilities, "targets": list(targets), "max_consequence_class": ceiling,
                           "budget_usd": budget, "horizon": horizon()}}
    if auto_attach:
        spec["auto_attach"] = {"max_consequence_class": "read_only"}
    return spec


def note_check(check_id: str, path: Path, text: str) -> dict:
    return {"check_id": check_id, "description": f"{path.name} contains {text}",
            "sensor": {"capability": "fs.read", "params": {"path": str(path)}, "target": f"fs:{path.name}"},
            "predicate": {"op": "contains", "field": "text", "value": text}}


def write_strategy(action_id: str, relative: str, content: str, advances: list, **extra) -> dict:
    return {"action_id": action_id, "capability": "fs.write",
            "params": {"relative_path": relative, "content": content}, "target": f"workspace:{relative}",
            "advances": advances, "rationale": f"write {relative}", **extra}


def workspace(home: Path, mission_id: str) -> Path:
    return Path(home).resolve() / "workspace" / mission_id.replace(":", "_")


def signed(key, body_id: str, kind: str, body: dict, **kw) -> dict:
    return sign_command(key, kind, body, body_id=body_id, **kw)


def drop(home: Path, envelope: dict, name: str | None = None) -> Path:
    path = Path(home) / "inbox" / (name or f"{envelope['nonce']}.json")
    path.write_text(json.dumps(envelope))
    return path
