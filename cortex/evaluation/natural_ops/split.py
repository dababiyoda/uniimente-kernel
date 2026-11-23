"""Deterministic split by instance id, declared before any held-out instance was scored.

``development`` iff ``int(instance_id, 16) % 10 < 3`` (about 30%); every other instance is ``heldout``. The id is a
hash of (S, T, relevant-subgraph digest), so the split cannot see any arm's output or the truth.
"""
from __future__ import annotations

DEV_BUCKETS = 3


def part(instance_id: str) -> str:
    return "development" if int(instance_id, 16) % 10 < DEV_BUCKETS else "heldout"


def split(instances):
    dev = [i for i in instances if part(i["instance_id"]) == "development"]
    held = [i for i in instances if part(i["instance_id"]) == "heldout"]
    return dev, held
