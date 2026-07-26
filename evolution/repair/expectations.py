"""Frozen spec -> DeclaredContract. Plumbing, not a mechanism.

This exists so that `detector.py` never imports `spec.py`. The spec names the
subject package (`SUBJECT_PACKAGE = "linker"`), so a detector that could read the
spec could read the answer. Routing the contract through this module keeps the
detector's blindness structural: it receives expected relations and nothing else.
"""
from __future__ import annotations

from evolution.repair import spec
from evolution.repair.detector import DeclaredContract


def live_contract() -> DeclaredContract:
    """The declared contract for the measurement corpus."""
    req = spec.REQUIRED_REFUSALS
    return DeclaredContract(
        capability=spec.TARGET_CAPABILITY,
        corpus_id=spec.MEASUREMENT_CORPUS["corpus_id"],
        required_edges=tuple(spec.REQUIRED_EDGE_TRIPLES),
        required_untyped=tuple(req["untyped"]),
        required_unconsumed=tuple(req["unconsumed"]),
        required_unproduced=tuple(req["unproduced"]),
        required_unresolved_count=req["unresolved_count"],
        required_overlapping=tuple(req["overlapping_authority"]),
        required_fully_connected=req["fully_connected"],
    )


def held_out_contract(case: dict) -> DeclaredContract:
    """The declared contract for one frozen held-out case."""
    exp = case["expected"]
    return DeclaredContract(
        capability=spec.TARGET_CAPABILITY,
        corpus_id=case["corpus_id"],
        required_edges=tuple(exp["edges"]),
        required_untyped=tuple(exp["untyped"]),
        required_unconsumed=tuple(exp["unconsumed"]),
        required_unproduced=tuple(exp["unproduced"]),
        required_unresolved_count=len(exp["unresolved"]),
        required_overlapping=tuple(exp["overlapping_authority"]),
        required_fully_connected=exp["fully_connected"],
    )


def all_contracts() -> dict[str, DeclaredContract]:
    """Every corpus the experiment scores, keyed by corpus id."""
    out = {"LIVE": live_contract()}
    for case in spec.HELD_OUT_CORPUS:
        out[case["corpus_id"]] = held_out_contract(case)
    return out
