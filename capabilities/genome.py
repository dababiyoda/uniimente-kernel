"""Layer 5 — Portable Capability Organelles: the capability genome.

Doctrine (CAPABILITIES): a capability is a portable organelle, fully
described by its genome — interface, contracts, authority envelope,
acceptance tests, failure modes, recovery path. A capability with an
incomplete genome does not instantiate anywhere. A genome with an
unbounded authority envelope is not a genome; it is a liability.

The genome is data. Organs consume genomes; the kernel validates them.
"""
from __future__ import annotations

from dataclasses import dataclass, field

KNOWN_CONTRACTS = (
    "capability-grant", "context-packet", "decision", "event", "evidence",
    "opportunity-packet", "outcome", "venture-assessment", "venture-cell-charter",
)
CONSEQUENCE_CLASSES = ("read_only", "internal_write", "external_contact",
                       "financial", "irreversible")


class GenomeError(ValueError):
    """Invalid or incomplete genome. Fails closed; nothing instantiates."""


@dataclass
class AuthorityEnvelope:
    max_consequence_class: str
    budget_ceiling_usd: float
    requires_human: bool = False

    def validate(self) -> list[str]:
        problems = []
        if self.max_consequence_class not in CONSEQUENCE_CLASSES:
            problems.append(f"unknown consequence class {self.max_consequence_class!r}")
        if self.budget_ceiling_usd < 0:
            problems.append("budget ceiling may not be negative")
        if self.max_consequence_class in ("financial", "irreversible") and not self.requires_human:
            problems.append(f"{self.max_consequence_class} capabilities must require a human")
        return problems


@dataclass
class CapabilityGenome:
    name: str
    version: str
    description: str
    interface: dict                       # {"inputs": {...}, "outputs": {...}}
    contracts: list[str]                  # names from KNOWN_CONTRACTS
    authority: AuthorityEnvelope
    acceptance_tests: list[str]
    failure_modes: list[str]
    recovery_path: str
    legal_operator: str = "alfonso_lopez"

    def validate(self) -> list[str]:
        problems = []
        for f in ("name", "version", "description", "recovery_path", "legal_operator"):
            if not getattr(self, f):
                problems.append(f"missing {f}")
        if self.legal_operator == "UNIIMENTE":
            problems.append("UNIIMENTE is never a legal operator")
        if not self.interface.get("inputs") or not self.interface.get("outputs"):
            problems.append("interface must declare inputs and outputs")
        unknown = [c for c in self.contracts if c not in KNOWN_CONTRACTS]
        if unknown:
            problems.append(f"unknown contracts: {unknown}")
        if not self.acceptance_tests:
            problems.append("genome requires acceptance tests")
        if not self.failure_modes:
            problems.append("genome must declare its failure modes")
        problems.extend(self.authority.validate())
        return problems


class GenomeRegistry:
    """The kernel's genome library. Instantiation is a bounded check, not a build."""

    def __init__(self, ledger=None):
        self.ledger = ledger
        self._genomes: dict[str, CapabilityGenome] = {}

    def register(self, genome: CapabilityGenome) -> CapabilityGenome:
        problems = genome.validate()
        if problems:
            raise GenomeError(f"invalid genome: {problems}")
        key = f"{genome.name}@{genome.version}"
        self._genomes[key] = genome
        if self.ledger is not None:
            self.ledger.append("event", {"type": "capabilities.genome_registered",
                                         "genome": key})
        return genome

    def get(self, name: str, version: str) -> CapabilityGenome | None:
        return self._genomes.get(f"{name}@{version}")

    def may_instantiate(self, name: str, version: str, *,
                        requested_class: str, requested_budget_usd: float) -> tuple[bool, str]:
        """Bounded-authority check: the request must fit INSIDE the envelope."""
        genome = self.get(name, version)
        if genome is None:
            return False, f"no genome {name}@{version} registered"
        if requested_class not in CONSEQUENCE_CLASSES:
            return False, f"unknown consequence class {requested_class!r}"
        if CONSEQUENCE_CLASSES.index(requested_class) > \
                CONSEQUENCE_CLASSES.index(genome.authority.max_consequence_class):
            return False, (f"requested {requested_class} exceeds genome envelope "
                           f"{genome.authority.max_consequence_class}")
        if requested_budget_usd > genome.authority.budget_ceiling_usd:
            return False, (f"requested budget ${requested_budget_usd} exceeds ceiling "
                           f"${genome.authority.budget_ceiling_usd}")
        return True, f"{name}@{version} may instantiate at {requested_class} within envelope"
