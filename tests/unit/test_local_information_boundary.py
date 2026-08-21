"""The local-knowledge invariants. If these fail, Gate F's claim is false."""
from __future__ import annotations

import inspect

import pytest

from substrate import Cell, CellView, Interface, Signal, Tissue, Tri
from substrate.deficit import DeficitObserver
from evolution.repair.detector import SYMPTOM_KINDS

IF = Interface(provides="decide", accepts=("ingest",), emits=("emit",))


def cell(cid="decide.a"):
    return Cell(cell_id=cid, capability=cid, interface=IF)


def test_a_cell_view_exposes_only_local_state():
    """GLOBAL_SYSTEM_STATE_VISIBLE_TO_CELLS = false, asserted on the type."""
    allowed = {"own_capability", "own_interface", "neighbours", "inbox",
               "resource", "stress", "local_attachments"}
    assert set(CellView.__slots__) == allowed
    for bad in ("pool", "tissue", "contract", "target", "topology", "all_cells"):
        assert bad not in allowed


def test_a_cell_cannot_reach_the_capability_pool_or_the_tissue():
    c = cell()
    v = c.view()
    assert not hasattr(v, "pool")
    assert not hasattr(v, "tissue")
    assert not hasattr(c, "pool")
    assert not hasattr(c, "contract")


def test_a_signal_carries_a_role_and_a_sign_never_a_solution():
    s = Signal(role="decide", sign=Tri.ACTIVATE, intensity=0.5, ttl=3,
               origin="x", seq=0)
    fields = set(vars(s))
    assert fields == {"role", "sign", "intensity", "ttl", "origin", "seq"}
    for bad in ("capabilities", "topology", "candidate", "target", "plan"):
        assert bad not in fields


def test_the_tissue_restricts_each_cell_to_its_own_neighbours():
    a, b, c = cell("ingest.a"), cell("decide.a"), cell("emit.a")
    t = Tissue([a, b, c])
    t.connect("ingest.a", "decide.a")          # c is NOT connected
    seen = t._neighbour_interfaces(a)
    assert set(seen) == {"decide.a"}
    assert "emit.a" not in seen


def test_the_substrate_cannot_issue_authority():
    """FORMATION_COMPONENT_CAN_ISSUE_AUTHORITY = false."""
    import substrate
    # Exact names, not substrings: "Tissue" contains "issue" and is innocent.
    for bad in ("SigningProvider", "Ed25519SigningProvider", "AuthorityIssuer",
                "issue", "issue_authority", "sign", "certificate",
                "AuthorizationCertificate"):
        assert not hasattr(substrate, bad), f"substrate exposes {bad}"
    src = inspect.getsource(Tissue)
    assert "aperture" not in src.lower()
    assert "certificate" not in src.lower()


def test_the_tissue_never_reads_a_function_contract():
    src = inspect.getsource(Tissue)
    for bad in ("FunctionContract", "function_id", "contract"):
        assert bad not in src


def test_the_readout_runs_after_formation_and_changes_nothing():
    a, b = cell("ingest.a"), cell("decide.a")
    a.interface = Interface(provides="ingest", accepts=(), emits=("decide",))
    t = Tissue([a, b]); t.connect("ingest.a", "decide.a")
    t.inject("ingest.a", Signal("ingest", Tri.ACTIVATE, 1.0, 4, "field", 0))
    t.develop(max_ticks=10)
    before = {c.cell_id: (c.differentiated_role, c.attached_to)
              for c in t.cells.values()}
    t.precipitate(); t.precipitate()
    after = {c.cell_id: (c.differentiated_role, c.attached_to)
             for c in t.cells.values()}
    assert before == after


def test_inhibit_dominates_activate():
    """Without dominance the field oscillates and the tissue over-recruits."""
    c = cell()
    c.inbox = [Signal("decide", Tri.INHIBIT, 1.0, 3, "n1", 0),
               Signal("decide", Tri.ACTIVATE, 1.0, 3, "n2", 1)]
    c.step({}, {})
    assert c._role_field["decide"] is Tri.INHIBIT
    assert c.differentiated_role is None       # did not take a filled role


def test_ternary_hold_is_not_the_same_as_inhibit():
    """0 means HOLD. It must not silently behave as 'satisfied'."""
    assert Tri.HOLD == 0 and Tri.INHIBIT == -1 and Tri.ACTIVATE == 1
    assert Tri.HOLD is not Tri.INHIBIT


def test_duplicate_signals_are_suppressed():
    c = cell()
    s = Signal("decide", Tri.ACTIVATE, 1.0, 3, "n1", 7)
    c.inbox = [s, s, s]
    c.step({}, {})
    assert len(c.seen) == 1


def test_the_deficit_never_names_a_cure():
    d = DeficitObserver().observe(
        contract_id="function:f", required_roles=["ingest", "decide"],
        produced_outputs=0, expected_outputs=1, filled_roles=[],
        open_obligations=["ob:1"])
    assert d is not None
    assert d.leaks_a_solution() is False
    assert all(s.kind in SYMPTOM_KINDS for s in d.symptoms)


def test_no_deficit_when_nothing_is_wrong():
    d = DeficitObserver().observe(
        contract_id="f", required_roles=["a"], produced_outputs=1,
        expected_outputs=1, filled_roles=["a"], open_obligations=[])
    assert d is None
