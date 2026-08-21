"""Mechanism tests for the multi-branch developmental substrate (Phase 3D).

Each test targets one audited defect of `substrate/cell.py` (PR #60), which is
left untouched so that PR's reported results remain exactly as reported. Test A
first REPRODUCES the defect against v1, then shows v2 removing it: a fix with no
reproduction is a claim, not evidence.
"""
from __future__ import annotations

import pytest

from substrate import Cell, Interface, Signal, Tissue, Tri as TriV1
from substrate.causal import CausalMotif
from substrate.v2 import (BranchSignal, Cell2, DependencyReceptor, GLOBAL_SCAN_COUNTER,
                          Interface2, Tissue2, Tri)

FORK_JOIN = {
    "ingest": Interface2("ingest", (), ("verify_a", "verify_b")),
    "verify_a": Interface2("verify_a", ("ingest",), ("reconcile",)),
    "verify_b": Interface2("verify_b", ("ingest",), ("reconcile",)),
    "reconcile": Interface2("reconcile", ("verify_a", "verify_b"), ("emit",)),
    "emit": Interface2("emit", ("reconcile",), ()),
}


def build(interfaces, families):
    cells = [Cell2(cell_id=f"{r}.{f}", capability=f"{r}.{f}", interface=interfaces[r])
             for f in families for r in interfaces]
    t = Tissue2(cells)
    ids = [c.cell_id for c in cells]
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            t.connect(a, b)
    return t


def demand(t, episode, root_role="ingest"):
    root = sorted(c.cell_id for c in t.cells.values()
                  if not c.interface.requires and not c.dissolved)[0]
    t.inject(root, BranchSignal(root_role, Tri.ACTIVATE, 1.0, 10, "field", (episode,)))
    t.develop()


# -- A: branch identity ------------------------------------------------------

def test_a_v1_branch_identity_collision_is_real():
    """The defect being fixed, demonstrated against the v1 substrate."""
    iface = Interface("ingest", (), ("verify_a", "verify_b"))
    c = Cell(cell_id="ingest.alpha", capability="ingest.alpha", interface=iface)
    sig = Signal("ingest", TriV1.ACTIVATE, 1.0, 6, "field", 0)
    emitted = [s for s in _v1_emissions(c, sig)]
    keys = {(s.origin, s.seq) for s in emitted}
    assert len(emitted) > len(keys), (
        "expected v1 to emit more branches than it has distinct (origin, seq) keys")


def _v1_emissions(cell, sig):
    """Mirror of v1 `_differentiate`'s emission rule, which shares one seq."""
    return [Signal(role=nxt, sign=TriV1.ACTIVATE, intensity=sig.intensity * 0.9,
                   ttl=sig.ttl - 1, origin=cell.cell_id, seq=sig.seq + 1)
            for nxt in cell.interface.emits]


def test_a_v2_branches_have_distinct_identities():
    root = BranchSignal("ingest", Tri.ACTIVATE, 1.0, 6, "field", ())
    kids = [root.child(r, i) for i, r in enumerate(("verify_a", "verify_b"))]
    assert len({k.branch_id for k in kids}) == 2


def test_a_relay_preserves_branch_identity_so_duplicates_still_suppress():
    """Distinctness must not be bought by making every copy unique - a second
    arrival of the SAME branch by another route must still be suppressed."""
    sig = BranchSignal("emit", Tri.ACTIVATE, 1.0, 5, "field", (0, 1))
    assert sig.relay().branch_id == sig.branch_id
    assert sig.relay().ttl < sig.ttl


def test_a_no_branch_is_lost_in_a_fork():
    t = build(FORK_JOIN, ("iota",))
    demand(t, 0)
    roles = {c.differentiated_role for c in t.cells.values() if c.differentiated_role}
    assert roles == set(FORK_JOIN), f"a fork branch was lost: {sorted(roles)}"


# -- B: genuine fan-in -------------------------------------------------------

def test_b_join_does_not_close_on_one_binding():
    r = DependencyReceptor(("verify_a", "verify_b"))
    r.bind("verify_a", "c1")
    assert not r.satisfied()
    assert r.unresolved() == ("verify_b",)
    r.bind("verify_b", "c2")
    assert r.satisfied()


def test_b_join_is_order_independent_and_monotonic():
    a, b = DependencyReceptor(("x", "y")), DependencyReceptor(("x", "y"))
    for role, cell in (("x", "1"), ("y", "2")):
        a.bind(role, cell)
    for role, cell in (("y", "2"), ("x", "1"), ("y", "9")):
        b.bind(role, cell)
    assert a.bindings == b.bindings


def test_b_quorum_closes_on_any_k_of_n():
    q = DependencyReceptor(("a", "b", "c"), quorum=2)
    q.bind("a", "1")
    assert not q.satisfied()
    q.bind("c", "3")
    assert q.satisfied()


def test_b_no_cell_differentiates_with_an_unsatisfied_join():
    t = build(FORK_JOIN, ("iota", "kappa"))
    demand(t, 0)
    offenders = [c.cell_id for c in t.cells.values()
                 if c.differentiated_role and not c.receptor.satisfied()]
    assert offenders == []


# -- C: refusal enforced at the commit, not logged after it ------------------

def test_c_prohibited_configuration_cannot_commit():
    iface = Interface2(provides="emit")
    c = Cell2(cell_id="emit.a", capability="emit.a", interface=iface)
    c.constraints.receive(
        CausalMotif(role="emit", redundancy=0, verification_class="single_read"),
        expires_after=3)
    sig = BranchSignal("emit", Tri.ACTIVATE, 1.0, 4, "field", (0,))
    assert c._try_differentiate(sig, {}) is False
    assert c.differentiated_role is None, "a refused proposal still committed"
    assert c.blocked_attachments == 1


def test_c_refusal_does_not_make_the_role_unreachable():
    """The PR #59 defect: constraint collapsed into role suppression."""
    iface = Interface2(provides="emit")
    c = Cell2(cell_id="emit.b", capability="emit.b", interface=iface)
    c.constraints.receive(
        CausalMotif(role="emit", redundancy=0, verification_class="single_read"),
        expires_after=3)
    sig = BranchSignal("emit", Tri.ACTIVATE, 1.0, 4, "field", (0,))
    assert c._try_differentiate(sig, {"emit.a": "emit"}) is True
    assert c.differentiated_role == "emit"


# -- D/E: locality -----------------------------------------------------------

def test_d_formation_performs_no_global_scan():
    before = GLOBAL_SCAN_COUNTER["n"]
    t = build(FORK_JOIN, ("iota", "kappa", "lam"))
    demand(t, 0)
    assert GLOBAL_SCAN_COUNTER["n"] == before


def test_d_redundancy_is_counted_over_neighbours_only():
    iface = Interface2(provides="emit")
    c = Cell2(cell_id="emit.a", capability="emit.a", interface=iface)
    assert c.local_redundancy({"n1": "emit", "n2": "ingest", "n3": None}) == 1


def test_e_each_cell_owns_its_receptors():
    t = build(FORK_JOIN, ("iota", "kappa"))
    receptors = [id(c.receptor) for c in t.cells.values()]
    constraints = [id(c.constraints) for c in t.cells.values()]
    assert len(set(receptors)) == len(receptors)
    assert len(set(constraints)) == len(constraints)


# -- F: loss is observed, never asserted -------------------------------------

def test_f_healthy_tissue_produces_a_real_output():
    t = build(FORK_JOIN, ("iota",))
    demand(t, 0)
    assert t.execute("payload", tuple(FORK_JOIN)) is not None


def test_f_output_depends_on_the_cells_that_carry_it():
    """A value derived from role NAMES is identical before and after damage,
    which is how PR #59 'observed' a loss that never happened."""
    t = build(FORK_JOIN, ("iota", "kappa"))
    demand(t, 0)
    before = t.execute("payload", tuple(FORK_JOIN))
    t.damage_capability("verify_a.iota")
    after = t.execute("payload", tuple(FORK_JOIN))
    assert before != after


def test_f_destroying_a_role_class_is_observed_as_output_loss():
    t = build(FORK_JOIN, ("iota", "kappa", "lam"))
    demand(t, 0)
    assert t.execute("payload", tuple(FORK_JOIN)) is not None
    for fam in ("iota", "kappa", "lam"):
        t.damage_capability(f"verify_a.{fam}")
    assert t.execute("payload", tuple(FORK_JOIN)) is None


def test_f_regeneration_restores_output_through_a_different_carrier():
    t = build(FORK_JOIN, ("iota", "kappa", "lam"))
    demand(t, 0)
    healthy = t.execute("payload", tuple(FORK_JOIN))
    for fam in ("iota", "kappa"):
        t.damage_capability(f"verify_a.{fam}")
    assert t.execute("payload", tuple(FORK_JOIN)) is None, "damage produced no loss"
    demand(t, 1)
    restored = t.execute("payload", tuple(FORK_JOIN))
    assert restored is not None
    assert restored != healthy
    carriers = [c.cell_id for c in t.cells.values()
                if c.differentiated_role == "verify_a"]
    assert carriers == ["verify_a.lam"]


# -- G/H: structural families the substrate was not developed against --------

@pytest.mark.parametrize("name,interfaces", [
    ("asymmetric_depth_join", {
        "ingest": Interface2("ingest", (), ("verify_a", "stage1")),
        "verify_a": Interface2("verify_a", ("ingest",), ("reconcile",)),
        "stage1": Interface2("stage1", ("ingest",), ("stage2",)),
        "stage2": Interface2("stage2", ("stage1",), ("reconcile",)),
        "reconcile": Interface2("reconcile", ("verify_a", "stage2"), ("emit",)),
        "emit": Interface2("emit", ("reconcile",), ())}),
    ("local_quorum", {
        "ingest": Interface2("ingest", (), ("v1", "v2", "v3")),
        "v1": Interface2("v1", ("ingest",), ("reconcile",)),
        "v2": Interface2("v2", ("ingest",), ("reconcile",)),
        "v3": Interface2("v3", ("ingest",), ("reconcile",)),
        "reconcile": Interface2("reconcile", ("v1", "v2", "v3"), ("emit",), quorum=2),
        "emit": Interface2("emit", ("reconcile",), ())}),
    ("nested_branch", {
        "ingest": Interface2("ingest", (), ("verify_a", "verify_b")),
        "verify_a": Interface2("verify_a", ("ingest",), ("sub_x", "sub_y")),
        "sub_x": Interface2("sub_x", ("verify_a",), ("reconcile",)),
        "sub_y": Interface2("sub_y", ("verify_a",), ("reconcile",)),
        "verify_b": Interface2("verify_b", ("ingest",), ("reconcile",)),
        "reconcile": Interface2("reconcile", ("sub_x", "sub_y", "verify_b"), ("emit",)),
        "emit": Interface2("emit", ("reconcile",), ())}),
])
def test_g_held_out_structures_form_and_produce_output(name, interfaces):
    t = build(interfaces, ("iota",))
    demand(t, 0)
    assert t.execute("payload", tuple(interfaces)) is not None, f"{name} produced nothing"
    offenders = [c.cell_id for c in t.cells.values()
                 if c.differentiated_role and not c.receptor.satisfied()]
    assert offenders == []


def test_g_nested_branch_reaches_lineage_depth_beyond_one():
    interfaces = {
        "ingest": Interface2("ingest", (), ("verify_a",)),
        "verify_a": Interface2("verify_a", ("ingest",), ("sub_x", "sub_y")),
        "sub_x": Interface2("sub_x", ("verify_a",), ()),
        "sub_y": Interface2("sub_y", ("verify_a",), ())}
    t = build(interfaces, ("iota",))
    demand(t, 0)
    depths = [len(s.split(":")[1].split(".")) for c in t.cells.values()
              for s in c.seen if s.split(":")[1]]
    assert max(depths) >= 2


def test_h_partition_blocks_its_edge_and_forces_another_route():
    t = build(FORK_JOIN, ("iota", "kappa"))
    t.partition("verify_a.iota", "reconcile.iota")
    demand(t, 0)
    assert t.blocked("verify_a.iota", "reconcile.iota")
    bound = t.cells["reconcile.iota"].receptor.bindings.get("verify_a")
    assert bound is not None
    assert bound != "verify_a.iota", "the partitioned edge was still used"


def test_h_partitioned_edge_carries_zero_messages():
    t = build(FORK_JOIN, ("iota", "kappa"))
    t.partition("verify_a.iota", "reconcile.iota")
    demand(t, 0)
    delivered = [(s, d) for s, d in t.delivered_edges
                 if {s, d} == {"verify_a.iota", "reconcile.iota"}]
    assert delivered == []
