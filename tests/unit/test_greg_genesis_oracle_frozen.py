"""The acceptance oracle is frozen before any candidate is tried (acceptance C.G7).

Read from the journal alone, for every deficit:

- ``deficit.opened`` comes before the first ``genesis.route``, ``genesis.built``, ``genesis.verified`` and
  ``genesis.discovery`` for that deficit, by position in the one canonical history; and
- the vector digest it records is recomputable from sources the candidate cannot touch: for a catalogued function, the
  frozen oracle at the seed derived from the deficit id; for a contract, the examples and held-out vectors in the signed
  MISSION envelope exactly as the founder signed them.

A checker that cannot fail proves nothing, so the same check is run on a history with one candidate event moved before
its deficit, and on a contract whose held-out vectors were changed after signing; both are refused.
"""
import pytest

from greg import genesis as genesis_mod
from greg.body import Body
from greg.capabilities import installed_binary
from provenance.ledger import sha256_json
from tests.greg_fixtures import Clock, drop, make_body, mission, signed

CANDIDATE_KINDS = ("greg.genesis.route", "greg.genesis.built", "greg.genesis.verified", "greg.genesis.discovery")


def frozen_before_candidates(events) -> list[str]:
    """Violations of 'the oracle is frozen first', from an ordered list of journal events."""
    opened_at, problems = {}, []
    for position, event in enumerate(events):
        payload = event.payload if hasattr(event, "payload") else event["payload"]
        kind = event.type if hasattr(event, "type") else event["type"]
        deficit = payload.get("deficit_id") if isinstance(payload, dict) else None
        if kind == "greg.deficit.opened":
            opened_at.setdefault(deficit, position)
        elif kind in CANDIDATE_KINDS and deficit is not None and deficit not in opened_at:
            problems.append(f"{kind} for {deficit} at {position} precedes its deficit.opened")
    return problems


def catalog_digest(function: str, seed: int) -> str:
    return sha256_json([{k: (v.hex() if isinstance(v, bytes) else v) for k, v in case.items()}
                        for case in genesis_mod.CATALOG[function]["oracle"](seed)])


def _hash_spec(data):
    import hashlib
    doc = data / "notes.txt"
    doc.write_text("frozen first\n")
    check = {"check_id": "digest", "description": "the notes have the founder's expected digest",
             "sensor": {"function": "hash.sha256", "params": {"path": str(doc)}, "target": "fs:notes.txt"},
             "predicate": {"op": "equals", "field": "sha256", "value": hashlib.sha256(b"frozen first\n").hexdigest()}}
    return mission("m:hash", checks=[check], strategies=[], ceiling="read_only", budget=1.0,
                   capabilities=["fs.read", "acquired.hash.sha256.*"], auto_attach=True)


CONTRACT = {
    "function": "text.distinct_line_count",
    "description": "The number of distinct lines in a text file; a final line without a newline counts.",
    "returns": "an integer", "output_field": "distinct",
    "examples": [{"input_text": "b\na\nb\n", "expected": 2}, {"input_text": "one\n", "expected": 1}],
    "held_out": [{"input_text": "", "expected": 0}, {"input_text": "x\nx\nx\n", "expected": 1},
                 {"input_text": "c\nb\na\nc\n", "expected": 3}, {"input_text": "p\nq", "expected": 2}],
    "build_budget_usd": 1.0}


def _contract_spec(data):
    doc = data / "notes.txt"
    doc.write_text("q\np\nq\np\n")
    check = {"check_id": "answered", "description": "the notes give the founder's expected answer",
             "sensor": {"function": CONTRACT["function"], "params": {"path": str(doc)}, "target": "fs:notes.txt"},
             "predicate": {"op": "equals", "field": "distinct", "value": 2}}
    spec = mission("m:distinct", checks=[check], strategies=[], ceiling="read_only", budget=1.0,
                   capabilities=["fs.read", f"acquired.{CONTRACT['function']}.*"], auto_attach=True)
    spec["capability_specs"] = [dict(CONTRACT)]
    return spec


def _run(tmp_path, spec):
    home, key, body_id, data = make_body(tmp_path)
    envelope = signed(key, body_id, "MISSION", spec(data))
    drop(home, envelope)
    clock = Clock()
    body = Body(home, clock=clock, builder=None).open()
    body.boot()
    for _ in range(4):
        clock.advance(30)
        body.tick()
    return body, envelope


@pytest.mark.skipif(installed_binary("sha256sum") is None, reason="sha256sum is needed on this host")
def test_a_catalogued_oracle_is_frozen_before_any_candidate_and_its_digest_recomputes(tmp_path):
    body, _ = _run(tmp_path, _hash_spec)
    history = body.journal.replay("")
    assert frozen_before_candidates(history) == []
    opened = body.journal.replay("deficit.opened")[0].payload
    candidates = [e for e in history if e.type in CANDIDATE_KINDS and e.payload.get("deficit_id") == opened["deficit_id"]]
    assert candidates and any(e.type == "greg.genesis.verified" for e in candidates)
    seed = int(sha256_json({"deficit": opened["deficit_id"]})[7:15], 16)
    assert opened["acceptance"]["seed"] == seed
    assert opened["acceptance"]["vector_digest"] == catalog_digest("hash.sha256", seed)
    body.close()


@pytest.mark.skipif(not all(installed_binary(b) for b in ("sort", "wc")), reason="sort and wc are needed")
def test_a_contract_oracle_is_the_signed_vectors_frozen_before_any_candidate(tmp_path):
    body, envelope = _run(tmp_path, _contract_spec)
    history = body.journal.replay("")
    assert frozen_before_candidates(history) == []
    opened = body.journal.replay("deficit.opened")[0].payload
    signed_contract = envelope["body"]["capability_specs"][0]
    assert opened["acceptance"]["vector_digest"] == sha256_json([signed_contract["examples"],
                                                                 signed_contract["held_out"]])
    assert opened["acceptance"]["public_examples"] == 2 and opened["acceptance"]["held_out_vectors"] == 4
    verified = [e.payload for e in body.journal.replay("genesis.verified")
                if e.payload["deficit_id"] == opened["deficit_id"]]
    assert verified and all(v["report"]["cases"] == 6 for v in verified)   # every candidate met all frozen vectors
    body.close()


@pytest.mark.skipif(not all(installed_binary(b) for b in ("sort", "wc")), reason="sort and wc are needed")
def test_the_check_refuses_a_candidate_moved_before_its_deficit_and_vectors_changed_after_signing(tmp_path):
    """The checks can fail: they are not satisfied by any history or any digest."""
    body, envelope = _run(tmp_path, _contract_spec)
    history = [{"type": e.type, "payload": e.payload} for e in body.journal.replay("")]
    opened_at = next(i for i, e in enumerate(history) if e["type"] == "greg.deficit.opened")
    first = next(i for i, e in enumerate(history) if e["type"] in CANDIDATE_KINDS)
    reordered = history[:opened_at] + [history[first]] + [e for i, e in enumerate(history[opened_at:], opened_at)
                                                          if i != first]
    assert frozen_before_candidates(reordered)
    opened = body.journal.replay("deficit.opened")[0].payload
    altered = dict(envelope["body"]["capability_specs"][0])
    altered["held_out"] = altered["held_out"][:-1] + [{"input_text": "p\nq", "expected": 1}]
    assert opened["acceptance"]["vector_digest"] != sha256_json([altered["examples"], altered["held_out"]])
    body.close()
