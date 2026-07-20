"""Phase 6 — the AI Influencer Company Foundry.

Doctrine (mission item 49; The Final Plan, Organ 1): a synthetic media
company is a complete company, not an account: owned identity, visual
canon, editorial Constitution, narrative world, owned distribution,
products, community, finance, and performance memory.

Red lines, structural not aspirational:
  - agents identify as machines everywhere, always: a charter without
    synthetic disclosure does not validate;
  - audience members are participants under participant-rights: no
    outrage optimization, no exploitation of vulnerable attention, no
    fear-based retention hooks, and a standing correction obligation;
  - official platform APIs only; no purchased metrics, no inauthentic
    behavior; transparent institutional authorship;
  - revenue routes to the Regenerative Treasury, never to the persona;
  - UNIIMENTE is never a legal operator;
  - a charter is executable only after hash-bound human ratification
    (edit the charter and it is a different, unratified charter);
  - every publish is an external effect and passes the Consequence Gate.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from loom.ratify import Ratifier
from policy.engine import Proposal
from provenance.commit_witness import sha256_obj

from foundry.territory import TerritoryGraph

# The editorial constitution must contain every one of these rules by id.
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
    """The complete synthetic media company, as a ratifiable artifact."""
    name: str                                  # the company, not the persona
    persona: str                               # the synthetic creator identity
    synthetic_disclosure: bool                 # machines identify as machines
    visual_canon: dict                         # hash-bound look invariants
    editorial_rules: list[str]                 # must cover REQUIRED_EDITORIAL_RULES
    narrative_world: str                       # the universe the canon inhabits
    owned_hub: str                             # canonical owned surface
    subscriber_list: str                       # the owned relationship store
    products: list[str]                        # what the company sells
    community: str                             # owned/federated community surface
    legal_operator: str = "alfonso_lopez"
    revenue_routes_to_treasury: bool = True    # sponsorships enter at treasury rules
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
            problems.append("agents identify as machines everywhere, always: "
                            "synthetic disclosure is not optional")
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
    """A chartered company bound to one territory graph."""
    charter: MediaCompanyCharter
    charter_hash: str
    territory: TerritoryGraph


class CompanyFoundry:
    """Assembles synthetic media companies; routes every publish through
    the Consequence Gate. The machine authors charters; the human ratifies;
    the gate executes; the territory's correction layer keeps it honest."""

    def __init__(self, ledger, *, operator: str = "alfonso_lopez"):
        self.ledger = ledger
        self.ratifier = Ratifier(ledger, operator=operator, kind="foundry.charter")
        self._companies: dict[str, MediaCompany] = {}

    # -- chartering -------------------------------------------------------
    def submit_charter(self, charter: MediaCompanyCharter,
                       territory: TerritoryGraph) -> str:
        t_problems = territory.validate()
        if t_problems:
            raise FoundryError(f"territory invalid, refusing charter: {t_problems}")
        h = self.ratifier.submit(charter)   # validates; raises on problems
        self._companies[h] = MediaCompany(charter=charter, charter_hash=h,
                                          territory=territory)
        return h

    def company(self, charter_hash: str) -> MediaCompany:
        if charter_hash not in self._companies:
            raise FoundryError(f"no company chartered under {charter_hash}")
        return self._companies[charter_hash]

    def is_operational(self, charter_hash: str) -> bool:
        return self.ratifier.is_ratified(charter_hash)

    # -- publishing (the only external effect) ----------------------------
    def publish(self, charter_hash: str, node_id: str, *, gate, actor: str,
                executor, platform: str, estimated_cost_usd: float = 0.0,
                approver=None):
        """Publish one territory node through the Consequence Gate.

        Refused before the gate even sees it when: the charter is not
        ratified (or was edited after ratification — different hash),
        the node is stale, retired, or below the evidence floor.
        The gate then applies identity, law, evidence, budget, witness,
        and commit-time revalidation exactly as for any external effect.
        """
        company = self.company(charter_hash)
        if not self.is_operational(charter_hash):
            raise FoundryError(f"charter {charter_hash[:16]}... not ratified; "
                               "an unratified company does not speak")
        if company.charter.hash() != charter_hash:
            raise FoundryError("charter content diverged from ratified hash; "
                               "an edited charter is an unratified charter")
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
            expected_outcome="artifact live on declared account")
        return gate.run(proposal, executor=executor, approver=approver)
