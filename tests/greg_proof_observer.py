"""Observe actual cached repositories under synthetic authority, never tick them.

Usage (inside tools/offline_test.py): -m tests.greg_proof_observer OUTPUT KERNEL DALE WMI
OUTPUT must be a new directory; the canonical ledger is retained alongside the
human-readable result projection. This is a proof runner, not a live installer.
"""
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

from compiler.ucl_compiler import compile_constitution
from egregore.local_mission import ROOT
from egregore.repository_audit import git_read
from events.spine import EventSpine
from provenance.ledger import EvidenceLedger


def observe(output, paths):
    output.mkdir(parents=True, exist_ok=False)
    repositories = [dict(role=role, path=str(path.resolve()), commit=git_read(
        str(path.resolve()), "rev-parse", "refs/remotes/origin/main").decode().strip())
        for role, path in zip(("kernel", "dale", "wmi"), paths, strict=True)]
    now = time.time()
    job = dict(mission_id="greg-proof:" + str(uuid.uuid4()), repositories=repositories,
        expected_pin="4999acff1a69502c05af455fbccfca380cad18ee", expected_version="0.1.2",
        due=now + 2, deadline=now + 40)
    job_file, history, result = [output / n for n in ("job.json", "ledger.jsonl", "host-result.json")]
    job_file.write_text(json.dumps(job, indent=2) + "\n")
    interface = subprocess.run([sys.executable, "-m", "tests.greg_proof_driver",
        str(job_file), str(history), str(result)], cwd=ROOT, capture_output=True, text=True, timeout=10)
    if interface.returncode:
        raise RuntimeError(interface.stderr)
    exited_at = time.time()
    while not result.exists() and time.time() < job["deadline"] + 3:
        time.sleep(.05)
    if not result.exists():
        raise RuntimeError("host did not retain result; inspect local host log")
    compiled = compile_constitution(str(ROOT))
    ledger = EvidenceLedger(compiled.constitution_hash, str(history), read_only=True)
    try:
        closed = EventSpine(ledger).replay("greg.closed")
        report = dict(interface=json.loads(interface.stdout), interface_exited_at=exited_at,
            interface_exited_before_due=exited_at < job["due"],
            host=json.loads(result.read_text()), ledger_head=ledger.head,
            dispatch_count=len(ledger.by_type("grant_dispatch")),
            receipt_count=len(ledger.by_type("receipt")), outcome_count=len(ledger.by_type("outcome")),
            closure=closed[0].payload["data"] if len(closed) == 1 else None,
            authority="synthetic test provisioning; not authenticated Alfonso",
            environment="development Linux; OS network denial supplied by offline launcher",
            hardware_activation=False)
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        if not (report["interface_exited_before_due"] and report["host"]["worker_exits"] == [75, 0]
                and report["dispatch_count"] == report["receipt_count"] == report["outcome_count"] == 1
                and report["closure"] is not None):
            raise RuntimeError("bounded proof did not meet its entry conditions; preserve evidence")
    finally:
        ledger.close()


if __name__ == "__main__":
    observe(Path(sys.argv[1]).resolve(), list(map(Path, sys.argv[2:])))
