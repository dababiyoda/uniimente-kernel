"""Body and compute manager: measure the body, recommend growth, never self-provision.

The first computer is Body 1, not the institution's identity. The institution is
the ledger, the founder key and the missions; a replacement machine restores
from them. Additional nodes join only by founder-signed NODE_ENROLL, each with
its own identity and a bounded light cone, never universal authority.

Growth is an instrument for founder goals. Telemetry may justify a
recommendation with alternatives and uncertainty; it may not buy, rent or
install anything, and it never argues from self-preservation.
"""
from __future__ import annotations

import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from greg import asks
from greg.journal import Journal, iso, utcnow
from greg.lightcone import LightCone
from provenance.ledger import sha256_json

LOAD_RATIO_THRESHOLD = 0.9
DISK_FREE_THRESHOLD = 0.10
SUSTAINED_SAMPLES = 5


def memory_bytes() -> int | None:
    try:
        if sys.platform == "darwin":
            out = subprocess.run(["/usr/sbin/sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5)
            return int(out.stdout.strip())
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (OSError, ValueError):
        return None


def sample(home: Path) -> dict:
    cores = os.cpu_count() or 1
    load1 = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0
    disk = shutil.disk_usage(home)
    return {"at": iso(utcnow()), "machine": platform.machine(), "system": platform.system(),
            "cores": cores, "load1": round(load1, 3), "load_ratio": round(load1 / cores, 3),
            "memory_bytes": memory_bytes(), "disk_total": disk.total, "disk_free": disk.free,
            "disk_free_ratio": round(disk.free / disk.total, 4) if disk.total else None}


def record_telemetry(journal: Journal, home: Path, *, telemetry: dict | None = None) -> dict:
    data = telemetry or sample(home)
    journal.record("compute.telemetry", data, key=data["at"])
    return data


def bottleneck(journal: Journal) -> dict | None:
    samples = [e.payload for e in journal.replay("compute.telemetry")][-SUSTAINED_SAMPLES:]
    if len(samples) < SUSTAINED_SAMPLES:
        return None
    if all(s["load_ratio"] >= LOAD_RATIO_THRESHOLD for s in samples):
        return {"resource": "cpu", "evidence": [s["at"] for s in samples],
                "measure": f"load/cores >= {LOAD_RATIO_THRESHOLD} for {SUSTAINED_SAMPLES} samples"}
    if all(s["disk_free_ratio"] is not None and s["disk_free_ratio"] < DISK_FREE_THRESHOLD for s in samples):
        return {"resource": "disk", "evidence": [s["at"] for s in samples],
                "measure": f"free disk < {DISK_FREE_THRESHOLD:.0%} for {SUSTAINED_SAMPLES} samples"}
    return None


def recommend(journal: Journal) -> dict | None:
    """Turn a sustained bottleneck into ONE founder decision request with alternatives."""
    found = bottleneck(journal)
    if found is None:
        return None
    request_id = "req-compute-" + sha256_json({"resource": found["resource"]})[7:23]
    if any(e.payload["request_id"] == request_id for e in journal.replay("decision.requested")):
        return None
    samples = [e.payload for e in journal.replay("compute.telemetry")][-SUSTAINED_SAMPLES:]
    message = asks.resource_request(
        request_id=request_id, kind="COMPUTE", resource="compute", scope_digest=sha256_json(found),
        why_now=found["measure"],
        recommendation="optimize the heaviest mission workload first; if still constrained, price cloud burst "
                       "versus an additional enrolled node and decide on measured ROI",
        expected_effect="missions stop queueing behind a saturated " + found["resource"] + "; the improvement is "
                        "benchmarked on the same missions before any growth is kept",
        options=[
            {"option": "software/workload optimization (no spend)", "cost": "none in money; engineering time",
             "expected_effect": "lower load from the same missions; measured by the next telemetry window"},
            {"option": "temporary cloud compute (metered)", "cost": "metered provider price; data leaves this body",
             "expected_effect": "burst capacity for the heaviest missions while it runs"},
            {"option": "additional local node (capital purchase; human installation)",
             "cost": "hardware price and your installation time",
             "expected_effect": "durable capacity as a separately enrolled body with its own bounded identity"},
            {"option": "do nothing: missions wait", "cost": "none",
             "expected_effect": "missions continue at current capacity and finish later"}],
        evidence={"bottleneck": found, "samples": [{k: s.get(k) for k in ("at", "cores", "load_ratio",
                                                                          "disk_free_ratio")} for s in samples]},
        uncertainty="prices and workload growth are not yet measured; no ROI claim is made",
        authority_requested={"spend": "none requested; any purchase is a separate founder decision"},
        consequence_of_no_response="missions continue at current capacity; nothing is bought",
        created_at=iso(utcnow()))
    return asks.record(journal, message)


def enroll_node(journal: Journal, body: dict, command_digest: str) -> dict:
    required = {"node_id", "node_public_key", "light_cone"}
    if set(body) != required:
        raise ValueError("NODE_ENROLL needs node_id, node_public_key, light_cone")
    cone = LightCone.from_dict(body["light_cone"])
    if bytes.fromhex(body["node_public_key"]).__len__() != 32:
        raise ValueError("node key must be a 32-byte Ed25519 public key")
    record = {"node_id": body["node_id"], "node_public_key": body["node_public_key"], "light_cone": cone.to_dict(),
              "founder_authority_inherited": False, "command_digest": command_digest}
    journal.record("node.enrolled", record, key=body["node_id"])
    return record
