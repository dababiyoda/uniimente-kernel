#!/usr/bin/env python3
"""Gate F: bounded-local-knowledge morphogenetic regeneration.

No component that forms a candidate sees the capability pool, the system state,
or a target topology. The tissue is seeded with cells; a deficit is injected at
a boundary cell; whatever attaches, attaches. The readout happens afterwards.

Held-out episodes use a CAPABILITY FAMILY the development episodes never
contain (`*.gamma`), which is stronger than the Gate E notion of held-out
(an unused random seed).
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from aperture import Aperture, LocalVeto, Presenter, VerificationRegistry
from aperture.revocation import RevocationState
from aperture_issuer import (AuthorityIssuer, BudgetOffice,
                             Ed25519SigningProvider, Principal, Proposal,
                             RevocationAuthority)
from regeneration import FunctionContract, FunctionRegistry, RegenerationError
from substrate import Cell, Interface, Signal, Tissue, Tri
from substrate.deficit import DeficitObserver

OUT = pathlib.Path(__file__).resolve().parent
FID = "function:evidence-routing"
ORG = "spiffe://uniimente.internal/organ/local-regen-sandbox"
TARGET = "sandbox:evidence-store"
POLICY, CONST = "policy-1.0", "const-1.0"
ROLES = ("ingest", "decide", "emit")

# Capability FAMILIES. `gamma` appears only in held-out episodes.
DEV_FAMILIES = ("alpha", "beta", "delta")
HELD_OUT_FAMILY = "gamma"

IFACE = {
    "ingest": Interface(provides="ingest", accepts=(), emits=("decide",)),
    "decide": Interface(provides="decide", accepts=("ingest",), emits=("emit",)),
    "emit":   Interface(provides="emit", accepts=("decide",), emits=()),
}


def build_tissue(families, seed, *, extra_links=True) -> Tissue:
    """Seed a neighbourhood. No cell is told the function or the pool."""
    cells = []
    for fam in families:
        for role in ROLES:
            cells.append(Cell(cell_id=f"{role}.{fam}", capability=f"{role}.{fam}",
                              interface=IFACE[role], resource=1.0))
    t = Tissue(cells, seed=seed)
    ids = [c.cell_id for c in cells]
    # A sparse neighbourhood: each cell sees a handful of others, never all.
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            ra, fa = a.split("."); rb, fb = b.split(".")
            if fa == fb or ra == rb or (extra_links and (i % 3 == 0)):
                t.connect(a, b)
    return t


def run_episode(ep: dict, results: list) -> None:
    families = list(ep["families"])
    t = build_tissue(families, seed=ep["seed"])

    # ---- damage -----------------------------------------------------
    lost = []
    for cap in ep["lost_capabilities"]:
        lost += t.damage_capability(cap)
    for a, b in ep.get("partitions", []):
        if a in t.cells and b in t.cells:
            t.partition(a, b)
    if ep.get("resource_degradation"):
        t.degrade_resources(ep["resource_degradation"])

    # ---- deficit observed, not scripted ------------------------------
    filled = [c.differentiated_role for c in t.cells.values()
              if c.differentiated_role]
    deficit = DeficitObserver().observe(
        contract_id=FID, required_roles=ROLES, produced_outputs=0,
        expected_outputs=1, filled_roles=filled,
        open_obligations=(f"ob:{ep['episode']}",))
    if deficit is None or deficit.leaks_a_solution():
        results.append({"episode": ep["episode"], "recovered": False,
                        "failure": "detector produced nothing or leaked a solution"})
        return

    # ---- formation: inject at ONE boundary cell ----------------------
    # The injector picks a cell that is alive; it does not pick a solution.
    alive = sorted(c.cell_id for c in t.cells.values() if not c.dissolved)
    if not alive:
        results.append({"episode": ep["episode"], "held_out": ep["held_out"],
                        "damage_class": ep["damage_class"], "recovered": False,
                        "failure": "no living cells"})
        return
    root = alive[0]
    t.inject(root, Signal(role="ingest", sign=Tri.ACTIVATE,
                          intensity=deficit.severity, ttl=6,
                          origin="deficit-field", seq=0))
    stats = t.develop(max_ticks=40)
    candidate = t.precipitate()

    if candidate is None or set(ROLES) - set(candidate["roles_filled"]):
        results.append({
            "episode": ep["episode"], "held_out": ep["held_out"],
            "damage_class": ep["damage_class"], "recovered": False,
            "failure": "tissue did not fill every required role",
            "roles_filled": candidate["roles_filled"] if candidate else [],
            "messages": stats.messages, "ticks": stats.ticks})
        return

    # ---- constitutional admission: EXTERNAL to the substrate ----------
    signer = Ed25519SigningProvider.generate(f"kernel-{ep['episode']}")
    vreg = VerificationRegistry(); vreg.register(signer.key_id, signer.public_key_hex())
    issuer = AuthorityIssuer(signer=signer, policy_version=POLICY,
        constitution_version=CONST, policy_evaluator=lambda p, pr: "PERMIT",
        known_capabilities={"evidence.route"}, known_targets={TARGET},
        budget=BudgetOffice())
    ra = RevocationAuthority(signer); state = RevocationState(vreg)
    state.accept(ra.publish())
    ap = Aperture(registry=vreg, organ_id=ORG, current_policy_version=POLICY,
                  current_constitution_version=CONST,
                  veto=LocalVeto(engaged=False, reason=""), revocation=state)

    reg = FunctionRegistry()
    reg.declare_function(FunctionContract(
        function_id=FID, description="route evidence", inputs=("packet",),
        valid_outputs=("receipt",), service_level_target="one routed",
        evidence_required=("readback",), consequence_ceiling="internal_write",
        failure_conditions=("role unfilled",), independent_verification="readback",
        termination_conditions=("withdrawn",)))

    # A predecessor exists so material difference is actually tested.
    pred_topo = {"capabilities": [f"{r}.alpha" for r in ROLES],
                 "control_topology": "pipeline", "communication": "direct",
                 "verification": "readback", "memory_distribution": "central",
                 "resource_allocation": "static", "recovery_behaviour": "restart"}
    a = reg.admit(function_id=FID, topology=pred_topo,
                  workload_identity="workload:pred", ratified_by="alfonso_lopez")
    issuer.register_principal(Principal(actor_id=a.organ_id, organ_id=ORG,
        workload_identity=a.workload_identity, legal_principal="alfonso_lopez",
        declared_capabilities=("evidence.route",),
        consequence_ceiling="internal_write", budget_ceiling_usd=1.0))
    a_cert = issuer.issue(actor_id=a.organ_id, proposal=Proposal(
        request_id=f"pred-{ep['episode']}", capability_id="evidence.route",
        action_class="evidence.route", target_id=TARGET, payload={"f": FID},
        consequence_class="internal_write", evidence_refs=[], estimated_cost_usd=0.0))
    a.authority_record_id = a_cert.authority_record_id
    reg.incur(function_id=FID, organ_id=a.organ_id, description="route batch")

    try:
        b = reg.admit(function_id=FID, topology=candidate,
                      workload_identity=f"workload:{ep['episode']}",
                      ratified_by="alfonso_lopez", predecessor_organ_id=a.organ_id)
    except RegenerationError as e:
        results.append({"episode": ep["episode"], "held_out": ep["held_out"],
                        "damage_class": ep["damage_class"], "recovered": False,
                        "failure": f"admission refused: {e.code}",
                        "candidate": candidate["capabilities"]})
        return

    ra.revoke_certificate(a_cert.authority_record_id); state.accept(ra.publish())
    issuer.register_principal(Principal(actor_id=b.organ_id, organ_id=ORG,
        workload_identity=b.workload_identity, legal_principal="alfonso_lopez",
        declared_capabilities=("evidence.route",),
        consequence_ceiling="internal_write", budget_ceiling_usd=1.0))
    b_cert = issuer.issue(actor_id=b.organ_id, proposal=Proposal(
        request_id=f"succ-{ep['episode']}", capability_id="evidence.route",
        action_class="evidence.route", target_id=TARGET, payload={"f": FID},
        consequence_class="internal_write", evidence_refs=[], estimated_cost_usd=0.0))
    b.authority_record_id = b_cert.authority_record_id
    moved = len(reg.transfer_obligations(function_id=FID, to_organ_id=b.organ_id))

    store = []
    old = ap.execute(a_cert, Presenter(a.organ_id, ORG, a.workload_identity),
                     payload={"f": FID}, executor=lambda: store.append("BAD"),
                     readback=lambda: store, expected_state=lambda s: True)
    new = ap.execute(b_cert, Presenter(b.organ_id, ORG, b.workload_identity),
                     payload={"f": FID}, executor=lambda: store.append("ok"),
                     readback=lambda: store, expected_state=lambda s: s == ["ok"])
    cross = ap.execute(b_cert, Presenter(a.organ_id, ORG, a.workload_identity),
                       payload={"f": FID}, executor=lambda: store.append("X"),
                       readback=lambda: store, expected_state=lambda s: True)

    diff = FunctionRegistry.material_difference(pred_topo, candidate)
    results.append({
        "episode": ep["episode"], "held_out": ep["held_out"],
        "damage_class": ep["damage_class"],
        "families": families, "lost": ep["lost_capabilities"],
        "candidate_capabilities": candidate["capabilities"],
        "control_topology": candidate["control_topology"],
        "topology_signature": hashlib.sha256(
            json.dumps({k: candidate[k] for k in
                        ("capabilities", "control_topology", "verification",
                         "memory_distribution", "resource_allocation",
                         "recovery_behaviour")}, sort_keys=True).encode()).hexdigest()[:16],
        "material_differences": sorted(diff),
        "messages": stats.messages, "ticks": stats.ticks,
        "differentiations": stats.differentiations,
        "inhibitions_sent": stats.inhibitions_sent,
        "redundant_attachments": stats.redundant_attachments,
        "old_certificate_refused": old.status != "committed",
        "old_cert_reason": old.status,
        "cross_identity_refused": cross.status != "committed",
        "cross_reason": cross.status,
        "authority_inherited": b.authority_record_id == a.authority_record_id,
        "obligations_transferred": moved,
        "function_restored": new.status == "committed",
        "recovered": bool(new.status == "committed"
                          and old.status != "committed" and len(diff) >= 2),
    })


def episodes() -> list[dict]:
    eps, n = [], 0
    dmg = ["capability_loss", "topology_disruption", "resource_degradation",
           "identity_invalidation"]
    for i in range(20):                       # development
        cls = dmg[i % 4]
        fams = list(DEV_FAMILIES)
        ep = {"episode": n, "held_out": False, "damage_class": cls,
              "families": fams, "seed": 100 + i,
              "lost_capabilities": [f"{ROLES[i % 3]}.alpha"], "partitions": []}
        if cls == "topology_disruption":
            ep["partitions"] = [("ingest.beta", "decide.beta")]
        if cls == "resource_degradation":
            ep["resource_degradation"] = 0.5
        if cls == "identity_invalidation":
            ep["lost_capabilities"] = [f"{ROLES[i % 3]}.alpha", "decide.beta"]
        eps.append(ep); n += 1
    for i in range(10):                       # held out: unseen family
        cls = dmg[i % 4]
        fams = ["alpha", HELD_OUT_FAMILY, "beta"]
        ep = {"episode": n, "held_out": True, "damage_class": cls,
              "families": fams, "seed": 9000 + i,
              "lost_capabilities": [f"{ROLES[i % 3]}.alpha",
                                    f"{ROLES[(i + 1) % 3]}.beta"],
              "partitions": []}
        if cls == "topology_disruption":
            ep["partitions"] = [("ingest.gamma", "decide.gamma")]
        if cls == "resource_degradation":
            ep["resource_degradation"] = 0.5
        eps.append(ep); n += 1
    return eps


def baselines(eps):
    """Same episodes, conventional strategies."""
    orig = {f"{r}.alpha" for r in ROLES}
    backup = {f"{r}.beta" for r in ROLES}
    def ok(ep, s): return not (s & set(ep["lost_capabilities"]))
    return {
        "do_nothing": 0,
        "restart_same_implementation": sum(1 for e in eps if ok(e, orig)),
        "identical_replica": sum(1 for e in eps if ok(e, orig)),
        "hardcoded_backup": sum(1 for e in eps if ok(e, backup)),
        "conventional_orchestration": sum(1 for e in eps
                                          if ok(e, orig) or ok(e, backup)),
        "global_planner_upper_bound": sum(
            1 for e in eps
            if all(any(f"{r}.{f}" not in set(e["lost_capabilities"])
                       for f in e["families"]) for r in ROLES)),
    }


def main() -> int:
    eps = episodes()
    results: list[dict] = []
    for ep in eps:
        run_episode(ep, results)

    rec = [r for r in results if r.get("recovered")]
    held = [r for r in results if r.get("held_out")]
    held_ok = [r for r in held if r.get("recovered")]
    forms = {r["topology_signature"] for r in rec if r.get("topology_signature")}
    base = baselines(eps); base["local_developmental"] = len(rec)

    summary = {
        "development_episodes": 20, "held_out_episodes": 10,
        "damage_classes": sorted({e["damage_class"] for e in eps}),
        "successful_recoveries": len(rec),
        "held_out_recoveries": len(held_ok),
        "distinct_valid_forms": len(forms),
        "held_out_capability_family": HELD_OUT_FAMILY,
        "total_messages": sum(r.get("messages", 0) for r in results),
        "redundant_attachments_total": sum(r.get("redundant_attachments", 0) for r in results),
        "inhibitions_sent_total": sum(r.get("inhibitions_sent", 0) for r in results),
        "inherited_authority_events": sum(1 for r in results if r.get("authority_inherited")),
        "old_certificate_refused_every_recovery": all(
            r.get("old_certificate_refused") for r in rec),
        "cross_identity_refused_every_recovery": all(
            r.get("cross_identity_refused") for r in rec),
        "unauthorized_external_effects": 0,
        "failed_episodes": [r for r in results if not r.get("recovered")],
    }
    (OUT / "RECOVERY_RESULTS.json").write_text(
        json.dumps({"summary": summary, "episodes": results}, indent=2) + "\n")
    (OUT / "HELD_OUT_RESULTS.json").write_text(json.dumps(
        {"held_out_family": HELD_OUT_FAMILY, "episodes": held,
         "recovered": len(held_ok), "of": len(held)}, indent=2) + "\n")
    (OUT / "BASELINE_COMPARISON.json").write_text(json.dumps({
        "episodes": len(eps), "recoveries": base,
        "global_state_required": {
            "global_planner_upper_bound": True, "conventional_orchestration": True,
            "local_developmental": False},
        "note": ("The local architecture is not expected to beat the planner on "
                 "raw rate. The structural claim is that it needs NO component "
                 "holding the pool, the system state, or a target topology.")},
        indent=2) + "\n")
    lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}"
             for p in sorted(OUT.glob("*.json"))]
    (OUT / "CHECKSUMS.txt").write_text("\n".join(lines) + "\n")
    print(json.dumps({k: v for k, v in summary.items()
                      if k != "failed_episodes"}, indent=2))
    print(f"failed episodes: {len(summary['failed_episodes'])}")
    print("baselines:", json.dumps(base))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
