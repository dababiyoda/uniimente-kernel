"""5K-T1: four-mode factorial audit of the five regressed cases.

AUDIT HARNESS ONLY. It imports the runtime, patches it inside a scoped context
manager, restores it, and writes evidence. It changes no runtime file, no active
test, and no marker, and it draws no conclusions -- classification belongs to
the evidence commit that reads this output.

WHY FOUR MODES. Two independent honest-evidence changes -- 5G (canonical
lifecycle as the sole record, outcome-only projection) and 5L (role-based
channel classification) -- each produced the SAME five regressions. A single
mode cannot say whether they share one cause, have two causes that coincide, or
interact. The factorial separates them:

    MODE 00   kind-first classification  + dual-written projection   (head)
    MODE 10   ROLE classification        + dual-written projection
    MODE 01   kind-first classification  + outcome-only projection
    MODE 11   ROLE classification        + outcome-only projection

Every mode runs identical seeds, topology, damage, credit and scheduler
ordering against a freshly built organ with freshly reset counters, so a
difference between modes is caused by the patch and by nothing else.
"""
from __future__ import annotations

import contextlib
import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "verification" / "phase3g"))

import substrate.v5 as v5
from substrate.v5 import C, ENV, SINK, reset

import fixtures as F

PAYLOAD_A = "  Claim-77  "
PAYLOAD_B = "  Claim-78  "
SEEDS = tuple(range(60))


# ---------------------------------------------------------------------------
# The two candidate semantics, applied as scoped patches. NEVER committed to
# the runtime by this file.
# ---------------------------------------------------------------------------

def _role(unit, edge_id):
    o = unit._organ
    rec = o.search_edge_probes.get(edge_id) if o is not None else None
    if rec is None:
        return ""
    if rec.get("from_unit") == unit.unit_id:
        return "opener"
    if rec.get("to_unit") == unit.unit_id:
        return "receiver"
    return ""


@contextlib.contextmanager
def mode(role_classification: bool, outcome_only_projection: bool):
    """Patch, yield, restore. Restoration is unconditional."""
    orig_record = v5.Unit._record_terminal
    orig_control = v5.Unit._record_control

    def patched_record_terminal(self, t):
        if role_classification:
            r = _role(self, t.edge_id)
            if r == "opener":
                return self._record_control(t)
            if r == "receiver":
                return self._record_outcome(t)
        if t.kind in v5.PARENT_CONTROL_KINDS:
            return self._record_control(t)
        return self._record_outcome(t)

    def patched_record_control(self, t):
        """5G: the control path stops writing the compatibility projection."""
        o = self._organ
        if o is None:
            return False
        rec = self._lifecycle_record(t)
        first = rec["accepted_control"]
        if first is not None:
            if first.kind != t.kind:
                rec["control_conflicts"].append((t.edge_id, first.kind, t.kind))
                o.search_edge_terminal_conflicts.append(
                    (t.edge_id, first.kind, t.kind))
            return False
        rec["controls"].append(t)
        rec["accepted_control"] = t
        C.incr("SEARCH_CONTROLS_RECORDED")
        return True

    v5.Unit._record_terminal = patched_record_terminal
    if outcome_only_projection:
        v5.Unit._record_control = patched_record_control
    try:
        yield
    finally:
        v5.Unit._record_terminal = orig_record
        v5.Unit._record_control = orig_control


# ---------------------------------------------------------------------------
# Fixtures, byte-identical to the ones the regressed cases use.
# ---------------------------------------------------------------------------

def _build_raw(n_auth=4, seed=7, density=0.8):
    caps = F._spine("alpha2") + F._spine("beta2") + F._spine("gamma2")
    for i in range(n_auth):
        caps.append(F.cap(f"au{i}", ("PX", "PX"), "AUTH", F.AUTHORISE,
                          1.0 + 0.1 * i, f"d.a{i}", "authorise", F.OK_PRICE))
    caps.append(F.cap("rn0", ("AUTH", "AUTH"), "RECON", F.RECONCILE,
                      1.0, "d.p", "reconcile", F.OK_AUTH))
    caps.append(F.cap("db0", ("RECON",), "VERDICT", F.DISBURSE,
                      1.0, "d.r", "disburse", F.OK_RECON))
    return F._organ(caps, random.Random(seed), density)


def _join(o, want="AUTH"):
    for u in o.units.values():
        if u.capability.accepts.count(want) == 2:
            return u
    return None


def _damaged(n_auth=4, density=0.8):
    for seed in SEEDS:
        o = _build_raw(n_auth, seed, density)
        F.prepare(o)
        reset()
        o.commission()
        if not o.result_ok(o.run_item(PAYLOAD_A)):
            continue
        j = _join(o)
        if j is None or len(j.bonds) != 2:
            continue
        if len({b.supplier for b in j.bonds.values()}) != 2:
            continue
        slot = min(j.bonds)
        victim = j.bonds[slot].supplier
        o.units[victim].silent = True
        return o, j, slot, victim, seed
    raise AssertionError("no formed independently-supplied join")


# ---------------------------------------------------------------------------
# Observation. Reports; asserts nothing.
# ---------------------------------------------------------------------------

def _observe(o, j):
    lc = getattr(o, "search_edge_lifecycle", {}) or {}
    probes = o.search_edge_probes
    proj = getattr(o, "search_edge_terminals", {}) or {}
    nodes = {(u.unit_id, k): n for u in o.units.values()
             for k, n in getattr(u, "canonical_searches", {}).items()}

    # THE STALE-PROJECTION PROBE. `_per_key_edge_uniqueness` requires exactly
    # one item in the legacy `outcomes` array for EVERY probed edge. Counted
    # here without asserting, so the audit can say how many edges that helper
    # would reject and why.
    legacy_violations = []
    for eid in probes:
        outs = proj.get(eid, {}).get("outcomes", [])
        if len(outs) != 1:
            rec = lc.get(eid) or {}
            legacy_violations.append({
                "edge": eid,
                "legacy_outcome_count": len(outs),
                "accepted_control": getattr(rec.get("accepted_control"), "kind", None),
                "accepted_outcome": getattr(rec.get("accepted_outcome"), "kind", None),
            })

    lineage_depth = max([len(n["lineage"]) for n in nodes.values()] or [0])
    return {
        # structural convergence -- test A's real core
        "UNIQUE_CANONICAL_SEARCH_NODES": C["UNIQUE_CANONICAL_SEARCH_NODES"],
        "CANONICAL_SEARCH_EXPANSIONS": C["CANONICAL_SEARCH_EXPANSIONS"],
        "DUPLICATE_SUBTREES_OPENED": C["DUPLICATE_SUBTREES_OPENED"],
        "COALESCED_DUPLICATE_ARRIVALS": C["COALESCED_DUPLICATE_ARRIVALS"],
        "DIRECTED_SEARCH_EDGES_PROBED": C["DIRECTED_SEARCH_EDGES_PROBED"],
        "duplicate_probe_ids": sum(1 for r in probes.values() if r["count"] != 1),
        # closure evidence -- the honest question
        "edges_total": len(probes),
        "edges_with_accepted_control": sum(
            1 for r in lc.values() if r["accepted_control"] is not None),
        "edges_with_accepted_outcome": sum(
            1 for r in lc.values() if r["accepted_outcome"] is not None),
        "lifecycle_conflicts": sum(
            len(r["control_conflicts"]) + len(r["outcome_conflicts"])
            for r in lc.values()),
        # the stale helper's verdict, observed rather than asserted
        "legacy_helper_violations": len(legacy_violations),
        "legacy_helper_detail": legacy_violations[:8],
        # lineage / cycle -- test_lineage's two independent claims
        "max_lineage_depth": lineage_depth,
        "CYCLE_EDGES_CLOSED": C["CYCLE_EDGES_CLOSED"],
        # amplification -- test J
        "messages": o.messages,
        "events": o.events_dispatched,
        "restored": bool(o.result_ok(o.run_item(PAYLOAD_B))) if False else None,
        # duplicate-work detectors: any nonzero forbids calling growth lawful
        "ORPHANED_SEARCH_EDGES": C["ORPHANED_SEARCH_EDGES"],
        "LEGACY_REPAIR_NEED_MESSAGES": C["LEGACY_REPAIR_NEED_MESSAGES"],
        "UNAUTHORIZED_EXTERNAL_EFFECTS": C["UNAUTHORIZED_EXTERNAL_EFFECTS"],
        "INHERITED_AUTHORITY_EVENTS": C["INHERITED_AUTHORITY_EVENTS"],
        "UNSUPPORTED_CHILD_CANCELLATION_CREDIT":
            C["UNSUPPORTED_CHILD_CANCELLATION_CREDIT"],
        "PARENT_CONTROLS_APPLIED": C["PARENT_CONTROLS_APPLIED"],
        "PARENT_CONTROLS_WITH_CHILD_OWNED_COMPLETION":
            C["PARENT_CONTROLS_WITH_CHILD_OWNED_COMPLETION"],
        "nodes_with_children_outstanding": sum(
            1 for n in nodes.values() if n["children_outstanding"]),
    }


def _run_case(density, role_cls, proj_only):
    """One fixture, one mode. Fresh organ, fresh counters, identical seeds."""
    with mode(role_cls, proj_only):
        o, j, slot, victim, seed = _damaged(4, density=density)
        reset()
        o.run_item(PAYLOAD_B)
        out = _observe(o, j)
        out["seed"] = seed
        return out


def main():
    matrix = {}
    modes = [("00", False, False), ("10", True, False),
             ("01", False, True), ("11", True, True)]
    for density in (0.8, 0.9, 1.0):
        for name, role_cls, proj_only in modes:
            key = f"density={density}/MODE_{name}"
            matrix[key] = _run_case(density, role_cls, proj_only)
            print(f"{key}: msgs={matrix[key]['messages']} "
                  f"legacy_violations={matrix[key]['legacy_helper_violations']} "
                  f"lineage={matrix[key]['max_lineage_depth']} "
                  f"cycles={matrix[key]['CYCLE_EDGES_CLOSED']} "
                  f"outcomes={matrix[key]['edges_with_accepted_outcome']}"
                  f"/{matrix[key]['edges_total']} "
                  f"dupes={matrix[key]['DUPLICATE_SUBTREES_OPENED']}")
    dest = ROOT / "verification" / "phase3g" / "CLOSURE_TRUTH_AUDIT.json"
    dest.write_text(json.dumps(matrix, indent=2, sort_keys=True, default=str))
    print(f"\nwritten -> {dest.relative_to(ROOT)}")
    # RESTORATION PROOF. If a patch leaked, everything after this file runs
    # against a runtime nobody committed.
    assert v5.Unit._record_terminal.__name__ == "_record_terminal", (
        "a mode patch leaked out of its context manager")
    assert v5.Unit._record_control.__name__ == "_record_control", (
        "a mode patch leaked out of its context manager")
    print("runtime restored: _record_terminal and _record_control are original")


if __name__ == "__main__":
    main()
