"""The typed seams Part 2 binds to.

`handoff/contract.json` names the components ChatGPT owns — the governed module
loader, the MCP/A2A boundary, and containment tier selection — and says they bind
to the kernel's read models. Until now that binding was described in prose. A
docstring is not a seam: it cannot be checked, and two collaborators reading the
same paragraph can still build to different shapes.

These Protocols are the shape. They are structural, so nothing in `discovery/`,
`knowledge/` or `routing/` imports this package or inherits from anything here —
the kernel components stay independent, and conformance is verified rather than
declared. A Part 2 component that type-checks against these Protocols will bind
to the real implementations without renegotiating anything.

Three rules the Protocols encode, not merely mention:

1. **Nothing here returns a grant.** `CapabilityDirectory` answers questions about
   what exists and what authority it *would* require. There is no method that
   confers any of it.
2. **Selection is not execution.** `Selector.route` returns a decision object.
   There is deliberately no `resolve`, no `execute`, no `invoke` — the omission is
   the contract, and it is what separates the canonical decision router from the
   provider-invoking router in draft PR #70 (see BLK-1).
3. **Provenance is mandatory.** `ProvenanceGraph` nodes carry a source; the
   Protocol requires the accessor so a consumer can always ask where a fact came
   from.

`runtime_checkable` is used so a conformance test can assert the real classes
satisfy these shapes. Note the standard caveat: `isinstance` against a runtime
Protocol checks method *presence*, not signatures. The tests in
`tests/unit/test_seams.py` therefore check signatures explicitly rather than
trusting `isinstance` alone.
"""
from __future__ import annotations

from typing import Any, Iterable, Protocol, runtime_checkable


@runtime_checkable
class CapabilityAdvertisementLike(Protocol):
    """One capability an organ declares. Carries no permission."""

    capability_id: str
    organ_id: str
    consumes: tuple[str, ...]
    produces: tuple[str, ...]
    lifecycle: str
    max_consequence_class: str
    requires_kernel_gate: bool

    def within(self, consequence_class: str) -> bool:
        """Would this capability's ceiling admit `consequence_class`?

        A truthful answer to a question, never an authorization.
        """
        ...


@runtime_checkable
class CapabilityDirectory(Protocol):
    """What a governed module loader needs before proposing an attachment.

    Deliberately absent: any method that issues, grants, approves or activates.
    Discovery does not grant access (FBO §4.10), and the Protocol makes that a
    type-level fact rather than a convention.
    """

    def lookup(self, capability_id: str) -> CapabilityAdvertisementLike:
        """One capability by id. Unknown ids raise; they are never approximated."""
        ...

    def offers(self, query: Any = None) -> tuple[CapabilityAdvertisementLike, ...]:
        """Every advertisement matching every supplied field of `query`."""
        ...

    def implementations_of(self, contract: str) -> tuple[CapabilityAdvertisementLike, ...]:
        """Every capability producing `contract` — a selector's candidate set."""
        ...

    def identity_reconciliation(self) -> dict:
        """Manifest publication versus identity registration, reported separately.

        A manifest is discovery-only. It implies neither institutional identity
        nor activation, and a loader must not treat one as the other (BLK-5).
        """
        ...


@runtime_checkable
class RoutingDecisionLike(Protocol):
    """A recommendation and its rationale. Confers nothing."""

    contract: str
    selected: str | None
    authorizes: None

    @property
    def is_refusal(self) -> bool:
        """True when no candidate may serve the request. A valid, final answer."""
        ...

    def explain(self) -> str: ...

    def to_dict(self) -> dict: ...


@runtime_checkable
class Selector(Protocol):
    """Chooses among competing implementations. Never invokes one.

    There is no `resolve`, `execute`, `invoke`, `run` or `apply` on this Protocol,
    and that absence is the whole point: a Part 2 component typed against
    `Selector` cannot call through to a provider, because the seam does not offer
    a way to. Execution requires a capability grant and the Consequence Gate,
    obtained elsewhere.
    """

    def route(self, criteria: Any, candidates: Iterable[Any] | None = None
              ) -> RoutingDecisionLike:
        """Rank admissible candidates and record the decision."""
        ...

    @property
    def decisions(self) -> tuple[RoutingDecisionLike, ...]:
        """Every decision made, in order (FBO §4.14 requires they be recorded)."""
        ...

    def outcomes_compared(self) -> int:
        """How many decisions have been compared against real outcomes."""
        ...


@runtime_checkable
class ProvenanceNodeLike(Protocol):
    """A graph node that can always say where it came from."""

    node_id: str
    label: str

    @property
    def key(self) -> str: ...


@runtime_checkable
class ProvenanceGraph(Protocol):
    """A read-only, provenance-carrying projection of institutional structure.

    Exposes no writer. A consumer reads and traverses; to see change it rebuilds.
    """

    def node(self, key: str) -> ProvenanceNodeLike: ...

    def nodes(self, kind: Any = None) -> tuple[ProvenanceNodeLike, ...]: ...

    def neighbours(self, key: str, relation: str | None = None
                   ) -> tuple[ProvenanceNodeLike, ...]: ...

    def path_exists(self, source: str, target: str, max_depth: int = 12) -> bool: ...

    def unpopulated(self) -> tuple[str, ...]:
        """Node kinds with no instances — honest emptiness, not missing features."""
        ...

    def summary(self) -> dict: ...


#: The Part 2 components named in handoff/contract.json, and the seam each binds to.
#: A conformance test asserts every seam here is satisfied by a real kernel class.
PART_2_BINDINGS: dict[str, str] = {
    "moduleloader": "CapabilityDirectory",
    "boundary": "CapabilityDirectory",
    "containment": "CapabilityDirectory",
    "any component selecting among implementations": "Selector",
    "any component reading institutional structure": "ProvenanceGraph",
}

__all__ = [
    "CapabilityAdvertisementLike", "CapabilityDirectory",
    "RoutingDecisionLike", "Selector",
    "ProvenanceNodeLike", "ProvenanceGraph",
    "PART_2_BINDINGS",
]
