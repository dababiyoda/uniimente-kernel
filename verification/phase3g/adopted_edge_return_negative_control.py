#!/usr/bin/env python3
"""LC-1 negative control for the adopted-parent-edge return invariant.

A corrected test that passes proves nothing on its own: the failure mode this
workstream keeps finding is an instrument that cannot observe its own subject
and therefore converts UNKNOWN into PASS. This attacks the corrected Test H
with disposable broken candidates and requires it to fail on each one.

The oracle is not re-implemented here. This imports the SAME
`_assert_offers_return_through_adopted_edges` the test calls, so a weakening of
the test is a weakening of this control, and the two cannot drift apart.

    python verification/phase3g/adopted_edge_return_negative_control.py
    python verification/phase3g/adopted_edge_return_negative_control.py --verify-results

Exit status is 0 only if:

  * the POSITIVE control passes -- the unmodified runtime satisfies the oracle
    on both fixtures (otherwise a failing negative proves only that everything
    fails);
  * EVERY broken candidate is caught on at least one fixture;
  * the caught message NAMES the wrong route, rather than failing for some
    unrelated reason such as a crash or an empty trace;
  * the destination clause -- "sent to X, not to its adopted parent Y" -- fires
    somewhere in the corpus, so the jump-to-origin attack is discriminated by
    where the message went and not only by which edge id it carried.

No runtime file is modified. Every candidate is installed on the class object
for the duration of one run and removed in a `finally`.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import traceback

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
for _p in (_ROOT, _ROOT / "tests" / "unit", _HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import substrate.v5 as v5                                       # noqa: E402
import test_substrate_v5_single_flight_echo as H                # noqa: E402

RESULTS = _HERE / "ADOPTED_EDGE_RETURN_NEGATIVE_CONTROL.json"

# The three fixtures the corrected test uses, for the same stated reasons: a
# competing arrival at a node that answered, a genuine relay hop, and a node
# that proposes while already holding a second incoming edge.
#
# The third exists BECAUSE of this control. With only the first two, the
# `most_recent_incoming_edge` candidate escaped -- not because the test was
# blind to it, but because in both runs the latest arrival at a proposing node
# still WAS its adopted edge, so the broken candidate emitted exactly what the
# correct one would have. An attack that cannot change the output is not
# evidence of coverage.
FIXTURES = (("n_auth=4 density=1.0", 4, 1.0),
            ("n_auth=5 density=0.8", 5, 0.8),
            ("n_auth=3 density=0.6", 3, 0.6))


# ---------------------------------------------------------------------------
# Disposable broken candidates. Each keeps the protocol otherwise intact and
# changes only WHERE the proposal is sent.
# ---------------------------------------------------------------------------

def _most_recent_incoming_edge(self, node, payload):
    """Return through the LAST edge that arrived, not the adopted one.

    This is the `reverse[need_id]` defect exactly: a later arrival captures the
    return route. It is only an attack where a node really did receive more
    than one arrival, which is why the fixtures are chosen to contain one.
    """
    edge = list(node["incoming_edges"])[-1]
    probe = (self._organ.search_edge_probes.get(edge) or {}) if self._organ else {}
    to = probe.get("from_unit") or node["adopted_parent_sender"]
    if not to:
        return
    self.outbox.append((to, ("__proposal__", node["search_key"], edge, payload)))


def _non_adopted_alias(self, node, payload):
    """Right destination, an edge id that names no probed edge."""
    to = node["adopted_parent_sender"]
    if not to:
        return
    self.outbox.append((to, ("__proposal__", node["search_key"],
                             node["adopted_parent_edge"] + "#alias", payload)))


def _jump_to_origin(self, node, payload):
    """Skip the chain and hand the evidence straight to the search origin.

    The adopted EDGE is kept deliberately. A candidate that changed both edge
    and destination would be rejected on the edge first, and the report would
    never show that a wrong destination is discriminated at all -- the edge
    clause would mask it. This attacks only where the message goes.
    """
    key = node["search_key"]
    to = key.origin_unit
    if not to or to == self.unit_id:
        return
    self.outbox.append((to, ("__proposal__", key,
                             node["adopted_parent_edge"], payload)))


CANDIDATES = (
    ("most_recent_incoming_edge", _most_recent_incoming_edge,
     "a later arrival captures the return route"),
    ("non_adopted_alias", _non_adopted_alias,
     "the return route is an alias of the adopted edge, not the adopted edge"),
    ("jump_to_origin", _jump_to_origin,
     "evidence is handed straight to the search origin, skipping the chain"),
)

# Substrings that mean the oracle rejected a ROUTE, as opposed to tripping over
# an unrelated failure. Keyed so the report can say which clause fired.
ROUTE_CLAUSES = {
    "wrong_edge": "not through its immutable adopted parent edge",
    "unprobed_edge": "an edge the organ never probed",
    "not_an_arrival": "which never arrived at this node",
    "wrong_destination": "not to its adopted parent",
    "not_a_neighbour": "which is not a neighbour",
    "retrace_mismatch": "does not retrace the arrival",
    "route_not_stable": "not solely through its immutable adopted parent edge",
    "undelivered": "emitted and arrived proposals disagree",
    "origin_proposed": "and still proposed upward",
    "unattributable_source": "neither produced nor opened the branch for",
}


def _run_one(label, n_auth, density):
    """One fixture under whatever `_propose_upward` is currently installed."""
    o, _j, _slot, _victim, seed = H._damaged(n_auth, density=density)
    tr = H._run_traced(o)
    facts = H._assert_offers_return_through_adopted_edges(
        o, tr, label=f"{label} seed={seed}")
    return facts


def _attempt(label, n_auth, density):
    try:
        facts = _run_one(label, n_auth, density)
        return {"fixture": label, "outcome": "PASSED", "facts": facts}
    except AssertionError as exc:
        msg = str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
        clauses = sorted(k for k, s in ROUTE_CLAUSES.items() if s in str(exc))
        return {"fixture": label, "outcome": "FAILED",
                "failure_kind": "assertion",
                "route_clauses": clauses, "message": msg}
    except Exception as exc:                        # noqa: BLE001
        return {"fixture": label, "outcome": "FAILED",
                "failure_kind": f"{exc.__class__.__name__}",
                "route_clauses": [],
                "message": str(exc).splitlines()[0] if str(exc) else "",
                "traceback_tail": traceback.format_exc().splitlines()[-1]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-results", action="store_true",
                    help="re-run and require the committed JSON to match")
    args = ap.parse_args()

    report = {"instrument": "adopted_edge_return_negative_control",
              "oracle": "tests/unit/test_substrate_v5_single_flight_echo.py"
                        "::_assert_offers_return_through_adopted_edges",
              "fixtures": [f[0] for f in FIXTURES],
              "positive_control": [], "candidates": []}

    # POSITIVE CONTROL FIRST. A negative that fails against a runtime where
    # everything fails is not evidence.
    for label, n_auth, density in FIXTURES:
        report["positive_control"].append(_attempt(label, n_auth, density))

    original = v5.Unit._propose_upward
    for name, fn, why in CANDIDATES:
        entry = {"candidate": name, "defect": why, "runs": []}
        v5.Unit._propose_upward = fn
        try:
            for label, n_auth, density in FIXTURES:
                entry["runs"].append(_attempt(label, n_auth, density))
        finally:
            v5.Unit._propose_upward = original
        caught = [r for r in entry["runs"]
                  if r["outcome"] == "FAILED" and r["route_clauses"]]
        entry["caught_on"] = [r["fixture"] for r in caught]
        entry["route_clauses"] = sorted({c for r in caught
                                         for c in r["route_clauses"]})
        entry["verdict"] = "CAUGHT" if caught else "ESCAPED"
        report["candidates"].append(entry)

    # -- verdicts -----------------------------------------------------------
    failures = []
    if any(r["outcome"] != "PASSED" for r in report["positive_control"]):
        failures.append("the unmodified runtime does not satisfy the oracle, so "
                        "a failing negative control would prove nothing")
    escaped = [c["candidate"] for c in report["candidates"]
               if c["verdict"] != "CAUGHT"]
    if escaped:
        failures.append(f"broken candidates the test did not catch: {escaped}")
    all_clauses = sorted({c for e in report["candidates"]
                          for c in e["route_clauses"]})
    if "wrong_destination" not in all_clauses:
        failures.append("no candidate was rejected for sending its proposal to "
                        "the wrong unit; only edge ids were discriminated, so "
                        "the jump-to-origin attack was not actually tested")
    report["route_clauses_exercised"] = all_clauses
    report["failures"] = failures
    report["verdict"] = "CORRECT" if not failures else "INSUFFICIENT"

    if args.verify_results:
        if not RESULTS.exists():
            print(f"FAIL: {RESULTS.name} has never been recorded")
            return 1
        stored = json.loads(RESULTS.read_text())
        drift = [k for k in ("verdict", "route_clauses_exercised")
                 if stored.get(k) != report[k]]
        drift += [f"candidate:{c['candidate']}"
                  for c, s in zip(report["candidates"],
                                  stored.get("candidates", []))
                  if c["verdict"] != s.get("verdict")]
        if drift:
            print(f"FAIL: committed results no longer reproduce: {drift}")
            return 1
        print(f"OK: committed results reproduce ({report['verdict']})")
        return 0 if report["verdict"] == "CORRECT" else 1

    RESULTS.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    for c in report["candidates"]:
        print(f"{c['verdict']:8} {c['candidate']:28} "
              f"clauses={c['route_clauses'] or '-'} on={c['caught_on'] or '-'}")
    print(f"positive control: "
          f"{[r['outcome'] for r in report['positive_control']]}")
    print(f"verdict: {report['verdict']}")
    for f in failures:
        print(f"  {f}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
