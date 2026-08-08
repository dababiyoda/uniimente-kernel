#!/usr/bin/env python3
"""NC-4A/4B — who retires each need generation, and by what authority.

NC-3 closes a root whose obligation generation is no longer current, and records
the reason `need_satisfied_elsewhere`. That reason is OVERBROAD. The predicate
proves the root can no longer settle; it does not prove why the generation was
retired. The counterexample is already in the fixture:

    reconcile.12:0:1    slot_bonded = false
                        closure_reason = need_satisfied_elsewhere

This traces every retirement to the function that performed it, classifies the
cause from repository evidence, and measures whether the LEGACY repair ledger
still holds authority to retire a CANONICAL repair root.

    python verification/phase3g/root_retirement_authority.py
    python verification/phase3g/root_retirement_authority.py --verify-results

Exits nonzero unless every recorded finding still holds. Results:
`ROOT_RETIREMENT_AUTHORITY.json`.

THE STRUCTURAL CONCERN, from reading the runtime rather than from the trace:

    _emit_need          writes open_needs[slot] = nid
                        AND creates self._search[nid], the LEGACY ledger
    step()              iterates open_needs, calls widen(slot) against that
                        legacy ledger, then _prove_exhaustion(slot, nid)
    _prove_exhaustion   pops open_needs[slot] and adds nid to closed_needs

So a canonical repair root carries a legacy ledger shadowing it, and that legacy
ledger can retire the canonical generation. Legacy repair MESSAGES were disabled
by the migration; legacy repair RETIREMENT AUTHORITY was not. One canonical
authority is a constitutional requirement, so this is measured, not assumed.

No runtime file is modified. Every wrapper installed below is disposable and
removed in a `finally`.
"""
from __future__ import annotations

import argparse
import collections
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
import test_substrate_v5_control_outcome_separation as S        # noqa: E402

RESULTS = _HERE / "ROOT_RETIREMENT_AUTHORITY.json"

FIXTURES = (("n_auth=4 density=1.0", 4, 1.0),
            ("n_auth=5 density=0.8", 5, 0.8),
            ("n_auth=3 density=0.6", 3, 0.6))

# The vocabulary. A cause is added only when repository evidence requires it,
# and distinct causes are never collapsed.
CAUSES = (
    "SATISFIED_BY_ALTERNATE_BOND",     # another path bonded the slot
    "CANONICAL_ROOT_COMMITTED",        # this root's own settlement
    "LEGACY_SEARCH_EXHAUSTED",         # _prove_exhaustion on the legacy ledger
    "CANONICAL_SEARCH_EXHAUSTED",      # the canonical root proved exhaustion
    "SUPERSEDED_BY_LATER_GENERATION",  # open_needs replaced, not deleted
    "ORIGINATION_REFUSED",             # _open_repair_root returned None
    "EXPLICIT_OPERATOR_CLOSURE",
    "UNKNOWN_RETIREMENT_CAUSE",
)

# Which authority each retiring function belongs to. Read from the call site,
# not inferred from the name.
AUTHORITY = {
    "_settle": "CANONICAL_OR_LEGACY_SETTLEMENT",   # shared: both paths reach it
    "_prove_exhaustion": "LEGACY_REPAIR",
    "_emit_need_origination_refused": "CANONICAL_REPAIR",
    "_emit_need_replacement": "CANONICAL_REPAIR",
}


def trace_run(n_auth, density):
    """One run, with every `open_needs` retirement attributed to its performer."""
    events: list[dict] = []
    o, _j, _slot, _victim, seed = S._damaged(n_auth, density=density)

    # WRAP THE DICT, NOT THE FUNCTIONS. A function wrapper records who was
    # CALLED; this records what was actually DONE to open_needs, so a retirement
    # through a path nobody thought to wrap still appears.
    class _TracedNeeds(dict):
        def __init__(self, owner, *a):
            super().__init__(*a)
            self._owner = owner

        def _stack(self):
            # Nearest substrate frame that is not this class.
            for fr in reversed(traceback.extract_stack()[:-2]):
                if fr.filename.endswith("v5.py"):
                    return fr.name
            return "<unknown>"

        def pop(self, key, *a):
            had = self.get(key)
            out = super().pop(key, *a)
            if had is not None:
                events.append({"unit": self._owner, "slot": key,
                               "need_id": had, "op": "pop",
                               "performed_by": self._stack()})
            return out

        def __setitem__(self, key, value):
            had = self.get(key)
            super().__setitem__(key, value)
            if had is not None and had != value:
                events.append({"unit": self._owner, "slot": key,
                               "need_id": had, "op": "replace",
                               "replaced_by": value,
                               "performed_by": self._stack()})

        def __delitem__(self, key):
            had = self.get(key)
            super().__delitem__(key)
            if had is not None:
                events.append({"unit": self._owner, "slot": key,
                               "need_id": had, "op": "del",
                               "performed_by": self._stack()})

    for u in o.units.values():
        u.open_needs = _TracedNeeds(u.unit_id, u.open_needs)

    v5.reset()
    o.run_item(S.PAYLOAD_B)
    return o, seed, events


def classify(o, ev):
    """The cause of one retirement, from evidence rather than from the reason
    string the runtime happens to have written."""
    unit = o.units.get(ev["unit"])
    slot, nid = ev["slot"], ev["need_id"]
    by = ev["performed_by"]
    bond = unit.bonds.get(slot) if unit else None
    ev["bond_after"] = getattr(bond, "settled_by", None) if bond else None
    ev["bond_from_search_offer"] = (
        getattr(bond, "settled_from_search_offer", None) if bond else None)
    ev["authority"] = AUTHORITY.get(by, "UNCLASSIFIED_AUTHORITY")

    if ev["op"] == "replace":
        return "SUPERSEDED_BY_LATER_GENERATION"
    if by == "_prove_exhaustion":
        return "LEGACY_SEARCH_EXHAUSTED"
    if by == "_emit_need":
        return "ORIGINATION_REFUSED"
    if by == "_settle":
        if bond is None:
            return "UNKNOWN_RETIREMENT_CAUSE"
        if getattr(bond, "settled_from_search_offer", False) \
                and getattr(bond, "settled_by", "") == nid:
            return "CANONICAL_ROOT_COMMITTED"
        return "SATISFIED_BY_ALTERNATE_BOND"
    return "UNKNOWN_RETIREMENT_CAUSE"


def legacy_authority_probe(n_auth, density):
    """Does a CORRUPTED legacy ledger change canonical repair?

    The legacy repair ledger is meant to be inert after the migration. If
    falsifying it changes the canonical outcome, the legacy path still holds
    decision authority over canonical repair, whatever the message counters say.
    """
    out = {}
    for name, mutate in (
            ("baseline", None),
            ("legacy_ledger_emptied", lambda u: u._search.clear()),
            ("legacy_marked_settled",
             lambda u: [st.__setitem__("settled", True) for st in u._search.values()]),
            ("legacy_marked_closed",
             lambda u: [st.__setitem__("closed", True) for st in u._search.values()]),
    ):
        o, _j, _s, _v, _seed = S._damaged(n_auth, density=density)
        v5.reset()
        if mutate is not None:
            orig_step = v5.Unit.step

            def step(self, caps, _m=mutate, _o=orig_step):
                _m(self)                       # corrupt just before every step
                return _o(self, caps)
            v5.Unit.step = step
            try:
                o.run_item(S.PAYLOAD_B)
            finally:
                v5.Unit.step = orig_step
        else:
            o.run_item(S.PAYLOAD_B)
        roots = {f"{u.unit_id}|{k.need_id}": n["status"]
                 for u in o.units.values()
                 for k, n in getattr(u, "canonical_searches", {}).items()
                 if k.origin_unit == u.unit_id}
        out[name] = {
            "canonical_roots": dict(sorted(roots.items())),
            "messages": o.messages,
            "closed_child_edges": sum(
                1 for e in o.search_edge_lifecycle.values()
                if e.get("accepted_outcome") is not None),
            "legacy_repair_need_messages": v5.C["LEGACY_REPAIR_NEED_MESSAGES"],
        }
    base = out["baseline"]
    out["canonical_repair_is_independent_of_legacy_ledger"] = all(
        out[k]["canonical_roots"] == base["canonical_roots"]
        for k in out if k != "baseline" and isinstance(out[k], dict))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-results", action="store_true")
    args = ap.parse_args()

    report = {"instrument": "root_retirement_authority", "fixtures": {}}
    for label, n_auth, density in FIXTURES:
        o, seed, events = trace_run(n_auth, density)
        causes, authorities = collections.Counter(), collections.Counter()
        for ev in events:
            ev["cause"] = classify(o, ev)
            causes[ev["cause"]] += 1
            authorities[ev["authority"]] += 1
        # Which retirements hit a canonical root that was still live?
        canonical_hit = 0
        for ev in events:
            unit = o.units.get(ev["unit"])
            for k, n in getattr(unit, "canonical_searches", {}).items():
                if k.need_id == ev["need_id"] and k.origin_unit == ev["unit"] \
                        and n.get("closure_reason"):
                    canonical_hit += 1
                    ev["retired_a_canonical_root"] = True
                    break
        report["fixtures"][label] = {
            "seed": seed,
            "retirements": len(events),
            "causes": dict(sorted(causes.items())),
            "authorities": dict(sorted(authorities.items())),
            "retirements_that_closed_a_canonical_root": canonical_hit,
            "events": events,
        }

    report["legacy_authority_probe"] = legacy_authority_probe(3, 0.6)

    sparse = report["fixtures"]["n_auth=3 density=0.6"]
    legacy_retirements = sum(
        n for f in report["fixtures"].values()
        for c, n in f["causes"].items() if c == "LEGACY_SEARCH_EXHAUSTED")
    canonical_roots_by_legacy = sum(
        1 for f in report["fixtures"].values() for ev in f["events"]
        if ev.get("retired_a_canonical_root")
        and ev["cause"] == "LEGACY_SEARCH_EXHAUSTED")
    unattributed = sum(
        n for f in report["fixtures"].values()
        for c, n in f["causes"].items() if c == "UNKNOWN_RETIREMENT_CAUSE")

    findings = {
        "ROOT_GENERATIONS_RETIRED": sum(f["retirements"]
                                        for f in report["fixtures"].values()),
        "ROOT_RETIREMENTS_WITH_UNATTRIBUTED_CAUSE": unattributed,
        "LEGACY_SEARCH_EXHAUSTED_retirements": legacy_retirements,
        "CANONICAL_ROOTS_RETIRED_BY_LEGACY_AUTHORITY": canonical_roots_by_legacy,
        "causes_observed": sorted({c for f in report["fixtures"].values()
                                   for c in f["causes"]}),
        "sparse_causes": sparse["causes"],
        "canonical_repair_is_independent_of_legacy_ledger":
            report["legacy_authority_probe"][
                "canonical_repair_is_independent_of_legacy_ledger"],
    }
    report["findings"] = findings

    failures = []
    if findings["ROOT_GENERATIONS_RETIRED"] == 0:
        failures.append("no need generation was retired in any fixture, so the "
                        "denominator is empty and nothing here is measured")
    if unattributed:
        failures.append(f"{unattributed} retirement(s) have no attributable "
                        f"cause; a closure reason cannot be truthful without one")
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
        print(f"{label:22} retirements={f['retirements']:3} "
              f"closed_a_canonical_root={f['retirements_that_closed_a_canonical_root']}")
        for c, n in f["causes"].items():
            print(f"    {n:3}  {c}")
    print(f"canonical roots retired by LEGACY authority: {canonical_roots_by_legacy}")
    print(f"canonical repair independent of legacy ledger: "
          f"{findings['canonical_repair_is_independent_of_legacy_ledger']}")
    print(f"verdict: {report['verdict']}")
    for f in failures:
        print(f"  {f}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
