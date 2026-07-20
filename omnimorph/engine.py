from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Protocol

from foundry.contracts import AdvantageArchitecture, ExternalOutcome, FoundryError

class GenomeRegistryLike(Protocol):
    def get(self, name: str, version: str) -> Any: ...
    def may_instantiate(self, name: str, version: str, *, requested_class: str, requested_budget_usd: float) -> tuple[bool, str]: ...

@dataclass(frozen=True)
class CapabilityBinding:
    capability: str
    version: str
    requested_class: str
    budget_usd: float

@dataclass(frozen=True)
class OrganManifest:
    organ_id: str
    architecture_hash: str
    objective: str
    legal_operator: str
    bindings: tuple[CapabilityBinding, ...]
    aggregate_budget_usd: float
    consequence_ceiling: str
    expires_at: str
    kill_conditions: tuple[str, ...]
    state_namespace: str
    human_ratification_required: bool = True

    @property
    def digest(self) -> str:
        raw = json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, separators=(",", ":"))
        return "sha256:" + sha256(raw.encode()).hexdigest()

@dataclass(frozen=True)
class SimulationReport:
    manifest_hash: str
    passed: bool
    reasons: tuple[str, ...]

@dataclass(frozen=True)
class RatificationRecord:
    manifest_hash: str
    ratifier: str
    signature_ref: str
    expires_at: str

@dataclass(frozen=True)
class ActivationProposal:
    manifest_hash: str
    status: str = "PROPOSED_NOT_EXECUTED"
    gate_receipt_hash: str | None = None

@dataclass
class OmnimorphEngine:
    registry: GenomeRegistryLike
    max_budget_usd: float = 10_000.0
    active: dict[str, ActivationProposal] = field(default_factory=dict)

    def compose(
        self,
        architecture: AdvantageArchitecture,
        versions: dict[str, str],
        *,
        objective: str,
        consequence_ceiling: str,
        expires_at: str,
    ) -> OrganManifest:
        bindings: list[CapabilityBinding] = []
        total = 0.0
        for need in architecture.capability_needs:
            need.validate()
            version = versions.get(need.capability)
            if not version:
                if need.required:
                    raise FoundryError(f"no version selected for {need.capability}")
                continue
            genome = self.registry.get(need.capability, version)
            if genome is None:
                raise FoundryError(f"unregistered capability {need.capability}@{version}")
            allowed, reason = self.registry.may_instantiate(
                need.capability,
                version,
                requested_class=need.consequence_class,
                requested_budget_usd=need.budget_usd,
            )
            if not allowed:
                raise FoundryError(reason)
            total += need.budget_usd
            bindings.append(CapabilityBinding(need.capability, version, need.consequence_class, need.budget_usd))
        if total > self.max_budget_usd:
            raise FoundryError("organ aggregate budget exceeds OMNIMORPH ceiling")
        seed = f"{architecture.digest}|{objective}|{expires_at}|{len(bindings)}"
        organ_id = "organ-" + sha256(seed.encode()).hexdigest()[:16]
        return OrganManifest(
            organ_id=organ_id,
            architecture_hash=architecture.digest,
            objective=objective,
            legal_operator=architecture.legal_operator,
            bindings=tuple(bindings),
            aggregate_budget_usd=total,
            consequence_ceiling=consequence_ceiling,
            expires_at=expires_at,
            kill_conditions=architecture.kill_conditions,
            state_namespace=f"omnimorph:{organ_id}",
        )

    def simulate(self, manifest: OrganManifest) -> SimulationReport:
        reasons: list[str] = []
        if manifest.legal_operator == "UNIIMENTE":
            reasons.append("institution_cannot_be_legal_operator")
        if not manifest.bindings:
            reasons.append("no_capabilities_bound")
        if manifest.aggregate_budget_usd > self.max_budget_usd:
            reasons.append("budget_ceiling_exceeded")
        if not manifest.kill_conditions:
            reasons.append("kill_conditions_missing")
        return SimulationReport(manifest.digest, not reasons, tuple(reasons))

    def propose_activation(self, manifest: OrganManifest, simulation: SimulationReport, ratification: RatificationRecord) -> ActivationProposal:
        if not simulation.passed or simulation.manifest_hash != manifest.digest:
            raise FoundryError("manifest has not passed simulation")
        if ratification.manifest_hash != manifest.digest:
            raise FoundryError("ratification is not bound to this manifest")
        if ratification.ratifier in {"UNIIMENTE", "OMNIMORPH", "foundry"}:
            raise FoundryError("the system cannot ratify itself")
        if not ratification.signature_ref:
            raise FoundryError("founder or authorized human signature reference required")
        proposal = ActivationProposal(manifest.digest)
        self.active[manifest.organ_id] = proposal
        return proposal

    def record_gate_activation(self, manifest: OrganManifest, receipt_hash: str) -> ActivationProposal:
        current = self.active.get(manifest.organ_id)
        if current is None:
            raise FoundryError("no activation proposal exists")
        if not receipt_hash.startswith("sha256:"):
            raise FoundryError("canonical Consequence Gate receipt hash required")
        activated = ActivationProposal(manifest.digest, status="GATE_ACTIVATED", gate_receipt_hash=receipt_hash)
        self.active[manifest.organ_id] = activated
        return activated

    @staticmethod
    def validate_paid_outcome(outcome: ExternalOutcome) -> None:
        if outcome.payment_usd <= 0:
            raise FoundryError("paid economic commitment required")
        if not outcome.accepted_delivery:
            raise FoundryError("customer delivery acceptance required")
        if not outcome.externally_verified:
            raise FoundryError("external outcome verification required")
        if not outcome.reconciliation_closed:
            raise FoundryError("reconciliation must be closed")
        if outcome.contribution_margin_usd < 0:
            raise FoundryError("negative contribution margin requires reconfiguration")
        if not outcome.receipt_refs:
            raise FoundryError("external receipt references required")
