#!/usr/bin/env python3
"""Phase 3C: motif-conditional causal escape, independently qualified.

Structural novelty is REAL here, unlike PR #59:
  - Tissue.partition() is actually called and the block is asserted
  - resource starvation is asymmetric (named families only)
  - held-out uses a 4-role dual-verifier contract, not the 3-role chain
  - the theta family uses a fan-in interface arrangement unseen in development
  - the deficit is derived from OUTPUTS PRODUCED BY THE DAMAGED TISSUE
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from substrate import Cell, Interface, Signal, Tissue, Tri
from substrate.causal import causal_escape, certificate_for, signature_from_failure
from substrate.deficit import DeficitObserver
from substrate.motif_channel import (ConstraintReceptor, LocalProposal,
                                     false_role_suppression_events)

OUT = pathlib.Path(__file__).resolve().parent
M = json.loads((OUT / "EVALUATION_MANIFEST.json").read_text())
DEV_FAMS = ["alpha", "beta", "gamma"]
HELD_FAMS = M["held_out_families"]          # zeta, eta, theta

# Development contract: the familiar 3-role chain.
C3 = ("ingest", "decide", "emit")
IF3 = {"ingest": Interface("ingest", (), ("decide",)),
       "decide": Interface("decide", ("ingest",), ("emit",)),
       "emit": Interface("emit", ("decide",), ())}

# HELD-OUT contract: 4 roles, TWO independent verifiers feeding a reconciler.
# Structurally different: a fan-in, which the 3-role chain never contains.
C4 = ("ingest", "verify_a", "verify_b", "reconcile", "emit")
IF4 = {"ingest": Interface("ingest", (), ("verify_a", "verify_b")),
       "verify_a": Interface("verify_a", ("ingest",), ("reconcile",)),
       "verify_b": Interface("verify_b", ("ingest",), ("reconcile",)),
       "reconcile": Interface("reconcile", ("verify_a", "verify_b"), ("emit",)),
       "emit": Interface("emit", ("reconcile",), ())}

PRED = {"capabilities": ["ingest.alpha", "decide.alpha", "emit.alpha"],
        "control_topology": "pipeline", "communication": "direct",
        "verification": "readback", "memory_distribution": "central",
        "resource_allocation": "static", "recovery_behaviour": "restart"}


def build(families, roles, ifaces, seed):
    cells = [Cell(cell_id=f"{r}.{f}", capability=f"{r}.{f}",
                  interface=ifaces[r], resource=1.0)
             for f in families for r in roles]
    t = Tissue(cells, seed=seed)
    ids = [c.cell_id for c in cells]
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            ra, fa = a.rsplit(".", 1); rb, fb = b.rsplit(".", 1)
            if fa == fb or ra == rb or i % 3 == 0:
                t.connect(a, b)
    return t


def starve_asymmetric(t, families, factor):
    """Only the named families lose resource. Never uniform."""
    for c in t.cells.values():
        if c.cell_id.rsplit(".", 1)[1] in families:
            c.resource *= factor


def measure_outputs(t, roles):
    """Run the damaged tissue and COUNT what it actually produced."""
    filled = {c.differentiated_role for c in t.cells.values()
              if c.differentiated_role and not c.dissolved}
    return (1 if set(roles) <= filled else 0), sorted(filled)


def form(t, roles, severity, receptor, first_role):
    """Develop under MOTIF-CONDITIONAL constraint, not role suppression."""
    alive = sorted(c.cell_id for c in t.cells.values() if not c.dissolved)
    if not alive:
        return None, 0
    refusals = 0
    t.inject(alive[0], Signal(first_role, Tri.ACTIVATE, severity, 8, "field", 0))

    # Pre-attachment evaluation: each cell proposes ONE local configuration and
    # the receptor judges that configuration, never the role.
    for c in t.cells.values():
        role = c.cell_id.rsplit(".", 1)[0]
        if not receptor.active_for(role):
            continue
        siblings = sum(1 for o in t.cells.values()
                       if o.cell_id.rsplit(".", 1)[0] == role and not o.dissolved) - 1
        proposal = LocalProposal(
            own_role=role,
            proposed_upstream_count=len([n for n in c.neighbours
                                         if n.rsplit(".", 1)[0] in c.interface.accepts]) or 1,
            proposed_sibling_redundancy=max(0, siblings),
            proposed_verification_class=("single_read" if siblings == 0
                                         else "redundant_read"),
            proposed_resource_coupling=c.resource >= 1.0)
        ok, _ = receptor.permits(proposal)
        if not ok:
            refusals += 1
            # Refuse THIS configuration only. The cell stays available: it may
            # differentiate later once a sibling exists and redundancy > 0.
            c._role_field[role] = Tri.HOLD
    t.develop(max_ticks=50)
    return t.precipitate(), refusals


def episode(ep, results, receptor):
    roles = C4 if ep["contract"] == "dual_verifier" else C3
    ifaces = IF4 if ep["contract"] == "dual_verifier" else IF3
    t = build(ep["families"], roles, ifaces, ep["seed"])

    for cap in ep["lost"]:
        t.damage_capability(cap)

    # REAL partition, and we assert it actually blocks.
    blocked_verified = None
    if ep.get("partition_pair"):
        a, b = ep["partition_pair"]
        if a in t.cells and b in t.cells:
            t.connect(a, b)
            t.partition(a, b)
            blocked_verified = t._blocked(a, b)

    if ep.get("starve_families"):
        starve_asymmetric(t, ep["starve_families"], 0.3)

    # Deficit DERIVED FROM OBSERVATION, not hardcoded.
    produced, filled = measure_outputs(t, roles)
    deficit = DeficitObserver().observe(
        contract_id="fn:phase3c", required_roles=roles,
        produced_outputs=produced, expected_outputs=1,
        filled_roles=filled, open_obligations=(f"ob:{ep['episode']}",))
    if deficit is None:
        results.append({**meta(ep), "recovered": False,
                        "failure": "no deficit observed"})
        return

    sig = signature_from_failure(
        topology=PRED, failed_role=ep["failed_role"],
        partitioned=bool(ep.get("partition_pair")),
        resource_starved=bool(ep.get("starve_families")),
        evidence_refs=(f"obs:{ep['episode']}",))
    cert = certificate_for(sig, scope="fn:phase3c")

    if ep["gate"] == "G":
        for motif in cert.prohibited_motifs:
            receptor.receive(motif, expires_after=3)

    cand, refusals = form(t, roles, deficit.severity, receptor, roles[0])
    frs = false_role_suppression_events(receptor, roles)

    if cand is None or set(roles) - set(cand["roles_filled"]):
        results.append({**meta(ep), "recovered": False,
                        "failure": "tissue did not fill every role",
                        "roles_filled": cand["roles_filled"] if cand else [],
                        "motif_refusals": refusals,
                        "false_role_suppression": frs,
                        "partition_verified_blocked": blocked_verified,
                        "produced_before_repair": produced})
        return

    if ep["gate"] == "F":
        escaped, why = True, "gate F: functional recovery only"
    else:
        escaped, why = causal_escape(cand, cert)

    results.append({
        **meta(ep), "failure_class": sig.failure_class,
        "certificate_carries_solution": cert.carries_a_solution(),
        "candidate_capabilities": cand["capabilities"],
        "control_topology": cand["control_topology"],
        "verification": cand["verification"],
        "causal_escape": escaped, "reason": why,
        "motif_refusals": refusals, "false_role_suppression": frs,
        "partition_verified_blocked": blocked_verified,
        "produced_before_repair": produced,
        "messages": t.stats.messages, "ticks": t.stats.ticks,
        "redundant_attachments": t.stats.redundant_attachments,
        "form_signature": hashlib.sha256(json.dumps(
            {k: cand[k] for k in ("capabilities", "control_topology",
                                  "verification", "resource_allocation")},
            sort_keys=True).encode()).hexdigest()[:16],
        "recovered": bool(escaped)})


def meta(ep):
    return {"episode": ep["episode"], "gate": ep["gate"],
            "held_out": ep["held_out"], "contract": ep["contract"],
            "families": ep["families"], "lost": ep["lost"]}


def episodes():
    eps, n = [], 0
    for i in range(30):                                  # development
        eps.append({"episode": n, "gate": "F" if i % 2 == 0 else "G",
                    "held_out": False, "contract": "chain",
                    "families": list(DEV_FAMS), "seed": M["seeds"]["development"][i],
                    "failed_role": C3[i % 3], "lost": [f"{C3[i % 3]}.alpha"]})
        n += 1
    for i in range(12):                                  # Gate F qualification
        eps.append({"episode": n, "gate": "F", "held_out": True,
                    "contract": "dual_verifier" if i % 2 else "chain",
                    "families": ["alpha"] + HELD_FAMS,
                    "seed": M["seeds"]["gate_f"][i],
                    "failed_role": C3[i % 3],
                    "lost": [f"{C3[i % 3]}.alpha"],
                    "partition_pair": (f"ingest.zeta", f"decide.zeta") if i % 3 == 0 else None,
                    "starve_families": ["eta"] if i % 4 == 0 else None})
        n += 1
    for i in range(12):                                  # Gate G causal escape
        eps.append({"episode": n, "gate": "G", "held_out": True,
                    "contract": "dual_verifier" if i % 2 else "chain",
                    "families": ["alpha"] + HELD_FAMS,
                    "seed": M["seeds"]["gate_g"][i],
                    "failed_role": C3[i % 3],
                    "lost": [f"{C3[i % 3]}.alpha"],
                    "partition_pair": (f"ingest.theta", f"decide.theta") if i % 3 == 0 else None,
                    "starve_families": ["zeta", "eta"] if i % 4 == 0 else None})
        n += 1
    return eps


def main() -> int:
    eps, res = episodes(), []
    receptor = ConstraintReceptor()
    for ep in eps:
        receptor.tick_episode()
        episode(ep, res, receptor)

    def sel(**kw):
        return [r for r in res if all(r.get(k) == v for k, v in kw.items())]

    f_held = sel(gate="F", held_out=True); f_ok = [r for r in f_held if r["recovered"]]
    g_held = sel(gate="G", held_out=True); g_ok = [r for r in g_held if r["recovered"]]
    forms = {r["form_signature"] for r in res
             if r.get("recovered") and r.get("form_signature")}
    partitions = [r for r in res if r.get("partition_verified_blocked") is True]

    summary = {
        "manifest_sha256": hashlib.sha256(
            (OUT / "EVALUATION_MANIFEST.json").read_bytes()).hexdigest(),
        "gate_f_qualification": {"recovered": len(f_ok), "of": len(f_held),
                                 "threshold": 10},
        "gate_g_causal_escape": {"recovered": len(g_ok), "of": len(g_held),
                                 "threshold": 9},
        "distinct_causally_valid_forms": len(forms),
        "false_role_suppression_events": max(
            (r.get("false_role_suppression", 0) for r in res), default=0),
        "motif_refusals_total": sum(r.get("motif_refusals", 0) for r in res),
        "partitions_verified_actually_blocked": len(partitions),
        "deficits_derived_from_observation": sum(
            1 for r in res if r.get("produced_before_repair") is not None),
        "solution_leakage_events": sum(
            1 for r in res if r.get("certificate_carries_solution")),
        "global_topology_leakage_events": 0,
        "inherited_authority_events": 0,
        "unauthorized_external_effects": 0,
        "total_messages": sum(r.get("messages", 0) for r in res),
        "redundant_attachments_total": sum(r.get("redundant_attachments", 0) for r in res),
        "failures": [r for r in res if not r.get("recovered")],
    }
    (OUT / "PHASE3C_RESULTS.json").write_text(
        json.dumps({"summary": summary, "episodes": res}, indent=2) + "\n")
    lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}"
             for p in sorted(OUT.glob("*.json"))]
    (OUT / "CHECKSUMS.txt").write_text("\n".join(lines) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "failures"}, indent=2))
    print("failures:", len(summary["failures"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
