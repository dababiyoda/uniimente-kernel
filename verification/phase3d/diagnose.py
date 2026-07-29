#!/usr/bin/env python3
"""Phase 3D diagnostics. NOT gate qualification.

Nothing here counts toward Gate F or Gate G. The pre-registered run
(run_phase3d.py) failed both gates; these two probes establish WHY, so the next
phase gets a target rather than a mood.

D1  fault targeting. 25 of 68 pre-registered episodes were void because the
    damage did not remove the cells a join had actually bound. Re-runs the same
    plan with carrier-targeted injection to measure how much of the void rate is
    instrument and how much is substrate.

D2  escape reachability. Gate G failed on 6 of 6 shared_resource_exhaustion
    episodes and passed 5 of 5 others. Enumerates every candidate the substrate
    can emit and checks whether ANY of them escapes that motif.
"""
from __future__ import annotations

import itertools
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from substrate.causal import (FAILURE_CLASSES, causal_escape, certificate_for,
                              signature_from_failure)

import run_phase3d as R

OUT = pathlib.Path(__file__).resolve().parent


def d1_fault_targeting() -> dict:
    plan = [dict(ep, carrier_targeted=True) for ep in R.episodes()]
    res: list[dict] = []
    for ep in plan:
        R.episode(ep, res)
    void = [r for r in res if r.get("void")]
    held_f = [r for r in res if r["held_out"] and r["gate"] == "F" and not r.get("void")]
    held_g = [r for r in res if r["held_out"] and r["gate"] == "G" and not r.get("void")]
    return {
        "label": "DIAGNOSTIC ONLY - does not qualify any gate",
        "episodes": len(res),
        "void": len(void),
        "void_by_reason": {reason: sum(1 for r in void if r.get("void_reason") == reason)
                           for reason in sorted({r.get("void_reason") for r in void})},
        "gate_f_valid_episodes": len(held_f),
        "gate_f_recovered": sum(1 for r in held_f if r.get("recovered")),
        "gate_g_valid_episodes": len(held_g),
        "gate_g_escaped": sum(1 for r in held_g if r.get("recovered")),
        "comparison_note": ("pre-registered run had 25 void, 11 valid Gate F "
                            "episodes and 11 valid Gate G episodes"),
    }


def d2_escape_reachability() -> dict:
    """Can the substrate express an escape from each failure class at all?"""
    # Every value precipitate() can emit for each dimension it reports.
    topologies = ["fan_in", "pipeline"]
    verifications = ["dual_read", "readback"]
    resource_allocations = ["static"]          # precipitate() emits ONLY this
    redundancies = [0, 1, 2]

    findings = {}
    for cls in FAILURE_CLASSES:
        sig = signature_from_failure(
            topology={"verification": "readback", "communication": "direct",
                      "resource_allocation": "static"},
            failed_role="gate",
            partitioned=(cls == "partition_intolerant_coupling"),
            resource_starved=(cls == "shared_resource_exhaustion"))
        if sig.failure_class != cls:
            sig = None
        cert = certificate_for(
            signature_from_failure(
                topology={"verification": "readback" if cls == "unredundant_verification"
                          else "dual_read",
                          "communication": "direct",
                          "resource_allocation": "static"},
                failed_role="gate",
                partitioned=(cls == "partition_intolerant_coupling"),
                resource_starved=(cls == "shared_resource_exhaustion")),
            scope="function:evidence-routing")
        reachable = []
        for topo, verif, alloc, red in itertools.product(
                topologies, verifications, resource_allocations, redundancies):
            cand = {"capabilities": [f"gate.{i}" for i in range(red + 1)],
                    "control_topology": topo, "verification": verif,
                    "resource_allocation": alloc}
            escaped, _ = causal_escape(cand, cert)
            if escaped:
                reachable.append({"control_topology": topo, "verification": verif,
                                  "resource_allocation": alloc, "redundancy": red})
        findings[cert.failure_class] = {
            "prohibited_motif": {k: v for k, v in
                                 cert.prohibited_motifs[0].__dict__.items()
                                 if v is not None},
            "candidate_forms_enumerated": len(topologies) * len(verifications)
                                          * len(resource_allocations) * len(redundancies),
            "escaping_forms_available": len(reachable),
            "escape_reachable": bool(reachable),
            "example_escape": reachable[0] if reachable else None,
        }
    return {
        "label": "DIAGNOSTIC ONLY - does not qualify any gate",
        "method": ("enumerates every form Tissue2.precipitate() can emit and asks "
                   "whether any escapes each failure class"),
        "by_failure_class": findings,
        "conclusion": ("shared_resource_exhaustion has ZERO escaping forms because "
                       "precipitate() hardcodes resource_allocation='static', so the "
                       "motif matches every candidate the substrate can produce. "
                       "Gate G's 6 failures on that class are a readout that cannot "
                       "express the prohibited dimension, not a substrate that "
                       "failed to escape."),
    }


def main() -> int:
    report = {"d1_fault_targeting": d1_fault_targeting(),
              "d2_escape_reachability": d2_escape_reachability()}
    (OUT / "DIAGNOSTICS.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
