"""Independent mission appraisal (Proof/Truth super-node).

Run as a separate process (``python -m greg.appraisal``) over a read-only,
head-pinned ledger. The engine's own "achieved" claim is not accepted; the
appraiser re-derives the result from retained bytes and from the world:

1. the mission body is exactly what an enrolled founder key signed (Ed25519 re-verified);
2. every success check the signed closure rule requires is re-evaluated from the receipt of a fresh
   observation inside the selected closure's window (not the engine's flag), and that receipt is bound
   to this mission's own grant -> witness -> dispatch -> receipt chain for the signed sensor;
3. read-only built-in sensors are re-run now, so the world must still match;
4. every action completed inside the closure window has exactly one dispatch claim and one receipt,
   bound to its signed strategy through the same Gate chain;
5. every completed action the founder-signed cone does not admit (re-derived here, not taken from the
   engine's asks) ran only after an exact-scope approval carried by a re-verified founder DECISION, or
   was pre-approved by the signed mission itself.

The closure window runs from the mission's one registration (or, for a standing mission, its previous
hold) to the selected closure; history outside it neither proves nor refutes this closure.

A failure closure (``mission.unmet``, #189) is verified the same way, in reverse: each check it names must
fail on a fresh, Gate-bound receipt's bytes and still fail when the world is re-read. Its verdict is
VERIFIED_UNMET, so no reader of VERIFIED takes it for a success, while settlement hears it.

Mechanism lineage: #101 verifier/local_repository_appraisal.py (separate process,
head binding, source re-read), #94 protected appraisal (worker success is not
acceptance) and #138 b8a0ccd (closure-bound evidence; ported 2026-10-14 with the binder
recomputing scope from the params the engine actually handed the Gate, i.e. after typed
handoffs were resolved). Limit: this is a separate process running reviewed Kernel code, not an
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
from greg.lightcone import LightCone
from greg.missions import INSUFFICIENT, TRUE, evaluate_receipt, judge, judge_receipt, pre_approved
from provenance.ledger import EvidenceLedger, sha256_json

REOBSERVABLE = {"fs.read", "fs.list", "git.inspect", "repo.pin_audit", "repo.integration_audit", "brief.freshness",
                "memory.precedents", "artifact.inspect", "cognition.status", "foundry.query", "pipeline.inspect",
                "worker.appraise", "browser.trace", "daleobanks.outcome", "organs.exchange_status",
                "institution.appraise", "organ.status"}
REOBSERVABLE.update(cid for cid in BUILTINS if cid.startswith("cognition.") and
                    cid not in ("cognition.semantic", "cognition.compose", "cognition.knowledge"))
DELIVERING = {"brief.engineering": "greg.briefs", "venture.assess": "greg.ventures",
              "organs.exchange": "greg.organ_exchange"}  # re-rendered from receipts


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


class _AsOf:
    """The journal as it stood before ledger position ``before``: later events are not replayed."""

    def __init__(self, journal: Journal, seq: dict, before: int):
        self.ledger, self._journal, self._seq, self._before = journal.ledger, journal, seq, before

    def replay(self, prefix: str):
        return [e for e in self._journal.replay(prefix) if self._seq.get(e.event_id, 1 << 60) < self._before]


def _handed_params(journal: Journal, seq: dict, invocation: dict, mission_id: str, before: int):
    """The params the engine handed the Gate for this signed sensor or strategy, or None.

    greg/missions.py resolves a strategy's signed ``bind`` edges (_bind) and then every inline
    ``$from_action`` reference (greg.pipeline.resolve) before office.act, and AuthorityOffice.scope_digest
    hashes those bound params. The appraiser re-derives them the same way, from this mission's own
    retained receipts as they stood before the grant, so a legitimate typed handoff verifies and a
    receipt bound for different params does not. Values are never read from the worker's projection.
    """
    from greg.missions import Unbound, _set_path, bound_value
    from greg.pipeline import BindingError, resolve
    view = _AsOf(journal, seq, before)
    params = json.loads(json.dumps(invocation.get("params", {})))
    try:
        if invocation.get("bind"):
            latest, passing = {}, {}
            for event in view.replay("mission.action"):
                data = event.payload
                if data.get("mission_id") == mission_id and data.get("status") == "DONE":
                    latest[data["action_id"]] = data.get("receipt")   # None: reconciled, never an older receipt
            for event in view.replay("mission.observed"):
                data = event.payload
                if data.get("mission_id") == mission_id and data.get("passed") and data.get("receipt"):
                    passing[data["check_id"]] = data["receipt"]       # a check-sourced edge binds its latest pass
            for edge in invocation["bind"]:
                source = edge["from"]
                held = passing.get(source["check_id"]) if "check_id" in source else latest.get(source["action_id"])
                record = journal.ledger.find(held or "")
                if record is None or record.record_type != "receipt" or record.seq >= before:
                    return None
                _set_path(params, edge["param"], bound_value(edge, record.payload.get("result", {}).get("output")))
        bound, _ = resolve(params, view, mission_id, before_seq=before)
    except (Unbound, BindingError, KeyError, TypeError):
        return None
    return bound


def _invocation_receipt_bound(ledger, journal, seq, receipt, invocation, *, mission_id, command_digest,
                              closure_seq, since_seq, observation=True, claimed_scope=None,
                              claimed_capability=None) -> bool:
    """Match a receipt to the exact signed invocation via existing Gate lineage.

    Hash-chain integrity alone does not make an unrelated receipt evidence for this check. No signer
    secret enters the appraiser; the reviewed Gate's retained grant, witness and dispatch must agree on
    this mission, its founder-signed command, the signed capability and target, and the params the
    engine handed the Gate (re-derived by ``_handed_params``).
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
    if manifest is None:            # a capability Genesis formed: the manifest registered before the witness
        registrations = [e for e in journal.replay("capability.registered")
                         if e.payload.get("manifest", {}).get("capability_id") == cid
                         and seq.get(e.event_id, 1 << 60) < witness.seq]
        if registrations:
            manifest = CapabilityManifest.from_dict(registrations[-1].payload["manifest"])
    if manifest is None or (observation and manifest.consequence_class != "read_only"):
        return False
    if invocation.get("capability") != cid and not (invocation.get("capability") is None
                                                    and invocation.get("function") == manifest.function):
        return False
    target = invocation["target"]
    params = _handed_params(journal, seq, invocation, mission_id, grant.seq)
    if params is None:
        return False
    cost = float(invocation.get("cost_usd", 0.0))
    scope = AuthorityOffice.scope_digest(mission_id=mission_id, capability_id=cid, params=params,
                                         target=target, consequence_class=manifest.consequence_class, cost_usd=cost)
    if cost > 0 and gd.get("scope_digest") != scope:
        # A paid scope binds the spend state it was dispatched at (#157 via #184). Re-derived here from retained
        # action records before the grant, never taken from the engine: booked spend plus open reservations.
        budget = _signed_budget(journal, mission_id, command_digest)
        if budget is not None:
            scope = AuthorityOffice.scope_digest(
                mission_id=mission_id, capability_id=cid, params=params, target=target,
                consequence_class=manifest.consequence_class, cost_usd=cost,
                spent_usd=_committed_before(journal, seq, mission_id, grant.seq), budget_usd=budget)
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


def _signed_budget(journal: Journal, mission_id: str, command_digest: str):
    """The budget of the founder-signed mission this appraisal checks (its retained registration)."""
    for e in journal.replay("mission.registered"):
        if e.payload.get("mission_id") == mission_id and e.payload.get("command_digest") == command_digest:
            return float(e.payload["spec"]["light_cone"]["budget_usd"])
    return None


def _committed_before(journal: Journal, seq: dict, mission_id: str, before: int) -> float:
    """Booked spend plus every unreconciled dispatch at its worst case, as retained before ledger position
    ``before``: the spend state a paid dispatch's scope binds (re-derived; the engine's fold is not trusted)."""
    spent, reserved = 0.0, {}
    signed = {}
    for e in journal.replay("mission.registered"):
        if e.payload.get("mission_id") == mission_id:
            signed = {s["action_id"]: float(s.get("cost_usd", 0.0)) for s in e.payload["spec"].get("strategies", [])}
    for e in journal.replay("mission.action"):
        p = e.payload
        if p.get("mission_id") != mission_id or seq.get(e.event_id, 1 << 60) >= before:
            continue
        slot = (p.get("action_id"), p.get("attempt"))
        if p.get("status") == "UNCERTAIN":
            # as the fold reads it: a #184-era record holds the cap it recorded (cost_reserved), an older one its
            # signed cost
            legacy = float(p.get("cost_usd", 0.0) or 0.0) if p.get("cost_reserved") else signed.get(p.get("action_id"), 0.0)
            reserved[slot] = float(p["reserved_usd"]) if "reserved_usd" in p else legacy
        else:
            reserved.pop(slot, None)
            # booked spend: a completion, and a metered run reconciled "not executed" at its cap (#178 H.G4)
            if p.get("status") in ("DONE", "RECONCILED_NOT_EXECUTED"):
                spent += float(p.get("cost_usd", 0.0) or 0.0)
    return round(spent + round(sum(reserved.values()), 9), 9)


def _instant_or_none(value):
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else None
    except ValueError:
        return None


def _manifest_before(journal: Journal, seq: dict, cid, before: int):
    """The manifest a capability had when it ran: a built-in, or the one Genesis registered before it."""
    if cid in BUILTINS:
        return BUILTINS[cid][0]
    registrations = [e for e in journal.replay("capability.registered")
                     if e.payload.get("manifest", {}).get("capability_id") == cid
                     and seq.get(e.event_id, 1 << 60) < before]
    return CapabilityManifest.from_dict(registrations[-1].payload["manifest"]) if registrations else None


def _devices_before(journal: Journal, seq: dict, before: int) -> dict:
    """Device delegations as the ledger stood at ``before``, under the body's rule (greg.body.device_delegations):
    a key delegated again after a revocation carries ``signed_not_before``, the recorded time of that re-delegation,
    and nothing it signed before then verifies (an old token never reactivates)."""
    devices, revoked = {}, set()
    for event in journal.replay("device."):
        if seq.get(event.event_id, 1 << 60) > before:
            continue
        kid = event.payload.get("device_key_id")
        if event.type == "greg.device.enrolled":
            devices[kid] = ({**event.payload, "signed_not_before": event.payload.get("at")} if kid in revoked
                            else event.payload)
        elif event.type == "greg.device.revoked":
            revoked.add(kid)
            devices.pop(kid, None)
    return devices


def _decision_signed(journal: Journal, ledger, seq: dict, answer: dict, answer_seq: int, request_id: str,
                     before: int) -> bool:
    """The answer is carried by exactly one accepted DECISION approving this request, whose retained
    envelope re-verifies against a founder key, or a delegated device key allowed to sign DECISION,
    as the ledger stood when the answer was recorded."""
    commands = [e.payload for e in journal.replay("command.accepted")
                if e.payload.get("digest") == answer.get("command_digest") and seq.get(e.event_id, 1 << 60) < before]
    if len(commands) != 1 or not isinstance(commands[0].get("envelope"), dict):
        return False
    env = commands[0]["envelope"]
    body = env.get("body") or {}
    if (sha256_json(env) != answer.get("command_digest") or env.get("kind") != "DECISION"
            or body.get("request_id") != request_id or body.get("answer") != "approve"):
        return False
    kid = env.get("founder_key_id")
    public = _founder_keys(journal, answer_seq, ledger).get(kid)
    if public is None:
        device = _devices_before(journal, seq, answer_seq).get(kid)
        issued, expires = _instant_or_none(env.get("issued_at")), _instant_or_none((device or {}).get("expires_at"))
        if (device is None or "DECISION" not in device.get("kinds", []) or issued is None or expires is None
                or not issued < expires):
            return False
        if "signed_not_before" in device:    # re-delegated: unbounded (no recorded time) refuses, as old tokens do
            not_before = _instant_or_none(device["signed_not_before"])
            if not_before is None or issued < not_before:
                return False
        public = device["public_key"]
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public)).verify(bytes.fromhex(env["signature"]),
                                                                          _signing_bytes(env))
    except (InvalidSignature, ValueError, KeyError, TypeError):
        return False
    return True


def _approved_before(journal, ledger, seq, requests, answers, scope_digest, at_seq) -> bool:
    """An exact-scope request of this mission, answered "approve" by a verified founder DECISION before
    the action ran."""
    for request in requests:
        data = request.payload
        answer = answers.get(data["request_id"])
        if (scope_digest and data.get("scope_digest") == scope_digest and seq[request.event_id] < at_seq
                and answer is not None and answer[0].get("answer") == "approve" and answer[1] < at_seq
                and _decision_signed(journal, ledger, seq, answer[0], answer[1], data["request_id"], at_seq)):
            return True
    return False


def _formed_registry(journal: Journal, workspace) -> object:
    """The body's registry as retained: built-ins plus every capability Genesis formed (constructed,
    acquired, built), re-pinned and re-checked as at restart, with nothing written to the ledger."""
    from greg.cognition.cortex import registry_view
    from greg.genesis import Genesis
    registry = registry_view(journal)
    Genesis(journal=journal, registry=registry, workspace_root=Path(workspace)).restore(record=False)
    return registry


def appraise(request: dict) -> dict:
    ledger = EvidenceLedger(request["constitution"], request["ledger"], read_only=True,
                            expected_head=request["head"], tail="ignore")
    findings, checks = [], {}
    try:
        ok, why = ledger.verify_chain()
        checks["chain_intact"] = ok
        journal = Journal(EventSpine(ledger), actor="spiffe://uniimente.internal/greg/appraiser")
        mid = request["mission_id"]
        # whole outputs the body kept beside cut receipts: read only by a receipt's recorded address, re-hashed
        artifacts = Path(request["artifact_root"]) if request.get("artifact_root") else None
        seq = {r.payload.get("event_id"): r.seq for r in ledger.by_type("event")}
        registered = [e for e in journal.replay("mission.registered") if e.payload["mission_id"] == mid]
        unmet = False
        if request.get("closure_event"):  # a standing mission's hold after new action, or a failure closure
            achieved = [e for e in journal.replay("mission.held")
                        if e.event_id == request["closure_event"] and e.payload["mission_id"] == mid]
            if not achieved:
                achieved = [e for e in journal.replay("mission.unmet")
                            if e.event_id == request["closure_event"] and e.payload["mission_id"] == mid]
                unmet = bool(achieved)
        else:
            achieved = [e for e in journal.replay("mission.achieved") if e.payload["mission_id"] == mid]
        checks["registered_once"] = len(registered) == 1
        checks["achieved_claimed"] = len(achieved) == 1
        if not (checks["registered_once"] and checks["achieved_claimed"]):
            return _verdict(request, checks, ["mission requires exactly one registration and selected closure"])
        spec, digest = registered[0].payload["spec"], registered[0].payload["command_digest"]
        registered_seq, achieved_seq = seq[registered[0].event_id], seq[achieved[0].event_id]
        # A failure closure (mission.unmet, #189) may close either kind of mission: every admissible strategy ran
        # and its named checks still fail. A success closure must be the one the signed rule selects.
        expected_kind = (spec["closure"]["kind"] if unmet
                         else "infinite" if request.get("closure_event") else "bounded")
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
        # Holds exist only at the highest rung; earlier setpoints are not closures. A ladder may
        # intentionally leave other declared checks inactive, so its required set is the cumulative
        # union of its signed rungs. Every required check needs a fresh observation after the last
        # completed action in the window: a pre-action reading cannot prove the action's outcome.
        ladder = spec["closure"].get("ladder") or []
        wanted = set().union(*ladder) if expected_kind == "infinite" and ladder else {
            c["check_id"] for c in spec["success_checks"]}
        # A failure closure is verified the same way, in reverse: each check it names must fail on its receipt's
        # bytes and still fail when the world is re-read; checks it does not name are not part of the claim.
        failing = set(achieved[0].payload.get("failing_checks") or []) if unmet else set()
        required_checks = [c for c in spec["success_checks"] if c["check_id"] in (failing if unmet else wanted)]
        previous_holds = [seq[e.event_id] for e in journal.replay("mission.held")
                          if e.payload["mission_id"] == mid and seq[e.event_id] < achieved_seq]
        since = max([registered_seq, *previous_holds]) if expected_kind == "infinite" else registered_seq
        completed = [e for e in journal.replay("mission.action")
                     if e.payload["mission_id"] == mid and e.payload["status"] == "DONE"
                     and since < seq[e.event_id] < achieved_seq]
        if expected_kind == "infinite" and not unmet and not completed:
            checks["closure_matches_signed_rule"] = False
            findings.append("standing closure requires a new completed action since its previous hold")
        # The engine closes a mission unmet only once something ran (greg/missions.py: actions_done); re-derived here
        # from the retained actions, not taken from the record: with nothing run there is no outcome to settle.
        if unmet and not any(e.payload["mission_id"] == mid and e.payload["status"] == "DONE"
                             and registered_seq < seq[e.event_id] < achieved_seq
                             for e in journal.replay("mission.action")):
            checks["closure_matches_signed_rule"] = False
            findings.append("a failure closure requires a completed action; nothing ran, so there is no outcome")
        after = max([since, *(seq[e.event_id] for e in completed)])
        observations = [e for e in journal.replay("mission.observed")
                        if e.payload["mission_id"] == mid and after < seq[e.event_id] < achieved_seq]
        # A failure closure records no evidence list (greg/missions.py), so its receipts are bound by the window and
        # the Gate chain below; any closure that does cite evidence must cite the receipt re-derived here.
        cited = achieved[0].payload.get("evidence")
        evidence = cited or []
        rederived, reobserved, bound = True, True, bool(required_checks)
        if unmet and not failing:
            rederived = False
            findings.append("a failure closure names no failing check")
        for check in required_checks:
            latest = [o for o in observations if o.payload["check_id"] == check["check_id"]]
            if not latest:
                rederived, reobserved, bound = False, False, False
                findings.append(f"{check['check_id']}: no fresh observation " + (
                    "of the claimed failure" if unmet else "for selected closure"))
                continue
            observation = latest[-1]
            last = observation.payload
            receipt = ledger.find(last["receipt"]) if last.get("receipt") else None
            if receipt is None or receipt.record_type != "receipt":
                rederived, bound = False, False
                findings.append(f"{check['check_id']}: no retained receipt")
                continue
            if (((cited is not None or not unmet) and receipt.hash not in evidence)
                    or not after < receipt.seq < seq[observation.event_id]
                    or not _invocation_receipt_bound(ledger, journal, seq, receipt, check["sensor"],
                                                    mission_id=mid, command_digest=digest,
                                                    closure_seq=achieved_seq, since_seq=after)):
                bound = False
                findings.append(f"{check['check_id']}: receipt not bound to this closure and signed sensor")
            # the receipt's kept output, or the whole output it kept in the body's artifact store, re-hashed here
            verdict, detail = judge_receipt(check["predicate"], receipt.payload["result"], artifacts)
            passed = verdict == TRUE
            if passed == unmet:
                rederived = False
                findings.append(f"{check['check_id']}: receipt bytes " + (
                    f"satisfy the predicate the closure says fails ({detail})" if unmet
                    else f"do not satisfy predicate ({detail})"))
            elif verdict == INSUFFICIENT:
                # Bytes that cannot decide the predicate prove no failure (an undecided success closure is refused
                # just above). Before, an undecided reading counted as a verified failure, and VERIFIED_UNMET
                # certified a check that was never measured (review of #196, J2).
                rederived = False
                findings.append(f"{check['check_id']}: receipt bytes cannot decide the predicate, so they prove "
                                f"no failure ({detail})")
            elif receipt.payload["result"].get("result_class") != "positive":
                # A refused sensor run is no reading of the world: it proves neither a success nor a failure.
                rederived = False
                findings.append(f"{check['check_id']}: receipt bytes " + (
                    f"are a refused observation, not a reading of the claimed failure ({detail})" if unmet
                    else f"do not satisfy predicate ({detail})"))
            # 3. re-observe the world now where a reviewed read-only sensor exists
            cap = check["sensor"].get("capability")
            if cap in REOBSERVABLE:
                manifest, adapter = BUILTINS[cap]
                ctx = InvocationContext(workspace=Path(request["workspace"]),
                                        read_roots=tuple(Path(p) for p in request["read_roots"]),
                                        secrets=None, manifest=manifest,
                                        deliver_root=Path(request["deliver_root"])
                                        if request.get("deliver_root") else None,
                                        journal=journal if cap in ("memory.precedents", "artifact.inspect", "worker.appraise", "daleobanks.outcome")
                                        or cap.startswith(("cognition.", "pipeline.", "institution.", "organ.", "foundry.")) else None,
                                        mission_id=mid,
                                        artifact_root=Path(request["artifact_root"])
                                        if request.get("artifact_root") else None,
                                        target=check["sensor"].get("target", ""),
                                        capability_registry=_formed_registry(journal, request["workspace"])
                                        if cap.startswith("cognition.") else None,
                                        worker_confinement=request.get("worker_confinement", "required"))
                try:
                    from greg.pipeline import resolve
                    bound_params, _ = resolve(check["sensor"].get("params", {}), journal, mid)
                    output = adapter(bound_params, ctx)
                    now_verdict, now_detail = judge(check["predicate"], output)
                    # an undecided re-reading (a list at the item limit, a declared-incomplete output) is no
                    # measurement of the world, either way
                    now_ok = None if now_verdict == INSUFFICIENT else now_verdict == TRUE
                    reasons = output.get("findings") if isinstance(output, dict) else None
                    if not now_ok and isinstance(reasons, list) and reasons:
                        # Say why, in the capability's own words: a forged acceptance and a host that cannot
                        # re-run the acceptance envelope must not read the same on the Proof view.
                        now_detail += "; because: " + "; ".join(str(r)[:200] for r in reasons[:3])
                except Exception as exc:  # the world could not be re-read: not verified, either way
                    now_ok, now_detail = None, type(exc).__name__
                if now_ok is None or now_ok == unmet:
                    reobserved = False
                    findings.append(f"{check['check_id']}: " + (
                        "the world could not be re-measured" if now_ok is None else "world no longer matches")
                        + f" ({now_detail})")
        checks["checks_rederived_from_receipts"] = rederived
        checks["world_reobserved"] = reobserved
        checks["closure_evidence_bound"] = bound

        # 4. exactly-once consequences, inside this closure's window only: each completed action has
        # its own receipt, bound to its signed strategy's one grant, witness and dispatch. Another
        # mission's dispatches, and actions after this closure, neither prove nor refute it.
        action_events = [e for e in journal.replay("mission.action")
                         if e.payload["mission_id"] == mid and e.payload["status"] == "DONE"
                         and registered_seq < seq[e.event_id] < achieved_seq]
        actions = [e.payload for e in action_events]
        receipts = [a["receipt"] for a in actions if a.get("receipt")]
        once = len(receipts) == len(actions) == len(set(receipts))
        # The Gate keeps one durable dispatch claim per proposal and per grant (policy/consequence_gate.py refuses
        # a second). A second claim in this window naming a completed action's proposal or grant is reported as
        # the duplicate it is; it also unbinds that action's receipt, so exactly_once fails.
        window_claims = [r.payload for r in ledger.by_type("grant_dispatch") if registered_seq < r.seq < achieved_seq]
        for event in action_events:
            action = event.payload
            receipt = ledger.find(action["receipt"]) if action.get("receipt") else None
            strategy = next((s for s in spec["strategies"] if s["action_id"] == action["action_id"]), None)
            settled = action.get("reconciles") or {}
            proposal = settled.get("proposal_id") or (AuthorityOffice.proposal_id(action["scope_digest"],
                                                                                  action.get("attempt"))
                                                      if action.get("scope_digest") else None)
            grant_id = (receipt.payload.get("grant_id") if receipt is not None and receipt.record_type == "receipt"
                        else settled.get("grant_id"))
            claimed = [c for c in window_claims if (proposal and c.get("proposal_id") == proposal)
                       or (grant_id and c.get("grant_id") == grant_id)]
            if len(claimed) > 1:
                once = False
                findings.append(f"{action['action_id']}: {len(claimed)} Gate dispatch claims name its proposal or "
                                "grant (duplicate dispatch claim; the Gate records exactly one)")
                continue
            if (receipt is None or receipt.record_type != "receipt" or strategy is None
                    or action.get("scope_digest") is None or action.get("capability") is None
                    or not registered_seq < receipt.seq < seq[event.event_id]
                    or receipt.payload.get("result", {}).get("result_class") != "positive"
                    or not _invocation_receipt_bound(ledger, journal, seq, receipt, strategy, mission_id=mid,
                                                    command_digest=digest, closure_seq=achieved_seq,
                                                    since_seq=since if seq[event.event_id] > since else registered_seq,
                                                    observation=False, claimed_scope=action["scope_digest"],
                                                    claimed_capability=action["capability"])):
                once = False
                findings.append(
                    f"{action['action_id']}: recorded as settled by a founder reconciliation answer, with no Gate "
                    "receipt; exactly-once cannot be re-derived from receipts"
                    if receipt is None and action.get("reconciles") else
                    f"{action['action_id']}: completed action lacks its signed strategy's Gate receipt")
        # A compensating receipt (mission abandoned or superseded after executing) is its own effect: it may
        # repeat no other receipt, and each executed action is compensated at most once.
        compensations = [e.payload for e in journal.replay("mission.compensated")
                         if e.payload["mission_id"] == mid and e.payload.get("receipt")]
        compensating = [c["receipt"] for c in compensations]
        compensated = [c["action_id"] for c in compensations]
        if len(compensating) != len(set(compensating)) or set(compensating) & set(receipts) \
                or len(compensated) != len(set(compensated)):
            once = False
            findings.append("a compensation repeats a receipt or compensates an action twice")
        checks["exactly_once"] = once
        if len(receipts) != len(set(receipts)):   # only a real duplicate is reported as one
            findings.append("duplicate receipt: one Gate receipt is cited by more than one completed action")

        # 4b. deliverables: the delivered file must be exactly the render of the receipted inputs
        # A standing mission's closure covers only the actions since its previous closure:
        # earlier deliveries were judged at their own closure against the evidence of that
        # time, and their superseded inputs are history, not a present-tense claim.
        window = [e.payload for e in completed] if request.get("closure_event") else actions
        import importlib
        delivered_ok = True
        for action in window:
            if action.get("capability") not in DELIVERING:
                continue
            receipt = ledger.find(action["receipt"]) if action.get("receipt") else None
            output = receipt.payload["result"].get("output") if receipt else None
            verify_delivery = importlib.import_module(DELIVERING[action["capability"]]).verify_delivery
            # #26: on a confined body the re-derivation runs as confined as the original did (organs: no network);
            # the venture bridge also checks each cognition receipt it rendered is on the canonical ledger.
            ok, detail = verify_delivery(output, Path(request["deliver_root"]) if request.get("deliver_root") else None,
                                         ledger=ledger, confined=bool(request.get("confined_egress")))
            if not ok:
                delivered_ok = False
                findings.append(f"{action['action_id']}: {detail}")
        checks["deliveries_bound_to_evidence"] = delivered_ok

        # 5. approval boundaries honored, inside the closure window. The founder-signed cone decides which
        # completed actions needed approval, not the engine's own asks: every DONE action is re-admitted
        # against LightCone.admits (capability, signed target, manifest class, cost, spend so far, its time).
        # One outside the cone, or one whose grant the engine marked founder-approved, ran honestly only
        # after an exact-scope approval answered "approve" by a DECISION whose accepted envelope re-verifies
        # against a key allowed to sign DECISION at that ledger position; or, past the cone only, when the
        # signed mission itself pre-approves that exact step (greg/sop.py runs). An engine that forgot to
        # ask, or an answer no founder command carries, refutes the closure (review of 2026-10-14).
        cone = LightCone.from_dict(spec["light_cone"])
        requests = [e for e in journal.replay("decision.requested") if e.payload.get("mission_id") == mid]
        # Both lineages' defenses hold: the answer row must also be one the mission fold counts, i.e. the record
        # re-derived from a founder-signed DECISION at its own acceptance (#184 item 7, ADR-GOAL-GRAVITY-002),
        # and _approved_before then re-verifies that DECISION's envelope independently (#178).
        from greg.goal_gravity import founder_facts
        counted = founder_facts(ledger).book.answers
        answers = {}
        for e in journal.replay("decision.answered"):
            if registered_seq < seq[e.event_id] < achieved_seq:
                held = counted.get(e.payload["request_id"])
                if held is None or held.get("command_digest") != e.payload.get("command_digest"):
                    continue              # a row no founder-signed DECISION stands behind moves nothing
                answers.setdefault(e.payload["request_id"], (e.payload, seq[e.event_id]))
        approvals_ok = True
        approvals_seen = sum(1 for r in requests if r.payload["kind"] == "APPROVAL"
                             and registered_seq < seq[r.event_id] < achieved_seq)
        grants = {r.payload.get("grant_id"): r.payload for r in ledger.by_type("event")
                  if r.payload.get("type") == "greg.authority.grant_issued" and r.seq < achieved_seq}
        by_id = {s["action_id"]: s for s in spec["strategies"]}
        spent = 0.0
        for event in journal.replay("mission.action"):
            action = event.payload
            if action["mission_id"] != mid or action["status"] != "DONE" or seq[event.event_id] >= achieved_seq:
                continue
            at_seq = seq[event.event_id]
            in_window = registered_seq < at_seq
            strategy = by_id.get(action["action_id"])
            manifest = _manifest_before(journal, seq, action.get("capability"), at_seq)
            receipt = ledger.find(action["receipt"]) if action.get("receipt") else None
            grant = grants.get(receipt.payload.get("grant_id")) if receipt is not None else None
            if in_window and (strategy is None or manifest is None):
                approvals_ok = False
                findings.append(f"{action['action_id']}: its admission to the signed cone cannot be re-derived")
            elif in_window:
                outside = cone.admits(capability=manifest.capability_id, target=strategy["target"],
                                      consequence_class=manifest.consequence_class,
                                      cost_usd=float(strategy.get("cost_usd", 0.0)), spent_usd=spent,
                                      at=_instant_or_none(action.get("at")) or _instant_or_none(cone.horizon))
                if not action.get("at"):          # no recorded time: the horizon cannot be judged here
                    outside = [r for r in outside if r != "scope horizon has expired"]
                if outside and pre_approved(spec, strategy, manifest):
                    outside = []                  # the signed mission approves this exact step itself
                human = bool(grant and grant.get("founder_approved_scope"))
                if (outside or human) and not _approved_before(journal, ledger, seq, requests, answers,
                                                               action.get("scope_digest"), at_seq):
                    approvals_ok = False
                    why = "; ".join(outside) if outside else "its grant claims a founder approval"
                    findings.append(f"{action['action_id']}: executed without a prior founder approval ({why})")
            spent += float(action.get("cost_usd", 0.0) or 0.0)
        checks["approval_boundaries_honored"] = approvals_ok
        checks["approval_boundary_encountered"] = approvals_seen > 0

        # 6. preconditions honored: a gated action ran only while every check it requires was
        # last observed passing, and that observation's receipt satisfies the predicate
        requires = {s["action_id"]: s.get("requires", []) for s in spec["strategies"]}
        predicates = {c["check_id"]: c["predicate"] for c in spec["success_checks"]}
        preconditions_ok = True
        for e in action_events:
            action = e.payload
            if not requires.get(action["action_id"]):
                continue
            for check_id in requires[action["action_id"]]:
                before = [o.payload for o in journal.replay("mission.observed") if o.payload["mission_id"] == mid
                          and o.payload["check_id"] == check_id and seq[o.event_id] < seq[e.event_id]]
                last = before[-1] if before else None
                receipt = ledger.find(last["receipt"]) if last and last.get("receipt") else None
                held = bool(last and last.get("passed") and receipt is not None and evaluate_receipt(
                    predicates[check_id], receipt.payload["result"], artifacts)[0])
                if not held:
                    preconditions_ok = False
                    findings.append(f"{action['action_id']}: ran before {check_id} was observed passing")
        checks["preconditions_honored"] = preconditions_ok
        required = ("chain_intact", "registered_once", "achieved_claimed", "closure_matches_signed_rule",
                    "founder_signature_verified", "closure_evidence_bound", "checks_rederived_from_receipts",
                    "world_reobserved", "exactly_once", "deliveries_bound_to_evidence",
                    "approval_boundaries_honored", "preconditions_honored")
        return _verdict(request, checks, findings, required=required, unmet=unmet)
    finally:
        ledger.close()


def _verdict(request, checks, findings, required=(), unmet=False):
    """VERIFIED is a verified success. A verified failure closure is VERIFIED_UNMET, so no reader of VERIFIED can
    take it for a success; settlement reads both, to hear failures as well as successes."""
    verified = bool(required) and all(checks.get(k) for k in required)
    return {"mission_id": request["mission_id"], "head": request["head"],
            "verdict": ("VERIFIED_UNMET" if unmet else "VERIFIED") if verified else "REFUTED",
            **({"closure": "unmet"} if unmet else {}), "checks": checks, "findings": findings,
            "appraiser": "separate process over read-only head-pinned ledger; re-derivation + re-observation",
            "limits": "shares reviewed Kernel code; not an independent implementation",
            **({"closure_event": request["closure_event"]} if request.get("closure_event") else {})}


if __name__ == "__main__":
    raw = sys.stdin.read(1 << 20)
    print(json.dumps(appraise(json.loads(raw)), sort_keys=True))
