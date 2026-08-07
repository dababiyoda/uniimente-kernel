#!/usr/bin/env python3
"""NC-0 — what actually proves an open root's obligation was satisfied elsewhere.

`_settle_pending_roots` skips any root whose `origin_slot` is already in
`self.bonds`, and the skip is silent: the root stays OPEN, no closure is
emitted, and every descendant keeps its parent's credit forever. Before any
runtime behaviour is written, this establishes the SMALLEST TRUTHFUL PREDICATE
that separates the seven states that skip currently conflates.

    python verification/phase3g/need_closure_diagnose.py
    python verification/phase3g/need_closure_diagnose.py --verify-results

Exits nonzero unless every recorded finding still holds. Results:
`NEED_CLOSURE_CAUSAL_DIAGNOSIS.json`.

This executes against the real runtime through the repository's own fixtures.
No mirrored model, no runtime file modified, no marker changed.

THE STATES, and why each needs a different answer:

  0   NOT_SKIPPED                 slot still unmet; the root is live.
  1   SAME_ROOT_COMMITTED         this root's own canonical settlement created
                                  the bond and the node records the accepted
                                  proposal. It won. Nothing is owed.
  2   SATISFIED_ELSEWHERE         same slot, same generation, NOT this root's
                                  canonical settlement -- `settled_from_search_offer`
                                  is False, so the legacy Need/Offer path filled
                                  the obligation while this root was in flight.
  2b  OBLIGATION_GENERATION_RETIRED
                                  `open_needs[slot]` no longer names this root's
                                  need_id, so `settle_search_offer` can only ever
                                  refuse with `wrong_need_generation`. The root
                                  can never settle anything again.
  3   UNRELATED_SLOT_BONDED       a bond exists for a different slot.
  4   STALE_GENERATION_BOND       the occupying bond was settled by an older
                                  need generation than this root serves.
  4a  BOND_WITHOUT_PROVENANCE     `settled_by` is empty; unattributable.
  5   LATER_GENERATION_EXISTS     the unit has already reopened past this root.
  6   ROOT_ALREADY_CLOSING        closure is in flight; do not restart it.
  7   ROOT_ALREADY_TERMINAL       nothing is owed.

2 and 2b are the closable set: both mean this root can never settle again, and
both leave descendants holding credit. A predicate that closes on 3, 4 or 5
destroys a live search; a predicate that refuses to close on 2 or 2b leaves the
liability stranded, which is the present behaviour.

MEASURED, and it is 2b rather than 2 that occurs. All three abandoned roots at
`_damaged(3, density=0.6)` have `open_needs[slot] is None` -- including the two
whose slot IS bonded by the legacy path. The generation test subsumes the bond
test, which is why it is evaluated first: whatever occupies the slot, a root
whose obligation generation has been retired is already unable to settle.
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

RESULTS = _HERE / "NEED_CLOSURE_CAUSAL_DIAGNOSIS.json"

FIXTURES = (("n_auth=4 density=1.0", 4, 1.0),
            ("n_auth=5 density=0.8", 5, 0.8),
            ("n_auth=3 density=0.6", 3, 0.6))

TERMINAL_STATUSES = ("COMMITTED", "EXHAUSTED", "CLOSED", "CANCELLED")


def classify_root(unit, key, node):
    """The seven states, decided from LOCAL state only.

    Every field read here belongs to the unit that owns the root. Nothing is
    read from the organ, from another unit, or from a global index: a predicate
    that needed global topology could not run inside the protocol it governs.
    """
    slot = key.origin_slot
    bond = unit.bonds.get(slot)
    facts = {
        "need_id": key.need_id,
        "work_item_generation": key.work_item_generation,
        "constraint_generation": key.constraint_generation,
        "origin_slot": slot,
        "node_status": node["status"],
        "accepted_proposal_id": node.get("accepted_proposal_id"),
        "terminal_signal_sent": node["terminal_signal_sent"],
        "slot_bonded": bond is not None,
        "bond_settled_by": getattr(bond, "settled_by", None) if bond else None,
        "bond_settled_item": getattr(bond, "settled_item", None) if bond else None,
        "bond_from_search_offer": getattr(bond, "settled_from_search_offer", None)
        if bond else None,
        "bond_supplier": getattr(bond, "supplier", None) if bond else None,
        "unit_local_activations": unit.local_activations,
        "open_need_for_slot": unit.open_needs.get(slot),
        "need_id_in_closed_needs": key.need_id in unit.closed_needs,
        "children_outstanding": len(node["children_outstanding"]),
        "proposals_outstanding": len(node["proposals_outstanding"]),
        "eligible_offer": bool(node.get("eligible_offer")),
        "holds_local_candidate": node.get("local_candidate") is not None,
        "credit_in_flight": node["child_allocations_in_flight"],
        "local_reserve": node["local_reserve"],
    }

    if node["status"] in TERMINAL_STATUSES or node["terminal_signal_sent"]:
        facts["state"] = "7_ROOT_ALREADY_TERMINAL"
        return facts
    if node["status"].startswith("CLOSING"):
        facts["state"] = "6_ROOT_ALREADY_CLOSING"
        return facts
    # THE OBLIGATION GENERATION THIS ROOT SERVES MUST STILL BE THE LIVE ONE.
    #
    # `settle_search_offer` refuses with `wrong_need_generation` unless
    # `open_needs[slot] == key.need_id`. So once the unit's open need for this
    # slot is cleared or replaced, this root can NEVER settle anything, whatever
    # arrives on it -- and it is checked before the bond, because a root whose
    # generation is already gone is abandoned regardless of what occupies the
    # slot. Measured: one such root, holding an outstanding proposal and 3.0
    # credit in flight, with no bond at all.
    live_need = unit.open_needs.get(slot)
    if live_need != key.need_id:
        facts["state"] = ("2b_OBLIGATION_GENERATION_RETIRED" if live_need is None
                          else "5_LATER_GENERATION_EXISTS")
        return facts

    if bond is None:
        facts["state"] = "0_NOT_SKIPPED_slot_still_unmet"
        return facts

    # The slot IS bonded and the generation is still live, which is the whole of
    # the present skip condition. Everything below is what the skip cannot tell
    # apart.
    settled_by = getattr(bond, "settled_by", "") or ""
    from_search = getattr(bond, "settled_from_search_offer", False)
    if not settled_by:
        # No provenance. The bond cannot be attributed to any need generation,
        # so it cannot prove THIS obligation was met.
        facts["state"] = "4a_BOND_WITHOUT_PROVENANCE"
        return facts
    owner, _, gen = settled_by.rpartition(":")
    b_unit, _, b_slot = owner.rpartition(":")
    if b_slot != str(slot) or b_unit != unit.unit_id:
        facts["state"] = "3_UNRELATED_SLOT_BONDED"
        return facts
    try:
        bond_gen, root_gen = int(gen), int(key.need_id.rpartition(":")[2])
    except ValueError:
        facts["state"] = "4a_BOND_WITHOUT_PROVENANCE"
        return facts
    facts["bond_generation"], facts["root_generation"] = bond_gen, root_gen
    if bond_gen < root_gen:
        facts["state"] = "4_STALE_GENERATION_BOND"
    elif bond_gen > root_gen:
        facts["state"] = "5_LATER_GENERATION_EXISTS"
    elif from_search and node.get("accepted_proposal_id"):
        # THIS root's own canonical settlement created the bond, and the node
        # records which proposal it accepted. The root won; nothing is owed.
        facts["state"] = "1_SAME_ROOT_COMMITTED"
    else:
        # Same slot, same generation -- and NOT this root's canonical
        # settlement. `settled_from_search_offer` is the discriminator the
        # runtime already records for exactly this question: False means the
        # legacy Need/Offer path filled the obligation while the canonical root
        # was still in flight. THE ONLY CLOSABLE CASE.
        facts["state"] = "2_SATISFIED_ELSEWHERE"
    return facts


def open_roots(o):
    """Every root a unit ORIGINATED that has not reached a terminal state."""
    out = []
    for u in o.units.values():
        for key, node in getattr(u, "canonical_searches", {}).items():
            if key.origin_unit != u.unit_id:
                continue
            out.append((u, key, node))
    return out


def liability_of(node):
    return (len(node["children_outstanding"])
            + len(node["proposals_outstanding"])
            + (1 if node.get("eligible_offer") else 0)
            + (1 if node.get("local_candidate") is not None else 0))


def run(n_auth, density):
    o, _j, _slot, _victim, seed = S._damaged(n_auth, density=density)
    v5.reset()
    o.run_item(S.PAYLOAD_B)
    roots, states = [], collections.Counter()
    for u, key, node in open_roots(o):
        f = classify_root(u, key, node)
        f["unit"] = u.unit_id
        f["descendant_liability"] = liability_of(node)
        states[f["state"]] += 1
        roots.append(f)
    # THE CLOSABLE SET. Both states mean the same operational fact: this root
    # can never settle anything again, because `settle_search_offer` refuses
    # unless `open_needs[slot] == key.need_id`. Whether the obligation was
    # filled by the legacy path, by this root's own settlement, or retired some
    # other way is provenance for the record -- it does not change what is owed.
    abandoned = [r for r in roots
                 if r["state"] in ("2_SATISFIED_ELSEWHERE",
                                   "2b_OBLIGATION_GENERATION_RETIRED")]
    return {
        "seed": seed,
        "open_roots": len(roots),
        "states": dict(sorted(states.items())),
        "alternate_satisfied_open_roots": len(abandoned),
        "abandoned_with_liability": sum(1 for r in abandoned
                                        if r["descendant_liability"] > 0),
        "abandoned_credit_in_flight": round(
            sum(r["credit_in_flight"] for r in abandoned), 6),
        "abandoned_with_proposals_outstanding": sum(
            1 for r in abandoned if r["proposals_outstanding"]),
        "abandoned_with_eligible_offer": sum(
            1 for r in abandoned if r["eligible_offer"]),
        "abandoned_with_local_candidate": sum(
            1 for r in abandoned if r["holds_local_candidate"]),
        "roots": roots,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-results", action="store_true")
    args = ap.parse_args()

    report = {"instrument": "need_closure_diagnose", "fixtures": {}}
    for label, n_auth, density in FIXTURES:
        report["fixtures"][label] = run(n_auth, density)

    sparse = report["fixtures"]["n_auth=3 density=0.6"]
    dense = report["fixtures"]["n_auth=4 density=1.0"]

    # -- NEGATIVE CONTROL ---------------------------------------------------
    # The predicate must be READING the live obligation generation, not
    # returning "abandoned" for every non-terminal root it sees. Restore each
    # root's own need_id as the unit's live open need -- the one condition under
    # which `settle_search_offer` would accept -- and every abandonment verdict
    # must vanish. A predicate that answered unconditionally would score
    # identically here, and this is what separates the two.
    restored = []
    for label, n_auth, density in FIXTURES:
        o, _j, _s, _v, seed = S._damaged(n_auth, density=density)
        v5.reset()
        o.run_item(S.PAYLOAD_B)
        for u, key, _node in open_roots(o):
            u.open_needs[key.origin_slot] = key.need_id
        n = collections.Counter()
        for u, key, node in open_roots(o):
            n[classify_root(u, key, node)["state"]] += 1
        restored.append({"fixture": label, "states": dict(sorted(n.items()))})
    generation_is_load_bearing = all(
        s["states"].get("2b_OBLIGATION_GENERATION_RETIRED", 0) == 0
        for s in restored)
    report["negative_control"] = {
        "candidate": "restore each root's need_id as the live open need",
        "restored": restored,
        "generation_is_load_bearing": generation_is_load_bearing,
    }

    findings = {
        "alternate_satisfied_open_roots_sparse":
            sparse["alternate_satisfied_open_roots"],
        "alternate_satisfied_open_roots_dense":
            dense["alternate_satisfied_open_roots"],
        "denominator_is_nonzero": sparse["alternate_satisfied_open_roots"] > 0,
        "every_abandoned_root_holds_liability":
            sparse["abandoned_with_liability"]
            == sparse["alternate_satisfied_open_roots"],
        "generation_is_load_bearing": generation_is_load_bearing,
        "states_observed": sorted({s for f in report["fixtures"].values()
                                   for s in f["states"]}),
    }
    report["findings"] = findings

    failures = []
    if not findings["denominator_is_nonzero"]:
        failures.append("no open root is provably satisfied elsewhere, so the "
                        "need-closure metric has an empty denominator and "
                        "nothing here can be verified")
    if not generation_is_load_bearing:
        failures.append("restoring the live open need did not change any verdict, "
                        "so the predicate is not reading the obligation "
                        "generation and would answer the same regardless")
    report["failures"] = failures
    report["verdict"] = "CORRECT" if not failures else "INSUFFICIENT"

    if args.verify_results:
        if not RESULTS.exists():
            print(f"FAIL: {RESULTS.name} has never been recorded")
            return 1
        stored = json.loads(RESULTS.read_text())
        drift = [k for k in ("verdict", "findings") if stored.get(k) != report[k]]
        if drift:
            print(f"FAIL: committed results no longer reproduce: {drift}")
            return 1
        print(f"OK: committed results reproduce ({report['verdict']})")
        return 0 if report["verdict"] == "CORRECT" else 1

    RESULTS.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    for label, f in report["fixtures"].items():
        print(f"{label:22} open_roots={f['open_roots']:3} "
              f"satisfied_elsewhere={f['alternate_satisfied_open_roots']:3} "
              f"with_liability={f['abandoned_with_liability']:3} "
              f"credit={f['abandoned_credit_in_flight']}")
        for s, n in f["states"].items():
            print(f"    {n:3}  {s}")
    print(f"generation load-bearing: {generation_is_load_bearing}")
    print(f"verdict: {report['verdict']}")
    for f in failures:
        print(f"  {f}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
