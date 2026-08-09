"""The four-state counterfactual for ``institutional.cross_organ_edge_resolution``.

The question conditions 2 and 7 of the frozen contract ask is not "can the
kernel prove an edge" — it has always been able to. It is whether a running
process *consumes* that capability, such that losing it costs the institution a
function rather than merely a health-check verdict.

Four states, and the controls that make them mean anything:

* **STATE A — healthy.** Real topology, real binding. DALEOBANKS' refinery
  produces a packet; WealthMachineIntelligence's intake evaluates it.
* **STATE B — damaged.** Edge resolution unavailable. The route must not
  materialise, no assessment may appear, and if one does, that is a bypass to
  be found and named, not a pass.
* **STATE C — repaired.** The capability returns; the function returns with it.
* **STATE D — rolled back.** The damage is reapplied. A capability that cannot
  be lost a second time was never really being consumed the first time.

And the two controls without which STATE A proves nothing:

* a binding for an organ with no proven edge must be refused;
* a binding pointing into ``WealthMachineClient`` — the local mock — must be
  detected as a bypass.

Silence is not a passing result. If the organ checkouts are missing the episode
reports ``UNRUNNABLE`` and exits non-zero; it never reports a quiet success.
"""
from __future__ import annotations

import contextlib
import json
import os
import tempfile
from dataclasses import dataclass, field

from events.spine import EventSpine
from provenance.ledger import EvidenceLedger
from runtime.contract import TARGET_CAPABILITY, contract_digest
from runtime.seam import bindings_p3
from runtime.seam.binding import BindingError
from runtime.seam.router import BypassDetected, ContractRouter, RouteNotEstablished
from runtime.seam.topology import DisabledEdgeResolution, LinkerTopology

ACTOR = "runtime.seam.episode"
LEGAL_PRINCIPAL = "alfonso_lopez"


class EpisodeUnrunnable(RuntimeError):
    """The episode cannot be constructed here.

    Raised rather than returning a soft verdict, for the same reason
    ``IsolationUnavailable`` is: a caller that read "could not run" as "nothing
    failed" would turn an unrunnable experiment into a passing one.
    """


def _fresh_router(topology, bindings, workdir: str) -> tuple[ContractRouter, EventSpine]:
    """A new spine per state.

    Subscriptions are per-spine and permanent; reusing one across states would
    let STATE A's live route answer STATE B's delivery, which is precisely the
    contamination the counterfactual exists to exclude.
    """
    ledger = EvidenceLedger(constitution_hash=contract_digest())
    spine = EventSpine(ledger)
    return ContractRouter(spine, topology, bindings, workdir=workdir), spine


@dataclass
class StateResult:
    """One state's outcome. ``assessment_present`` is the load-bearing field."""

    state: str
    topology: str
    routes: int
    refused: list = field(default_factory=list)
    delivered: bool = False
    assessment_present: bool = False
    assessment: dict | None = None
    error: str | None = None
    receipt: dict | None = None
    executed_in_consumer_repo: int = 0
    files_written: list = field(default_factory=list)

    def describe(self) -> dict:
        d = {
            "state": self.state,
            "topology": self.topology,
            "routes": self.routes,
            "refused": self.refused,
            "delivered": self.delivered,
            "assessment_present": self.assessment_present,
            "executed_files_in_consumer_repo": self.executed_in_consumer_repo,
            "organ_files_written_in_scratch": self.files_written,
        }
        if self.assessment is not None:
            d["assessment"] = self.assessment
        if self.error:
            d["error"] = self.error
        if self.receipt:
            d["receipt"] = self.receipt
        return d


def _summarise(assessment: dict) -> dict:
    keep = ("go_no_go", "opportunity_score", "risk_level",
            "requires_human_approval", "opportunity_packet_id", "legal_readiness")
    return {k: assessment[k] for k in keep if k in assessment}


def _run_state(name: str, topology, wire: dict, workdir: str) -> StateResult:
    consumer = bindings_p3.consumer_binding()
    router, _ = _fresh_router(topology, [consumer], workdir)
    router.materialise()
    result = StateResult(
        state=name, topology=topology.provider_id, routes=len(router.routes),
        refused=[why for _, why in router.refused],
    )
    try:
        receipt = router.deliver(
            bindings_p3.CONTRACT, wire,
            producer=bindings_p3.DALEOBANKS_ORGAN,
            actor=ACTOR, legal_principal=LEGAL_PRINCIPAL,
        )
    except RouteNotEstablished as exc:
        result.error = str(exc)
        return result
    except BypassDetected as exc:
        result.error = f"BYPASS_DETECTED: {exc}"
        return result

    result.receipt = receipt.describe()
    result.delivered = receipt.delivered
    result.error = receipt.error
    result.executed_in_consumer_repo = len(
        receipt.executed_in(bindings_p3.WEALTHMACHINE_ROOT)
    )
    result.files_written = list(receipt.files_written)
    if receipt.delivered and isinstance(receipt.result, dict):
        result.assessment_present = True
        result.assessment = _summarise(receipt.result)
    return result


def _control_no_proven_edge(workdir: str) -> dict:
    """A binding whose organ has no proven edge must be refused."""
    router, _ = _fresh_router(LinkerTopology(), [bindings_p3.wrong_consumer_binding()], workdir)
    router.materialise()
    return {
        "control": "binding_without_proven_edge",
        "routes": len(router.routes),
        "refused": [why for _, why in router.refused],
        "fired": len(router.routes) == 0 and bool(router.refused),
    }


def _control_bypass_detected(wire: dict, workdir: str) -> dict:
    """A binding into the local mock evaluator must be caught, not accepted.

    Deliberately runs the route all the way to execution. Detection has to come
    from what actually ran, because "the mock is importable" is permanently
    true in any workspace with DALEOBANKS checked out and therefore
    discriminates nothing.
    """
    router, _ = _fresh_router(LinkerTopology(), [bindings_p3.bypass_consumer_binding()], workdir)
    router.materialise()
    if not router.routes:
        reasons = " | ".join(why for _, why in router.refused)
        return {
            "control": "bypass_binding_detected",
            "outcome": f"refused before execution: {reasons}",
            "fired": False,
            "note": (
                "the control never reached the detector, so it says nothing "
                "about whether the detector works"
            ),
        }
    try:
        receipt = router.deliver(
            bindings_p3.CONTRACT, wire, producer=bindings_p3.DALEOBANKS_ORGAN,
            actor=ACTOR, legal_principal=LEGAL_PRINCIPAL,
        )
    except BypassDetected as exc:
        return {"control": "bypass_binding_detected",
                "outcome": f"BypassDetected: {exc}", "fired": True}
    except (RouteNotEstablished, BindingError) as exc:
        return {"control": "bypass_binding_detected",
                "outcome": f"{type(exc).__name__}: {exc}", "fired": False}
    return {
        "control": "bypass_binding_detected",
        "outcome": ("DELIVERED WITHOUT DETECTION — the bypass detector is dead"
                    if receipt.delivered else f"undetected failure: {receipt.error}"),
        "fired": False,
    }


def run_episode() -> dict:
    """Run all four states plus both controls. Returns the full record."""
    ok, why = bindings_p3.organs_available()
    if not ok:
        raise EpisodeUnrunnable(why)

    producer = bindings_p3.producer_binding()

    # The whole episode runs inside a scratch directory, not just the
    # deliveries. Organ code writes relative to the working directory at
    # *import* time as well as at call time — WealthMachineIntelligence's agent
    # store logged a sqlalchemy warning into ``data/agent_store.jsonl`` the
    # moment its connector was imported, which landed inside the kernel
    # repository on the first two runs. Containing only the delivery left that
    # write in place, so containment starts before the producer runs and ends
    # after the last control.
    with tempfile.TemporaryDirectory(prefix="uniimente-p3-") as workdir, \
            contextlib.chdir(workdir):
        try:
            wire, producer_evidence = producer.produce()
        except BindingError as exc:
            raise EpisodeUnrunnable(f"producer side did not run: {exc}") from exc

        # The four states run contiguously and first, so nothing a control does
        # can be mistaken for part of the counterfactual. The controls then
        # judge whether STATE A's result was worth anything.
        state_a = _run_state("A_healthy", LinkerTopology(), wire, workdir)
        state_b = _run_state("B_damaged", DisabledEdgeResolution(TARGET_CAPABILITY),
                             wire, workdir)
        state_c = _run_state("C_repaired", LinkerTopology(), wire, workdir)
        state_d = _run_state("D_rolled_back", DisabledEdgeResolution(TARGET_CAPABILITY),
                             wire, workdir)
        control_edge = _control_no_proven_edge(workdir)
        control_bypass = _control_bypass_detected(wire, workdir)

    states = [state_a, state_b, state_c, state_d]
    discriminates = (
        state_a.assessment_present
        and not state_b.assessment_present
        and state_c.assessment_present
        and not state_d.assessment_present
    )
    controls_fired = control_edge["fired"] and control_bypass["fired"]
    non_vacuous = state_a.executed_in_consumer_repo > 0
    human_approval_held = bool(
        state_a.assessment and state_a.assessment.get("requires_human_approval") is True
    )

    if discriminates and controls_fired and non_vacuous and human_approval_held:
        verdict = "RUNTIME_CONSUMPTION_PROVEN"
    elif not controls_fired:
        verdict = "UNKNOWN_VACUOUS"          # never renders as a pass
    else:
        verdict = "RUNTIME_CONSUMPTION_NOT_PROVEN"

    return {
        "target_capability": TARGET_CAPABILITY,
        "contract_sha256": contract_digest(),
        "geometry": "B — one generic contract-delivery event; contract name is data",
        "producer_binding": producer.describe(),
        "consumer_binding": bindings_p3.consumer_binding().describe(),
        "producer_evidence": producer_evidence,
        "packet_id": wire.get("id"),
        "states": [s.describe() for s in states],
        "controls": [control_edge, control_bypass],
        "discriminates": discriminates,
        "controls_fired": controls_fired,
        "non_vacuous": non_vacuous,
        "human_approval_invariant_held": human_approval_held,
        "verdict": verdict,
    }


if __name__ == "__main__":  # pragma: no cover - manual invocation
    import argparse
    import sys

    # The organs log to stdout when they run — they are real services, not
    # fixtures, and silencing them would be tampering with the thing under
    # test. So the record gets its own channel: --out is the only way to read
    # it back reliably, and the exit status is the direct one, never a
    # pipeline's.
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", help="write the episode record here as JSON")
    args = ap.parse_args()

    try:
        record = run_episode()
    except EpisodeUnrunnable as exc:
        record, status = {"verdict": "UNRUNNABLE", "reason": str(exc)}, 2
    else:
        status = 0 if record["verdict"] == "RUNTIME_CONSUMPTION_PROVEN" else 1

    text = json.dumps(record, indent=2, sort_keys=True, default=str)
    if args.out:
        args.out = os.path.abspath(args.out)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"episode record written to {args.out}: {record['verdict']}")
    else:
        print(text)
    sys.exit(status)
