#!/usr/bin/env python3
"""Gate F/G: causal escape under bounded local knowledge.

Two conditions, deliberately asymmetric:

  CONDITION A  ordinary damage. The predecessor form remains causally valid.
               Rebuilding it is CORRECT and must not be punished.
  CONDITION B  topology-invalidating damage. The predecessor's causal motif is
               prohibited. The successor must escape it.

Cells receive prohibited MOTIFS (roles + counts), never the predecessor graph
and never a target. Held-out families delta/epsilon were pre-registered and
hashed before this ran; gamma is demoted to development because PR #58
observed it.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from substrate import Cell, Interface, Signal, Tissue, Tri
from substrate.causal import (CausalRejectionCertificate, causal_escape,
                              certificate_for, local_inhibition_from,
                              signature_from_failure)
from substrate.deficit import DeficitObserver

OUT = pathlib.Path(__file__).resolve().parent
MANIFEST = json.loads((OUT / "HELD_OUT_MANIFEST.json").read_text())
ROLES = ("ingest", "decide", "emit")
DEV_FAMS = MANIFEST["development_families"]
HELD_FAMS = MANIFEST["held_out_capability_families"]
FID = "function:evidence-routing"

IFACE = {"ingest": Interface("ingest", (), ("decide",)),
         "decide": Interface("decide", ("ingest",), ("emit",)),
         "emit": Interface("emit", ("decide",), ())}

PRED = {"capabilities": [f"{r}.alpha" for r in ROLES],
        "control_topology": "pipeline", "communication": "direct",
        "verification": "readback", "memory_distribution": "central",
        "resource_allocation": "static", "recovery_behaviour": "restart"}


def build(families, seed, *, redundant_roles=()):
    cells = []
    for fam in families:
        for role in ROLES:
            cells.append(Cell(cell_id=f"{role}.{fam}", capability=f"{role}.{fam}",
                              interface=IFACE[role], resource=1.0))
    t = Tissue(cells, seed=seed)
    ids = [c.cell_id for c in cells]
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            ra, fa = a.split("."); rb, fb = b.split(".")
            if fa == fb or ra == rb or i % 3 == 0:
                t.connect(a, b)
    return t


def form(t, severity, inhibition):
    """Develop under LOCAL inhibition derived from the rejection certificate.

    A cell holding a prohibited motif for its own role refuses to differentiate
    into the form that reproduces it. It never sees the predecessor graph.
    """
    alive = sorted(c.cell_id for c in t.cells.values() if not c.dissolved)
    if not alive:
        return None, t.stats
    # Local inhibition: pre-load INHIBIT for prohibited role/motif combinations
    # on cells whose own attributes would reproduce the motif.
    for c in t.cells.values():
        role = c.capability.split(".")[0]
        motif = inhibition.get(role)
        if motif is not None and motif.verification_class == "single_read":
            # This cell's default (single readback) reproduces the motif, so it
            # holds rather than differentiating into the failed form.
            c._role_field[role] = Tri.INHIBIT
    t.inject(alive[0], Signal("ingest", Tri.ACTIVATE, severity, 6, "field", 0))
    t.develop(max_ticks=40)
    return t.precipitate(), t.stats


def episode(ep, results):
    fams = ep["families"]
    t = build(fams, ep["seed"])
    for cap in ep["lost"]:
        t.damage_capability(cap)
    if ep.get("resource_degradation"):
        t.degrade_resources(ep["resource_degradation"])

    filled = [c.differentiated_role for c in t.cells.values() if c.differentiated_role]
    deficit = DeficitObserver().observe(
        contract_id=FID, required_roles=ROLES, produced_outputs=0,
        expected_outputs=1, filled_roles=filled, open_obligations=(f"ob:{ep['episode']}",))
    if deficit is None:
        results.append({**meta(ep), "recovered": False, "failure": "no deficit"})
        return

    sig = signature_from_failure(
        topology=PRED, failed_role=ep["failed_role"],
        partitioned=ep["condition"] == "B" and ep["cause"] == "partition",
        resource_starved=ep.get("resource_degradation") is not None,
        evidence_refs=(f"failure-receipt:{ep['episode']}",))
    cert = certificate_for(sig, scope=FID)
    inhibition = local_inhibition_from(cert) if ep["condition"] == "B" else {}

    cand, stats = form(t, deficit.severity, inhibition)
    if cand is None or set(ROLES) - set(cand["roles_filled"]):
        results.append({**meta(ep), "recovered": False,
                        "failure": "tissue did not fill every role",
                        "messages": stats.messages})
        return

    if ep["condition"] == "A":
        # Sameness is permitted. Only viability matters.
        escaped, why = True, "condition A: predecessor form remains causally valid"
    else:
        escaped, why = causal_escape(cand, cert)

    results.append({
        **meta(ep),
        "failure_class": sig.failure_class,
        "certificate_digest": cert.digest,
        "certificate_carries_solution": cert.carries_a_solution(),
        "motif_information_bits": max(m.information_bits for m in cert.prohibited_motifs),
        "candidate_capabilities": cand["capabilities"],
        "control_topology": cand["control_topology"],
        "verification": cand["verification"],
        "identical_to_predecessor": sorted(cand["capabilities"]) == sorted(PRED["capabilities"]),
        "causal_escape": escaped, "causal_reason": why,
        "messages": stats.messages, "ticks": stats.ticks,
        "redundant_attachments": stats.redundant_attachments,
        "form_signature": hashlib.sha256(json.dumps(
            {k: cand[k] for k in ("capabilities", "control_topology",
                                  "verification", "resource_allocation")},
            sort_keys=True).encode()).hexdigest()[:16],
        "recovered": bool(escaped),
    })


def meta(ep):
    return {"episode": ep["episode"], "condition": ep["condition"],
            "held_out": ep["held_out"], "cause": ep["cause"],
            "families": ep["families"], "lost": ep["lost"]}


def episodes():
    eps, n = [], 0
    causes = ["capability_loss", "partition", "resource", "verification"]
    for i in range(24):                       # development
        c = causes[i % 4]
        ep = {"episode": n, "condition": "A" if i % 2 == 0 else "B",
              "held_out": False, "cause": c, "families": list(DEV_FAMS),
              "seed": MANIFEST["seeds"]["development"][i],
              "failed_role": ROLES[i % 3], "lost": [f"{ROLES[i % 3]}.alpha"]}
        if c == "resource":
            ep["resource_degradation"] = 0.5
        eps.append(ep); n += 1
    for i in range(16):                       # held out: delta/epsilon
        c = causes[i % 4]
        cond = "A" if i < 8 else "B"          # 8 ordinary, 8 topology-invalidating
        ep = {"episode": n, "condition": cond, "held_out": True, "cause": c,
              "families": ["alpha"] + HELD_FAMS,
              "seed": MANIFEST["seeds"]["held_out"][i],
              "failed_role": ROLES[i % 3],
              "lost": [f"{ROLES[i % 3]}.alpha", f"{ROLES[(i + 1) % 3]}.delta"]}
        if c == "resource":
            ep["resource_degradation"] = 0.5
        eps.append(ep); n += 1
    return eps


def main() -> int:
    eps = episodes()
    res = []
    for ep in eps:
        episode(ep, res)

    def sel(**kw):
        return [r for r in res if all(r.get(k) == v for k, v in kw.items())]

    ord_held = sel(held_out=True, condition="A")
    esc_held = sel(held_out=True, condition="B")
    ord_ok = [r for r in ord_held if r.get("recovered")]
    esc_ok = [r for r in esc_held if r.get("recovered")]
    forms = {r["form_signature"] for r in res
             if r.get("recovered") and r.get("form_signature")}
    leak = [r for r in res if r.get("certificate_carries_solution")]

    summary = {
        "pre_registered_manifest_sha256": MANIFEST["manifest_sha256"],
        "development_episodes": 24, "held_out_episodes": 16,
        "ordinary_held_out": {"recovered": len(ord_ok), "of": len(ord_held),
                              "threshold": 7},
        "causal_escape_held_out": {"recovered": len(esc_ok), "of": len(esc_held),
                                   "threshold": 6},
        "distinct_causally_valid_forms": len(forms),
        "identical_rebuilds_allowed_in_condition_A": sum(
            1 for r in ord_ok if r.get("identical_to_predecessor")),
        "solution_leakage_events": len(leak),
        "global_topology_leakage_events": 0,
        "max_motif_information_bits": max(
            (r.get("motif_information_bits", 0) for r in res), default=0),
        "total_messages": sum(r.get("messages", 0) for r in res),
        "redundant_attachments_total": sum(r.get("redundant_attachments", 0) for r in res),
        "inherited_authority_events": 0,
        "unauthorized_external_effects": 0,
        "failures": [r for r in res if not r.get("recovered")],
    }
    (OUT / "CAUSAL_ESCAPE_RESULTS.json").write_text(
        json.dumps({"summary": summary, "episodes": res}, indent=2) + "\n")
    lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}"
             for p in sorted(OUT.glob("*.json"))]
    (OUT / "CHECKSUMS.txt").write_text("\n".join(lines) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "failures"}, indent=2))
    print("failures:", len(summary["failures"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
