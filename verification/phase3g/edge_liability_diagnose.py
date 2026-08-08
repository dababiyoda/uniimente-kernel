#!/usr/bin/env python3
"""LC-2a — edge-scoped liability: exact diagnosis before any mechanism.

The four LC-2 specifications describe a real defect: a parent opens an edge,
commits credit to it, and never receives a child-owned answer on that edge, so
its liability is stranded forever. This measures whether that defect is present
where those tests look for it, and whether their metric can be read at all.

    python verification/phase3g/edge_liability_diagnose.py
    python verification/phase3g/edge_liability_diagnose.py --verify-results

Exits nonzero unless every recorded finding still holds. Results:
`EDGE_LIABILITY_DIAGNOSIS.json`.

No runtime file is modified. The one candidate installed below is disposable
and removed in a `finally`.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
for _p in (_ROOT, _ROOT / "tests" / "unit", _HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import substrate.v5 as v5                                       # noqa: E402
import test_substrate_v5_control_outcome_separation as S        # noqa: E402

RESULTS = _HERE / "EDGE_LIABILITY_DIAGNOSIS.json"

# The seven counters the LC-2 specifications assert on.
METRIC_COUNTERS = (
    "CLOSED_CHILD_EDGES",
    "CLOSED_CHILD_EDGES_WITH_ACCEPTED_CHILD_OUTCOME",
    "CLOSED_CHILD_EDGES_WITHOUT_CHILD_EVIDENCE",
    "CHILD_EDGES_RECONCILED_FROM_EVIDENCE",
    "PARENT_CONTROLS_RECORDED_AS_CHILD_OUTCOMES",
    "OUTCOME_SLOT_OCCUPIED_BY_CONTROL",
    "TERMINALS_WITH_UNRECONCILED_CHILDREN",
)

# `_damaged(4, density=1.0)` is the fixture every LC-2 specification uses.
FIXTURES = (("n_auth=4 density=1.0", 4, 1.0),
            ("n_auth=5 density=0.8", 5, 0.8),
            ("n_auth=3 density=0.6", 3, 0.6))


def audit(o):
    """Liability state DERIVED from the organ, not from a counter.

    A hand-maintained counter can only report what somebody remembered to
    increment. This reads the edges themselves, so an edge nobody accounted for
    still appears.
    """
    probes, lc, edges = o.search_edge_probes, o.search_edge_lifecycle, o.search_edges
    opened = set(probes)
    with_outcome = {e for e in opened
                    if (lc.get(e) or {}).get("accepted_outcome") is not None}
    terminal = {e for e in opened
                if (edges.get(e) or {}).get("terminal_status") == "terminal"}
    stranded = opened - with_outcome
    control_only = {e for e in stranded
                    if (lc.get(e) or {}).get("accepted_control") is not None}
    owed = collections.Counter(probes[e]["from_unit"] for e in sorted(stranded))
    outstanding = sum(len(n["children_outstanding"])
                      for u in o.units.values()
                      for n in getattr(u, "canonical_searches", {}).values())
    nodes_outstanding = sum(1 for u in o.units.values()
                            for n in getattr(u, "canonical_searches", {}).values()
                            if n["children_outstanding"])
    return {
        "edges_opened": len(opened),
        "edges_with_accepted_child_outcome": len(with_outcome),
        "edges_marked_terminal": len(terminal),
        "edges_stranded": len(stranded),
        "stranded_holding_only_a_control": len(control_only),
        "terminal_without_child_outcome": len(terminal - with_outcome),
        "parents_left_waiting": dict(sorted(owed.items())),
        "nodes_with_children_outstanding": nodes_outstanding,
        "children_outstanding_total": outstanding,
    }


def classify_stranding(o):
    """Why each stranded edge stranded, read from the RECEIVER's own state.

    The classes are not a taxonomy invented for the write-up. They decide what
    is owed: an unresolved proposal (A, A2) needs its DISPOSITION routed back to
    its source, a closed frontier (C) needs `SearchExhausted`, spent credit (D)
    needs `SearchBudgetExhausted`. A design that cannot tell them apart cannot
    be correct, and the first version of this function could not: it tested
    `untried == 0` before it tested for an outstanding proposal, and so filed
    every node still waiting on its candidate as "space exhausted".
    """
    probes, lc = o.search_edge_probes, o.search_edge_lifecycle
    out = collections.Counter()
    detail = []
    for e in sorted(probes):
        if (lc.get(e) or {}).get("accepted_outcome") is not None:
            continue
        p = probes[e]
        recv = o.units.get(p["to_unit"])
        node = getattr(recv, "canonical_searches", {}).get(p["search_key"]) if recv else None
        if node is None:
            out["no_canonical_node_at_receiver"] += 1
            continue
        if node["adopted_parent_edge"] != e:
            out["stranded_edge_is_not_the_adopted_edge"] += 1
            continue
        outstanding = len(node["children_outstanding"])
        untried = node.get("eligible_untried_routes") or 0
        reserve = node["local_reserve"]
        # ORDER MATTERS, AND THE FIRST VERSION HAD IT WRONG. A node holding an
        # unresolved proposal is NOT frontier-empty: `_continue_after_child`
        # refuses to report exhaustion while `eligible_offer` stands, and it is
        # right to, because a candidate is still travelling. Classifying on
        # `untried == 0` first labelled those nodes "space exhausted" and made
        # the stranding look like a missing discharge, which it is not.
        if node.get("eligible_offer") or node.get("local_candidate") is not None:
            cls = "A_proposed_itself_and_was_never_answered"
        elif node.get("proposals_outstanding"):
            cls = "A2_relayed_a_proposal_and_was_never_answered"
        elif outstanding:
            cls = "B_waiting_on_a_stranded_child"
        elif untried == 0:
            cls = "C_frontier_empty_space_exhausted"
        elif reserve <= 0:
            cls = "D_routes_remain_credit_spent"
        else:
            cls = "E_unclassified_frontier_and_credit_both_remain"
        out[cls] += 1
        detail.append({"edge": e, "class": cls, "from": p["from_unit"],
                       "to": p["to_unit"], "outstanding": outstanding,
                       "untried": untried, "reserve": reserve,
                       "eligible_offer": bool(node.get("eligible_offer")),
                       "holds_local_candidate": node.get("local_candidate") is not None,
                       "status": node["status"]})
    return dict(sorted(out.items())), detail


def run(n_auth, density):
    o, _j, _slot, _victim, seed = S._damaged(n_auth, density=density)
    v5.reset()
    o.run_item(S.PAYLOAD_B)
    a = audit(o)
    a["seed"] = seed
    a["counters"] = {c: (v5.C[c] if c in v5.C.d else None) for c in METRIC_COUNTERS}
    a["stranding_classes"], a["stranding_detail"] = classify_stranding(o)
    return o, a


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-results", action="store_true")
    args = ap.parse_args()

    report = {"instrument": "edge_liability_diagnose", "fixtures": {}}
    for label, n_auth, density in FIXTURES:
        _o, a = run(n_auth, density)
        report["fixtures"][label] = a

    dense = report["fixtures"]["n_auth=4 density=1.0"]
    sparse = report["fixtures"]["n_auth=3 density=0.6"]

    # -- NEGATIVE CONTROL. The audit must be able to SEE a stranded edge. -----
    # Suppress the acceptance of one outcome kind and the stranded count must
    # rise. Without this, "0 stranded" on the dense fixture is unfalsifiable:
    # an audit that can never report a stranding would print 0 forever.
    original = v5.Unit._record_outcome
    seen: list = []

    def suppress_one(self, t):
        # Suppress EVERY outcome for one chosen edge, not merely the first call.
        # Dropping a single call left the edge closable by the next outcome that
        # arrived on it, so the injected defect healed itself and the control
        # reported a clean run -- the exact shape of failure it exists to catch.
        if not seen:
            seen.append(t.edge_id)
        if t.edge_id == seen[0]:
            return False                    # dropped: no outcome is accepted
        return original(self, t)

    v5.Unit._record_outcome = suppress_one
    try:
        seen.clear()
        _o, injected = run(4, 1.0)
    finally:
        v5.Unit._record_outcome = original
    report["negative_control"] = {
        "candidate": "suppress the first accepted outcome",
        "baseline_stranded": dense["edges_stranded"],
        "injected_stranded": injected["edges_stranded"],
        "detected": injected["edges_stranded"] > dense["edges_stranded"],
    }

    dead = [c for c in METRIC_COUNTERS
            if sparse["counters"].get(c) == 0 and dense["counters"].get(c) == 0]

    findings = {
        "the_lc2_fixture_contains_no_stranding": dense["edges_stranded"] == 0,
        "stranding_is_real_at_sparse_density": sparse["edges_stranded"] > 0,
        "no_edge_is_terminal_without_child_evidence": all(
            f["terminal_without_child_outcome"] == 0
            for f in report["fixtures"].values()),
        "closed_child_edges_counter_is_dead": dense["counters"]["CLOSED_CHILD_EDGES"] == 0
            and dense["edges_marked_terminal"] > 0,
        "counters_reading_zero_on_every_fixture": dead,
        # LC-2b depends on these three classes existing and on every stranded
        # edge being an ADOPTED edge. If a stranded edge appears that is not an
        # adopted edge, or a class D appears where frontier and credit both
        # remain, the recommended design does not cover the case and the
        # comparison has to be redone rather than quietly extended.
        "every_stranded_edge_is_an_adopted_edge": all(
            not f["stranding_classes"].get("stranded_edge_is_not_the_adopted_edge")
            and not f["stranding_classes"].get("no_canonical_node_at_receiver")
            for f in report["fixtures"].values()),
        "no_unclassified_stranding": all(
            not f["stranding_classes"].get(
                "E_unclassified_frontier_and_credit_both_remain")
            for f in report["fixtures"].values()),
        "sparse_stranding_classes": sparse["stranding_classes"],
    }
    report["findings"] = findings

    failures = []
    # POST-NC-3. This instrument was written to CHARACTERISE a defect and now
    # GUARDS its absence. The original finding -- 13 of 39 edges stranded at
    # sparse density -- is preserved in EDGE_LIABILITY_DIAGNOSIS_PRE_NC3.json and
    # in the markdown, because a diagnosis regenerated over its own subject stops
    # being evidence of anything. What is asserted here is the live invariant.
    if not report["negative_control"]["detected"]:
        failures.append("the audit did not notice a deliberately stranded edge, "
                        "so a zero stranding count proves nothing")
    stranded = {k: f["edges_stranded"] for k, f in report["fixtures"].items()
                if f["edges_stranded"]}
    if stranded:
        failures.append(f"edges are stranded again after need closure: {stranded}")
    if not findings["no_edge_is_terminal_without_child_evidence"]:
        failures.append("an edge reached terminal_status without an accepted "
                        "child outcome")
    if not findings["closed_child_edges_counter_is_dead"]:
        failures.append("CLOSED_CHILD_EDGES is no longer dead; the metric "
                        "denominator finding is stale and LC-2's remaining "
                        "specifications must be re-read against it")
    if not findings["every_stranded_edge_is_an_adopted_edge"]:
        failures.append("a stranded edge is not an adopted edge; LC-2b assumes "
                        "the liability is always the adopted one and the design "
                        "comparison must be redone")
    if not findings["no_unclassified_stranding"]:
        failures.append("a stranded node has both untried routes and reserve "
                        "left, which none of the three classes covers")
    report["failures"] = failures
    report["verdict"] = "CORRECT" if not failures else "STALE"

    if args.verify_results:
        if not RESULTS.exists():
            print(f"FAIL: {RESULTS.name} has never been recorded")
            return 1
        stored = json.loads(RESULTS.read_text())
        drift = [k for k in ("verdict", "findings")
                 if stored.get(k) != report[k]]
        if drift:
            print(f"FAIL: committed results no longer reproduce: {drift}")
            return 1
        print(f"OK: committed results reproduce ({report['verdict']})")
        return 0 if report["verdict"] == "CORRECT" else 1

    RESULTS.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    for label, f in report["fixtures"].items():
        print(f"{label:22} opened={f['edges_opened']:3} "
              f"answered={f['edges_with_accepted_child_outcome']:3} "
              f"stranded={f['edges_stranded']:3} "
              f"nodes_outstanding={f['nodes_with_children_outstanding']}")
    print(f"negative control detected a deliberate stranding: "
          f"{report['negative_control']['detected']} "
          f"({dense['edges_stranded']} -> {injected['edges_stranded']})")
    print(f"counters reading zero on every fixture: {dead}")
    print(f"verdict: {report['verdict']}")
    for f in failures:
        print(f"  {f}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
