"""Canonical fifteen-module closure registry.

This wrapper preserves the first complete-registry implementation while
repairing the Foundry regenerative check to inspect the canonical serialized
event payload rather than trying to serialize live StrategyBranch objects.
"""
from __future__ import annotations

import json

from foundry import AdvantageFoundry
from provenance.ledger import EvidenceLedger

from . import complete_registry as _complete
from .framework import ModuleClosures


def _foundry_regenerative() -> tuple[bool, str]:
    ledger = EvidenceLedger("sha256:" + "0" * 64)
    foundry = AdvantageFoundry(ledger)
    architecture = _complete._architecture(foundry)
    genome = foundry.seal_advantage_genome(
        "proof-diagnostic",
        "1.0.0",
        architecture,
        ("research.read@1.0.0", "offer.compile@1.0.0"),
        _complete._outcome(),
        time_to_validated_genome_days=7,
        rollback="revoke grants and restore prior workflow",
    )

    tournaments = [
        record.payload
        for record in ledger.by_type("event")
        if record.payload.get("type") == "foundry.route_tournament_completed"
    ]
    if len(tournaments) != 1:
        return False, "exactly one route tournament must be preserved"

    tournament = tournaments[0]
    winner = tournament.get("winning_branch")
    rejected = tournament.get("rejected_branches")
    if not isinstance(winner, dict):
        return False, "winning branch was not serialized as data"
    if not isinstance(rejected, list) or len(rejected) != 10:
        return False, "all ten rejected branches must remain serialized"

    # Prove the preserved strategic search is portable JSON rather than a live
    # Python object graph that disappears or fails after process loss.
    preserved = json.dumps(
        {"winner": winner, "rejected": rejected},
        sort_keys=True,
    )
    restarted = AdvantageFoundry(ledger)
    rebuilt = restarted.get_genome("proof-diagnostic", "1.0.0")
    ok = (
        bool(preserved)
        and bool(genome.rollback)
        and bool(genome.kill_conditions)
        and rebuilt == genome
        and ledger.verify_chain()[0]
    )
    return ok, "winner, ten rejected branches, rollback, kill criteria, and sealed Genome survive restart"


def build_registry():
    registry = _complete.build_registry()
    existing = registry._modules["foundry"]
    checks = dict(existing.checks)
    checks["regenerative"] = _foundry_regenerative
    registry.register(ModuleClosures("foundry", checks))
    return registry


__all__ = ["build_registry"]
