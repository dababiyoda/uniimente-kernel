"""Reviewed verifiers a repository work order may name for the artifact it delivers (``worker.appraise``).

A work order's frozen acceptance may say ``"verifiers": [{"name": ..., "artifact": ..., "problem": ...}]``. The
appraiser then runs the named verifier here on GREG's own copies: the problem as it stood at the recorded base
commit, the artifact as the retained patch delivers it in GREG's fresh clone, both read before any worker code
runs there. The worker's tests, report and tree are never consulted, so a worker whose own test asserts its own
wrong answer (a coherent lie) is still refused.

Each verifier returns findings (empty when the artifact holds). It shares no code with the method that produced
the answer: ``assignment.staffing`` checks feasibility here and the optimum with the exhaustive Hall/Koenig oracle
(``greg.recombine.staffing_brute_force``), never the max-flow engine the Mind's construction runs on; it is the
check ``scripts/verify_one_machine.py`` applies to the Mind's answer, applied to the delivered plan.

Lineage: R1-A (#190, ``INTENT-20261019-UPWARD-ASCENT``), recombining #178's independent re-derivation
(``verify_one_machine``) with the appraiser. Limit: the oracle is exponential in the number of orders, so a problem
with more than ``MAX_EXHAUSTIVE_ORDERS`` orders is refused, never assumed optimal.
"""
from __future__ import annotations

import json

MAX_EXHAUSTIVE_ORDERS = 16


def canonical(value) -> str:
    """The canonical JSON normalisation two values are compared in (sorted keys, no insignificant whitespace)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def staffing_plan(artifact, problem) -> list[str]:
    """``assignment.staffing``: the plan is feasible for the problem, its total is its own, and no plan staffs more."""
    from greg.recombine import ReductionError, normalize_staffing, staffing_brute_force
    try:
        p = normalize_staffing(problem)
    except (ReductionError, ValueError, TypeError, KeyError) as exc:
        return [f"the problem is not a staffing problem the verifier can read: {str(exc)[:200]}"]
    if not isinstance(artifact, dict) or not isinstance(artifact.get("assignment"), list):
        return ["the artifact carries no assignment list"]
    capacity, demand = dict(map(tuple, p["workers"])), dict(map(tuple, p["orders"]))
    used, filled, seen, findings = {}, {}, set(), []
    for item in artifact["assignment"]:
        if not isinstance(item, list) or len(item) != 3:
            return [f"assignment entry {str(item)[:80]} is not [worker, order, units]"]
        w, o, x = item
        if not isinstance(w, str) or not isinstance(o, str) or (w, o) in seen or o not in demand \
                or w not in p["eligible"][o]:
            return [f"{str(w)[:40]} is not eligible for {str(o)[:40]}, or the pair repeats"]
        if isinstance(x, bool) or not isinstance(x, int) or x <= 0:
            return [f"units of {w} on {o} are not a positive integer"]
        seen.add((w, o))
        used[w] = used.get(w, 0) + x
        filled[o] = filled.get(o, 0) + x
    findings += [f"{w} is assigned {u}, above capacity {capacity[w]}" for w, u in used.items() if u > capacity[w]]
    findings += [f"{o} is filled {f}, above demand {demand[o]}" for o, f in filled.items() if f > demand[o]]
    staffed = artifact.get("staffed")
    if staffed != sum(filled.values()):
        findings.append(f"staffed {str(staffed)[:20]} is not the assignment's own total {sum(filled.values())}")
    if len(demand) > MAX_EXHAUSTIVE_ORDERS:
        return findings + [f"{len(demand)} orders exceed the exhaustive verifier's {MAX_EXHAUSTIVE_ORDERS}; "
                           "optimality cannot be re-derived, so it is not assumed"]
    best = staffing_brute_force(p)
    if staffed != best:
        findings.append(f"staffed {str(staffed)[:20]} but the exhaustive optimum of the problem is {best}")
    return findings


VERIFIERS = {"assignment.staffing": staffing_plan}
