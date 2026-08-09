"""Where proven edges come from — and what their absence looks like.

The target capability under test is ``institutional.cross_organ_edge_resolution``.
The four-state counterfactual needs a healthy configuration and a damaged one,
and the damage must be the *capability* going away, not the data being
falsified. Editing a manifest so the edge stops existing would prove that a
different organism has a different topology, which is not the question.

So the damaged state removes the kernel's ability to resolve edges at all:
``DisabledEdgeResolution`` raises. Everything downstream must then fail closed,
and any assessment that still appears is a bypass, not a success.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from linker.linker import CONTRACTS_DIR, Edge, InstitutionalLinker
from linker.manifest import ORGANS_DIR, load_all


class EdgeResolutionUnavailable(RuntimeError):
    """The kernel cannot resolve cross-organ edges.

    Raised rather than returning an empty list: an empty topology and an
    unavailable capability are different facts, and a caller that treated
    "no edges" as "nothing to route" would silently convert a missing
    capability into a normal quiet outcome.
    """


class TopologyProvider(Protocol):
    """Supplies proven edges. Proving is the linker's job, not the seam's."""

    def resolve_edges(self) -> list[Edge]:  # pragma: no cover - protocol
        ...

    @property
    def provider_id(self) -> str:  # pragma: no cover - protocol
        ...


@dataclass
class LinkerTopology:
    """Healthy state: the real ``InstitutionalLinker`` over the real manifests.

    No second linker is constructed and no edge is cached. ``REQUIRED_EXISTING_
    COMPONENTS`` names ``linker.linker.InstitutionalLinker`` as the component
    this must invoke, and this invokes exactly that.
    """

    organs_dir: str = ORGANS_DIR
    contracts_dir: str = CONTRACTS_DIR

    @property
    def provider_id(self) -> str:
        return "linker.linker.InstitutionalLinker"

    def resolve_edges(self) -> list[Edge]:
        manifests = load_all(self.organs_dir)
        if not manifests:
            raise EdgeResolutionUnavailable(
                f"no organ manifests under {self.organs_dir}; nothing to link"
            )
        return InstitutionalLinker(manifests, self.contracts_dir).link().edges


@dataclass
class DisabledEdgeResolution:
    """Damaged state: the target capability is absent.

    This is the deliberate loss the episode detects. It is not a mock of the
    linker and does not return a plausible-looking degraded answer — the
    capability simply is not there.
    """

    capability: str = "institutional.cross_organ_edge_resolution"

    @property
    def provider_id(self) -> str:
        return f"DISABLED:{self.capability}"

    def resolve_edges(self) -> list[Edge]:
        raise EdgeResolutionUnavailable(
            f"capability {self.capability!r} is disabled for this episode"
        )
