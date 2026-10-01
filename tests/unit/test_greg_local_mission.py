"""Real local Git capability, synthetic pre-existing authority, no network."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

from egregore.repository_audit import capture, derive
from egregore.local_mission import ROOT, proposal, run_once, supervise
from events.spine import EventSpine
from policy.consequence_gate import ConsequenceGate
from provenance.ledger import EvidenceLedger
from tests.greg_proof_driver import authority, prepare
from verifier.local_repository_appraisal import appraise

PIN = "4999acff1a69502c05af455fbccfca380cad18ee"


@pytest.fixture
def mission(tmp_path):
    repositories = []
    for role in ("kernel", "dale", "wmi"):
        path = tmp_path / role
        path.mkdir()
        def git(*args):
            return subprocess.check_output(["git", "-C", str(path), *args], stderr=subprocess.DEVNULL).decode().strip()
        git("init", "-q")
        dependency = f"uniimente-kernel-boundaries @ https://github.com/dababiyoda/uniimente-kernel/archive/{PIN}.tar.gz"
        (path / "pyproject.toml").write_text('[project]\nname="fixture"\nversion="0.1.2"\ndependencies=[' + json.dumps(dependency) + ']\n')
        (path / "requirements.txt").write_text(dependency + "\n")
        git("add", ".")
        git("-c", "user.name=Proof Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false", "commit", "-qm", "bounded fixture")
        head = git("rev-parse", "HEAD")
        git("update-ref", "refs/remotes/origin/main", head)
        repositories.append(dict(role=role, path=str(path), commit=head))
    now = time.time()
    return dict(mission_id="greg-proof:local-audit", repositories=repositories,
                expected_pin=PIN, expected_version="0.1.2", due=now, deadline=now + 40)


def ledger(path, auth):
    return EvidenceLedger(auth["compiled"].constitution_hash, str(path), read_only=True)


def test_interface_exits_then_due_mission_recovers_without_human_tick(mission, tmp_path):
    mission["due"] = time.time() + 2
    job_file, history, result = [tmp_path / n for n in ("job.json", "history.jsonl", "result.json")]
    job_file.write_text(json.dumps(mission))
    child = subprocess.run([sys.executable, "-m", "tests.greg_proof_driver", str(job_file), str(history), str(result)],
                           cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert child.returncode == 0, child.stderr
    assert time.time() < mission["due"]  # Submitting process is gone before work becomes due.
    interface = json.loads(child.stdout)
    while not result.exists() and time.time() < mission["deadline"] + 3:
        time.sleep(.05)  # Observer only; no execution API or manual restart.
    assert result.exists(), Path(str(result) + ".log").read_text()
    status = json.loads(result.read_text())
    assert status["status"] == "COMPLETE", Path(str(result) + ".log").read_text()
    assert status["worker_exits"] == [75, 0]
    assert len(set(status["worker_pids"] + [interface["host_pid"], interface["interface_pid"]])) == 4
    auth = authority(mission)  # Read-only constitution hash; not passed to the running mission.
    records = ledger(history, auth)
    try:
        assert len(records.by_type("grant_dispatch")) == len(records.by_type("receipt")) == len(records.by_type("outcome")) == 1
        closed = EventSpine(records).replay("greg.closed")
        assert len(closed) == 1
        assert closed[0].payload["data"]["appraisal"]["report"]["compatible"]
        assert closed[0].payload["data"]["CMC"] == closed[0].payload["data"]["VDM"] == 0
        triggered = EventSpine(records).replay("greg.triggered")
        assert triggered[0].payload["data"]["at"] >= mission["due"]
    finally:
        records.close()


def test_completed_mission_reuses_retained_result(mission, tmp_path, monkeypatch):
    auth, path = authority(mission), tmp_path / "history"
    prepare(path, mission, auth)
    first = run_once(path, mission, **auth)
    monkeypatch.setattr("egregore.local_mission.capture", lambda _: pytest.fail("redispatch"))
    assert run_once(path, mission, **auth) == first


def test_missing_grant_blocks_and_stays_remembered(mission, tmp_path):
    auth, path = authority(mission), tmp_path / "history"
    prepare(path, mission, auth)
    auth["grant_id"] = "unregistered"
    result = supervise(path, mission, auth)
    assert result["status"] == "BLOCKED"
    assert "reconciliation" in result["next_reconsideration"]
    assert result["pending_message"]["kind"] == "RECOVERY_REQUIRED"
    assert supervise(path, mission, auth) == result
    history = ledger(path, auth)
    try:
        assert not history.by_type("grant_dispatch")
        assert not history.by_type("receipt")
        assert not EventSpine(history).replay("greg.closed")
    finally:
        history.close()


def test_changed_mission_is_rejected(mission, tmp_path):
    auth, path = authority(mission), tmp_path / "history"
    prepare(path, mission, auth)
    changed = dict(mission, expected_pin="a" * 40)
    with pytest.raises(ValueError, match="changed retained mission"):
        run_once(path, changed, **auth)


def test_future_obligation_waits_without_dispatch(mission, tmp_path):
    mission["due"] += 10
    auth, path = authority(mission), tmp_path / "history"
    prepare(path, mission, auth)
    assert run_once(path, mission, **auth)["status"] == "WAITING"


def test_source_changes_cannot_be_presented_as_adopted(mission):
    changed = copy.deepcopy(mission)
    changed["repositories"][0]["commit"] = "a" * 40
    with pytest.raises(ValueError, match="cached main changed"):
        capture(changed["repositories"])


def test_appraisal_reports_actual_discrepancy(mission):
    report = derive(capture(mission["repositories"]), "a" * 40, "0.1.2")
    assert report["compatible"] is False
    assert sum(row["matches"] for row in report["rows"]) == 1


def test_appraisal_rejects_wrong_retained_head(mission, tmp_path):
    auth, path = authority(mission), tmp_path / "history"
    prepare(path, mission, auth)
    result = run_once(path, mission, **auth)
    with pytest.raises(Exception, match="head"):
        appraise(dict(ledger=str(path), constitution=auth["compiled"].constitution_hash,
                      mission_id=mission["mission_id"], receipt=result["receipt"], head="a" * 64))


def test_reserved_matter_cannot_execute_without_approval(mission, tmp_path):
    auth = authority(mission)
    history = EvidenceLedger(auth["compiled"].constitution_hash, str(tmp_path / "approval-history"))
    try:
        gate = ConsequenceGate(compiled=auth["compiled"], passports=auth["passports"],
            grants=auth["grants"], signer=auth["signer"], ledger=history)
        p = proposal(mission, auth["actor"])
        p.action_class = "material_debt"
        grant = auth["grants"].issue_single_action(proposal=p, policy_version="1.0.0")
        result = gate.run(p, standing_grant=grant, executor=lambda _: pytest.fail("unapproved executor"))
        assert result.state != "recorded"
        assert result.state == "expired"
        assert "pending_human" in [step["state"] for step in result.trajectory]
        assert any("no approver available" in reason for reason in result.refusal_reasons)
        assert not history.by_type("grant_dispatch")
        assert not history.by_type("receipt")
    finally:
        history.close()


@pytest.mark.parametrize("failure_type, expected_calls, expected_claims", [
    ("grant_dispatch", 0, 0), ("receipt", 1, 1), ("outcome", 1, 1)])
def test_persistence_failure_never_fabricates_closure(mission, tmp_path, monkeypatch,
                                                    failure_type, expected_calls, expected_claims):
    auth, path = authority(mission), tmp_path / "history"
    prepare(path, mission, auth)
    append = EvidenceLedger.append
    calls = []
    def tool(repositories):
        calls.append(1)
        return capture(repositories)
    def failing_append(self, record_type, payload, **kwargs):
        if record_type == failure_type:
            raise OSError("injected persistence failure: " + failure_type)
        return append(self, record_type, payload, **kwargs)
    monkeypatch.setattr("egregore.local_mission.capture", tool)
    monkeypatch.setattr(EvidenceLedger, "append", failing_append)
    with pytest.raises(Exception):
        run_once(path, mission, **auth)
    assert len(calls) == expected_calls
    monkeypatch.setattr(EvidenceLedger, "append", append)
    if expected_claims:
        with pytest.raises(Exception):
            run_once(path, mission, **auth)
        assert len(calls) == 1  # No blind repetition after possible acceptance.
    history = ledger(path, auth)
    try:
        assert len(history.by_type("grant_dispatch")) == expected_claims
        assert not EventSpine(history).replay("greg.closed")
    finally:
        history.close()


def test_worker_lie_is_rejected_by_separate_appraiser(mission, tmp_path, monkeypatch):
    auth, path = authority(mission), tmp_path / "history"
    prepare(path, mission, auth)
    monkeypatch.setattr("egregore.local_mission.capture", lambda _: [])
    with pytest.raises(Exception):
        run_once(path, mission, **auth)
    history = ledger(path, auth)
    try:
        assert len(history.by_type("receipt")) == 1  # Negative evidence retained.
        assert not EventSpine(history).replay("greg.closed")
    finally:
        history.close()


def test_changed_implementation_requires_migration(mission, tmp_path, monkeypatch):
    auth, path = authority(mission), tmp_path / "history"
    prepare(path, mission, auth)
    monkeypatch.setattr("egregore.local_mission.code_digest", lambda: "changed")
    with pytest.raises(ValueError, match="migration"):
        run_once(path, mission, **auth)


def test_expired_mission_never_dispatches(mission, tmp_path):
    auth, path = authority(mission), tmp_path / "history"
    prepare(path, mission, auth)
    from unittest.mock import patch
    with patch("egregore.local_mission.time.time", return_value=mission["deadline"] + 1):
        result = supervise(path, mission, auth)
    assert result["status"] == "BLOCKED"
    assert result["worker_exits"] == []


def test_replacement_does_not_implicitly_transfer_identity(mission, tmp_path):
    auth, path = authority(mission), tmp_path / "history"
    prepare(path, mission, auth)
    replacement = authority(mission)
    with pytest.raises(ValueError, match="identity differs"):
        run_once(path, mission, **replacement)


def test_lost_host_claim_requires_reconciliation(mission, tmp_path):
    from egregore.local_mission import emit
    auth, path = authority(mission), tmp_path / "history"
    prepare(path, mission, auth)
    history = EvidenceLedger(auth["compiled"].constitution_hash, str(path))
    try:
        emit(EventSpine(history), auth["actor"], "host_started", mission, {"host_pid": -1})
    finally:
        history.close()
    result = supervise(path, mission, auth)
    assert result["status"] == "HOST_ALREADY_CLAIMED"
    assert result["worker_exits"] == []
