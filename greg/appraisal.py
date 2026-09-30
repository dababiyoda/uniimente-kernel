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
from greg.authority import AuthorityOffice
from greg.capabilities import BUILTINS, CapabilityManifest, InvocationContext
from greg.founder import _signing_bytes
from greg.journal import Journal
from greg.missions import evaluate_predicate
from provenance.ledger import EvidenceLedger, sha256_json

REOBSERVABLE = {"fs.read", "fs.list", "git.inspect", "repo.pin_audit", "repo.integration_audit", "brief.freshness",
                "memory.precedents", "artifact.inspect"}
DELIVERING = {"brief.engineering": "greg.briefs", "venture.assess": "greg.ventures"}  # re-rendered from receipts


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


def _invocation_receipt_bound(ledger, journal, receipt, invocation, *, mission_id, command_digest,
                              closure_seq, since_seq, observation=True, claimed_scope=None,
                              claimed_capability=None) -> bool:
    """Match a receipt to the exact signed invocation via existing Gate lineage.

    Hash-chain integrity alone does not make an unrelated receipt evidence for
    this check. No signer secret enters the appraiser; the reviewed Gate's
    retained scope, witness and dispatch must agree on the invocation.
    """
    data = receipt.payload
    witnesses = [r for r in ledger.by_type("witness")
                 if r.seq < closure_seq and r.payload.get("witness_id") == data.get("witness_id")]
    dispatches = [r for r in ledger.by_type("grant_dispatch")
                  if r.seq < closure_seq and r.payload.get("grant_id") == data.get("grant_id")]
    grants = [r for r in ledger.by_type("event")
              if r.seq < closure_seq and r.payload.get("type") == "greg.authority.grant_issued"
              and r.payload.get("grant_id") == data.get("grant_id")]
    if not (len(witnesses) == len(dispatches) == len(grants) == 1):
        return False
    witness, dispatch, grant = witnesses[0], dispatches[0], grants[0]
    wd, dd, gd = witness.payload, dispatch.payload, grant.payload
    cid = wd.get("capability")
    manifest = BUILTINS[cid][0] if cid in BUILTINS else None
    if manifest is None:
        registrations = [e for e in journal.replay("capability.registered")
                         if e.payload.get("manifest", {}).get("capability_id") == cid
                         and next(r.seq for r in ledger.by_type("event")
                                  if r.payload.get("event_id") == e.event_id) < witness.seq]
        if registrations:
            manifest = CapabilityManifest.from_dict(registrations[-1].payload["manifest"])
    if manifest is None or (observation and manifest.consequence_class != "read_only"):
        return False
    if invocation.get("capability") != cid and not (invocation.get("capability") is None
                                                    and invocation.get("function") == manifest.function):
        return False
    target, params = invocation["target"], invocation.get("params", {})
    scope = AuthorityOffice.scope_digest(mission_id=mission_id, capability_id=cid, params=params,
                                         target=target, consequence_class=manifest.consequence_class,
                                         cost_usd=float(invocation.get("cost_usd", 0.0)))
    payload = {"capability": cid, "params": params, "manifest_digest": manifest.digest()}
    proposal_dispatches = [r for r in ledger.by_type("grant_dispatch")
                          if r.seq < closure_seq and r.payload.get("proposal_id") == dd.get("proposal_id")]
    granted_receipts = [r for r in ledger.by_type("receipt")
                        if r.seq < closure_seq and r.payload.get("grant_id") == data.get("grant_id")]
    return (grant.seq < witness.seq < dispatch.seq < receipt.seq
            and since_seq < dispatch.seq
            and len(proposal_dispatches) == len(granted_receipts) == 1
            and (claimed_scope is None or claimed_scope == scope)
            and (claimed_capability is None or claimed_capability == cid)
            and wd.get("grant_id") == data.get("grant_id")
            and dd.get("witness_id") == data.get("witness_id")
            and dd.get("proposal_id") == gd.get("proposal_id")
            and gd.get("scope_digest") == scope and gd.get("authority_ref") == command_digest
            and wd.get("target") == target and wd.get("action_class") == "greg." + cid
            and wd.get("payload_hash") == sha256_json(payload)
            and dd.get("effect_digest") == sha256_json({"payload": payload, "target": target,
                                                        "action_class": "greg." + cid})
            and wd.get("expected_outcome") == ("observation captured" if observation else
                                               invocation.get("expected_outcome", "strategy executed"))
            and command_digest in wd.get("evidence_refs", []))


def appraise(request: dict) -> dict:
    ledger = EvidenceLedger(request["constitution"], request["ledger"], read_only=True,
                            expected_head=request["head"], tail="ignore")
    findings, checks = [], {}
    try:
        ok, why = ledger.verify_chain()
        checks["chain_intact"] = ok
        journal = Journal(EventSpine(ledger), actor="spiffe://uniimente.internal/greg/appraiser")
        mid = request["mission_id"]
        seq = {r.payload.get("event_id"): r.seq for r in ledger.by_type("event")}
        registered = [e for e in journal.replay("mission.registered") if e.payload["mission_id"] == mid]
        if request.get("closure_event"):  # a standing mission's hold after new action
            achieved = [e for e in journal.replay("mission.held")
                        if e.event_id == request["closure_event"] and e.payload["mission_id"] == mid]
        else:
            achieved = [e for e in journal.replay("mission.achieved") if e.payload["mission_id"] == mid]
        checks["registered_once"] = len(registered) == 1
        checks["achieved_claimed"] = len(achieved) == 1
        if not (checks["registered_once"] and checks["achieved_claimed"]):
            return _verdict(request, checks, ["mission requires exactly one registration and selected closure"])
        spec, digest = registered[0].payload["spec"], registered[0].payload["command_digest"]
        registered_seq, achieved_seq = seq[registered[0].event_id], seq[achieved[0].event_id]
        expected_kind = "infinite" if request.get("closure_event") else "bounded"
        checks["closure_matches_signed_rule"] = (spec["closure"]["kind"] == expected_kind
                                                 and registered_seq < achieved_seq)
        if not checks["closure_matches_signed_rule"]:
            return _verdict(request, checks, ["selected closure does not match the signed mission closure rule"])

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
        # Holds exist only at the highest rung; earlier setpoints are not
        # closures. A ladder may intentionally leave other declared checks
        # inactive, so derive its cumulative required set from the signed spec.
        ladder = spec["closure"].get("ladder") or []
        wanted = set().union(*ladder) if expected_kind == "infinite" and ladder else {
            c["check_id"] for c in spec["success_checks"]}
        required_checks = [c for c in spec["success_checks"] if c["check_id"] in wanted]
        previous_holds = [seq[e.event_id] for e in journal.replay("mission.held")
                          if e.payload["mission_id"] == mid and seq[e.event_id] < achieved_seq]
        since = max([registered_seq, *previous_holds]) if expected_kind == "infinite" else registered_seq
        completed = [e for e in journal.replay("mission.action")
                     if e.payload["mission_id"] == mid and e.payload["status"] == "DONE"
                     and since < seq[e.event_id] < achieved_seq]
        if expected_kind == "infinite" and not completed:
            checks["closure_matches_signed_rule"] = False
            findings.append("standing closure requires a new completed action since its previous hold")
        after = max([since, *(seq[e.event_id] for e in completed)])
        observations = [e for e in journal.replay("mission.observed")
                        if e.payload["mission_id"] == mid and after < seq[e.event_id] < achieved_seq]
        evidence = achieved[0].payload.get("evidence", [])
        rederived, reobserved, bound = True, True, bool(required_checks)
        for check in required_checks:
            latest = [o for o in observations if o.payload["check_id"] == check["check_id"]]
            if not latest:
                rederived, reobserved, bound = False, False, False
                findings.append(f"{check['check_id']}: no fresh observation for selected closure")
                continue
            observation = latest[-1]
            last = observation.payload
            receipt = ledger.find(last["receipt"]) if last.get("receipt") else None
            if receipt is None or receipt.record_type != "receipt":
                rederived, bound = False, False
                findings.append(f"{check['check_id']}: no retained receipt")
                continue
            if (receipt.hash not in evidence or not after < receipt.seq < seq[observation.event_id]
                    or not _invocation_receipt_bound(ledger, journal, receipt, check["sensor"],
                                                    mission_id=mid, command_digest=digest,
                                                    closure_seq=achieved_seq, since_seq=after)):
                bound = False
                findings.append(f"{check['check_id']}: receipt not bound to this closure and signed sensor")
            passed, detail = evaluate_predicate(check["predicate"], receipt.payload["result"].get("output"))
            if not passed or receipt.payload["result"].get("result_class") != "positive":
                rederived = False
                findings.append(f"{check['check_id']}: receipt bytes do not satisfy predicate ({detail})")
            # 3. re-observe the world now where a reviewed read-only sensor exists
            cap = check["sensor"].get("capability")
            if cap in REOBSERVABLE:
                manifest, adapter = BUILTINS[cap]
                ctx = InvocationContext(workspace=Path(request["workspace"]),
                                        read_roots=tuple(Path(p) for p in request["read_roots"]),
                                        secrets=None, manifest=manifest,
                                        deliver_root=Path(request["deliver_root"])
                                        if request.get("deliver_root") else None,
                                        journal=journal if cap in ("memory.precedents", "artifact.inspect") else None,
                                        artifact_root=Path(request["artifact_root"])
                                        if request.get("artifact_root") else None,
                                        target=check["sensor"].get("target", ""))
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
        checks["closure_evidence_bound"] = bound

        # 4. exactly-once consequences
        action_events = [e for e in journal.replay("mission.action")
                         if e.payload["mission_id"] == mid and e.payload["status"] == "DONE"
                         and registered_seq < seq[e.event_id] < achieved_seq]
        actions = [e.payload for e in action_events]
        receipts = [a["receipt"] for a in actions if a.get("receipt")]
        once = len(receipts) == len(actions) == len(set(receipts))
        for event in action_events:
            action = event.payload
            receipt = ledger.find(action["receipt"]) if action.get("receipt") else None
            strategy = next((s for s in spec["strategies"] if s["action_id"] == action["action_id"]), None)
            if (receipt is None or receipt.record_type != "receipt" or strategy is None
                    or action.get("scope_digest") is None or action.get("capability") is None
                    or not registered_seq < receipt.seq < seq[event.event_id]
                    or receipt.payload.get("result", {}).get("result_class") != "positive"
                    or not _invocation_receipt_bound(ledger, journal, receipt, strategy, mission_id=mid,
                                                    command_digest=digest, closure_seq=achieved_seq,
                                                    since_seq=since if seq[event.event_id] > since else registered_seq,
                                                    observation=False, claimed_scope=action["scope_digest"],
                                                    claimed_capability=action["capability"])):
                once = False
                findings.append(f"{action['action_id']}: completed action lacks its signed strategy's Gate receipt")
        checks["exactly_once"] = once
        if not checks["exactly_once"]:
            findings.append("duplicate receipt or dispatch claim")

        # 4b. deliverables: the delivered file must be exactly the render of the receipted inputs
        # A standing mission's closure covers only the actions since its previous closure:
        # earlier deliveries were judged at their own closure against the evidence of that
        # time, and their superseded inputs are history, not a present-tense claim.
        window = actions
        if request.get("closure_event"):
            holds = sorted(seq[e.event_id] for e in journal.replay("mission.held")
                           if e.payload["mission_id"] == mid and seq[e.event_id] < achieved_seq)
            since = holds[-1] if holds else -1
            window = [e.payload for e in journal.replay("mission.action")
                      if e.payload["mission_id"] == mid and e.payload["status"] == "DONE"
                      and since < seq[e.event_id] < achieved_seq]
        import importlib
        delivered_ok = True
        for action in window:
            if action.get("capability") not in DELIVERING:
                continue
            receipt = ledger.find(action["receipt"]) if action.get("receipt") else None
            output = receipt.payload["result"].get("output") if receipt else None
            verify_delivery = importlib.import_module(DELIVERING[action["capability"]]).verify_delivery
            ok, detail = verify_delivery(output, Path(request["deliver_root"]) if request.get("deliver_root") else None)
            if not ok:
                delivered_ok = False
                findings.append(f"{action['action_id']}: {detail}")
        checks["deliveries_bound_to_evidence"] = delivered_ok

        # 5. approval boundaries honored
        answered = {e.payload["request_id"]: (e.payload, seq[e.event_id]) for e in journal.replay("decision.answered")
                    if registered_seq < seq[e.event_id] < achieved_seq}
        approvals_ok, approvals_seen = True, 0
        for req in journal.replay("decision.requested"):
            data = req.payload
            if (data.get("mission_id") != mid or data["kind"] != "APPROVAL"
                    or not registered_seq < seq[req.event_id] < achieved_seq):
                continue
            approvals_seen += 1
            executed = [e for e in journal.replay("mission.action") if e.payload["mission_id"] == mid
                        and e.payload.get("scope_digest") == data["scope_digest"] and e.payload["status"] == "DONE"
                        and registered_seq < seq[e.event_id] < achieved_seq]
            for e in executed:
                ans = answered.get(data["request_id"])
                if ans is None or ans[0]["answer"] != "approve" or ans[1] > seq[e.event_id]:
                    approvals_ok = False
                    findings.append(f"{e.payload['action_id']}: executed without a prior founder approval")
        checks["approval_boundaries_honored"] = approvals_ok
        checks["approval_boundary_encountered"] = approvals_seen > 0
        required = ("chain_intact", "registered_once", "achieved_claimed", "closure_matches_signed_rule",
                    "founder_signature_verified", "closure_evidence_bound", "checks_rederived_from_receipts",
                    "world_reobserved", "exactly_once", "deliveries_bound_to_evidence",
                    "approval_boundaries_honored")
        return _verdict(request, checks, findings, required=required)
    finally:
        ledger.close()


def _verdict(request, checks, findings, required=()):
    verified = bool(required) and all(checks.get(k) for k in required)
    return {"mission_id": request["mission_id"], "head": request["head"],
            "verdict": "VERIFIED" if verified else "REFUTED", "checks": checks, "findings": findings,
            "appraiser": "separate process over read-only head-pinned ledger; re-derivation + re-observation",
            "limits": "shares reviewed Kernel code; not an independent implementation",
            **({"closure_event": request["closure_event"]} if request.get("closure_event") else {})}


if __name__ == "__main__":
    raw = sys.stdin.read(1 << 20)
    print(json.dumps(appraise(json.loads(raw)), sort_keys=True))
