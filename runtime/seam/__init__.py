"""P3 — the contract-to-runtime-event seam.

`P3_INSPECTION.md` measured two genuine absences: no binding exists anywhere
between a manifest **contract name** and a runtime **event type**, and the
kernel has no in-kernel consumer to deliver to. This package builds the first
absence and declares the second one explicitly rather than inventing it.

Three layers stay separate here, because collapsing any two of them is how a
routing experiment turns into theatre:

* **Structure** — the ``InstitutionalLinker`` proves an edge exists.
  A ``LinkReport`` is a statement about topology and nothing else.
* **Semantics** — a ``ConsumerBinding`` says which code actually receives the
  contract. Written by hand, never derived from string similarity.
* **Authority** — neither of the above grants any. Nothing in this package
  consults a gate, mints a permission, or widens a ceiling, and a test asserts
  it stays that way.

A route is materialised only when structure AND semantics both hold. Missing
either one fails closed as ``ROUTE_NOT_ESTABLISHED``.
"""
from runtime.seam.binding import (
    BindingError,
    ConsumerBinding,
    OrganEntryPoint,
    ProducerBinding,
    ResolvedEntryPoint,
)
from runtime.seam.router import (
    CONTRACT_DELIVERY_EVENT,
    BypassDetected,
    ContractRouter,
    DeliveryReceipt,
    Route,
    RouteNotEstablished,
)
from runtime.seam.topology import (
    DisabledEdgeResolution,
    EdgeResolutionUnavailable,
    LinkerTopology,
)

__all__ = [
    "BindingError",
    "BypassDetected",
    "CONTRACT_DELIVERY_EVENT",
    "ConsumerBinding",
    "ContractRouter",
    "DeliveryReceipt",
    "DisabledEdgeResolution",
    "EdgeResolutionUnavailable",
    "LinkerTopology",
    "OrganEntryPoint",
    "ProducerBinding",
    "ResolvedEntryPoint",
    "Route",
    "RouteNotEstablished",
]
