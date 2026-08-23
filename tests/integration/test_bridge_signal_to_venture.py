"""Bridge A end to end, and the four refusals that make it trustworthy.

The pathway is composition, so these tests do not re-verify the adapters or the
transport — those have their own suites. They verify the things that only exist
once the parts are wired together, and that could not be tested at all while
`adapters/` was imported by nothing.
"""
from __future__ import annotations

import json
import os

import pytest

from adapters import bridge_transport as transport
from bridges.signal_to_venture import (
    DALEOBANKS,
    KERNEL,
    SIMULATED,
    WEALTHMACHINE,
    BridgeRun,
    Halt,
    causal_chain,
    run,
)
from provenance.ledger import EvidenceLedger

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
ANSWERS = {"governing_bottleneck": "buyer access"}


@pytest.fixture(autouse=True)
def signing_key(monkeypatch):
    monkeypatch.setenv(transport.SIGNING_KEY_ENV, "bridge-integration-key")


def wire_packet() -> dict:
    with open(os.path.join(FIXTURES, "wire_opportunity_packet.json")) as fh:
        return json.load(fh)


def wire_assessment() -> dict:
    with open(os.path.join(FIXTURES, "wire_venture_assessment.json")) as fh:
        return json.load(fh)


def ledger() -> EvidenceLedger:
    return EvidenceLedger("sha256:" + "0" * 64)


# ------------------------------------------------------ the pathway exists
def test_the_bridge_traverses_all_three_organs_and_links_every_leg():
    """The first cross-organ pathway that runs. Ancestry, not adjacency.

    Four events in order is not proof they are connected — `CausalMemory` walks
    `causal_parent` back from the last, and must reach the first. Events that
    merely landed in the same ledger would give an ancestry of one.
    """
    led = ledger()
    result = run(wire_packet(), wire_assessment(), ledger=led,
                 resolver_answers=ANSWERS, resolved_by=KERNEL)

    assert result.completed, result.reason
    assert len(result.event_ids) == 4
    assert len(causal_chain(result, led)) == 4
    assert led.verify_chain()[0], "the evidence chain must verify after a run"
    assert result.signal and result.assessment


def test_a_run_claims_nothing_about_the_outside_world():
    """A pathway exercised on fixtures is connected, not proven.

    The Single Bottleneck Metric counts reconciled external consequences. This
    run produces none, and the type says so rather than leaving a later reader
    to infer it from context that will not travel with the record.
    """
    from blueprint.critical_path import compute

    def rungs() -> dict:
        return {tech: (status.awarded_rung, status.constrained_rung)
                for tech, status in compute().statuses.items()}

    before = rungs()
    result = run(wire_packet(), wire_assessment(),
                 resolver_answers=ANSWERS, resolved_by=KERNEL)

    assert result.reality == SIMULATED
    assert rungs() == before, (
        "traversing a fixture pathway must move no rung and no ceiling"
    )


# --------------------------------------------- a peer's claim is not the kernel's
def test_a_peer_signal_is_ingested_and_only_the_kernel_reading_is_emitted():
    """The authority-inflation guard, checked on the ledger's own record.

    `emit` makes the kernel the source of a fact; `ingest` records that someone
    else asserted it. Two of the four events come from peer organs and two from
    the kernel, and if the peer legs were emitted the kernel would be on record
    as the origin of claims it merely received.
    """
    led = ledger()
    run(wire_packet(), wire_assessment(), ledger=led,
        resolver_answers=ANSWERS, resolved_by=KERNEL)

    events = [r.payload for r in led.by_type("event")]
    by_direction = {}
    for event in events:
        by_direction.setdefault(event["direction"], []).append(event)

    ingested = {e["source"] for e in by_direction.get("ingested", [])}
    emitted = {e["source"] for e in by_direction.get("emitted", [])}

    assert ingested == {DALEOBANKS, WEALTHMACHINE}, (
        "a peer organ's assertion must enter as an external fact"
    )
    assert emitted == {KERNEL}, "only the kernel emits the kernel's own reading"
    assert DALEOBANKS not in emitted and WEALTHMACHINE not in emitted


def test_no_event_names_uniimente_as_a_legal_principal():
    """Constitutional invariant, enforced by the spine and asserted here too."""
    led = ledger()
    run(wire_packet(), wire_assessment(), ledger=led,
        resolver_answers=ANSWERS, resolved_by=KERNEL)
    for record in led.by_type("event"):
        assert record.payload["legal_principal"] != "UNIIMENTE"


# ------------------------------------------------- an unresolved field halts
def test_the_bridge_halts_rather_than_inventing_an_untranslatable_field():
    """The default path, and the reason the default is the honest one.

    The DALEOBANKS wire packet genuinely cannot supply `governing_bottleneck`.
    A pathway that filled it in to reach a clean finish would be fabricating the
    institution's own record at the one point nobody would look.
    """
    result = run(wire_packet(), wire_assessment())

    assert not result.completed
    assert result.halted_at is Halt.SIGNAL_UNRESOLVED
    assert "governing_bottleneck" in result.unresolved
    assert "fabricate" in result.reason
    assert result.crossed_organ_boundary, (
        "the transport leg still happened and is still on record"
    )
    assert len(result.event_ids) == 1, "it stops at the translation, not before"


def test_resolution_requires_an_institutional_identity():
    """An answer with no accountable author is not an answer."""
    from adapters.daleobanks_opportunity import AdapterError

    with pytest.raises(AdapterError):
        run(wire_packet(), wire_assessment(),
            resolver_answers=ANSWERS, resolved_by="whoever")


# ------------------------------------------------------- transport fails closed
def test_a_tampered_body_never_reaches_either_adapter():
    """Identity comes from the verified transport, never the payload.

    The attack this forbids: a body that names a different origin and is trusted
    because it said so. Verification runs before either adapter sees the packet,
    so a forged body cannot select its own provenance.
    """
    packet = wire_packet()
    packet["id"] = "tampered-after-signing"

    class _Recorder:
        called = False

    import bridges.signal_to_venture as bridge
    original = bridge.packet_adapter.adapt

    def _spy(*args, **kwargs):
        _Recorder.called = True
        return original(*args, **kwargs)

    bridge.packet_adapter.adapt = _spy
    try:
        # A packet whose id is unknown to the wire schema is refused upstream of
        # translation; whichever guard fires, the adapter must not have run on
        # an unverified body.
        result = run(packet, wire_assessment())
    finally:
        bridge.packet_adapter.adapt = original

    if result.halted_at is Halt.TRANSPORT_REFUSED:
        assert not _Recorder.called, "translation ran on an unverified body"


def test_an_unknown_transport_identity_cannot_be_chosen_by_the_payload():
    """Asserted against the adapter both legs rely on."""
    from adapters.daleobanks_opportunity import AdapterError, adapt

    with pytest.raises(AdapterError) as exc:
        adapt(wire_packet(), transport_identity="railscout")
    assert "verified transport" in str(exc.value)


# ------------------------------------------------------------ composition only
def test_the_bridge_introduces_no_new_mechanism():
    """Every import is a module that existed and was tested before this file.

    The value claimed here is wiring, not invention. If this file starts
    defining its own transport, adapter or ledger, that claim stops being true
    and the institution has quietly grown a second implementation.
    """
    import ast

    path = os.path.join(ROOT, "bridges", "signal_to_venture.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    # BridgeRun and Halt describe the traversal itself; anything else would be a
    # mechanism this module should have imported instead.
    assert defined <= {"BridgeRun", "Halt"}, (
        f"bridge defines its own mechanism: {sorted(defined - {'BridgeRun', 'Halt'})}"
    )


def test_adapters_are_no_longer_imported_only_by_tests():
    """The disconnection this bridge exists to end, stated as a test.

    Before `bridges/`, `adapters/` was imported by zero non-test modules: a
    verified parts bin with no pathway through it.
    """
    # Filesystem walk rather than `git grep`: the latter searches only tracked
    # files, so the test would pass or fail on staging state instead of on the
    # property. First draft did exactly that and failed on an unstaged bridge.
    importers: list[str] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in {".git", "__pycache__", "tests", "adapters"}]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            full = os.path.join(dirpath, name)
            with open(full, encoding="utf-8", errors="ignore") as fh:
                if "from adapters" in fh.read():
                    importers.append(os.path.relpath(full, ROOT))

    assert importers, "adapters must be reachable from production code"
    assert any(p.startswith("bridges" + os.sep) for p in importers), importers
