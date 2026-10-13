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

from .contract_check import validate_record
from .contracts import canonical_copy, digest, require_text
from .goals import CONSEQUENCE_CLASSES, GoalRegistry, iso, parse_time

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

    INTERVENTION_RECORD = "egregore.intervention"   # written by the loop; read here to bind outcomes to goals

    def __init__(self, *, ledger: Any, registry: GoalRegistry, genomes: GenomeRegistry,
                 source: str = "spiffe://uniimente.internal/egregore/goal-gravity"):
        self.ledger = ledger
        self.registry = registry
        self.genomes = genomes
        self.source = require_text("source", source)
        self._hydrate_genomes()

    @property
    def execution_authority(self) -> str:
        return "none"

    def _hydrate_genomes(self) -> None:
        """Capabilities retained on the ledger survive a restart: re-register them into the genome registry."""
        for record in self.ledger.by_type(self.ASSET_RECORD):
            for asset in record.payload.get("retention", {}).get("assets", []):
                cap = asset.get("capability")
                if not cap:
                    continue
                cap = dict(cap)
                try:
                    genome = CapabilityGenome(authority=AuthorityEnvelope(**cap.pop("authority")), **cap)
                except TypeError:
                    continue   # a malformed historical record is evidence, not a registration
                if self.genomes.get(genome.name, genome.version) is None and not genome.validate():
                    self.genomes._genomes[f"{genome.name}@{genome.version}"] = genome   # replay, no new ledger event

    def _outcome(self, outcome_ref: str) -> dict[str, Any] | None:
        for record in self.ledger.by_type("outcome"):
            if record.hash == outcome_ref or record.payload.get("outcome_id") == outcome_ref:
                return canonical_copy(record.payload)
        return None

    def _outcome_bound_to_goal(self, goal_id: str, outcome: Mapping[str, Any]) -> bool:
        """The outcome must belong to a move this goal executed (loop intervention record carrying the action id)."""
        action_ref = outcome.get("action_ref")
        for record in self.ledger.by_type(self.INTERVENTION_RECORD):
            p = record.payload
            if p.get("goal_id") == goal_id and p.get("evidence_state") in ("executed", "externally_verified") \
                    and p.get("detail", {}).get("action_id") == action_ref:
                return True
        return False

    def retain(self, *, goal_id: str, outcome_ref: str, what_worked: Sequence[str], assets: Sequence[DurableAsset],
               new_options: Sequence[str] = (), now: datetime | str) -> RetentionRecord:
        spec = self.registry.get(goal_id)
        outcome_ref = require_text("outcome_ref", outcome_ref)
        outcome = self._outcome(outcome_ref)
        if outcome is None:
            raise ValueError("retention requires a ledgered outcome; a claim is not an outcome")
        if not self._outcome_bound_to_goal(goal_id, outcome):
            raise ValueError("the outcome is not bound to a move this goal executed through the Gate")
        retained_at = iso(parse_time(now))
        ceiling = CONSEQUENCE_CLASSES.index(spec.authority["max_consequence_class"])
        registered: list[str] = []
        for asset in assets:
            if not isinstance(asset, DurableAsset):
                raise ValueError("assets must be DurableAsset instances")
            if asset.capability:
                cap = dict(asset.capability)
                envelope = AuthorityEnvelope(**cap.pop("authority"))
                if CONSEQUENCE_CLASSES.index(envelope.max_consequence_class) > ceiling:
                    raise ValueError(f"capability envelope {envelope.max_consequence_class} exceeds the goal's authority "
                                     f"ceiling {spec.authority['max_consequence_class']}; retention never inflates authority")
                genome = CapabilityGenome(authority=envelope, **cap)
                key = f"{genome.name}@{genome.version}"
                if self.genomes.get(genome.name, genome.version) is None:
                    self.genomes.register(genome)
                registered.append(key)
        cheaper: list[str] = []
        for other in self.registry.goals():
            state = self.registry.state(other)
            if state.status in ("revoked", "completed", "superseded"):
                continue
            missing = list(state.missing_capabilities)
            resolved = [c for c in missing if c in registered]
            if resolved:
                remaining = [c for c in missing if c not in registered]
                self.registry.transition(other, reason=f"capability retained from goal {goal_id[:19]}: {', '.join(resolved)}",
                                         now=now, missing_capabilities=remaining)
                cheaper.append(other)
                self._resolve_deficits(other, resolved, retained_at=retained_at, resolved_by=f"retention:{goal_id[:19]}")
        record = RetentionRecord(
            retention_id=digest({"kind": "egregore-retention", "goal_id": goal_id, "outcome_ref": outcome_ref}),
            goal_id=goal_id, outcome_ref=outcome_ref, what_worked=tuple(require_text("what_worked[]", w) for w in what_worked),
            assets=tuple(a.to_dict() for a in assets), capabilities_registered=tuple(registered),
            goals_made_cheaper=tuple(cheaper), new_options=tuple(new_options), retained_at=retained_at)
        self.ledger.append(self.ASSET_RECORD, {"source": self.source, "retention": record.to_dict(),
                                               "disposition": "durable_asset_recorded"})
        return record

    def _resolve_deficits(self, goal_id: str, capabilities: Sequence[str], *, retained_at: str, resolved_by: str) -> None:
        """Close open capability deficits whose missing capabilities are now registered; the goal resumes."""
        from .interventions import InterventionClassifier
        open_ids: set[str] = set()
        resolved_ids: set[str] = set()
        records = self.ledger.by_type(InterventionClassifier.DEFICIT_RECORD)
        for r in records:
            d = r.payload.get("deficit")
            if not d:
                continue
            if d["disposition"] == "resolved_resume_original_goal":
                resolved_ids.add(d["deficit_id"])
            elif d["goal_id"] == goal_id:
                open_ids.add(d["deficit_id"])
        for r in records:
            d = r.payload.get("deficit")
            if not d or d["deficit_id"] not in open_ids or d["deficit_id"] in resolved_ids:
                continue
            if not set(d["missing_capabilities"]) <= set(capabilities):
                continue
            closed = {**d, "lifecycle": "TESTED", "disposition": "resolved_resume_original_goal",
                      "resolved_at": retained_at, "resolved_by": resolved_by}
            validate_record(closed, "capability-deficit")
            self.ledger.append(InterventionClassifier.DEFICIT_RECORD, {
                "source": self.source, "deficit": closed, "goal_id": goal_id,
                "missing_capabilities": closed["missing_capabilities"], "founder_intent": closed["founder_intent"],
                "disposition": closed["disposition"]})
            resolved_ids.add(d["deficit_id"])

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
