"""One bounded GREG proof using canonical workflow, ledger and authority owners.

This host accepts already-provisioned authority; it issues none. It is a fixed
local repository audit, not a general scheduler/goal engine or a live service.
The caller owns the host and must provide reviewed paths, identity and grants.
"""
from __future__ import annotations

import json
import math
import multiprocessing
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

from egregore.repository_audit import capture, validate_repositories, SHA
from events.spine import Event, EventSpine, WorkflowStep, durable_workflow, resume_workflow
from policy.consequence_gate import ConsequenceGate
from policy.engine import Proposal
from provenance.ledger import EvidenceLedger, ReconciliationRequired, sha256_json

SOURCE = "spiffe://uniimente.internal/egregore/local-mission-proof"
ROOT = Path(__file__).resolve().parents[1]


def validate_job(job):
    if set(job) != {"mission_id", "repositories", "expected_pin", "expected_version", "due", "deadline"}:
        raise ValueError("unknown or missing mission field")
    if not isinstance(job["mission_id"], str) or not job["mission_id"].startswith("greg-proof:"):
        raise ValueError("explicit proof mission identity required")
    validate_repositories(job["repositories"])
    if not SHA.fullmatch(job["expected_pin"]) or job["expected_version"] != "0.1.2":
        raise ValueError("unsupported package contract")
    if any(type(job[k]) not in (int, float) or not math.isfinite(job[k]) for k in ("due", "deadline")):
        raise ValueError("finite deadline required")
    if not 0 < job["deadline"] - job["due"] <= 60:
        raise ValueError("proof window must be at most 60 seconds")
    return json.loads(json.dumps(job))


def proposal(job, actor):
    job = validate_job(job)
    return Proposal(actor=actor, legal_principal="alfonso_lopez", action_class="repository.audit",
        objective=job["mission_id"], payload=job, target="local:approved-repository-snapshots",
        consequence_class="read_only", evidence_confidence=1.0,
        evidence_refs=[sha256_json(job)], estimated_cost_usd=0.0,
        requested_capability="repository.audit", expected_outcome="local repository snapshot retained",
        proposal_id="greg-audit-" + sha256_json(job))


def emit(spine, actor, kind, job, data):
    import uuid
    key = sha256_json({"mission": job["mission_id"], "kind": kind, "data": data})
    old = [e for e in spine.replay("greg." + kind) if e.payload["key"] == key]
    if old:
        return old[0]
    event = Event(type="greg." + kind, source=SOURCE, actor=actor,
        legal_principal="alfonso_lopez", event_id=str(uuid.uuid5(uuid.NAMESPACE_URL, key)),
        payload={"mission_id": job["mission_id"], "key": key, "data": data})
    spine.emit(event)
    return event


def bound_job(spine, job):
    records = [e for e in spine.replay("greg.submitted") if e.payload["mission_id"] == job["mission_id"]]
    if len(records) != 1 or records[0].payload["data"]["job"] != job:
        raise ValueError("missing or changed retained mission")
    return records[0]


def submit(path, job, gate, *, actor):
    """Submit once while the interface owns the writer; close it before hosting."""
    job = validate_job(job)
    if gate.ledger.path != str(path) or not time.time() < job["deadline"]:
        raise ValueError("wrong ledger or expired mission")
    spine = EventSpine(gate.ledger)
    existing = [e for e in spine.replay("greg.submitted") if e.payload["mission_id"] == job["mission_id"]]
    if existing:
        bound_job(spine, job)
        return
    emit(spine, proposal(job, actor).actor, "submitted", job,
         {"job": job, "code": code_digest(), "next_reconsideration": "due time or explicit operator review",
          "authentication": "host-provided workload identity; no founder authentication claim"})


def code_digest():
    files = ("egregore/local_mission.py", "verifier/local_repository_appraisal.py",
             "egregore/repository_audit.py")
    import hashlib
    return sha256_json({name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files})


def receipt_for(ledger, p):
    ids = {r.payload["action_id"] for r in ledger.by_type("event")
           if r.payload.get("type") == "action.proposed" and r.payload.get("proposal_id") == p.proposal_id}
    receipts = [r for r in ledger.by_type("receipt") if r.payload.get("action_id") in ids]
    outcomes = [r for r in ledger.by_type("outcome") if r.payload.get("action_ref") in ids]
    if receipts:
        if len(receipts) != 1 or len(outcomes) != 1:
            raise ReconciliationRequired("ambiguous retained acceptance")
        receipt = receipts[0]
        claims = [r for r in ledger.by_type("grant_dispatch")
                  if r.payload.get("proposal_id") == p.proposal_id]
        if (len(claims) != 1 or
                claims[0].payload.get("grant_id") != receipt.payload.get("grant_id") or
                claims[0].payload.get("witness_id") != receipt.payload.get("witness_id") or
                outcomes[0].payload.get("action_ref") != receipt.payload.get("action_id") or
                receipt.payload.get("result", {}).get("scope_digest") != sha256_json(p.payload)):
            raise ReconciliationRequired("retained acceptance binding mismatch")
        return receipts[0]
    if any(r.payload["proposal_id"] == p.proposal_id for r in ledger.by_type("grant_dispatch")):
        raise ReconciliationRequired("dispatch claimed without complete retained evidence")
    return None


def run_once(path, job, *, compiled, passports, grants, signer, actor, grant_id, crash_after_receipt=False):
    """Fixed reviewed worker. No authority provisioning or external channel."""
    job = validate_job(job)
    ledger = EvidenceLedger(compiled.constitution_hash, str(path))
    try:
        spine = EventSpine(ledger)
        submission = bound_job(spine, job)
        if submission.actor != actor:
            raise ValueError("worker identity differs from retained mission owner")
        if submission.payload["data"]["code"] != code_digest():
            raise ValueError("implementation changed; explicit migration required")
        closed = [e for e in spine.replay("greg.closed") if e.payload["mission_id"] == job["mission_id"]]
        if closed:
            return closed[-1].payload["data"]
        if time.time() < job["due"]:
            return {"status": "WAITING", "reconsider_at": job["due"]}
        if time.time() >= job["deadline"]:
            raise TimeoutError("mission deadline expired")
        gate = ConsequenceGate(compiled=compiled, passports=passports, grants=grants, signer=signer, ledger=ledger)
        p = proposal(job, actor)

        def audit(state):
            retained = receipt_for(ledger, p)
            if retained is None:
                grant = grants.get(grant_id)
                rec = gate.run(p, standing_grant=grant, executor=lambda _: {
                    "observed_outcome": p.expected_outcome, "result_class": "positive",
                    "sources": capture(job["repositories"]), "scope_digest": sha256_json(job),
                    "validation_status": "self_reported"})
                if rec.state != "recorded":
                    raise ReconciliationRequired("Gate refused or awaits reconciliation: " + "; ".join(rec.refusal_reasons))
                retained = receipt_for(ledger, p)
                if crash_after_receipt:
                    os._exit(75)  # Explicit proof fault, after durable result and before checkpoint.
            return {"receipt": retained.hash}

        def appraise(state):
            # The child receives no passport, grant, signer or callable. It opens
            # retained history read-only and checks the original local sources.
            request = {"ledger": str(path), "head": ledger.head, "constitution": compiled.constitution_hash,
                       "mission_id": job["mission_id"], "receipt": state["receipt"]}
            env = {"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
            # Dependencies only; exact application root is fixed by this module.
            env["PYTHONPATH"] = os.pathsep.join([str(ROOT)] + [s for s in sys.path if "site-packages" in s])
            child = subprocess.run([sys.executable, "-m", "verifier.local_repository_appraisal"],
                input=json.dumps(request), capture_output=True, text=True, timeout=15, env=env, cwd=ROOT)
            if child.returncode or len(child.stdout) > 65536:
                raise ReconciliationRequired("protected appraisal failed: " + child.stderr[-500:])
            result = json.loads(child.stdout)
            if result.get("receipt") != state["receipt"] or result.get("head") != request["head"]:
                raise ReconciliationRequired("appraisal binding mismatch")
            emit(spine, actor, "appraised", job, result)
            return {"appraisal": result}

        steps = [WorkflowStep("audit", audit, max_retries=0, retry_safe=True),
                 WorkflowStep("appraise", appraise, max_retries=0, retry_safe=True)]
        checkpoints = [r for r in ledger.by_type("workflow") if r.payload.get("workflow_id") == job["mission_id"]]
        if checkpoints and checkpoints[-1].payload["status"] == "completed":
            state = checkpoints[-1].payload["state"]
        else:
            wf = (resume_workflow(spine, job["mission_id"], steps) if checkpoints else
                  durable_workflow(spine, job["mission_id"], steps, actor=actor, legal_principal="alfonso_lopez"))
            state = wf.execute().state
        result = {"status": "VERIFIED_LOCAL_AUDIT", "mission_id": job["mission_id"],
                  "receipt": state["receipt"], "appraisal": state["appraisal"],
                  "CMC": 0, "VDM": 0, "founder_authenticated": False}
        emit(spine, actor, "closed", job, result)
        return result
    finally:
        ledger.close()


def _worker(path, job, authority, crash):
    os.setsid()
    try:
        run_once(path, job, **authority, crash_after_receipt=crash)
    except Exception:
        raise


def supervise(path, job, authority, *, crash_first=False):
    """Finite host: wait economically, replace a crashed worker, stop at bounds.

    Unix proof host only. A hardware service manager may call this composition
    later; no service is installed and no new grants are created on restart.
    """
    job = validate_job(job)
    started_at = time.monotonic()
    cpu_start = resource.getrusage(resource.RUSAGE_SELF)
    if job["due"] - time.time() > 60:
        raise ValueError("proof host will not wait more than 60 seconds")
    prior = EvidenceLedger(authority["compiled"].constitution_hash, str(path))
    try:
        spine = EventSpine(prior)
        bound_job(spine, job)
        stopped = [e for e in spine.replay("greg.host_stopped")
                   if e.payload["mission_id"] == job["mission_id"]]
        if stopped:
            return stopped[-1].payload["data"]
        started = [e for e in spine.replay("greg.host_started")
                   if e.payload["mission_id"] == job["mission_id"]]
        if started:
            return {"status": "HOST_ALREADY_CLAIMED", "worker_exits": [],
                    "next_reconsideration": "existing host completion or explicit operator reconciliation"}
        emit(spine, authority["actor"], "host_started", job,
             {"host_pid": os.getpid(), "at": time.time(), "due": job["due"],
              "priority": "sole admitted mission; no competing work",
              "limits": {"attempts": 3, "worker_seconds": 20, "window_seconds": 60,
                         "model_calls": 0, "external_spend_usd": 0}})
    finally:
        prior.close()
    while time.time() < min(job["due"], job["deadline"]):
        time.sleep(max(0, min(.1, job["due"] - time.time())))
    trigger_ledger = EvidenceLedger(authority["compiled"].constitution_hash, str(path))
    try:
        emit(EventSpine(trigger_ledger), authority["actor"], "triggered", job,
             {"at": time.time(), "host_pid": os.getpid(), "cause": "due time"})
    finally:
        trigger_ledger.close()
    exits = []
    worker_pids = []
    for attempt in range(3):
        if time.time() >= job["deadline"]:
            break
        process = multiprocessing.get_context("fork").Process(
            target=_worker, args=(path, job, authority, crash_first and attempt == 0))
        process.start()
        worker_pids.append(process.pid)
        try:
            process.join(min(20, max(0, job["deadline"] - time.time())))
            if process.is_alive():
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    process.kill()
                process.join(3)
            exits.append(process.exitcode)
        finally:
            if process.is_alive():
                process.kill()
                process.join(3)
            # Remove any descendants still in this worker's owned process group.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.close()
        if exits[-1] != 75:
            break
    ledger = EvidenceLedger(authority["compiled"].constitution_hash, str(path))
    try:
        spine = EventSpine(ledger)
        bound_job(spine, job)
        closed = [e for e in spine.replay("greg.closed") if e.payload["mission_id"] == job["mission_id"]]
        data = {"worker_exits": exits, "worker_pids": worker_pids, "attempt_limit": 3,
                "status": "COMPLETE" if closed else "BLOCKED",
                "next_reconsideration": None if closed else "explicit operator reconciliation; no blind redispatch"}
        cpu_end = resource.getrusage(resource.RUSAGE_SELF)
        data["host_elapsed_seconds"] = time.monotonic() - started_at
        data["host_cpu_seconds"] = ((cpu_end.ru_utime + cpu_end.ru_stime) -
                                    (cpu_start.ru_utime + cpu_start.ru_stime))
        if not closed:
            data["pending_message"] = {
                "kind": "RECOVERY_REQUIRED", "goal_id": job["mission_id"],
                "why_now": "bounded host stopped without verified closure",
                "requested_action": "review retained failure before any further execution",
                "evidence_head": ledger.head, "delivery": "retained locally; no real channel"}
        emit(spine, authority["actor"], "host_stopped", job, data)
        return data
    finally:
        ledger.close()
