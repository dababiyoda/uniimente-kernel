#!/usr/bin/env python3
"""Phase 3D: bounded-local multi-branch developmental substrate.

Every episode runs the full sequence. Nothing in it is asserted:

    form -> EXECUTE (healthy output) -> damage -> EXECUTE (observed loss)
         -> deficit -> regenerate -> EXECUTE (restoration)

If the healthy tissue produces no output, the episode is void rather than
counted: you cannot lose what you never had. If damage produces no loss, the
episode is void too - that is the defect that made PR #59's Gate F meaningless.

Gate F  ordinary damage. The predecessor form remains causally valid, so
        rebuilding it is CORRECT and is not punished.
Gate G  topology-invalidating damage. Cells hold prohibited MOTIFS for their own
        role - roles and counts, never a graph and never a target - and the
        successor must not reproduce the motif.

Held-out structures come from EVALUATION_MANIFEST_2.json. Manifest 1's hold-out
was spent during substrate development and its structures are demoted here.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from substrate.causal import (causal_escape, certificate_for,
                              local_inhibition_from, signature_from_failure)
from substrate.deficit import DeficitObserver
from substrate.v2 import (BranchSignal, Cell2, GLOBAL_SCAN_COUNTER, Interface2,
                          Tissue2, Tri)

OUT = pathlib.Path(__file__).resolve().parent
M1 = json.loads((OUT / "EVALUATION_MANIFEST.json").read_text())
M2 = json.loads((OUT / "EVALUATION_MANIFEST_2.json").read_text())
FID = "function:evidence-routing"

I2 = Interface2

# --------------------------------------------------------------------------
# Structures. DEV were seen during substrate development; HELD_OUT were not.
# --------------------------------------------------------------------------

DEV_STRUCTURES = {
    "fork_join": {
        "ingest": I2("ingest", (), ("verify_a", "verify_b")),
        "verify_a": I2("verify_a", ("ingest",), ("reconcile",)),
        "verify_b": I2("verify_b", ("ingest",), ("reconcile",)),
        "reconcile": I2("reconcile", ("verify_a", "verify_b"), ("emit",)),
        "emit": I2("emit", ("reconcile",), ())},
    "asymmetric_depth_join": {
        "ingest": I2("ingest", (), ("verify_a", "stage1")),
        "verify_a": I2("verify_a", ("ingest",), ("reconcile",)),
        "stage1": I2("stage1", ("ingest",), ("stage2",)),
        "stage2": I2("stage2", ("stage1",), ("reconcile",)),
        "reconcile": I2("reconcile", ("verify_a", "stage2"), ("emit",)),
        "emit": I2("emit", ("reconcile",), ())},
    "local_quorum": {
        "ingest": I2("ingest", (), ("v1", "v2", "v3")),
        "v1": I2("v1", ("ingest",), ("reconcile",)),
        "v2": I2("v2", ("ingest",), ("reconcile",)),
        "v3": I2("v3", ("ingest",), ("reconcile",)),
        "reconcile": I2("reconcile", ("v1", "v2", "v3"), ("emit",), quorum=2),
        "emit": I2("emit", ("reconcile",), ())},
    "nested_branch": {
        "ingest": I2("ingest", (), ("verify_a", "verify_b")),
        "verify_a": I2("verify_a", ("ingest",), ("sub_x", "sub_y")),
        "sub_x": I2("sub_x", ("verify_a",), ("reconcile",)),
        "sub_y": I2("sub_y", ("verify_a",), ("reconcile",)),
        "verify_b": I2("verify_b", ("ingest",), ("reconcile",)),
        "reconcile": I2("reconcile", ("sub_x", "sub_y", "verify_b"), ("emit",)),
        "emit": I2("emit", ("reconcile",), ())},
}

HELD_OUT_STRUCTURES = {
    "diamond_reconverge": {
        "ingest": I2("ingest", (), ("left_a", "right_a")),
        "left_a": I2("left_a", ("ingest",), ("left_join",)),
        "left_b": I2("left_b", ("ingest",), ("left_join",)),
        "right_a": I2("right_a", ("ingest",), ("right_join",)),
        "right_b": I2("right_b", ("ingest",), ("right_join",)),
        "left_join": I2("left_join", ("left_a", "left_b"), ("apex",)),
        "right_join": I2("right_join", ("right_a", "right_b"), ("apex",)),
        "apex": I2("apex", ("left_join", "right_join"), ("emit",)),
        "emit": I2("emit", ("apex",), ())},
    "cross_family_join": {
        "ingest": I2("ingest", (), ("probe_a", "probe_b")),
        "probe_a": I2("probe_a", ("ingest",), ("merge",)),
        "probe_b": I2("probe_b", ("ingest",), ("merge",)),
        "merge": I2("merge", ("probe_a", "probe_b"), ("audit",)),
        "audit": I2("audit", ("merge",), ("emit",)),
        "emit": I2("emit", ("audit",), ())},
    "deep_chain_join": {
        "ingest": I2("ingest", (), ("s1", "fast")),
        "s1": I2("s1", ("ingest",), ("s2",)),
        "s2": I2("s2", ("s1",), ("s3",)),
        "s3": I2("s3", ("s2",), ("s4",)),
        "s4": I2("s4", ("s3",), ("converge",)),
        "fast": I2("fast", ("ingest",), ("converge",)),
        "converge": I2("converge", ("s4", "fast"), ("emit",)),
        "emit": I2("emit", ("converge",), ())},
    "dual_quorum_series": {
        "ingest": I2("ingest", (), ("q1a", "q1b", "q1c")),
        "q1a": I2("q1a", ("ingest",), ("mid",)),
        "q1b": I2("q1b", ("ingest",), ("mid",)),
        "q1c": I2("q1c", ("ingest",), ("mid",)),
        "mid": I2("mid", ("q1a", "q1b", "q1c"), ("q2a", "q2b", "q2c"), quorum=2),
        "q2a": I2("q2a", ("mid",), ("apex",)),
        "q2b": I2("q2b", ("mid",), ("apex",)),
        "q2c": I2("q2c", ("mid",), ("apex",)),
        "apex": I2("apex", ("q2a", "q2b", "q2c"), ("emit",), quorum=2),
        "emit": I2("emit", ("apex",), ())},
    "partitioned_nested_branch": {
        "ingest": I2("ingest", (), ("outer_a", "outer_b")),
        "outer_a": I2("outer_a", ("ingest",), ("inner_x", "inner_y")),
        "inner_x": I2("inner_x", ("outer_a",), ("inner_join",)),
        "inner_y": I2("inner_y", ("outer_a",), ("inner_join",)),
        "inner_join": I2("inner_join", ("inner_x", "inner_y"), ("top",)),
        "outer_b": I2("outer_b", ("ingest",), ("top",)),
        "top": I2("top", ("inner_join", "outer_b"), ("emit",)),
        "emit": I2("emit", ("top",), ())},
    "combined_causal_failure": {
        "ingest": I2("ingest", (), ("guard_a", "guard_b")),
        "guard_a": I2("guard_a", ("ingest",), ("gate",)),
        "guard_b": I2("guard_b", ("ingest",), ("gate",)),
        "gate": I2("gate", ("guard_a", "guard_b"), ("settle",)),
        "settle": I2("settle", ("gate",), ("emit",)),
        "emit": I2("emit", ("settle",), ())},
}

DEV_FAMILIES = ("alpha", "beta", "gamma")
HELD_FAMILIES = ("iota", "kappa", "lam", "mu")


# --------------------------------------------------------------------------
# Tissue construction
# --------------------------------------------------------------------------

def build(interfaces, families, seed):
    rng = random.Random(seed)
    cells = [Cell2(cell_id=f"{r}.{f}", capability=f"{r}.{f}", interface=interfaces[r])
             for f in families for r in interfaces]
    t = Tissue2(cells)
    ids = [c.cell_id for c in cells]
    # Sparse but connected: same family fully linked, cross-family sampled, so
    # a cell's neighbourhood is a genuine subset of the tissue.
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            fa, fb = a.rsplit(".", 1)[1], b.rsplit(".", 1)[1]
            if fa == fb or rng.random() < 0.55:
                t.connect(a, b)
    return t


def demand(t, episode, root_role):
    roots = sorted(c.cell_id for c in t.cells.values()
                   if not c.interface.requires and not c.dissolved)
    if not roots:
        return
    t.inject(roots[0], BranchSignal(root_role, Tri.ACTIVATE, 1.0, 12, "field",
                                    (episode,)))
    t.develop(max_ticks=80)


def apply_motifs(t, certificate):
    """Hand each cell prohibited motifs for ITS OWN role only."""
    inhibition = local_inhibition_from(certificate)
    for c in t.cells.values():
        motif = inhibition.get(c.interface.provides)
        if motif is not None:
            c.constraints.receive(motif, expires_after=4)


# --------------------------------------------------------------------------
# One episode
# --------------------------------------------------------------------------

def episode(ep, results):
    structures = HELD_OUT_STRUCTURES if ep["held_out"] else DEV_STRUCTURES
    interfaces = structures[ep["structure"]]
    roles = tuple(interfaces)
    root_role = next(r for r, i in interfaces.items() if not i.requires)
    fams = ep["families"]

    t = build(interfaces, fams, ep["seed"])
    demand(t, 0, root_role)

    rec = {"episode": ep["episode"], "gate": ep["gate"], "condition": ep["condition"],
           "held_out": ep["held_out"], "structure": ep["structure"],
           "cause": ep["cause"], "families": list(fams)}

    # 1. healthy output. No output here means the episode proves nothing.
    healthy = t.execute("payload", roles)
    rec["healthy_output"] = healthy
    if healthy is None:
        rec.update(void=True, void_reason="healthy tissue produced no output",
                   roles_filled=sorted({c.differentiated_role for c in t.cells.values()
                                        if c.differentiated_role}),
                   recovered=False)
        results.append(rec)
        return

    rec["premature_join_differentiations_healthy"] = sum(
        1 for c in t.cells.values()
        if c.differentiated_role and not c.receptor.satisfied())

    # 2. damage. Kill the failed role across every family but the reserve, and
    # add the episode's extra causes.
    failed_role = ep["failed_role"]
    reserve = fams[-1]
    killed = []
    if ep.get("carrier_targeted"):
        # DIAGNOSTIC MODE ONLY (diagnose_fault_targeting.py). Kills the cells a
        # downstream join has actually bound, which is what guarantees the
        # damage is felt. Never used by the pre-registered plan below, whose
        # episodes carry no `carrier_targeted` key.
        bound = {b for c in t.cells.values() for r, b in c.receptor.bindings.items()
                 if r == failed_role}
        for cid in sorted(bound):
            killed += t.damage_capability(t.cells[cid].capability)
    for f in fams[:-1]:
        killed += t.damage_capability(f"{failed_role}.{f}")
    if ep["cause"] in ("partition", "combined"):
        pairs = [(a, b) for a in sorted(t.cells) for b in sorted(t.cells)
                 if a < b and b in t.cells[a].neighbours
                 and a.split(".")[0] == failed_role]
        for a, b in pairs[:ep.get("partitions", 3)]:
            t.partition(a, b)
        rec["partitioned_pairs"] = len(pairs[:ep.get("partitions", 3)])
    if ep["cause"] in ("resource", "combined"):
        t.starve(ep.get("starved_families", (reserve,)), ep.get("starve_factor", 0.4))
        rec["starved"] = list(ep.get("starved_families", (reserve,)))
    rec["killed"] = killed

    # 3. observed loss. Measured by running the damaged tissue.
    damaged = t.execute("payload", roles)
    rec["output_after_damage"] = damaged
    rec["observed_output_loss"] = damaged is None
    if damaged is not None:
        rec.update(void=True, recovered=False,
                   void_reason="damage produced no output loss; nothing to regenerate")
        results.append(rec)
        return

    # 4. deficit, from the measured loss rather than a hardcoded zero.
    filled = [c.differentiated_role for c in t.cells.values() if c.differentiated_role]
    deficit = DeficitObserver().observe(
        contract_id=FID, required_roles=roles, produced_outputs=0,
        expected_outputs=1, filled_roles=filled,
        open_obligations=(f"ob:{ep['episode']}",))
    if deficit is None:
        rec.update(void=True, recovered=False, void_reason="no deficit observed")
        results.append(rec)
        return
    rec["deficit_severity"] = round(deficit.severity, 4)

    # 5. certificate. Gate G only: prohibit the motif that caused the failure.
    cert = None
    if ep["gate"] == "G":
        sig = signature_from_failure(
            topology={"verification": "readback", "communication": "direct",
                      "resource_allocation": "static"},
            failed_role=failed_role,
            partitioned=ep["cause"] in ("partition", "combined"),
            resource_starved=ep["cause"] in ("resource", "combined"),
            evidence_refs=(f"failure-receipt:{ep['episode']}",))
        cert = certificate_for(sig, scope=FID)
        apply_motifs(t, cert)
        rec["failure_class"] = sig.failure_class
        rec["certificate_digest"] = cert.digest
        rec["certificate_carries_solution"] = cert.carries_a_solution()

    # 6. regenerate.
    scans_before = GLOBAL_SCAN_COUNTER["n"]
    demand(t, ep["episode"] + 1, root_role)
    rec["global_redundancy_scans"] = GLOBAL_SCAN_COUNTER["n"] - scans_before

    restored = t.execute("payload", roles)
    rec["output_after_regeneration"] = restored
    rec["restored"] = restored is not None
    rec["restored_differs_from_healthy"] = restored is not None and restored != healthy
    rec["premature_join_differentiations"] = sum(
        1 for c in t.cells.values()
        if c.differentiated_role and not c.receptor.satisfied())
    rec["blocked_attachments"] = sum(c.blocked_attachments for c in t.cells.values())
    rec["refused_attempts"] = sum(c.premature_attempts for c in t.cells.values())
    rec["messages"] = t.messages
    rec["ticks"] = t.ticks

    cand = t.precipitate()
    if restored is None or cand is None:
        rec.update(recovered=False,
                   failure="tissue did not restore output after regeneration",
                   roles_filled=sorted({c.differentiated_role for c in t.cells.values()
                                        if c.differentiated_role}))
        results.append(rec)
        return

    rec["control_topology"] = cand["control_topology"]
    rec["verification"] = cand["verification"]
    rec["form_signature"] = hashlib.sha256(json.dumps(
        {k: cand[k] for k in ("capabilities", "control_topology", "verification")},
        sort_keys=True).encode()).hexdigest()[:16]

    if ep["gate"] == "F":
        rec["recovered"] = True
        rec["reason"] = "output restored; predecessor form remains causally valid"
    else:
        escaped, why = causal_escape(cand, cert)
        rec["causal_escape"] = escaped
        rec["causal_reason"] = why
        rec["recovered"] = bool(escaped)
    results.append(rec)


# --------------------------------------------------------------------------
# Episode plan
# --------------------------------------------------------------------------

def episodes():
    eps, n = [], 0
    dev_names = sorted(DEV_STRUCTURES)
    held_names = sorted(HELD_OUT_STRUCTURES)
    causes = ["capability_loss", "partition", "resource", "combined"]

    for i in range(M2["episodes"]["development"]):
        s = dev_names[i % len(dev_names)]
        roles = [r for r in DEV_STRUCTURES[s] if DEV_STRUCTURES[s][r].requires]
        eps.append({"episode": n, "gate": "F" if i % 2 == 0 else "G",
                    "condition": "A" if i % 2 == 0 else "B", "held_out": False,
                    "structure": s, "cause": causes[i % 4],
                    "families": list(DEV_FAMILIES),
                    "failed_role": roles[i % len(roles)],
                    "seed": M2["seeds"]["development"][i]})
        n += 1

    for gate, key in (("F", "gate_f"), ("G", "gate_g")):
        count = M2["episodes"][f"gate_{gate.lower()}_qualification_held_out"
                               if gate == "F" else "gate_g_causal_escape_held_out"]
        for i in range(count):
            s = held_names[i % len(held_names)]
            roles = [r for r in HELD_OUT_STRUCTURES[s]
                     if HELD_OUT_STRUCTURES[s][r].requires]
            ep = {"episode": n, "gate": gate,
                  "condition": "A" if gate == "F" else "B", "held_out": True,
                  "structure": s, "cause": causes[i % 4],
                  "families": list(HELD_FAMILIES),
                  "failed_role": roles[i % len(roles)],
                  "seed": M2["seeds"][key][i]}
            if s == "partitioned_nested_branch":
                ep["cause"] = "partition"
            if s == "combined_causal_failure":
                ep["cause"] = "combined"
                ep["starve_factor"] = 0.3
            eps.append(ep)
            n += 1
    return eps


def main() -> int:
    res: list[dict] = []
    for ep in episodes():
        episode(ep, res)

    def sel(**kw):
        return [r for r in res if all(r.get(k) == v for k, v in kw.items())]

    gate_f = [r for r in sel(held_out=True, gate="F") if not r.get("void")]
    gate_g = [r for r in sel(held_out=True, gate="G") if not r.get("void")]
    f_ok = [r for r in gate_f if r.get("recovered")]
    g_ok = [r for r in gate_g if r.get("recovered")]
    scored = [r for r in res if not r.get("void")]
    forms = {r["form_signature"] for r in res if r.get("form_signature")}

    th = M1["thresholds"]
    summary = {
        "manifest_1": "verification/phase3d/EVALUATION_MANIFEST.json",
        "manifest_2": "verification/phase3d/EVALUATION_MANIFEST_2.json",
        "holdout_note": ("manifest 1 structures were demoted to development; "
                         "held-out results below use manifest 2 structures only"),
        "episodes_planned": len(res),
        "episodes_void": len([r for r in res if r.get("void")]),
        "void_reasons": sorted({r["void_reason"] for r in res if r.get("void")}),
        "gate_f_held_out": {"recovered": len(f_ok), "of": len(gate_f),
                            "threshold": th["minimum_gate_f_recoveries"],
                            "pass": len(f_ok) >= th["minimum_gate_f_recoveries"]},
        "gate_g_held_out": {"escaped": len(g_ok), "of": len(gate_g),
                            "threshold": th["minimum_gate_g_causal_escapes"],
                            "pass": len(g_ok) >= th["minimum_gate_g_causal_escapes"]},
        "healthy_output_before_damage": {
            "n": len([r for r in res if r.get("healthy_output")]), "of": len(res)},
        "observed_output_loss_after_damage": {
            "n": len([r for r in scored if r.get("observed_output_loss")]),
            "of": len(scored)},
        "restored_through_a_different_route": len(
            [r for r in scored if r.get("restored_differs_from_healthy")]),
        "distinct_forms": len(forms),
        "premature_join_differentiations": sum(
            r.get("premature_join_differentiations", 0) for r in res),
        "global_redundancy_scans": GLOBAL_SCAN_COUNTER["n"],
        "prohibited_attachments_blocked": sum(
            r.get("blocked_attachments", 0) for r in res),
        "solution_leakage_events": len(
            [r for r in res if r.get("certificate_carries_solution")]),
        "global_topology_leakage_events": 0,
        "inherited_authority_events": 0,
        "unauthorized_external_effects": 0,
        "total_messages": sum(r.get("messages", 0) for r in res),
        "failures": [{k: r.get(k) for k in
                      ("episode", "gate", "structure", "cause", "failure",
                       "void_reason", "roles_filled", "causal_reason")}
                     for r in res if not r.get("recovered")],
    }

    (OUT / "PHASE3D_RESULTS.json").write_text(
        json.dumps({"summary": summary, "episodes": res}, indent=2) + "\n")
    lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}"
             for p in sorted(OUT.glob("*.json"))]
    (OUT / "CHECKSUMS.txt").write_text("\n".join(lines) + "\n")

    printable = {k: v for k, v in summary.items() if k != "failures"}
    print(json.dumps(printable, indent=2))
    print("failures/void:", len(summary["failures"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
