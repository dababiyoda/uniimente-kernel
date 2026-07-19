"""Phase 4 — Automation Loom: machine-authored workflow patterns.

Doctrine (LOOM): the institution weaves its own routines. The machine
authors workflow definitions AS DATA (patterns); a human ratifies them;
only then do they execute on the durable spine. A pattern is a complete,
checkable contract: every step names its capability, consequence class,
compensation, and approval gate.

Fail closed: irreversible or external steps without an approval gate are
invalid; side-effecting steps without compensation are invalid; a pattern
that names UNIIMENTE as legal principal is invalid.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field

HUMAN_REQUIRED_CLASSES = ("irreversible", "financial", "external_contact")
SIDE_EFFECT_CLASSES = ("internal_write", "external_contact", "financial", "irreversible")


class PatternError(ValueError):
    """Invalid pattern. Fails closed; nothing weaves from an invalid pattern."""


@dataclass
class StepSpec:
    name: str
    action: str                      # named operation in the weaver's registry
    capability: str                  # capability the step consumes
    consequence_class: str           # read_only | internal_write | external_contact | financial | irreversible
    params: dict = field(default_factory=dict)
    compensation: str | None = None  # named compensation operation
    approval_required: bool = False
    max_retries: int = 2


@dataclass
class WorkflowPattern:
    title: str
    objective: str
    authored_by: str                 # passport id of the authoring agent
    legal_principal: str             # never UNIIMENTE
    steps: list[StepSpec]
    budget_usd: float = 0.0
    required_capabilities: list[str] = field(default_factory=list)
    pattern_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def validate(self) -> list[str]:
        problems = []
        if not self.title or not self.objective:
            problems.append("pattern needs title and objective")
        if self.legal_principal == "UNIIMENTE":
            problems.append("UNIIMENTE is never a legal principal")
        if not self.steps:
            problems.append("pattern has no steps")
        if self.budget_usd < 0:
            problems.append("budget may not be negative")
        seen = set()
        for s in self.steps:
            if s.name in seen:
                problems.append(f"duplicate step name: {s.name}")
            seen.add(s.name)
            if not s.capability:
                problems.append(f"step {s.name}: capability required")
            if s.consequence_class in HUMAN_REQUIRED_CLASSES and not s.approval_required:
                problems.append(f"step {s.name}: {s.consequence_class} requires a human approval gate")
            if s.consequence_class in SIDE_EFFECT_CLASSES and not s.compensation:
                problems.append(f"step {s.name}: side-effecting step requires a compensation")
            if s.max_retries < 0:
                problems.append(f"step {s.name}: max_retries may not be negative")
        return problems

    def canonical(self) -> dict:
        """The ratification surface: exactly what the human signs off on."""
        return {"title": self.title, "objective": self.objective,
                "authored_by": self.authored_by, "legal_principal": self.legal_principal,
                "budget_usd": self.budget_usd,
                "required_capabilities": sorted(self.required_capabilities),
                "steps": [{"name": s.name, "action": s.action, "capability": s.capability,
                           "consequence_class": s.consequence_class, "params": s.params,
                           "compensation": s.compensation,
                           "approval_required": s.approval_required,
                           "max_retries": s.max_retries} for s in self.steps]}

    def hash(self) -> str:
        """Content hash. Any edit after ratification yields a new hash —
        and an unratified pattern. Ratification binds to THIS definition."""
        blob = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()
