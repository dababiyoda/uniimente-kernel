"""Fail-closed binding between linker-proven contracts and the EventSpine.

This is a routing seam, not a new event bus, policy engine, authority source,
or execution gate. A delivery can occur only when the canonical
``InstitutionalLinker`` produced one exact producer-contract-consumer edge and
the registered callable has the exact implementation reference declared by the
episode. Contract names remain data inside one generic event type. They are
never converted into event names by spelling convention.

This P3 seam accepts only an ``INERT`` consequence classification. It routes an
internal wire payload to an already-existing consumer and records
request/result provenance on the existing ``EventSpine``. It grants no
capability and cannot flush an external outbox. The enclosing episode must
still prove that the registered implementation is actually inert.
"""
from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from events.spine import Event, EventSpine, SPIFFE_PREFIX
from linker.linker import Edge, LinkReport


CONTRACT_DELIVERY_EVENT = "contract.delivery"
CONTRACT_RESULT_EVENT = "contract.delivery_completed"
INERT_CONSEQUENCE_CLASS = "INERT"


class ContractRouteError(ValueError):
    """A contract delivery could not be proven safe enough to route."""


@dataclass(frozen=True, order=True)
class RouteKey:
    producer: str
    contract: str
    consumer: str


@dataclass(frozen=True)
class ConsumerBinding:
    key: RouteKey
    handler_ref: str
    producer_revision: str
    consumer_revision: str
    consequence_class: str
    schema_path: str
    schema_sha256: str

    def provenance(self) -> dict[str, str]:
        return {
            "producer": self.key.producer,
            "producer_revision": self.producer_revision,
            "contract": self.key.contract,
            "schema_path": self.schema_path,
            "schema_sha256": self.schema_sha256,
            "consumer": self.key.consumer,
            "consumer_revision": self.consumer_revision,
            "handler_ref": self.handler_ref,
            "consequence_class": self.consequence_class,
        }


@dataclass(frozen=True)
class DeliveryResult:
    request_event_id: str
    result_event_id: str
    binding: ConsumerBinding
    output: dict[str, Any]


def callable_ref(handler: Callable[[dict[str, Any]], dict[str, Any]]) -> str:
    """Return a stable Python implementation reference or fail closed."""
    module = getattr(handler, "__module__", "")
    qualname = getattr(handler, "__qualname__", "")
    if (
        not module
        or not qualname
        or "<lambda>" in qualname
        or "<locals>" in qualname
    ):
        raise ContractRouteError("consumer must be a stable module-level or bound method")
    return f"{module}.{qualname}"


def _schema_digest(edge: Edge) -> str:
    path = Path(edge.schema_path)
    if not path.is_file():
        raise ContractRouteError(f"linked schema is no longer readable: {edge.schema_path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _schema_locator(edge: Edge) -> str:
    """Return a checkout-independent locator for the linked contract."""
    return f"contracts/{Path(edge.schema_path).name}"


class ContractEventRouter:
    """Materialize exact linker edges as internal EventSpine deliveries."""

    def __init__(self, spine: EventSpine, report: LinkReport) -> None:
        self.spine = spine
        self.report = report
        self._edges: dict[RouteKey, Edge] = {}
        self._bindings: dict[RouteKey, tuple[ConsumerBinding, Callable]] = {}
        self._results: dict[str, dict[str, Any]] = {}

        for edge in report.edges:
            key = RouteKey(edge.producer, edge.contract, edge.consumer)
            if key in self._edges:
                raise ContractRouteError(f"ambiguous duplicate linker edge: {key}")
            self._edges[key] = edge

    def bind(
        self,
        *,
        producer: str,
        contract: str,
        consumer: str,
        handler: Callable[[dict[str, Any]], dict[str, Any]],
        handler_ref: str,
        producer_revision: str,
        consumer_revision: str,
        consequence_class: str,
    ) -> ConsumerBinding:
        """Bind a real consumer only to one exact linker-proven edge."""
        key = RouteKey(producer, contract, consumer)
        edge = self._edges.get(key)
        if edge is None:
            raise ContractRouteError(f"linker did not prove route: {key}")
        if key in self._bindings:
            raise ContractRouteError(f"route already bound: {key}")
        if not producer.startswith(SPIFFE_PREFIX) or not consumer.startswith(
            SPIFFE_PREFIX
        ):
            raise ContractRouteError(
                "producer and consumer must be kernel-recognized SPIFFE organ ids"
            )
        if producer == consumer:
            raise ContractRouteError("contract delivery must cross an organ boundary")
        if not producer_revision or not consumer_revision:
            raise ContractRouteError("both organ revisions are required for provenance")
        if consequence_class != INERT_CONSEQUENCE_CLASS:
            raise ContractRouteError("P3 contract delivery permits only INERT consequences")

        observed_ref = callable_ref(handler)
        if observed_ref != handler_ref:
            raise ContractRouteError(
                f"consumer implementation mismatch: expected {handler_ref}, observed {observed_ref}"
            )

        binding = ConsumerBinding(
            key=key,
            handler_ref=handler_ref,
            producer_revision=producer_revision,
            consumer_revision=consumer_revision,
            consequence_class=consequence_class,
            schema_path=_schema_locator(edge),
            schema_sha256=_schema_digest(edge),
        )

        def receive(event: Event) -> None:
            if event.type != CONTRACT_DELIVERY_EVENT:
                return
            if event.source != binding.key.producer:
                return
            route = event.payload.get("route")
            if route != binding.provenance():
                return
            body = event.payload.get("body")
            if not isinstance(body, dict):
                raise ContractRouteError("wire payload must be an object")
            output = handler(copy.deepcopy(body))
            if not isinstance(output, dict):
                raise ContractRouteError("contract consumer must return a wire object")
            self._results[event.event_id] = copy.deepcopy(output)

        self.spine.subscribe(CONTRACT_DELIVERY_EVENT, receive)
        self._bindings[key] = (binding, handler)
        return binding

    def deliver(
        self,
        *,
        producer: str,
        contract: str,
        consumer: str,
        body: dict[str, Any],
        actor: str,
        legal_principal: str,
        sensitivity: str = "internal",
    ) -> DeliveryResult:
        """Route one internal request and ledger both request and result."""
        key = RouteKey(producer, contract, consumer)
        bound = self._bindings.get(key)
        if bound is None:
            raise ContractRouteError(f"route is not bound: {key}")
        if not isinstance(body, dict):
            raise ContractRouteError("wire payload must be an object")

        binding, _handler = bound
        request = self.spine.emit(Event(
            type=CONTRACT_DELIVERY_EVENT,
            source=producer,
            actor=actor,
            legal_principal=legal_principal,
            sensitivity=sensitivity,
            payload={"route": binding.provenance(), "body": copy.deepcopy(body)},
        ))
        output = self._results.pop(request.event_id, None)
        if output is None:
            raise ContractRouteError("proven route produced no consumer result")

        result = self.spine.emit(Event(
            type=CONTRACT_RESULT_EVENT,
            source=consumer,
            actor=actor,
            legal_principal=legal_principal,
            sensitivity=sensitivity,
            causal_parent=request.event_id,
            payload={
                "route": binding.provenance(),
                "request_event_id": request.event_id,
                "body": copy.deepcopy(output),
            },
        ))
        return DeliveryResult(
            request_event_id=request.event_id,
            result_event_id=result.event_id,
            binding=binding,
            output=output,
        )


__all__ = [
    "CONTRACT_DELIVERY_EVENT",
    "CONTRACT_RESULT_EVENT",
    "INERT_CONSEQUENCE_CLASS",
    "ContractRouteError",
    "RouteKey",
    "ConsumerBinding",
    "DeliveryResult",
    "ContractEventRouter",
    "callable_ref",
]
