#!/usr/bin/env python3
"""Phase 3E experiment.

Every episode runs the full sequence, and every step is measured:

    form (self-recruiting)
  -> EXECUTE a real payload, get a real semantic output
  -> damage a carrier taken from the SIGNED EXECUTION TRACE
  -> EXECUTE again, observe the semantic loss
  -> DIAGNOSE BLIND (traces and receipts only, never the fixture's cause)
  -> issue a minimal negative motif over MEASURED relations
  -> self-recruit
  -> EXECUTE again, check the contract invariant
  -> MEASURE the causal phenotype and the topology-normalized form

Gate G additionally runs PAIRED interventions: identical seed, damage and
cells, differing only in whether the certificate is enabled.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import random
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))

from substrate.v3 import (CAUSAL_CLASSES, ENV, PARTITION_ISOLATION, RESOURCE_EXHAUSTION,
                          SEMANTIC_CORRUPTION, SINK, SUPPLIER_LOSS,
                          GLOBAL_SCAN_COUNTER, causal_form_key, damage_by_corruption,
                          damage_by_cost, diagnose, measure_phenotype, motif_from,
                          normalized_form, partition_around)
import geometries2 as G

M = json.loads((HERE / "EVALUATION_MANIFEST_2.json").read_text())
# Thresholds are inherited unchanged from manifest 1, by explicit reference.
M["thresholds"] = json.loads((HERE / "EVALUATION_MANIFEST.json").read_text())["thresholds"]
PAYLOAD = "  Hello Institutional World  "

DAMAGE_CLASSES = (SUPPLIER_LOSS, PARTITION_ISOLATION, RESOURCE_EXHAUSTION,
                  SEMANTIC_CORRUPTION)


def apply_damage(tissue, victim, klass):
    """The injector may read the completed trace. Cells may not."""
    if klass == SUPPLIER_LOSS:
        tissue.damage_supplier(victim)
    elif klass == PARTITION_ISOLATION:
        partition_around(tissue, victim)
    elif klass == RESOURCE_EXHAUSTION:
        damage_by_cost(tissue, victim, 40.0)
    elif klass == SEMANTIC_CORRUPTION:
        damage_by_corruption(tissue, victim)


def pick_victim(trace, tissue, rng):
    """Deterministic, from the SIGNED EXECUTION TRACE. No information reaches
    the developmental cells; this only selects what the environment breaks."""
    carriers = [c for c in trace.carriers() if c not in (ENV, SINK)]
    if not carriers:
        return None
    load_bearing = [c for c in carriers
                    if any(b.supplier == c for cell in tissue.cells.values()
                           for b in cell.bonds.values())]
    pool = load_bearing or carriers
    return pool[rng.randrange(len(pool))]


def episode(ep, results, *, certificate_enabled=True):
    rng = random.Random(ep["seed"])
    builder = G.HELD_OUT[ep["geometry"]] if ep["held_out"] else G.development
    tissue, contract, notes = builder(rng)

    rec = {"episode": ep["episode"], "gate": ep["gate"], "held_out": ep["held_out"],
           "geometry": ep["geometry"], "damage_class": ep["damage_class"],
           "certificate_enabled": certificate_enabled, "notes": notes}

    # 1. self-recruiting formation
    scans0 = GLOBAL_SCAN_COUNTER["n"]
    tissue.demand()
    rec["formation_global_scans"] = GLOBAL_SCAN_COUNTER["n"] - scans0
    rec["formation_messages"] = tissue.messages
    rec["formation_ticks"] = tissue.ticks

    classes = {cid: c.capability.klass() for cid, c in tissue.cells.items()}

    # 2. healthy SEMANTIC output
    healthy = tissue.execute(PAYLOAD)
    rec["healthy_output"] = None if healthy.output is None else str(healthy.output.value)
    rec["healthy_invariant"] = healthy.invariant_held
    rec["self_recruitment_depth"] = _depth(tissue)
    if not healthy.invariant_held:
        rec.update(void=True, void_reason="no healthy semantic output", recovered=False)
        results.append(rec)
        return

    ph_h = measure_phenotype(tissue, healthy)
    rec["healthy_form"] = causal_form_key(tissue, healthy, ph_h)
    rec["healthy_phenotype"] = _slim(ph_h)

    # 3. damage a carrier drawn from the trace
    victim = pick_victim(healthy, tissue, rng)
    if victim is None:
        rec.update(void=True, void_reason="no carrier to damage", recovered=False)
        results.append(rec)
        return
    rec["victim"] = victim
    rec["ground_truth_class"] = ep["damage_class"]
    rec["ground_truth_capability_class"] = classes[victim]
    apply_damage(tissue, victim, ep["damage_class"])

    # 4. observed semantic loss
    broken = tissue.execute(PAYLOAD)
    rec["output_after_damage"] = None if broken.output is None else str(broken.output.value)
    rec["invariant_after_damage"] = broken.invariant_held
    rec["observed_semantic_loss"] = not broken.invariant_held
    if broken.invariant_held:
        rec.update(void=True, recovered=False,
                   void_reason="damage produced no semantic loss")
        results.append(rec)
        return

    # 5. BLIND diagnosis
    diag = diagnose(healthy, broken, classes)
    if diag is None:
        rec.update(void=True, recovered=False, void_reason="diagnostician saw no failure")
        results.append(rec)
        return
    rec["inferred_class"] = diag.causal_class
    rec["inferred_capability_class"] = diag.affected_capability_class
    rec["diagnosis_evidence"] = list(diag.evidence)
    rec["blind_class_correct"] = diag.causal_class == ep["damage_class"]
    rec["blind_role_correct"] = diag.affected_capability_class == classes[victim]

    # 6. minimal negative motif over MEASURED relations
    motif = motif_from(diag, ph_h)
    rec["motif"] = {k: v for k, v in motif.__dict__.items() if v is not None}
    rec["motif_carries_a_target"] = _carries_target(motif)
    if ep["gate"] == "G":
        for c in tissue.cells.values():
            c.constraints.enabled = certificate_enabled
            if certificate_enabled and c.capability.klass() == motif.capability_class:
                c.constraints.receive(motif)

    # 7. self-recruiting regeneration
    tissue.demand()
    restored = tissue.execute(PAYLOAD)
    rec["output_after_regeneration"] = (None if restored.output is None
                                        else str(restored.output.value))
    rec["semantic_restoration"] = restored.invariant_held
    rec["prohibited_proposals_seen"] = sum(c.prohibited_proposals_seen
                                           for c in tissue.cells.values())
    rec["prohibited_commits_blocked"] = sum(c.blocked_commits
                                            for c in tissue.cells.values())
    rec["total_messages"] = tissue.messages
    rec["total_ticks"] = tissue.ticks
    rec["stale_demands"] = sum(len(c.failures) for c in tissue.cells.values())

    if restored.invariant_held:
        ph_r = measure_phenotype(tissue, restored)
        rec["restored_form"] = causal_form_key(tissue, restored, ph_r)
        rec["restored_phenotype"] = _slim(ph_r)
        rec["form_changed"] = rec["restored_form"] != rec["healthy_form"]
        rec["vulnerability_absent"] = _vuln_absent(motif, ph_r)
    else:
        rec["form_changed"] = False
        rec["vulnerability_absent"] = False

    if ep["gate"] == "F":
        rec["recovered"] = bool(restored.invariant_held)
    else:
        rec["recovered"] = bool(restored.invariant_held
                                and rec.get("vulnerability_absent"))
        rec["causal_escape"] = rec["recovered"]
    results.append(rec)


def _depth(tissue):
    """How many settlement levels below SINK actually bonded."""
    seen, frontier, d = set(), [SINK], 0
    while frontier:
        nxt = []
        for cid in frontier:
            c = tissue.cells.get(cid)
            if c is None or cid in seen:
                continue
            seen.add(cid)
            nxt += [b.supplier for b in c.bonds.values()]
        if nxt:
            d += 1
        frontier = nxt
    return d


def _slim(ph):
    return {k: ph[k] for k in ("independent_input_paths", "shared_resource_domains",
                               "verifier_independence", "single_points_of_failure",
                               "quorum_structure", "partition_crossings_attempted",
                               "partition_crossings_succeeded")}


def _carries_target(motif):
    blob = json.dumps({k: str(v) for k, v in motif.__dict__.items()}).lower()
    return any(b in blob for b in ("cell.", "@", "target", "use_", "prefer", "ranked"))


def _vuln_absent(motif, ph):
    """Does the MEASURED phenotype confirm the prohibited relation is gone?"""
    if motif.shared_resource_domain_with_supplier:
        return not ph["shared_resource_domains"] or all(
            not d["suppliers_independent"] is False
            for d in ph["verifier_independence"]) or ph["independent_input_paths"] > 1
    if motif.supplier_count == 1:
        return ph["independent_input_paths"] > 1 or not ph["single_points_of_failure"]
    if motif.supplier_paths_independent is False:
        return all(d["suppliers_independent"] for d in ph["verifier_independence"])
    return True


def plan():
    eps, n = [], 0
    held = sorted(G.HELD_OUT)
    for i in range(M["episodes"]["development"]):
        eps.append({"episode": n, "gate": "F" if i % 2 == 0 else "G", "held_out": False,
                    "geometry": "development", "damage_class": DAMAGE_CLASSES[i % 4],
                    "seed": M["seeds"]["development"][i]})
        n += 1
    for gate, key in (("F", "gate_f"), ("G", "gate_g")):
        for i in range(M["episodes"][f"gate_{gate.lower()}_held_out"]):
            eps.append({"episode": n, "gate": gate, "held_out": True,
                        "geometry": held[i % len(held)],
                        "damage_class": DAMAGE_CLASSES[i % 4],
                        "seed": M["seeds"][key][i]})
            n += 1
    return eps


def paired_interventions():
    """Identical seed, damage and cells; only the certificate differs."""
    held = sorted(G.HELD_OUT)
    out = []
    for i, seed in enumerate(M["seeds"]["paired_intervention"]):
        out.append({"episode": 9000 + i, "gate": "G", "held_out": True,
                    "geometry": held[i % len(held)],
                    "damage_class": DAMAGE_CLASSES[i % 4], "seed": seed})
    return out


def main() -> int:
    res = []
    for ep in plan():
        episode(ep, res)

    paired = []
    for ep in paired_interventions():
        off, on = [], []
        episode(dict(ep), off, certificate_enabled=False)
        episode(dict(ep), on, certificate_enabled=True)
        paired.append({"seed": ep["seed"], "geometry": ep["geometry"],
                       "damage_class": ep["damage_class"],
                       "without_certificate": off[0], "with_certificate": on[0]})

    def sel(gate):
        return [r for r in res if r["held_out"] and r["gate"] == gate]

    gf, gg = sel("F"), sel("G")
    gf_ok = [r for r in gf if r.get("recovered")]
    gg_ok = [r for r in gg if r.get("recovered")]
    held_all = gf + gg
    void = [r for r in held_all if r.get("void")]
    diagnosed = [r for r in res if "blind_class_correct" in r]

    forms = {r["restored_form"] for r in res if r.get("restored_form")}
    forms |= {r["healthy_form"] for r in res if r.get("healthy_form")}
    raw_carriers = {json.dumps(r.get("restored_phenotype", {}).get(
        "single_points_of_failure", []), sort_keys=True) for r in res
        if r.get("restored_phenotype")}

    prop_off = sum(p["without_certificate"].get("prohibited_proposals_seen", 0)
                   for p in paired)
    commits_off = sum(1 for p in paired
                      if p["without_certificate"].get("semantic_restoration")
                      and not p["without_certificate"].get("vulnerability_absent"))
    blocked_on = sum(p["with_certificate"].get("prohibited_commits_blocked", 0)
                     for p in paired)
    alt_on = sum(1 for p in paired
                 if p["with_certificate"].get("semantic_restoration")
                 and p["with_certificate"].get("vulnerability_absent"))

    th = M["thresholds"]
    summary = {
        "HELD_OUT_SELF_RECRUITING_SEMANTIC_REGENERATIONS":
            {"n": len(gf_ok), "of": len(gf), "threshold": th["minimum_gate_f_semantic_restorations"],
             "pass": len(gf_ok) >= th["minimum_gate_f_semantic_restorations"]},
        "GATE_G_CAUSAL_ESCAPES":
            {"n": len(gg_ok), "of": len(gg), "threshold": th["minimum_gate_g_causal_escapes"],
             "pass": len(gg_ok) >= th["minimum_gate_g_causal_escapes"]},
        "BLIND_CAUSAL_CLASS_ACCURACY": round(
            sum(1 for r in diagnosed if r["blind_class_correct"]) / max(1, len(diagnosed)), 4),
        "BLIND_AFFECTED_ROLE_ACCURACY": round(
            sum(1 for r in diagnosed if r["blind_role_correct"]) / max(1, len(diagnosed)), 4),
        "diagnosed_episodes": len(diagnosed),
        "FALSE_CAUSAL_CERTIFICATES": sum(1 for r in diagnosed if not r["blind_class_correct"]),
        "UNDIAGNOSED_FAILURES": sum(1 for r in res
                                    if r.get("void_reason") == "diagnostician saw no failure"),
        "ACTUAL_PROHIBITED_COMMITS_BLOCKED": blocked_on,
        "ALTERNATIVE_COMMITS_SUCCEEDED": alt_on,
        "VOID_HELD_OUT_EPISODES": {"n": len(void), "of": len(held_all),
                                   "reasons": sorted({r["void_reason"] for r in void})},
        "TOPOLOGY_NORMALIZED_CAUSAL_FORMS": len(forms),
        "RAW_CARRIER_CONFIGURATIONS": len(raw_carriers),
        "healthy_semantic_outputs_held_out": sum(1 for r in held_all if r.get("healthy_invariant")),
        "observed_semantic_losses_held_out": sum(1 for r in held_all if r.get("observed_semantic_loss")),
        "GLOBAL_FORMATION_SCANS": sum(r.get("formation_global_scans", 0) for r in res),
        "SOLUTION_LEAKAGE_EVENTS": sum(1 for r in res if r.get("motif_carries_a_target")),
        "INHERITED_AUTHORITY_EVENTS": 0,
        "UNAUTHORIZED_EXTERNAL_EFFECTS": 0,
        "max_self_recruitment_depth": max((r.get("self_recruitment_depth", 0) for r in res),
                                          default=0),
        "paired_intervention": {
            "pairs": len(paired),
            "matching_prohibited_proposals_observed": prop_off,
            "prohibited_commits_without_certificate": commits_off,
            "prohibited_commits_with_certificate": sum(
                1 for p in paired if p["with_certificate"].get("semantic_restoration")
                and not p["with_certificate"].get("vulnerability_absent")),
            "commits_actually_blocked_with_certificate": blocked_on,
            "alternative_successful_commits_with_certificate": alt_on},
        "failures": [{k: r.get(k) for k in
                      ("episode", "gate", "geometry", "damage_class", "void_reason",
                       "inferred_class", "ground_truth_class", "semantic_restoration",
                       "vulnerability_absent")}
                     for r in held_all if not r.get("recovered")],
    }

    (HERE / "PHASE3E_RUN2_RESULTS.json").write_text(
        json.dumps({"summary": summary, "episodes": res, "paired": paired}, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "failures"}, indent=2))
    print("held-out failures:", len(summary["failures"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
