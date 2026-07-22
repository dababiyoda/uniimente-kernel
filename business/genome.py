"""Phase 7 — the Business Genome Compiler.

Doctrine (mission items 47/50; Layer 12): business creation is an
evidence-gated manufacturing process, not improvisation. A Business
Genome defines problem, buyer, offer, distribution, conversion,
fulfillment, retention, economics, required capabilities, required
workflows, legal restrictions, regenerative effect, and kill condition.

The compiler refuses:
  - any missing field (an incomplete genome does not compile);
  - required capabilities absent from the Capability Genome Registry
    (a business may not depend on competence the institution does not
    hold);
  - required workflows that are not ratified Loom patterns (a business
    may not run on unratified automation);
  - unit economics where the price does not cover marginal cost
    (a business that loses money per sale is a donation with paperwork);
  - a genome without a kill condition or a 90-day falsification test
    (a business that cannot die cannot be trusted to live);
  - UNIIMENTE as legal operator.

Do not build software before the workflow and demand are proven: the
genome records demand evidence refs, and compilation records the
falsification deadline on the ledger.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

from provenance.commit_witness import sha256_obj

FALSIFICATION_WINDOW_DAYS = 90


def _now() -> datetime:
    return datetime.now(timezone.utc)


class GenomeCompileError(ValueError):
    """The genome does not compile. Nothing launches."""


@dataclass
class BusinessGenome:
    """The complete definition of one bounded digital business."""
    name: str
    problem: str
    buyer: str
    offer: str
    price_usd: float
    distribution: str
    conversion: str
    fulfillment: str
    retention: str
    marginal_cost_usd: float
    demand_evidence_refs: list[str]
    required_capabilities: list[tuple[str, str]]
    required_workflows: list[str]
    legal_restrictions: list[str]
    regenerative_effect: str
    kill_condition: str
    falsification_test: str
    legal_operator: str = "alfonso_lopez"
    authored_by: str = "machine"

    @property
    def title(self) -> str:
        return f"business:{self.name}"

    def validate(self) -> list[str]:
        problems = []
        for f in ("name", "problem", "buyer", "offer", "distribution",
                  "conversion", "fulfillment", "retention", "regenerative_effect",
                  "kill_condition", "falsification_test", "legal_operator"):
            if not getattr(self, f):
                problems.append(f"genome missing {f}")
        if self.price_usd <= 0:
            problems.append("price must be positive; free is a distribution strategy, not a business")
        if self.marginal_cost_usd < 0:
            problems.append("marginal cost may not be negative")
        if self.price_usd <= self.marginal_cost_usd:
            problems.append(f"price ${self.price_usd} does not cover marginal cost ${self.marginal_cost_usd}: a donation with paperwork")
        if not self.demand_evidence_refs:
            problems.append("no demand evidence: do not build software before the workflow and demand are proven")
        if not self.required_capabilities:
            problems.append("genome must declare its required capabilities")
        if not self.legal_restrictions:
            problems.append("genome must declare what this business may never do")
        if self.legal_operator == "UNIIMENTE":
            problems.append("UNIIMENTE is never a legal operator")
        return problems

    def hash(self) -> str:
        return sha256_obj({
            "name": self.name, "problem": self.problem, "buyer": self.buyer,
            "offer": self.offer, "price_usd": self.price_usd,
            "distribution": self.distribution, "conversion": self.conversion,
            "fulfillment": self.fulfillment, "retention": self.retention,
            "marginal_cost_usd": self.marginal_cost_usd,
            "required_capabilities": sorted(map(list, self.required_capabilities)),
            "required_workflows": sorted(self.required_workflows),
            "legal_restrictions": sorted(self.legal_restrictions),
            "regenerative_effect": self.regenerative_effect,
            "kill_condition": self.kill_condition,
            "falsification_test": self.falsification_test,
            "legal_operator": self.legal_operator})


@dataclass
class CompiledBusiness:
    """A genome that compiled: launchable, falsifiable, killable."""
    business_id: str
    genome: BusinessGenome
    genome_hash: str
    compiled_at: datetime
    falsification_deadline: datetime
    capability_checks: list[str] = field(default_factory=list)
    workflow_checks: list[str] = field(default_factory=list)


class BusinessGenomeCompiler:
    """Compiles genomes against the institution's actual competence."""

    def __init__(self, *, genome_registry, ratifier, ledger):
        self.genome_registry = genome_registry
        self.ratifier = ratifier
        self.ledger = ledger

    def compile(self, genome: BusinessGenome) -> CompiledBusiness:
        problems = genome.validate()

        capability_checks: list[str] = []
        for name, version in genome.required_capabilities:
            if self.genome_registry.get(name, version) is None:
                problems.append(f"required capability {name}@{version} not in registry: the institution does not hold that competence")
            else:
                capability_checks.append(f"{name}@{version} present")

        workflow_checks: list[str] = []
        for pattern_hash in genome.required_workflows:
            status = self.ratifier.status(pattern_hash)
            if status != "ratified":
                problems.append(f"required workflow {pattern_hash[:16]}... is {status}, not ratified: a business may not run on unratified automation")
            else:
                workflow_checks.append(f"{pattern_hash[:16]}... ratified")

        if problems:
            self.ledger.append("event", {"type": "business.genome_refused",
                                         "genome": genome.name,
                                         "problems": problems})
            raise GenomeCompileError(f"genome does not compile: {problems}")

        now = _now()
        compiled = CompiledBusiness(
            business_id=str(uuid.uuid4()), genome=genome, genome_hash=genome.hash(),
            compiled_at=now,
            falsification_deadline=now + timedelta(days=FALSIFICATION_WINDOW_DAYS),
            capability_checks=capability_checks, workflow_checks=workflow_checks)
        self.ledger.append("event", {
            "type": "business.genome_compiled", "genome": genome.name,
            "business_id": compiled.business_id, "genome_hash": compiled.genome_hash,
            "falsification_test": genome.falsification_test,
            "falsification_deadline": compiled.falsification_deadline.isoformat(),
            "kill_condition": genome.kill_condition})
        return compiled
