"""Independent mission appraisal (Proof/Truth super-node).

Run as a separate process (``python -m greg.appraisal``) over a read-only,
head-pinned ledger. The engine's own "achieved" claim is not accepted; the
appraiser re-derives the result from retained bytes and from the world:

1. the mission body is exactly what an enrolled founder key signed (Ed25519 re-verified);
2. every success check is re-evaluated from its receipt's bytes (not the engine's flag);
3. read-only built-in sensors are re-run now, so the world must still match;
4. every consequential action has exactly one dispatch claim and one receipt;
5. any action that needed founder approval happened only after an approving decision.

Mechanism lineage: #101 verifier/local_repository_appraisal.py (separate process,
head binding, source re-read) and #94 protected appraisal (worker success is not
acceptance). Limit: this is a separate process running reviewed Kernel code, not an
independently written implementation or an OS sandbox against the host owner.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from events.spine import EventSpine
from greg.capabilities import BUILTINS, InvocationContext
from greg.founder import _signing_bytes
from greg.journal import Journal
from greg.missions import evaluate_predicate
from provenance.ledger import EvidenceLedger, sha256_json

REOBSERVABLE = {"fs.read", "fs.list", "git.inspect", "repo.pin_audit", "repo.integration_audit"}


def _founder_keys(journal: Journal, before_seq: int, ledger) -> dict:
    keys = {}
    seq = {r.payload.get("event_id"): r.seq for r in ledger.by_type("event")}
    for event in journal.replay("founder."):
        if seq.get(event.event_id, 1 << 60) > before_seq:
            continue
        if event.type == "greg.founder.enrolled":
            keys[event.payload["key_id"]] = event.payload["public_key"]
        elif event.type == "greg.founder.key_rotated":
            keys.pop(event.payload["old_key_id"], None)
            keys[event.payload["new_key_id"]] = event.payload["new_public_key"]
    return keys


def appraise(request: dict) -> dict:
    ledger = EvidenceLedger(request["constitution"], request["ledger"], read_only=True,
                            expected_head=request["head"])
    findings, checks = [], {}
    try:
        ok, why = ledger.verify_chain()
        checks["chain_intact"] = ok
        journal = Journal(EventSpine(ledger), actor="spiffe://uniimente.internal/greg/appraiser")
        mid = request["mission_id"]
        seq = {r.payload.get("event_id"): r.seq for r in ledger.by_type("event")}
        registered = [e for e in journal.replay("mission.registered") if e.payload["mission_id"] == mid]
        achieved = [e for e in journal.replay("mission.achieved") if e.payload["mission_id"] == mid]
        checks["registered_once"] = len(registered) == 1
        checks["achieved_claimed"] = len(achieved) == 1
        if not (registered and achieved):
            return _verdict(request, checks, ["mission not registered or not claimed achieved"])
        spec, digest = registered[0].payload["spec"], registered[0].payload["command_digest"]

        # 1. founder signature, re-verified independently of the body's acceptance
        accepted = [e.payload for e in journal.replay("command.accepted") if e.payload["digest"] == digest]
        signed = False
        if len(accepted) == 1 and accepted[0].get("envelope"):
            env = accepted[0]["envelope"]
            keys = _founder_keys(journal, seq[registered[0].event_id], ledger)
            public = keys.get(env.get("founder_key_id"))
            try:
                if public and sha256_json(env) == digest and env["kind"] == "MISSION" and env["body"] == spec:
                    Ed25519PublicKey.from_public_bytes(bytes.fromhex(public)).verify(
                        bytes.fromhex(env["signature"]), _signing_bytes(env))
                    signed = True
            except (InvalidSignature, ValueError, KeyError):
                signed = False
        checks["founder_signature_verified"] = signed
        if not signed:
            findings.append("mission body is not provably what an enrolled founder key signed")
        checks["arrived_via_inbox"] = bool(accepted) and accepted[0].get("channel") == "inbox"

        # 2. success checks re-derived from receipt bytes
        achieved_seq = seq[achieved[0].event_id]
        observations = [e for e in journal.replay("mission.observed")
                        if e.payload["mission_id"] == mid and seq[e.event_id] < achieved_seq]
        rederived, reobserved = True, True
        for check in spec["success_checks"]:
            latest = [o.payload for o in observations if o.payload["check_id"] == check["check_id"]]
            if not latest:
                continue  # checks outside the achieved rung are not required for this closure
            last = latest[-1]
            receipt = ledger.find(last["receipt"]) if last.get("receipt") else None
            if receipt is None or receipt.record_type != "receipt":
                rederived = False
                findings.append(f"{check['check_id']}: no retained receipt")
                continue
            passed, detail = evaluate_predicate(check["predicate"], receipt.payload["result"].get("output"))
            if not passed:
                rederived = False
                findings.append(f"{check['check_id']}: receipt bytes do not satisfy predicate ({detail})")
            # 3. re-observe the world now where a reviewed read-only sensor exists
            cap = check["sensor"].get("capability")
            if cap in REOBSERVABLE:
                manifest, adapter = BUILTINS[cap]
                ctx = InvocationContext(workspace=Path(request["workspace"]),
                                        read_roots=tuple(Path(p) for p in request["read_roots"]),
                                        secrets=None, manifest=manifest)
                try:
                    now_ok, now_detail = evaluate_predicate(check["predicate"],
                                                            adapter(check["sensor"].get("params", {}), ctx))
                except Exception as exc:  # the world could not be re-read: not verified
                    now_ok, now_detail = False, type(exc).__name__
                if not now_ok:
                    reobserved = False
                    findings.append(f"{check['check_id']}: world no longer matches ({now_detail})")
        checks["checks_rederived_from_receipts"] = rederived
        checks["world_reobserved"] = reobserved

        # 4. exactly-once consequences
        actions = [e.payload for e in journal.replay("mission.action")
                   if e.payload["mission_id"] == mid and e.payload["status"] == "DONE"]
        receipts = [a["receipt"] for a in actions if a.get("receipt")]
        dispatch = {}
        for r in ledger.by_type("grant_dispatch"):
            dispatch[r.payload["proposal_id"]] = dispatch.get(r.payload["proposal_id"], 0) + 1
        checks["exactly_once"] = len(receipts) == len(set(receipts)) and all(n == 1 for n in dispatch.values())
        if not checks["exactly_once"]:
            findings.append("duplicate receipt or dispatch claim")

        # 5. approval boundaries honored
        answered = {e.payload["request_id"]: (e.payload, seq[e.event_id]) for e in journal.replay("decision.answered")}
        approvals_ok, approvals_seen = True, 0
        for req in journal.replay("decision.requested"):
            data = req.payload
            if data.get("mission_id") != mid or data["kind"] != "APPROVAL":
                continue
            approvals_seen += 1
            executed = [e for e in journal.replay("mission.action") if e.payload["mission_id"] == mid
                        and e.payload.get("scope_digest") == data["scope_digest"] and e.payload["status"] == "DONE"]
            for e in executed:
                ans = answered.get(data["request_id"])
                if ans is None or ans[0]["answer"] != "approve" or ans[1] > seq[e.event_id]:
                    approvals_ok = False
                    findings.append(f"{e.payload['action_id']}: executed without a prior founder approval")
        checks["approval_boundaries_honored"] = approvals_ok
        checks["approval_boundary_encountered"] = approvals_seen > 0
        required = ("chain_intact", "founder_signature_verified", "checks_rederived_from_receipts",
                    "world_reobserved", "exactly_once", "approval_boundaries_honored")
        return _verdict(request, checks, findings, required=required)
    finally:
        ledger.close()


def _verdict(request, checks, findings, required=()):
    verified = bool(required) and all(checks.get(k) for k in required)
    return {"mission_id": request["mission_id"], "head": request["head"],
            "verdict": "VERIFIED" if verified else "REFUTED", "checks": checks, "findings": findings,
            "appraiser": "separate process over read-only head-pinned ledger; re-derivation + re-observation",
            "limits": "shares reviewed Kernel code; not an independent implementation"}


if __name__ == "__main__":
    raw = sys.stdin.read(1 << 20)
    print(json.dumps(appraise(json.loads(raw)), sort_keys=True))
