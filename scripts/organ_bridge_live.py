"""Live cross-organ mission recorded into GREG's journal and traced by Foundry #44.

DALEOBANKS and WealthMachineIntelligence run their real code in their own
checkouts and interpreters. Their signed bridge messages are recorded through
`greg.organ_bridge` (transport-verified, retained as untrusted evidence, bound to
one mission and one trace). A second WealthMachine run re-derives the assessment
for a non-producer appraisal. `foundry.systems.observability` then answers from
the journal alone. No external effect, no spend.

The organ stages mirror scripts/cross_organ_mission.py on PR #166 (main line);
the two converge when the #166 and #132 lines merge.

Usage:
  python scripts/organ_bridge_live.py --daleobanks DIR --daleobanks-python PY \\
      --wealthmachine DIR --wealthmachine-python PY --out DIR
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters import bridge_transport as bt  # noqa: E402
from events.spine import EventSpine  # noqa: E402
from foundry.systems import observability  # noqa: E402
from greg import metrics, organ_bridge, routing  # noqa: E402
from greg.journal import Journal  # noqa: E402
from provenance.ledger import EvidenceLedger  # noqa: E402

SEED = ("Financial independence is not selfish. It is protection from systems that profit "
        "from dependency. Maybe a budgeting checklist or workshop could help people start.")

DALEOBANKS_STAGE = r'''
import asyncio, json, sys
from adapters import bridge_transport as bt
from db.session import get_db_session, init_db
from services.idea_refinery import IdeaRefinery
from services.venture_protocol import packet_to_wire
init_db()
refinery = IdeaRefinery()
with get_db_session() as session:
    idea = refinery.intake(session, sys.argv[1])
    result = asyncio.run(refinery.refine(session, idea))
wire = packet_to_wire(result["opportunity"])
body = json.dumps(wire, sort_keys=True).encode()
headers = bt.build_headers(body, identity="daleobanks", schema_version=wire.get("schema_version", "1.1"),
                           idempotency_key=wire["id"], trace_id=sys.argv[2])
print(json.dumps({"body": body.decode(), "headers": headers}))
'''

WEALTHMACHINE_STAGE = r'''
import json, sys
from adapters import bridge_transport as bt
from src.services.opportunity_intake import OpportunityIntakeService
msg = json.loads(sys.stdin.read())
body = msg["body"].encode()
bt.verify_headers(msg["headers"], body, nonce_cache=bt.NonceCache(), expected_sender="daleobanks",
                  expected_recipient="wealthmachine", expected_operation="opportunity.evaluate")
assessment = OpportunityIntakeService().evaluate_packet(json.loads(body))
out = json.dumps(assessment, sort_keys=True).encode()
headers = bt.build_headers(out, identity="wealthmachine", schema_version=assessment["schema_version"],
                           idempotency_key=assessment["id"], recipient="kernel", operation="assessment.report",
                           trace_id=msg["headers"]["X-Trace-Id"], request_digest=bt.body_digest(body))
print(json.dumps({"body": out.decode(), "headers": headers}))
'''

REPRODUCIBLE = ("go_no_go", "opportunity_score", "market_alignment", "risk_level", "legal_readiness",
                "requires_human_approval", "validation_plan", "reasons")


def stage(python, cwd, code, *args, stdin=None, env=None):
    proc = subprocess.run([python, "-c", code, *args], cwd=cwd, capture_output=True, text=True, timeout=600,
                          input=json.dumps(stdin) if stdin is not None else None, env={**os.environ, **env})
    if proc.returncode:
        raise RuntimeError(proc.stderr[-4000:])
    return json.loads(proc.stdout.strip().splitlines()[-1])


def main() -> int:
    ap = argparse.ArgumentParser()
    for organ in ("daleobanks", "wealthmachine"):
        ap.add_argument(f"--{organ}", required=True)
        ap.add_argument(f"--{organ}-python", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    key = secrets.token_hex(32)  # per run, never written
    os.environ[bt.SIGNING_KEY_ENV] = key
    env = {bt.SIGNING_KEY_ENV: key, "PERSIST_STORE": "false",
           "LEDGER_PATH": str(out / "daleobanks-decision-ledger.jsonl"),
           "DB_SNAPSHOT_PATH": str(out / "daleobanks-store.jsonl")}
    mission, trace = "m:organ-bridge-" + secrets.token_hex(4), "trace-" + secrets.token_hex(8)

    ledger_path = out / "greg-ledger.jsonl"
    for p in (ledger_path, Path(str(ledger_path) + ".lock")):
        p.unlink(missing_ok=True)
    journal = Journal(EventSpine(EvidenceLedger("sha256:" + "1" * 64, path=str(ledger_path))),
                      actor="spiffe://uniimente.internal/greg/organ-bridge-live")

    d = stage(a.daleobanks_python, a.daleobanks, DALEOBANKS_STAGE, SEED, trace, env=env)
    w = stage(a.wealthmachine_python, a.wealthmachine, WEALTHMACHINE_STAGE, stdin=d, env=env)
    cache = bt.NonceCache()
    organ_bridge.record_exchange(journal, mission_id=mission, headers=d["headers"], body=d["body"].encode(),
                                 nonce_cache=cache, expected_sender="daleobanks",
                                 expected_operation="opportunity.evaluate")
    organ_bridge.record_exchange(journal, mission_id=mission, headers=w["headers"], body=w["body"].encode(),
                                 nonce_cache=cache, expected_sender="wealthmachine", expected_recipient="kernel",
                                 expected_operation="assessment.report",
                                 request_digest=bt.body_digest(d["body"].encode()))

    redo = stage(a.wealthmachine_python, a.wealthmachine, WEALTHMACHINE_STAGE, stdin={
        **d, "headers": bt.build_headers(d["body"].encode(), identity="daleobanks",
                                         schema_version=d["headers"]["X-Schema-Version"],
                                         idempotency_key=json.loads(d["body"])["id"], trace_id=trace)}, env=env)
    packet, original, again = json.loads(d["body"]), json.loads(w["body"]), json.loads(redo["body"])
    appraisal = organ_bridge.record_appraisal(
        journal, mission_id=mission, appraiser="kernel-appraiser",
        reproduced={k: again.get(k) == original.get(k) for k in REPRODUCIBLE},
        invariants={"human_approval_required": original.get("requires_human_approval") is True,
                    "answers_this_packet": original.get("opportunity_packet_id") == packet.get("id"),
                    "finance_flag_forces_review": "finance_education_only" not in packet.get("risk_flags", [])
                                                  or original.get("legal_readiness") == "review_required"})

    replay_refused = False
    try:
        organ_bridge.record_exchange(journal, mission_id=mission, headers=d["headers"], body=d["body"].encode(),
                                     nonce_cache=cache, expected_sender="daleobanks",
                                     expected_operation="opportunity.evaluate")
    except bt.BridgeSecurityError:
        replay_refused = True

    events = [{"type": e.type, "event_id": e.event_id, "payload": e.payload,
               "at": e.payload.get("at") or e.occurred_at} for e in journal.replay("")]
    trace_view = observability.correlate(events, mission)["missions"][mission]
    result = {
        "mission_id": mission, "trace_id": trace,
        "system_44_trace": [{k: s[k] for k in ("kind", "event_id") if k in s} | ({"verdict": s["verdict"]} if "verdict" in s else {})
                            for s in trace_view["spans"]],
        "system_44_metrics": observability.metrics(events),
        "organs_observed": sorted({e.payload["organ"] for e in journal.replay("mission.observed")}),
        "sender_identity_isolated": sorted({e.payload["sender_identity_isolated"] for e in journal.replay("mission.observed")}),
        "appraisal": appraisal, "replay_refused": replay_refused,
        "vepmc": metrics.vepmc(journal)["VEPMC"], "routing_track_records": routing.track_record(journal),
        "ledger_chain": journal.ledger.verify_chain(),
        "external_effects": None, "spend_usd": 0.0,
    }
    (out / "organ-bridge-live.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps(result, indent=2, default=str))
    ok = (appraisal["verdict"] == "REPRODUCED" and replay_refused and result["vepmc"] == 0
          and result["routing_track_records"] == {} and result["system_44_metrics"]["verified_rate"] == 0.0
          and result["organs_observed"] == ["daleobanks", "wealthmachine"] and result["ledger_chain"][0])
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
