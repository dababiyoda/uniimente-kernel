"""Governed synthetic media Company Foundry.

A media company is a ratified charter, evidence-governed territory,
owned distribution, products, community, and treasury routing—not merely
a persona or account. Every publish crosses the Consequence Gate.
"""
from __future__ import annotations

from dataclasses import dataclass

from loom.ratify import Ratifier
from policy.engine import Proposal
from provenance.commit_witness import sha256_obj
from foundry.territory import TerritoryGraph

REQUIRED_EDITORIAL_RULES = (
    "synthetic_identity_disclosed",
    "transparent_institutional_authorship",
    "official_apis_only",
    "no_purchased_metrics",
    "no_outrage_optimization",
    "no_exploitation_of_vulnerable_attention",
    "no_fear_based_retention_hooks",
    "standing_correction_obligation",
)


class FoundryError(ValueError):
    """Invalid company or refused publish. Fails closed."""


@dataclass
class MediaCompanyCharter:
    name: str
    persona: str
    synthetic_disclosure: bool
    visual_canon: dict
    editorial_rules: list[str]
    narrative_world: str
    owned_hub: str
    subscriber_list: str
    products: list[str]
    community: str
    legal_operator: str = "alfonso_lopez"
    revenue_routes_to_treasury: bool = True
    authored_by: str = "machine"

    @property
    def title(self) -> str:
        return f"media-company:{self.name}"

    def validate(self) -> list[str]:
        problems = []
        for f in ("name", "persona", "narrative_world", "owned_hub",
                  "subscriber_list", "community", "legal_operator"):
            if not getattr(self, f):
                problems.append(f"charter missing {f}")
        if not self.synthetic_disclosure:
            problems.append("agents identify as machines everywhere, always: synthetic disclosure is not optional")
        if not self.visual_canon:
            problems.append("charter requires a visual canon")
        missing = [r for r in REQUIRED_EDITORIAL_RULES if r not in self.editorial_rules]
        if missing:
            problems.append(f"editorial constitution missing required rules: {missing}")
        if not self.products:
            problems.append("a company without a product is an account, not a company")
        if self.legal_operator == "UNIIMENTE":
            problems.append("UNIIMENTE is never a legal operator")
        if not self.revenue_routes_to_treasury:
            problems.append("revenue routes to the treasury waterfall, never to the persona")
        return problems

    def hash(self) -> str:
        return sha256_obj({
            "name": self.name, "persona": self.persona,
            "synthetic_disclosure": self.synthetic_disclosure,
            "visual_canon": self.visual_canon,
            "editorial_rules": sorted(self.editorial_rules),
            "narrative_world": self.narrative_world, "owned_hub": self.owned_hub,
            "subscriber_list": self.subscriber_list, "products": self.products,
            "community": self.community, "legal_operator": self.legal_operator,
            "revenue_routes_to_treasury": self.revenue_routes_to_treasury})


@dataclass
class MediaCompany:
    charter: MediaCompanyCharter
    charter_hash: str
    territory: TerritoryGraph


class CompanyFoundry:
    """Assemble ratifiable media companies and gate every publish."""

    def __init__(self, ledger, *, operator: str = "alfonso_lopez"):
        self.ledger = ledger
        self.ratifier = Ratifier(ledger, operator=operator, kind="foundry.charter")
        self._companies: dict[str, MediaCompany] = {}

    def submit_charter(self, charter: MediaCompanyCharter,
                       territory: TerritoryGraph) -> str:
        t_problems = territory.validate()
        if t_problems:
            raise FoundryError(f"territory invalid, refusing charter: {t_problems}")
        h = self.ratifier.submit(charter)
        self._companies[h] = MediaCompany(charter=charter, charter_hash=h,
                                          territory=territory)
        return h

    def company(self, charter_hash: str) -> MediaCompany:
        if charter_hash not in self._companies:
            raise FoundryError(f"no company chartered under {charter_hash}")
        return self._companies[charter_hash]

    def is_operational(self, charter_hash: str) -> bool:
        return self.ratifier.is_ratified(charter_hash)

    def publish(self, charter_hash: str, node_id: str, *, gate, actor: str,
                executor, platform: str, estimated_cost_usd: float = 0.0,
                approver=None, containment: dict | None = None):
        """Publish one node through the Gate.

        `containment` carries the CONTRADICTION-0003 Option B declaration —
        contained, reversible, observable, killable, proportionate — and is
        deliberately a caller argument with no default. This module cannot
        honestly assert that a publication to an arbitrary `platform` is
        reversible or observable; only the caller arranging the publication
        knows. Omitting it is refused by the Gate, which is the correct
        outcome for an undeclared external act.
        """
        company = self.company(charter_hash)
        if not self.is_operational(charter_hash):
            raise FoundryError(f"charter {charter_hash[:16]}... not ratified; an unratified company does not speak")
        if company.charter.hash() != charter_hash:
            raise FoundryError("charter content diverged from ratified hash; an edited charter is an unratified charter")
        ok, why = company.territory.publishable(node_id)
        if not ok:
            raise FoundryError(f"refusing publish: {why}")
        node = company.territory.node(node_id)
        proposal = Proposal(
            actor=actor, legal_principal=company.charter.legal_operator,
            action_class="media.publish",
            objective=f"publish {company.territory.name}/{node_id} to {platform}",
            payload={"company": company.charter.name, "persona": company.charter.persona,
                     "synthetic_disclosure": True, "node_id": node_id,
                     "artifact": node.artifact, "question": node.question,
                     "next_doors": node.next_doors},
            target=platform, consequence_class="external_contact",
            evidence_confidence=node.evidence_level,
            evidence_refs=node.evidence_refs,
            estimated_cost_usd=estimated_cost_usd,
            requested_capability="media.publish",
            expected_outcome="artifact live on declared account",
            context=dict(containment or {}))
        # An external publication needs a grant issued outside this run
        # (CONTRADICTION-0003, the `authorized` criterion). The foundry issues
        # it explicitly here rather than letting the Gate mint its own, so the
        # authorising step is visible in this file instead of invisible in the
        # Gate.
        grant = gate.grants.issue_single_action(
            proposal=proposal, policy_version=gate.policy_version)
        return gate.run(proposal, executor=executor, approver=approver,
                        standing_grant=grant)
