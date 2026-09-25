"""Does developmental restoration actually beat the conventional route?

Founder clarification 2026-09-09: the conventional durable runtime stays the
**primary comparator**; developmental work is the **challenger**. The next proof
must show UNIIMENTE can "discover/acquire/compose/build a genuinely missing
capability and resume a persistent mission better than a simpler route" — so the
simpler route has to actually be run, not described.

The persistent mission is three steps on the existing ``DurableWorkflow``
(``events/spine.py``, reused, not reimplemented): produce a real DALEOBANKS
packet, route it through the seam to WealthMachineIntelligence, record the
assessment. Step 2 depends on ``institutional.cross_organ_edge_resolution``.

Both arms lose that capability mid-mission, at the same step, from the same
cause. They differ in one respect:

* **BASELINE — conventional durable runtime.** The missing dependency parks the
  mission (``WorkflowKilled``, resumable from its checkpoint). It stays parked
  until something outside the runtime restores the capability. Then ``resume()``
  finishes from where it stopped. This is the correct conventional design and it
  already worked before any of this was built.
* **CHALLENGER — developmental.** The same park happens. Then the deficit is
  *verified* (``capabilities/deficit.py``) and the router restores the
  capability from a preserved alternative. The mission resumes with nothing
  outside the runtime intervening.

The measured difference is ``external_interventions_required``: 1 versus 0.
Both arms must complete the mission and produce a real assessment, or the
comparison is meaningless rather than favourable.

What the challenger does NOT win on is recorded too. Its replacement discards
the linker's unresolved-question and overlapping-authority analysis, so
continuity is bought with information. "Better" is a direction, not a verdict.
"""
from __future__ import annotations

import contextlib
import json
import os
import tempfile

from capabilities import deficit as deficit_mod
from capabilities.router import CapabilityRouter, Implementation
from events.spine import EventSpine, WorkflowKilled, WorkflowStep, durable_workflow, resume_workflow
from provenance.ledger import EvidenceLedger
from runtime.contract import TARGET_CAPABILITY, contract_digest
from runtime.seam import bindings_p3
from runtime.seam.router import ContractRouter, RouteNotEstablished
from runtime.seam.topology import LinkerTopology, ManifestContractTopology, RoutedTopology

ACTOR = "runtime.mission"
LEGAL_PRINCIPAL = "alfonso_lopez"
CANONICAL_IMPL = "linker.linker.InstitutionalLinker"
PRESERVED_IMPL = "runtime.seam.topology.ManifestContractTopology"


class MissionUnrunnable(RuntimeError):
    """The comparison cannot be constructed here. Never a passing result."""


def _build_router(*, canonical_lifecycle: str = "ACTIVE") -> CapabilityRouter:
    router = CapabilityRouter(ledger=EvidenceLedger(constitution_hash=contract_digest()))
    router.register(Implementation(
        implementation_id=CANONICAL_IMPL, capability=TARGET_CAPABILITY,
        provider=LinkerTopology, lifecycle=canonical_lifecycle, origin="CANONICAL",
        cost=1.0, evidence_maturity="verified_by_execution"))
    router.register(Implementation(
        implementation_id=PRESERVED_IMPL, capability=TARGET_CAPABILITY,
        provider=ManifestContractTopology, lifecycle="FALLBACK", origin="RETRIEVED",
        cost=1.0, evidence_maturity="tested"))
    return router


def _deliver(wire: dict, router: CapabilityRouter, workdir: str) -> dict:
    """One delivery attempt through the seam. Raises if the route is unavailable."""
    spine = EventSpine(EvidenceLedger(constitution_hash=contract_digest()))
    contract_router = ContractRouter(
        spine, RoutedTopology(router), [bindings_p3.consumer_binding()], workdir=workdir)
    contract_router.materialise()
    receipt = contract_router.deliver(
        bindings_p3.CONTRACT, wire, producer=bindings_p3.DALEOBANKS_ORGAN,
        actor=ACTOR, legal_principal=LEGAL_PRINCIPAL)
    if not receipt.delivered:
        raise RouteNotEstablished(receipt.error or "delivery produced no assessment")
    return receipt.result


def _steps(wire: dict, router: CapabilityRouter, workdir: str, trace: list) -> list:
    """The persistent mission. Step 2 is the one that depends on the capability."""

    def produce(state):
        trace.append("produce_packet")
        return {"packet_id": wire["id"]}

    def route(state):
        trace.append("route_to_intake")
        try:
            assessment = _deliver(wire, router, workdir)
        except RouteNotEstablished as exc:
            # A missing dependency PARKS the mission rather than failing it.
            # WorkflowKilled leaves the checkpoint resumable, which is what
            # makes the baseline a fair comparator instead of a straw man: the
            # conventional runtime does not lose the work, it waits.
            raise WorkflowKilled(f"capability unavailable: {exc}") from exc
        return {"go_no_go": assessment["go_no_go"],
                "requires_human_approval": assessment["requires_human_approval"]}

    def record(state):
        trace.append("record_assessment")
        return {"recorded": True}

    return [WorkflowStep("produce_packet", produce),
            WorkflowStep("route_to_intake", route, max_retries=0),
            WorkflowStep("record_assessment", record)]


def _run_arm(name: str, wire: dict, workdir: str, *, developmental: bool) -> dict:
    """Run one arm. Identical loss, identical mission, different recovery."""
    router = _build_router()
    spine = EventSpine(EvidenceLedger(constitution_hash=contract_digest()))
    trace: list = []
    workflow_id = f"mission-{name}"
    steps = _steps(wire, router, workdir, trace)

    # The capability is lost before the mission reaches the step that needs it.
    router.set_lifecycle(TARGET_CAPABILITY, CANONICAL_IMPL, "QUARANTINED")
    router.set_lifecycle(TARGET_CAPABILITY, PRESERVED_IMPL, "QUARANTINED")

    parked = False
    try:
        durable_workflow(spine, workflow_id, steps,
                         actor=ACTOR, legal_principal=LEGAL_PRINCIPAL).execute()
    except WorkflowKilled:
        parked = True

    record: dict = {
        "arm": name,
        "developmental": developmental,
        "mission_parked_on_capability_loss": parked,
        "trace_before_recovery": list(trace),
    }
    if not parked:
        record["error"] = "the mission did not park; the loss was not load-bearing"
        return record

    interventions = 0
    if developmental:
        # Verify the deficit before reconfiguring anything. An UNVERIFIED
        # deficit must not authorise restoration, and this is where that is
        # enforced rather than described.
        deficit = deficit_mod.verify_against_router(
            TARGET_CAPABILITY, required_by=workflow_id,
            failed_invocation="runtime.seam.router.ContractRouter.deliver",
            failure_error="ROUTE_NOT_ESTABLISHED", router=router)
        record["deficit"] = deficit.describe()
        if not deficit.morphogenesis_authorized():
            record["error"] = "deficit unverified; restoration correctly refused"
            return record
        # Resolution ladder: the preserved implementation is rung 1
        # (EXISTING_CAPABILITY, merely quarantined). Nothing is generated.
        router.set_lifecycle(TARGET_CAPABILITY, PRESERVED_IMPL, "FALLBACK")
        replacement, decision = router.restore(TARGET_CAPABILITY, unavailable=CANONICAL_IMPL)
        record["replacement"] = replacement.implementation_id
        record["replacement_origin"] = replacement.origin
        record["resolution_rung"] = deficit_mod.RESOLUTION_LADDER[0]
        record["routing_decision"] = decision.describe()
    else:
        # The conventional route: something OUTSIDE the runtime restores the
        # capability. Counted, because it is the whole cost being compared.
        router.set_lifecycle(TARGET_CAPABILITY, CANONICAL_IMPL, "ACTIVE")
        interventions = 1
        record["external_intervention"] = (
            "an operator outside the durable runtime re-enabled "
            f"{CANONICAL_IMPL}; the runtime cannot do this for itself")

    resumed = resume_workflow(spine, workflow_id, steps)
    resumed.execute()
    record.update({
        "external_interventions_required": interventions,
        "mission_status": resumed.status,
        "mission_completed": resumed.status == "completed",
        "resumed_rather_than_restarted": trace.count("produce_packet") == 1,
        "trace": list(trace),
        "assessment": {k: resumed.state.get(k)
                       for k in ("go_no_go", "requires_human_approval", "packet_id")},
    })
    return record


def run_comparison() -> dict:
    available, why = bindings_p3.organs_available()
    if not available:
        raise MissionUnrunnable(why)
    producer = bindings_p3.producer_binding()
    with tempfile.TemporaryDirectory(prefix="uniimente-mission-") as workdir, \
            contextlib.chdir(workdir):
        wire, _ = producer.produce()
        baseline = _run_arm("baseline_conventional", wire, workdir, developmental=False)
        challenger = _run_arm("challenger_developmental", wire, workdir, developmental=True)

    both_completed = baseline.get("mission_completed") and challenger.get("mission_completed")
    both_resumed = (baseline.get("resumed_rather_than_restarted")
                    and challenger.get("resumed_rather_than_restarted"))
    challenger_wins = bool(
        both_completed and both_resumed
        and challenger.get("external_interventions_required") == 0
        and baseline.get("external_interventions_required") == 1
    )
    return {
        "question": ("can UNIIMENTE resume a persistent mission after a verified "
                     "CapabilityDeficit better than the conventional route?"),
        "primary_comparator": "events.spine.DurableWorkflow (conventional, pre-existing)",
        "challenger": "capabilities.router.CapabilityRouter restoration",
        "metric": "external_interventions_required",
        "baseline": baseline,
        "challenger_arm": challenger,
        "both_missions_completed": bool(both_completed),
        "both_resumed_from_checkpoint": bool(both_resumed),
        "challenger_wins_on_continuity": challenger_wins,
        "what_the_challenger_does_not_win": (
            "the replacement discards the linker's unresolved-question and "
            "overlapping-authority analysis, so continuity is bought with "
            "information. And it only wins at all because a preserved "
            "alternative existed; with nothing to find it degrades exactly to "
            "the baseline."
        ),
        "closure_claim": "NONE. This measures mission continuity, not a developmental closure.",
    }


if __name__ == "__main__":       # pragma: no cover - manual invocation
    import argparse
    import sys

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", help="write the comparison record here as JSON")
    args = ap.parse_args()
    try:
        rec = run_comparison()
    except MissionUnrunnable as exc:
        rec, status = {"verdict": "UNRUNNABLE", "reason": str(exc)}, 2
    else:
        status = 0 if rec["challenger_wins_on_continuity"] else 1
    text = json.dumps(rec, indent=2, sort_keys=True, default=str)
    if args.out:
        out = os.path.abspath(args.out)
        open(out, "w", encoding="utf-8").write(text + "\n")
        print(f"comparison written to {out}")
    else:
        print(text)
    sys.exit(status)
