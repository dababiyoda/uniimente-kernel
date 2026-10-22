"""A value larger than a receipt keeps passes whole from one mission action to the next, by artifact.

The receipt bound (greg/authority.py ``bounded``) cuts a long string to a prefix; a bind refuses a cut value. When an
output is cut, ``keep_output`` keeps the whole output in the body's content-addressed artifact store and the receipt
records its address. An edge that opts in (``by: artifact``) binds the whole value, read back by that address and
re-hashed. Without the opt-in a cut value is still refused; a missing or altered artifact holds the strategy and
never yields a prefix. The founder key is a per-test key, not Alfonso's.
"""
import hashlib
import json

import pytest

from greg.artifacts import ArtifactStore
from greg.authority import RECEIPT_TEXT_LIMIT, keep_output, output_store
from greg.body import Body
from greg.missions import MissionError, Unbound, artifact_output, bound_value, validate_mission
from tests.greg_fixtures import Clock, drop, make_body, mission, signed, workspace

BIG = "".join(f"line {i:06d} of a long answer\n" for i in range(4000))   # about 100 KB
assert 90_000 < len(BIG.encode()) and len(BIG) > RECEIPT_TEXT_LIMIT
DIGEST = hashlib.sha256(BIG.encode()).hexdigest()


def edge(**kw):
    return {"param": "content", "from": {"action_id": "read-a", "field": "text"}, "type": "string", **kw}


def receipt_result(output, root):
    kept, whole = keep_output(output, root)
    return {"output": kept, **({"output_artifact": whole} if whole else {})}


def test_a_long_string_binds_whole_through_the_artifact_route(tmp_path):
    result = receipt_result({"text": BIG, "sha256": DIGEST}, tmp_path)
    assert result["output"]["text"]["truncated"] is True          # the receipt stays bounded
    assert result["output_artifact"]["address"].startswith("sha256:")
    whole = artifact_output(result, tmp_path)
    value = bound_value(edge(by="artifact"), result["output"], whole)
    assert hashlib.sha256(value.encode()).hexdigest() == DIGEST and value == BIG


def test_without_the_opt_in_a_cut_value_is_still_refused(tmp_path):
    result = receipt_result({"text": BIG}, tmp_path)
    whole = artifact_output(result, tmp_path)
    with pytest.raises(Unbound, match="prefix is not bound"):
        bound_value(edge(), result["output"])
    with pytest.raises(Unbound, match="prefix is not bound"):     # even handed the whole, a receipt edge ignores it
        bound_value(edge(), result["output"], whole)


def test_an_uncut_output_records_no_artifact_and_binds_as_before(tmp_path):
    result = receipt_result({"text": "short"}, tmp_path)
    assert "output_artifact" not in result and artifact_output(result, tmp_path) is None
    assert bound_value(edge(by="artifact"), result["output"], None) == "short"


@pytest.mark.parametrize("damage", ["missing", "tampered", "foreign"])
def test_a_missing_or_altered_artifact_is_unbound_never_a_prefix(tmp_path, damage):
    result = receipt_result({"text": BIG}, tmp_path)
    path = output_store(tmp_path).path(result["output_artifact"]["address"])
    if damage == "missing":
        path.unlink()
    elif damage == "tampered":
        path.chmod(0o600)
        path.write_bytes(path.read_bytes().replace(b"line 003999", b"line 00399X"))
    else:   # intact bytes of another output, recorded under this receipt
        other = receipt_result({"text": BIG + "x"}, tmp_path)
        result["output_artifact"] = other["output_artifact"]
    with pytest.raises(Unbound):
        artifact_output(result, tmp_path)


def test_a_body_without_a_store_records_why_and_binds_nothing(tmp_path):
    result = receipt_result({"text": BIG}, None)
    assert result["output_artifact"]["address"] is None
    with pytest.raises(Unbound, match="no artifact store"):
        artifact_output(result, tmp_path)


def test_a_large_max_bytes_needs_the_artifact_route(tmp_path):
    spec, _ = big_mission(tmp_path, tmp_path / "source.txt", by=None)
    spec["strategies"][1]["bind"][0]["max_bytes"] = 200_000
    with pytest.raises(MissionError, match="only by artifact"):
        validate_mission(spec)
    spec["strategies"][1]["bind"][0]["by"] = "artifact"
    validate_mission(spec)


# -- end to end on a real Body ------------------------------------------------------------------------------------

def big_mission(home, source, *, by="artifact"):
    root = workspace(home, "m:big")
    bind = edge(**({"by": by} if by else {}))
    read = {"action_id": "read-a", "capability": "fs.read", "params": {"path": str(source)},
            "target": "fs:source.txt", "advances": ["b"], "rationale": "read the long source"}
    write = {"action_id": "write-b", "capability": "fs.write", "params": {"relative_path": "b.txt"},
             "bind": [bind], "target": "workspace:b.txt", "advances": ["b"],
             "rationale": "write the whole source into b"}
    check = {"check_id": "b", "description": "b.txt holds the whole source",
             "sensor": {"capability": "fs.read", "params": {"path": str(root / "b.txt")}, "target": "fs:b.txt"},
             "predicate": {"op": "equals", "field": "sha256", "value": DIGEST}}
    return mission("m:big", checks=[check], strategies=[read, write], capabilities=["fs.read", "fs.write"]), root


def start(tmp_path, *, by="artifact"):
    home, key, body_id, data = make_body(tmp_path)
    source = data / "source.txt"
    source.write_text(BIG)
    spec, root = big_mission(home, source, by=by)
    drop(home, signed(key, body_id, "MISSION", spec))
    return home, root


def tick(body, clock, n):
    states = []
    for _ in range(n):
        clock.advance(60)
        states.append(body.tick()["missions"][0]["state"])
        if states[-1] == "ACHIEVED":
            break
    return states


def actions(body):
    return [e.payload for e in body.journal.replay("mission.action") if e.payload.get("mission_id") == "m:big"]


def test_a_large_value_reaches_the_next_action_and_the_mission_closes(tmp_path):
    home, root = start(tmp_path)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        states = tick(body, clock, 8)
        done = actions(body)
        receipt = body.office.ledger.find(next(a for a in done if a["action_id"] == "read-a")["receipt"])
    assert states[-1] == "ACHIEVED", states
    assert (root / "b.txt").read_text() == BIG
    kept = receipt.payload["result"]
    assert kept["output"]["text"]["truncated"] is True and len(json.dumps(kept["output"])) < 3 * RECEIPT_TEXT_LIMIT
    write = next(a for a in done if a["action_id"] == "write-b" and a["status"] == "DONE")
    (binding,) = write["bindings"]
    assert binding["from_artifact"] == kept["output_artifact"]["address"]
    assert binding["value_sha256"] == __import__("provenance.ledger", fromlist=["x"]).sha256_json({"v": BIG})


def test_ablation_without_the_route_the_mission_does_not_close_on_a_cut_value(tmp_path):
    home, root = start(tmp_path, by=None)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        states = tick(body, clock, 8)
        done = actions(body)
    assert "ACHIEVED" not in states
    assert [a["action_id"] for a in done if a["status"] == "DONE"] == ["read-a"]
    assert not (root / "b.txt").exists()


def test_ablation_without_the_kept_artifact_the_opted_in_edge_holds(tmp_path, monkeypatch):
    import greg.authority as authority
    monkeypatch.setattr(authority, "keep_output", lambda output, root: (authority.bounded(output), None))
    home, root = start(tmp_path)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        states = tick(body, clock, 8)
    assert "ACHIEVED" not in states and not (root / "b.txt").exists()


def test_a_tampered_artifact_holds_the_strategy_and_never_writes_a_prefix(tmp_path):
    home, root = start(tmp_path)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(8):
            clock.advance(60)
            body.tick()
            if any(a["action_id"] == "read-a" and a["status"] == "DONE" for a in actions(body)):
                break
        receipt = body.office.ledger.find(next(a for a in actions(body) if a["action_id"] == "read-a")["receipt"])
        path = output_store(home / "artifacts").path(receipt.payload["result"]["output_artifact"]["address"])
        path.chmod(0o600)
        path.write_bytes(b"{}")
        states = tick(body, clock, 6)
    assert "ACHIEVED" not in states
    assert not (root / "b.txt").exists()


def test_restart_binds_the_same_whole_value(tmp_path):
    home, root = start(tmp_path)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(8):
            clock.advance(60)
            body.tick()
            if any(a["action_id"] == "read-a" and a["status"] == "DONE" for a in actions(body)):
                break
        assert not any(a["action_id"] == "write-b" for a in actions(body))
    with Body(home, clock=clock) as body:
        body.boot()
        states = tick(body, clock, 8)
        write = next(a for a in actions(body) if a["action_id"] == "write-b" and a["status"] == "DONE")
    assert states[-1] == "ACHIEVED"
    assert (root / "b.txt").read_text() == BIG and write["bindings"][0]["from_artifact"]


def test_kept_outputs_never_spend_the_import_quota(tmp_path, monkeypatch):
    """Sensors re-observe large, changing outputs every tick. Kept in the import store, they would fill its quota and
    make artifact.store refuse imports until founder review; in their own root a full store only stops keeping
    outputs, and the receipt says why."""
    import greg.artifacts as artifacts
    monkeypatch.setattr(artifacts, "MAX_OBJECTS", 2)
    for i in range(2):
        assert receipt_result({"text": BIG + str(i)}, tmp_path)["output_artifact"]["address"]
    full = receipt_result({"text": BIG + "full"}, tmp_path)["output_artifact"]
    assert full["address"] is None and "quota" in full["unavailable"]
    assert not list((tmp_path / "sha256").glob("*/*"))           # the import store is untouched
    assert ArtifactStore(tmp_path).put(b"an import")[0].startswith("sha256:")
