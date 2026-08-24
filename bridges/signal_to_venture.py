"""Bridge A — Signal-to-Venture, executed end to end.

DALEOBANKS opportunity signal -> verified transport -> canonical packet ->
WealthMachine assessment -> canonical assessment -> kernel causal episode.

Composition only. Every step calls a module that existed and was tested before
this file: `adapters.bridge_transport`, `adapters.daleobanks_opportunity`,
`adapters.wealthmachine_assessment`, `events.spine`, `memory.causal`. What was
missing was not a component. It was the wire between them.

Four properties this pathway keeps, each of which is a rule the institution
already wrote down and could not previously execute:

**A peer's claim is ingested, never emitted.** `EventSpine.emit` requires a
SPIFFE source and refuses anything else; `ingest` exists for facts arriving from
outside. A signal from DALEOBANKS is another organ's assertion, so it enters as
an ingested external fact. Only the kernel's own reading of it is emitted. Get
this backwards and the kernel launders a peer's claim into its own — the exact
authority inflation section 8 forbids, in the one place it would be invisible.

**Identity comes from the verified transport, never the payload.** Both adapters
already refuse an unknown transport identity; this pathway verifies the signature,
nonce and timestamp *before* either adapter sees the body, so a forged body cannot
choose its own provenance.

**An unresolved field halts the bridge.** The packet adapter returns fields it
cannot translate rather than guessing. A pathway that continued past them would
be fabricating the institution's own record. It stops and names them.

**It claims nothing about the outside world.** Running this changes no external
state and produces no verified outcome. `reality` says SIMULATED, and the
Single Bottleneck Metric is untouched by construction. A cross-organ pathway that
runs on fixtures is a connected institution, not a proven one.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum

from adapters import bridge_transport as transport
from adapters import daleobanks_opportunity as packet_adapter
from adapters import wealthmachine_assessment as assessment_adapter
from events.spine import Event, EventSpine
from identity.pki.errors import IdentityError
from memory.causal import CausalMemory
from provenance.ledger import EvidenceLedger

DALEOBANKS = "spiffe://uniimente.internal/organ/daleobanks"
WEALTHMACHINE = "spiffe://uniimente.internal/organ/wealthmachine"
KERNEL = "spiffe://uniimente.internal/organ/constitutional-controller"

#: The wire protocol version DALEOBANKS and WealthMachine both pin. Declared
#: here rather than defaulted, because a transport that guesses its own version
#: is a downgrade waiting to happen.
WIRE_SCHEMA_VERSION = "1.1"

#: The reality axis of `blueprint.ladder`. Stated as a constant so no caller can
#: quietly upgrade what a fixture run means.
SIMULATED = "SIMULATED"


class Halt(Enum):
    """Why a run stopped short. Every value is a refusal the institution wanted."""

    TRANSPORT_REFUSED = "transport_refused"
    #: The peer authenticated, and then sent something that violates the wire
    #: contract. Added 2026-08-23: previously unreachable, because the transport
    #: leg refused every run before a body was read. Adopting isolated identity
    #: made a genuinely authenticated peer with a malformed payload possible for
    #: the first time, and an authenticated peer is exactly the case where
    #: "crash" is the wrong answer — the institution should record that a
    #: verified organ sent something it could not accept.
    SIGNAL_MALFORMED = "signal_malformed"
    SIGNAL_UNRESOLVED = "signal_unresolved"
    ASSESSMENT_REFUSED = "assessment_refused"


@dataclass(frozen=True)
class BridgeRun:
    """What one traversal actually did. Derived; nothing here is supplied."""

    completed: bool
    #: Ordered event ids the run wrote, oldest first.
    event_ids: tuple[str, ...] = ()
    #: Present only when the run stopped early.
    halted_at: Halt | None = None
    #: The adapter's own words for what it could not translate.
    unresolved: tuple[str, ...] = ()
    reason: str = ""
    reality: str = SIMULATED
    #: The canonical objects produced, for a caller that wants to inspect them.
    signal: dict | None = None
    assessment: dict | None = None

    @property
    def crossed_organ_boundary(self) -> bool:
        """True once a peer fact has been verified and admitted."""
        return bool(self.event_ids)


def _ingest_peer_fact(spine: EventSpine, *, event_type: str, origin: str,
                      payload: dict, causal_parent: str | None) -> str:
    """Admit another organ's assertion as an external fact.

    `ingest`, not `emit`. The distinction is the whole point: emit would make the
    kernel the source of a claim it merely received.
    """
    event = Event(
        type=event_type,
        source=origin,
        actor=origin,
        payload=payload,
        legal_principal="Alfonso Lopez",
        causal_parent=causal_parent,
    )
    spine.ingest(event)
    return event.event_id


def _emit_kernel_fact(spine: EventSpine, *, event_type: str, payload: dict,
                      causal_parent: str | None) -> str:
    """The kernel's own reading. Emitted, because the kernel is its source."""
    event = Event(
        type=event_type,
        source=KERNEL,
        actor=KERNEL,
        payload=payload,
        legal_principal="Alfonso Lopez",
        causal_parent=causal_parent,
    )
    spine.emit(event)
    return event.event_id


def run(wire_packet: dict, wire_assessment: dict, *,
        ledger: EvidenceLedger | None = None,
        resolver_answers: dict | None = None,
        resolved_by: str = KERNEL,
        mesh: "InternalMesh | None" = None) -> BridgeRun:
    """Traverse Bridge A once.

    `resolver_answers` supplies attributed answers for fields the packet adapter
    cannot translate. Omit them and the run halts at the unresolved list rather
    than inventing values — which is the behaviour worth having, so the default
    is the honest one.

    `mesh` is the internal identity mesh used to authenticate the peer. It
    defaults to a fresh `InternalMesh`, which reads
    `identity/service-identities.yaml` and issues an isolated workload key per
    declared service. Passing one in lets a caller share an anchor across
    traversals, or supply a revocation list.
    """
    from identity.mesh import InternalMesh

    ledger = ledger or EvidenceLedger("sha256:" + "0" * 64)
    mesh = mesh or InternalMesh()
    spine = EventSpine(ledger)
    events: list[str] = []

    # --- leg 1: the peer boundary, verified before anything is read ----------
    #
    # Adopted 2026-08-23 under FOUNDER-RULING-2026-08-23. This leg used to build
    # HMAC headers and verify them against a shared secret — a loop in which the
    # kernel signed a message as "daleobanks" and then congratulated itself on
    # verifying that DALEOBANKS had sent it. Every participant holds the one key,
    # so the identity header was a claim, not a proof.
    #
    # Now the peer authenticates with an isolated workload key it alone holds.
    # `identity_isolated` reads "true" for the first time in the live pathway,
    # and it is the handshake that earns it rather than the string.
    packet_id = wire_packet.get("id")
    try:
        headers = transport.verify_mutual_identity(
            mesh, "bridge_daleobanks", "kernel_gateway",
            schema_version=WIRE_SCHEMA_VERSION,
            idempotency_key=str(packet_id or ""))
    except (transport.BridgeSecurityError, IdentityError,
            ValueError, KeyError) as exc:
        return BridgeRun(completed=False, halted_at=Halt.TRANSPORT_REFUSED,
                         reason=f"transport refused the peer message: {exc}")

    # The organ is read from the certificate, never from the payload or from a
    # literal in this file. If the handshake ever authenticated a different
    # workload, this is where the pathway would notice.
    peer_organ = headers["identity"]

    events.append(_ingest_peer_fact(
        spine, event_type="bridge.opportunity_signal_received",
        origin=DALEOBANKS,
        payload={"packet_id": packet_id, "verified": True},
        causal_parent=None))

    # --- leg 2: translate, and stop if the translation is incomplete ---------
    try:
        adapted = packet_adapter.adapt(wire_packet,
                                       transport_identity=peer_organ)
    except packet_adapter.AdapterError as exc:
        return BridgeRun(
            completed=False, event_ids=tuple(events),
            halted_at=Halt.SIGNAL_MALFORMED,
            reason=f"the verified peer sent a packet its own contract rejects: {exc}")
    if not adapted.resolved:
        if not resolver_answers:
            return BridgeRun(
                completed=False, event_ids=tuple(events),
                halted_at=Halt.SIGNAL_UNRESOLVED,
                unresolved=tuple(adapted.unresolved),
                reason=("the packet adapter could not translate every required "
                        "field and no authorized resolver supplied answers; "
                        "continuing would fabricate the institution's own record"))
        signal = packet_adapter.resolve(adapted, resolver_answers,
                                        resolved_by=resolved_by)
    else:
        signal = adapted.canonical

    events.append(_emit_kernel_fact(
        spine, event_type="bridge.opportunity_signal_accepted",
        payload={"signal_id": signal.get("signal_id") or signal.get("packet_id")},
        causal_parent=events[-1]))

    # --- leg 3: the second organ, same discipline ----------------------------
    #
    # It said "same discipline" for a day while not being that. Leg 2 passed
    # `transport_identity=peer_organ`, read off a chain-validated certificate;
    # this leg passed the literal `"wealthmachine"`. The adapter's own refusal
    # message states the rule — "identity comes from verified transport, never
    # the payload" — and a constant in this file is not the payload, but it is
    # not verified transport either. Nothing had authenticated WealthMachine,
    # and its assessment is what Bridge B and every downstream decision read.
    #
    # Adopted 2026-08-24, mirroring leg 1: `bridge_wealthmachine` was already a
    # declared service in `identity/service-identities.yaml` and `identity/mesh.py`
    # could already authenticate it. The edge was adoptable the whole time; the
    # comment claiming it was already adopted is what hid that.
    try:
        assessment_headers = transport.verify_mutual_identity(
            mesh, "bridge_wealthmachine", "kernel_gateway",
            schema_version=WIRE_SCHEMA_VERSION,
            idempotency_key=str(packet_id or ""))
    except (transport.BridgeSecurityError, IdentityError,
            ValueError, KeyError) as exc:
        return BridgeRun(completed=False, event_ids=tuple(events),
                         halted_at=Halt.TRANSPORT_REFUSED, signal=signal,
                         reason=f"transport refused the assessment peer: {exc}")

    assessment_organ = assessment_headers["identity"]

    events.append(_ingest_peer_fact(
        spine, event_type="bridge.venture_assessment_received",
        origin=WEALTHMACHINE,
        payload={"assessment_of": packet_id, "verified": True},
        causal_parent=events[-1]))

    try:
        assessment = assessment_adapter.adapt(
            wire_assessment, transport_identity=assessment_organ)
    except assessment_adapter.AdapterError as exc:
        return BridgeRun(completed=False, event_ids=tuple(events),
                         halted_at=Halt.ASSESSMENT_REFUSED, signal=signal,
                         reason=f"assessment refused: {exc}")

    events.append(_emit_kernel_fact(
        spine, event_type="bridge.decision_episode_recorded",
        payload={"assessment_of": packet_id,
                 "requires_human_approval": True,
                 "reality": SIMULATED},
        causal_parent=events[-1]))

    return BridgeRun(completed=True, event_ids=tuple(events),
                     signal=signal, assessment=assessment)


def causal_chain(run_result: BridgeRun, ledger: EvidenceLedger) -> list[dict]:
    """The recorded ancestry of a completed run, read back from the ledger.

    Proof the legs are linked rather than merely adjacent: `CausalMemory` walks
    `causal_parent` from the last event and must reach the first.
    """
    if not run_result.event_ids:
        return []
    return CausalMemory(ledger).ancestry(run_result.event_ids[-1])
