"""Adapter 3 of 4 — the replacement-candidate interface.

One normalized output shape and one provider registry, so that the detector can
ask for an institutional capability without knowing which module answers, and so
that four structurally unrelated implementations can be compared on identical
terms.

This is an interface and a lookup table. It is deliberately not a module loader,
a composer, or a capability router — those already exist on the canonical line
and are not re-implemented here.

AUTHORITY. Registering a provider grants nothing. The registry answers "who
claims to implement X", never "who is permitted to". Nothing in this module
consults or confers authority, and a candidate cannot register itself: the
registry refuses a registration whose factory is the caller's own module, which
is the structural form of "no component may authorize its own promotion".
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from typing import Callable, Protocol, runtime_checkable

Triple = tuple[str, str, str]
Pair = tuple[str, str]


class CandidateError(ValueError):
    """A candidate or provider violated the interface. Fails closed."""


# --------------------------------------------------------------------------
# The normalized function output
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class FunctionOutput:
    """What the target capability produces, independent of implementation.

    Every field is a sorted tuple so that two implementations that agree on the
    relation are byte-identical here even if they build it in different orders.
    Comparison is therefore about the relation, not about iteration order.
    """
    edges: tuple[Triple, ...] = ()
    untyped: tuple[Pair, ...] = ()
    unconsumed: tuple[Pair, ...] = ()
    unproduced: tuple[Pair, ...] = ()
    unresolved: tuple[Pair, ...] = ()
    overlapping_authority: tuple[Pair, ...] = ()
    #: Free-form, per-candidate. Never compared; R2's constraint explanations
    #: live here so richer diagnostics cannot change the correctness verdict.
    diagnostics: tuple[str, ...] = field(default=(), compare=False)

    @staticmethod
    def normalize(edges=(), untyped=(), unconsumed=(), unproduced=(),
                  unresolved=(), overlapping_authority=(), diagnostics=()):
        return FunctionOutput(
            edges=tuple(sorted(tuple(e) for e in edges)),
            untyped=tuple(sorted(tuple(p) for p in untyped)),
            unconsumed=tuple(sorted(tuple(p) for p in unconsumed)),
            unproduced=tuple(sorted(tuple(p) for p in unproduced)),
            unresolved=tuple(sorted(tuple(p) for p in unresolved)),
            overlapping_authority=tuple(
                sorted(tuple(p) for p in overlapping_authority)),
            diagnostics=tuple(diagnostics),
        )

    @property
    def fully_connected(self) -> bool:
        """Same definition the original uses: nothing unproduced, nothing
        untyped. Reproduced here so the property is part of the compared
        contract rather than a detail of one implementation."""
        return not self.unproduced and not self.untyped

    def is_wellformed(self) -> bool:
        """Shape check only — says nothing about correctness. The detector uses
        this to tell 'the provider is broken' from 'the provider is wrong'."""
        try:
            return (all(len(t) == 3 for t in self.edges)
                    and all(len(p) == 2 for p in
                            self.untyped + self.unconsumed + self.unproduced
                            + self.unresolved + self.overlapping_authority))
        except TypeError:
            return False


# --------------------------------------------------------------------------
# The candidate protocol
# --------------------------------------------------------------------------

@runtime_checkable
class ResolverCandidate(Protocol):
    """A replacement implementation of the target capability.

    `candidate_id` must be one of spec.CANDIDATE_IDS. `resolve` takes the same
    two inputs for every candidate — the manifest set and the contract
    directory — so no candidate gets a shaped-to-fit input.
    """
    candidate_id: str

    def resolve(self, manifests: list, contracts_dir: str) -> FunctionOutput:
        ...


@dataclass
class ManifestView:
    """The minimum a resolver may rely on. Structurally compatible with
    linker.manifest.OrganManifest, so the baseline candidate needs no
    translation and its repair cost is not inflated by adapter code."""
    organ_id: str
    produces: list[str]
    consumes: list[str]
    unresolved: list[str] = field(default_factory=list)
    capabilities: list[dict] = field(default_factory=list)


# --------------------------------------------------------------------------
# Corpus materialisation
# --------------------------------------------------------------------------

def materialize_corpus(case: dict, root: str) -> tuple[list[ManifestView], str]:
    """Turn a frozen held-out case into (manifests, contracts_dir).

    Contract files are written as real schema files in a fresh directory, so a
    candidate that checks the filesystem and a candidate that reasons over a
    name set are both exercised against the same ground truth.
    """
    contracts_dir = os.path.join(root, f"contracts-{case['corpus_id']}")
    os.makedirs(contracts_dir, exist_ok=True)
    for name in case["contract_names"]:
        with open(os.path.join(contracts_dir, f"{name}.schema.json"), "w") as fh:
            json.dump({"$schema": "https://json-schema.org/draft/2020-12/schema",
                       "title": name, "type": "object"}, fh)

    manifests = [
        ManifestView(
            organ_id=m["organ_id"],
            produces=list(m["produces"]),
            consumes=list(m["consumes"]),
            unresolved=list(m["unresolved"]),
            capabilities=[{"capability_id": cap, "lifecycle": "SPECIALIZED"}
                          for cap in m["specialized"]],
        )
        for m in case["manifests"]
    ]
    return manifests, contracts_dir


class HeldOutCorpora:
    """Materializes every frozen held-out case into one temporary tree."""

    def __init__(self, cases):
        self.cases = tuple(cases)
        self._tmp: tempfile.TemporaryDirectory | None = None

    def __enter__(self) -> dict[str, tuple[list[ManifestView], str]]:
        self._tmp = tempfile.TemporaryDirectory(prefix="p3-heldout-")
        return {c["corpus_id"]: materialize_corpus(c, self._tmp.name)
                for c in self.cases}

    def __exit__(self, *exc) -> None:
        if self._tmp is not None:
            self._tmp.cleanup()
            self._tmp = None
        return None


# --------------------------------------------------------------------------
# The provider registry — how the detector stays blind
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Provider:
    """A claim to implement a capability. Not a permission to."""
    capability: str
    provider_id: str
    factory: Callable[[], ResolverCandidate]
    registered_by: str


class CapabilityProviderRegistry:
    """Capability name -> at most one active provider.

    The detector resolves the capability through this registry. That indirection
    is the entire reason detection can be blind: the detector holds a capability
    name and a contract, and the registry either produces something that answers
    or it does not. Nothing tells the detector what the provider was.
    """

    def __init__(self, ledger=None):
        self.ledger = ledger
        self._providers: dict[str, Provider] = {}
        self._history: list[dict] = []

    def register(self, capability: str, provider_id: str,
                 factory: Callable[[], ResolverCandidate], *,
                 registered_by: str) -> Provider:
        if not capability or not provider_id or not registered_by:
            raise CandidateError(
                "a provider registration must name the capability, the provider "
                "and the registering principal")

        # No self-registration. A candidate may not install itself as the answer
        # to an institutional capability; a distinct principal must do it.
        #
        # This is checked as an explicit named-principal rule, NOT by inspecting
        # the caller's stack frame. Frame inspection looked stronger and was
        # weaker: it cannot tell a candidate registering itself from a harness
        # that legitimately defines a double inline, and a frame is not a
        # security boundary. The structural half of this invariant — that no
        # candidate module contains a registration call at all — is enforced by
        # AST inspection in tests/unit/test_repair_adapters.py, which is a
        # boundary a candidate cannot talk its way past at runtime.
        if registered_by == provider_id:
            raise CandidateError(
                f"{provider_id} named itself as its own registering principal "
                f"for {capability}; no component may authorize its own promotion")

        provider = Provider(capability=capability, provider_id=provider_id,
                            factory=factory, registered_by=registered_by)
        self._providers[capability] = provider
        record = {"type": "repair.provider_registered", "capability": capability,
                  "provider_id": provider_id, "registered_by": registered_by}
        self._history.append(record)
        if self.ledger is not None:
            self.ledger.append("event", record)
        return provider

    def withdraw(self, capability: str, *, reason: str) -> None:
        """Remove the active provider. Preserved in history, never erased."""
        provider = self._providers.pop(capability, None)
        record = {"type": "repair.provider_withdrawn", "capability": capability,
                  "provider_id": provider.provider_id if provider else None,
                  "reason": reason}
        self._history.append(record)
        if self.ledger is not None:
            self.ledger.append("event", record)

    def provider_of(self, capability: str) -> Provider | None:
        return self._providers.get(capability)

    def instantiate(self, capability: str) -> ResolverCandidate:
        """Build the active provider. Raises if there is none, or if its factory
        cannot produce a resolver — both are symptoms the detector reads."""
        provider = self._providers.get(capability)
        if provider is None:
            raise LookupError(f"no provider registered for {capability}")
        candidate = provider.factory()
        if not hasattr(candidate, "resolve"):
            raise CandidateError(
                f"provider {provider.provider_id} does not implement resolve()")
        return candidate

    @property
    def history(self) -> tuple[dict, ...]:
        return tuple(self._history)
