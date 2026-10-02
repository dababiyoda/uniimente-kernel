"""Owned OCI packaging through the real signed Body; image proof runs in CI."""
import io
import json
from pathlib import Path
import tarfile

import pytest

from foundry.oci_entry import evaluate
from foundry.systems import oci
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, signed, workspace

BASE = "python@sha256:" + "0" * 64


def package_with_body(tmp_path, base=BASE):
    home, key, body_id, _ = make_body(tmp_path)
    check = {"check_id": "packaged", "description": "owned pinned context is intact",
             "sensor": {"capability": "foundry.query", "target": "foundry:oci",
                        "params": {"system": 9, "op": "inspect"}},
             "predicate": {"op": "equals", "field": "result.intact", "value": True}}
    action = {"action_id": "package", "capability": "foundry.apply", "target": "foundry:oci",
              "params": {"system": 9, "op": "package", "args": {"base": base}},
              "advances": ["packaged"], "rationale": "package existing owned rule capability"}
    planned = mission("m:oci", checks=[check], strategies=[action],
                      capabilities=["foundry.query", "foundry.apply"], targets=("foundry:*",),
                      ceiling="internal_write")
    drop(home, signed(key, body_id, "MISSION", planned))
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(5):
            body.tick(); clock.advance(30)
        assert body.appraise("m:oci")["verdict"] == "VERIFIED"
    return workspace(home, "m:oci") / "foundry" / "system-09"


def test_signed_body_packages_exact_owned_bytes_and_tampering_refutes(tmp_path):
    root = package_with_body(tmp_path)
    state = oci.inspect(root)
    assert state["intact"] and state["manifest"]["image_built"] is False
    expected, _ = oci.context(BASE)
    assert (root / "context.tar").read_bytes() == expected
    with tarfile.open(fileobj=io.BytesIO(expected)) as tar:
        assert tar.extractfile("owned/dsl.py").read() == (oci.ROOT / "foundry/systems/dsl.py").read_bytes()
        dockerfile = tar.extractfile("Dockerfile").read()
        assert b"USER 10001:10001" in dockerfile and b"RUN " not in dockerfile
    (root / "context.tar").write_bytes(expected + b"substitute")
    assert not oci.inspect(root)["intact"]


@pytest.mark.parametrize("base", ["python:latest", "python:3.11", "private@sha256:" + "a" * 64,
                                  "python@sha256:" + "A" * 64, BASE + "\nRUN echo escaped"])
def test_mutable_foreign_and_injected_base_refused(base):
    with pytest.raises(ValueError, match="pinned"):
        oci.context(base)


def test_entry_uses_existing_dsl_and_refuses_source_and_non_numeric_inputs():
    path = oci.ROOT / "foundry/systems/dsl.py"
    assert evaluate({"language": "budget", "source": "min(requested, remaining-reserve)",
                     "inputs": {"requested": 90, "remaining": 80, "reserve": 10}}, path) == {"value": 70}
    for source, inputs in [("__import__('os').system('id')", {}), ("1", {"remaining": "80"}),
                           ("1", {"remaining": float("nan")}), ("1", {"unknown": 1})]:
        with pytest.raises(ValueError):
            evaluate({"language": "budget", "source": source, "inputs": inputs}, path)
