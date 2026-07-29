#!/usr/bin/env python3
"""Taxonomy V2. Evaluator-only. Changes NO runtime behaviour.

V1 had two measurement defects, both found by audit:

  1. It dropped every restored episode (`if restored_ok: continue`), so
     `assigned_damage_not_observed = 5` was the count among FAILURES only.
     Cohort-wide the earlier development summary shows 15 of 48. Some reported
     successes may therefore be episodes where the assigned damage never
     occurred, which means 17/48 was never a clean restoration score.

  2. `bond_settled_supplier_not_produced` was appended once per matching bond
     and tallied per append, so 39 was EDGE OCCURRENCES, not episodes. The
     predicate also scanned every live bond without proving the supplier was
     newly settled, on the active path, or needed for the current result.

V2 therefore reports all 48 episodes, separates episode prevalence from edge
occurrences, and scopes flagged edges to an active repair cone built from TWO
states so that neither error recurs:

  A. the healthy PRE-damage cone (ENV -> settled dependencies -> SINK), which
     is what actually supported the valid result; and
  B. the post-damage obligation cone (victim, its direct consumers, reopened
     slots, replacement edges and their dependants).

Using only post-repair bonds would hide the paths that failed to reform; using
every bond would count idle parallel branches that were never needed.
"""
from __future__ import annotations

import json
import pathlib
import random
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))

from substrate.v5 import ENV, SINK, reset
import fixtures as F
import run_phase3g as R


EDGE_CLASSES = ("replacement_settled_supplier_not_produced",
                "preexisting_active_supplier_not_produced",
                "off_path_idle_bonded_supplier")


def cone_from(organ, produced, roots):
    """Units reachable backwards from `roots` through settled bonds."""
    seen, stack = set(), list(roots)
    while stack:
        uid = stack.pop()
        if uid in seen or uid not in organ.units:
            continue
        seen.add(uid)
        for b in organ.units[uid].bonds.values():
            stack.append(b.supplier)
    return seen


def snapshot_bonds(organ):
    return {(u.unit_id, s): b.supplier
            for u in organ.units.values() for s, b in u.bonds.items()}


def main() -> int:
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                         text=True, cwd=HERE.parents[1]).stdout.strip()
    plan = R.plan({"development"})
    rows = []

    for ep in plan:
        rng = random.Random(ep["seed"])
        organ = F.development(rng)
        F.prepare(organ)
        reset()
        organ.commission()
        healthy = organ.run_item(R.PAYLOAD_A)
        healthy_ok = organ.result_ok(healthy)

        row = {"episode": ep["episode"], "seed": ep["seed"],
               "damage_class": ep["damage_class"], "healthy_formation": healthy_ok}
        if not healthy_ok:
            row.update(assigned_damage_observed=False, semantic_restoration=False,
                       group="formation_failed", terminal_causes=["healthy_formation_failed"])
            rows.append(row)
            continue

        # A. healthy pre-damage cone: what actually supported the valid result
        pre_cone = cone_from(organ, organ._produced, [SINK])
        pre_bonds = snapshot_bonds(organ)

        pool = R.interior_pool(organ, organ._produced)
        if not pool:
            row.update(assigned_damage_observed=False, semantic_restoration=False,
                       group="formation_failed", terminal_causes=["no_interior_carrier"])
            rows.append(row)
            continue
        victim = pool[ep["seed"] % len(pool)]
        consumers = sorted(organ.units[victim].consumers)
        observed, _ = F.inject(organ, victim, ep["damage_class"], rng)

        reset()
        restored = organ.run_item(R.PAYLOAD_B)
        restored_ok = organ.result_ok(restored)
        dmg_ok = bool(observed())
        post_bonds = snapshot_bonds(organ)

        # B. post-damage obligation cone
        obligation_roots = [victim] + consumers + [
            u.unit_id for u in organ.units.values() if u.open_needs]
        post_cone = cone_from(organ, organ._produced, obligation_roots)
        active = (pre_cone | post_cone | {victim} | set(consumers))

        newly = {k: v for k, v in post_bonds.items() if pre_bonds.get(k) != v}
        edges = []
        for (cid, slot), sup in sorted(post_bonds.items()):
            if sup == ENV or sup in organ._produced:
                continue
            s = organ.units.get(sup)
            if s is None or s.dissolved or s.unmet():
                continue
            on_path = cid in active or sup in active
            edges.append({
                "consumer": cid, "slot": slot, "supplier": sup,
                "need_generation": organ.units[cid].bonds[slot].supplier_class,
                "work_item": "B",
                "newly_settled": (cid, slot) in newly,
                "on_active_path": on_path,
                "classification": ("replacement_settled_supplier_not_produced"
                                   if on_path and (cid, slot) in newly else
                                   "preexisting_active_supplier_not_produced"
                                   if on_path else "off_path_idle_bonded_supplier")})

        row.update(
            assigned_damage_observed=dmg_ok, semantic_restoration=restored_ok,
            victim=victim,
            group=("damage_not_observed_but_reported_success" if not dmg_ok and restored_ok
                   else "damage_not_observed_and_failed" if not dmg_ok
                   else "damage_observed_and_restored" if restored_ok
                   else "damage_observed_and_not_restored"),
            edge_occurrences=edges,
            active_path_replacement_idle=[e for e in edges
                if e["classification"] == "replacement_settled_supplier_not_produced"],
            off_path_idle=sum(1 for e in edges
                              if e["classification"] == "off_path_idle_bonded_supplier"))
        rows.append(row)

    groups = {}
    for r in rows:
        groups[r["group"]] = groups.get(r["group"], 0) + 1

    valid = [r for r in rows if r["healthy_formation"] and r["assigned_damage_observed"]]
    valid_restored = [r for r in valid if r["semantic_restoration"]]

    def count(cls, subset=None):
        sub = rows if subset is None else subset
        sel = [e for r in sub for e in r.get("edge_occurrences", [])
               if e["classification"] == cls]
        return {"edge_occurrences": len(sel),
                "episodes": len({r["episode"] for r in sub
                                 if any(e["classification"] == cls
                                        for e in r.get("edge_occurrences", []))}),
                "episodes_of": len(sub),
                "unique_suppliers": len({e["supplier"] for e in sel}),
                "unique_consumers": len({e["consumer"] for e in sel})}

    # A pattern that appears just as often in RESTORED episodes is background,
    # not cause. V1 pooled the two and could not tell the difference.
    restored_rows = [r for r in rows if r.get("semantic_restoration")]
    unrestored_rows = [r for r in rows
                       if r.get("semantic_restoration") is False and r["healthy_formation"]]

    out = {
        "note": "Evaluator-only. No runtime behaviour changed. V1 preserved.",
        "implementation_sha": sha,
        "development_episodes": len(plan),
        "mutually_exclusive_groups": groups,
        "VALID_FORMATION_AND_OBSERVED_DAMAGE_EPISODES": len(valid),
        "VALID_OBSERVED_DAMAGE_RESTORATIONS": len(valid_restored),
        "diagnostic_only": ("This denominator is diagnostic. It does NOT replace "
                            "or alter the preregistered Gate F denominator."),
        "reported_success_without_observed_damage": groups.get(
            "damage_not_observed_but_reported_success", 0),
        "edge_classification": {
            c: count(c) for c in EDGE_CLASSES},
        "edge_classification_by_outcome": {
            c: {"restored_episodes": count(c, restored_rows),
                "unrestored_episodes": count(c, unrestored_rows)}
            for c in EDGE_CLASSES},
        "discriminative_note": (
            "An edge class occurring at a similar episode rate in restored and "
            "unrestored episodes is background, not a terminal cause."),
        "episodes": rows,
    }
    (HERE / "RESTORATION_FAILURE_TAXONOMY_V2.json").write_text(
        json.dumps(out, indent=2) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "episodes"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
