"""VEPMC — Verified Embodied Persistent Mission Closures, computed from retained history.

The Single Bottleneck Metric is derived only from ledger facts, never from
activity counts. A closure counts when EVERY condition holds for one mission:

  founder_signed        appraiser re-verified the Ed25519 mission signature
  interface_detached    the mission arrived through the inbox (the interface process had exited)
  persistent_runtime    it closed inside a hosted body run (a recorded boot)
  real_capability       at least one receipted Gate action or observation used a real capability
  approval_boundary     it met at least one founder approval boundary and honored it
  interruption_survived a body interruption was recovered between registration and closure
  appraised_verified    the separate-process appraiser returned VERIFIED (includes exactly-once)
  founder_accepted      Alfonso signed an accepting CRITIQUE of the closure (morning tribunal)
  founder_body          it ran on the body explicitly designated by a founder-signed command

The ledger can check key possession, designation, and process history. It cannot
establish the physical owner's identity or verify hardware ownership by itself.
Fixture results are structural tests, never external VEPMC evidence: a closure whose
receipts carry fixture-mode or fixture-tier output is reported with its conditions but
never counted, whatever else holds (the nine conditions themselves are unchanged).
"""
from __future__ import annotations

from greg import organ_bridge
from greg.journal import Journal

CONDITIONS = ("founder_signed", "interface_detached", "persistent_runtime", "real_capability",
              "approval_boundary", "interruption_survived", "appraised_verified", "founder_accepted", "founder_body")


def _fixture(value) -> bool:
    """Whether a receipted output carries a fixture stamp anywhere (``mode`` or ``tier`` "fixture",
    the marks fixture offers, journeys and media-company outputs put on everything they produce)."""
    if isinstance(value, dict):
        if str(value.get("mode", "")).lower() == "fixture" or str(value.get("tier", "")).lower() == "fixture":
            return True
        return any(_fixture(v) for v in value.values())
    if isinstance(value, list):
        return any(_fixture(v) for v in value)
    return False


def vepmc(journal: Journal) -> dict:
    ledger = journal.ledger
    seq = {r.payload.get("event_id"): r.seq for r in ledger.by_type("event")}
    registered = {e.payload["mission_id"]: seq[e.event_id] for e in journal.replay("mission.registered")}
    achieved = {e.payload["mission_id"]: (e, seq[e.event_id]) for e in journal.replay("mission.achieved")}
    appraised = {e.payload["mission_id"]: e for e in journal.replay("mission.appraised")}
    contexts = {e.payload["mission_id"]: e.payload for e in journal.replay("mission.closure_context")}
    accepted_designations = {e.payload["digest"]: seq[e.event_id] for e in journal.replay("command.accepted")
                             if e.payload.get("kind") == "BODY_DESIGNATE" and e.payload.get("signer") == "founder"}
    designations = [(e.payload, accepted_designations.get(e.payload.get("command_digest"), 1 << 60))
                    for e in journal.replay("body.designated")]
    recoveries = [seq[e.event_id] for e in journal.replay("body.recovered")]
    accepted_targets = {e.payload["target_event_id"] for e in journal.replay("critique.recorded")
                        if e.payload["verdict"] == "accept"}
    rows = []
    for mid, (event, done_seq) in achieved.items():
        appraisal = appraised.get(mid)
        checks = appraisal.payload.get("checks", {}) if appraisal else {}
        receipts = [e for e in journal.replay("mission.observed")
                    if e.payload["mission_id"] == mid and e.payload.get("receipt")]
        context = contexts.get(mid, {})
        row = {
            "founder_signed": bool(checks.get("founder_signature_verified")),
            "interface_detached": bool(checks.get("arrived_via_inbox")),
            "persistent_runtime": bool(context.get("hosted")),
            "real_capability": bool(receipts),
            "approval_boundary": bool(checks.get("approval_boundary_encountered"))
                                 and bool(checks.get("approval_boundaries_honored")),
            "interruption_survived": any(registered.get(mid, 1 << 60) < r < done_seq for r in recoveries),
            "appraised_verified": bool(appraisal) and appraisal.payload.get("verdict") == "VERIFIED",
            "founder_accepted": bool(accepted_targets & {event.event_id, appraisal.event_id if appraisal else None}),
            "founder_body": any(d.get("body_id") == context.get("body_id")
                                and d.get("platform") == context.get("platform")
                                and d.get("purpose") == "first_founder_body"
                                and designation_seq < registered.get(mid, 0)
                                for d, designation_seq in designations),
        }
        # The Gate receipts behind this closure's observations and actions: simulated (fixture) evidence
        # never moves the Single Bottleneck Metric, even when every condition is met.
        evidence = [e.payload.get("receipt") for kind in ("mission.observed", "mission.action")
                    for e in journal.replay(kind) if e.payload.get("mission_id") == mid and e.payload.get("receipt")]
        fixture = any(_fixture((record.payload.get("result") or {}).get("output"))
                      for record in (ledger.find(h) for h in evidence)
                      if record is not None and record.record_type == "receipt")
        rows.append({"mission_id": mid, "closure_event_id": event.event_id, **row,
                     "fixture_evidence": fixture,
                     "counts": all(row[c] for c in CONDITIONS) and not fixture,
                     "missing": [c for c in CONDITIONS if not row[c]] + (["no_fixture_evidence"] if fixture else [])})
    return {"VEPMC": sum(r["counts"] for r in rows), "missions": rows, "conditions": list(CONDITIONS),
            "external_confirmation_required": "ledger checks cannot prove physical ownership or personal presence"}


# -- engineering diagnostic: sandbox whole-machine closures (NEVER VEPMC) ---------------------

STAGES = ("founder_signed_via_inbox", "mind_certified_without_model", "capability_formed", "organs_reproduced",
          "worker_accepted", "interruption_reconciled", "appraised_verified")


def sandbox_whole_machine(journal: Journal) -> dict:
    """How many closed missions exercised the whole machine on one path, from ledger facts.

    A diagnostic for engineering convergence, distinct from VEPMC by name, by evidence tier and
    by construction: it needs no founder acceptance and no founder-designated body, and it counts
    synthetic-authority test runs. It must never be reported as, added to, or substituted for VEPMC.

      founder_signed_via_inbox      appraiser re-verified the signature; the mission came through the inbox
      mind_certified_without_model  a Competency Compiler receipt ANSWERED with a certified result, 0 model calls
      capability_formed             Genesis opened, verified and resolved a deficit for this mission
      organs_reproduced             two organs observed, transport-verified, organ.appraised REPRODUCED,
                                    counting only facts a DONE organ.exchange receipt stands behind
      worker_accepted               a passing check whose sensor is worker.appraise observed ACCEPTED

    Each stage is read from the observation of the capability it names (resolved through the
    registered spec), so another sensor's output that happens to look alike never counts.
      interruption_reconciled       a body recovery between registration and closure, and a founder
                                    reconciliation answered for this mission (no blind retry)
      appraised_verified            the separate-process closure appraisal returned VERIFIED
    """
    ledger = journal.ledger
    seq = {r.payload.get("event_id"): r.seq for r in ledger.by_type("event")}
    registered = {e.payload["mission_id"]: seq[e.event_id] for e in journal.replay("mission.registered")}
    appraised = {e.payload["mission_id"]: e.payload for e in journal.replay("mission.appraised")}
    recoveries = [seq[e.event_id] for e in journal.replay("body.recovered")]
    reconciliations = {e.payload.get("request_id") for e in journal.replay("decision.requested")
                       if e.payload.get("kind") == "RECONCILIATION"}
    answered = {e.payload["request_id"] for e in journal.replay("decision.answered")
                if e.payload.get("answer", "").startswith("reconcile_")}
    requested_for = {e.payload["request_id"]: e.payload.get("mission_id") for e in journal.replay("decision.requested")}
    rows = []
    sensors = {}
    for e in journal.replay("mission.registered"):
        for check in e.payload.get("spec", {}).get("success_checks", []):
            sensors[(e.payload["mission_id"], check["check_id"])] = check.get("sensor", {}).get("capability", "")
    for event in journal.replay("mission.achieved"):
        mid, done = event.payload["mission_id"], seq[event.event_id]
        checks = (appraised.get(mid) or {}).get("checks", {})
        observed = [e.payload for e in journal.replay("mission.observed") if e.payload["mission_id"] == mid]
        outputs = []
        for o in observed:
            record = ledger.find(o.get("receipt") or "") if o.get("receipt") else None
            if record is not None and record.record_type == "receipt":
                outputs.append((o, sensors.get((mid, o.get("check_id")), ""),
                                record.payload.get("result", {}).get("output")))
        organ_facts = organ_bridge.bound_facts(journal, mid)
        organs = organ_facts["observed"]
        organ_verdicts = [a["verdict"] for a in organ_facts["appraisals"]]
        deficits = {e.payload["deficit_id"] for e in journal.replay("deficit.opened") if e.payload.get("mission_id") == mid}
        resolved = {e.payload["deficit_id"] for e in journal.replay("deficit.resolved") if e.payload.get("mission_id") == mid}
        verified = {e.payload["deficit_id"] for e in journal.replay("genesis.verified") if e.payload.get("passed")}
        row = {
            "founder_signed_via_inbox": bool(checks.get("founder_signature_verified")) and bool(checks.get("arrived_via_inbox")),
            "mind_certified_without_model": any(
                o.get("passed") and sensor.startswith("cognition.") and isinstance(out, dict)
                and out.get("schema") == "greg-competency-compilation/0.1"
                and out.get("state") == "ANSWERED" and str(out.get("confidence_type", "")).startswith("certified")
                and (out.get("cost") or {}).get("model_calls") == 0 for o, sensor, out in outputs),
            "capability_formed": bool(deficits & resolved & verified),
            "organs_reproduced": {o.get("organ") for o in organs} >= {"daleobanks", "wealthmachine"}
                                 and all(o.get("transport_verified") for o in organs)
                                 and bool(organ_verdicts) and organ_verdicts[-1] == "REPRODUCED",
            "worker_accepted": any(sensor == "worker.appraise" and isinstance(out, dict)
                                   and out.get("verdict") == "ACCEPTED" and o.get("passed")
                                   for o, sensor, out in outputs),
            "interruption_reconciled": any(registered.get(mid, 1 << 60) < r < done for r in recoveries)
                                       and any(requested_for.get(rid) == mid for rid in reconciliations & answered),
            "appraised_verified": (appraised.get(mid) or {}).get("verdict") == "VERIFIED",
        }
        rows.append({"mission_id": mid, **row, "whole_machine": all(row.values()),
                     "missing": [s for s in STAGES if not row[s]]})
    return {"SANDBOX_WHOLE_MACHINE_CLOSURES": sum(r["whole_machine"] for r in rows), "missions": rows,
            "stages": list(STAGES),
            "tier": "sandbox integration diagnostic: synthetic or test authority allowed; never VEPMC, never "
                    "founder acceptance, never real-world outcome evidence"}
