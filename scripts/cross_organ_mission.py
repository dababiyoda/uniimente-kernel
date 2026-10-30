"""One cross-organ mission, run through each organ's real code in its own process.

DALEOBANKS (its checkout, its interpreter) refines a founder thought into an
OpportunityPacket and signs it onto the bridge. WealthMachineIntelligence (its
checkout, its interpreter) verifies the request and runs its venture loop. The
Kernel verifies both messages, adapts them through the canonical adapters,
records every step on a persisted EvidenceLedger via the EventSpine, and keeps
unresolved fields as open obligations instead of inventing answers.

Independent appraisal is done by parties other than the producer:
  * a fresh WealthMachine process re-derives the assessment from the signed
    packet bytes (reproduction, not correctness);
  * the Kernel checks invariants the producer cannot self-certify.
Each organ then witnesses the Kernel ledger with its own key and durable
state (provenance.witness), and a 2-of-2 quorum must accept the checkpoint.

Nothing here contacts anyone, spends, publishes or deploys. Evidence tier of
the result: internal multi-process execution; no external acceptance.

Usage:
  python scripts/cross_organ_mission.py \\
      --daleobanks ../DALEOBANKS --daleobanks-python <py> \\
      --wealthmachine ../WealthMachineIntelligence --wealthmachine-python <py> \\
      --out tests/evidence/cross-organ-mission-YYYYMMDD
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

KERNEL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KERNEL_ROOT))

from adapters import bridge_transport as bt  # noqa: E402
from adapters import daleobanks_opportunity as pkt_adapter  # noqa: E402
from adapters import wealthmachine_assessment as asm_adapter  # noqa: E402
from events.spine import Event, EventSpine  # noqa: E402
from memory.causal import CausalMemory  # noqa: E402
from provenance.consistency import prove_consistency  # noqa: E402
from provenance.ledger import EvidenceLedger  # noqa: E402
from provenance.proof import LedgerProver  # noqa: E402
from provenance.witness import Checkpoint, QuorumPolicy  # noqa: E402

KERNEL = "spiffe://uniimente.internal/organ/constitutional-controller"
ORIGIN = "uniimente-kernel/evidence-ledger"
SEED_THOUGHT = (
    "Financial independence is not selfish. It is protection from systems "
    "that profit from dependency. Maybe a budgeting checklist or workshop "
    "could help people start."
)

DALEOBANKS_STAGE = r'''
import asyncio, json, sys, time
from adapters import bridge_transport as bt
from db.session import get_db_session, init_db
from services.idea_refinery import IdeaRefinery
from services.venture_protocol import packet_to_wire
started = time.perf_counter()
init_db()
refinery = IdeaRefinery()
with get_db_session() as session:
    idea = refinery.intake(session, sys.argv[1])
    result = asyncio.run(refinery.refine(session, idea))
wire = packet_to_wire(result["opportunity"])
body = json.dumps(wire, sort_keys=True).encode()
headers = bt.build_headers(body, identity="daleobanks", schema_version=wire.get("schema_version", "1.1"),
                           idempotency_key=wire["id"], trace_id=sys.argv[2])
print(json.dumps({"body": body.decode(), "headers": headers,
                  "drafts": len(result["drafts"]), "thesis": result["thesis"],
                  "seconds": round(time.perf_counter() - started, 4)}))
'''

WEALTHMACHINE_STAGE = r'''
import json, sys, time
from adapters import bridge_transport as bt
from src.services.opportunity_intake import OpportunityIntakeService
started = time.perf_counter()
msg = json.loads(sys.stdin.read())
body = msg["body"].encode()
meta = bt.verify_headers(msg["headers"], body, nonce_cache=bt.NonceCache(),
                         expected_sender="daleobanks", expected_recipient="wealthmachine",
                         expected_operation="opportunity.evaluate")
assessment = OpportunityIntakeService().evaluate_packet(json.loads(body))
out = json.dumps(assessment, sort_keys=True).encode()
headers = bt.build_headers(out, identity="wealthmachine", schema_version=assessment["schema_version"],
                           idempotency_key=assessment["id"], recipient="kernel",
                           operation="assessment.report", trace_id=msg["headers"]["X-Trace-Id"],
                           request_digest=bt.body_digest(body))
print(json.dumps({"body": out.decode(), "headers": headers, "verified_sender": meta["identity"],
                  "seconds": round(time.perf_counter() - started, 4)}))
'''

WITNESS_STAGE = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
from provenance.consistency import ConsistencyProof
from provenance.witness import Checkpoint, Witness, WitnessRefused
req = json.loads(sys.stdin.read())
w = Witness(req["witness_id"], bytes.fromhex(req["key"]), state_path=req["state_path"])
cp = Checkpoint(req["origin"], req["tree_size"], req["root"])
proof = ConsistencyProof(**{**req["proof"], "path": tuple(req["proof"]["path"])}) if req.get("proof") else None
fresh = req["origin"] not in w.last_seen
try:
    sig = w.cosign(cp, proof)
    print(json.dumps({"cosigned": True, "signature": sig, "this_cosign_was_first_use": fresh}))
except WitnessRefused as exc:
    print(json.dumps({"cosigned": False, "reason": str(exc)}))
'''


REPRODUCIBLE_FIELDS = ("go_no_go", "opportunity_score", "market_alignment", "risk_level",
                       "legal_readiness", "requires_human_approval", "validation_plan", "reasons")


def appraise(wire_packet: dict, wire_assessment: dict, rederived: dict) -> dict:
    """Appraise a producer's assessment without trusting the producer.

    `rederived` must come from a separate run over the same signed packet.
    Agreement shows reproducibility, not correctness; the invariants are the
    Kernel's own checks. Neither is external acceptance.
    """
    reproduced = {k: rederived.get(k) == wire_assessment.get(k) for k in REPRODUCIBLE_FIELDS}
    flags = wire_packet.get("risk_flags", [])
    invariants = {
        "human_approval_required": wire_assessment.get("requires_human_approval") is True,
        "committee_has_bull_bear_do_nothing":
            {"bull", "bear", "do_nothing"} <= {c.get("case") for c in wire_assessment.get("cases", [])},
        "finance_flag_forces_review": ("finance_education_only" not in flags)
                                      or wire_assessment.get("legal_readiness") == "review_required",
        "no_revenue_promise": "no revenue promises" in str(wire_assessment.get("expected_roi", "")),
        "assessment_answers_this_packet": wire_assessment.get("opportunity_packet_id") == wire_packet.get("id"),
    }
    ok = all(reproduced.values()) and all(invariants.values())
    return {"reproduced": reproduced, "invariants": invariants,
            "verdict": "internally_appraised" if ok else "appraisal_failed",
            "tier": "multi-process reproduction + invariant check; not external acceptance"}


def run_stage(python: str, cwd: Path, code: str, *args: str, stdin: dict | None = None,
              env: dict | None = None) -> dict:
    proc = subprocess.run([python, "-c", code, *args], cwd=cwd, capture_output=True, text=True,
                          input=json.dumps(stdin) if stdin is not None else None,
                          env={**os.environ, **(env or {})}, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(f"stage failed in {cwd}:\n{proc.stderr[-4000:]}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def main() -> int:
    ap = argparse.ArgumentParser()
    for organ in ("daleobanks", "wealthmachine"):
        ap.add_argument(f"--{organ}", required=True)
        ap.add_argument(f"--{organ}-python", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    work = out / "work"
    work.mkdir(exist_ok=True)

    organs = {"daleobanks": (Path(args.daleobanks).resolve(), args.daleobanks_python),
              "wealthmachine": (Path(args.wealthmachine).resolve(), args.wealthmachine_python)}
    bridge_key = secrets.token_hex(32)  # per-run; never written to evidence
    witness_keys = {o: secrets.token_bytes(32) for o in organs}
    os.environ[bt.SIGNING_KEY_ENV] = bridge_key
    shared_env = {bt.SIGNING_KEY_ENV: bridge_key, "PERSIST_STORE": "false",
                  "LEDGER_PATH": str(work / "daleobanks-decision-ledger.jsonl"),
                  "DB_SNAPSHOT_PATH": str(work / "daleobanks-store.jsonl")}
    trace_id = "mission-" + secrets.token_hex(8)
    findings: dict = {"trace_id": trace_id, "stages": {}, "attacks": {}}

    ledger_path = work / "kernel-ledger.jsonl"
    if ledger_path.exists():
        ledger_path.unlink()
    ledger = EvidenceLedger("sha256:" + hashlib.sha256(b"cross-organ-mission").hexdigest(),
                            path=str(ledger_path))
    spine = EventSpine(ledger)
    prover = LedgerProver(ledger)
    policy = QuorumPolicy({o: k for o, k in witness_keys.items()}, threshold=2)

    def witness_round(tree_size: int, root: str, proof=None, *, forged=False) -> dict:
        cp = Checkpoint(ORIGIN, tree_size, root)
        results = {}
        for organ, (cwd, python) in organs.items():
            res = run_stage(python, cwd, WITNESS_STAGE, str(KERNEL_ROOT), stdin={
                "witness_id": organ, "key": witness_keys[organ].hex(),
                "state_path": str(work / f"{organ}-witness-state.json"), "origin": ORIGIN,
                "tree_size": tree_size, "root": root,
                "proof": None if proof is None else {"old_size": proof.old_size,
                                                     "new_size": proof.new_size,
                                                     "path": list(proof.path)}})
            results[organ] = {k: v for k, v in res.items() if k != "signature"}
            if res["cosigned"]:
                cp.cosignatures[organ] = res["signature"]
        accepted, why = policy.accepts(cp)
        return {"tree_size": tree_size, "root": root, "witnesses": results,
                "quorum_accepted": accepted, "quorum_reason": why, "forged": forged}

    # 0. Baseline checkpoint, witnessed on first use by both organs.
    c0 = prover.checkpoint()
    findings["checkpoint_0"] = witness_round(c0["tree_size"], c0["root"])

    # 1. DALEOBANKS: founder thought -> refined packet -> signed request.
    d_cwd, d_py = organs["daleobanks"]
    d = run_stage(d_py, d_cwd, DALEOBANKS_STAGE, SEED_THOUGHT, trace_id, env=shared_env)
    findings["stages"]["daleobanks"] = {"seconds": d["seconds"], "drafts": d["drafts"],
                                         "thesis": d["thesis"],
                                         "packet_sha256": bt.body_digest(d["body"].encode())}

    # 2. WealthMachine: verify request, run venture loop, sign assessment to the Kernel.
    w_cwd, w_py = organs["wealthmachine"]
    w = run_stage(w_py, w_cwd, WEALTHMACHINE_STAGE, stdin=d, env=shared_env)
    findings["stages"]["wealthmachine"] = {"seconds": w["seconds"], "verified_sender": w["verified_sender"],
                                            "assessment_sha256": bt.body_digest(w["body"].encode())}

    # 3. Kernel: verify both messages from transport, never from payload.
    nonces = bt.NonceCache()
    p_meta = bt.verify_headers(d["headers"], d["body"].encode(), nonce_cache=nonces,
                               expected_sender="daleobanks", expected_operation="opportunity.evaluate")
    a_meta = bt.verify_headers(w["headers"], w["body"].encode(), nonce_cache=nonces,
                               expected_sender="wealthmachine", expected_recipient="kernel",
                               expected_operation="assessment.report",
                               request_digest=bt.body_digest(d["body"].encode()))
    wire_packet, wire_assessment = json.loads(d["body"]), json.loads(w["body"])
    ev_signal = spine.ingest(Event(type="bridge.signal_observed", source="ext:daleobanks-bridge",
                                   actor=p_meta["identity"], legal_principal="alfonso_lopez",
                                   payload={"packet_sha256": findings["stages"]["daleobanks"]["packet_sha256"],
                                            "trace_id": trace_id, "transport": p_meta}))
    adapted = pkt_adapter.adapt(wire_packet, transport_identity=p_meta["identity"])
    ev_packet = spine.emit(Event(type="bridge.opportunity_adapted", source=KERNEL, actor="kernel",
                                 legal_principal="alfonso_lopez",
                                 payload={"unresolved": adapted.unresolved,
                                          "obligation": "authorized human must answer unresolved fields"
                                          if adapted.unresolved else None},
                                 causal_parent=ev_signal.event_id))
    assessment = asm_adapter.adapt(wire_assessment, transport_identity=a_meta["identity"])
    bound, bound_why = pkt_adapter.justified_verdict(
        assessment["verdict"], adapted.unresolved, wire_packet.get("evidence") or [])
    ev_assessment = spine.emit(Event(type="bridge.assessment_adapted", source=KERNEL,
                                     actor=a_meta["identity"], legal_principal="alfonso_lopez",
                                     payload={"verdict": bound, "engine_verdict": assessment["verdict"],
                                              "verdict_why": bound_why,
                                              "requires_human_approval": assessment["requires_human_approval"],
                                              "assessment_sha256": findings["stages"]["wealthmachine"]["assessment_sha256"]},
                                     causal_parent=ev_packet.event_id))

    # 4. Independent appraisal: a fresh WealthMachine process re-derives the
    # assessment from the same signed packet; the Kernel checks invariants.
    redo = run_stage(w_py, w_cwd, WEALTHMACHINE_STAGE, stdin={**d, "headers": bt.build_headers(
        d["body"].encode(), identity="daleobanks", schema_version=d["headers"]["X-Schema-Version"],
        idempotency_key=json.loads(d["body"])["id"], trace_id=trace_id)}, env=shared_env)
    rederived = json.loads(redo["body"])
    appraisal = appraise(wire_packet, wire_assessment, rederived)
    ev_appraisal = spine.emit(Event(type="bridge.assessment_appraised", source=KERNEL, actor="kernel-appraiser",
                                    legal_principal="alfonso_lopez", payload=appraisal,
                                    causal_parent=ev_assessment.event_id))
    spine.emit(Event(type="bridge.obligation_open", source=KERNEL, actor="kernel", legal_principal="alfonso_lopez",
                     payload={"awaiting": "founder approval of the recommended next action",
                              "recommended_next_action": wire_assessment["recommended_next_action"],
                              "external_effect": None},
                     causal_parent=ev_appraisal.event_id))
    findings["appraisal"] = appraisal

    # 5. Attacks against the live episode.
    try:
        bt.verify_headers(d["headers"], d["body"].encode(), nonce_cache=nonces,
                          expected_sender="daleobanks", expected_operation="opportunity.evaluate")
        findings["attacks"]["replayed_packet"] = "ACCEPTED"
    except bt.BridgeSecurityError as exc:
        findings["attacks"]["replayed_packet"] = f"refused: {exc}"
    tampered = json.loads(w["body"])
    tampered["go_no_go"] = "go" if tampered["go_no_go"] != "go" else "kill"
    try:
        bt.verify_headers(w["headers"], json.dumps(tampered, sort_keys=True).encode(), nonce_cache=bt.NonceCache(),
                          expected_sender="wealthmachine", expected_recipient="kernel",
                          expected_operation="assessment.report")
        findings["attacks"]["tampered_assessment"] = "ACCEPTED"
    except bt.BridgeSecurityError as exc:
        findings["attacks"]["tampered_assessment"] = f"refused: {exc}"

    # 6. Checkpoint the episode; both organs witness the append-only extension.
    c1 = prover.checkpoint()
    hashes = [r.hash for r in ledger.records[:c1["covers_records"]]]
    findings["checkpoint_1"] = witness_round(c1["tree_size"], c1["root"],
                                             prove_consistency(hashes, c0["covers_records"]))

    # 7. Attacks on history. (a) Same size, different root: equivocation.
    # (b) Rewrite an old record and append one more, with a proof from the
    # last witnessed size: no valid append-only proof exists.
    from provenance.consistency import merkle_root
    forged = list(hashes)
    forged[2] = "sha256:" + hashlib.sha256(b"rewritten history").hexdigest()
    findings["attacks"]["equivocating_checkpoint"] = witness_round(
        len(forged), merkle_root(forged), forged=True)
    extended = forged + ["sha256:" + hashlib.sha256(b"appended after rewrite").hexdigest()]
    findings["attacks"]["rewritten_and_extended"] = witness_round(
        len(extended), merkle_root(extended), prove_consistency(extended, len(hashes)), forged=True)

    # 8. Mission trace from retained evidence only.
    memory = CausalMemory(ledger)
    chain = memory.ancestry(ev_appraisal.event_id)
    ok, why = ledger.verify_chain()
    findings["mission_trace"] = {
        "what_happened": [e["type"] for e in reversed(chain)],
        "components": sorted({e.get("actor") for e in chain if e.get("actor")}),
        "authorized": "no consequence was requested; nothing required authorization",
        "executed_externally": False,
        "accepted_by_recipient": None,
        "outcome_verified": appraisal["verdict"],
        "remaining_obligations": ["founder approval of the recommended next action"]
                                 + ([f"unresolved packet fields: {adapted.unresolved}"] if adapted.unresolved else []),
        "resources": {"daleobanks_seconds": d["seconds"], "wealthmachine_seconds": w["seconds"],
                      "reported_spend_usd": 0.0, "spend_verified": "no paid calls were made by this script"},
        "ledger_chain_ok": ok, "ledger_chain_detail": why,
        "unknowns": ["whether any buyer wants the offer", "whether the founder approves",
                     "real-world effect of the recommended validation action"],
    }
    (out / "mission-result.json").write_text(json.dumps(findings, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps(findings["mission_trace"], indent=2, default=str))
    passed = (appraisal["verdict"] == "internally_appraised"
              and findings["checkpoint_1"]["quorum_accepted"]
              and not findings["attacks"]["equivocating_checkpoint"]["quorum_accepted"]
              and not findings["attacks"]["rewritten_and_extended"]["quorum_accepted"]
              and findings["attacks"]["replayed_packet"].startswith("refused")
              and findings["attacks"]["tampered_assessment"].startswith("refused") and ok)
    print("RESULT:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
