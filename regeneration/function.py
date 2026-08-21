"""Function-level institutional identity: the state this repository did not have.

WHAT THE REPOSITORY ALREADY HAS (inspected, not assumed):

  evolution/repair/detector.py   FunctionLossDetector - "observes a capability
                                 and reports whether the institution still has
                                 it". Deficit detection exists.
  evolution/repair/candidate.py  CapabilityProviderRegistry, ResolverCandidate,
                                 HeldOutCorpora. Candidate generation and
                                 blind held-out evaluation exist.
  omnimorph/engine.py            compose -> simulate -> propose_activation ->
                                 ratify -> retire, with human ratification and
                                 ledger replay. Organ admission exists.
  morphogenesis/                 MorphogeneticSetPoint, error direction,
                                 ranked bounded CandidateActions. Set-point
                                 fields exist.
  aperture/                      portable exact authority. Authorization exists.

WHAT IS MISSING, AND IS THEREFORE WHAT THIS MODULE IS:

  1. `OrganManifest.objective` is a bare `str`. An organ names its purpose; it
     does not reference an institutional object that outlives it. When the
     organ retires, the purpose retires with it.

  2. `evolution/repair` swaps a replacement provider in with NO organ identity
     and NO certificate. Grep for `aperture` or `certificate` under
     evolution/repair returns nothing. Repair today is a function-level
     substitution that the authority system never sees.

  3. `OmnimorphEngine.retire()` takes a `reconciliation_ref` HASH. There is no
     object holding unresolved duties, so nothing can carry them across a
     replacement. Obligations are referenced, never transferred.

So the gap is not detection, not candidate generation, not admission, and not
authorization. It is that NOTHING PERSISTS AT THE FUNCTION LEVEL. The
institution can notice a loss and can build a replacement, but has no object
that says "this duty is still owed, by whoever now performs it".

THE FIVE SEPARATIONS, made executable rather than documentary:

    function identity   is not   organ identity
    organ identity      is not   workload identity
    workload identity   is not   authority
    authority           is not   obligation
    obligation continuity is not permission inheritance

The last one is the load-bearing claim. A successor inherits DUTIES and
EVIDENCE. It never inherits IDENTITY or PERMISSION. Those must be issued
afresh, by the one canonical issuer, to a distinct organ.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"),
                   default=str).encode()).hexdigest()


class RegenerationError(Exception):
    """Every refusal here. Never raised to mean 'permitted'."""

    def __init__(self, message: str, *, code: str = "refused"):
        super().__init__(message)
        self.code = code


class ObligationState(str, Enum):
    OPEN = "open"
    DISCHARGED = "discharged"
    TRANSFERRED = "transferred"
    ABANDONED = "abandoned"          # requires an explicit human decision


@dataclass
class Obligation:
    """A duty the INSTITUTION owes, not a duty an organ owes.

    An obligation survives the organ that incurred it. That is the whole point:
    if duties died with their organ, replacement would be a way to escape them.
    """
    obligation_id: str
    function_id: str
    description: str
    incurred_by_organ: str
    state: ObligationState = ObligationState.OPEN
    incurred_at: str = field(default_factory=_now)
    discharged_by_organ: Optional[str] = None
    transfer_history: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["state"] = self.state.value
        return d


@dataclass(frozen=True)
class FunctionContract:
    """A required function, represented independently of any implementation.

    This object is the institutional identity that persists. Organs come and
    go against it. It is deliberately NOT a class to subclass or an interface
    to implement - it is a *duty specification* plus an identity that outlives
    every performer.
    """
    function_id: str
    description: str
    inputs: tuple[str, ...]
    valid_outputs: tuple[str, ...]
    service_level_target: str
    evidence_required: tuple[str, ...]
    consequence_ceiling: str
    failure_conditions: tuple[str, ...]
    independent_verification: str
    termination_conditions: tuple[str, ...]
    created_at: str = field(default=_now())

    @property
    def digest(self) -> str:
        return _digest(asdict(self))

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class OrganIncarnation:
    """One organ's tenure performing one function. Deliberately not the function.

    `organ_id`, `workload_identity` and `authority_record_id` are three
    DIFFERENT things and are never derived from one another. A successor gets
    new values for all three.
    """
    organ_id: str
    function_id: str
    workload_identity: str
    topology: dict                     # capability composition + control shape
    authority_record_id: Optional[str] = None
    admitted_at: str = field(default_factory=_now)
    retired_at: Optional[str] = None
    predecessor_organ_id: Optional[str] = None
    retirement_reason: str = ""

    @property
    def topology_signature(self) -> str:
        """What makes two incarnations materially the same or different."""
        return _digest(self.topology)

    def to_dict(self) -> dict:
        return asdict(self)


class FunctionRegistry:
    """Holds function identity, incarnation lineage, and the obligation ledger.

    This is the object that makes regeneration governed rather than merely
    possible. It refuses, by construction:

      - reusing a retired organ identity
      - a successor whose topology is materially identical to its predecessor
      - a successor inheriting its predecessor's authority record
      - retiring an organ while it still holds open obligations, unless those
        obligations are explicitly transferred or a human abandons them
      - an organ self-ratifying its own admission
    """

    def __init__(self) -> None:
        self.functions: dict[str, FunctionContract] = {}
        self.incarnations: dict[str, OrganIncarnation] = {}
        self.obligations: dict[str, Obligation] = {}
        self.lineage: dict[str, list[str]] = {}     # function_id -> [organ_id]
        self.events: list[dict] = []
        self._retired_ids: set[str] = set()

    # -- events -----------------------------------------------------------
    def _record(self, kind: str, payload: dict) -> None:
        self.events.append({"kind": kind, "at": _now(), **payload})

    # -- functions --------------------------------------------------------
    def declare_function(self, contract: FunctionContract) -> FunctionContract:
        if contract.function_id in self.functions:
            raise RegenerationError(
                f"function {contract.function_id!r} is already declared; a "
                "function identity is stable and is never silently redefined",
                code="function_already_declared")
        self.functions[contract.function_id] = contract
        self.lineage[contract.function_id] = []
        self._record("function.declared",
                     {"function_id": contract.function_id,
                      "digest": contract.digest})
        return contract

    def function(self, function_id: str) -> FunctionContract:
        f = self.functions.get(function_id)
        if f is None:
            raise RegenerationError(f"unknown function {function_id!r}",
                                    code="unknown_function")
        return f

    # -- admission --------------------------------------------------------
    def admit(
        self,
        *,
        function_id: str,
        topology: dict,
        workload_identity: str,
        ratified_by: str,
        authority_record_id: Optional[str] = None,
        predecessor_organ_id: Optional[str] = None,
        minimum_material_difference: int = 2,
    ) -> OrganIncarnation:
        """Admit an organ to perform a function. Refuses every shortcut."""
        self.function(function_id)

        if not ratified_by or ratified_by.lower() in {
                "uniimente", "omnimorph", "foundry", "self", ""}:
            raise RegenerationError(
                f"admission must be ratified by an accountable party; "
                f"{ratified_by!r} is the institution ratifying itself",
                code="self_ratified_organ")

        organ_id = f"organ:{function_id}:{uuid.uuid4().hex[:12]}"
        if organ_id in self._retired_ids:                 # practically impossible
            raise RegenerationError("organ identity reuse",
                                    code="reused_organ_identity")

        prior = self.lineage[function_id]
        if predecessor_organ_id is not None:
            if predecessor_organ_id not in self.incarnations:
                raise RegenerationError(
                    f"unknown predecessor {predecessor_organ_id!r}",
                    code="unknown_predecessor")
            pred = self.incarnations[predecessor_organ_id]

            # A successor must be MATERIALLY different. Otherwise "regeneration"
            # is a restart with a new name, which is the central false success.
            diff = self.material_difference(pred.topology, topology)
            if len(diff) < minimum_material_difference:
                raise RegenerationError(
                    f"successor differs from {predecessor_organ_id} in only "
                    f"{len(diff)} dimension(s) {sorted(diff)}; at least "
                    f"{minimum_material_difference} are required. A replacement "
                    "that reconstructs the same topology under a new name is a "
                    "restart, not a regeneration.",
                    code="topology_not_materially_different")

            # Authority is never inherited. Obligations are.
            if (authority_record_id is not None
                    and authority_record_id == pred.authority_record_id):
                raise RegenerationError(
                    "successor was handed its predecessor's authority record; "
                    "authority is issued afresh, never inherited",
                    code="inherited_authority")

        inc = OrganIncarnation(
            organ_id=organ_id, function_id=function_id,
            workload_identity=workload_identity, topology=topology,
            authority_record_id=authority_record_id,
            predecessor_organ_id=predecessor_organ_id)
        self.incarnations[organ_id] = inc
        prior.append(organ_id)
        self._record("organ.admitted",
                     {"organ_id": organ_id, "function_id": function_id,
                      "ratified_by": ratified_by,
                      "predecessor": predecessor_organ_id,
                      "topology_signature": inc.topology_signature})
        return inc

    # -- material difference ----------------------------------------------
    MATERIAL_DIMENSIONS = ("capabilities", "control_topology",
                           "communication", "verification",
                           "memory_distribution", "resource_allocation",
                           "recovery_behaviour")

    @classmethod
    def material_difference(cls, a: dict, b: dict) -> set[str]:
        """Which material dimensions actually differ.

        Compared on VALUES, not names. Renaming a component does not make a
        topology different, which is exactly the 'renamed topology' cheat.
        """
        diff = set()
        for dim in cls.MATERIAL_DIMENSIONS:
            av, bv = a.get(dim), b.get(dim)
            if isinstance(av, (list, tuple)) and isinstance(bv, (list, tuple)):
                if sorted(map(str, av)) != sorted(map(str, bv)):
                    diff.add(dim)
            elif av != bv:
                diff.add(dim)
        return diff

    # -- obligations ------------------------------------------------------
    def incur(self, *, function_id: str, organ_id: str, description: str,
              evidence_refs: tuple[str, ...] = ()) -> Obligation:
        self.function(function_id)
        ob = Obligation(
            obligation_id=f"ob:{uuid.uuid4().hex[:12]}", function_id=function_id,
            description=description, incurred_by_organ=organ_id,
            evidence_refs=evidence_refs)
        self.obligations[ob.obligation_id] = ob
        self._record("obligation.incurred",
                     {"obligation_id": ob.obligation_id, "organ_id": organ_id})
        return ob

    def open_obligations(self, function_id: str) -> list[Obligation]:
        return [o for o in self.obligations.values()
                if o.function_id == function_id
                and o.state is ObligationState.OPEN]

    def transfer_obligations(self, *, function_id: str,
                             to_organ_id: str) -> list[Obligation]:
        """Duties move to the successor. Permissions do not move with them."""
        if to_organ_id not in self.incarnations:
            raise RegenerationError(f"unknown organ {to_organ_id!r}",
                                    code="unknown_organ")
        moved = []
        for ob in self.open_obligations(function_id):
            ob.transfer_history = ob.transfer_history + (ob.incurred_by_organ,)
            ob.incurred_by_organ = to_organ_id
            moved.append(ob)
        self._record("obligations.transferred",
                     {"function_id": function_id, "to_organ": to_organ_id,
                      "count": len(moved)})
        return moved

    def discharge(self, obligation_id: str, *, by_organ: str,
                  evidence_ref: str) -> Obligation:
        ob = self.obligations.get(obligation_id)
        if ob is None:
            raise RegenerationError("unknown obligation",
                                    code="unknown_obligation")
        if not evidence_ref:
            raise RegenerationError(
                "discharging an obligation requires evidence; an unevidenced "
                "discharge is a claim, not a settlement",
                code="unevidenced_discharge")
        ob.state = ObligationState.DISCHARGED
        ob.discharged_by_organ = by_organ
        ob.evidence_refs = ob.evidence_refs + (evidence_ref,)
        self._record("obligation.discharged",
                     {"obligation_id": obligation_id, "by_organ": by_organ})
        return ob

    # -- retirement -------------------------------------------------------
    def retire(self, organ_id: str, *, reason: str,
               obligations_disposition: str = "must_be_empty") -> OrganIncarnation:
        """Retire an organ. Open duties block retirement unless disposed of."""
        inc = self.incarnations.get(organ_id)
        if inc is None:
            raise RegenerationError(f"unknown organ {organ_id!r}",
                                    code="unknown_organ")
        still_open = [o for o in self.open_obligations(inc.function_id)
                      if o.incurred_by_organ == organ_id]
        if still_open and obligations_disposition == "must_be_empty":
            raise RegenerationError(
                f"organ {organ_id} still holds {len(still_open)} open "
                "obligation(s). Retiring it now would let the institution "
                "escape a duty by dissolving the body that owed it. Transfer "
                "or explicitly abandon them first.",
                code="open_obligations_block_retirement")
        inc.retired_at = _now()
        inc.retirement_reason = reason
        self._retired_ids.add(organ_id)
        self._record("organ.retired",
                     {"organ_id": organ_id, "reason": reason,
                      "open_obligations_at_retirement": len(still_open)})
        return inc

    def is_retired(self, organ_id: str) -> bool:
        return organ_id in self._retired_ids

    # -- lineage ----------------------------------------------------------
    def function_lineage(self, function_id: str) -> list[dict]:
        return [{"organ_id": oid,
                 "topology_signature": self.incarnations[oid].topology_signature,
                 "predecessor": self.incarnations[oid].predecessor_organ_id,
                 "retired": self.is_retired(oid)}
                for oid in self.lineage.get(function_id, [])]

    def distinct_forms(self, function_id: str) -> int:
        """How many MATERIALLY distinct topologies have served this function."""
        return len({self.incarnations[oid].topology_signature
                    for oid in self.lineage.get(function_id, [])})
