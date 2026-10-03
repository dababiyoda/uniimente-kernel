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
from greg.capabilities import BUILTINS, CapabilityManifest, CapabilityRegistry, InvocationContext
from greg.founder import _signing_bytes
from greg.journal import Journal
from greg.missions import evaluate_predicate
from provenance.ledger import EvidenceLedger, sha256_json

REOBSERVABLE = {"fs.read", "fs.list", "git.inspect", "repo.pin_audit", "repo.integration_audit", "brief.freshness",
                "memory.precedents", "artifact.inspect", "cognition.status", "foundry.query",
                "worker.appraise", "browser.trace"}
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


def _signed_command(journal, ledger, seq, command_digest, kind, expected_body):
    """Independently authenticate retained scope; no reconstruction grants anything."""
    accepted = [e.payload for e in journal.replay('command.accepted')
                if e.payload['digest'] == command_digest]
    if len(accepted) != 1 or not accepted[0].get('envelope'):
        return False
    env = accepted[0]['envelope']
    public = _founder_keys(journal, seq, ledger).get(env.get('founder_key_id'))
    try:
        if not public or sha256_json(env) != command_digest or env['kind'] != kind or env['body'] != expected_body:
            return False
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public)).verify(
            bytes.fromhex(env['signature']), _signing_bytes(env))
        return True
    except (InvalidSignature, ValueError, KeyError):
        return False


def _read_only_cognition_registry(journal, ledger, seq):
    """Project retained package state without restoring/attaching or writing events.

    Genesis.restore can append quarantine events. The read-only appraiser instead
    authenticates each permission-bearing attachment and passes cards to the
    worker, which re-pins package/runner files and independently checks the
    engine's output. Conservative detached/quarantined state never enables use.
    """
    from greg.genesis import CATALOG, package_adapter
    from greg.lightcone import LightCone
    from greg.mechanisms import PackageCandidate
    registry = CapabilityRegistry()
    for manifest, adapter in BUILTINS.values():
        registry.register(manifest, adapter, state='ATTACHED')
    valid_authority = True
    for event in journal.replay('capability.'):
        data = event.payload
        if event.type == 'greg.capability.registered' and data.get('origin', {}).get('kind') == 'package':
            manifest = CapabilityManifest.from_dict(data['manifest'])
            origin = data['origin']
            candidate = next((c for c in CATALOG.get(origin['function'], {}).get('candidates', ())
                              if isinstance(c, PackageCandidate) and c.runner == origin['runner'] and
                              c.distribution == origin['distribution']), None)
            if candidate is not None:
                registry.register(manifest, package_adapter(origin['function'], candidate), state='VERIFIED')
        elif event.type == 'greg.capability.state' and data['capability_id'] in registry.manifests:
            cid, state = data['capability_id'], data['state']
            if state != 'ATTACHED':
                registry.set_state(cid, state)
                continue
            authorized = False
            if data.get('by') == 'founder command':
                authorized = _signed_command(journal, ledger, seq[event.event_id], data.get('command_digest'),
                                              'CAPABILITY_ATTACH', {'capability_id': cid})
            elif data.get('by') == 'founder-signed mission auto_attach (read_only)':
                parents = [e for e in journal.replay('mission.registered')
                           if e.payload['mission_id'] == data.get('mission_id') and
                           seq[e.event_id] < seq[event.event_id]]
                if len(parents) == 1:
                    parent = parents[0]
                    spec = parent.payload['spec']
                    authorized = (spec.get('auto_attach', {}).get('max_consequence_class') == 'read_only' and
                                  registry.manifests[cid].consequence_class == 'read_only' and
                                  LightCone.from_dict(spec['light_cone'])._capability_inside(cid) and
                                  _signed_command(journal, ledger, seq[parent.event_id], parent.payload['command_digest'],
                                                  'MISSION', spec))
            if authorized:
                registry.set_state(cid, 'ATTACHED')
            else:
                valid_authority = False
    return registry, valid_authority


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
        cognitive_registry = None
        if any(c['sensor'].get('capability') == 'cognition.status' for c in spec['success_checks']):
            cognitive_registry, cognitive_authority = _read_only_cognition_registry(journal, ledger, seq)
            checks['cognition_attachment_authority_rederived'] = cognitive_authority
            if not cognitive_authority:
                findings.append('cognition package attachment lacks independently verified founder scope')

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
                                        secrets=None, manifest=manifest,
                                        deliver_root=Path(request["deliver_root"])
                                        if request.get("deliver_root") else None,
                                        journal=journal if cap in ("memory.precedents", "artifact.inspect", "cognition.status", "worker.appraise") else None,
                                        mission_id=mid,
                                        registry=cognitive_registry,
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

        # 6. preconditions honored: a gated action ran only while every check it requires was
        # last observed passing, and that observation's receipt satisfies the predicate
        requires = {s["action_id"]: s.get("requires", []) for s in spec["strategies"]}
        predicates = {c["check_id"]: c["predicate"] for c in spec["success_checks"]}
        preconditions_ok = True
        for e in journal.replay("mission.action"):
            action = e.payload
            if action["mission_id"] != mid or action["status"] != "DONE" or not requires.get(action["action_id"]):
                continue
            for check_id in requires[action["action_id"]]:
                before = [o.payload for o in journal.replay("mission.observed") if o.payload["mission_id"] == mid
                          and o.payload["check_id"] == check_id and seq[o.event_id] < seq[e.event_id]]
                last = before[-1] if before else None
                receipt = ledger.find(last["receipt"]) if last and last.get("receipt") else None
                held = bool(last and last.get("passed") and receipt is not None and evaluate_predicate(
                    predicates[check_id], receipt.payload["result"].get("output"))[0])
                if not held:
                    preconditions_ok = False
                    findings.append(f"{action['action_id']}: ran before {check_id} was observed passing")
        checks["preconditions_honored"] = preconditions_ok
        required = ("chain_intact", "founder_signature_verified", "checks_rederived_from_receipts",
                    "world_reobserved", "exactly_once", "deliveries_bound_to_evidence",
                    "approval_boundaries_honored", "preconditions_honored")
        if cognitive_registry is not None:
            required += ('cognition_attachment_authority_rederived',)
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
