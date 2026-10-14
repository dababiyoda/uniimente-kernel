"""The artifact is useful to another signed mission after complete process death."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys

from greg.body import Body
from tests.greg_fixtures import drop, make_body, mission, signed, workspace

ROOT = Path(__file__).resolve().parents[2]


def _run(home):
    child = subprocess.run([sys.executable, "-m", "greg", "--home", str(home), "run",
                            "--max-ticks", "5", "--tick-seconds", "0.05"], cwd=ROOT,
                           env={**os.environ, "PYTHONPATH": str(ROOT)}, capture_output=True, text=True,
                           timeout=45)
    assert child.returncode == 0, (child.stdout, child.stderr)


def test_real_process_replacement_recovers_receipt_bound_bytes(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    raw = b"recorded report\x00not a string"
    source = data / "source.bin"
    source.write_bytes(raw)
    address = "sha256:" + hashlib.sha256(raw).hexdigest()
    first = mission("m:artifact-import", checks=[{
        "check_id": "exists", "description": "artifact is addressable",
        "sensor": {"capability": "artifact.inspect", "target": "artifact:reports",
                   "params": {"namespace": "reports", "address": address}},
        "predicate": {"op": "equals", "field": "present", "value": True}}],
        strategies=[{"action_id": "store", "capability": "artifact.store", "target": "artifact:reports",
                     "params": {"namespace": "reports", "path": str(source)}, "advances": ["exists"],
                     "rationale": "keep a reproducible artifact", "expected_outcome": "retained"}],
        capabilities=["artifact.store", "artifact.inspect"], targets=("artifact:reports",))
    drop(home, signed(key, body_id, "MISSION", first))
    _run(home)
    with Body(home) as body:
        assert body.engine.book.missions["m:artifact-import"].status == "ACHIEVED"
        assert any(e.payload.get("mission_id") == "m:artifact-import" and e.payload.get("verdict") == "VERIFIED"
                   for e in body.journal.replay("mission.appraised"))

    dest = workspace(home, "m:artifact-reuse") / "recovered.bin"
    second = mission("m:artifact-reuse", checks=[{
        "check_id": "same", "description": "recovered bytes match",
        "sensor": {"capability": "fs.read", "target": "fs:recovered.bin", "params": {"path": str(dest)}},
        "predicate": {"op": "equals", "field": "sha256", "value": address[7:]}}],
        strategies=[{"action_id": "restore", "capability": "artifact.materialize",
                     "target": "workspace:recovered.bin",
                     "params": {"namespace": "reports", "address": address, "relative_path": "recovered.bin"},
                     "advances": ["same"], "rationale": "reuse prior evidence in a new mission",
                     "expected_outcome": "restored"}],
        capabilities=["artifact.materialize", "fs.read"], targets=("workspace:recovered.bin", "fs:recovered.bin"))
    drop(home, signed(key, body_id, "MISSION", second))
    _run(home)
    with Body(home) as body:
        assert dest.read_bytes() == raw
        assert body.engine.book.missions["m:artifact-reuse"].status == "ACHIEVED"
        assert any(e.payload.get("mission_id") == "m:artifact-reuse" and e.payload.get("verdict") == "VERIFIED"
                   for e in body.journal.replay("mission.appraised"))
        assert len([e for e in body.journal.replay("mission.action") if e.payload.get("mission_id") ==
                    "m:artifact-reuse" and e.payload["status"] == "DONE"]) == 1
