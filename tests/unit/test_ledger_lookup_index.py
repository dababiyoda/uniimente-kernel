"""Lookups by record hash, type and payload field read only what they return.

Measured (docs/collaboration/FINDING-LEDGER-APPEND-COST-2026-10-14.md): after the mission book
stopped replaying history, a holding mission's tick still grew about 1.8 ms per thousand retained
records, because every observation goes through the Consequence Gate. The Authority Office looked
up a prior dispatch claim and receipt by scanning (and copying) every record of that type, and the
engine counted a check's observations by replaying all of them. The ledger now answers lookups by
hash, type and payload field from indexes it keeps up to date the way the event spine keeps its
views. These tests pin that every answer equals the scan it replaces.

The Gate's own dispatch-claim check still reads every claim (through by_type): the Gate's bytes are
a continuity artifact, so changing it is a founder decision (see the finding).
"""
from __future__ import annotations

import random
from dataclasses import replace

import pytest

import provenance.ledger as ledger_module
from tests.unit.test_consequence_gate import stack  # noqa: F401  (pytest fixture)
from provenance.ledger import EvidenceLedger

ANCHOR = "sha256:" + "0" * 64


def scan(led, record_type, **where):
    """What by_type and select returned before the index: a filter over every retained record."""
    return [r for r in led._records if r.record_type == record_type
            and all(r.payload.get(f) == v for f, v in where.items())]


def same(found, expected):
    assert [r.hash for r in found] == [r.hash for r in expected]
    assert all(f is not e and f.payload == e.payload for f, e in zip(found, expected))   # copies


def grow(led, n, rng):
    for i in range(n):
        kind = rng.choice(["grant_dispatch", "receipt", "event", "witness"])
        payload = {"proposal_id": f"p{rng.randrange(8)}", "grant_id": f"g{rng.randrange(8)}", "n": i,
                   "flag": rng.choice([True, 1, 1.0, None]), "nested": {"k": [i]}}
        if rng.random() < 0.2:
            payload.pop("grant_id")
        if rng.random() < 0.1:
            payload["grant_id"] = ["unhashable", i]
        led.append(kind, payload)


def queries(rng):
    for _ in range(40):
        kind = rng.choice(["grant_dispatch", "receipt", "event", "witness", "seal"])
        field = rng.choice(["proposal_id", "grant_id", "flag", "missing"])
        value = rng.choice([f"p{rng.randrange(9)}", f"g{rng.randrange(9)}", True, 1, None, ["unhashable", 3]])
        yield kind, {field: value}
        yield kind, {"proposal_id": f"p{rng.randrange(8)}", "grant_id": f"g{rng.randrange(8)}"}
        yield kind, {}


def test_select_by_type_and_find_equal_a_scan_while_history_grows():
    rng = random.Random(7)
    led = EvidenceLedger(ANCHOR)
    for _ in range(5):
        grow(led, 60, rng)
        for kind, where in queries(rng):
            same(led.select(kind, **where), scan(led, kind, **where))
        for kind in ("grant_dispatch", "receipt", "event", "genesis", "none"):
            same(led.by_type(kind), scan(led, kind))
        for rec in rng.sample(led._records, 20):
            assert led.find(rec.hash).hash == rec.hash and led.find(rec.hash) is not rec
        assert led.find("sha256:" + "f" * 64) is None


def test_assigned_or_reloaded_history_is_indexed_again(tmp_path):
    rng = random.Random(11)
    path = tmp_path / "ledger.jsonl"
    led = EvidenceLedger(ANCHOR, path=str(path))
    grow(led, 120, rng)
    full = list(led.records)
    probe = full[100]
    assert led.select("grant_dispatch", proposal_id="p3")      # indexes built
    led.records = full[:50]                                    # an earlier snapshot
    assert led.find(probe.hash) is None
    for kind, where in queries(rng):
        same(led.select(kind, **where), scan(led, kind, **where))
    led.records = full                                         # and back
    assert led.find(probe.hash).hash == probe.hash
    for kind, where in queries(rng):
        same(led.select(kind, **where), scan(led, kind, **where))
    led.close()
    reopened = EvidenceLedger(ANCHOR, path=str(path))
    for kind, where in queries(rng):
        same(reopened.select(kind, **where), scan(reopened, kind, **where))


def test_a_lookup_copies_only_what_it_returns(monkeypatch):
    rng = random.Random(3)
    led = EvidenceLedger(ANCHOR)
    grow(led, 400, rng)
    led.append("grant_dispatch", {"proposal_id": "the-one", "grant_id": "gx"})
    led.select("grant_dispatch", proposal_id="warm-up")        # the field index is built once
    copied = []
    real = ledger_module._copy_record
    monkeypatch.setattr(ledger_module, "_copy_record", lambda r: copied.append(r.seq) or real(r))
    [found] = led.select("grant_dispatch", proposal_id="the-one")
    assert copied == [found.seq]
    copied.clear()
    assert led.find(found.hash).seq == found.seq and copied == [found.seq]


def test_a_record_altered_in_place_is_never_returned_for_what_it_no_longer_holds():
    """Only the ledger's private list can be altered in place, and verification catches that (see
    test_ledger_incremental_verification). Lookups never return a record that no longer matches; a
    value written in place is not found by it until history is assigned or reloaded."""
    led = EvidenceLedger(ANCHOR)
    a = led.append("receipt", {"grant_id": "g1"})
    b = led.append("receipt", {"grant_id": "g2"})
    led.select("receipt", grant_id="g1")
    led._records[a.seq].payload["grant_id"] = "g2"             # tamper after indexing
    assert [r.hash for r in led.select("receipt", grant_id="g1")] == []
    assert [r.hash for r in led.select("receipt", grant_id="g2")] == [b.hash]   # the index never invents
    led._records[b.seq].hash = "sha256:" + "e" * 64
    assert led.find(b.hash) is None and led.find("sha256:" + "e" * 64) is None
    assert led.verify_chain()[0] is False


def test_a_dispatch_claim_is_found_by_proposal_and_by_grant():
    """The lookups a claim check needs (the Authority Office uses the first)."""
    led = EvidenceLedger(ANCHOR)
    led.append("grant_dispatch", {"proposal_id": "p1", "grant_id": "g1"})
    assert led.select("grant_dispatch", proposal_id="p1")
    assert led.select("grant_dispatch", grant_id="g1")
    assert not led.select("grant_dispatch", proposal_id="p2") and not led.select("grant_dispatch", grant_id="g2")


@pytest.mark.parametrize("value", [["a"], {"k": 1}])
def test_an_unhashable_query_value_is_compared_record_by_record(value):
    led = EvidenceLedger(ANCHOR)
    led.append("event", {"v": value})
    led.append("event", {"v": "other"})
    assert [r.payload["v"] for r in led.select("event", v=value)] == [value]


def test_a_claimed_proposal_or_a_claimed_grant_alone_stops_a_second_dispatch(stack):
    """The Gate reads every dispatch claim through by_type, now answered from the type index; a claim
    by proposal or by grant must each still stop a second execution after an interrupted one."""
    from tests.unit.test_consequence_gate import make_proposal
    gate, _, _, actor, _ = stack
    p = make_proposal(actor.passport_id)
    g = gate.grants.issue_single_action(proposal=p, policy_version='1.0.0')

    def uncertain(_):
        raise RuntimeError('unknown effect')

    assert gate.run(p, executor=uncertain, standing_grant=g).state == 'reconciliation_required'
    executed = []
    again = gate.grants.issue_single_action(proposal=p, policy_version='1.0.0')     # same proposal, new grant
    assert gate.run(p, executor=executed.append, standing_grant=again).state == 'reconciliation_required'
    other = make_proposal(actor.passport_id)                                         # new proposal, same grant
    assert other.proposal_id != p.proposal_id
    assert gate.run(other, executor=executed.append, standing_grant=g).state == 'reconciliation_required'
    assert executed == []


def test_find_answers_the_first_record_with_a_hash():
    """Only a malformed history holds one hash twice; find answers with the first, as a scan did."""
    led = EvidenceLedger(ANCHOR)
    a = led.append("receipt", {"grant_id": "g1"})
    led.append("receipt", {"grant_id": "g2"})
    later = replace(list(led.records)[a.seq], payload={"grant_id": "later"})
    led.records = list(led.records) + [later]                          # assigned history repeats a hash
    assert led.find(a.hash).payload == {"grant_id": "g1"}
