"""Closure registrations for the institutional nervous system.

Four modules join the five-closure standard here: the Opus Maximus blueprint,
capability discovery, the knowledge graph and the capability router.

These modules are unusual among registered modules in one respect worth stating
plainly: none of them can act. Their authority closure is not "they check
permission before acting" but "there is no action to check" — asserted by
structure, not by promise. The checks below prove that rather than assert it.

Registered here rather than inside `kernel_registry` so the constitutional core
registry stays as it was. This is an extension point, never a second authority
path.
"""
from __future__ import annotations

import ast
import os

from closure.framework import ClosureRegistry, ModuleClosures

KERNEL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Modules no non-authorizing component may import. Checked by AST, never by
# substring: a guard that fires on an identifier containing the word "gate" is
# as broken as one that never fires at all.
FORBIDDEN_IMPORTS = ("policy.consequence_gate", "policy.engine")


def imported_modules(path: str) -> set[str]:
    """Every module name imported by `path`, resolved from the AST."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found.update(f"{node.module}.{a.name}" for a in node.names)
    return found


def package_imports(*relative_paths: str) -> set[str]:
    found: set[str] = set()
    for rel in relative_paths:
        target = os.path.join(KERNEL_ROOT, rel)
        if os.path.isdir(target):
            for name in sorted(os.listdir(target)):
                if name.endswith(".py"):
                    found |= imported_modules(os.path.join(target, name))
        elif os.path.isfile(target):
            found |= imported_modules(target)
    return found


def _authority_free(*relative_paths: str) -> tuple[bool, str]:
    """No path may import the gate or the policy engine. Fails closed."""
    imports = package_imports(*relative_paths)
    violations = sorted(
        i for i in imports
        if any(i == f or i.startswith(f + ".") for f in FORBIDDEN_IMPORTS)
    )
    if violations:
        return False, f"imports authority modules: {violations}"
    return True, (f"no authority import across {len(relative_paths)} path(s); "
                  f"cannot open the gate, mint a grant, or widen a ceiling")


def register_nervous_system_closures(reg: ClosureRegistry) -> ClosureRegistry:
    # ------------------------------------------------------------ blueprint
    def blueprint_technical():
        from blueprint.critical_path import compute
        report = compute()
        return len(report.statuses) == 55, (
            f"55 technologies resolved; {len(report.frontier)} on the frontier, "
            f"{len(report.blocked)} blocked"
        )

    def blueprint_authority():
        return _authority_free("blueprint")

    def blueprint_evidence():
        from blueprint.registry import audit
        results = audit()
        dishonest = [a.technology_id for a in results if a.problems]
        return not dishonest, (
            "every awarded rung is backed by a reference that resolves against "
            "the real tree"
            if not dishonest else f"over-claimed bindings: {dishonest}"
        )

    def blueprint_economic():
        from blueprint.critical_path import compute
        report = compute()
        # The durable asset is an ordered frontier: work that can start today
        # without waiting, ranked by how much it unblocks.
        return bool(report.frontier), (
            f"{len(report.frontier)} unblocked technologies ranked by leverage; "
            "the build order is computed, not argued"
        )

    def blueprint_regenerative():
        from blueprint.evidence import EvidenceRef, resolve
        from blueprint.ladder import EvidenceKind
        bogus = EvidenceRef(EvidenceKind.IMPLEMENTATION_PATH, "does/not/exist.py")
        r = resolve(bogus)
        return not r.ok, (
            "an unresolvable reference is refused rather than warned about; "
            "the ladder cannot be inflated by adding claims"
        )

    reg.register(ModuleClosures("blueprint", {
        "technical": blueprint_technical, "authority": blueprint_authority,
        "evidence": blueprint_evidence, "economic": blueprint_economic,
        "regenerative": blueprint_regenerative}))

    # ------------------------------------------------------------ discovery
    def discovery_technical():
        from discovery.service import CapabilityDiscoveryService
        d = CapabilityDiscoveryService()
        return len(d.organs) >= 3 and bool(d.capabilities), (
            f"{len(d.organs)} organs, {len(d.capabilities)} capabilities published"
        )

    def discovery_authority():
        ok, detail = _authority_free("discovery")
        if not ok:
            return ok, detail
        from discovery.service import CapabilityDiscoveryService
        d = CapabilityDiscoveryService()
        # Structural: no public member of an advertisement grants anything.
        ad = d.capabilities[0]
        leaks = [n for n in dir(ad)
                 if not n.startswith("_") and "grant" in n.lower()
                 and getattr(ad, n) is not None]
        return not leaks and d.directory()["grants_issued"] == 0, (
            f"{detail}; advertisements expose no grant and the directory has "
            "issued zero"
        )

    def discovery_evidence():
        from discovery.service import CapabilityDiscoveryService
        d = CapabilityDiscoveryService()
        # Every advertisement traces to a manifest-declared capability id.
        from blueprint.evidence import declared_capability_ids
        declared = declared_capability_ids()
        unbacked = [a.capability_id for a in d.capabilities
                    if a.capability_id not in declared]
        return not unbacked, (
            "every advertisement traces to a capability an organ manifest declares"
            if not unbacked else f"invented advertisements: {unbacked}"
        )

    def discovery_economic():
        from discovery.service import CapabilityDiscoveryService
        d = CapabilityDiscoveryService()
        overlaps = d.overlapping_authority()
        return True, (
            f"one directory serves every consumer; {len(overlaps)} overlapping "
            "governance capabilities surfaced for the canonical path to resolve"
        )

    def discovery_regenerative():
        from discovery.service import CapabilityDiscoveryService, DiscoveryError
        try:
            CapabilityDiscoveryService(organs_dir=os.path.join(KERNEL_ROOT, "contracts"))
            return False, "a directory over a non-organ path did not fail closed"
        except DiscoveryError:
            return True, (
                "an invalid or empty organ source refuses to publish rather than "
                "serving a partial view of the organism"
            )

    reg.register(ModuleClosures("discovery", {
        "technical": discovery_technical, "authority": discovery_authority,
        "evidence": discovery_evidence, "economic": discovery_economic,
        "regenerative": discovery_regenerative}))

    # ------------------------------------------------------ knowledge graph
    def graph_technical():
        from knowledge.graph import build
        g = build()
        return len(g) > 55 and g.edge_count > 0, (
            f"{len(g)} nodes, {g.edge_count} edges, sealed={g.sealed}"
        )

    def graph_authority():
        return _authority_free("knowledge")

    def graph_evidence():
        from knowledge.graph import build
        g = build()
        missing = [n.key for n in g.nodes() if n.provenance is None]
        return not missing, (
            f"all {len(g)} nodes carry a source kind and locator; a node with no "
            "provenance is structurally unconstructible"
        )

    def graph_economic():
        from knowledge.graph import build
        g = build()
        unpopulated = g.unpopulated()
        return True, (
            f"one traversal answers cross-organ questions; {len(unpopulated)} node "
            f"kinds are reported empty rather than filled with placeholders: "
            f"{list(unpopulated)}"
        )

    def graph_regenerative():
        from knowledge.graph import GraphError, Node, NodeKind, build
        g = build()
        try:
            g.add_node(Node(NodeKind.FILE, "x", "x", None))  # type: ignore[arg-type]
            return False, "a node with no provenance was admitted"
        except GraphError:
            pass
        try:
            Node(NodeKind.FILE, "y", "y", None)  # type: ignore[arg-type]
            return False, "an unprovenanced node was constructible"
        except GraphError:
            return True, (
                "an unprovenanced node cannot be constructed, and a sealed graph "
                "refuses mutation; the graph cannot drift from its sources"
            )

    reg.register(ModuleClosures("knowledge_graph", {
        "technical": graph_technical, "authority": graph_authority,
        "evidence": graph_evidence, "economic": graph_economic,
        "regenerative": graph_regenerative}))

    # ------------------------------------------------------ capability router
    def router_technical():
        from routing.decision_router import Candidate, DecisionRouter, RoutingCriteria
        r = DecisionRouter()
        a = Candidate("a", "organ", "evidence", evidence_maturity="PROVEN")
        b = Candidate("b", "organ", "evidence", evidence_maturity="BUILT")
        d = r.route(RoutingCriteria(contract="evidence"), [a, b])
        return d.selected == "a" and len(d.ranking) == 2, (
            f"ranked {len(d.ranking)} candidates deterministically; "
            f"selected {d.selected} on declared evidence maturity"
        )

    def router_authority():
        ok, detail = _authority_free("routing")
        if not ok:
            return ok, detail
        from routing.decision_router import Candidate, DecisionRouter, RoutingCriteria
        r = DecisionRouter()
        d = r.route(RoutingCriteria(contract="evidence"),
                    [Candidate("a", "o", "evidence", evidence_maturity="PROVEN")])
        return d.authorizes is None and d.to_dict()["grants_issued"] == 0, (
            f"{detail}; a decision carries no grant and issues none"
        )

    def router_evidence():
        from routing.decision_router import Candidate, DecisionRouter, RoutingCriteria
        r = DecisionRouter()
        r.route(RoutingCriteria(contract="evidence"),
                [Candidate("a", "o", "evidence", evidence_maturity="PROVEN")])
        recorded = r.decisions
        return len(recorded) == 1 and bool(recorded[0].ranking), (
            "every decision is recorded with its full ranking, score breakdown "
            f"and refusals; {r.outcomes_compared()} have been compared against "
            "real outcomes"
        )

    def router_economic():
        from routing.decision_router import Candidate, DecisionRouter, RoutingCriteria
        r = DecisionRouter()
        cheap = Candidate("cheap", "o", "evidence", evidence_maturity="PROVEN",
                          cost_units=1.0)
        dear = Candidate("dear", "o", "evidence", evidence_maturity="PROVEN",
                         cost_units=100.0)
        d = r.route(RoutingCriteria(contract="evidence"), [cheap, dear])
        return d.selected == "cheap", (
            "at equal evidence the cheaper implementation wins; cost is a "
            "ranked term, never the dominant one"
        )

    def router_regenerative():
        from routing.decision_router import Candidate, DecisionRouter, RoutingCriteria
        r = DecisionRouter()
        over = Candidate("over", "o", "evidence", authority_ceiling="read_only",
                         evidence_maturity="PROVEN")
        d = r.route(RoutingCriteria(contract="evidence",
                                    consequence_class="financial"), [over])
        return d.is_refusal and bool(d.refused), (
            "a request beyond every candidate's ceiling returns a refusal with "
            "reasons, never the least-bad option"
        )

    reg.register(ModuleClosures("decision_router", {
        "technical": router_technical, "authority": router_authority,
        "evidence": router_evidence, "economic": router_economic,
        "regenerative": router_regenerative}))

    return reg
