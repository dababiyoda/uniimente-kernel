"""The Opus Maximus Blueprint: the complete institution, bound to evidence.

`foundry/arsenal.py` already carries the 55-technology anatomy — every
technology, its control surfaces, its consequence class, and its dependency
edges. What it carries is a *description*: `status="executable"` is a claim
bound to no proof, and nothing computes what to build next.

This package converts that description into a governed instrument:

- `ladder`      — six rungs and one separate reality axis. Each rung declares
                  the evidence kinds it requires. A rung claim without its
                  evidence is refused; it is never rounded up.
- `evidence`    — the binder. Every reference resolves against the real
                  repository or it does not resolve at all. No fabricated
                  evidence, no assumed proof.
- `registry`    — the 55 bindings: claimed rung, reality, evidence, named
                  hardening gaps, and which collaborator owns the next step.
- `critical_path` — topological resolution over the arsenal's own dependency
                  graph, producing the frontier that is unblocked right now
                  and the exact dependency blocking everything else.

The blueprint holds no state, opens no gate, grants nothing. It reports what
the institution can prove about itself and what it must build next. Reading
it confers no authority.
"""
from blueprint.ladder import (
    Rung,
    Reality,
    EvidenceKind,
    RUNG_ORDER,
    RUNG_REQUIREMENTS,
    required_evidence,
    rung_at_or_above,
    LadderError,
)
from blueprint.evidence import EvidenceRef, Resolution, resolve, resolve_all
from blueprint.registry import (
    TechnologyBinding,
    Owner,
    BINDINGS,
    binding,
    validate_binding,
    effective_rung,
    audit,
)
from blueprint.critical_path import (
    CriticalPathReport,
    TechnologyStatus,
    compute,
)

__all__ = [
    "Rung", "Reality", "EvidenceKind", "RUNG_ORDER", "RUNG_REQUIREMENTS",
    "required_evidence", "rung_at_or_above", "LadderError",
    "EvidenceRef", "Resolution", "resolve", "resolve_all",
    "TechnologyBinding", "Owner", "BINDINGS", "binding", "validate_binding",
    "effective_rung", "audit",
    "CriticalPathReport", "TechnologyStatus", "compute",
]
