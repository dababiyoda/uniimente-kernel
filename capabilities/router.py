"""Capability Router — the Competency Compiler (Final Build Order §4.14).

Founder name: *Competency Compiler*. Target effect: given a problem, decide
which kinds of knowing can actually answer it, recruit the smallest
registered mechanism (or composition) competent to produce that evidence
inside its authority envelope, record the choice, learn from independently
verified outcomes which mechanisms are reliable, and name the gap as a
CapabilityDeficit when nothing registered is competent.

What this is not: an executor, a builder, or a source of authority. A
routing decision is a recommendation with typed evidence expectations.
Execution still requires a grant and the Kernel Consequence Gate. A
deficit is data for the founder loop; this module never builds, installs
or activates anything, and a mechanism cannot improve its own track record.

Mechanisms searched before writing this: `GenomeRegistry` (descriptors and
envelopes — reused here, not replaced), `foundry.composition` (technology
dependency closure for advantage plans — different question),
`egregore.runtime._select` (chooses among proposals of *what to do*, not
*which mechanism can know*). The residual missing capability is the
problem-to-epistemic-method mapping, competence-aware selection, and
outcome calibration. Pure stdlib, pure data.
"""
from __future__ import annotations

import hashlib
import json
from itertools import combinations
from dataclasses import asdict, dataclass
from typing import Optional

from capabilities.genome import CONSEQUENCE_CLASSES, GenomeRegistry

# --------------------------------------------------------------------------
# Epistemic methods and the evidence each can produce
# --------------------------------------------------------------------------
# `establishes` says what a method's output can count as. Only methods that
# touch the world or a proof can establish fact; the rest produce hypotheses,
# estimates, critiques or judgments — useful, but typed as what they are.
EPISTEMIC_METHODS: dict[str, dict] = {
    "deterministic_computation": {"evidence": "computed_result", "establishes": "fact_within_model"},
    "formal_verification":       {"evidence": "proof", "establishes": "fact_within_model"},
    "retrieval":                 {"evidence": "sourced_claim", "establishes": "claim_with_provenance"},
    "empirical_experiment":      {"evidence": "observed_outcome", "establishes": "external_fact"},
    "statistical_inference":     {"evidence": "estimate", "establishes": "estimate"},
    "simulation":                {"evidence": "model_output", "establishes": "hypothesis"},
    "adversarial_review":        {"evidence": "critique", "establishes": "objection"},
    "expert_judgment":           {"evidence": "judgment", "establishes": "hypothesis"},
    "human_decision":            {"evidence": "decision", "establishes": "authorization"},
    "legal_determination":       {"evidence": "ruling", "establishes": "legal_position"},
}

# Methods no machine may supply. The router routes these to a person.
HUMAN_ONLY_METHODS = frozenset({"human_decision", "legal_determination"})

# Which methods can *answer* each problem class. `all_of` must all be present
# (a composition); `any_of` needs one. A method absent here cannot answer the
# class however confident it is — e.g. a simulation never answers demand.
PROBLEM_CLASSES: dict[str, dict] = {
    "arithmetic":         {"any_of": ("deterministic_computation",), "all_of": ()},
    "fact_lookup":        {"any_of": ("retrieval",), "all_of": ()},
    "code_correctness":   {"any_of": ("formal_verification", "deterministic_computation"),
                           "all_of": ("adversarial_review",)},
    "forecast":           {"any_of": ("statistical_inference", "simulation", "expert_judgment"),
                           "all_of": ()},
    "market_demand":      {"any_of": ("empirical_experiment",), "all_of": ()},
    "design_critique":    {"any_of": ("adversarial_review", "expert_judgment"), "all_of": ()},
    "legal_question":     {"any_of": ("legal_determination",), "all_of": ()},
    "authorization":      {"any_of": ("human_decision",), "all_of": ()},
}

# The doctrine's acquisition order, attached to every deficit as next steps.
RESOLUTION_ORDER = (
    "existing capability", "composition/reconfiguration", "commodity infrastructure",
    "open source", "API/plugin/service", "authorized computer use", "small bounded utility",
    "coding agent/team", "OMNIMORPH (only if organization design is needed)", "new architecture",
)

DEFAULT_MIN_RELIABILITY = 0.6


class RouterError(ValueError):
    """Invalid problem, competency or outcome. Fails closed."""


def _digest(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ProblemSpec:
    problem_id: str
    question: str
    problem_class: str
    max_consequence_class: str = "read_only"
    budget_usd: float = 0.0
    min_reliability: float = DEFAULT_MIN_RELIABILITY

    def validate(self) -> list[str]:
        problems = []
        if not self.problem_id or not self.question:
            problems.append("problem_id and question are required")
        if self.problem_class not in PROBLEM_CLASSES:
            problems.append(f"unknown problem class {self.problem_class!r}")
        if self.max_consequence_class not in CONSEQUENCE_CLASSES:
            problems.append(f"unknown consequence class {self.max_consequence_class!r}")
        if self.budget_usd < 0:
            problems.append("budget may not be negative")
        if not 0.0 <= self.min_reliability <= 1.0:
            problems.append("min_reliability must be within [0, 1]")
        return problems


@dataclass(frozen=True)
class Competency:
    """A registered genome's claim to answer some problems by some methods.
    The claim is a hypothesis until verified outcomes calibrate it."""
    genome_name: str
    genome_version: str
    methods: tuple[str, ...]
    problem_classes: tuple[str, ...]
    consequence_class: str = "read_only"
    cost_usd: float = 0.0

    @property
    def key(self) -> str:
        return f"{self.genome_name}@{self.genome_version}"


@dataclass(frozen=True)
class Calibration:
    """Beta(1,1)-prior track record from independently verified outcomes.
    Immutable: callers get a snapshot, and only `record_outcome` (evidence,
    independent verifier, ledger event) or ledger replay can change it."""
    correct: int = 0
    incorrect: int = 0

    @property
    def trials(self) -> int:
        return self.correct + self.incorrect

    @property
    def reliability(self) -> float:
        return (self.correct + 1) / (self.trials + 2)


@dataclass(frozen=True)
class Candidate:
    key: str
    methods: tuple[str, ...]
    consequence_class: str
    cost_usd: float
    reliability: float
    trials: int
    proven: bool


@dataclass
class CapabilityDeficit:
    """The repertoire cannot answer this problem. Data, not a build order."""
    problem_id: str
    problem_class: str
    missing_methods: list[str]
    rejected: dict[str, str]
    resolution_order: tuple[str, ...] = RESOLUTION_ORDER
    status: str = "open"
    authority: str = "none: a deficit authorizes no acquisition, build or activation"

    @property
    def deficit_id(self) -> str:
        return _digest({"p": self.problem_id, "c": self.problem_class,
                        "m": sorted(self.missing_methods)})


@dataclass
class RoutingDecision:
    problem_id: str
    problem_class: str
    selected: list[Candidate]
    expected_evidence: dict[str, str]
    human_escalation: list[str]
    rejected: dict[str, str]
    deficit: Optional[CapabilityDeficit]
    exploratory: bool
    requires_gate: bool
    authority: str = "none: routing confers no execution authority"
    decision_id: str = ""

    @property
    def routed(self) -> bool:
        return self.deficit is None

    def to_dict(self) -> dict:
        data = asdict(self)
        if self.deficit is not None:
            data["deficit"]["deficit_id"] = self.deficit.deficit_id
        return data


# --------------------------------------------------------------------------
# The router
# --------------------------------------------------------------------------
class CapabilityRouter:
    """Problem → admissible methods → smallest competent registered
    mechanism inside its envelope → recorded decision → verified-outcome
    calibration. Deterministic: same inputs, same decision."""

    def __init__(self, genomes: GenomeRegistry, ledger=None):
        self.genomes = genomes
        self.ledger = ledger
        self._competencies: dict[str, Competency] = {}
        self._calibration: dict[tuple[str, str], Calibration] = {}
        # decision_id -> (problem_class, selected keys). Enough to validate
        # an outcome, and rebuildable from the ledger after a restart.
        self._decisions: dict[str, tuple[str, frozenset]] = {}

    # ------------------------------------------------------------ register
    def register(self, competency: Competency) -> Competency:
        genome = self.genomes.get(competency.genome_name, competency.genome_version)
        if genome is None:
            raise RouterError(f"no registered genome {competency.key}: a competency "
                              "must describe an existing, validated capability")
        unknown = [m for m in competency.methods if m not in EPISTEMIC_METHODS]
        if unknown or not competency.methods:
            raise RouterError(f"unknown or missing epistemic methods: {unknown}")
        human = sorted(set(competency.methods) & HUMAN_ONLY_METHODS)
        if human:
            raise RouterError(f"no mechanism may claim human-only methods: {human}")
        bad = [c for c in competency.problem_classes if c not in PROBLEM_CLASSES]
        if bad or not competency.problem_classes:
            raise RouterError(f"unknown or missing problem classes: {bad}")
        ok, reason = self.genomes.may_instantiate(
            competency.genome_name, competency.genome_version,
            requested_class=competency.consequence_class,
            requested_budget_usd=competency.cost_usd)
        if not ok:
            raise RouterError(f"competency exceeds its genome envelope: {reason}")
        # Ledger first: if the record cannot be written, nothing changes.
        self._record("capabilities.competency_registered", {
            "competency": competency.key, "methods": list(competency.methods),
            "problem_classes": list(competency.problem_classes)})
        self._competencies[competency.key] = competency
        return competency

    def calibration(self, key: str, problem_class: str) -> Calibration:
        return self._calibration.get((key, problem_class), Calibration())

    # --------------------------------------------------------------- route
    def route(self, problem: ProblemSpec) -> RoutingDecision:
        problems = problem.validate()
        if problems:
            raise RouterError(f"invalid problem: {problems}")
        spec = PROBLEM_CLASSES[problem.problem_class]
        admissible = set(spec["any_of"]) | set(spec["all_of"])
        # A person is needed when every way to answer is human-only, or a
        # required part of the composition is.
        any_human = set(spec["any_of"]) & HUMAN_ONLY_METHODS
        any_machine = set(spec["any_of"]) - HUMAN_ONLY_METHODS
        human_needed = sorted((any_human if not any_machine else set())
                              | (set(spec["all_of"]) & HUMAN_ONLY_METHODS))

        rejected: dict[str, str] = {}
        eligible: list[Candidate] = []
        for key in sorted(self._competencies):
            comp = self._competencies[key]
            reason = self._rejection(comp, problem, admissible)
            if reason:
                rejected[key] = reason
                continue
            cal = self.calibration(key, problem.problem_class)
            eligible.append(Candidate(
                key=key, methods=tuple(m for m in comp.methods if m in admissible),
                consequence_class=comp.consequence_class, cost_usd=comp.cost_usd,
                reliability=round(cal.reliability, 4), trials=cal.trials,
                proven=cal.trials > 0 and cal.reliability >= problem.min_reliability))

        selected, missing = self._compose(spec, eligible, human_needed, problem.budget_usd)
        deficit = None
        if missing:
            deficit = CapabilityDeficit(problem_id=problem.problem_id,
                                        problem_class=problem.problem_class,
                                        missing_methods=missing, rejected=dict(rejected))
            selected = []
        expected = {c.key: ",".join(EPISTEMIC_METHODS[m]["establishes"] for m in c.methods)
                    for c in selected}
        decision = RoutingDecision(
            problem_id=problem.problem_id, problem_class=problem.problem_class,
            selected=selected, expected_evidence=expected, human_escalation=human_needed,
            rejected=rejected, deficit=deficit,
            exploratory=bool(selected) and not all(c.proven for c in selected),
            requires_gate=any(CONSEQUENCE_CLASSES.index(c.consequence_class) > 0
                              for c in selected))
        decision.decision_id = _digest({"problem": asdict(problem),
                                        "selected": [c.key for c in selected],
                                        "deficit": deficit.deficit_id if deficit else None,
                                        "calibration": [(c.key, c.trials, c.reliability)
                                                        for c in selected]})
        self._record("capabilities.routing_decision", {
            "decision_id": decision.decision_id, "problem_id": problem.problem_id,
            "problem_class": problem.problem_class,
            "selected": [c.key for c in selected],
            "deficit": deficit.deficit_id if deficit else None,
            "human_escalation": human_needed, "exploratory": decision.exploratory})
        self._decisions[decision.decision_id] = (problem.problem_class,
                                                 frozenset(c.key for c in selected))
        return decision

    def _rejection(self, comp: Competency, problem: ProblemSpec, admissible: set) -> str:
        if problem.problem_class not in comp.problem_classes:
            return "does not claim this problem class"
        if not set(comp.methods) & admissible:
            return (f"its methods {list(comp.methods)} cannot answer "
                    f"{problem.problem_class} (needs {sorted(admissible)})")
        if CONSEQUENCE_CLASSES.index(comp.consequence_class) > \
                CONSEQUENCE_CLASSES.index(problem.max_consequence_class):
            return f"consequence {comp.consequence_class} exceeds problem limit {problem.max_consequence_class}"
        if comp.cost_usd > problem.budget_usd:
            return f"cost ${comp.cost_usd} exceeds budget ${problem.budget_usd}"
        cal = self.calibration(comp.key, problem.problem_class)
        if cal.trials > 0 and cal.reliability < problem.min_reliability:
            return (f"verified reliability {cal.reliability:.2f} over {cal.trials} outcomes "
                    f"is below {problem.min_reliability}")
        ok, reason = self.genomes.may_instantiate(
            comp.genome_name, comp.genome_version,
            requested_class=comp.consequence_class, requested_budget_usd=comp.cost_usd)
        return "" if ok else reason

    @staticmethod
    def _rank(c: Candidate) -> tuple:
        # Smallest competent first: proven before unproven, then least
        # consequence, then cheapest, then most reliable, then name.
        return (not c.proven, CONSEQUENCE_CLASSES.index(c.consequence_class),
                c.cost_usd, -c.reliability, c.key)

    def _compose(self, spec: dict, eligible: list[Candidate], human_needed: list[str],
                 budget_usd: float) -> tuple[list[Candidate], list[str]]:
        """Cover one `any_of` method plus every `all_of` method with the
        fewest, smallest mechanisms whose combined cost fits the problem
        budget. Searched exactly, not greedily, so one mechanism that covers
        everything beats a cheaper partial one plus another. Human-only
        methods are escalated, not covered."""
        machine_all = [m for m in spec["all_of"] if m not in HUMAN_ONLY_METHODS]
        machine_any = [m for m in spec["any_of"] if m not in HUMAN_ONLY_METHODS]
        if not machine_any and not machine_all:
            return [], []  # wholly human question: escalation, not a deficit

        def covers(group) -> bool:
            methods = {m for c in group for m in c.methods}
            return ((not machine_any or bool(methods & set(machine_any)))
                    and all(m in methods for m in machine_all))

        # Name what no eligible mechanism can supply at any price.
        offered = {m for c in eligible for m in c.methods}
        missing = []
        if machine_any and not offered & set(machine_any):
            missing.append("one of: " + "|".join(machine_any))
        missing += [m for m in machine_all if m not in offered]
        if missing:
            return [], missing

        # The cover needs at most one mechanism per required slot.
        max_size = (1 if machine_any else 0) + len(machine_all)
        best = None
        for size in range(1, max_size + 1):
            for group in combinations(sorted(eligible, key=self._rank), size):
                total = sum(c.cost_usd for c in group)
                if total > budget_usd or not covers(group):
                    continue
                key = (sum(1 for c in group if not c.proven),
                       max(CONSEQUENCE_CLASSES.index(c.consequence_class) for c in group),
                       total, -min(c.reliability for c in group),
                       tuple(sorted(c.key for c in group)))
                if best is None or key < best[0]:
                    best = (key, list(group))
            if best is not None:
                return best[1], []  # fewest mechanisms wins before anything else
        return [], [f"no composition within budget ${budget_usd}"]

    # ------------------------------------------------------------ outcomes
    def record_outcome(self, decision_id: str, competency_key: str, *, correct: bool,
                       evidence_ref: str, verified_by: str) -> Calibration:
        """Calibrate from an independently verified outcome. A mechanism may
        not grade itself, and an outcome without evidence is not recorded."""
        decision = self._decisions.get(decision_id)
        if decision is None:
            raise RouterError("unknown routing decision")
        problem_class, selected = decision
        if competency_key not in selected:
            raise RouterError("outcome names a mechanism this decision did not select")
        if not evidence_ref:
            raise RouterError("an outcome requires an evidence reference")
        if not verified_by or verified_by == competency_key or \
                verified_by.split("@", 1)[0] == competency_key.split("@", 1)[0]:
            raise RouterError("outcomes must be verified by someone other than the mechanism")
        # Stage the new record, ledger it, and only then make it current, so
        # in-memory selection never trusts an outcome history lacks.
        cal = self._next(competency_key, problem_class, bool(correct))
        self._record("capabilities.routing_outcome", {
            "decision_id": decision_id, "competency": competency_key,
            "problem_class": problem_class, "correct": bool(correct),
            "evidence_ref": evidence_ref, "verified_by": verified_by,
            "reliability": round(cal.reliability, 4), "trials": cal.trials})
        self._calibration[(competency_key, problem_class)] = cal
        return cal

    # ------------------------------------------------------------- restart
    def restore(self) -> int:
        """Rebuild decisions and calibration from the ledger after a restart.
        Competencies are not restored: they must be re-registered against
        the current genome registry, so a retired genome cannot come back
        through history. Returns the number of outcomes replayed."""
        if self.ledger is None:
            raise RouterError("no ledger to restore from")
        ok, reason = self.ledger.verify_chain()
        if not ok:
            raise RouterError(f"ledger chain is broken; refusing to restore: {reason}")
        self._decisions.clear()
        self._calibration.clear()
        replayed = 0
        for record in self.ledger.records:
            payload = record.payload if record.record_type == "event" else {}
            kind = payload.get("type")
            if kind == "capabilities.routing_decision":
                self._decisions[payload["decision_id"]] = (
                    payload["problem_class"], frozenset(payload["selected"]))
            elif kind == "capabilities.routing_outcome":
                self._bump(payload["competency"], payload["problem_class"],
                           bool(payload["correct"]))
                replayed += 1
        return replayed

    def _next(self, key: str, problem_class: str, correct: bool) -> Calibration:
        old = self._calibration.get((key, problem_class), Calibration())
        return Calibration(old.correct + (1 if correct else 0),
                           old.incorrect + (0 if correct else 1))

    def _bump(self, key: str, problem_class: str, correct: bool) -> Calibration:
        new = self._next(key, problem_class, correct)
        self._calibration[(key, problem_class)] = new
        return new

    def _record(self, event_type: str, payload: dict) -> None:
        if self.ledger is not None:
            self.ledger.append("event", {"type": event_type, **payload})


__all__ = [
    "EPISTEMIC_METHODS", "HUMAN_ONLY_METHODS", "PROBLEM_CLASSES", "RESOLUTION_ORDER",
    "RouterError", "ProblemSpec", "Competency", "Calibration", "Candidate",
    "CapabilityDeficit", "RoutingDecision", "CapabilityRouter",
]
