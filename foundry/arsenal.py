"""Canonical 55-technology anatomy for the Asymmetric Advantage Foundry.

The registry is descriptive and selection-oriented. An entry never claims
production completeness. Status is explicit so the Composer cannot confuse
target architecture with executable capability.
"""
from __future__ import annotations

from dataclasses import dataclass

VALID_STATUSES = ("executable", "partial", "target")
VALID_CONSEQUENCE_CLASSES = (
    "read_only", "internal_write", "external_contact", "financial", "irreversible",
)


@dataclass(frozen=True)
class TechnologySpec:
    id: int
    name: str
    category: str
    status: str
    control_surfaces: tuple[str, ...]
    dependencies: tuple[int, ...] = ()
    consequence_class: str = "internal_write"
    description: str = ""

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not 1 <= self.id <= 55:
            problems.append("technology id must be within 1..55")
        if self.status not in VALID_STATUSES:
            problems.append(f"invalid status {self.status!r}")
        if self.consequence_class not in VALID_CONSEQUENCE_CLASSES:
            problems.append(f"invalid consequence class {self.consequence_class!r}")
        if not self.name or not self.category or not self.control_surfaces:
            problems.append("name, category, and control surfaces are required")
        if self.id in self.dependencies:
            problems.append("technology may not depend on itself")
        return problems


def _t(identifier, name, category, status, surfaces, deps=(), consequence="internal_write", description=""):
    spec = TechnologySpec(identifier, name, category, status, surfaces, deps, consequence, description)
    problems = spec.validate()
    if problems:
        raise ValueError(f"invalid arsenal entry {identifier}: {problems}")
    return spec


_ENTRIES = (
    _t(1, "Interpreters and compilers", "construction", "partial", ("governance", "software")),
    _t(2, "Restricted DSLs", "construction", "partial", ("governance", "workflow"), (1,)),
    _t(3, "Git and version control", "construction", "partial", ("software", "resilience")),
    _t(4, "Databases", "data", "partial", ("state", "eligibility", "customer")),
    _t(5, "Event sourcing", "data", "executable", ("proof", "workflow", "coordination"), (4,)),
    _t(6, "Cryptographic proof primitives", "trust", "executable", ("proof", "settlement"), (5,)),
    _t(7, "Public-key infrastructure", "identity", "partial", ("identity", "trust")),
    _t(8, "Capability security", "authority", "executable", ("identity", "authority", "eligibility"), (7,)),
    _t(9, "Containers", "runtime", "partial", ("software", "resilience")),
    _t(10, "Microvirtual machines", "runtime", "target", ("software", "resilience"), (9,)),
    _t(11, "WebAssembly components", "runtime", "target", ("software", "composition")),
    _t(12, "Capability Genome Registry", "composition", "partial", ("composition", "software"), (8,)),
    _t(13, "Linkers and component composition", "composition", "partial", ("composition", "coordination"), (12,)),
    _t(14, "Institutional shell and pipelines", "operations", "target", ("governance", "workflow"), (1, 8)),
    _t(15, "Workflow engines", "operations", "executable", ("workflow", "coordination"), (5, 8)),
    _t(16, "CI/CD systems", "software", "partial", ("software", "resilience"), (3, 9)),
    _t(17, "Causal search engines", "intelligence", "partial", ("search", "memory"), (4, 5)),
    _t(18, "Knowledge graphs", "intelligence", "partial", ("knowledge", "eligibility", "reputation"), (4,)),
    _t(19, "Recommender systems", "intelligence", "partial", ("routing", "distribution", "validation"), (17,)),
    _t(20, "Emulators", "simulation", "partial", ("simulation", "resilience")),
    _t(21, "Virtual machines and snapshots", "simulation", "partial", ("simulation", "resilience"), (20,)),
    _t(22, "Simulation engines", "simulation", "executable", ("simulation", "strategy"), (20, 21)),
    _t(23, "Distributed-systems controls", "coordination", "partial", ("coordination", "workflow", "resilience"), (5,)),
    _t(24, "Message queues", "coordination", "partial", ("coordination", "routing"), (5, 23)),
    _t(25, "Cognitive router", "intelligence", "target", ("routing", "cost", "resilience"), (19,)),
    _t(26, "Zero-trust computer networks", "security", "partial", ("identity", "security", "resilience"), (7, 8)),
    _t(27, "RPC and service discovery", "coordination", "partial", ("routing", "composition"), (13, 26)),
    _t(28, "MCP integration", "coordination", "target", ("tools", "composition"), (8, 27)),
    _t(29, "Agent-to-agent protocols", "coordination", "partial", ("agents", "composition"), (8, 26, 27)),
    _t(30, "API gateway and Consequence Gate", "authority", "executable", ("authority", "proof", "settlement"), (5, 6, 8), "external_contact"),
    _t(31, "Web servers", "distribution", "executable", ("distribution", "customer"), (), "external_contact"),
    _t(32, "Owned social networks", "distribution", "partial", ("distribution", "community"), (31,), "external_contact"),
    _t(33, "Federated protocols", "distribution", "target", ("distribution", "resilience"), (31,), "external_contact"),
    _t(34, "Recommendation-graph observability", "distribution", "target", ("distribution", "measurement"), (19, 44)),
    _t(35, "Graphics, audio, video, and game engines", "media", "target", ("media", "distribution"), (31,), "external_contact"),
    _t(36, "Content-addressed storage", "trust", "partial", ("proof", "media", "resilience"), (6,)),
    _t(37, "Marketplace systems", "commerce", "target", ("marketplace", "coordination", "settlement"), (18, 23, 38), "financial"),
    _t(38, "Payment systems", "commerce", "partial", ("payment", "settlement"), (30,), "financial"),
    _t(39, "Double-entry accounting", "commerce", "partial", ("capital", "settlement", "measurement"), (38,), "financial"),
    _t(40, "Game theory and mechanism design", "market-design", "partial", ("incentives", "marketplace", "reputation"), (18,)),
    _t(41, "Reputation systems", "market-design", "target", ("reputation", "routing", "eligibility"), (5, 18, 40)),
    _t(42, "Digital twins", "simulation", "partial", ("simulation", "measurement"), (5, 22)),
    _t(43, "Formal methods", "assurance", "partial", ("governance", "security", "proof"), (1, 2)),
    _t(44, "Observability systems", "assurance", "partial", ("measurement", "security", "economics"), (5,)),
    _t(45, "Security information and event management", "security", "partial", ("security", "resilience"), (26, 44)),
    _t(46, "Backup and disaster recovery", "resilience", "target", ("resilience", "continuity"), (3, 4, 36)),
    _t(47, "Business Architecture Compiler", "venture", "partial", ("venture", "composition"), (1, 12, 13)),
    _t(48, "Agent swarm architectures", "venture", "partial", ("agents", "venture", "coordination"), (12, 15, 29)),
    _t(49, "AI influencer company systems", "media", "partial", ("media", "distribution", "venture"), (19, 31, 35, 48), "external_contact"),
    _t(50, "Rabbit Hole Engine", "media", "partial", ("media", "distribution", "customer"), (18, 19, 34, 49), "external_contact"),
    _t(51, "Automated software development", "software", "partial", ("software", "agents"), (3, 9, 16, 48)),
    _t(52, "Failure-driven program repair", "software", "partial", ("software", "resilience", "learning"), (16, 20, 44, 51)),
    _t(53, "Self-hosting toolchains", "sovereignty", "partial", ("software", "resilience", "sovereignty"), (1, 3, 12)),
    _t(54, "Agent-native commerce", "commerce", "target", ("agents", "payment", "marketplace"), (29, 37, 38, 41), "financial"),
    _t(55, "Regenerative Treasury", "capital", "executable", ("capital", "regeneration", "settlement"), (39,), "financial"),
)

ARSENAL: dict[int, TechnologySpec] = {entry.id: entry for entry in _ENTRIES}
if set(ARSENAL) != set(range(1, 56)):
    raise RuntimeError("Foundry arsenal must contain exactly technologies 1..55")


def technology(technology_id: int) -> TechnologySpec:
    try:
        return ARSENAL[technology_id]
    except KeyError as exc:
        raise KeyError(f"unknown Foundry technology {technology_id}") from exc


def by_surface(surface: str) -> tuple[TechnologySpec, ...]:
    return tuple(spec for spec in _ENTRIES if surface in spec.control_surfaces)
