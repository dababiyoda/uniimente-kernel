"""The Capability Discovery Service: a directory, never a door.

Doctrine (DISCOVERY, FBO §4.10): every organ publishes a manifest declaring the
capabilities it offers, the contract versions it speaks, its health, and the
authority those capabilities would require. Discovery makes that findable.

    "Discovery does not grant access."  — Final Build Order §4.10

Three consequences the implementation is built around:

1. **Advertisements are derived, never authored here.** Everything published
   comes from `organs/*.manifest.yaml`, loaded through the existing
   `linker.manifest` loader so a manifest that fails its contract never enters
   the directory. This service invents no capability and no organ.

2. **Authority is reported as a requirement, not conferred.** An advertisement
   states the consequence class an organ's authority ceiling permits and whether
   the kernel gate is mandatory. Reading that tells a caller what it would have
   to obtain. It obtains nothing.

3. **Health is quoted, not measured.** The manifest's declared test command and
   last verified result are reproduced verbatim and labelled as declared. This
   service runs nothing.

The interface below is the seam ChatGPT's governed module loader binds to:
`CapabilityDiscoveryService.lookup` and `.offers` are the only two calls a
loader needs to decide whether a capability is worth proposing.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import yaml

from linker.manifest import ORGANS_DIR, ManifestError, OrganManifest, load_all

# Ordered weakest to strongest; mirrors capabilities.genome.CONSEQUENCE_CLASSES.
CONSEQUENCE_ORDER = (
    "read_only", "internal_write", "external_contact", "financial", "irreversible",
)

# Organ statuses the canonical manifest contract admits. Only these two describe
# an organ that is attached to the running institution; `planned` does not.
ATTACHED_ORGAN_STATUSES = frozenset({"active", "this_repository"})


class DiscoveryError(ValueError):
    """Discovery could not be performed. Fails closed; publishes nothing partial."""


@dataclass(frozen=True)
class CapabilityAdvertisement:
    """One capability an organ says it offers. Carries no permission."""

    capability_id: str
    organ_id: str
    organ_name: str
    description: str
    implementation_path: str
    consumes: tuple[str, ...]
    produces: tuple[str, ...]
    lifecycle: str
    # Authority is a REQUIREMENT the caller must satisfy elsewhere, never a grant.
    max_consequence_class: str
    requires_kernel_gate: bool
    declared_health: str
    organ_status: str

    @property
    def grants(self) -> None:
        """Present so the answer is explicit and greppable: an advertisement
        grants nothing. There is no capability grant on this object."""
        return None

    def within(self, consequence_class: str) -> bool:
        """Would this capability's ceiling admit `consequence_class`?

        A truthful answer to a question. Not an authorization, and not a
        substitute for the Consequence Gate's own commit-time revalidation.
        """
        if consequence_class not in CONSEQUENCE_ORDER:
            raise DiscoveryError(f"unknown consequence class {consequence_class!r}")
        if self.max_consequence_class not in CONSEQUENCE_ORDER:
            return False
        return (CONSEQUENCE_ORDER.index(consequence_class)
                <= CONSEQUENCE_ORDER.index(self.max_consequence_class))


@dataclass(frozen=True)
class OrganAdvertisement:
    organ_id: str
    name: str
    role: str
    repository: str | None
    status: str
    consumes: tuple[str, ...]
    produces: tuple[str, ...]
    prohibited_actions: tuple[str, ...]
    max_consequence_class: str
    requires_kernel_gate: bool
    may_self_promote: bool
    declared_health: str
    unresolved: tuple[str, ...]
    capabilities: tuple[CapabilityAdvertisement, ...]


@dataclass(frozen=True)
class DiscoveryQuery:
    """A narrowing question. Every field is optional; all supplied fields must match."""

    capability_id: str | None = None
    organ_id: str | None = None
    produces: str | None = None
    consumes: str | None = None
    max_consequence_class: str | None = None   # ceiling must admit this class
    lifecycle: str | None = None
    include_unattached_organs: bool = False    # `planned` organs are excluded by default


def _health_summary(health: dict) -> str:
    command = health.get("test_command", "<none declared>")
    passing = health.get("tests_passing")
    total = health.get("tests_total")
    if passing is None or total is None:
        return f"declared: {command} (no verified result recorded)"
    return f"declared: {command} -> {passing}/{total} at last recorded run"


class CapabilityDiscoveryService:
    """The institutional directory. Read-only over organ manifests.

    Constructing the service loads and validates every manifest. A manifest that
    fails its contract is not skipped quietly — `load_all` raises, and the
    directory refuses to exist rather than publish a partial view of the organism.
    """

    def __init__(self, organs_dir: str = ORGANS_DIR,
                 manifests: list[OrganManifest] | None = None):
        try:
            self._manifests = manifests if manifests is not None else load_all(organs_dir)
        except (ManifestError, OSError) as exc:
            raise DiscoveryError(f"discovery cannot publish a partial directory: {exc}") from exc
        self._organs: dict[str, OrganAdvertisement] = {}
        self._capabilities: dict[str, CapabilityAdvertisement] = {}
        self._build()

    # -- construction ------------------------------------------------------
    def _build(self) -> None:
        for m in self._manifests:
            authority = m.authority or {}
            ceiling = str(authority.get("max_consequence_class", "read_only"))
            gate = bool(authority.get("external_actions_require_kernel_gate", True))
            health = _health_summary(m.health or {})

            ads: list[CapabilityAdvertisement] = []
            for cap in m.capabilities:
                cap_id = str(cap.get("capability_id", "")).strip()
                if not cap_id:
                    raise DiscoveryError(
                        f"organ {m.organ_id} declares a capability with no capability_id"
                    )
                if cap_id in self._capabilities:
                    raise DiscoveryError(
                        f"capability_id {cap_id!r} is declared by more than one organ; "
                        "discovery refuses an ambiguous directory"
                    )
                ad = CapabilityAdvertisement(
                    capability_id=cap_id,
                    organ_id=m.organ_id,
                    organ_name=m.name,
                    description=str(cap.get("description", "")),
                    implementation_path=str(cap.get("implementation_path", "")),
                    consumes=tuple(cap.get("consumes") or ()),
                    produces=tuple(cap.get("produces") or ()),
                    lifecycle=str(cap.get("lifecycle", "DISCOVERED")),
                    max_consequence_class=ceiling,
                    requires_kernel_gate=gate,
                    declared_health=health,
                    organ_status=m.status,
                )
                self._capabilities[cap_id] = ad
                ads.append(ad)

            self._organs[m.organ_id] = OrganAdvertisement(
                organ_id=m.organ_id, name=m.name, role=m.role,
                repository=m.repository, status=m.status,
                consumes=tuple(m.consumes), produces=tuple(m.produces),
                prohibited_actions=tuple(m.prohibited_actions),
                max_consequence_class=ceiling, requires_kernel_gate=gate,
                may_self_promote=bool(authority.get("may_self_promote", False)),
                declared_health=health,
                unresolved=tuple(m.unresolved),
                capabilities=tuple(ads),
            )

    # -- reads -------------------------------------------------------------
    @property
    def organs(self) -> tuple[OrganAdvertisement, ...]:
        return tuple(self._organs[k] for k in sorted(self._organs))

    @property
    def capabilities(self) -> tuple[CapabilityAdvertisement, ...]:
        return tuple(self._capabilities[k] for k in sorted(self._capabilities))

    def organ(self, organ_id: str) -> OrganAdvertisement:
        try:
            return self._organs[organ_id]
        except KeyError as exc:
            raise DiscoveryError(f"unknown organ {organ_id!r}") from exc

    def lookup(self, capability_id: str) -> CapabilityAdvertisement:
        """Find one capability. Unknown ids are refused, never approximated."""
        try:
            return self._capabilities[capability_id]
        except KeyError as exc:
            raise DiscoveryError(f"unknown capability {capability_id!r}") from exc

    def offers(self, query: DiscoveryQuery | None = None
               ) -> tuple[CapabilityAdvertisement, ...]:
        """Every advertisement matching every supplied field of `query`."""
        q = query or DiscoveryQuery()
        if q.max_consequence_class is not None and \
                q.max_consequence_class not in CONSEQUENCE_ORDER:
            raise DiscoveryError(
                f"unknown consequence class {q.max_consequence_class!r}"
            )
        out = []
        for ad in self.capabilities:
            if not q.include_unattached_organs and \
                    ad.organ_status not in ATTACHED_ORGAN_STATUSES:
                continue
            if q.capability_id is not None and ad.capability_id != q.capability_id:
                continue
            if q.organ_id is not None and ad.organ_id != q.organ_id:
                continue
            if q.produces is not None and q.produces not in ad.produces:
                continue
            if q.consumes is not None and q.consumes not in ad.consumes:
                continue
            if q.lifecycle is not None and ad.lifecycle != q.lifecycle:
                continue
            if q.max_consequence_class is not None and \
                    not ad.within(q.max_consequence_class):
                continue
            out.append(ad)
        return tuple(out)

    def implementations_of(self, contract: str) -> tuple[CapabilityAdvertisement, ...]:
        """Every capability producing `contract` — the Router's candidate set."""
        return self.offers(DiscoveryQuery(produces=contract,
                                          include_unattached_organs=True))

    def overlapping_authority(self) -> tuple[tuple[str, str], ...]:
        """Organs other than the kernel declaring governance-shaped capabilities.

        Reported for visibility. Discovery does not resolve authority conflicts;
        the canonical Kernel control plane does.
        """
        markers = ("constitution", "governance", "risk_management", "policy", "authority")
        found = []
        for ad in self.capabilities:
            if ad.organ_id.endswith("/constitutional-controller"):
                continue
            lowered = f"{ad.capability_id} {ad.description}".lower()
            if any(marker in lowered for marker in markers):
                found.append((ad.organ_id, ad.capability_id))
        return tuple(sorted(found))

    def identity_reconciliation(self, registry_path: str | None = None) -> dict:
        """Reconcile the manifest set against `identity/organ-registry.yaml`.

        These are two different registers and neither is a subset of the other:

        - **Identity registration** is a constitutional act. `organ-registry.yaml`
          says which organs the institution recognizes, with SPIFFE identities and
          founder-approval rules.
        - **A manifest** is a self-description that makes an organ *discoverable*.

        A manifest does not confer identity, registration, or activation. An organ
        can be identity-registered with no manifest (invisible to the linker), and
        an organ can publish a manifest without being identity-registered (visible
        but not constitutionally recognized). Both states exist right now, and
        this method names each one instead of averaging them into a single count.
        """
        registry_path = registry_path or os.path.join(
            os.path.dirname(ORGANS_DIR), "identity", "organ-registry.yaml")
        try:
            with open(registry_path, encoding="utf-8") as fh:
                registry = yaml.safe_load(fh) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise DiscoveryError(f"cannot read the organ registry: {exc}") from exc

        registered = {
            str(entry.get("identity")): name
            for name, entry in (registry.get("organs") or {}).items()
            if isinstance(entry, dict) and entry.get("identity")
        }
        manifested = {o.organ_id: o.name for o in self.organs}

        registered_without_manifest = sorted(
            (registered[i], i) for i in registered if i not in manifested
        )
        manifested_without_registration = sorted(
            (manifested[i], i) for i in manifested if i not in registered
        )
        both = sorted(manifested[i] for i in manifested if i in registered)

        return {
            "identity_registered": len(registered),
            "manifests_published": len(manifested),
            "both": both,
            "registered_without_manifest": [
                {"name": n, "organ_id": i} for n, i in registered_without_manifest
            ],
            "manifested_without_identity_registration": [
                {"name": n, "organ_id": i} for n, i in manifested_without_registration
            ],
            "note": (
                "A manifest is discovery-only. It does not imply registered "
                "institutional identity, constitutional recognition, or activation. "
                "Registering a new organ requires unique_mission, trust_boundary, "
                "charter and founder_approval per identity/organ-registry.yaml."
            ),
        }

    def directory(self) -> dict:
        """A plain, serializable snapshot. Useful for the knowledge graph and CLI."""
        return {
            "organs": [
                {
                    "organ_id": o.organ_id, "name": o.name, "status": o.status,
                    "repository": o.repository,
                    "max_consequence_class": o.max_consequence_class,
                    "requires_kernel_gate": o.requires_kernel_gate,
                    "may_self_promote": o.may_self_promote,
                    "capabilities": [c.capability_id for c in o.capabilities],
                    "unresolved": list(o.unresolved),
                }
                for o in self.organs
            ],
            "capability_count": len(self._capabilities),
            "grants_issued": 0,   # structural: this service issues none, ever
        }
