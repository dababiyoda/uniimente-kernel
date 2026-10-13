"""Asymmetry Retention (target H): every verified success leaves a durable asset.

After a mission outcome is recorded, extract what worked, which durable
assets were created, which capability became reusable (registered as a
Capability Genome under its own bounded envelope), which new options exist,
and which other goals became cheaper because a capability they were
missing now exists. Goals do not learn from claims: retention is anchored to
a ledger outcome reference.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from capabilities.genome import AuthorityEnvelope, CapabilityGenome, GenomeRegistry

from .contracts import canonical_copy, digest, require_text
from .goals import GoalRegistry, iso, parse_time

ASSET_KINDS = ("knowledge", "evidence", "software", "automation", "relationship", "reputation", "distribution",
               "data", "permission", "capability", "contract", "cash", "ownership", "infrastructure",
               "intellectual_property", "institutional_memory", "optionality")


@dataclass(frozen=True)
class DurableAsset:
    kind: str
    name: str
    description: str
    evidence_refs: tuple[str, ...]
    capability: dict[str, Any] | None = None   # CapabilityGenome fields when reusable

    @classmethod
    def build(cls, *, kind: str, name: str, description: str, evidence_refs: Sequence[str] = (),
              capability: Mapping[str, Any] | None = None) -> "DurableAsset":
        if kind not in ASSET_KINDS:
            raise ValueError(f"unknown asset kind {kind!r}")
        return cls(kind=kind, name=require_text("name", name), description=require_text("description", description),
                   evidence_refs=tuple(require_text("evidence_refs[]", r) for r in evidence_refs),
                   capability=canonical_copy(dict(capability)) if capability else None)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "name": self.name, "description": self.description,
                "evidence_refs": list(self.evidence_refs), "capability": canonical_copy(self.capability)}


@dataclass(frozen=True)
class RetentionRecord:
    retention_id: str
    goal_id: str
    outcome_ref: str
    what_worked: tuple[str, ...]
    assets: tuple[dict[str, Any], ...]
    capabilities_registered: tuple[str, ...]
    goals_made_cheaper: tuple[str, ...]
    new_options: tuple[str, ...]
    retained_at: str

    def to_dict(self) -> dict[str, Any]:
        return {"retention_id": self.retention_id, "goal_id": self.goal_id, "outcome_ref": self.outcome_ref,
                "what_worked": list(self.what_worked), "assets": [canonical_copy(a) for a in self.assets],
                "capabilities_registered": list(self.capabilities_registered),
                "goals_made_cheaper": list(self.goals_made_cheaper), "new_options": list(self.new_options),
                "retained_at": self.retained_at}


class AsymmetryRetention:
    ASSET_RECORD = "egregore.asset_retained"

    def __init__(self, *, ledger: Any, registry: GoalRegistry, genomes: GenomeRegistry,
                 source: str = "spiffe://uniimente.internal/egregore/goal-gravity"):
        self.ledger = ledger
        self.registry = registry
        self.genomes = genomes
        self.source = require_text("source", source)

    @property
    def execution_authority(self) -> str:
        return "none"

    def _outcome_exists(self, outcome_ref: str) -> bool:
        for record in self.ledger.by_type("outcome"):
            if record.hash == outcome_ref or record.payload.get("outcome_id") == outcome_ref:
                return True
        return False

    def retain(self, *, goal_id: str, outcome_ref: str, what_worked: Sequence[str], assets: Sequence[DurableAsset],
               new_options: Sequence[str] = (), now: datetime | str) -> RetentionRecord:
        self.registry.get(goal_id)
        outcome_ref = require_text("outcome_ref", outcome_ref)
        if not self._outcome_exists(outcome_ref):
            raise ValueError("retention requires a ledgered outcome; a claim is not an outcome")
        retained_at = iso(parse_time(now))
        registered: list[str] = []
        for asset in assets:
            if not isinstance(asset, DurableAsset):
                raise ValueError("assets must be DurableAsset instances")
            if asset.capability:
                cap = dict(asset.capability)
                envelope = AuthorityEnvelope(**cap.pop("authority"))
                genome = CapabilityGenome(authority=envelope, **cap)
                key = f"{genome.name}@{genome.version}"
                if self.genomes.get(genome.name, genome.version) is None:
                    self.genomes.register(genome)
                registered.append(key)
        cheaper: list[str] = []
        for other in self.registry.goals():
            state = self.registry.state(other)
            spec = self.registry.get(other)
            missing = list(state.missing_capabilities or spec.missing_capabilities)
            resolved = [c for c in missing if c in registered]
            if resolved:
                remaining = [c for c in missing if c not in registered]
                self.registry.transition(other, reason=f"capability retained from goal {goal_id[:19]}: {', '.join(resolved)}",
                                         now=now, missing_capabilities=remaining)
                cheaper.append(other)
        record = RetentionRecord(
            retention_id=digest({"kind": "egregore-retention", "goal_id": goal_id, "outcome_ref": outcome_ref}),
            goal_id=goal_id, outcome_ref=outcome_ref, what_worked=tuple(require_text("what_worked[]", w) for w in what_worked),
            assets=tuple(a.to_dict() for a in assets), capabilities_registered=tuple(registered),
            goals_made_cheaper=tuple(cheaper), new_options=tuple(new_options), retained_at=retained_at)
        self.ledger.append(self.ASSET_RECORD, {"source": self.source, "retention": record.to_dict(),
                                               "disposition": "durable_asset_recorded"})
        return record

    def compounding_report(self) -> dict[str, Any]:
        by_kind: dict[str, int] = {}
        capabilities: set[str] = set()
        cheaper: set[str] = set()
        retentions = 0
        for record in self.ledger.by_type(self.ASSET_RECORD):
            retentions += 1
            r = record.payload["retention"]
            for asset in r["assets"]:
                by_kind[asset["kind"]] = by_kind.get(asset["kind"], 0) + 1
            capabilities.update(r["capabilities_registered"])
            cheaper.update(r["goals_made_cheaper"])
        return {"retentions": retentions, "assets_by_kind": by_kind, "capabilities_registered": sorted(capabilities),
                "goals_made_cheaper": sorted(cheaper)}
