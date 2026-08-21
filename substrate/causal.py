"""Causal escape: prohibit the failure motif, not the shape.

THE CORRECTED TARGET

Gate F's predicate demanded that a successor be *materially different* from its
predecessor. The audit (tests/unit/test_material_difference_audit.py) shows
that measures attribute distance, and gets both directions wrong:

  FALSE ACCEPT   a different-looking form with the identical single point of
                 failure is admitted
  FALSE ACCEPT   one decorative capability plus one cosmetic label flip = 2
                 dimensions = admitted
  FALSE REFUSAL  the predecessor form, still viable and cheapest, refused
                 purely for being the same
  FALSE REFUSAL  adding redundancy to the failed verifier - a real causal fix -
                 touches one dimension, so it is refused

The right requirement is not "be different". It is:

    a successor must not reproduce the causal mechanism that made the
    predecessor unable to satisfy the function contract.

If the old form remains valid, rebuilding it is CORRECT and cheap.

THE INFORMATION GEOMETRY, AND WHY IT DOES NOT LEAK

The tension: a cell cannot avoid recreating a failed topology it was never told
about; but handing every cell the predecessor graph destroys local knowledge.

Resolution: reduce the failure to a MOTIF. A motif is a statement about a local
structural relation, expressed in ROLES and COUNTS, never in cell identities or
graph extent:

    role=emit, upstream_count=1, redundancy=0

That is checkable by a cell against its own neighbourhood alone. It is also
provably not enough to reconstruct the predecessor: a motif names 1-2 roles and
a couple of integers, while the graph has N cells and N-1 edges. The leakage
test asserts exactly that - motif size stays bounded as the graph grows.

A rejection certificate carries a NEGATIVE constraint ("do not build this") and
never a positive one ("build that"). It cannot rank components, cannot name a
winner, and cannot describe a target. That is what stops it from being a
central planner speaking in the negative.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable, Optional

# Causal failure classes. Each names WHY a form failed, never what to build.
SINGLE_PATH_DEPENDENCY = "single_path_dependency"
UNREDUNDANT_VERIFICATION = "unredundant_verification"
SHARED_RESOURCE_EXHAUSTION = "shared_resource_exhaustion"
PARTITION_INTOLERANT_COUPLING = "partition_intolerant_coupling"

FAILURE_CLASSES = (SINGLE_PATH_DEPENDENCY, UNREDUNDANT_VERIFICATION,
                   SHARED_RESOURCE_EXHAUSTION, PARTITION_INTOLERANT_COUPLING)


@dataclass(frozen=True)
class CausalMotif:
    """A minimal local structural pattern. Roles and counts only.

    Deliberately has NO field that could carry a cell id, a capability name, a
    ranked list, or a graph. The leakage tests assert on this attribute set.
    """
    role: str
    upstream_count: Optional[int] = None      # exactly-N upstream attachments
    redundancy: Optional[int] = None          # sibling count filling same role
    verification_class: Optional[str] = None  # e.g. "single_read"
    shares_resource_with_upstream: Optional[bool] = None

    def matches_local(self, *, role: str, upstream_count: int,
                      redundancy: int, verification_class: str,
                      shares_resource: bool) -> bool:
        """Can a cell evaluate this from its own neighbourhood? Yes - only."""
        if self.role != role:
            return False
        if self.upstream_count is not None and self.upstream_count != upstream_count:
            return False
        if self.redundancy is not None and self.redundancy != redundancy:
            return False
        if (self.verification_class is not None
                and self.verification_class != verification_class):
            return False
        if (self.shares_resource_with_upstream is not None
                and self.shares_resource_with_upstream != shares_resource):
            return False
        return True

    @property
    def information_bits(self) -> int:
        """How much this motif says. Used by the leakage test."""
        return sum(1 for v in asdict(self).values() if v is not None)


@dataclass(frozen=True)
class FailureSignature:
    """Why the predecessor failed. Derived from observation, not from a plan."""
    failure_class: str
    affected_role: str
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self):
        if self.failure_class not in FAILURE_CLASSES:
            raise ValueError(f"unknown failure class {self.failure_class!r}")


@dataclass(frozen=True)
class CausalRejectionCertificate:
    """A machine-checkable NEGATIVE proof handed back by admission.

    Contains: the failed invariant, the causal class, prohibited motifs, scope,
    expiry, evidence. Contains NOT: a target topology, a ranked component list,
    the predecessor graph, or any positive construction instruction.
    """
    reason: str
    failure_class: str
    prohibited_motifs: tuple[CausalMotif, ...]
    scope: str                                # function contract id
    expires_after_episodes: int
    evidence_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["prohibited_motifs"] = [asdict(m) for m in self.prohibited_motifs]
        return d

    @property
    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()[:16]

    def carries_a_solution(self) -> bool:
        """Must always be False. Asserted by test on every certificate issued."""
        blob = json.dumps(self.to_dict()).lower()
        banned = ("cell_id", "cell.", "attach_to", "build", "use_", "prefer",
                  "ranked", "winner", "target_topology", "capabilities")
        return any(b in blob for b in banned)


# --------------------------------------------------------------------------
# Deriving the signature from an observed failure
# --------------------------------------------------------------------------

def signature_from_failure(*, topology: dict, failed_role: str,
                           partitioned: bool = False,
                           resource_starved: bool = False,
                           evidence_refs: tuple[str, ...] = ()) -> FailureSignature:
    """Name WHY it failed, using only the observed form and the symptom."""
    if resource_starved:
        cls = SHARED_RESOURCE_EXHAUSTION
    elif partitioned and topology.get("communication") == "direct":
        cls = PARTITION_INTOLERANT_COUPLING
    elif topology.get("verification") in ("readback", "single_read"):
        cls = UNREDUNDANT_VERIFICATION
    else:
        cls = SINGLE_PATH_DEPENDENCY
    return FailureSignature(failure_class=cls, affected_role=failed_role,
                            evidence_refs=evidence_refs)


def certificate_for(sig: FailureSignature, *, scope: str,
                    expires_after_episodes: int = 3) -> CausalRejectionCertificate:
    """Reduce a failure signature to the smallest prohibiting motif set."""
    if sig.failure_class == UNREDUNDANT_VERIFICATION:
        motifs = (CausalMotif(role=sig.affected_role, redundancy=0,
                              verification_class="single_read"),)
        reason = "repeats unredundant verification on the failed role"
    elif sig.failure_class == SINGLE_PATH_DEPENDENCY:
        motifs = (CausalMotif(role=sig.affected_role, upstream_count=1,
                              redundancy=0),)
        reason = "repeats a single unredundant path through the failed role"
    elif sig.failure_class == PARTITION_INTOLERANT_COUPLING:
        motifs = (CausalMotif(role=sig.affected_role, upstream_count=1),)
        reason = "repeats partition-intolerant direct coupling"
    else:
        motifs = (CausalMotif(role=sig.affected_role,
                              shares_resource_with_upstream=True),)
        reason = "repeats shared-resource coupling that exhausted"
    return CausalRejectionCertificate(
        reason=reason, failure_class=sig.failure_class,
        prohibited_motifs=motifs, scope=scope,
        expires_after_episodes=expires_after_episodes,
        evidence_refs=sig.evidence_refs)


# --------------------------------------------------------------------------
# The successor predicate
# --------------------------------------------------------------------------

def causal_escape(candidate: dict, certificate: CausalRejectionCertificate
                  ) -> tuple[bool, str]:
    """Does the candidate avoid the prohibited motifs? Sameness is allowed.

    Returns (escaped, reason). A candidate identical to the predecessor passes
    IF the predecessor's failure motif is absent from it - which happens when
    the failure was environmental rather than structural.
    """
    role_counts: dict[str, int] = {}
    for cap in candidate.get("capabilities", ()):
        role = str(cap).split(".")[0]
        role_counts[role] = role_counts.get(role, 0) + 1

    verification_class = ("single_read"
                          if candidate.get("verification") in ("readback", "single_read")
                          else "redundant_read")
    shares = candidate.get("resource_allocation") == "static"

    for motif in certificate.prohibited_motifs:
        redundancy = max(0, role_counts.get(motif.role, 0) - 1)
        upstream = 1 if candidate.get("control_topology") == "pipeline" else 2
        if motif.matches_local(role=motif.role, upstream_count=upstream,
                               redundancy=redundancy,
                               verification_class=verification_class,
                               shares_resource=shares):
            return False, (f"reproduces prohibited motif for role "
                           f"{motif.role!r} ({certificate.failure_class})")
    return True, "escapes every prohibited causal motif"


def local_inhibition_from(certificate: CausalRejectionCertificate) -> dict:
    """Translate a certificate into what a CELL may hold.

    A cell receives motifs for its own role only. It never receives the
    certificate's scope-wide view, and never another role's motifs beyond what
    it needs to refuse its own attachment.
    """
    return {m.role: m for m in certificate.prohibited_motifs}
