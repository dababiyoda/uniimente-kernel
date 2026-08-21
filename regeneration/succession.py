"""Governed succession: damage -> candidate search -> admission -> new authority.

The candidate generator is deliberately SEPARATE from the admitter, and neither
can issue authority. Three different components, three different powers:

    CandidateFormer   proposes topologies. Cannot admit. Cannot authorize.
    FunctionRegistry  admits, records lineage, moves obligations. Cannot authorize.
    AuthorityIssuer   authorizes. Cannot admit. Does not choose topologies.

That separation is what stops the "central planner did all the work" critique
from being true by construction: the former does not know which candidate will
be admitted, the admitter does not know how candidates were found, and the
issuer sees only an admitted organ.

The candidate former is also blind to the damage episode it is repairing. It
receives a DEFICIT - which capabilities are unavailable - not a script naming
the replacement. Held-out damage episodes exercise capability combinations the
former has never been run against.
"""
from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .function import (FunctionContract, FunctionRegistry, OrganIncarnation,
                       RegenerationError)


@dataclass
class Deficit:
    """What the institution has lost. NOT what it should do about it."""
    function_id: str
    unavailable_capabilities: tuple[str, ...]
    symptom: str
    detected_at_episode: int


@dataclass
class CandidateForm:
    candidate_id: str
    topology: dict
    rationale: str
    rejected_reason: str = ""

    @property
    def accepted(self) -> bool:
        return not self.rejected_reason


class CapabilityPool:
    """Which concrete capabilities can satisfy which abstract requirement.

    A function needs ROLES filled (`ingest`, `decide`, `emit`). Several
    capabilities can fill each role, so a function has many valid bodies rather
    than one implementation plus a backup.
    """

    def __init__(self, roles: dict[str, tuple[str, ...]]):
        self.roles = roles

    def options(self, role: str, unavailable: set[str]) -> list[str]:
        return [c for c in self.roles.get(role, ()) if c not in unavailable]


class CandidateFormer:
    """Searches the capability pool for bodies that could serve the function.

    It does not know the correct answer. It enumerates role assignments that
    avoid the unavailable capabilities and that differ materially from the
    predecessor, then varies the CONTROL SHAPE as well - because a replacement
    that only swaps a component is the 'renamed topology' failure.
    """

    CONTROL_SHAPES = ("pipeline", "fan_out_vote", "supervised_pair")
    VERIFICATION = ("readback", "dual_read", "checksum_quorum")

    def __init__(self, pool: CapabilityPool, *, seed: int = 0):
        self.pool = pool
        self.rng = random.Random(seed)
        self.calls = 0

    def form(self, deficit: Deficit, predecessor: Optional[dict],
             *, limit: int = 6) -> list[CandidateForm]:
        self.calls += 1
        unavailable = set(deficit.unavailable_capabilities)
        roles = sorted(self.pool.roles)
        per_role = [self.pool.options(r, unavailable) for r in roles]
        if any(not opts for opts in per_role):
            return []          # the function genuinely cannot be served

        out: list[CandidateForm] = []
        combos = list(itertools.product(*per_role))
        self.rng.shuffle(combos)
        shapes = list(itertools.product(self.CONTROL_SHAPES, self.VERIFICATION))
        self.rng.shuffle(shapes)

        for i, combo in enumerate(combos[:limit]):
            shape, verify = shapes[i % len(shapes)]
            topo = {
                "capabilities": list(combo),
                "control_topology": shape,
                "communication": "direct" if shape == "pipeline" else "broadcast",
                "verification": verify,
                "memory_distribution": "central" if shape == "pipeline" else "replicated",
                "resource_allocation": "static" if shape != "fan_out_vote" else "elastic",
                "recovery_behaviour": "restart" if shape == "pipeline" else "reassign",
            }
            cand = CandidateForm(
                candidate_id=f"cand-{deficit.detected_at_episode}-{i}",
                topology=topo,
                rationale=f"avoids {sorted(unavailable)}; shape={shape}; verify={verify}")
            if predecessor is not None:
                diff = FunctionRegistry.material_difference(predecessor, topo)
                if len(diff) < 2:
                    cand.rejected_reason = (
                        f"only {len(diff)} material difference(s) from the "
                        f"predecessor {sorted(diff)}: this is a restart")
            if any(c in unavailable for c in combo):
                cand.rejected_reason = "uses an unavailable capability"
            out.append(cand)
        return out


class SuccessionOutcome:
    def __init__(self) -> None:
        self.candidates: list[CandidateForm] = []
        self.admitted: Optional[OrganIncarnation] = None
        self.old_certificate_refused: Optional[str] = None
        self.old_identity_refused: Optional[str] = None
        self.new_authority_record: Optional[str] = None
        self.obligations_transferred: int = 0
        self.function_restored: bool = False
        self.failure_reason: str = ""


def succeed(
    *,
    registry: FunctionRegistry,
    former: CandidateFormer,
    deficit: Deficit,
    predecessor: OrganIncarnation,
    ratified_by: str,
    issue_authority: Callable[[OrganIncarnation], str],
    verify_function: Callable[[dict], bool],
    revoke_predecessor: Callable[[OrganIncarnation], str],
    refuse_old_identity: Callable[[OrganIncarnation], str],
) -> SuccessionOutcome:
    """One governed succession. Every step can refuse; none can be skipped."""
    out = SuccessionOutcome()

    out.candidates = former.form(deficit, predecessor.topology)
    viable = [c for c in out.candidates if c.accepted]
    if not viable:
        out.failure_reason = ("no viable replacement form: every candidate was "
                              "rejected or the capability pool is exhausted")
        return out

    # Independent verification chooses, not the former. The former does not
    # know which of its proposals will be tried.
    chosen = None
    for cand in viable:
        if verify_function(cand.topology):
            chosen = cand
            break
    if chosen is None:
        out.failure_reason = "no candidate satisfied independent verification"
        return out

    # Admission. Refuses a non-materially-different successor and refuses
    # inherited authority.
    admitted = registry.admit(
        function_id=deficit.function_id, topology=chosen.topology,
        workload_identity=f"workload:{chosen.candidate_id}",
        ratified_by=ratified_by, predecessor_organ_id=predecessor.organ_id)
    out.admitted = admitted

    # The predecessor's authority dies BEFORE the successor's is issued, so
    # there is never a window in which both are valid.
    out.old_certificate_refused = revoke_predecessor(predecessor)
    out.old_identity_refused = refuse_old_identity(predecessor)

    # Fresh authority, issued by the one canonical issuer, to the new organ.
    out.new_authority_record = issue_authority(admitted)
    admitted.authority_record_id = out.new_authority_record

    # Duties move. Permissions did not.
    out.obligations_transferred = len(
        registry.transfer_obligations(function_id=deficit.function_id,
                                      to_organ_id=admitted.organ_id))

    out.function_restored = verify_function(admitted.topology)
    return out
