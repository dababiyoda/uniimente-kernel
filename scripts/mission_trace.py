"""Read one mission's complete trace out of a body's own ledger (read-only), as the founder's handoff asks for it.

    python scripts/mission_trace.py <body home> <mission id> [--out trace.json]

Every field is re-read from retained events, receipts and delivered files; nothing is inferred or summarised by a
model. Intended outcome, selected intelligence, chosen tools, authority decision, executed steps, artifacts, proof,
persistence and retained learning are kept as separate sections. The executed steps are the canonical correlated
trace (``greg foundry trace``, ``foundry.systems.observability.correlate``); this view only adds what a handoff needs
around it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def trace(home: Path, mission_id: str) -> dict:
    from greg.body import Body
    with Body(home) as body:
        journal = body.journal
        mine = lambda kind: [e.payload for e in journal.replay(kind) if e.payload.get("mission_id") == mission_id]
        registered = mine("mission.registered")
        if not registered:
            raise SystemExit(f"no mission {mission_id!r} in {home}")
        spec = registered[-1]["spec"]
        actions = mine("mission.action")
        receipts = {r.hash for r in body.ledger.by_type("receipt")}
        chain_ok, chain_detail = body.ledger.verify_chain()
        attaches = [e.payload for e in journal.replay("capability.state")]
        decisions = [e.payload for e in journal.replay("decision.requested") if e.payload.get("mission_id") == mission_id]
        answers = [e.payload for e in journal.replay("decision.answered")
                   if e.payload.get("request_id") in {d["request_id"] for d in decisions}]
        appraised = mine("mission.appraised")
        achieved = mine("mission.achieved")
        observed = mine("mission.observed")
        events = [{"type": e.type, "event_id": e.event_id, "payload": e.payload,
                   "at": e.payload.get("at") or e.occurred_at} for e in journal.replay("")]
    from foundry.systems import observability
    spans = observability.correlate(events, mission_id)["missions"].get(mission_id, {}).get("spans", [])
    deliveries = sorted((home / "deliveries").rglob(mission_id.replace(":", "_") + "*"))
    used = sorted({a["capability"] for a in actions if a["status"] == "DONE"}
                  | {c["sensor"]["capability"] for c in spec["success_checks"]})
    intelligence = [{"action_id": a["action_id"], "capability": a["capability"], "routing": a.get("routing")}
                    for a in actions if a["capability"].startswith(("cognition.", "institution."))
                    and a["status"] == "DONE"]
    dossier = next((p for p in deliveries if p.suffix == ".json"), None)
    lesson = json.loads(dossier.read_text()).get("lesson") if dossier else None
    return {
        "mission_id": mission_id,
        "intended_outcome": {"founder_expression": spec["founder_expression"],
                             "intended_effect": spec["intended_effect"],
                             "success_checks": [c["description"] for c in spec["success_checks"]]},
        "selected_intelligence": intelligence,
        "chosen_tools": used,
        "authority_decision": {"light_cone": spec["light_cone"],
                               "capability_transitions": [{k: a.get(k) for k in ("capability_id", "state", "by")}
                                                          for a in attaches],
                               "founder_decisions_requested": [{k: d.get(k) for k in ("kind", "why_now")}
                                                               for d in decisions],
                               "founder_answers": [{k: a.get(k) for k in ("answer",)} for a in answers]},
        "executed_steps": [{k: a.get(k) for k in ("action_id", "attempt", "status", "capability", "receipt",
                                                  "cost_usd", "at")} for a in actions],
        "correlated_trace": spans,
        "artifacts": [{"path": str(p.relative_to(home)), "bytes": p.stat().st_size,
                       "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in deliveries if p.is_file()],
        "proof": {"observations": [{k: o.get(k) for k in ("check_id", "passed", "receipt")} for o in observed[-len(
                      spec["success_checks"]):]],
                  "independent_appraisal": appraised[-1] if appraised else None,
                  "achieved": bool(achieved),
                  "receipts_on_ledger": sum(1 for a in actions if a.get("receipt") in receipts)},
        "persistence": {"ledger_chain_verified": chain_ok, "chain_detail": str(chain_detail)[:200],
                        "ledger": str(home / "ledger.jsonl")},
        "retained_learning": {"lesson": lesson},
        "reality": "RECORDED_LOCAL_REHEARSAL; counts toward no VEPMC; a throwaway key authenticates no one",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("home", type=Path)
    parser.add_argument("mission_id")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    data = json.dumps(trace(args.home.resolve(), args.mission_id), indent=1, default=str)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(data + "\n")
    print(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
