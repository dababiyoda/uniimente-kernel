"""Canonical CMC evidence resolution and fixed-process appraisal.

The EvidenceLedger and this verifier's code are trusted infrastructure. Direct
privileged mutation of that infrastructure is outside this simulation proof.
No identities, credentials, signatures or permissions are issued here.
"""
from __future__ import annotations
import copy
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import fcntl
from contextlib import contextmanager
from functools import wraps
from threading import RLock

from events.spine import Event
from omnimorph.organization_compiler import content_digest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "docs/organizational-morphogenesis/phase4/input.json"
IDENTITY = "spiffe://uniimente.internal/evaluator/cmc-protected-appraisal"
POLICY_FILES = ("verifier/appraisal_worker.py", "verifier/mission_audit.py",
                "verifier/retained_appraisal.py",
                "contracts/mission-appraisal.schema.json",
                "docs/organizational-morphogenesis/phase4/input.json")
MAX_BYTES = 262144
_LOCK = RLock()


def serialized(method):
    """One trusted writer; a stale process must reopen EventSpine, not append."""
    @wraps(method)
    def call(self, *args, **kwargs):
        with writer(self.spine):
            return method(self, *args, **kwargs)
    return call


@contextmanager
def writer(spine):
    with _LOCK:
        path = spine.ledger.path
        if not path:
            yield
            return
        with open(str(path) + ".cmc-appraisal.lock", "a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise AppraisalRefused("concurrent appraisal writer; reopen and reconcile") from exc
            with open(path) as handle:
                records = [json.loads(line) for line in handle if line.strip()]
            if not records or records[-1]["hash"] != spine.ledger.head:
                raise AppraisalRefused("stale EventSpine; reopen before writing")
            try:
                yield
            finally:
                sync(spine)


def sync(spine):
    if spine.ledger.path:
        with open(spine.ledger.path, "rb") as handle:
            os.fsync(handle.fileno())


class AppraisalRefused(ValueError):
    pass


def policy():
    return {"version": "CMC-002-repair-1", "purpose": "frozen-declared-route-audit",
            "source_code": {p: "sha256:" + sha256((ROOT / p).read_bytes()).hexdigest()
                            for p in POLICY_FILES},
            "authority": "none", "evidence_mode": "SIMULATION"}


def frozen_snapshot():
    corpus = json.loads(FIXTURE.read_text())
    raw = {p: (ROOT / p).read_text() for p in corpus["source_hashes"]}
    if {p: "sha256:" + sha256(t.encode()).hexdigest() for p, t in raw.items()} != corpus["source_hashes"]:
        raise AppraisalRefused("frozen corpus drift; no silent refresh")
    return {"corpus": corpus, "source_texts": raw}


def _seal(body):
    body = copy.deepcopy(body)
    body["digest"] = content_digest(body, excluding=("digest",))
    return body


def resolve(spine, ref, expected_type):
    if not spine.ledger.verify_chain()[0]:
        raise AppraisalRefused("ledger integrity failure")
    matches = [e for e in spine.replay() if e.event_id == ref]
    if len(matches) != 1 or matches[0].type != expected_type:
        raise AppraisalRefused("missing, fabricated or wrong-kind evidence reference")
    event = matches[0]
    if event.payload.get("digest") != content_digest(event.payload, excluding=("digest",)):
        raise AppraisalRefused("retained evidence digest mismatch")
    return event


def retain_snapshot(spine, mission, envelope, admission_id):
    body = _seal({"mission_id": mission["mission_id"], "task_id": envelope["task_id"],
                  "mission_digest": content_digest(mission),
                  "task_digest": content_digest(envelope), "snapshot": frozen_snapshot(),
                  "policy": policy(), "evidence_mode": "SIMULATION"})
    existing = [e for e in spine.replay("mission.evidence.retained")
                if e.payload.get("task_id") == envelope["task_id"]]
    if existing:
        if len(existing) != 1 or resolve(spine, existing[0].event_id, "mission.evidence.retained").payload != body:
            raise AppraisalRefused("source evidence cannot be silently replaced")
        return existing[0]
    return spine.emit(Event(type="mission.evidence.retained", source=IDENTITY, actor=IDENTITY,
        legal_principal=mission["legal_principal"], causal_parent=admission_id, payload=body))


def retain_result(spine, mission, envelope, result, evidence_refs, parent_id, submitted):
    body = _seal({"mission_id": mission["mission_id"], "task_id": envelope["task_id"],
                  "mission_digest": content_digest(mission), "task_digest": content_digest(envelope),
                  "worker_identity": submitted.worker_identity, "lease_id": submitted.lease_id,
                  "result": copy.deepcopy(dict(result)),
                  "result_digest": content_digest({"task_id": envelope["task_id"], "result": dict(result)}),
                  "evidence_refs": list(evidence_refs), "evidence_mode": "SIMULATION"})
    previous = [e for e in spine.replay("mission.result")
                if e.payload.get("task_id") == envelope["task_id"]]
    if previous:
        if len(previous) != 1 or resolve(spine, previous[0].event_id, "mission.result").payload != body:
            raise AppraisalRefused("retained result cannot be replaced")
        return previous[0]
    return spine.emit(Event(type="mission.result", source=submitted.worker_identity,
        actor=submitted.worker_identity, legal_principal=mission["legal_principal"],
        causal_parent=parent_id, payload=body))


def _request(spine, mission, envelope, submitted):
    results = [e for e in spine.replay("mission.result")
               if e.payload.get("task_id") == envelope["task_id"]]
    if len(results) != 1:
        raise AppraisalRefused("one retained result is required")
    result = resolve(spine, results[0].event_id, "mission.result")
    refs = list(submitted.evidence_refs)
    if len(refs) != 1 or result.payload["evidence_refs"] != refs:
        raise AppraisalRefused("one canonical source snapshot must match submission")
    source = resolve(spine, refs[0], "mission.evidence.retained")
    sources = [e for e in spine.replay("mission.evidence.retained")
               if e.payload.get("task_id") == envelope["task_id"]]
    if len(sources) != 1:
        raise AppraisalRefused("conflicting retained source snapshots")
    if (result.source != submitted.worker_identity
            or result.payload["worker_identity"] != submitted.worker_identity
            or result.payload["lease_id"] != submitted.lease_id):
        raise AppraisalRefused("result is not bound to the submitting worker lease")
    for e in (result, source):
        if (e.payload["mission_digest"] != content_digest(mission)
                or e.payload["task_digest"] != content_digest(envelope)
                or e.payload["mission_id"] != mission["mission_id"]
                or e.payload["task_id"] != envelope["task_id"]):
            raise AppraisalRefused("stale or cross-mission/task evidence")
    if result.causal_parent != source.event_id:
        raise AppraisalRefused("result/source causal parent mismatch")
    admissions = [e for e in spine.replay("mission.admitted")
                  if e.event_id == source.causal_parent]
    if (len(admissions) != 1 or admissions[0].payload["mission_digest"] != content_digest(mission)
            or admissions[0].payload["mission"] != mission):
        raise AppraisalRefused("source/admission causal parent mismatch")
    if source.payload["policy"] != policy() or source.payload["snapshot"] != frozen_snapshot():
        raise AppraisalRefused("stale source or evaluator policy")
    expected = content_digest({"task_id": envelope["task_id"], "result": result.payload["result"]})
    if result.payload["result_digest"] != expected or submitted.result_digest != expected:
        raise AppraisalRefused("submitted result digest mismatch")
    binding = {"mission_digest": content_digest(mission), "task_digest": content_digest(envelope),
               "worker_identity": submitted.worker_identity, "lease_id": submitted.lease_id,
               "submission_id": submitted.receipt_id, "submission_event_id": submitted.event_id,
               "source_event_id": source.event_id, "source_digest": source.payload["digest"],
               "result_event_id": result.event_id, "result_digest": expected}
    return {"snapshot": source.payload["snapshot"], "result": result.payload["result"],
            "binding": binding, "policy": policy()}


def appraisal(spine, mission, envelope, submitted, *, retained_only=False):
    """Return durable appraisal, or execute the fixed child once then retain it.

    A persisted START with no completed appraisal is uncertain and is refused,
    never automatically rerun. A new founder repair decision is required.
    """
    request = _request(spine, mission, envelope, submitted)
    existing = [e for e in spine.replay("mission.appraised")
                if e.payload.get("task_id") == envelope["task_id"]]
    if existing:
        if len(existing) != 1:
            raise AppraisalRefused("conflicting appraisal records")
        e = resolve(spine, existing[0].event_id, "mission.appraised")
        receipt = e.payload["receipt"]
        if (e.source != IDENTITY or receipt["binding"] != request["binding"]
                or receipt["policy"] != request["policy"]
                or receipt["digest"] != content_digest(receipt, excluding=("digest",))
                or receipt.get("appraisal_performed") is not True):
            raise AppraisalRefused("appraisal lineage or policy mismatch")
        start = resolve(spine, e.causal_parent, "mission.appraisal.started")
        if (start.source != IDENTITY or start.causal_parent != submitted.event_id
                or start.payload["binding"] != request["binding"]
                or start.payload["policy"] != request["policy"]):
            raise AppraisalRefused("appraisal start lineage mismatch")
        validate_receipt(receipt, request)
        return e
    if retained_only:
        raise AppraisalRefused("no protected appraisal has occurred")
    if any(e.payload.get("task_id") == envelope["task_id"]
           for e in spine.replay("mission.appraisal.started")):
        raise AppraisalRefused("interrupted appraisal requires reconciliation, not blind retry")
    start = spine.emit(Event(type="mission.appraisal.started", source=IDENTITY, actor=IDENTITY,
        legal_principal=mission["legal_principal"], causal_parent=submitted.event_id,
        payload=_seal({"mission_id": mission["mission_id"], "task_id": envelope["task_id"],
                       "binding": request["binding"], "policy": request["policy"]})))
    sync(spine)  # persist uncertainty marker before the child can run
    wire = json.dumps(request)
    if len(wire.encode()) > MAX_BYTES:
        raise AppraisalRefused("appraisal input ceiling exceeded")
    env = {"PATH": os.defpath, "PYTHONPATH": os.pathsep.join(
        p for p in sys.path if p and p.endswith("site-packages"))}
    try:
        proc = subprocess.run([sys.executable, "-B", "-s", str(ROOT / "verifier/appraisal_worker.py")],
            input=wire, text=True, capture_output=True, timeout=15, env=env, cwd=ROOT)
        if proc.returncode != 0:
            raise AppraisalRefused("fixed appraiser failed: " + proc.stderr[-800:])
        receipt = json.loads(proc.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
        raise AppraisalRefused("appraiser unavailable; no fallback acceptance") from exc
    if (receipt.get("binding") != request["binding"] or receipt.get("policy") != request["policy"]
            or receipt.get("appraisal_performed") is not True or receipt.get("process_id") == os.getpid()
            or receipt.get("digest") != content_digest(receipt, excluding=("digest",))):
        raise AppraisalRefused("invalid child appraisal receipt")
    validate_receipt(receipt, request)
    return spine.emit(Event(type="mission.appraised", source=IDENTITY, actor=IDENTITY,
        legal_principal=mission["legal_principal"], causal_parent=start.event_id,
        payload=_seal({"mission_id": mission["mission_id"], "task_id": envelope["task_id"],
                       "receipt": receipt, "evidence_mode": "SIMULATION"})))


def validate_receipt(receipt, request):
    from jsonschema import Draft202012Validator, ValidationError
    schema = json.loads((ROOT / "contracts/mission-appraisal.schema.json").read_text())
    try:
        Draft202012Validator(schema).validate(receipt)
    except ValidationError as exc:
        raise AppraisalRefused("invalid closed appraisal receipt schema") from exc
    report = receipt["report"]
    if (report["digest"] != content_digest(report, excluding=("digest",))
            or report["result_digest"] != content_digest(request["result"])
            or report["snapshot_digest"] != content_digest(request["snapshot"])
            or not report["dissent"]):
        raise AppraisalRefused("appraisal report is incomplete or mismatched")


def require_task_appraisal(spine, envelope, receipts, *, actor=None,
                           assessment_refs=None, dissent_refs=None):
    """Read-only transition guard. It cannot create an appraisal on demand."""
    admissions = [e for e in spine.replay("mission.admitted")
                  if e.payload.get("mission_id") == envelope["mission_id"]]
    if not admissions:
        return None  # other TaskFabric experiments retain their existing contract
    if len(admissions) != 1:
        raise AppraisalRefused("ambiguous mission admission")
    submitted = [r for r in receipts if r.state == "SUBMITTED"]
    if len(submitted) != 1:
        raise AppraisalRefused("one immutable submission is required")
    e = appraisal(spine, admissions[0].payload["mission"], envelope, submitted[0],
                  retained_only=True)
    report = e.payload["receipt"]["report"]
    if report["accepted"] is not True:
        raise AppraisalRefused("independent evaluator disagreed")
    if actor is not None and actor != IDENTITY:
        raise AppraisalRefused("caller is not the protected appraisal transition")
    if assessment_refs is not None and tuple(assessment_refs) != (e.event_id,):
        raise AppraisalRefused("assessment must resolve to the retained appraisal")
    if dissent_refs is not None and tuple(dissent_refs) != tuple(report["dissent"]):
        raise AppraisalRefused("required appraisal dissent was suppressed")
    return e
