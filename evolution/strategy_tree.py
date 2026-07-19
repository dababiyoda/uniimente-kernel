"""Strategic Tree Search Engine.

Doctrine: for every material bottleneck, generate materially different
branches. The preferred idea may not win by default. Rejected branches
are preserved with why they lost and what evidence could revive them.

Branch kinds (all eleven):
    fastest_path, lowest_capital, maximum_ownership, maximum_reversibility,
    maximum_regeneration, strongest_partnership, acquisition,
    incumbent_compatible, radical_simplification, complete_removal,
    do_nothing.

Every branch must state: governing assumption, mechanism, required
capabilities, cost, founder attention, time to proof, authority
requirements, irreversible downside, expected result, strongest
counterargument, cheapest falsification test, and kill condition.
A branch missing any field is structurally invalid and cannot compete.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict

BRANCH_KINDS = (
    "fastest_path", "lowest_capital", "maximum_ownership", "maximum_reversibility",
    "maximum_regeneration", "strongest_partnership", "acquisition",
    "incumbent_compatible", "radical_simplification", "complete_removal",
    "do_nothing",
)

REQUIRED_FIELDS = (
    "governing_assumption", "mechanism", "required_capabilities", "cost_usd",
    "founder_attention_minutes", "time_to_proof_days", "authority_requirements",
    "irreversible_downside", "expected_result", "strongest_counterargument",
    "cheapest_falsification_test", "kill_condition",
)


@dataclass
class StrategyBranch:
    kind: str
    title: str
    governing_assumption: str
    mechanism: str
    required_capabilities: list[str]
    cost_usd: float
    founder_attention_minutes: int
    time_to_proof_days: int
    authority_requirements: list[str]
    irreversible_downside: str
    expected_result: str
    strongest_counterargument: str
    cheapest_falsification_test: str
    kill_condition: str
    branch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    # filled after selection:
    rejected: bool = False
    rejection_reason: str | None = None
    revival_evidence: str | None = None

    def validate(self) -> list[str]:
        problems = []
        if self.kind not in BRANCH_KINDS:
            problems.append(f"unknown branch kind {self.kind!r}")
        for f in REQUIRED_FIELDS:
            v = getattr(self, f)
            if v is None or v == "" or v == []:
                problems.append(f"missing required field: {f}")
        return problems

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StrategyTree:
    """All branches for one bottleneck, with the decision trail preserved."""
    bottleneck: str
    objective: str
    branches: list[StrategyBranch] = field(default_factory=list)
    tree_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    selected_branch_id: str | None = None
    decisive_unknown: str | None = None

    def add(self, branch: StrategyBranch) -> StrategyBranch:
        problems = branch.validate()
        if problems:
            raise ValueError(f"branch structurally invalid: {problems}")
        self.branches.append(branch)
        return branch

    def select(self, branch_id: str, *, decisive_unknown: str, reason: str) -> StrategyBranch:
        """Select one branch. All others are rejected WITH reasons and
        revival evidence. Nothing is deleted; losing is information."""
        chosen = None
        for b in self.branches:
            if b.branch_id == branch_id:
                chosen = b
        if chosen is None:
            raise ValueError(f"no branch {branch_id}")
        self.selected_branch_id = branch_id
        self.decisive_unknown = decisive_unknown
        for b in self.branches:
            if b.branch_id != branch_id and not b.rejected:
                b.rejected = True
                b.rejection_reason = (f"lost to '{chosen.title}': {reason}; "
                                      f"its own counterargument stands: {b.strongest_counterargument}")
                b.revival_evidence = b.cheapest_falsification_test
        return chosen

    def coverage(self) -> dict:
        """Which of the eleven mandated branch kinds are present."""
        present = {b.kind for b in self.branches}
        return {k: (k in present) for k in BRANCH_KINDS}

    def to_dict(self) -> dict:
        return {"tree_id": self.tree_id, "bottleneck": self.bottleneck,
                "objective": self.objective, "decisive_unknown": self.decisive_unknown,
                "selected": self.selected_branch_id,
                "coverage": self.coverage(),
                "branches": [b.to_dict() for b in self.branches]}
