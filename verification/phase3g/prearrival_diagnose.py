#!/usr/bin/env python3
"""PA-0B: EXECUTABLE reproduction of the pre-arrival control diagnosis.

Run it from anywhere:

    python verification/phase3g/prearrival_diagnose.py     (from the repo root)
    python prearrival_diagnose.py                          (from this directory)
    python /abs/path/to/prearrival_diagnose.py             (from anywhere)

Exits NONZERO unless every assertion below holds, and writes
`PREARRIVAL_DIAGNOSIS.json` beside itself.

WHY THIS FILE EXISTS IN THIS FORM. Its first version recorded snapshots and
asserted nothing, and the copy that was committed omitted the `context=`
argument the reported measurement depended on -- so the written diagnosis and
the executable instrument disagreed, and the repository could not reproduce its
own conclusion. That is the same defect this workstream has now hit six times:
a result asserted rather than executed. A diagnostic that cannot fail proves
nothing, so this one fails loudly.

NEGATIVE CONTROL. Pass `--negative-control` to drop the `context=` argument from
the late SearchNeed. The T2 adoption assertions MUST then fail, which is what
proves this instrument distinguishes a valid late adoption from a
context-rejected non-adoption. A negative-control run that passes T2 is itself
a defect and exits nonzero.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

# ---------------------------------------------------------------- portability
# Derived from __file__, never from the caller's working directory and never
# from an absolute developer path. This file lives at <repo>/verification/
# phase3g/, so the repo root is two parents up.
_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
for _p in (_ROOT, _ROOT / "tests" / "unit", _HERE):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

import substrate.v5 as v5                                   # noqa: E402
from substrate.v5 import C, reset                           # noqa: E402
from test_substrate_v5_direction_classification import (    # noqa: E402
    _pair, _open,
)

FAILURES: list[str] = []


def check(label: str, ok: bool, detail=None) -> bool:
    """Record an assertion. Never raises, so every check runs and all report."""
    if not ok:
        FAILURES.append(str(label) + (f"  [{detail}]" if detail is not None else ""))
    return bool(ok)


def head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(_ROOT),
                              capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:                                       # noqa: BLE001
        return "unavailable"


def credit_of(unit, key):
    """Every credit-bearing field on the receiver's node, or None if no node."""
    n = unit.canonical_searches.get(key)
    if n is None:
        return None
    return {f: round(float(n[f]), 9) for f in
            ("local_reserve", "child_allocations_in_flight", "cancelled_credit",
             "consumed_credit", "child_refunds_received", "returned_credit")
            if f in n}


def observe(unit, key, edge):
    o = unit._organ
    lc = o.search_edge_lifecycle.get(edge) or {}
    n = unit.canonical_searches.get(key)
    ac, ao = lc.get("accepted_control"), lc.get("accepted_outcome")
    return {
        "probe_exists": edge in o.search_edge_probes,
        "node_exists": n is not None,
        "adopted_parent_edge": n["adopted_parent_edge"] if n else None,
        "accepted_control": ac.kind if ac else None,
        "accepted_outcome": ao.kind if ao else None,
        "lifecycle_record_exists": bool(lc),
        "projection_entry": edge in o.search_edge_terminals,
        "edge_terminal_status": (o.search_edges.get(edge) or {}).get("terminal_status"),
        "credit": credit_of(unit, key),
    }


WATCH = tuple(n for n in (
    "ORPHANED_SEARCH_EDGES", "UNAUTHENTICATED_TERMINAL_CONTROLS",
    "UNAUTHENTICATED_SEARCH_DELIVERIES", "UNKNOWN_EDGE_TERMINAL_EMISSIONS",
    "UNAUTHENTICATED_TERMINAL_EMISSIONS", "UNCLASSIFIABLE_TERMINAL_RECORDINGS",
    "SEARCH_CONTROLS_RECORDED", "TERMINAL_ECHOS_SENT",
    "UNIQUE_CANONICAL_SEARCH_NODES", "DUPLICATE_TERMINAL_RESOLUTIONS",
    "UNAUTHORIZED_EXTERNAL_EFFECTS", "INHERITED_AUTHORITY_EVENTS",
) if n in v5.COUNTER_NAMES)


def counters():
    return {n: C[n] for n in WATCH}


# =====================================================================
def legitimate_sequence(pass_context: bool) -> dict:
    """T0 -> T3. The whole diagnosis lives here."""
    o, parent, child, ctx, key, seed = _pair()
    edge = "e/pa/clean"
    _open(o, parent, child, key, edge, allocation=6.0)      # sender-owned probe
    reset()

    # --- T0: probe present, node absent -----------------------------------
    t0 = observe(child, key, edge)
    check("T0 probe exists", t0["probe_exists"], t0)
    check("T0 canonical node absent", not t0["node_exists"], t0)
    credit_before = t0["credit"]

    # --- T1: a LEGITIMATE control arrives before the node exists ----------
    child.deliver_terminal(key, edge, "SearchCancelled", refund=6.0,
                           sender=parent.unit_id,
                           from_unit=parent.unit_id, to_unit=child.unit_id)
    t1, c1 = observe(child, key, edge), counters()
    check("T1 legitimate pre-arrival control observed",
          c1["ORPHANED_SEARCH_EDGES"] >= 1, c1)
    check("T1 accepted_control absent", t1["accepted_control"] is None, t1)
    check("T1 accepted_outcome absent", t1["accepted_outcome"] is None, t1)
    check("T1 lifecycle decision state unchanged",
          not t1["lifecycle_record_exists"], t1)
    check("T1 edge still open", t1["edge_terminal_status"] == "open", t1)
    check("T1 credit state unchanged", t1["credit"] == credit_before,
          (credit_before, t1["credit"]))

    # --- T2: the SearchNeed finally arrives, WITH its context --------------
    # The keyword is `context` -- see the deliver_search signature in
    # substrate/v5.py. --negative-control omits it, and the checks below must
    # then fail, which is what makes this instrument discriminating.
    if pass_context:
        child.deliver_search(key, edge, 6.0, sender=parent.unit_id, context=ctx)
    else:
        child.deliver_search(key, edge, 6.0, sender=parent.unit_id)
    t2, c2 = observe(child, key, edge), counters()
    check("T2 canonical node exists", t2["node_exists"], t2)
    check("T2 adopted_parent_edge == the pre-arrival edge",
          t2["adopted_parent_edge"] == edge, t2)
    check("T2 accepted_control STILL absent", t2["accepted_control"] is None, t2)
    check("T2 pre-arrival control was NOT recovered",
          c2["SEARCH_CONTROLS_RECORDED"] == 0, c2)

    # --- T3: the sender replays the same control after adoption -----------
    child.deliver_terminal(key, edge, "SearchCancelled", refund=6.0,
                           sender=parent.unit_id,
                           from_unit=parent.unit_id, to_unit=child.unit_id)
    t3, c3 = observe(child, key, edge), counters()
    check("T3 replay after adoption is accepted",
          c3["SEARCH_CONTROLS_RECORDED"] > c2["SEARCH_CONTROLS_RECORDED"], c3)
    check("T3 no duplicate terminal resolution",
          c3["DUPLICATE_TERMINAL_RESOLUTIONS"] == 0, c3)
    check("T3 no second orphan for the same control",
          c3["ORPHANED_SEARCH_EDGES"] == c1["ORPHANED_SEARCH_EDGES"], c3)

    return {"seed": seed, "parent": parent.unit_id, "child": child.unit_id,
            "edge": edge, "T0": t0, "T1": t1, "T2": t2, "T3": t3,
            "credit_before": credit_before, "credit_after": t3["credit"],
            "counters_T1": c1, "counters_T2": c2, "counters_T3": c3}


def forged_sequence() -> dict:
    """A stranger owning neither end, in the same pre-arrival window.

    At PA-0 there is no pending mechanism, so this proves CURRENT behaviour:
    the forgery reaches no state at all. It is recorded now so that the PA-3
    implementation has a before-picture it must not regress.
    """
    o, parent, child, ctx, key, seed = _pair()
    edge = "e/pa/forged"
    _open(o, parent, child, key, edge, allocation=6.0)
    stranger = next(u for u in o.units.values()
                    if u.unit_id not in (v5.ENV, v5.SINK,
                                         parent.unit_id, child.unit_id))
    reset()
    before = observe(child, key, edge)
    child.deliver_terminal(key, edge, "SearchCancelled", refund=6.0,
                           sender=stranger.unit_id,
                           from_unit=stranger.unit_id, to_unit=child.unit_id)
    after, c = observe(child, key, edge), counters()
    check("FORGED probe exists", after["probe_exists"], after)
    check("FORGED canonical node absent", not after["node_exists"], after)
    check("FORGED not placed into lifecycle state",
          not after["lifecycle_record_exists"], after)
    check("FORGED no accepted control", after["accepted_control"] is None, after)
    check("FORGED credit unchanged", after["credit"] == before["credit"],
          (before["credit"], after["credit"]))
    check("FORGED no unauthorized external effect",
          c.get("UNAUTHORIZED_EXTERNAL_EFFECTS", 0) == 0, c)
    check("FORGED no inherited authority",
          c.get("INHERITED_AUTHORITY_EVENTS", 0) == 0, c)
    return {
        "stranger": stranger.unit_id, "before": before, "after": after,
        "counters": c,
        # THE ORDERING FINDING, recorded as a measured fact rather than a claim.
        # The node-existence check precedes sender authentication, so a forged
        # pre-arrival control is refused for the WRONG REASON and is
        # indistinguishable in evidence from a legitimate one.
        "authentication_counter_fired":
            c["UNAUTHENTICATED_TERMINAL_CONTROLS"] > 0,
        "refused_via_orphan_branch": c["ORPHANED_SEARCH_EDGES"] >= 1,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--negative-control", action="store_true",
                    help="omit context= from the late SearchNeed; T2 MUST fail")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    negative = args.negative_control
    out_path = pathlib.Path(args.json) if args.json else (
        _HERE / ("PREARRIVAL_DIAGNOSIS_NEGATIVE_CONTROL.json" if negative
                 else "PREARRIVAL_DIAGNOSIS.json"))

    legit = legitimate_sequence(pass_context=not negative)
    forged = forged_sequence()

    classification = (
        "SILENT_LOSS"
        if (legit["T1"]["accepted_control"] is None
            and not legit["T1"]["lifecycle_record_exists"]
            and legit["T1"]["credit"] == legit["credit_before"]
            and legit["counters_T1"]["ORPHANED_SEARCH_EDGES"] >= 1)
        else "NOT_ESTABLISHED")

    out = {
        "starting_head": head(),
        "command_executed": " ".join([sys.executable] + sys.argv),
        "working_directory": str(pathlib.Path.cwd()),
        "repo_root_derived_from___file__": str(_ROOT),
        "portable_path_check":
            "sys.path derived from __file__; no absolute developer path",
        "mode": "NEGATIVE_CONTROL" if negative else "NORMAL",
        "legitimate_prearrival_result": legit["T1"],
        "late_adoption_result": legit["T2"],
        "post_adoption_replay_result": legit["T3"],
        "forged_prearrival_result": forged,
        "credit_before": legit["credit_before"],
        "credit_after": legit["credit_after"],
        "counters": legit["counters_T3"],
        "classification": classification,
        "assertions_failed": FAILURES,
        "result": "PASS" if not FAILURES else "FAIL",
    }

    if negative:
        # FAILING T2 is the correct outcome here. Passing would mean the
        # instrument cannot tell adoption from context-rejection.
        expected = [f for f in FAILURES if f.startswith("T2 ")]
        out["negative_control_expected_failures"] = expected
        out["negative_control_verdict"] = (
            "CORRECT: T2 adoption assertions failed as required"
            if expected else
            "DEFECTIVE: T2 passed without a context, so this instrument cannot "
            "distinguish valid late adoption from context-rejected non-adoption")
        with open(out_path, "w") as fh:
            json.dump(out, fh, indent=2, sort_keys=True)
        print(json.dumps({k: out[k] for k in
                          ("mode", "negative_control_verdict",
                           "negative_control_expected_failures")}, indent=2))
        return 0 if expected else 1

    with open(out_path, "w") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
    print(json.dumps({k: out[k] for k in
                      ("starting_head", "working_directory", "mode",
                       "classification", "result", "assertions_failed")},
                     indent=2))
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    sys.exit(main())
