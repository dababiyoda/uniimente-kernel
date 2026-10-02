"""Independent mission appraisal (Proof/Truth super-node).

Run as a separate process (``python -m greg.appraisal``) over a read-only,
head-pinned ledger. The engine's own "achieved" claim is not accepted; the
appraiser re-derives the result from retained bytes and from the world:

1. the mission body is exactly what an enrolled founder key signed (Ed25519 re-verified);
2. every success check is re-evaluated from its receipt's bytes (not the engine's flag);
3. read-only built-in sensors are re-run now; semantic source-snapshot artifacts
   are independently revalidated without another stochastic model call;
4. every consequential action has exactly one dispatch claim and one receipt;
5. any action that needed founder approval happened only after an approving decision.

Mechanism lineage: #101 verifier/local_repository_appraisal.py (separate process,
head binding, source re-read) and #94 protected appraisal (worker success is not
acceptance). Limit: this is a separate process running reviewed Kernel code, not an
independently written implementation or an OS sandbox against the host owner.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import re
import sys

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from events.spine import EventSpine
from greg.capabilities import BUILTINS, InvocationContext
from greg.founder import _signing_bytes
from greg.journal import Journal
from greg.missions import evaluate_predicate
from provenance.ledger import EvidenceLedger, sha256_json

REOBSERVABLE = {"fs.read", "fs.list", "git.inspect", "repo.pin_audit", "repo.integration_audit", "brief.freshness",
                "memory.precedents", "artifact.inspect"}
REOBSERVABLE.update(cid for cid in BUILTINS if cid.startswith("cognition.") and
                    cid not in ("cognition.semantic", "cognition.compose", "cognition.knowledge"))
DELIVERING = {"brief.engineering": "greg.briefs", "venture.assess": "greg.ventures"}  # re-rendered from receipts


def _semantic_sensor(check: dict) -> bool:
    sensor = check.get("sensor", {})
    return (sensor.get("capability") in ("cognition.solve", "cognition.semantic") and
            sensor.get("params", {}).get("operation") == "interpret")


def _bind_native_witness(check, receipt, journal, command_digest):
    from provenance.commit_witness import sha256_obj
    sensor = check["sensor"]
    witnesses = [r.payload for r in journal.ledger.by_type("witness")
                 if r.payload.get("witness_id") == receipt.payload.get("witness_id")]
    expected_payload = sha256_obj({"capability": sensor["capability"], "params": sensor["params"],
                                   "manifest_digest": BUILTINS[sensor["capability"]][0].digest()})
    if (len(witnesses) != 1 or witnesses[0].get("capability") != sensor["capability"] or
            witnesses[0].get("target") != sensor.get("target") or
            witnesses[0].get("payload_hash") != expected_payload or
            witnesses[0].get("constitution_hash") != journal.ledger.constitution_hash or
            command_digest not in witnesses[0].get("evidence_refs", [])):
        raise ValueError("cognitive receipt lacks the matching native mission witness")


def _revalidate_semantic_result(params, answer, *, journal=None, now=None):
    """Validate the recorded snapshot/proposal contract, never fresh world truth.

    A second model answer would be a different stochastic artifact. The exact
    signed inputs and the original native witness instead bind the source spans
    checked here. Model provenance is retained inventory evidence, not an audit
    of the model server, weight license, factual accuracy or useful strategy.
    """
    from greg.cognition.contracts import digest
    from greg.cognition.advantage import validate_against_input
    from greg.cognition.cortex import compile_problem
    from greg.cognition.semantic import validate_semantic
    from greg.cognition.settlement import _valid_receipt
    from greg.cognition.verification import verify

    now = now or datetime.now(timezone.utc)
    if not _valid_receipt(answer):
        raise ValueError("invalid retained cognitive receipt")
    validate_against_input(params, answer, journal=journal)
    if (answer["method"] != "cognition.semantic" or answer["proof_type"] != "sourced_claims" or
            answer["method_version"] != BUILTINS["cognition.semantic"][0].version or
            answer["input_digest"] != digest(params) or answer["abstention_state"] != "NONE" or
            answer["empirical_validity"] != "WORLD_UNVERIFIED" or
            answer["evaluator_result"].get("verdict") != "STRUCTURALLY_VERIFIED"):
        raise ValueError("semantic result does not match the signed snapshot contract")
    geometry, consequences = compile_problem(params)
    if (digest(answer["geometry"]) != digest(asdict(geometry)) or
            digest(answer["consequence_vector"]) != digest(asdict(consequences)) or
            geometry.unknown_geometry or geometry.out_of_distribution or geometry.classification_uncertainty > .5 or
            geometry.legal_content or geometry.human_value_content or geometry.rights_impact or
            consequences.prohibited or consequences.high):
        raise ValueError("semantic receipt cannot lower source classification or consequential conditions")
    for expiry in [params.get("evidence_expires_at"), *(s.get("expires_at") for s in params["data"].get("sources", []))]:
        if expiry is None:
            continue
        at = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        if at.tzinfo is None or at <= now:
            raise ValueError("semantic source evidence is stale or undated")
    provenance = answer.get("model_provenance")
    artifact = answer["proof_artifact"]
    if (not isinstance(provenance, dict) or provenance != artifact.get("model_provenance") or
            provenance.get("provider") != "ollama" or not isinstance(provenance.get("requested"), str) or
            provenance.get("requested") != provenance.get("served") or
            not isinstance(provenance.get("weight_digest"), str) or
            not re.fullmatch(r"[a-fA-F0-9]{64}", provenance["weight_digest"])):
        raise ValueError("semantic model provenance is absent or inconsistent")
    # Constructor validates the permitted local model name without network I/O.
    from greg.models import OllamaRoute
    OllamaRoute(provenance["requested"])
    validate_semantic({k: artifact[k] for k in ("claims", "contradictions", "uncertainty")}, params["data"].get("sources", []))
    checked = verify("semantic", params["data"], {"output": answer["output"], "proof": artifact}, "sourced_claims")
    if checked["verdict"] != "STRUCTURALLY_VERIFIED":
        raise ValueError("semantic source/artifact checks refuted the retained result")
    return {"receipt_id": answer["receipt_id"],
            "scope": "signed source snapshot and provisional proposal structure",
            "empirical_validity": "WORLD_UNVERIFIED", "current_world_observation": False,
            "model_reexecuted": False, "outcome_credit": False, "artifact_verification": checked}


def _revalidate_semantic(check, receipt, journal, command_digest, *, now=None):
    _bind_native_witness(check, receipt, journal, command_digest)
    return {"check_id": check["check_id"], **_revalidate_semantic_result(
        check["sensor"]["params"], receipt.payload.get("result", {}).get("output"), journal=journal, now=now)}


def _revalidate_cognitive_result(params, result, *, journal=None, now=None):
    """Challenge the original artifact against its source, not a new answer."""
    from greg.cognition.catalog import FAMILIES
    from greg.cognition.advantage import validate_against_input
    from greg.cognition.contracts import digest
    from greg.cognition.cortex import compile_problem
    from greg.cognition.settlement import _valid_receipt
    from greg.cognition.verification import verify

    now = now or datetime.now(timezone.utc)
    if not _valid_receipt(result) or result["input_digest"] != digest(params):
        raise ValueError("retained receipt is not bound to the exact signed cognitive input")
    validate_against_input(params, result, journal=journal)
    geometry, consequences = compile_problem(params)
    if (digest(result["geometry"]) != digest(asdict(geometry)) or
            digest(result["consequence_vector"]) != digest(asdict(consequences))):
        raise ValueError("retained receipt changes the signed classification")
    if (geometry.unknown_geometry or geometry.out_of_distribution or geometry.classification_uncertainty > .5 or
            geometry.legal_content or geometry.human_value_content or geometry.rights_impact or consequences.prohibited):
        raise ValueError("request requires abstention or human authority, not an answered result")
    family = result["method"].removeprefix("cognition.")
    metadata = FAMILIES.get(family)
    if (metadata is None or params["operation"] not in metadata[1] or
            result["method_version"] != BUILTINS[result["method"]][0].version):
        raise ValueError("retained method does not match the signed operation/version")
    if params.get("evidence_expires_at"):
        expiry = datetime.fromisoformat(params["evidence_expires_at"].replace("Z", "+00:00"))
        if expiry.tzinfo is None or expiry <= now:
            raise ValueError("retained source evidence is stale")
    if result["proof_type"] is None or result["output"] is None or result["abstention_state"] == "REFUTED":
        raise ValueError("retained result is blocked or refuted; no checked result can be claimed")
    if family == "semantic":
        return _revalidate_semantic_result(params, result, journal=journal, now=now)
    native = result["output"].get("solver_status")
    status = "ANSWER" if result["abstention_state"] == "NONE" else result["abstention_state"]
    required_status = ("UNKNOWN" if native == "UNKNOWN" else "ABSTAIN" if native == "MODEL_INVALID" else
                       "UNIDENTIFIED" if family == "causal" and not result["output"].get("identified_conditionally") else
                       "ABSTAIN" if family == "evidence" and result["output"].get("contested") else None)
    if required_status is not None and status != required_status:
        raise ValueError("retained receipt relabelled a native abstention/UNKNOWN result")
    checked = verify(family, params["data"], {"output": result["output"], "proof": result["proof_artifact"],
                     "status": status, "formal_validity": result["formal_validity"]}, result["proof_type"])
    if checked["verdict"] != "STRUCTURALLY_VERIFIED":
        raise ValueError("retained source/proof/output checks refuted the result")
    return {"receipt_id": result["receipt_id"], "scope": "encoded computation/artifact only",
            "empirical_validity": "WORLD_UNVERIFIED", "artifact_verification": checked,
            "current_world_observation": False, "model_reexecuted": False, "outcome_credit": False}


def _revalidate_composition(check, receipt, journal, command_digest, *, now=None):
    """Challenge each signed subclaim, without inferring composition advantage."""
    from greg.cognition.contracts import digest
    from greg.cognition.verification import metaconsensus

    now = now or datetime.now(timezone.utc)
    _bind_native_witness(check, receipt, journal, command_digest)
    params, output = check["sensor"]["params"], receipt.payload.get("result", {}).get("output")
    if (not isinstance(params, dict) or set(params) != {"requests"} or not isinstance(params["requests"], list) or
            not 1 <= len(params["requests"]) <= 4 or not isinstance(output, dict) or
            set(output) != {"receipts", "metaconsensus", "authority_created", "superiority"} or
            output["authority_created"] is not False or not isinstance(output["receipts"], list) or
            len(output["receipts"]) != len(params["requests"]) or
            output["superiority"] != "unproven until compared with every constituent and strongest simple baseline"):
        raise ValueError("composition envelope is not its bounded recommendation-only contract")
    components, verified = [], True
    for index, (request, result) in enumerate(zip(params["requests"], output["receipts"])):
        detail = {"subclaim_index": index, "problem_id": request.get("problem_id"),
                  "abstention_state": result.get("abstention_state") if isinstance(result, dict) else None,
                  "receipt_id": result.get("receipt_id") if isinstance(result, dict) else None,
                  "dissent": result.get("strongest_counterargument") if isinstance(result, dict) else None,
                  "missing_information": result.get("missing_information") if isinstance(result, dict) else None,
                  "current_world_observation": False, "outcome_credit": False}
        try:
            detail.update(_revalidate_cognitive_result(request, result, journal=journal, now=now))
            detail["verified"] = True
        except Exception as exc:
            verified = False
            detail.update(verified=False, finding=f"{type(exc).__name__}: {str(exc)[:160]}")
        components.append(detail)
    if digest(output["metaconsensus"]) != digest(metaconsensus(output["receipts"])):
        raise ValueError("composition altered jurisdiction, dissent, abstention or reconciliation")
    return {"check_id": check["check_id"], "verified": verified, "components": components,
            "reconciled_state": output["metaconsensus"]["state"], "current_world_observation": False,
            "scope": "signed subclaim artifacts and jurisdiction; no composition utility/net lift claim",
            "outcome_credit": False, "shared_dependencies": "reviewed Kernel specification/code and signed input snapshots"}


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

        # 2. success checks re-derived from receipt bytes
        achieved_seq = seq[achieved[0].event_id]
        observations = [e for e in journal.replay("mission.observed")
                        if e.payload["mission_id"] == mid and seq[e.event_id] < achieved_seq]
        rederived, reobserved = True, True
        semantic_scopes = []
        composition_scopes = []
        numerical_scopes = []
        foundry_scopes = []
        has_semantic = any(_semantic_sensor(check) for check in spec["success_checks"])
        has_composition = any(check["sensor"].get("capability") == "cognition.compose" for check in spec["success_checks"])
        has_foundry = any(check["sensor"].get("capability") == "foundry.query" for check in spec["success_checks"])
        has_cognitive = any(check["sensor"].get("capability", "").startswith("cognition.")
                            for check in spec["success_checks"])
        has_snapshot = has_cognitive or has_foundry
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
            if _semantic_sensor(check):
                try:
                    semantic_scopes.append(_revalidate_semantic(check, receipt, journal, digest))
                except Exception as exc:
                    reobserved = False
                    findings.append(f"{check['check_id']}: semantic snapshot not verified ({type(exc).__name__}: {str(exc)[:160]})")
            elif cap == "cognition.compose":
                try:
                    scope = _revalidate_composition(check, receipt, journal, digest)
                    composition_scopes.append(scope)
                    if not scope["verified"]:
                        reobserved = False
                        findings.extend(f"{check['check_id']}: subclaim {part['subclaim_index']}: {part.get('finding', 'not verified')}"
                                        for part in scope["components"] if not part["verified"])
                except Exception as exc:
                    reobserved = False
                    findings.append(f"{check['check_id']}: composition not verified ({type(exc).__name__}: {str(exc)[:160]})")
            elif cap == "foundry.query":
                try:
                    from greg.foundry_bridge import revalidate
                    _bind_native_witness(check, receipt, journal, digest)
                    ctx = InvocationContext(workspace=Path(request["workspace"]), read_roots=(), secrets=None,
                                            manifest=BUILTINS[cap][0], journal=journal, target=check["sensor"]["target"])
                    scope = revalidate(check["sensor"]["params"], receipt.payload["result"].get("output"),
                                       ctx, mission_id=spec["mission_id"])
                    if scope.get("verified") is not True or scope.get("current_world_observation") is not False:
                        raise ValueError("Foundry appraisal did not preserve the snapshot-only contract")
                    foundry_scopes.append({"check_id": check["check_id"], **scope})
                except Exception as exc:
                    reobserved = False
                    findings.append(f"{check['check_id']}: original Foundry artifact not verified ({type(exc).__name__}: {str(exc)[:160]})")
            elif cap in REOBSERVABLE:
                manifest, adapter = BUILTINS[cap]
                if cap.startswith("cognition."):
                    # Recomputing the native answer cannot validate a proposal
                    # packet attached to the original output. Challenge that
                    # exact packet against the signed sensor input and custody.
                    original = receipt.payload.get("result", {}).get("output")
                    params = check["sensor"].get("params", {})
                    try:
                        _bind_native_witness(check, receipt, journal, digest)
                        numerical_scopes.append({"check_id": check["check_id"], **_revalidate_cognitive_result(
                            params, original, journal=journal)})
                    except Exception as exc:
                        reobserved = False
                        findings.append(f"{check['check_id']}: original cognitive artifact/review not verified ({type(exc).__name__}: {str(exc)[:160]})")
                        continue
                ctx = InvocationContext(workspace=Path(request["workspace"]),
                                        read_roots=tuple(Path(p) for p in request["read_roots"]),
                                        secrets=None, manifest=manifest,
                                        deliver_root=Path(request["deliver_root"])
                                        if request.get("deliver_root") else None,
                                        journal=journal if cap in ("memory.precedents", "artifact.inspect") or cap.startswith("cognition.") else None,
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
        # Recomputed arithmetic, encoded models and quote/proposal snapshots
        # are not present-world measurements.
        # Existing outcome/SOP consumers require world_reobserved=true; snapshot
        # appraisal therefore cannot manufacture outcome competence or benefit.
        checks["world_reobserved"] = reobserved and not has_snapshot
        if has_snapshot:
            checks["applicable_observations_revalidated"] = reobserved

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
        if has_snapshot:
            required = tuple("applicable_observations_revalidated" if k == "world_reobserved" else k for k in required)
        verdict = _verdict(request, checks, findings, required=required)
        if numerical_scopes:
            verdict["numerical_artifact_verification"] = numerical_scopes
            verdict["limits"] += "; numerical re-observation establishes encoded computation only, no empirical world benefit"
        if has_semantic:
            verdict["semantic_snapshot_verification"] = semantic_scopes
            verdict["limits"] += "; semantic snapshot/source structure only, no fresh-world truth, strategy usefulness or observed outcome credit"
        if has_composition:
            verdict["composition_artifact_verification"] = composition_scopes
            verdict["limits"] += "; composition verifies signed subclaim artifacts/jurisdiction only, no world truth, utility/net lift or observed outcome credit"
        if has_foundry:
            verdict["foundry_artifact_verification"] = foundry_scopes
            verdict["limits"] += "; Foundry revalidates supplied computation or retained journal snapshot with shared source code, no world truth, utility or outcome credit"
        return verdict
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
