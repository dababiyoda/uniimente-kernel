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

from substrate.v5 import ENV, SINK, C, reset
import evaluator as EV
import fixtures as F
import run_phase3g as R


LIFECYCLE = ("consumer_gone", "no_reopen_detected", "reopened_but_no_need_sent",
             "need_created_no_search_state", "need_sent_no_offer_received",
             "offer_received_never_settled", "settled_supplier_never_produced",
             "supplier_produced_consumer_idle", "consumer_resumed_sink_not_reached",
             "sink_reached_invariant_failed", "no_break_restored")


def first_lifecycle_break(organ, produced, victim, target_edges, restored_ok):
    """The FIRST stage that did not complete FOR THE OBLIGATION THE DAMAGE MADE.

    `target_edges` are the (consumer, slot) pairs that were bonded to the victim
    in the healthy run. Those, and only those, are the slots the damage forced
    open. An earlier version of this function scanned every reopened unit in the
    organ and reported `offer_received_never_settled` for 20 of 23 unrestored
    episodes -- and also for 16 of 18 RESTORED ones, because an unrelated
    leftover search elsewhere is not the repair that mattered. That is V1's
    scoping error in a new place, so the scope is now the damage's own cone.
    """
    stages = []
    for cid, slot in target_edges:
        u = organ.units.get(cid)
        if u is None:
            stages.append(("consumer_gone", {"consumer": cid, "slot": slot}))
            continue
        d = {"consumer": cid, "slot": slot}
        if not any(e.get("slot") == slot for e in u.refusal_evidence):
            stages.append(("no_reopen_detected", d))
            continue
        b = u.bonds.get(slot)
        resettled = b is not None and b.supplier != victim
        nid = u.open_needs.get(slot)
        st = u._search.get(nid) if nid else None
        if not resettled:
            if nid is None:
                stages.append(("reopened_but_no_need_sent", d))
                continue
            if st is None:
                stages.append(("need_created_no_search_state", dict(d, need=nid)))
                continue
            d.update(need=nid, credits=round(st.get("credits", 0.0), 1),
                     round=st.get("round", 0), tried=len(st.get("tried", ())),
                     offers=st.get("offers", 0), rejected=dict(st.get("rejected", {})))
            stages.append((("need_sent_no_offer_received" if not st.get("offers")
                            else "offer_received_never_settled"), d))
            continue
        d.update(replacement=b.supplier, settled_by=b.settled_by,
                 settled_item=b.settled_item)
        if b.supplier not in produced:
            s = organ.units.get(b.supplier)
            d["replacement_unmet"] = bool(s is not None and s.unmet())
            d["replacement_dissolved"] = bool(s is not None and s.dissolved)
            stages.append(("settled_supplier_never_produced", d))
        elif cid not in produced:
            stages.append(("supplier_produced_consumer_idle", d))
        elif SINK not in produced:
            stages.append(("consumer_resumed_sink_not_reached", d))
        elif not restored_ok:
            stages.append(("sink_reached_invariant_failed", d))
        else:
            stages.append(("no_break_restored", d))
    if not stages:
        return "no_target_edge_identified", {}
    order = {k: i for i, k in enumerate(LIFECYCLE)}
    stages.sort(key=lambda s: order.get(s[0], len(LIFECYCLE)))
    return stages[0][0], {"targets": len(stages), "earliest": stages[0][1],
                          "all_stages": [s[0] for s in stages]}


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
    """Full edge identity, not just supplier name.

    V1 appended `b.supplier` to a list, so episode 27 showed `reconcile.10`
    twice with no way to tell distinct legitimate edges from a re-settlement in
    a later work item or from duplicate instrumentation. Keying by consumer +
    slot + supplier + need generation + work-item generation separates all
    three. `(consumer, slot)` is unique per snapshot because bonds are a dict
    keyed by slot, so a repeated supplier is necessarily a different consumer
    or a different slot -- never the same edge counted twice.
    """
    return {(u.unit_id, s): (b.supplier, b.settled_by, b.settled_item)
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

        # Pre-repair semantic loss, proved on an independent twin exactly as the
        # scored harness does it. Zero shared mutable state with this organ.
        loss_proven = R._twin_pre_repair_loss(ep, victim)

        reset()
        restored = organ.run_item(R.PAYLOAD_B)
        snap = C.snapshot()
        restored_ok = organ.result_ok(restored)
        dmg_ok = bool(observed())
        post_bonds = snapshot_bonds(organ)
        repair_item = organ.item_seq        # the work item repair ran during

        # B. post-damage obligation cone
        obligation_roots = [victim] + consumers + [
            u.unit_id for u in organ.units.values() if u.open_needs]
        post_cone = cone_from(organ, organ._produced, obligation_roots)
        active = (pre_cone | post_cone | {victim} | set(consumers))

        newly = {k for k, v in post_bonds.items() if pre_bonds.get(k) != v}
        # Any settlement at all during the repair work item, whether or not it
        # ended up flagged. This is the direct test of "did the repair rebind?"
        settled_in_repair = sorted(
            f"{cid}[{slot}]<-{v[0]}" for (cid, slot), v in post_bonds.items()
            if v[2] == repair_item)

        edges, seen_keys = [], {}
        for (cid, slot), (sup, gen, item) in sorted(post_bonds.items()):
            if sup == ENV or sup in organ._produced:
                continue
            s = organ.units.get(sup)
            if s is None or s.dissolved or s.unmet():
                continue
            on_path = cid in active or sup in active
            key = (cid, slot, sup, gen, item)
            seen_keys[key] = seen_keys.get(key, 0) + 1
            edges.append({
                "edge_key": f"{cid}|{slot}|{sup}|{gen or '-'}|item{item}",
                "consumer": cid, "slot": slot, "supplier": sup,
                "need_generation": gen or None,
                "work_item_generation": item,
                "settled_during_repair": item == repair_item,
                "newly_settled": (cid, slot) in newly,
                "on_active_path": on_path,
                "classification": ("replacement_settled_supplier_not_produced"
                                   if on_path and (cid, slot) in newly else
                                   "preexisting_active_supplier_not_produced"
                                   if on_path else "off_path_idle_bonded_supplier")})
        dup_candidates = [f"{k}" for k, n in seen_keys.items() if n > 1]

        acts = snap["EVENT_DRIVEN_LOCAL_ACTIVATIONS"]
        # The slots the damage forced open: those bonded to the victim while healthy.
        target_edges = sorted(k for k, v in pre_bonds.items() if v[0] == victim)
        brk, brk_detail = first_lifecycle_break(
            organ, organ._produced, victim, target_edges, restored_ok)
        invalid = []
        if not dmg_ok:
            invalid.append("assigned_damage_never_occurred")
        if not loss_proven:
            invalid.append("no_pre_repair_semantic_loss")
        row.update(
            assigned_damage_observed=dmg_ok,
            semantic_loss_proven=loss_proven,
            event_driven_local_activation=acts > 0,
            event_driven_local_activations=acts,
            replacement_settlement_occurred=bool(settled_in_repair),
            replacement_settlements=settled_in_repair,
            semantic_restoration=restored_ok,
            # The preregistered qualifying predicate, evaluated by the same
            # evaluator the harness uses. Not recomputed by hand here.
            qualified=EV.qualifies({
                "semantic_loss": loss_proven,
                "local_evidence_at_direct_consumer": bool(
                    organ.units[victim].consumers or consumers),
                "event_driven_local_activations": acts,
                "boundary_triggered_repair_events":
                    snap["BOUNDARY_TRIGGERED_REPAIR_EVENTS"],
                "supervisor_restart_events": snap["SUPERVISOR_RESTART_EVENTS"],
                "whole_organ_review_passes": snap["WHOLE_ORGAN_REVIEW_PASSES"],
                "developmental_provider_index_reads":
                    snap["FULL_PROVIDER_INDEX_READS"],
                "over_refusal": EV.over_refusal(organ),
                "semantic_restoration": restored_ok}),
            invalidity_reasons=invalid,
            first_lifecycle_break=brk,
            first_lifecycle_break_detail=brk_detail,
            victim=victim,
            group=("damage_not_observed_but_reported_success" if not dmg_ok and restored_ok
                   else "damage_not_observed_and_failed" if not dmg_ok
                   else "damage_observed_and_restored" if restored_ok
                   else "damage_observed_and_not_restored"),
            edge_occurrences=edges,
            duplicate_instrumentation_candidates=dup_candidates,
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
        "VALID_OBSERVED_DAMAGE_QUALIFYING": sum(1 for r in valid if r.get("qualified")),
        "replacement_settlement_occurred": {
            "episodes": sum(1 for r in rows if r.get("replacement_settlement_occurred")),
            "of_post_formation": sum(1 for r in rows if r["healthy_formation"]),
            "among_restored": sum(1 for r in restored_rows
                                  if r.get("replacement_settlement_occurred")),
            "among_unrestored": sum(1 for r in unrestored_rows
                                    if r.get("replacement_settlement_occurred"))},
        "duplicate_instrumentation_candidates": sum(
            len(r.get("duplicate_instrumentation_candidates", [])) for r in rows),
        "FIRST_LIFECYCLE_BREAK_unrestored": {
            k: sum(1 for r in unrestored_rows if r.get("first_lifecycle_break") == k)
            for k in sorted({r.get("first_lifecycle_break") for r in unrestored_rows})},
        "FIRST_LIFECYCLE_BREAK_restored": {
            k: sum(1 for r in restored_rows if r.get("first_lifecycle_break") == k)
            for k in sorted({r.get("first_lifecycle_break") for r in restored_rows})},
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
