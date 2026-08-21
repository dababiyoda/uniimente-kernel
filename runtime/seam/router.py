"""The seam itself: proven edge + declared binding -> a live event route.

Geometry B. There is exactly ONE event type — :data:`CONTRACT_DELIVERY_EVENT` —
and the contract name travels inside the payload as data. The rejected
alternative was minting an event type per contract by normalising the contract
string, which would have manufactured a namespace out of nothing and made
``wire-opportunity-packet`` look like evidence for an event called
``wire.opportunity_packet``. Contract names are data. Data does not become
identifiers.

What this module may do: read a proven topology, read declared bindings,
subscribe, deliver, and write receipts. What it may not do, and what
``tests/unit/test_seam_router.py`` asserts it does not do: consult a gate,
create a permission, alter a manifest, widen a ceiling, or produce an external
effect. Routing is not authorisation.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

from events.spine import SPIFFE_PREFIX, Event
from runtime.seam.binding import BindingError, ConsumerBinding
from runtime.seam.topology import EdgeResolutionUnavailable, TopologyProvider

#: Geometry B: one generic typed contract-delivery event for every contract.
CONTRACT_DELIVERY_EVENT = "institution.contract_delivery"

#: Source identity of the seam itself. It is an internal kernel component, so
#: it emits under a spiffe id; it is not an organ and never a legal principal.
SEAM_SOURCE = SPIFFE_PREFIX + "runtime/seam/contract_router"


class RouteNotEstablished(RuntimeError):
    """No route exists for this contract, so nothing was delivered.

    Distinct from a delivery that ran and produced nothing: the caller must be
    able to tell "the institution could not route this" from "the institution
    routed it and the consumer declined".
    """


class BypassDetected(RuntimeError):
    """A delivery reached the consumer through a path the binding forbids.

    The specific hazard this exists for: DALEOBANKS' ``WealthMachineClient``
    defaults to ``mock`` mode without credentials and computes a
    VentureAssessment locally. An episode routed through it would produce a
    perfectly valid-looking assessment while WealthMachineIntelligence was
    never invoked — and the counterfactual would prove nothing at all.
    """


class _ExecutionWitness:
    """Records which files actually executed during a delivery.

    The receipt must distinguish a real cross-repository invocation from a
    local mock, and neither the return value nor the binding's own claims can
    do that: a mock returns the same shape. What the profiler sees cannot be
    claimed, only performed.
    """

    def __init__(self) -> None:
        self.files: set[str] = set()
        self._prev = None

    def __enter__(self) -> "_ExecutionWitness":
        self._prev = sys.getprofile()
        sys.setprofile(self._record)
        return self

    def _record(self, frame, event, arg) -> None:
        if event == "call":
            self.files.add(frame.f_code.co_filename)

    def __exit__(self, *exc) -> bool:
        sys.setprofile(self._prev)
        return False


@dataclass(frozen=True)
class Route:
    """One materialised path. Every field is evidence, not configuration."""

    producer: str
    consumer: str
    contract: str
    schema_path: str
    binding: ConsumerBinding

    def describe(self) -> dict:
        return {
            "producer": self.producer,
            "consumer": self.consumer,
            "contract": self.contract,
            "schema_path": self.schema_path,
            "binding": self.binding.describe(),
        }


@dataclass
class DeliveryReceipt:
    """What happened, and how we know it was not a mock.

    ``authority_granted`` is hardcoded False and asserted by test. A receipt
    that could ever report otherwise would mean the seam had become a second
    grant path.
    """

    contract: str
    producer: str
    consumer: str
    event_id: str
    event_type: str
    delivered: bool
    result: object = None
    consumer_evidence: dict = field(default_factory=dict)
    witness_files: list[str] = field(default_factory=list)
    bypass_candidates: list[str] = field(default_factory=list)
    error: str | None = None
    workdir: str | None = None
    #: Organ-local files the delivery created. Reported rather than suppressed:
    #: a side effect nobody counted is the kind that later turns out to matter.
    files_written: list[str] = field(default_factory=list)
    at: str = field(
        default_factory=lambda: datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
    authority_granted: bool = False

    def describe(self) -> dict:
        d = {
            "contract": self.contract,
            "producer": self.producer,
            "consumer": self.consumer,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "delivered": self.delivered,
            "consumer_evidence": self.consumer_evidence,
            "witness_file_count": len(self.witness_files),
            "bypass_candidates": self.bypass_candidates,
            "authority_granted": self.authority_granted,
            "files_written": self.files_written,
            "at": self.at,
        }
        if self.error:
            d["error"] = self.error
        return d

    def executed_in(self, repository_root: str) -> list[str]:
        root = os.path.abspath(repository_root) + os.sep
        return sorted(f for f in self.witness_files if f.startswith(root))


class ContractRouter:
    """Materialises subscriptions where structure and semantics both hold."""

    def __init__(self, spine, topology: TopologyProvider,
                 bindings: list[ConsumerBinding], *, workdir: str | None = None) -> None:
        """``workdir`` contains organ-local file writes during delivery.

        Not cosmetic. WealthMachineIntelligence's agent store resolves
        ``data/agent_store.jsonl`` against the current working directory, so
        the first run of this episode deposited a JSONL file inside the kernel
        repository. ``CONSEQUENCE_CLASS = INERT`` has to mean more than "it
        only wrote a log into our own checkout": the write is redirected here
        and then reported on the receipt, which turns an accidental side effect
        into measured evidence.

        Defaults to None (no redirection) so the router imposes no
        process-global state on callers that do not ask for it.
        """
        self.spine = spine
        self.topology = topology
        self.workdir = workdir
        self.bindings = list(bindings)
        self.routes: list[Route] = []
        self.refused: list[tuple[ConsumerBinding, str]] = []
        self.topology_error: str | None = None
        self._pending: DeliveryReceipt | None = None
        self._materialised = False

    # -- materialisation ----------------------------------------------------
    def materialise(self) -> list[Route]:
        """Subscribe only where a proven edge and a resolvable binding meet.

        Refusals are recorded with a reason rather than dropped. A binding that
        silently fails to route is indistinguishable from one that was never
        declared, and the counterfactual depends on telling those apart.
        """
        self._materialised = True
        self.routes, self.refused, self.topology_error = [], [], None

        try:
            edges = self.topology.resolve_edges()
        except EdgeResolutionUnavailable as exc:
            self.topology_error = str(exc)
            for b in self.bindings:
                self.refused.append((b, f"ROUTE_NOT_ESTABLISHED: {exc}"))
            return []

        for binding in self.bindings:
            matching = [
                e for e in edges
                if e.consumer == binding.organ_id and e.contract == binding.contract
            ]
            if not matching:
                self.refused.append((
                    binding,
                    f"no linker-proven edge delivers {binding.contract!r} to "
                    f"{binding.organ_id!r}; binding refused",
                ))
                continue
            try:
                call, resolved, instance = binding.bind()
            except BindingError as exc:
                self.refused.append((binding, f"binding did not resolve: {exc}"))
                continue

            for edge in matching:
                route = Route(
                    producer=edge.producer, consumer=edge.consumer,
                    contract=edge.contract, schema_path=edge.schema_path,
                    binding=binding,
                )
                self.routes.append(route)
                self.spine.subscribe(
                    CONTRACT_DELIVERY_EVENT,
                    self._handler(route, call, resolved, instance),
                )
        return self.routes

    @staticmethod
    def _written_under(workdir: str | None) -> list[str]:
        if not workdir or not os.path.isdir(workdir):
            return []
        out = []
        for root, _dirs, files in os.walk(workdir):
            for name in files:
                out.append(os.path.relpath(os.path.join(root, name), workdir))
        return sorted(out)

    def route_for(self, contract: str, producer: str) -> Route | None:
        for r in self.routes:
            if r.contract == contract and r.producer == producer:
                return r
        return None

    # -- delivery -----------------------------------------------------------
    def _handler(self, route: Route, call, resolved, instance):
        """Geometry B dispatch: filter on payload data, not on event type.

        Every contract-delivery event reaches every handler, exactly because
        there is only one event type. The handler decides by reading the
        contract name out of the payload — which is what keeping contract names
        as data costs, and it is a cheap price for not inventing a namespace.
        """

        def handle(event: Event) -> None:
            payload = event.payload
            if payload.get("contract") != route.contract:
                return
            if payload.get("producer") != route.producer:
                return

            entry = route.binding.entry_point
            receipt = DeliveryReceipt(
                contract=route.contract, producer=route.producer,
                consumer=route.consumer, event_id=event.event_id,
                event_type=event.type, delivered=False,
                consumer_evidence={**resolved.describe(), **instance},
            )
            failure: Exception | None = None
            result = None
            previous_cwd = os.getcwd()
            if self.workdir:
                os.chdir(self.workdir)
            try:
                with _ExecutionWitness() as witness:
                    try:
                        result = call(payload["body"])
                    except Exception as exc:              # consumer's own failure
                        failure = exc
            finally:
                os.chdir(previous_cwd)

            receipt.witness_files = sorted(witness.files)
            receipt.workdir = self.workdir
            receipt.files_written = self._written_under(self.workdir)
            receipt.bypass_candidates = sorted(
                f for f in receipt.witness_files
                if any(frag in f for frag in entry.forbidden_fragments)
            )
            # Checked before the consumer's own error is reported: a delivery
            # that reached the mock and then crashed still reached the mock,
            # and that is the more important fact about it.
            if receipt.bypass_candidates:
                receipt.error = (
                    "BYPASS_DETECTED: the delivery executed "
                    f"{receipt.bypass_candidates}, which this binding forbids"
                )
                self._pending = receipt
                raise BypassDetected(receipt.error)

            if failure is not None:
                receipt.error = f"{type(failure).__name__}: {failure}"
                self._pending = receipt
                return

            if not receipt.executed_in(resolved.repository_root):
                receipt.error = (
                    "VACUOUS_DELIVERY: nothing under "
                    f"{resolved.repository_root} executed, so the consumer "
                    "cannot have produced this result"
                )
                self._pending = receipt
                raise BypassDetected(receipt.error)

            receipt.delivered = True
            receipt.result = result
            self._pending = receipt

        return handle

    def deliver(self, contract: str, body: dict, *, producer: str,
                actor: str, legal_principal: str) -> DeliveryReceipt:
        """Emit one contract-delivery event and return its receipt.

        Fails closed: with no materialised route the payload is not emitted at
        all, so a damaged topology cannot leak work onto the spine and have it
        picked up by something else.
        """
        if not self._materialised:
            raise RouteNotEstablished(
                "router.materialise() has not run; refusing to deliver against "
                "an unexamined topology"
            )
        route = self.route_for(contract, producer)
        if route is None:
            reason = self.topology_error or (
                f"no materialised route for {contract!r} from {producer!r}"
            )
            raise RouteNotEstablished(f"ROUTE_NOT_ESTABLISHED: {reason}")

        self._pending = None
        event = Event(
            type=CONTRACT_DELIVERY_EVENT,
            source=SEAM_SOURCE,
            actor=actor,
            legal_principal=legal_principal,
            sensitivity="internal",
            payload={
                # The contract name is DATA. It never becomes an event type.
                "contract": contract,
                "producer": route.producer,
                "consumer": route.consumer,
                "schema_path": route.schema_path,
                "topology_provider": self.topology.provider_id,
                "body": body,
            },
        )
        self.spine.emit(event)
        if self._pending is None:                     # pragma: no cover - defensive
            raise RouteNotEstablished(
                "the event was emitted but no handler produced a receipt; the "
                "subscription is not live"
            )
        return self._pending

    # -- reporting ----------------------------------------------------------
    def describe(self) -> dict:
        return {
            "topology_provider": self.topology.provider_id,
            "topology_error": self.topology_error,
            "event_type": CONTRACT_DELIVERY_EVENT,
            "routes": [r.describe() for r in self.routes],
            "refused": [
                {"binding": b.describe(), "reason": why} for b, why in self.refused
            ],
        }
