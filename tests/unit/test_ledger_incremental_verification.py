"""Retained evidence never leaves the ledger, so reads and appends verify only what is new.

Measured first (docs/collaboration/FINDING-LEDGER-APPEND-COST-2026-10-14.md): every append and
every spine read re-hashed the whole chain, and a body tick read the spine 46 times, so one tick
cost about 46 x 9 us per retained record. A body that keeps working for months would spend its
ticks re-verifying history.

What must survive: a change to retained history is never silently served. Every read now hands
out the caller's own copy (plain dicts and lists, as before), so changing it changes nothing
retained. The only way left to alter retained history is the ledger's private list; every explicit
verify_chain() detects that at once, and the hot path at its next full reconstruction (on open, on
a replaced prefix, and at least every FULL_VERIFY_SECONDS).
"""
from __future__ import annotations

import copy
import json
from dataclasses import asdict

import pytest

import provenance.ledger as ledger_module
from events.spine import Event, EventError, EventSpine
from provenance.ledger import EvidenceLedger, sha256_json

ANCHOR = "sha256:" + "0" * 64


def _event(i: int, kind: str = "work.item_done", **payload) -> Event:
    return Event(type=kind, source="spiffe://uniimente.internal/test", actor="tester",
                 payload={"i": i, "items": [i, {"n": i}], **payload}, legal_principal="alfonso_lopez",
                 event_id=f"e-{kind}-{i}", occurred_at="2026-10-14T00:00:00Z")


def test_every_read_hands_out_a_copy_and_retained_evidence_is_unchanged():
    led = EvidenceLedger(ANCHOR)
    spine = EventSpine(led)
    spine.emit(_event(1))
    returned = led.append("witness", {"a": 1, "nested": {"b": [1, 2]}})
    returned.payload["nested"]["b"].append(3)
    led.records[2].payload["nested"]["b"].append(4)
    for rec in led.records:
        rec.payload.clear()
    for rec in reversed(led.records):
        rec.payload["x"] = 1
    led.records[1:][0].payload.clear()
    led.by_type("witness")[0].payload["a"] = 2
    led.find(returned.hash).payload["a"] = 3
    led.records[2].prev_hash = "sha256:" + "e" * 64
    event = spine.replay("work.")[0]
    event.payload["items"][1]["n"] = 99
    spine.latest(event.event_id).payload["i"] = 99
    assert led.verify_chain()[0]
    assert led.records[2].payload == {"a": 1, "nested": {"b": [1, 2]}}
    assert spine.replay("work.")[0].payload == {"i": 1, "items": [1, {"n": 1}]}
    with pytest.raises(TypeError):
        led.records[1] = led.records[2]  # the view itself is read-only


def test_what_readers_get_is_plain_json_data_as_before():
    led = EvidenceLedger(ANCHOR)
    spine = EventSpine(led)
    spine.emit(_event(1))
    data = {"z": 1, "a": [1, {"b": None}], "s": "x"}
    led.append("witness", data)
    payload = led.records[2].payload
    # Consumers check exact types (type(x) is dict): readers get plain dicts and lists.
    assert type(payload) is dict and type(payload["a"]) is list and type(payload["a"][1]) is dict
    assert type(spine.replay()[0].payload["items"]) is list
    assert json.dumps(payload) == json.dumps(data)
    assert led.records[2] == led.records[2] and led.records[2] in led.records


def test_tampering_with_the_retained_list_is_detected_by_explicit_verification_at_once(tmp_path):
    led = EvidenceLedger(ANCHOR, str(tmp_path / "l.jsonl"))
    for i in range(5):
        led.append("event", {"n": i})
    led._records[2].payload["n"] = 999
    ok, why = led.verify_chain()
    assert not ok and "payload hash mismatch at seq 2" in why
    with pytest.raises(ValueError, match="payload hash mismatch"):
        led.append("event", {"n": 5})  # the failed reconstruction is not forgotten


def test_the_hot_path_detects_tampering_at_its_next_full_reconstruction(tmp_path, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(ledger_module, "_monotonic", lambda: now[0])
    led = EvidenceLedger(ANCHOR, str(tmp_path / "l.jsonl"))
    spine = EventSpine(led)
    for i in range(5):
        spine.emit(_event(i))
    led._records[3].payload["direction"] = "rewritten"
    # Inside the window the alteration is not yet seen: the stated, bounded cost of not re-hashing.
    spine.emit(_event(5))
    now[0] += ledger_module.FULL_VERIFY_SECONDS
    with pytest.raises(EventError, match="payload hash mismatch at seq 3"):
        spine.replay("work.")
    with pytest.raises(ValueError, match="payload hash mismatch at seq 3"):
        led.append("event", {"n": 6})


def test_replacing_the_last_verified_record_forces_full_reconstruction(tmp_path):
    led = EvidenceLedger(ANCHOR, str(tmp_path / "l.jsonl"))
    for i in range(4):
        led.append("event", {"n": i})
    led._records[2].payload["n"] = 99
    led._records[-1] = copy.deepcopy(led._records[-1])  # a different object where the verified tail was
    with pytest.raises(ValueError, match="payload hash mismatch at seq 2"):
        led.append("event", {"n": 4})


def test_a_record_that_did_not_come_through_append_is_verified_before_the_next_append():
    led = EvidenceLedger(ANCHOR)
    led.append("event", {"n": 1})
    forged = ledger_module.LedgerRecord(2, "2026-10-14T00:00:00Z", "event", {"n": 2}, led.head,
                                        "sha256:" + "f" * 64, None, 2)
    led._records.append(forged)  # beyond the verified prefix
    with pytest.raises(ValueError, match="payload hash mismatch at seq 2"):
        led.append("event", {"n": 3})


def test_assigning_history_copies_it_in_and_reverifies_all_of_it():
    led = EvidenceLedger(ANCHOR)
    for i in range(4):
        led.append("event", {"n": i})
    led.verify_chain()
    kept = list(led.records)
    kept[2].payload["n"] = 99  # a changed middle, assigned back
    led.records = kept
    with pytest.raises(ValueError, match="payload hash mismatch at seq 2"):
        led.append("event", {"n": 4})
    fresh = EvidenceLedger(ANCHOR, read_only=True)
    good = list(EvidenceLedger(ANCHOR).records)
    fresh.records = good
    good[0].payload["kind"] = "changed after assignment"  # the caller's list stays the caller's
    assert fresh.verify_chain()[0]


def test_a_snapshot_assignment_reverifies_and_the_spine_rebuilds(tmp_path):
    led = EvidenceLedger(ANCHOR, str(tmp_path / "l.jsonl"))
    spine = EventSpine(led)
    for i in range(6):
        spine.emit(_event(i))
    snap = EvidenceLedger(ANCHOR, read_only=True)
    snap.records = copy.deepcopy(led.records[:4])  # genesis + 3 events, as morning_review does
    view = EventSpine(snap)
    assert [e.event_id for e in view.replay("work.")] == [f"e-work.item_done-{i}" for i in range(3)]
    snap.records = copy.deepcopy(led.records[:3])
    assert [e.event_id for e in view.replay("work.")] == [f"e-work.item_done-{i}" for i in range(2)]


def test_history_replaced_at_the_same_length_is_rebuilt():
    first, second = EvidenceLedger(ANCHOR), EvidenceLedger(ANCHOR)
    a, b = EventSpine(first), EventSpine(second)
    for i in range(3):
        a.emit(_event(i))
        b.emit(_event(i + 100))
    view_ledger = EvidenceLedger(ANCHOR, read_only=True)
    view_ledger.records = list(first.records)
    view = EventSpine(view_ledger)
    assert [e.payload["i"] for e in view.replay()] == [0, 1, 2]
    view_ledger.records = list(second.records)  # same length, different history
    assert [e.payload["i"] for e in view.replay()] == [100, 101, 102]
    assert view.latest("e-work.item_done-0") is None


def test_a_non_object_payload_is_refused_even_with_a_matching_hash(tmp_path):
    path = tmp_path / "l.jsonl"
    led = EvidenceLedger(ANCHOR, str(path))
    led.append("event", {"n": 1})
    led.close()
    body = {"seq": 2, "record_type": "event", "payload": [1, 2], "prev_hash": led.head, "corrects": None,
            "ts_utc": "2026-10-14T00:00:00Z", "hash_version": 2}
    line = {"seq": 2, "ts_utc": body["ts_utc"], "record_type": "event", "payload": [1, 2],
            "prev_hash": led.head, "hash": sha256_json(body), "corrects": None, "hash_version": 2}
    with open(path, "a") as fh:
        fh.write(json.dumps(line) + "\n")
    with pytest.raises(ValueError, match="unsupported record at 2"):
        EvidenceLedger(ANCHOR, str(path))


def test_conflicting_identities_in_retained_history_are_refused(tmp_path):
    path = str(tmp_path / "l.jsonl")
    led = EvidenceLedger(ANCHOR, path)
    spine = EventSpine(led)
    spine.emit(_event(1))
    forged = {**asdict(_event(1)), "payload": {"i": "changed"}, "direction": "emitted"}
    led.append("event", forged)  # written around the spine, which would have refused it
    with pytest.raises(EventError, match="conflicting durable event identity"):
        spine.replay()  # the live view refuses it as it folds
    with pytest.raises(EventError, match="conflicting durable event identity"):
        spine.replay()  # and keeps refusing (fail closed)
    led.close()
    with pytest.raises(EventError, match="conflicting durable event identity"):
        EventSpine(EvidenceLedger(ANCHOR, path))  # so does a rebuild from the file


def _views(spine: EventSpine):
    return (dict(spine._bindings), [e.event_id for e in spine._outbox], set(spine._uncertain_deliveries),
            [asdict(e) for e in spine.replay()], [asdict(e) for e in spine.replay("work.")],
            [asdict(e) for e in spine.replay("work.item")], [asdict(e) for e in spine.replay("other.")])


def test_incremental_views_equal_a_rebuild_from_the_beginning(tmp_path):
    path = str(tmp_path / "l.jsonl")
    led = EvidenceLedger(ANCHOR, path)
    live = EventSpine(led)
    touched = []
    for i in range(12):
        kind = ("work.item_done", "work.item_started", "other.note", "work.batch_closed")[i % 4]
        if i % 3 == 0:
            live.outbox_stage(_event(i, kind))
        else:
            live.emit(_event(i, kind))
        led.append("witness", {"i": i})  # non-event records interleave
        if i % 5 == 4:
            def mediator(ev):
                ev.payload["mediator_was_here"] = True  # a mediator's change stays its own
                touched.append(ev.event_id)
                return ev.payload["i"] % 2 == 0
            live.outbox_flush(mediator=mediator)
    assert touched and led.verify_chain()[0]
    assert all("mediator_was_here" not in e.payload for e in live.replay())
    assert live.emit(_event(1, "work.item_started")) is None  # a re-emitted identical fact is idempotent
    with pytest.raises(EventError):
        live.emit(_event(4, "work.item_done", changed=True))
    expected = _views(live)
    led.close()
    rebuilt = EventSpine(EvidenceLedger(ANCHOR, path))
    assert _views(rebuilt) == expected
    everything = rebuilt.replay()
    for prefix in ("work.", "work.item", "work.item_done", "other.", "nothing."):
        assert [asdict(e) for e in rebuilt.replay(prefix)] == \
            [asdict(e) for e in everything if e.type.startswith(prefix)]  # the original filter, in ledger order
    assert rebuilt.latest("e-work.item_started-1").payload["i"] == 1 and rebuilt.latest("nope") is None
    for event_id in ("e-work.item_started-1", "e-work.batch_closed-3"):  # the second was staged, then flushed
        records = [r for r in rebuilt.ledger.records if r.payload.get("event_id") == event_id]
        assert rebuilt.record_hash(event_id) == records[-1].hash  # the LAST record of that identity
        assert rebuilt.latest(event_id).payload == records[-1].payload["payload"]
    assert len([r for r in rebuilt.ledger.records if r.payload.get("event_id") == "e-work.batch_closed-3"]) >= 3


def test_positions_equal_numbering_a_full_replay_as_history_grows_and_is_replaced():
    led = EvidenceLedger(ANCHOR)
    spine = EventSpine(led)

    def expected(prefix):
        return {e.event_id: i for i, e in enumerate(spine.replay(prefix))}
    for i in range(9):
        kind = ("work.item_done", "other.note", "work.batch_closed")[i % 3]
        (spine.outbox_stage if i % 4 == 0 else spine.emit)(_event(i, kind))
        if i % 4 == 3:
            spine.outbox_flush(mediator=lambda ev: True)  # repeated identities: the last position wins
        for prefix in ("", "work.", "other.", "work.batch"):
            assert dict(spine.positions(prefix)) == expected(prefix)
    with pytest.raises(TypeError):
        spine.positions("work.")["x"] = 1  # read-only
    other = EvidenceLedger(ANCHOR)
    EventSpine(other).emit(_event(50, "other.note"))
    view_ledger = EvidenceLedger(ANCHOR, read_only=True)
    view_ledger.records = list(led.records)
    view = EventSpine(view_ledger)
    assert dict(view.positions("work.")) == {e.event_id: i for i, e in enumerate(view.replay("work."))}
    view_ledger.records = list(other.records)  # replaced history: positions start over
    assert dict(view.positions("")) == {"e-other.note-50": 0} and dict(view.positions("work.")) == {}


def test_the_journal_finds_retained_facts_through_the_spine_index():
    from greg.journal import Journal
    led = EvidenceLedger(ANCHOR)
    journal = Journal(EventSpine(led), actor="spiffe://uniimente.internal/greg/test")
    first = journal.record("mission.noted", {"mission_id": "m:one", "n": 1}, key="one")
    journal.record("mission.noted", {"mission_id": "m:two", "n": 2}, key="two")
    record = next(r for r in led.records if r.payload.get("event_id") == first.event_id)
    assert journal.event_hash(first.event_id) == record.hash and journal.event_hash("absent") is None
    again = journal.record("mission.noted", {"mission_id": "m:one", "n": 1}, key="one")  # idempotent
    assert again.event_id == first.event_id and again.payload == {"mission_id": "m:one", "n": 1}
    assert len(led.records) == 3
    with pytest.raises(EventError, match="reused with different content"):
        journal.record("mission.noted", {"mission_id": "m:one", "n": 9}, key="one")


def test_improvement_numbers_events_exactly_as_before_because_the_numbers_are_persisted():
    from greg import improvement
    from greg.journal import Journal
    journal = Journal(EventSpine(EvidenceLedger(ANCHOR)), actor="spiffe://uniimente.internal/greg/test")
    for i in range(7):
        journal.record(("brief.delivered", "critique.recorded", "improvement.proposed")[i % 3], {"i": i}, key=i)
    old = {e.event_id: i for i, e in enumerate(journal.replay())}  # the definition before this change
    assert dict(improvement._order(journal)) == old and len(old) == 7


def _hashes_for(monkeypatch, action) -> int:
    calls = [0]
    real = ledger_module.sha256_json

    def counting(obj):
        calls[0] += 1
        return real(obj)
    monkeypatch.setattr(ledger_module, "sha256_json", counting)
    try:
        action()
    finally:
        monkeypatch.setattr(ledger_module, "sha256_json", real)
    return calls[0]


@pytest.mark.parametrize("history", [200, 2000])
def test_hashing_per_operation_does_not_grow_with_history(history, monkeypatch, tmp_path):
    monkeypatch.setattr(ledger_module, "_monotonic", lambda: 1000.0)  # stay inside one window
    led = EvidenceLedger(ANCHOR, str(tmp_path / "l.jsonl"))
    spine = EventSpine(led)
    for i in range(history):
        spine.emit(_event(i))
    n = [history]

    def one_operation():
        spine.emit(_event(n[0]))
        spine.replay("work.")
        spine.latest("e-work.item_done-0")
        spine.positions("work.")
        n[0] += 1
    # Before: each emit re-hashed the chain three times and each replay once (thousands here).
    assert _hashes_for(monkeypatch, one_operation) <= 6


def test_full_reconstruction_still_costs_the_whole_chain(monkeypatch):
    led = EvidenceLedger(ANCHOR)
    for i in range(50):
        led.append("event", {"n": i})
    assert _hashes_for(monkeypatch, led.verify_chain) >= 50  # explicit verification is never shortened


def test_history_written_before_this_change_loads_verifies_and_reserializes_byte_for_byte():
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "evidence" / "greg-body" / "vepmc-path-ledger.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    led = EvidenceLedger(json.loads(lines[0])["payload"]["constitution_hash"], str(path), read_only=True)
    assert led.verify_chain()[0] and len(led.records) == len(lines)
    assert [json.dumps(asdict(r), allow_nan=False) for r in led.records] == lines


def test_a_commit_witness_is_appended_only_onto_a_wholly_verified_chain():
    """Installed-body merge: the Consequence Gate relied on append() re-verifying the whole chain before its
    Commit Witness. Hot-path appends now verify only new records, so the witness, the Gate's durability
    boundary, still reconstructs the whole chain (COMMIT_RECORD_TYPES). An ordinary append is served for up
    to FULL_VERIFY_SECONDS on altered history (the stated residual); a witness never is."""
    led = EvidenceLedger(ANCHOR)
    for i in range(3):
        led.append("event", {"i": i})
    assert led.verify_incremental()[0]
    led._records[1].payload["i"] = 99                    # an old retained record, altered in this process
    led.append("event", {"i": 3})                         # the hot path does not see it (the residual)
    with pytest.raises(ValueError, match="payload hash mismatch at seq 1"):
        led.append("witness", {"w": 1})
    assert not led.by_type("witness") and ledger_module.COMMIT_RECORD_TYPES == ("witness",)
