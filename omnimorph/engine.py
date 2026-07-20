from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any, Protocol

from foundry.contracts import AdvantageArchitecture, ExternalOutcome, FoundryError


class GenomeRegistryLike(Protocol):
    def get(self, name: str, version: str) -> Any: ...
    def may_instantiate(
        self,
        name: str,
        version: str,
        *,
        requested_class: str,
        requested_budget_usd: float,
    ) -> tuple[bool, str]: ...


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
        raw = json.dumps(
            self,
            default=lambda value: value.__dict__,
            sort_keys=True,
            separators=(",", ":"),
        )
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
    ledger: Any | None = None
    manifests: dict[str, OrganManifest] = field(default_factory=dict)
    simulations: dict[str, SimulationReport] = field(default_factory=dict)
    active: dict[str, ActivationProposal] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.ledger is not None:
            self.rebuild_from_ledger()

    def _record(self, event_type: str, payload: dict) -> None:
        if self.ledger is not None:
            self.ledger.append("event", {"type": event_type, **payload})

    @staticmethod
    def _manifest_from_data(data: dict[str, Any]) -> OrganManifest:
        raw = dict(data)
        raw["bindings"] = tuple(
            CapabilityBinding(**dict(binding)) for binding in raw.get("bindings") or ()
        )
        raw["kill_conditions"] = tuple(raw.get("kill_conditions") or ())
        return OrganManifest(**raw)

    def rebuild_from_ledger(self) -> None:
        """Reconstruct manifests, simulations, and activation state.

        Hash-only legacy events still restore activation status. New manifest
        events restore the complete body plan so the organ can be inspected,
        simulated, ratified, or retired after process loss.
        """
        self.manifests.clear()
        self.simulations.clear()
        self.active.clear()
        for record in self.ledger.by_type("event"):
            payload = record.payload
            event_type = payload.get("type")
            organ_id = payload.get("organ_id")
            if not organ_id:
                continue
            if event_type == "omnimorph.manifest_composed":
                if isinstance(payload.get("manifest"), dict):
                    manifest = self._manifest_from_data(payload["manifest"])
                    if manifest.digest != payload["manifest_hash"]:
                        raise FoundryError("ledgered manifest digest mismatch")
                    self.manifests[organ_id] = manifest
            elif event_type == "omnimorph.simulation_completed":
                report = SimulationReport(
                    manifest_hash=payload["manifest_hash"],
                    passed=bool(payload["passed"]),
                    reasons=tuple(payload.get("reasons") or ()),
                )
                self.simulations[organ_id] = report
            elif event_type == "omnimorph.activation_proposed":
                self.active[organ_id] = ActivationProposal(payload["manifest_hash"])
            elif event_type == "omnimorph.gate_activation_recorded":
                self.active[organ_id] = ActivationProposal(
                    payload["manifest_hash"],
                    status="GATE_ACTIVATED",
                    gate_receipt_hash=payload["gate_receipt_hash"],
                )

    def compose(
        self,
        architecture: AdvantageArchitecture,
        versions: dict[str, str],
        *,
        objective: str,
        consequence_ceiling: str,
        expires_at: str,
    ) -> OrganManifest:
        if not objective or not expires_at:
            raise FoundryError("objective and expiration are required")
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
            bindings.append(
                CapabilityBinding(
                    need.capability,
                    version,
                    need.consequence_class,
                    need.budget_usd,
                )
            )
        if total > self.max_budget_usd:
            raise FoundryError("organ aggregate budget exceeds OMNIMORPH ceiling")
        seed = f"{architecture.digest}|{objective}|{expires_at}|{len(bindings)}"
        organ_id = "organ-" + sha256(seed.encode()).hexdigest()[:16]
        manifest = OrganManifest(
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
        existing = self.manifests.get(organ_id)
        if existing is not None and existing.digest != manifest.digest:
            raise FoundryError("organ id collision with different manifest")
        self.manifests[organ_id] = manifest
        self._record("omnimorph.manifest_composed", {
            "organ_id": manifest.organ_id,
            "manifest_hash": manifest.digest,
            "architecture_hash": manifest.architecture_hash,
            "capabilities": [
                f"{binding.capability}@{binding.version}"
                for binding in manifest.bindings
            ],
            "aggregate_budget_usd": manifest.aggregate_budget_usd,
            "manifest": asdict(manifest),
        })
        return manifest

    def simulate(self, manifest: OrganManifest) -> SimulationReport:
        stored = self.manifests.get(manifest.organ_id)
        if stored is not None and stored.digest != manifest.digest:
            raise FoundryError("simulation manifest differs from registered organ")
        reasons: list[str] = []
        if manifest.legal_operator == "UNIIMENTE":
            reasons.append("institution_cannot_be_legal_operator")
        if not manifest.bindings:
            reasons.append("no_capabilities_bound")
        if manifest.aggregate_budget_usd > self.max_budget_usd:
            reasons.append("budget_ceiling_exceeded")
        if not manifest.kill_conditions:
            reasons.append("kill_conditions_missing")
        report = SimulationReport(manifest.digest, not reasons, tuple(reasons))
        self.simulations[manifest.organ_id] = report
        self._record("omnimorph.simulation_completed", {
            "organ_id": manifest.organ_id,
            "manifest_hash": manifest.digest,
            "passed": report.passed,
            "reasons": list(report.reasons),
        })
        return report

    def propose_activation(
        self,
        manifest: OrganManifest,
        simulation: SimulationReport,
        ratification: RatificationRecord,
    ) -> ActivationProposal:
        stored_manifest = self.manifests.get(manifest.organ_id)
        if stored_manifest is None or stored_manifest.digest != manifest.digest:
            raise FoundryError("manifest must be registered before activation proposal")
        stored_simulation = self.simulations.get(manifest.organ_id)
        if stored_simulation != simulation:
            raise FoundryError("simulation must be the recorded report for this organ")
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
        self._record("omnimorph.activation_proposed", {
            "organ_id": manifest.organ_id,
            "manifest_hash": manifest.digest,
            "ratifier": ratification.ratifier,
            "ratification_signature_ref": ratification.signature_ref,
            "ratification_expires_at": ratification.expires_at,
            "status": proposal.status,
        })
        return proposal

    def record_gate_activation(
        self,
        manifest: OrganManifest,
        receipt_hash: str,
    ) -> ActivationProposal:
        stored = self.manifests.get(manifest.organ_id)
        if stored is None or stored.digest != manifest.digest:
            raise FoundryError("unknown or changed organ manifest")
        current = self.active.get(manifest.organ_id)
        if current is None:
            raise FoundryError("no activation proposal exists")
        if not receipt_hash.startswith("sha256:") or len(receipt_hash) != 71:
            raise FoundryError("canonical Consequence Gate receipt hash required")
        activated = ActivationProposal(
            manifest.digest,
            status="GATE_ACTIVATED",
            gate_receipt_hash=receipt_hash,
        )
        self.active[manifest.organ_id] = activated
        self._record("omnimorph.gate_activation_recorded", {
            "organ_id": manifest.organ_id,
            "manifest_hash": manifest.digest,
            "gate_receipt_hash": receipt_hash,
            "status": activated.status,
        })
        return activated

    def get_manifest(self, organ_id: str) -> OrganManifest | None:
        return self.manifests.get(organ_id)

    def get_simulation(self, organ_id: str) -> SimulationReport | None:
        return self.simulations.get(organ_id)

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
