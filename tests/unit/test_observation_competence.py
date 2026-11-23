"""Observation competence for sensors and acquired readers.

A method that failed to measure the world is ranked after one that has not. A signed success
check is not an input to that ranking and its bytes stay what the founder signed.
"""
import hashlib
import json
from types import SimpleNamespace

from greg.capabilities import CapabilityError, CapabilityManifest, CapabilityRegistry
from greg.genesis import Candidate, Genesis
from greg.missions import measured
from greg.routing import OBSERVATION_WINDOW, observation_competence, observation_method_failed


def canonical_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


class _Journal:
    def __init__(self, observations):
        self.events = [SimpleNamespace(payload=dict(payload)) for payload in observations]

    def replay(self, prefix=""):
        if prefix in ("", "mission.observed"):
            return list(self.events)
        return []


def _reader(capability_id, function="hash.sha256"):
    return CapabilityManifest(
        capability_id=capability_id, version="1.0.0", provider="test", function=function,
        description="read-only acquired reader", route="api", consequence_class="read_only",
        inputs={"path": "str"}, outputs={"sha256": "str"}, target_prefix="fs:",
        retry_safe=True, strengthens=("proof",))


def _genesis(tmp_path, observations, *manifests):
    registry = CapabilityRegistry()
    for manifest in manifests:
        registry.register(manifest, lambda params, ctx: {}, state="ATTACHED")
    return Genesis(journal=_Journal(observations), registry=registry, workspace_root=tmp_path)


def test_the_failure_marker_matches_the_engines_measurement():
    failed = {"detail": "sensor REFUSED: reader exited", "passed": False}
    measured_miss = {"detail": "equals 'abc' != 'def'", "passed": False}
    assert observation_method_failed(failed) and not measured(failed)
    assert not observation_method_failed(measured_miss) and measured(measured_miss)


def test_a_failed_method_is_deprioritized_and_a_measured_miss_is_not(tmp_path):
    failed_id, other_id = "acquired.hash.sha256.sha256sum", "acquired.hash.sha256.shasum"
    failed, other = _reader(failed_id), _reader(other_id)
    no_memory = _genesis(tmp_path, [], failed, other)
    assert no_memory.find_attached("hash.sha256").capability_id == failed_id

    method_failure = {"capability": failed_id, "check_id": "digest", "passed": False,
                      "detail": "sensor REFUSED: reader exited"}
    before = canonical_bytes(method_failure)
    genesis = _genesis(tmp_path, [method_failure], failed, other)
    assert genesis.find_attached("hash.sha256").capability_id == other_id
    assert canonical_bytes(method_failure) == before
    assert observation_competence(genesis.journal)[failed_id] == {"method_failed": True}

    measured_miss = {"capability": failed_id, "check_id": "digest", "passed": False,
                     "detail": "field 'sha256' != expected"}
    still_first = _genesis(tmp_path, [measured_miss], failed, other)
    assert still_first.find_attached("hash.sha256").capability_id == failed_id


def test_a_later_measurement_and_the_window_bound_the_memory(tmp_path):
    failed_id, other_id = "acquired.hash.sha256.sha256sum", "acquired.hash.sha256.shasum"
    failed, other = _reader(failed_id), _reader(other_id)
    failure = {"capability": failed_id, "detail": "sensor REFUSED: reader exited", "passed": False}
    success = {"capability": failed_id, "detail": "equals the digest", "passed": True}
    restored = _genesis(tmp_path, [failure, success], failed, other)
    assert restored.find_attached("hash.sha256").capability_id == failed_id

    filler = [{"capability": f"acquired.hash.sha256.other{i}", "detail": "equals", "passed": True}
              for i in range(OBSERVATION_WINDOW)]
    expired = _genesis(tmp_path, [failure, *filler], failed, other)
    assert expired.find_attached("hash.sha256").capability_id == failed_id
    kept = _genesis(tmp_path, [failure, *filler[:-1]], failed, other)
    assert kept.find_attached("hash.sha256").capability_id == other_id


def test_acquired_reader_search_tries_a_failed_method_last(tmp_path):
    import inspect
    sha = Candidate("sha256sum", ("{binary}", "--", "{file}"), "first_hex_token")
    shasum = Candidate("shasum", ("{binary}", "-a", "256", "{file}"), "first_hex_token")
    failure = {"capability": "acquired.hash.sha256.sha256sum", "detail": "sensor REFUSED: reader exited",
               "passed": False}
    genesis = _genesis(tmp_path, [failure])
    ordered = [c.binary_name for c in genesis.acquired_reader_order("hash.sha256", (sha, shasum))]
    assert ordered == ["shasum", "sha256sum"]
    assert "acquired_reader_order(function, spec[\"candidates\"])" in inspect.getsource(Genesis.resolve)


def test_signed_checks_stay_byte_identical(tmp_path):
    """A function sensor may change which attached reader runs. The signed check bytes do not.

    A check that names a capability keeps that capability after the method fails.
    """
    from greg.body import Body
    from tests.greg_fixtures import Clock, drop, make_body, mission, signed

    home, key, body_id, data = make_body(tmp_path)
    target = data / "evidence.bin"
    target.write_bytes(b"evidence")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    failing_id, working_id = "acquired.hash.sha256.failing", "acquired.hash.sha256.working"
    function_check = {"check_id": "digest", "description": "evidence digest matches",
                      "sensor": {"function": "hash.sha256", "params": {"path": str(target)},
                                 "target": "fs:evidence.bin"},
                      "predicate": {"op": "equals", "field": "sha256", "value": digest}}
    pinned_check = {"check_id": "digest", "description": "evidence digest matches",
                    "sensor": {"capability": failing_id, "params": {"path": str(target)},
                               "target": "fs:evidence.bin"},
                    "predicate": {"op": "equals", "field": "sha256", "value": digest}}
    signed_function = canonical_bytes([function_check])
    signed_pinned = canonical_bytes([pinned_check])
    scope = ["acquired.hash.sha256.*"]
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:readers", checks=[function_check], strategies=[], capabilities=scope,
        targets=("fs:*",), ceiling="read_only", priority=90)))
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:pinned", checks=[pinned_check], strategies=[], capabilities=scope,
        targets=("fs:*",), ceiling="read_only", priority=10)))

    def failing_adapter(params, ctx):
        raise CapabilityError("reader exited")

    def working_adapter(params, ctx):
        return {"sha256": digest}

    clock = Clock()
    with Body(home, clock=clock) as body:
        body.registry.register(_reader(failing_id), failing_adapter, state="ATTACHED")
        body.registry.register(_reader(working_id), working_adapter, state="ATTACHED")
        for _ in range(4):
            body.tick()
            clock.advance(31)
        observed = [e.payload for e in body.journal.replay("mission.observed")]
        registered = {e.payload["mission_id"]: e.payload["spec"]
                      for e in body.journal.replay("mission.registered")}
        by_mission = {}
        for row in observed:
            by_mission.setdefault(row["mission_id"], []).append(row["capability"])

    assert by_mission["m:readers"] == [failing_id, working_id]
    assert by_mission["m:pinned"] and set(by_mission["m:pinned"]) == {failing_id}
    assert canonical_bytes(registered["m:readers"]["success_checks"]) == signed_function
    assert canonical_bytes(registered["m:pinned"]["success_checks"]) == signed_pinned
    assert canonical_bytes([function_check]) == signed_function
    assert canonical_bytes([pinned_check]) == signed_pinned
    assert "capability" not in registered["m:readers"]["success_checks"][0]["sensor"]
    assert registered["m:pinned"]["success_checks"][0]["sensor"]["capability"] == failing_id
