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

# AUDIT INSTRUMENTATION. Populated by the corrected classifier; read by the
# evidence report. Not counters on `C`, because these describe the AUDIT, not
# the runtime.
AUDIT = {}


def _audit_reset():
    AUDIT.clear()
    AUDIT.update({
        "AUDIT_CONTROL_CLASSIFICATIONS": 0,
        "AUDIT_OUTCOME_CLASSIFICATIONS": 0,
        "AUDIT_CLASSIFICATIONS_BY_AUTHOR_DIRECTION": 0,
        "AUDIT_CLASSIFICATIONS_BY_RECORDER_IDENTITY": 0,
        "AUDIT_UNCLASSIFIABLE_EDGE_MESSAGES": 0,
        "AUDIT_OBSERVED_CHILD_OUTCOMES": 0,
        "AUDIT_OBSERVED_CHILD_OUTCOMES_CLASSIFIED_AS_CONTROL": 0,
        "records": [],
    })


def _classify(unit, t):
    """CHANNEL FOLLOWS THE AUTHENTICATED AUTHOR AND DIRECTION.

    THE DEFECT THIS REPLACES, which was mine. The first harness asked
    `_role(self, edge_id)` -- whether the Unit OBJECT executing the recording is
    the edge's opener or receiver. That is not the evidence author. In
    `deliver_terminal` the PARENT observes a child's closure and calls

        self._record_terminal(Terminal(kind, key, edge_id, credited, 0.0,
                                       node["child_targets"][edge_id],  # child
                                       self.unit_id, ...))              # parent

    so the recorder is the opener while the author is the receiver. Classifying
    from `self.unit_id` therefore routed a child-authored outcome into the
    control channel -- which is exactly how one edge came to hold
    `accepted_control = SearchCycleClosed` AND
    `accepted_outcome = SearchCycleClosed`, a pair that cannot both be true.

    The rule compares the terminal's endpoints against the SENDER-CREATED probe:

        from == probe.from and to == probe.to   -> CONTROL   (opener -> receiver)
        from == probe.to   and to == probe.from -> OUTCOME   (receiver -> opener)

    Anything else is UNCLASSIFIABLE and mutates nothing: defaulting by kind is
    what this audit exists to stop. An empty destination is resolved from the
    author alone, because the runtime legitimately records an outcome it does
    not deliver.
    """
    o = unit._organ
    probe = o.search_edge_probes.get(t.edge_id) if o is not None else None
    rec = {"recorder_unit": unit.unit_id, "kind": t.kind, "edge_id": t.edge_id,
           "terminal_from": t.from_unit, "terminal_to": t.to_unit,
           "probe_from": (probe or {}).get("from_unit"),
           "probe_to": (probe or {}).get("to_unit"),
           "observation": t.from_unit != unit.unit_id}
    if probe is None or (probe.get("search_key") != t.search_key):
        AUDIT["AUDIT_UNCLASSIFIABLE_EDGE_MESSAGES"] += 1
        rec["selected_channel"] = None
        AUDIT["records"].append(rec)
        return None
    pf, pt = probe.get("from_unit"), probe.get("to_unit")
    if t.from_unit == pf and (t.to_unit == pt or not t.to_unit):
        channel = "CONTROL"
    elif t.from_unit == pt and (t.to_unit == pf or not t.to_unit):
        channel = "OUTCOME"
    else:
        AUDIT["AUDIT_UNCLASSIFIABLE_EDGE_MESSAGES"] += 1
        rec["selected_channel"] = None
        AUDIT["records"].append(rec)
        return None
    AUDIT["AUDIT_CLASSIFICATIONS_BY_AUTHOR_DIRECTION"] += 1
    if channel == "CONTROL":
        AUDIT["AUDIT_CONTROL_CLASSIFICATIONS"] += 1
    else:
        AUDIT["AUDIT_OUTCOME_CLASSIFICATIONS"] += 1
    # A child outcome the PARENT is recording: the case the old classifier got
    # wrong. Counted so "we no longer classify from recorder identity" is
    # measured rather than asserted.
    if rec["observation"] and channel == "OUTCOME":
        AUDIT["AUDIT_OBSERVED_CHILD_OUTCOMES"] += 1
    if rec["observation"] and channel == "CONTROL" and t.kind in v5.CHILD_OUTCOME_KINDS:
        AUDIT["AUDIT_OBSERVED_CHILD_OUTCOMES_CLASSIFIED_AS_CONTROL"] += 1
    rec["selected_channel"] = channel
    AUDIT["records"].append(rec)
    return channel


@contextlib.contextmanager
def mode(role_classification: bool, outcome_only_projection: bool):
    """Patch, yield, restore. Restoration is unconditional."""
    orig_record = v5.Unit._record_terminal
    orig_control = v5.Unit._record_control

    def patched_record_terminal(self, t):
        if role_classification:
            channel = _classify(self, t)
            if channel == "CONTROL":
                return self._record_control(t)
            if channel == "OUTCOME":
                return self._record_outcome(t)
            return False        # unclassifiable: mutate NEITHER channel
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


def _exact_assertions(o, msgs_before=0):
    """RETIRED AS A CLASSIFICATION AUTHORITY. Preserved as evidence, not deleted.

    The docstring below was wrong in the way that matters, and the error is
    worth keeping legible. These assertions are not "the exact assertions" of
    the five cases: they are RE-IMPLEMENTATIONS of them against a fixture this
    file builds. A re-implementation can diverge from the test it imitates
    without anything reporting that it has, and this one did -- it reported
    `A.coalesced_positive` failing at head, where `test_A` passes, and evaluated
    `LIN.cycle_closed_positive` at densities `test_lineage` never uses.

    Superseded by `CLOSURE_TRUTH_EXACT_EXECUTION.json/.md`, which runs the real
    pytest node IDs in disposable worktrees and reads pytest's own verdicts out
    of the JUnit XML pytest wrote. That audit found all five of these cases
    passing under every candidate -- so the regression set this function was
    built to explain did not exist.

    Nothing here may be cited to classify a test. It remains callable, and its
    output remains recorded, as the record of how a mirrored harness produces
    confident wrong answers.

    --- original docstring, retained verbatim ---

    THE EXACT ASSERTIONS of the five formerly regressed cases, executed
    rather than approximated. Each is evaluated and recorded pass/fail with its
    observed value; none of them raises, because the audit reports and does not
    judge."""
    lc = getattr(o, "search_edge_lifecycle", {}) or {}
    proj = getattr(o, "search_edge_terminals", {}) or {}
    probes = o.search_edge_probes
    nodes = {(u.unit_id, k): n for u in o.units.values()
             for k, n in getattr(u, "canonical_searches", {}).items()}
    res = {}

    def rec(name, ok, observed):
        res[name] = {"pass": bool(ok), "observed": observed}

    # --- test_A convergence core -------------------------------------------
    rec("A.nodes_exist", C["UNIQUE_CANONICAL_SEARCH_NODES"] > 0,
        C["UNIQUE_CANONICAL_SEARCH_NODES"])
    rec("A.expansions_eq_nodes",
        C["CANONICAL_SEARCH_EXPANSIONS"] == C["UNIQUE_CANONICAL_SEARCH_NODES"],
        [C["CANONICAL_SEARCH_EXPANSIONS"], C["UNIQUE_CANONICAL_SEARCH_NODES"]])
    rec("A.no_duplicate_subtree", C["DUPLICATE_SUBTREES_OPENED"] == 0,
        C["DUPLICATE_SUBTREES_OPENED"])
    rec("A.coalesced_positive", C["COALESCED_DUPLICATE_ARRIVALS"] > 0,
        C["COALESCED_DUPLICATE_ARRIVALS"])
    rec("A.probe_count_one",
        all(r["count"] == 1 for r in probes.values()),
        sorted({r["count"] for r in probes.values()}))

    # --- THE SHARED STALE HELPER, executed exactly ---------------------------
    bad = {e: len(proj.get(e, {}).get("outcomes", [])) for e in probes
           if len(proj.get(e, {}).get("outcomes", [])) != 1}
    rec("SHARED.legacy_outcomes_len_eq_1", not bad, bad)

    # --- test_lineage -------------------------------------------------------
    depth = max([len(n["lineage"]) for n in nodes.values()] or [0])
    rec("LIN.nodes_exist", bool(nodes), len(nodes))
    rec("LIN.max_lineage_depth_ge_2", depth >= 2, depth)
    rec("LIN.cycle_closed_positive", C["CYCLE_EDGES_CLOSED"] > 0,
        C["CYCLE_EDGES_CLOSED"])
    cyc_canonical = [e for e, r in lc.items()
                     if getattr(r.get("accepted_outcome"), "kind", None)
                     == "SearchCycleClosed"]
    cyc_legacy = [e for e, r in proj.items()
                  if any(getattr(x, "kind", x) == "SearchCycleClosed"
                         for x in r.get("outcomes", []))]
    rec("LIN.cycle_edge_found_canonically", bool(cyc_canonical), cyc_canonical)
    rec("LIN.cycle_edge_found_in_legacy", bool(cyc_legacy), cyc_legacy)
    rec("LIN.cycle_edge_legacy_len_eq_1",
        all(len(proj.get(e, {}).get("outcomes", [])) == 1 for e in cyc_legacy),
        {e: len(proj.get(e, {}).get("outcomes", [])) for e in cyc_legacy})
    res["LIN.cycle_edge_detail"] = {
        e: {"accepted_control": getattr((lc.get(e) or {}).get("accepted_control"),
                                        "kind", None),
            "accepted_outcome": getattr((lc.get(e) or {}).get("accepted_outcome"),
                                        "kind", None),
            "legacy_len": len(proj.get(e, {}).get("outcomes", [])),
            "control_conflicts": len((lc.get(e) or {}).get("control_conflicts", [])),
            "outcome_conflicts": len((lc.get(e) or {}).get("outcome_conflicts", [])),
            }
        for e in set(cyc_canonical) | set(cyc_legacy)}

    # --- test_J -------------------------------------------------------------
    # THE TEST'S OWN FORMULA: the message DELTA caused by the repair, over ALL
    # units. An earlier revision of this harness divided TOTAL messages and
    # reported ~65-77 against a ceiling of 12 in every mode INCLUDING head --
    # which would have been reported as a universal failure of a test that
    # passes. Reproducing an assertion means reproducing its arithmetic.
    amp = round((o.messages - msgs_before) / max(1, len(o.units)), 2)
    rec("J.amp_le_12", amp <= 12, amp)
    return res


def _run_case(density, role_cls, proj_only):
    """One fixture, one mode. Fresh organ, fresh counters, identical seeds."""
    _audit_reset()
    with mode(role_cls, proj_only):
        o, j, slot, victim, seed = _damaged(4, density=density)
        reset()
        before = o.messages
        o.run_item(PAYLOAD_B)
        out = _observe(o, j)
        out["seed"] = seed
        out["messages_before_repair"] = before
        out["repair_message_delta"] = o.messages - before
        out["assertions"] = _exact_assertions(o, before)
        out["audit"] = {k: v for k, v in AUDIT.items() if k != "records"}
        out["audit_sample"] = AUDIT["records"][:6]
        lc = getattr(o, "search_edge_lifecycle", {}) or {}
        out["lifecycle_conflicts_detail"] = {
            e: {"control": r["control_conflicts"], "outcome": r["outcome_conflicts"]}
            for e, r in lc.items()
            if r["control_conflicts"] or r["outcome_conflicts"]}
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
