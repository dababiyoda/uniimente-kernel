"""OMNIMORPH: compose temporary institutional organs without self-activation.

OMNIMORPH binds a passed Advantage Architecture, a non-executing Composition
Plan, and registered Capability Genomes into an Organ Manifest. It may simulate,
request human ratification, and record an exact Consequence Gate receipt. It
never calls the Gate, mints authority, moves capital, or activates itself.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Protocol

from capabilities.genome import CONSEQUENCE_CLASSES
from foundry.advantage import AdvantageArchitecture, AdvantageRefused
from foundry.composition import CompositionPlan
from foundry.tribunal import SpiderWebTribunal, TribunalReport


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
    composition_plan_id: str
    tribunal_report_hash: str
    objective: str
    legal_operator: str
    selected_technology_ids: tuple[int, ...]
    bindings: tuple[CapabilityBinding, ...]
    aggregate_budget_usd: float
    consequence_ceiling: str
    expires_at: str
    kill_conditions: tuple[str, ...]
    state_namespace: str
    human_ratification_required: bool = True
    execution_authority: bool = False

    @property
    def digest(self) -> str:
        raw = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return "sha256:" + sha256(raw.encode()).hexdigest()


@dataclass(frozen=True)
class SimulationReport:
    manifest_hash: str
    passed: bool
    reasons: tuple[str, ...]
    checks: tuple[str, ...]


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


@dataclass(frozen=True)
class GateActivationReceipt:
    receipt_hash: str
    manifest_hash: str
    action_class: str
    legal_principal: str
    state: str

    def validate(self, manifest: OrganManifest) -> None:
        _require_hash(self.receipt_hash, "receipt_hash")
        if self.manifest_hash != manifest.digest:
            raise AdvantageRefused("Gate receipt is not bound to this Organ Manifest")
        if self.action_class != "organ.activate":
            raise AdvantageRefused("Gate receipt must be for organ.activate")
        if self.legal_principal != manifest.legal_operator:
            raise AdvantageRefused("Gate receipt legal principal does not match the manifest")
        if self.state != "recorded":
            raise AdvantageRefused("only a recorded Gate action may activate an organ")


@dataclass(frozen=True)
class RetirementRecord:
    organ_id: str
    manifest_hash: str
    actor: str
    reason: str
    human_approval_ref: str
    reconciliation_ref: str
    status: str = "RETIRED"


@dataclass
class OmnimorphEngine:
    registry: GenomeRegistryLike
    tribunal: SpiderWebTribunal
    max_budget_usd: float = 10_000.0
    ledger: Any | None = None
    manifests: dict[str, OrganManifest] = field(default_factory=dict)
    simulations: dict[str, SimulationReport] = field(default_factory=dict)
    activation_state: dict[str, ActivationProposal] = field(default_factory=dict)
    retirements: dict[str, RetirementRecord] = field(default_factory=dict)

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
        for key in ("selected_technology_ids", "kill_conditions"):
            raw[key] = tuple(raw.get(key) or ())
        return OrganManifest(**raw)

    def rebuild_from_ledger(self) -> None:
        self.manifests.clear()
        self.simulations.clear()
        self.activation_state.clear()
        self.retirements.clear()
        for record in self.ledger.by_type("event"):
            payload = record.payload
            event_type = payload.get("type")
            organ_id = payload.get("organ_id")
            if not organ_id:
                continue
            if event_type == "omnimorph.manifest_composed" and isinstance(payload.get("manifest"), dict):
                manifest = self._manifest_from_data(payload["manifest"])
                if manifest.digest != payload["manifest_hash"]:
                    raise AdvantageRefused("ledgered Organ Manifest digest mismatch")
                self.manifests[organ_id] = manifest
            elif event_type == "omnimorph.simulation_completed":
                self.simulations[organ_id] = SimulationReport(
                    manifest_hash=payload["manifest_hash"],
                    passed=bool(payload["passed"]),
                    reasons=tuple(payload.get("reasons") or ()),
                    checks=tuple(payload.get("checks") or ()),
                )
            elif event_type == "omnimorph.activation_proposed":
                self.activation_state[organ_id] = ActivationProposal(payload["manifest_hash"])
            elif event_type == "omnimorph.gate_activation_recorded":
                self.activation_state[organ_id] = ActivationProposal(
                    payload["manifest_hash"],
                    status="GATE_ACTIVATED",
                    gate_receipt_hash=payload["gate_receipt_hash"],
                )
            elif event_type == "omnimorph.organ_retired":
                raw = {key: value for key, value in payload.items() if key != "type"}
                self.retirements[organ_id] = RetirementRecord(**raw)
                self.activation_state.pop(organ_id, None)

    def compose(
        self,
        architecture: AdvantageArchitecture,
        plan: CompositionPlan,
        tribunal_report: TribunalReport,
        versions: dict[str, str],
        *,
        objective: str,
        consequence_ceiling: str,
        expires_at: str,
    ) -> OrganManifest:
        if not objective or not expires_at:
            raise AdvantageRefused("objective and expiration are required")
        if architecture.legal_operator == "UNIIMENTE":
            raise AdvantageRefused("UNIIMENTE is never the legal operator")
        if not plan.verify_id():
            raise AdvantageRefused("Composition Plan identity is invalid")
        if architecture.control_surfaces and not set(architecture.control_surfaces).issubset(
            set(plan.control_surfaces)
        ):
            raise AdvantageRefused("Composition Plan does not cover the architecture control surfaces")
        if plan.legal_principal != architecture.legal_operator:
            raise AdvantageRefused("Composition Plan legal principal differs from the architecture")
        self.tribunal.require_passed(architecture, tribunal_report)
        if consequence_ceiling not in CONSEQUENCE_CLASSES:
            raise AdvantageRefused("unknown consequence ceiling")
        _parse_future(expires_at, "manifest expiration")

        bindings: list[CapabilityBinding] = []
        total = 0.0
        for need in architecture.capability_needs:
            need.validate()
            if CONSEQUENCE_CLASSES.index(need.consequence_class) > CONSEQUENCE_CLASSES.index(
                consequence_ceiling
            ):
                raise AdvantageRefused(
                    f"capability {need.capability} exceeds the Organ Manifest consequence ceiling"
                )
            version = versions.get(need.capability)
            if not version:
                if need.required:
                    raise AdvantageRefused(f"no version selected for {need.capability}")
                continue
            genome = self.registry.get(need.capability, version)
            if genome is None:
                raise AdvantageRefused(f"unregistered capability {need.capability}@{version}")
            allowed, reason = self.registry.may_instantiate(
                need.capability,
                version,
                requested_class=need.consequence_class,
                requested_budget_usd=need.budget_usd,
            )
            if not allowed:
                raise AdvantageRefused(reason)
            total += need.budget_usd
            bindings.append(CapabilityBinding(
                need.capability, version, need.consequence_class, need.budget_usd
            ))

        effective_ceiling = min(self.max_budget_usd, plan.budget_ceiling_usd)
        if total > effective_ceiling:
            raise AdvantageRefused(
                f"organ aggregate budget ${total} exceeds effective ceiling ${effective_ceiling}"
            )
        seed = (
            f"{architecture.digest}|{plan.plan_id}|{tribunal_report.digest}|"
            f"{objective}|{expires_at}|{len(bindings)}"
        )
        organ_id = "organ-" + sha256(seed.encode()).hexdigest()[:16]
        manifest = OrganManifest(
            organ_id=organ_id,
            architecture_hash=architecture.digest,
            composition_plan_id=plan.plan_id,
            tribunal_report_hash=tribunal_report.digest,
            objective=objective,
            legal_operator=architecture.legal_operator,
            selected_technology_ids=plan.selected_technology_ids,
            bindings=tuple(bindings),
            aggregate_budget_usd=total,
            consequence_ceiling=consequence_ceiling,
            expires_at=expires_at,
            kill_conditions=architecture.kill_conditions,
            state_namespace=f"omnimorph:{organ_id}",
        )
        existing = self.manifests.get(organ_id)
        if existing is not None and existing.digest != manifest.digest:
            raise AdvantageRefused("organ id collision with different manifest")
        self.manifests[organ_id] = manifest
        self._record("omnimorph.manifest_composed", {
            "organ_id": manifest.organ_id,
            "manifest_hash": manifest.digest,
            "architecture_hash": manifest.architecture_hash,
            "composition_plan_id": manifest.composition_plan_id,
            "tribunal_report_hash": manifest.tribunal_report_hash,
            "capabilities": [f"{binding.capability}@{binding.version}" for binding in manifest.bindings],
            "selected_technology_ids": list(manifest.selected_technology_ids),
            "aggregate_budget_usd": manifest.aggregate_budget_usd,
            "manifest": asdict(manifest),
        })
        return manifest

    def simulate(self, manifest: OrganManifest, plan: CompositionPlan) -> SimulationReport:
        stored = self.manifests.get(manifest.organ_id)
        if stored is None or stored.digest != manifest.digest:
            raise AdvantageRefused("simulation requires the registered Organ Manifest")
        reasons: list[str] = []
        checks: list[str] = []
        if manifest.legal_operator == "UNIIMENTE":
            reasons.append("institution_cannot_be_legal_operator")
        else:
            checks.append("legal_operator_bound")
        if not manifest.bindings:
            reasons.append("no_capabilities_bound")
        else:
            checks.append("capabilities_bound")
        if manifest.aggregate_budget_usd > min(self.max_budget_usd, plan.budget_ceiling_usd):
            reasons.append("budget_ceiling_exceeded")
        else:
            checks.append("budget_within_ceiling")
        if not manifest.kill_conditions:
            reasons.append("kill_conditions_missing")
        else:
            checks.append("kill_conditions_present")
        if not plan.implementation_ready:
            gaps = [
                f"technology_{technology_id}_{status}"
                for technology_id, status in plan.implementation_status.items()
                if status != "executable"
            ]
            reasons.extend(gaps)
        else:
            checks.append("all_selected_technologies_executable")
        report = SimulationReport(manifest.digest, not reasons, tuple(reasons), tuple(checks))
        self.simulations[manifest.organ_id] = report
        self._record("omnimorph.simulation_completed", {
            "organ_id": manifest.organ_id,
            "manifest_hash": manifest.digest,
            "passed": report.passed,
            "reasons": list(report.reasons),
            "checks": list(report.checks),
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
            raise AdvantageRefused("manifest must be registered before activation proposal")
        stored_simulation = self.simulations.get(manifest.organ_id)
        if stored_simulation != simulation:
            raise AdvantageRefused("simulation must be the recorded report for this organ")
        if not simulation.passed or simulation.manifest_hash != manifest.digest:
            raise AdvantageRefused("manifest has not passed simulation")
        if ratification.manifest_hash != manifest.digest:
            raise AdvantageRefused("ratification is not bound to this manifest")
        if ratification.ratifier in {"UNIIMENTE", "OMNIMORPH", "foundry"}:
            raise AdvantageRefused("the system cannot ratify itself")
        _require_hash(ratification.signature_ref, "ratification signature_ref")
        _parse_future(ratification.expires_at, "ratification expiration")
        proposal = ActivationProposal(manifest.digest)
        self.activation_state[manifest.organ_id] = proposal
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
        receipt: GateActivationReceipt,
    ) -> ActivationProposal:
        stored = self.manifests.get(manifest.organ_id)
        if stored is None or stored.digest != manifest.digest:
            raise AdvantageRefused("unknown or changed Organ Manifest")
        current = self.activation_state.get(manifest.organ_id)
        if current is None or current.status != "PROPOSED_NOT_EXECUTED":
            raise AdvantageRefused("a pending activation proposal is required")
        receipt.validate(manifest)
        activated = ActivationProposal(
            manifest.digest,
            status="GATE_ACTIVATED",
            gate_receipt_hash=receipt.receipt_hash,
        )
        self.activation_state[manifest.organ_id] = activated
        self._record("omnimorph.gate_activation_recorded", {
            "organ_id": manifest.organ_id,
            "manifest_hash": manifest.digest,
            "gate_receipt_hash": receipt.receipt_hash,
            "action_class": receipt.action_class,
            "legal_principal": receipt.legal_principal,
            "status": activated.status,
        })
        return activated

    def retire(
        self,
        organ_id: str,
        *,
        actor: str,
        reason: str,
        human_approval_ref: str,
        reconciliation_ref: str,
    ) -> RetirementRecord:
        manifest = self.manifests.get(organ_id)
        if manifest is None:
            raise AdvantageRefused("unknown organ")
        if not actor or actor in {"UNIIMENTE", "OMNIMORPH", "foundry"}:
            raise AdvantageRefused("an accountable human or lawful operator must retire the organ")
        if not reason:
            raise AdvantageRefused("retirement reason is required")
        _require_hash(human_approval_ref, "human_approval_ref")
        _require_hash(reconciliation_ref, "reconciliation_ref")
        record = RetirementRecord(
            organ_id=organ_id,
            manifest_hash=manifest.digest,
            actor=actor,
            reason=reason,
            human_approval_ref=human_approval_ref,
            reconciliation_ref=reconciliation_ref,
        )
        self.retirements[organ_id] = record
        self.activation_state.pop(organ_id, None)
        self._record("omnimorph.organ_retired", asdict(record))
        return record

    def get_manifest(self, organ_id: str) -> OrganManifest | None:
        return self.manifests.get(organ_id)

    def get_simulation(self, organ_id: str) -> SimulationReport | None:
        return self.simulations.get(organ_id)


def _require_hash(value: Any, field_name: str) -> str:
    value = str(value or "")
    if not value.startswith("sha256:") or len(value) != 71:
        raise AdvantageRefused(f"canonical sha256 {field_name} required")
    return value


def _parse_future(value: str, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AdvantageRefused(f"{field_name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise AdvantageRefused(f"{field_name} must include a timezone")
    if parsed <= datetime.now(timezone.utc):
        raise AdvantageRefused(f"{field_name} must be in the future")
    return parsed
