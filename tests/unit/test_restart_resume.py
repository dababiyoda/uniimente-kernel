"""Restart and resume — what survives a process boundary, and what does not.

Written 2026-08-23 while establishing the Alpha prerequisite the Infinite Goal
Chase recompute named as the bottleneck. The recompute's first draft claimed
"nothing persists across processes", which was wrong: `EvidenceLedger` has
carried optional JSONL persistence with reload-and-reverify for some time, and
a closure check already proved it.

Checking that claim against the code found the real defect, which was narrower
and worse: derived state rebuilt on restart, but the **idempotent inbox did
not**, so replay protection lived only in process memory.
"""
from __future__ import annotations

import os

import pytest

from events.spine import Event, EventSpine
from memory.causal import CausalMemory
from provenance.ledger import EvidenceLedger

CONSTITUTION = "sha256:" + "0" * 64
PEER = "spiffe://uniimente.internal/organ/daleobanks"


def _event(event_id: str | None = None, **kw) -> Event:
    event = Event(type="bridge.opportunity_signal_received", source=PEER,
                  actor=PEER, payload={"packet_id": "OPP-1"},
                  legal_principal="Alfonso Lopez", **kw)
    if event_id:
        event.event_id = event_id
    return event


@pytest.fixture()
def durable(tmp_path):
    """A ledger path that outlives the objects built on it."""
    return str(tmp_path / "ledger.jsonl")


def _boot(path: str) -> tuple[EvidenceLedger, EventSpine]:
    """Everything a restart reconstructs: a reloaded ledger and a fresh spine.

    Deliberately builds NEW objects from the path rather than reusing any, so
    the only thing crossing the boundary is what is actually on disk.
    """
    ledger = EvidenceLedger(CONSTITUTION, path=path)
    return ledger, EventSpine(ledger)


# -- the defect this file was written for ------------------------------------

def test_replay_protection_survives_a_restart(durable):
    """The defect, fixed and pinned.

    Before the fix `EventSpine._seen_ids` started empty at construction, so a
    reloaded ledger came back with a spine that had never seen anything. The
    same peer event — same `event_id`, byte-identical — was accepted a second
    time and written to the chain again.

    A standing mandate resuming after a crash would have re-ingested every fact
    it had already processed, and the ledger would have looked perfectly valid:
    the hash chain over two identical records verifies exactly as well as the
    chain over one.
    """
    ledger, spine = _boot(durable)
    event = _event()
    assert spine.ingest(event) is not None
    assert len(ledger.by_type("event")) == 1

    reloaded, resumed = _boot(durable)

    assert resumed.ingest(event) is None, "the replay was accepted after restart"
    assert len(reloaded.by_type("event")) == 1
    assert reloaded.verify_chain()[0]


def test_the_inbox_is_rebuilt_from_the_ledger_not_carried_in_memory(durable):
    """Asserted against the mechanism, not only against the symptom.

    A future refactor could keep the symptom test passing by threading the old
    spine's set into the new one — which would work in-process and fail across
    a real restart, where there is no old spine to thread.
    """
    ledger, spine = _boot(durable)
    spine.ingest(_event(event_id="fixed-id-1"))
    spine.emit(Event(type="kernel.reading",
                     source="spiffe://uniimente.internal/organ/constitutional-controller",
                     actor="spiffe://uniimente.internal/organ/constitutional-controller",
                     payload={}, legal_principal="Alfonso Lopez",
                     event_id="fixed-id-2"))

    _reloaded, resumed = _boot(durable)

    assert resumed._seen_from_ledger() == {"fixed-id-1", "fixed-id-2"}
    assert resumed._seen_ids == {"fixed-id-1", "fixed-id-2"}


def test_an_emitted_id_cannot_return_as_an_ingested_fact(durable):
    """Both directions count toward the inbox.

    An event the kernel emitted, arriving back as an ingested external fact,
    would be the institution accepting its own claim from a peer — the exact
    authority laundering the emit/ingest split exists to prevent. Cheap to get
    wrong: an inbox rebuilt from `direction == "ingested"` only would allow it.
    """
    ledger, spine = _boot(durable)
    spine.emit(Event(type="kernel.reading",
                     source="spiffe://uniimente.internal/organ/constitutional-controller",
                     actor="spiffe://uniimente.internal/organ/constitutional-controller",
                     payload={}, legal_principal="Alfonso Lopez",
                     event_id="boomerang"))

    _reloaded, resumed = _boot(durable)

    assert resumed.ingest(_event(event_id="boomerang")) is None


# -- what already worked, now asserted rather than assumed -------------------

def test_the_ledger_reloads_and_reverifies_its_whole_chain(durable):
    ledger, spine = _boot(durable)
    for i in range(5):
        spine.ingest(_event(event_id=f"e-{i}"))
    head = ledger.head

    reloaded, _resumed = _boot(durable)

    assert reloaded.head == head
    assert reloaded.verify_chain()[0]
    assert len(reloaded.records) == len(ledger.records)


def test_a_tampered_durable_ledger_refuses_to_load(durable):
    """Persistence is a convenience, never the source of truth."""
    ledger, spine = _boot(durable)
    spine.ingest(_event())

    with open(durable, encoding="utf-8") as fh:
        lines = fh.readlines()
    lines[-1] = lines[-1].replace('"OPP-1"', '"OPP-TAMPERED"')
    with open(durable, "w", encoding="utf-8") as fh:
        fh.writelines(lines)

    with pytest.raises(ValueError, match="failed verification on load"):
        EvidenceLedger(CONSTITUTION, path=durable)


def test_causal_memory_rebuilds_itself_from_the_reloaded_ledger(durable):
    """Derived views need no persistence of their own.

    This is why the inbox defect was the only one: causal memory and `replay()`
    were already written as views over the ledger, so they survived a restart
    without anyone having to arrange it. The inbox was the one piece of state
    that had been cached instead of derived.
    """
    ledger, spine = _boot(durable)
    parent = _event(event_id="parent")
    spine.ingest(parent)
    child = _event(event_id="child", causal_parent="parent")
    spine.ingest(child)

    reloaded, resumed = _boot(durable)

    assert [e["event_id"] for e in CausalMemory(reloaded).ancestry("child")] \
        == [e["event_id"] for e in CausalMemory(ledger).ancestry("child")]
    assert len(resumed.replay()) == 2


def test_a_resumed_institution_continues_the_chain_rather_than_restarting_it(durable):
    """Resume appends; it does not begin again.

    A second genesis would make the ledger two chains in one file, each
    internally valid, with the earlier history silently unreachable.
    """
    ledger, spine = _boot(durable)
    spine.ingest(_event(event_id="before"))
    seq_before = len(ledger.records)

    reloaded, resumed = _boot(durable)
    resumed.ingest(_event(event_id="after"))

    assert len(reloaded.records) == seq_before + 1
    assert len([r for r in reloaded.records if r.record_type == "genesis"]) == 1
    assert reloaded.verify_chain()[0]
