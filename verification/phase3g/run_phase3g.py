#!/usr/bin/env python3
"""Phase 3G experiment runner.

Per episode:

  commission (the ONLY boundary event)
  -> run one work item, real semantic output
  -> inject a preregistered damage class on a load-bearing interior carrier
  -> run the NEXT work item; the affected consumer discovers the break during
     its own ordinary processing
  -> evaluate from events and evidence

Cohorts are scored on their OWN denominators. Combining Gate F and Gate G for
any Gate F metric is prohibited by the manifest and not done here.

Usage:  run_phase3g.py [development|heldout|all]
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import random
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))

from substrate.v5 import (COOLDOWN_RETURN, CONFLICTING, COSTLY, DELAYED, ENV,
                          EXPIRED, FALSE_SUSPICION, GONE, INTERMITTENT, ISOLATED,
                          MISSING_RECEIPT, REPEATED, SILENT, SINK, STALE_RETURN,
                          WRONG, C, MeasuredMotif, diagnose, form_key, measure,
                          motif_from, normalized_form, reset)
import evaluator as EV
import fixtures as F

M = json.loads((HERE / "EVALUATION_MANIFEST.json").read_text())
PAYLOAD_A = "  Claim-4417 / Ambulatory  "
PAYLOAD_B = "  Claim-4418 / Ambulatory  "

DAMAGE = (GONE, SILENT, ISOLATED, COSTLY, WRONG, INTERMITTENT, DELAYED, EXPIRED,
          STALE_RETURN, FALSE_SUSPICION, CONFLICTING, MISSING_RECEIPT, REPEATED,
          COOLDOWN_RETURN)
assert len(DAMAGE) == 14


def implementation_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                              text=True, cwd=HERE.parents[1]).stdout.strip()
    except Exception:
        return "unknown"


def require_clean_tree() -> None:
    """A run whose recorded SHA does not reproduce it is not evidence.

    R3 recorded 1d7349c while the tested changes were uncommitted. Bypass is
    possible with PHASE3G_ALLOW_DIRTY=1, and the result is then marked
    exploratory rather than reproducible.
    """
    import os
    out = subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                         text=True, cwd=HERE.parents[1]).stdout.strip()
    tracked = [l for l in out.splitlines() if not l.startswith("??")]
    if tracked and os.environ.get("PHASE3G_ALLOW_DIRTY") != "1":
        print("REFUSING TO RUN: working tree is dirty, so the recorded SHA "
              "would not reproduce this run.")
        for l in tracked[:10]:
            print("   ", l)
        raise SystemExit(2)
    return bool(tracked)


def interior_pool(organ, produced):
    """Preregistered rule: carriers in the trace bonded as a supplier by a
    consumer that is not the boundary."""
    consumed = {b.supplier for uid, u in organ.units.items() if uid != SINK
                for b in u.bonds.values()}
    return sorted(c for c in produced if c in consumed and c not in (ENV, SINK))


def _twin_pre_repair_loss(ep, victim) -> bool:
    """Independent twin. Nothing here touches the scored organ."""
    rng = random.Random(ep["seed"])
    build = (F.HELD_OUT[ep["fixture"]] if ep["held_out"]
             else (F.RESILIENCE if ep["cohort"] == "resilience" else F.development))
    twin = build(rng)
    F.prepare(twin)
    saved = C.snapshot()
    try:
        twin.commission()
        if not twin.result_ok(twin.run_item(PAYLOAD_A)):
            return True
        if victim not in twin.units:
            return True
        F.inject(twin, victim, ep["damage_class"], rng)
        for u in twin.units.values():
            u.repair_budget = 0.0          # repair prohibited on the twin
        return not twin.result_ok(twin.run_item(PAYLOAD_B))
    finally:
        for k, v in saved.items():         # the twin must not move the counters
            C.d[k] = v


def episode(ep, results, *, certificate=True):
    rng = random.Random(ep["seed"])
    build = (F.HELD_OUT[ep["fixture"]] if ep["held_out"]
             else (F.RESILIENCE if ep["cohort"] == "resilience" else F.development))
    organ = build(rng)
    F.prepare(organ)
    rec = {"episode": ep["episode"], "cohort": ep["cohort"], "gate": ep.get("gate"),
           "held_out": ep["held_out"], "fixture": ep["fixture"],
           "damage_class": ep["damage_class"], "certificate": certificate,
           "seed": ep["seed"]}

    reset()
    organ.commission()
    healthy = organ.run_item(PAYLOAD_A)
    rec["healthy_ok"] = organ.result_ok(healthy)
    if not rec["healthy_ok"]:
        rec.update(void=True, void_reason="no healthy semantic output", success=False)
        results.append(rec)
        return
    rec["initial_form"] = form_key(organ, measure(organ, organ._produced))

    pool = interior_pool(organ, organ._produced)
    if not pool:
        rec.update(void=True, void_reason="no interior carrier", success=False)
        results.append(rec)
        return
    victim = pool[ep["seed"] % len(pool)]
    rec["victim"] = victim
    rec["victim_class"] = organ.units[victim].capability.klass()
    consumers_of_victim = sorted(organ.units[victim].consumers)
    rec["direct_consumers"] = consumers_of_victim

    observed, how = F.inject(organ, victim, ep["damage_class"], rng)
    rec["injection"] = how

    # Gate G: hand the affected consumers a prohibition over measured relations
    if ep.get("gate") == "G":
        for cid in consumers_of_victim:
            u = organ.units.get(cid)
            if u is None:
                continue
            u.constraint_enabled = certificate
            if certificate:
                u.prohibited.append(MeasuredMotif(u.capability.klass(),
                                                  supplier_count=1))

    # PRE-REPAIR PROBE ON AN INDEPENDENT TWIN. Running it on the scored organ
    # mutated receipts, messages, memory, produced values and need state, and
    # its traffic was being counted as repair traffic. The twin is rebuilt from
    # the same seed, forms the same structure, selects the same victim by the
    # same preregistered rule, takes the same damage, is denied repair, and is
    # then discarded. Zero shared mutable state with the scored episode.
    pre_loss = _twin_pre_repair_loss(ep, victim)

    reset()
    before_msgs = organ.messages
    restored = organ.run_item(PAYLOAD_B)
    snap = C.snapshot()

    rec["damage_class_observed"] = bool(observed())
    # PRE-REPAIR SEMANTIC LOSS, proved from evidence rather than inferred from
    # the fact that something activated. An activation shows detection; it does
    # not show the business-facing output was lost. Evaluator-only: this never
    # triggers repair.
    rec["pre_repair_semantic_loss_proven"] = bool(pre_loss)
    rec["semantic_loss"] = rec["pre_repair_semantic_loss_proven"]
    rec["event_driven_local_activations"] = snap["EVENT_DRIVEN_LOCAL_ACTIVATIONS"]
    rec["boundary_triggered_repair_events"] = snap["BOUNDARY_TRIGGERED_REPAIR_EVENTS"]
    rec["supervisor_restart_events"] = snap["SUPERVISOR_RESTART_EVENTS"]
    rec["whole_organ_review_passes"] = snap["WHOLE_ORGAN_REVIEW_PASSES"]
    rec["global_repair_scans"] = snap["GLOBAL_REPAIR_SCANS"]
    rec["unit_enumerations_for_repair"] = snap["UNIT_ENUMERATIONS_FOR_REPAIR"]
    rec["developmental_provider_index_reads"] = snap["FULL_PROVIDER_INDEX_READS"]
    rec["stale_derivations_rejected"] = EV.stale_derivations_rejected(organ)
    # Constraint-preserving distinct replacement search.
    for k in ("DISTINCT_ELIGIBLE_REPLACEMENTS_DISCOVERED",
              "DISTINCT_ELIGIBLE_REPLACEMENTS_SETTLED",
              "BOUNDED_DISTINCT_REPLACEMENT_EXHAUSTIONS",
              "INELIGIBLE_CANDIDATE_BRANCH_CONTINUATIONS",
              "INDEPENDENCE_VIOLATIONS"):
        rec[k.lower()] = snap[k]
    rec["duplicate_supplier_blocked_repair"] = EV.duplicate_supplier_blocked(organ)
    rec["credit_ledger"] = EV.credit_ledger_reconciliation(organ)
    rec["credit_conservation_ok"] = rec["credit_ledger"]["ok"]
    rec["bounded_escalation_proven"] = EV.bounded_escalation_proven(organ)
    rec["tree_ledger"] = EV.tree_credit_reconciliation(organ)
    rec["unacknowledged_terminal_branches"] = EV.unacknowledged_terminal_branches(organ)
    for k in ("BRANCH_TREES_OPENED", "CHILD_BRANCHES_COMPLETED",
              "PREMATURE_PARENT_BRANCH_COMPLETIONS",
              "PARENT_BRANCH_COMPLETIONS_PROPAGATED"):
        rec[k.lower()] = snap[k]
    rec["events_dispatched"] = organ.events_dispatched
    rec["repair_messages"] = organ.messages - before_msgs
    rec["repair_amplification"] = EV.repair_amplification(
        organ, rec["repair_messages"])

    # local evidence at a DIRECT consumer of the victim
    rs = EV.receipts(organ)
    rec["local_evidence_at_direct_consumer"] = any(
        r.at in consumers_of_victim and r.kind in ("reopened", "semantic_reject")
        for r in rs)

    diag = diagnose(rs)
    rec["inferred_class"] = diag.failure_class if diag else None
    rec["inferred_capability_class"] = diag.affected_class if diag else None
    rec["blind_class_correct"] = bool(diag and diag.failure_class == ep["damage_class"])
    rec["blind_role_correct"] = bool(diag and diag.affected_class == rec["victim_class"])

    rec["semantic_restoration"] = organ.result_ok(restored)
    rec["stale_derivation_reuse"] = EV.stale_derivation_reuse(organ, organ._produced)
    # provider-index reads by the EVALUATOR are counted separately and are legal
    reads_before = C["FULL_PROVIDER_INDEX_READS"]
    rec["over_refusal"] = EV.over_refusal(organ)
    rec["evaluator_provider_index_reads"] = C["FULL_PROVIDER_INDEX_READS"] - reads_before
    rec["unauthorized_external_effects"] = EV.unauthorised_external_effects()
    rec["escalations"] = sum(len(u.escalations) for u in organ.units.values())
    rec["refusal_evidence"] = EV.refusal_evidence(organ)[:3]

    if rec["semantic_restoration"]:
        rec["recovered_form"] = form_key(organ, measure(organ, organ._produced))
        rec["form_changed"] = rec["recovered_form"] != rec["initial_form"]

    if ep["cohort"] == "resilience":
        rec["success"] = rec["semantic_restoration"]
        rec["tolerated"] = rec["semantic_restoration"] and \
            rec["event_driven_local_activations"] == 0
    elif ep["cohort"] == "no_replacement":
        rec["success"] = (not rec["semantic_restoration"]
                          and rec["escalations"] > 0)
        rec["correct_refusal"] = rec["success"]
    elif ep.get("gate") == "G":
        rec["prohibited_proposals"] = sum(u.prohibited_proposals
                                          for u in organ.units.values())
        rec["blocked_commits"] = sum(u.blocked_commits for u in organ.units.values())
        rec["success"] = bool(rec["semantic_restoration"] and rec.get("form_changed"))
        rec["causal_escape"] = rec["success"]
    else:
        rec["success"] = EV.qualifies(rec)
    results.append(rec)


def plan(cohorts):
    eps, n = [], 0
    held = sorted(F.HELD_OUT)
    E = M["episodes"]
    if "development" in cohorts:
        for i in range(E["development"]):
            eps.append({"episode": n, "cohort": "development", "held_out": False,
                        "fixture": "development", "damage_class": DAMAGE[i % 14],
                        "seed": M["seeds"]["development"][i]})
            n += 1
    if "heldout" in cohorts:
        n = 1000
        for gate, key, cnt in (("F", "gate_f", E["gate_f_held_out"]),
                               ("G", "gate_g", E["gate_g_held_out"])):
            for i in range(cnt):
                eps.append({"episode": n, "cohort": "regeneration", "gate": gate,
                            "held_out": True, "fixture": held[i % len(held)],
                            "damage_class": DAMAGE[i % 14],
                            "seed": M["seeds"][key][i]})
                n += 1
        for i in range(E["mixed_failure"]):
            eps.append({"episode": n, "cohort": "mixed", "held_out": True,
                        "fixture": "two_simultaneous_breaks_different_causes",
                        "damage_class": DAMAGE[i % 14],
                        "seed": M["seeds"]["mixed"][i]})
            n += 1
        for i in range(E["resilience"]):
            eps.append({"episode": n, "cohort": "resilience", "held_out": False,
                        "fixture": "resilience", "damage_class": DAMAGE[i % 14],
                        "seed": M["seeds"]["resilience"][i]})
            n += 1
        for i in range(E["no_replacement"]):
            eps.append({"episode": n, "cohort": "no_replacement", "held_out": True,
                        "fixture": "no_valid_replacement", "damage_class": GONE,
                        "seed": M["seeds"]["no_replacement"][i]})
            n += 1
    return eps


FAIL_KEYS = ("episode", "cohort", "fixture", "damage_class", "void_reason",
             "event_driven_local_activations", "semantic_restoration",
             "over_refusal", "inferred_class", "repair_amplification",
             "events_dispatched", "pre_repair_semantic_loss_proven")


def _fails(rows):
    return [{k: r.get(k) for k in FAIL_KEYS} for r in rows if not r.get("success")]


DIRTY = [False]


def summarise(res, paired, cohorts):
    gf = [r for r in res if r.get("gate") == "F" and r["held_out"]]
    gg = [r for r in res if r.get("gate") == "G" and r["held_out"]]
    mixed = [r for r in res if r["cohort"] == "mixed"]
    resil = [r for r in res if r["cohort"] == "resilience"]
    norep = [r for r in res if r["cohort"] == "no_replacement"]
    dev = [r for r in res if r["cohort"] == "development"]

    diagnosed = [r for r in gf + gg if r.get("inferred_class")]
    mdiag = [r for r in mixed if r.get("inferred_class")]
    exercised = {}
    for k in DAMAGE:
        got = [r for r in res if r["damage_class"] == k]
        exercised[k] = {"episodes": len(got),
                        "observed": sum(1 for r in got if r.get("damage_class_observed"))}

    s = {
        "implementation_sha_at_development_run": implementation_sha(),
        "frozen": False,   # set only by the freeze commit + heldout run
        "reproducible_from_recorded_sha": not DIRTY[0],
        "cohorts_run": sorted(cohorts),
        "HELD_OUT_EVENT_DRIVEN_LOCAL_SEMANTIC_REGENERATIONS": {
            "n": sum(1 for r in gf if r.get("success")), "of": len(gf),
            "denominator": "Gate F held-out only; Gate G is NOT combined",
            "threshold": 17},
        "EVENT_DRIVEN_LOCAL_ACTIVATIONS_gate_f": {
            "n": sum(1 for r in gf if r.get("event_driven_local_activations", 0) > 0),
            "of": len(gf)},
        "HELD_OUT_SEMANTIC_RESTORATIONS_gate_f": {
            "n": sum(1 for r in gf if r.get("semantic_restoration")), "of": len(gf)},
        "GATE_G_CAUSAL_ESCAPES": {"n": sum(1 for r in gg if r.get("success")),
                                  "of": len(gg), "threshold": 15},
        "BOUNDARY_TRIGGERED_REPAIR_EVENTS": sum(
            r.get("boundary_triggered_repair_events", 0) for r in res),
        "SUPERVISOR_RESTART_EVENTS": sum(
            r.get("supervisor_restart_events", 0) for r in res),
        "WHOLE_ORGAN_REVIEW_PASSES": sum(
            r.get("whole_organ_review_passes", 0) for r in res),
        "GLOBAL_REPAIR_SCANS": sum(r.get("global_repair_scans", 0) for r in res),
        "UNIT_ENUMERATIONS_FOR_REPAIR": sum(
            r.get("unit_enumerations_for_repair", 0) for r in res),
        "DEVELOPMENTAL_PROVIDER_INDEX_READS": sum(
            r.get("developmental_provider_index_reads", 0) for r in res),
        "evaluator_provider_index_reads": sum(
            r.get("evaluator_provider_index_reads", 0) for r in res),
        "STALE_DERIVATION_REUSE": sum(r.get("stale_derivation_reuse", 0) for r in res),
        "STALE_DERIVATIONS_REJECTED": sum(
            r.get("stale_derivations_rejected", 0) for r in res),
        "OVER_REFUSAL_EVENTS": sum(r.get("over_refusal", 0) for r in res),
        "DUPLICATE_SUPPLIER_BLOCKED_REPAIR_EPISODES": sum(
            1 for r in res if r.get("duplicate_supplier_blocked")),
        "DISTINCT_ELIGIBLE_REPLACEMENTS_DISCOVERED": sum(
            r.get("distinct_eligible_replacements_discovered", 0) for r in res),
        "DISTINCT_ELIGIBLE_REPLACEMENTS_SETTLED": sum(
            r.get("distinct_eligible_replacements_settled", 0) for r in res),
        "BOUNDED_DISTINCT_REPLACEMENT_EXHAUSTIONS": sum(
            r.get("bounded_distinct_replacement_exhaustions", 0) for r in res),
        "INELIGIBLE_CANDIDATE_BRANCH_CONTINUATIONS": sum(
            r.get("ineligible_candidate_branch_continuations", 0) for r in res),
        "INDEPENDENCE_VIOLATIONS": sum(
            r.get("independence_violations", 0) for r in res),
        "CREDIT_CONSERVATION_FAILURES": sum(
            1 for r in res if r.get("credit_conservation_ok") is False),
        "CREDIT_LEDGER_INVARIANT_FAILURES": sum(
            r.get("credit_ledger", {}).get("invariant_failures", 0) for r in res),
        "CREDIT_LEDGER_BUDGET_EXCEEDED": sum(
            r.get("credit_ledger", {}).get("budget_exceeded", 0) for r in res),
        "CREDIT_LEDGER_BRANCH_OVERPAYMENTS": sum(
            r.get("credit_ledger", {}).get("branch_overpayments", 0) for r in res),
        "CREDIT_LEDGER_NEEDS_RECONCILED": sum(
            r.get("credit_ledger", {}).get("needs", 0) for r in res),
        "BOUNDED_ESCALATION_PROVEN_EPISODES": sum(
            1 for r in res if r.get("bounded_escalation_proven")),
        "BRANCH_TREES_OPENED": sum(r.get("branch_trees_opened", 0) for r in res),
        "CHILD_BRANCHES_COMPLETED": sum(
            r.get("child_branches_completed", 0) for r in res),
        "PARENT_BRANCH_COMPLETIONS_PROPAGATED": sum(
            r.get("parent_branch_completions_propagated", 0) for r in res),
        "PREMATURE_PARENT_BRANCH_COMPLETIONS": sum(
            r.get("premature_parent_branch_completions", 0) for r in res)
            + sum(r.get("tree_ledger", {}).get("premature_parent_completions", 0)
                  for r in res),
        "UNACKNOWLEDGED_TERMINAL_BRANCHES": sum(
            r.get("unacknowledged_terminal_branches", 0) for r in res)
            + sum(r.get("tree_ledger", {}).get(
                "unacknowledged_terminal_branches", 0) for r in res),
        "TREE_CREDIT_LEDGER_FAILURES": sum(
            r.get("tree_ledger", {}).get("invariant_failures", 0) for r in res),
        "VOID_REGENERATION_EPISODES": {
            "n": sum(1 for r in gf + gg if r.get("void")), "of": len(gf) + len(gg),
            "reasons": sorted({r["void_reason"] for r in gf + gg if r.get("void")})},
        "INITIAL_TOPOLOGY_NORMALIZED_FORMS": len(
            {r["initial_form"] for r in res if r.get("initial_form")}),
        "RECOVERED_TOPOLOGY_NORMALIZED_FORMS": len(
            {r["recovered_form"] for r in res if r.get("recovered_form")}),
        "HELD_OUT_BLIND_CAUSAL_CLASS_ACCURACY": round(
            sum(1 for r in diagnosed if r["blind_class_correct"]) / max(1, len(diagnosed)), 4),
        "HELD_OUT_BLIND_AFFECTED_ROLE_ACCURACY": round(
            sum(1 for r in diagnosed if r["blind_role_correct"]) / max(1, len(diagnosed)), 4),
        "MIXED_FAILURE_CAUSAL_CLASS_ACCURACY": round(
            sum(1 for r in mdiag if r["blind_class_correct"]) / max(1, len(mdiag)), 4),
        "diagnosed": len(diagnosed), "mixed_diagnosed": len(mdiag),
        "RESILIENCE_TOLERATED": {"n": sum(1 for r in resil if r.get("tolerated")),
                                 "of": len(resil)},
        "CORRECT_ESCALATIONS": {"n": sum(1 for r in norep if r.get("success")),
                                "of": len(norep)},
        "REPAIR_AMPLIFICATION_MAX": max(
            (r.get("repair_amplification", 0) for r in res), default=0),
        "UNAUTHORIZED_EXTERNAL_EFFECTS": max(
            (r.get("unauthorized_external_effects", 0) for r in res), default=0),
        "damage_classes_exercised": exercised,
        "damage_classes_not_observed": sorted(
            k for k, v in exercised.items() if v["episodes"] and not v["observed"]),
        # PER-EPISODE, not per-class. Reporting only classes with zero
        # observations hid partial injector failures: a class could be counted
        # as exercised while most of its episodes never saw the condition.
        "damage_episodes_assigned": len([r for r in res if not r.get("void")]),
        "damage_episodes_observed": len([r for r in res
                                         if r.get("damage_class_observed")]),
        "damage_episodes_not_observed": [
            {"episode": r["episode"], "damage_class": r["damage_class"],
             "fixture": r["fixture"]}
            for r in res if not r.get("void") and not r.get("damage_class_observed")],
        "development_success": {"n": sum(1 for r in dev if r.get("success")),
                                "of": len(dev)},
        "paired_intervention": {
            "pairs": len(paired),
            "MATCHING_PROHIBITED_PROPOSALS_OBSERVED": sum(
                p["without"].get("prohibited_proposals", 0) for p in paired),
            "PROHIBITED_COMMITS_WITHOUT_CERTIFICATE": sum(
                1 for p in paired if p["without"].get("semantic_restoration")
                and not p["without"].get("form_changed")),
            "PROHIBITED_COMMITS_WITH_CERTIFICATE": sum(
                1 for p in paired if p["with"].get("semantic_restoration")
                and not p["with"].get("form_changed")
                and not p["with"].get("blocked_commits")),
            "ALTERNATIVE_SUCCESSFUL_COMMITS_WITH_CERTIFICATE": sum(
                1 for p in paired if p["with"].get("semantic_restoration")
                and p["with"].get("form_changed"))},
        "development_failures": _fails(dev),
        "heldout_failures": _fails(gf),
        "gate_g_failures": _fails(gg),
        "mixed_failures": _fails(mixed),
    }
    return s


COHORT_ARGS = {"development": {"development"},
               "heldout": {"heldout"},
               "all": {"development", "heldout"}}


def main() -> int:
    # FAIL CLOSED. This previously read `sys.argv[1]` and sent ANY unrecognised
    # value to the else branch, whose value was {"development", "heldout"}. So a
    # typo -- `--cohorts development` -- silently consumed the entire
    # preregistered held-out draw. An unknown argument now aborts, and the
    # held-out cohorts require an explicit acknowledgement that the draw is
    # spent by running them, because that draw can only be spent once.
    which = sys.argv[1] if len(sys.argv) > 1 else "development"
    if which not in COHORT_ARGS:
        print(f"REFUSING TO RUN: unknown cohort argument {which!r}.")
        print(f"Expected exactly one of: {', '.join(sorted(COHORT_ARGS))}")
        print("This script takes a POSITIONAL argument and accepts no flags.")
        return 2
    cohorts = COHORT_ARGS[which]
    if "heldout" in cohorts:
        retired = json.loads((HERE / "RETIRED_DRAWS.json").read_text())
        active = M.get("draw_id", "phase3g-heldout-draw-1")
        for d in retired["retired_draws"]:
            if d["draw_id"] == active:
                print(f"REFUSING TO RUN: draw {active!r} is {d['status']} and "
                      f"{d['admissibility']}. It may never instantiate a gate run.")
                print(f"Reason: {d['retired_because']}")
                print("See FRESH_DRAW_PROTOCOL.md.")
                return 2
        if active in retired.get("spent_draws", []):
            print(f"REFUSING TO RUN: draw {active!r} has already been spent.")
            return 2
    if "heldout" in cohorts and os.environ.get("PHASE3G_SPEND_HELDOUT") != "1":
        print("REFUSING TO RUN: running the held-out cohort spends the "
              "preregistered draw, which is valid exactly once and only after "
              "the implementation is frozen.")
        print("Set PHASE3G_SPEND_HELDOUT=1 to spend it deliberately.")
        return 2
    DIRTY[0] = require_clean_tree()
    res: list[dict] = []
    for ep in plan(cohorts):
        episode(ep, res)

    paired = []
    if "heldout" in cohorts:
        held = sorted(F.HELD_OUT)
        for i, seed in enumerate(M["seeds"]["paired"]):
            base = {"episode": 9000 + i, "cohort": "regeneration", "gate": "G",
                    "held_out": True, "fixture": held[i % len(held)],
                    "damage_class": DAMAGE[i % 14], "seed": seed}
            off, on = [], []
            episode(dict(base), off, certificate=False)
            episode(dict(base), on, certificate=True)
            paired.append({"seed": seed, "fixture": base["fixture"],
                           "damage_class": base["damage_class"],
                           "without": off[0], "with": on[0]})

    s = summarise(res, paired, cohorts)
    tag = "PHASE3G_RESULTS.json" if "heldout" in cohorts else "DEVELOPMENT_RESULTS.json"
    (HERE / tag).write_text(json.dumps(
        {"summary": s, "episodes": res, "paired": paired}, indent=2) + "\n")
    if paired:
        (HERE / "PAIRED_INTERVENTIONS.json").write_text(
            json.dumps(paired, indent=2) + "\n")
    print(json.dumps({k: v for k, v in s.items()
                      if k not in ("failures", "damage_classes_exercised")}, indent=2))
    print("development failures:", len(s["development_failures"]),
          "| heldout:", len(s["heldout_failures"]),
          "| gate G:", len(s["gate_g_failures"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
