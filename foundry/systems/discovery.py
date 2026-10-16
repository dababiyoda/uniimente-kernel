"""#27 Service discovery: organs publish signed, typed capability manifests; discovery grants nothing.

Each organ is enrolled once with a pinned Ed25519 public key. It then publishes
a signed descriptor: its capabilities, the contracts each consumes/produces
(names must exist in contracts/, so every edge is typed), consequence class,
health, cost and latency, a sequence number and a time-to-live. The directory
refuses unknown organs, bad signatures, untyped contracts and replayed or
older sequences. ``discover`` answers "who produces X / consumes Y" with fresh,
healthy entries ranked by latency then cost, and never returns a credential:
invoking a discovered capability still goes through the Kernel gate with its
own grant. The static organ manifests (organs/*.manifest.yaml, validated by
linker/manifest.py) seed the directory as unsigned, health-unknown entries.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from capabilities.genome import CONSEQUENCE_CLASSES


class DiscoveryError(ValueError):
    pass


def _canon(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _load(root: Path) -> dict:
    p = Path(root) / "directory.json"
    return json.loads(p.read_text()) if p.exists() else {"organs": {}, "entries": {}}


def _save(root: Path, state: dict) -> None:
    Path(root).mkdir(parents=True, exist_ok=True)
    tmp = Path(root) / "directory.tmp"
    tmp.write_text(json.dumps(state, sort_keys=True, indent=1))
    tmp.replace(Path(root) / "directory.json")


def enroll(root: Path, organ_id: str, public_hex: str) -> dict:
    state = _load(root)
    if organ_id in state["organs"] and state["organs"][organ_id] != public_hex:
        raise DiscoveryError(f"{organ_id} is already enrolled with a different key; re-enrollment is a founder act")
    state["organs"][organ_id] = public_hex
    _save(root, state)
    return {"organ_id": organ_id, "enrolled": True}


def sign(private_key, descriptor: dict) -> dict:
    return {"descriptor": descriptor, "signature": private_key.sign(_canon(descriptor)).hex()}


def _check_descriptor(d: dict, contracts: set[str]) -> None:
    required = {"organ_id", "sequence", "published_at", "ttl_s", "capabilities"}
    if set(d) != required:
        raise DiscoveryError(f"descriptor fields must be exactly {sorted(required)}")
    for cap in d["capabilities"]:
        for key in ("capability_id", "consumes", "produces", "consequence_class", "health", "cost_usd", "latency_ms"):
            if key not in cap:
                raise DiscoveryError(f"capability missing {key}")
        if cap["consequence_class"] not in CONSEQUENCE_CLASSES:
            raise DiscoveryError(f"unknown consequence class {cap['consequence_class']!r}")
        untyped = sorted((set(cap["consumes"]) | set(cap["produces"])) - contracts)
        if untyped:
            raise DiscoveryError(f"{cap['capability_id']} names untyped contracts {untyped}")


def publish(root: Path, signed: dict) -> dict:
    from linker.linker import known_contracts
    d = signed["descriptor"]
    state = _load(root)
    public_hex = state["organs"].get(d.get("organ_id"))
    if public_hex is None:
        raise DiscoveryError(f"organ {d.get('organ_id')!r} is not enrolled")
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex)).verify(bytes.fromhex(signed["signature"]), _canon(d))
    except (InvalidSignature, ValueError):
        raise DiscoveryError("manifest signature does not verify against the enrolled key") from None
    _check_descriptor(d, set(known_contracts()))
    current = state["entries"].get(d["organ_id"])
    if current and current.get("sequence", -1) >= d["sequence"]:
        raise DiscoveryError(f"sequence {d['sequence']} is not newer than {current['sequence']} (replay or rollback)")
    state["entries"][d["organ_id"]] = {**d, "signed": True}
    _save(root, state)
    return {"organ_id": d["organ_id"], "sequence": d["sequence"], "capabilities": len(d["capabilities"])}


def seed_static(root: Path) -> dict:
    from linker.manifest import load_all
    state = _load(root)
    seeded = []
    for m in load_all():
        if m.organ_id in state["entries"]:
            continue
        state["entries"][m.organ_id] = {
            "organ_id": m.organ_id, "sequence": 0, "published_at": None, "ttl_s": None, "signed": False,
            "capabilities": [{"capability_id": c["capability_id"], "consumes": c.get("consumes", []),
                              "produces": c.get("produces", []), "consequence_class": None, "health": "unknown",
                              "cost_usd": None, "latency_ms": None} for c in m.capabilities]}
        seeded.append(m.organ_id)
    _save(root, state)
    return {"seeded": seeded}


def discover(root: Path, *, now: str, produces: str | None = None, consumes: str | None = None,
             include_unverified: bool = False) -> dict:
    hits = []
    for organ, e in sorted(_load(root)["entries"].items()):
        fresh = e["signed"] and _t(now) < _t(e["published_at"]) + timedelta(seconds=e["ttl_s"])
        if not fresh and not include_unverified:
            continue
        for cap in e["capabilities"]:
            if produces and produces not in cap["produces"]:
                continue
            if consumes and consumes not in cap["consumes"]:
                continue
            if fresh and cap["health"] != "up":
                continue
            hits.append({"organ_id": organ, **cap, "verified": fresh, "grants_access": False})
    hits.sort(key=lambda h: (not h["verified"], h["latency_ms"] if h["latency_ms"] is not None else 1e12,
                             h["cost_usd"] if h["cost_usd"] is not None else 1e12, h["capability_id"]))
    return {"matches": hits}


QUERY_OPS = {"discover": lambda a, r: discover(r, now=a["now"], produces=a.get("produces"), consumes=a.get("consumes"),
                                               include_unverified=bool(a.get("include_unverified")))}
APPLY_OPS = {"enroll": lambda a, r: enroll(r, a["organ_id"], a["public_key"]),
             "publish": lambda a, r: publish(r, a["signed"]),
             "seed_static": lambda a, r: seed_static(r)}


def exercise(root) -> dict:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from foundry.systems.kernel_stack import agent, gate_stack, proposal
    from greg.founder import public_bytes
    root = Path(root)
    now = "2026-09-27T12:00:00Z"
    wmi_key = Ed25519PrivateKey.from_private_bytes(bytes(32 * [11]))
    dale_key = Ed25519PrivateKey.from_private_bytes(bytes(32 * [12]))
    rogue = Ed25519PrivateKey.from_private_bytes(bytes(32 * [13]))
    enroll(root, "organ:wmi", public_bytes(wmi_key.public_key()).hex())
    enroll(root, "organ:daleobanks", public_bytes(dale_key.public_key()).hex())

    def cap(cid, consumes, produces, health="up", cost=0.0, latency=100, cls="read_only"):
        return {"capability_id": cid, "consumes": consumes, "produces": produces, "consequence_class": cls,
                "health": health, "cost_usd": cost, "latency_ms": latency}

    def desc(organ, seq, caps, at=now, ttl=3600):
        return {"organ_id": organ, "sequence": seq, "published_at": at, "ttl_s": ttl, "capabilities": caps}

    wmi_v1 = sign(wmi_key, desc("organ:wmi", 1, [cap("wmi.assess", ["wire-opportunity-packet"],
                                                     ["wire-venture-assessment"], latency=900)]))
    publish(root, wmi_v1)
    publish(root, sign(dale_key, desc("organ:daleobanks", 1, [
        cap("dale.assess_fast", ["wire-opportunity-packet"], ["wire-venture-assessment"], latency=200, cost=0.01),
        cap("dale.assess_down", ["wire-opportunity-packet"], ["wire-venture-assessment"], health="down", latency=10)])))
    refusals = {}
    def refused(label, fn):
        try:
            fn()
            refusals[label] = False
        except DiscoveryError as exc:
            refusals[label] = str(exc)
    refused("unenrolled_organ", lambda: publish(root, sign(rogue, desc("organ:rogue", 1, []))))
    refused("forged_signature", lambda: publish(root, sign(rogue, desc("organ:wmi", 2, []))))
    refused("replayed_sequence", lambda: publish(root, wmi_v1))
    refused("untyped_contract", lambda: publish(root, sign(wmi_key, desc("organ:wmi", 3, [cap("x", ["made-up"], [])]))))
    refused("rekey_without_founder", lambda: enroll(root, "organ:wmi", public_bytes(rogue.public_key()).hex()))
    found = discover(root, now=now, produces="wire-venture-assessment")["matches"]
    stale = discover(root, now="2026-09-27T14:00:00Z", produces="wire-venture-assessment")["matches"]
    seeded = seed_static(root)
    with_static = discover(root, now=now, include_unverified=True)["matches"]

    # discovery grants nothing: using a discovered capability still needs the gate and its own grant
    gate, passports, _ = gate_stack()
    actor = agent(passports)
    ungranted = gate.run(proposal(actor.passport_id, target=f"organ:{found[0]['capability_id']}"), executor=lambda p: "ok")
    return {"ranked": [(h["capability_id"], h["latency_ms"]) for h in found],
            "down_excluded": all(h["capability_id"] != "dale.assess_down" for h in found),
            "stale_after_ttl": len(stale), "grants_access": any(h["grants_access"] for h in with_static),
            "refusals": refusals, "static_seeded": seeded["seeded"],
            "static_entries": sum(1 for h in with_static if not h["verified"]),
            "use_without_grant": ungranted.state}
