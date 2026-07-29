#!/usr/bin/env python3
"""Evaluator-only terminal-state classification for the development cohort.

Changes NO runtime behaviour. It re-runs each development episode with the same
seeds and the same mechanism, then classifies the terminal state from state,
receipts, search records, produced values and message evidence.

The classification never reads the fixture name or the hidden damage label.
Episode 0 alone must not drive a mechanism change; this is what tells us
whether search stalling dominates or the architecture has several bottlenecks.
"""
from __future__ import annotations

import json
import pathlib
import random
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))

from substrate.v5 import ENV, SINK, C, reset
import fixtures as F
import run_phase3g as R

CAUSES = (
    "healthy_formation_failed", "assigned_damage_not_observed",
    "search_stalled_with_unspent_credit", "search_budget_exhausted",
    "no_eligible_frontier", "no_valid_provider_exists",
    "offer_rejected_nonfirm", "offer_rejected_stale", "offer_rejected_cooldown",
    "offer_rejected_prohibition", "offer_rejected_duplicate_supplier",
    "bond_settled_supplier_not_produced", "supplier_produced_consumer_not_resumed",
    "consumer_resumed_downstream_not_completed",
    "sink_produced_semantic_invariant_failed", "over_refusal",
    "repair_budget_exhausted", "unknown_terminal_state",
)


def classify(organ, produced, healthy_ok, damage_observed, restored_ok):
    """Terminal causes, derived from evidence only."""
    causes, detail = [], {}
    if not healthy_ok:
        return ["healthy_formation_failed"], detail
    if not damage_observed:
        causes.append("assigned_damage_not_observed")
    if restored_ok:
        return causes, detail

    open_units = [u for u in organ.units.values()
                  if not u.dissolved and u.open_needs and u.unit_id != ENV]
    rej = {}
    for u in organ.units.values():
        for st in u._search.values():
            for k, v in st.get("rejected", {}).items():
                rej[k] = rej.get(k, 0) + v
    for r in (rr for u in organ.units.values() for rr in u.receipts):
        if r.kind == "stale_rejected":
            rej["stale"] = rej.get("stale", 0) + 1
        elif r.kind == "cooldown":
            rej["cooldown"] = rej.get("cooldown", 0) + 1
        elif r.kind == "commit_blocked":
            rej["prohibition"] = rej.get("prohibition", 0) + 1
    detail["offers_rejected"] = rej
    for key, cause in (("nonfirm", "offer_rejected_nonfirm"),
                       ("stale", "offer_rejected_stale"),
                       ("cooldown", "offer_rejected_cooldown"),
                       ("prohibition", "offer_rejected_prohibition")):
        if rej.get(key):
            causes.append(cause)

    stalled = exhausted = no_frontier = 0
    credits_left = 0.0
    rounds = 0
    for u in open_units:
        for nid, st in u._search.items():
            if st.get("settled"):
                continue
            rounds = max(rounds, st.get("round", 0))
            c = st.get("credits", 0.0)
            credits_left += c
            want = None
            for slot, n in u.open_needs.items():
                if n == nid:
                    want = u.capability.accepts[slot]
            eligible = [n for n in u.neighbours
                        if n not in st.get("tried", set()) and n not in u.refused]
            if c > 0 and st.get("offers", 0) == 0 and eligible:
                stalled += 1
            elif c > 0 and not eligible:
                no_frontier += 1
            elif c <= 0:
                exhausted += 1
    detail.update(open_needs=len(open_units), credits_remaining=round(credits_left, 1),
                  max_round=rounds)
    if stalled:
        causes.append("search_stalled_with_unspent_credit")
        detail["stalled_needs"] = stalled
    if exhausted:
        causes.append("search_budget_exhausted")
    if no_frontier:
        causes.append("no_eligible_frontier")

    # Did any producer of a still-required type exist at all, anywhere?
    for u in open_units:
        for slot in u.open_needs:
            want = u.capability.accepts[slot]
            others = [x for x in organ.units.values()
                      if x.capability.produces == want and not x.dissolved
                      and x.unit_id != u.unit_id]
            if not others:
                causes.append("no_valid_provider_exists")
                break

    # Settled but the supplier produced nothing this item.
    for u in organ.units.values():
        if u.dissolved:
            continue
        for b in u.bonds.values():
            if b.supplier not in produced and b.supplier != ENV:
                sup = organ.units.get(b.supplier)
                if sup is not None and not sup.dissolved and not sup.unmet():
                    causes.append("bond_settled_supplier_not_produced")
                    detail.setdefault("settled_not_produced", []).append(b.supplier)
                    break

    # A consumer whose suppliers all produced, that did not itself produce.
    for u in organ.units.values():
        if u.dissolved or u.unit_id in produced or u.unmet() or u.unit_id == ENV:
            continue
        if all(b.supplier in produced or b.supplier == ENV for b in u.bonds.values()):
            causes.append("supplier_produced_consumer_not_resumed")
            detail.setdefault("not_resumed", []).append(u.unit_id)
            break

    if SINK in produced:
        causes.append("sink_produced_semantic_invariant_failed")
    elif any(u.unit_id in produced for u in organ.units.values()
             if u.capability.produces == organ.contract.output_type):
        causes.append("consumer_resumed_downstream_not_completed")

    if sum(len(u.escalations) for u in organ.units.values()):
        causes.append("repair_budget_exhausted")
    if not causes:
        causes.append("unknown_terminal_state")
    return causes, detail


def main() -> int:
    plan = R.plan({"development"})
    rows, tally = [], {}
    for ep in plan:
        rng = random.Random(ep["seed"])
        organ = F.development(rng)
        F.prepare(organ)
        reset()
        organ.commission()
        healthy = organ.run_item(R.PAYLOAD_A)
        healthy_ok = organ.result_ok(healthy)
        obs = lambda: True
        victim = None
        if healthy_ok:
            pool = R.interior_pool(organ, organ._produced)
            if pool:
                victim = pool[ep["seed"] % len(pool)]
                obs, _ = F.inject(organ, victim, ep["damage_class"], rng)
        reset()
        restored = organ.run_item(R.PAYLOAD_B)
        restored_ok = organ.result_ok(restored)
        causes, detail = classify(organ, organ._produced, healthy_ok,
                                  bool(obs()), restored_ok)
        if restored_ok:
            continue
        for c in causes:
            tally[c] = tally.get(c, 0) + 1
        rows.append({"episode": ep["episode"], "seed": ep["seed"],
                     "damage_class": ep["damage_class"], "victim": victim,
                     "terminal_causes": causes, "evidence": detail,
                     "produced": sorted(organ._produced)})

    out = {"note": "Evaluator-only. No runtime behaviour was changed.",
           "development_episodes": len(plan),
           "unsuccessful_episodes": len(rows),
           "count_per_terminal_cause": dict(sorted(tally.items(),
                                                   key=lambda kv: -kv[1])),
           "episodes": rows}
    (HERE / "RESTORATION_FAILURE_TAXONOMY.json").write_text(
        json.dumps(out, indent=2) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "episodes"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
