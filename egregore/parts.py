"""Detachable parts for standing cognition.

Every proposer and evaluator the runtime uses sits in a named *slot*
(``proposer:<role>`` or ``evaluator:<role>``). Implementations (a
deterministic rule set, a local open-weight model, a hosted model, a future
system) are *parts* registered against a slot. A part can be:

- registered   -- described and held in memory; this grants nothing;
- shadowed     -- run on the same inputs as the active part after each tick,
                  with its output compared and recorded but never selected;
- bound        -- made the active part for its slot;
- detached     -- removed from an optional slot;
- rolled back  -- the slot re-bound to the part it held before.

Shadow, bind, detach and rollback change what standing cognition does, so
each passes the canonical Consequence Gate with a pre-existing single-action
grant, exactly like ``StandingCognitionRuntime.resume``. The objective a grant
is issued for binds the slot, the part, the mode and the slot's current state,
so a grant cannot be replayed after the slot has moved. No part can register,
shadow, bind or promote itself; ``PartsBoard`` has no path that does so
without a grant.

Required slots (Guardian and Treasury by default) can be replaced but never
left empty. Code is not stored in the ledger: after a restart the process
must register the same parts again, and a binding whose part is not
registered is reported as unresolved instead of being guessed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from .contracts import (
    Assessment,
    CandidateProposal,
    ContractError,
    SignalEnvelope,
    canonical_copy,
    digest,
    require_text,
)
from .resources import ResourceExhausted, ResourceGovernor
from .runtime import CognitionCycle, StandingCognitionRuntime

SLOT_PATTERN = re.compile(r"^(proposer|evaluator):[a-z0-9][a-z0-9_.-]*$")
ACTIVE = "active"
SHADOW = "shadow"
_MODES = (ACTIVE, SHADOW)


def _slot(value: str) -> str:
    value = require_text("slot", value)
    if not SLOT_PATTERN.match(value):
        raise ContractError("slot must look like 'proposer:<role>' or 'evaluator:<role>'")
    return value


@dataclass(frozen=True)
class PartSpec:
    """Declared identity of one implementation of one slot."""

    slot: str
    implementation: str
    version: str
    provenance: str
    open_weights: bool | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "slot", _slot(self.slot))
        for name in ("implementation", "version", "provenance"):
            object.__setattr__(self, name, require_text(name, getattr(self, name)))
        if self.open_weights is not None and not isinstance(self.open_weights, bool):
            raise ContractError("open_weights must be true, false or null")
        if not isinstance(self.notes, str):
            raise ContractError("notes must be text")

    @property
    def kind(self) -> str:
        return self.slot.split(":", 1)[0]

    @property
    def role(self) -> str:
        return self.slot.split(":", 1)[1]

    @property
    def part_id(self) -> str:
        return digest({"kind": "egregore-part", **self.to_dict(include_id=False)})

    def to_dict(self, *, include_id: bool = True) -> dict[str, Any]:
        body = {
            "slot": self.slot,
            "implementation": self.implementation,
            "version": self.version,
            "provenance": self.provenance,
            "open_weights": self.open_weights,
            "notes": self.notes,
        }
        if include_id:
            body["part_id"] = self.part_id
        return body

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PartSpec":
        spec = cls(
            slot=value["slot"],
            implementation=value["implementation"],
            version=value["version"],
            provenance=value["provenance"],
            open_weights=value.get("open_weights"),
            notes=value.get("notes", ""),
        )
        if "part_id" in value and value["part_id"] != spec.part_id:
            raise ContractError("persisted part_id does not match its spec")
        return spec


class PartsBoard:
    """Governed slot bindings for one standing-cognition runtime."""

    REGISTER_RECORD = "egregore.part_registered"
    BINDING_RECORD = "egregore.part_binding"
    SHADOW_RESULT_RECORD = "egregore.shadow_result"
    ACTION_CLASS = "cognition.rebind"

    def __init__(
        self,
        *,
        ledger: Any,
        required_slots: Sequence[str] = ("evaluator:guardian", "evaluator:treasury"),
        source: str = "spiffe://uniimente.internal/egregore/standing-cognition",
    ):
        if not all(hasattr(ledger, name) for name in ("append", "by_type", "find")):
            raise ContractError("ledger must provide append(), by_type() and find()")
        self.ledger = ledger
        self.source = require_text("source", source)
        self.required_slots = tuple(_slot(slot) for slot in required_slots)
        if any(not slot.startswith("evaluator:") for slot in self.required_slots):
            raise ContractError("required slots are evaluator slots")
        self._specs: dict[str, PartSpec] = {}
        self._implementations: dict[str, Callable] = {}
        # slot -> {"active": part_id|None, "shadow": part_id|None}
        self._bindings: dict[str, dict[str, str | None]] = {}
        # slot -> list of previously active part_ids, oldest first
        self._history: dict[str, list[str]] = {}
        self._heads: dict[str, str] = {}
        self._hydrate()

    # -- persistence -----------------------------------------------------
    def _hydrate(self) -> None:
        for record in self.ledger.by_type(self.REGISTER_RECORD):
            if record.payload.get("source") != self.source:
                continue
            spec = PartSpec.from_dict(record.payload["part"])
            self._specs[spec.part_id] = spec
        for record in self.ledger.by_type(self.BINDING_RECORD):
            payload = record.payload
            if payload.get("source") != self.source:
                continue
            try:
                authorized = self._authorized(record, payload)
            except (KeyError, TypeError, ContractError):
                authorized = False
            if not authorized:
                continue  # retained as history, never treated as authority
            self._apply(payload["slot"], payload["mode"], payload.get("part_id"), record.hash)

    def _authorized(self, record: Any, payload: Mapping[str, Any]) -> bool:
        receipt = self.ledger.find(payload.get("authorization_hash"))
        if receipt is None or receipt.record_type != "receipt" or receipt.seq >= record.seq:
            return False
        result = receipt.payload.get("result", {})
        return (
            result.get("source") == self.source
            and result.get("objective") == payload.get("objective")
            and payload.get("objective") == self._objective(
                payload["slot"], payload["mode"], payload.get("part_id"), payload.get("prior_head")
            )
            and payload.get("prior_head") == self._heads.get(payload["slot"], "none")
        )

    def _apply(self, slot: str, mode: str, part_id: str | None, record_hash: str) -> None:
        binding = self._bindings.setdefault(slot, {ACTIVE: None, SHADOW: None})
        if mode == ACTIVE:
            previous = binding[ACTIVE]
            history = self._history.setdefault(slot, [])
            if history and history[-1] == part_id:
                history.pop()  # rollback: step back through prior parts
            elif previous and previous != part_id:
                history.append(previous)
            if binding[SHADOW] == part_id:
                binding[SHADOW] = None  # a promoted shadow stops shadowing itself
        binding[mode] = part_id
        self._heads[slot] = record_hash

    # -- registration ------------------------------------------------------
    def register(self, spec: PartSpec, implementation: Callable) -> str:
        """Describe a part and hold its code in memory. Grants nothing."""
        if not isinstance(spec, PartSpec):
            raise ContractError("register requires a PartSpec")
        if not callable(implementation):
            raise ContractError("implementation must be callable")
        part_id = spec.part_id
        if part_id not in self._specs:
            self.ledger.append(
                self.REGISTER_RECORD,
                {"source": self.source, "part": spec.to_dict(), "disposition": "registered_not_bound"},
            )
            self._specs[part_id] = spec
        self._implementations[part_id] = implementation
        return part_id

    def spec(self, part_id: str) -> PartSpec | None:
        return self._specs.get(part_id)

    # -- authority path ----------------------------------------------------
    def _objective(self, slot: str, mode: str, part_id: str | None, prior_head: str | None) -> str:
        return digest({
            "kind": "egregore-rebind",
            "source": self.source,
            "slot": slot,
            "mode": mode,
            "part_id": part_id,
            "prior_head": prior_head or "none",
        })

    def _check_change(self, slot: str, mode: str, part_id: str | None) -> None:
        slot = _slot(slot)
        if mode not in _MODES:
            raise ContractError("mode must be 'active' or 'shadow'")
        if part_id is None:
            if mode == ACTIVE and slot in self.required_slots:
                raise ContractError(f"{slot} is required; replace it instead of detaching it")
            return
        spec = self._specs.get(part_id)
        if spec is None or part_id not in self._implementations:
            raise ContractError("part is not registered in this process")
        if spec.slot != slot:
            raise ContractError(f"part is registered for {spec.slot}, not {slot}")

    def change_proposal(self, *, actor: str, slot: str, part_id: str | None, mode: str = ACTIVE):
        """The exact Gate proposal a human-held grant must be issued for."""
        from policy.engine import Proposal

        self._check_change(slot, mode, part_id)
        prior_head = self._heads.get(slot, "none")
        objective = self._objective(slot, mode, part_id, prior_head)
        return Proposal(
            actor=require_text("actor", actor),
            legal_principal="alfonso_lopez",
            action_class=self.ACTION_CLASS,
            objective=objective,
            payload={"slot": slot, "mode": mode, "part_id": part_id, "prior_head": prior_head,
                     "source": self.source},
            target=self.source,
            consequence_class="internal_write",
            evidence_confidence=1.0,
            evidence_refs=[prior_head] if prior_head != "none" else [objective],
            estimated_cost_usd=0.0,
            requested_capability=self.ACTION_CLASS,
            expected_outcome=f"{mode} binding of {slot} set to {part_id or 'nothing'}",
            proposal_id="rebind:" + objective,
        )

    def change(self, *, actor: str, slot: str, part_id: str | None, mode: str = ACTIVE,
               gate: Any = None, grant: Mapping[str, Any] | None = None) -> str:
        """Apply one binding change through the canonical Gate."""
        from policy.consequence_gate import ConsequenceGate

        if not isinstance(gate, ConsequenceGate) or gate.ledger is not self.ledger or grant is None:
            raise ContractError("canonical Gate and pre-existing rebind grant required")
        proposal = self.change_proposal(actor=actor, slot=slot, part_id=part_id, mode=mode)
        action = gate.run(proposal, standing_grant=dict(grant), executor=lambda _: {
            "observed_outcome": proposal.expected_outcome,
            "result_class": "positive",
            "objective": proposal.objective,
            "source": self.source,
        })
        if action.state != "recorded":
            raise ContractError("rebind refused: " + "; ".join(action.refusal_reasons))
        record = self.ledger.append(self.BINDING_RECORD, {
            "source": self.source,
            "actor": proposal.actor,
            "slot": slot,
            "mode": mode,
            "part_id": part_id,
            "prior_head": proposal.payload["prior_head"],
            "objective": proposal.objective,
            "authorization_hash": action.receipt_hash,
            "authentication": "Kernel workload grant; not founder authentication",
        })
        self._apply(slot, mode, part_id, record.hash)
        return record.hash

    def rollback_target(self, slot: str) -> str | None:
        """The part a rollback of ``slot`` would re-bind, if any."""
        history = self._history.get(_slot(slot), [])
        return history[-1] if history else None

    # -- views ---------------------------------------------------------------
    def bindings(self) -> dict[str, dict[str, str | None]]:
        return {slot: dict(binding) for slot, binding in sorted(self._bindings.items())}

    def unresolved(self) -> list[str]:
        """Bound slots whose part code was not registered in this process."""
        gaps = []
        for slot, binding in sorted(self._bindings.items()):
            for mode in _MODES:
                part_id = binding[mode]
                if part_id and part_id not in self._implementations:
                    gaps.append(f"{slot}:{mode}")
        return gaps

    def missing_required(self) -> list[str]:
        return [slot for slot in self.required_slots
                if not self._bindings.get(slot, {}).get(ACTIVE)]

    def _active(self, kind: str) -> dict[str, Callable]:
        organs = {}
        for slot, binding in self._bindings.items():
            part_id = binding[ACTIVE]
            if part_id and slot.startswith(kind + ":") and part_id in self._implementations:
                organs[slot.split(":", 1)[1]] = self._implementations[part_id]
        return organs

    def runtime(self, **kwargs: Any) -> StandingCognitionRuntime:
        """Build the runtime from the current active parts.

        The runtime is restartable from the ledger, so a swap is a rebuild
        with different parts; recorded cycles, signals and suspension survive.
        """
        gaps = [gap for gap in self.unresolved() if gap.endswith(":" + ACTIVE)]
        if gaps:
            raise ContractError("active parts not registered in this process: " + ", ".join(gaps))
        missing = self.missing_required()
        if missing:
            raise ContractError("required slots have no active part: " + ", ".join(missing))
        return StandingCognitionRuntime(
            ledger=self.ledger,
            proposers=self._active("proposer"),
            evaluators=self._active("evaluator"),
            required_evaluators=tuple(slot.split(":", 1)[1] for slot in self.required_slots),
            source=self.source,
            **kwargs,
        )

    # -- shadow trials -------------------------------------------------------
    def shadow_run(
        self,
        cycle: CognitionCycle,
        signals: Sequence[SignalEnvelope],
        context: Mapping[str, Any] | None = None,
        *,
        resources: ResourceGovernor,
        call_costs: Mapping[str, float] | None = None,
    ) -> list[str]:
        """Run shadow parts on a finished cycle's inputs and record the comparison.

        Shadow output never enters the cycle and never influences selection.
        The comparison records are the evidence a human uses to decide whether
        to promote a shadow part.
        """
        if not isinstance(cycle, CognitionCycle):
            raise ContractError("shadow_run requires a recorded CognitionCycle")
        if not isinstance(resources, ResourceGovernor):
            raise ContractError("shadow_run requires its own ResourceGovernor")
        by_id = {signal.signal_id: signal for signal in signals}
        if set(cycle.signal_ids) - set(by_id):
            raise ContractError("shadow_run needs every signal the cycle used")
        cycle_signals = tuple(SignalEnvelope.from_dict(by_id[sid].to_dict()) for sid in cycle.signal_ids)
        clean_context = canonical_copy(dict(context or {}))
        costs = dict(call_costs or {})
        hashes = []
        for slot, binding in sorted(self._bindings.items()):
            part_id = binding[SHADOW]
            if not part_id or part_id not in self._implementations:
                continue
            component = f"shadow:{slot}"
            try:
                resources.consume_call(component=component,
                                       estimated_cost_usd=float(costs.get(component, 0.0)))
                if slot.startswith("proposer:"):
                    comparison = self._compare_proposer(slot, part_id, cycle, cycle_signals, clean_context)
                else:
                    comparison = self._compare_evaluator(slot, part_id, cycle, cycle_signals, clean_context)
                error = None
            except ResourceExhausted as exc:
                comparison, error = {}, {"error_type": type(exc).__name__, "error": str(exc),
                                         "disposition": "budget_refusal"}
            except Exception as exc:  # a failing trial is evidence, not an outage
                comparison, error = {}, {"error_type": type(exc).__name__, "error": str(exc),
                                         "disposition": "isolated_and_retained"}
            record = self.ledger.append(self.SHADOW_RESULT_RECORD, {
                "source": self.source,
                "cycle_id": cycle.cycle_id,
                "slot": slot,
                "shadow_part_id": part_id,
                "active_part_id": binding[ACTIVE],
                "comparison": comparison,
                "failure": error,
                "disposition": "no_influence",
            })
            hashes.append(record.hash)
            if error and error["disposition"] == "budget_refusal":
                break
        return hashes

    def _compare_proposer(self, slot, part_id, cycle, signals, context) -> dict[str, Any]:
        role = slot.split(":", 1)[1]
        produced = StandingCognitionRuntime._normalize_candidates(
            self._implementations[part_id](signals, canonical_copy(context))
        )
        shadow = []
        for candidate in produced:
            candidate = CandidateProposal.from_dict(candidate.to_dict())
            if candidate.proposed_by != role:
                raise ContractError("shadow candidate proposed_by does not match its slot")
            if not set(candidate.source_signal_ids).issubset(cycle.signal_ids):
                raise ContractError("shadow candidate cites a signal outside the cycle")
            shadow.append(candidate)
        active_ids = sorted(c.candidate_id for c in cycle.candidates if c.proposed_by == role)
        shadow_ids = sorted({c.candidate_id for c in shadow})
        return {
            "active_candidate_ids": active_ids,
            "shadow_candidates": [c.to_dict() for c in sorted(shadow, key=lambda c: c.candidate_id)],
            "identical": active_ids == shadow_ids,
        }

    def _compare_evaluator(self, slot, part_id, cycle, signals, context) -> dict[str, Any]:
        role = slot.split(":", 1)[1]
        rows = []
        for candidate in cycle.candidates:
            shadow = self._implementations[part_id](
                CandidateProposal.from_dict(candidate.to_dict()), signals, canonical_copy(context)
            )
            if not isinstance(shadow, Assessment) or shadow.role != role \
                    or shadow.candidate_id != candidate.candidate_id:
                raise ContractError("shadow evaluator returned a mismatched Assessment")
            active = next((a for a in cycle.assessments
                           if a.role == role and a.candidate_id == candidate.candidate_id), None)
            rows.append({
                "candidate_id": candidate.candidate_id,
                "active": active.to_dict() if active else None,
                "shadow": shadow.to_dict(),
                "veto_agrees": active is not None and active.veto == shadow.veto,
                "score_delta": None if active is None else round(shadow.score - active.score, 6),
            })
        return {"assessments": rows}
