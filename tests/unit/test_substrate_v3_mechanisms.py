"""Mechanism tests for the Phase 3E substrate (recursive conditional settlement).

Each test pins one Phase 3D proof defect, or one property of the new mechanism.
Where a defect is claimed removed, the test demonstrates the removal rather than
asserting it.
"""
from __future__ import annotations

import pytest

from substrate.v3 import (ENV, SINK, Capability, Cell3, ConstraintChannel, ExecutionTrace,
                          FunctionContract, MeasuredMotif, PARTITION_ISOLATION,
                          RESOURCE_EXHAUSTION, SEMANTIC_CORRUPTION, SUPPLIER_LOSS,
                          GLOBAL_SCAN_COUNTER, Tissue3, causal_form_key, damage_by_corruption,
                          diagnose, measure_phenotype, normalized_form, partition_around)

NORM = lambda s: str(s).strip().lower()
SUM = lambda s: f"sum:{len(s)}"
AGREE = lambda a, b: "ACCEPT" if a == b else "REJECT"
CONTRACT = FunctionContract("fn", "RAW", "VERDICT", lambda v: v.value == "ACCEPT")
PAYLOAD = "  Hello World  "


def chain(fam, domain=None, checker=SUM):
    d = domain or f"d.{fam}"
    return [Capability(f"n.{fam}", ("RAW",), "NORM", NORM, 1.0, d, "normalize"),
            Capability(f"c.{fam}", ("NORM",), "CHK", checker, 1.0, d, "check")]


def build(fams=("nu", "xi"), extra=(), checkers=None):
    caps = []
    for f in fams:
        caps += chain(f, checker=(checkers or {}).get(f, SUM))
    caps += list(extra) or [Capability("r", ("CHK", "CHK"), "VERDICT", AGREE,
                                       1.0, "d.r", "reconcile")]
    cells = [Cell3(cell_id=f"{c.klass()}.{i}", capability=c) for i, c in enumerate(caps)]
    t = Tissue3(cells, CONTRACT)
    ids = list(t.cells)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            t.connect(a, b)
    return t


# -- D1: execution is real --------------------------------------------------

def test_healthy_tissue_computes_a_real_semantic_output():
    t = build()
    t.demand()
    tr = t.execute(PAYLOAD)
    assert tr.output is not None
    assert tr.output.value == "ACCEPT"
    assert tr.invariant_held
    # A real transformation actually ran.
    assert any(v.value == "hello world" for v in tr.values.values())


def test_values_carry_provenance():
    t = build()
    t.demand()
    tr = t.execute(PAYLOAD)
    assert len(tr.output.parents) == 2, "a two-input join must record two parents"


def test_type_compatible_but_wrong_supplier_is_caught_by_the_invariant():
    """Phase 3D could not see this: structural closure is identical."""
    t = build(checkers={"xi": lambda s: "LIE"})
    t.demand()
    tr = t.execute(PAYLOAD)
    assert 0 in t.cells[SINK].bonds, "structure closed exactly as in the healthy case"
    assert tr.output.value == "REJECT"
    assert not tr.invariant_held


# -- the mechanism: recursive self-recruitment ------------------------------

def test_sink_asks_only_for_the_contract_output_and_the_chain_self_assembles():
    t = build()
    t.demand()
    root = t.cells[SINK].bonds[0].supplier
    rec = t.cells[root]
    assert rec.capability.produces == "VERDICT"
    assert rec.closed()
    for b in rec.bonds.values():
        up = t.cells[b.supplier]
        assert up.closed(), "a supplier bonded before its own prerequisites settled"


def test_settlement_recurses_below_the_boundary():
    t = build()
    t.demand()
    depth, frontier, seen = 0, [SINK], set()
    while frontier:
        nxt = []
        for cid in frontier:
            if cid in seen:
                continue
            seen.add(cid)
            nxt += [b.supplier for b in t.cells[cid].bonds.values()]
        if nxt:
            depth += 1
        frontier = nxt
    assert depth >= 4, f"expected nested settlement, got depth {depth}"


def test_a_supplier_with_unmet_prerequisites_does_not_bind():
    """The PENDING offer is what makes this a settlement, not a reply."""
    cap = Capability("r", ("CHK", "CHK"), "VERDICT", AGREE, 1.0, "d.r", "reconcile")
    c = Cell3(cell_id="r.0", capability=cap)
    assert not c.closed()
    assert c.missing_capability_classes() == ("CHK", "CHK")


def test_offer_type_is_checked_at_settlement():
    t = build()
    t.demand()
    for c in t.cells.values():
        for slot, b in c.bonds.items():
            assert b.delivered_type == c.capability.accepts[slot]


def test_one_supplier_may_not_fill_two_slots_of_a_join():
    t = build()
    t.demand()
    joins = [c for c in t.cells.values() if len(c.capability.accepts) > 1 and c.closed()]
    assert joins
    for j in joins:
        suppliers = [b.supplier for b in j.bonds.values()]
        assert len(set(suppliers)) == len(suppliers)


def test_loop_suppression_by_lineage_terminates_on_cyclic_affordances():
    extra = [Capability("up", ("NORM",), "MID", lambda v: f"w({v})", 1.0, "d.c", "up"),
             Capability("dn", ("MID",), "NORM", lambda v: v[2:-1], 1.0, "d.c", "down"),
             Capability("r", ("CHK", "CHK"), "VERDICT", AGREE, 1.0, "d.r", "reconcile")]
    t = build(extra=extra)
    t.demand()                      # must terminate
    assert t.ticks < 60


def test_development_performs_no_global_scan():
    before = GLOBAL_SCAN_COUNTER["n"]
    t = build()
    t.demand()
    assert GLOBAL_SCAN_COUNTER["n"] == before


# -- D3: the phenotype is measured ------------------------------------------

def test_phenotype_is_derived_from_evidence_not_declared():
    t = build()
    t.demand()
    tr = t.execute(PAYLOAD)
    ph = measure_phenotype(t, tr)
    assert ph["per_cell_resource_consumption"], "resource use must be measured"
    assert ph["actual_dependency_edges"], "edges must come from real bonds"
    for d in ph["verifier_independence"]:
        assert isinstance(d["suppliers_independent"], bool)
    # Nothing in the phenotype is one of Phase 3D's constants.
    assert "static" not in str(ph)
    assert "reassign" not in str(ph)


# -- D4: form identity is normalized ----------------------------------------

def test_renaming_cells_and_families_does_not_create_a_new_causal_form():
    a = build(fams=("nu", "xi"))
    b = build(fams=("aaa", "zzz"))
    a.demand(); b.demand()
    ta, tb = a.execute(PAYLOAD), b.execute(PAYLOAD)
    assert normalized_form(a, ta) == normalized_form(b, tb)
    assert causal_form_key(a, ta, measure_phenotype(a, ta)) == \
           causal_form_key(b, tb, measure_phenotype(b, tb))


# -- D2: diagnosis is blind --------------------------------------------------

def _traces(damage):
    t = build(fams=("nu", "xi", "om"))
    t.demand()
    h = t.execute(PAYLOAD)
    classes = {cid: c.capability.klass() for cid, c in t.cells.items()}
    victim = t.cells[SINK].bonds[0].supplier
    damage(t, victim)
    b = t.execute(PAYLOAD)
    return h, b, classes, victim, t


def test_diagnose_infers_supplier_loss_from_evidence_alone():
    h, b, classes, victim, t = _traces(lambda t, v: t.damage_supplier(v))
    d = diagnose(h, b, classes)
    assert d is not None
    assert d.causal_class == SUPPLIER_LOSS
    assert d.affected_capability_class == classes[victim]


def test_diagnose_infers_semantic_corruption_without_being_told():
    h, b, classes, victim, t = _traces(damage_by_corruption)
    d = diagnose(h, b, classes)
    assert d is not None
    assert d.causal_class == SEMANTIC_CORRUPTION


def test_diagnose_returns_none_when_the_function_still_holds():
    t = build()
    t.demand()
    h = t.execute(PAYLOAD)
    assert diagnose(h, t.execute(PAYLOAD),
                    {c: x.capability.klass() for c, x in t.cells.items()}) is None


def test_diagnostician_signature_takes_no_cause_label():
    import inspect
    params = set(inspect.signature(diagnose).parameters)
    assert params == {"healthy", "broken", "observed_classes"}
    for banned in ("cause", "partitioned", "resource_starved", "failed_role",
                   "expected", "ground_truth"):
        assert banned not in params


# -- D0: the constraint blocks an actual commit ------------------------------

def test_constraint_blocks_a_matching_commit_and_permits_otherwise():
    ch = ConstraintChannel()
    ch.receive(MeasuredMotif("reconcile", supplier_count=1))
    ok, _ = ch.permits(capability_class="reconcile", shares_domain=False,
                       supplier_count=1, paths_independent=True)
    assert ok is False
    ok2, _ = ch.permits(capability_class="reconcile", shares_domain=False,
                        supplier_count=2, paths_independent=True)
    assert ok2 is True, "the class must remain reachable in another configuration"


def test_disabled_channel_is_the_control_arm():
    ch = ConstraintChannel(enabled=False)
    ch.receive(MeasuredMotif("reconcile", supplier_count=1))
    ok, why = ch.permits(capability_class="reconcile", shares_domain=False,
                         supplier_count=1, paths_independent=True)
    assert ok is True and "disabled" in why


def test_motif_carries_no_target_or_ranking():
    m = MeasuredMotif("reconcile", supplier_count=1)
    blob = str(m.__dict__).lower()
    for banned in ("cell.", "@", "target", "prefer", "ranked", "use_"):
        assert banned not in blob


# -- the Phase 3E bottleneck, pinned as a failing-by-design property ---------

def test_interior_starvation_does_not_reopen_demand_KNOWN_BOTTLENECK():
    """Phase 3E's exact limit, recorded as executable evidence.

    Demand originates only at the boundary. An interior cell that loses a bond
    knows it is starved and can name what it is missing, but has no way to
    re-open its own need, so regeneration never starts. This is why Gate F
    scored 0/20 in run 2. It is pinned here rather than repaired, because
    repairing it and rescoring the same held-out fixtures is prohibited.
    """
    t = build(fams=("nu", "xi", "om"))
    t.demand()
    t.execute(PAYLOAD)
    interior = [c.cell_id for c in t.cells.values()
                if c.capability.klass() == "normalize"][0]
    t.damage_supplier(interior)
    starved = [c.cell_id for c in t.cells.values()
               if not c.dissolved and c.unmet_slots() and c.cell_id != ENV]
    assert starved, "some interior cell must now be starved"
    assert t.cells[SINK].unmet_slots() == (), "the boundary is still satisfied"
    before = t.messages
    t.demand()
    assert t.messages == before, (
        "BOTTLENECK: demand() emits nothing because only SINK can originate a "
        "need; the starved interior cells cannot re-open their own")
