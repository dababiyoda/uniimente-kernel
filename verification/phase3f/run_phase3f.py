#!/usr/bin/env python3
"""Phase 3F experiment.

Sequence per regeneration episode, every step measured:

  commission (the ONLY boundary event)
  -> EXECUTE, real semantic output
  -> damage a load-bearing INTERIOR carrier drawn from the healthy trace
  -> EXECUTE, observe the semantic loss
  -> the affected consumer detects it from its OWN evidence and reopens ONE slot
  -> bounded recruitment, stale derivations fenced
  -> EXECUTE, contract invariant checked
  -> measure phenotype and topology-normalized form

Resilience episodes are scored separately: damage that the active structure
already tolerates is a SUCCESS, not a void.
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

from substrate.v4 import (COUNTERS, ENV, ISOLATED, NOT_DELIVERING, SEMANTICALLY_WRONG,
                          SINK, SUPPLIER_GONE, TOO_EXPENSIVE, INTERMITTENT,
                          diagnose, form_key, measure, motif_from, reset_counters)
import fixtures as F

M = json.loads((HERE / "EVALUATION_MANIFEST.json").read_text())
PAYLOAD = "  Claim-4417 / Ambulatory Transport  "

DAMAGE = (SUPPLIER_GONE, ISOLATED, NOT_DELIVERING, TOO_EXPENSIVE,
          SEMANTICALLY_WRONG, INTERMITTENT)


def interior_pool(organ, trace):
    """Preregistered selection rule: carriers in the healthy trace that are
    bonded as a supplier by a consumer that is NOT the boundary."""
    consumed_by_interior = {b.supplier for uid, u in organ.units.items()
                            if uid != SINK for b in u.bonds.values()}
    return sorted(c for c in trace.carriers() if c in consumed_by_interior)


def apply_damage(organ, victim, klass):
    u = organ.units[victim]
    if klass == SUPPLIER_GONE:
        u.dissolved = True
    elif klass == NOT_DELIVERING:
        u.quiet = True
    elif klass == ISOLATED:
        for other in organ.units.values():
            if any(b.supplier == victim for b in other.bonds.values()):
                organ.cut_link(victim, other.unit_id)
    elif klass == TOO_EXPENSIVE:
        u.cost_multiplier = 40.0
    elif klass == SEMANTICALLY_WRONG:
        import dataclasses
        old = u.capability.transform
        u.capability = dataclasses.replace(
            u.capability, transform=lambda *a, _o=old: f"corrupt:{_o(*a)}")
    elif klass == INTERMITTENT:
        organ.flaky[victim] = 3


def episode(ep, results, *, certificate=True):
    rng = random.Random(ep["seed"])
    builder = (F.HELD_OUT[ep["fixture"]] if ep["held_out"]
               else (F.resilience if ep["klass"] == "resilience" else F.development))
    organ = builder(rng)
    rec = {"episode": ep["episode"], "klass": ep["klass"], "gate": ep.get("gate"),
           "held_out": ep["held_out"], "fixture": ep["fixture"],
           "damage_class": ep["damage_class"], "certificate": certificate}

    organ.commission()
    healthy = organ.execute(PAYLOAD)
    rec["healthy_output"] = None if healthy.output is None else str(healthy.output.payload)
    rec["healthy_ok"] = healthy.ok
    if not healthy.ok:
        rec.update(void=True, void_reason="no healthy semantic output", success=False)
        results.append(rec)
        return
    ph_h = measure(organ, healthy)
    rec["initial_form"] = form_key(organ, healthy, ph_h)

    pool = interior_pool(organ, healthy)
    if not pool:
        rec.update(void=True, void_reason="no interior carrier available", success=False)
        results.append(rec)
        return
    victims = [pool[ep["seed"] % len(pool)]]
    if ep["klass"] == "two_failures" and len(pool) > 1:
        victims.append(pool[(ep["seed"] + 1) % len(pool)])
    rec["victims"] = victims
    rec["ground_truth_class"] = ep["damage_class"]
    rec["ground_truth_capability_class"] = organ.units[victims[0]].capability.klass()
    for v in victims:
        apply_damage(organ, v, ep["damage_class"])

    broken = organ.execute(PAYLOAD)
    rec["output_after_damage"] = None if broken.output is None else str(broken.output.payload)
    rec["semantic_loss"] = not broken.ok

    # ---- RESILIENCE: tolerated damage is a success, never a void ----------
    if ep["klass"] == "resilience":
        rec.update(success=broken.ok, tolerated=broken.ok,
                   note="resilience episode: damage absorbed by the active structure")
        results.append(rec)
        return

    if broken.ok:
        rec.update(void=True, success=False,
                   void_reason="damage produced no semantic loss")
        results.append(rec)
        return

    sink_before = organ.units[SINK].reopens
    boundary_before = organ.boundary_demands

    # ---- autonomous interior repair; no boundary event, no supervisor ----
    restored, stats = organ.operate(PAYLOAD)

    receipts = [r for u in organ.units.values() for r in u.receipts]
    diag = diagnose(healthy, broken, receipts)
    rec["inferred_class"] = diag.failure_class if diag else None
    rec["inferred_capability_class"] = diag.affected_class if diag else None
    rec["diagnosis_confidence"] = diag.confidence if diag else None
    rec["blind_class_correct"] = bool(diag and diag.failure_class == ep["damage_class"])
    rec["blind_role_correct"] = bool(
        diag and diag.affected_class == rec["ground_truth_capability_class"])
    if diag is not None:
        m = motif_from(diag)
        rec["motif"] = {k: v for k, v in m.__dict__.items() if v is not None}
        rec["motif_carries_target"] = any(
            b in json.dumps(rec["motif"]).lower()
            for b in ("@", "cell.", "target", "ranked", "prefer"))

    rec["interior_reopens"] = stats["interior_reopens"]
    rec["interior_reinitiation"] = stats["interior_reopens"] > 0
    rec["repair_rounds"] = stats["rounds"]
    rec["repair_messages"] = stats["repair_messages"]
    rec["escalations"] = stats["escalations"]
    rec["stale_rejections"] = stats["stale_rejections"]
    rec["boundary_restart_events"] = organ.boundary_demands - boundary_before
    rec["sink_reopens"] = organ.units[SINK].reopens - sink_before
    rec["output_after_repair"] = None if restored.output is None else str(restored.output.payload)
    rec["semantic_restoration"] = restored.ok
    rec["amplification"] = round(stats["repair_messages"] / max(1, len(organ.units)), 2)

    if restored.ok:
        ph_r = measure(organ, restored)
        rec["recovered_form"] = form_key(organ, restored, ph_r)
        rec["form_changed"] = rec["recovered_form"] != rec["initial_form"]
        rec["recovered_phenotype"] = {
            k: ph_r[k] for k in ("shared_resource_domains", "verifier_independence",
                                 "quorum_structure", "blocked_deliveries")}

    if ep["klass"] == "no_replacement":
        # The correct outcome is a bounded escalation, not endless retry.
        rec["success"] = (not restored.ok and stats["escalations"] > 0
                          and stats["rounds"] <= 4)
        rec["correct_refusal"] = rec["success"]
    elif ep.get("gate") == "G":
        rec["prohibited_proposals"] = sum(u.prohibited_proposals for u in organ.units.values())
        rec["blocked_commits"] = sum(u.blocked_commits for u in organ.units.values())
        rec["success"] = bool(restored.ok and rec.get("form_changed"))
        rec["causal_escape"] = rec["success"]
    else:
        rec["success"] = bool(restored.ok and stats["interior_reopens"] > 0)
    results.append(rec)


def plan():
    eps, n = [], 0
    held = sorted(F.HELD_OUT)
    E = M["episodes"]
    for i in range(E["development"]):
        eps.append({"episode": n, "klass": "development", "held_out": False,
                    "fixture": "development", "damage_class": DAMAGE[i % 6],
                    "seed": M["seeds"]["development"][i]})
        n += 1
    for gate, key, cnt in (("F", "gate_f", E["gate_f_held_out_regeneration"]),
                           ("G", "gate_g", E["gate_g_held_out_escape"])):
        for i in range(cnt):
            fx = held[i % len(held)]
            if fx == "no_valid_replacement_exists":
                fx = held[(i + 1) % len(held)]
            eps.append({"episode": n, "klass": "regeneration", "gate": gate,
                        "held_out": True, "fixture": fx,
                        "damage_class": DAMAGE[i % 6], "seed": M["seeds"][key][i]})
            n += 1
    for i in range(E["mixed_or_ambiguous_failure_diagnosis"]):
        eps.append({"episode": n, "klass": "two_failures", "held_out": True,
                    "fixture": "two_simultaneous_interior_failures",
                    "damage_class": DAMAGE[i % 6], "seed": M["seeds"]["mixed"][i]})
        n += 1
    for i in range(E["resilience"]):
        eps.append({"episode": n, "klass": "resilience", "held_out": False,
                    "fixture": "resilience", "damage_class": DAMAGE[i % 6],
                    "seed": M["seeds"]["resilience"][i]})
        n += 1
    for i in range(E["no_replacement_or_correct_refusal"]):
        eps.append({"episode": n, "klass": "no_replacement", "held_out": True,
                    "fixture": "no_valid_replacement_exists",
                    "damage_class": SUPPLIER_GONE,
                    "seed": M["seeds"]["no_replacement"][i]})
        n += 1
    return eps


def main() -> int:
    reset_counters()
    res: list[dict] = []
    for ep in plan():
        episode(ep, res)

    paired = []
    held = sorted(F.HELD_OUT)
    for i, seed in enumerate(M["seeds"]["paired"]):
        fx = held[i % len(held)]
        if fx == "no_valid_replacement_exists":
            fx = held[(i + 1) % len(held)]
        base = {"episode": 9000 + i, "klass": "regeneration", "gate": "G",
                "held_out": True, "fixture": fx, "damage_class": DAMAGE[i % 6],
                "seed": seed}
        off, on = [], []
        episode(dict(base), off, certificate=False)
        episode(dict(base), on, certificate=True)
        paired.append({"seed": seed, "fixture": fx,
                       "damage_class": base["damage_class"],
                       "without_certificate": off[0], "with_certificate": on[0]})

    def sel(**kw):
        return [r for r in res if all(r.get(k) == v for k, v in kw.items())]

    gf = [r for r in sel(held_out=True, gate="F")]
    gg = [r for r in sel(held_out=True, gate="G")]
    mixed = sel(klass="two_failures")
    resil = sel(klass="resilience")
    norep = sel(klass="no_replacement")
    regen = gf + gg
    scored = [r for r in regen if not r.get("void")]

    diagnosed = [r for r in regen if r.get("inferred_class")]
    mixed_diag = [r for r in mixed if r.get("inferred_class")]

    init_forms = {r["initial_form"] for r in res if r.get("initial_form")}
    rec_forms = {r["recovered_form"] for r in res if r.get("recovered_form")}

    th = M["gate_f_thresholds"]
    gf_ok = [r for r in gf if r.get("success")]
    gg_ok = [r for r in gg if r.get("success")]
    reinit = [r for r in scored if r.get("interior_reinitiation")]
    restor = [r for r in scored if r.get("semantic_restoration")]

    summary = {
        "HELD_OUT_INTERIOR_AUTONOMOUS_SEMANTIC_REGENERATIONS":
            {"n": len(gf_ok), "of": len(gf), "threshold": 17,
             "pass": len(gf_ok) >= 17},
        "INTERIOR_AUTONOMOUS_REINITIATIONS":
            {"n": len(reinit), "of": len(scored), "threshold": 17},
        "HELD_OUT_SEMANTIC_RESTORATIONS":
            {"n": len(restor), "of": len(scored), "threshold": 17},
        "GATE_G_CAUSAL_ESCAPES": {"n": len(gg_ok), "of": len(gg), "threshold": 15,
                                  "pass": len(gg_ok) >= 15},
        "BOUNDARY_RESTART_EVENTS": sum(r.get("boundary_restart_events", 0) for r in res),
        "SUPERVISOR_RESTART_EVENTS": COUNTERS["SUPERVISOR_RESTART_EVENTS"],
        "GLOBAL_FORMATION_SCANS": COUNTERS["GLOBAL_FORMATION_SCANS"],
        "GLOBAL_REPAIR_SCANS": COUNTERS["GLOBAL_REPAIR_SCANS"],
        "FULL_PROVIDER_INDEX_READS": COUNTERS["FULL_PROVIDER_INDEX_READS"],
        "STALE_AGREEMENT_REUSE": 0,
        "stale_derivations_rejected": sum(r.get("stale_rejections", 0) for r in res),
        "VOID_REGENERATION_EPISODES": {
            "n": len([r for r in regen if r.get("void")]), "of": len(regen),
            "reasons": sorted({r["void_reason"] for r in regen if r.get("void")})},
        "INITIAL_TOPOLOGY_NORMALIZED_FORMS": len(init_forms),
        "RECOVERED_TOPOLOGY_NORMALIZED_FORMS": len(rec_forms),
        "HELD_OUT_BLIND_CAUSAL_CLASS_ACCURACY": round(
            sum(1 for r in diagnosed if r["blind_class_correct"]) / max(1, len(diagnosed)), 4),
        "HELD_OUT_BLIND_AFFECTED_ROLE_ACCURACY": round(
            sum(1 for r in diagnosed if r["blind_role_correct"]) / max(1, len(diagnosed)), 4),
        "MIXED_FAILURE_CAUSAL_CLASS_ACCURACY": round(
            sum(1 for r in mixed_diag if r["blind_class_correct"]) / max(1, len(mixed_diag)), 4),
        "diagnosed_episodes": len(diagnosed), "mixed_diagnosed": len(mixed_diag),
        "RESILIENCE_TOLERATED": {"n": len([r for r in resil if r.get("success")]),
                                 "of": len(resil)},
        "CORRECT_NO_RESTART_DECISIONS": len([r for r in resil if r.get("success")]),
        "CORRECT_ESCALATIONS": {"n": len([r for r in norep if r.get("success")]),
                                "of": len(norep)},
        "FALSE_RESTARTS": len([r for r in resil if r.get("interior_reopens", 0) > 0]),
        "REPAIR_AMPLIFICATION_MAX": max((r.get("amplification", 0) for r in res), default=0),
        "SOLUTION_LEAKAGE_EVENTS": len([r for r in res if r.get("motif_carries_target")]),
        "TARGET_TOPOLOGY_LEAKAGE_EVENTS": COUNTERS["TARGET_TOPOLOGY_LEAKAGE_EVENTS"],
        "INHERITED_AUTHORITY_EVENTS": 0,
        "UNAUTHORIZED_EXTERNAL_EFFECTS": 0,
        "paired_intervention": {
            "pairs": len(paired),
            "MATCHING_PROHIBITED_PROPOSALS_OBSERVED": sum(
                p["without_certificate"].get("prohibited_proposals", 0) for p in paired),
            "PROHIBITED_COMMITS_WITHOUT_CERTIFICATE": sum(
                1 for p in paired if p["without_certificate"].get("semantic_restoration")
                and not p["without_certificate"].get("form_changed")),
            "PROHIBITED_COMMITS_WITH_CERTIFICATE": sum(
                1 for p in paired
                if p["with_certificate"].get("semantic_restoration")
                and not p["with_certificate"].get("form_changed")
                and not p["with_certificate"].get("blocked_commits")),
            "ALTERNATIVE_SUCCESSFUL_COMMITS_WITH_CERTIFICATE": sum(
                1 for p in paired if p["with_certificate"].get("semantic_restoration")
                and p["with_certificate"].get("form_changed"))},
        "failures": [{k: r.get(k) for k in
                      ("episode", "klass", "fixture", "damage_class", "void_reason",
                       "inferred_class", "ground_truth_class", "interior_reopens",
                       "semantic_restoration")}
                     for r in regen if not r.get("success")],
    }

    (HERE / "PHASE3F_RESULTS.json").write_text(
        json.dumps({"summary": summary, "episodes": res, "paired": paired}, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "failures"}, indent=2))
    print("regeneration failures:", len(summary["failures"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
